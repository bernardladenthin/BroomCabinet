# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""How far through a pack is Rar.exe, and how much longer.

    python pack-progress.py --unit oldskool
    python pack-progress.py --unit bitsavers --work X:/tar
    python pack-progress.py --unit misc --log somewhere/else.log

RAR PRINTS A PERCENTAGE PER FILE AND NO TOTAL, so a run's own output cannot answer the one
question anybody watching it has. `bitsavers` is thirteen hours; until this existed every answer
was a guess from the bytes on disk, which is the COMPRESSED size and says nothing about the input
left.

WHAT IT COUNTS IS FILES, AND THAT IS NOT WHAT THE FIRST TWO VERSIONS DID. They reported a share
of BYTES, by looking up each named file's size in the index -- and both were wrong, each for its
own reason, and each found only by using the tool:

  1. RAR TRUNCATES THE NAME to its output column, so a name lookup cannot find a long path in the
     packing list at all. It matched whatever it collided with and reported 87.7 %, then 49.0 %
     minutes later. Replaced by counting the lines, which needs no name.

  2. RAR DOES NOT FOLLOW THE LIST ORDER, AND rar.txt SAYS SO: "Normalerweise werden Dateien in
     soliden Archiven nach ihrer Erweiterung sortiert" -- files in a solid archive are sorted BY
     EXTENSION, which is what makes -s worth having, because like compresses with like. It can be
     turned off with -ds or redirected with a rarfiles.lst. Measured on ibm-aix-opensource:

         list                           log
         oss4aix.org\SRPMS\gc\MD5SUMS    oss4aix.org\compatible\aix-51.txt
         oss4aix.org\SRPMS\sha\MD5SUMS   oss4aix.org\latest\aix-51.txt

     all .txt first, .rpm much later. So the Nth `Archiviere` line is NOT the Nth entry of the
     list, and summing the first N list entries adds up the wrong files: the tool claimed 0.3 %
     of bytes while 25 GB of output had already been written, which is impossible and is what
     gave it away. I first blamed -oi1 for the reordering; the owner pointed at the extension
     sort and rar.txt confirms him.

     THE SORT COULD IN PRINCIPLE BE REPLICATED and the byte figure recovered -- but "by
     extension" is all the documentation gives, the tie-breaking is unstated, and a rarfiles.lst
     may override it. A byte share rebuilt on a guessed sort would be wrong in a way nobody could
     see, which is worse than a count that is right about what it measures.

SO THE SHARE IS BY FILE COUNT, which is valid whatever the order, because every file is named
exactly once. ITS WEAKNESS IS STATED RATHER THAN HIDDEN: with sizes as skewed as this collection's
it is a poor predictor of time. ibm-aix-opensource stood at 58.6 % of files after 68 minutes with
the large RPMs still ahead; oldskool stood at 99.6 % of files with 13 % of its bytes left. The
figure says how much of the WORK LIST is done, not how much of the data.

The bytes written to the output directory are reported beside it, because they are the one
physical fact available -- but without knowing the final ratio they cannot be extrapolated
either, and the tool does not pretend otherwise.

Nothing reads the collection or the archive: the list, the index and the log are all small, which
is why this can be asked while a thirteen-hour run is going.
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

    A `Teste` LINE MEANS PACKING IS OVER, because `rar t` follows `rar a` in the same run, and
    extrapolating a finished phase would report time left for work already done. An `Archiviere`
    line after one clears the flag again: a multi-unit run packs the second while the first has
    been tested, so the flag has to reflect the LAST phase and not any.

    THE POSITION IS THE COUNT. RAR names each file exactly once, one line each,
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


def progress(order, named):
    r"""-> (position, total files), clamped to the list.

    NO BYTES. See the module docstring: RAR reorders, so the first `named` entries of the list are
    not the files it has done, and summing their sizes adds up the wrong ones.

    Measured: ibm-aix-opensource's log held 184 472 names for 184 465 files, and oldskool's 77 632
    for 77 631 -- the index CSV goes to RAR as an extra argument beside the @list, so one or two
    more names than the list holds is normal and must clamp rather than run off the end.
    """
    if named <= 0:
        return None
    return min(named, len(order)), len(order)


def written_bytes(folder):
    """-> bytes of .rar and .rev in the output directory, or None if it is not there yet."""
    if not os.path.isdir(folder):
        return None
    total = 0
    for name in os.listdir(folder):
        if name.endswith(".rar") or name.endswith(".rev"):
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass
    return total


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
    got = progress(order, named)
    if got is None:
        report_to("  %s: cannot place file %d in a list of %d" % (unit, named, len(order)))
        return 0
    position, total = got

    # THE LIST IS WRITTEN IMMEDIATELY BEFORE Rar.exe STARTS, so its mtime is the start time. The
    # alternative -- the archive's first volume -- appears only once 3.5 GB have been compressed,
    # which on bitsavers is half an hour of having nothing to say.
    started = os.path.getmtime(list_path)
    elapsed = (now or time.time()) - started
    share = position / float(total) if total else 0.0

    report_to("  %s" % unit)
    report_to("     file %d of %d  (%.1f %% of the work list)" % (position, total, 100.0 * share))
    out = written_bytes(os.path.dirname(archive_guess(unit, work)))
    if out:
        report_to("     %s written so far" % human(out))
    report_to("     running %s" % as_hours(elapsed))
    if position >= total:
        report_to("     every file has been named; RAR is finishing the last volume")
        return 0
    if share > 0.02 and elapsed > 0:
        report_to("     about %s left IF THE REST AVERAGES THE SAME, which with these file sizes "
                  "it will not" % as_hours(elapsed / share - elapsed))
    else:
        report_to("     too early to estimate")
    return 0


def archive_guess(unit, work):
    """-> where the volumes most likely are, for the written-bytes line only.

    A GUESS AND LABELLED AS ONE: the output root is not in the work directory and this tool is not
    told it. `X:\tarTarget\\<unit>\\` is where every unit so far has been written, and a wrong
    guess costs one missing line rather than a wrong number.
    """
    return os.path.join("X:" + os.sep, "tarTarget", unit, unit + ".rar")


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
