# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""How big is a remote tree, before any disk is committed to it?

    python measure-remote.py http://host/path/ [more URLs...]
    python measure-remote.py --log m.log --no-follow-html http://host/path/

WHY MEASURE FIRST. This collection has twice been steered by an estimate that came from
extrapolating one directory: "ftpmirror.infania.net is 20-60 GB" was arrived at that way, and the
real figure is at least 324 GiB -- of which ~85% turned out to be a bitsavers copy already held.
An unmeasured candidate is not a plan.

IT HANDLES BOTH SHAPES, BECAUSE MIRROR TREES MIX THEM. `ftpmirror.infania.net/sites/os2bbs.com/`
is an Apache autoindex, but `.../solaris/i86pc/` under the same parent is a mirrored WEBSITE with
its own index.html, and `.../unixos2.org/` is a third. A walker that assumes autoindex silently
measures the front page and reports four files. So: parse the size column when the listing has
one, and fall back to a HEAD request when it does not.

SIZES FROM AN AUTOINDEX ARE ROUNDED AND SAID TO BE. Apache's apr_strfsize prints "1.2M", so a
listing-derived total carries a few percent of error -- fine for choosing a disk, not fine for
claiming a tree is complete. The report separates bytes MEASURED by HEAD from bytes READ OFF a
listing, and never merges the two into one authoritative-looking number.

