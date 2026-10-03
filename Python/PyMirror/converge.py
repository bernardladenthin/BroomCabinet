# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Harvest, fetch, repeat -- until a round names nothing new.

    python converge.py --archive dreamlandbbs-os2 --delay 0.5        # show the plan, fetch nothing
    python converge.py --archive dreamlandbbs-os2 --delay 0.5 --go

WHY ONE PASS CANNOT FINISH THESE ARCHIVES. In an MBSE file area, or any hand-written tree whose
listings are static HTML, each area's `index.html` IS A FILE. It cannot be read before it is
fetched, so a URL list built from the pages currently on disk describes one layer and not the tree.
dreamlandbbs-os2, 2026-10-02 to 2026-10-03:

    61 pages on disk  ->  5 330 files named  ->  13.59 GB
    73                ->  1 521              ->   4.25 GB
    77                ->    395
                      ->    113
                      ->      5
                      ->      0   and one more empty round to confirm it

AFTER THE FIRST ROUND THAT ARCHIVE LOOKED FINISHED. Taking it then -- into a solid archive that
by design is never modified again -- would have frozen it 2 034 files short, permanently. Three
markers in this collection claimed COMPLETE on 2026-10-03 and all three were short; this is the
tool that would have caught them.

TWO BRAKES AND NOT ONE, because a loop that fetches from a stranger's server must be able to stop
itself. The register already holds the counter-example: retro-digitalvintage's `Jumper Reference/`
branch stopped yielding new files at page 950 while 99 000 pages were still queued -- per-board
pages cross-linking to the same files for ever. A round cap alone would have spent 27 hours there
for nothing, so a round that reduces the outstanding count by less than `--min-gain` stops the run
and says which brake fired. The throwaway loop this replaces had only the cap, and five was luck.

IT ONLY EVER ADDS. Each round runs pages-to-urllist.py and then manifest-fetch.py, both unchanged
and both of which only write files that are missing. Nothing here deletes, renames or rewrites a
marker; the marker belongs to `mirror.py` and is earned by a crawl that finds nothing left to do.

A RECORD IS WRITTEN INTO THE ARCHIVE, because a count nobody can retake is a count nobody can
argue with. See CONVERGED.md beside the mirror.
"""
import argparse
import io
import os
import re
import subprocess
import sys
import time

from common import GONE_FILE, MIRROR_ROOT, load_mirror, say

HERE = os.path.dirname(os.path.abspath(__file__))
HARVEST = os.path.join(HERE, "pages-to-urllist.py")
FETCH = os.path.join(HERE, "manifest-fetch.py")
RECORD = "CONVERGED.md"

# pages-to-urllist.py's headline line. Parsed rather than recomputed: a second implementation of
# "what is outstanding" is a second opinion, and the whole point of that tool's recent repair is
# that its number can now be believed. It read 1 562 for ardent-tool where 3 were outstanding
# until the query rule and the .mirror-gone check landed on 2026-10-03.
OUTSTANDING = re.compile(r"^\s*(\d+) FILES NAMED AND NOT ON DISK", re.M)
FETCHED = re.compile(r"DONE fetched (\d+), gone from the source (\d+), failed (\d+)")


def outstanding(root, archive, out_path):
    """-> (count, text) from one harvest. The count is the tool's own figure."""
    res = subprocess.run([sys.executable, HARVEST, "--root", root, "--archive", archive,
                          "--out", out_path],
                         capture_output=True, text=True, cwd=HERE)
    text = res.stdout + res.stderr
    found = OUTSTANDING.search(text)
    if not found:
        # NOT TREATED AS ZERO. A harvest whose figure cannot be read has said nothing, and reading
        # silence as "nothing outstanding" is the exact failure this collection keeps meeting -- a
        # clean zero that looks like a finding.
        return None, text
    return int(found.group(1)), text


def fetch(archive, base, url_list, delay, give_up, report=say):
    """-> (fetched, gone, failed) for one round, or None if the figures cannot be read."""
    res = subprocess.run([sys.executable, FETCH, "--archive", archive, "--base", base,
                          "--url-list", url_list, "--delay", str(delay),
                          "--give-up", str(give_up)],
                         capture_output=True, text=True, cwd=HERE)
    text = res.stdout + res.stderr
    for line in text.splitlines():
        if "DONE fetched" in line or "FAILED" in line or "ABANDONED" in line:
            report("      %s" % line.strip())
    found = FETCHED.search(text)
    if not found:
        report("      the fetch printed no DONE line -- stopping rather than guessing")
        return None
    return tuple(int(g) for g in found.groups())


