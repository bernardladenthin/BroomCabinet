#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What `recheck-decisions.py` concludes from an answer, without asking any host.

THE QUESTION IT ANSWERS is not "does this name resolve" but "is the archive back". A lapsed
domain is bought, parked, and answers 200 forever; a decommissioned box answers 200 with 44
bytes of Apache's stock "It works!". Both would put a permanent `!!` next to a host whose own
marker says it is gone.

WHY THIS FILE EXISTS. The vocabulary behind that judgement -- PLACEHOLDER_TITLES, STUB_BODIES,
the "too small to be a page" rule -- moved into common.py on 2026-09-27 and is tested there. What
was NOT tested is the wiring in this tool: that it passes the title it already read, that it
tells `stub` from `parked` in the output, and above all that the `<h1>` fallback page_title()
gained on the same day did not change a verdict. It did change one thing, in the wanted
direction, and that is pinned below.

NO NETWORK. `http_open` and `gethostbyname` are replaced in the tool's own namespace, which is
where `from common import ...` binds them.
"""
import importlib.util
import os
import sys
import unittest


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TOOL = load("recheck-decisions")

# Real shapes. The first is Apache's stock page as `download.aixtools.net` served it; the second
# is the form `www.spscicomp.org` answered with after the IBM HPC user group's domain lapsed.
IT_WORKS = b"<html><body><h1>It works!</h1></body></html>"
BLUEHOST = (b"<html><head><title>Welcome spscicomp.org - BlueHost.com</title></head><body>"
            + b"<p>filler</p>" * 40 + b"</body></html>")
AUTOINDEX = (b"<html><head><title>Index of /pub</title></head><body><h1>Index of /pub</h1>"
             + b'<a href="x">x</a>' * 40 + b"</body></html>")
AUTOINDEX_NO_TITLE = (b"<html><body><h1>Index of /pub</h1>"
                      + b'<a href="x">x</a>' * 40 + b"</body></html>")
REAL_SITE = (b"<html><head><title>Sun Hardware Reference</title></head><body>"
             + b"<p>real content</p>" * 40 + b"</body></html>")


class Answer(object):
    """The little of urlopen's result that probe() uses."""

    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def read(self, n):
        return self.body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class WhatItConcludes(unittest.TestCase):

    def setUp(self):
        self.real_open = TOOL.http_open
        self.real_dns = TOOL.socket.gethostbyname
        TOOL.socket.gethostbyname = lambda host: "192.0.2.1"

    def tearDown(self):
        TOOL.http_open = self.real_open
        TOOL.socket.gethostbyname = self.real_dns

    def probe(self, body, status=200):
        TOOL.http_open = lambda url, timeout=None, **kw: Answer(body, status)
        return TOOL.probe("host.invalid")

    def test_a_real_site_is_alive_and_shows_its_title(self):
        state, alive = self.probe(REAL_SITE)
        self.assertTrue(alive)
        self.assertIn("Sun Hardware Reference", state)
        self.assertNotIn("[STUB]", state)
        self.assertNotIn("[PARKED?]", state)

    def test_A_STUB_IS_NOT_A_SITE(self):
        """`download.aixtools.net` answers 200 with 44 bytes of Apache's stock page and no title
        at all, so a title-only test calls it alive and puts a permanent `!!` on an archive whose
        own marker says the origin is gone."""
        state, alive = self.probe(IT_WORKS)
        self.assertFalse(alive)
        self.assertIn("[STUB]", state)

    def test_AND_A_PARKED_DOMAIN_IS_NOT_ONE_EITHER_BUT_IS_SAID_DIFFERENTLY(self):
        """They mean different things -- a machine with nothing on it, against somebody else's
        machine -- so the output distinguishes them."""
        state, alive = self.probe(BLUEHOST)
        self.assertFalse(alive)
        self.assertIn("[PARKED?]", state)
        self.assertNotIn("[STUB]", state)

    def test_AN_AUTOINDEX_IS_THE_BEST_ANSWER_THERE_IS(self):
        """The rule most worth re-reading: an Apache autoindex means there are files to walk. A
        placeholder list that swallowed it would silence exactly the finding this tool makes."""
        state, alive = self.probe(AUTOINDEX)
        self.assertTrue(alive)
        self.assertIn("Index of /pub", state)

    def test_THE_H1_FALLBACK_IS_WHAT_MADE_THAT_TITLE_VISIBLE(self):
        """The behaviour this tool GAINED on 2026-09-27, and the reason this file exists.

        An autoindex names itself in <h1> and nothing else. Until page_title() fell back to the
        heading, such a host was reported with no title at all -- alive, correctly, but silent
        about the one thing worth reading. It now reads `Index of /pub`.
        """
        state, alive = self.probe(AUTOINDEX_NO_TITLE)
        self.assertTrue(alive)
        self.assertIn("Index of /pub", state)

    def test_and_the_fallback_cannot_make_a_live_host_look_dead(self):
        # The other direction of the same change: no <h1> text is in PLACEHOLDER_TITLES.
        for body in (AUTOINDEX, AUTOINDEX_NO_TITLE, REAL_SITE):
            _state, alive = self.probe(body)
            self.assertTrue(alive, body[:40])

    def test_a_refusal_is_not_a_disappearance(self):
        import urllib.error

        def raising(url, timeout=None, **kw):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

        TOOL.http_open = raising
        state, alive = TOOL.probe("host.invalid")
        self.assertTrue(alive)
        self.assertIn("refusing, not gone", state)

    def test_AND_A_5XX_IS_NOT_A_RETURN(self):
        """HTTP 522 is Cloudflare's own code for "I resolved, the origin did not answer". DNS and
        a CDN survive the machine behind them for years."""
        import urllib.error

        def raising(url, timeout=None, **kw):
            raise urllib.error.HTTPError(url, 522, "Origin down", {}, None)

        TOOL.http_open = raising
        state, alive = TOOL.probe("host.invalid")
        self.assertFalse(alive)
        self.assertIn("not a return", state)

    def test_no_dns_is_decided_before_anything_is_asked(self):
        TOOL.socket.gethostbyname = lambda host: (_ for _ in ()).throw(OSError("gaierror"))
        state, alive = TOOL.probe("host.invalid")
        self.assertFalse(alive)
        self.assertEqual(state, "no DNS")

    def test_it_uses_the_librarys_judgement_and_not_its_own(self):
        """The tables lived here until 2026-09-27, beside a looser copy of the same question in
        find-html-imposters.py. Two files that could learn different vocabularies about one
        thing is the shape this collection keeps removing."""
        real = TOOL.looks_like_a_placeholder_page
        try:
            TOOL.looks_like_a_placeholder_page = lambda body, title=None: ("stub", "SENTINEL")
            state, alive = self.probe(REAL_SITE)
            self.assertFalse(alive)
            self.assertIn("[STUB]", state)
        finally:
            TOOL.looks_like_a_placeholder_page = real


if __name__ == "__main__":
    unittest.main()
