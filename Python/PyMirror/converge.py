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
import urllib.error
import urllib.parse

from common import (GONE_FILE, GONE_STATUS, MIRROR_ROOT, Pacer, REFUSED_FILE, host_of,
                    http_open, load_mirror, record_gone, record_refused, say)

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


def probe(urls, delay, pacer=None, report=say):
    """Ask HEAD about each candidate. -> {"get": [...], "gone": [(url, code)], "refused": [...]}

    A HEAD BEFORE A GET, BECAUSE MOST OF THESE ARE NOT FILES. Measured over three batches on
    2026-10-03/04, 1 202 of 1 607 outstanding paths answered 404 -- pages naming files their own
    server no longer has. Fetching them costs a full request each and an error page to discard;
    asking costs a header.

        infania-os-history   54 outstanding, 54 x 404
        somuchstuff-pdp8    480 outstanding, 480 x 404
        dialectronics       158 outstanding, 158 x 404
        techsysadm          402 outstanding, 402 x 200   -- and 199 of them were already HELD,
                                                            which is what content_root fixed

    THE 404s ARE RECORDED FROM THIS MEASUREMENT and not re-asked with a GET, which is the whole
    saving. A HEAD is the source answering, and .mirror-gone holds what the source answered; going
    back for a second opinion would spend 1 202 requests on a question already settled.

    A THIRD OUTCOME EXISTS AND IS NOT A FAILURE. 403 and 500 are permanent in practice and
    record_gone refuses them -- it takes 404 and 410 only, deliberately, because `gone` and
    `refused` are different facts. They are returned separately so the caller can stop instead of
    asking again next round: five such paths are known, and before this they cost one wasted round
    each before the gain brake noticed.
    """
    pacer = pacer or Pacer(delay)
    out = {"get": [], "gone": [], "refused": []}
    for i, url in enumerate(urls, 1):
        pacer.wait(host_of(url))
        try:
            with http_open(url, timeout=45, method="HEAD") as resp:
                code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:                                 # noqa: BLE001
            # NOT COUNTED AS GONE. A timeout or a DNS failure is our side of the wire or a host
            # having a bad minute, and writing it into .mirror-gone would record our own trouble
            # as the source's answer.
            out["refused"].append((url, type(e).__name__))
            continue
        if code == 200:
            out["get"].append(url)
        elif int(code) in GONE_STATUS:
            out["gone"].append((url, code))
        else:
            out["refused"].append((url, code))
        if i % 100 == 0:
            report("      ... %d of %d asked" % (i, len(urls)))
    return out


def outstanding(root, archive, out_path):
    """-> (count, urls, text) from one harvest. The count is the tool's own figure.

    THE URLS COME BACK WITH THE COUNT rather than being re-read from the file by the caller. One
    read, one source of truth, and the probe step cannot end up asking about a different list than
    the one the figure describes.
    """
    res = subprocess.run([sys.executable, HARVEST, "--root", root, "--archive", archive,
                          "--out", out_path],
                         capture_output=True, text=True, cwd=HERE)
    text = res.stdout + res.stderr
    found = OUTSTANDING.search(text)
    if not found:
        # NOT TREATED AS ZERO. A harvest whose figure cannot be read has said nothing, and reading
        # silence as "nothing outstanding" is the exact failure this collection keeps meeting -- a
        # clean zero that looks like a finding.
        return None, [], text
    urls = []
    if os.path.exists(out_path):
        with io.open(out_path, encoding="utf-8") as fh:
            urls = [ln.strip() for ln in fh if ln.strip()]
    return int(found.group(1)), urls, text


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


