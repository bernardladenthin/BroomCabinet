# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What do an archive's BOOKKEEPING_FILES STORED PAGES name that is not on disk? Answered for zero requests.

    python pages-to-urllist.py --archive dialectronics
    python pages-to-urllist.py --archive dialectronics --out todo.txt
    ...then: manifest-fetch.py --archive dialectronics --url-list todo.txt --base <url> --delay 4

WHY THIS EXISTS. Some hosts ration requests rather than rate. dialectronics.com allows roughly
227 in a window and then stops answering for hours -- measured three times, at eight connections,
at one connection, and at four seconds apart. Against such a host every crawl is a budget, and
the budget decides how much progress a session makes.

A crawl spends that budget badly. `ENUM COMPLETE: 118 directories, 267 files` -- the run walked
118 listings, whose contents were already on disk, before asking for a single missing file. Half
the quota went on re-counting.

THE PAGES ARE ALREADY HERE. For any HTML_CRAWL archive every listing and every hand-written page
was saved. Reading them back yields the same link set the crawler would rediscover, for nothing,
and the difference against the tree is exactly what is still owed. dialectronics: 41 stored pages,
224 targets named, 158 of them real files absent from disk -- a list that fits inside one window
where a crawl needed three.

WHAT IT IS NOT, AND THIS MATTERS MORE THAN WHAT IT IS.

**A LINK IS NOT A FILE.** This tool reports what pages NAME and the tree LACKS. Whether the server
still has those bytes is a separate question that only the server can answer. The first run of
this list against dialectronics got exactly two answers before the host cut us off, and BOTH WERE
HTTP 404: 156 of the 158 entries were images in one directory that the pages link and the server
does not have. Two samples cannot condemn all 156 -- but "158 files are missing" was never
measured, it was counted off the pages, and the difference is the whole lesson of this collection.
ardent-tool carried 15 478 links the old parser could not see and lost nothing at all.

So: a list from here is a list of CANDIDATES. Feed it to manifest-fetch.py, which reports 404
separately from failure precisely so the difference stays visible, and read the result as the
measurement -- not this output.

It also cannot name what no stored page mentions. A directory whose listing was never readable
stays unknown; only a crawl opens it. And a crawl works from LISTINGS, i.e. from what the server
says it has, which is the stronger evidence. This tool shortens a rationed fetch; it does not
replace the closing run, and it does not outrank it.