def converge(root, archive, base, delay, max_rounds, min_gain, give_up, go, report=say):
    """Run rounds until a harvest finds nothing. -> the list of (round, outstanding, fetched)."""
    history = []
    previous = None
    for n in range(1, max_rounds + 1):
        out_path = os.path.join(root, "logs", "converge-%s-r%d.txt" % (archive, n))
        if not os.path.isdir(os.path.dirname(out_path)):
            os.makedirs(os.path.dirname(out_path))
        count, text = outstanding(root, archive, out_path)
        if count is None:
            report("  round %d: the harvest figure could not be read -- stopping" % n)
            report(text[-400:])
            return history
        report("  round %d: %d outstanding" % (n, count))
        if count == 0:
            # THE FIXED POINT, and it is only believable because the harvest that reports it reads
            # pages fetched in the PREVIOUS round. A first round of 0 means the archive was already
            # there, which is also an answer.
            report("  FIXED POINT -- every name a held page gives is held or recorded in %s"
                   % GONE_FILE)
            history.append((n, 0, 0))
            return history
        if previous is not None and previous - count < min_gain:
            # THE SECOND BRAKE. retro-digitalvintage's Jumper Reference branch is the recorded
            # case: pages kept naming files the fetch could not reduce, and a cap alone would have
            # spent a day of somebody else's bandwidth on it.
            report("  STOPPING: round %d reduced the figure by %d, below --min-gain %d. "
                   "Look at the list before spending more requests."
                   % (n, previous - count, min_gain))
            return history
        if not go:
            report("  --go not given: %d urls written to %s, nothing fetched" % (count, out_path))
            history.append((n, count, 0))
            return history
        got = fetch(archive, base, out_path, delay, give_up, report=report)
        if got is None:
            return history
        history.append((n, count, got[0]))
        previous = count
    report("  STOPPING: --max-rounds %d reached while the figure was still falling" % max_rounds)
    return history


def write_record(root, archive, history, base):
    """Leave the rounds inside the archive. Appends; an earlier run's rounds are not overwritten."""
    path = os.path.join(root, archive, RECORD)
    first = not os.path.exists(path)
    with io.open(path, "a", encoding="utf-8", newline="\n") as fh:
        if first:
            fh.write("# How this archive was brought to a fixed point\n\n"
                     "Each of this tree's listing pages IS A FILE, so a URL list built from the\n"
                     "pages on disk describes one layer rather than the tree. `converge.py`\n"
                     "harvests, fetches and repeats until a round names nothing new.\n\n"
                     "A COUNT NOBODY CAN RETAKE IS A COUNT NOBODY CAN ARGUE WITH, which is why\n"
                     "the rounds are here and not only in a log.\n")
        fh.write("\n## %s  (%s)\n\n" % (time.strftime("%Y-%m-%d %H:%M"), base))
        fh.write("| round | outstanding | fetched |\n|---|---|---|\n")
        for n, count, got in history:
            fh.write("| %d | %d | %d |\n" % (n, count, got))
        if history and history[-1][1] == 0:
            fh.write("\nThe last round found NOTHING outstanding: every name a held page gives is\n"
                     "either held or recorded in `%s`.\n" % GONE_FILE)
        else:
            fh.write("\nThis run did NOT reach a fixed point -- see the tool's output for which\n"
                     "brake fired. The archive is not closed.\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--base", help="default: the archive's base from mirror.py's register")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between requests (default 2). The register's MIN_INTERVAL for "
                         "the archive is the figure to respect; this tool does not read it for "
                         "you")
    ap.add_argument("--max-rounds", type=int, default=8,
                    help="first brake (default 8). dreamlandbbs-os2 needed 6")
    ap.add_argument("--min-gain", type=int, default=1,
                    help="second brake (default 1): stop when a round reduces the outstanding "
                         "figure by less than this. Guards against a tree whose pages cross-link "
                         "to the same files for ever -- see the Jumper Reference note in the "
                         "module docstring")
    ap.add_argument("--give-up", type=int, default=4, help="passed to manifest-fetch.py")
    ap.add_argument("--go", action="store_true",
                    help="actually fetch. Without it one harvest runs and nothing is requested")
    args = ap.parse_args()

    base = args.base
    if not base:
        mirror = load_mirror(HERE)
        if mirror is None:
            say("mirror.py could not be read -- pass --base")
            return 2
        found = dict(mirror.ARCHIVES).get(args.archive)
        if not found:
            say("%s is not in the register -- pass --base" % args.archive)
            return 2
        base = found

    say("  %s  <-  %s" % (args.archive, base))
    say("  %s" % ("FETCHING" if args.go else "LOOKING ONLY -- nothing is requested"))
    history = converge(args.root, args.archive, base, args.delay, args.max_rounds,
                       args.min_gain, args.give_up, args.go)
    if args.go and history:
        say("\n  record: %s" % write_record(args.root, args.archive, history, base))
        say("  NEXT: mirror.py --archive %s --index, then a crawl to earn the marker"
            % args.archive)
    return 0 if (history and history[-1][1] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
