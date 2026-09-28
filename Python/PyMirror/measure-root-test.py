#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""A root may be a PAGE, and measure-remote.py could not measure one.

WHERE THIS CAME FROM. On 2026-09-26 two candidate sites turned out to be enterable only through
an HTML page: `sgidepot.co.uk/` is a 71-byte meta-refresh stub whose whole content hangs off
`sgi.html`, and `spider.seds.org`'s PS/2 and OS/2 material hangs off `ps2.html` and `os2.html`.
Both measured as ZERO, twice over, for two independent reasons:

  * `main()` appended a slash to every root unconditionally, so `sgi.html` was requested as
    `sgi.html/` -- HTTP 404, `LISTFAIL`, 0 files.
  * and even without that, `rows()` keeps a child only `if full.startswith(base)`. With the page
    itself as the base, no child can start with it, so a page-rooted tree measures as nothing
    whatever the request returns.

THE SECOND ONE IS THE DANGEROUS HALF. The slash bug announced itself: `LISTFAIL ... HTTP 404`
next to `0 files` is visibly not a measurement. The scope bug would have printed `0 files` with
no error at all -- the same line a genuinely empty directory prints. This collection has a name
for that shape: a checker that reads nothing and a checker that finds nothing print the same line.

WHAT THE FIX SEPARATES. Where to BEGIN and what counts as INSIDE are two different questions.
Begin at the page; count everything under the directory that holds it.
"""
import importlib.util
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("measure-remote")


class APageRootBeginsAtThePageAndCountsItsDirectory(unittest.TestCase):

    def test_the_two_sites_that_produced_the_bug(self):
        self.assertEqual(TOOL.start_and_base("http://www.sgidepot.co.uk/sgi.html"),
                         ("http://www.sgidepot.co.uk/sgi.html",
                          "http://www.sgidepot.co.uk/"))
        self.assertEqual(TOOL.start_and_base("https://spider.seds.org/ps2/ps2.html"),
                         ("https://spider.seds.org/ps2/ps2.html",
                          "https://spider.seds.org/ps2/"))

    def test_NO_SLASH_IS_APPENDED_TO_A_PAGE(self):
        """`sgi.html/` answered 404. That was the visible half of the failure."""
        start, _base = TOOL.start_and_base("http://www.sgidepot.co.uk/sgi.html")
        self.assertFalse(start.endswith("/"), start)

    def test_THE_SCOPE_IS_THE_DIRECTORY_AND_NOT_THE_PAGE(self):
        """The invisible half: with the page as base, no sibling can ever be inside it."""
        _start, base = TOOL.start_and_base("http://www.sgidepot.co.uk/sgi.html")
        self.assertTrue("http://www.sgidepot.co.uk/octane.html".startswith(base))


class MainActuallyCallsIt(unittest.TestCase):
    r"""THE UNIT TEST ABOVE PASSED WHILE THE WIRING WAS MISSING, and that is why this exists.

    `start_and_base()` was written, tested in isolation, and green. `main()` went on appending a
    slash unconditionally, because the edit that was supposed to replace those three lines failed
    silently and nothing asserted that it had. The next measurement run requested `sgi.html/`
    again and returned 0 files -- the same wasted run as before the fix.

    A function nobody calls is not a fix. This test replaces `measure` with a recorder and runs
    the real `main()`, so the question it asks is "what did the program do", not "what would this
    function return if something called it".
    """

    def run_main(self, *urls):
        seen = []

        def recorder(start, args, log, pacer, base=None):
            seen.append((start, base))
            return {"url": base, "files": 0, "listed": 0, "measured": 0,
                    "unknown": 0, "pages": 0, "capped_pages": 0, "capped_heads": 0,
                    "looped": 0, "seconds": 0.0}

        real_measure, real_argv = TOOL.measure, sys.argv
        out, keep = io.StringIO(), sys.stdout
        TOOL.measure, sys.argv = recorder, ["measure-remote.py"] + list(urls)
        sys.stdout = out
        try:
            TOOL.main()
        finally:
            TOOL.measure, sys.argv, sys.stdout = real_measure, real_argv, keep
        return seen

    def test_a_page_root_reaches_measure_as_page_plus_directory(self):
        self.assertEqual(self.run_main("http://www.sgidepot.co.uk/sgi.html"),
                         [("http://www.sgidepot.co.uk/sgi.html",
                           "http://www.sgidepot.co.uk/")])

    def test_NO_SLASH_IS_APPENDED_ON_THE_WAY_THROUGH_MAIN(self):
        """The exact regression: `sgi.html/` answered 404 twice, on two separate runs."""
        (start, _base), = self.run_main("http://www.sgidepot.co.uk/sgi.html")
        self.assertFalse(start.endswith(".html/"), start)

    def test_a_directory_root_still_arrives_with_its_slash(self):
        self.assertEqual(self.run_main("http://iommu.com/datasheets"),
                         [("http://iommu.com/datasheets/", "http://iommu.com/datasheets/")])

    def test_several_roots_are_each_resolved(self):
        got = self.run_main("http://www.sgidepot.co.uk/sgi.html", "http://iommu.com/datasheets/")
        self.assertEqual(len(got), 2)
        self.assertNotEqual(got[0][0], got[0][1])   # the page root differs from its directory
        self.assertEqual(got[1][0], got[1][1])      # the directory root does not


class ADirectoryRootIsUnchanged(unittest.TestCase):
    """The common case must not move, or the fix costs more than the bug."""

    def test_a_trailing_slash_is_kept_and_used_for_both(self):
        self.assertEqual(TOOL.start_and_base("http://iommu.com/datasheets/"),
                         ("http://iommu.com/datasheets/", "http://iommu.com/datasheets/"))

    def test_a_missing_trailing_slash_is_still_added(self):
        self.assertEqual(TOOL.start_and_base("http://iommu.com/datasheets"),
                         ("http://iommu.com/datasheets/", "http://iommu.com/datasheets/"))

    def test_a_bare_host_is_a_directory(self):
        start, base = TOOL.start_and_base("https://datasheets.chipdb.org")
        self.assertEqual(start, base)
        self.assertTrue(base.endswith("/"))


class EveryLinkOnALineIsSeen(unittest.TestCase):
    r"""The parser read only the FIRST link of each line, and said nothing about the rest.

    Group 4 of the pattern carries mod_autoindex's size column, and while it read `(.*)$` it
    swallowed every further anchor on the same line. One row per line is exactly what an
    autoindex writes, so the limitation was invisible there -- and wrong for every hand-written
    page, which is the shape of site this collection keeps finding.

    MEASURED, not supposed: across the 141 HTML pages of the fetched mcamafia mirror, 54 lines
    carry more than one `<a href>` and hide 61 links. It is the partial form of the failure the
    file's own header already describes -- a total that is quietly short rather than quietly
    zero -- and it is part of why mcamafia measured 1 467 files and fetched 1 770.
    """

    BASE = "http://h/"

    def test_three_links_on_one_line(self):
        page = '<a href="a.html">A</a> <a href="b.html">B</a> <a href="c.html">C</a>'
        got = [u for u, _size in TOOL.rows(page, self.BASE, self.BASE)]
        self.assertEqual(got, ["http://h/a.html", "http://h/b.html", "http://h/c.html"])

    def test_AN_AUTOINDEX_ROW_STILL_YIELDS_ITS_SIZE(self):
        """The reason the old pattern reached to end of line. It must not be lost.

        The size column sits AFTER the anchor, so the tail has to stay greedy enough to reach it
        while stopping before the next anchor.
        """
        row = '<a href="file.tar.gz">file.tar.gz</a>   2026-01-01 12:00  1.2M'
        self.assertEqual(TOOL.rows(row, self.BASE, self.BASE),
                         [("http://h/file.tar.gz", 1258291)])

    def test_TWO_ROWS_ON_ONE_LINE_YIELD_NO_SIZE_AT_ALL(self):
        """And that is the safe answer, not a shortcoming.

        This test demanded the opposite at first -- 100 for the first link, 200 for the second --
        and the demand was wrong. mod_autoindex writes ONE ROW PER LINE, so a line carrying two
        rows and two size columns is a shape no real listing produces; guessing which number
        belongs to which link would be inventing data. `common.parse_listing` declines, both
        links come back with no size, and the caller falls back to a HEAD request per file.
        Slower and true beats fast and misattributed.
        """
        line = '<a href="a.bin">a</a> 100 <a href="b.bin">b</a> 200'
        got = dict(TOOL.rows(line, self.BASE, self.BASE))
        self.assertEqual(sorted(got), ["http://h/a.bin", "http://h/b.bin"])
        self.assertIsNone(got["http://h/a.bin"])
        self.assertIsNone(got["http://h/b.bin"])

    def test_AN_UPWARD_CROSS_LINK_IS_KEPT(self):
        """`../elsewhere/page.htm` is navigation on a listing and content on a written page.

        The library drops `..` by default, which is right for a directory index. Passing
        allow_up=True is the whole difference between the two callers -- and the first comparison
        run, made without it, lost 722 links across four mirrors.
        """
        line = '<a href="../mcapage0/mcaindex.htm">MCA Enthusiasts Page</a>'
        got = [u for u, _s in TOOL.rows(line, "http://h/blackbird/blackbird.htm", self.BASE)]
        self.assertEqual(got, ["http://h/mcapage0/mcaindex.htm"])

    def test_the_bare_parent_link_is_still_dropped(self):
        self.assertEqual(TOOL.rows('<a href="../">up</a>', "http://h/sub/x.html", self.BASE), [])

    def test_a_directory_row_still_reports_no_size(self):
        row = '<a href="sub/">sub/</a>   2026-01-01 12:00  -'
        self.assertEqual(TOOL.rows(row, self.BASE, self.BASE), [("http://h/sub/", None)])


class TheScopeTestItself(unittest.TestCase):
    """`rows()` is where the base is applied, so the fix is worth checking there too."""

    # One anchor per line, because this class is about the SCOPE. Several on one line is a
    # different question and has its own class above.
    PAGE = "\n".join(('<a href="octane.html">Octane</a>',
                      '<a href="indigo/indigo.html">Indigo</a>',
                      '<a href="http://elsewhere.example/x.pdf">off-site</a>'))

    def test_children_under_the_directory_are_kept_and_off_site_is_not(self):
        start, base = TOOL.start_and_base("http://www.sgidepot.co.uk/sgi.html")
        got = [u for u, _size in TOOL.rows(self.PAGE, start, base)]
        self.assertIn("http://www.sgidepot.co.uk/octane.html", got)
        self.assertIn("http://www.sgidepot.co.uk/indigo/indigo.html", got)
        self.assertNotIn("http://elsewhere.example/x.pdf", got)

    def test_WITH_THE_PAGE_AS_BASE_EVERYTHING_IS_DROPPED(self):
        """The bug, reproduced: this is what the tool did before the fix."""
        page = "http://www.sgidepot.co.uk/sgi.html"
        self.assertEqual(TOOL.rows(self.PAGE, page, page), [])



class WhatTheCallerForbids(unittest.TestCase):
    """`--exclude`, and why this tool does not read robots.txt itself.

    openpa.net is the case it was written for. Its robots.txt carries `User-Agent: ClaudeBot /
    Disallow: /` AND a `User-agent: *` group disallowing `/images/` and `/systems/images/`. The
    recorded position -- the owner's, and correct -- is that this collection is `mirror/1.0`
    fetching for preservation and not Anthropic's training crawler, so the named rule does not
    reach us and the WILDCARD one does. A tool that applied robots.txt automatically would get
    that backwards in one direction or the other; the judgement is written down per host, and
    this honours what is passed.
    """

    BASE = "https://www.openpa.net/"

    def test_a_forbidden_branch_is_named_back(self):
        self.assertEqual(TOOL.refused(self.BASE + "images/foo.png", self.BASE,
                                      ["images/", "systems/images/"]), "images/")

    def test_and_the_deeper_one_too(self):
        self.assertEqual(TOOL.refused(self.BASE + "systems/images/x.jpg", self.BASE,
                                      ["images/", "systems/images/"]), "systems/images/")

    def test_AN_ARTICLE_IS_NOT_FORBIDDEN(self):
        """The whole point: openpa's articles may be taken and its scans may not."""
        self.assertIsNone(TOOL.refused(self.BASE + "systems/hp9000_785.html", self.BASE,
                                       ["images/", "systems/images/"]))

    def test_no_prefixes_forbids_nothing(self):
        self.assertIsNone(TOOL.refused(self.BASE + "images/x.png", self.BASE, []))

    def test_THE_PREFIX_IS_RELATIVE_TO_THE_ROOT_NOT_TO_THE_HOST(self):
        """Same convention as mirror.EXCLUDE, so a rule written for one can be passed to the
        other unchanged. The iommu entry cost 16 GB by getting exactly this wrong: patterns match
        the path relative to the base, and `mirrors/` named a directory that did not exist there.
        """
        base = "https://host.invalid/deep/root/"
        self.assertIsNone(TOOL.refused(base + "images/x", base, ["deep/root/images/"]))
        self.assertEqual(TOOL.refused(base + "images/x", base, ["images/"]), "images/")

    def test_a_url_outside_the_root_is_left_to_the_crawls_own_scope_rule(self):
        # Answering it here as well would put one decision in two places.
        self.assertIsNone(TOOL.refused("https://elsewhere.invalid/images/x", self.BASE,
                                       ["images/"]))

    def test_a_prefix_matches_only_at_the_start(self):
        self.assertIsNone(TOOL.refused(self.BASE + "systems/hp-images/x", self.BASE, ["images/"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
