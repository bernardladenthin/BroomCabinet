#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Which of these archives' sources publish a sitemap, and does the mirror hold what it lists?

    python find-sitemaps.py                       every HTTP archive, two requests each
    python find-sitemaps.py --archive openpa      one of them
    python find-sitemaps.py --save                store each sitemap found in its archive

WHY A SITEMAP IS WORTH TWO REQUESTS WHEN A MEASUREMENT IS NOT. measure-remote.py crawls: it
follows links, so its file count is what a link-following fetch would reach. That makes it an
excellent instrument for "how big is this" and a useless one for "is this all of it" -- it
rediscovers our own method's reach and charges one HEAD per file for the privilege. A sitemap is
the OPERATOR'S statement of what the site consists of. It is evidence from the other side.

MEASURED 2026-10-02 ON openpa.net, the case that produced this tool. Five days of crawling,
harvesting and url-list fetching had built 679 files with no way to say whether that was all of
them, and the next step on the table was a measurement run of several hundred requests against a
host that had already cut us off three times. Instead: robots.txt (no Sitemap: line at all), then
one guess at /sitemap.xml -- HTTP 200, 171 entries, 168 internal paths, and the mirror held 168 of
168. The page side of that archive was settled by its own publisher, for two requests.

NEITHER DISCOVERY ROUTE IS SUFFICIENT ALONE, which is why both are tried. robots.txt is where the
standard says to declare a sitemap, and openpa.net declares none while serving one; guessing
/sitemap.xml finds that, and misses every site that puts it elsewhere and says so in robots.txt.
Two requests, in that order, and no third guess -- a tool that tries eight filenames per host is
spending somebody else's bandwidth on our convenience.

