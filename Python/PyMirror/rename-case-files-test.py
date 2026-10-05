# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Tests for rename-case-files.py.

EVERY FIXTURE IS A FRESH tempfile.mkdtemp() AND NO TEST NAMES THE COLLECTION. `--root` is always
passed explicitly and always points into a temporary directory. Nothing here removes a directory
it did not create, and nothing removes a non-empty one.

THE CASE PAIR IS INJECTED, NOT WRITTEN TO DISK, wherever the decision depends on it. `A.TBL` and
`a.TBL` resolve to ONE file on an ordinary Windows directory -- the real collection holds both
only because those directories carry the per-directory case-sensitivity flag -- so a fixture that
wrote both would end up with one file whose digest trivially equals itself. The index is written
from the names given, and `digest_of` is handed a table saying what each NAME holds.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common                                                       # noqa: E402

TOOL = common.load_peer("rename-case-files.py", "_rcf", HERE)


def write(path, data):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    mode = "wb" if isinstance(data, bytes) else "w"
    with io.open(path, mode) as handle:
        handle.write(data)


class Tree(object):
    """A throwaway archive with an index, built from {relative path: bytes}."""

    def __init__(self, files, archive="arch"):
        self.root = tempfile.mkdtemp(prefix="rcf-")
        self.archive = archive
        self.dir = os.path.join(self.root, archive)
        self.digests = {}
        rows = {}
        for rel, data in files.items():
            full = os.path.join(self.dir, *rel.split("/"))
            write(full, data)
            self.digests[os.path.abspath(full)] = common.sha256_bytes(data)
            rows[rel] = (len(data), 0, common.sha256_bytes(data))
        common.write_index(os.path.join(self.dir, common.INDEX_FILE),
                           os.path.join(self.dir, common.SUMS_FILE), rows)
        common.write_manifests(self.dir, dict(
            (rel, {"sha1": "1" * 40, "md5": "2" * 32, "crc32": "AABBCCDD"}) for rel in files))

    def digest_of(self, path):
        return self.digests.get(os.path.abspath(path))

    def plan(self, report=None):
        return TOOL.candidates(self.root, self.archive, digest_of=self.digest_of,
                               report=report or (lambda *_a: None))

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Fixture(unittest.TestCase):
    def tearDown(self):
        if getattr(self, "tree", None):
            self.tree.close()


class WhatNeedsARename(Fixture):
    def test_two_spellings_with_different_content(self):
        self.tree = Tree({"d/Wm.n": b"tk version", "d/wm.n": b"a much longer tcl version"})
        self.assertEqual([(old, new) for old, new, _s, _p in self.tree.plan()],
                         [("d/wm.n", "d/wm.n_")])

    def test_the_FIRST_spelling_in_sorted_order_keeps_its_name(self):
        r"""rename-case-dirs.py's rule, chosen to be predictable rather than clever."""
        self.tree = Tree({"d/B.txt": b"one", "d/b.txt": b"two"})
        old, new, _size, partner = self.tree.plan()[0]
        self.assertEqual((old, new), ("d/b.txt", "d/b.txt_"))
        self.assertEqual(partner, "d/B.txt")

    def test_the_underscore_goes_at_the_very_END_of_the_name(self):
        r"""`wm.n_` reads as "wm.n, adjusted"; `wm_.n` reads as a different file."""
        self.tree = Tree({"d/A.TBL": b"one", "d/a.TBL": b"two"})
        _old, new, _size, _partner = self.tree.plan()[0]
        self.assertTrue(new.endswith("_"))
        self.assertEqual(new, "d/a.TBL_")

    def test_a_DOUBLE_extension_keeps_the_underscore_at_the_end(self):
        r"""THE REASON THE TIDIER RULE WAS REJECTED. Inserting before the final dot has to decide
        whether `.tar.gz` is one extension or two, and this collection holds `.tar.gz`,
        `.epkg.Z`, `.nsm.cat.gz` and `lincks2.2.1db.tgz` side by side -- version numbers and
        extensions are not distinguishable by a dot.
        """
        self.tree = Tree({"d/Thing.tar.gz": b"one", "d/thing.tar.gz": b"two"})
        _old, new, _size, _partner = self.tree.plan()[0]
        self.assertEqual(new, "d/thing.tar.gz_")

    def test_a_version_number_in_the_name_is_not_mistaken_for_an_extension(self):
        self.tree = Tree({"d/Lincks2.2.1db.tgz": b"one", "d/lincks2.2.1db.tgz": b"two"})
        _old, new, _size, _partner = self.tree.plan()[0]
        self.assertEqual(new, "d/lincks2.2.1db.tgz_")

    def test_three_spellings_rename_two_and_keep_the_first(self):
        r"""netstation.msg.CA_ES / Ca_ES / ca_ES is a real three-member shape."""
        self.tree = Tree({"d/AB": b"one", "d/Ab": b"two", "d/ab": b"three"})
        self.assertEqual([(old, new) for old, new, _s, _p in self.tree.plan()],
                         [("d/Ab", "d/Ab_"), ("d/ab", "d/ab_")])

    def test_the_size_recorded_is_the_renamed_file_s_own(self):
        self.tree = Tree({"d/A": b"1234567", "d/a": b"12"})
        _old, _new, size, _partner = self.tree.plan()[0]
        self.assertEqual(size, 2)

    def test_a_lone_file_is_not_a_candidate(self):
        self.tree = Tree({"d/only.txt": b"x", "d/other.txt": b"y"})
        self.assertEqual(self.tree.plan(), [])


