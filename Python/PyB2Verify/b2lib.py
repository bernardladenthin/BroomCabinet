# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The part of PyB2Verify that needs neither the network nor a third-party package.

EVERYTHING HERE IS PURE ON PURPOSE. Selecting files, hashing a byte stream, reading and writing the
checksum files, comparing two sides and planning a verification run are the rules the tool stands
on, and a rule is only trustworthy if a test can break it without a B2 account. `b2verify.py` adds
the bucket, the S3 endpoint and the command line around this; `b2lib_test.py` covers this file.

THE ONE IDEA THAT MAKES LARGE FILES CHECKABLE. B2 records a SHA-1 for a file uploaded in one piece,
but a large file is uploaded in parts and often carries no SHA-1 at all. Its S3 ETag is the MD5 of
the concatenated part MD5s, suffixed with the part count. Given the part sizes, a local file can
be cut the same way and hashed to the same ETag -- so `StreamHasher` computes SHA-1 and, when part
sizes are known, the part MD5s in ONE pass over the bytes, whether they come from a disk or a
download.
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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Iterator, TypeVar

READ_CHUNK = 1024 * 1024
# How often a long run writes its checksum file, so an interruption loses at most this much work.
SAVE_INTERVAL = 30
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
YES = "yes"
INCOMPLETE = "no (interrupted, partial)"
SNAPSHOT_COLUMNS = ["size", "mtime_ms", "sha1", "etag", "parts", "verified", "source", "file_id", "path"]

# Header keys and values as the first, German-language version of this tool wrote them. Files from
# that version are read and translated; files are always written in English.
LEGACY_META_KEYS = {"seite": "side", "erzeugt": "created", "vollstaendig": "complete",
                    "verify_vollstaendig": "verify_complete"}


def now_ts() -> str:
    return datetime.now().strftime(TS_FORMAT)


def norm(name: str) -> str:
    """NFC, because the same visible name can arrive composed from one side and decomposed from
    the other, and two spellings of one name would show up as one file missing on each side."""
    return unicodedata.normalize("NFC", name)


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def is_excluded(rel_path: str, patterns: list[str]) -> bool:
    """Permanent exclusions from the configuration: glob patterns on the path or the file name."""
    return any(fnmatch.fnmatch(rel_path, p) or fnmatch.fnmatch(basename(rel_path), p) for p in patterns)


# --------------------------------------------------------------------------- long paths

LONG_PREFIX = "\\\\?\\"


