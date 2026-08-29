#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Move a tree to another NTFS location so that EVERY directory carries the case-sensitive flag.

WHY NOT JUST MOVE THE DIRECTORY
    Because a move preserves the directory object, and with it the absence of the flag. NTFS
    grants case sensitivity only to directories created AFTER the flag is set on their parent --
    never retroactively. A plain `move` of the tree this was written for would have arrived with
    34 280 directories of which exactly two were case-sensitive, and the other 34 278 silently
    unable to hold two names differing only in case.

    So: create every directory fresh under the new root, let it inherit, then move the files
    into it. A same-volume file move is a rename -- metadata only, no copying, no second copy of
    2.8 TB needed.

WHAT IS AT STAKE
    In the tree this was written for, 4030 names differed from another name only in case. Moving
    one of those into a directory without the flag does not fail. It OVERWRITES. The result would
    have been 4030 files short and every count would still have looked right, because the count
    was taken afterwards.

    That is why this script verifies the flag on every directory that holds a collision BEFORE it
    moves anything into it, and refuses the whole run if even one is missing it.

USAGE
    python move-mirror.py SRC DST                report only -- nothing created, nothing moved
    python move-mirror.py SRC DST --go           create directories, verify flags, move files
    python move-mirror.py SRC DST --only tuhs    one subdirectory first

    DST must exist and must already carry the flag; set it by hand, deliberately:

        fsutil file setCaseSensitiveInfo DST enable

    Same volume is strongly preferred -- a same-volume file move is a rename, metadata only, so
    2.8 TB moves in minutes and never exists twice. Resumable: a file already at the target is
    left alone, one still at the source is moved. Interrupting it is safe.
