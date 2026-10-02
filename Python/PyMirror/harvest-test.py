#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What a stored page NAMES, and the absolute link that was thrown away for a week.

WHAT HAPPENED, dreamlandbbs-os2, 2026-10-02. pages-to-urllist.py read 61 stored index pages and
reported:

    61 stored pages read, 2 targets named ... 0 FILES NAMED AND NOT ON DISK

over an archive that holds those 61 pages and NOT ONE of the 5 648 files they name -- 14.05 GB by
the sizes the pages state themselves. A clean zero, which is the one answer this collection has
taught itself to distrust, and it stood for five days while the archive was treated as having
nothing outstanding.

THE CAUSE WAS A PRIVATE SKIP-LIST. The tool carried `"http://"`, `"https://"` and `"//"` among the
schemes it refused, so it discarded every ABSOLUTE url -- and MBSE, which generates these pages,
spells out the host on every single file link:

    <A HREF='http://www.dreamlandbbs.com/gfd/apparc/PMZppr18.zip'>

A link that names its own site is not an offsite link. What decides offsite is the BASE, and the
loop already made that test three lines further down; the scheme check did the same job a second
time and got it wrong, because `http://` says nothing about which host follows it.

AND THE REGISTER ALREADY KNEW. mirror.py's HTML_CRAWL entry for this very archive says "MBSE writes
every file link as http://www.dreamlandbbs.com/gfd/<area>/<file>", which is why the CRAWLER was
given allow_up for it. The crawler was fixed; the harvester kept its own list and was not. A
hazard recorded next to one tool is not a check on the next one.

These tests pin the distinction rather than the fix: an absolute link UNDER the base is named, an
absolute link to another host is counted outside, and neither decision is made from the spelling.

No network. Pages are written into a temporary directory.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

BASE = "http://www.example.invalid/gfd/"


class Harvest(object):
    """One archive directory with pages in it, harvested through the real tool."""

    ARCHIVE = "tvsat-cpc710"          # a registered name; --archive is checked against the register

    def __init__(self, pages):
        self.root = tempfile.mkdtemp()
        self.dir = os.path.join(self.root, self.ARCHIVE)
        os.makedirs(self.dir)
        for rel, body in pages.items():
            full = os.path.join(self.dir, *rel.split("/"))
            d = os.path.dirname(full)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(full, "w", encoding="utf-8") as fh:
                fh.write(body)

    def run(self, *extra):
        self.out = os.path.join(self.root, "list.txt")
        res = subprocess.run(
            [sys.executable, os.path.join(HERE, "pages-to-urllist.py"),
             "--root", self.root, "--archive", self.ARCHIVE, "--base", BASE,
             "--out", self.out] + list(extra),
            capture_output=True, text=True, cwd=HERE)
        self.text = res.stdout + res.stderr
        if os.path.exists(self.out):
            with io.open(self.out, encoding="utf-8") as fh:
                self.named = [ln.strip() for ln in fh
                              if ln.strip() and not ln.startswith("#")]
        else:
            self.named = []
        return self

    def rels(self):
        return sorted(u[len(BASE):] for u in self.named if u.startswith(BASE))

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def page(*hrefs):
    return "<HTML><BODY>" + "".join("<A HREF='%s'>x</A>" % h for h in hrefs) + "</BODY></HTML>"


