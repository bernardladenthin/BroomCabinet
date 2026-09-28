#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""wayback.py: the two Internet Archive addresses, checked without asking the Archive anything.

MOVED OUT OF common_test.py ON 2026-09-23 with the module it tests, unchanged. A library split
into modules that share one test file has only been rearranged; the test file is where a reader
goes to find out what a module promises, so it moves with it.

WHAT THESE ARE ABOUT IS ENCODING. A url goes into a query VALUE, so its own `?`, `&` and `/`
must not survive as structure -- otherwise the Archive is asked a different question and answers
it, correctly, about something else. That is the kind of mistake that returns plausible data.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wayback  # noqa: E402

class TestWaybackMatchType(unittest.TestCase):
    """A bare host asked for as a prefix comes back half missing, with nothing to show it."""

    def test_a_bare_host_is_a_domain(self):
        # So its subdomains come along. A site that moved between `www.` and no-`www.` over
        # twenty years lives under both.
        for source in ("ftp.example.org", "example.org", "example.org/"):
            self.assertEqual(wayback.wayback_match_type(source), "domain", source)

    def test_a_path_is_a_prefix(self):
        for source in ("example.org/pub", "example.org/pub/", "example.org/a/b.txt"):
            self.assertEqual(wayback.wayback_match_type(source), "prefix", source)

    def test_a_trailing_slash_alone_does_not_make_it_a_path(self):
        self.assertEqual(wayback.wayback_match_type("example.org/"), "domain")


class TestWaybackCdxUrl(unittest.TestCase):
    def test_the_ordinary_query(self):
        got = wayback.wayback_cdx_url("ftp.example.org")
        self.assertTrue(got.startswith(wayback.WAYBACK_CDX_BASE + "?url=ftp.example.org"))
        self.assertIn("matchType=domain", got)
        self.assertIn("fl=" + wayback.WAYBACK_CDX_FIELDS, got)

    def test_THE_SOURCE_IS_FULLY_ENCODED(self):
        # It is going into a query VALUE, so its own ? & and / must not survive as structure --
        # otherwise the Archive is asked a different question and answers it, correctly, about
        # something else.
        got = wayback.wayback_cdx_url("h.org/a?b=c&d=e/f")
        self.assertIn("url=h.org%2Fa%3Fb%3Dc%26d%3De%2Ff", got)
        self.assertEqual(got.count("?"), 1)
        self.assertEqual(got.count("&"), got.count("&matchType=") + got.count("&fl="))

    def test_the_match_type_can_be_given(self):
        self.assertIn("matchType=host", wayback.wayback_cdx_url("h.org", match="host"))

    def test_AN_EMPTY_MATCH_LEAVES_IT_OUT(self):
        # Not the same as choosing one: the index has its own default, and a caller that was
        # relying on it should go on relying on it rather than inherit a guess about what it is.
        got = wayback.wayback_cdx_url("h.org/a.txt", match="")
        self.assertNotIn("matchType", got)

    def test_the_json_form(self):
        got = wayback.wayback_cdx_url("h.org", output="json", fields="timestamp,statuscode")
        self.assertIn("&output=json", got)
        self.assertIn("fl=timestamp,statuscode", got)

    def test_no_output_means_the_text_form(self):
        self.assertNotIn("output", wayback.wayback_cdx_url("h.org"))

    def test_it_is_https(self):
        # One caller asked over http and the other did not; the Archive redirects the first to the
        # second, so http cost a round trip per query and bought nothing.
        self.assertTrue(wayback.wayback_cdx_url("h.org").startswith("https://"))

    def test_extra_is_appended_verbatim(self):
        self.assertTrue(wayback.wayback_cdx_url("h.org", extra="&limit=5").endswith("&limit=5"))


class TestWaybackReplayUrl(unittest.TestCase):
    """The stored bytes, not the rendered page."""

    def test_the_id_suffix_is_there(self):
        # Without it the Archive returns the page as it renders it, with its own banner and its
        # rewritten links. A copy made from that is a copy of the Archive, not of the site.
        got = wayback.wayback_replay_url("20010704120000", "http://h.org/a.txt")
        self.assertEqual(got, "https://web.archive.org/web/20010704120000id_/http://h.org/a.txt")

    def test_A_SCHEMELESS_URL_GETS_ONE(self):
        # One caller carries urls as host/path -- that is what its records hold -- and the replay
        # address needs an absolute one.
        self.assertEqual(wayback.wayback_replay_url("2001", "h.org/a.txt"),
                         "https://web.archive.org/web/2001id_/http://h.org/a.txt")

    def test_an_https_source_keeps_its_scheme(self):
        self.assertIn("id_/https://h.org/", wayback.wayback_replay_url("2001", "https://h.org/a"))

    def test_a_query_string_containing_slashes_does_not_look_like_a_scheme(self):
        # `//` inside a query must not be read as "this already has one".
        got = wayback.wayback_replay_url("2001", "h.org/cgi?a=//b")
        self.assertIn("id_/http://h.org/cgi?a=//b", got)

    def test_the_url_is_NOT_encoded(self):
        # The replay path carries the original url as a path, not as a query value; encoding it
        # would ask the Archive for a capture of a url that contains percent signs.
        self.assertIn("a b.txt", wayback.wayback_replay_url("2001", "h.org/a b.txt"))


class TestTheReplayBaseNoTestTouched(unittest.TestCase):
    """One export no test mentioned, measured 2026-09-24. No caller outside wayback.py."""

    def test_wayback_replay_url_is_built_from_it(self):
        url = wayback.wayback_replay_url("20080527120000", "h18002.www1.hp.com/x.htm")
        self.assertTrue(url.startswith(wayback.WAYBACK_REPLAY_BASE), url)

    def test_AND_IT_ENDS_IN_A_SLASH(self):
        # It is joined by concatenation, not by urljoin. Losing the slash would produce
        # `.../web20080527...` -- a URL the Archive answers for nothing.
        self.assertTrue(wayback.WAYBACK_REPLAY_BASE.endswith("/"))

    def test_and_it_is_the_replay_host_not_the_index_host(self):
        self.assertNotEqual(wayback.WAYBACK_REPLAY_BASE, wayback.WAYBACK_CDX_BASE)

if __name__ == "__main__":
    unittest.main()
