#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""page-extensions.py's own logic, on temporary trees. The mirror is never touched.

WHAT IS WORTH TESTING HERE is not the walk -- that is os.walk -- but extension_of(), which is the
kind of small function that is silently wrong for years. It has to survive a query string, a
fragment, a directory URL, a name that is all dots, a version number that looks like a suffix,
and a dot in a DIRECTORY component rather than in the file name. Each of those is a real spelling
in this collection.
"""

import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

pe = common.load_peer("page-extensions.py", "_page_extensions")


class TestExtensionOf(unittest.TestCase):

    def test_the_ordinary_ones(self):
        for name, want in (("a.html", ".html"), ("A.HTML", ".html"),
                           ("dir/b.htm", ".htm"), ("x.tar.gz", ".gz")):
            self.assertEqual(pe.name_extension(name), want, name)

    def test_A_QUERY_AND_A_FRAGMENT_ARE_NOT_PART_OF_THE_NAME(self):
        # urlsplit does this; doing it by hand is how ".html?v=2" becomes an extension of its own.
        self.assertEqual(pe.link_extension("a.html?v=2"), ".html")
        self.assertEqual(pe.link_extension("a.html#top"), ".html")
        self.assertEqual(pe.link_extension("http://h/p/a.php?x=1#f"), ".php")

    def test_A_LINK_ENDING_IN_A_SLASH_HAS_NO_EXTENSION(self):
        """Even when the directory is named `icons.gif` -- and one in this collection is.

        CHANGED DELIBERATELY. The first version stripped the slash and answered `.gif`, on the
        argument that the directory's own name decides. It is the wrong answer for this census:
        the link addresses a DIRECTORY, mirror.py branches on href.endswith("/") long before any
        extension is looked at, and a row counting `icons.gif/` among the images describes a
        tree that does not exist.
        """
        self.assertEqual(pe.link_extension("http://h/docs/"), pe.NO_EXT)
        self.assertEqual(pe.link_extension("http://h/icons.gif/"), pe.NO_EXT)
        self.assertEqual(pe.link_extension("http://h/page.html/"), pe.NO_EXT)

    def test_A_DOT_IN_A_PARENT_DIRECTORY_IS_NOT_THE_FILES_EXTENSION(self):
        # The one that catches a naive rfind over the whole path.
        self.assertEqual(pe.link_extension("http://h/v1.2/README"), pe.NO_EXT)
        self.assertEqual(pe.name_extension("some.dir/plainfile"), pe.NO_EXT)

    def test_a_dotfile_is_not_an_extension(self):
        # `.gitignore` is a NAME beginning with a dot, not a file of type "gitignore" -- the same
        # distinction that made lstrip(".") the wrong tool elsewhere in this collection.
        self.assertEqual(pe.name_extension(".gitignore"), pe.NO_EXT)
        self.assertEqual(pe.name_extension("dir/.htaccess"), pe.NO_EXT)

    def test_a_long_tail_is_not_a_suffix(self):
        # "README.SOMETHINGLONG" is a name, not a type. The cut-off is deliberate and pinned so
        # that moving it is a decision rather than a slip.
        self.assertEqual(pe.name_extension("README.INSTRUCTIONS"), pe.NO_EXT)
        self.assertEqual(pe.name_extension("a.vim58"), ".vim58")

    def test_no_name_at_all(self):
        for name in ("", "/"):
            self.assertEqual(pe.name_extension(name), pe.NO_EXT, repr(name))
        self.assertEqual(pe.link_extension("http://h/"), pe.NO_EXT)

    def test_A_NAME_ENDING_IN_A_DOT_HAS_NO_EXTENSION(self):
        """Found by this test: the first version answered "." for all three.

        `TALK.` and friends are real names in this collection -- they are why long_path() exists
        at all, because Windows strips a trailing dot while OPENING the file. An extension of "."
        would have become its own row in every report, and a row that means nothing is worse than
        a missing one: somebody eventually explains it.
        """
        for name in ("...", "a.", "TALK."):
            self.assertEqual(pe.name_extension(name), pe.NO_EXT, repr(name))
        self.assertEqual(pe.link_extension("http://h/p/x."), pe.NO_EXT)


class TestVerdict(unittest.TestCase):
    """Which predicate accepts a name with this extension -- the tool's whole classification."""

    def test_the_narrow_one_wins_when_both_would_accept(self):
        self.assertEqual(pe.verdict(".html"), "document")
        self.assertEqual(pe.verdict(".php"), "document")

    def test_the_wide_one_is_reported_separately(self):
        for ext in common.PROGRAM_PAGE_EXTENSIONS:
            self.assertEqual(pe.verdict(ext), "page", ext)

    def test_and_content_is_walked_by_neither(self):
        for ext in (".pdf", ".gz", ".gif", ".iso", ".readme"):
            self.assertIsNone(pe.verdict(ext), ext)

    def test_NO_EXT_is_decided_by_neither(self):
        # Not an oversight: only the caller knows whether its tree holds directories, scripts or
        # files somebody forgot to name.
        self.assertIsNone(pe.verdict(pe.NO_EXT))

    def test_it_agrees_with_the_library_rather_than_repeating_it(self):
        for ext in common.DOCUMENT_EXTENSIONS:
            self.assertEqual(pe.verdict(ext), "document", ext)
        for ext in common.PAGE_EXTENSIONS:
            self.assertIsNotNone(pe.verdict(ext), ext)


