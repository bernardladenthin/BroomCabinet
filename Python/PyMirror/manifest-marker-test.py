#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The completion marker manifest-fetch.py writes, and the one it must refuse to touch.

WHY THE MARKER MATTERS AT ALL. Everything downstream keys off `.mirror-complete`: catalogue.py
takes an archive's file and byte counts from it, and `mirror.py --verify` compares the tree
against the two figures in it. An archive fetched from a URL list and never crawled has no
marker unless this tool writes one, and then it reads `None files, 0.0 GB` -- on disk and
invisible to every report. That hole was found and closed once already, for the Internet Archive
items in ia-item-fetch.py; this is the same hole in the next tool along.

AND WHY IT IS OPT-IN. A manifest fetch is often a TOP-UP of an archive mirror.py crawled, whose
marker is that crawl's record of its own run -- its duration, its failure count, its name.
Replacing it would be this tool signing somebody else's work.

NOTHING HERE TOUCHES THE COLLECTION. Every case builds an archive in a temporary directory.
"""
import importlib.util
import io
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


TOOL = load("manifest-fetch")

BASE = "https://example.invalid/ACME/"
ARCHIVE = "an-archive"
FILES = {"HARDWARE/drive.pdf": b"a service manual" * 40,
         "HARDWARE/printer.pdf": b"another one" * 30,
         "CATALOGUE-PAGE.html": b"<html>the page the list came from</html>"}


class TheMarkerItWrites(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="marker-")
        self.dir = os.path.join(self.root, ARCHIVE)
        for rel, blob in FILES.items():
            full = os.path.join(self.dir, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with io.open(full, "wb") as fh:
                fh.write(blob)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def marker(self):
        with io.open(os.path.join(self.dir, common.COMPLETE_MARKER), encoding="utf-8") as fh:
            return fh.read()

    def write(self, named=2, gone=0, failed=0):
        TOOL.write_marker(self.dir, ARCHIVE, BASE, "a-url-list.txt", named, gone, failed)

    def test_it_writes_one_where_there_was_none(self):
        self.write()
        self.assertTrue(os.path.isfile(os.path.join(self.dir, common.COMPLETE_MARKER)))

    def test_THE_COUNTS_COME_FROM_THE_SAME_FUNCTION_THAT_LATER_CHECKS_THEM(self):
        """ia-item-fetch.py records why: a second counter with its own idea of what an own file
        is makes a marker that is wrong from the moment it is written, and an archive that
        reports a mismatch forever over a discrepancy between two pieces of our own code."""
        self.write()
        n, b = common.scan_tree(self.dir)
        self.assertIn("files         %d" % n, self.marker())
        self.assertIn("bytes         %d" % b, self.marker())

    def test_and_the_marker_itself_is_not_counted(self):
        self.write()
        n, _b = common.scan_tree(self.dir)
        self.assertEqual(n, len(FILES))

    def test_IT_SAYS_THE_CLAIM_IS_WEAKER_THAN_A_CRAWLS(self):
        """Completeness here means "everything the list named", and the list is only as complete
        as whatever produced it. A marker that did not say so would be read as a crawl's."""
        self.write()
        text = self.marker()
        self.assertIn("NOT crawled", text)
        self.assertIn("PROVENANCE.md", text)

    def test_it_records_what_the_list_named_and_what_went_wrong(self):
        self.write(named=34, gone=2, failed=1)
        text = self.marker()
        self.assertIn("named-by-the-list 34", text)
        self.assertIn("gone-from-the-source 2", text)
        self.assertIn("failed        1", text)

    def test_IT_REFUSES_TO_REPLACE_A_MARKER_IT_DID_NOT_WRITE(self):
        """A manifest fetch is often a top-up of a CRAWLED archive, and that marker is mirror.py's
        record of its own run -- its duration, its failure count. Overwriting it would throw that
        away and put this tool's name on it."""
        theirs = "archive       an-archive\nsource        somewhere\nfiles         999\n"
        with io.open(os.path.join(self.dir, common.COMPLETE_MARKER), "w",
                     encoding="utf-8") as fh:
            fh.write(theirs)
        self.write()
        self.assertEqual(self.marker(), theirs)

    def test_AND_IT_DOES_REPLACE_ITS_OWN(self):
        """The first version refused every existing marker, so a second run over the same
        archive -- four more files added to a list-fetched tree on 2026-09-27 -- would have left
        the counts describing the tree as it was before. A stale marker is worse than a missing
        one: --verify then reports a mismatch that is nobody's fault.

        Ours is recognised by a field only this tool writes. Not by the prose, which a person
        may edit, and not by a timestamp, which says nothing about who.
        """
        self.write(named=2)
        self.assertIn("named-by-the-list 2", self.marker())
        with io.open(os.path.join(self.dir, "HARDWARE", "third.pdf"), "wb") as fh:
            fh.write(b"one more file")
        self.write(named=3)
        text = self.marker()
        self.assertIn("named-by-the-list 3", text)
        n, _b = common.scan_tree(self.dir)
        self.assertIn("files         %d" % n, text)

    def test_and_the_field_it_recognises_itself_by_is_really_written(self):
        # If the name of that field ever changed, the tool would start refusing its own markers
        # and every re-run would silently leave a stale one.
        self.write()
        self.assertIn("named-by-the-list",
                      common.read_marker(os.path.join(self.dir, common.COMPLETE_MARKER)))

    def test_the_format_is_the_librarys_and_not_this_tools(self):
        """The header format lived in two files once and they agreed on the columns and disagreed
        on the line ending, which is how 66 markers in this collection came to be CRLF and 31 LF.
        """
        self.write()
        fields = common.read_marker(os.path.join(self.dir, common.COMPLETE_MARKER))
        self.assertEqual(fields.get("archive"), ARCHIVE)
        self.assertEqual(fields.get("source"), BASE)


if __name__ == "__main__":
    unittest.main()
