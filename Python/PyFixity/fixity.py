# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fixity for a directory tree: checksums made in one read, kept current, and re-read later.

"Fixity" is the digital-preservation word for evidence that content has not changed: fixity
information (checksums) is recorded once, and fixity checks re-read the content against it to
catch silent damage. This module is that, for one directory tree, and nothing else. It needs
neither the network nor a third-party package, and `fixity_test.py` covers it.

ONE READ, FOUR DIGESTS. SHA-256 is the strong one; SHA-1, MD5 and CRC32 exist because somebody
else speaks them -- Backblaze B2 records a SHA-1, the Internet Archive publishes MD5, RAR and ZIP
store a CRC32 per member. Reading a file four times would cost four passes over a disk that is the
bottleneck anyway; computing all four in one pass costs CPU that the disk leaves idle. When the
part sizes of an S3 multipart upload are known, the same pass also yields its ETag (the MD5 of the
part MD5s), so a cloud copy without a whole-file checksum can still be compared.

TWO RECORDS, KEPT APART ON PURPOSE.

    the INDEX       one CSV per tree: size, mtime, all digests, part sizes, ETag, last check.
                    Columns path,size,mtime_ns,sha256 come first and are named as PyMirror's
                    index names them, so readers of that format read this one unchanged.
                    It changes on every check (the "last checked" time), so it belongs in a
                    state directory, not in the tree that gets uploaded.
    the MANIFESTS   .sha256sum .sha1sum .md5sum .sfv at the root of the tree, in the formats
                    sha256sum(1), sha1sum(1), md5sum(1) and RHash/QuickSFV write. OpenHashTab
                    and TeraCopy read them without being told anything. They change only when
                    content changes, so uploading them with the tree costs nothing per check.

