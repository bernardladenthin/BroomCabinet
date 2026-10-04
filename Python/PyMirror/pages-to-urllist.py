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

from common import (MIRROR_ROOT, BOOKKEEPING_FILES, IMG_SRC, LINK_ODD_RE, GONE_FILE,
                    content_root, exists, load_mirror,
                    looks_like_a_page, read_gone, relative_to, strip_cache_buster, under_site)

# Both are the library's, written out here character for character until 2026-09-23.
HREF = LINK_ODD_RE
IMG = IMG_SRC

# SCHEMES AND SHAPES THAT ARE NOT A FILE ON THIS SITE. `http://`, `https://` and `//` are NOT
# here, and their absence is the whole point of this comment.
#
# THEY WERE HERE UNTIL 2026-10-02 AND COST AN ENTIRE ARCHIVE. A page that links its own files by
# their full address -- `http://host/gfd/area/file.zip` rather than `file.zip` -- is not linking
# offsite, and skipping every absolute URL threw away exactly those. dreamlandbbs-os2 is written
# by MBSE, which spells out the host on every single file link, and this tool reported
#
#     61 stored pages read, 2 targets named ... 0 FILES NAMED AND NOT ON DISK
#
# over an archive holding 61 index pages and not one of the ~6 000 files they name. A clean zero,
# which is the one answer this collection has learned to distrust. The register already carried
# the hazard, beside that archive's own HTML_CRAWL entry: "MBSE writes every file link as
# http://www.dreamlandbbs.com/gfd/<area>/<file>". The CRAWLER was fixed for it; the harvester kept
# its own private skip-list and was not.
#
# WHAT DECIDES OFFSITE IS THE BASE, NOT THE SPELLING, and the loop below already does that test:
# every target is resolved and then compared against the archive's base, with anything outside
# counted separately. Dropping absolute URLs here did the same job a second time and got it wrong,
# because `http://` says nothing about which host follows it.
SKIP = ("#", "mailto:", "javascript:", "data:", "?", "tel:", "about:", "file:")


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
                    # A QUERY MEANS THIS IS NOT A FILE ON THIS SITE, which common.is_child_link
                    # has said since the crawler was written -- "on a generated index it is a sort
                    # order, not a file" -- and which this tool never applied. It cost the headline
                    # figure its meaning: ardent-tool reported 1 562 FILES NAMED AND NOT ON DISK
                    # with THREE actually outstanding, and MEASURING the 1 443 that survived the
                    # other filters settled what they were:
                    #
                    #   type=FB&url=https://...   1 330   Facebook share buttons
                    #   type=DM&url=https://...      76   direct-message share buttons
                    #   file=../2_21/ENGLISH/...     15   a CGI document reader
                    #   lang=en_US&page=...           8
                    #   v=3, v=2                      5   actual cache-busters
                    #
                    # Not one of the first 1 429 is a file, and no amount of filtering downstream
                    # could have made them into one. THE CACHE-BUSTER IS THE ONE EXCEPTION, and
                    # strip_cache_buster carries the safety margin: the query goes only when what
                    # precedes it ends in a static IMAGE extension, where it cannot be selecting
                    # anything. `reader.html?file=...` names a different document per query and
                    # keeps its query -- and is then dropped by the line below, which is right,
                    # because what it names is a CGI response and not a file in this tree.
                    h = strip_cache_buster(h)
                    if "?" in h:
                        continue
                    if not h or h.lower().startswith(SKIP):
                        continue
                    named.setdefault(urllib.parse.urljoin(here_url, h), here_url)

    patterns, excluded_by = refusals(here, args.archive)
    # WHAT THE SOURCE HAS ALREADY ANSWERED 404 FOR. Without this the same dead names are reported
    # as outstanding after every fetch, for ever: ardent-tool carries 95 of them and they were the
    # rest of the gap between its headline figure and its real one. .mirror-gone is the record a
    # fetch writes when the source says the file is gone -- treating it as still-missing asks a
    # stranger's server the same question again on every run.
    # WHERE THE BASE'S PATHS ACTUALLY LIVE. Four archives keep a host directory level -- a wayback
    # salvage and a multi-host fetch write `<host>/<path>` -- and comparing against the archive
    # root instead reported 199 held pages of techsysadm as missing. See common.content_root.
    tree = content_root(root, base)
    gone = read_gone(root)
    files, dirs, outside, refused, dead = [], [], 0, [], []
    for url in sorted(named):
        # THE SAME SITE UNDER ANOTHER SPELLING IS STILL THE SAME SITE. A plain startswith on the
        # registered base reads https where the register said http -- or the apex where the page
        # says www -- as a foreign host, and the archive then looks complete because nothing
        # overlapped. common.under_site folds both; see its docstring for the two tools that
        # needed it on the same day.
        cut = under_site(url, base)
        if cut is None:
            outside += 1
            continue
        rel = urllib.parse.unquote(cut)
        if not rel or rel.endswith("/"):
            continue
        # The archive's own EXCLUDE, applied with the crawler's own comparison rather than a
        # second one written here -- see refusals() for what an unfiltered list would ask for.
        if excluded_by and excluded_by(rel, patterns, args.archive):
            refused.append(rel)
            continue
        local = os.path.join(tree, *[p for p in rel.split("/") if p])
        if exists(local):
            continue
        if rel in gone:
            dead.append(rel)
            continue
        # A directory linked without its slash is not a file. If the directory is here, the
        # crawler already walked it; asking for the bare name only earns a redirect.
        if os.path.isdir(local):
            dirs.append(rel)
            continue
        # WRITTEN IN THE REGISTERED BASE'S SPELLING, not the page's. Once the same site under
        # another scheme or host spelling is accepted as its own -- see under_site -- the raw url
        # may say https where the register says http, and manifest-fetch.py tests its list against
        # `--base` and would report every one of them as OUTSIDE THE BASE and skip it. Accepting a
        # second spelling on the way in while emitting it on the way out moves the rejection one
        # tool further along instead of removing it.
        files.append(base + urllib.parse.quote(rel, safe="/"))

    print("  %s: %d stored pages read, %d targets named" % (args.archive, pages, len(named)))
    print("     %d outside the archive" % outside)
    print("     %d directory links without a trailing slash (already walked)" % len(dirs))
    if dead:
        print("     %d already answered 404 by the source (in %s) -- not counted below"
              % (len(dead), GONE_FILE))
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
