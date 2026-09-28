#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The two halves of the imposter scan, and above all that they do not overlap.

The default scan reads every file whose extension is one where markup does NOT belong.
`--pages` reads exactly the complement -- the files where markup is expected -- and reports the
ones whose own <title> announces a failure. Between them they must cover every file once, and
the inversion that achieves it is a single `!=` in jobs_for(). A `==` there, or a forgotten
`markup=` at the call site, produces a scan that looks like it ran and reads the wrong half.

NOTHING HERE TOUCHES THE COLLECTION. The tree is built in a temporary directory, with the four
shapes that matter: an error page under a name it is entitled to, a real page beside it under the
same extension, markup under a binary name, and a file that is not markup at all.
"""
import contextlib
import io
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("find-html-imposters")


@contextlib.contextmanager
def weak(on):
    """--weak, as the workers see it. It is a list because a rebind in main() would not reach
    them, so a test that sets it must put it back."""
    before = TOOL.WEAK_TOO[0]
    TOOL.WEAK_TOO[0] = on
    try:
        yield
    finally:
        TOOL.WEAK_TOO[0] = before

# The real titles, from spider.seds.org/ngc/, measured 2026-09-27.
ERROR_PAGE = b"<!DOCTYPE html><html><head><title>NGC Error !</title></head><body>x</body></html>"
REAL_PAGE = (b"<!DOCTYPE html><html><head><title>Digital Sky Survey image</title></head>"
             b"<body>x</body></html>")
NOT_MARKUP = b"%PDF-1.4\nnot a page at all\n"

FILES = {
    "ngc/ngc.cgi": ERROR_PAGE,          # right name, admitted failure  -> --pages
    "ngc/ngcdss.cgi": REAL_PAGE,        # right name, genuine page      -> neither
    "docs/page.html": REAL_PAGE,        # right name, genuine page      -> neither
    "bin/smp0951.bin": ERROR_PAGE,      # WRONG name                    -> default scan
    "docs/manual.pdf": NOT_MARKUP,      # not markup                    -> neither
}


class TheTwoHalvesCoverEveryFileOnce(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="imposters-")
        base = os.path.join(self.root, "an-archive")
        for rel, blob in FILES.items():
            full = os.path.join(base, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with io.open(full, "wb") as fh:
                fh.write(blob)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def picked(self, markup):
        return sorted(rel for _a, rel, _f, _s in
                      TOOL.jobs_for(self.root, ["an-archive"], markup=markup))

    def test_the_default_half_reads_the_non_markup_names(self):
        self.assertEqual(self.picked(markup=False), ["bin/smp0951.bin", "docs/manual.pdf"])

    def test_and_pages_reads_exactly_the_other_ones(self):
        self.assertEqual(self.picked(markup=True),
                         ["docs/page.html", "ngc/ngc.cgi", "ngc/ngcdss.cgi"])

    def test_TOGETHER_THEY_ARE_EVERY_FILE_AND_NEITHER_IS_EMPTY(self):
        """The property the `!=` in jobs_for() exists for.

        A `==` there gives two scans that read the same half and leave the other unread, and
        both still print a plausible report. Overlap would double-report; a gap would hide a
        file from both.
        """
        a, b = self.picked(markup=False), self.picked(markup=True)
        self.assertEqual(sorted(a + b), sorted(FILES))
        self.assertEqual(set(a) & set(b), set())
        self.assertTrue(a and b)

    def test_markup_defaults_to_the_original_behaviour(self):
        # The default scan is what every existing caller and every recorded run used.
        self.assertEqual(sorted(rel for _a, rel, _f, _s in
                                TOOL.jobs_for(self.root, ["an-archive"])),
                         self.picked(markup=False))


class WhatEachHalfReports(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="imposters-one-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def job(self, name, blob):
        full = os.path.join(self.dir, name)
        with io.open(full, "wb") as fh:
            fh.write(blob)
        return ("an-archive", name, full, len(blob))

    def test_A_WRONG_PAGE_UNDER_A_RIGHT_NAME_IS_ONLY_SEEN_BY_pages(self):
        """The whole reason --pages exists. `.cgi` is in MARKUP_EXT, so the default scan never
        reads the file -- correctly, because HTML under a `.cgi` name is expected.

        `NGC Error !` is WEAK evidence, so it takes --weak. See the STOCK/WEAK note in
        common.py: over the whole collection the loose vocabulary finds 2 357 pages and about
        2 275 of them are IBM manuals about error codes.
        """
        job = self.job("ngc.cgi", ERROR_PAGE)
        self.assertIn(".cgi", TOOL.MARKUP_EXT)
        with weak(True):
            got = TOOL.inspect_page(job)
        self.assertEqual((got["kind"], got["title"]), ("error?", "NGC Error !"))

    def test_AND_A_WEAK_FINDING_IS_SILENT_WITHOUT_weak(self):
        """A sweep of the collection on weak evidence is 2 357 findings of which 2 275 are
        documents. The default has to be the strong rule or the report is not one."""
        self.assertIsNone(TOOL.inspect_page(self.job("ngc.cgi", ERROR_PAGE)))

    def test_A_STOCK_FINDING_NEEDS_NO_FLAG_AND_IS_MARKED_WITHOUT_A_QUESTION_MARK(self):
        """`404 Not Found` is 67 of the 82 stock findings in the collection. The `?` on a weak
        kind is what tells a reader which half of the table a row came from."""
        stock = b"<!DOCTYPE html><html><head><title>404 Not Found</title></head></html>"
        got = TOOL.inspect_page(self.job("gone.cgi", stock))
        self.assertEqual((got["kind"], got["title"]), ("not found", "404 Not Found"))

    def test_and_the_genuine_page_beside_it_is_not_reported(self):
        self.assertIsNone(TOOL.inspect_page(self.job("ngcdss.cgi", REAL_PAGE)))

    def test_a_page_that_is_not_markup_is_not_reported_either(self):
        self.assertIsNone(TOOL.inspect_page(self.job("manual.pdf", NOT_MARKUP)))

    def test_AN_UNREADABLE_FILE_IS_SAID_SO_AND_NOT_DROPPED(self):
        """Silence and "nothing wrong" must not be the same answer -- inspect() has said this
        since it was written, and the new half has to agree or a scan can lose files quietly."""
        missing = ("an-archive", "gone.cgi", os.path.join(self.dir, "gone.cgi"), 0)
        self.assertEqual(TOOL.inspect_page(missing)["kind"], "UNREADABLE")

    def test_the_default_half_still_reports_markup_under_a_binary_name(self):
        got = TOOL.inspect(self.job("smp0951.bin", ERROR_PAGE))
        self.assertEqual(got["title"], "NGC Error !")

    def test_IT_USES_THE_LIBRARY_AND_NOT_A_SIXTH_PRIVATE_COPY(self):
        """Both halves read the title through common.page_title(), which had five hand-rolled
        copies across this directory until 2026-09-27. The point of removing them is that a new
        one cannot creep back in unnoticed.

        THE SENTINEL GOES ON THE TOOL'S NAME, NOT THE LIBRARY'S, and the first version of this
        test put it on the library's and failed. `from common import page_title` binds the
        function into THIS module's namespace at import time, so patching common changes nothing
        here -- which is also exactly why the shadowing rule in common_test.py is worth having:
        a local definition of an imported name is invisible from the library's side.
        """
        real = TOOL.page_title
        try:
            TOOL.page_title = lambda head: "SENTINEL"
            self.assertEqual(TOOL.inspect(self.job("x.bin", ERROR_PAGE))["title"], "SENTINEL")
        finally:
            TOOL.page_title = real
        self.assertIs(TOOL.page_title, common.page_title)


if __name__ == "__main__":
    unittest.main()