class WhatThisToolRefusesToTouch(Fixture):
    def test_IDENTICAL_content_is_left_for_the_other_tool(self):
        r"""Renaming a byte-identical duplicate would keep it for ever under a made-up name.

        `drop-empty-case-twins.py --same-content` can drop one of those and prove nothing was
        lost, which a rename cannot.
        """
        self.tree = Tree({"d/Filink.zip": b"payload", "d/filink.zip": b"payload"})
        self.assertEqual(self.tree.plan(), [])

    def test_and_it_says_why_rather_than_passing_over_it_in_silence(self):
        said = []
        self.tree = Tree({"d/A": b"same", "d/a": b"same"})
        self.tree.plan(report=said.append)
        self.assertIn("identical content", "\n".join(said))

    def test_EQUAL_SIZE_with_different_content_IS_renamed(self):
        r"""THE MEASUREMENT THAT MAKES SIZE USELESS HERE. Seven groups in the collection hold
        members of exactly equal size and different bytes -- README_IZ28002 against
        README_iz28002, both 244 B. A size test would have destroyed those seven files.
        """
        self.tree = Tree({"d/README_IZ28002": b"A" * 244, "d/README_iz28002": b"B" * 244})
        self.assertEqual([(old, new) for old, new, _s, _p in self.tree.plan()],
                         [("d/README_iz28002", "d/README_iz28002_")])

    def test_a_member_that_is_not_on_disk_stops_its_group(self):
        self.tree = Tree({"d/A": b"one", "d/a": b"two"})
        self.tree.digests.pop(os.path.abspath(os.path.join(self.tree.dir, "d", "A")), None)
        self.assertEqual(self.tree.plan(), [])

    def test_a_target_name_THAT_IS_ON_DISK_refuses_the_whole_run(self):
        r"""`a_` may be a real file of its own, and a rename onto it is an overwrite.

        The disk check fires first, which is the right order: `spelled_exactly` is a first-hand
        look at the directory, while the index is a record that may be stale.
        """
        self.tree = Tree({"d/A": b"one", "d/a": b"two", "d/a_": b"a real file called a_"})
        said = []
        self.assertIsNone(self.tree.plan(report=said.append))
        self.assertIn("is already there", "\n".join(said))

    def test_a_target_name_that_is_only_INDEXED_also_refuses(self):
        r"""The second guard, for the case the disk cannot answer: a path the index names but
        that is not on disk under that spelling. Both guards exist because either source alone
        can be the one that knows."""
        self.tree = Tree({"d/A": b"one", "d/a": b"two", "d/a_": b"indexed"})
        os.remove(os.path.join(self.tree.dir, "d", "a_"))        # indexed, no longer on disk
        said = []
        self.assertIsNone(self.tree.plan(report=said.append))
        self.assertIn("collides with an indexed path", "\n".join(said))


class NarrowingToABranch(Fixture):
    r"""`--under`, because one archive's branches want different answers.

    ibiblio's `ftp-archives` is nine renames the owner asked for; its `distributions` is
    eighty-three he has not decided on. A run that could only take the whole archive would make
    that decision for him.
    """

    def setUp(self):
        self.tree = Tree({
            "wanted/A": b"one", "wanted/a": b"two",
            "other/B": b"three", "other/b": b"four",
        })

    def test_without_under_both_branches_are_considered(self):
        self.assertEqual(len(self.tree.plan()), 2)

    def test_under_keeps_only_the_named_branch(self):
        rows = TOOL.candidates(self.tree.root, self.tree.archive,
                               digest_of=self.tree.digest_of, report=lambda *_a: None,
                               under=["wanted"])
        self.assertEqual([old for old, _n, _s, _p in rows], ["wanted/a"])

    def test_a_trailing_slash_on_the_prefix_is_accepted(self):
        rows = TOOL.candidates(self.tree.root, self.tree.archive,
                               digest_of=self.tree.digest_of, report=lambda *_a: None,
                               under=["wanted/"])
        self.assertEqual(len(rows), 1)

    def test_two_prefixes_can_be_given(self):
        r"""efixes and ifixes are one decision taken in two branches."""
        rows = TOOL.candidates(self.tree.root, self.tree.archive,
                               digest_of=self.tree.digest_of, report=lambda *_a: None,
                               under=["wanted", "other"])
        self.assertEqual(len(rows), 2)

    def test_the_prefix_is_compared_CASE_SENSITIVELY(self):
        r"""A tool about case is the last place to fold it: `Wanted` is not `wanted`."""
        rows = TOOL.candidates(self.tree.root, self.tree.archive,
                               digest_of=self.tree.digest_of, report=lambda *_a: None,
                               under=["Wanted"])
        self.assertEqual(rows, [])

    def test_a_prefix_matching_nothing_yields_nothing_rather_than_everything(self):
        r"""The failure that would quietly widen the run back to the whole archive."""
        rows = TOOL.candidates(self.tree.root, self.tree.archive,
                               digest_of=self.tree.digest_of, report=lambda *_a: None,
                               under=["nope"])
        self.assertEqual(rows, [])


