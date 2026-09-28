#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Which names does the collection link to and store, and which of them does nothing ever walk?

WHY THIS EXISTS. sun3arc.org writes every one of its 134 pages as `.phtml`. All 134 were fetched
and stored; not one was walked, because the crawler's extension set did not know that spelling.
878 links and 318 <img src> lay on disk unread, and the run reported COMPLETE with zero failures
-- the seeds had opened the directories, the listings covered the linked files, and NOTHING
COUNTS WHAT WAS NEVER LOOKED AT. That was the eighth defect of that shape; `.php` and
so-much-stuff.com were the ninth. This asks the collection whether there is a tenth, instead of
waiting for somebody to notice a thin archive.

THE FINDING IT LOOKS FOR is one sentence: a STORED FILE that is markup AND HOLDS LINKS IN SCOPE,
under a name no page predicate accepts. Such a file was saved as content and never opened, and
every extension in that list is a candidate for DOCUMENT_EXTENSIONS. Nothing else here is a
finding; the census above it is context for reading the list.

THE LINKS PART OF THAT SENTENCE WAS NOT IN THE FIRST VERSION, which asked only whether the bytes
were markup. Its first full run returned 71 extensions and almost no findings: looks_like_html()
accepts `<?xml`, so every EAGLE schematic (.brd, 1 522 files), every MSBuild project (.vcxproj,
.filters), every QNX package manifest (.qpm) and all 4 149 .xml files answered yes. They are
markup; they are not pages. What was lost at sun3arc was 878 LINKS, so links are what is counted,
and a file that nothing could have been walked from is not a finding however it starts.

MEASURE AT THE LEVEL THE CALLER DECIDES AT. The first version of this comparison ran over raw
hrefs and reported 50 differences that do not exist at the only place they could matter. The
crawler never sees a raw href: it sees `child`, which is urljoin(resolve_from, href), and by then
it has dropped everything off-host. `--raw` prints the other level beside this one so the gap is
visible rather than assumed. Every one of those 50 was an href ending in a NEWLINE, which urljoin
removes and endswith does not; the reasoning that had called that impossible was simply wrong,
and only measuring said so.

AND THE SCOPE TEST HERE IS NOT is_child_link(). That was this tool's second mistake, and the
library says so in its own docstring: is_child_link is the WEAKER of two guards, and with
allow_up it lets a fully-qualified URL through on purpose, because a hand-written page may spell
out its own host. Built on it, this reported `0 off-host` across 4.9 million links -- a guard
that never fires reads exactly like a tree with nothing outside it. What decides here is what
decides in mirror.py: resolve against the page's own position, then compare against the base.

READ ONLY. It opens files and reads bytes. Nothing under --root is written, renamed or removed,
and no host is contacted.

    python page-extensions.py --root Q:\mirror
    python page-extensions.py --root Q:\mirror --sample 400     # per archive, minutes not hours
    python page-extensions.py --root Q:\mirror --archive sun3arc --raw

