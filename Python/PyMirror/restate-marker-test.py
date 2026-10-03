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
        # no way to see what it used to claim. The wording changed on 2026-10-02, when one note
        # became a list of repairs; both figures are still there and now so is the one it moved TO,
        # which is what makes a second entry readable as a continuation rather than a replacement.
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "files": "444", "bytes": "999"})
        try:
            rm.restate(t.root, t.archive, "a repair", apply_it=True, report=quiet)
            text = t.text()
            self.assertIn("444 -> 1 files", text)
            self.assertIn("999 -> 7 bytes", text)
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

    def test_restating_twice_keeps_both_repairs_under_one_heading(self):
        """ONE heading, EVERY repair -- and this test used to assert the opposite.

        Until 2026-10-02 the prose was rebuilt from the newest reason alone, and this case pinned
        the resulting loss: `assertNotIn("first repair")`, with a docstring explaining that only
        one hop back survived "so nobody discovers it by needing it". Somebody then needed it.
        ardent-tool was restated a second time and the dry run showed the first repair -- 25 files
        recovered from a stored directory page -- gone from the preview, and the crawl's own
        figure of 25608 with it.

        Two stacked HEADINGS would still be wrong, for the reason the old docstring gave: the file
        would read as though two repairs were outstanding. One heading over a list says what
        actually happened.
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
            self.assertIn("first repair", text)
            self.assertIn("second repair", text)
            # Oldest first, so reading downwards follows the tree forwards.
            self.assertLess(text.index("first repair"), text.index("second repair"))
            # And the chain reaches back past the first repair to what the crawl left.
            self.assertIn("10 -> 7 bytes", text)
        finally:
            t.close()

    def test_a_third_repair_does_not_drop_the_first(self):
        """The list has to survive being read back, not just written once."""
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            for n, size in (("first repair", 3), ("second repair", 4), ("third repair", 5)):
                with io.open(os.path.join(t.path, "f%d.bin" % size), "wb") as fh:
                    fh.write(b"z" * size)
                rm.restate(t.root, t.archive, n, apply_it=True, report=quiet)
            text = t.text()
            self.assertEqual(text.count(rm.RESTATED), 1)
            for n in ("first repair", "second repair", "third repair"):
                self.assertIn(n, text)
            self.assertEqual(text.count(rm.ENTRY), 3)
        finally:
            t.close()

    def test_a_marker_from_before_the_list_keeps_its_one_paragraph(self):
        """The shape that existed on disk when this changed must not be thrown away.

        Every restated marker in the collection on 2026-10-02 carried the old one-paragraph form.
        If the first list-aware restate dropped it, the change would have caused exactly the loss
        it was made to prevent.
        """
        t = Tree(files=[("a.bin", b"x" * 7)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            old_shape = (
                "This mirror is complete.\n\n"
                "%s: the two figures above were moved after the crawl that wrote this file,\n"
                "from 1 files and 99 bytes, by a deliberate repair:\n"
                "a repair done the old way\n"
                "`completed` above is still the crawl's date, not the repair's.\n" % rm.RESTATED)
            self.assertEqual(rm.earlier_entries(old_shape), ["a repair done the old way"])
            with io.open(os.path.join(t.path, "b.bin"), "wb") as fh:
                fh.write(b"z" * 3)
            rm.restate(t.root, t.archive, "the new one", apply_it=True, report=quiet)
            text = t.text()
            self.assertIn("the new one", text)
        finally:
            t.close()

    def test_no_restated_block_means_no_earlier_entries(self):
        self.assertEqual(rm.earlier_entries("archive x\n\nThis mirror is complete.\n"), [])
        self.assertEqual(rm.earlier_entries(""), [])
        self.assertEqual(rm.earlier_entries(None), [])

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


class WhenNothingMovesTheReasonIsLOSTAndItSaysSo(unittest.TestCase):
    """The silent no-op, found on 2026-10-03 by reading a file rather than by being told.

    dreamlandbbs-os2 had just earned a marker from a completed crawl, so its figures already
    agreed with the tree -- which is exactly what a freshly earned marker looks like. restate was
    then called with a --reason explaining that the marker's "duration 0h00m" hid twelve hours of
    fetching across six rounds. It printed "already agrees with the tree", returned, and dropped
    the text. Nothing said so, and the reason would have been believed recorded.

    WHAT IS PINNED HERE IS THE SENTENCE, NOT A NEW BEHAVIOUR. This tool moves `files` and `bytes`
    and appends why they moved; a marker whose figures did not move has nothing for it to restate,
    and letting it append prose to any marker at any time is the authority it was deliberately
    refused -- the same refusal as not inventing a marker that does not exist. The fix is that it
    now says what it is not doing.
    """

    AGREES = {"archive": "an-archive", "files": "1", "bytes": "7"}

    def run_it(self, reason, apply_it=True):
        t = Tree(files=[("a.bin", b"x" * 7)], marker=dict(self.AGREES))
        said = []
        try:
            before = t.text()
            out = rm.restate(t.root, t.archive, reason, apply_it=apply_it, report=said.append)
            return t, before, t.text(), chr(10).join(said), out
        finally:
            t.close()

    def test_the_figures_already_agree_so_the_file_is_untouched(self):
        _t, before, after, _said, out = self.run_it("a reason that goes nowhere")
        self.assertEqual(before, after)
        self.assertEqual(out, ((1, 7), (1, 7)))

    def test_AND_THE_REASON_IS_NOWHERE_IN_IT(self):
        """The case itself: the text really is lost, and the test says so out loud."""
        _t, _before, after, _said, _out = self.run_it("twelve hours across six rounds")
        self.assertNotIn("twelve hours across six rounds", after)

    def test_BUT_IT_SAYS_THE_REASON_WAS_NOT_WRITTEN(self):
        """Losing the text is defensible. Losing it in silence is not."""
        _t, _b, _a, said, _out = self.run_it("twelve hours across six rounds")
        self.assertIn("REASON NOT WRITTEN", said)
        self.assertIn("already agrees with the tree", said)

    def test_and_it_says_where_to_put_it_instead(self):
        """A refusal that names no alternative gets worked around."""
        _t, _b, _a, said, _out = self.run_it("some history")
        self.assertIn("by hand", said)

    def test_no_such_line_when_no_reason_was_given(self):
        """The message must only appear when something was actually dropped."""
        for reason in ("", None):
            _t, _b, _a, said, _out = self.run_it(reason)
            self.assertNotIn("REASON NOT WRITTEN", said, repr(reason))

    def test_it_still_appears_on_a_dry_run(self):
        """--apply is about writing. Whether the reason would be kept is the same either way, and
        learning it only after committing to --apply is learning it too late."""
        _t, _b, _a, said, _out = self.run_it("some history", apply_it=False)
        self.assertIn("REASON NOT WRITTEN", said)

    def test_a_marker_whose_figures_DO_move_still_carries_its_reason(self):
        """The guard must not have turned the normal path off."""
        t = Tree(files=[("a.bin", b"x" * 100)],
                 marker={"archive": "an-archive", "files": "1", "bytes": "10"})
        try:
            rm.restate(t.root, t.archive, "this one must survive", apply_it=True, report=quiet)
            self.assertIn("this one must survive", t.text())
        finally:
            t.close()


if __name__ == "__main__":
    unittest.main()