class SpelledExactly(unittest.TestCase):
    r"""os.path.exists answers a DIFFERENT question, and the difference cost a measurement.

    On a directory without the case-sensitivity flag it resolves `fixes/V4` to `fixes/v4` and
    reports True for a name that is not there.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rcf-sp-")
        os.makedirs(os.path.join(self.root, "arch", "d"))
        write(os.path.join(self.root, "arch", "d", "Thing.txt"), b"x")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_exact_spelling_is_found(self):
        self.assertTrue(TOOL.spelled_exactly(self.root, "arch", "d/Thing.txt"))

    def test_another_casing_is_NOT_found_even_though_the_file_opens(self):
        self.assertFalse(TOOL.spelled_exactly(self.root, "arch", "d/thing.txt"))

    def test_a_missing_directory_is_answered_and_not_raised(self):
        self.assertFalse(TOOL.spelled_exactly(self.root, "arch", "nope/thing.txt"))


class TheRunItself(unittest.TestCase):
    def setUp(self):
        self.tree = Tree({"d/Wm.n": b"tk", "d/wm.n": b"tcl and more of it",
                          "other/keep.txt": b"untouched"})
        self.backup = tempfile.mkdtemp(prefix="rcf-bk-")

    def tearDown(self):
        self.tree.close()
        shutil.rmtree(self.backup, ignore_errors=True)

    def run_tool(self, *extra):
        argv = ["--root", self.tree.root, "--archive", self.tree.archive] + list(extra)
        return TOOL.main(argv)

    def test_a_dry_run_renames_nothing(self):
        self.assertEqual(self.run_tool(), 0)
        self.assertTrue(os.path.isfile(os.path.join(self.tree.dir, "d", "wm.n")))
        self.assertFalse(os.path.isfile(os.path.join(self.tree.dir, "d", "wm.n_")))

    def test_apply_without_backup_is_refused(self):
        r"""The five bookkeeping files are the only record of what the paths were."""
        self.assertEqual(self.run_tool("--apply"), 2)
        self.assertTrue(os.path.isfile(os.path.join(self.tree.dir, "d", "wm.n")))

    def test_a_plan_file_can_be_written_without_applying(self):
        r"""THE HEADER ONLY, AND THAT IS NOT LAZINESS. Running through main() means running
        against the real filesystem, where `Wm.n` and `wm.n` are ONE file -- so the group loses a
        member, `candidates` skips it, and the plan is empty here however correct the tool is. The
        rows are pinned where the decision lives, on injected digests, in WhatNeedsARename.
        """
        where = os.path.join(self.backup, "plan.tsv")
        self.assertEqual(self.run_tool("--out", where), 0)
        with io.open(where, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("archive\told\tnew\tsize\tpartner", text)

    def test_the_plan_rows_carry_the_partner_name(self):
        r"""What the plan's fifth column holds, decided where the digests can be injected."""
        tree = Tree({"d/Wm.n": b"tk", "d/wm.n": b"tcl and more of it"})
        try:
            old, new, size, partner = tree.plan()[0]
            self.assertEqual((old, new, partner), ("d/wm.n", "d/wm.n_", "d/Wm.n"))
            self.assertEqual(size, len(b"tcl and more of it"))
        finally:
            tree.close()


