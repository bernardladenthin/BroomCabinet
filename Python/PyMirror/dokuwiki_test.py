#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""dokuwiki.py: the contract with the third wiki engine, checked without asking a wiki anything.

MOVED OUT OF common_test.py ON 2026-09-23 with the module it tests, unchanged. A library split
into modules that share one test file has only been rearranged; the test file is where a reader
goes to find out what a module promises, so it moves with it.

Every request here is answered by a fake opener. A helper that can only be exercised against a
live wiki is a helper nobody exercises -- and against somebody's private server, exercising it
is not free.

WATCH WHAT THE FAKE OPENER ITSELF NEEDS. dokuwiki_page_ids() skips a namespace that will not
answer, deliberately and silently -- one dead branch must not end a whole index walk. So an
exception raised INSIDE the fake, for any reason, looks exactly like a wiki declining to answer:
the walk goes on, the test passes fewer pages than it meant to, and nothing says so. This file
was one missing `import urllib.parse` away from that on the day it was split out, and the only
reason it was caught is that two tests happened to assert the walked result rather than just
its shape.
"""

import io
import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dokuwiki  # noqa: E402

class TestDokuWikiUrls(unittest.TestCase):
    def test_the_whole_tree(self):
        self.assertEqual(dokuwiki.dokuwiki_index_url("https://w/doku.php"),
                         "https://w/doku.php?do=index")

    def test_one_namespace(self):
        self.assertEqual(dokuwiki.dokuwiki_index_url("https://w/doku.php", "aix"),
                         "https://w/doku.php?do=index&idx=aix")

    def test_a_nested_namespace_keeps_its_colon(self):
        # A colon is legal in a query value and IS the namespace separator; encoding it asks for
        # a namespace whose name contains a literal colon, which does not exist.
        url = dokuwiki.dokuwiki_index_url("https://w/d.php", "aix:boot")
        self.assertIn("idx=aix%3Aboot", url)

    def test_the_raw_source_of_a_page(self):
        self.assertEqual(dokuwiki.dokuwiki_source_url("https://w/d.php", "aix:boot"),
                         "https://w/d.php?id=aix%3Aboot&do=export_raw")

    def test_a_space_in_an_id_is_encoded(self):
        self.assertIn("id=a%20b", dokuwiki.dokuwiki_source_url("https://w/d.php", "a b"))


class TestDokuWikiParseIndex(unittest.TestCase):
    """One function, one lesson, and the lesson cost a whole wiki."""

    PAGE = (
        '<ul>'
        '<li><a href="/doku.php?do=index&amp;idx=aix" class="idx_dir">aix</a></li>'
        '<li><a href="/doku.php?id=aix%3Aboot_problem">boot problem</a></li>'
        '<li><a href="/doku.php?id=start">start</a></li>'
        '<li><a href="/doku.php?id=aix%3Anet%3Atcpip">tcpip</a></li>'
        '<li><a href="/doku.php?do=edit&amp;id=start">edit</a></li>'
        '</ul>')

    def test_it_finds_the_pages(self):
        ids, _ns = dokuwiki.dokuwiki_parse_index(self.PAGE)
        self.assertEqual(sorted(ids), ["aix:boot_problem", "aix:net:tcpip", "start"])

    def test_HTML_UNESCAPE_BEFORE_MATCHING(self):
        # The index writes `&amp;idx=aix`, so a pattern anchored on a literal `&` sees `;idx=`
        # and matches nothing. The wiki then looks like a two-page wiki instead of a 500-page
        # one, WITH NO ERROR ANYWHERE -- the run finishes and reports success.
        _ids, ns = dokuwiki.dokuwiki_parse_index(self.PAGE)
        self.assertIn("aix", ns)

    def test_and_without_the_unescape_it_would_find_nothing(self):
        # The danger, stated. An escaped index yields no namespace to the naive pattern.
        raw = '<a href="/doku.php?do=index&amp;idx=aix">aix</a>'
        self.assertEqual(dokuwiki.DOKUWIKI_NS_LINK.findall(raw), [])
        self.assertEqual(dokuwiki.dokuwiki_parse_index(raw)[1], {"aix"})

    def test_percent_encoding_is_undone(self):
        ids, _ns = dokuwiki.dokuwiki_parse_index(self.PAGE)
        self.assertIn("aix:boot_problem", ids)

    def test_AN_ACTION_IS_NOT_A_PAGE(self):
        # `do=edit` and DokuWiki's own control entries are links, not content.
        ids, _ns = dokuwiki.dokuwiki_parse_index(self.PAGE)
        self.assertFalse(any(i.startswith("do=") for i in ids))

    def test_A_PAGES_PARENT_IS_A_NAMESPACE_WORTH_VISITING(self):
        # A namespace is also a page when it has a start page, and a collapsed index never names
        # the deeper ones. Leaving them out loses whole branches silently.
        _ids, ns = dokuwiki.dokuwiki_parse_index(self.PAGE)
        self.assertIn("aix:net", ns)

    def test_a_page_with_no_namespace_adds_none(self):
        _ids, ns = dokuwiki.dokuwiki_parse_index('<a href="?id=start">s</a>')
        self.assertEqual(ns, set())

    def test_an_empty_page_is_two_empty_sets(self):
        self.assertEqual(dokuwiki.dokuwiki_parse_index(""), (set(), set()))


class TestDokuWikiLocalPath(unittest.TestCase):
    def test_the_colon_becomes_a_separator(self):
        got = dokuwiki.dokuwiki_local_path("/srv/w", "aix:boot")
        self.assertEqual(got, os.path.join("/srv/w", "aix", "boot.txt"))

    def test_a_page_with_no_namespace(self):
        self.assertEqual(dokuwiki.dokuwiki_local_path("/srv/w", "start"),
                         os.path.join("/srv/w", "start.txt"))

    def test_deep_namespaces(self):
        self.assertEqual(dokuwiki.dokuwiki_local_path("/srv/w", "a:b:c"),
                         os.path.join("/srv/w", "a", "b", "c.txt"))

    def test_AN_ID_CANNOT_WALK_OUT_OF_THE_ROOT(self):
        # An id is a REMOTE name. One that climbs upward is either a mistake or an attack, and
        # nothing below this should have to think about it.
        self.assertEqual(dokuwiki.dokuwiki_local_path("/srv/w", "..:..:etc:passwd"),
                         os.path.join("/srv/w", "etc", "passwd.txt"))

    def test_an_id_that_names_nothing_is_None(self):
        for bad in ("", ":", "::", ".:..:"):
            self.assertIsNone(dokuwiki.dokuwiki_local_path("/srv/w", bad), repr(bad))

    def test_empty_components_are_dropped(self):
        self.assertEqual(dokuwiki.dokuwiki_local_path("/srv/w", "a::b"),
                         os.path.join("/srv/w", "a", "b.txt"))


class TestDokuWikiPageIds(unittest.TestCase):
    """The walk, against recorded pages. Nobody's wiki is touched."""

    def opener(self, pages):
        """pages: {namespace: html}. A namespace not listed answers empty."""
        seen = []

        def open_url(req, **_kw):
            url = req.full_url
            ns = ""
            if "idx=" in url:
                ns = urllib.parse.unquote(url.split("idx=", 1)[1])
            seen.append(ns)
            body = pages.get(ns, "").encode("utf-8")

            class R(io.BytesIO):
                headers = {"Content-Type": "text/html"}

                def __enter__(self):
                    return self

                def __exit__(self, *e):
                    self.close()
                    return False
            return R(body)
        open_url.seen = seen
        return open_url

    def test_it_walks_into_a_namespace(self):
        op = self.opener({
            "": '<a href="?do=index&amp;idx=aix">aix</a><a href="?id=start">s</a>',
            "aix": '<a href="?id=aix%3Aboot">b</a>',
        })
        self.assertEqual(dokuwiki.dokuwiki_page_ids("https://w/d.php", opener=op),
                         ["aix:boot", "start"])

    def test_the_result_is_sorted(self):
        op = self.opener({"": '<a href="?id=z">z</a><a href="?id=a">a</a>'})
        self.assertEqual(dokuwiki.dokuwiki_page_ids("https://w/d.php", opener=op), ["a", "z"])

    def test_A_NAMESPACE_IS_ASKED_FOR_ONCE(self):
        # Two pages in one namespace both name it as their parent; asking twice is somebody
        # else's server answering the same question twice.
        op = self.opener({"": '<a href="?id=a%3Ax">x</a><a href="?id=a%3Ay">y</a>',
                          "a": ""})
        dokuwiki.dokuwiki_page_ids("https://w/d.php", opener=op)
        self.assertEqual(sorted(op.seen), ["", "a"])

    def test_A_NAMESPACE_THAT_FAILS_IS_REPORTED_NOT_FATAL(self):
        # One branch being unreachable is not a reason to lose the rest of the wiki.
        calls = []

        def op(req, **_kw):
            if "idx=" in req.full_url:
                raise TimeoutError("that branch is not answering")
            class R(io.BytesIO):
                headers = {"Content-Type": "text/html"}
                def __enter__(self): return self
                def __exit__(self, *e):
                    self.close()
                    return False
            return R(b'<a href="?do=index&amp;idx=aix">aix</a><a href="?id=start">s</a>')

        got = dokuwiki.dokuwiki_page_ids("https://w/d.php", opener=op,
                                       report=lambda *a: calls.append(a))
        self.assertEqual(got, ["start"])
        self.assertTrue(any(c[3] is not None for c in calls))

    def test_progress_is_a_callback(self):
        seen = []
        op = self.opener({"": '<a href="?id=a">a</a>'})
        dokuwiki.dokuwiki_page_ids("https://w/d.php", opener=op,
                                 report=lambda *a: seen.append(a))
        self.assertEqual(seen[0][0], "")          # the root namespace
        self.assertEqual(seen[0][1], 1)           # one id found

    def test_an_empty_wiki_is_an_empty_list(self):
        self.assertEqual(dokuwiki.dokuwiki_page_ids("https://w/d.php", opener=self.opener({})), [])


