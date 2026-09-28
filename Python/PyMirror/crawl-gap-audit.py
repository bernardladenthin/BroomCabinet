# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What did the crawler fail to SEE? Read the stored pages and ask the tree.

Every defect this collection found between 2026-09-08 and 2026-09-11 has the same shape: a run
reports COMPLETE, with zero failures and zero unreadable listings, over an archive that is short.
Nothing failed -- the files were never requested, because the parser did not recognise the form
in which the page named them.

    <img src="...">                     12 195 files across eight archives, including
                                        board photographs and chip images
    <a class="..." href="...">          87 links on one page, 3 of them visible; that run
                                        reported COMPLETE WITH ZERO FILES
    <frame src="...">                   a frameset root: 387 bytes, no <a> at all, and a
                                        1.72 GB archive fetched as 0 files
    case collisions                     153 files dropped and logged, unnoticed for six weeks
    a directory that serves a document  271 files that no crawl could ever have reached

NO COUNTER IN THE CRAWLER CAN CATCH ANY OF THESE. This tool exists because the only thing that
can is a second reading of the pages we already hold, with a wider notion of what a link is.

    python crawl-gap-audit.py                          every archive, every check
    python crawl-gap-audit.py --archive ardent-tool    one of them
    python crawl-gap-audit.py --links                  only the link-form check

WHAT IT DOES NOT DO. It reports what needs CHECKING, never what is lost. The difference is the
most expensive lesson in this file's history: ardent-tool had 15 478 links the old rules could not
see and ZERO missing files -- every target had been reached another way. A tool that called those
15 478 a loss would have sent someone chasing nothing for a week. Conversely, 765 COLLISION
DROPPED lines in one log turned out to be 153 real losses, and only a comparison against the tree
could tell which was which.

