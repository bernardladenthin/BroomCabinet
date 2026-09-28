#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Filling an archive's gaps from another copy already in the collection.

NOTHING HERE TOUCHES THE COLLECTION. Every case builds a two-tree fixture in a temporary
directory: an archive with a hole in it, and a copy of the same site that has the missing file.

WHAT IS WORTH TESTING HERE is not the copying -- common.copy_new_file() owns that and is tested
where it lives -- but the three ways this tool can be WRONG IN A WAY THAT LOOKS RIGHT:

    a `--from` rooted at a different depth, which reports every file as absent
    a gap that is not in the error log, which must not be filled just because the copy has it
    a file that is already there, which must survive

The first is not hypothetical. The first real run was pointed at
`iommu/.../www.vgamuseum.info` while the archive is mounted at
`https://www.vgamuseum.info/images/doc/`, and it answered "not in the copy either" for two files
that were sitting two directories deeper.
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("fill-from-local")

BASE = "https://example.invalid/images/doc/"
ARCHIVE = "an-archive"

# What the archive has, what the copy has, and what the log says was given up on.
IN_ARCHIVE = {"sis/have.pdf": b"already here", "upload/other.zip": b"also here"}
IN_COPY = {"sis/have.pdf": b"the copy's own version -- must never win",
           "upload/big.zip": b"the missing bytes" * 10,
           "upload/never-asked-for.zip": b"present but not in the log"}
GAVE_UP_ON = ("upload/big.zip", "sis/have.pdf", "upload/gone-everywhere.zip")


def write(root, files):
    for rel, blob in files.items():
        full = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, "wb") as fh:
            fh.write(blob)


class Fixture(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="fill-")
        self.archive_dir = os.path.join(self.root, ARCHIVE)
        # The copy is rooted at the SITE, one level above what BASE addresses -- the real shape.
        self.site = os.path.join(self.root, "other", "www.example.invalid")
        self.copy = os.path.join(self.site, "images", "doc")
        write(self.archive_dir, IN_ARCHIVE)
        write(self.copy, IN_COPY)
        os.makedirs(os.path.join(self.root, "logs"), exist_ok=True)
        with io.open(os.path.join(self.root, "logs", "errors-%s.txt" % ARCHIVE),
                     "w", encoding="utf-8") as fh:
            for rel in GAVE_UP_ON:
                fh.write("2026-09-27 11:03:36 FAIL OSError: short read 1 of 2 %s%s\n"
                         % (BASE, rel))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def read(self, *parts):
        with io.open(os.path.join(*parts), "rb") as fh:
            return fh.read()

    def why(self, rows):
        return {rel: why for rel, _url, _t, _s, why in rows}


class WhatItConsidersAGap(Fixture):

    def test_it_reads_the_fetchs_own_error_log(self):
        rows = TOOL.gaps(self.root, ARCHIVE, BASE, self.copy)
        self.assertEqual(sorted(self.why(rows)), sorted(GAVE_UP_ON))

    def test_ONLY_WHAT_THE_LOG_NAMES_IS_EVER_FILLED(self):
        """The copy also holds `upload/never-asked-for.zip`. Copying "everything the source has
        and the target lacks" would quietly undo every exclusion in mirror.EXCLUDE and every
        judgement behind it."""
        rows = TOOL.gaps(self.root, ARCHIVE, BASE, self.copy)
        self.assertNotIn("upload/never-asked-for.zip", self.why(rows))

    def test_a_file_already_here_is_reported_and_not_filled(self):
        self.assertEqual(self.why(TOOL.gaps(self.root, ARCHIVE, BASE, self.copy))["sis/have.pdf"],
                         "already here")

    def test_and_one_missing_from_both_says_so_rather_than_vanishing(self):
        """A run that silently dropped what it cannot help with would make "nothing to do" and
        "I could not tell" the same output."""
        self.assertEqual(self.why(TOOL.gaps(self.root, ARCHIVE, BASE, self.copy))
                         ["upload/gone-everywhere.zip"], "not in the copy either")

    def test_the_fillable_one_has_no_reason_against_it(self):
        self.assertIsNone(self.why(TOOL.gaps(self.root, ARCHIVE, BASE, self.copy))
                          ["upload/big.zip"])

    def test_a_url_outside_the_archives_base_is_not_silently_mapped(self):
        with io.open(os.path.join(self.root, "logs", "errors-%s.txt" % ARCHIVE),
                     "a", encoding="utf-8") as fh:
            fh.write("2026-09-27 11:03:36 FAIL HTTP 500 https://elsewhere.invalid/x.pdf\n")
        rows = TOOL.gaps(self.root, ARCHIVE, BASE, self.copy)
        self.assertEqual(self.why(rows)["https://elsewhere.invalid/x.pdf"],
                         "not under this archive's base url")


