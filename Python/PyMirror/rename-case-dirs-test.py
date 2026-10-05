# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Giving one of two directories that differ only in case a name Windows can keep apart.

NOTHING HERE TOUCHES THE COLLECTION. Every fixture is a fresh tempfile.mkdtemp() tree and the
collection root is never named. The tool's `--root` defaults to common.MIRROR_ROOT, so each case
passes its temporary root explicitly -- a test for a tool that RENAMES must not reach real data
through a default argument.

AND THE FIXTURE CANNOT ALWAYS BE BUILT ON DISK. `X` and `x` cannot both exist in an ordinary
Windows directory; the real collection holds them only because those directories carry the
per-directory case-sensitivity flag. So `candidates` takes the index as an argument and the cases
below hand it one -- choosing which member to rename is string work and deserves to be tested as
such.

WHY RENAMING RATHER THAN MERGING. merge-case-dirs.py puts two such directories into one, which is
right where their contents belong together. It cannot be used in ibiblio-historic-linux, where
every group is blocked by `TRANS.TBL` -- the ISO-9660 table that describes the very directory it
sits in, so the one file a merge would have to rewrite. Renaming leaves both directories and both
tables untouched: measured on 2026-10-05, 16 groups, 65 file paths, 0 bytes of content changed,
and 0 colliding directories left. Merging the same 16 would have moved ~700 files and rewritten
16 tables.
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

TOOL = common.load_peer("rename-case-dirs.py", "_rename", HERE)


def index_of(paths):
    return dict((rel, (1, 0, "d%d" % n)) for n, rel in enumerate(paths))


class WhichMemberGetsRenamed(unittest.TestCase):

    def test_the_upper_case_member_gets_the_underscore(self):
        got = TOOL.candidates("r", "a", index_of(["d/X/one", "d/x/two"]))
        self.assertEqual(got, [("d/X", "d/X_", None)])

    def test_THE_SUFFIX_IS_A_MARK_AND_THE_ORIGINAL_IS_RECORDED(self):
        """The owner's words: "das man weiss, diese sind abgeleitet". A trailing underscore is
        legal on NTFS, survives every archiver and reads as mechanical -- and the name it replaced
        lives in CASE-DIRS-RENAMED.txt, which is the only place it survives."""
        self.assertEqual(TOOL.MARK, "_")
        self.assertIn("renamed from  ->  to", TOOL.RECORD_HEADER)

    def test_TWO_UPPER_CASE_MEMBERS_ARE_REFUSED_NOT_GUESSED(self):
        """ibm-aix holds IJ36417 and ij36417: both could take the underscore and the rule has no
        business choosing. The group comes back with a reason so a reader of the plan sees it."""
        got = TOOL.candidates("r", "a", index_of(["d/IJ36417/x", "d/IJ3641/y"]))
        self.assertEqual(got, [])
        got = TOOL.candidates("r", "a", index_of(["d/AB/x", "d/Ab/y"]))
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0][1])
        self.assertIn("--pair", got[0][2])

    def test_NO_UPPER_CASE_MEMBER_IS_ALSO_REFUSED(self):
        """ibm-aix's generalIfix and generalifix both start lower-case."""
        got = TOOL.candidates("r", "a", index_of(["d/generalIfix/x", "d/generalifix/y"]))
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0][1])

    def test_a_name_that_is_already_taken_is_refused(self):
        got = TOOL.candidates("r", "a", index_of(["d/X/one", "d/x/two", "d/X_/three"]))
        self.assertTrue([g for g in got if g[1] is None and "already taken" in (g[2] or "")])

    def test_an_ordinary_tree_proposes_nothing(self):
        self.assertEqual(TOOL.candidates("r", "a", index_of(["one/a", "two/b"])), [])

    def test_a_pair_of_FILES_differing_in_case_is_not_this_tools_business(self):
        """Only directory components are grouped. The ~3 800 file-level collisions are a separate
        question this tool deliberately does not answer."""
        self.assertEqual(TOOL.candidates("r", "a", index_of(["d/A.txt", "d/a.txt"])), [])


class Tree(object):
    """A throwaway archive on disk with its bookkeeping, from {relative path: bytes}."""

    def __init__(self, files, archive="arch"):
        self.root = tempfile.mkdtemp(prefix="ren-")
        self.archive = archive
        self.dir = os.path.join(self.root, archive)
        rows = {}
        for rel, data in files.items():
            full = os.path.join(self.dir, *rel.split("/"))
            parent = os.path.dirname(full)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with io.open(full, "wb") as fh:
                fh.write(data)
            rows[rel] = (len(data), 0, common.sha256_file(full))
        common.write_index(os.path.join(self.dir, common.INDEX_FILE),
                           os.path.join(self.dir, common.SUMS_FILE), rows)
        common.write_manifests(self.dir, dict(
            (rel, {"sha1": "1" * 40, "md5": "2" * 32, "crc32": "AABBCCDD"}) for rel in files))

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def has(self, rel):
        return os.path.isfile(os.path.join(self.dir, *rel.split("/")))


