# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Putting two directories that differ only in case into one.

NOTHING HERE TOUCHES THE COLLECTION. Every fixture is a fresh tempfile.mkdtemp() tree and the
collection root is never named. The tool's `--root` defaults to common.MIRROR_ROOT, so each case
passes its temporary root explicitly -- a test for a tool that MOVES AND DELETES must not be able
to reach real data through a default argument.

AND THE FIXTURE CANNOT BE BUILT THE OBVIOUS WAY. `Docs/x` and `docs/x` cannot both exist in an
ordinary Windows directory; the real collection holds them only because those directories carry
the per-directory case-sensitivity flag. So `groups_in` takes the index as an argument and the
cases below hand it one -- the grouping is string work and deserves to be tested as such.

WHY ANY OF THIS EXISTS. Rar.exe cannot store two paths differing only in case: it keeps ONE, says
nothing, and exits 0. 7-Zip refuses outright. Extracting such a pair onto a normal Windows folder
produces one file with the wrong name AND the wrong content while reporting "Alles OK". So the
collection has to become something Windows can hold, and where two directories differ only in case
their contents go into one -- "as if it had arrived that way from the mirror".

THE RULE IS UNIFORM, WHICH IS THE OWNER'S CHOICE: the first name in sorted order keeps its name.
It sometimes moves the many into the few -- ardent-tool's `PS55/docs` has 157 files against
`PS55/Docs`'s 1, and `Docs` wins because `D` sorts before `d` -- and that is the price of a rule
nobody has to remember exceptions to.
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

TOOL = common.load_peer("merge-case-dirs.py", "_merge", HERE)

SRC_DIR = HERE


def index_of(paths):
    """{path: (size, mtime_ns, sha256)} from {path: digest} or a list of paths."""
    if isinstance(paths, dict):
        return dict((rel, (1, 0, digest)) for rel, digest in paths.items())
    return dict((rel, (1, 0, "d" + str(n))) for n, rel in enumerate(paths))


class WhichGroupsAreSafeToMerge(unittest.TestCase):

    def test_a_plain_pair_merges_into_the_sorted_first_name(self):
        got = TOOL.mergeable("r", "a", index_of(["Docs/one.txt", "docs/two.txt"]))
        self.assertEqual(len(got), 1)
        target, others, moves, clash = got[0]
        self.assertEqual(target, "Docs")
        self.assertEqual(others, ["docs"])
        self.assertEqual(moves, [("docs/two.txt", "Docs/two.txt")])
        self.assertEqual(clash, [])

    def test_THE_MANY_MOVE_INTO_THE_FEW_IF_THAT_IS_WHERE_THE_RULE_POINTS(self):
        """ardent-tool: `PS55/docs` holds 157 files and `PS55/Docs` holds 1, and `Docs` wins.
        Uniform beats cheap -- the alternative was a rule that depends on which side is bigger,
        and nobody would remember which archive got which treatment."""
        paths = ["PS55/Docs/keep.pdf"] + ["PS55/docs/f%d.pdf" % n for n in range(157)]
        got = TOOL.mergeable("r", "a", index_of(paths))
        self.assertEqual(got[0][0], "PS55/Docs")
        self.assertEqual(len(got[0][2]), 157)

    def test_A_REAL_NAME_CLASH_IS_REFUSED_AND_NAMED(self):
        """16 of the 17 refused groups are blocked by one auxiliary file, TRANS.TBL -- an ISO-9660
        table describing the directory it sits in, so the one file whose content a merge would
        have to change. ibm-aix's fixes/V4 against fixes/v4 has 1 887 clashing names."""
        idx = index_of({"X/TRANS.TBL": "aaa", "x/TRANS.TBL": "bbb", "x/other": "ccc"})
        self.assertEqual(TOOL.mergeable("r", "a", idx), [])
        every = TOOL.groups_in("r", "a", idx)
        self.assertEqual(every[0][3], ["trans.tbl"])

    def test_THE_SAME_NAME_WITH_THE_SAME_BYTES_IS_NOT_A_CLASH(self):
        """funet-aix's RS6000 and rs6000 hold the same 20 files with the same digests. One copy
        survives the merge, the other is dropped, and nothing is lost."""
        idx = index_of({"RS6000/a": "same", "rs6000/a": "same"})
        got = TOOL.mergeable("r", "a", idx)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][3], [])

    def test_a_NESTED_group_is_left_to_its_parent(self):
        """aixpdslib/pub/URT and pub/URT/RISC both collide; merging the parent carries the child.
        Acting on both would move the same files twice."""
        idx = index_of(["pub/URT/RISC/a", "pub/urt/RISC/b"])
        got = TOOL.groups_in("r", "a", idx)
        self.assertEqual([g[0] for g in got], ["pub/URT"])

    def test_three_casings_all_land_in_the_first(self):
        idx = index_of(["A/one", "a/two", "A~x/three"])
        got = TOOL.mergeable("r", "a", index_of(["A/one", "a/two"]))
        self.assertEqual(got[0][1], ["a"])
        self.assertTrue(idx)

    def test_an_ordinary_tree_has_no_groups(self):
        self.assertEqual(TOOL.mergeable("r", "a", index_of(["one/a", "two/b"])), [])

    def test_a_file_colliding_with_a_file_is_not_this_tools_business(self):
        """Only DIRECTORY components are grouped here. A pair of files differing in case inside
        one directory is the 4 269-file question this tool deliberately does not answer."""
        self.assertEqual(TOOL.mergeable("r", "a", index_of(["d/A.txt", "d/a.txt"])), [])


