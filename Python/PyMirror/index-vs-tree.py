# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What changed in an archive since its checksum index was written? Names, not counts. Reads only.

    python index-vs-tree.py --archive bitsavers
    python index-vs-tree.py --archive fsck-vendors --expect-gone "NeXT/next.68k.org Archive/next.68k.org.tar"

WHY NOT `mirror.py --verify`. That compares the tree's FILE COUNT and BYTE TOTAL against the marker
and says so itself: counts cannot see a file whose disappearance is balanced by another's arrival,
and they cannot name anything. This collection has already been bitten -- 21 files with trailing
dots vanished under a --verify that reported the archive unchanged.

WHY NOT `verify-content.py`. That re-reads and re-hashes every byte, which for bitsavers is 1.24 TB
and hours. The question here is not "are the bytes right" but "is the set of names still the set of
names", and that is a directory walk against a text file.

WHAT IT IS FOR. Before re-indexing an archive, prove that the difference between the recorded state
and the current one is EXACTLY what you believe you changed -- no more. Re-indexing overwrites the
only record of what used to be there; a mistake made before that point becomes unprovable after it.
`--expect-gone` turns that belief into an assertion the tool can fail on.

WRITES NOTHING. No index, no marker, no repair. It reports and exits non-zero if anything is
unexpected.
"""
import argparse
import io
import os
import sys

from common import MIRROR_ROOT, OWN_FILES, SUMS_FILE, long_path, relative_to


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--expect-gone", action="append", default=[],
                    help="a path (relative to the archive) that SHOULD be absent now. Repeatable. "
                         "Anything else missing is reported as unexpected, and the run fails.")
    ap.add_argument("--show", type=int, default=40, help="how many of each kind to print")
    args = ap.parse_args()

    base = os.path.join(os.path.abspath(args.root), args.archive)
    idx = os.path.join(base, SUMS_FILE)
    if not os.path.isfile(idx):
        sys.exit("no index at %s" % idx)

    want = {}
    with io.open(idx, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            h, rel = line[:64], line[66:].rstrip("\r\n")
            if len(h) == 64 and rel:
                want[rel] = h
    # "the stored index lists", not "index written". This tool writes nothing, and a line of its
    # own output saying "written" is the one thing that could make a reader believe otherwise --
    # it read as an action taken here rather than as a description of the record on disk. Noticed
    # 2026-09-23 while measuring which tools are safe to run against the live collection.
    print("the stored index lists %d files" % len(want))

    have = set()
    pfx = long_path(base)
    for dirpath, _dirs, files in os.walk(pfx, onerror=lambda e: print("  WALK ERROR: %s" % e)):
        for n in files:
            rel = relative_to(pfx, os.path.join(dirpath, n))
            # `rel` carries the whole path, so a nested file cannot match a bare name in the
            # set: this already means AT THE TOP, which is the rule the index was built with.
            if rel is None or rel in OWN_FILES:
                continue
            have.add(rel)
    print("on disk now       %d files" % len(have))

    expect = set(p.replace("\\", "/") for p in args.expect_gone)
    missing = sorted(set(want) - have)
    extra = sorted(have - set(want))

    accounted = [p for p in missing if p in expect]
    unexpected = [p for p in missing if p not in expect]
    not_gone = sorted(expect - set(missing))

    print()
    print("  gone as expected      %d" % len(accounted))
    for p in accounted:
        print("     - %s" % p)
    print("  GONE UNEXPECTEDLY     %d" % len(unexpected))
    for p in unexpected[:args.show]:
        print("     ! %s" % p)
    if len(unexpected) > args.show:
        print("     ... and %d more" % (len(unexpected) - args.show))
    print("  new since the index   %d" % len(extra))
    for p in extra[:args.show]:
        print("     + %s" % p)
    if len(extra) > args.show:
        print("     ... and %d more" % (len(extra) - args.show))
    if not_gone:
        print("  EXPECTED GONE BUT STILL PRESENT   %d" % len(not_gone))
        for p in not_gone:
            print("     ? %s" % p)

    print()
    if not unexpected and not extra and not not_gone:
        print("  The ONLY difference is the %d file(s) named with --expect-gone." % len(accounted))
        print("  Safe to re-index: nothing else will be lost from the record.")
        return 0
    print("  DO NOT RE-INDEX YET. Re-indexing overwrites the only record of the previous state,")
    print("  and the differences above are not all accounted for.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