class AnAbsoluteSelfLinkIsAFile(unittest.TestCase):
    """THE REGRESSION. These are the shapes that were silently discarded."""

    def harvest(self, pages, *extra):
        self.h = Harvest(pages).run(*extra)
        return self.h

    def tearDown(self):
        if getattr(self, "h", None):
            self.h.close()

    def test_the_mbse_shape_itself(self):
        """Upper-case HREF, single quotes, the host spelled out. Verbatim from the archive."""
        h = self.harvest({"apparc/index.html":
                          page("http://www.example.invalid/gfd/apparc/PMZppr18.zip")})
        self.assertEqual(h.rels(), ["apparc/PMZppr18.zip"])

    def test_a_page_of_nothing_but_absolute_self_links_is_NOT_zero(self):
        """The exact failure: 5 648 files reported as 0 because every link named its own host."""
        many = ["%sapparc/f%02d.zip" % (BASE, n) for n in range(40)]
        h = self.harvest({"apparc/index.html": page(*many)})
        self.assertEqual(len(h.rels()), 40)
        self.assertIn("40 FILES NAMED AND NOT ON DISK", h.text)

    def test_https_spelling_of_the_same_site_is_still_the_same_site(self):
        """A page may write https where the archive's base says http, and both are the site.

        This failed when the test was written: the tool compared against the registered base with
        a plain startswith, so the scheme flip made a file its own site serves look like somebody
        else's. The folding now lives in common.site_prefixes, which find-sitemaps.py needed the
        same day for the apex-vs-www half of the same mistake."""
        h = self.harvest({"a/index.html": page("https://www.example.invalid/gfd/a/x.zip")})
        self.assertEqual(h.rels(), ["a/x.zip"])

    def test_the_apex_spelling_too(self):
        """The register says www; the page may not."""
        h = self.harvest({"a/index.html": page("http://example.invalid/gfd/a/x.zip")})
        self.assertEqual(h.rels(), ["a/x.zip"])

    def test_a_protocol_relative_link_is_not_a_scheme_to_refuse(self):
        h = self.harvest({"a/index.html": page("//www.example.invalid/gfd/a/y.zip")})
        self.assertEqual(h.rels(), ["a/y.zip"])

    def test_a_relative_link_still_works(self):
        """The shape that always worked must not be broken by widening the other one."""
        h = self.harvest({"a/index.html": page("z.zip", "../b/w.zip")})
        self.assertEqual(h.rels(), ["a/z.zip", "b/w.zip"])


class TheSharedFoldingItRestsOn(unittest.TestCase):
    """common.site_prefixes / under_site, which both this tool and find-sitemaps.py now use."""

    def test_every_spelling_of_one_site(self):
        got = set(common.site_prefixes("https://ardent-tool.com/"))
        self.assertEqual(got, {"https://ardent-tool.com/", "http://ardent-tool.com/",
                               "https://www.ardent-tool.com/", "http://www.ardent-tool.com/"})

    def test_longest_first_so_a_deep_base_wins(self):
        """Against `/` and `/a/` for one host the shorter would glue `a/` onto every path."""
        order = common.site_prefixes("http://h.invalid/deep/path/")
        self.assertEqual(order[0], max(order, key=len))

    def test_under_site_tells_the_root_from_a_foreign_host(self):
        base = "http://www.example.invalid/gfd/"
        self.assertEqual(common.under_site(base, base), "")
        self.assertIsNone(common.under_site("http://elsewhere.invalid/x", base))
        self.assertEqual(common.under_site("https://example.invalid/gfd/a/x.zip", base), "a/x.zip")

    def test_a_lookalike_host_is_not_the_site(self):
        self.assertIsNone(common.under_site(
            "http://www.example.invalid.evil.test/gfd/x", "http://www.example.invalid/gfd/"))


class WhatDecidesOffsiteIsTheBase(unittest.TestCase):

    def tearDown(self):
        if getattr(self, "h", None):
            self.h.close()

    def harvest(self, pages):
        self.h = Harvest(pages).run()
        return self.h

    def test_another_host_is_counted_outside_and_not_named(self):
        h = self.harvest({"a/index.html": page("http://somewhere.else.invalid/x.zip")})
        self.assertEqual(h.rels(), [])
        self.assertIn("1 outside the archive", h.text)

    def test_the_same_host_above_the_base_is_also_outside(self):
        """`/index.html` on the same host is not under `/gfd/`. dreamlandbbs' nav links are these,
        and they are the two targets the broken version did report."""
        h = self.harvest({"a/index.html": page("http://www.example.invalid/index.html")})
        self.assertEqual(h.rels(), [])
        self.assertIn("1 outside the archive", h.text)

    def test_a_lookalike_host_is_outside(self):
        """`example.invalid.evil.test` starts with the host and is not the host."""
        h = self.harvest({"a/index.html":
                          page("http://www.example.invalid.evil.test/gfd/a/x.zip")})
        self.assertEqual(h.rels(), [])


