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
import gzip
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


class ASitemapArrivesInThreeShapes(unittest.TestCase):
    """read_sitemap, in find-sitemaps.py. All three shapes were met within one afternoon.

    WHY IT IS A FUNCTION AT ALL. On 2026-10-02 the four remaining sitemap INDEXES were followed by
    hand, in a throwaway script, because the tool reported an index and declined to follow it. The
    script knew one shape -- XML with <loc> -- and it also skipped the tool's page/file/directory
    classification. Both omissions produced a wrong number in the same run:

        bretjohnson        40896 named under the base, 50 held, MISSING 40896

    and the 40 896 are CMS pages called `1000032207`, not files. internal() would have counted them
    as pageish; the hand-written loop never called it. THE DEFECT WAS IN THE HAND-WRITTEN SCRIPT
    AND NOT IN THE TOOL -- which is the argument for the tool doing the following, so that one
    classification serves every caller.

    The gzipped-plain-text shape is the one that could have produced another clean zero: ftp.zx.net.nz
    publishes `_ftp_sitemap_part_aa.txt.gz`, and no <loc> regex will ever find anything in it.
    """

    def setUp(self):
        self.fs = common.load_peer("find-sitemaps.py", "_find_sitemaps", HERE)

    XML = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.org/pub/a.tardist</loc></url>
  <url><loc>https://example.org/pub/b.txt</loc></url>
</urlset>
"""

    TEXT = """https://example.org/pub/a.tardist
https://example.org/pub/b.txt
"""

    def test_xml_with_loc_elements(self):
        got = self.fs.read_sitemap(self.XML.encode("utf-8"))
        self.assertEqual(got, ["https://example.org/pub/a.tardist",
                               "https://example.org/pub/b.txt"])

    def test_plain_text_one_url_per_line(self):
        """The standard permits it and ftp.zx.net.nz uses it. No <loc> to find."""
        self.assertNotIn("<loc", self.TEXT)
        got = self.fs.read_sitemap(self.TEXT.encode("utf-8"))
        self.assertEqual(got, ["https://example.org/pub/a.tardist",
                               "https://example.org/pub/b.txt"])

    def test_GZIPPED_plain_text_which_is_what_zx_actually_serves(self):
        got = self.fs.read_sitemap(gzip.compress(self.TEXT.encode("utf-8")))
        self.assertEqual(got, ["https://example.org/pub/a.tardist",
                               "https://example.org/pub/b.txt"])

    def test_gzipped_xml_too(self):
        got = self.fs.read_sitemap(gzip.compress(self.XML.encode("utf-8")))
        self.assertEqual(len(got), 2)

    def test_gzip_IS_RECOGNISED_BY_MAGIC_AND_NOT_BY_THE_NAME(self):
        """read_sitemap is handed bytes and never sees the url, deliberately.

        A server may decompress on the way out, so `part_aa.txt.gz` can arrive as plain text; and
        a part with no `.gz` in its name can arrive gzipped under Content-Encoding. The bytes are
        the only thing that knows.
        """
        self.assertEqual(self.fs.GZIP_MAGIC, bytes([0x1F, 0x8B]))
        plain_despite_the_name = self.fs.read_sitemap(self.TEXT.encode("utf-8"))
        self.assertEqual(len(plain_despite_the_name), 2)

    def test_a_line_that_is_not_just_a_url_is_not_an_entry(self):
        """A text sitemap is urls and nothing else, so prose containing one does not count."""
        prose = """see https://example.org/pub/a.tardist for details
https://example.org/pub/b.txt
# https://example.org/pub/c.txt
"""
        self.assertEqual(self.fs.read_sitemap(prose.encode("utf-8")),
                         ["https://example.org/pub/b.txt"])

    def test_an_empty_part_gives_an_empty_list_and_does_not_raise(self):
        self.assertEqual(self.fs.read_sitemap(b""), [])


class AnIndexIsFollOwedOnlyWhenAsked(unittest.TestCase):
    """42 parts for one archive is a decision about somebody else's bandwidth, not a detail."""

    def test_the_flag_exists_and_defaults_to_off(self):
        out = subprocess.run([sys.executable, os.path.join(HERE, "find-sitemaps.py"), "--help"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        self.assertIn("--follow-index", out)
        self.assertIn("Off by default", out)

    def test_without_the_flag_the_line_says_how_to_follow(self):
        """A report that only says "not followed" leaves the reader to find the flag."""
        with io.open(os.path.join(HERE, "find-sitemaps.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("pass --follow-index", src)


class NumericCmsPagesAreNotFiles(unittest.TestCase):
    """The bretjohnson defect, pinned on the classifier that the hand-written loop bypassed.

    bretjohnson.us lists 40 896 urls of the shape `/1000032207` -- a CMS page id. They answer 200
    with `text/html` and NO Content-Length. Counting them as files turned an archive of 50 held
    files into one "missing 40 896", which is the same category error that ibm-redbooks produced
    earlier the same day.
    """

    def setUp(self):
        self.fs = common.load_peer("find-sitemaps.py", "_find_sitemaps", HERE)
        self.tmp = tempfile.mkdtemp(prefix="pymirror-cms-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_bare_number_is_pageish(self):
        base = "https://bretjohnson.us/"
        locs = [base + "1000032207", base + "100037841", base + "1000591577"]
        inside, outside, pageish, dirish = self.fs.internal(locs, base, self.tmp)
        self.assertEqual(pageish, 3)
        self.assertEqual(len(inside), 0)

    def test_and_a_real_filename_beside_them_still_is_one(self):
        """The rule must not simply refuse everything -- that would hide real gaps."""
        base = "https://bretjohnson.us/"
        locs = [base + "1000032207", base + "programs/setup.zip"]
        inside, outside, pageish, dirish = self.fs.internal(locs, base, self.tmp)
        self.assertEqual(pageish, 1)
        self.assertEqual(sorted(inside), ["programs/setup.zip"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
