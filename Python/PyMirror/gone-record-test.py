#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""A path the source has already said it does not have must not be asked for again.

WHAT HAPPENED, openpa, 2026-10-02. images/dcsscr4.gif had been requested in THREE separate
sessions and answered 404 every time. So had images/dcsscrus.jpg, twice, and
mages/hp_ns-1_1987.jpg, twice.

WHY IT REPEATED, AND WHY NO CHECK COULD HAVE CAUGHT IT. A url list is built by diffing the names
pages mention against the names on disk. A 404 creates no file, so the path stays absent, so the
next list names it again -- and "absent from the tree" is true of a file that is gone and of a
file never asked for. The diff cannot tell those apart, because the information that separates
them was thrown away as soon as the run printed it.

AND IT WAS NOT MERELY WASTE. These names sort to the FRONT of such a list -- dcss*, sna* -- so
they were the first requests of a session, at a host that grants a few dozen. On 2026-10-02 the
run spent four requests, two of them on dead paths, and the give-up guard then fired on two
timeouts for files that do not exist. A session ended having fetched nothing, over names that had
been settled a day earlier.

WHAT IS AND IS NOT WRITTEN DOWN. 404 and 410 only. Not a timeout, which says nothing whatever
about the file; not 403 or 401, which say we may not HAVE it rather than that it is gone, and
which a configuration change reverses. Collapsing any of those into "gone" is the mistake
http_try's docstring exists to prevent, committed one level further on -- and this record is read
by a tool that then stops asking, so a wrong entry here closes a question rather than losing a
file.

IT IS A NOTE, NOT A VERDICT. The date is stored and --ask-gone-again ignores the record, because
this collection has already learned what a closed question costs: LOST and FROZEN exist to stop
anyone looking again, and recheck-decisions.py exists because a host comes back and nothing on
disk changes when it does.

No network. Everything happens in a temporary directory.
"""
import importlib.util
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


def load(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIRROR = load("mirror")


class WhatGoesIntoTheRecord(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_a_missing_record_reads_as_empty_and_not_as_an_error(self):
        self.assertEqual(common.read_gone(self.d), {})

    def test_a_404_is_written_with_its_date(self):
        self.assertTrue(common.record_gone(self.d, "a/b.gif", 404, when="2026-10-02"))
        self.assertEqual(common.read_gone(self.d), {"a/b.gif": "2026-10-02"})

    def test_a_410_is_written_too(self):
        common.record_gone(self.d, "e.gif", 410, when="2026-10-02")
        self.assertIn("e.gif", common.read_gone(self.d))

    def test_a_403_is_NOT_written(self):
        """403 says we may not have it, not that it is gone, and a configuration reverses that."""
        self.assertFalse(common.record_gone(self.d, "d.gif", 403))
        self.assertEqual(common.read_gone(self.d), {})

    def test_a_401_is_NOT_written(self):
        self.assertFalse(common.record_gone(self.d, "d.gif", 401))
        self.assertEqual(common.read_gone(self.d), {})

    def test_a_500_is_NOT_written(self):
        """A server error is this minute's accident, not a fact about the file."""
        self.assertFalse(common.record_gone(self.d, "d.gif", 500))
        self.assertEqual(common.read_gone(self.d), {})

    def test_only_404_and_410_are_eligible_at_all(self):
        """Stated against the constant, so widening it has to be deliberate."""
        self.assertEqual(sorted(common.GONE_STATUS), [404, 410])
        self.assertNotIn(403, common.GONE_STATUS)
        self.assertNotIn(401, common.GONE_STATUS)

    def test_the_same_path_is_not_written_twice(self):
        """Three identical lines say nothing one line and its date does not."""
        common.record_gone(self.d, "a.gif", 404, when="2026-10-02")
        self.assertFalse(common.record_gone(self.d, "a.gif", 404, when="2026-10-09"))
        with io.open(os.path.join(self.d, common.GONE_FILE), encoding="utf-8") as fh:
            self.assertEqual(sum(1 for ln in fh if ln.strip() and not ln.startswith("#")), 1)

    def test_the_first_date_is_kept_not_the_latest(self):
        """When the question was settled is what a re-check needs to reason about."""
        common.record_gone(self.d, "a.gif", 404, when="2026-10-02")
        common.record_gone(self.d, "a.gif", 404, when="2026-10-09")
        self.assertEqual(common.read_gone(self.d)["a.gif"], "2026-10-02")

    def test_a_path_with_spaces_survives_the_round_trip(self):
        """The collection is full of them -- `basil.holloway/ALL PDF/...`."""
        rel = "basil.holloway/ALL PDF/a b.pdf"
        common.record_gone(self.d, rel, 404, when="2026-10-02")
        self.assertIn(rel, common.read_gone(self.d))

    def test_comments_and_blank_lines_are_ignored_when_reading(self):
        with io.open(os.path.join(self.d, common.GONE_FILE), "w", encoding="utf-8") as fh:
            fh.write("# a comment\n\n2026-10-02 404 a.gif\n")
        self.assertEqual(common.read_gone(self.d), {"a.gif": "2026-10-02"})

    def test_the_file_carries_its_own_explanation(self):
        """Somebody will find this file in a decade without this repository beside it."""
        common.record_gone(self.d, "a.gif", 404)
        with io.open(os.path.join(self.d, common.GONE_FILE), encoding="utf-8") as fh:
            head = fh.read()
        self.assertIn("404", head)
        self.assertIn("NOT a statement that the bytes are gone from the world", head)


