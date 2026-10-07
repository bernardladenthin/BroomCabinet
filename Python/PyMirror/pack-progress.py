# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""How far through a pack is Rar.exe, and how much longer.

    python pack-progress.py --unit oldskool
    python pack-progress.py --unit bitsavers-paper --work X:/tar
    python pack-progress.py --unit misc --log somewhere/else.log

RAR PRINTS A PERCENTAGE PER FILE AND NO TOTAL, so a run's own output cannot answer the one
question anybody watching it has. Nine hours is the estimate for `bitsavers-paper`, and until
this existed every answer was a guess from the bytes on disk -- which is the COMPRESSED size and
says nothing about how much input is left.

THE THREE THINGS IT NEEDS ARE ALL TINY. The packing order is fixed: it is the `.list` file
b2-pack wrote before starting Rar.exe. The size of every entry is in `<unit>.index.csv` beside
it. And the NUMBER of `Archiviere` lines in the log says how far down that list RAR has got --
counted and not matched by name, because RAR truncates long names to its output column and a
name-matching lookup reported 87.7 % and then 49.0 % minutes later. Nothing reads the collection
or the archive, which is why this can be asked while a seven-hour run is going.

BYTES AND NOT FILE COUNT, because the two disagree wildly and most where it matters. Measured on
2026-10-07, with oldskool at file 77 286 of 77 631: by COUNT that is 99.6 % and by BYTES 86.7 %,
because the last few hundred files were the large ones. A count-based figure would have promised
two minutes where twenty-five were left, and it is worst exactly where the files are least
uniform -- oldskool averages 1.92 MB per file, misc 0.42, vendors 16.31.

WHEN THE LOG SAYS `Teste`, PACKING IS OVER. `rar t` follows `rar a` in the same run, so a log
whose last interesting line is a test line means the estimate no longer applies -- and saying
"done, testing" is more useful than extrapolating a finished phase.

IT READS AND NOTHING ELSE. No argument of this tool can write, and it names no path it was not
given or did not derive from --work.
"""
import argparse
import io
import os
import re
import sys
import time

from common import human, say

# `Archiviere` is the German build's word and `Adding` the English one; both are followed by the
# name and then at least two spaces before the percentage column.
ARCHIVING = re.compile(r"^(?:Archiviere|Adding)\s+(.+?)\s{2,}")
TESTING = re.compile(r"^(?:Teste|Testing)\s")
WORK = os.path.join("X:" + os.sep, "tar")


def packing_order(list_path):
    r"""-> the file names in the order RAR was given them.

    THE LIST IS THE ORDER AND NOT A GUESS AT IT. b2-pack sorts its rows with `sort_key` and writes
    them to this file; re-deriving that sort here would be a second implementation of the one
    thing the estimate depends on, and the two would agree until one of them changed.
    """
    out = []
    with io.open(list_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(line.replace("/", "\\"))
    return out


def sizes_from_index(index_path):
    """-> {archive\\path: size} out of the unit's own index CSV."""
    out = {}
    with io.open(index_path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle):
            if number == 0:
                continue                       # archive,path,size,sha256
            parts = line.rstrip("\n").split(",")
            if len(parts) < 4:
                continue
            try:
                out[(parts[0] + "\\" + parts[1]).replace("/", "\\")] = int(parts[2])
            except ValueError:
                continue
    return out