class TestTheConstantsNoTestTouched(unittest.TestCase):
    """Two exports no test mentioned, measured 2026-09-24. Neither has a caller outside here.

    What is asserted is the RELATIONSHIP to the function that reads the constant, not its text:
    a copy of the source line fails only when somebody edits it deliberately.
    """

    def test_DOKUWIKI_ID_LINK_reads_a_page_id_out_of_a_query(self):
        self.assertEqual(dokuwiki.DOKUWIKI_ID_LINK.findall('<a href="/d.php?id=start">'),
                         ["start"])
        self.assertEqual(dokuwiki.DOKUWIKI_ID_LINK.findall('?do=x&id=aix%3Aboot"'),
                         ["aix%3Aboot"])

    def test_AND_IT_STOPS_AT_THE_QUOTE_AND_THE_AMPERSAND(self):
        # Running past either swallows the rest of the tag into the id, and the wiki then looks
        # like it holds one page with an enormous name.
        self.assertEqual(dokuwiki.DOKUWIKI_ID_LINK.findall('?id=start" class="wikilink"'),
                         ["start"])
        self.assertEqual(dokuwiki.DOKUWIKI_ID_LINK.findall('?id=start&do=edit'), ["start"])

    def test_DOKUWIKI_NOT_A_PAGE_is_what_parse_index_refuses(self):
        ids, _ns = dokuwiki.dokuwiki_parse_index(
            '<a href="?id=start">s</a><a href="?do=edit&amp;id=x">e</a><a href="?id=-">d</a>')
        self.assertIn("start", ids)
        for junk in dokuwiki.DOKUWIKI_NOT_A_PAGE:
            self.assertFalse(any(i.startswith(junk) for i in ids), junk)

    def test_and_a_page_whose_name_merely_contains_a_dash_is_kept(self):
        # The rule is a PREFIX, and `boot-problem` is an ordinary page name.
        ids, _ns = dokuwiki.dokuwiki_parse_index('<a href="?id=boot-problem">b</a>')
        self.assertEqual(sorted(ids), ["boot-problem"])

if __name__ == "__main__":
    unittest.main()