def converge(root, archive, base, delay, max_rounds, min_gain, give_up, go, report=say,
             use_probe=True):
    """Run rounds until a harvest finds nothing. -> the list of (round, outstanding, fetched)."""
    archive_dir = os.path.join(root, archive)
    history = []
    previous = None
    for n in range(1, max_rounds + 1):
        out_path = os.path.join(root, "logs", "converge-%s-r%d.txt" % (archive, n))
        if not os.path.isdir(os.path.dirname(out_path)):
            os.makedirs(os.path.dirname(out_path))
        count, urls, text = outstanding(root, archive, out_path)
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
        # ASKED BEFORE FETCHED. The candidates are split by what the source says about them, and
        # only the 200s are handed to the fetcher; see probe() for the measurement that makes this
        # the default rather than an option.
        # A FIGURE WITHOUT A LIST IS A BROKEN HARVEST, NOT AN EMPTY ONE, and treating the two
        # alike cost gsi-collection a false closure on 2026-10-04. pages-to-urllist.py announced
        # "3789 FILES NAMED AND NOT ON DISK" and then died printing a sample path its console
        # could not encode -- before writing the file. This loop read the figure, found no urls,
        # fell through to "nothing here is fetchable" and stopped. Had the figure been 0 it would
        # have claimed a FIXED POINT.
        #
        # THE SAME SHAPE AS EVERY OTHER CLEAN ZERO IN THIS COLLECTION: an answer that looks like a
        # finding because the thing that should have spoken said nothing at all.
        if count > 0 and not urls:
            report("  round %d: the harvest reported %d outstanding and wrote NO url list -- "
                   "stopping. Run pages-to-urllist.py by hand and read its output; this is a "
                   "broken harvest, not an empty one." % (n, count))
            return history
        if not use_probe:
            # STRAIGHT TO THE FETCHER, which records a 404 itself. The probe's whole value is not
            # repeating a request; where most candidates are real it only adds one.
            report("    --no-probe: handing all %d to the fetcher" % len(urls))
            asked = {"get": list(urls), "gone": [], "refused": []}
        else:
            asked = probe(urls, delay, report=report)
        report("    asked %d: %d fetchable, %d gone, %d refused"
               % (len(urls), len(asked["get"]), len(asked["gone"]), len(asked["refused"])))
        # RECORDED FROM THE ANSWER WE ALREADY HAVE. Going back with a GET to learn the same 404
        # again would spend one request per dead link, which is the cost this step exists to avoid.
        noted = 0
        for url, code in asked["gone"]:
            rel = url[len(base):] if url.startswith(base) else None
            if rel and record_gone(archive_dir, urllib.parse.unquote(rel), code):
                noted += 1
        if noted:
            report("    %d recorded in %s" % (noted, GONE_FILE))
        # A REFUSAL IS AN ANSWER TOO, and it now has a file. Only a real status goes in --
        # record_refused declines a timeout or a DNS failure, because those are our side of the
        # wire and develooper-hpux answered 503 on one probe and 404 on the next.
        noted_refused = 0
        for url, code in asked["refused"]:
            rel = url[len(base):] if url.startswith(base) else None
            if rel and isinstance(code, int):
                if record_refused(archive_dir, urllib.parse.unquote(rel), code):
                    noted_refused += 1
        if noted_refused:
            report("    %d recorded in %s" % (noted_refused, REFUSED_FILE))
        for url, code in asked["refused"][:6]:
            report("    REFUSED %s -- %s" % (code, url[-66:]))
        if not asked["get"]:
            # NO WASTED ROUND. Before this, a list of nothing but refusals cost a full fetch
            # attempt and then one more harvest before the gain brake noticed. There are five such
            # paths in the collection and record_gone holds none of them.
            report("  STOPPING: nothing here is fetchable -- %d gone (recorded), %d refused and "
                   "not recordable" % (len(asked["gone"]), len(asked["refused"])))
            history.append((n, count, 0))
            return history
        with io.open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(asked["get"]) + "\n")
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
    ap.add_argument("--no-probe", action="store_true",
                    help="skip the HEAD step and hand every candidate to the fetcher. THE PROBE "
                         "IS A BET: it wins when most candidates are dead (2 099 of 2 504 across "
                         "five archives) and LOSES when most are real -- ps-2.kev009.com answered "
                         "200 for 4 906 of 6 098, so asking first turned 6 098 requests into "
                         "11 004. manifest-fetch.py records a 404 itself, so nothing is lost "
                         "except the saving")
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
                       args.min_gain, args.give_up, args.go, use_probe=not args.no_probe)
    if args.go and history:
        say("\n  record: %s" % write_record(args.root, args.archive, history, base))
        say("  NEXT: mirror.py --archive %s --index, then a crawl to earn the marker"
            % args.archive)
    return 0 if (history and history[-1][1] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