def files_named(log_path):
    r"""-> (how many files RAR has named, whether it has moved on to testing).

    COUNTED AND NOT MATCHED BY NAME, because RAR TRUNCATES THE NAME to its output column. Measured
    2026-10-07 on the oldskool log:

        'oldskool\\misc\\...\\VHS Tutorial Videos\\G'
        'oldskool\\drivers\\Panasonic\\...\\typing and printing on the Panas'

    Those are prefixes, cut mid-word. A name-matching lookup cannot find them in the packing list
    at all -- neither exactly nor by suffix, since a prefix is not a suffix -- and the first
    version of this tool therefore matched whatever it happened to collide with and reported
    87.7 %, then 49.0 % minutes later. A progress figure that walks backwards is the symptom that
    found this.

    THE POSITION IS THE COUNT. RAR names the files in the order the list gave them, one line each,
    so the Nth `Archiviere` line is the Nth entry. That needs no name at all and cannot be fooled
    by a width.
    """
    count = 0
    testing = False
    with io.open(log_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if ARCHIVING.match(line):
                count += 1
                testing = False
            elif TESTING.match(line):
                testing = True
    return count, testing


def progress(order, sizes, named):
    r"""-> (position, bytes done, bytes total) for the `named`-th file in `order`.

    THE SUM STOPS AT THAT FILE INCLUSIVE, which overstates by at most one file -- RAR has read
    some part of it. Against 148 GB at an average of 1.92 MB that is noise, and the honest
    alternative would be to parse RAR's per-file percentage, which is a column position rather
    than a number in a format.

    BYTES AND NOT FILE COUNT, because the two disagree most where it matters. Measured 2026-10-07
    with oldskool at file 77 286 of 77 631: 99.6 % by count and 86.7 % by bytes, because the last
    few hundred files were the large ones.
    """
    total = sum(sizes.values())
    if named <= 0:
        return None
    position = min(named, len(order)) - 1
    done = sum(sizes.get(name, 0) for name in order[:position + 1])
    return position, done, total


def report(unit, work, log_path, report_to=say, now=None):
    """-> 0 when something could be said, 2 when a file it needs is missing."""
    list_path = os.path.join(work, unit + ".list")
    index_path = os.path.join(work, unit + ".index.csv")
    for path in (list_path, index_path, log_path):
        if not os.path.isfile(path):
            report_to("  no %s" % path)
            return 2

    named, testing = files_named(log_path)
    if testing:
        report_to("  %s: packing is DONE; `rar t` is running" % unit)
        return 0
    if named == 0:
        report_to("  %s: no `Archiviere` line yet -- still building the list" % unit)
        return 0

    order = packing_order(list_path)
    sizes = sizes_from_index(index_path)
    got = progress(order, sizes, named)
    if got is None:
        report_to("  %s: cannot place file %d in a list of %d" % (unit, named, len(order)))
        return 0
    position, done, total = got
    if named >= len(order):
        report_to("  %s: every file has been named; RAR is finishing the last volume" % unit)
        return 0

    # THE LIST IS WRITTEN IMMEDIATELY BEFORE Rar.exe STARTS, so its mtime is the start time. The
    # alternative -- the archive's first volume -- appears only once 3.5 GB have been compressed,
    # which on bitsavers-paper is half an hour of having nothing to say.
    started = os.path.getmtime(list_path)
    elapsed = (now or time.time()) - started
    share = (done / float(total)) if total else 0.0

    report_to("  %s" % unit)
    report_to("     file %d of %d" % (position + 1, len(order)))
    report_to("     %s of %s read  (%.1f %%)" % (human(done), human(total), 100.0 * share))
    report_to("     running %s" % as_hours(elapsed))
    if share > 0.01 and elapsed > 0:
        report_to("     about %s left for packing, then the checks"
                  % as_hours(elapsed / share - elapsed))
    else:
        report_to("     too early to estimate")
    return 0


def as_hours(seconds):
    """-> `2.4 h` or `25 min`, whichever reads better at that size."""
    if seconds < 90 * 60:
        return "%.0f min" % (seconds / 60.0)
    return "%.1f h" % (seconds / 3600.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--unit", required=True, help="the unit being packed")
    ap.add_argument("--work", default=WORK, help="where the .list and .index.csv are (default %s)"
                                                % WORK)
    ap.add_argument("--log", help="the pack log (default <work>/<unit>-pack.log)")
    args = ap.parse_args(argv)
    log_path = args.log or os.path.join(args.work, args.unit + "-pack.log")
    return report(args.unit, args.work, log_path)


if __name__ == "__main__":
    sys.exit(main())
