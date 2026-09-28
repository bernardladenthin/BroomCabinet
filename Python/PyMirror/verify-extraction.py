# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Check an unpacked container tar against every independent record of it that exists.

    python verify-extraction.py --archive hp-alphaserver-2008 \
        --tar "Q:\mirror\bitsavers\mirrors\h18002.www1.hp.com_20080527.tar" --strip-root

WHY NOT JUST TRUST extract-container-tar.py. It compares the tree with the tar headers the same
process just read. That catches a truncated write and nothing else: if the tool misreads the
archive it misreads it identically both times, and a size check is blind to a flipped byte anyway.
Every real assurance has to come from a record made by somebody else.

THREE CHECKS, AND THEY ARE NOT INTERCHANGEABLE.

  paths     against `<tar>.txt`, the `tar -t` listing bitsavers publishes beside each tar. Made
            years ago on another machine. Answers: is every file here, and is anything here that
            should not be?
  sizes     against the same file, when it is `tar -tv` rather than `tar -t` -- four of the five
            bitsavers manifests carry sizes and timestamps, the agilent one does not. Answers: did
            any file arrive short?
  content   every member re-hashed OUT OF THE TAR and compared with the tree's .sha256sum. This is
            the only check that would catch a bad write, because the two hashes come from two
            different sources. It reads the whole tar again, which is 36 GB for ftp.digital.com.

A run that passes all three has been read by two tools, on two occasions, against a listing made by
a third party. That is as close to proof as this gets.

