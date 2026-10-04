# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Walk a source's own directory listings and write the url list they name.

    python listing-to-urllist.py --base https://retro.digitalvintage.ru/ \
        --branch "Hardware%20Info/OEMINFO/" --branch "Hardware%20Info/ROM%20Archive/" \
        --out Q:\mirror\logs\retro-branches.txt

THE SIBLING OF pages-to-urllist.py AND NOT A REPLACEMENT. That one reads pages ALREADY ON DISK and
costs no requests; this one reads listings from the SOURCE and costs one request per directory. Use
it when the tree is not held yet -- a branch that EXCLUDE has been keeping out, or an archive being
weighed before it is taken -- and use the other one afterwards, for ever.

WHY NOT measure-remote.py. That tool crawls to estimate a SIZE and follows pages as well as
listings, which is what made retro-digitalvintage's `Jumper Reference/` cost ~100 000 requests for
~42 000 files. This walks listings only, emits names rather than a figure, and on a plain Apache
index a whole branch is a few dozen requests: OEMINFO/ and ROM Archive/ together were 38.

IT ONLY READS. No file in the collection is written; the output is a url list for
manifest-fetch.py, which is the tool that may write.

MEASURED ON 2026-10-02, which is why it exists as a tool rather than a throwaway: those two
branches had sat in EXCLUDE since 2026-09-27 marked "not reached at all", on the reputation of the
branch beside them. A walk of 38 directories and 170 HEADs said 22.1 MB and 62.3 MB, and taking
them cost five minutes. The figure was the only thing missing, and the script that produced it
lived in a temporary directory.
"""
import argparse
import collections
import io
import os
import sys
import urllib.parse

from common import Pacer, host_of, http_try, parse_listing, say

# A link that cannot be a child of the directory being listed. `?` is a sort order on a generated
# index and `..` is the way out of the tree; both are the listing talking about itself.
NOT_A_CHILD = ("/", "http", "?", "#")


def walk(base, branch, pacer, cap, report=say):
    """-> (file paths under `branch`, directories walked). One request per directory."""
    queue = collections.deque([branch])
    seen = set()
    files = []
    pages = 0
    while queue and pages < cap:
        d = queue.popleft()
        if d in seen:
            continue
        seen.add(d)
        pacer.wait(host_of(base))
        r = http_try(base + d, timeout=60, limit=8 * 1024 * 1024)
        pages += 1
        status, body = r[0], r[1]
        if not (isinstance(status, int) and status == 200 and body):
            # SAID, NOT SWALLOWED. A directory that does not answer is a hole in the list this
            # produces, and a list with a hole in it is what a fetch then calls complete.
            report("     %s -> %s" % (d, status))
            continue
        # parse_listing WANTS TEXT. It was handed bytes once and raised TypeError on a comparison
        # three frames in, which is a long way from the mistake.
        for href, _size, _mtime in parse_listing(body.decode("utf-8", "replace")):
            if href.startswith(NOT_A_CHILD) or href.startswith(".."):
                continue
            (queue.append if href.endswith("/") else files.append)(d + href)
        if pages % 25 == 0:
            report("     ... %d directories, %d files" % (pages, len(files)))
    if pages >= cap:
        report("     STOPPED at --max-dirs %d with %d still queued -- the list is a FLOOR"
               % (cap, len(queue)))
    return files, pages


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True, help="the archive's base url")
    ap.add_argument("--branch", action="append", default=[], metavar="PATH",
                    help="a path under --base to walk, url-encoded as the server writes it; "
                         "repeatable. Default: the base itself")
    ap.add_argument("--out", metavar="PATH", help="write the urls here, one per line")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between two requests to the same host (default 2). The "
                         "archive's MIN_INTERVAL in mirror.py is the figure to respect; this tool "
                         "does not read it for you")
    ap.add_argument("--max-dirs", type=int, default=2000, metavar="N",
                    help="stop after N directories (default 2000). A brake, because a generated "
                         "index can cross-link for ever -- retro-digitalvintage's Jumper "
                         "Reference/ still had 99 000 pages queued after it had stopped yielding "
                         "new files")
    args = ap.parse_args()

    base = args.base.rstrip("/") + "/"
    branches = args.branch or [""]
    pacer = Pacer(args.delay)
    all_files = []
    for branch in branches:
        files, pages = walk(base, branch, pacer, args.max_dirs)
        say("  %-44s %4d directories, %5d files"
            % (urllib.parse.unquote(branch) or "(the base)", pages, len(files)))
        all_files.extend(files)

    urls = sorted(base + u for u in all_files)
    say("  %d files named in total" % len(urls))
    if args.out:
        d = os.path.dirname(os.path.abspath(args.out))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(urls) + "\n" if urls else "")
        say("  written: %s" % args.out)
        say("  NEXT: manifest-fetch.py --archive <name> --url-list %s --base %s --delay <seconds>"
            % (args.out, base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