class AMoveSomebodyElseMade(unittest.TestCase):
    r"""The owner moved ibm-aix's fixes/V4 into fixes/v4 by hand; the tree was then right and the
    index still named the old paths. The four files matched their recorded SHA-256 exactly.
    """

    def tearDown(self):
        self.tree.close()

    def test_it_is_RECOGNISED_only_when_every_digest_matches(self):
        self.tree = Tree({"fixes/v4/ml/a.tar.gz": b"payload"})
        rows = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        rows["fixes/V4/ml/a.tar.gz"] = rows.pop("fixes/v4/ml/a.tar.gz")
        common.write_index(os.path.join(self.tree.dir, common.INDEX_FILE),
                           os.path.join(self.tree.dir, common.SUMS_FILE), rows)
        self.assertTrue(TOOL.already_done(self.tree.root, self.tree.archive,
                                          "fixes/V4", "fixes/v4"))

    def test_A_DELETED_SOURCE_IS_NOT_PROOF_OF_A_CLEAN_MOVE(self):
        """A tool that took "the source is gone" as proof would also accept a source that was
        simply deleted. So every affected file is hashed at the target and compared."""
        self.tree = Tree({"keep.txt": b"x"})
        rows = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        rows["fixes/V4/ml/a.tar.gz"] = (7, 0, "f" * 64)
        common.write_index(os.path.join(self.tree.dir, common.INDEX_FILE),
                           os.path.join(self.tree.dir, common.SUMS_FILE), rows)
        self.assertIsNone(TOOL.already_done(self.tree.root, self.tree.archive,
                                            "fixes/V4", "fixes/v4", report=lambda _m: None))

    def test_a_wrong_digest_at_the_target_is_a_refusal(self):
        self.tree = Tree({"fixes/v4/ml/a.tar.gz": b"different bytes"})
        rows = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        rows["fixes/V4/ml/a.tar.gz"] = (7, 0, "f" * 64)
        del rows["fixes/v4/ml/a.tar.gz"]
        common.write_index(os.path.join(self.tree.dir, common.INDEX_FILE),
                           os.path.join(self.tree.dir, common.SUMS_FILE), rows)
        self.assertIsNone(TOOL.already_done(self.tree.root, self.tree.archive,
                                            "fixes/V4", "fixes/v4", report=lambda _m: None))

    def test_EXISTENCE_IS_ASKED_CASE_SENSITIVELY_AND_NOT_VIA_os_path_exists(self):
        """On an ordinary Windows directory `fixes/V4` RESOLVES TO `fixes/v4`, so os.path.exists
        answers True for a name that is not there -- and telling those two apart is the entire
        point of this tool. It only answered correctly for ibm-aix because `fixes` happens to
        carry the per-directory case-sensitivity flag, confirmed with fsutil on 2026-10-05. A
        check that depends on a flag somebody else set is not a check, so the parent is listed and
        the name compared byte for byte.
        """
        self.tree = Tree({"fixes/v4/ml/a.tar.gz": b"payload"})
        self.assertTrue(TOOL.spelled_exactly(self.tree.root, self.tree.archive, "fixes/v4"))
        self.assertFalse(TOOL.spelled_exactly(self.tree.root, self.tree.archive, "fixes/V4"))
        self.assertFalse(TOOL.spelled_exactly(self.tree.root, self.tree.archive, "fixes/v4/ML"))
        self.assertFalse(TOOL.spelled_exactly(self.tree.root, self.tree.archive, "nope"))

    def test_and_the_tool_does_not_use_exists_for_that_question(self):
        self.tree = Tree({"a": b"x"})
        src = io.open(os.path.join(HERE, "rename-case-dirs.py"), encoding="utf-8").read()
        block = src[src.index("def already_done("):src.index("def save_bookkeeping(")]
        self.assertIn("spelled_exactly(", block)

    def test_a_source_that_is_still_there_is_not_already_done(self):
        self.tree = Tree({"fixes/V4/ml/a.tar.gz": b"payload"})
        self.assertFalse(TOOL.already_done(self.tree.root, self.tree.archive,
                                           "fixes/V4", "fixes/v4"))