class TheIndexAndManifestsFollowTheRename(unittest.TestCase):
    r"""A rename changes no byte, so every digest carries over -- under the new path."""

    def setUp(self):
        self.tree = Tree({"d/A.TBL": b"one", "d/a.TBL": b"two and longer"})

    def tearDown(self):
        self.tree.close()

    def test_the_index_names_the_new_path_and_not_the_old(self):
        pairs = [("d/a.TBL", "d/a.TBL_", 14, "d/A.TBL")]
        self.assertTrue(TOOL.remap(self.tree.root, self.tree.archive, pairs))
        rows = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        flat = set(r.replace("\\", "/") for r in rows)
        self.assertIn("d/a.TBL_", flat)
        self.assertNotIn("d/a.TBL", flat)

    def test_the_other_member_is_untouched(self):
        pairs = [("d/a.TBL", "d/a.TBL_", 14, "d/A.TBL")]
        TOOL.remap(self.tree.root, self.tree.archive, pairs)
        rows = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertIn("d/A.TBL", set(r.replace("\\", "/") for r in rows))

    def test_the_digest_carries_over_unchanged(self):
        before = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        want = dict((k.replace("\\", "/"), v[2]) for k, v in before.items())["d/a.TBL"]
        TOOL.remap(self.tree.root, self.tree.archive, [("d/a.TBL", "d/a.TBL_", 14, "d/A.TBL")])
        after = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        got = dict((k.replace("\\", "/"), v[2]) for k, v in after.items())["d/a.TBL_"]
        self.assertEqual(got, want)

    def test_all_four_manifests_name_the_new_path(self):
        TOOL.remap(self.tree.root, self.tree.archive, [("d/a.TBL", "d/a.TBL_", 14, "d/A.TBL")])
        for name in (common.SUMS_FILE, ".sha1sum", ".md5sum", ".sfv"):
            with io.open(os.path.join(self.tree.dir, name), encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("d/a.TBL_", text, name)

    def test_a_remap_that_would_collide_stops_instead_of_overwriting(self):
        said = []
        pairs = [("d/a.TBL", "d/A.TBL", 14, "d/A.TBL")]       # deliberately onto the keeper
        self.assertFalse(TOOL.remap(self.tree.root, self.tree.archive, pairs, report=said.append))
        self.assertIn("would land on an existing row", "\n".join(said))


class TheRecord(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="rcf-rec-")
        os.makedirs(os.path.join(self.folder, "arch"))

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def read(self):
        with io.open(os.path.join(self.folder, "arch", TOOL.RECORD_FILE),
                     encoding="utf-8") as handle:
            return handle.read()

    def test_it_names_both_files_and_the_size(self):
        TOOL.write_record(self.folder, "arch", [("d/wm.n", "d/wm.n_", 30933, "d/Wm.n")])
        text = self.read()
        self.assertIn("d/wm.n", text)
        self.assertIn("d/wm.n_", text)
        self.assertIn("30933 bytes", text)
        self.assertIn("collided with d/Wm.n", text)

    def test_it_states_that_nothing_was_merged_or_dropped(self):
        r"""The claim a reader has to be able to trust a year from now."""
        TOOL.write_record(self.folder, "arch", [("d/a", "d/a_", 1, "d/A")])
        self.assertIn("NOTHING WAS MERGED AND NOTHING WAS DROPPED", self.read())

    def test_it_explains_which_name_was_kept_and_why(self):
        TOOL.write_record(self.folder, "arch", [("d/a", "d/a_", 1, "d/A")])
        self.assertIn("sorts FIRST", self.read())

    def test_the_record_name_is_registered_as_bookkeeping(self):
        r"""EMPTY-CASE-TWINS-REMOVED.txt was missing from that set for an hour on 2026-10-05, and
        `mirror.py --verify` read it as unindexed content inside that hour."""
        self.assertIn(TOOL.RECORD_FILE, common.BOOKKEEPING_FILES)

    def test_a_second_run_appends_rather_than_replacing(self):
        TOOL.write_record(self.folder, "arch", [("d/a", "d/a_", 1, "d/A")])
        TOOL.write_record(self.folder, "arch", [("d/b", "d/b_", 2, "d/B")])
        text = self.read()
        self.assertIn("d/a_", text)
        self.assertIn("d/b_", text)
        self.assertEqual(text.count("NOTHING WAS MERGED"), 1)   # the header only once


class TheDocumentedReasons(unittest.TestCase):
    def source(self):
        with io.open(os.path.join(HERE, "rename-case-files.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_it_records_why_size_is_not_a_proof(self):
        self.assertIn("244 bytes", TOOL.__doc__)

    def test_it_records_which_shapes_belong_to_the_other_two_answers(self):
        doc = TOOL.__doc__
        self.assertIn("drop-empty-case-twins.py --same-content", doc)
        self.assertIn("goes into a tar", doc)

    def test_it_records_why_the_underscore_goes_at_the_end(self):
        self.assertIn("sorts next to its partner", TOOL.__doc__)

    def test_the_order_of_index_then_marker_is_stated(self):
        src = self.source()
        self.assertLess(src.index("--index"), src.index("restate-marker"))
        self.assertIn("one file short", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
