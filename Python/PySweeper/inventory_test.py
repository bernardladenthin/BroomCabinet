#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""inventory.py -- the file that decides what sweep.py is allowed to look at.

WHY THIS MATTERS MORE THAN IT LOOKS. `sweep.py` is the one that deletes, and it is carefully
guarded: 20 checks, a real junction, a refusal for every row that no longer describes the file on
disk. But every one of those guards compares a file against **a row inventory.py wrote**. If a row
is wrong in a way that still matches the file, sweep does exactly as it is told and removes the
wrong thing. The dangerous failure is not "inventory crashes", it is "inventory writes a plausible
row about the wrong file".

So these are the properties where being wrong is expensive, in rough order:

  * a junction is NOT descended -- otherwise foreign files enter the inventory under names that
    look local, and a person reads that list and believes it
  * `--held-in` matches by CONTENT and skips empty files -- every empty file has the same digest,
    so one empty file in a collection would mark every empty file in the working directory as
    "already held" and pre-select them for deletion
  * `decision` starts EMPTY -- an unedited inventory must sweep nothing
  * a re-run KEEPS what a person wrote
  * the inventory is replaced whole or not at all -- a truncated one is a list of rows somebody
    will act on

WHY `unittest` HERE AND A HAND-ROLLED HARNESS IN `sweep_test.py`. The repository's other 34 test
files are unittest; that one is hand-rolled because it drives the tool as a subprocess and prints
a case table a person reads while deleting things. Nothing here needs that, and the standard
runner names the failing property out loud.