def long_path(path: str | os.PathLike, windows: bool = os.name == "nt") -> str:
    r"""-> the path with the `\\?\` prefix on Windows, unchanged elsewhere.

    WITHOUT IT WINDOWS REFUSES PATHS OF 260 CHARACTERS AND MORE, unless LongPathsEnabled is set
    for the whole machine -- a setting of the computer, not of this tool, and one that a fresh
    installation or another account does not have. A collection of recorded broadcasts easily
    holds file names of 300 characters. The prefix needs an absolute path with backslashes; a UNC
    path becomes `\\?\UNC\server\share`. Applying it twice changes nothing.
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

    TWO CONCEPTS, NOT FOUR SWITCHES. One regex mechanism covers folders (`^Recordings/`), file
    names (`(^|/)serial\\.txt$`) and extensions (`\\.mp4$`), because all three are just parts of
    the relative path. Patterns are matched with re.search, ignoring case.

    - include: at least one pattern must match (none given = everything)
    - exclude: no pattern may match; it wins over include
    - min_size inclusive, max_size exclusive -- so `--max-size 1M` and `--min-size 1M` split a
      collection completely and without overlap, which is what a test can actually check
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

    def apply(self, entries: list[FileEntry]) -> list[FileEntry]:
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
class FileEntry:
    path: str  # relative path with '/' (local) or the file name in the bucket
    size: int
    mtime_ms: int
    sha1: str | None = None
    etag: str | None = None  # S3 ETag: an MD5, or "<md5 of the part md5s>-<part count>"
    parts: list[int] | None = None  # the part sizes that belong to the ETag
    source: str = ""  # local | b2 (metadata) | s3 (ETag) | download (downloaded and hashed)
    file_id: str = ""  # B2 only
    verified: str = ""  # last successful read-and-compare (TS_FORMAT); empty = never, or failed
    abs_path: Path | None = None  # local only, not stored
    key: str = ""  # B2 only: the file name exactly as stored, for S3; not stored
    skipped: bool = False  # verification run: not read this time (checked recently); not stored


# key (relative path, or only the file name in flat mode) -> every file with that key
Index = dict[str, list[FileEntry]]


@dataclass(frozen=True)
class Labels:
    left: str
    right: str
    only_left: str
    only_right: str


LOCAL_VS_B2 = Labels("Local", "B2", "Only local (missing in B2)", "Only in B2 (missing locally)")
NOW_VS_SAVED = Labels("Current", "Saved", "New (not in the checksums)", "Gone (only in the checksums)")
CONTENT_VS_META = Labels("Content", "Metadata", "Read only", "Not read")


@dataclass
class Diff:
    flat: bool
    labels: Labels = LOCAL_VS_B2
    only_left: list[FileEntry] = field(default_factory=list)
    only_right: list[FileEntry] = field(default_factory=list)
    size: list[tuple[FileEntry, FileEntry]] = field(default_factory=list)
    mtime: list[tuple[FileEntry, FileEntry]] = field(default_factory=list)
    checksum: list[tuple[FileEntry, FileEntry]] = field(default_factory=list)
    checksum_unknown: list[tuple[FileEntry, FileEntry]] = field(default_factory=list)
    errors: list[tuple[FileEntry, FileEntry]] = field(default_factory=list)  # read or download errors
    sha1_ok: int = 0
    etag_ok: int = 0
    skipped: int = 0
    notes: dict[str, str] = field(default_factory=dict)  # path -> remark
    duplicates: list[tuple[str, list[FileEntry], list[FileEntry]]] = field(default_factory=list)
    left_count: int = 0
    right_count: int = 0

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


def decode_parts(text: str) -> list[int] | None:
    if not text:
        return None
    parts: list[int] = []
    for item in text.split(","):
        size, _, count = item.partition("*")
        parts.extend([int(size)] * int(count or 1))
    return parts


def is_multipart_etag(etag: str) -> bool:
    return "-" in etag


class Cancelled(Exception):
    """The run was interrupted (Ctrl+C)."""


class StreamHasher:
    """SHA-1 over everything and, when part sizes are known, the S3 ETag -- in one pass.

    Chunk boundaries of the incoming data are arbitrary (a file, a network stream). If the amount
    of data does not fit the part sizes exactly, the ETag is None rather than a wrong value.
    """

    def __init__(self, parts: list[int] | None = None, multipart: bool = False) -> None:
        self._sha1 = hashlib.sha1()
        self.size = 0
        self._parts = parts or []
        self._multipart = multipart
        self._index = 0
        self._left = self._parts[0] if self._parts else 0
        self._md5 = hashlib.md5()
        self._digests: list[bytes] = []
        self._overflow = False

    def update(self, data: bytes) -> None:
        self._sha1.update(data)
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
                self._digests.append(self._md5.digest())
                self._index += 1
                if self._index < len(self._parts):
                    self._left = self._parts[self._index]
                    self._md5 = hashlib.md5()

    def result(self) -> tuple[str, str | None]:
        sha1 = self._sha1.hexdigest()
        if not self._parts or self._overflow or self._index != len(self._parts):
            return sha1, None
        if self._multipart:
            return sha1, f"{hashlib.md5(b''.join(self._digests)).hexdigest()}-{len(self._digests)}"
        return sha1, self._digests[0].hex()


def hash_chunks(chunks: Iterable[bytes], parts: list[int] | None = None, multipart: bool = False,
                stop: threading.Event | None = None) -> tuple[str, str | None, int]:
    """Hash a byte stream (file or download) -> (sha1, etag, bytes seen). Closes the stream."""
    h = StreamHasher(parts, multipart)
    try:
        for chunk in chunks:
            if stop is not None and stop.is_set():
                raise Cancelled()
            h.update(chunk)
    finally:
        close = getattr(chunks, "close", None)
        if close:
            close()
    sha1, etag = h.result()
    return sha1, etag, h.size


def read_file_chunks(path: str | os.PathLike, chunk_size: int = READ_CHUNK) -> Iterator[bytes]:
    with open(long_path(path), "rb") as f:
        yield from iter(lambda: f.read(chunk_size), b"")


def hash_file(path: str | os.PathLike, parts: list[int] | None = None,
              multipart: bool = False) -> tuple[str, str | None]:
    sha1, etag, _size = hash_chunks(read_file_chunks(path), parts, multipart)
    return sha1, etag


def scan_local(root: Path, excludes: list[str]) -> list[FileEntry]:
    """Every file below root except the permanent exclusions, sorted by relative path.

    Walked through the long path, so files deeper than 259 characters are found and can be read;
    FileEntry.path stays the relative path with '/'.
    """
    base = long_path(root)
    files: list[FileEntry] = []
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = norm(os.path.relpath(full, base).replace(os.sep, "/"))
            if is_excluded(rel, excludes):
                continue
            st = os.stat(full)
            files.append(FileEntry(rel, st.st_size, int(st.st_mtime * 1000), source="local", abs_path=Path(full)))
    return sorted(files, key=lambda e: e.path)


# --------------------------------------------------------------------------- checksum files

def write_snapshot(path: Path, meta: dict[str, str], entries: list[FileEntry]) -> None:
    """Header lines (`# key: value`), then a tab-separated table. Written to a temporary name and
    renamed, so an interruption never leaves a half-written file that still looks complete."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        for key, value in meta.items():
            f.write(f"# {key}: {value}\n")
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(SNAPSHOT_COLUMNS)
        for e in entries:
            w.writerow([e.size, e.mtime_ms, e.sha1 or "", e.etag or "", encode_parts(e.parts),
                        e.verified, e.source, e.file_id, e.path])
    tmp.replace(path)