WHAT IT WILL NOT DO. It does not fetch anything a sitemap names: it reports. A sitemap naming
files the mirror lacks is a FINDING, to be looked at and then acted on deliberately -- this
collection has an entry for what happens when a list of names is mistaken for a list of missing
files (158 urls, 156 of them answered 404). It also honours DO_NOT_FETCH and robots.txt: a host
this collection has decided not to touch is not touched for this either.
"""
import argparse
import io
import os
import re
import sys
import urllib.parse

from common import (MIRROR_ROOT, BOOKKEEPING_FILES, Pacer, exists, host_of, http_try,
                    load_mirror, long_path, under_site)
from robots import robots_verdict, sitemaps

LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
# A SITEMAP SAYS SO IN ITS ROOT ELEMENT, and asking for that is the whole defence against the
# thing that happened on the first survey: www.vintagecomputer.net answers /sitemap.xml with
# HTTP 200 and an HTML page -- a background image, a stylesheet and a <LINK REL="SHORTCUT ICON">.
# Four archives were reported as "publishes a readable sitemap" on the strength of a status code.
# A soft 404 is the oldest trap in this collection; status 200 is not evidence of anything.
IS_SITEMAP = re.compile(r"<(?:urlset|sitemapindex)", re.I)
# A sitemap index points at further sitemaps rather than at pages. Reported, not followed: each
# one is another request, and the decision to spend it belongs to a person.
IS_INDEX = re.compile(r"<sitemapindex", re.I)


def held_paths(archive_dir):
    """-> the relative paths this archive holds, bookkeeping excluded."""
    out = set()
    for dirpath, _dirs, names in os.walk(archive_dir):
        for name in names:
            if name in BOOKKEEPING_FILES or name.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), archive_dir)
            out.add(rel.replace(os.sep, "/"))
    return out


# `bases` LIVED HERE AND IS NOW common.site_prefixes. It was written for this tool on 2026-10-02
# and pages-to-urllist.py needed the identical thing hours later, for the identical reason: a
# plain prefix test reads one spelling of a site as a foreign host and the archive then looks
# complete because nothing overlapped. Two private copies of that rule would drift.


def internal(locs, base, archive_dir=None):
    """-> (paths under this archive's base, how many fell outside, how many are page urls).

    A sitemap is written for the whole SITE; an archive may be rooted at a subdirectory of it.
    Entries outside the base are counted rather than dropped -- their number says whether the
    base is narrower than the site, which is worth knowing when reading the rest of the line.

    AND AN ENTRY WITH NO FILE EXTENSION IS NOT COMPARABLE TO A STORED PATH. redbooks.ibm.com lists
    https://www.redbooks.ibm.com/feature/defender -- a page its server renders, with no file behind
    it. The first survey compared 3025 such entries against the mirror's stored file names and
    reported MISSING 3025, which reads as a catastrophe and is a category error. They are counted
    on their own and left out of the comparison.
    """
    inside, outside, pageish, dirish = set(), 0, 0, []
    for loc in locs:
        cut = under_site(loc, base)
        if cut is None:
            outside += 1
            continue
        rel = urllib.parse.unquote(cut).split("#")[0].split("?")[0]
        if not rel or rel.endswith("/"):
            continue
        if "." not in rel.rsplit("/", 1)[-1]:
            pageish += 1
            continue
        # A DOT IN THE NAME IS NOT A FILE EXTENSION, and this collection is full of the
        # counter-examples. novasareforever.org lists documentation/dg.aviion,
        # documentation/third.party.hardware and four more; every one is a DIRECTORY that this
        # mirror holds in full, and the first version of this tool reported all six as missing
        # files. The tree is the only thing that can settle it -- the same test
        # pages-to-urllist.py already makes, for the same reason.
        if archive_dir:
            local = os.path.join(archive_dir, *[q for q in rel.split("/") if q])
            if os.path.isdir(local):
                dirish.append(rel)
                continue
        inside.add(rel)
    return inside, outside, pageish, dirish


def fetch(url, limit=4 * 1024 * 1024):
    """-> (status, text). Never raises; http_try's status is a string when nothing answered."""
    status, body = http_try(url, timeout=45, limit=limit)[:2]
    return status, body.decode("utf-8", "replace") if body else ""


def look(name, base, archive_dir, mirror, save=False, pacer=None):
    """Two requests at most for one archive. -> a one-line verdict string."""
    host = host_of(base)
    if mirror and mirror.blocked_host(base):
        return "%-24s SKIPPED -- the host is in DO_NOT_FETCH" % name

    root = "%s://%s/" % (urllib.parse.urlsplit(base).scheme, host)
    # SEVERAL ARCHIVES SHARE ONE HOST -- crashing-org-www and crashing-org-kernel, the four
    # infania-* , the zx-* group. Walking the register in order therefore puts two requests each
    # for two or three archives at the same machine within a second of each other, which is the
    # shape that has cost this collection two hosts. The pacer is keyed by host, so unrelated
    # hosts never wait for one another.
    if pacer:
        pacer.wait(host)
    status, robots_text = fetch(root + "robots.txt", limit=256 * 1024)
    declared = sitemaps(robots_text) if isinstance(status, int) and status == 200 else []

    tried = declared or [root + "sitemap.xml"]
    how = "declared in robots.txt" if declared else "guessed at /sitemap.xml"

    # One candidate only. A tool that walks a list of likely names spends somebody else's
    # bandwidth on our convenience, and the second guess has never been the one that paid.
    url = tried[0]

    # WHAT DECIDES WHETHER TO ASK, AND WHAT DOES NOT. The first version of this called
    # robots_verdict() here and refused on BLOCKED -- and the first host it ran against was
    # refused for the wrong reason: openpa.net names ClaudeBot with Disallow: /, which the owner
    # recorded on 2026-09-26 as NOT binding this collection, since it is mirror/1.0 fetching for
    # preservation. The tool was re-deciding a question the register had already settled, and
    # settling it the other way.
    #
    # THE REGISTER IS WHERE ROBOTS DECISIONS LIVE, not in each tool: DO_NOT_FETCH for a host that
    # may not be touched at all, EXCLUDE for paths within one that may not. Both were written by
    # a person reading the file; a tool that consults robots.txt afresh gets a second opinion and
    # has no way to know it is the worse one. So the verdict is REPORTED beside the result and
    # acted on by nobody here.
    rel_for_exclude = urllib.parse.urlsplit(url).path.lstrip("/")
    patterns = tuple(mirror.EXCLUDE.get(name, ())) if mirror else ()
    if patterns and mirror.is_excluded(rel_for_exclude, patterns, name):
        return "%-24s SKIPPED -- EXCLUDE[%r] covers the sitemap path" % (name, name)
    note = ""
    if robots_text:
        verdict, why = robots_verdict(robots_text, urllib.parse.urlsplit(url).path)
        if verdict != "OPEN":
            note = "  [robots: %s -- %s]" % (verdict, why)
    if pacer:
        pacer.wait(host)
    status, text = fetch(url)
    if not isinstance(status, int):
        return "%-24s no answer (%s)" % (name, status)
    if status != 200:
        return "%-24s none (HTTP %s, %s)" % (name, status, how)
    if not IS_SITEMAP.search(text):
        head = " ".join(text[:60].split())
        return ("%-24s NOT A SITEMAP -- HTTP 200 but no <urlset>/<sitemapindex>: %r (%s)"
                % (name, head, how))
    if IS_INDEX.search(text):
        n = len(LOC.findall(text))
        return "%-24s SITEMAP INDEX, %d further sitemaps -- not followed (%s)" % (name, n, how)

    locs = LOC.findall(text)
    inside, outside, pageish, dirish = internal(locs, base.rstrip("/") + "/", archive_dir)
    missing = sorted(inside - held_paths(archive_dir)) if os.path.isdir(archive_dir) else []
    saved = ""
    if save and os.path.isdir(archive_dir):
        dest = os.path.join(archive_dir, "sitemap.xml")
        if not exists(dest):
            with io.open(long_path(dest), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            saved = "  [saved]"
        else:
            saved = "  [already held]"
    return ("%-24s %4d entries, %4d files under the base, %4d page urls, %4d dirs, %4d outside, "
            "MISSING %d%s  (%s)%s%s"
            % (name, len(locs), len(inside), pageish, len(dirish), outside, len(missing), saved,
               how, note,
               "" if not missing else "\n" + "\n".join("        %s" % m for m in missing[:10])
               + ("\n        ... and %d more" % (len(missing) - 10) if len(missing) > 10 else "")))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append",
                    help="only this archive; repeatable. Default: every HTTP archive")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between two requests to the SAME host (default 2). Unrelated "
                         "hosts do not wait for each other")
    ap.add_argument("--save", action="store_true",
                    help="store each sitemap found as sitemap.xml inside its archive. It is "
                         "content the source serves, so it belongs with the rest of it -- and a "
                         "stored copy is what a later run compares against without asking again")
    args = ap.parse_args()

    mirror = load_mirror(here)
    todo = [(n, u) for n, u in mirror.ARCHIVES if u.startswith("http")]
    if args.archive:
        wanted = set(args.archive)
        todo = [(n, u) for n, u in todo if n in wanted]
    if not todo:
        sys.exit("no HTTP archive matched")

    print("  %d archive(s), at most two requests each. A sitemap names what the OPERATOR says is\n"
          "  there, which is the one kind of evidence a crawl cannot produce.\n" % len(todo))
    found = 0
    pacer = Pacer(args.delay)
    for name, base in todo:
        line = look(name, base, os.path.join(args.root, name), mirror, save=args.save,
                    pacer=pacer)
        print("  " + line, flush=True)
        if "entries," in line:
            found += 1
    print("\n  %d of %d publish a readable sitemap." % (found, len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
