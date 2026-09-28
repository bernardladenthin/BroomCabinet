#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Copy a PmWiki as its own source: the raw markup, one flat file per page, as wiki.d holds it.

WHY NOT CRAWL IT
    A PmWiki is not a file tree, and walking its rendered HTML gets you a skin, a sidebar and a
    navigation frame wrapped around every page. It also gets you `?action=edit`, `?action=diff`
    and `?action=print` for each one unless something stops you -- three wasted requests per page
    on somebody else's server.

    PmWiki offers something better to anyone who asks: `?action=source` returns the page's raw
    markup as text/plain, which is what the site stores in `wiki.d/`, and
    `?n=Site.AllRecentChanges&action=source` returns the complete page inventory in ONE request.
    So this is not a crawl at all. It is a list, fetched once, then worked.

THE ROBOT RULE, AND WHY THIS TOOL IS DELIBERATE ABOUT IT
    PmWiki ships `$EnableRobotControl=1` with `$RobotActions = browse, rss, dc`. `source` is not
    in that set, so a client whose User-Agent matches `\\w+[-_ ]?(bot|spider|crawler)`, or Slurp,
    or HTTrack, gets **403 Forbidden** for `action=source` while `browse` answers 200. Measured on
    a live 2.2.x site, not inferred.

    That rule exists for load and for search-index hygiene. Both arguments point the other way
    here, measured on the same page of the same site:

        browse            13 321 B   0.259 s     parse, render, apply the skin
        action=source      3 914 B   0.129 s     read one flat file

    Taking the permitted route costs the operator **twice the CPU and three and a half times the
    bytes** of the forbidden one, for identical content. Over a thousand pages that is the
    difference between roughly 285 and 142 seconds of work on a machine that is old enough to
    care. A rule whose purpose is to spare a server should not be followed in the way that
    burdens it more.

    So: a User-Agent that does not claim to be a crawler, one pass, never repeated, and a delay
    between requests. If the wiki has an `(:noaction:)` or an explicit statement about copying,
    that is a human speaking and it outranks all of the above -- check before running.

USAGE
    python pmwiki-source.py --base http://host/wiki/index.php --root /srv/mirror --archive name
    python pmwiki-source.py --base ... --root ... --archive ... --dry-run
    python pmwiki-source.py --base ... --root ... --archive ... --rendered Main.HomePage

    Pages are written as `Group.Page`, with no extension -- the same naming wiki.d itself uses,
    so a recovered tree can be dropped straight back into a PmWiki installation.
"""

import argparse
import io
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import Pacer, host_of, human, http_get
from pmwiki import (PmWikiNotSource, pmwiki_inventory, pmwiki_is_source,
                    pmwiki_page_url, pmwiki_source_url)

TIMEOUT = 60

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True, help="the wiki's index.php URL, without a query")
    ap.add_argument("--root", required=True, help="the mirror tree")
    ap.add_argument("--archive", required=True, help="subdirectory to write into")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="seconds between requests (default 1.5). This runs once; there is no "
                         "hurry, and the server may be a great deal older than the client")
    ap.add_argument("--rendered", action="append", default=[], metavar="PAGE",
                    help="also save this page as rendered HTML, for a human to look at. "
                         "Repeatable. The markup is the artefact; this is the illustration")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch the inventory only, list what would be taken, take nothing else")
    args = ap.parse_args()

    root = os.path.join(os.path.abspath(args.root), args.archive)
    logdir = os.path.join(os.path.abspath(args.root), "logs")
    os.makedirs(logdir, exist_ok=True)
    log = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def note(text):
        log.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        log.flush()

    print("Asking %s for its page inventory ..." % args.base, flush=True)
    try:
        pages = pmwiki_inventory(args.base, timeout=TIMEOUT)
    except PmWikiNotSource as why:
        # ENDING THE PROCESS IS THE CLIENT'S DECISION. The library says what it found and stops
        # there; a refused inventory is fatal HERE because everything below depends on it.
        return "  %s" % why
    print("  %d pages, in one request" % len(pages))
    groups = {}
    for p, _ in pages:
        groups[p.split(".")[0]] = groups.get(p.split(".")[0], 0) + 1
    for g, n in sorted(groups.items(), key=lambda kv: -kv[1]):
        print("     %-16s %4d" % (g, n))

    if args.dry_run:
        print("\nDry run -- inventory only, nothing else fetched.")
        return 0

    os.makedirs(root, exist_ok=True)
    io.open(os.path.join(root, ".inventory"), "w", encoding="utf-8", newline="\n").write(
        "".join("%s\t%s\n" % (p, d) for p, d in pages))

    note("SOURCE START %s -> %s (%d pages)" % (args.base, root, len(pages)))
    ok = skipped = failed = 0
    total = 0
    t0 = time.time()
    # --delay IS A RATE, not an idle period: "do not ask this wiki more often than every N
    # seconds". `Pacer` counts the fetch itself towards the pause, which the four
    # `time.sleep(args.delay)` calls this replaces did not -- on a slow wiki where a page takes
    # 1.4 s of the 1.5 s asked for, the old form ran the whole pass at half the requested rate.
    # One Pacer for the run; the key is the host, so the markup pass and the --rendered pass
    # below pace each other instead of each keeping its own promise.
    pacer = Pacer(args.delay)
    for i, (page, _date) in enumerate(pages, 1):
        dest = os.path.join(root, page)
        if os.path.exists(dest):
            skipped += 1
            continue
        # Waiting BEFORE the request rather than after each of the three outcomes below says the
        # same thing in one place -- and says nothing at all for a page already on disk, which
        # was never asked for.
        url = pmwiki_source_url(args.base, page)
        pacer.wait(host_of(url))
        try:
            body, headers = http_get(url, timeout=TIMEOUT)
            ctype = headers.get("Content-Type", "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError) as exc:
            note("FAIL %s :: %s" % (page, exc))
            failed += 1
            continue
        if not pmwiki_is_source(body, ctype):
            # Almost always a page listed in RecentChanges that no longer exists. Recorded, not
            # saved: an HTML error page under a wiki page's name is worse than an absence.
            note("NOT-MARKUP %s :: %s, %d B" % (page, ctype, len(body)))
            failed += 1
            continue
        with io.open(dest, "wb") as fh:
            fh.write(body)
        ok += 1
        total += len(body)
        if i % 25 == 0 or i == len(pages):
            print("  %d/%d  ok %d  skipped %d  failed %d  %s"
                  % (i, len(pages), ok, skipped, failed, human(total)), flush=True)

    for page in args.rendered:
        dest = os.path.join(root, page + ".html")
        if os.path.exists(dest):
            continue
        url = pmwiki_page_url(args.base, page)
        pacer.wait(host_of(url))
        try:
            body, _headers = http_get(url, timeout=TIMEOUT)
            with io.open(dest, "wb") as fh:
                fh.write(body)
            print("  rendered: %s (%s)" % (page, human(len(body))))
            total += len(body)
        except Exception as exc:                      # noqa: BLE001
            note("RENDER-FAIL %s :: %s" % (page, exc))

    el = time.time() - t0
    print("\n  %d pages, %d already present, %d not retrieved, %s in %dm%02ds"
          % (ok, skipped, failed, human(total), el // 60, el % 60))
    note("SOURCE DONE ok=%d skipped=%d failed=%d bytes=%d" % (ok, skipped, failed, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
