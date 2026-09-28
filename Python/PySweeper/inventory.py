#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Write down every file in a working directory, so the decision can be made once and read back.

sweep.py deletes nothing it cannot find a row for. This builds those rows: one line per file with
its size, mtime, SHA-256, a group, and two columns a person fills in -- `decision` and `reason`.

THE DECISION COLUMN STARTS EMPTY, AND THAT IS THE POINT. A tool that guesses "delete" and asks
for a veto gets the veto it deserves only for the files somebody looked at. The default here is
"keep" by omission: an unedited inventory sweeps nothing.

WHAT --held-in IS FOR. Most of a working directory is copies. `--held-in Q:\mirror` hashes that
collection once and marks every file whose content is already in it, with the path where it is
held written into the reason -- "held in Q:\mirror\tuhs\tarball_tocs.txt.gz", not "duplicate".
A reason a person cannot check is not a reason. Matching is by CONTENT: a name shared with an
archive member proves nothing, and the first real run of this found a Makefile that matched a tar
member by name and differed in bytes.

RE-RUNNING KEEPS WHAT YOU WROTE. An existing inventory is read first and its decision/reason/group
columns are carried over for every path still present, so the file survives another pass after
the directory changed. Nothing is written in place: a temp file is renamed over the old one, after
it is complete. A `csv.DictWriter(open(CSV, "w"))` without a `with` truncated an inventory once.

    python inventory.py --root DIR
    python inventory.py --root DIR --held-in Q:\mirror --held-in Q:\mirrorLess
    python inventory.py --root DIR --summary
"""

import argparse
import csv
import hashlib
import os
import stat
import sys

DEFAULT_CSV = "sweep-inventory.csv"
COLUMNS = ["decision", "group", "reason", "size", "mtime", "sha256", "path"]
LONG_PREFIX = "\\\\?\\"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# Extension -> group. A group is a handle for "sweep these together", not a claim about content:
# the reason column says what a file is, this only says which pass it belongs to.
GROUPS = {
    ".log": "logs", ".txt": "text", ".out": "logs", ".err": "logs",
    ".htm": "pages", ".html": "pages", ".css": "pages", ".js": "pages",
    ".png": "images", ".jpg": "images", ".jpeg": "images", ".gif": "images",
    ".svg": "images", ".ico": "images",
    ".py": "scripts", ".sh": "scripts", ".bat": "scripts", ".tcl": "scripts",
    ".c": "source", ".h": "source", ".cc": "source", ".cpp": "source", ".s": "source",
    ".patch": "patches", ".diff": "patches",
    ".tar": "archives", ".gz": "archives", ".xz": "archives", ".bz2": "archives",
    ".zip": "archives", ".z": "archives", ".tgz": "archives",
    ".csv": "data", ".json": "data", ".tsv": "data", ".xml": "data",
    ".pdf": "documents",
}


def long_path(path):
    absolute = os.path.abspath(path)
    if os.name != "nt" or absolute.startswith(LONG_PREFIX):
        return absolute
    return LONG_PREFIX + absolute


def is_reparse_point(path):
    try:
        info = os.lstat(long_path(path))
    except FileNotFoundError:
        return False
    except OSError:
        return True
    attrs = getattr(info, "st_file_attributes", None)
    if attrs is not None and attrs & FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    return os.path.islink(path)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(long_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_files(root, skip_names):
    """Yield (relative path, lstat) for every regular file under root.

    A JUNCTION IS NOT DESCENDED. Walking through one puts foreign paths in the inventory under
    names that look local, and sweep.py would then correctly refuse every one of them -- after a
    person had already read the list and believed it.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames)
                       if d not in skip_names
                       and not is_reparse_point(os.path.join(dirpath, d))]
        for name in sorted(filenames):
            if name in skip_names:
                continue
            full = os.path.join(dirpath, name)
            if is_reparse_point(full):
                continue
            try:
                info = os.lstat(long_path(full))
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            yield os.path.relpath(full, root).replace(os.sep, "/"), info


def index_collection(roots, log):
    """-> {sha256: first path where it is held}, over every file under every named root."""
    index = {}
    for root in roots:
        real = os.path.realpath(root)
        if not os.path.isdir(real):
            log("  --held-in %s is not a directory, skipped" % root)
            continue
        count = 0
        for rel, info in walk_files(real, set()):
            if info.st_size == 0:
                continue
            full = os.path.join(real, rel.replace("/", os.sep))
            try:
                index.setdefault(sha256_of(full), full)
            except OSError:
                continue
            count += 1
            if count % 5000 == 0:
                log("  %s: %d files hashed" % (root, count))
        log("  %s: %d files, %d distinct contents so far" % (root, count, len(index)))
    return index


