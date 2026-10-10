#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Checksums for a directory tree in one read, kept current, and re-read later to catch damage.

    python pyfixity.py index  D:\data\photos
    python pyfixity.py verify D:\data\photos --older-than 90

EVERY FOLDER CARRIES ITS OWN RECORD: six files at its root, and nothing about it anywhere else.
    .sha256sum .sha1sum .md5sum .sfv   the digests, in the formats sha256sum -c and QuickSFV read
    .s3etag                            the S3 / B2 ETags of the large files (below)
    .fixity-state.csv                  sizes, times, last checks and run state -- no digest the
                                       manifests hold. Copied, synced or uploaded with the folder,
                                       the record goes along: another machine reads only what changed.
A folder with manifests but no state file (older, or copied without it) is taken over without
reading: a file not modified since the manifests is trusted, a newer one is read. An index of an
earlier version inside the tree (.fixity-index.csv) is taken over and then removed.

COMMANDS
    index TREE      bring the record up to date (reads only what changed), then write the
                    manifests .sha256sum .sha1sum .md5sum .sfv and .s3etag at the root of TREE
        --force     read every file; a saved checksum is NEVER replaced when size and mtime are
                    unchanged -- that is damage, and it is reported (exit status 1)
        --parts F   CSV with path,parts,etag: the real S3 multipart layouts of a cloud copy; they
                    take precedence over the default below (parts like 100000000*3,4200)
        --no-manifests   index only
    verify TREE     re-read files against the index: new, gone, resized, re-dated, damaged
        --quick     names, sizes and times only; read nothing
    manifests TREE  write the manifests from the index, reading nothing