class Tree(object):
    """A throwaway archive on disk, built from {relative path: bytes}, with its bookkeeping."""

    def __init__(self, files, archive="arch"):
        self.root = tempfile.mkdtemp(prefix="merge-")
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


class TheIndexAndManifestsFollowTheMove(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_a_moved_path_keeps_every_digest_it_had(self):
        self.tree = Tree({"Docs/keep.txt": b"one", "stay.txt": b"two"})
        before = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertTrue(TOOL.remap(self.tree.root, self.tree.archive,
                                   {"Docs/keep.txt": "docs/keep.txt"}, set()))
        after = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertIn("docs/keep.txt", after)
        self.assertNotIn("Docs/keep.txt", after)
        self.assertEqual(after["docs/keep.txt"], before["Docs/keep.txt"])
        self.assertEqual(after["stay.txt"], before["stay.txt"])

    def test_ALL_FOUR_MANIFESTS_FOLLOW_IT_TOO(self):
        """Four formats, and `.sfv` puts the columns the other way round from sha256sum(1). They
        are rewritten through the library's own writers, so no format is spelled out twice."""
        self.tree = Tree({"Docs/keep.txt": b"one"})
        TOOL.remap(self.tree.root, self.tree.archive, {"Docs/keep.txt": "docs/keep.txt"}, set())
        for name in sorted(common.MANIFEST_FILES.values()) + [common.SUMS_FILE]:
            with io.open(os.path.join(self.tree.dir, name), encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("docs/keep.txt", body, name)
            self.assertNotIn("Docs/keep.txt", body, name)

    def test_a_dropped_duplicate_leaves_the_index(self):
        self.tree = Tree({"RS6000/a": b"same", "keep.txt": b"x"})
        TOOL.remap(self.tree.root, self.tree.archive, {}, {"RS6000/a"})
        after = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertEqual(sorted(after), ["keep.txt"])

    def test_NOTHING_IS_RE_HASHED(self):
        """A file moved within one volume has the bytes it had. Re-indexing instead would read
        every moved byte to learn what was already recorded."""
        self.tree = Tree({"a.txt": b"x"})
        src = io.open(os.path.join(HERE, "merge-case-dirs.py"), encoding="utf-8").read()
        block = src[src.index("def remap("):src.index("def main(")]
        self.assertNotIn("sha256_file", block)
        self.assertNotIn("digests_of_file", block)

    def test_it_refuses_if_two_rows_would_land_on_one_path(self):
        """The merge is only attempted for groups with no clash, so this is a belt-and-braces
        refusal -- and it must be a refusal rather than a silently lost row."""
        self.tree = Tree({"A/x": b"one", "keep": b"two"})
        self.assertFalse(TOOL.remap(self.tree.root, self.tree.archive,
                                    {"A/x": "keep"}, set(), report=lambda _m: None))


class PruningRefusesWhenSomethingIsThere(unittest.TestCase):
    r"""A file is checked before it moves; a directory goes because one `os.listdir` was empty."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prune-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def make(self, rel, data=b"x"):
        full = os.path.join(self.root, *rel.split("/"))
        parent = os.path.dirname(full)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with io.open(full, "wb") as fh:
            fh.write(data)
        return full

    def test_a_directory_holding_another_file_is_NOT_removed(self):
        self.make("a/deep/stays.txt")
        n = TOOL.prune_empty_dirs(self.root, "", "a/deep", report=lambda _m: None)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "a", "deep")))

    def test_a_directory_holding_a_SUBdirectory_is_NOT_removed(self):
        self.make("a/deep/sub/stays.txt")
        n = TOOL.prune_empty_dirs(self.root, "", "a/deep", report=lambda _m: None)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "a", "deep", "sub")))

    def test_a_directory_holding_a_HIDDEN_file_is_NOT_removed(self):
        """Our own bookkeeping is dotfiles, and `os.listdir` sees them -- unlike a glob of `*`."""
        self.make("a/deep/.mirror-gone")
        n = TOOL.prune_empty_dirs(self.root, "", "a/deep", report=lambda _m: None)
        self.assertEqual(n, 0)

    def test_it_climbs_only_while_each_level_is_empty(self):
        self.make("a/keep.txt")
        os.makedirs(os.path.join(self.root, "a", "b", "c"))
        n = TOOL.prune_empty_dirs(self.root, "", "a/b/c", report=lambda _m: None)
        self.assertEqual(n, 2)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "a", "keep.txt")))

    def test_a_path_that_is_not_a_directory_stops_it(self):
        n = TOOL.prune_empty_dirs(self.root, "", "nope/deeper", report=lambda _m: None)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isdir(self.root))


class TheCommandLineRefusesBeforeItActs(unittest.TestCase):

    def setUp(self):
        self.tree = Tree({"Docs/one.txt": b"x", "other.txt": b"y"})
        self.out = io.StringIO()
        self.keep = sys.stdout
        sys.stdout = self.out

    def tearDown(self):
        sys.stdout = self.keep
        self.tree.close()

    def test_THE_DEFAULT_IS_A_DRY_RUN_AND_IT_WRITES_NOTHING(self):
        code = TOOL.main(["--root", self.tree.root])
        text = self.out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("NOTHING WAS MOVED", text)
        self.assertTrue(self.tree.has("Docs/one.txt"))

    def test_apply_without_a_backup_is_refused(self):
        code = TOOL.main(["--root", self.tree.root, "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("needs --backup", self.out.getvalue())
        self.assertTrue(self.tree.has("Docs/one.txt"))

    def test_a_collection_that_is_not_there(self):
        self.assertEqual(TOOL.main(["--root", os.path.join(self.tree.root, "nope")]), 2)


class TheRecord(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_it_names_both_sides_and_follows_the_collections_convention(self):
        """FRAGMENT-COPIES-REMOVED.txt and EMPTY-CASE-TWINS-REMOVED.txt have the same shape: a
        header saying why and how it was verified, then `from -> to` pairs."""
        self.tree = Tree({"Docs/one.txt": b"x"})
        groups = [("Docs", ["docs"], [("docs/two.txt", "Docs/two.txt")], [])]
        path = TOOL.write_record(self.tree.root, self.tree.archive, groups)
        with io.open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertTrue(body.startswith("# Directories merged "))
        self.assertIn("docs\n  -> Docs", body)

    def test_the_record_name_is_registered_as_bookkeeping(self):
        """EMPTY-CASE-TWINS-REMOVED.txt was missing from BOOKKEEPING_FILES for about an hour on
        2026-10-05 and `mirror.py --verify` caught it at once: the file sat outside the index and
        read as unindexed content. Same mistake, not twice."""
        self.tree = Tree({"a": b"x"})
        self.assertIn(TOOL.RECORD_FILE, common.BOOKKEEPING_FILES)
        self.assertNotIn(TOOL.RECORD_FILE, common.OWN_FILES)


class TheOrderOfWhatComesAfterwards(unittest.TestCase):
    r"""--index BEFORE restate-marker, and getting it wrong is what happened.

    The record this tool writes is a NEW file in the archive, and it lands AFTER the index was
    rewritten -- so it is on disk, the marker counts it, and the index and all four manifests do
    not know it. Measured on 2026-10-05, restating first: all six touched archives reported
    "crc32 covers 25820 of 25821 ... --index-force once completes them", one file short in every
    manifest, for a tree that was correct. Indexing afterwards then adds a file the marker has
    already been told about, so the marker is wrong again.

    SO BOTH STEPS ARE NAMED, IN ORDER, PER ARCHIVE AND ONCE MORE AT THE END. A tool that leaves a
    manifest one file short and tells nobody is a tool that teaches its reader to ignore
    "--index-force once completes them", which is the message that would otherwise mean something.
    """

    def source(self):
        with io.open(os.path.join(SRC_DIR, "merge-case-dirs.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_the_docstring_states_both_steps_in_order(self):
        doc = TOOL.__doc__
        self.assertIn("mirror.py --archive <name> --index", doc)
        self.assertIn("restate-marker.py --archive <name> --apply", doc)
        self.assertLess(doc.index("--index"), doc.index("restate-marker"))

    def test_the_per_archive_hint_names_index_first(self):
        src = self.source()
        block = src[src.index("NEXT: mirror.py"):]
        self.assertLess(block.index("--index"), block.index("restate-marker"))

    def test_and_it_says_so_again_at_the_end(self):
        """One archive's hint scrolls away; the closing line is what a reader of the tail sees."""
        self.assertIn("BEFORE restate-marker.py", self.source())

    def test_the_reason_is_recorded_and_not_just_the_instruction(self):
        """An instruction without its reason is one somebody reorders later."""
        self.assertIn("not in the index it rewrote", self.source())



if __name__ == "__main__":
    unittest.main(verbosity=2)
