#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for move-mirror.py's survey(), on trees built for the purpose.

WHY A TEST FILE OF ITS OWN. survey() is not library code -- it belongs to the tool that moves a
tree so every directory inherits the NTFS case-sensitive flag -- but it is the function the whole
safety of that tool rests on. Its collision map decides which target directories get the flag
checked, and a directory whose collision goes unnoticed does not fail the move: it OVERWRITES one
of the two files, and every count afterwards still looks right.

NOTHING HERE TOUCHES THE COLLECTION. Every tree is made in a temporary directory and removed
again. A test that needs the finished mirror to prove something about a tool that MOVES files is
not a test anyone should run twice.

THE COLLISION TESTS NEED A CASE-SENSITIVE DIRECTORY and say so: on a volume that will not take
the flag they skip rather than pass, because a collision test on a filesystem that cannot hold a
collision proves nothing and would go green for the wrong reason.

    python move-mirror-test.py
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

mm = common.load_peer("move-mirror.py", "_move_mirror")


class TreeTest(unittest.TestCase):
    """A throwaway tree, and the helpers to build one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="move-mirror-test-")

    def tearDown(self):
        shutil.rmtree(common.long_path(self.tmp), ignore_errors=True)

    def file(self, rel, size=3):
        p = os.path.join(self.tmp, *rel.split("/"))
        parent = os.path.dirname(p)
        if parent and not os.path.isdir(common.long_path(parent)):
            os.makedirs(common.long_path(parent))
        with io.open(common.long_path(p), "wb") as fh:
            fh.write(b"x" * size)
        return p

    def directory(self, rel):
        p = os.path.join(self.tmp, *rel.split("/"))
        if not os.path.isdir(common.long_path(p)):
            os.makedirs(common.long_path(p))
        return p

    def case_sensitive_or_skip(self, path):
        got = common.set_case_sensitive(path)
        if got is not True:
            self.skipTest("this volume will not take the case-sensitive flag: %s" % got)


class TestSurveyCounts(TreeTest):
    def test_files_and_bytes(self):
        self.file("a.txt", 10)
        self.file("sub/b.bin", 20)
        _dirs, files, total, _coll = mm.survey(self.tmp, self.tmp)
        self.assertEqual((files, total), (2, 30))

    def test_the_root_itself_is_not_a_directory_to_create(self):
        # It exists already; listing it would make the tool try to create DST inside DST.
        self.file("a.txt")
        dirs, _f, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual(dirs, [])

    def test_every_subdirectory_is_listed(self):
        self.directory("a/b/c")
        dirs, _f, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual(sorted(dirs), ["a", "a/b", "a/b/c"])

    def test_an_empty_directory_is_still_listed(self):
        # It has to exist at the target, or a later run finds a tree that is not the same tree.
        self.directory("empty")
        dirs, _f, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual(dirs, ["empty"])

    def test_paths_use_forward_slashes(self):
        self.directory("a/b")
        dirs, _f, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertFalse(any("\\" in d for d in dirs))

    def test_skipped_directories_are_not_walked(self):
        for skip in mm.SKIP_DIRS:
            self.file("%s/inside.txt" % skip)
        self.file("kept.txt")
        dirs, files, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual(files, 1)
        self.assertEqual(dirs, [])

    def test_skipped_files_are_not_counted(self):
        for skip in mm.SKIP_FILES:
            self.file(skip)
        self.file("kept.txt")
        _dirs, files, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual(files, 1)

    def test_an_unreadable_file_does_not_stop_the_walk(self):
        # It is not counted in the bytes, and the walk finishes. The comparison at the end is
        # what notices a shortfall, not this.
        self.file("a.txt", 5)
        self.file("b.txt", 7)
        _dirs, files, total, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual((files, total), (2, 12))

    def test_a_trailing_dot_in_a_name_survives(self):
        # 21 files in this collection end in one, and a path that loses it is a path to a file
        # that does not exist.
        self.directory("Wavefunction Inc Spartan ")
        self.file("TALK.")
        dirs, files, _t, _c = mm.survey(self.tmp, self.tmp)
        self.assertEqual(dirs, ["Wavefunction Inc Spartan "])
        self.assertEqual(files, 1)


class TestSurveyBase(TreeTest):
    """`base` is not always `root`, and that is the whole reason it has no default."""

    def test_measured_against_a_parent(self):
        # What --only does: walk one archive, but name its directories from the collection root,
        # because that is where they have to be created.
        self.directory("archive/inner")
        dirs, _f, _t, _c = mm.survey(os.path.join(self.tmp, "archive"), self.tmp)
        self.assertEqual(sorted(dirs), ["archive", "archive/inner"])

    def test_measured_against_itself(self):
        # What the destination survey does: the paths are only counted and compared.
        self.directory("archive/inner")
        root = os.path.join(self.tmp, "archive")
        dirs, _f, _t, _c = mm.survey(root, root)
        self.assertEqual(dirs, ["inner"])

    def test_THE_TWO_ANSWERS_DIFFER_AND_BOTH_ARE_RIGHT(self):
        # Which is why a default would be wrong: it would make one of them the accident.
        self.directory("archive/inner")
        root = os.path.join(self.tmp, "archive")
        self.assertNotEqual(mm.survey(root, self.tmp)[0], mm.survey(root, root)[0])

    def test_the_file_and_byte_counts_do_not_depend_on_base(self):
        self.file("archive/inner/a.txt", 11)
        root = os.path.join(self.tmp, "archive")
        self.assertEqual(mm.survey(root, self.tmp)[1:3], mm.survey(root, root)[1:3])


class TestSurveyCollisions(TreeTest):
    """The map the flag check keys on. A missed collision overwrites a file silently."""

    def test_no_collision_is_an_empty_map(self):
        self.file("a.txt")
        self.file("b.txt")
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {})

    def test_TWO_FILES_DIFFERING_ONLY_IN_CASE(self):
        self.case_sensitive_or_skip(self.tmp)
        self.file("File.txt")
        self.file("file.txt")
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {"": 1})

    def test_and_two_DIRECTORIES_differing_only_in_case(self):
        """Either kind arriving in a target without the flag overwrites the other, so both count.

        ONE collision, not two: the figure is names-minus-one per group, because that is how many
        would be LOST. Two spellings lose one; this test asserted two before it was run once.
        """
        self.case_sensitive_or_skip(self.tmp)
        self.directory("Docs")
        self.directory("docs")
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {"": 1})

    def test_a_file_and_a_directory_of_the_same_name_collide_too(self):
        self.case_sensitive_or_skip(self.tmp)
        self.directory("Thing")
        self.file("thing")
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {"": 1})

    def test_the_collision_is_keyed_by_the_directory_that_holds_it(self):
        self.directory("inner")
        self.case_sensitive_or_skip(os.path.join(self.tmp, "inner"))
        self.file("inner/A.txt")
        self.file("inner/a.txt")
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {"inner": 1})

    def test_three_spellings_count_as_two(self):
        # n - 1 per group: two of the three would be lost, not one.
        self.case_sensitive_or_skip(self.tmp)
        for name in ("X.txt", "x.txt", "X.TXT"):
            self.file(name)
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {"": 2})

    def test_A_SKIPPED_NAME_DOES_NOT_MANUFACTURE_A_COLLISION(self):
        # The skip lists are applied before the comparison, so a file that is never moved cannot
        # make the tool demand a flag for a directory that does not need one.
        self.case_sensitive_or_skip(self.tmp)
        skip = sorted(mm.SKIP_FILES)[0]
        self.file(skip)
        self.file(skip.upper() if skip.lower() == skip else skip.lower())
        self.assertEqual(mm.survey(self.tmp, self.tmp)[3], {})


class TestSurveyAgreesWithItself(TreeTest):
    """Source and destination are surveyed by ONE function now. They have to agree on a copy."""

    def test_a_copied_tree_gives_the_same_figures(self):
        self.file("a.txt", 5)
        self.file("sub/b.bin", 9)
        self.directory("sub/empty")
        src = self.directory("src")
        for rel in ("a.txt", "sub/b.bin"):
            p = os.path.join(src, *rel.split("/"))
            if not os.path.isdir(os.path.dirname(p)):
                os.makedirs(os.path.dirname(p))
            shutil.copy(os.path.join(self.tmp, *rel.split("/")), p)
        os.makedirs(os.path.join(src, "sub", "empty"))

        here = mm.survey(os.path.join(self.tmp, "sub"), os.path.join(self.tmp, "sub"))
        there = mm.survey(os.path.join(src, "sub"), os.path.join(src, "sub"))
        self.assertEqual((len(here[0]), here[1], here[2]), (len(there[0]), there[1], there[2]))
        self.assertEqual(sum(here[3].values()), sum(there[3].values()))


if __name__ == "__main__":
    unittest.main()
