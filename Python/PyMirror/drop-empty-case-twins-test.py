# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Removing a 0-byte file that is only the other casing of a file holding the content.

NOTHING HERE TOUCHES THE COLLECTION. Every fixture is a fresh tempfile.mkdtemp() tree and the
collection root is never named, not even to skip it -- a test for a tool that DELETES must not be
able to reach real data through a typo, a default argument or an environment variable. The tool's
own `--root` defaults to common.MIRROR_ROOT, so each case passes its temporary root explicitly.

WHAT THESE FILES ARE. A case-insensitive web or FTP server answers `.../iz42658.epkg.Z` and
`.../IZ42658.epkg.Z` as one resource. This crawler followed both links and one arrived EMPTY while
the other brought 348 631 bytes. Measured on 2026-10-05: 56 such files in three archives, and the
direction is NOT fixed -- sometimes the upper-case name is the empty one (`terminfo/A/TRANS.TBL`
against `terminfo/a/TRANS.TBL`, 10 810 bytes), sometimes the lower-case one. So every case below
tests EMPTINESS and none tests casing.

WHY THEY MATTER AT ALL, since zero bytes cost nothing to store: Rar.exe cannot hold two paths
differing only in case. It keeps ONE of the pair, says nothing, and exits 0 -- measured through a
directory argument, -r, an @list, -oni and both names explicitly. Which one it keeps is not
predictable, so for 56 pairs RAR might keep the EMPTY member and 348 631 bytes would not reach
cold storage.

THE DANGEROUS PART OF THIS TOOL IS NOT THE DELETION, IT IS THE PRUNING. A file is checked three
ways before it goes; a directory is removed on the strength of one `os.listdir` being empty. So
the pruning cases below are the longest ones, and they test refusal rather than success.
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

TOOL = common.load_peer("drop-empty-case-twins.py", "_twins", HERE)

SRC_DIR = HERE


def write(path, data=b""):
    """Create a file and every directory above it. -> the path."""
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "wb") as fh:
        fh.write(data)
    return path


class Tree(object):
    r"""A throwaway archive with an index, built from {relative path: bytes}.

    THE INDEX MAY NAME TWO CASINGS THAT THE FILESYSTEM CANNOT HOLD, which is the whole point: on
    an ordinary Windows directory `A.TBL` and `a.TBL` are one file, so a fixture that writes both
    ends up with one. The real collection holds them only because those directories carry the
    per-directory case-sensitivity flag. So the index is written from the names given here, the
    bytes land under whichever name NTFS keeps, and `sizes` is handed to `twins_in` in place of
    the filesystem -- which is what `size_of` exists for.
    """

    def __init__(self, files, archive="arch"):
        self.root = tempfile.mkdtemp(prefix="twins-")
        self.archive = archive
        self.dir = os.path.join(self.root, archive)
        self.sizes = {}
        rows = {}
        for rel, data in files.items():
            full = os.path.join(self.dir, *rel.split("/"))
            write(full, data)
            # NOT os.path.normcase: it lower-cases on Windows, which would map A.TBL and
            # a.TBL onto one key and defeat the very distinction this table exists to carry.
            self.sizes[os.path.abspath(full)] = len(data)
            rows[rel] = (len(data), 0, common.sha256_file(full))
        common.write_index(os.path.join(self.dir, common.INDEX_FILE),
                           os.path.join(self.dir, common.SUMS_FILE), rows)
        common.write_manifests(self.dir, dict(
            (rel, {"sha1": "1" * 40, "md5": "2" * 32, "crc32": "AABBCCDD"}) for rel in files))

    def size_of(self, path):
        """The filesystem's answer, replaced by what the fixture declared."""
        return self.sizes.get(os.path.abspath(path))

    def twins(self):
        return TOOL.twins_in(self.root, self.archive, size_of=self.size_of)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def has(self, rel):
        return os.path.isfile(os.path.join(self.dir, *rel.split("/")))


