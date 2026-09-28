# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Does restating a marker say what it did, and refuse what it should?

EVERY CASE BUILDS ITS OWN TREE in a temporary directory. Nothing here reads or writes the real
collection: this tool's whole job is to overwrite a record, and a test that practised on the real
records would be the exact accident it is meant to prevent.
"""
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest

import common

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("restate_marker",
                                               os.path.join(HERE, "restate-marker.py"))
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


class Tree(object):
    """One archive with a marker, built from nothing and thrown away afterwards."""

    def __init__(self, files=(), marker=None):
        self.root = tempfile.mkdtemp(prefix="restate-")
        self.archive = "an-archive"
        self.path = os.path.join(self.root, self.archive)
        os.makedirs(self.path)
        for name, body in files:
            full = os.path.join(self.path, name)
            if not os.path.isdir(os.path.dirname(full)):
                os.makedirs(os.path.dirname(full))
            with io.open(full, "wb") as fh:
                fh.write(body)
        if marker is not None:
            common.write_marker(os.path.join(self.path, common.COMPLETE_MARKER), marker,
                                "This mirror is complete.")

    def marker(self):
        return common.read_marker(os.path.join(self.path, common.COMPLETE_MARKER))

    def text(self):
        with io.open(os.path.join(self.path, common.COMPLETE_MARKER), encoding="utf-8") as fh:
            return fh.read()

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def quiet(_msg):
    pass


class TestRestating(unittest.TestCase):

    def test_it_moves_the_counts_onto_the_tree(self):
        t = Tree(files=[("a.bin", b"x" * 100), ("b.bin", b"y" * 50)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            old, new = rm.restate(t.root, t.archive, "a repair", apply_it=True, report=quiet)
            self.assertEqual(old, (1, 10))
            self.assertEqual(new, (2, 150))
            self.assertEqual(t.marker()["files"], "2")
            self.assertEqual(t.marker()["bytes"], "150")
        finally:
            t.close()

    def test_WITHOUT_APPLY_NOTHING_MOVES(self):
        """The dry run has to be a real dry run, because the thing at stake is a record."""
        t = Tree(files=[("a.bin", b"x" * 100)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            before = t.text()
            rm.restate(t.root, t.archive, "a repair", apply_it=False, report=quiet)
            self.assertEqual(t.text(), before)
        finally:
            t.close()

    def test_THE_REASON_IS_IN_THE_FILE_NOT_IN_A_LOG(self):
        """A year from now the marker is what somebody reads, and a log is not."""
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            rm.restate(t.root, t.archive, "33 blocked pages removed", apply_it=True, report=quiet)
            text = t.text()
            self.assertIn("33 blocked pages removed", text)
            self.assertIn(rm.RESTATED, text)
        finally:
            t.close()

    def test_AND_SO_ARE_THE_NUMBERS_IT_MOVED_AWAY_FROM(self):
        # Without them the chain back to the crawl is broken: the file would claim a count with
        # no way to see what it used to claim.
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "files": "444", "bytes": "999"})
        try:
            rm.restate(t.root, t.archive, "a repair", apply_it=True, report=quiet)
            text = t.text()
            self.assertIn("from 444 files and 999 bytes", text)
        finally:
            t.close()

    def test_THE_COMPLETION_DATE_IS_NOT_TOUCHED(self):
        """The archive was completed then and repaired today. Those are two different facts.

        Moving `completed` forward would turn a two-week-old mirror into a fresh one in the only
        record that says how old it is.
        """
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "completed": "2026-09-11 07:18:43",
                         "files": "1", "bytes": "10"})
        try:
            rm.restate(t.root, t.archive, "a repair", apply_it=True, report=quiet)
            self.assertEqual(t.marker()["completed"], "2026-09-11 07:18:43")
        finally:
            t.close()

    def test_every_other_field_survives(self):
        # source and permanent-404 are the archive's own record and this tool has no opinion
        # about them. Dropping one would lose it silently.
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "source": "https://h/x/",
                         "duration": "0h14m", "permanent-404": "4279",
                         "files": "1", "bytes": "10"})
        try:
            rm.restate(t.root, t.archive, "a repair", apply_it=True, report=quiet)
            m = t.marker()
            self.assertEqual(m["source"], "https://h/x/")
            self.assertEqual(m["permanent-404"], "4279")
            self.assertEqual(m["duration"], "0h14m")
        finally:
            t.close()

    def test_AN_ARCHIVE_WITH_NO_MARKER_IS_NOT_GIVEN_ONE(self):
        """It was never complete, and saying it is now is not this tool's decision to make."""
        t = Tree(files=[("a.bin", b"x" * 7)])
        try:
            self.assertIsNone(rm.restate(t.root, t.archive, "a repair", apply_it=True,
                                         report=quiet))
            self.assertFalse(os.path.exists(os.path.join(t.path, common.COMPLETE_MARKER)))
        finally:
            t.close()

    def test_a_marker_without_counts_is_left_alone(self):
        # Some markers were written by hand. Reading "files" out of one that has none and
        # writing a number in its place would invent a claim nobody made.
        t = Tree(files=[("a.bin", b"x" * 7)], marker={"archive": "an-archive"})
        try:
            self.assertIsNone(rm.restate(t.root, t.archive, "a repair", apply_it=True,
                                         report=quiet))
        finally:
            t.close()

    def test_restating_twice_does_not_stack_two_notes(self):
        """One note, the newest -- and the cost of that, recorded rather than glossed over.

        Two stacked notes would make the file read as if two repairs were outstanding. The price
        is that only ONE hop back is kept: after a second restate the crawl's original figure is
        no longer in the file. The test asserts the loss so nobody discovers it by needing it.
        """
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            rm.restate(t.root, t.archive, "first repair", apply_it=True, report=quiet)
            with io.open(os.path.join(t.path, "b.bin"), "wb") as fh:
                fh.write(b"z" * 3)
            rm.restate(t.root, t.archive, "second repair", apply_it=True, report=quiet)
            text = t.text()
            self.assertEqual(text.count(rm.RESTATED), 1)
            self.assertIn("second repair", text)
            self.assertNotIn("first repair", text)
            self.assertIn("from 1 files and 7 bytes", text)      # the first restate's result
            self.assertNotIn("from 1 files and 10 bytes", text)  # the crawl's, now gone
        finally:
            t.close()

    def test_the_bookkeeping_files_do_not_count(self):
        """scan_tree's rule, pinned here because this tool writes the number it produces.

        A marker that counted its own file would disagree with itself the moment it was written.
        """
        t = Tree(files=[("a.bin", b"x" * 7), (common.SUMS_FILE, b"junk"),
                        (common.INDEX_FILE, b"junk"), ("STILL-MISSING.txt", b"junk")],
                 marker={"archive": "an-archive", "files": "99", "bytes": "99"})
        try:
            _old, new = rm.restate(t.root, t.archive, "a repair", apply_it=True, report=quiet)
            self.assertEqual(new, (1, 7))
        finally:
            t.close()

    def test_an_empty_reason_is_refused(self):
        # argparse prints its complaint to stderr; swallowed so a passing run stays readable.
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit):
                rm.main(["--root", "x", "--archive", "y", "--reason", "   "])
        self.assertIn("--reason", err.getvalue())


if __name__ == "__main__":
    unittest.main()
