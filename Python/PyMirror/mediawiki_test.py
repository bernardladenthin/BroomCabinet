#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""mediawiki.py: the API contract, checked without asking a wiki anything.

MOVED OUT OF common_test.py ON 2026-09-23 with the module it tests, unchanged. A library split
into modules that share one test file has only been rearranged; the test file is where a reader
goes to find out what a module promises, so it moves with it.

THE TESTS FOR WINDOWS_RESERVED DID NOT COME ALONG, and that is the point of where they are: the
constant stayed in common, because what this filesystem refuses to store is a fact about the
machine and not about MediaWiki. mediawiki_filename() is tested here; the list of device names
it consults is tested there.
"""

import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mediawiki  # noqa: E402


# MOVED HERE WITH THE TESTS THAT USE THEM. `answers` was the only caller of this
# FakeResponse, and these five classes were the only callers of `answers` -- so both
# belonged to mediawiki rather than to the shared file. common_test.py keeps a
# _FakeResponse of its own, which is a different class that had come to live one
# underscore away from this one.
class FakeResponse(io.BytesIO):
    """Enough of a urlopen response for json.load and a `with`."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def answers(*payloads):
    """An opener that returns each payload in turn. A string raises instead.

    Exercising these against a live wiki is not free -- it is somebody's server -- so the
    contract is tested against recorded shapes and the network is never touched.
    """
    seen = []
    queue = list(payloads)

    def opener(req, **kw):
        seen.append(req.full_url)
        item = queue.pop(0) if queue else {}
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode("utf-8"))

    opener.seen = seen
    return opener

class TestMediaWikiApi(unittest.TestCase):
    def test_a_good_answer(self):
        op = answers({"query": {"allpages": []}})
        data, why = mediawiki.mediawiki_api("http://w/", [("action", "query")], opener=op)
        self.assertEqual(why, "")
        self.assertIn("query", data)

    def test_the_url_carries_the_format_the_parser_expects(self):
        op = answers({})
        mediawiki.mediawiki_api("http://w/w", [("action", "query")], opener=op)
        self.assertIn("format=json", op.seen[0])
        self.assertIn("formatversion=2", op.seen[0])
        self.assertTrue(op.seen[0].startswith("http://w/w/api.php?"))

    def test_a_trailing_slash_does_not_become_a_double_one(self):
        op = answers({})
        mediawiki.mediawiki_api("http://w/w/", [("a", "b")], opener=op)
        self.assertNotIn("//api.php", op.seen[0])

    def test_FAILURE_IS_NEVER_A_BARE_NONE(self):
        # A failed request and an empty answer are different facts, and this collection has
        # already acted on the confusion: a 503 was recorded as "no captures".
        op = answers(urllib.error.HTTPError("http://w/", 503, "busy", {}, None))
        data, why = mediawiki.mediawiki_api("http://w/", [], tries=1, opener=op,
                                         sleep=lambda _s: None)
        self.assertIsNone(data)
        self.assertEqual(why, "HTTP 503")

    def test_a_socket_error_carries_its_type_as_the_reason(self):
        op = answers(TimeoutError("took too long"))
        data, why = mediawiki.mediawiki_api("http://w/", [], tries=1, opener=op,
                                         sleep=lambda _s: None)
        self.assertIsNone(data)
        self.assertEqual(why, "TimeoutError")

    def test_it_retries_and_then_succeeds(self):
        op = answers(TimeoutError(), {"query": {"ok": True}})
        data, why = mediawiki.mediawiki_api("http://w/", [], tries=4, opener=op,
                                         sleep=lambda _s: None)
        self.assertEqual(why, "")
        self.assertEqual(len(op.seen), 2)

    def test_A_RATE_LIMIT_IS_WAITED_OUT_LONGER_THAN_AN_ORDINARY_ERROR(self):
        # 429 and 503 are instructions, not failures. Hammering is how a polite client gets
        # blocked outright, and this collection depends on not being blocked.
        slept = []
        op = answers(urllib.error.HTTPError("http://w/", 429, "slow down", {}, None),
                     urllib.error.HTTPError("http://w/", 404, "gone", {}, None))
        mediawiki.mediawiki_api("http://w/", [], delay=1.0, tries=2, opener=op,
                             sleep=slept.append)
        self.assertGreaterEqual(slept[0], 10)     # the rate limit
        self.assertEqual(slept[1], 1.0)           # an ordinary error waits the plain delay

    def test_it_stops_after_the_given_number_of_tries(self):
        op = answers(*([TimeoutError()] * 10))
        mediawiki.mediawiki_api("http://w/", [], tries=3, opener=op, sleep=lambda _s: None)
        self.assertEqual(len(op.seen), 3)