Reads only. Opens no connection.
"""

import argparse
import html
import io
import os
import sys
import urllib.parse

from common import (MIRROR_ROOT, BOOKKEEPING_FILES, IMG_SRC, LINK_ODD_RE, exists, load_mirror,
                    looks_like_a_page, relative_to)

# Both are the library's, written out here character for character until 2026-09-23.
HREF = LINK_ODD_RE
IMG = IMG_SRC

SKIP = ("http://", "https://", "//", "#", "mailto:", "javascript:", "data:", "?", "ftp://",
        "tel:", "about:", "file:")


def refusals(here, archive):
    """-> (EXCLUDE patterns for this archive, the checker), or ((), None) if mirror.py is absent.

    WHY A LIST FROM HERE HAS TO BE FILTERED AT ALL. This tool reads pages and reports what they
    name; a page names whatever its author linked, and an EXCLUDE entry is the record of what
    this collection has decided -- or been told -- not to take. The two have never agreed and
    were never going to.

    MEASURED 2026-09-30 ON openpa: 621 urls harvested, of which 580 sit under images/ and
    systems/images/. Those two paths are openpa.net's robots.txt WILDCARD group -- not a
    preference of ours, a rule binding every crawler -- and the next line this tool prints is a
    manifest-fetch.py command. An unfiltered list is therefore an instruction to fetch 580 things
    nobody is allowed to fetch, printed by the tool as the obvious next step.

    It was caught by hand, twice, on two consecutive days, by someone who happened to remember
    the rule. That is not a check.
    """
    try:
        m = load_mirror(here)
        return tuple(m.EXCLUDE.get(archive, ())), m.is_excluded
    except (OSError, AttributeError):
        return (), None


def base_urls(here):
    """-> {archive: base url} from mirror.py, or {} if it cannot be read."""
    try:
        return dict(load_mirror(here).ARCHIVES)
    # MIRROR.PY IS NOT BESIDE THIS SCRIPT, AND NOTHING ELSE. It was `except Exception`,
    # which also swallows an AttributeError -- so the day mirror.py stopped carrying
    # ARCHIVES, every tool reading it here would have quietly seen an empty register and
    # reported a clean pass over nothing. "The file is absent" is a fact; "the register
    # moved" is a defect, and only the first belongs here.
    except (OSError, ImportError):
        return {}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--base", help="base URL; taken from mirror.py's ARCHIVES when omitted")
    ap.add_argument("--images", action="store_true",
                    help="also follow <img src>. Off by default: on a generated index the only "
                         "images are the server's own icons, and they resolve outside the "
                         "archive anyway")
    ap.add_argument("--out", help="write the URL list here (default: print a summary only)")
    args = ap.parse_args()

    root = os.path.join(args.root, args.archive)
    if not os.path.isdir(root):
        sys.exit("no such archive: %s" % root)
    base = args.base or base_urls(here).get(args.archive)
    if not base:
        sys.exit("no base URL for %s -- pass --base" % args.archive)
    base = base.rstrip("/") + "/"

    named, pages = {}, 0
    for dirpath, _d, names in os.walk(root):
        for f in names:
            if f in BOOKKEEPING_FILES or not looks_like_a_page(f):
                continue
            pages += 1
            try:
                body = io.open(os.path.join(dirpath, f),
                               encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # The page's own location, so relative links resolve as the crawler resolved them.
            rel = relative_to(root, dirpath)
            here_url = base if rel in (".", "") else base + rel + "/"
            rxs = (HREF, IMG) if args.images else (HREF,)
            for rx in rxs:
                for a, b, c in rx.findall(body):
                    # UNESCAPE FIRST. An href written as numeric character references -- the old
                    # anti-spam `&#109;&#097;...` for mailto: -- otherwise splits at the '#' of
                    # its own first entity and leaves a bare ampersand, which looks like a file.
                    # This tool found that defect in mirror.py and must not carry it itself.
                    h = html.unescape((a or b or c).strip()).split("#")[0]
                    if not h or h.lower().startswith(SKIP):
                        continue
                    named.setdefault(urllib.parse.urljoin(here_url, h), here_url)

    patterns, excluded_by = refusals(here, args.archive)
    files, dirs, outside, refused = [], [], 0, []
    for url in sorted(named):
        if not url.startswith(base):
            outside += 1
            continue
        rel = urllib.parse.unquote(url[len(base):])
        if not rel or rel.endswith("/"):
            continue
        # The archive's own EXCLUDE, applied with the crawler's own comparison rather than a
        # second one written here -- see refusals() for what an unfiltered list would ask for.
        if excluded_by and excluded_by(rel, patterns, args.archive):
            refused.append(rel)
            continue
        local = os.path.join(root, *[p for p in rel.split("/") if p])
        if exists(local):
            continue
        # A directory linked without its slash is not a file. If the directory is here, the
        # crawler already walked it; asking for the bare name only earns a redirect.
        if os.path.isdir(local):
            dirs.append(rel)
            continue
        files.append(url)

    print("  %s: %d stored pages read, %d targets named" % (args.archive, pages, len(named)))
    print("     %d outside the archive" % outside)
    print("     %d directory links without a trailing slash (already walked)" % len(dirs))
    if refused:
        # SAID BEFORE THE HEADLINE FIGURE, not after it. The count below is what the next command
        # would fetch, and a reader who sees only that number cannot tell it was ever narrowed.
        print("     %d REFUSED by EXCLUDE[%r] -- not offered, not counted below"
              % (len(refused), args.archive))
        for pattern in patterns:
            n = sum(1 for r in refused if r.startswith(pattern))
            if n:
                print("        %-24s %d" % (pattern, n))
    elif patterns:
        print("     EXCLUDE[%r] is set (%s) and matched nothing here"
              % (args.archive, ", ".join(patterns)))
    elif excluded_by is None:
        # A MISSING REGISTER MUST NOT LOOK LIKE AN EMPTY ONE. Without mirror.py this tool cannot
        # know what is refused, and silence would read as "nothing is".
        print("     WARNING mirror.py could not be read -- NO exclusion was applied. Check the "
              "list by hand before fetching it.")
    print("     %d FILES NAMED AND NOT ON DISK" % len(files))
    for u in files[:12]:
        print("        %s" % urllib.parse.unquote(u[len(base):])[:86])
    if len(files) > 12:
        print("        ... and %d more" % (len(files) - 12))

    if args.out:
        io.open(args.out, "w", encoding="utf-8", newline="\n").write("\n".join(files) + "\n")
        print("\n  written: %s" % args.out)
        print("  NEXT: manifest-fetch.py --archive %s --url-list %s --base %s --delay <seconds>"
              % (args.archive, args.out, base))
        print("  AND AFTERWARDS a normal run, for the directories no stored page names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
