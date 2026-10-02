# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fetch what an archive's OWN manifest names and the crawl could not reach.

WHY A CRAWLER IS NOT ENOUGH, and this is the case that shows it plainly. On
gatekeeper.dec.com, `.../SRC/research-reports/SRC-021-html/` does not serve a directory listing --
it serves the research paper. A crawler can therefore see only what that PAGE links: not
`evolve.css`, not `evolve.html`, not the backup files ending in `~`, not the contents of a
subdirectory confusingly named `icons.gif/`. Those files exist, answer 200, and are invisible to
any amount of crawling, because there is no listing anywhere that names them.

The archive's own `Index-byname` names all of them. So the manifest, not the crawl, is the
authority for this archive -- the same relationship as bitsavers' .tar.txt and bullfreeware's
.sfv, and the reason this collection keeps those files rather than treating them as clutter.

    python manifest-fetch.py --archive zx-gatekeeper-dec \
        --manifest Index-byname --prefix /pub/ --base http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/

Skips anything already on disk, so it is safe to re-run and cheap when there is nothing to do.
"""
import argparse
import io
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (COMPLETE_MARKER, GONE_FILE, MIRROR_ROOT, Pacer, Patience, exists,
                    host_of, http_get,
                    load_mirror, read_gone, record_gone,
                    read_marker, scan_tree)
from common import write_marker as common_write_marker

# `<date> <time> <size><unit> <absolute path>` -- gatekeeper's Index-byname shape. The size is
# rounded to a unit and is deliberately not parsed: this tool needs names, not figures.
LINE = re.compile(r"^\s*\S+\s+\S+\s+[\d.]+[kKmMgGbB]?\s+(/\S.*)$")


def write_marker(base_dir, archive, base_url, source, named, gone, failed):
    """Mark an archive that exists ONLY as a URL-list fetch. Refuses to replace another's.

    WHY THIS IS NOT mirror.py's JOB HERE. An archive it never crawled has no marker, and
    everything downstream keys off that file: catalogue.py takes its counts from it, and without
    one the archive reads `None files, 0.0 GB` -- on disk and invisible to every report. That is
    the same hole ia-item-fetch.py closed for the Internet Archive items, for the same reason,
    and the marker is written with the same library function so the two cannot drift in format.

    IT REFUSES TO OVERWRITE SOMEBODY ELSE'S. A manifest fetch is often a TOP-UP of an archive
    mirror.py crawled, and that marker is mirror.py's record of its own run -- replacing it would
    throw away the crawl's failure count and duration and put this tool's name on another's work.

    ITS OWN, THOUGH, IT REPLACES, and the first version got that wrong: it refused every existing
    marker, so a second run over the same archive -- four more files added to a list-fetched
    tree -- left the counts describing the tree as it was before. A marker that is stale is worse
    than one that is missing, because --verify then reports a mismatch that is nobody's fault.
    OURS IS RECOGNISED BY A FIELD ONLY THIS TOOL WRITES, `named-by-the-list`. Not by the prose,
    which a person may edit, and not by a timestamp, which says nothing about who.

    COUNTED WITH THE SAME FUNCTION THAT LATER CHECKS IT, for the reason ia-item-fetch.py records:
    a second counter with its own idea of what an own file is makes a marker that is wrong from
    the moment it is written.
    """
    path = os.path.join(base_dir, COMPLETE_MARKER)
    if exists(path) and "named-by-the-list" not in read_marker(path):
        print("  MARKER LEFT ALONE: %s already exists and this tool did not write it. It belongs "
              "to whatever did -- for a crawled archive that is mirror.py, and its run is not "
              "this one." % path)
        return
    n, b = scan_tree(base_dir)
    common_write_marker(
        path,
        {"archive": archive,
         "source": base_url,
         "completed": time.strftime("%Y-%m-%d %H:%M:%S"),
         "files": n,
         "bytes": b,
         "named-by-the-list": named,
         "gone-from-the-source": gone,
         "failed": failed},
        "Fetched with manifest-fetch.py from a URL LIST, NOT crawled. The source serves no "
        "directory listing this tool could follow -- so completeness here means `everything the "
        "list named`, and the list is only as complete as whatever produced it. That is a weaker "
        "claim than a crawl's and is why it is spelled out.\n"
        "\n"
        "`--verify` compares the tree against the two figures above. See PROVENANCE.md beside "
        "this file for where the list came from and what it could not name.")
    print("  wrote %s: %d files, %d bytes" % (COMPLETE_MARKER, n, b))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--manifest",
                    help="file inside the archive that lists its contents, in the "
                         "`<date> <time> <size> <path>` form gatekeeper.dec.com publishes")
    ap.add_argument("--url-list", metavar="PATH",
                    help="instead of --manifest: a file of absolute URLs, one per line. For a "
                         "store that cannot be enumerated at all -- novasareforever.org answers "
                         "403 to every directory under /user/archive/, and its filenames exist "
                         "only as hrefs on the catalogue pages")
    ap.add_argument("--base", required=True, help="URL the manifest's paths are relative to")
    ap.add_argument("--prefix", default="/",
                    help="only take manifest paths starting with this (default: everything)")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--marker", action="store_true",
                    help="write .mirror-complete afterwards. For an archive that exists "
                         "ONLY as a URL-list fetch: without a marker catalogue.py reports "
                         "it as `None files, 0.0 GB` -- present on disk, invisible to every "
                         "report. Off by default because a top-up of a CRAWLED archive must "
                         "leave mirror.py's own marker alone, and this refuses to overwrite "
                         "one that is already there.")
    ap.add_argument("--ask-gone-again", action="store_true",
                    help="ask for the paths this archive's " + GONE_FILE + " records as 404 or "
                         "410. Off by default: three sessions in a row spent their first "
                         "requests on the same dead names, because a 404 creates no file and so "
                         "a list diffed against the tree names it again every time. On, because "
                         "a host comes back and nothing on disk changes when it does -- the "
                         "record keeps the DATE so this flag has something to mean")
    ap.add_argument("--give-up", type=int, default=5, metavar="N",
                    help="stop after N CONSECUTIVE requests that got no answer at all "
                         "(default 5). A 404 is an answer and resets the count -- see "
                         "common.Patience. A url-list has no person watching it, and "
                         "31 urls at a 120 s timeout is an hour of knocking on a door "
                         "that is already shut; that is how two hosts were lost.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base_dir = os.path.join(args.root, args.archive)
    if not args.manifest and not args.url_list:
        sys.exit("give either --manifest or --url-list")
    if args.manifest and args.url_list:
        sys.exit("--manifest and --url-list are alternatives, not both")

    base_url = args.base.rstrip("/") + "/"
    named = []

    if args.url_list:
        # Paths are derived from the URL's tail after --base, so the local tree mirrors the
        # server's layout rather than flattening it.
        for line in io.open(args.url_list, encoding="utf-8", errors="replace"):
            u = line.strip()
            if not u or u.startswith("#"):
                continue
            if not u.startswith(base_url):
                print("  OUTSIDE THE BASE, skipped: %s" % u[:78])
                continue
            rel = urllib.parse.unquote(u[len(base_url):])
            if rel.startswith(args.prefix.lstrip("/")) or args.prefix == "/":
                named.append(rel)
    else:
        man = os.path.join(base_dir, args.manifest)
        if not exists(man):
            sys.exit("no manifest at %s" % man)
        for line in io.open(man, encoding="utf-8", errors="replace"):
            m = LINE.match(line)
            if m and m.group(1).startswith(args.prefix):
                named.append(m.group(1).lstrip("/"))

    # THE ARCHIVE'S OWN EXCLUDE, ENFORCED HERE AND NOT ONLY WHERE THE LIST WAS MADE. A url list
    # is a file; it can be hand-written, carried over from another day, or produced by a tool
    # that did not know about EXCLUDE -- pages-to-urllist.py did not, until 2026-09-30, and on
    # openpa it offered 580 urls under the two paths that host's robots.txt forbids to every
    # crawler. This is the last point before a request leaves, so it is the one place the check
    # cannot be skipped by feeding the fetch a different list.
    #
    # THE CHECK IS MIRROR.PY'S OWN, not a second comparison written here. A copy would be a
    # fourth place the rule lives and would drift; see is_excluded's docstring, which exists
    # because there were once three.
    refused = []
    try:
        mirror = load_mirror(os.path.dirname(os.path.abspath(__file__)))
        patterns = tuple(mirror.EXCLUDE.get(args.archive, ()))
        if patterns:
            keep = []
            for r in named:
                (refused if mirror.is_excluded(r, patterns, args.archive) else keep).append(r)
            named = keep
    except (OSError, AttributeError):
        # A MISSING REGISTER IS NOT AN EMPTY ONE, and the difference decides whether a fetch is
        # allowed to proceed. Refusing outright would make this tool unusable beside a mirror.py
        # that moved; proceeding in silence is how a forbidden path gets fetched. So: say it.
        print("  WARNING mirror.py could not be read -- NO exclusion was applied to this list.",
              flush=True)
    if refused:
        print("  %d url(s) REFUSED by EXCLUDE[%r] and not requested:" % (len(refused),
                                                                         args.archive))
        for r in refused[:5]:
            print("     %s" % r)
        if len(refused) > 5:
            print("     ... and %d more" % (len(refused) - 5))

    # PATHS THIS SOURCE HAS ALREADY SAID IT DOES NOT HAVE. Skipped before the on-disk test, not
    # after, because the on-disk test is exactly what cannot tell them apart: a 404 leaves no
    # file, so "absent from the tree" is true of a file that is gone and of a file never asked
    # for. Measured 2026-10-02 on openpa: images/dcsscr4.gif asked three times, answered the
    # same way three times, and these names sort to the front -- dcss*, sna* -- so they were the
    # first requests of a session the host grants a few dozen of.
    gone = {} if args.ask_gone_again else read_gone(base_dir)
    skipped_gone = [r for r in named if r in gone]
    if skipped_gone:
        print("  %d path(s) skipped: %s records them as 404/410. --ask-gone-again to ask anyway."
              % (len(skipped_gone), GONE_FILE))
        for r in skipped_gone[:5]:
            print("     %s   (%s)" % (r, gone[r]))
        if len(skipped_gone) > 5:
            print("     ... and %d more" % (len(skipped_gone) - 5))
        named = [r for r in named if r not in gone]

    todo = [r for r in named
            if not exists(os.path.join(base_dir, r.replace("/", os.sep)))]
    print("  %s: the %s names %d paths under %s, %d are missing"
          % (args.archive, "URL list" if args.url_list else "manifest",
             len(named), args.prefix, len(todo)), flush=True)

    if args.dry_run:
        for r in todo[:20]:
            print("     %s" % r)
        if len(todo) > 20:
            print("     ... and %d more" % (len(todo) - 20))
        return 0

    # ONE PACER FOR THE RUN, made here and not in the loop: the pause is about the INTERVAL
    # between two requests, and a pacer created per file has no previous request to measure from
    # and would never wait. It also changes what `--delay` means, for the better -- "not more
    # often than every N seconds" rather than "idle N seconds after every request", so a fetch
    # that took longer than the delay has already paid it instead of paying it twice.
    pacer = Pacer(args.delay)

    ok = gone = failed = 0
    total = 0
    # WHAT DECIDES TO STOP. Not a count of failures -- a count of SILENCES in a row; see
    # common.Patience for why a 404 must reset it and why summing them would get both cases
    # backwards. `stopped` survives the loop so the summary can say the list was not finished.
    patience = Patience(limit=args.give_up)
    stopped = None
    for rel in todo:
        url = base_url + "/".join(urllib.parse.quote(p) for p in rel.split("/"))
        out = os.path.join(base_dir, rel.replace("/", os.sep))
        # WAITED ONCE BEFORE THE REQUEST rather than in each of the three branches below. Every
        # one of them -- fetched, 404, failed -- had its own sleep, because every one of them
        # cost the server a request; asking before covers all three and cannot be forgotten in a
        # fourth.
        pacer.wait(host_of(url))
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            body, _headers = http_get(url, timeout=120)
        except urllib.error.HTTPError as e:
            # A manifest describes the ORIGINAL. A 404 here means the file did not survive the
            # mirroring, which is a fact about the copy and not a failure of this run.
            gone += 1
            # AN HTTP STATUS IS THE SERVER TALKING, so this is progress even though no file
            # arrived. A manifest full of files the mirror never kept is a long run of these and
            # must be allowed to finish -- it is the answer to the question being asked.
            patience.answered()
            # AND THE ANSWER IS WRITTEN DOWN, for 404 and 410 only; record_gone refuses the rest.
            # Without this the same question is asked again next session, and there is no cheaper
            # place to put the answer than beside the files it is about.
            noted = record_gone(base_dir, rel, e.code)
            print("  GONE HTTP %s  %s%s" % (e.code, rel, "" if noted else "  (already noted)"),
                  flush=True)
            continue
        except Exception as exc:                               # noqa: BLE001
            failed += 1
            print("  FAIL   %s :: %s" % (rel, str(exc)[:60]), flush=True)
            if patience.went_quiet(type(exc).__name__):
                stopped = patience.reason
                break
            continue
        with io.open(out, "wb") as fh:
            fh.write(body)
        patience.answered()
        ok += 1
        total += len(body)
        if ok % 25 == 0:
            print("  %d/%d, %.1f MB" % (ok, len(todo), total / 1e6), flush=True)

    print("  DONE fetched %d, gone from the source %d, failed %d, %.1f MB"
          % (ok, gone, failed, total / 1e6))
    if stopped:
        # SAID TWICE AND ON PURPOSE. The count above is the same shape a finished run prints, and
        # a run that stopped early has a REMAINDER -- anyone reading only the totals would take
        # this for the whole list.
        print("  " + stopped)
        print("  %d of %d urls were never tried. Nothing here says they are gone."
              % (len(todo) - (ok + gone + failed), len(todo)))

    if args.marker and stopped:
        # A MARKER IS A CLAIM OF COMPLETENESS and this run stopped in the middle. Writing one here
        # is the exact failure this collection has made twice over: `61 files, 0 failed` on a tree
        # missing 99.4 % of itself. Refuse, and say so.
        print("  NO MARKER WRITTEN -- the run stopped early, so it cannot claim the list is done.")
    elif args.marker:
        write_marker(base_dir, args.archive, base_url, args.url_list or args.manifest,
                     len(named), gone, failed)
    elif ok:
        print("  Next: mirror.py --archive %s --index, then bring the marker up to date."
              % args.archive)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