class TestHtmlRoot(unittest.TestCase):
    """XML that is not a page, which is the second reason this tool could not be a gate.

    `looks_like_html` accepts `<?xml` because XHTML opens that way -- right for it, and not
    enough here. The collection holds `.xsl` stylesheets, EAGLE boards, MSBuild projects and QNX
    manifests that all start the same, and the tool's own docstring already records that class.
    The LINKS test was supposed to settle it and does not: an XSL stylesheet really does carry
    hrefs, for the HTML it generates rather than for anything to walk.

    So the ROOT ELEMENT decides. Measured on `ps-2.kev009.com/pccbbs/pc_servers/IBMupdate.xsl`,
    which opens `<?xml version='1.0'?>` and then `<xsl:stylesheet`.
    """

    def test_an_xsl_stylesheet_is_not_a_page(self):
        head = b"<?xml version='1.0'?>\r\n<xsl:stylesheet xmlns:xsl='x'>"
        self.assertFalse(pe.html_root(head))

    def test_nor_are_the_other_xml_formats_this_collection_holds(self):
        for head in (b'<?xml version="1.0"?><eagle version="6">',
                     b'<?xml version="1.0"?><Project ToolsVersion="4">',
                     b'<?xml version="1.0"?><qpm:QPM>'):
            self.assertFalse(pe.html_root(head), head)

    def test_BUT_XHTML_IS(self):
        # The direction that must not break: XHTML opens with the declaration too, and it is
        # exactly the kind of page this tool exists to find when nothing walks its name.
        self.assertTrue(pe.html_root(b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'))

    def test_and_a_comment_between_them_does_not_hide_it(self):
        self.assertTrue(pe.html_root(b'<?xml version="1.0"?><!-- generated --><html>'))

    def test_plain_html_never_reaches_the_question(self):
        for head in (b"<!DOCTYPE html><html>", b"<html><body>", b"<HTML>"):
            self.assertTrue(pe.html_root(head), head)

    def test_an_unterminated_comment_is_not_an_answer(self):
        # A fixed-size head was read. "It may continue" is not "it does".
        self.assertFalse(pe.html_root(b'<?xml version="1.0"?><!-- never closed'))


class TestPagesWithLinks(unittest.TestCase):
    """The finding test. It asks for markup AND links, and the second half is the whole point."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="pe-test-")

    def tearDown(self):
        for f in os.listdir(self.d):
            os.remove(os.path.join(self.d, f))
        os.rmdir(self.d)

    def write(self, name, data):
        """-> (archive root, path), the pair pages_with_links takes so it can rebuild the URL."""
        p = os.path.join(self.d, name)
        with io.open(p, "wb") as fh:
            fh.write(data)
        return (self.d, p)

    PAGE = b'<html><body><a href="one.html">1</a> <a href="sub/two.htm">2</a></body></html>'

    def test_a_page_with_links_is_the_finding(self):
        pages, read, links, _c, _s = pe.pages_with_links([self.write("a", self.PAGE)])
        self.assertEqual((pages, read, links), (1, 1, 2))

    def test_THE_EXAMPLES_ARE_THE_FILES_THAT_COUNTED(self):
        """The report used to print the first three files carrying the extension, which are not
        the files that produced the finding -- and that led the person who wrote the row to the
        wrong conclusion the same day.

        `.orig` showed `Jensen-HOWTO.orig`, a plain-text HOWTO that `looks_like_html` had already
        rejected, beside a count of 168 pages it had nothing to do with. A row whose evidence
        belongs to a different file is worse than a row with no evidence: it gets believed.
        """
        paths = [self.write("plain.orig", b"just text, no markup at all"),
                 self.write("real.orig", self.PAGE)]
        pages, _r, _l, _c, shown = pe.pages_with_links(paths)
        self.assertEqual(pages, 1)
        self.assertEqual([os.path.basename(q) for q in shown], ["real.orig"])

    def test_and_a_copy_is_not_offered_as_evidence_either(self):
        paths = [self.write("index.html.orig", self.PAGE), self.write("real.orig", self.PAGE)]
        _p, _r, _l, copies, shown = pe.pages_with_links(paths)
        self.assertEqual(copies, 1)
        self.assertEqual([os.path.basename(q) for q in shown], ["real.orig"])

    def test_A_COPIES_ONLY_ROW_SHOWS_A_COPY(self):
        """A row with no hits used to show the files that were READ and rejected, which are not
        the copies it claims to be listing.

        Measured: `.perl` appeared under "copies of pages" showing `wall.perl`, `uureroute.perl`
        and `myformat.perl` -- three ordinary Perl scripts. The one copy in that extension was
        `perl.html.perl`, and it was the only file not shown. Evidence that belongs to a
        different file is worse than none, because it gets believed; this is that mistake one
        layer below the one already fixed.
        """
        paths = [self.write("wall.perl", b"#!/usr/bin/perl"),
                 self.write("perl.html.perl", self.PAGE)]
        pages, _r, _l, copies, shown = pe.pages_with_links(paths)
        self.assertEqual((pages, copies), (0, 1))
        self.assertEqual([os.path.basename(q) for q in shown], ["perl.html.perl"])

    def test_A_COPY_OF_A_PAGE_IS_NOT_A_FINDING(self):
        """D1: this tool could not be a gate, because most of what it found was backups.

        `fetch.html.new` holds exactly the links `fetch.html` holds, and that one IS walked, so
        nothing was missed. Counting it kept the real rows unreadable and the exit code useless.
        """
        pages, read, links, copies, _s = pe.pages_with_links(
            [self.write("fetch.html.new", self.PAGE)])
        self.assertEqual((pages, read, links), (0, 0, 0))
        self.assertEqual(copies, 1)

    def test_AND_IT_IS_NOT_OPENED_AT_ALL(self):
        # `read` stays 0, which is the cheap half: a backup is decided by its NAME, before any
        # disk is touched. Over this collection that is the difference between a check that runs
        # and one that reads a few hundred thousand files in order to say nothing.
        _p, read, _l, copies, _s = pe.pages_with_links([self.write("index.html.orig", self.PAGE)])
        self.assertEqual((read, copies), (0, 1))

    def test_and_the_sort_order_variants_too(self):
        _p, _r, _l, copies, _s = pe.pages_with_links([self.write("index.html@S=A", self.PAGE)])
        self.assertEqual(copies, 1)

    def test_A_REAL_UNWALKED_SPELLING_STILL_COUNTS(self):
        """The direction that matters. `.phtml` is what sun3arc used for all 134 of its pages,
        and this tool exists because nothing walked them. A rule that excused it would have
        excused the very defect it was written to find."""
        pages, _r, links, copies, _s = pe.pages_with_links([self.write("page.phtml", self.PAGE)])
        self.assertEqual((pages, links, copies), (1, 2, 0))

    def test_and_a_backup_of_something_that_is_not_a_page_is_not_excused(self):
        # `data.csv.bak` strips to a name no predicate accepts, so it is not a copy of a PAGE.
        # If it holds links, it is a finding like any other.
        pages, _r, links, copies, _s = pe.pages_with_links([self.write("data.csv.bak", self.PAGE)])
        self.assertEqual((pages, links, copies), (1, 2, 0))

    def test_AN_XML_FILE_IS_MARKUP_AND_IS_NOT_A_FINDING(self):
        """The one that matters: the first full run drowned in these.

        looks_like_html() accepts `<?xml`, so an EAGLE schematic, an MSBuild project and a QNX
        package manifest all answered "markup". None of them is a page, and counting them as one
        produced 71 extensions of noise around the two real answers.
        """
        eagle = b'<?xml version="1.0"?>\n<eagle><drawing><layers/></drawing></eagle>'
        msbuild = (b'<?xml version="1.0"?>\n<Project><ItemGroup>'
                   b'<ClCompile Include="a.c" /></ItemGroup></Project>')
        pages, read, links, _c, _s = pe.pages_with_links([self.write("a.brd", eagle),
                                                  self.write("b.vcxproj", msbuild)])
        self.assertEqual((pages, links), (0, 0))
        self.assertEqual(read, 2, "they must still be counted as looked at")

    def test_markup_with_only_OFF_HOST_links_is_not_a_finding_either(self):
        """Nothing would have been walked from it, so nothing was lost.

        THIS IS THE TEST THAT CAUGHT THE WRONG GUARD. The first version asked
        is_child_link(href, allow_up=True), which returns TRUE for a fully-qualified URL on
        purpose -- the library's own docstring calls it the weaker of two guards and says the
        real one is comparing the resolved url against the base. Built on the weak one, the
        tool reported `0 off-host` across 4.9 million links, and a guard that never fires reads
        exactly like a tree with nothing outside it.
        """
        off = b'<html><a href="http://elsewhere.example/x.html">x</a></html>'
        self.assertEqual(pe.pages_with_links([self.write("a", off)])[:4], (0, 1, 0, 0))

    def test_and_a_link_that_climbs_out_of_the_archive_is_off_host_too(self):
        # `../` resolving above the archive root is the case allow_up exists for, and exactly
        # the one a prefix comparison catches and a shape test cannot.
        out = b'<html><a href="../../../elsewhere/x.html">x</a></html>'
        self.assertEqual(pe.pages_with_links([self.write("a", out)])[:4], (0, 1, 0, 0))

    def test_and_neither_is_markup_with_no_links_at_all(self):
        self.assertEqual(pe.pages_with_links([self.write("a", b"<html>text only</html>")])[:4],
                         (0, 1, 0, 0))

    def test_LEADING_WHITESPACE_DOES_NOT_HIDE_THE_TAG(self):
        # Hand-written pages start with a blank line often enough that a strict first-byte test
        # would answer "not a page" for a page.
        p = self.write("a", b"\r\n\r\n   " + self.PAGE)
        self.assertEqual(pe.pages_with_links([p])[0], 1)

    def test_a_non_page_is_not_even_opened_as_text(self):
        for data in (b"GIF89a\x00\x00", b"%PDF-1.4", b""):
            pages, read, links, _c, _s = pe.pages_with_links([self.write("a", data)])
            self.assertEqual((pages, read, links), (0, 1, 0), repr(data[:8]))

    def test_an_unreadable_file_is_not_counted_as_read(self):
        # The denominator has to mean "files actually opened", or a directory full of refusals
        # reads as a clean answer.
        missing = (self.d, os.path.join(self.d, "does-not-exist"))
        self.assertEqual(pe.pages_with_links([missing, self.write("a", self.PAGE)])[:4], (1, 1, 2, 0))


class TestCount(unittest.TestCase):
    """It exists because human() was used for counts and printed `1.19 kB` for 1 190 links."""

    def test_it_groups_without_claiming_bytes(self):
        self.assertEqual(pe.count(0), "0")
        self.assertEqual(pe.count(1190), "1 190")
        self.assertEqual(pe.count(9255290), "9 255 290")

    def test_and_human_would_still_have_said_bytes(self):
        self.assertIn("B", common.human(1190))
        self.assertNotIn("B", pe.count(1190))


if __name__ == "__main__":
    unittest.main()
