# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""When a source serves both `X` and `X/y`, which one does the tree keep?

A FILESYSTEM HOLDS ONE OR THE OTHER. ps-2.kev009.com serves `ohlandl/CPU/docs/Intel` as a listing
page and `ohlandl/CPU/docs/Intel/210844-001.pdf` beneath it. Until 2026-10-04 whichever ARRIVED
FIRST won, which is why that archive has `Harris` as a directory -- its files came first -- and had
`Intel` as a 4 901-byte page that made 20 datasheets unstorable.

THE OWNER'S DECISION: FILES WIN, and the page is kept as `<name>/index.html`, recorded in
RENAMED.txt. The trade is 4 901 bytes of listing against 20 PDFs, and the listing is the one page
whose content the directory itself already carries.

INSIDE THE DIRECTORY AND NOT BESIDE IT. The first version wrote `<name>.html` in the parent, which
REINTERPRETS EVERY RELATIVE LINK THE PAGE HOLDS -- see
test_a_directory_answer_is_stored_INSIDE_the_directory for the measurement that caught it.

TWO HALVES, DELIBERATELY NOT THE SAME RISK:

  a response that IS a directory    stored as <name>/index.html automatically. Nothing on disk
                                    changes; a file arrives under a name the source did not use.
  a file ALREADY in the way         moved into <name>/index.html only with --free-blockers,
                                    because a fetch that quietly rearranges an archive is not one
                                    anybody can audit.

AND THE RENAME IS WRITTEN DOWN, which is the whole difference between a rename and a quiet loss:
the source called it `Intel`, and only RENAMED.txt says so afterwards.

NO NETWORK AND NO COLLECTION.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402