def _translate_legacy(key: str, value: str) -> tuple[str, str]:
    key = LEGACY_META_KEYS.get(key, key)
    if key in ("complete", "verify_complete"):
        if value == "ja":
            value = YES
        elif value.startswith("nein"):
            value = INCOMPLETE
    return key, value


def read_snapshot(path: Path) -> tuple[dict[str, str], list[FileEntry]]:
    meta: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line.startswith("#"):
                f.seek(pos)
                break
            key, _, value = line[1:].partition(":")
            key, value = _translate_legacy(key.strip(), value.strip())
            meta[key] = value
        entries = [FileEntry(r["path"], int(r["size"]), int(r["mtime_ms"]), r["sha1"] or None,
                             r.get("etag") or None, decode_parts(r.get("parts", "")),
                             r["source"], r["file_id"], r.get("verified") or "")
                   for r in csv.DictReader(f, delimiter="\t")]
    return meta, entries


def new_meta(bucket: str, side: str, prev_meta: dict[str, str] | None = None) -> dict[str, str]:
    meta = {"bucket": bucket, "side": side, "created": now_ts(), "complete": INCOMPLETE}
    for key in ("verify_start", "verify_complete"):  # the state of verification runs survives
        if prev_meta and key in prev_meta:
            meta[key] = prev_meta[key]
    return meta


def load_previous(path: Path) -> tuple[dict[str, str], dict[str, FileEntry]]:
    if not path.is_file():
        return {}, {}
    meta, entries = read_snapshot(path)
    return meta, {e.path: e for e in entries}


class SnapshotSaver:
    """Writes the checksum file at intervals, so an interruption loses at most one interval.

    complete_key: the header that becomes 'yes' at the end, or 'no' when interrupted.
    keep: which entries are written (for example only those already hashed).
    """

    def __init__(self, path: Path, meta: dict[str, str], entries: list[FileEntry],
                 complete_key: str = "complete", keep: Callable[[FileEntry], object] = lambda e: True,
                 interval: float = SAVE_INTERVAL) -> None:
        self.path, self.meta, self.entries = path, meta, entries
        self.complete_key, self.keep, self.interval = complete_key, keep, interval
        self.last = time.monotonic()

    def maybe_save(self) -> None:
        if time.monotonic() - self.last > self.interval:
            self.save(complete=False)

    def save(self, complete: bool) -> None:
        self.meta[self.complete_key] = YES if complete else INCOMPLETE
        write_snapshot(self.path, self.meta, [e for e in self.entries if self.keep(e)])
        self.last = time.monotonic()


# --------------------------------------------------------------------------- comparison

def make_index(entries: list[FileEntry], flat: bool) -> Index:
    idx: Index = {}
    for e in entries:
        idx.setdefault(basename(e.path) if flat else e.path, []).append(e)
    return idx


def checksums_match(a: FileEntry, b: FileEntry) -> bool | None:
    """True/False when comparable by SHA-1, or by ETag over the same part sizes; None otherwise."""
    if a.size != b.size:
        return False
    if a.sha1 and b.sha1:
        return a.sha1 == b.sha1
    if a.etag and b.etag and a.parts == b.parts:
        return a.etag == b.etag
    return None


