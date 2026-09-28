#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Delete what an inventory says may be deleted, and nothing else.

THE PROBLEM THIS SOLVES. A working directory fills with tens of thousands of files over weeks
-- probes, half-downloads, unpacked copies, one-shot scripts, saved pages. Clearing it by
extension or by age deletes the wrong things, because the only thing a filename reliably tells
you is what somebody hoped the file would be. So the decision is made once, per file, in a CSV
that records WHY; this tool carries it out and refuses anything the CSV does not describe any
more.

THE GUARDS, and each one is here because the alternative failed.

  1. THE ROOT MUST CARRY A MARKER. `--root` alone is not enough: a path is a thing one mistypes,
     and the one mistake that matters here is emptying the wrong directory. The root must
     contain a file called `.sweepable`, put there by hand. There is no flag to skip this.

  2. EVERY PATH IN THE CSV IS RELATIVE. A row carrying a drive letter, a leading separator or a
     `..` component is refused unread. A CSV is a text file and is treated as untrusted input.

  3. CONTAINMENT IS DECIDED ON THE RESOLVED PATH. os.path.realpath() follows junctions and
     symlinks, so a junction inside the root that points at C:\Windows resolves to C:\Windows
     and fails the test. This is the check that actually stops that case.

  4. NO REPARSE POINT ANYWHERE ON THE WAY. Belt and braces for (3): the file and every directory
     between it and the root are checked for FILE_ATTRIBUTE_REPARSE_POINT.

  5. LONG PATHS ARE OPENED WITH THE \\?\ PREFIX. Without it Windows refuses paths over 259
     characters, os.lstat raises, and a tool that treats "cannot stat" as "unsafe" reports a
     long path as a junction. That happened to 634 files before this was fixed, and the decision
     was safe while the REASON was a lie.

  6. THE ROW MUST STILL DESCRIBE THE FILE. Size and mtime are compared against the inventory,
     and SHA-256 too unless --no-verify-hash. A file that changed since is refused: the evidence
     that justified deleting it described something else.

  7. A REMOVAL IS WRITTEN DOWN BEFORE IT HAPPENS, so an interrupted run still says what it did.

  8. A FAILURE IS AS LOUD AS A SUCCESS. An early version printed "removed 495" over 498
     candidates and said nothing about the three that failed; the difference was visible only to
     a reader who subtracted.

    python sweep.py --root DIR                       # dry run, everything marked delete
    python sweep.py --root DIR --group listings      # one group
    python sweep.py --root DIR --apply
    python sweep.py --root DIR --prune-empty --apply
