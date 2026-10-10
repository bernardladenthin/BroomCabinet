# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The B2 side of PyB2Verify, without the network: what B2 states about a file, and how that is
recorded, compared and explained. Covered by `b2lib_test.py`.

EVERYTHING ABOUT THE LOCAL TREE LIVES IN PyFixity, not here. Hashing a directory in one read,
its index, its manifests and its verification runs are ../PyFixity/fixity.py, which this module
imports by path: one implementation, shared, instead of two that drift apart. What is left here
is what only B2 knows -- file ids, the source of a checksum (B2 metadata, S3 ETag, or our own
download), unfinished uploads -- and the one-time move of the first version's local checksum files
onto PyFixity's index.

THE ONE IDEA THAT MAKES LARGE FILES CHECKABLE. B2 records a SHA-1 for a file uploaded in one piece,
but a large file is uploaded in parts and often carries no SHA-1 at all. Its S3 ETag is the MD5 of
the concatenated part MD5s; with the part sizes, PyFixity cuts the local file the same way in the
same read that computes its other digests.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

# ONE IMPLEMENTATION OF THE LOCAL SIDE: PyFixity, beside this project in the same repository.
_FIXITY = Path(__file__).resolve().parent.parent / "PyFixity"
if str(_FIXITY) not in sys.path:
    sys.path.insert(0, str(_FIXITY))

import fixity  # noqa: E402

TS_FORMAT = fixity.TS_FORMAT
YES = fixity.YES
INCOMPLETE = fixity.INCOMPLETE
SNAPSHOT_COLUMNS = ["size", "mtime_ms", "sha1", "etag", "parts", "verified", "source", "file_id", "path"]

# Header keys and values as the first, German-language version of this tool wrote them. Files from
# that version are read and translated; files are always written in English.
LEGACY_META_KEYS = {"seite": "side", "erzeugt": "created", "vollstaendig": "complete",
                    "verify_vollstaendig": "verify_complete"}

# The files PyFixity writes at the root of a tree: the five manifests and its state file. They are
# uploaded with the tree, but they describe it rather than belong to it, so neither side's
# comparison counts them. The state file was missing here at first: once uploaded, check and
# compare reported it as a file only in B2 (seen 2026-10-10, the day it was introduced).
ROOT_MANIFESTS = frozenset(fixity.MANIFEST_FILES.values()) | {fixity.ETAG_MANIFEST, fixity.STATE_FILE}


@dataclass
class FileEntry:
    """A file as B2 states it (or as the first version's local checksum files recorded it)."""
    path: str  # the file name in the bucket
    size: int
    mtime_ms: int
    sha1: str | None = None
    etag: str | None = None  # S3 ETag: an MD5, or "<md5 of the part md5s>-<part count>"
    parts: list[int] | None = None  # the part sizes that belong to the ETag
    source: str = ""  # b2 (metadata) | s3 (ETag) | download (downloaded and hashed) | local (legacy)
    file_id: str = ""
    verified: str = ""  # last successful content check (TS_FORMAT); empty = never, or failed
    key: str = ""  # the file name exactly as stored, for S3; not stored
    skipped: bool = False  # verification run: not read this time; not stored

    @property
    def mtime_ns(self) -> int:
        """So PyFixity's comparison, which works in nanoseconds, can take a B2 entry as it is."""
        return self.mtime_ms * 1_000_000


LOCAL_VS_B2 = fixity.Labels("Local", "B2", "Only local (missing in B2)", "Only in B2 (missing locally)")
B2_NOW_VS_SAVED = fixity.Labels("Current", "Saved", "New (not in the checksums)", "Gone (only in the checksums)")
CONTENT_VS_META = fixity.Labels("Content", "Metadata", "Read only", "Not read")


def is_root_manifest(path: str) -> bool:
    return path in ROOT_MANIFESTS


# --------------------------------------------------------------------------- the B2 checksum file

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
            w.writerow([e.size, e.mtime_ms, e.sha1 or "", e.etag or "", fixity.encode_parts(e.parts),
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
                             r.get("etag") or None, fixity.decode_parts(r.get("parts", "")),
                             r["source"], r["file_id"], r.get("verified") or "")
                   for r in csv.DictReader(f, delimiter="\t")]
    return meta, entries


def new_meta(bucket: str, side: str, prev_meta: dict[str, str] | None = None) -> dict[str, str]:
    meta = {"bucket": bucket, "side": side, "created": fixity.now_ts(), "complete": INCOMPLETE}
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
    """Writes the B2 checksum file at intervals, so an interruption loses at most one interval."""

    def __init__(self, path: Path, meta: dict[str, str], entries: list[FileEntry],
                 complete_key: str = "complete", keep: Callable[[FileEntry], object] = lambda e: True,
                 interval: float = fixity.SAVE_INTERVAL) -> None:
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


# --------------------------------------------------------------------------- moving to PyFixity