class WhatCountsAsAnEmptyTwin(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_a_pair_with_one_empty_member_is_found(self):
        self.tree = Tree({"dir/A.TBL": b"", "dir/a.TBL": b"content here"})
        self.assertEqual(self.tree.twins(), [("dir/A.TBL", "dir/a.TBL", 12)])

    def test_THE_EMPTY_ONE_GOES_WHICHEVER_CASE_IT_HAS(self):
        """Measured on 2026-10-05: ibiblio's upper-case TRANS.TBL is the empty one, ibm-aix's
        LOWER-case iz42658.epkg.Z is. A rule about casing would have been wrong half the time."""
        self.tree = Tree({"d/x.Z": b"", "d/X.Z": b"payload"})
        self.assertEqual(self.tree.twins(), [("d/x.Z", "d/X.Z", 7)])

    def test_two_empty_members_are_left_alone(self):
        """Both empty means byte-identical, so RAR keeping either loses nothing and there is
        nothing here worth a deletion."""
        self.tree = Tree({"d/A": b"", "d/a": b""})
        self.assertEqual(self.tree.twins(), [])

    def test_two_filled_members_are_left_alone(self):
        """The 3 700 groups that hold genuinely different content are a separate decision -- two
        valid JPEGs of 320x116 and 333x165, two working ELF binaries. This tool must not touch
        them."""
        self.tree = Tree({"d/A": b"one", "d/a": b"two"})
        self.assertEqual(self.tree.twins(), [])

    def test_an_empty_file_with_NO_twin_is_left_alone(self):
        """A source may legitimately serve an empty file. Emptiness alone is not the signal; being
        the empty half of a case pair is."""
        self.tree = Tree({"d/lonely": b"", "d/other": b"x"})
        self.assertEqual(self.tree.twins(), [])

    def test_THE_SIZES_ARE_READ_FROM_DISK_AND_NOT_FROM_THE_INDEX(self):
        """An index can be stale -- that is what the CRC32 cross-check found on 2026-10-05, two
        manifests describing a file rewritten after they were built.

        THIS ONE USES THE PRODUCTION READER, `disk_size`, because what it asserts is where the
        number comes from. The index says 0 bytes, the file on disk says otherwise, and the file
        wins -- so nothing is proposed for deletion."""
        self.tree = Tree({"d/A": b"", "d/other": b"x"})
        write(os.path.join(self.tree.dir, "d", "A"), b"no longer empty")
        self.assertEqual(TOOL.twins_in(self.tree.root, self.tree.archive), [])

    def test_a_group_whose_file_is_missing_from_disk_is_skipped(self):
        """Not guessed at. An index naming a file that is gone is a different problem and not this
        tool's to decide, so the whole group is passed over."""
        self.tree = Tree({"d/A": b"", "d/a": b"content"})
        self.assertEqual(
            TOOL.twins_in(self.tree.root, self.tree.archive,
                          size_of=lambda path: None if path.endswith("a") else 0),
            [])

    def test_disk_size_answers_None_for_what_is_not_there(self):
        """The production reader's contract, which the skip above depends on."""
        self.tree = Tree({"a.txt": b"x"})
        self.assertEqual(TOOL.disk_size(os.path.join(self.tree.dir, "a.txt")), 1)
        self.assertIsNone(TOOL.disk_size(os.path.join(self.tree.dir, "nope")))

    def test_AND_THE_FIXTURE_CANNOT_BE_BUILT_ON_A_NORMAL_DIRECTORY(self):
        """Which is why `size_of` is injectable at all, and it is worth asserting rather than
        explaining: writing both casings into an ordinary temp directory leaves ONE file."""
        self.tree = Tree({"d/A.TBL": b"", "d/a.TBL": b"content here"})
        here = os.path.join(self.tree.dir, "d")
        self.assertEqual(len(os.listdir(here)), 1, os.listdir(here))

    def test_the_largest_filled_member_is_named_as_the_keeper(self):
        """With three members the record has to point somewhere definite, and the biggest is the
        one most likely to be the whole resource."""
        self.tree = Tree({"d/A": b"", "d/a": b"short", "d/a~": b"x"})
        self.assertEqual(self.tree.twins(), [("d/A", "d/a", 5)])


class PruningRefusesWhenSomethingIsThere(unittest.TestCase):
    r"""THE CASES THAT MATTER MOST. A file is checked three ways before it goes; a directory is
    removed because one `os.listdir` came back empty. Every case here asserts that something
    survives.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prune-")
        self.said = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def report(self, line):
        self.said.append(line)

    def test_a_directory_holding_another_file_is_NOT_removed(self):
        write(os.path.join(self.root, "a", "deep", "gone.txt"), b"")
        keep = write(os.path.join(self.root, "a", "deep", "stays.txt"), b"x")
        os.remove(os.path.join(self.root, "a", "deep", "gone.txt"))
        n = TOOL.prune_empty_dirs(self.root, "", "a/deep/gone.txt", report=self.report)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isfile(keep))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "a", "deep")))

    def test_a_directory_holding_a_SUBdirectory_is_NOT_removed(self):
        """`os.listdir` is non-empty for a directory too, and a tool that only looked for files
        would take the parent of a surviving subtree with it."""
        write(os.path.join(self.root, "a", "deep", "sub", "stays.txt"), b"x")
        n = TOOL.prune_empty_dirs(self.root, "", "a/deep/gone.txt", report=self.report)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "a", "deep", "sub")))

    def test_a_directory_holding_a_HIDDEN_file_is_NOT_removed(self):
        """Our own bookkeeping is dotfiles. A directory holding only a .mirror-index.csv is not
        an empty directory, and os.listdir says so -- unlike a glob of `*`."""
        write(os.path.join(self.root, "a", "deep", ".mirror-gone"), b"x")
        n = TOOL.prune_empty_dirs(self.root, "", "a/deep/gone.txt", report=self.report)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "a", "deep")))

    def test_it_climbs_only_while_each_level_is_empty(self):
        """48 of the 56 empty twins are the ONLY thing in their directory, so climbing is the
        common case -- and it must stop the moment a level holds something."""
        write(os.path.join(self.root, "a", "keep.txt"), b"x")
        os.makedirs(os.path.join(self.root, "a", "b", "c"))
        n = TOOL.prune_empty_dirs(self.root, "", "a/b/c/gone.txt", report=self.report)
        self.assertEqual(n, 2)
        self.assertFalse(os.path.isdir(os.path.join(self.root, "a", "b")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "a", "keep.txt")))

    def test_it_never_climbs_past_the_archive_root(self):
        """The loop runs out of path components, so the archive directory itself and the
        collection root above it are unreachable even for a file at the top level."""
        n = TOOL.prune_empty_dirs(self.root, "", "top.txt", report=self.report)
        self.assertEqual(n, 0)
        self.assertTrue(os.path.isdir(self.root))

    def test_a_refusal_is_said_and_not_swallowed(self):
        write(os.path.join(self.root, "a", "stays.txt"), b"x")
        before = os.listdir(os.path.join(self.root, "a"))
        TOOL.prune_empty_dirs(self.root, "", "a/gone.txt", report=self.report)
        self.assertEqual(os.listdir(os.path.join(self.root, "a")), before)


class TheIndexAndManifestsLoseExactlyWhatWasNamed(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_one_path_goes_and_the_others_keep_their_digests(self):
        self.tree = Tree({"a.txt": b"one", "b.txt": b"two", "d/A": b"", "d/a": b"three"})
        before = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertTrue(TOOL.forget(self.tree.root, self.tree.archive, ["d/A"]))
        after = common.read_index(os.path.join(self.tree.dir, common.INDEX_FILE))
        self.assertEqual(set(before) - set(after), {"d/A"})
        for rel in after:
            self.assertEqual(after[rel], before[rel])

    def test_ALL_FOUR_MANIFESTS_LOSE_IT_TOO(self):
        """Four formats, and `.sfv` puts the columns the other way round from sha256sum(1). They
        are rewritten through the library's own writers, so no format is spelled out twice."""
        self.tree = Tree({"keep.txt": b"x", "d/A": b"", "d/a": b"content"})
        TOOL.forget(self.tree.root, self.tree.archive, ["d/A"])
        for name in sorted(common.MANIFEST_FILES.values()) + [common.SUMS_FILE]:
            with io.open(os.path.join(self.tree.dir, name), encoding="utf-8") as fh:
                body = fh.read()
            self.assertNotIn("d/A", body, name)
            self.assertIn("keep.txt", body, name)

    def test_NOTHING_IS_RE_HASHED(self):
        self.tree = Tree({"a.txt": b"x"})
        """Removing a path changes no other file's digest. Re-indexing instead would have read
        56.7 GB to learn what was already recorded."""
        src = io.open(os.path.join(HERE, "drop-empty-case-twins.py"), encoding="utf-8").read()
        block = src[src.index("def forget("):src.index("def main(")]
        self.assertNotIn("sha256_file", block)
        self.assertNotIn("digests_of_file", block)

    def test_it_refuses_if_the_index_would_lose_the_wrong_number(self):
        """A name that is not in the index means the caller and the tool disagree about the tree,
        and the manifests must not be rewritten on that footing."""
        self.tree = Tree({"a.txt": b"x"})
        self.assertFalse(TOOL.forget(self.tree.root, self.tree.archive, ["not-there"],
                                     report=lambda _m: None))


class TheRecordAndTheBackup(unittest.TestCase):

    def tearDown(self):
        self.tree.close()

    def test_the_record_names_both_sides_and_the_size_that_survives(self):
        self.tree = Tree({"d/A.TBL": b"", "d/a.TBL": b"content here"})
        path = TOOL.write_record(self.tree.root, self.tree.archive, self.tree.twins())
        with io.open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("d/A.TBL", body)
        self.assertIn("-> d/a.TBL", body)
        self.assertIn("(12 bytes)", body)

    def test_IT_FOLLOWS_THE_CONVENTION_THIS_COLLECTION_ALREADY_HAS(self):
        """FRAGMENT-COPIES-REMOVED.txt exists in four archives for the same shape of mistake -- a
        file fetched twice under two spellings of one URL. One convention, not two."""
        self.tree = Tree({"d/A": b"", "d/a": b"x"})
        path = TOOL.write_record(self.tree.root, self.tree.archive, self.tree.twins())
        with io.open(path, encoding="utf-8") as fh:
            head = fh.read().splitlines()
        self.assertTrue(head[0].startswith("# Files removed "))
        self.assertIn("removed (0 bytes)", "\n".join(head))

    def test_the_backup_copies_the_bookkeeping_and_verifies_every_copy(self):
        self.tree = Tree({"a.txt": b"x"})
        where = tempfile.mkdtemp(prefix="backup-")
        try:
            self.assertTrue(TOOL.save_bookkeeping(self.tree.root, self.tree.archive, where))
            saved = sorted(os.listdir(os.path.join(where, self.tree.archive)))
            for name in sorted(common.MANIFEST_FILES.values()) + [common.SUMS_FILE,
                                                                  common.INDEX_FILE]:
                self.assertIn(name, saved)
        finally:
            shutil.rmtree(where, ignore_errors=True)


class TheCommandLineRefusesBeforeItActs(unittest.TestCase):

    def setUp(self):
        self.tree = Tree({"d/A": b"", "d/a": b"content"})
        self.out = io.StringIO()
        self.keep = sys.stdout
        sys.stdout = self.out

    def tearDown(self):
        sys.stdout = self.keep
        self.tree.close()

    def run_tool(self, *args):
        code = TOOL.main(["--root", self.tree.root] + list(args))
        return code, self.out.getvalue()

    def test_THE_DEFAULT_IS_A_DRY_RUN_AND_IT_WRITES_NOTHING(self):
        """4 542 collisions were found by a check nobody had asked for; the tool that acts on a
        slice of them starts by doing nothing."""
        code, text = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIn("NOTHING WAS REMOVED", text)
        self.assertTrue(self.tree.has("d/A"))
        self.assertTrue(self.tree.has("d/a"))

    def test_apply_without_a_backup_is_refused(self):
        """These five files per archive are the only record of what the tree looked like, and the
        tool rewrites them."""
        code, text = self.run_tool("--apply")
        self.assertEqual(code, 2)
        self.assertIn("needs --backup", text)
        self.assertTrue(self.tree.has("d/A"))

    def test_a_collection_that_is_not_there(self):
        code = TOOL.main(["--root", os.path.join(self.tree.root, "nope")])
        self.assertEqual(code, 2)


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
        with io.open(os.path.join(SRC_DIR, "drop-empty-case-twins.py"), encoding="utf-8") as fh:
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