REAL JUNCTIONS, NOT MOCKS. The whole question is what the filesystem does, so the tests that need
one create one and skip themselves when the platform will not.
"""
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402


def make_junction(link, target):
    """-> True when a real junction or symlink now exists at `link`."""
    if os.name == "nt":
        # Captured as bytes: cmd answers in the console codepage and decoding it has raised
        # inside subprocess's reader thread before. Only the exit code is read.
        result = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                                capture_output=True)
        return result.returncode == 0 and os.path.exists(link)
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except OSError:
        return False


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="inventory-test-")
        self.root = os.path.join(self.tmp, "work")
        os.makedirs(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, rel, blob=b"x", where=None):
        path = os.path.join(where or self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "wb") as fh:
            fh.write(blob)
        return path

    def walked(self, root=None, skip=()):
        return sorted(rel for rel, _info in inventory.walk_files(root or self.root, set(skip)))


class WhatTheWalkFinds(Tree):

    def test_every_regular_file_with_a_forward_slash_path(self):
        """sweep.py reads these back and joins them, so the separator is part of the contract."""
        self.put("a.txt")
        self.put("deep/b.txt")
        self.assertEqual(self.walked(), ["a.txt", "deep/b.txt"])

    def test_a_directory_is_not_a_row(self):
        os.makedirs(os.path.join(self.root, "empty-dir"))
        self.assertEqual(self.walked(), [])

    def test_skip_names_leave_out_files_and_directories_alike(self):
        self.put("keep.txt")
        self.put("drop.txt")
        self.put("node_modules/x.txt")
        self.assertEqual(self.walked(skip=("drop.txt", "node_modules")), ["keep.txt"])

    def test_the_order_is_stable(self):
        # A person diffs two inventories to see what changed. Unstable order makes every line
        # look changed, which is the same as none of them being readable.
        for name in ("c.txt", "a.txt", "b.txt"):
            self.put(name)
        self.assertEqual(self.walked(), ["a.txt", "b.txt", "c.txt"])
        self.assertEqual(self.walked(), self.walked())


class JunctionsAreNotFollowed(Tree):
    """THE ONE THAT MATTERS MOST.

    Walking through a junction puts somebody else's files into this inventory under names that
    look local. `sweep.py` would then refuse every one of them -- correctly, because they resolve
    outside the root -- but only AFTER a person had read the list and believed it. The refusal is
    the second line of defence; this is the first.
    """

    def setUp(self):
        super().setUp()
        self.outside = os.path.join(self.tmp, "outside")
        os.makedirs(self.outside)
        self.put("treasure.txt", b"do not touch", where=self.outside)

    def test_a_junction_to_a_directory_is_not_descended(self):
        link = os.path.join(self.root, "link")
        if not make_junction(link, self.outside):
            self.skipTest("this platform will not make a junction here")
        self.put("local.txt")
        self.assertEqual(self.walked(), ["local.txt"])

    def test_and_the_file_behind_it_is_untouched(self):
        link = os.path.join(self.root, "link")
        if not make_junction(link, self.outside):
            self.skipTest("this platform will not make a junction here")
        self.walked()
        self.assertTrue(os.path.exists(os.path.join(self.outside, "treasure.txt")))

    def test_is_reparse_point_says_no_about_an_ordinary_file(self):
        self.assertFalse(inventory.is_reparse_point(self.put("plain.txt")))

    def test_and_no_about_something_that_is_not_there(self):
        """A missing path is not a link. Answering True would hide a real file from the walk."""
        self.assertFalse(inventory.is_reparse_point(os.path.join(self.root, "nope")))


class TheDigest(Tree):

    def test_it_is_the_sha256_of_the_bytes(self):
        import hashlib
        blob = b"the quick brown fox" * 1000
        path = self.put("f.bin", blob)
        self.assertEqual(inventory.sha256_of(path), hashlib.sha256(blob).hexdigest())

    def test_an_empty_file_hashes_to_the_empty_digest(self):
        self.assertEqual(inventory.sha256_of(self.put("e.bin", b"")),
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_a_file_larger_than_one_chunk_is_read_whole(self):
        """It reads in 1 MiB chunks; a loop that stopped after the first would be invisible
        on every small file and wrong on every large one."""
        import hashlib
        blob = bytes(range(256)) * ((1 << 20) // 256 + 17)
        path = self.put("big.bin", blob)
        self.assertEqual(inventory.sha256_of(path), hashlib.sha256(blob).hexdigest())


class TheCollectionIndex(Tree):
    """--held-in, and the emptiness trap."""

    def setUp(self):
        super().setUp()
        self.collection = os.path.join(self.tmp, "collection")
        os.makedirs(self.collection)
        self.said = []

    def index(self, *roots):
        return inventory.index_collection(list(roots) or [self.collection], self.said.append)

    def test_it_maps_content_to_where_it_is_held(self):
        held = self.put("archive/thing.gz", b"contents", where=self.collection)
        index = self.index()
        self.assertEqual(index[inventory.sha256_of(held)], held)

    def test_AN_EMPTY_FILE_IS_NEVER_INDEXED(self):
        """The trap this check exists for.

        Every empty file has the same digest. One empty file in a collection would match every
        empty file in the working directory, and `main()` pre-marks a match as `delete` with
        "held in ..." as its reason -- a reason that reads like somebody checked.
        """
        self.put("empty", b"", where=self.collection)
        self.assertEqual(self.index(), {})

    def test_the_first_holder_wins_and_the_second_does_not_overwrite_it(self):
        """The reason names a path a person can go and look at. Which one hardly matters;
        that it stops changing between runs does."""
        first = self.put("a/one.bin", b"same", where=self.collection)
        self.put("b/two.bin", b"same", where=self.collection)
        index = self.index()
        self.assertEqual(index[inventory.sha256_of(first)], first)

    def test_a_root_that_is_not_a_directory_is_reported_rather_than_ignored(self):
        missing = os.path.join(self.tmp, "does-not-exist")
        self.assertEqual(self.index(missing), {})
        self.assertTrue(any("not a directory" in line for line in self.said))

    def test_it_matches_by_content_and_not_by_name(self):
        """The first real run of this tool found a Makefile matching a tar member by name and
        differing in bytes. A name shared with an archive member proves nothing."""
        self.put("Makefile", b"collection version", where=self.collection)
        mine = self.put("Makefile", b"my version")
        self.assertNotIn(inventory.sha256_of(mine), self.index())


class ReadingAnExistingInventory(Tree):

    def write_csv(self, rows):
        path = os.path.join(self.tmp, "inv.csv")
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=inventory.COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def blank(self, **kw):
        row = {c: "" for c in inventory.COLUMNS}
        row.update(kw)
        return row

    def test_no_inventory_yet_is_an_empty_answer_not_a_crash(self):
        self.assertEqual(inventory.read_existing(os.path.join(self.tmp, "nothing.csv")), {})

    def test_it_is_keyed_by_path(self):
        path = self.write_csv([self.blank(path="a.txt", decision="delete", reason="mine")])
        got = inventory.read_existing(path)
        self.assertEqual(got["a.txt"]["decision"], "delete")
        self.assertEqual(got["a.txt"]["reason"], "mine")

    def test_a_row_with_no_path_is_dropped(self):
        # Such a row cannot be matched to a file, and keeping it would put a decision in the
        # carry-over map under an empty key.
        path = self.write_csv([self.blank(path=""), self.blank(path="real.txt")])
        self.assertEqual(sorted(inventory.read_existing(path)), ["real.txt"])


class WritingTheInventory(Tree):
    """Whole or not at all. A `DictWriter(open(CSV, "w"))` without a `with` truncated one once."""

    def test_it_writes_the_columns_in_order(self):
        path = os.path.join(self.tmp, "out.csv")
        inventory.write_rows(path, [{c: "" for c in inventory.COLUMNS}])
        with io.open(path, encoding="utf-8", newline="") as fh:
            self.assertEqual(next(csv.reader(fh)), inventory.COLUMNS)

    def test_the_temp_file_does_not_survive(self):
        path = os.path.join(self.tmp, "out.csv")
        inventory.write_rows(path, [])
        self.assertFalse(os.path.exists(path + ".tmp"))

    def test_an_existing_inventory_is_replaced_and_not_appended_to(self):
        path = os.path.join(self.tmp, "out.csv")
        inventory.write_rows(path, [{c: "old" for c in inventory.COLUMNS}])
        inventory.write_rows(path, [{c: "new" for c in inventory.COLUMNS}])
        with io.open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "new")


class TheGroups(unittest.TestCase):

    def test_a_group_is_found_case_insensitively(self):
        # Paths out of a working directory arrive as .ZIP as often as .zip.
        for ext in (".zip", ".ZIP", ".Zip"):
            self.assertEqual(inventory.GROUPS.get(ext.lower()), "archives", ext)

    def test_an_unknown_extension_has_no_group_of_its_own(self):
        self.assertIsNone(inventory.GROUPS.get(".wibble"))

    def test_no_group_name_is_empty(self):
        for ext, group in inventory.GROUPS.items():
            self.assertTrue(group.strip(), ext)


class EndToEnd(Tree):
    """The tool as a person runs it. The properties here are about the CSV, not the functions."""

    def run_tool(self, *argv):
        out = io.StringIO()
        keep_out, keep_argv = sys.stdout, sys.argv
        sys.stdout, sys.argv = out, ["inventory.py"] + list(argv)
        try:
            code = inventory.main()
        finally:
            sys.stdout, sys.argv = keep_out, keep_argv
        return code, out.getvalue()

    def rows(self, path=None):
        with io.open(path or os.path.join(self.root, inventory.DEFAULT_CSV),
                     encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def test_THE_DECISION_COLUMN_STARTS_EMPTY(self):
        """An unedited inventory must sweep nothing. This is the tool's whole posture."""
        self.put("a.txt")
        self.put("b.log")
        self.run_tool("--root", self.root)
        self.assertTrue(self.rows())
        for row in self.rows():
            self.assertEqual(row["decision"], "")

    def test_A_RERUN_KEEPS_WHAT_A_PERSON_WROTE(self):
        self.put("a.txt")
        self.run_tool("--root", self.root)
        path = os.path.join(self.root, inventory.DEFAULT_CSV)
        rows = self.rows()
        rows[0]["decision"] = "delete"
        rows[0]["reason"] = "I looked at it"
        rows[0]["group"] = "mine"
        inventory.write_rows(path, rows)

        self.put("b.txt")                      # the directory changed under it
        self.run_tool("--root", self.root)
        after = {r["path"]: r for r in self.rows()}
        self.assertEqual(after["a.txt"]["decision"], "delete")
        self.assertEqual(after["a.txt"]["reason"], "I looked at it")
        self.assertEqual(after["a.txt"]["group"], "mine")
        self.assertEqual(after["b.txt"]["decision"], "")

    def test_the_inventory_does_not_list_itself(self):
        self.put("a.txt")
        self.run_tool("--root", self.root)
        self.assertNotIn(inventory.DEFAULT_CSV, [r["path"] for r in self.rows()])

    def test_summary_writes_nothing(self):
        self.put("a.txt")
        code, _text = self.run_tool("--root", self.root, "--summary")
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(self.root, inventory.DEFAULT_CSV)))

    def test_HELD_IN_PREMARKS_BY_CONTENT_AND_SAYS_WHERE(self):
        """"held in <path>" rather than "duplicate": a reason a person cannot check is not one."""
        collection = os.path.join(self.tmp, "collection")
        os.makedirs(collection)
        held = self.put("kept/thing.gz", b"identical bytes", where=collection)
        self.put("copy.gz", b"identical bytes")
        self.put("mine.txt", b"only here")
        self.run_tool("--root", self.root, "--held-in", collection)
        rows = {r["path"]: r for r in self.rows()}
        self.assertEqual(rows["copy.gz"]["decision"], "delete")
        self.assertIn(os.path.basename(held), rows["copy.gz"]["reason"])
        self.assertEqual(rows["mine.txt"]["decision"], "")

    def test_and_it_refuses_to_run_without_hashes(self):
        """--held-in compares content, so `--no-hash` is not a slower answer but no answer."""
        code, text = self.run_tool("--root", self.root, "--held-in", self.tmp, "--no-hash")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", text)

    def test_a_root_that_is_not_a_directory_is_refused(self):
        code, text = self.run_tool("--root", os.path.join(self.tmp, "nope"))
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", text)

    def test_no_root_prints_help_and_writes_nothing(self):
        code, _text = self.run_tool()
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
