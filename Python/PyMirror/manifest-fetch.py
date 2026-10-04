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

from common import (COMPLETE_MARKER, GONE_FILE, GONE_STATUS, MIRROR_ROOT, Pacer, Patience,
                    answered_as_a_directory, blocking_parent, content_root, exists,
                    http_open, local_path,
                    relative_to, safe_name,
                    host_of,
                    load_mirror, local_failure, read_gone, record_gone, under_site,
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

    archive_dir = os.path.join(args.root, args.archive)
    # WHERE THE BASE'S PATHS BELONG, which is not always the archive root. Four archives keep a
    # HOST DIRECTORY LEVEL -- a wayback salvage and a multi-host fetch write `<host>/<path>` --
    # and this tool wrote straight under the root.
    #
    # IT SPLIT AN ARCHIVE ON 2026-10-04. Four techsysadm pages landed in `techsysadm/p/` beside
    # `techsysadm/techsysadm.blogspot.com/`, where the other 368 files live, and had to be moved
    # by hand afterwards. A fetch that puts a file next to the tree instead of in it is worse than
    # one that fails: the file is there, the check cannot see it, and the next survey reports it
    # missing and fetches it again.
    base_dir = content_root(archive_dir, args.base)
    if base_dir != archive_dir:
        print("  %s keeps a host directory level -- writing under %s"
              % (args.archive, os.path.basename(base_dir)), flush=True)
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
            # THE SAME SITE UNDER ANOTHER SPELLING IS STILL THE SAME SITE -- and this was the
            # THIRD tool to get it wrong on 2026-10-02. pages-to-urllist.py and find-sitemaps.py
            # were both fixed hours earlier; this one was overlooked, and the first list that met
            # it lost all 4 404 entries at once: ftp.zx.net.nz publishes its sitemap over https
            # while the archive is registered on http, so every single url was reported OUTSIDE
            # THE BASE and the run ended "0 paths, 0 missing, DONE fetched 0" -- a clean zero that
            # looked like there was nothing to do.
            #
            # Three tools, one rule, now one implementation: common.under_site. What decides
            # offsite is the base, not how the scheme or the `www.` happens to be written.
            cut = under_site(u, base_url)
            if cut is None:
                print("  OUTSIDE THE BASE, skipped: %s" % u[:78])
                continue
            rel = urllib.parse.unquote(cut)
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

    # THE SECOND HALF OF THE SAME DEFECT, found by a test written for the first. This tested the
    # RAW name while the file was written through safe_name(), so every file whose name had to be
    # made storable was judged missing and FETCHED AGAIN on every run -- gsi-collection's
    # `Aster*x_3.1.0.50_pcf_font_problem` is stored as `Aster_x_...`, and this line would have
    # asked that server for it for ever.
    todo = [r for r in named
            if not exists(os.path.join(base_dir, *[safe_name(q) for q in r.split("/") if q]))]
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
    # A PATH NO FILESYSTEM CAN HOLD IS NOT A FETCH THAT FAILED. See common.blocking_parent: a
    # source may serve both `X` and `X/y` and a filesystem may not. Counted apart from `failed`
    # and never charged to Patience, because the request never happened and could not have.
    unstorable = []
    # PATHS THE SERVER ANSWERED AS DIRECTORIES. Not failures and not content: the body is a
    # listing, and storing it under the bare name is how 2 416 files were lost once already.
    directories = []
    # WHAT DECIDES TO STOP. Not a count of failures -- a count of SILENCES in a row; see
    # common.Patience for why a 404 must reset it and why summing them would get both cases
    # backwards. `stopped` survives the loop so the summary can say the list was not finished.
    patience = Patience(limit=args.give_up)
    stopped = None
    for rel in todo:
        url = base_url + "/".join(urllib.parse.quote(p) for p in rel.split("/"))
        # common.local_path AND NOT A JOIN OF OUR OWN. This line read
        #
        #     out = os.path.join(base_dir, rel.replace("/", os.sep))
        #
        # until 2026-10-04, which skips safe_name() and therefore every character NTFS forbids.
        # gsi-collection names a file `Aster*x_3.1.0.50_pcf_font_problem` -- `%2A` in the url --
        # and this tool died on it with an UNHANDLED OSError, Errno 22, after 3 788 of 3 789
        # candidates had been dealt with.
        #
        # THE CRASH IS THE SMALLER HALF. mirror.py stores that file as `Aster_x_...` because it
        # goes through local_path; this tool would have stored it under the raw name wherever the
        # filesystem allowed one. Two tools disagreeing about where a file belongs is how an
        # archive ends up holding the same document twice under two spellings, and how a
        # completeness check then reports one of them missing for ever.
        out = local_path(base_dir, base_url, url)
        # WAITED ONCE BEFORE THE REQUEST rather than in each of the three branches below. Every
        # one of them -- fetched, 404, failed -- had its own sleep, because every one of them
        # cost the server a request; asking before covers all three and cannot be forgotten in a
        # fourth.
        # ASKED BEFORE THE REQUEST, so the source is not made to send bytes that cannot be
        # written -- and, far more importantly, so a local impossibility is never reported as the
        # host going quiet. 30 of these in a row abandoned ps-2.kev009.com with 2 124 fetchable
        # files untouched, and the failure was read as a block: hours of argument about whether a
        # second address would be route-shopping, and a router restarted for nothing, while that
        # server answered 200 throughout.
        blocker = blocking_parent(out)
        if blocker:
            unstorable.append((rel, relative_to(base_dir, blocker)))
            continue
        pacer.wait(host_of(url))
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            # THE FINAL URL IS READ, not just the body, because a trailing slash on it is the
            # server saying "this is a directory". See common.answered_as_a_directory: writing the
            # body under the bare name puts a file where a directory has to go, and on 2026-10-04
            # this tool did exactly that four times -- ps-2.kev009.com answers
            # /ohlandl/CPU/docs/Intel with a redirect to ardent-tool.com/CPU/docs/Intel/ -- and
            # those four impostors then made 692 datasheets unstorable.
            with http_open(url, timeout=120) as resp:
                final = resp.geturl()
                body = resp.read()
                _headers = resp.headers
            if answered_as_a_directory(url, final):
                directories.append((rel, final))
                continue
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
            # TWO REASONS FOR A FALSE, AND THEY ARE NOT THE SAME FACT. record_gone returns False
            # both when the path is already in the file AND when it REFUSES the status code --
            # only 404 and 410 go in. Printing "(already noted)" for the second said the answer
            # was on record when nothing had been written at all.
            #
            # MET ON 2026-10-03: zx-kednos-vms/pub/kednos/vax/pli038.zip is named by the source's
            # own sitemap and answers 403. The fetch said "(already noted)", the archive has no
            # .mirror-gone, and the only record of that 403 is a PERMFAIL line in
            # logs/errors-zx-kednos-vms.txt dated 2026-09-10. So every future survey reports the
            # file as outstanding and asks that server for it again.
            #
            # WHETHER A 403 BELONGS IN .mirror-gone IS NOT THIS LINE'S DECISION. The file records
            # what is GONE; a 403 is the operator refusing, which is a different answer and may
            # not be permanent. Widening GONE_STATUS would change the meaning of a record that
            # data has already been written against, and the register's rule for that is explicit.
            # What this fixes is only the report.
            if noted:
                why = ""
            elif int(e.code) in GONE_STATUS:
                why = "  (already noted)"
            else:
                why = "  (NOT recorded -- only %s go in %s)" % (
                    "/".join(str(c) for c in sorted(GONE_STATUS)), GONE_FILE)
            print("  GONE HTTP %s  %s%s" % (e.code, rel, why), flush=True)
            continue
        except Exception as exc:                               # noqa: BLE001
            failed += 1
            print("  FAIL   %s :: %s" % (rel, str(exc)[:60]), flush=True)
            # DID THIS REQUEST REACH THE WIRE? On 2026-10-02 a 568-url run of openpa ended on two
            # `[Errno 11001] getaddrinfo failed` and announced that the host had stopped talking
            # and should be left alone for days. The owner's wifi had dropped; the host answered
            # 200 within the minute. The run was right to stop and wrong about why, and the why is
            # the part somebody acts on the next day.
            unreached = local_failure(exc)
            spent = (patience.unreachable(unreached) if unreached
                     else patience.went_quiet(type(exc).__name__))
            if spent:
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
    if directories:
        print("  %d path(s) the server answered AS A DIRECTORY -- redirected to the same name "
              "with a trailing slash. The body is a listing and was NOT stored; a file there "
              "would block everything beneath it." % len(directories))
        for rel, final in directories[:6]:
            print("     %-40s -> %s" % (rel[:38], final[-52:]))
    if unstorable:
        # NAMED WITH THE BLOCKER, not just counted. The useful fact is WHICH file is in the way:
        # two of them accounted for all 154 cases on ps-2.kev009.com, so the decision is about two
        # files rather than a hundred and fifty.
        import collections as _c
        by = _c.Counter(b for _r, b in unstorable)
        print("  %d path(s) UNSTORABLE: a file occupies a parent directory. Not requested, and "
              "not counted as a failure." % len(unstorable))
        for blocker, n in by.most_common(10):
            print("     %-54s blocks %d" % (blocker[:52], n))
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