EXIT CODE. Non-zero when at least --min stored files of one unwalked extension hold markup.
Everything found is printed either way; the floor exists because the first run of this tool went
red over a single `fetch.html.new` left behind by something else, and a tool that cries wolf once
is a tool nobody runs twice. An extension that is linked and not followed is usually just
content -- a .pdf is not a page, and saying so is not a defect.
"""

import argparse
import collections
import io
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (MIRROR_ROOT, BOOKKEEPING_FILES, file_extension, iter_archives,  # noqa: E402
                    looks_like_a_copy_of_a_page, looks_like_a_document, looks_like_a_page,
                    looks_like_html,
                    parse_listing, plural, relative_to, say, url_extension)

# A stand-in for the archive's real source URL, which the stored tree does not record. Only its
# PREFIX is ever compared, so the host name does no work -- what matters is that a page's own
# position inside the archive is reproduced underneath it, so urljoin resolves `../` and a
# fully-qualified link exactly as it did during the crawl.
#
# IT MUST BE A PATH, NOT A BARE HOST. urljoin clamps excess `..` at the HOST root, so with
# `http://a/` as the base a link of `../../../elsewhere/x.html` resolves back to
# `http://a/elsewhere/x.html` -- still under the base, and counted as in scope. A real base_url
# is a path like `http://host/pub/archive/`, where the same link lands above it and is refused.
# Found by a test, after the tool had already been corrected once for using the wrong guard.
BASE = "http://archive.invalid/root/"

# A page larger than this is not a directory listing and reading it whole costs more than it can
# return. The same ceiling corpus-coverage.py uses, for the same reason.
MAX_BYTES = 8 * 1024 * 1024

# How many stored files of one extension to open when asking whether that extension holds markup.
# A sample, not a census: the question is "does this extension EVER hold a page", and the answer
# does not get truer past a few hundred.
PROBE_PER_EXT = 300

# Enough bytes for looks_like_html to decide -- it compares against HTML_HEADS, the longest of
# which is five. Read a few more so a leading BOM or blank line cannot hide the tag.
HEAD_BYTES = 64

# A name with no dot, or a dot so far from the end that it is part of the name rather than a
# suffix. Counted as one bucket rather than dropped, because "no extension" is itself an answer:
# it is the one case neither page predicate decides.
NO_EXT = "(no extension)"

# One stray file is an accident; a hundred is a spelling. sun3arc was 134 pages, so a floor well
# under that still catches the shape this exists for, while a single `fetch.html.new` left behind
# by some other tool does not turn the whole run red. Everything found is PRINTED either way --
# the floor decides the exit code, not the report.
DEFAULT_MIN = 5


def count(n):
    """-> a plain integer, grouped. NOT human(), which formats BYTES and read `1.19 kB` for 1190
    links in this tool's first run."""
    return "{:,}".format(n).replace(",", " ")


def bucket(ext):
    """-> the extension as this report groups it: the library's answer, or NO_EXT.

    THE ONLY POLICY THIS TOOL ADDS is the length cut-off: `README.INSTRUCTIONS` and
    `x.pcsi_sfx_axpexe` are NAMES, and listing them as types would give the census a row each.
    That is a decision about a REPORT and stays here; what an extension IS belongs to the
    library, and asking it in two places is how the two answers drift.
    """
    return ext if ext and len(ext) <= 9 else NO_EXT


def name_extension(name):
    """-> how a STORED FILE NAME is bucketed. Never urlsplit -- see common.file_extension."""
    return bucket(file_extension(name))


def link_extension(url):
    """-> how a LINK is bucketed. Query and fragment are not part of what it addresses."""
    return bucket(url_extension(url))


def verdict(ext):
    """-> which page predicate accepts a name with this extension, or None if neither does."""
    name = "x" + ("" if ext == NO_EXT else ext)
    if looks_like_a_document(name):
        return "document"
    if looks_like_a_page(name):
        return "page"
    return None


def walk(root, only=None):
    """Yield (archive, archive root, full path, filename) for every stored file.

    The outer loop is common.iter_archives(): which directories ARE archives is a fact
    about the collection, not about this tool, and it was written out here and in
    corpus-coverage.py identically until 2026-09-23.
    """
    for name, archive in iter_archives(root, only):
        for dirpath, _dirnames, files in os.walk(archive):
            for f in sorted(files):
                if f in BOOKKEEPING_FILES:
                    continue
                yield name, archive, os.path.join(dirpath, f), f


def page_url_of(archive_root, path):
    """-> the URL this stored page would have had, so that urljoin resolves as it did.

    relative_to(), not os.path.relpath: relpath normalises, and normalising strips a trailing
    dot -- the same defect long_path() exists to avoid. A page whose directory ends in a dot is
    rare and real, and the difference would move every link on it.
    """
    rel = relative_to(archive_root, path)
    return BASE + urllib.parse.quote(rel if rel is not None else "")