It opens no network connection. Everything here is local.
"""

import argparse
import collections
import io
import os
import re
import sys
import urllib.parse

from common import (MIRROR_ROOT, BOOKKEEPING_FILES, COLLISION_DROPPED, FRAME_RE, IMG_SRC,
                    LINK_ODD_RE, exists, load_mirror, looks_like_a_page)


# href as the FIRST attribute -- what mirror.py's LINK_RE matched, and for a long time all it
# matched. Kept here to measure the gap rather than to find links.
HREF_FIRST = re.compile(r'<a\s+href="', re.I)
# Every form: any quoting, any attribute order. All three were written out here character
# for character until 2026-09-23, and are the library's.
HREF_ANY = LINK_ODD_RE
IMG_ANY = IMG_SRC
FRAME_ANY = FRAME_RE

DROPPED = COLLISION_DROPPED
# `file:` BELONGS HERE AND WAS MISSING. ps-2.kev009.com's saved fax pages carry
# `<img src=file:/PitStop/packages/gifs/bolt.gif` -- unquoted, and an absolute path on the
# machine of whoever saved the page in the 1990s. Not fetchable by anyone, ever.
#
# IT REMOVED 5 ENTRIES, NOT THE 2 455 CLAIMED FOR IT. check_refs returns a SET of resolved target
# PATHS; hundreds of file: references point at the same handful of paths and collapse. The column
# was read as a reference count and it is a distinct-path count -- "a pattern count is not a loss
# count" again, one level further down. Fix kept because the rejection is right; the claim was
# not. The same pages also name those images correctly as `../gifs/bolt.gif`, which IS on disk.
SKIP_SCHEME = ("http://", "https://", "//", "data:", "mailto:", "javascript:", "tel:",
               "about:", "#", "ftp://", "file:")


def pages_of(base):
    """-> (relative dir, filename, body) for every stored HTML page under `base`."""
    for dirpath, _dirnames, names in os.walk(base):
        for n in names:
            if n in BOOKKEEPING_FILES or not looks_like_a_page(n):
                continue
            try:
                yield dirpath, n, io.open(os.path.join(dirpath, n),
                                          encoding="utf-8", errors="replace").read()
            except OSError:
                continue


def _targets(rx, body):
    for a, b, c in rx.findall(body):
        t = (a or b or c).strip()
        if t and not t.lower().startswith(SKIP_SCHEME):
            yield t


def check_refs(base, rx, label):
    """-> (named, missing_set) for one reference form, resolved against each page's own location.

    A target is counted only if it resolves INSIDE the archive. Anything above the root belongs
    to someone else and is not this collection's business.
    """
    # NORMALISE THE BASE BEFORE COMPARING AGAINST NORMALISED TARGETS. `target` below is built
    # with os.path.normpath, which rewrites every "/" as "\" on Windows; `base` arrives however
    # --root was typed. Given `--root Q:/mirror` the two differ from the third character on, the
    # containment test fails for every single target, and this function returns an empty missing
    # set for every archive -- reporting a clean bill of health because it compared nothing.
    # Found 2026-09-11: the audit said sun3arc had 0 absent images while a direct call to this
    # same function said 213. A checker that reads nothing and a checker that finds nothing print
    # the identical line, which is precisely the defect class this file exists to catch.
    base = os.path.normpath(base)
    named = 0
    missing = set()
    for dirpath, _n, body in pages_of(base):
        for t in _targets(rx, body):
            named += 1
            rel = urllib.parse.unquote(t.split("#")[0].split("?")[0])
            if not rel:
                continue
            target = os.path.normpath(os.path.join(dirpath, rel.replace("/", os.sep)))
            if not target.lower().startswith(base.lower()):
                continue
            if exists(target):
                continue
            # A directory link is satisfied by the directory or by an index page inside it.
            if any(exists(os.path.join(target, i))
                   for i in ("index.html", "index.htm", "default.html")):
                continue
            missing.add(target)
    return named, missing


def check_link_forms(base):
    """-> (href-first count, href-any count). The gap is what the old LINK_RE could not see.

    COUNTS LINKS, NOT LOSSES, and the distinction is the point: ardent-tool showed 15 478 links
    invisible to the old rule and lost nothing at all.
    """
    first = anyq = 0
    for _d, _n, body in pages_of(base):
        first += len(HREF_FIRST.findall(body))
        anyq += sum(1 for _ in HREF_ANY.finditer(body))
    return first, anyq


def check_collisions(root, archive, base_url):
    """-> (pairs, still-missing) from COLLISION DROPPED lines, checked against the tree TODAY.

    A log line proves a file was skipped on the day it was written, not that it is absent now: a
    later run, after the NTFS case-sensitivity flag was set, may have fetched it. An identical
    claim about ardent-tool was retracted for exactly that reason.
    """
    log = os.path.join(root, "logs", "%s.log" % archive)
    if not os.path.isfile(log) or not base_url:
        return None
    pairs = set()
    for line in io.open(log, encoding="utf-8", errors="replace"):
        m = DROPPED.search(line)
        if m:
            pairs.add((m.group(1), m.group(2)))
    base = os.path.join(root, archive)
    lost = []
    for dropped, kept in sorted(pairs):
        if not dropped.startswith(base_url) or not kept.startswith(base_url):
            continue
        pd = os.path.join(base, urllib.parse.unquote(dropped[len(base_url):])
                          .replace("/", os.sep))
        pk = os.path.join(base, urllib.parse.unquote(kept[len(base_url):]).replace("/", os.sep))
        if not exists(pd) and exists(pk):
            lost.append(dropped)
    return len(pairs), lost


def base_urls():
    """-> {archive: base url} from mirror.py, or {} if it is not beside this script."""
    try:
        return dict(load_mirror().ARCHIVES)
    # MIRROR.PY IS NOT BESIDE THIS SCRIPT, AND NOTHING ELSE. It was `except Exception`,
    # which also swallows an AttributeError -- so the day mirror.py stopped carrying
    # ARCHIVES, every tool reading it here would have quietly seen an empty register and
    # reported a clean pass over nothing. "The file is absent" is a fact; "the register
    # moved" is a defect, and only the first belongs here.
    except (OSError, ImportError):
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append", default=[],
                    help="audit only this archive; repeatable")
    ap.add_argument("--links", action="store_true", help="only the link-form check")
    ap.add_argument("--images", action="store_true", help="only the <img src> check")
    ap.add_argument("--frames", action="store_true", help="only the <frame src> check")
    ap.add_argument("--collisions", action="store_true", help="only the case-collision check")
    ap.add_argument("--examples", type=int, default=3, help="missing paths to name per archive")
    args = ap.parse_args()

    all_checks = not (args.links or args.images or args.frames or args.collisions)
    bases = base_urls()
    names = args.archive or sorted(
        d for d in os.listdir(args.root)
        if os.path.isdir(os.path.join(args.root, d)) and d != "logs")

    print("  Reading stored pages only. No network. Reports what needs CHECKING, not what is "
          "lost.\n")
    print("  %-26s %8s %8s %7s %7s %7s"
          % ("archive", "href1st", "hrefAny", "blind", "img?", "frame?"))

    totals = collections.Counter()
    detail = []
    for name in names:
        base = os.path.join(args.root, name)
        if not os.path.isdir(base):
            continue
        row = {"name": name}

        if all_checks or args.links:
            first, anyq = check_link_forms(base)
            if not anyq:
                continue
            row["first"], row["any"] = first, anyq
            totals["blind"] += anyq - first
        else:
            row["first"] = row["any"] = 0

        if all_checks or args.images:
            _n, miss = check_refs(base, IMG_ANY, "img")
            row["img"] = miss
            totals["img"] += len(miss)
        else:
            row["img"] = set()

        if all_checks or args.frames:
            _n, miss = check_refs(base, FRAME_ANY, "frame")
            row["frame"] = miss
            totals["frame"] += len(miss)
        else:
            row["frame"] = set()

        if all_checks or args.collisions:
            got = check_collisions(args.root, name, bases.get(name))
            row["coll"] = got
            if got:
                totals["coll"] += len(got[1])

        interesting = (row["any"] - row["first"] or row["img"] or row["frame"]
                       or (row.get("coll") and row["coll"][1]))
        if not interesting:
            continue
        detail.append(row)
        print("  %-26s %8d %8d %7d %7d %7d"
              % (name, row["first"], row["any"], row["any"] - row["first"],
                 len(row["img"]), len(row["frame"])))

    print()
    for row in detail:
        bits = []
        if row["img"]:
            bits.append(("%d embedded images not on disk" % len(row["img"]),
                         sorted(row["img"])[:args.examples]))
        if row["frame"]:
            bits.append(("%d frame targets not on disk" % len(row["frame"]),
                         sorted(row["frame"])[:args.examples]))
        if row.get("coll") and row["coll"][1]:
            bits.append(("%d of %d COLLISION DROPPED still absent"
                         % (len(row["coll"][1]), row["coll"][0]),
                         row["coll"][1][:args.examples]))
        if not bits:
            continue
        print("  === %s" % row["name"])
        for headline, examples in bits:
            print("      %s" % headline)
            for e in examples:
                print("         %s" % str(e)[-92:])

    print()
    print("  TOTALS: %d links the old href-first rule could not see, %d embedded images absent, "
          "%d frame targets absent, %d dropped collisions still absent"
          % (totals["blind"], totals["img"], totals["frame"], totals["coll"]))
    print()
    print("  A blind link is NOT a missing file. ardent-tool carried 15 478 of them and lost")
    print("  nothing -- every target was reached another way. Re-run the archive and compare")
    print("  file counts; that is the only answer that means anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