NO FILE DESCRIBES ITSELF. The four manifests, the index and its state file are never listed in a
manifest; a manifest that contained its own checksum could never be correct. The index, which
lives elsewhere, may list the manifests -- that is how a cloud copy of them can be checked too.
"""
from __future__ import annotations

import csv
import fnmatch
import hashlib
import ntpath
import os
import re
import threading
import time
import unicodedata
import zlib
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Iterator, TypeVar

READ_CHUNK = 1024 * 1024
# How often a long run writes its index, so an interruption loses at most this much work.
SAVE_INTERVAL = 30
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
YES = "yes"
INCOMPLETE = "no (interrupted, partial)"

DIGESTS = ("sha256", "sha1", "md5", "crc32")
# algorithm -> manifest file name. The names are the tools' own, and the same as PyMirror's.
MANIFEST_FILES = {"sha256": ".sha256sum", "sha1": ".sha1sum", "md5": ".md5sum", "crc32": ".sfv"}
DEFAULT_INDEX = ".fixity-index.csv"
INDEX_COLUMNS = ["path", "size", "mtime_ns", "sha256", "sha1", "md5", "crc32", "etag", "parts", "verified"]


def now_ts() -> str:
    return datetime.now().strftime(TS_FORMAT)


def norm(name: str) -> str:
    """NFC, because the same visible name can arrive composed from one source and decomposed from
    another, and two spellings of one name would show up as one file missing on each side."""
    return unicodedata.normalize("NFC", name)


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def is_excluded(rel_path: str, patterns: Iterable[str]) -> bool:
    """Permanent exclusions: glob patterns on the relative path or on the file name."""
    return any(fnmatch.fnmatch(rel_path, p) or fnmatch.fnmatch(basename(rel_path), p) for p in patterns)


# --------------------------------------------------------------------------- long paths

LONG_PREFIX = "\\\\?\\"


def long_path(path: str | os.PathLike, windows: bool = os.name == "nt") -> str:
    r"""-> the path with the `\\?\` prefix on Windows, unchanged elsewhere.

    WITHOUT IT WINDOWS REFUSES PATHS OF 260 CHARACTERS AND MORE, unless LongPathsEnabled is set
    for the whole machine -- a setting of the computer, not of this tool, and one that a fresh
    installation or another account does not have. The prefix needs an absolute path with
    backslashes; a UNC path becomes `\\?\UNC\server\share`. Applying it twice changes nothing.
    """
    text = os.fspath(path)
    if not windows or text.startswith(LONG_PREFIX):
        return text
    text = ntpath.abspath(text) if os.name == "nt" else ntpath.normpath(text)
    if text.startswith("\\\\"):
        return LONG_PREFIX + "UNC\\" + text[2:]
    return LONG_PREFIX + text


# --------------------------------------------------------------------------- selection

_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([KMGT]?)(?:I?B)?\s*$", re.IGNORECASE)


def parse_size(text: str) -> int:
    """'500' -> 500, '64K' -> 65536, '1M' / '1MB' / '1MiB' -> 1048576, '1.5G'. Base 1024."""
    m = _SIZE_RE.match(text)
    if not m:
        raise ValueError(f"not a size: {text!r} (examples: 500, 64K, 1M, 1.5G)")
    number, unit = m.groups()
    exponent = "KMGT".index(unit.upper()) + 1 if unit else 0
    return int(float(number) * 1024 ** exponent)


@dataclass
class FileFilter:
    """Which files one run looks at: the path by regex, positive and negative, and a size range.

    One regex mechanism covers folders (`^Recordings/`), file names (`(^|/)serial\\.txt$`) and
    extensions (`\\.mp4$`). Matched with re.search, ignoring case. include: at least one must
    match (none = everything); exclude: none may match and wins. min_size inclusive, max_size
    exclusive, so `--max-size 1M` and `--min-size 1M` split a tree exactly.
    """
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    min_size: int | None = None
    max_size: int | None = None

    def __post_init__(self) -> None:
        self._include = [re.compile(p, re.IGNORECASE) for p in self.include]
        self._exclude = [re.compile(p, re.IGNORECASE) for p in self.exclude]

    def matches(self, path: str, size: int) -> bool:
        if self.min_size is not None and size < self.min_size:
            return False
        if self.max_size is not None and size >= self.max_size:
            return False
        if self._include and not any(r.search(path) for r in self._include):
            return False
        return not any(r.search(path) for r in self._exclude)

    def apply(self, entries: list) -> list:
        return [e for e in entries if self.matches(e.path, e.size)]

    def active(self) -> bool:
        return bool(self.include or self.exclude or self.min_size is not None or self.max_size is not None)

    def describe(self) -> str:
        parts = [f"include '{p}'" for p in self.include] + [f"exclude '{p}'" for p in self.exclude]
        if self.min_size is not None:
            parts.append(f">= {fmt_size(self.min_size)}")
        if self.max_size is not None:
            parts.append(f"< {fmt_size(self.max_size)}")
        return ", ".join(parts) or "all files"


# --------------------------------------------------------------------------- data model

@dataclass
class Entry:
    path: str  # relative path with '/'
    size: int
    mtime_ns: int
    sha256: str | None = None
    sha1: str | None = None
    md5: str | None = None
    crc32: str | None = None  # eight upper-case hex digits, as every .sfv writes it
    etag: str | None = None  # S3 ETag: an MD5, or "<md5 of the part md5s>-<part count>"
    parts: list[int] | None = None  # the part sizes that belong to the ETag
    verified: str = ""  # last successful read-and-compare (TS_FORMAT); empty = never, or failed
    abs_path: Path | None = None  # not stored
    skipped: bool = False  # verification run: not read this time; not stored

    def has_all_digests(self) -> bool:
        return all(getattr(self, name) for name in DIGESTS)

    def set_digests(self, digests: dict[str, str]) -> None:
        for name, value in digests.items():
            setattr(self, name, value)

    def digests(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in DIGESTS if getattr(self, name)}


@dataclass(frozen=True)
class Labels:
    left: str
    right: str
    only_left: str
    only_right: str


NOW_VS_SAVED = Labels("Current", "Saved", "New (not in the index)", "Gone (only in the index)")


@dataclass
class Diff:
    flat: bool
    labels: Labels = NOW_VS_SAVED
    only_left: list = field(default_factory=list)
    only_right: list = field(default_factory=list)
    size: list = field(default_factory=list)
    mtime: list = field(default_factory=list)
    checksum: list = field(default_factory=list)
    checksum_unknown: list = field(default_factory=list)
    errors: list = field(default_factory=list)  # read or download errors
    ok: dict[str, int] = field(default_factory=dict)  # digest used -> files that matched by it
    skipped: int = 0
    notes: dict[str, str] = field(default_factory=dict)  # path -> remark
    duplicates: list = field(default_factory=list)
    left_count: int = 0
    right_count: int = 0

    @property
    def identical(self) -> int:
        return sum(self.ok.values())

    def has_differences(self) -> bool:
        return bool(self.only_left or self.only_right or self.size or self.mtime
                    or self.checksum or self.duplicates or self.errors)

    def attach_errors(self, errors: dict[str, str]) -> None:
        """A file that could not be read is an ERROR, not merely 'not checkable'."""
        keep = []
        for left, right in self.checksum_unknown:
            if left.path in errors:
                self.errors.append((left, right))
                self.notes[left.path] = errors[left.path]
            else:
                keep.append((left, right))
        self.checksum_unknown = keep


# --------------------------------------------------------------------------- parts, ETag, hashing

def encode_parts(parts: list[int] | None) -> str:
    """[100, 100, 43] -> '100*2,43'"""
    if not parts:
        return ""
    out, i = [], 0
    while i < len(parts):
        j = i
        while j < len(parts) and parts[j] == parts[i]:
            j += 1
        out.append(f"{parts[i]}*{j - i}" if j - i > 1 else str(parts[i]))
        i = j
    return ",".join(out)


def decode_parts(text: str | None) -> list[int] | None:
    if not text:
        return None
    parts: list[int] = []
    for item in text.split(","):
        size, _, count = item.partition("*")
        parts.extend([int(size)] * int(count or 1))
    return parts


def is_multipart_etag(etag: str) -> bool:
    return "-" in etag


def crc32_text(value: int) -> str:
    """A CRC32 as the eight upper-case hex digits every .sfv in the wild uses."""
    return "%08X" % (value & 0xFFFFFFFF)


class Cancelled(Exception):
    """The run was interrupted (Ctrl+C)."""


class StreamHasher:
    """All digests in one pass and, when part sizes are known, the S3 ETag too.

    Chunk boundaries of the incoming data are arbitrary (a file, a network stream). If the amount
    of data does not fit the part sizes exactly, the ETag is None rather than a wrong value.
    """

    def __init__(self, parts: list[int] | None = None, multipart: bool = False,
                 want: Iterable[str] = DIGESTS) -> None:
        want = tuple(want)
        self._hashes = {name: hashlib.new(name) for name in want if name != "crc32"}
        self._crc = 0 if "crc32" in want else None
        self.size = 0
        self._parts = parts or []
        self._multipart = multipart
        self._index = 0
        self._left = self._parts[0] if self._parts else 0
        self._md5 = hashlib.md5()
        self._part_digests: list[bytes] = []
        self._overflow = False

    def update(self, data: bytes) -> None:
        for h in self._hashes.values():
            h.update(data)
        if self._crc is not None:
            self._crc = zlib.crc32(data, self._crc)
        self.size += len(data)
        if not self._parts or self._overflow:
            return
        view = memoryview(data)
        while view:
            if self._index >= len(self._parts):
                self._overflow = True
                return
            take = min(len(view), self._left)
            self._md5.update(view[:take])
            self._left -= take
            view = view[take:]
            if self._left == 0:
                self._part_digests.append(self._md5.digest())
                self._index += 1
                if self._index < len(self._parts):
                    self._left = self._parts[self._index]
                    self._md5 = hashlib.md5()

    def result(self) -> tuple[dict[str, str], str | None]:
        digests = {name: h.hexdigest() for name, h in self._hashes.items()}
        if self._crc is not None:
            digests["crc32"] = crc32_text(self._crc)
        if not self._parts or self._overflow or self._index != len(self._parts):
            return digests, None
        if self._multipart:
            etag = f"{hashlib.md5(b''.join(self._part_digests)).hexdigest()}-{len(self._part_digests)}"
        else:
            etag = self._part_digests[0].hex()
        return digests, etag


def hash_chunks(chunks: Iterable[bytes], parts: list[int] | None = None, multipart: bool = False,
                stop: threading.Event | None = None,
                want: Iterable[str] = DIGESTS) -> tuple[dict[str, str], str | None, int]:
    """Hash a byte stream (file or download) -> (digests, etag, bytes seen). Closes the stream."""
    h = StreamHasher(parts, multipart, want)
    try:
        for chunk in chunks:
            if stop is not None and stop.is_set():
                raise Cancelled()
            h.update(chunk)
    finally:
        close = getattr(chunks, "close", None)
        if close:
            close()
    digests, etag = h.result()
    return digests, etag, h.size


def read_file_chunks(path: str | os.PathLike, chunk_size: int = READ_CHUNK) -> Iterator[bytes]:
    with open(long_path(path), "rb") as f:
        yield from iter(lambda: f.read(chunk_size), b"")


def hash_file(path: str | os.PathLike, parts: list[int] | None = None, multipart: bool = False,
              want: Iterable[str] = DIGESTS) -> tuple[dict[str, str], str | None]:
    digests, etag, _size = hash_chunks(read_file_chunks(path), parts, multipart, want=want)
    return digests, etag


# --------------------------------------------------------------------------- the tree

def own_files(root: Path, index_path: Path | None = None) -> set[str]:
    """Relative paths at the root of the tree that belong to this tool and are never content."""
    own = set(MANIFEST_FILES.values()) | {DEFAULT_INDEX, DEFAULT_INDEX + ".state"}
    if index_path is not None:
        try:
            rel = Path(index_path).resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            rel = None
        if rel:
            own |= {rel, rel + ".state", rel + ".tmp"}
    own |= {name + ".tmp" for name in MANIFEST_FILES.values()}
    return own


def scan_tree(root: Path, excludes: Iterable[str] = (), skip: Iterable[str] = ()) -> list[Entry]:
    """Every file below root, sorted by relative path, without the permanent exclusions and
    without `skip` (relative paths, normally own_files()).

    Walked through the long path, so files deeper than 259 characters are found and can be read.
    """
    excludes, skip = list(excludes), set(skip)
    base = long_path(root)
    files: list[Entry] = []
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = norm(os.path.relpath(full, base).replace(os.sep, "/"))
            if rel in skip or is_excluded(rel, excludes):
                continue
            st = os.stat(full)
            files.append(Entry(rel, st.st_size, st.st_mtime_ns, abs_path=Path(full)))
    return sorted(files, key=lambda e: e.path)


# --------------------------------------------------------------------------- the index

def write_index(path: Path, entries: list[Entry]) -> None:
    """CSV, written to a temporary name and renamed, so an interruption never leaves a half-written
    index that still looks complete."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(long_path(tmp), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(INDEX_COLUMNS)
        for e in sorted(entries, key=lambda x: x.path):
            w.writerow([e.path, e.size, e.mtime_ns, e.sha256 or "", e.sha1 or "", e.md5 or "",
                        e.crc32 or "", e.etag or "", encode_parts(e.parts), e.verified])
    os.replace(long_path(tmp), long_path(path))


def read_index(path: Path) -> list[Entry]:
    """Read an index. Columns beyond path,size,mtime_ns are optional, so a PyMirror index
    (path,size,mtime_ns,sha256) reads as one whose other digests are simply not known yet."""
    if not Path(path).is_file():
        return []
    entries = []
    with open(long_path(path), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            entries.append(Entry(r["path"], int(r["size"]), int(r["mtime_ns"]),
                                 r.get("sha256") or None, r.get("sha1") or None, r.get("md5") or None,
                                 r.get("crc32") or None, r.get("etag") or None,
                                 decode_parts(r.get("parts")), r.get("verified") or ""))
    return entries


def state_path(index_path: Path) -> Path:
    return index_path.with_name(index_path.name + ".state")


def read_state(index_path: Path) -> dict[str, str]:
    """Run state beside the index (created, complete, verify_start, verify_complete), `key: value`."""
    p = state_path(index_path)
    if not p.is_file():
        return {}
    state = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            state[key.strip()] = value.strip()
    return state


def write_state(index_path: Path, state: dict[str, str]) -> None:
    p = state_path(index_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("".join(f"{k}: {v}\n" for k, v in state.items()), encoding="utf-8")
    os.replace(tmp, p)


class IndexSaver:
    """Writes index and state at intervals, so an interruption loses at most one interval.

    complete_key: the state key that becomes 'yes' at the end, or 'no' when interrupted.
    keep: which entries are written (for example only those already hashed).
    """

    def __init__(self, index_path: Path, state: dict[str, str], entries: list[Entry],
                 complete_key: str = "complete", keep: Callable[[Entry], object] = lambda e: True,
                 interval: float = SAVE_INTERVAL) -> None:
        self.index_path, self.state, self.entries = index_path, state, entries
        self.complete_key, self.keep, self.interval = complete_key, keep, interval
        self.last = time.monotonic()

    def maybe_save(self) -> None:
        if time.monotonic() - self.last > self.interval:
            self.save(complete=False)

    def save(self, complete: bool) -> None:
        self.state[self.complete_key] = YES if complete else INCOMPLETE
        write_index(self.index_path, [e for e in self.entries if self.keep(e)])
        write_state(self.index_path, self.state)
        self.last = time.monotonic()


# --------------------------------------------------------------------------- manifests

def sums_line(digest: str, rel: str) -> str:
    """One line of sha256sum(1)/sha1sum(1)/md5sum(1) output, in binary mode (`*`).

    GNU escapes a path containing a backslash or a newline by prefixing the line with one
    backslash; neither can occur in a Windows file name, but the format stays correct anyway.
    """
    if "\\" in rel or "\n" in rel:
        return "\\%s *%s\n" % (digest, rel.replace("\\", "\\\\").replace("\n", "\\n"))
    return "%s *%s\n" % (digest, rel)


def sfv_line(crc: str, rel: str) -> str:
    """One line of an .sfv: `<name> <CRC32>` -- the columns the OTHER way round from sha256sum,
    which is why a reader must split from the right."""
    return "%s %s\n" % (rel, crc)


def manifest_text(entries: list[Entry], algo: str) -> str | None:
    """The full text of one manifest, or None when any file lacks that digest.

    A manifest that silently leaves files out reads as a complete check that was made, so a
    partial one is not written at all; neither is an empty one, because `md5sum -c` over zero
    lines reports success."""
    if not entries or any(not getattr(e, algo) for e in entries):
        return None
    line = sfv_line if algo == "crc32" else sums_line
    return "".join(line(getattr(e, algo), e.path) for e in sorted(entries, key=lambda x: x.path))


def write_manifests(root: Path, entries: list[Entry], want: Iterable[str] = DIGESTS) -> dict[str, str]:
    """Write the manifests at the root of the tree -> {file name: what happened}.

    A MANIFEST IS REWRITTEN ONLY WHEN ITS TEXT CHANGES. Re-checking a tree must not produce new
    manifests, or every check would hand a sync tool a fresh version to upload.
    """
    result = {}
    for algo in want:
        name = MANIFEST_FILES[algo]
        target = Path(root) / name
        text = manifest_text(entries, algo)
        if text is None:
            result[name] = "not written (a digest is missing)"
            continue
        current = None
        if os.path.isfile(long_path(target)):
            with open(long_path(target), encoding="utf-8", newline="") as f:
                current = f.read()
        if current == text:
            result[name] = "unchanged"
            continue
        tmp = target.with_name(name + ".tmp")
        with open(long_path(tmp), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(long_path(tmp), long_path(target))
        result[name] = "written"
    return result


def read_sums(path: Path) -> dict[str, str]:
    """-> {relative path: digest} from a sha*sum/md5sum file. The split is on the FIRST ` *`,
    because a path may contain spaces. GNU-escaped lines are skipped rather than guessed at."""
    out = {}
    if not os.path.isfile(long_path(path)):
        return out
    with open(long_path(path), encoding="utf-8", newline="") as f:
        for line in f.read().splitlines():
            if not line or line.startswith("\\"):
                continue
            digest, sep, rel = line.partition(" *")
            if sep:
                out[rel] = digest
    return out


def looks_like_a_crc32(text: str) -> bool:
    """-> True for exactly eight hex digits, which is what every .sfv writes."""
    return len(text) == 8 and all(c in "0123456789abcdefABCDEF" for c in text)


def read_sfv(path: Path) -> dict[str, str]:
    """-> {relative path: CRC32} from an .sfv. Split from the RIGHT.

    `;` STARTS A COMMENT, AND A FILE NAME MAY START WITH `;`. The format has no escape for that --
    it is `<name> <CRC32>` and nothing else -- so a line beginning with `;` is ambiguous, and
    skipping all of them made a real file vanish from the manifest without a word. Found by a test
    on 2026-10-09, after the same class of defect (a path containing the format's own delimiter)
    had been found unescaped in PyMirror's index CSV for 4 476 real paths.

    SO A LEADING `;` IS A COMMENT ONLY WHEN THE LINE DOES NOT END IN A CRC32. The failure modes
    are not symmetric: a dropped entry is silent, while a comment misread as an entry shows up in
    the next `verify` run as a file that is listed and not there. Loud beats silent. A comment
    whose last word is exactly eight hex digits is the one case this gets wrong, and it announces
    itself.
    """
    out = {}
    if not os.path.isfile(long_path(path)):
        return out
    with open(long_path(path), encoding="utf-8", newline="") as f:
        for line in f.read().splitlines():
            if not line:
                continue
            rel, sep, crc = line.rpartition(" ")
            if not sep:
                continue
            if line.startswith(";") and not looks_like_a_crc32(crc):
                continue
            out[rel] = crc.upper()
    return out


# --------------------------------------------------------------------------- comparison

def make_index(entries: list, flat: bool) -> dict[str, list]:
    idx: dict[str, list] = {}
    for e in entries:
        idx.setdefault(basename(e.path) if flat else e.path, []).append(e)
    return idx


def checksums_match(a, b) -> tuple[bool | None, str | None]:
    """-> (match, digest used). By the strongest digest both sides have, else by ETag over the
    same part sizes; (None, None) when nothing is comparable. A size difference never matches."""
    if a.size != b.size:
        return False, "size"
    for name in DIGESTS:
        x, y = getattr(a, name, None), getattr(b, name, None)
        if x and y:
            return x.lower() == y.lower(), name
    if a.etag and b.etag and a.parts == b.parts:
        return a.etag == b.etag, "etag"
    return None, None


def compare(left: list, right: list, flat: bool = False, check_mtime: bool = False,
            check_sum: bool = False, mtime_tolerance_ns: int = 2_000_000_000,
            labels: Labels = NOW_VS_SAVED) -> Diff:
    d = Diff(flat=flat, labels=labels, left_count=len(left), right_count=len(right))
    li, ri = make_index(left, flat), make_index(right, flat)
    for key in sorted(li.keys() - ri.keys()):
        d.only_left.extend(li[key])
    for key in sorted(ri.keys() - li.keys()):
        d.only_right.extend(ri[key])
    for key in sorted(li.keys() & ri.keys()):
        ls, rs = li[key], ri[key]
        if len(ls) > 1 or len(rs) > 1:  # only possible in flat mode: one name, several files
            d.duplicates.append((key, ls, rs))
            continue
        lf, rf = ls[0], rs[0]
        if lf.size != rf.size:
            d.size.append((lf, rf))
            continue
        if check_mtime and abs(lf.mtime_ns - rf.mtime_ns) > mtime_tolerance_ns:
            d.mtime.append((lf, rf))
        if check_sum:
            if getattr(lf, "skipped", False):
                d.skipped += 1
                continue
            match, used = checksums_match(lf, rf)
            if match is None:
                d.checksum_unknown.append((lf, rf))
            elif not match:
                d.checksum.append((lf, rf))
            else:
                d.ok[used] = d.ok.get(used, 0) + 1
    return d


# --------------------------------------------------------------------------- runs

@dataclass
class VerifyPlan:
    todo: list
    skipped: list
    run_start: str
    cutoff: str | None
    resumed: bool


def plan_verification(entries: list, state: dict[str, str], resume: bool = False,
                      older_than_days: float | None = None, now: datetime | None = None) -> VerifyPlan:
    """Which files must a verification run read?

    - resume: continue an incomplete run, skipping what was checked since that run started
    - older_than_days: only files whose last successful check is older than that
    A file without a timestamp -- never checked, or failed last time -- is always read.
    """
    now = now or datetime.now()
    resumed = bool(resume and state.get("verify_complete", YES) != YES and state.get("verify_start"))
    run_start = state["verify_start"] if resumed else now.strftime(TS_FORMAT)
    cutoff = ((now - timedelta(days=older_than_days)).strftime(TS_FORMAT)
              if older_than_days is not None else None)
    todo, skipped = [], []
    for e in entries:
        recent = bool(e.verified) and ((resumed and e.verified >= run_start)
                                       or (cutoff is not None and e.verified > cutoff))
        (skipped if recent else todo).append(e)
    return VerifyPlan(todo, skipped, run_start, cutoff, resumed)


T = TypeVar("T")
R = TypeVar("R")


def run_parallel(items: Iterable[T], work: Callable[[T, threading.Event], R], threads: int,
                 on_done: Callable[[T, R | None, Exception | None], None]) -> None:
    """Run work(item, stop) on `threads` threads; on_done(item, result, error) runs in the CALLING
    thread, so it needs no locking. On Ctrl+C `stop` is set; hash_chunks checks it per chunk."""
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=max(1, threads)) as pool:
        futures = {pool.submit(work, item, stop): item for item in items}
        pending = set(futures)
        try:
            while pending:
                # With a timeout, because on Windows an untimed wait does not see Ctrl+C.
                done, pending = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
                for fut in done:
                    try:
                        result, error = fut.result(), None
                    except Cancelled:
                        continue
                    except Exception as e:  # noqa: BLE001 - an error is part of the result
                        result, error = None, e
                    on_done(futures[fut], result, error)
        except BaseException:
            stop.set()
            for fut in pending:
                fut.cancel()
            raise


class Progress:
    """One line per finished file. Called from the main thread only."""

    def __init__(self, total_files: int, total_bytes: int, out: Callable[[str], None] = print) -> None:
        self.n, self.total_files, self.total_bytes, self.out = 0, total_files, total_bytes, out
        self.bytes, self.start = 0, time.monotonic()

    def step(self, status: str, e) -> None:
        self.n += 1
        self.bytes += e.size
        self.out(f"  [{self.n}/{self.total_files}] {status:<9} {fmt_size(e.size):>9}  {e.path}")

    def summary(self) -> str:
        secs = time.monotonic() - self.start
        speed = f", {fmt_size(self.bytes / secs)}/s" if secs > 1 else ""
        return f"{fmt_size(self.bytes)} in {secs:.0f} s{speed}"


# --------------------------------------------------------------------------- the two operations

Layouts = dict[str, tuple[list[int], bool]]  # key -> (part sizes, multipart)


@dataclass
class UpdateResult:
    entries: list[Entry]
    hashed: list[Entry]
    damaged: list[tuple[Entry, dict[str, str]]]  # (entry with the KEPT digests, digests just read)
    complete: bool
    manifests: dict[str, str]
    summary: str


def update_index(root: Path, index_path: Path, excludes: Iterable[str] = (),
                 layouts: Layouts | None = None, layout_key: Callable[[str], str] = lambda p: p,
                 force: bool = False, manifests: bool = True,
                 out: Callable[[str], None] = print) -> UpdateResult:
    """Bring the index of a tree up to date, then its manifests.

    A file is read again only when its size or mtime moved, when a digest is missing, or when a
    part layout asks for an ETag the index does not hold. With `force` every file is read -- and a
    file whose size and mtime did NOT move but whose content did keeps its saved digests and is
    reported as damage: a new version would have a new mtime, silent damage does not.
    """
    root, index_path = Path(root), Path(index_path)
    layouts = layouts or {}
    prev = {e.path: e for e in read_index(index_path)}
    state = read_state(index_path)
    entries = scan_tree(root, excludes, own_files(root, index_path))
    todo: list[tuple[Entry, list[int] | None, bool]] = []
    for e in entries:
        parts, multipart = layouts.get(layout_key(e.path), (None, False))
        if parts and sum(parts) != e.size:
            parts = None  # the size differs, so the file differs anyway
        p = prev.get(e.path)
        same_file = bool(p and p.size == e.size and p.mtime_ns == e.mtime_ns and p.digests())
        if same_file:
            e.verified = p.verified
        if (same_file and not force and p.has_all_digests()
                and (not parts or (p.etag and p.parts == parts))):
            e.set_digests(p.digests())
            e.etag, e.parts = p.etag, p.parts
        else:
            todo.append((e, parts, multipart))
    out(f"{root.name}: {len(entries)} files, {len(entries) - len(todo)} unchanged, {len(todo)} to read "
        f"({fmt_size(sum(e.size for e, _p, _m in todo))}, {sum(1 for _e, p, _m in todo if p)} with part MD5s)")

    state = {**state, "created": now_ts()}
    saver = IndexSaver(index_path, state, entries, keep=lambda e: e.has_all_digests())
    progress = Progress(len(todo), sum(e.size for e, _p, _m in todo), out)
    damaged: list[tuple[Entry, dict[str, str]]] = []
    hashed: list[Entry] = []
    try:
        for e, parts, multipart in todo:
            digests, etag = hash_file(e.abs_path, parts, multipart)
            p = prev.get(e.path)
            if p and p.size == e.size and p.mtime_ns == e.mtime_ns:
                saved = p.digests()
                clash = [n for n in saved if n in digests and saved[n].lower() != digests[n].lower()]
                if clash:
                    # Same size, same mtime, different bytes: keep what was saved, and say so.
                    e.set_digests(saved)
                    e.set_digests({n: v for n, v in digests.items() if n not in saved})
                    e.etag, e.parts, e.verified = p.etag, p.parts, ""
                    damaged.append((e, digests))
                    progress.step("DAMAGE?", e)
                    saver.maybe_save()
                    continue
            e.set_digests(digests)
            e.etag, e.parts, e.verified = etag, parts, now_ts()
            hashed.append(e)
            progress.step("hashed", e)
            saver.maybe_save()
    finally:
        complete = all(e.has_all_digests() for e in entries)
        saver.save(complete)
    written = write_manifests(root, entries) if manifests and complete else {}
    return UpdateResult(entries, hashed, damaged, complete, written, progress.summary())


@dataclass
class VerifyResult:
    diff: Diff
    plan: VerifyPlan | None
    summary: str


def verify_tree(root: Path, index_path: Path, excludes: Iterable[str] = (),
                selection: FileFilter | None = None, quick: bool = False, resume: bool = False,
                older_than: float | None = None, threads: int = 1,
                out: Callable[[str], None] = print) -> VerifyResult:
    """Re-read a tree against its index: new, gone, resized, re-dated and damaged files.

    Only files of unchanged size are read; new, gone or resized ones are reported anyway. Known
    part sizes are hashed along, so a caller can judge a difference against a cloud copy's ETag.
    A file that fails loses its 'last checked' time, so every later run reads it again.
    """
    root, index_path = Path(root), Path(index_path)
    selection = selection or FileFilter()
    all_saved = read_index(index_path)
    state = read_state(index_path)
    saved = selection.apply([e for e in all_saved if not is_excluded(e.path, excludes)])
    by_path = {e.path: e for e in saved}
    current = selection.apply(scan_tree(root, excludes, own_files(root, index_path)))
    errors: dict[str, str] = {}
    plan = None
    summary = ""
    if not quick:
        pairs = {e.path: (e, by_path[e.path]) for e in current
                 if e.path in by_path and by_path[e.path].size == e.size}
        plan = plan_verification([p for _e, p in pairs.values()], state, resume, older_than)
        for p in plan.skipped:
            e = pairs[p.path][0]
            e.set_digests(p.digests())
            e.skipped = True
        todo = [pairs[p.path] for p in plan.todo]
        if plan.resumed:
            out(f"  resuming the run of {plan.run_start}")
        out(f"  reading {len(todo)} files ({fmt_size(sum(e.size for e, _p in todo))}) on "
            f"{threads} thread(s), {len(plan.skipped)} skipped")
        state["verify_start"] = plan.run_start
        saver = IndexSaver(index_path, state, all_saved, complete_key="verify_complete")
        progress = Progress(len(todo), sum(e.size for e, _p in todo), out)

        def work(pair, stop):
            e, p = pair
            parts = p.parts if p.etag else None
            return hash_chunks(read_file_chunks(e.abs_path), parts,
                               bool(p.etag and is_multipart_etag(p.etag)), stop)

        def done(pair, result, err):
            e, p = pair
            if err:
                errors[e.path] = f"read error: {err}"
                p.verified = ""
                progress.step("ERROR", e)
            else:
                digests, etag, _size = result
                e.set_digests(digests)
                e.etag, e.parts = etag, (p.parts if p.etag else None)
                ok = checksums_match(e, p)[0]
                p.verified = now_ts() if ok else ""
                progress.step("OK" if ok else "MISMATCH", e)
            saver.maybe_save()

        finished = False
        try:
            run_parallel(todo, work, threads, done)
            finished = True
        finally:
            saver.save(complete=finished)
        summary = progress.summary()
    diff = compare(current, saved, check_mtime=True, mtime_tolerance_ns=0, check_sum=not quick)
    diff.attach_errors(errors)
    return VerifyResult(diff, plan, summary)


# --------------------------------------------------------------------------- formatting

def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def fmt_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9).strftime(TS_FORMAT)


def total(entries: list) -> str:
    return fmt_size(sum(e.size for e in entries))


def copy_entry(e, **changes):
    return replace(e, **changes)