def in_scope(page_url, href):
    """Does this href resolve to somewhere inside the archive? THE CRAWLER'S OWN TEST.

    is_child_link() is deliberately NOT that test, and its own docstring says so: it is the
    weaker of two guards, and with allow_up it lets a fully-qualified URL through ON PURPOSE,
    because a hand-written page may spell out its own host. What keeps a crawl inside a tree is
    comparing the RESOLVED url against the base, which is what mirror.py does one line after
    urljoin and what this reproduces.

    Building this tool on is_child_link(allow_up=True) instead made every off-host link in the
    collection count as in scope, and the first full run duly reported `0 off-host` for 4.9
    million links. A guard that never fires reads exactly like a tree with nothing outside it.
    """
    return urllib.parse.urljoin(page_url, href).startswith(BASE)


def census(root, only, sample, raw):
    """Read every stored page and count what its links end in, at both levels.

    -> (links, stored, examples, pages, unreadable) where `links` counts children by extension
    and `stored` counts file names by extension, keeping a few paths of each for probing later.
    """
    links = collections.Counter()        # in-scope children, by extension
    offhost = collections.Counter()      # links that are not children at all
    raw_only = collections.Counter()     # raw-href level, for --raw
    stored = collections.Counter()
    examples = collections.defaultdict(list)
    pages = unreadable = 0
    per_archive = collections.Counter()

    for archive, archive_root, path, f in walk(root, only):
        ext = name_extension(f)
        stored[ext] += 1
        if len(examples[ext]) < PROBE_PER_EXT:
            examples[ext].append((archive_root, path))

        if not looks_like_a_page(f):
            continue
        if sample and per_archive[archive] >= sample:
            continue
        try:
            if os.path.getsize(path) > MAX_BYTES:
                continue
            with io.open(path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            unreadable += 1
            continue
        pages += 1
        per_archive[archive] += 1

        # allow_up and images as the HTML_CRAWL archives use them: those are the runs where a
        # page is walked as well as saved, and so the only ones where any of this decides
        # anything. It is also what lets an off-host absolute URL through, which is why the
        # scope test below is is_child_link and not the shape of the href.
        page_url = page_url_of(archive_root, path)
        for href, _size, _mtime in parse_listing(body, allow_up=True, images=True):
            if raw:
                raw_only[link_extension(href)] += 1
            child = urllib.parse.urljoin(page_url, href)
            if child.startswith(BASE):
                links[link_extension(child)] += 1
            else:
                offhost[link_extension(child)] += 1
        if pages % 20000 == 0:
            say("  ... %s read" % plural(pages, "page"))

    return links, offhost, raw_only, stored, examples, pages, unreadable


# XML that is not a page. `looks_like_html` accepts `<?xml` because XHTML opens that way, which
# is right for it and not enough here: the collection holds `.xsl` stylesheets, EAGLE boards,
# MSBuild projects and QNX manifests that all start the same. The tool's docstring already
# records that class -- the LINKS test was supposed to settle it, and does not, because an XSL
# stylesheet really does carry hrefs, for the HTML it generates rather than for anything to walk.
#
# So the root element decides. After the declaration and any comment, an XHTML document says
# `<html`; a stylesheet says `<xsl:stylesheet`. Measured 2026-09-24:
# `ps-2.kev009.com/pccbbs/pc_servers/IBMupdate.xsl` opens
# `<?xml version='1.0'?>` then `<xsl:stylesheet ...`, and six such files were the second
# reason this tool could not be a gate.
ROOT_TAG = re.compile(rb"<\s*([A-Za-z][-A-Za-z0-9:_]*)")


def html_root(head):
    """-> False when this is XML whose root element is not <html>. True for everything else.

    Only the XML case is judged. A file that opens `<!DOCTYPE html>` or `<html` has already
    answered, and a file that is not markup at all never reaches this.
    """
    stripped = head.lstrip()[:2048]
    if not stripped.startswith(b"<?xml"):
        return True
    rest = stripped.split(b"?>", 1)[-1]
    while rest.lstrip().startswith(b"<!--"):
        end = rest.find(b"-->")
        if end < 0:
            return False
        rest = rest[end + 3:]
    m = ROOT_TAG.search(rest)
    if not m:
        return False
    return m.group(1).lower() in (b"html", b"!doctype")


def pages_with_links(paths):
    """-> (pages with links, files read, total links, copies skipped, up to 3 of the pages).

    THE LAST ONE IS NOT DECORATION. The report used to print the first three files carrying the
    extension, which are not the files that produced the finding: `.orig` showed
    `Jensen-HOWTO.orig`, a plain-text HOWTO that `looks_like_html` had already rejected, beside a
    count of 168 pages it had nothing to do with. Reading the row led straight to the wrong
    conclusion -- measured on 2026-09-24, by the person who wrote the row.

    NOT "does this begin with markup". The first version asked that, and the first full run
    answered with 71 extensions of which almost none were findings: looks_like_html() accepts
    `<?xml`, so every EAGLE schematic (.brd, .sch), every MSBuild project (.vcxproj, .filters)
    and every QNX package manifest (.qpm) counted as markup. They are markup. They are not pages.

    What was actually lost at sun3arc was 878 LINKS nobody followed, so that is what is counted.
    A file only matters here if walking it would have produced something to walk.
    """
    pages = read = links = copies = 0
    counted, copied = [], []
    for archive_root, p in paths:
        # A COPY OF A PAGE IS NOT AN UNWALKED PAGE. `fetch.html.new` holds exactly the links
        # `fetch.html` holds, and that one IS walked, so nothing was missed -- but these drowned
        # the real rows and kept this tool out of the gates. Counted separately rather than
        # dropped, because "23 of the 24 are backups" is the sentence that makes the 24th
        # readable, and a silenced row is one nobody can ever challenge.
        if looks_like_a_copy_of_a_page(os.path.basename(p)):
            copies += 1
            if len(copied) < 3:
                copied.append(p)
            continue
        try:
            if os.path.getsize(p) > MAX_BYTES:
                continue
            with io.open(p, "rb") as fh:
                head = fh.read(HEAD_BYTES)
            if not looks_like_html(head.lstrip()[:8]) or not html_root(head):
                read += 1
                continue
            with io.open(p, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            continue
        read += 1
        page_url = page_url_of(archive_root, p)
        found = [h for h, _s, _m in parse_listing(body, allow_up=True, images=True)
                 if in_scope(page_url, h)]
        if found:
            pages += 1
            links += len(found)
            if len(counted) < 3:
                counted.append(p)
    # THE EVIDENCE FOR EACH GROUP, SEPARATELY. A row with no hits and some copies used to print
    # the first three files carrying the extension, which are the ones that were READ and found
    # not to be pages -- so `.perl` appeared under "copies of pages" showing `wall.perl`,
    # `uureroute.perl` and `myformat.perl`, none of which is a copy of anything. The one copy was
    # `perl.html.perl`. Same mistake as the one fixed a layer up, one layer down.
    return pages, read, links, copies, (counted or copied)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=MIRROR_ROOT,
                    metavar="PATH", help="the mirror root (read only)")
    ap.add_argument("--archive", metavar="NAME", help="one archive instead of all of them")
    ap.add_argument("--sample", type=int, default=0, metavar="N",
                    help="read at most N pages per archive. 0, the default, reads every one. "
                         "Stored NAMES are still counted in full -- only link reading is capped")
    ap.add_argument("--show", type=int, default=25, metavar="N",
                    help="how many extensions to list per section (default 25)")
    ap.add_argument("--min", type=int, default=DEFAULT_MIN, metavar="N",
                    help="how many markup files under one unwalked extension count as a finding "
                         "rather than an accident (default %d). Everything is printed either "
                         "way; this decides the exit code only" % DEFAULT_MIN)
    ap.add_argument("--raw", action="store_true",
                    help="also count links at the RAW HREF level, beside the child level. The "
                         "two differ, the child level is the one the crawler decides at, and "
                         "measuring the wrong one is how this tool's first version went wrong")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        return "no such directory: %s" % args.root

    links, offhost, raw_only, stored, examples, pages, unreadable = census(
        args.root, args.archive, args.sample, args.raw)
    if not pages:
        return "no pages under %s -- wrong root, or --archive names one that is not there" % (
            args.root,)

    say("")
    say("%s read, %s links in scope, %s off-host, %s stored files"
        % (plural(pages, "page"), count(sum(links.values())),
           count(sum(offhost.values())), count(sum(stored.values()))))
    if unreadable:
        say("%s could not be opened" % plural(unreadable, "file"))

    say("")
    say("LINKS IN SCOPE, by what they end in")
    say("  %-16s %12s  %-9s %12s" % ("extension", "children", "walked as", "stored files"))
    for ext, n in links.most_common(args.show):
        say("  %-16s %12s  %-9s %12s"
            % (ext, count(n), verdict(ext) or "-", count(stored.get(ext, 0))))

    if args.raw:
        say("")
        say("THE SAME LINKS AT THE RAW HREF LEVEL -- not what the crawler sees")
        differing = [(e, raw_only[e] - links.get(e, 0) - offhost.get(e, 0))
                     for e in sorted(set(raw_only) | set(links))]
        differing = [(e, d) for e, d in differing if d]
        if not differing:
            say("  the two levels agree on every extension")
        for ext, d in sorted(differing, key=lambda x: -abs(x[1]))[:args.show]:
            say("  %-16s %+d at href level" % (ext, d))

    # ------------------------------------------------------------------ the finding
    # Only extensions nothing walks are worth opening: for the rest the answer is already known
    # and reading the bytes would say nothing new.
    suspects = sorted((e for e in stored if verdict(e) is None and e != NO_EXT),
                      key=lambda e: -stored[e])
    findings = []
    for ext in suspects:
        hits, read, links, copies, shown = pages_with_links(examples[ext])
        if hits or copies:
            findings.append((ext, hits, read, stored[ext], links, copies, shown or
                             [q for _r, q in examples[ext][:3]]))

    say("")
    if not findings:
        say("NO UNWALKED PAGES.")
        say("Every stored file that is a page with links inside carries a name one of the two "
            "predicates accepts, so nothing was saved and then left unread.")
        return 0

    # THE EXIT CODE RESTS ON hits ONLY, and hits no longer counts copies of pages. An extension
    # that turns out to be nothing but backups now has hits == 0 and cannot make this tool refuse
    # a gate -- which is the whole of D1. It is still PRINTED, in its own section.
    strong = [f for f in findings if f[1] >= args.min]
    stray = [f for f in findings if 0 < f[1] < args.min]
    backups = [f for f in findings if f[1] == 0]

    say("PAGES WITH LINKS, UNDER NAMES NOTHING WALKS -- %s"
        % plural(len(findings), "extension"))
    say("Each of these files is markup AND holds links in scope, and no page predicate accepts")
    say("its name. They were saved and never opened. That is how sun3arc's 134 .phtml pages hid,")
    say("and the `links` column is what a run would have had to follow and did not.")
    say("")
    say("READING IT: a copy of a page is not an unwalked page, and copies are no longer counted")
    say("here. `fetch.html.new` holds exactly the links `fetch.html` holds and that one IS")
    say("walked, so nothing was missed; the same goes for `x.html~`, `x.html.~1~` and a listing")
    say("saved under its own sort order, `index.html@S=A`. They are separated by SHAPE rather")
    say("than by a list of extensions -- take the suffix off and a page name is left -- and they")
    say("are listed at the foot rather than dropped. What is left above is a SPELLING OF MARKUP")
    say("nothing walks. Check whether its link targets are on disk: that, not this table, is the")
    say("proof that something is gone.")
    say("")
    say("  %-16s %18s %12s %12s" % ("extension", "pages / sampled", "links", "stored"))
    for label, group in (("", strong),
                        ("below --min %d, reported only:" % args.min, stray),
                        ("copies of pages -- nothing was missed, listed so it can be checked:",
                         backups)):
        if label and group:
            say("")
            say("  %s" % label)
        for ext, hits, read, total, links, _c, shown in sorted(group,
                                                               key=lambda x: -x[4])[:args.show]:
            say("  %-16s %18s %12s %12s"
                % (ext, "%d / %d" % (hits, read), count(links), count(total)))
            for p in shown[:3]:
                say("      %s" % p)
    return 1 if strong else 0


if __name__ == "__main__":
    sys.exit(main())
