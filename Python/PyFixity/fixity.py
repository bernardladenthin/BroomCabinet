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
bottleneck anyway; computing all four in one pass costs CPU that the disk leaves idle.

AND, BY DEFAULT, THE ETAG A CLOUD COPY WILL REPORT. A large file uploaded in parts has no
whole-file checksum in S3 or Backblaze B2 -- only an ETag, the MD5 of the part MD5s, which depends
on where the parts were cut and cannot be derived from any whole-file digest afterwards. Learning
that only after 2.5 TB had been hashed and uploaded meant reading all of it again. So the same
pass now always computes the ETag for the part layout uploaders actually use (S3Layout: parts of
100 000 000 bytes above 200 MiB -- B2's recommended part size and Cyberduck's fixed behaviour; every
one of 3 572 multipart files across fifteen real buckets was cut exactly so). Explicit layouts, from
a listing of the real cloud copy, still take precedence.

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
                    Beside them .s3etag, the ETags of the files above the cutoff, in md5sum's
                    layout under a header naming the part size. It travels WITH the tree into
                    the cloud, so the cloud copy can be checked even where the index is gone.

NO FILE DESCRIBES ITSELF. The five manifests, the index and its state file are never listed in a
manifest; a manifest that contained its own checksum could never be correct. The index, which
lives elsewhere, may list the manifests -- that is how a cloud copy of them can be checked too.
"""
from __future__ import annotations

import csv
import fnmatch
import hashlib
import ntpath
import os
import queue
import re
import threading
import time
import unicodedata
import zlib
from collections import deque
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
ETAG_MANIFEST = ".s3etag"
DEFAULT_INDEX = ".fixity-index.csv"
# B2's recommendedPartSize, the part size of the b2 command line tool, and Cyberduck's fixed chunk.
S3_PART_SIZE = 100_000_000
# Cyberduck uploads a file of up to 200 MiB in one request -- B2 then records its SHA-1, which
# .sha1sum already covers -- and cuts anything larger: "Files larger than 200MB are split into
# 100MB chunks". Measured in real buckets: SHA-1s up to exactly 209 715 200 bytes, none above.
S3_CUTOFF = 200 * 1024 * 1024


@dataclass(frozen=True)
class S3Layout:
    """Where an uploader cuts a file into the parts of an S3 multipart upload."""
    part_size: int = S3_PART_SIZE
    cutoff: int = S3_CUTOFF  # files of up to this size are uploaded in one piece

    def parts(self, size: int) -> list[int] | None:
        """The part sizes of a file of this size, or None when it is uploaded in one piece."""
        if self.part_size <= 0 or size <= self.cutoff:
            return None
        full, rest = divmod(size, self.part_size)
        return [self.part_size] * full + ([rest] if rest else [])

    def header(self) -> str:
        return (f"# S3 multipart ETags (Backblaze B2, AWS S3 and others report them for files uploaded in parts)\n"
                f"# part size {self.part_size} bytes; files larger than {self.cutoff} bytes\n")


DEFAULT_S3 = S3Layout()
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


# THE DIGESTS OF ONE STREAM ARE SPREAD OVER THREADS, because the CPU is the bottleneck, not the
# disk. Measured on 2026-10-10, 16 cores, data in memory: SHA-256 1482, SHA-1 1584, MD5 630,
# CRC32 2106 MB/s each. All five one after the other (MD5 twice: whole file, and per part for the
# ETag) manage 202 MB/s -- and a real run that day read 72 GB at 178 MB/s, CPU-bound with the disk
# waiting. One thread per digest: 620 MB/s, the MD5 then being the limit. hashlib and zlib release
# the GIL on large buffers, so the threads really run at once. The data is still read ONCE: every
# chunk goes to every thread.
HASH_THREADS = 5
# Below this a file is hashed in the calling thread: starting threads would cost more than it saves.
PARALLEL_MIN_SIZE = 8 * 1024 * 1024
# How many chunks a thread may lag behind the reader -- bounds the memory to threads x this x chunk.
LANE_DEPTH = 8
# Seconds per MB, from the measurement above: how the digests are grouped when threads are fewer.
_COST = {"sha256": 1 / 1482, "sha1": 1 / 1584, "md5": 1 / 630, "crc32": 1 / 2106, "etag": 1 / 630}


class _Digest:
    """One whole-stream digest."""

    def __init__(self, name: str) -> None:
        self.name, self.cost = name, _COST.get(name, 1 / 600)
        self._h = None if name == "crc32" else hashlib.new(name)
        self._crc = 0

    def update(self, data) -> None:
        if self._h is None:
            self._crc = zlib.crc32(data, self._crc)
        else:
            self._h.update(data)

    def value(self) -> str:
        return crc32_text(self._crc) if self._h is None else self._h.hexdigest()


class _PartMD5:
    """The S3 ETag: an MD5 per part, then the MD5 of those. None if the stream does not fit the
    part sizes exactly -- rather than a wrong value."""

    name, cost = "etag", _COST["etag"]

    def __init__(self, parts: list[int], multipart: bool) -> None:
        self._parts, self._multipart = parts, multipart
        self._index, self._left = 0, parts[0]
        self._md5 = hashlib.md5()
        self._digests: list[bytes] = []
        self._overflow = False

    def update(self, data) -> None:
        if self._overflow:
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

    def value(self) -> str | None:
        if self._overflow or self._index != len(self._parts):
            return None
        if self._multipart:
            return f"{hashlib.md5(b''.join(self._digests)).hexdigest()}-{len(self._digests)}"
        return self._digests[0].hex()


def spread(costs: list[float], lanes: int) -> list[list[int]]:
    """Group items (by index) into at most `lanes` groups of similar total cost: the most
    expensive first, each to the cheapest group so far. Deterministic."""
    groups: list[list[int]] = [[] for _ in range(max(1, min(lanes, len(costs))))]
    load = [0.0] * len(groups)
    for i in sorted(range(len(costs)), key=lambda k: (-costs[k], k)):
        g = load.index(min(load))
        groups[g].append(i)
        load[g] += costs[i]
    return [g for g in groups if g]


class _Lane(threading.Thread):
    """A thread feeding every chunk it receives to its share of the digests."""

    def __init__(self, consumers: list) -> None:
        super().__init__(daemon=True)
        self.consumers = consumers
        self.queue: queue.Queue = queue.Queue(maxsize=LANE_DEPTH)
        self.error: BaseException | None = None

    def run(self) -> None:
        while True:
            data = self.queue.get()
            if data is None:
                return
            if self.error is None:  # after an error: keep draining, so the reader never blocks
                try:
                    for c in self.consumers:
                        c.update(data)
                except BaseException as e:  # noqa: BLE001 - handed to the caller in result()
                    self.error = e


class StreamHasher:
    """All digests in one pass and, when part sizes are known, the S3 ETag too.

    Chunk boundaries of the incoming data are arbitrary (a file, a network stream). If the amount
    of data does not fit the part sizes exactly, the ETag is None rather than a wrong value.

    threads > 1 spreads the digests over that many threads (at most one per digest); each gets
    every chunk, so the data is still read once. Chunks must not be changed after update() --
    `bytes`, as files and downloads deliver them, never are. close() or result() ends the threads.
    """

    def __init__(self, parts: list[int] | None = None, multipart: bool = False,
                 want: Iterable[str] = DIGESTS, threads: int = 1) -> None:
        self._consumers: list = [_Digest(name) for name in want]
        self._etag = _PartMD5(parts, multipart) if parts else None
        if self._etag:
            self._consumers.append(self._etag)
        self.size = 0
        self._lanes: list[_Lane] = []
        if threads > 1 and len(self._consumers) > 1:
            groups = spread([c.cost for c in self._consumers], threads)
            self._lanes = [_Lane([self._consumers[i] for i in g]) for g in groups]
            for lane in self._lanes:
                lane.start()

    def update(self, data: bytes) -> None:
        self.size += len(data)
        if self._lanes:
            if not isinstance(data, bytes):
                data = bytes(data)  # a buffer the caller might reuse
            for lane in self._lanes:
                lane.queue.put(data)
        else:
            for c in self._consumers:
                c.update(data)

    def close(self) -> None:
        """End the threads (idempotent). Called by result(); call it on an aborted stream too."""
        lanes, self._lanes = self._lanes, []
        for lane in lanes:
            lane.queue.put(None)
        for lane in lanes:
            lane.join()
        for lane in lanes:
            if lane.error is not None:
                raise lane.error

    def result(self) -> tuple[dict[str, str], str | None]:
        self.close()
        digests = {c.name: c.value() for c in self._consumers if c is not self._etag}
        return digests, (self._etag.value() if self._etag else None)


def hash_chunks(chunks: Iterable[bytes], parts: list[int] | None = None, multipart: bool = False,
                stop: threading.Event | None = None, want: Iterable[str] = DIGESTS,
                threads: int = 1) -> tuple[dict[str, str], str | None, int]:
    """Hash a byte stream (file or download) -> (digests, etag, bytes seen). Closes the stream."""
    h = StreamHasher(parts, multipart, want, threads)
    try:
        for chunk in chunks:
            if stop is not None and stop.is_set():
                raise Cancelled()
            h.update(chunk)
    except BaseException:
        try:
            h.close()  # end the threads; the stream's own error is the one that matters
        except BaseException:  # noqa: BLE001
            pass
        raise
    finally:
        close = getattr(chunks, "close", None)
        if close:
            close()
    digests, etag = h.result()  # raises a digest thread's error, if one had any
    return digests, etag, h.size


def read_file_chunks(path: str | os.PathLike, chunk_size: int = READ_CHUNK) -> Iterator[bytes]:
    with open(long_path(path), "rb") as f:
        yield from iter(lambda: f.read(chunk_size), b"")


def hash_threads_for(size: int, hash_threads: int) -> int:
    """Threads for one stream of this size: none extra for a small one."""
    return hash_threads if size >= PARALLEL_MIN_SIZE else 1


def hash_file(path: str | os.PathLike, parts: list[int] | None = None, multipart: bool = False,
              want: Iterable[str] = DIGESTS, threads: int = 1,
              stop: threading.Event | None = None) -> tuple[dict[str, str], str | None]:
    threads = hash_threads_for(os.stat(long_path(path)).st_size, threads)
    digests, etag, _size = hash_chunks(read_file_chunks(path), parts, multipart, stop, want, threads)
    return digests, etag


# --------------------------------------------------------------------------- the tree

def own_files(root: Path, index_path: Path | None = None) -> set[str]:
    """Relative paths at the root of the tree that belong to this tool and are never content."""
    manifests = set(MANIFEST_FILES.values()) | {ETAG_MANIFEST}
    own = manifests | {DEFAULT_INDEX, DEFAULT_INDEX + ".state"}
    if index_path is not None:
        try:
            rel = Path(index_path).resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            rel = None
        if rel:
            own |= {rel, rel + ".state", rel + ".tmp"}
    own |= {name + ".tmp" for name in manifests}
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


def etag_manifest_text(entries: list[Entry], s3: S3Layout) -> tuple[str | None, str]:
    """-> (text of .s3etag, why not) for the files above the cutoff.

    Every line must be an ETag over exactly the layout the header names: an ETag taken over other
    part sizes (an explicit layout of an older upload) would read as a mismatch on the far side.
    So, as with the other manifests, an incomplete one is not written at all."""
    large = sorted((e for e in entries if s3.parts(e.size)), key=lambda x: x.path)
    if not large:
        return None, f"not needed (no file larger than {s3.cutoff} bytes)"
    off = [e for e in large if not e.etag or e.parts != s3.parts(e.size)]
    if off:
        return None, (f"not written ({len(off)} of {len(large)} large files lack an ETag over parts of "
                      f"{s3.part_size} bytes, e.g. {off[0].path})")
    return s3.header() + "".join(sums_line(e.etag, e.path) for e in large), ""


def _write_if_changed(target: Path, text: str) -> str:
    current = None
    if os.path.isfile(long_path(target)):
        with open(long_path(target), encoding="utf-8", newline="") as f:
            current = f.read()
    if current == text:
        return "unchanged"
    tmp = target.with_name(target.name + ".tmp")
    with open(long_path(tmp), "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(long_path(tmp), long_path(target))
    return "written"


def write_manifests(root: Path, entries: list[Entry], want: Iterable[str] = DIGESTS,
                    s3: S3Layout | None = DEFAULT_S3) -> dict[str, str]:
    """Write the manifests at the root of the tree -> {file name: what happened}.

    A MANIFEST IS REWRITTEN ONLY WHEN ITS TEXT CHANGES. Re-checking a tree must not produce new
    manifests, or every check would hand a sync tool a fresh version to upload.
    """
    result = {}
    for algo in want:
        name = MANIFEST_FILES[algo]
        text = manifest_text(entries, algo)
        if text is None:
            result[name] = "not written (a digest is missing)"
            continue
        result[name] = _write_if_changed(Path(root) / name, text)
    if s3 is not None and s3.part_size > 0:
        target = Path(root) / ETAG_MANIFEST
        text, why = etag_manifest_text(entries, s3)
        if text is not None:
            result[ETAG_MANIFEST] = _write_if_changed(target, text)
        elif not any(s3.parts(e.size) for e in entries) and os.path.isfile(long_path(target)):
            # The large files are gone; a manifest still naming them would fail on the far side.
            os.remove(long_path(target))
            result[ETAG_MANIFEST] = "removed (no file larger than the cutoff any more)"
        else:
            result[ETAG_MANIFEST] = why
    return result


def read_etags(path: Path) -> tuple[int | None, dict[str, str]]:
    """-> (part size from the header, {relative path: ETag}) from an .s3etag file."""
    part_size, etags = None, {}
    if not os.path.isfile(long_path(path)):
        return part_size, etags
    with open(long_path(path), encoding="utf-8", newline="") as f:
        for line in f.read().splitlines():
            if line.startswith("#"):
                m = re.search(r"part size (\d+) bytes", line)
                if m:
                    part_size = int(m.group(1))
                continue
            etag, sep, rel = line.partition(" *")
            if sep and not line.startswith("\\"):
                etags[rel] = etag
    return part_size, etags


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


def run_ordered(items: Iterable[T], work: Callable[[T, threading.Event], R], threads: int,
                on_done: Callable[[T, R | None, Exception | None], None]) -> None:
    """Like run_parallel, but on_done sees the items IN THEIR ORDER, and at most `threads` are in
    work at once: a file that finishes early waits for the ones before it. That blocks a little;
    in exchange the output, the progress and an interrupted index read exactly as a run with one
    thread would have left them. With threads <= 1 everything runs in the calling thread."""
    stop = threading.Event()
    if threads <= 1:
        for item in items:
            try:
                result, error = work(item, stop), None
            except Cancelled:
                return
            except Exception as e:  # noqa: BLE001 - an error is part of the result
                result, error = None, e
            on_done(item, result, error)
        return
    source = iter(items)
    window: deque = deque()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        def refill() -> None:
            while len(window) < threads:
                item = next(source, _END)
                if item is _END:
                    return
                window.append((item, pool.submit(work, item, stop)))

        try:
            refill()
            while window:
                item, fut = window[0]
                while not fut.done():
                    wait([fut], timeout=1.0)  # with a timeout: an untimed wait misses Ctrl+C on Windows
                window.popleft()
                try:
                    result, error = fut.result(), None
                except Cancelled:
                    continue
                except Exception as e:  # noqa: BLE001
                    result, error = None, e
                on_done(item, result, error)
                refill()
        except BaseException:
            stop.set()
            for _item, fut in window:
                fut.cancel()
            raise


_END = object()


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
                 out: Callable[[str], None] = print, s3: S3Layout | None = DEFAULT_S3,
                 threads: int = 1, hash_threads: int = HASH_THREADS) -> UpdateResult:
    """Bring the index of a tree up to date, then its manifests.

    A file is read again only when its size or mtime moved, when a digest is missing, or when a
    part layout asks for an ETag the index does not hold. With `force` every file is read -- and a
    file whose size and mtime did NOT move but whose content did keeps its saved digests and is
    reported as damage: a new version would have a new mtime, silent damage does not.

    The part layout of a file is the explicit one from `layouts` if given, else the default `s3`
    one (None: no ETag at all). So the first run after this default arrived reads every file
    above the cutoff once more -- and never again.

    threads: files read at once, finished in their order (run_ordered); hash_threads: threads the
    digests of each file are spread over (StreamHasher). 2 x 5 keeps ten cores busy.
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
        if not parts and s3 is not None:
            parts, multipart = s3.parts(e.size), True
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

    def work(item, stop: threading.Event):
        e, parts, multipart = item
        return hash_file(e.abs_path, parts, multipart, threads=hash_threads, stop=stop)

    def done(item, result, error: Exception | None) -> None:
        if error is not None:
            raise error  # a file that cannot be read stops the run; what is done so far is saved
        e, parts, _multipart = item
        digests, etag = result
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
                return
        e.set_digests(digests)
        e.etag, e.parts, e.verified = etag, parts, now_ts()
        hashed.append(e)
        progress.step("hashed", e)
        saver.maybe_save()

    try:
        run_ordered(todo, work, threads, done)
    finally:
        complete = all(e.has_all_digests() for e in entries)
        saver.save(complete)
    written = write_manifests(root, entries, s3=s3) if manifests and complete else {}
    return UpdateResult(entries, hashed, damaged, complete, written, progress.summary())


@dataclass
class VerifyResult:
    diff: Diff
    plan: VerifyPlan | None
    summary: str


def verify_tree(root: Path, index_path: Path, excludes: Iterable[str] = (),
                selection: FileFilter | None = None, quick: bool = False, resume: bool = False,
                older_than: float | None = None, threads: int = 1,
                out: Callable[[str], None] = print, hash_threads: int = HASH_THREADS) -> VerifyResult:
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
                               bool(p.etag and is_multipart_etag(p.etag)), stop,
                               threads=hash_threads_for(e.size, hash_threads))

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
