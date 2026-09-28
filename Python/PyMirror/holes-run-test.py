#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""holes-run.py -- and above all: an interrupted archive must not count as done.

WHAT THIS IS GUARDING. The run it drives takes about eight hours and is meant to survive being
stopped. Its entire notion of "what is already finished" is the presence of a log file, so there
is exactly one way it can lose work quietly: a log written for an archive that was not actually
read to the end. A restart would then skip that archive for good, and the collection would carry
a clean bill of health for a part of itself nobody ever looked at.

That is the same failure `common.atomic_write` was written for -- its docstring says a
half-written file that looks complete is not retried but inherited -- and this file exists to
prove the runner really gets it right, rather than to note that it calls the right function.

NOTHING HERE TOUCHES THE COLLECTION. Every test builds a small tree in a temporary directory.
`check_holes` is the real one: it is cheap on a handful of small files, and stubbing it would
leave the one integration that matters untested.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def load():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holes-run.py")
    spec = importlib.util.spec_from_file_location("holes_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load()

MARKER = common.COMPLETE_MARKER


class TempCollection(unittest.TestCase):
    """A handful of tiny archives, thrown away afterwards."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="holes-run-test-")
        self.root = os.path.join(self.tmp, "mirror")
        self.logs = os.path.join(self.tmp, "logs")
        os.makedirs(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def archive(self, name, marker_bytes=None, files=()):
        d = os.path.join(self.root, name)
        os.makedirs(d, exist_ok=True)
        if marker_bytes is not None:
            with io.open(os.path.join(d, MARKER), "w", encoding="utf-8") as fh:
                fh.write("archive       %s\nbytes         %d\nfiles         %d\n\nprose\n"
                         % (name, marker_bytes, len(files)))
        for fname, blob in files:
            with io.open(os.path.join(d, fname), "wb") as fh:
                fh.write(blob)
        return d


class TheOrderItWorksIn(TempCollection):

    def test_largest_first_by_the_marker(self):
        self.archive("small", 10)
        self.archive("huge", 10_000)
        self.archive("middle", 500)
        self.assertEqual([n for _s, n in TOOL.archives(self.root)],
                         ["huge", "middle", "small"])

    def test_an_archive_with_no_marker_sorts_last_and_is_not_skipped(self):
        """No marker means nobody finished crawling it -- not that there is nothing to read."""
        self.archive("with", 10)
        self.archive("without")
        rows = TOOL.archives(self.root)
        self.assertEqual([n for _s, n in rows], ["with", "without"])
        self.assertEqual(dict((n, s) for s, n in rows)["without"], 0)

    def test_equal_sizes_are_ordered_by_name_so_a_restart_is_predictable(self):
        for name in ("b", "a", "c"):
            self.archive(name, 100)
        self.assertEqual([n for _s, n in TOOL.archives(self.root)], ["a", "b", "c"])

    def test_a_file_in_the_root_is_not_an_archive(self):
        self.archive("real", 1)
        with io.open(os.path.join(self.root, "loose.txt"), "w", encoding="utf-8") as fh:
            fh.write("x")
        self.assertEqual([n for _s, n in TOOL.archives(self.root)], ["real"])


class WhatCountsAsDone(TempCollection):

    def test_an_archive_with_no_log_is_not_done(self):
        self.assertFalse(TOOL.already_done(self.logs, "anything"))

    def test_an_archive_with_a_log_is_done(self):
        os.makedirs(self.logs)
        common.atomic_write(TOOL.log_path(self.logs, "a"), b"whatever")
        self.assertTrue(TOOL.already_done(self.logs, "a"))

    def test_A_PART_FILE_DOES_NOT_COUNT_AS_DONE(self):
        """THE ONE THAT MATTERS.

        `atomic_write` writes to `<dest>.part` and renames. If the process dies mid-write, the
        `.part` is what survives. Were that mistaken for the log, a restart would skip an archive
        that was never read -- and the run would report a clean collection having looked at part
        of it. There is no louder symptom; this test is the symptom.
        """
        os.makedirs(self.logs)
        with io.open(TOOL.log_path(self.logs, "a") + ".part", "wb") as fh:
            fh.write(b"half a log")
        self.assertFalse(TOOL.already_done(self.logs, "a"))


class WhatItWritesAndWhen(TempCollection):

    def test_a_finished_archive_is_marked_finished(self):
        self.archive("a", 1, files=[("f.bin", b"x" * 10)])
        text, findings, failed = TOOL.run_one(self.root, "a", 1)
        self.assertFalse(failed)
        self.assertEqual(findings, 0)
        self.assertIn(TOOL.DONE, text)

    def test_AN_ARCHIVE_THAT_RAISES_IS_RECORDED_AND_NOT_MARKED_DONE(self):
        """Eight hours unattended: one OSError must not end the run, and must not look fine.

        The log still gets written -- losing the traceback would be worse than losing the run --
        but it does NOT carry the finished marker, so a human greps for it and finds this one.
        """
        real = TOOL.audit.check_holes

        def boom(*a, **k):
            raise OSError("the volume went away")
        TOOL.audit.check_holes = boom
        try:
            text, findings, failed = TOOL.run_one(self.root, "a", 1)
        finally:
            TOOL.audit.check_holes = real
        self.assertTrue(failed)
        self.assertEqual(findings, 0)
        self.assertIn("THIS ARCHIVE FAILED", text)
        self.assertIn("the volume went away", text)
        self.assertNotIn(TOOL.DONE, text)

    def test_the_findings_of_a_real_hole_are_counted(self):
        """A megabyte of zeros inside a file -- what the whole run is looking for.

        ALIGNED ON PURPOSE. check_holes reads in 1 MiB blocks and counts a block only if the
        WHOLE of it is zero, so a megabyte of zeros straddling two reads is found by neither.
        Putting four bytes of padding in front of it is the difference between a test that proves
        the check works and one that proves nothing; that mistake has already cost an afternoon
        once in this project.
        """
        blob = b"\x00" * (1 << 20) + b"TAIL" * 300
        self.archive("a", 1, files=[("big.dat", blob)])
        _text, findings, failed = TOOL.run_one(self.root, "a", 1)
        self.assertFalse(failed)
        self.assertEqual(findings, 1)


class TheDryRunReadsNothing(TempCollection):

    def test_it_creates_no_log_directory(self):
        self.archive("a", 1, files=[("f.bin", b"x" * 10)])
        code = TOOL.main(["--root", self.root, "--logs", self.logs, "--dry-run"])
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(self.logs))

    def test_it_opens_no_file_in_the_collection(self):
        self.archive("a", 1, files=[("f.bin", b"x" * 10)])
        real = TOOL.audit.check_holes
        TOOL.audit.check_holes = lambda *a, **k: self.fail("--dry-run must read nothing")
        try:
            TOOL.main(["--root", self.root, "--logs", self.logs, "--dry-run"])
        finally:
            TOOL.audit.check_holes = real

    def test_an_empty_root_is_refused_rather_than_reported_as_finished(self):
        # Nothing to do and exit 0 is how a typo in --root looks like a clean collection.
        self.assertEqual(TOOL.main(["--root", self.root, "--logs", self.logs]), 2)


class ARestartDoesTheRestAndOnlyTheRest(TempCollection):

    def test_it_skips_what_has_a_log_and_runs_what_does_not(self):
        self.archive("done", 100, files=[("f.bin", b"x" * 10)])
        self.archive("todo", 50, files=[("f.bin", b"x" * 10)])
        os.makedirs(self.logs)
        common.atomic_write(TOOL.log_path(self.logs, "done"), b"already\n")

        ran = []
        real = TOOL.audit.check_holes

        def note(root, min_size, report=None):
            ran.append(os.path.basename(root))
            return 0
        TOOL.audit.check_holes = note
        try:
            TOOL.main(["--root", self.root, "--logs", self.logs])
        finally:
            TOOL.audit.check_holes = real
        self.assertEqual(ran, ["todo"])
        with io.open(TOOL.log_path(self.logs, "done"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "already\n")   # untouched
        self.assertTrue(TOOL.already_done(self.logs, "todo"))

    def test_running_twice_does_nothing_the_second_time(self):
        self.archive("a", 1, files=[("f.bin", b"x" * 10)])
        TOOL.main(["--root", self.root, "--logs", self.logs])
        ran = []
        real = TOOL.audit.check_holes
        TOOL.audit.check_holes = lambda *a, **k: ran.append(1) or 0
        try:
            TOOL.main(["--root", self.root, "--logs", self.logs])
        finally:
            TOOL.audit.check_holes = real
        self.assertEqual(ran, [])


class ItNeverWritesInsideTheCollection(TempCollection):
    """The promise the whole night rests on."""

    def test_the_default_log_directory_is_not_under_the_collection(self):
        self.assertNotIn(TOOL.DEFAULT_ROOT.lower(), TOOL.DEFAULT_LOGS.lower())

    def test_a_full_run_leaves_the_tree_byte_for_byte_as_it_was(self):
        self.archive("a", 1, files=[("f.bin", b"x" * 10), ("g.bin", b"y" * 20)])
        before = {}
        for dirpath, _dn, filenames in os.walk(self.root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                with io.open(p, "rb") as fh:
                    before[p] = (fh.read(), os.stat(p).st_mtime_ns)
        TOOL.main(["--root", self.root, "--logs", self.logs])
        after = {}
        for dirpath, _dn, filenames in os.walk(self.root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                with io.open(p, "rb") as fh:
                    after[p] = (fh.read(), os.stat(p).st_mtime_ns)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
