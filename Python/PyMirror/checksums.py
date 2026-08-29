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
moved, compared in nanoseconds. The primitives come from mirror.py by import rather than by
copying, because a manifest format defined in two places is a manifest format that will
eventually disagree with itself.

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
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

INDEX_FILE = "collection-index.csv"
SUMS_FILE = "collection.sha256sum"

# Top-level directories skipped unless --skip says otherwise. `mirror` is here because a mirror
# tree carries its own manifest and must not be described twice; `__pycache__` is not content.
SKIP_TOP = {"mirror", "__pycache__"}


def _load_mirror_tool():
    """Load mirror.py, which sits next to this file, by path.

    By path and not by `import mirror`, because a directory named `mirror/` is a plausible thing
    to find beside either script -- and it would be a candidate for the same module name, a
    namespace package shadowing the module or not depending on how the script was started.
    """
    path = os.path.join(HERE, "mirror.py")
    if not os.path.isfile(path):
        sys.exit("mirror.py is expected next to this script, at %s.\n"
                 "  The manifest format lives there; this tool only applies it to a tree that "
                 "is not a mirror." % path)
    spec = importlib.util.spec_from_file_location("_mirror_tool", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mt = _load_mirror_tool()


def iter_collection(root, skip):
    """Yield (relative path, absolute path) for every file the manifest should cover."""
    for dirpath, dirnames, names in os.walk(root):
        top = os.path.normcase(dirpath) == os.path.normcase(root)
        dirnames[:] = [d for d in dirnames
                       if d != "__pycache__" and not (top and d in skip)]
        for f in names:
            if f.endswith(".part"):
                continue
            if top and f in (INDEX_FILE, SUMS_FILE):
                continue
            full = os.path.join(dirpath, f)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


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

    idx_path = os.path.join(out, INDEX_FILE)
    sums_path = os.path.join(out, SUMS_FILE)

    old = {} if args.force else mt.read_index(idx_path)
    rows = {}
    todo = []
    todo_bytes = 0

    for rel, full in iter_collection(root, skip):
        try:
            st = os.stat(mt.long_path(full))
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
             total, len(rows), len(todo), mt.human(todo_bytes)), flush=True)

    if not todo:
        if rows == old and os.path.exists(idx_path) and os.path.exists(sums_path):
            print("unchanged", flush=True)
            return
        mt.write_index(idx_path, sums_path, rows)
        print("nothing to hash, index rewritten", flush=True)
        return

    done, done_bytes, failed, elapsed = mt.hash_tree(
        todo, rows, args.workers, args.interval,
        checkpoint=lambda: mt.write_index(idx_path, sums_path, rows))

    print("%d files indexed, %d hashed in %dm%02ds (%.0f MB/s)"
          % (len(rows), done, elapsed // 60, elapsed % 60,
             done_bytes / max(elapsed, 1e-6) / 1e6), flush=True)
    for rel, err in failed[:10]:
        print("  UNREADABLE  %s  (%s)" % (rel, err), flush=True)
    if len(failed) > 10:
        print("  ... and %d more" % (len(failed) - 10), flush=True)


if __name__ == "__main__":
    main()
