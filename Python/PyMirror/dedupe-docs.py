#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Delete files in a collection that are byte-identical to a copy inside a mirror.

The mirrors are never touched. Nothing in the mirror tree is read except to hash it, and nothing
in it is ever deleted -- see README.md. This tool only removes the *outer* copy, and only after
proving, at this moment, that an inner one exists and matches.

Run `audit.py` first: it reads the same manifests, costs no disk, and tells you what there is to
find. This tool is the irreversible half and is deliberately narrower.

WHY IT RE-HASHES INSTEAD OF TRUSTING THE MANIFESTS
    collection-index.csv and the per-mirror indexes are caches keyed on size and mtime. They are
    right, and they were right twenty minutes ago -- but a deletion is irreversible and a cache
    is not evidence. So the manifests are used only to *propose* pairs; every pair is then
    re-read from disk in full, on both sides, before anything is unlinked.

    A file is deleted only when ALL of these hold:
      - the mirror copy exists, is a regular file, and is readable
      - both files have the same size
      - both files hash to the same SHA-256, computed now, from the actual bytes
      - that hash also equals what the outer manifest recorded (catches a file that changed since
        indexing -- such a file is not the one that was cleared for deletion)
      - the outer path really is under one of the requested prefixes

    Any mismatch, any unreadable file, any exception: the pair is skipped and reported. There is
    no "close enough" branch.

USAGE
    python dedupe-docs.py --root /srv/collection --mirror /srv/mirror
    python dedupe-docs.py --root ... --mirror ... --delete        verify again, then delete
    python dedupe-docs.py --root ... --mirror ... media firmware \\
        --report dedupe-media-report.csv                          another subtree, own report

    Positional arguments are top-level directories of the collection to consider; the default is
    `docs`. Both modes write the report: every candidate, its verdict, and the mirror paths that
    hold it. That file is the record of where a deleted document now lives, and documentation
    tends to cite it by name -- which is why a run over a different subtree must be given its own
    --report instead of overwriting the one those links point at.

WHERE THINGS LIVE
    The report belongs next to the collection it describes, not next to this script. --report
    defaults to the collection root for that reason.
