# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Run `--holes` over the collection ONE ARCHIVE AT A TIME, so that stopping costs one archive.

WHY THIS EXISTS RATHER THAN `audit.py --holes --root Q:\mirror`. That command is correct and it
reads 2.39 TB. Measured 2026-09-25 on `develooper-hpux`: 11.55 GB in 145 s, **76 MB/s**, so the
whole of it is **8.3 hours**. A single process holds everything until the last file has been read
and prints at the end, so an interruption at hour seven leaves nothing at all -- and this
collection has already killed two long runs for looking hung, which is C4's whole history.

ONE ARCHIVE PER LOG FILE, WRITTEN ATOMICALLY. `common.atomic_write` exists for exactly the failure
this has to avoid: its own docstring says a half-written file that looks complete is not retried
but inherited. A log appears whole or not at all, so a log that exists means that archive is done,
and a restart re-does only the archive that was interrupted. There is no state to keep and nothing
to corrupt -- the logs ARE the state.

IT WRITES NOTHING ANYWHERE NEAR THE COLLECTION. `audit.py` has no write path at all; this adds
log files, and they go wherever `--logs` says, which defaults to a directory beside this script
and never inside `--root`. The collection is opened read-only, one file at a time, and that is the
whole of the interaction.

LARGEST ARCHIVE FIRST, and that is a choice about how it fails. A run cut short leaves the cheap
tail undone, which finishes in daylight; the other order leaves the 400 GB archives undone, which
costs another night. Within equal sizes the order is by name, so a restart is predictable.

AN ARCHIVE THAT RAISES DOES NOT STOP THE RUN. Eight hours unattended over 1.76 M files on an NTFS
volume with `\\?\` paths is not where a single OSError should end everything. The failure is
written into that archive's log with the traceback, the log is NOT marked complete, and the next
archive starts.

    python holes-run.py                      # the default root and log directory
    python holes-run.py --dry-run            # what it would do, and what is already done
"""
import argparse
import io
import os
import sys
import time
import traceback

import audit
from common import MIRROR_ROOT, atomic_write, human, long_path, read_marker, say, COMPLETE_MARKER

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = MIRROR_ROOT
DEFAULT_LOGS = os.path.join(HERE, "measurements", "holes-run")

# The last line of a finished log. The file is written atomically, so its mere existence already
# means "done" -- this is belt and braces, and it is what a human greps for.
DONE = "=== archive finished ==="


def archives(root):
    """-> [(bytes, name)], largest first, from each archive's own completion marker.

    THE MARKER IS READ, NOT THE TREE. Walking 1.76 M files to decide what order to walk them in
    would cost a measurable part of the run. A directory with no marker still gets processed --
    it sorts last with size 0, because "no marker" means nobody finished crawling it, not that it
    is empty.
    """
    out = []
    for name in sorted(os.listdir(long_path(root))):
        path = os.path.join(root, name)
        if not os.path.isdir(long_path(path)):
            continue
        rec = read_marker(os.path.join(path, COMPLETE_MARKER))
        try:
            size = int(rec["bytes"])
        except (KeyError, TypeError, ValueError):
            size = 0
        out.append((size, name))
    out.sort(key=lambda row: (-row[0], row[1]))
    return out


def log_path(logs, name):
    return os.path.join(logs, name + ".log")


def already_done(logs, name):
    return os.path.exists(long_path(log_path(logs, name)))


def run_one(root, name, min_size):
    """-> (text of the log, findings, failed). Never raises."""
    buf = io.StringIO()
    keep = sys.stdout
    started = time.time()
    findings = 0
    failed = False
    sys.stdout = buf
    try:
        findings = audit.check_holes(os.path.join(root, name), min_size,
                                     report=lambda m: None)
    except Exception:  # noqa: BLE001 -- see the module docstring: one archive must not end the run
        failed = True
        buf.write("\n=== THIS ARCHIVE FAILED ===\n")
        buf.write(traceback.format_exc())
    finally:
        sys.stdout = keep
    text = buf.getvalue()
    text += "\n%s  %s  %.1f s\n" % (DONE if not failed else "=== archive FAILED ===",
                                    name, time.time() - started)
    return text, findings, failed


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=DEFAULT_ROOT, help="the collection (default %(default)s)")
    ap.add_argument("--logs", default=DEFAULT_LOGS,
                    help="one log per archive lands here (default beside this script)")
    ap.add_argument("--min-size", type=int, default=16,
                    help="only read files of at least this many MB (default %(default)s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what is done and what is left, and read nothing")
    args = ap.parse_args(argv)

    rows = archives(args.root)
    if not rows:
        say("no archives under %s" % args.root)
        return 2

    todo = [(size, name) for size, name in rows if not already_done(args.logs, name)]
    done_bytes = sum(size for size, name in rows if already_done(args.logs, name))
    left_bytes = sum(size for size, _n in todo)
    say("=== holes: %d archive(s), %d already done, %d to go ==="
        % (len(rows), len(rows) - len(todo), len(todo)))
    say("    done %s, left %s (marker figures, whole archives -- not the >= %d MB subset)"
        % (human(done_bytes), human(left_bytes), args.min_size))

    if args.dry_run:
        for size, name in todo:
            say("    todo  %-34s %10s" % (name, human(size)))
        return 0

    os.makedirs(long_path(args.logs), exist_ok=True)
    findings = failures = 0
    for i, (size, name) in enumerate(todo, 1):
        say("[%d/%d] %-34s %10s" % (i, len(todo), name, human(size)))
        sys.stdout.flush()
        text, found, failed = run_one(args.root, name, args.min_size * 1048576)
        findings += found
        failures += 1 if failed else 0
        # WRITTEN LAST AND IN ONE PIECE. Until this returns, the archive counts as not done.
        atomic_write(log_path(args.logs, name), text.encode("utf-8", "replace"))
        say("        %d finding(s)%s" % (found, "  FAILED" if failed else ""))
        sys.stdout.flush()

    say("\n=== %d archive(s) read, %d finding(s), %d failed ==="
        % (len(todo), findings, failures))
    return 1 if findings or failures else 0


if __name__ == "__main__":
    sys.exit(main())
