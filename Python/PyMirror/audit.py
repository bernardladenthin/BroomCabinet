#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Find duplicates across any number of trees, and files that lie about what they are.

REPORTS ONLY. This script deletes nothing and changes nothing. It prints candidates and a human
decides -- deliberately, because the one thing worse than a redundant copy is a mirror with a
hole in it.

DUPLICATES ARE READ OUT OF MANIFESTS, NOT OFF THE DISK
    Give it the checksum files that `mirror.py --index` and `checksums.py` have already written,
    and it compares whole collections without reading a byte of content. Two consequences worth
    stating plainly:

      * It is exact. The previous version walked the trees and matched on name and size, because
        hashing hundreds of gigabytes to find a handful of matches was not worth the disk pass.
        That found 5 duplicates where the manifests find 163: anything renamed on its way in was
        invisible to it, and a same-name-same-size pair that differed was a false positive.
      * It is cheap enough for terabytes. The work is proportional to the NUMBER of files, not to
        their size.

    The price is that a manifest is a cache -- it was true when it was written. Refresh first if
    it matters, and never delete on this report alone. dedupe-docs.py re-reads both sides in full
    before it removes anything, and that separation is the point.

THE RULE THIS ENCODES
    A mirror is a faithful copy of someone else's tree. Its internal redundancy belongs to the
    source, not to us. oss4aix serves 97 % of `RPMS/` again under `everything/` and 99 % of
    `latest/` and `compatible/` -- of 208 GB only about 85 GB is distinct. Removing that would
    save 100 GB and destroy what the mirror is for: answering *what did this archive serve, and
    under which path*, byte for byte.

    So duplicates are classified by WHERE they sit, and only one class is ever a candidate:

      PROTECTED   every copy lives in a protected tree -- the same one, or two different ones.
                  Never a deletion candidate, not even across mirrors: if two archives both
                  carry a file, both are entitled to their copy.
      CANDIDATE   at least one copy in a protected tree, at least one outside it. The outside
                  copy is the redundant one; the protected tree is the authoritative location.
      LOOSE       no copy in any protected tree. An ordinary duplicate between working
                  directories -- a judgement call, not a rule.

    A tree is protected when its manifest is a mirror's (`.mirror-index.csv`). That needs no
    configuration and cannot be forgotten on the day it matters. `--protect` and `--unprotect`
    override it by label.

USAGE
    python audit.py --index /srv/mirror --index /srv/collection/collection-index.csv
    python audit.py --index ... --csv report.csv        the full list, not just the head
    python audit.py --ruins --root /srv/collection      magic bytes vs extension (reads a little)
    python audit.py --holes --root /srv/collection      whole-megabyte runs of zeros (reads all)

    `--index` takes a manifest file or a directory. A directory is searched at its own level and
    one level down, so pointing it at a mirror root loads every archive in it at once -- which is
    the common case, and naming twelve paths by hand is how one of them silently gets left out.