class TheSchemesStillRefused(unittest.TestCase):

    def tearDown(self):
        if getattr(self, "h", None):
            self.h.close()

    def test_none_of_these_is_a_file(self):
        self.h = Harvest({"a/index.html": page(
            "#anchor", "mailto:someone@example.invalid", "javascript:void(0)",
            "data:text/plain,hello", "?sort=name", "tel:+1234", "about:blank",
            "file:///etc/passwd", "real.zip")}).run()
        self.assertEqual(self.h.rels(), ["a/real.zip"])

    def test_http_and_https_are_NOT_among_them(self):
        """Pinned against the source, so putting them back has to be deliberate."""
        with io.open(os.path.join(HERE, "pages-to-urllist.py"), encoding="utf-8") as fh:
            src = fh.read()
        skip = src.split("SKIP = (", 1)[1].split(")", 1)[0]
        for scheme in ('"http://"', '"https://"', '"//"'):
            self.assertNotIn(scheme, skip,
                             "%s is back in SKIP; an absolute self-link is a file, and what "
                             "decides offsite is the base" % scheme)


class TheListIsWrittenForTheNextTool(unittest.TestCase):
    """What comes out has to be what manifest-fetch.py accepts.

    Once the same site under another spelling is read as its own -- which is the point of the fix
    -- the raw url may say https where the register says http. manifest-fetch.py tests its list
    against `--base` and prints "OUTSIDE THE BASE, skipped" for anything else, so emitting the
    page's spelling would move the rejection one tool further along instead of removing it.
    """

    def tearDown(self):
        if getattr(self, "h", None):
            self.h.close()

    def test_every_url_written_starts_with_the_registered_base(self):
        self.h = Harvest({"a/index.html": page(
            "https://www.example.invalid/gfd/a/one.zip",     # scheme differs
            "http://example.invalid/gfd/a/two.zip",          # apex instead of www
            "three.zip")}).run()                             # plainly relative
        self.assertEqual(len(self.h.named), 3)
        for u in self.h.named:
            self.assertTrue(u.startswith(BASE), u)

    def test_a_space_in_the_name_comes_out_encoded(self):
        """The next tool puts this in an HTTP request; a raw space is not a url."""
        self.h = Harvest({"a/index.html": page("two words.zip")}).run()
        self.assertEqual(self.h.named, [BASE + "a/two%20words.zip"])

    def test_and_the_slashes_are_left_alone(self):
        self.h = Harvest({"a/index.html": page("deep/down/x.zip")}).run()
        self.assertEqual(self.h.named, [BASE + "a/deep/down/x.zip"])


class TheCountsAgreeWithTheList(unittest.TestCase):
    """The headline figure is what a reader acts on; it must describe the file written."""

    def tearDown(self):
        if getattr(self, "h", None):
            self.h.close()

    def test_the_number_printed_is_the_number_written(self):
        self.h = Harvest({"a/index.html": page(
            "%sa/one.zip" % BASE, "%sa/two.zip" % BASE,
            "http://elsewhere.invalid/three.zip")}).run()
        self.assertIn("2 FILES NAMED AND NOT ON DISK", self.h.text)
        self.assertEqual(len(self.h.named), 2)

    def test_a_file_already_held_is_not_named(self):
        h = Harvest({"a/index.html": page("%sa/have.zip" % BASE, "%sa/lack.zip" % BASE),
                     "a/have.zip": "x"})
        self.h = h.run()
        self.assertEqual(self.h.rels(), ["a/lack.zip"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
