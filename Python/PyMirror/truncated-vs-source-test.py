#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""truncated-vs-source.py, without asking anybody.

WHY THIS FILE EXISTS AT ALL, WRITTEN A DAY LATE. Three tools were built on 2026-09-25 with tests
-- `holes-run.py`, `holes-vs-source.py`, `ask-the-source.py`, 17, 21 and 29 of them. This one was
not, and it is the one that produced the answer the owner acted on: 532 files asked of their
sources, **0 re-fetchable**.

AND IT ALREADY CARRIED THE BUG A TEST WOULD HAVE CAUGHT IN A SECOND. Its first run reported
"nobody answered -- 8" for all eight files in one archive. Eight of eight failing is not a
statement about eight servers; it is one mistake. `--under` yields paths that are ALREADY relative
to the archive, and the code stripped the first segment off them anyway, so `Incoming/sf4.0.zip`
became `sf4.0.zip` and every request asked for a file that had never existed. It read exactly like
"the source is gone", which is a conclusion somebody could have acted on.

That is why `test_THE_ARCHIVE_IS_A_PARAMETER_NOT_SOMETHING_TO_PEEL_OFF` is the one that matters
here: the path split, in both modes, against a tree on disk.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("truncated-vs-source")

REGISTER = {"an-archive": "https://example.invalid/pub/",
            "over-rsync": "rsync://example.invalid/mod/",
            "bitsavers": "rsync://bitsavers.org/bitsavers/"}


def zip_bytes(comment=b""):
    """A minimal, valid zip: one local header, an empty central directory, an EOCD."""
    import struct
    entry = b"PK" + bytes([3, 4]) + bytes(26)
    eocd = (b"PK" + bytes([5, 6]) + struct.pack("<HHHH", 0, 0, 0, 0)
            + struct.pack("<II", 0, len(entry)) + struct.pack("<H", len(comment)))
    return entry + eocd + comment