"""

import argparse
import collections
import os
import sys
import time

# Set by main() from the two positional arguments. Deliberately without defaults: this tool moves
# whole trees, and a default would be a guess about where terabytes go.
SRC = None
DST = None

SKIP_DIRS = {"__pycache__"}

# Created and removed inside case_sensitive(); telling the two spellings apart IS the measurement.
PROBE = ".case-probe"

# The probe is removed in a finally, but a process killed between the create and the remove would
# leave one behind -- and this tool proves a move by comparing counts on both sides, so one stray
# file is the difference between "identical" and "do not delete SRC".
SKIP_FILES = {PROBE, PROBE.upper()}


def long_path(path):
    """Windows refuses paths over 260 characters without the \\\\?\\ prefix.

    NOT via os.path.abspath(). abspath() normalises, and normalising STRIPS A TRAILING DOT --
    which is precisely what the \\\\?\\ prefix exists to prevent. 21 files in this tree end in a
    dot: `bndstd.`, `HZLDPY.`, `GERMAN.`, `TALK.`, off PDP-8 paper tapes and RSTS/E disk images.
    For every one of them abspath turned a name that exists into a name that does not, and the
    move failed with "file not found" on files that were plainly there. The helper defeated the
    very thing it was written for.  [2026-08-29]

    So: make it absolute by hand if it is not already, switch the separators, prefix. No
    normalisation anywhere. Safe here because SRC, DST and everything os.walk() yields are
    already clean absolute paths without `..` components.
    """
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    path = path.replace("/", "\\")
    if path.startswith("\\\\?\\"):
        return path
    return "\\\\?\\" + path


def case_sensitive(path):
    """-> True if this directory can hold two names differing only in case.

    Measured, not asked. This used to run `fsutil file queryCaseSensitiveInfo` and look for
    "disabled" or "deaktiviert" in its output -- two of the forty-odd languages Windows ships in,
    decoded as cp850, which is a third assumption. On any other locale neither word matches, the
    negative test yields True, and the whole safety check of this script passes for directories
    that would silently overwrite one collision each.

    Making a file and looking for the other spelling answers the actual question in one syscall,
    in every language, on every filesystem. Here it matters more than anywhere else: this is the
    check that stands between 4030 colliding names and losing one copy of each.  [2026-08-29]
    """
    lower = os.path.join(path, PROBE)
    upper = os.path.join(path, PROBE.upper())
    try:
        with open(long_path(lower), "wb"):
            pass
    except OSError:
        return False
    try:
        return not os.path.exists(long_path(upper))
    finally:
        for probe in (lower, upper):
            try:
                os.remove(long_path(probe))
            except OSError:
                pass


def survey(only=None):
    """-> (dirs, files, bytes, {relative dir -> number of colliding names in it}).

    `only` restricts everything to one archive directory. Moving a single small mirror first is
    not caution for its own sake: it proves the whole mechanism -- inheritance, the flag check,
    the rename, the comparison -- against something that could be re-fetched in half an hour if
    it went wrong, before the same code is pointed at 2.8 TB that could not.
    """
    dirs, files, total = [], 0, 0
    coll = {}
    root = os.path.join(SRC, only) if only else SRC
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        fn[:] = [f for f in fn if f not in SKIP_FILES]
        rel = os.path.relpath(dp, SRC)
        if rel != ".":
            dirs.append(rel)
        seen = collections.defaultdict(list)
        for f in fn:
            files += 1
            try:
                total += os.path.getsize(long_path(os.path.join(dp, f)))
            except OSError:
                pass
            seen[f.lower()].append(f)
        for d in dn:
            seen[d.lower()].append(d)
        n = sum(len(v) - 1 for v in seen.values() if len(v) > 1)
        if n:
            coll[rel] = n
    return dirs, files, total, coll


def main():
    global SRC, DST
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", metavar="SRC", help="the tree to move")
    ap.add_argument("dst", metavar="DST",
                    help="the destination, which must exist and already carry the flag")
    ap.add_argument("--go", action="store_true",
                    help="actually create directories and move files")
    ap.add_argument("--only", metavar="ARCHIVE",
                    help="restrict to one subdirectory, e.g. --only tuhs. Moving a small one "
                         "first proves the whole mechanism against something that could be "
                         "re-fetched, before the same code is pointed at what could not")
    args = ap.parse_args()
    SRC = os.path.abspath(args.src)
    DST = os.path.abspath(args.dst)
    if os.path.normcase(SRC) == os.path.normcase(DST):
        sys.exit("SRC and DST are the same directory.")

    if not os.path.isdir(SRC):
        sys.exit("SRC does not exist: %s" % SRC)
    if not os.path.isdir(DST):
        sys.exit("DST does not exist: %s -- create it first and set the flag" % DST)
    if not case_sensitive(DST):
        sys.exit("DST %s does NOT carry the flag. Without it the whole point is lost." % DST)

    if args.only and not os.path.isdir(os.path.join(SRC, args.only)):
        sys.exit("No such subdirectory: %s" % args.only)
    print("Surveying %s ..." % (os.path.join(SRC, args.only) if args.only else SRC), flush=True)
    dirs, files, total, coll = survey(args.only)
    print("  %d directories, %d files, %.2f GB" % (len(dirs), files, total / 1e9))
    print("  %d directories hold case collisions, %d names in all"
          % (len(coll), sum(coll.values())))
    tops = collections.Counter(d.split(os.sep)[0] for d in coll)
    for k, v in tops.most_common(5):
        print("     %-24s %d directories" % (k, v))

    if not args.go:
        print("\nDry run -- nothing created, nothing moved. Run it with --go.")
        return 0

    # --- 1. create the directories, so they inherit the flag ---------------------------------
    print("\nCreating %d directories ..." % len(dirs), flush=True)
    t0 = time.time()
    for i, rel in enumerate(dirs, 1):
        os.makedirs(long_path(os.path.join(DST, rel)), exist_ok=True)
        if i % 5000 == 0:
            print("  %d/%d" % (i, len(dirs)), flush=True)
    print("  done in %.0f s" % (time.time() - t0))

    # --- 2. check the flag BEFORE anything moves into them ------------------------------------------
    #
    # Only the directories that actually hold a collision are checked: 34 280 fsutil calls would
    # take an hour and tell us nothing the inheritance rule does not already guarantee. These are
    # the ones where a missing flag destroys data rather than merely being untidy.
    print("\nChecking the flag on %d directories that hold collisions ..." % len(coll), flush=True)
    bad = [rel for rel in coll if not case_sensitive(os.path.join(DST, rel))]
    if bad:
        print("  ABORT: %d target directories do not carry the flag:" % len(bad))
        for rel in bad[:10]:
            print("     %s" % rel)
        print("  Nothing was moved.")
        return 1
    print("  all %d are fine" % len(coll))

    # --- 3. move the files ---------------------------------------------------------------
    print("\nMoving %d files ..." % files, flush=True)
    t0 = time.time()
    moved = skipped = 0
    clashes = []
    for dp, dn, fn in os.walk(os.path.join(SRC, args.only) if args.only else SRC):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        fn[:] = [f for f in fn if f not in SKIP_FILES]
        rel = os.path.relpath(dp, SRC)
        for f in fn:
            s = os.path.join(dp, f)
            d = os.path.join(DST, f) if rel == "." else os.path.join(DST, rel, f)
            if os.path.exists(long_path(d)):
                # Never overwrite. On a resume this is the file already moved; anything else is
                # a collision the flag was supposed to prevent, and must be looked at by a human.
                skipped += 1
                continue
            try:
                os.replace(long_path(s), long_path(d))
                moved += 1
            except OSError as exc:
                clashes.append((s, str(exc)))
            if (moved + skipped) % 50000 == 0:
                print("  %d/%d  (%.0f s)" % (moved + skipped, files, time.time() - t0), flush=True)
    print("  moved %d, skipped %d, errors %d, in %.0f s"
          % (moved, skipped, len(clashes), time.time() - t0))
    for s, e in clashes[:10]:
        print("     ERROR %s: %s" % (s, e))

    # --- 4. cross-check -------------------------------------------------------------------------
    dn2, fn2, tb2, coll2 = survey_at(os.path.join(DST, args.only) if args.only else DST)
    print("\nDST: %d directories, %d files, %.2f GB, %d colliding names"
          % (dn2, fn2, tb2 / 1e9, sum(coll2.values())))
    print("SRC before: %d / %d / %.2f GB / %d"
          % (len(dirs), files, total / 1e9, sum(coll.values())))
    ok = (fn2 == files and abs(tb2 - total) < 1024
          and sum(coll2.values()) == sum(coll.values()))
    print("COMPARISON: %s" % ("identical" if ok else "MISMATCH -- do not delete SRC!"))
    return 0 if ok and not clashes else 1


def survey_at(root):
    dirs = files = total = 0
    coll = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        fn[:] = [f for f in fn if f not in SKIP_FILES]
        if os.path.relpath(dp, root) != ".":
            dirs += 1
        seen = collections.defaultdict(list)
        for f in fn:
            files += 1
            try:
                total += os.path.getsize(long_path(os.path.join(dp, f)))
            except OSError:
                pass
            seen[f.lower()].append(f)
        for d in dn:
            seen[d.lower()].append(d)
        n = sum(len(v) - 1 for v in seen.values() if len(v) > 1)
        if n:
            coll[os.path.relpath(dp, root)] = n
    return dirs, files, total, coll


if __name__ == "__main__":
    sys.exit(main())