"""

import argparse
import collections
import csv
import io
import os
import re
import sys

MIRROR_INDEX = ".mirror-index.csv"
COLLECTION_INDEX = "collection-index.csv"
MIRROR_SUMS = ".sha256sum"

# Half-finished downloads. A running mirror always has some, they are not content, and reporting
# them as ruins would bury the real findings. One outage on 2026-08-23 left 11 of them.
SKIP_EXT = {".part"}

BIG_EXT = {".pdf", ".iso", ".img", ".rpm", ".tar", ".gz", ".zip", ".rar", ".z",
           ".squash", ".qcow2", ".ova", ".bff"}
MAGIC = {
    ".pdf": (b"%PDF",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06"),
    ".rar": (b"Rar!",),
    ".gz": (b"\x1f\x8b",),
    ".z": (b"\x1f\x9d", b"\x1f\xa0"),
    ".rpm": (b"\xed\xab\xee\xdb",),
    ".squash": (b"hsqs", b"sqsh"),
    ".qcow2": (b"QFI\xfb",),
}
HTML_HEADS = (b"<!DOC", b"<html", b"<HTML", b"<?xml")

# An autoindex page saved as a file, which is what happens when a listing links a subdirectory
# WITHOUT a trailing slash: the crawler cannot tell it from a file and downloads the index. Then
# nothing below that path can be written, because a filesystem cannot hold a file and a directory
# under one name. Cost on 2026-08-23: 49 files and 7.6 GB behind `rs6000/files`.
#
# It says what it is in its own title, and no genuine document says that about itself.
INDEX_PAGE = re.compile(rb"<title>\s*Index of /|<h1>\s*Index of /", re.I)

# The SHA-256 of nothing. Every empty file matches every other empty file, which is true and
# useless, and on a large collection it is one enormous meaningless group.
EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def long_path(path):
    """Windows refuses paths over 260 characters without the \\\\?\\ prefix.

    Not via os.path.abspath(): normalising strips a trailing dot, which is precisely one of the
    things the prefix exists to preserve, and several files in these trees end in one.
    """
    if os.name != "nt":
        return path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    path = path.replace("/", "\\")
    return path if path.startswith("\\\\?\\") else "\\\\?\\" + path


def ngroups(n):
    """'1 group' / '2 groups'.

    Not named `groups`: audit_duplicates() already binds that name to the classification dict, and
    a module-level function of the same name would be shadowed for the whole function body --
    including the lines above the assignment, where it would raise UnboundLocalError instead.
    """
    return "%d group%s" % (n, "" if n == 1 else "s")


def human(n):
    for unit in ("B", "K", "M", "G", "T"):
        if abs(n) < 1024 or unit == "T":
            return "%.1f %s" % (n, unit)
        n /= 1024.0


# --------------------------------------------------------------------------------- manifests


def find_manifests(target):
    """-> [(manifest path, is a mirror's)] for a file or a directory."""
    if os.path.isfile(target):
        return [(target, os.path.basename(target) == MIRROR_INDEX)]
    if not os.path.isdir(target):
        return []
    found = []
    for name in (COLLECTION_INDEX, MIRROR_INDEX, MIRROR_SUMS):
        p = os.path.join(target, name)
        if os.path.isfile(p):
            found.append((p, name == MIRROR_INDEX))
    try:
        entries = sorted(os.listdir(target))
    except OSError:
        return found
    for e in entries:
        p = os.path.join(target, e, MIRROR_INDEX)
        if os.path.isfile(p):
            found.append((p, True))
    return found


def label_for(manifest, used):
    """A short, unique name for the tree a manifest describes."""
    d = os.path.dirname(os.path.abspath(manifest))
    label = os.path.basename(d) or d
    if label in used:
        parent = os.path.basename(os.path.dirname(d))
        label = "%s/%s" % (parent, label) if parent else d
    base, n = label, 2
    while label in used:
        label, n = "%s#%d" % (base, n), n + 1
    return label


def read_manifest(path):
    """-> [(relative path, size or None, sha256)] from a CSV index or a .sha256sum."""
    rows = []
    if path.endswith(".sha256sum"):
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if len(line) > 66 and line[64:66] in (" *", "  "):
                    rows.append((line[66:], None, line[:64].lower()))
        return rows
    with io.open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                size = int(r["size"])
            except (KeyError, TypeError, ValueError):
                size = None
            rows.append((r.get("path", ""), size, (r.get("sha256") or "").lower()))
    return rows


# -------------------------------------------------------------------------------- duplicates


def load_sources(targets, protect, unprotect):
    """-> [(label, manifest, protected)], resolving directories and applying the overrides."""
    sources, used = [], set()
    for t in targets:
        found = find_manifests(t)
        if not found:
            print("  NO MANIFEST under %s -- skipped" % t)
            continue
        for manifest, is_mirror in found:
            label = label_for(manifest, used)
            used.add(label)
            prot = is_mirror
            if label in protect:
                prot = True
            if label in unprotect:
                prot = False
            sources.append((label, manifest, prot))
    return sources


def audit_duplicates(targets, protect, unprotect, csv_out, head):
    sources = load_sources(targets, protect, unprotect)
    if not sources:
        print("No manifests found. --index takes a file or a directory.")
        return 1

    print("=== Sources ===")
    by_hash = collections.defaultdict(list)      # sha -> [(label, rel, size, protected)]
    total = 0
    for label, manifest, prot in sources:
        try:
            rows = read_manifest(manifest)
        except (OSError, csv.Error) as exc:
            print("  %-26s UNREADABLE (%s)" % (label, exc))
            continue
        for rel, size, sha in rows:
            if sha and sha != EMPTY_SHA:
                by_hash[sha].append((label, rel, size, prot))
        total += len(rows)
        print("  %-26s %8d files  %-11s %s"
              % (label, len(rows), "protected" if prot else "", manifest))
    print("  %d files from %d manifests\n" % (total, len(sources)))

    groups = {"CANDIDATE": [], "LOOSE": [], "PROTECTED": []}
    for sha, copies in by_hash.items():
        if len(copies) < 2:
            continue
        prot = any(c[3] for c in copies)
        unprot = any(not c[3] for c in copies)
        groups["CANDIDATE" if prot and unprot else "PROTECTED" if prot else "LOOSE"].append(
            (sha, copies))

    def biggest(copies):
        return max((c[2] or 0) for c in copies)

    def waste(entries):
        """Bytes held by every copy after the first. Unknown sizes count as zero."""
        return sum(biggest(copies) * (len(copies) - 1) for _, copies in entries)

    print("=== CANDIDATE: in a protected tree AND outside one ===")
    cand = sorted(groups["CANDIDATE"], key=lambda g: -biggest(g[1]))
    outer_bytes = sum(sum((c[2] or 0) for c in copies if not c[3]) for _, copies in cand)
    for sha, copies in cand[:head]:
        print("  %10s  %s" % (human(biggest(copies)), sha[:12]))
        for label, rel, _s, prot in sorted(copies, key=lambda c: (not c[3], c[0], c[1])):
            print("      %-11s %-24s %s" % ("protected" if prot else "outside", label, rel))
    if len(cand) > head:
        print("  ... and %s not shown" % ngroups(len(cand) - head))
    print("  %s; the copies outside hold %s and are expendable,"
          " the protected ones are not\n" % (ngroups(len(cand)), human(outer_bytes)))

    print("=== LOOSE: outside every protected tree -- a judgement call ===")
    loose = sorted(groups["LOOSE"], key=lambda g: -waste([g]))
    for sha, copies in loose[:head]:
        print("  %10s  x%d  %s" % (human(biggest(copies)), len(copies), sha[:12]))
        for label, rel, _s, _p in sorted(copies):
            print("      %-24s %s" % (label, rel))
    if len(loose) > head:
        print("  ... and %s not shown" % ngroups(len(loose) - head))
    print("  %s, %s held twice\n" % (ngroups(len(loose)), human(waste(loose))))

    print("=== PROTECTED: duplicates within or between protected trees ===")
    print("  %s, %s. Not deletable -- which is the purpose, not a limitation:"
          % (ngroups(len(groups["PROTECTED"])), human(waste(groups["PROTECTED"]))))
    print("  a mirror is a copy of somebody else's tree, and its internal redundancy belongs")
    print("  to the source. Two identical files at two paths are two answers.\n")

    if csv_out:
        with io.open(csv_out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(("class", "sha256", "size", "source", "protected", "path"))
            for cls in ("CANDIDATE", "LOOSE", "PROTECTED"):
                for sha, copies in groups[cls]:
                    for label, rel, size, prot in sorted(copies):
                        w.writerow((cls, sha, "" if size is None else size,
                                    label, "yes" if prot else "no", rel))
        print("  Full report: %s" % csv_out)
    return 0


# ------------------------------------------------------------------------ content-level checks


def walk(root):
    for dirpath, dirnames, names in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for n in names:
            p = os.path.join(dirpath, n)
            try:
                yield os.path.getsize(long_path(p)), p
            except OSError:
                pass


def check_ruins(root):
    """A file that lies about what it is. Cheap: a few bytes read per file.

    Two kinds. A wrong magic number is the loud one and was worth fifteen findings on 2026-08-22:
    saved HTTP error pages under .pdf names, indistinguishable from real documents in any listing
    or file count. The quiet one is an autoindex page saved under a directory's name -- it blocks
    everything below that path and produces no error until something tries to write there.
    """
    print("=== Ruins: the contents contradict the extension ===")
    found = 0
    for size, p in walk(root):
        ext = os.path.splitext(p)[1].lower()
        if ext in SKIP_EXT:
            continue
        # A directory name rarely carries an extension, so only the extension-less candidates can
        # be an index page written where a directory belongs.
        if not ext and size < 300_000:
            try:
                with open(long_path(p), "rb") as fh:
                    head = fh.read(4096)
            except OSError:
                continue
            if INDEX_PAGE.search(head):
                m = re.search(rb"Index of (/[^<]*)", head)
                print("  DIRECTORY PAGE saved as a file  %9d B  %s   = index of %s"
                      % (size, os.path.relpath(p, root),
                         m.group(1).decode("utf-8", "replace").strip() if m else "?"))
                found += 1
                continue
        if ext not in BIG_EXT:
            continue
        try:
            with open(long_path(p), "rb") as fh:
                head = fh.read(8)
        except OSError:
            continue
        if head.startswith(HTML_HEADS):
            print("  HTML instead of %-8s %9d B  %s" % (ext, size, os.path.relpath(p, root)))
            found += 1
        elif ext in MAGIC and not head.startswith(MAGIC[ext]):
            print("  wrong magic %-6s %9d B  %s" % (ext, size, os.path.relpath(p, root)))
            found += 1
    print("  %d found\n" % found)
    return found


def check_holes(root, min_size):
    """Find downloads that stopped in the middle without saying so.

    A file can carry the right magic bytes, the right extension and a plausible size and still be
    unusable: an abandoned torrent preallocates the full length and fills pieces out of order, so
    what is missing reads back as zeros. A set of fix-pack archives was found this way -- 827 MB with
    0.8 % of its blocks empty looks perfectly healthy in any directory listing.

    Whole-megabyte runs of zeros are the signature. Real compressed data effectively never
    produces one; sparse disk images legitimately do, which is why they are exempt.
    """
    print("=== Holes: entirely empty blocks in the middle of a file ===")
    print("  (reads every file of %d MB or more in full -- this takes a while)" % (min_size // 1048576))
    blk = 1 << 20
    zero = bytes(blk)
    # Unallocated blocks in a disk image read as zeros and always will. A carved region such as an
    # AIX boot logical volume can be 37 % empty and perfectly intact.
    exempt = {".qcow2", ".img", ".iso", ".raw", ".bin"}
    found = 0
    for size, p in walk(root):
        if size < min_size or os.path.splitext(p)[1].lower() in exempt:
            continue
        n = empty = 0
        try:
            with open(long_path(p), "rb") as fh:
                while True:
                    b = fh.read(blk)
                    if not b:
                        break
                    n += 1
                    if b == zero[:len(b)]:
                        empty += 1
        except OSError:
            continue
        if empty:
            found += 1
            print("  %6.1f MB  %4d/%4d blocks empty (%.1f %%)  %s"
                  % (size / 1048576, empty, n, 100 * empty / n, os.path.relpath(p, root)))
    print("  %d incomplete files\n" % found)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", action="append", metavar="PATH", default=[],
                    help="manifest file, or a directory to find manifests in. Repeatable. A "
                         "directory is searched at its own level and one level down, so a mirror "
                         "root loads every archive in it")
    ap.add_argument("--protect", action="append", metavar="LABEL", default=[],
                    help="treat this source as authoritative even though it is not a mirror")
    ap.add_argument("--unprotect", action="append", metavar="LABEL", default=[],
                    help="the reverse, for a mirror manifest to be treated as ordinary")
    ap.add_argument("--csv", metavar="PATH",
                    help="write every duplicate group here, not just the head of each list")
    ap.add_argument("--head", type=int, default=15,
                    help="groups printed per class (default 15); the counts are always complete")
    ap.add_argument("--ruins", action="store_true", help="magic bytes vs extension; needs --root")
    ap.add_argument("--holes", action="store_true", help="zero-block check; needs --root")
    ap.add_argument("--root", metavar="PATH", help="the tree for --ruins and --holes")
    ap.add_argument("--min-size", type=int, default=16,
                    help="minimum size in MB for --holes (default 16)")
    args = ap.parse_args()

    print("This script deletes nothing. It only reports.\n")

    if args.ruins or args.holes:
        if not args.root or not os.path.isdir(args.root):
            sys.exit("--ruins and --holes read files, so they need --root pointing at a tree.")
        root = os.path.abspath(args.root)
        if args.ruins:
            check_ruins(root)
        if args.holes:
            check_holes(root, args.min_size * 1048576)
        return 0

    if not args.index:
        sys.exit("Nothing to do. Give --index (a manifest, or a directory holding some), or "
                 "--ruins / --holes together with --root.")
    return audit_duplicates(args.index, set(args.protect), set(args.unprotect),
                            args.csv, args.head)


if __name__ == "__main__":
    sys.exit(main())
