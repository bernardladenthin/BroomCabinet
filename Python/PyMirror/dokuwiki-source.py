#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Copy a DokuWiki as raw wiki markup, from the wiki's own page index.

WHEN THIS IS THE RIGHT TOOL
    When the target is a DokuWiki and the crawler would be the wrong instrument -- the same
    reasoning as pmwiki-source.py beside this file, and the same conclusion for the same reason.

    A DokuWiki addresses pages as QUERY STRINGS: `doku.php?id=aix:boot_problem`. Those URLs are
    reachable only from the wiki's own sidebar, which is rendered per page, so a crawler entering
    at the front page finds the namespace index and very often stops there. This is not a
    hypothetical: measured on rainsbrook.co.uk, the Internet Archive holds 5 476 URLs from one
    DokuWiki and exactly ONE of them is an AIX page. On emmanuel.iffly.free.fr it holds 436 URLs
    of which most are crawler-trap variants (`do=edit`, `do=backlink`, sort parameters) and only
    ~71 are content.

    So: ask the wiki for its index instead of walking links, and take each page as source.

        ?do=index                     the complete page tree, one request
        ?id=<page>&do=export_raw      that page as the wikitext the wiki actually stores

    The result is smaller, cheaper for the server, free of skin and navigation furniture, and
    closer to what the wiki is than any copy of its rendered HTML.

USAGE
    python dokuwiki-source.py --base https://example.org/doku.php \\
        --root /srv/mirror --archive example-wiki --delay 1.5

THINGS THAT WILL BITE
    1. `do=index` renders the tree with JavaScript-collapsed namespaces on some themes. The `idx`
       parameter expands one: `?do=index&idx=aix`. This tool walks namespaces explicitly rather
       than trusting a single index page.
    2. `export_raw` returns text/plain with a 200 even for a page that does not exist -- the body
       is then empty. Zero-length is treated as a miss, not as an empty page.
    3. Page ids use `:` as the namespace separator and that is not a legal filename character on
       Windows. Ids are written with `:` mapped to the path separator, so `aix:boot` becomes
       `aix/boot.txt`, which also makes the namespace tree browsable on disk.
    4. Media (images, PDFs) are NOT wikitext and do not come out of export_raw, and THIS TOOL DOES
       NOT FETCH THEM. Earlier text here described a --media flag using
       `lib/exe/fetch.php?media=<id>`; neither the flag nor the code was ever written. What comes
       out of this tool is the wikitext and nothing else.
    5. Some wikis disable export_raw. If the first page returns HTML rather than text, this tool
       says so and stops rather than saving a skin.

POLITENESS
    One request per page and one for the index. The default delay is 1.5 s because these wikis are
    typically one person's machine; several in this collection run PHP that went out of support
    years ago. Leave it alone unless the operator has said otherwise.
"""

import argparse
import io
import os
import sys
import time

from common import Pacer, host_of, http_open
from dokuwiki import dokuwiki_local_path, dokuwiki_page_ids, dokuwiki_source_url

TIMEOUT = 90

def fetch(url):
    with http_open(url, timeout=TIMEOUT) as r:
        return r.read(), r.headers.get("Content-Type", "")


def index_progress(namespace, count, queued, error):
    """One line per namespace. THE TOOL OWNS THE SCREEN, the library does not."""
    if error is not None:
        print("  index %-28s FAILED %s" % (namespace or "(root)", error), flush=True)
    else:
        print("  index %-28s %4d ids so far, %d namespaces queued"
              % (namespace or "(root)", count, queued), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True,
                    help="the wiki entry point, e.g. https://example.org/doku.php")
    ap.add_argument("--root", required=True, help="the mirror tree")
    ap.add_argument("--archive", required=True, help="subdirectory to write into")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="seconds between requests (default 1.5). These are one-person servers")
    ap.add_argument("--dry-run", action="store_true", help="list the page ids and stop")
    args = ap.parse_args()

    base = args.base
    root = os.path.join(os.path.abspath(args.root), args.archive)
    logdir = os.path.join(os.path.abspath(args.root), "logs")
    os.makedirs(logdir, exist_ok=True)
    log = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def note(t):
        log.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), t))
        log.flush()

    # ONE PACER FOR THE RUN, and one for BOTH phases: the index walk and the page fetches go to
    # the same host, so they must share one rate rather than keep one each. Made here and not in
    # the loop, because a pacer that is new every iteration has no previous request to measure
    # from and would never wait. `--delay` now means "not more often than every N seconds", so
    # the time a request itself took counts towards the pause instead of being added to it.
    pacer = Pacer(args.delay)
    host = host_of(base)

    print("Asking %s for its own page index ..." % base, flush=True)
    # NO `delay` ARGUMENT: the pacer already carries it, and passing both would state the rate
    # twice with nothing keeping the two statements equal.
    ids = dokuwiki_page_ids(base, report=index_progress, timeout=TIMEOUT, pacer=pacer)
    print("\n  %d pages\n" % len(ids), flush=True)
    if args.dry_run:
        for i in ids[:40]:
            print("     %s" % i)
        if len(ids) > 40:
            print("     ... and %d more" % (len(ids) - 40))
        return 0

    note("WIKI START %s -> %s (%d pages)" % (base, root, len(ids)))
    ok = skipped = empty = failed = 0
    total = 0
    t0 = time.time()
    for i, pid in enumerate(ids, 1):
        dest = dokuwiki_local_path(root, pid)
        if dest is None:
            continue
        if os.path.exists(dest):
            skipped += 1
            continue
        url = dokuwiki_source_url(base, pid)
        # WAITED ONCE BEFORE THE REQUEST rather than in each branch after it. A page that
        # failed, a page that came back empty and a page that was saved all cost the server the
        # same one request and all three had their own sleep; asking first is the same rate in
        # one place. The pages already on disk above are skipped without a wait, because nothing
        # is asked for them.
        pacer.wait(host)
        try:
            body, ctype = fetch(url)
        except Exception as exc:
            note("FAIL %s :: %s" % (pid, exc))
            failed += 1
            continue
        if "html" in ctype.lower():
            print("\n  %s answered HTML, not wikitext -- export_raw looks disabled here."
                  % url, flush=True)
            print("  Stopping rather than saving a skin. Nothing was written for this page.")
            note("ABORT export_raw disabled (Content-Type %s)" % ctype)
            return 2
        if not body.strip():
            empty += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        io.open(dest, "wb").write(body)
        ok += 1
        total += len(body)
        if i % 25 == 0 or i == len(ids):
            print("  %d/%d  ok %d  empty %d  failed %d  skipped %d  %.1f KB"
                  % (i, len(ids), ok, empty, failed, skipped, total / 1024.0), flush=True)

    el = time.time() - t0
    print("\n  fetched %d, empty %d, failed %d, already present %d, %.1f KB in %dm%02ds"
          % (ok, empty, failed, skipped, total / 1024.0, el // 60, el % 60))
    note("WIKI DONE ok=%d empty=%d failed=%d skipped=%d bytes=%d" % (ok, empty, failed, skipped, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