BOUNDED BY DESIGN. --max-pages and --max-heads stop a runaway crawl; whatever was skipped is
COUNTED AND PRINTED, because a silent cap reads as "that is all there is" and this collection has
been misled by exactly that once already (a log truncated its own paths to 52 characters and the
truncated names 404'd, which looked like confirmation).
"""
import argparse
import http.client
import io
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (Pacer, head_size, host_of, http_get, human, looks_like_a_loop,
                    looks_like_a_page, parse_listing, resolution_base, say)

# THE LISTING PARSER LIVES IN common.py AND ONLY THERE. This file used to carry its own --
# A_RE, SIZE_RE, TAG_RE and a SKIP tuple -- and the second copy was worse than the first in a way
# nobody noticed for as long as it existed: its pattern ended in `(.*)$` so that group 4 could
# reach the size column, which meant it saw ONLY THE FIRST LINK OF EACH LINE. Right for
# mod_autoindex, which writes one row per line; wrong for every hand-written page.
#
# MEASURED BEFORE THE SWAP, over the 1 790 stored HTML pages of mcamafia, sgidepot, obsolyte and
# seds-frommert: common.parse_listing finds 2 008 links the private parser missed, and misses 78
# it found. All 78 contain a "?" -- they are cgi-bin query URLs, which were never files. So the
# exchange is a strict gain, and that was checked rather than assumed.
#
# `allow_up=True` IS THE WHOLE DIFFERENCE IN INTENT. A directory listing's `../` is noise and
# common.parse_listing drops it by default; on a hand-written site `../elsewhere/page.htm` is an
# ordinary cross-link, and dropping it cost 722 links in the first comparison run.



# ---------------------------------------------------------------------------- loop guard
#
# Borrowed from mirror.py rather than reimplemented. See that function's docstring for why a
# `seen` set does not catch a symlink cycle served over HTTP.
LOOKS_LIKE_A_LOOP = looks_like_a_loop

# HOW LONG A MEASUREMENT MAY SAY NOTHING before it says something anyway. Two minutes, which
# is short enough that a watching person does not start wondering and long enough that a fast
# tree is not narrated line by line.
QUIET_SECONDS = 120

def rows(body, page, base):
    """-> [(absolute_url, listed_size_or_None)] for links on `page` that stay under `base`.

    TWO DIFFERENT URLs, and conflating them is a real bug this tool shipped with for one run:
    a relative href must resolve against the PAGE it appears on, while the under-the-root test
    uses BASE. Joining against base instead turned `pub/TCImages/` into `/TCImages/`, which 404s,
    and the tree was reported as two files.

    A THIRD URL WHEN THE PAGE DECLARES ONE. unixos2.org's mirrored HTML carries
    `<base href="/mirrors/unixos2.org/">` -- the path the site occupied on ITS ORIGINAL HOST.
    infania serves it at /sites/unixos2.org/ and has no /mirrors/ at all (404). Ignoring the tag
    resolved the author's `pub/list/ux2bs/` against whatever page it appeared on and 404'd; every
    one of those is a link that is not actually broken.
    So: honour <base> as the resolution target, but REBASE IT ONTO OUR ROOT when it points
    somewhere this host does not serve. A mirror's <base> says where the site used to live and
    the mirror root says where it lives now; mapping one onto the other is what mirroring is.
    """
    # The <base> rule lives in common.resolution_base now. It was written HERE first, and
    # mirror.py did not have it until a day later -- so the measurement said eighteen files
    # and the fetch produced eleven, and nothing compared the two.
    page = resolution_base(body, page, base)
    out = []
    for href, size, _mtime in parse_listing(body, allow_up=True):
        # The bare parent link is navigation, not a child. Everything else `..`-relative is a
        # real cross-link on a hand-written site and is resolved below.
        if href in ("/", "../"):
            continue
        full = urllib.parse.urljoin(page, href.split("#")[0])
        if not full.startswith(base):
            continue
        out.append((full, size))
    return out


def is_page(url):
    """-> True if this URL should also be OPENED and walked, not merely counted.

    A directory ends in "/". A mirrored website does not: `unixos2.org/index.html` links
    `pages/Downloads.html`, which links the actual archive. Treating those as leaves is why the
    first run reported unixos2.org as twelve files and os-history.de as six -- those were the
    front pages' links, not the trees. mirror.py's own R16 states the same rule from the other
    side: an HTML page is BOTH content to keep and a listing to walk.
    """
    path = urllib.parse.urlparse(url).path
    if path.endswith("/"):
        return True
    tail = path.rsplit("/", 1)[-1]
    # No extension at all is a page here, and that is this tool's decision rather than the
    # library's: on a remote host a bare name is usually a directory the server will index.
    return looks_like_a_page(tail) or "." not in tail


def start_and_base(url):
    """-> (where to begin, what counts as inside). Two different things, and it cost a run.

    A ROOT MAY BE A PAGE. `sgidepot.co.uk/` is a 71-byte meta-refresh stub, so the tree can only
    be entered at `sgi.html`; `spider.seds.org` is the same shape. Passing that page as the root
    failed twice over on 2026-09-26:

      * main() appended a slash unconditionally, so `sgi.html` was requested as `sgi.html/` and
        answered 404 -- reported honestly as `0 files`, but zero is not a measurement.
      * even without that, `rows()` keeps a child only `if full.startswith(base)`. With the page
        itself as base, NO child can start with it, so the tree would have measured as nothing.

    So: begin at the page, and count everything under the DIRECTORY that holds it.
    """
    if looks_like_a_page(url):
        return url, url.rsplit("/", 1)[0] + "/"
    if not url.endswith("/"):
        url += "/"
    return url, url



def refused(url, base, prefixes):
    """-> the prefix that forbids opening this url, or None.

    Prefixes are relative to the ROOT BEING MEASURED, exactly as mirror.EXCLUDE's are relative to
    an archive's base url -- so a rule written for one can be passed to the other unchanged, and
    a reader comparing the two is comparing the same thing. `is_excluded()` in mirror.py is the
    same comparison with a hit counter attached to its own table.

    THIS TOOL DOES NOT READ robots.txt, AND THAT IS DELIBERATE RATHER THAN MISSING. Reading it
    would mean deciding which agent this collection is, and that question is already settled
    PER HOST in mirror.DO_NOT_FETCH and in the CANDIDATES notes, sometimes against what a naive
    reader of the file would conclude. openpa.net is the case in hand: its robots.txt carries
    `User-Agent: ClaudeBot / Disallow: /`, and the recorded position -- the owner's, and correct
    -- is that this collection is `mirror/1.0` fetching for preservation and not Anthropic's
    training crawler. A tool that applied that line automatically would refuse a host the owner
    did not refuse us. A tool that ignored robots.txt entirely would walk into `/images/`, which
    the same file forbids to EVERYONE through its `User-agent: *` group.

    So the judgement stays with the person, who writes it down, and this honours what they pass.
    `--exclude images/ --exclude systems/images/` is that file's wildcard group, in this tool's
    own vocabulary, and it is the same pair that goes into EXCLUDE["openpa"] when it is fetched.

    A URL OUTSIDE THE ROOT IS NOT REFUSED HERE. Whether to leave the tree at all is the crawl's
    own question -- see `--no-follow-html` and the loop guard -- and answering it here as well
    would put one decision in two places.
    """
    if not url.startswith(base):
        return None
    rel = url[len(base):]
    for prefix in prefixes:
        if rel.startswith(prefix):
            return prefix
    return None

def measure(start, args, log, pacer, base=None):
    base = base or start
    seen = set()          # URLs already OPENED as pages
    counted = set()       # URLs already counted as files -- a page is both, and must not double
    queue = [start]
    files = 0
    listed_b = measured_b = 0
    unknown = pages = heads = 0
    capped_pages = capped_heads = 0
    looped = 0
    excluded = set()
    t0 = time.time()
    said_at = t0

    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        skipped = refused(url, base, args.exclude)
        if skipped is not None:
            excluded.add(skipped)
            continue
        if pages >= args.max_pages:
            capped_pages += 1
            continue
        # BEFORE THE REQUEST, not after it: a page dropped as already-seen or beyond --max-pages
        # was never asked for, and there is nobody to be polite to on its account. The old sleep
        # sat at the foot of the loop and paced those too.
        pacer.wait(host_of(url))
        try:
            body, _hdr = http_get(url, timeout=60)
            ctype = _hdr.get("Content-Type", "")
            pages += 1
        except Exception as exc:
            # The status code IS the diagnosis: 404 means the link is wrong, 403 means the
            # directory exists and is closed. Printing only "HTTPError" throws that away, which
            # is the same evidence-destroying mistake as a log that truncates its own paths.
            code = getattr(exc, "code", None)
            say("     LISTFAIL %s -- %s" % (url, ("HTTP %d" % code) if code else
                                            "%s: %s" % (exc.__class__.__name__, exc)), log)
            continue
        if "html" not in ctype.lower():
            continue                       # a page that turned out to be a file; counted below
        for child, listed in rows(body.decode("utf-8", "replace"), url, base):
            # A page is queued AND counted. Two sets rather than one, because the old single
            # `seen` made those mutually exclusive: whatever was counted could never be opened.
            if args.follow_html and is_page(child) and child not in seen:
                # A SELF-REFERENCING DIRECTORY IS INVISIBLE TO `seen`, because every level of it
                # is a new URL. data.microway.com/pub/ is the archive root; pub/pub/pub/ answers
                # with it again, and this tool once reported 284.44 GB for a 15.66 GB tree.
                loop = LOOKS_LIKE_A_LOOP(child, base) if LOOKS_LIKE_A_LOOP else None
                if loop:
                    say("     LOOP REFUSED %s -- %s" % (child, loop), log)
                    looped += 1
                else:
                    queue.append(child)
            if child.endswith("/") or child in counted:
                continue
            counted.add(child)
            files += 1
            if listed is not None:
                listed_b += listed
            elif heads < args.max_heads:
                try:
                    measured_b += head_size(child)
                    heads += 1
                # A HEAD REQUEST THAT DID NOT ANSWER, AND NOTHING ELSE. It counts the file as
                # unknown, which is honest about the network and dishonest about a typo: a
                # NameError here would make EVERY child unknown and the total meaningless.
                except (urllib.error.URLError, OSError, http.client.HTTPException,
                        ValueError):
                    unknown += 1
            else:
                capped_heads += 1
        # EVERY 25 PAGES OR EVERY QUIET_SECONDS, WHICHEVER COMES FIRST, and the second half
        # was added 2026-09-27 after a run looked dead for 51 minutes and was not. A page is a
        # directory listing, and one directory under `Computer Collection/` holds thousands of
        # files -- each needing a HEAD, because the listing gives no size. Twenty-five such
        # pages is an hour of honest work with nothing printed, which is indistinguishable
        # from a hang. It cost one investigation: the host was probed, the process checked,
        # say() read to see whether it flushes. All fine; the tool was simply quiet.
        if pages % 25 == 0 or time.time() - said_at >= QUIET_SECONDS:
            said_at = time.time()
            # WHERE IT IS, AND NOT ONLY HOW FAR. Added 2026-09-27 after a 318.7-minute run over
            # retro.digitalvintage.ru answered "1.83 TB" and nothing else. The question that
            # followed was the obvious one -- WHICH BRANCH is that? -- and the log could not say,
            # because every one of its 750 progress lines was a running total with no position.
            #
            # The answer had to be RECONSTRUCTED from the 94 LISTFAIL lines, which are the only
            # place a URL appeared: they put 1.62 TB of the 1.83 TB in `Abandonware Archives/`
            # and 109 GB in `Computer Collection/`. That worked only because the run happened to
            # fail often enough to leave a trail, which is not a thing to rely on twice.
            #
            # ONE FIELD, AND IT IS THE BRANCH RATHER THAN THE FULL URL: a full URL would be 150
            # characters of mostly-identical prefix on every line, and what a reader wants is
            # which part of the tree the total is growing in.
            here = url[len(base):].split("/")[0] if url.startswith(base) else url
            say("     %d pages, %d files, %s listed + %s measured, %d queued  in %s"
                % (pages, files, human(listed_b), human(measured_b), len(queue),
                   urllib.parse.unquote(here) or "(root)"), log)

    el = time.time() - t0
    say("  %-46s %6d files  %10s listed + %10s measured  (%d pages, %.1f min)"
        % (base, files, human(listed_b), human(measured_b), pages, el / 60), log)
    if excluded:
        say("     NOT OPENED: %s -- excluded by the caller, not by this tool's judgement"
            % ", ".join(sorted(excluded)), log)
    if unknown or capped_pages or capped_heads:
        say("     NOT COUNTED: %d size lookups failed, %d pages beyond --max-pages, "
            "%d files beyond --max-heads -- the total above is a FLOOR"
            % (unknown, capped_pages, capped_heads), log)
    return {"url": base, "files": files, "listed": listed_b, "measured": measured_b,
            "pages": pages, "unknown": unknown + capped_heads, "capped": capped_pages}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--max-pages", type=int, default=20000)
    ap.add_argument("--max-heads", type=int, default=20000)
    ap.add_argument("--no-follow-html", dest="follow_html", action="store_false",
                    help="do not open HTML pages as listings. Correct for a pure autoindex, "
                         "where every page ends in '/' anyway; wrong for a mirrored website, "
                         "which is what made unixos2.org measure as twelve files.")
    ap.add_argument("--exclude", action="append", default=[], metavar="PREFIX",
                    help="do not open anything under this path, relative to the root being "
                         "measured. Repeatable. THIS TOOL DOES NOT READ robots.txt -- see "
                         "refused() for why that is the caller's job -- so a rule that binds us "
                         "is passed in here. openpa.net's `User-agent: *` disallows /images/ and "
                         "/systems/images/, and measuring them anyway would be asking for "
                         "exactly what the file refuses.")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    log = io.open(args.log, "a", encoding="utf-8") if args.log else None
    say("measure-remote  %d roots  %s" % (len(args.urls), time.strftime("%Y-%m-%d %H:%M")), log)
    res = []
    # ONE PACER FOR THE WHOLE RUN, and per host. --delay is a RATE -- "do not ask this host more
    # often than every N seconds" -- so the time a listing took to arrive counts towards it; the
    # old `time.sleep(args.delay)` idled the full delay on top of a fetch that had already paid
    # it. Made once rather than per root, because two roots given on one command line are often
    # the same server, and pacing them separately promises that server nothing.
    pacer = Pacer(args.delay)
    for u in args.urls:
        start, base = start_and_base(u)
        where = base if start == base else "%s   entered at %s" % (base, start)
        say("\n=== %s" % where, log)
        res.append(measure(start, args, log, pacer, base=base))

    say("\n" + "=" * 92, log)
    tf = sum(r["files"] for r in res)
    tl = sum(r["listed"] for r in res)
    tm = sum(r["measured"] for r in res)
    for r in sorted(res, key=lambda r: -(r["listed"] + r["measured"])):
        say("  %-52s %6d files  %10s" % (r["url"][-52:], r["files"],
                                         human(r["listed"] + r["measured"])), log)
    say("  TOTAL %d files, %s  (%s read off listings, %s measured by HEAD)"
        % (tf, human(tl + tm), human(tl), human(tm)), log)
    miss = sum(r["unknown"] for r in res)
    if miss:
        say("  %d files have NO size in this figure -- it is a floor, not a total" % miss, log)
    if log:
        log.close()


if __name__ == "__main__":
    main()
