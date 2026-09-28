#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""pmwiki.py: the contract with one wiki engine, checked without asking a wiki anything.

MOVED OUT OF common_test.py ON 2026-09-23 with the module it tests, unchanged. A library split
into modules that share one test file has only been rearranged; the test file is where a reader
goes to find out what a module promises, so it moves with it.

Every request here is answered by a fake opener. A helper that can only be exercised against a
live wiki is a helper nobody exercises -- and against somebody's private server, exercising it
is not free.
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmwiki  # noqa: E402


class TestPmWikiUrls(unittest.TestCase):
    def test_the_source_action(self):
        self.assertEqual(pmwiki.pmwiki_source_url("http://w/pmwiki.php", "Main.HomePage"),
                         "http://w/pmwiki.php?n=Main.HomePage&action=source")

    def test_THE_DOT_IS_NOT_ESCAPED(self):
        # A PmWiki page name IS `Group.Page`. Encoding the separator asks for a page whose name
        # contains a literal dot, which does not exist -- and the wiki answers with its "no such
        # page" HTML under a 200, which is the one failure shape that looks like success.
        self.assertIn("n=Main.HomePage", pmwiki.pmwiki_source_url("http://w/", "Main.HomePage"))
        self.assertNotIn("%2E", pmwiki.pmwiki_source_url("http://w/", "Main.HomePage"))

    def test_but_everything_else_is(self):
        url = pmwiki.pmwiki_source_url("http://w/", "Main.A B&C")
        self.assertIn("A%20B%26C", url)

    def test_the_rendered_page_has_no_action(self):
        self.assertEqual(pmwiki.pmwiki_page_url("http://w/pmwiki.php", "Main.X"),
                         "http://w/pmwiki.php?n=Main.X")


class TestPmWikiIsSource(unittest.TestCase):
    """A refusal arrives with status 200, so the status code is not consulted at all."""

    def test_plain_markup(self):
        self.assertTrue(pmwiki.pmwiki_is_source(b"!! Heading\n* item\n", "text/plain"))

    def test_a_charset_parameter_does_not_matter(self):
        self.assertTrue(pmwiki.pmwiki_is_source(b"text", "text/plain; charset=utf-8"))

    def test_AN_ERROR_PAGE_IS_NOT_SOURCE(self):
        # Saving that under a wiki page's name is worse than an absence: it looks like a copy.
        self.assertFalse(pmwiki.pmwiki_is_source(b"<!DOCTYPE html><html>", "text/html"))

    def test_BOTH_HALVES_ARE_NEEDED_the_type(self):
        # A body that is plainly markup, served as HTML, is still not what was asked for.
        self.assertFalse(pmwiki.pmwiki_is_source(b"!! Heading", "text/html"))

    def test_BOTH_HALVES_ARE_NEEDED_the_body(self):
        # A wiki that serves its error page as text/plain would pass on the type alone.
        self.assertFalse(pmwiki.pmwiki_is_source(b"<html><body>gone</body></html>", "text/plain"))

    def test_leading_whitespace_does_not_disguise_html(self):
        self.assertFalse(pmwiki.pmwiki_is_source(b"\n\n   <!doctype html>", "text/plain"))

    def test_case_does_not_disguise_it_either(self):
        self.assertFalse(pmwiki.pmwiki_is_source(b"<HTML>", "text/plain"))

    def test_a_missing_content_type_is_not_source(self):
        for ctype in (None, "", "application/octet-stream"):
            self.assertFalse(pmwiki.pmwiki_is_source(b"!! Heading", ctype), repr(ctype))

    def test_an_empty_body_with_the_right_type_is_source(self):
        # An empty page is a page. Nothing here decides whether it is worth keeping.
        self.assertTrue(pmwiki.pmwiki_is_source(b"", "text/plain"))


class TestPmWikiRecentChanges(unittest.TestCase):
    """The whole inventory in one request, which is why this page is used at all."""

    SAMPLE = (
        "!! Recent Changes\n"
        "* [[Main.HomePage]]  . . . March 02, 2019, at 11:04 AM by simon\n"
        "* [[Docs.Install-Guide]]  . . . January 14, 2011, at 09:22 PM by ?\n"
        "* [[Main.HomePage]]  . . . March 01, 2019, at 08:00 AM by simon\n"
        "* [[Site.Side_Bar]]  . . . 2008 by admin\n"
        "not a change line at all\n"
        "* [[NotAPage]]  . . . no group, so no match\n"
    )

    def test_it_finds_the_pages(self):
        got = pmwiki.pmwiki_parse_recent_changes(self.SAMPLE)
        self.assertEqual([p for p, _w in got],
                         ["Main.HomePage", "Docs.Install-Guide", "Site.Side_Bar"])

    def test_it_keeps_the_date_text_verbatim(self):
        got = dict(pmwiki.pmwiki_parse_recent_changes(self.SAMPLE))
        self.assertEqual(got["Docs.Install-Guide"], "January 14, 2011, at 09:22 PM by ?")

    def test_A_PAGE_APPEARS_ONCE_PER_EDIT_AND_IS_COUNTED_ONCE(self):
        # Keeping both would inflate the inventory and make the count disagree with the number of
        # files written -- and this collection's whole currency is numbers.
        got = pmwiki.pmwiki_parse_recent_changes(self.SAMPLE)
        self.assertEqual(len([p for p, _w in got if p == "Main.HomePage"]), 1)

    def test_the_FIRST_mention_wins_which_is_the_newest(self):
        got = dict(pmwiki.pmwiki_parse_recent_changes(self.SAMPLE))
        self.assertIn("March 02", got["Main.HomePage"])

    def test_a_name_without_a_group_is_not_a_page(self):
        self.assertNotIn("NotAPage",
                         [p for p, _w in pmwiki.pmwiki_parse_recent_changes(self.SAMPLE)])

    def test_hyphens_and_underscores_are_allowed_in_the_page_half(self):
        got = [p for p, _w in pmwiki.pmwiki_parse_recent_changes(self.SAMPLE)]
        self.assertIn("Docs.Install-Guide", got)
        self.assertIn("Site.Side_Bar", got)

    def test_leading_whitespace_on_the_line_is_tolerated(self):
        got = pmwiki.pmwiki_parse_recent_changes("   * [[A.B]]  . . . today\n")
        self.assertEqual(got, [("A.B", "today")])

    def test_an_empty_page_is_an_empty_list_not_an_error(self):
        self.assertEqual(pmwiki.pmwiki_parse_recent_changes(""), [])

    def test_crlf_does_not_leave_a_carriage_return_in_the_date(self):
        got = pmwiki.pmwiki_parse_recent_changes("* [[A.B]]  . . . today\r\n")
        self.assertEqual(got, [("A.B", "today")])