def migrate_local_tsv(tsv: Path, index: Path, root: Path, excludes: list[str]) -> tuple[int, int]:
    """Carry a first-version local checksum file (`<bucket>.tsv`) over into PyFixity's index.

    -> (entries adopted, entries left to be read again). Nothing is read: an entry is adopted when
    the file still has its recorded size and modification time, with the time compared at the
    millisecond precision the old file stored (allowing one millisecond for float rounding). The
    old file had only SHA-1 (and an ETag for large files), so the next `hash-local` reads every
    file once more to add SHA-256, MD5 and CRC32 -- and checks the old SHA-1 on the way, so damage
    since the first run is reported, not written over. The old file is kept as `.tsv.migrated`.
    """
    meta, old = read_snapshot(tsv)
    current = {e.path: e for e in fixity.scan_tree(root, excludes, fixity.own_files(root, index))}
    adopted: list[fixity.Entry] = []
    for o in old:
        c = current.get(o.path)
        if c and c.size == o.size and abs(c.mtime_ns // 1_000_000 - o.mtime_ms) <= 1 and o.sha1:
            adopted.append(fixity.Entry(o.path, o.size, c.mtime_ns, sha1=o.sha1, etag=o.etag,
                                        parts=o.parts, verified=o.verified))
    fixity.write_index(index, adopted)
    state = {"created": meta.get("created", fixity.now_ts()),
             "complete": "no (migrated from the first version; run hash-local)"}
    for key in ("verify_start", "verify_complete"):
        if key in meta:
            state[key] = meta[key]
    fixity.write_state(index, state)
    os.replace(tsv, tsv.with_name(tsv.name + ".migrated"))
    return len(adopted), len(old) - len(adopted)


# --------------------------------------------------------------------------- what B2 states

def expected_from_metadata(e: FileEntry) -> FileEntry:
    """The checksum a content check of a B2 file must reproduce.

    Source 'b2' (SHA-1 from the B2 metadata) and 'download' (computed earlier by this tool): the
    SHA-1. Source 's3': the ETag is what B2 actually states; a SHA-1 this tool learned from an
    earlier download is our own record, not B2's, and does not count as metadata.
    """
    return replace(e, sha1=None, skipped=False) if e.source == "s3" else replace(e, skipped=False)


def b2_state(now, saved, candidates: list[FileEntry] | None) -> str:
    """A local file changed: how does the copy in B2 relate to the saved and the current content?"""
    if candidates is None:
        return "no B2 checksums available (run hash-b2)"
    if not candidates:
        return "not in B2"
    if len(candidates) > 1:
        return "name occurs more than once in B2, ambiguous"
    r = candidates[0]
    m_saved, m_now = fixity.checksums_match(saved, r)[0], fixity.checksums_match(now, r)[0]
    if m_saved:
        return "B2 intact (matches the saved checksum) -> restorable from B2"
    if m_now:
        return "B2 holds the same content as the local file now"
    if m_saved is None or m_now is None:
        return "B2 not comparable (B2 has only an ETag, the local part MD5s are missing)"
    return "B2 differs from both"


def local_state(content: FileEntry, candidates: list | None) -> str:
    """A B2 file does not match its metadata: how does the local file relate to what B2 delivered?"""
    if candidates is None:
        return "no local checksums available"
    if not candidates:
        return "not present locally"
    if len(candidates) > 1:
        return "name occurs more than once locally, ambiguous"
    match = fixity.checksums_match(content, candidates[0])[0]
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


def stale_b2_hint(diff: fixity.Diff, b2_created: str | None) -> str | None:
    """A hint when the saved B2 checksums are probably older than what was uploaded since.

    compare works on what hash-b2 recorded, not on the live bucket. A file uploaded after that
    shows up as 'only local' (or as a size or checksum difference) although it is in B2 by now --
    seen on 2026-10-04, when two newly uploaded files were reported missing against a B2 record
    three days old. If a local file on the differing side is NEWER than the B2 record, that is the
    likely explanation, and the cheap fix is another hash-b2 before believing the difference.
    """
    if not b2_created:
        return None
    try:
        # The record keeps whole seconds, so the moment it was made lies anywhere in that second:
        # a file is "newer" only from the next second on.
        created_ns = int(datetime.strptime(b2_created, TS_FORMAT).timestamp() * 1e9) + 1_000_000_000
    except ValueError:
        return None
    # Only what an upload since would explain: missing in B2, or different there. 'Not checkable'
    # means the LOCAL part MD5s are missing, which no new hash-b2 changes.
    local_side = list(diff.only_left) + [a for a, _b in diff.size + diff.checksum]
    newer = [e for e in local_side if e.mtime_ns > created_ns]
    if not newer:
        return None
    return (f"the B2 checksums are from {b2_created}; {len(newer)} differing local file(s) are newer than "
            f"that - probably uploaded since. Run hash-b2 for this bucket before trusting the difference.")


def fmt_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime(TS_FORMAT)


def copy_entry(e, **changes):
    return replace(e, **changes)