def read_existing(csv_path):
    """-> {path: row} of what a person already decided, or {} when there is no inventory yet."""
    if not os.path.isfile(csv_path):
        return {}
    with open(csv_path, encoding="utf-8", newline="") as handle:
        return {row["path"]: row for row in csv.DictReader(handle) if row.get("path")}


def write_rows(csv_path, rows):
    """Write completely to a temp file, then rename over the target."""
    temp = csv_path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(temp, csv_path)


def summarise(rows):
    by_group = {}
    for row in rows:
        entry = by_group.setdefault(row["group"], [0, 0, 0])
        entry[0] += 1
        entry[1] += int(row["size"])
        if row["decision"] == "delete":
            entry[2] += 1
    print("\n  %-14s %7s %10s %9s" % ("group", "files", "MB", "delete"))
    for group, (count, size, marked) in sorted(by_group.items(), key=lambda kv: -kv[1][1]):
        print("  %-14s %7d %10.1f %9d" % (group, count, size / 1e6, marked))
    total = sum(int(r["size"]) for r in rows)
    marked = sum(1 for r in rows if r["decision"] == "delete")
    print("  %-14s %7d %10.1f %9d" % ("TOTAL", len(rows), total / 1e6, marked))


def main():
    parser = argparse.ArgumentParser(
        description="Write down every file in a working directory, one row each.")
    parser.add_argument("--root", metavar="DIR", help="the directory to inventory")
    parser.add_argument("--out", metavar="FILE",
                        help="where to write (default: %s inside the root)" % DEFAULT_CSV)
    parser.add_argument("--held-in", action="append", default=[], metavar="DIR",
                        help="a collection to compare against by content; a file already held "
                             "there is pre-marked 'delete' with the holding path as its reason. "
                             "Repeatable")
    parser.add_argument("--skip", action="append", default=[], metavar="NAME",
                        help="a file or directory name to leave out entirely. Repeatable")
    parser.add_argument("--no-hash", action="store_true",
                        help="leave the sha256 column empty. Faster, and sweep.py then has "
                             "only size and mtime to re-check a row against")
    parser.add_argument("--summary", action="store_true",
                        help="print the per-group table and write nothing")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    if not args.root:
        parser.print_help()
        return 0
    root = os.path.realpath(args.root)
    if not os.path.isdir(root):
        print("REFUSED: %s is not a directory" % root)
        return 2

    csv_path = args.out or os.path.join(root, DEFAULT_CSV)
    skip = set(args.skip) | {".sweepable", "sweep.log", os.path.basename(csv_path),
                             os.path.basename(csv_path) + ".tmp", "__pycache__", ".git"}

    if args.held_in and args.no_hash:
        print("REFUSED: --held-in compares content, so it cannot run with --no-hash")
        return 2

    held = {}
    if args.held_in:
        print("indexing the collections by content:")
        held = index_collection(args.held_in, print)

    previous = read_existing(csv_path)
    rows = []
    for rel, info in walk_files(root, skip):
        digest = ""
        if not args.no_hash:
            try:
                digest = sha256_of(os.path.join(root, rel.replace("/", os.sep)))
            except OSError as exc:
                print("  unreadable, left out: %s (%s)" % (rel, exc.__class__.__name__))
                continue
        old = previous.get(rel, {})
        decision = old.get("decision", "")
        reason = old.get("reason", "")
        if not decision and digest and digest in held:
            decision = "delete"
            reason = "held in %s" % held[digest]
        rows.append({
            "decision": decision,
            "group": old.get("group") or GROUPS.get(os.path.splitext(rel)[1].lower(), "other"),
            "reason": reason,
            "size": info.st_size,
            "mtime": "%.0f" % info.st_mtime,
            "sha256": digest,
            "path": rel,
        })

    carried = sum(1 for r in rows if r["path"] in previous and previous[r["path"]].get("decision"))
    print("\n  %d files under %s" % (len(rows), root))
    if previous:
        print("  %d decisions carried over from the existing inventory" % carried)
    if held:
        print("  %d pre-marked as held elsewhere" % sum(
            1 for r in rows if r["reason"].startswith("held in ")))
    summarise(rows)

    if args.summary:
        print("\n  --summary: nothing written.")
        return 0
    write_rows(csv_path, rows)
    print("\n  written to %s" % csv_path)
    print("  Fill the 'decision' column with 'delete' where you mean it, say why in 'reason',")
    print("  then: python sweep.py --root %s" % root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