"""

import argparse
import csv
import hashlib
import os
import stat
import sys
import time

MARKER = ".sweepable"
DEFAULT_CSV = "sweep-inventory.csv"
DEFAULT_LOG = "sweep.log"
LONG_PREFIX = "\\\\?\\"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def long_path(path):
    """-> the form Windows will open even past 259 characters."""
    absolute = os.path.abspath(path)
    if os.name != "nt" or absolute.startswith(LONG_PREFIX):
        return absolute
    return LONG_PREFIX + absolute


def is_reparse_point(path):
    """True for a junction, a symlink or any other reparse point, without following it.

    A PATH THAT IS NOT THERE IS NOT A LINK. Answering "unsafe" for a missing file is harmless
    as a decision and a lie as a reason, and the reason is what a person reads.
    """
    try:
        info = os.lstat(long_path(path))
    except FileNotFoundError:
        return False
    except OSError:
        return True
    attrs = getattr(info, "st_file_attributes", None)
    if attrs is not None and attrs & FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    return os.path.islink(path)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(long_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(rel, row, root_real, verify_hash):
    """-> (absolute path, None) when this row may be removed, or (None, reason) when not."""
    if not rel:
        return None, "empty path"
    if os.path.isabs(rel) or (len(rel) > 1 and rel[1] == ":"):
        return None, "path is absolute"
    parts = rel.replace("/", os.sep).split(os.sep)
    if any(part == ".." for part in parts):
        return None, "path contains '..'"

    joined = os.path.join(root_real, *parts)
    try:
        if os.path.commonpath([root_real, os.path.realpath(joined)]) != root_real:
            return None, "resolves outside the root"
    except ValueError:
        return None, "different drive"

    probe = joined
    while True:
        probe = os.path.dirname(probe)
        if os.path.normcase(probe) == os.path.normcase(root_real) or not probe:
            break
        if is_reparse_point(probe):
            return None, "a parent directory is a junction or symlink"

    try:
        info = os.lstat(long_path(joined))
    except FileNotFoundError:
        return None, "already gone"
    except OSError as exc:
        return None, "cannot stat: %s" % exc.__class__.__name__
    if is_reparse_point(joined):
        return None, "is a junction or symlink, not a plain file"
    if not stat.S_ISREG(info.st_mode):
        return None, "not a regular file"

    try:
        want_size = int(row["size"])
    except (KeyError, TypeError, ValueError):
        return None, "row has no usable size"
    if info.st_size != want_size:
        return None, "size changed since the inventory: %d -> %d" % (want_size, info.st_size)
    try:
        want_mtime = float(row["mtime"])
    except (KeyError, TypeError, ValueError):
        return None, "row has no usable mtime"
    if abs(info.st_mtime - want_mtime) > 2:
        return None, "mtime changed since the inventory"
    if verify_hash and row.get("sha256"):
        if sha256_of(joined) != row["sha256"]:
            return None, "content changed since the inventory"
    return joined, None


def resolve_root(root):
    """-> (resolved root, None) or (None, reason). Guard 1 lives here."""
    if not root:
        return None, "no --root given"
    real = os.path.realpath(root)
    if not os.path.isdir(real):
        return None, "%s is not a directory" % real
    marker = os.path.join(real, MARKER)
    if not os.path.isfile(marker):
        return None, ("%s carries no %s.\n"
                      "  A path is a thing one mistypes, and emptying the wrong directory is\n"
                      "  the one mistake that matters here. Put an empty file called %s in\n"
                      "  the directory you mean, by hand. There is no flag that skips this."
                      % (real, MARKER, MARKER))
    return real, None


def clear_readonly(path):
    """A file unpacked from an old archive keeps that archive's read-only bit.

    That is an artefact of the extraction, not a protection anyone set here. Clear it and
    remove -- but the caller says so in the log, because a tool that quietly defeats a write
    protection is not one to trust with a delete.
    """
    os.chmod(long_path(path), stat.S_IWRITE)


def prune_empty(root_real, apply_it):
    """Remove directories left empty, children before parents."""
    gone = []
    for _round in range(12):
        found = False
        for dirpath, dirnames, filenames in os.walk(root_real, topdown=False):
            if os.path.normcase(dirpath) == os.path.normcase(root_real):
                continue
            if dirnames or filenames or is_reparse_point(dirpath):
                continue
            try:
                if os.path.commonpath([root_real, os.path.realpath(dirpath)]) != root_real:
                    continue
            except ValueError:
                continue
            gone.append(os.path.relpath(dirpath, root_real))
            found = True
            if apply_it:
                try:
                    os.rmdir(long_path(dirpath))
                except OSError:
                    pass
        if not found or not apply_it:
            break
    print("%s -- %d empty directories" % ("APPLY" if apply_it else "DRY RUN", len(gone)))
    for name in gone[:20]:
        print("    %s" % name)
    if len(gone) > 20:
        print("    ... and %d more" % (len(gone) - 20))
    if not apply_it:
        print("\n  nothing was removed. Add --apply to do it.")
    return 0


def run(args, root_real):
    csv_path = args.csv or os.path.join(root_real, DEFAULT_CSV)
    if not os.path.isfile(csv_path):
        print("REFUSED: %s not found -- run inventory.py first" % csv_path)
        return 2
    with open(csv_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print("REFUSED: %s is empty" % csv_path)
        return 2

    todo = [r for r in rows if r.get("decision") == "delete"
            and (not args.group or r.get("group") in args.group)]
    if not todo:
        print("nothing marked 'delete'%s"
              % (" in %s" % ",".join(args.group) if args.group else ""))
        return 0

    passed, refused = [], []
    for row in todo:
        path, why = check(row["path"], row, root_real, not args.no_verify_hash)
        (passed if path else refused).append((row, path or row["path"], why))

    total = sum(int(r["size"]) for r, _p, _w in passed)
    print("%s -- %d rows marked delete in %s"
          % ("APPLY" if args.apply else "DRY RUN", len(todo),
             ",".join(args.group) if args.group else "all groups"))
    print("  passed every guard : %5d files, %8.1f MB" % (len(passed), total / 1e6))
    print("  REFUSED            : %5d files" % len(refused))
    if refused:
        print()
        by_reason = {}
        for _row, path, why in refused:
            by_reason.setdefault(why.split(":")[0], []).append(path)
        for why, paths in sorted(by_reason.items()):
            print("    %-46s %4d   e.g. %s" % (why, len(paths), paths[0][:48]))

    if not args.apply:
        print("\n  nothing was removed. Add --apply to do it.")
        if passed and args.show:
            print("\n  the %d largest that would go:" % min(args.show, len(passed)))
            for row, _p, _w in sorted(passed, key=lambda x: -int(x[0]["size"]))[:args.show]:
                print("    %10d  %-46s  %s"
                      % (int(row["size"]), row["path"][:46], row.get("reason", "")[:40]))
        return 0

    log_path = args.log or os.path.join(root_real, DEFAULT_LOG)
    removed = freed = 0
    failed = []
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        log.write("# sweep %s  root=%s  groups=%s  candidates=%d\n"
                  % (time.strftime("%Y-%m-%d %H:%M:%S"), root_real,
                     ",".join(args.group) if args.group else "all", len(passed)))
        for row, path, _why in passed:
            log.write("%s\t%s\t%s\n" % (row["size"], row["path"], row.get("reason", "")))
            log.flush()
            try:
                os.remove(long_path(path))
            except PermissionError:
                try:
                    clear_readonly(path)
                    os.remove(long_path(path))
                    log.write("# read-only attribute cleared before removal: %s\n" % row["path"])
                except OSError as exc:
                    failed.append((row["path"], exc))
                    log.write("# FAILED %s: %s\n" % (row["path"], exc))
                    continue
            except OSError as exc:
                failed.append((row["path"], exc))
                log.write("# FAILED %s: %s\n" % (row["path"], exc))
                continue
            removed += 1
            freed += int(row["size"])

    print("\n  removed %d files, %.1f MB freed" % (removed, freed / 1e6))
    if failed:
        print("  COULD NOT REMOVE %d:" % len(failed))
        for path, exc in failed[:10]:
            print("    %-52s %s" % (path[:52], exc.__class__.__name__))
        if len(failed) > 10:
            print("    ... and %d more, all in the log" % (len(failed) - 10))
    if removed != len(passed):
        print("  NOTE: %d of %d candidates did not result in a removal."
              % (len(passed) - removed, len(passed)))
    print("  logged to %s" % log_path)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Delete what an inventory says may be deleted, and nothing else.")
    parser.add_argument("--root", metavar="DIR",
                        help="the directory to sweep; it must contain a file called "
                             + MARKER)
    parser.add_argument("--csv", metavar="FILE",
                        help="the inventory (default: %s inside the root)" % DEFAULT_CSV)
    parser.add_argument("--log", metavar="FILE",
                        help="where removals are recorded (default: %s inside the root)"
                             % DEFAULT_LOG)
    parser.add_argument("--group", action="append", metavar="NAME",
                        help="only rows whose group column is this. Repeatable")
    parser.add_argument("--apply", action="store_true",
                        help="actually remove. Without this, nothing is touched")
    parser.add_argument("--prune-empty", action="store_true",
                        help="remove directories left empty by a sweep")
    parser.add_argument("--no-verify-hash", action="store_true",
                        help="skip the SHA-256 re-check; size and mtime are still checked")
    parser.add_argument("--show", type=int, default=10, metavar="N",
                        help="how many of the largest candidates a dry run lists")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    if not args.root:
        parser.print_help()
        return 0
    root_real, problem = resolve_root(args.root)
    if problem:
        print("REFUSED: %s" % problem)
        return 2
    if args.prune_empty:
        return prune_empty(root_real, args.apply)
    return run(args, root_real)


if __name__ == "__main__":
    sys.exit(main())
