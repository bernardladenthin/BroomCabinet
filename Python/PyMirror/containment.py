# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Which mirror contains which other mirror, and what would a deduplicating packer save?

Run it whenever an archive is added, and before packaging the collection.

    python containment.py                 # full report
    python containment.py --root Q:\mirror

WHY THIS EXISTS. Two archives here hold the same documents under different names --
`rwth-aachen-ftp` and `ps-2.kev009.com` are both IBM's PC Company BBS, one via the PS/2 Super
Site -- so a filename comparison says "no overlap" and is wrong. Content is the only honest key,
and every archive already carries a verified .sha256sum, so the question is a set join over
~800k hashes: seconds, with no 3 TB re-read.

WHAT IT ANSWERS
  * Is any archive redundant? (2026-09-05: NO. Highest coverage 61.2%, no 100% row.)
  * Where is the redundancy a packer can collapse -- across archives, or inside one? That
    decides whether to pack per archive or as one solid blob. Measured: 47.59 GB of the
    337.62 GB spans archives, so packing per archive costs 1.4% and keeps each one
    independently restorable.

DIRECTION MATTERS, AND MOST MISREADINGS START HERE. `A -> B  61%` means 61% OF A exists
byte-identically in B. The reverse is different and usually much smaller: fsck-aix-apps against
fsck-vendors is 61.2% one way and 8.8% the other -- the same 182 files against a different
denominator. Only a 100% row means B could stand in for A. Never quote one direction alone.

FILE COUNTS MISLEAD, SO BYTES ARE CARRIED THROUGHOUT. `rwth-aachen-ftp -> ps-2.kev009.com` is
81.6% of the files but 59.5% of the bytes, because those files are BIOS diskettes;
`fsck-aix-apps -> fsck-vendors` is half the files and 61.2% of the bytes, because those are ISOs.

TWO TRAPS, BOTH LEARNED THE HARD WAY
  * e3b0c442... is the SHA-256 of zero bytes, and 20 archives here hold empty files. Counting
    them manufactures overlap between archives that share nothing. Excluded, and reported.
  * 21 files in this collection end in a dot and one directory ends in a space. Windows strips
    those when parsing a path, so plain getsize cannot see the file; mirror.py's long_path can.
    Anything still unreadable is COUNTED AND REPORTED -- a silent zero is how an earlier run
    called a tree clean while two files were missing from it.