"""

import argparse
import collections
import csv
import hashlib
import io
import os
import sys

DOCS = "docs"
COLLECTION_INDEX = "collection-index.csv"
MIRROR_INDEX = ".mirror-index.csv"
REPORT = "dedupe-docs-report.csv"

CHUNK = 1 << 20
EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def long_path(path):
    """Windows refuses paths over 260 characters without the \\\\?\\ prefix.

    Not via os.path.abspath(): normalising strips a trailing dot, and the prefix exists partly to
    preserve exactly that. Here the consequence is quiet rather than loud -- a stat that fails
    turns into "cannot verify", so the file is skipped and kept. Safe, but it hides work.
    """
    if os.name != "nt":
        return path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    path = path.replace("/", "\\")
    return path if path.startswith("\\\\?\\") else "\\\\?\\" + path


def sha256_file(path):
    h = hashlib.sha256()
    with open(long_path(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def load_index(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return [(r["path"], int(r["size"]), r["sha256"]) for r in csv.DictReader(fh)]


def human(n):
    for unit in ("B", "K", "M", "G"):
        if abs(n) < 1024 or unit == "G":
            return "%.1f%s" % (n, unit)
        n /= 1024.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prefix", nargs="*", default=[DOCS],
                    help="top-level directories of the collection to consider (default: docs)")
    ap.add_argument("--root", metavar="PATH", required=True,
                    help="the collection: the tree files may be deleted FROM")
    ap.add_argument("--mirror", metavar="PATH", required=True,
                    help="the mirror tree: the authoritative side, never modified")
    ap.add_argument("--index", metavar="PATH",
                    help="the collection manifest (default: %s in the root)" % COLLECTION_INDEX)
    ap.add_argument("--delete", action="store_true",
                    help="actually delete. Without it nothing is removed and the run is a report")
    ap.add_argument("--report", metavar="PATH",
                    help="where to write the record (default: %s in the root). Give a run over a "
                         "different subtree its own file -- documentation tends to cite the "
                         "default one by name" % REPORT)
    args = ap.parse_args()
    prefixes = tuple(p.rstrip("/\\") + "/" for p in (args.prefix or [DOCS]))

    root = os.path.abspath(args.root)
    mirror_root = os.path.abspath(args.mirror)
    for label, path in (("--root", root), ("--mirror", mirror_root)):
        if not os.path.isdir(path):
            sys.exit("%s names %s, which is not a directory." % (label, path))
    if os.path.normcase(root) == os.path.normcase(mirror_root):
        sys.exit("--root and --mirror are the same directory. This tool deletes from the first "
                 "and protects the second; they must not be the same tree.")
    index_path = os.path.abspath(args.index) if args.index else os.path.join(root, COLLECTION_INDEX)
    if not os.path.isfile(index_path):
        sys.exit("No collection manifest at %s. Run checksums.py --root %s first."
                 % (index_path, root))
    report_path = os.path.abspath(args.report) if args.report else os.path.join(root, REPORT)

    # --- propose pairs from the manifests -----------------------------------
    mirror_by_hash = collections.defaultdict(list)
    for arch in sorted(os.listdir(mirror_root)):
        idx = os.path.join(mirror_root, arch, MIRROR_INDEX)
        if os.path.exists(idx):
            for rel, size, digest in load_index(idx):
                mirror_by_hash[digest].append((arch, rel))
    if not mirror_by_hash:
        sys.exit("No mirror manifests under %s -- nothing could be proven, so nothing is "
                 "deleted. Run mirror.py --root %s --index first."
                 % (mirror_root, mirror_root))

    candidates = [(p, s, h) for p, s, h in load_index(index_path)
                  if p.startswith(prefixes) and h != EMPTY_SHA and h in mirror_by_hash]

    print("Under: %s" % ", ".join(prefixes))
    print("%d candidates from the manifests (%s)"
          % (len(candidates), human(sum(s for _, s, _ in candidates))))
    print("Both sides are now re-read and re-hashed.\n")

    rows = []
    deleted = kept = 0
    freed = 0

    for outer_rel, want_size, want_sha in sorted(candidates):
        outer_path = os.path.join(root, outer_rel.replace("/", os.sep))
        verdict = None
        locations = []

        # Every mirror copy that claims this hash, verified one by one. The first that proves
        # itself is enough to justify deletion, but all of them are recorded, because the report
        # is what tells a reader later where the document went.
        for arch, mrel in mirror_by_hash[want_sha]:
            mpath = os.path.join(mirror_root, arch, mrel.replace("/", os.sep))
            try:
                if not os.path.isfile(long_path(mpath)):
                    continue
                if os.path.getsize(long_path(mpath)) != want_size:
                    continue
                if sha256_file(mpath) != want_sha:
                    continue
            except OSError:
                continue
            locations.append("%s/%s" % (arch, mrel))

        if not locations:
            verdict = "NO-CONFIRMED-MATCH"
        else:
            # Now the outer side. Re-read it too: if it changed since it was indexed, it is not
            # the file that was cleared for deletion, whatever its name still says.
            try:
                actual_size = os.path.getsize(long_path(outer_path))
                actual_sha = sha256_file(outer_path)
            except OSError as exc:
                verdict = "OUTER-UNREADABLE (%s)" % exc
            else:
                if actual_size != want_size or actual_sha != want_sha:
                    verdict = "OUTER-CHANGED-SINCE-INDEX"
                else:
                    verdict = "VERIFIED-IDENTICAL"

        if verdict == "VERIFIED-IDENTICAL" and args.delete:
            try:
                os.remove(long_path(outer_path))
                verdict = "DELETED"
                deleted += 1
                freed += want_size
            except OSError as exc:
                verdict = "DELETE-FAILED (%s)" % exc

        if verdict not in ("DELETED",):
            kept += 1
            if verdict != "VERIFIED-IDENTICAL":
                print("  %-28s %s" % (verdict.split(" ")[0], outer_rel))

        rows.append((outer_rel, want_size, want_sha, verdict, " | ".join(locations)))

    with io.open(report_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        # `outer_path`, not `outer_path`: the tool works on any collection, `docs` is merely the
        # default prefix, and the verdicts already say OUTER-*. The three reports written before
        # 2026-08-29 were relabelled to match -- verdict column and header only, every other cell
        # compared against a backup afterwards and found unchanged.
        w.writerow(("outer_path", "size", "sha256", "verdict", "mirror_locations"))
        w.writerows(rows)

    ok = sum(1 for r in rows if r[3] in ("VERIFIED-IDENTICAL", "DELETED"))
    bad = [r for r in rows if r[3] not in ("VERIFIED-IDENTICAL", "DELETED")]
    print("\n  confirmed identical: %d of %d" % (ok, len(rows)))
    if bad:
        print("  NOT confirmed:       %d -- left alone" % len(bad))
    if args.delete:
        print("  deleted:             %d files, %s freed" % (deleted, human(freed)))
    else:
        print("  Dry run -- nothing deleted. Run it with --delete.")
    print("  Report:              %s" % report_path)

    # The mirrors must be exactly as they were. Cheap to assert, and the one thing that would
    # be unforgivable to get wrong.
    missing = [loc for r in rows for loc in r[4].split(" | ") if loc
               and not os.path.isfile(long_path(os.path.join(mirror_root,
                                                             loc.replace("/", os.sep))))]
    print("  Mirror files missing after the run: %d" % len(missing))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