class TestMediaWikiSiteinfo(unittest.TestCase):
    PAYLOAD = {"query": {"namespaces": {"-2": {"name": "Media"}, "-1": {"name": "Special"},
                                        "0": {"name": ""}, "14": {"name": "Category"}},
                         "general": {"sitename": "ND Wiki", "generator": "MediaWiki 1.39"},
                         "statistics": {"pages": 12, "articles": 9}}}

    def test_it_returns_the_namespaces(self):
        ns, general, stats = mediawiki.mediawiki_siteinfo("http://w/", opener=answers(self.PAYLOAD))
        self.assertEqual(ns[14], "Category")
        self.assertEqual(general["sitename"], "ND Wiki")
        self.assertEqual(stats["pages"], 12)

    def test_the_unnamed_namespace_is_called_Main(self):
        ns, _g, _s = mediawiki.mediawiki_siteinfo("http://w/", opener=answers(self.PAYLOAD))
        self.assertEqual(ns[0], "Main")

    def test_NEGATIVE_NAMESPACES_ARE_DROPPED(self):
        # Special and Media are virtual and hold nothing that can be fetched as a page.
        ns, _g, _s = mediawiki.mediawiki_siteinfo("http://w/", opener=answers(self.PAYLOAD))
        self.assertEqual(sorted(ns), [0, 14])

    def test_IT_RAISES_RATHER_THAN_GUESSING_THE_NAMESPACE_LIST(self):
        # A guessed list produces a copy that is missing whole sections while reporting success.
        op = answers(urllib.error.HTTPError("http://w/", 500, "boom", {}, None))
        with self.assertRaises(mediawiki.MediaWikiUnanswered):
            mediawiki.mediawiki_siteinfo("http://w/", tries=1, opener=op, sleep=lambda _s: None)

    def test_a_wiki_with_no_statistics_still_answers(self):
        payload = {"query": {"namespaces": {"0": {"name": ""}}, "general": {}}}
        ns, general, stats = mediawiki.mediawiki_siteinfo("http://w/", opener=answers(payload))
        self.assertEqual(stats, {})
        self.assertEqual(general, {})