class ItIsBookkeepingAndNotContent(unittest.TestCase):

    def test_it_is_in_the_narrow_set(self):
        """Otherwise it is hashed into the index and then reported as a change every session."""
        self.assertIn(common.GONE_FILE, common.OWN_FILES)

    def test_and_therefore_in_the_wide_one(self):
        self.assertIn(common.GONE_FILE, common.BOOKKEEPING_FILES)

    def test_a_tree_walk_does_not_count_it_as_a_file(self):
        d = tempfile.mkdtemp()
        try:
            with io.open(os.path.join(d, "real.bin"), "wb") as fh:
                fh.write(b"x")
            common.record_gone(d, "a.gif", 404)
            self.assertEqual(sorted(rel for rel, _f in common.iter_tree(d)), ["real.bin"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


def run(tool, *argv):
    out = subprocess.run([sys.executable, os.path.join(HERE, tool + ".py")] + list(argv),
                         capture_output=True, text=True, cwd=HERE)
    return out.stdout + out.stderr


class TheFetcherSkipsWhatIsRecorded(unittest.TestCase):

    def setUp(self):
        self.archive = "an-archive"
        self.root = tempfile.mkdtemp()
        self.dir = os.path.join(self.root, self.archive)
        os.makedirs(self.dir)
        common.record_gone(self.dir, "dead.gif", 404, when="2026-10-02")
        self.list = os.path.join(self.root, "urls.txt")
        with io.open(self.list, "w", encoding="utf-8") as fh:
            fh.write("https://example.invalid/dead.gif\n")
            fh.write("https://example.invalid/alive.gif\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def fetch(self, *extra):
        return run("manifest-fetch", "--root", self.root, "--archive", self.archive,
                   "--base", "https://example.invalid/", "--url-list", self.list,
                   "--dry-run", *extra)

    def test_the_recorded_path_is_skipped_and_said_so(self):
        out = self.fetch()
        self.assertIn("dead.gif", out)
        self.assertIn("404/410", out)
        self.assertIn("names 1 paths", out)

    def test_the_date_is_shown_so_the_skip_can_be_judged(self):
        self.assertIn("2026-10-02", self.fetch())

    def test_the_other_path_is_untouched(self):
        self.assertIn("alive.gif", self.fetch())

    def test_ask_gone_again_overrides_it(self):
        """A host comes back, and nothing on disk changes when it does."""
        out = self.fetch("--ask-gone-again")
        self.assertIn("names 2 paths", out)
        self.assertNotIn("404/410", out)

    def test_the_skip_happens_before_the_on_disk_test(self):
        """Which is the whole point: the on-disk test cannot tell 'gone' from 'never asked'.

        Both are absent from the tree. If the skip ran afterwards it would still work here, but
        the reported count would be built from a list that had already lost the distinction.
        """
        out = self.fetch()
        self.assertLess(out.index("404/410"), out.index("names 1 paths"))


class ThePermanentSetIsNotTheGoneSet(unittest.TestCase):
    """mirror.py treats 401/403/404/410 alike when deciding not to retry, and that is right for
    a retry decision. It would be wrong here: this record is read by a tool that then stops
    asking, so it must hold only statuses that mean the file is not there."""

    def test_mirror_permanent_is_wider(self):
        self.assertTrue(set(MIRROR.PERMANENT) > set(common.GONE_STATUS))

    def test_and_the_difference_is_exactly_the_permission_codes(self):
        self.assertEqual(sorted(set(MIRROR.PERMANENT) - set(common.GONE_STATUS)), [401, 403])


if __name__ == "__main__":
    unittest.main(verbosity=1)