class TheIndexAndManifestsFollowTheRename(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_every_path_below_it_moves_and_keeps_its_digests(self):
        self.tree = Tree({"d/X/one": b"a", "d/X/deep/two": b"b", "stay.txt": b"c"})
        before = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertTrue(TOOL.remap(self.tree.root, self.tree.archive, [("d/X", "d/X_", 2)]))
        after = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertEqual(sorted(after), ["d/X_/deep/two", "d/X_/one", "stay.txt"])
        self.assertEqual(after["d/X_/one"], before["d/X/one"])
        self.assertEqual(after["stay.txt"], before["stay.txt"])

    def test_ALL_FOUR_MANIFESTS_FOLLOW_IT_TOO(self):
        """Four formats, and `.sfv` puts the columns the other way round from sha256sum(1)."""
        self.tree = Tree({"d/X/one": b"a"})
        TOOL.remap(self.tree.root, self.tree.archive, [("d/X", "d/X_", 1)])
        for name in sorted(common.MANIFEST_FILES.values()) + [common.SUMS_FILE]:
            with io.open(os.path.join(self.tree.dir, name), encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("d/X_/one", body, name)
            self.assertNotIn("d/X/one", body, name)

    def test_NOTHING_IS_RE_HASHED(self):
        """Renaming a directory changes no file's bytes."""
        self.tree = Tree({"a": b"x"})
        src = io.open(os.path.join(HERE, "rename-case-dirs.py"), encoding="utf-8").read()
        block = src[src.index("def remap("):src.index("def main(")]
        self.assertNotIn("sha256_file", block)

    def test_a_prefix_that_only_looks_like_one_is_not_moved(self):
        """`d/XY/one` must not follow a rename of `d/X`, which a careless startswith would do."""
        self.tree = Tree({"d/X/one": b"a", "d/XY/two": b"b"})
        TOOL.remap(self.tree.root, self.tree.archive, [("d/X", "d/X_", 1)])
        after = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertEqual(sorted(after), ["d/XY/two", "d/X_/one"])


class TheCommandLineRefusesBeforeItActs(unittest.TestCase):

    def setUp(self):
        self.tree = Tree({"d/X/one": b"x"})
        self.out = io.StringIO()
        self.keep = sys.stdout
        sys.stdout = self.out

    def tearDown(self):
        sys.stdout = self.keep
        self.tree.close()

    def test_THE_DEFAULT_IS_A_DRY_RUN_AND_IT_WRITES_NOTHING(self):
        code = TOOL.main(["--root", self.tree.root, "--archive", self.tree.archive,
                          "--pair", "d/X=d/X_"])
        self.assertEqual(code, 0)
        self.assertIn("NOTHING WAS RENAMED", self.out.getvalue())
        self.assertTrue(self.tree.has("d/X/one"))

    def test_apply_without_a_backup_is_refused(self):
        code = TOOL.main(["--root", self.tree.root, "--archive", self.tree.archive,
                          "--pair", "d/X=d/X_", "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("needs --backup", self.out.getvalue())
        self.assertTrue(self.tree.has("d/X/one"))

    def test_pair_needs_exactly_one_archive(self):
        """A pair is a path inside ONE archive, and applying it to every archive that happens to
        have that path is not something to allow by accident."""
        code = TOOL.main(["--root", self.tree.root, "--pair", "d/X=d/X_"])
        self.assertEqual(code, 2)
        self.assertIn("exactly one --archive", self.out.getvalue())

    def test_a_malformed_pair_is_refused(self):
        code = TOOL.main(["--root", self.tree.root, "--archive", self.tree.archive,
                          "--pair", "no-equals-sign"])
        self.assertEqual(code, 2)

    def test_a_collection_that_is_not_there(self):
        self.assertEqual(TOOL.main(["--root", os.path.join(self.tree.root, "nope")]), 2)


class TheRecordAndTheOrderAfterwards(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_the_record_names_both_sides(self):
        self.tree = Tree({"d/X/one": b"x"})
        path = TOOL.write_record(self.tree.root, self.tree.archive, [("d/X", "d/X_", 1)])
        with io.open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertTrue(body.startswith("# Directories renamed "))
        self.assertIn("d/X\n  -> d/X_", body)

    def test_the_record_name_is_registered_as_bookkeeping(self):
        """EMPTY-CASE-TWINS-REMOVED.txt was missing from BOOKKEEPING_FILES for about an hour on
        2026-10-05 and `mirror.py --verify` caught it at once. Same mistake, not three times."""
        self.tree = Tree({"a": b"x"})
        self.assertIn(TOOL.RECORD_FILE, common.BOOKKEEPING_FILES)
        self.assertNotIn(TOOL.RECORD_FILE, common.OWN_FILES)

    def test_INDEX_COMES_BEFORE_RESTATE_MARKER(self):
        """The record is a new file landing after the index was rewritten: on disk, counted by the
        marker, unknown to the index. Restating first made all six archives report one file short
        in every manifest on 2026-10-05, for trees that were correct."""
        self.tree = Tree({"a": b"x"})
        doc = TOOL.__doc__
        self.assertIn("--index", doc)
        self.assertLess(doc.index("--index"), doc.index("restate-marker"))
        src = io.open(os.path.join(HERE, "rename-case-dirs.py"), encoding="utf-8").read()
        block = src[src.index("NEXT: mirror.py"):]
        self.assertLess(block.index("--index"), block.index("restate-marker"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
