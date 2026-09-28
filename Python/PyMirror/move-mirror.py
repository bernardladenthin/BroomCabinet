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
import io
import os
import shutil
import stat
import sys
import time

from common import long_path, relative_to

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


def survey(root, base):
    """Walk `root`. -> ([relative dirs], files, bytes, {relative dir: colliding names in it}).

    `base` IS WHAT THE RELATIVE PATHS ARE MEASURED AGAINST, AND IT IS NOT ALWAYS `root`. With
    --only the walk is restricted to one archive, but its directories still have to be created
    under DST at their FULL relative position, so the source survey measures against SRC while
    walking SRC/only. The destination survey afterwards measures against what it walks, because
    those paths are only counted and compared.

    It has no default for that reason. Two functions did this walk until 2026-09-23, differing in
    exactly this, and a default would let the next caller inherit whichever the author happened
    to write first -- in a tool where a wrong relative path means a file moved to the wrong place.

    relative_to says the root itself is "" where this file's own copy said "."; measured over
    60 136 paths in two real trees, that and the separator are the only two ways the answers ever
    differed.

    A COLLISION IS TWO NAMES THAT DIFFER ONLY IN CASE, counted per directory, files and
    subdirectories together -- because either kind arriving in a target without the flag
    overwrites the other. That count is what the flag check and the final comparison both key on.
    """
    dirs, files, total = [], 0, 0
    coll = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        fn[:] = [f for f in fn if f not in SKIP_FILES]
        rel = relative_to(base, dp)
        if rel:
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
    ap.add_argument("--pause-secs", type=float, default=0.0,
                    help="idle this long after every --pause-every-gb written (default 0, off). "
                         "ONLY FOR A DRIVE THAT NEEDS IDLE TIME TO CATCH UP -- an SMR disk "
                         "rewriting shingled tracks out of its CMR cache is the case it was "
                         "written for. IT DOES NOT HELP THE COMMONER PROBLEM, which is NTFS "
                         "alternating between the MFT near the start of the volume and the data "
                         "area: that is seek thrashing, the head is busy rather than behind, and "
                         "idling it just stops work. Diagnose before reaching for this -- if "
                         "throughput scales with average file size, it is seeks, not cache. "
                         "Measured on the tree this was written for: 44 MB/s average across "
                         "archives averaging 3-47 MB per file, against about 1.5 MB/s on the one "
                         "archive averaging 1.1 MB per file. That is the seek pattern, and no "
                         "pause length improves it.")
    ap.add_argument("--pause-every-gb", type=float, default=1.0,
                    help="how much to write between pauses (default 1.0). BYTES, not files: an "
                         "SMR cache fills by volume, so one 2 GB ISO exhausts it while ten "
                         "thousand small files may not.")
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

    # ONE MOVER AT A TIME. On 2026-09-06 two instances ran against the same tree for fourteen
    # minutes, because stopping the shell that launched the first one did not stop the PYTHON
    # PROCESS UNDER IT, and a second was started on top. They interleaved:
    #
    #   * both wrote the SAME `<dest>.moving` temp file, so a file that arrived at the
    #     destination was a mixture of two copies. bitsavers' 83X9181.ZIP came out 178 bytes
    #     short with a hash matching nothing.
    #   * one process held a source file open while the other tried to delete it, so the
    #     source survived a "move" and the tree ended up with files on both volumes.
    #
    # Neither failure announced itself: counts still rose, no exception was raised, and the
    # damage was only visible by hashing the destination against the index. A lock is cheap;
    # discovering this afterwards was not.
    lock = os.path.join(DST, ".move-mirror.lock")
    if args.go:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("pid %d, started %s, SRC %s, --only %s\n"
                          % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S"), SRC,
                             args.only or "(all)")).encode("utf-8"))
            os.close(fd)
        except FileExistsError:
            sys.exit("ANOTHER MOVE IS RUNNING (or died leaving %s behind):\n  %s\n"
                     "Two movers on one tree corrupt files silently -- see the note in main().\n"
                     "If no python is running, delete that file by hand and start again."
                     % (lock, io.open(lock, encoding="utf-8", errors="replace").read().strip()))
        import atexit
        atexit.register(lambda: os.path.exists(lock) and os.remove(lock))
    print("Surveying %s ..." % (os.path.join(SRC, args.only) if args.only else SRC), flush=True)
    # measured against SRC even when --only narrows the walk: these become directories under
    # DST at their full relative position.
    dirs, files, total, coll = survey(
        os.path.join(SRC, args.only) if args.only else SRC, SRC)
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
    moved = skipped = copied = 0
    clashes = []
    pause_budget = int(args.pause_every_gb * 1e9)
    for dp, dn, fn in os.walk(os.path.join(SRC, args.only) if args.only else SRC):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        fn[:] = [f for f in fn if f not in SKIP_FILES]
        rel = relative_to(SRC, dp)
        for f in fn:
            s = os.path.join(dp, f)
            # `rel` is "" for the root. os.path.join(DST, "", f) would give the right path
            # anyway, but saying it makes the root case visible where it is decided.
            d = os.path.join(DST, f) if not rel else os.path.join(DST, rel, f)
            if os.path.exists(long_path(d)):
                # Never overwrite. On a resume this is the file already moved; anything else is
                # a collision the flag was supposed to prevent, and must be looked at by a human.
                skipped += 1
                continue
            try:
                os.replace(long_path(s), long_path(d))
                moved += 1
            except OSError as exc:
                # ACROSS VOLUMES, os.replace() CANNOT WORK. Windows raises WinError 17, "the
                # system cannot move the file to a different disk drive". This tool was written
                # for a same-volume move, where a rename is metadata only and 2.8 TB moves in
                # minutes; X: -> Q: is not that, and without this branch the FIRST file ends
                # the run.
                #
                # Copy to a .part beside the destination, fsync, compare sizes, then put it in
                # place and drop the source. The .part is the point: a kill midway leaves a
                # fragment under a name nothing reads, never a truncated file under the real one.
                # Same discipline mirror.py uses for downloads.
                #
                # SIZE IS NOT PROOF OF CONTENT -- it catches a truncated copy and nothing else.
                # The real check is verify-content.py against the archive's own .sha256sum AT THE
                # DESTINATION. Move one archive, verify it there, and only then let the next one
                # start; that is what --only is for.
                if getattr(exc, "winerror", None) != 17:
                    clashes.append((s, str(exc)))
                    continue
                part = d + ".moving"
                try:
                    with io.open(long_path(s), "rb") as fs, io.open(long_path(part), "wb") as fd:
                        while True:
                            chunk = fs.read(8 << 20)
                            if not chunk:
                                break
                            fd.write(chunk)
                        fd.flush()
                        os.fsync(fd.fileno())
                    got, want = os.path.getsize(long_path(part)), os.path.getsize(long_path(s))
                    if got != want:
                        raise OSError("short copy: %d of %d bytes" % (got, want))
                    os.replace(long_path(part), long_path(d))
                    shutil.copystat(long_path(s), long_path(d))
                except OSError as exc2:
                    # The COPY failed. Nothing has been removed; the source is untouched.
                    clashes.append((s, "cross-volume COPY failed (source kept): %s" % exc2))
                    try:
                        os.remove(long_path(part))
                    except OSError:
                        pass
                    continue
                # The copy is in place. Removing the source is a SEPARATE step with a separate
                # failure mode, and conflating the two produced nine log lines reading "copy
                # failed" for files that had copied perfectly -- the copy was fine, the DELETE
                # was refused.
                #
                # READ-ONLY SOURCES ARE NORMAL HERE. git marks everything under
                # .git/objects/pack/ read-only, and Windows refuses os.remove() on a read-only
                # file with WinError 5 rather than the permission error the name suggests. The
                # same attribute arrives on rsync'd trees. Clear it and retry once; a file left
                # behind is a copy that did not become a move, which quietly doubles the tree.
                try:
                    os.remove(long_path(s))
                except OSError:
                    try:
                        os.chmod(long_path(s), stat.S_IWRITE)
                        os.remove(long_path(s))
                    except OSError as exc3:
                        clashes.append((s, "copied, but SOURCE NOT REMOVED (still on both "
                                           "volumes): %s" % exc3))
                copied += 1
                moved += 1
                # Count what actually crossed the bus. A same-volume rename writes nothing and
                # must not consume the budget, which is why this sits in the copy branch only.
                pause_budget -= want
            # NOT A RATE AND NOT A BACKOFF, which is why this stays a plain sleep. The three
            # meanings a pause carries in this collection were written down on 2026-09-25 and two
            # of them moved into the library: `common.Pacer` for "do not contact this host more
            # often than", `common.Backoff` for "wait longer after each failure". Neither fits
            # here. There is no host and no failure -- this is a COOLDOWN for a piece of hardware,
            # budgeted in gigabytes written rather than in requests made, because a USB drive's
            # write cache needs somewhere to go. Wrapping one `sleep` in a helper would say less
            # than this comment does.
            if args.pause_secs and pause_budget <= 0:
                print("  pausing %.0f s to let the drive drain (%.1f GB since the last pause)"
                      % (args.pause_secs, args.pause_every_gb), flush=True)
                time.sleep(args.pause_secs)
                pause_budget = int(args.pause_every_gb * 1e9)
            if (moved + skipped) % 2000 == 0:
                print("  %d/%d  (%.0f s, %d copied across volumes)"
                      % (moved + skipped, files, time.time() - t0, copied), flush=True)
    print("  moved %d (%d copied across volumes), skipped %d, errors %d, in %.0f s"
          % (moved, copied, skipped, len(clashes), time.time() - t0))
    for s, e in clashes[:10]:
        print("     ERROR %s: %s" % (s, e))

    # --- 4. cross-check -------------------------------------------------------------------------
    # measured against what it walks: these paths are only counted and compared.
    dst_root = os.path.join(DST, args.only) if args.only else DST
    dirs2, fn2, tb2, coll2 = survey(dst_root, dst_root)
    print("\nDST: %d directories, %d files, %.2f GB, %d colliding names"
          % (len(dirs2), fn2, tb2 / 1e9, sum(coll2.values())))
    print("SRC before: %d / %d / %.2f GB / %d"
          % (len(dirs), files, total / 1e9, sum(coll.values())))
    ok = (fn2 == files and abs(tb2 - total) < 1024
          and sum(coll2.values()) == sum(coll.values()))
    print("COMPARISON: %s" % ("identical" if ok else "MISMATCH -- do not delete SRC!"))
    return 0 if ok and not clashes else 1


if __name__ == "__main__":
    sys.exit(main())