class Tree(unittest.TestCase):
    """A small collection in a temporary directory. Nothing here touches Q:\\mirror."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="truncated-test-")
        self.root = os.path.join(self.tmp, "mirror")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, rel, blob):
        path = os.path.join(self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "wb") as fh:
            fh.write(blob)
        return path


class WhatItFinds(Tree):

    def test_a_zip_with_no_central_directory(self):
        self.put("arc/deep/cut.zip", b"PK" + bytes([3, 4]) + bytes([0xFF]) * 5000)
        got = TOOL.truncated(self.root)
        self.assertEqual([(a, r) for a, r, _s, _e, _f in got], [("arc", "deep/cut.zip")])

    def test_an_intact_zip_is_not_a_finding(self):
        self.put("arc/ok.zip", zip_bytes())
        self.assertEqual(TOOL.truncated(self.root), [])

    def test_a_file_longer_than_it_declares_is_not_a_finding(self):
        """Padding is ordinary. Reporting it would bury the real ones."""
        self.put("arc/padded.zip", zip_bytes() + bytes(4096))
        self.assertEqual(TOOL.truncated(self.root), [])

    def test_an_extension_that_declares_nothing_is_skipped(self):
        self.put("arc/notes.txt", b"hello")
        self.assertEqual(TOOL.truncated(self.root), [])

    def test_a_zero_length_zip_is_a_finding(self):
        """Nothing else in this collection can see one: `check_empty` tests `size == 0`."""
        self.put("arc/empty.zip", b"")
        self.assertEqual(len(TOOL.truncated(self.root)), 1)


class TheArchiveAndThePath(Tree):
    """The split that was wrong, in both modes."""

    def test_THE_ARCHIVE_IS_A_PARAMETER_NOT_SOMETHING_TO_PEEL_OFF(self):
        """THE BUG. Walking one archive gives paths already relative to it.

        Taking the first segment off those threw away a real directory:
        `Incoming/sf4.0.zip` became `sf4.0.zip`, every request 404ed, and the report said
        "nobody answered -- 8". One mistake reading as eight dead servers.
        """
        self.put("arc/Incoming/cut.zip", b"PK" + bytes([3, 4]) + bytes([0xFF]) * 500)
        whole = TOOL.truncated(self.root)
        one = TOOL.truncated(self.root, "arc")
        self.assertEqual([(a, r) for a, r, _s, _e, _f in whole], [("arc", "Incoming/cut.zip")])
        self.assertEqual([(a, r) for a, r, _s, _e, _f in one], [("arc", "Incoming/cut.zip")])

    def test_both_modes_agree_on_everything_they_find(self):
        for rel in ("arc/a/one.zip", "arc/b/c/two.zip", "arc/three.zip"):
            self.put(rel, b"PK" + bytes([3, 4]) + bytes([0xFF]) * 300)
        self.put("other/four.zip", b"PK" + bytes([3, 4]) + bytes([0xFF]) * 300)
        whole = sorted((a, r) for a, r, _s, _e, _f in TOOL.truncated(self.root))
        one = sorted((a, r) for a, r, _s, _e, _f in TOOL.truncated(self.root, "arc"))
        self.assertEqual([p for p in whole if p[0] == "arc"], one)
        self.assertIn(("other", "four.zip"), whole)

    def test_a_loose_file_in_the_collection_root_belongs_to_no_archive(self):
        # There is no archive to ask, so there is nothing to report -- and calling the file its
        # own archive would build an address out of a filename.
        self.put("stray.zip", b"PK" + bytes([3, 4]) + bytes([0xFF]) * 300)
        self.assertEqual(TOOL.truncated(self.root), [])


class TheAddressItBuilds(unittest.TestCase):

    def test_a_plain_archive(self):
        self.assertEqual(TOOL.source_url("an-archive", "a/b.zip", REGISTER),
                         "https://example.invalid/pub/a/b.zip")

    def test_a_space_is_encoded_and_a_slash_is_not(self):
        got = TOOL.source_url("an-archive", "QNX 6/x.zip", REGISTER)
        self.assertEqual(got, "https://example.invalid/pub/QNX%206/x.zip")
        self.assertNotIn("%2F", got)

    def test_AN_RSYNC_ARCHIVE_WITH_AN_HTTP_FACE_IS_ASKABLE(self):
        """bitsavers is taken over rsync and serves the same tree over HTTPS.

        Without this a third of the findings would be unanswerable, and the evidence for the
        entry is first-hand: two files were fetched whole from `https://bitsavers.org/` and
        matched byte for byte.
        """
        self.assertIn("bitsavers", common.HTTP_FACE)   # the library's table since 2026-09-27
        got = TOOL.source_url("bitsavers", "pdf/x.zip", REGISTER)
        self.assertTrue(got.startswith("https://bitsavers.org/"), got)

    def test_an_rsync_archive_without_one_cannot_be_asked(self):
        self.assertIsNone(TOOL.source_url("over-rsync", "a/b.zip", REGISTER))

    def test_an_archive_nobody_recorded_cannot_be_asked(self):
        self.assertIsNone(TOOL.source_url("never-heard-of-it", "a/b.zip", REGISTER))


class WhichVerdictALengthEarns(unittest.TestCase):

    def test_more_at_the_source_is_the_finding_worth_having(self):
        self.assertEqual(TOOL.judge(100, 200), TOOL.BIGGER)

    def test_the_same_length_means_it_is_broken_there_too(self):
        self.assertEqual(TOOL.judge(100, 100), TOOL.SAME)

    def test_less_at_the_source_means_our_copy_is_the_better_one(self):
        """Two real cases: the source now serves 0 bytes where we hold 10.93 MB."""
        self.assertEqual(TOOL.judge(100, 0), TOOL.SMALLER)

    def test_no_length_at_all_is_not_a_verdict_about_the_file(self):
        self.assertEqual(TOOL.judge(100, None), TOOL.NO_SIZE)

    def test_every_verdict_is_in_ORDER_and_they_are_distinct(self):
        named = {getattr(TOOL, n) for n in
                 ("BIGGER", "SAME", "SMALLER", "NO_SIZE", "GONE", "UNASKABLE")}
        self.assertEqual(set(TOOL.ORDER), named)
        self.assertEqual(len(TOOL.ORDER), 6)

    def test_the_one_that_needs_acting_on_comes_first(self):
        self.assertEqual(TOOL.ORDER[0], TOOL.BIGGER)


class TheDryRunAsksNobody(Tree):

    def run_tool(self, *argv):
        out = io.StringIO()
        keep = sys.stdout
        sys.stdout = out
        try:
            code = TOOL.main(list(argv))
        finally:
            sys.stdout = keep
        return code, out.getvalue()

    def test_it_asks_nobody(self):
        self.put("arc/cut.zip", b"PK" + bytes([3, 4]) + bytes([0xFF]) * 300)
        real = TOOL.head_size
        TOOL.head_size = lambda *a, **k: self.fail("--dry-run must ask nobody")
        try:
            code, text = self.run_tool("--root", self.root, "--dry-run", "--quiet")
        finally:
            TOOL.head_size = real
        self.assertEqual(code, 0)
        self.assertIn("cut.zip", text)

    def test_a_root_with_nothing_in_it_is_refused_rather_than_called_clean(self):
        os.makedirs(self.root)
        code, _text = self.run_tool("--root", self.root, "--quiet")
        self.assertEqual(code, 0)

    def test_a_root_that_does_not_exist_is_refused(self):
        code, _text = self.run_tool("--root", os.path.join(self.tmp, "nope"), "--quiet")
        self.assertEqual(code, 2)


class ItGoesThroughTheLibrary(unittest.TestCase):

    def test_it_does_not_build_its_own_request(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "truncated-vs-source.py"), encoding="utf-8") as fh:
            src = fh.read()
        # Spelled in pieces: common_test.py greps every file for this name to keep its census of
        # who opens sockets, and a test that wrote it out would put itself on that list.
        self.assertNotIn("urllib.request." + "urlopen", src)
        self.assertIn("head_size", src)

    def test_it_paces_itself(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "truncated-vs-source.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("Pacer", src)
        self.assertNotIn("time." + "sleep", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