class TheRenameIsRecorded(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="fileswin-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def text(self):
        with io.open(os.path.join(self.d, common.RENAMED_FILE), encoding="utf-8") as fh:
            return fh.read()

    def test_a_pair_is_written_with_its_reason(self):
        self.assertTrue(common.record_renamed(
            self.d, "CPU/docs/Intel", "CPU/docs/Intel.html",
            "the source answered it as a directory"))
        t = self.text()
        self.assertIn("CPU/docs/Intel\n", t)
        self.assertIn("  -> CPU/docs/Intel.html", t)
        self.assertIn("answered it as a directory", t)

    def test_THE_FORMAT_IS_THE_ONE_FOUR_ARCHIVES_ALREADY_CARRY(self):
        """extract-container-tar.py wrote dec-ftp-2006's and three more. A second layout would be
        a second opinion about what the tree holds, and there are readers for the first."""
        common.record_renamed(self.d, "a", "b", "why", source="x.tar")
        head = self.text().splitlines()
        self.assertEqual(head[0],
                         "# Names changed because NTFS cannot hold them. Original -> on disk.")
        self.assertTrue(head[1].startswith("# Source: "))

    def test_the_source_is_named_and_defaults_to_something_true(self):
        common.record_renamed(self.d, "a", "b", "why")
        self.assertIn("# Source: fetched by url", self.text())

    def test_a_name_that_did_not_change_is_not_recorded(self):
        """A no-op line would make the file lie about what was done."""
        self.assertFalse(common.record_renamed(self.d, "same", "same", "why"))
        self.assertFalse(os.path.exists(os.path.join(self.d, common.RENAMED_FILE)))

    def test_an_empty_side_is_not_recorded(self):
        for a, b in (("", "x"), ("x", ""), (None, "x"), ("x", None)):
            self.assertFalse(common.record_renamed(self.d, a, b, "why"), (a, b))

    def test_it_appends_rather_than_rewrites(self):
        """A later fetch of the same archive must not erase what an earlier one recorded."""
        common.record_renamed(self.d, "a", "a.html", "first")
        common.record_renamed(self.d, "b", "b.html", "second")
        t = self.text()
        self.assertIn("a.html", t)
        self.assertIn("b.html", t)
        self.assertEqual(t.count("# Names changed"), 1)

    def test_it_is_bookkeeping_and_not_content_for_an_auditor(self):
        """In the WIDE set only, like the hand-written notes: an auditor skips it, a marker counts
        it. That is the collection's convention and it is why four markers already include one."""
        self.assertIn(common.RENAMED_FILE, common.BOOKKEEPING_FILES)
        self.assertNotIn(common.RENAMED_FILE, common.OWN_FILES)


class FilesWinInTheFetcher(unittest.TestCase):
    """The two halves, read from the source because the alternative is a live fetch."""

    def source(self):
        with io.open(os.path.join(HERE, "manifest-fetch.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_a_directory_answer_is_stored_INSIDE_the_directory(self):
        """`<name>/index.html` AND NOT `<name>.html`, which was the first version and was wrong.

        A page one level up has ALL ITS RELATIVE LINKS REINTERPRETED. ps-2.kev009.com's listing of
        /615x/AOS_43/Docs/ holds href="AOS_4.3_Volume_1.pdf"; from `AOS_43/Docs.html` that resolves
        to `AOS_43/AOS_4.3_Volume_1.pdf`, which the source answers 404 for, instead of
        `AOS_43/Docs/AOS_4.3_Volume_1.pdf`, which answers 200. The next harvest asked for six
        paths that do not exist, and the four pages already written that day had to be moved.

        The decision is unchanged -- files win and the listing is kept. Only the place was wrong.
        """
        src = self.source()
        self.assertIn('page = os.path.join(out, "index.html")', src)
        self.assertNotIn('page = out + ".html"', src)
        self.assertIn('rel + "/index.html"', src)

    def test_a_freed_blocker_also_ends_up_inside(self):
        """Two steps, because the name has to be free before the directory can be made."""
        src = self.source()
        block = src[src.index("if blocker and args.free_blockers:"):src.index("if blocker:\n")]
        self.assertIn('os.path.join(blocker, "index.html")', block)
        self.assertIn(".moving", block)
        self.assertIn("os.makedirs(", block)

    def test_and_it_counts_as_progress_rather_than_silence(self):
        """A page that arrived is the server answering. Leaving Patience untouched here would let
        a run of them look like the host going quiet -- the exact misreading that cost an afternoon
        on 2026-10-04."""
        src = self.source()
        block = src[src.index('page = os.path.join(out, "index.html")'):
                    src.index("renamed.append(") + 400]
        self.assertIn("patience.answered()", block)

    def test_an_existing_html_is_not_overwritten(self):
        """A second run must not replace a page somebody may have looked at; it falls through to
        the report instead."""
        src = self.source()
        self.assertIn("if exists(page):", src)

    def test_MOVING_A_FILE_ALREADY_ON_DISK_NEEDS_THE_FLAG(self):
        """Prevention is automatic; rearranging an archive is not. A fetch that quietly moves
        files is not one anybody can audit."""
        src = self.source()
        self.assertIn("if blocker and args.free_blockers:", src)
        self.assertIn("--free-blockers", src)

    def test_the_flag_is_off_by_default(self):
        src = self.source()
        self.assertIn('ap.add_argument("--free-blockers", action="store_true"', src)

    def test_every_move_is_recorded_before_it_is_used(self):
        """The record must not depend on the rest of the run finishing."""
        src = self.source()
        block = src[src.index("if blocker and args.free_blockers:"):src.index("if blocker:\n")]
        self.assertIn("os.replace(", block)
        self.assertIn("record_renamed(", block)
        self.assertLess(block.index("os.replace("), block.index("freed.append("))

    def test_the_two_are_reported_separately(self):
        """One is a file that arrived, the other a file that was already here. A single count
        would hide which of the two happened."""
        src = self.source()
        self.assertIn("MOVED out of the way (--free-blockers)", src)
        self.assertIn("stored as <name>/index.html", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