"""
import argparse
import collections
import io
import os
import sys

from common import MIRROR_ROOT, EMPTY_SHA256, SUMS_FILE, long_path

RULE = "=" * 92


def load(root):
    """archive -> [(hash, size)], plus hash -> size, and the empty/unreadable tallies."""
    names = sorted(d for d in os.listdir(root)
                   if os.path.isfile(os.path.join(root, d, SUMS_FILE)))
    if not names:
        sys.exit("no .sha256sum under %s -- run mirror.py --index first" % root)
    size, per = {}, {}
    empty = collections.Counter()
    bad = collections.Counter()
    for n in names:
        base = os.path.join(root, n)
        lst = []
        with io.open(os.path.join(base, SUMS_FILE), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # "<64 hex><space><asterisk><path>" -- binary mode, as sha256sum writes it.
                h, rel = line[:64], line[66:].rstrip("\r\n")
                if len(h) != 64 or not rel:
                    continue
                if h == EMPTY_SHA256:
                    empty[n] += 1
                    continue
                try:
                    sz = os.path.getsize(long_path(os.path.join(base, rel.replace("/", os.sep))))
                except OSError:
                    bad[n] += 1
                    continue
                size[h] = sz
                lst.append((h, sz))
        per[n] = lst
        print("  %-22s %7d files %9.2f GB%s"
              % (n, len(lst), sum(s for _h, s in lst) / 1e9,
                 ("  %d UNREADABLE" % bad[n]) if bad[n] else ""), flush=True)
    return names, per, size, empty, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--min-gb", type=float, default=0.2,
                    help="hide pairs below this many GB unless they also exceed --min-pct")
    ap.add_argument("--min-pct", type=float, default=2.0)
    args = ap.parse_args()

    names, per, size, empty, bad = load(args.root)
    idx = {n: i for i, n in enumerate(names)}
    total = {n: sum(s for _h, s in per[n]) for n in names}

    # hash -> bitmask of the archives holding it; 36 archives fit in one int.
    mask = collections.defaultdict(int)
    for n in names:
        b = 1 << idx[n]
        for h, _s in per[n]:
            mask[h] |= b

    pair_n, pair_b = collections.Counter(), collections.Counter()
    for n in names:
        me = 1 << idx[n]
        for h, s in per[n]:
            m = mask[h] & ~me
            while m:
                low = m & -m
                pair_n[(n, names[low.bit_length() - 1])] += 1
                pair_b[(n, names[low.bit_length() - 1])] += s
                m ^= low

    print("\n" + RULE)
    print("A -> B : how much OF A exists byte-identically in B  (direction is significant)")
    print(RULE)
    rows = sorted(((pair_b[k] / max(1, total[k[0]]), pair_b[k], pair_n[k], k) for k in pair_b),
                  reverse=True)
    full = 0
    for frac, b, c, (a, bb) in rows:
        if b < args.min_gb * 1e9 and frac * 100 < args.min_pct:
            continue
        flag = "  <== FULLY CONTAINED" if frac > 0.999 else ""
        full += frac > 0.999
        print("  %-22s -> %-22s %6d f.  %8.2f GB of %8.2f GB  %5.1f%%%s"
              % (a, bb, c, b / 1e9, total[a] / 1e9, frac * 100, flag))
    print("  %d pairs overlap at all; %d fully contained in another" % (len(rows), full))

    print("\n" + RULE)
    print("PER ARCHIVE : how much of me exists ANYWHERE ELSE in the collection")
    print(RULE)
    lonely = 0
    stats = []
    for n in names:
        me = 1 << idx[n]
        dup = sum(s for h, s in per[n] if mask[h] & ~me)
        dupn = sum(1 for h, _s in per[n] if mask[h] & ~me)
        lonely += dup == 0
        stats.append((dup / max(1, total[n]), dup, dupn, len(per[n]), total[n], n))
    for frac, dup, dupn, cnt, tot, n in sorted(stats, reverse=True):
        if dup:
            print("  %-22s %6d/%6d f.  %8.2f GB of %8.2f GB  %5.1f%%"
                  % (n, dupn, cnt, dup / 1e9, tot / 1e9, frac * 100))
    print("  %d archives overlap nothing at all" % lonely)

    # Three DIFFERENT quantities. An earlier version summed two of them over the same dict and
    # printed identical figures for "on disk" and "distinct" -- they are not the same thing.
    on_disk = sum(total.values())
    uniq = sum(size.values())
    cross = sum(size[h] for h, m in mask.items() if m & (m - 1))
    once = sum(size[h] for h, m in mask.items() if m and not (m & (m - 1)))
    entries = sum(len(v) for v in per.values())
    print("\n" + RULE)
    print("  on disk (excl. empty files) : %8.2f GB in %d files" % (on_disk / 1e9, entries))
    print("  distinct content            : %8.2f GB in %d hashes" % (uniq / 1e9, len(size)))
    print("  dedup saving                : %8.2f GB (%.1f%%) in %d surplus files"
          % ((on_disk - uniq) / 1e9, 100.0 * (on_disk - uniq) / max(1, on_disk),
             entries - len(size)))
    print("    of which CROSS-ARCHIVE    : %8.2f GB -- the rest duplicates WITHIN one archive"
          % (cross / 1e9))
    print("  content in exactly 1 archive: %8.2f GB (%.1f%% of distinct)"
          % (once / 1e9, 100.0 * once / max(1, uniq)))
    print("\n  empty files skipped: %d across %d archives" % (sum(empty.values()), len(empty)))
    if bad:
        print("  UNREADABLE: %d files in %s -- investigate, do not ignore"
              % (sum(bad.values()), ", ".join("%s(%d)" % (k, v) for k, v in sorted(bad.items()))))


if __name__ == "__main__":
    main()