class TestPmWikiInventory(unittest.TestCase):
    """Fetch plus parse, against a recorded answer. Nobody's server is touched."""

    def opener(self, body, ctype="text/plain"):
        class Response(io.BytesIO):
            headers = {"Content-Type": ctype}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.close()
                return False

        def open_url(_req, **_kw):
            return Response(body)
        return open_url

    def test_it_returns_the_inventory(self):
        body = b"* [[Main.HomePage]]  . . . today by simon\n"
        got = pmwiki.pmwiki_inventory("http://w/", opener=self.opener(body))
        self.assertEqual(got, [("Main.HomePage", "today by simon")])

    def test_AN_ERROR_PAGE_RAISES_RATHER_THAN_LOOKING_EMPTY(self):
        # An empty inventory and a refused one look identical afterwards, and only one of them
        # means the wiki is empty.
        op = self.opener(b"<!DOCTYPE html><html>no such page</html>", "text/html")
        with self.assertRaises(pmwiki.PmWikiNotSource):
            pmwiki.pmwiki_inventory("http://w/", opener=op)

    def test_the_reason_names_the_type_it_got(self):
        op = self.opener(b"<html>", "text/html")
        try:
            pmwiki.pmwiki_inventory("http://w/", opener=op)
        except pmwiki.PmWikiNotSource as why:
            self.assertIn("text/html", str(why))
        else:
            self.fail("should have raised")

    def test_IT_DOES_NOT_END_THE_PROCESS(self):
        # It called sys.exit until 2026-09-22, which took the decision away from every caller and
        # made this test impossible to write without a subprocess.
        op = self.opener(b"<html>", "text/html")
        with self.assertRaises(pmwiki.PmWikiNotSource):
            pmwiki.pmwiki_inventory("http://w/", opener=op)

    def test_A_BYTE_THAT_IS_NOT_UTF8_DOES_NOT_LOSE_THE_INVENTORY(self):
        # A wiki old enough to have no API is old enough to serve a mixed-encoding page. Guessing
        # UTF-8 and failing would throw away every page over one character in an edit summary.
        body = b"* [[Main.Caf\xe9]]  . . . by Ren\xe9\n* [[Main.Plain]]  . . . today\n"
        got = pmwiki.pmwiki_inventory("http://w/", opener=self.opener(body))
        self.assertEqual([p for p, _w in got], ["Main.Plain"])   # the accented name has no match
        self.assertTrue(got)

    def test_it_asks_for_the_right_page(self):
        seen = []

        def op(req, **_kw):
            seen.append(req.full_url)
            class R(io.BytesIO):
                headers = {"Content-Type": "text/plain"}
                def __enter__(self): return self
                def __exit__(self, *e):
                    self.close()
                    return False
            return R(b"")
        pmwiki.pmwiki_inventory("http://w/pmwiki.php", opener=op)
        self.assertEqual(seen, ["http://w/pmwiki.php?n=Site.AllRecentChanges&action=source"])


class TestTheRecentChangesLineNoTestTouched(unittest.TestCase):
    """One export no test mentioned, measured 2026-09-24. No caller outside pmwiki.py."""

    def test_it_reads_a_line_of_Site_AllRecentChanges(self):
        got = pmwiki.PMWIKI_RC_LINE.match("* [[Main.HomePage]] . . . 2019 by ?:")
        self.assertIsNotNone(got)
        self.assertEqual(got.group(1), "Main.HomePage")

    def test_AND_THE_PAGE_NAME_MUST_CARRY_ITS_GROUP(self):
        # `Group.Page` is PmWiki's whole addressing scheme. A bare name is a heading in that
        # page, not an entry, and following it asks the wiki for something that does not exist.
        self.assertIsNone(pmwiki.PMWIKI_RC_LINE.match("* [[HomePage]] . . . 2019"))

    def test_a_page_name_may_hold_a_dash_or_an_underscore(self):
        got = pmwiki.PMWIKI_RC_LINE.match("* [[Main.Boot-Problem_2]] . . . x")
        self.assertEqual(got.group(1), "Main.Boot-Problem_2")

    def test_and_pmwiki_parse_recent_changes_is_that_pattern_applied(self):
        # It returns (page, when) pairs -- the date text is kept verbatim beside the name.
        self.assertEqual(pmwiki.pmwiki_parse_recent_changes("* [[A.B]] . . . x"), [("A.B", "x")])

if __name__ == "__main__":
    unittest.main()
