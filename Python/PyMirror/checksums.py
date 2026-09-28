#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""SHA-256 over an ordinary directory tree, in the same manifest format the mirrors use.

A mirror carries its own `.mirror-index.csv` and `.sha256sum`, written and kept current by
`mirror.py --index`. This is the same thing for a tree that is *not* a mirror -- a working
collection, a media directory, anything -- written as one pair of files at its top level:

    collection-index.csv    master: path, size, mtime_ns, sha256
    collection.sha256sum    derived, in the format `sha256sum -c` reads

Same format and the same incremental rule: a file is re-hashed only when its size or its mtime
moved, compared in nanoseconds. The format itself -- the index, the sums file, the batched
hashing -- comes from common.py, because a manifest format defined in two places is a manifest
format that will eventually disagree with itself.

    python checksums.py --root /srv/collection            refresh
    python checksums.py --root /srv/collection --force    re-hash everything
    python checksums.py --root /srv/collection --skip scratch --skip incoming

WHERE THE MANIFEST IS WRITTEN
    Next to the tree it describes, because that is the only place it stays true. `--out` can put
    it elsewhere, but then `sha256sum -c` has to be run from the root with the manifest given by
    path -- its entries are relative to the root, not to wherever the file ended up.

WHAT TO LEAVE OUT
    `--skip` names top-level directories the manifest ignores. Use it for anything that already
    carries its own manifest -- a mirror tree, which is why `mirror` is skipped by default -- and
    for anything whose *filenames* should not travel. A manifest is a list of paths, and it gets
    read by people who were never given the files.
"""

import argparse
import os
import sys

# RENAMED 2026-09-22: these were INDEX_FILE and SUMS_FILE here and in mirror.py, where
# they name DIFFERENT files. One identifier, two meanings, in one directory.
from common import (COLLECTION_INDEX, COLLECTION_SUMS, hash_tree, human,
                    long_path, read_index, relative_to, write_index)

# Top-level directories skipped unless --skip says otherwise. `mirror` is here because a mirror
# tree carries its own manifest and must not be described twice; `__pycache__` is not content.
SKIP_TOP = {"mirror", "__pycache__"}


def iter_collection(root, skip):
    """Yield (relative path, absolute path) for every file the manifest should cover."""
    for dirpath, dirnames, names in os.walk(root):
        top = os.path.normcase(dirpath) == os.path.normcase(root)
        dirnames[:] = [d for d in dirnames
                       if d != "__pycache__" and not (top and d in skip)]
        for f in names:
            if f.endswith(".part"):
                continue
            if top and f in (COLLECTION_INDEX, COLLECTION_SUMS):
                continue
            full = os.path.join(dirpath, f)
            rel = relative_to(root, full)
            if rel is not None:
                yield rel, full


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", metavar="PATH", required=True,
                    help="the tree to hash. Required: this tool used to sit inside the tree it "
                         "described, and inheriting that as a default would silently index "
                         "whatever directory the script happens to live in")
    ap.add_argument("--out", metavar="PATH",
                    help="where to write the two manifest files (default: the root itself). "
                         "Entries stay relative to the root wherever they are written")
    ap.add_argument("--skip", action="append", metavar="NAME", default=None,
                    help="top-level directory to leave out; repeatable. Replaces the default "
                         "set (%s)" % ", ".join(sorted(SKIP_TOP)))
    ap.add_argument("--force", action="store_true",
                    help="re-hash every file, ignoring the existing index")
    ap.add_argument("--workers", type=int, default=8, help="hashing threads (default 8)")
    ap.add_argument("--interval", type=float, default=10.0,
                    help="seconds between progress lines (default 10)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit("--root names %s, which is not a directory." % root)
    out = os.path.abspath(args.out) if args.out else root
    if not os.path.isdir(out):
        sys.exit("--out names %s, which is not a directory." % out)
    skip = set(args.skip) if args.skip is not None else set(SKIP_TOP)

    idx_path = os.path.join(out, COLLECTION_INDEX)
    sums_path = os.path.join(out, COLLECTION_SUMS)

    old = {} if args.force else read_index(idx_path)
    rows = {}
    todo = []
    todo_bytes = 0

    for rel, full in iter_collection(root, skip):
        try:
            st = os.stat(long_path(full))
        except OSError:
            continue
        prev = old.get(rel)
        if prev is not None and prev[0] == st.st_size and prev[1] == st.st_mtime_ns:
            rows[rel] = prev
        else:
            todo.append((rel, full, st.st_size, st.st_mtime_ns))
            todo_bytes += st.st_size

    total = len(rows) + len(todo)
    print("%s%s: %d files, %d carried over, %d to hash (%s)"
          % (root, " without %s" % "/, ".join(sorted(skip)) if skip else "",
             total, len(rows), len(todo), human(todo_bytes)), flush=True)

    if not todo:
        if rows == old and os.path.exists(idx_path) and os.path.exists(sums_path):
            print("unchanged", flush=True)
            return
        write_index(idx_path, sums_path, rows)
        print("nothing to hash, index rewritten", flush=True)
        return

    done, done_bytes, failed, elapsed = hash_tree(
        todo, rows, args.workers, args.interval,
        checkpoint=lambda: write_index(idx_path, sums_path, rows))

    print("%d files indexed, %d hashed in %dm%02ds (%.0f MB/s)"
          % (len(rows), done, elapsed // 60, elapsed % 60,
             done_bytes / max(elapsed, 1e-6) / 1e6), flush=True)
    for rel, err in failed[:10]:
        print("  UNREADABLE  %s  (%s)" % (rel, err), flush=True)
    if len(failed) > 10:
        print("  ... and %d more" % (len(failed) - 10), flush=True)


if __name__ == "__main__":
    main()