def expected_from_metadata(e: FileEntry) -> FileEntry:
    """The checksum a content check of a B2 file must reproduce.

    Source 'b2' (SHA-1 from the B2 metadata) and 'download' (computed earlier by this tool): the
    SHA-1. Source 's3': the ETag is what B2 actually states; a SHA-1 this tool learned from an
    earlier download is our own record, not B2's, and does not count as metadata.
    """
    return replace(e, sha1=None, skipped=False) if e.source == "s3" else replace(e, skipped=False)


def compare(left: list[FileEntry], right: list[FileEntry], flat: bool,
            check_mtime: bool = False, check_sum: bool = False, mtime_tolerance_ms: int = 2000,
            labels: Labels = LOCAL_VS_B2) -> Diff:
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
        if check_mtime and abs(lf.mtime_ms - rf.mtime_ms) > mtime_tolerance_ms:
            d.mtime.append((lf, rf))
        if check_sum:
            if lf.skipped:
                d.skipped += 1
                continue
            match = checksums_match(lf, rf)
            if match is None:
                d.checksum_unknown.append((lf, rf))
            elif not match:
                d.checksum.append((lf, rf))
            elif lf.sha1 and rf.sha1:
                d.sha1_ok += 1
            else:
                d.etag_ok += 1
    return d


def b2_state(now: FileEntry, saved: FileEntry, candidates: list[FileEntry] | None) -> str:
    """A local file changed: how does the copy in B2 relate to the saved and the current content?"""
    if candidates is None:
        return "no B2 checksums available (run hash-b2)"
    if not candidates:
        return "not in B2"
    if len(candidates) > 1:
        return "name occurs more than once in B2, ambiguous"
    r = candidates[0]
    m_saved, m_now = checksums_match(saved, r), checksums_match(now, r)
    if m_saved:
        return "B2 intact (matches the saved checksum) -> restorable from B2"
    if m_now:
        return "B2 holds the same content as the local file now"
    if m_saved is None or m_now is None:
        return "B2 not comparable (B2 has only an ETag, the local part MD5s are missing)"
    return "B2 differs from both"


def local_state(content: FileEntry, candidates: list[FileEntry] | None) -> str:
    """A B2 file does not match its metadata: how does the local file relate to what B2 delivered?"""
    if candidates is None:
        return "no local checksums available"
    if not candidates:
        return "not present locally"
    if len(candidates) > 1:
        return "name occurs more than once locally, ambiguous"
    match = checksums_match(content, candidates[0])
    if match is None:
        return "local file not comparable"
    return ("local file identical to the B2 content" if match
            else "local file differs from the B2 content -> check it, re-upload if it is good")


def classify_unfinished(unfinished: list[str], present: set[str]) -> tuple[list[str], list[str]]:
    """Unfinished large-file uploads -> (leftovers, missing), each sorted and without repeats.

    A dropped connection during a multi-part upload leaves the upload open in B2: its parts are
    stored and billed, but the file never appears in a listing. A LEFTOVER has a finished file of
    the same name beside it -- the upload was retried and completed, and the abandoned parts only
    cost storage. A MISSING one has no finished file of that name: that file is not in B2 at all.
    """
    names = set(unfinished)
    return sorted(names & present), sorted(names - present)


# --------------------------------------------------------------------------- verification runs

@dataclass
class VerifyPlan:
    todo: list[FileEntry]
    skipped: list[FileEntry]
    run_start: str
    cutoff: str | None
    resumed: bool


def plan_verification(entries: list[FileEntry], meta: dict[str, str], resume: bool = False,
                      older_than_days: float | None = None, now: datetime | None = None) -> VerifyPlan:
    """Which files must a verification run read?

    - resume: continue an incomplete run, skipping what was checked since that run started
    - older_than_days: only files whose last successful check is older than that
    A file without a timestamp -- never checked, or failed last time -- is always read.
    """
    now = now or datetime.now()
    resumed = bool(resume and meta.get("verify_complete", YES) != YES and meta.get("verify_start"))
    run_start = meta["verify_start"] if resumed else now.strftime(TS_FORMAT)
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
    """Run work(item, stop) on `threads` threads.

    on_done(item, result, error) runs in the CALLING thread, so it needs no locking. On Ctrl+C
    `stop` is set; work should check it regularly -- hash_chunks does, once per chunk.
    """
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


# --------------------------------------------------------------------------- formatting

def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def fmt_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime(TS_FORMAT)


def total(entries: list[FileEntry]) -> str:
    return fmt_size(sum(e.size for e in entries))


def copy_entry(e: FileEntry, **changes) -> FileEntry:
    return replace(e, **changes)