class TestMediaWikiTitles(unittest.TestCase):
    def test_it_follows_the_continuation_marker(self):
        op = answers({"query": {"allpages": [{"title": "A"}, {"title": "B"}]},
                      "continue": {"apcontinue": "C"}},
                     {"query": {"allpages": [{"title": "C"}]}})
        titles, complete = mediawiki.mediawiki_titles("http://w/", {0: "Main"}, opener=op)
        self.assertEqual([t for _ns, t in titles], ["A", "B", "C"])
        self.assertTrue(complete)
        self.assertEqual(len(op.seen), 2)

    def test_the_second_request_carries_the_marker(self):
        op = answers({"query": {"allpages": []}, "continue": {"apcontinue": "Xyz"}},
                     {"query": {"allpages": []}})
        mediawiki.mediawiki_titles("http://w/", {0: "Main"}, opener=op)
        self.assertIn("apcontinue=Xyz", op.seen[1])

    def test_AN_UNANSWERED_NAMESPACE_IS_NOT_AN_EMPTY_ONE(self):
        # The list that comes back is indistinguishable, by inspection, from a complete one. The
        # caller is told, and must not write a completion marker over a False.
        op = answers({"query": {"allpages": [{"title": "A"}]}},
                     urllib.error.HTTPError("http://w/", 503, "busy", {}, None))
        titles, complete = mediawiki.mediawiki_titles(
            "http://w/", {0: "Main", 14: "Category"}, tries=1, opener=op, sleep=lambda _s: None)
        self.assertEqual(len(titles), 1)
        self.assertFalse(complete)

    def test_the_namespace_id_travels_with_the_title(self):
        op = answers({"query": {"allpages": [{"title": "Category:X"}]}})
        titles, _c = mediawiki.mediawiki_titles("http://w/", {14: "Category"}, opener=op)
        self.assertEqual(titles, [(14, "Category:X")])

    def test_only_ns_limits_what_is_asked_for(self):
        op = answers({"query": {"allpages": []}})
        mediawiki.mediawiki_titles("http://w/", {0: "Main", 14: "Category"}, only_ns={14}, opener=op)
        self.assertEqual(len(op.seen), 1)
        self.assertIn("apnamespace=14", op.seen[0])

    def test_progress_is_a_callback(self):
        seen = []
        op = answers({"query": {"allpages": [{"title": "A"}]}})
        mediawiki.mediawiki_titles("http://w/", {0: "Main"}, opener=op,
                                report=lambda *a: seen.append(a))
        self.assertEqual(seen[-1][2], 1)          # one page reported for that namespace


class TestMediaWikiImages(unittest.TestCase):
    def test_it_collects_the_inventory(self):
        op = answers({"query": {"allimages": [{"name": "a.png", "size": 10}]},
                      "continue": {"aicontinue": "b"}},
                     {"query": {"allimages": [{"name": "b.png", "size": 20}]}})
        imgs, complete = mediawiki.mediawiki_images("http://w/", opener=op)
        self.assertEqual([i["name"] for i in imgs], ["a.png", "b.png"])
        self.assertTrue(complete)

    def test_A_TRUNCATED_LIST_SAYS_SO(self):
        op = answers({"query": {"allimages": [{"name": "a.png"}]},
                      "continue": {"aicontinue": "b"}},
                     urllib.error.HTTPError("http://w/", 503, "busy", {}, None))
        imgs, complete = mediawiki.mediawiki_images("http://w/", tries=1, opener=op,
                                                 sleep=lambda _s: None)
        self.assertEqual(len(imgs), 1)
        self.assertFalse(complete)

    def test_it_asks_for_the_fields_a_check_needs(self):
        op = answers({"query": {"allimages": []}})
        mediawiki.mediawiki_images("http://w/", opener=op)
        for field in ("url", "size", "sha1", "mime"):
            self.assertIn(field, urllib.parse.unquote(op.seen[0]))


