# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Ask a second, independent reader about the ISO images `--declared` called short.

WHY A SECOND READER RATHER THAN A BETTER FIRST ONE. `audit.py --declared` compares an image
against the volume size its own primary volume descriptor states. That is a real signal -- the
little-endian and big-endian copies of the field agree -- and it cannot tell *truncated* from
*the descriptor describes more than this image holds*. Writing a fourth hand-rolled parser to
settle it was the obvious move and the wrong one: three ZIP versions had already been wrong that
same evening, and each was caught by a second opinion rather than by re-reading the code. The ZIP
half was settled by Python's own `zipfile` agreeing 300 times out of 300. This is that move again.

THE SIGNAL, and it needs no judgement about formats. `7z l` walks the directory tree and prints
the total size of the files it finds. If that total EXCEEDS the image, the image cannot contain
what its own filesystem says it contains -- truncation, and nothing else. If it fits and 7-Zip
reports no error, the filesystem is simply smaller than the volume the descriptor describes,
which is not damage. If 7-Zip errors out, neither reader can say anything, and "I cannot tell"
is an answer rather than a finding.

It reads metadata, not content, so it is cheap even on gigabyte images.

WHY IT SHELLS OUT AND THE LIBRARY DOES NOT. `common.py` is standard library only, and that stays
true: nothing here is imported by the library or by `audit.py`. This is an INVESTIGATION tool --
it borrows somebody else's mature reader for one question and writes the answer down, in the same
way a person would run `7z l` by hand and read the output. A dependency inside the checks would be
a different thing entirely.

    python iso-second-opinion.py --report measurements/declared-2026-09-25.txt
    python iso-second-opinion.py --report ... --json out.json
"""
import argparse
import io
import os
import re
import subprocess
import sys

from common import MIRROR_ROOT, find_tool, human, long_path, say

# Where 7-Zip usually is on Windows. Not configuration and not a dependency: a missing one is
# reported and the run refuses, because a second opinion nobody gave is not a second opinion.
SEVEN_ZIP_CANDIDATES = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    "7z",
    "7zz",
)

# The `--declared` report's finding lines, ISO only.
ROW = re.compile(r"^\s+[\d.]+ [kMG]?B missing\s+[\d.]+ [kMG]?B of [\d.]+ [kMG]?B\s+ISO 9660\s+(.*)$")

TRUNCATED = "TRUNCATED -- its own filesystem needs more than the file holds"
FITS = "the filesystem reads cleanly and fits; the descriptor overstates"
NO_VERDICT = "7-Zip cannot read the filesystem either -- no verdict possible"
UNREADABLE = "the file could not be opened"
ORDER = (TRUNCATED, NO_VERDICT, UNREADABLE, FITS)


def find_seven_zip(candidates=SEVEN_ZIP_CANDIDATES):
    """-> the first candidate that answers, or None.

    The candidate list above is this tool's. The loop was identical to b2-pack.py's find_rar()
    byte for byte, including the "ran and misbehaved still means it is there" branch, and is
    common.find_tool() since 2026-09-27.
    """
    return find_tool(candidates)


def findings(report):
    """-> [relative path] of every ISO the report called short."""
    out = []
    with io.open(report, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = ROW.match(line.rstrip("\n"))
            if m:
                out.append(m.group(1))
    return out


def listing(seven_zip, path, run=subprocess.run):
    """-> (total bytes 7-Zip finds, file count, 'Errors'/'Warnings'/''). Never raises.

    THE SUMMARY LINE IS PARSED, NOT THE ENTRIES. 7-Zip prints one line per file and then a total;
    reading the total is one regular expression against output that a person can check by eye,
    where summing thousands of entry lines would be a second parser to get wrong.
    """
    try:
        result = run([seven_zip, "l", path], capture_output=True, text=True,
                     errors="replace", timeout=600)
    except Exception as exc:                                    # noqa: BLE001
        return None, None, type(exc).__name__
    out = result.stdout or ""
    note = ""
    if re.search(r"^Errors: \d+", out, re.M):
        note = "Errors"
    elif re.search(r"^Warnings: \d+", out, re.M):
        note = "Warnings"
    m = re.search(r"-{10,}[^\n]*\n[^\n]*?(\d+)\s+(\d+)?\s+(\d+) files", out)
    if not m:
        return None, None, note or "no summary"
    return int(m.group(1)), int(m.group(3)), note


def judge(size, listed, note):
    """The three-way answer. `listed is None` means 7-Zip would not read it."""
    if listed is None:
        return NO_VERDICT
    if listed > size:
        return TRUNCATED
    if note == "Errors":
        # It read a fragment and complained. A total that fits is not evidence when the reader
        # says it could not finish -- that is the same "I cannot tell" as a refusal.
        return NO_VERDICT
    return FITS


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", required=True,
                    help="an `audit.py --declared` report to take the ISO findings from")
    ap.add_argument("--root", default=MIRROR_ROOT, help="the collection (default %(default)s)")
    ap.add_argument("--json", help="also write one record per image here")
    ap.add_argument("--quiet", action="store_true", help="no progress while it runs")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.report):
        say("no report at %s" % args.report)
        return 2
    rows = findings(args.report)
    if not rows:
        say("the report names no ISO findings")
        return 2

    seven_zip = find_seven_zip()
    if seven_zip is None:
        say("REFUSING TO RUN: 7-Zip is not on this machine.")
        say("A second opinion nobody gave is not a second opinion, and guessing from the volume")
        say("descriptor alone is what this tool exists to avoid. Looked for:")
        for candidate in SEVEN_ZIP_CANDIDATES:
            say("    %s" % candidate)
        return 2

    say("=== %d ISO finding(s), asked of %s ===" % (len(rows), seven_zip))
    records, counts = [], {}
    for i, rel in enumerate(rows, 1):
        path = os.path.join(args.root, rel.replace("/", os.sep))
        try:
            size = os.path.getsize(long_path(path))
        except OSError:
            counts.setdefault(UNREADABLE, []).append((rel, None, None))
            continue
        listed, files, note = listing(seven_zip, path)
        verdict = judge(size, listed, note)
        counts.setdefault(verdict, []).append((rel, size, listed))
        records.append({"path": rel, "size": size, "listed": listed,
                        "files": files, "note": note, "verdict": verdict})
        if not args.quiet and i % 20 == 0:
            say("  %d/%d" % (i, len(rows)))

    for verdict in ORDER:
        items = counts.get(verdict)
        if not items:
            continue
        say("\n  %s -- %d" % (verdict, len(items)))
        if verdict is TRUNCATED:
            for rel, size, listed in sorted(items, key=lambda r: -(r[2] - r[1])):
                say("    missing %10s   %s" % (human(listed - size), rel[-64:]))

    if args.json:
        import json
        with io.open(args.json, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=1)
        say("\n  written to %s" % args.json)

    total = sum(len(v) for v in counts.values())
    say("\n  %d image(s) asked about, %d accounted for" % (len(rows), total))
    if total != len(rows):
        say("  THE SUMMARY DOES NOT ADD UP -- a verdict is missing from ORDER")
        return 2
    return 1 if counts.get(TRUNCATED) else 0


if __name__ == "__main__":
    sys.exit(main())