S3 / B2 ETAGS (index and manifests), ON BY DEFAULT
    A file uploaded to S3 or B2 in parts gets no whole-file checksum there, only an ETag over its
    parts -- which no whole-file digest can be turned into later. So every file above the cutoff
    gets that ETag in the same read, and .s3etag lists them, ready to compare with the cloud.
    --s3-part-size SIZE   default 100000000 (B2's recommended part size, Cyberduck's chunk);
                          0 switches the ETag off
    --s3-cutoff SIZE      default 200M: larger files are uploaded in parts (Cyberduck's rule)

COMMON
    --index FILE        keep the record in an index OUTSIDE the tree instead of the state file
                        (with all digests, and a .state file beside it) -- for a tree that must
                        not be written to apart from its manifests
    --exclude-glob P    never look at files matching P (name or relative path; repeatable)

SPEED (index and verify). The CPU, not the disk, is usually the limit: all digests in one thread
manage about 200 MB/s, one thread per digest about 620 MB/s. The data is read once either way.
    --hash-threads N    threads the digests of each file are spread over (default 5 = one per
                        digest; 1 = all in the reading thread). Files under 8 MiB use one.
    --threads N         files at once (default 1). index finishes them in their order, so its
                        output and an interrupted index look exactly as with one; e.g. 2 x 5

VERIFY RUNS
    --resume            continue an interrupted run
    --older-than DAYS   only files not successfully checked for DAYS
    --include REGEX / --exclude REGEX   relative path, repeatable, case-insensitive
    --min-size SIZE (inclusive) / --max-size SIZE (exclusive)   500, 64K, 1M, 1.5G

The manifests are what OpenHashTab, sha256sum -c, md5sum -c and QuickSFV read. They are rewritten
only when their text changes, and they never list themselves, the index or its state file.

Exit status: 0 nothing wrong, 1 differences or damage found, 2 error.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import fixity


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def read_layouts(path: Path, by_name: bool) -> fixity.Layouts:
    layouts: fixity.Layouts = {}
    with open(fixity.long_path(path), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            parts = fixity.decode_parts(r.get("parts"))
            if not parts:
                continue
            key = fixity.basename(r["path"]) if by_name else r["path"]
            layouts[fixity.norm(key)] = (parts, fixity.is_multipart_etag(r.get("etag") or "-"))
    return layouts


def print_diff(name: str, d: fixity.Diff, limit: int) -> None:
    lb = d.labels
    print(f"\n=== {name}: {'DIFFERENCES' if d.has_differences() else 'unchanged'}  "
          f"({lb.left} {d.left_count} files, {lb.right} {d.right_count} files)")
    if d.ok or d.checksum or d.checksum_unknown:
        used = ", ".join(f"{k} {v}" for k, v in sorted(d.ok.items()))
        print(f"  checksum identical: {d.identical}" + (f"  ({used})" if used else ""))
    if d.skipped:
        print(f"  not read (checked recently): {d.skipped}")

    def section(title: str, rows: list[str]) -> None:
        if not rows:
            return
        print(f"  {title}: {len(rows)}")
        for r in rows[:limit] if limit else rows:
            print(f"    {r}")
        if limit and len(rows) > limit:
            print(f"    ... and {len(rows) - limit} more (--limit 0 shows all)")

    section(lb.only_left, [f"+ {e.path}" for e in d.only_left])
    section(lb.only_right, [f"- {e.path}" for e in d.only_right])
    section("size differs", [f"~ {a.path}  {fixity.fmt_size(a.size)} / {fixity.fmt_size(b.size)}" for a, b in d.size])
    section("modification time differs",
            [f"~ {a.path}  {fixity.fmt_ns(a.mtime_ns)} / {fixity.fmt_ns(b.mtime_ns)}" for a, b in d.mtime])
    section("checksum differs (same size: damage, or a changed file with a new time)",
            [f"! {a.path}" for a, _b in d.checksum])
    section("read error", [f"X {a.path}  ({d.notes.get(a.path, '')})" for a, _b in d.errors])
    section("not checkable (no digest saved)", [f"? {a.path}" for a, _b in d.checksum_unknown])


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("tree", type=Path, help="the directory tree")
    common.add_argument("--index", type=Path,
                        help=f"an index outside the tree (default: the folder's own {fixity.STATE_FILE})")
    common.add_argument("--exclude-glob", action="append", default=[], metavar="PATTERN",
                        help="never look at files matching PATTERN (name or relative path)")
    common.add_argument("--limit", type=int, default=50, help="max. lines per category (0 = all)")

    speed = argparse.ArgumentParser(add_help=False)
    g = speed.add_argument_group("speed")
    g.add_argument("--threads", type=int, default=1, metavar="N", help="files at once (default 1)")
    g.add_argument("--hash-threads", type=int, default=fixity.HASH_THREADS, metavar="N",
                   help=f"threads per file for the digests (default {fixity.HASH_THREADS}; 1 = none)")

    s3 = argparse.ArgumentParser(add_help=False)
    g = s3.add_argument_group("S3 / B2 ETag (on by default)")
    g.add_argument("--s3-part-size", default=str(fixity.S3_PART_SIZE), metavar="SIZE",
                   help=f"part size of the uploader (default {fixity.S3_PART_SIZE}; 0 = no ETag)")
    g.add_argument("--s3-cutoff", default="200M", metavar="SIZE",
                   help="files larger than this are uploaded in parts (default 200M = 209715200)")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("index", parents=[common, s3, speed], help="update the index, then write the manifests")
    p.add_argument("--force", action="store_true", help="read every file, not only changed ones")
    p.add_argument("--parts", type=Path, metavar="FILE", help="CSV path,parts,etag: multipart layouts")
    p.add_argument("--parts-by-name", action="store_true",
                   help="match --parts by file name only (for a cloud copy uploaded without directories)")
    p.add_argument("--no-manifests", action="store_true", help="index only")
    p = sub.add_parser("verify", parents=[common, speed], help="re-read files against the index")
    p.add_argument("--quick", action="store_true", help="names, sizes and times only; read nothing")
    p.add_argument("--resume", action="store_true", help="continue an interrupted run")
    p.add_argument("--older-than", type=float, metavar="DAYS", help="only files not checked for DAYS")
    p.add_argument("--include", action="append", default=[], metavar="REGEX")
    p.add_argument("--exclude", action="append", default=[], metavar="REGEX")
    p.add_argument("--min-size", metavar="SIZE")
    p.add_argument("--max-size", metavar="SIZE")
    sub.add_parser("manifests", parents=[common, s3], help="write the manifests from the index")
    return ap


def s3_layout(args) -> fixity.S3Layout | None:
    try:
        part_size, cutoff = fixity.parse_size(args.s3_part_size), fixity.parse_size(args.s3_cutoff)
    except ValueError as e:
        fail(f"invalid S3 size: {e}")
    return fixity.S3Layout(part_size, cutoff) if part_size > 0 else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tree: Path = args.tree
    if not tree.is_dir():
        fail(f"not a directory: {tree}")
    index = args.index  # None: the folder's own record
    record = index or tree / fixity.STATE_FILE

    if args.command == "index":
        layouts = read_layouts(args.parts, args.parts_by_name) if args.parts else None
        key = fixity.basename if args.parts_by_name else (lambda p: p)
        r = fixity.update_index(tree, index, args.exclude_glob, layouts, key, args.force,
                                manifests=not args.no_manifests, s3=s3_layout(args),
                                threads=max(1, args.threads), hash_threads=max(1, args.hash_threads))
        print(f"  -> {record}  ({r.summary}){'' if r.complete else '  INCOMPLETE'}")
        for name, what in r.manifests.items():
            print(f"  {name}: {what}")
        if r.damaged:
            print(f"  WARNING: {len(r.damaged)} file(s) with different content at the same size and time "
                  f"(possible silent damage); the saved checksums were kept:")
            for e, _new in r.damaged:
                print(f"    ! {e.path}")
            return 1
        return 0

    if args.command == "manifests":
        entries = fixity.read_index(index) if index else fixity.folder_record(tree, args.exclude_glob)[0]
        live = {e.path for e in fixity.scan_tree(tree, args.exclude_glob, fixity.own_files(tree, index))}
        entries = [e for e in entries if e.path in live]
        for name, what in fixity.write_manifests(tree, entries, s3=s3_layout(args)).items():
            print(f"  {name}: {what}")
        return 0

    try:
        selection = fixity.FileFilter(
            include=args.include, exclude=args.exclude,
            min_size=fixity.parse_size(args.min_size) if args.min_size else None,
            max_size=fixity.parse_size(args.max_size) if args.max_size else None)
    except (ValueError, re.error) as e:
        fail(f"invalid selection: {e}")
    print(f"verifying {tree} against {record} ...")
    r = fixity.verify_tree(tree, index, args.exclude_glob, selection, args.quick, args.resume,
                           args.older_than, max(1, args.threads), hash_threads=max(1, args.hash_threads))
    if r.summary:
        print(f"  read: {r.summary}")
    print_diff(tree.name, r.diff, args.limit)
    return 1 if r.diff.has_differences() else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted (progress has been saved).", file=sys.stderr)
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