class WhetherTheTreesLineUp(Fixture):

    def test_a_correctly_rooted_copy_shares_paths(self):
        matched, tried = TOOL.trees_line_up(self.archive_dir, self.copy)
        self.assertTrue(tried)
        self.assertGreater(matched, 0)

    def test_A_COPY_ROOTED_HIGHER_SHARES_NONE(self):
        """The real mistake, and the reason this check exists: `--from` pointed at the site root
        while the archive is mounted at `images/doc/`. Every file then reads "not in the copy
        either", which reads as a finding and is false."""
        matched, tried = TOOL.trees_line_up(self.archive_dir, self.site)
        self.assertTrue(tried)
        self.assertEqual(matched, 0)

    def test_and_main_refuses_rather_than_reporting_them_absent(self):
        rc = self.run_tool("--from", self.site)
        self.assertEqual(rc, 2)
        # and it wrote nothing
        self.assertFalse(os.path.exists(os.path.join(self.archive_dir, TOOL.FILLED_FROM)))

    def run_tool(self, *extra):
        argv = ["--root", self.root, "--archive", ARCHIVE] + list(extra)
        register = {ARCHIVE: BASE}

        class FakeMirror(object):
            ARCHIVES = tuple(register.items())

        real = TOOL.load_mirror
        TOOL.load_mirror = lambda *a, **k: FakeMirror()
        try:
            return TOOL.main(argv)
        finally:
            TOOL.load_mirror = real


class WhatARunDoes(WhetherTheTreesLineUp):

    def test_A_DRY_RUN_IS_THE_DEFAULT_AND_WRITES_NOTHING(self):
        """This writes into the collection. The flag is on the side that acts, not the side that
        looks."""
        self.assertEqual(self.run_tool("--from", self.copy), 0)
        self.assertFalse(os.path.exists(os.path.join(self.archive_dir, "upload", "big.zip")))
        self.assertFalse(os.path.exists(os.path.join(self.archive_dir, TOOL.FILLED_FROM)))

    def test_apply_fills_exactly_the_one_gap(self):
        self.assertEqual(self.run_tool("--from", self.copy, "--apply"), 0)
        self.assertEqual(self.read(self.archive_dir, "upload", "big.zip"),
                         IN_COPY["upload/big.zip"])
        self.assertFalse(os.path.exists(
            os.path.join(self.archive_dir, "upload", "never-asked-for.zip")))

    def test_AND_NEVER_REPLACES_WHAT_IS_ALREADY_THERE(self):
        """`sis/have.pdf` is in the log, in the archive AND in the copy, with different bytes.
        The one in the archive came from the archive's own source and must win."""
        self.run_tool("--from", self.copy, "--apply")
        self.assertEqual(self.read(self.archive_dir, "sis", "have.pdf"),
                         IN_ARCHIVE["sis/have.pdf"])

    def test_IT_LEAVES_THE_PROVENANCE_IN_THE_ARCHIVE(self):
        """A file whose provenance differs from the rest of the archive must say so IN THE
        ARCHIVE, not in a log somebody has to still have."""
        self.run_tool("--from", self.copy, "--apply")
        text = self.read(self.archive_dir, TOOL.FILLED_FROM).decode("utf-8")
        self.assertIn("upload/big.zip", text)
        self.assertIn(common.sha256_file(
            os.path.join(self.archive_dir, "upload", "big.zip")), text)
        # AND NO LICENCE HEADER. The first version wrote one, and privacy-test.py reported the
        # author's address in a file this tool generates. No PROVENANCE.md in the collection
        # carries one either: the mirror is not a REUSE tree, the repository producing it is.
        self.assertNotIn("SPDX", text)

    def test_and_a_second_run_appends_rather_than_starting_over(self):
        self.run_tool("--from", self.copy, "--apply")
        os.remove(os.path.join(self.archive_dir, "upload", "big.zip"))
        self.run_tool("--from", self.copy, "--apply")
        text = self.read(self.archive_dir, TOOL.FILLED_FROM).decode("utf-8")
        self.assertEqual(text.count("# Files in this archive"), 1)
        self.assertEqual(text.count("upload/big.zip"), 2)

    def test_nothing_partial_survives_a_run(self):
        self.run_tool("--from", self.copy, "--apply")
        left = [f for _r, _d, fs in os.walk(self.root) for f in fs if f.endswith(".part")]
        self.assertEqual(left, [])

    def test_an_archive_the_register_does_not_know_is_refused(self):
        argv = ["--root", self.root, "--archive", "no-such-archive", "--from", self.copy]

        class FakeMirror(object):
            ARCHIVES = ((ARCHIVE, BASE),)

        real = TOOL.load_mirror
        TOOL.load_mirror = lambda *a, **k: FakeMirror()
        try:
            self.assertEqual(TOOL.main(argv), 2)
        finally:
            TOOL.load_mirror = real

    def test_a_from_that_is_not_a_directory_is_refused(self):
        self.assertEqual(self.run_tool("--from", os.path.join(self.copy, "upload", "big.zip")), 2)


if __name__ == "__main__":
    unittest.main()