THE MANIFEST PATHS NEED THE SAME MAPPING THE EXTRACTION USED. A tar can hold `?` and `\` in a
filename and NTFS cannot, so comparing raw manifest paths against on-disk paths would report every
renamed file as both missing and extra. The mapping is imported from extract-container-tar.py
rather than reimplemented -- a second copy would drift, and the drift would look like corruption.
"""
import argparse
import hashlib
import io
import os
import posixpath
import re
import sys
import tarfile
import time

from common import (MIRROR_ROOT, BOOKKEEPING_FILES, COMPLETE_MARKER, SUMS_FILE, long_path,
                    safe_tar_segment)


# `tar -tv`: mode, owner/group, size, date, time, then the name -- which may contain spaces, and
# for a link is followed by " -> target" or " link to target".
LONG = re.compile(r"^([-dlbcpsh])[rwxstST-]{9}\s+\S+\s+(\d+)\s+"
                  r"\d{4}-\d\d-\d\d\s+\d\d:\d\d(?::\d\d)?\s+(.*)$")

# GNU tar's listing ESCAPES the name; the tar header does not. A file whose Unix name holds one
# backslash is printed with two, so comparing the printed form against the header form makes every
# such file look simultaneously missing and extra -- 35 of them in h18002, reported as 70 defects
# that were really one unhandled escape. Reverse it before anything else touches the string.
TAR_ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
               "t": "\t", "v": "\v", "\\": "\\"}


def unescape_tar_name(s):
    r"""Undo GNU tar's C-style quoting: `\\` -> `\`, `\n` -> newline, `\NNN` -> that octal byte."""
    if "\\" not in s:
        return s
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c != "\\" or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        nxt = s[i + 1]
        if nxt in TAR_ESCAPES:
            out.append(TAR_ESCAPES[nxt])
            i += 2
        elif nxt.isdigit() and s[i + 1:i + 4].isdigit() and len(s[i + 1:i + 4]) == 3:
            out.append(chr(int(s[i + 1:i + 4], 8)))
            i += 4
        else:
            # An escape this does not know. Keep the backslash rather than guess -- a wrong guess
            # would be a silent mismatch, and an unknown one is a loud one.
            out.append(c)
            i += 1
    return "".join(out)


def read_tar_listing(path, strip):
    """Reads a TAR LISTING. common.read_manifest() reads a checksum index; the two share no format
    and shared a name. [renamed 2026-09-24]

    -> ({relpath: size or None}, has_sizes, {relpath: target}).

    Directories are included, with size None. LINKS AND DEVICES ARE RETURNED SEPARATELY and are
    NOT in the first dict: Windows cannot create them, the extractor skips them by design and
    records them in SYMLINKS.txt, so counting them as missing would raise the same twelve false
    alarms on every run -- and a check that cries wolf on every run is a check nobody reads.
    """
    entries, has_sizes, links = {}, False, {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            m = LONG.match(line)
            target = ""
            if m:
                has_sizes = True
                kind, size, name = m.group(1), int(m.group(2)), m.group(3)
                for sep in (" -> ", " link to "):
                    if kind in "lh" and sep in name:
                        name, _, target = name.partition(sep)
            else:
                kind, size, name = "?", None, line
            name = unescape_tar_name(name).rstrip("/")
            if strip:
                if name == strip.rstrip("/"):
                    continue
                if not name.startswith(strip):
                    print("   MANIFEST LINE OUTSIDE THE ROOT: %r" % name)
                    continue
                name = name[len(strip):]
            if not name:
                continue
            rel = "/".join(safe_tar_segment(p) for p in name.split("/"))
            if kind in "lhbcps":
                links[rel] = target
            else:
                entries[rel] = size if kind == "-" else None
    return entries, has_sizes, links


def walk_tree(base):
    """-> {relpath: size}. Directories carry None, matching the manifest's shape."""
    out = {}
    pfx = long_path(base)
    for dirpath, dirs, files in os.walk(pfx, onerror=lambda e: print("   WALK ERROR: %s" % e)):
        for n in dirs:
            rel = os.path.join(dirpath, n)[len(pfx):].lstrip("\\").replace("\\", "/")
            out[rel] = None
        for n in files:
            full = os.path.join(dirpath, n)
            rel = full[len(pfx):].lstrip("\\").replace("\\", "/")
            try:
                out[rel] = os.path.getsize(full)
            except OSError:
                out[rel] = -1
    return out


# Files this collection writes about itself. They are not in the tar and must not be reported as
# extra -- but they must be named here explicitly rather than pattern-matched, so that a genuinely
# unexpected file is never waved through by a rule that was meant for our own bookkeeping.


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--tar", required=True)
    ap.add_argument("--manifest", default=None, help="default: <tar>.txt")
    ap.add_argument("--strip-root", action="store_true")
    ap.add_argument("--skip-content", action="store_true",
                    help="skip the hash-from-the-tar pass. It reads the whole tar again; for "
                         "ftp.digital.com that is 36 GB. Skipping it leaves the one check that "
                         "could catch a bad write undone -- say so if you do.")
    args = ap.parse_args()

    tree = os.path.join(os.path.abspath(args.root), args.archive)
    manifest = args.manifest or (args.tar + ".txt")
    strip = ""
    if args.strip_root:
        with tarfile.open(args.tar, "r:") as tf:
            roots = set()
            for m in tf:
                roots.add(m.name.split("/")[0])
                if len(roots) > 1:
                    break
        if len(roots) != 1:
            sys.exit("--strip-root: the tar has %d top-level entries" % len(roots))
        strip = roots.pop() + "/"
        print("stripped root: %r" % strip)

    fails = []

    # ---- 1. paths and sizes, against the third-party manifest ------------------------------
    print("\n[1/3] against %s" % os.path.basename(manifest))
    want, has_sizes, links = read_tar_listing(manifest, strip)
    have = walk_tree(tree)
    for own in BOOKKEEPING_FILES:
        have.pop(own, None)
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    print("      manifest %d entries, tree %d entries" % (len(want), len(have)))
    if links:
        print("      %d links/devices in the manifest, not counted: Windows cannot create them."
              % len(links))
        print("      They are recorded in SYMLINKS.txt with their targets.")
        for rel, tgt in sorted(links.items())[:4]:
            print("         link %s -> %s" % (rel, tgt))
        if not os.path.isfile(os.path.join(tree, "SYMLINKS.txt")):
            print("      BUT SYMLINKS.txt IS NOT THERE -- the links were dropped without a record.")
            fails.append("symlink-record")
        # A LINK WHOSE TARGET IS ALSO MISSING IS A REAL HOLE, not a Windows limitation, and the two
        # must not be reported the same way. The target is relative to the link's own directory.
        dangling = []
        for rel, tgt in sorted(links.items()):
            if not tgt:
                continue
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), tgt))
            if resolved not in have and resolved not in want:
                dangling.append((rel, tgt, resolved))
        if dangling:
            print("      %d links point at something NOT IN THIS TREE:" % len(dangling))
            for rel, tgt, resolved in dangling[:6]:
                print("         DANGLING %s -> %s (would be %s)" % (rel, tgt, resolved))
            fails.append("dangling-links")
        else:
            print("      every link's target is present in this tree.")
    print("      missing from the tree: %d" % len(missing))
    print("      in the tree, not in the manifest: %d" % len(extra))
    for p in missing[:15]:
        print("         MISSING %s" % p)
    for p in extra[:15]:
        print("         EXTRA   %s" % p)
    if missing or extra:
        fails.append("paths")

    if has_sizes:
        short = [(p, have[p], want[p]) for p in want
                 if want[p] is not None and p in have and have[p] != want[p]]
        print("      sizes: %d files compared, %d wrong" % (
            sum(1 for p in want if want[p] is not None), len(short)))
        for p, g, w in short[:15]:
            print("         SIZE %s: %d on disk, manifest says %d" % (p, g, w))
        if short:
            fails.append("sizes")
    else:
        print("      sizes: manifest is `tar -t`, no sizes to compare. NOT CHECKED HERE --")
        print("             the content pass below covers it and more.")

    # ---- 2. content, tar member vs the tree's own checksum index ---------------------------
    if args.skip_content:
        print("\n[2/3] content: SKIPPED at your request. The check that would catch a bad write")
        print("      has not been run.")
        fails.append("content-skipped")
    else:
        print("\n[2/3] re-hashing every member out of the tar", flush=True)
        idx = {}
        with io.open(os.path.join(tree, SUMS_FILE), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                h, rel = line[:64], line[66:].rstrip("\r\n")
                if len(h) == 64 and rel:
                    idx[rel] = h
        # The index covers the archive's own bookkeeping too -- RENAMED.txt is written INTO the
        # tree by the extractor and is naturally not in the tar. Counting it as an index entry the
        # tar failed to cover would report a defect that consists entirely of us.
        ours_in_index = sorted(r for r in idx if r in BOOKKEEPING_FILES)
        for r in ours_in_index:
            idx.pop(r)
        print("      index: %d files (%d of ours set aside: %s)"
              % (len(idx), len(ours_in_index), ", ".join(ours_in_index) or "none"))
        seen, bad, unindexed = 0, [], []
        t0 = time.time()
        with tarfile.open(args.tar, "r:") as tf:
            for m in tf:
                if not m.isreg():
                    continue
                name = m.name[len(strip):] if strip and m.name.startswith(strip) else m.name
                rel = "/".join(safe_tar_segment(p) for p in name.split("/"))
                w = idx.get(rel)
                if w is None:
                    unindexed.append(rel)
                    continue
                h = hashlib.sha256()
                src = tf.extractfile(m)
                while True:
                    b = src.read(8 << 20)
                    if not b:
                        break
                    h.update(b)
                seen += 1
                if h.hexdigest() != w:
                    bad.append(rel)
                    print("         MISMATCH %s" % rel)
                if seen % 2000 == 0:
                    print("         %d/%d  (%.0f s)" % (seen, len(idx), time.time() - t0),
                          flush=True)
        print("      %d members hashed in %.0f s, %d mismatches, %d not in the index"
              % (seen, time.time() - t0, len(bad), len(unindexed)))
        for r in unindexed[:10]:
            print("         NOT INDEXED %s" % r)
        if seen != len(idx):
            print("      %d index entries were never met while walking the tar" % (len(idx) - seen))
            fails.append("index-coverage")
        if bad or unindexed:
            fails.append("content")

    # ---- 3. the marker ---------------------------------------------------------------------
    print("\n[3/3] marker")
    mk = os.path.join(tree, COMPLETE_MARKER)
    if os.path.isfile(mk):
        print("      present")
    else:
        print("      MISSING -- mirror.py --verify has nothing to compare against, and --fresh")
        print("      will not refuse. Write one.")
        fails.append("marker")

    print("\n" + "=" * 74)
    if fails:
        print("  FAILED: %s" % ", ".join(fails))
    else:
        print("  every check passed: paths%s, content, marker"
              % (", sizes" if has_sizes else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