class TestMediaWikiFilename(unittest.TestCase):
    """A title is not a filename, and the difference has to be recorded."""

    def test_an_ordinary_title(self):
        self.assertEqual(mediawiki.mediawiki_filename("Norsk Data"), ("Norsk Data.wiki", False))

    def test_forbidden_characters_become_underscores(self):
        name, changed = mediawiki.mediawiki_filename('A:B"C|D?E*F')
        self.assertEqual(name, "A_B_C_D_E_F.wiki")
        self.assertTrue(changed)

    def test_a_backslash_is_not_a_directory(self):
        self.assertEqual(mediawiki.mediawiki_filename("A\\B")[0], "A_B.wiki")

    def test_THE_SLASH_IS_REPLACED_BUT_NOT_REPORTED(self):
        # Pinned rather than endorsed. A title with a slash must become one file -- otherwise a
        # page turns into a directory -- but it does not reach RENAMED.txt, whose heading says it
        # lists titles that could not be filenames. Nothing is LOST: the manifest carries the real
        # title for every page. The list is simply shorter than its heading claims.
        name, changed = mediawiki.mediawiki_filename("A/B")
        self.assertEqual(name, "A_B.wiki")
        self.assertFalse(changed)

    def test_A_TRAILING_DOT_OR_SPACE_IS_MADE_VISIBLE(self):
        # Windows drops it while OPENING, so the name silently becomes a different name.
        self.assertEqual(mediawiki.mediawiki_filename("Trailing.")[0], "Trailing_.wiki")
        self.assertEqual(mediawiki.mediawiki_filename("Trailing ")[0], "Trailing_.wiki")
        self.assertTrue(mediawiki.mediawiki_filename("Trailing.")[1])

    def test_a_reserved_device_name_is_escaped(self):
        for title in ("CON", "com1", "LPT9", "NUL.txt"):
            name, changed = mediawiki.mediawiki_filename(title)
            self.assertTrue(name.startswith("_"), title)
            self.assertTrue(changed, title)

    def test_a_name_merely_containing_one_is_left_alone(self):
        self.assertEqual(mediawiki.mediawiki_filename("CONTROL")[0], "CONTROL.wiki")
        self.assertEqual(mediawiki.mediawiki_filename("Falcon")[0], "Falcon.wiki")

    def test_A_LONG_TITLE_KEEPS_A_DIGEST_SO_TWO_DO_NOT_COLLIDE(self):
        # Truncation alone overwrites one page with another, silently, when two long titles share
        # a prefix.
        a = mediawiki.mediawiki_filename("Z" * 300)[0]
        b = mediawiki.mediawiki_filename("Z" * 300 + "different ending")[0]
        self.assertNotEqual(a, b)
        self.assertLess(len(a.encode("utf-8")), 200)

    def test_THE_LIMIT_IS_ON_BYTES_NOT_CHARACTERS(self):
        # A title in a non-Latin script reaches the limit at a third of the length, and a path
        # that is legal by character count can still be refused by the filesystem.
        title = "æ" * 120                    # 240 bytes, 120 characters
        self.assertLess(len(mediawiki.mediawiki_filename(title)[0].encode("utf-8")), 200)

    def test_the_extension_can_be_dropped_for_something_that_is_not_a_page(self):
        # An uploaded file already has its own extension; appending .wiki and cutting it off
        # again, which this replaced, was one line away from cutting five real characters.
        self.assertEqual(mediawiki.mediawiki_filename("photo.jpg", ext="")[0], "photo.jpg")


class TestThePageLimitNoTestTouched(unittest.TestCase):
    """One export no test mentioned, measured 2026-09-24. No caller outside mediawiki.py."""

    def test_it_is_the_API_S_OWN_CEILING_and_a_string(self):
        """500 is what MediaWiki allows an anonymous client per request. It is a STRING because
        it goes straight into a query value -- an int here would be formatted at every call site
        instead of once, and the first one to forget would send `limit=500.0`."""
        self.assertEqual(mediawiki.MEDIAWIKI_PAGE_LIMIT, "500")
        self.assertIsInstance(mediawiki.MEDIAWIKI_PAGE_LIMIT, str)

    def test_AND_IT_REACHES_THE_QUERY(self):
        """A constant nothing sends is a constant nobody obeys.

        The first version of this test asserted that a word appeared in a docstring -- which is
        prose about the code, not the code. It failed because the docstring says "complete"
        rather than "continue", and it would have passed just as happily if the limit were never
        sent at all.
        """
        seen = []

        def opener(req, **_kw):
            seen.append(req.full_url)
            return FakeResponse(json.dumps({"query": {"allpages": []}}).encode("utf-8"))

        mediawiki.mediawiki_titles("http://w/api.php", {0: ""}, opener=opener)
        self.assertTrue(seen)
        self.assertIn("=" + mediawiki.MEDIAWIKI_PAGE_LIMIT, seen[0])

if __name__ == "__main__":
    unittest.main()
