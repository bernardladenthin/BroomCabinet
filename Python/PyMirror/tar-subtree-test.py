# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Tests for tar-subtree.py.

EVERY FIXTURE IS A FRESH tempfile.mkdtemp() AND NOTHING HERE NAMES THE COLLECTION. The tool reads
a mirror and writes tars; a test that pointed either end at Q: or at X:\tarTarget could pack 92 GB
or refuse a real tar, so the roots are always passed explicitly and always point into a temporary
directory. No test removes a directory it did not create, and none removes a non-empty one.

THE CASE PAIR IS INJECTED, NOT CREATED ON DISK, wherever a test needs one. `A.TBL` and `a.TBL`
cannot both exist in an ordinary Windows directory -- the mirror's own directories carry the
case-sensitivity flag, which a temporary directory does not -- so the comparison functions are
tested on dictionaries, which is where the case question actually lives.
"""
import io
import os
import shutil
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common                                                       # noqa: E402

TOOL = common.load_peer("tar-subtree.py", "_tarsub", HERE)


def write(path, text):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


# EVERY CASE HERE NEEDS A REAL GNU tar, so the file says so once instead of failing 51 times.
# A runner without one is not a broken runner: this tool exists for a Windows host where the
# System32 `tar.exe` is bsdtar, and `check_tar_binary()` is what refuses the wrong binary.
NEEDS_GNU_TAR = unittest.skipUnless(
    TOOL.GNU_TAR and os.path.isfile(TOOL.GNU_TAR), "no GNU tar on this host")


class Fixture(unittest.TestCase):
    """A source root with one subtree, and a target root beside it. Both temporary."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="tarsub-")
        self.source_root = os.path.join(self.base, "fixes")
        self.target_root = os.path.join(self.base, "target")
        os.makedirs(os.path.join(self.source_root, "v9", "sub"))
        os.makedirs(os.path.join(self.target_root, "v9"))
        self.files = {
            "one.bff": "first file\n",
            "two.info": "second file, a little longer\n",
            "sub/three.bff": "third\n",
        }
        for rel, text in self.files.items():
            write(os.path.join(self.source_root, "v9", rel), text)
        self.said = []

    def tearDown(self):
        # Only ever the directory this test made, and only through the handle it kept.
        shutil.rmtree(self.base, ignore_errors=True)

    def report(self, text=""):
        self.said.append(text)

    def write_manifest(self, rows=None):
        """The .sha256sum the tool reads, with real digests unless rows says otherwise."""
        import hashlib
        lines = []
        for rel in sorted(rows if rows is not None else self.files):
            if rows is not None and rows[rel] is not None:
                digest = rows[rel]
            else:
                with io.open(os.path.join(self.source_root, "v9", rel), "rb") as handle:
                    digest = hashlib.sha256(handle.read()).hexdigest()
            lines.append("%s *%s" % (digest, rel))
        write(os.path.join(self.source_root, "v9", common.SUMS_FILE), "\n".join(lines) + "\n")

    def pack(self, **kwargs):
        settings = dict(name="v9", source_root=self.source_root, target_root=self.target_root,
                        apply_it=False, check_only=False, report=self.report)
        settings.update(kwargs)
        return TOOL.pack(**settings)

    def output(self):
        return "\n".join(self.said)


class ReadingAManifest(unittest.TestCase):
    r"""manifest_rows() on the format PyFixity writes."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="tarsub-m-")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def path(self, text):
        where = os.path.join(self.folder, common.SUMS_FILE)
        write(where, text)
        return where

    def test_it_reads_a_digest_and_a_path(self):
        rows = TOOL.manifest_rows(self.path("ab12 *adt/x.bff\n"))
        self.assertEqual(rows, {"adt/x.bff": "ab12"})

    def test_the_star_is_not_part_of_the_path(self):
        """sha256sum(1) writes `*` for binary mode; it belongs to the format, not the name."""
        rows = TOOL.manifest_rows(self.path("ab12 *x.bff\n"))
        self.assertIn("x.bff", rows)

    def test_a_path_with_spaces_survives(self):
        r"""`IBM C Set.bff` is a real shape here, and split() would keep only `IBM`."""
        rows = TOOL.manifest_rows(self.path("ab12 *lib/IBM C Set.bff\n"))
        self.assertEqual(rows, {"lib/IBM C Set.bff": "ab12"})

    def test_two_spellings_are_two_rows(self):
        r"""THE WHOLE POINT. Folding these together is the bug the tar exists to prevent."""
        rows = TOOL.manifest_rows(self.path("aa *dtext.De_DE.bff\nbb *dtext.de_DE.bff\n"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows["dtext.De_DE.bff"], "aa")
        self.assertEqual(rows["dtext.de_DE.bff"], "bb")

    def test_blank_lines_and_comments_are_skipped(self):
        rows = TOOL.manifest_rows(self.path("; a note\n\naa *x.bff\n"))
        self.assertEqual(rows, {"x.bff": "aa"})


class ComparingAgainstTheTar(unittest.TestCase):
    r"""compare() is where completeness is decided, so the case question is pinned here."""

    def test_a_complete_tar_reports_nothing(self):
        missing, extra, wrong = TOOL.compare({"a.bff": 5}, {"v9/a.bff": 5}, "v9")
        self.assertEqual((missing, extra, wrong), ([], [], []))

    def test_a_missing_member_is_named(self):
        missing, _extra, _wrong = TOOL.compare({"a.bff": 5, "b.bff": 7}, {"v9/a.bff": 5}, "v9")
        self.assertEqual(missing, ["v9/b.bff"])

    def test_a_wrong_size_is_named_separately_from_a_missing_one(self):
        """Present-but-short is a different failure from absent, and reads differently."""
        missing, _extra, wrong = TOOL.compare({"a.bff": 5}, {"v9/a.bff": 4}, "v9")
        self.assertEqual(missing, [])
        self.assertEqual(wrong, ["v9/a.bff"])

    def test_an_unexpected_member_is_named(self):
        _missing, extra, _wrong = TOOL.compare({"a.bff": 5}, {"v9/a.bff": 5, "v9/x": 1}, "v9")
        self.assertEqual(extra, ["v9/x"])

    def test_a_case_twin_stored_under_the_other_spelling_counts_as_MISSING(self):
        r"""THE MEASUREMENT THAT MATTERS, and the one a case-folding compare gets wrong.

        This is exactly what rar a did to misc.rar: `De_DE` went in, `de_DE` did not, and a
        forgiving comparison called the archive complete. Here it must come back missing.
        """
        expected = {"dtext.De_DE.bff": 10, "dtext.de_DE.bff": 20}
        present = {"v9/dtext.De_DE.bff": 10}
        missing, _extra, _wrong = TOOL.compare(expected, present, "v9")
        self.assertEqual(missing, ["v9/dtext.de_DE.bff"])

    def test_both_spellings_present_is_complete(self):
        expected = {"dtext.De_DE.bff": 10, "dtext.de_DE.bff": 20}
        present = {"v9/dtext.De_DE.bff": 10, "v9/dtext.de_DE.bff": 20}
        missing, extra, wrong = TOOL.compare(expected, present, "v9")
        self.assertEqual((missing, extra, wrong), ([], [], []))

    def test_the_prefix_is_applied_to_the_expected_side(self):
        """A tar made with -C <parent> stores `v9/...`; the manifest holds bare relatives."""
        missing, extra, _wrong = TOOL.compare({"a.bff": 1}, {"other/a.bff": 1}, "v9")
        self.assertEqual(missing, ["v9/a.bff"])
        self.assertEqual(extra, ["other/a.bff"])


class WhatADryRunDoes(Fixture):
    def test_it_writes_no_tar(self):
        self.write_manifest()
        self.assertEqual(self.pack(), 0)
        self.assertFalse(os.path.exists(os.path.join(self.target_root, "v9", "v9.tar")))

    def test_it_says_what_it_would_do(self):
        self.write_manifest()
        self.pack()
        self.assertIn("WOULD create the tar", self.output())

    def test_it_reports_the_file_count_from_the_manifest(self):
        self.write_manifest()
        self.pack()
        self.assertIn("3 files in the manifest", self.output())


class WhatItRefuses(Fixture):
    def test_a_source_that_is_not_there(self):
        self.assertEqual(self.pack(name="nope"), 2)
        self.assertIn("not a directory", self.output())

    def test_a_target_that_is_not_there(self):
        self.write_manifest()
        self.assertEqual(self.pack(target_root=os.path.join(self.base, "absent")), 2)
        self.assertIn("target missing", self.output())

    def test_a_subtree_with_no_manifest(self):
        """Packing before pyfixity has run would make a tar nothing can check."""
        self.assertEqual(self.pack(apply_it=True), 2)
        self.assertIn("no .sha256sum", self.output())

    def test_check_only_with_no_tar(self):
        self.write_manifest()
        self.assertEqual(self.pack(check_only=True), 2)
        self.assertIn("no tar to check", self.output())

    def test_apply_refuses_to_overwrite_a_tar_that_is_there(self):
        r"""A 92 GB tar that took 15 minutes is not something to clobber by re-running."""
        self.write_manifest()
        write(os.path.join(self.target_root, "v9", "v9.tar"), "not really a tar")
        self.assertEqual(self.pack(apply_it=True), 2)
        self.assertIn("ALREADY THERE", self.output())

    def test_and_it_leaves_that_tar_alone(self):
        self.write_manifest()
        where = os.path.join(self.target_root, "v9", "v9.tar")
        write(where, "not really a tar")
        self.pack(apply_it=True)
        with io.open(where, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "not really a tar")


@NEEDS_GNU_TAR
class PackingForReal(Fixture):
    r"""--apply end to end, in a temporary directory, with tar.exe actually running."""

    def setUp(self):
        Fixture.setUp(self)
        self.write_manifest()

    def test_it_creates_the_tar_and_proves_it(self):
        self.assertEqual(self.pack(apply_it=True), 0)
        self.assertTrue(os.path.exists(os.path.join(self.target_root, "v9", "v9.tar")))
        self.assertIn("PROVED", self.output())

    def test_the_members_are_stored_under_the_subtree_name(self):
        """So the tar unpacks into a folder of its own instead of scattering."""
        self.pack(apply_it=True)
        with tarfile.open(os.path.join(self.target_root, "v9", "v9.tar")) as archive:
            names = [m.name for m in archive.getmembers() if m.isfile()]
        self.assertIn("v9/one.bff", names)
        self.assertIn("v9/sub/three.bff", names)

    def test_the_manifest_travels_inside_the_tar(self):
        r"""A tar that cannot be re-verified from a file inside itself is an opaque blob."""
        self.pack(apply_it=True)
        with tarfile.open(os.path.join(self.target_root, "v9", "v9.tar")) as archive:
            names = [m.name for m in archive.getmembers()]
        self.assertIn("v9/.sha256sum", names)

    def test_the_extra_manifest_member_does_not_count_as_a_failure(self):
        """It is in the tar and absent from its own line count, which is correct, not an error."""
        self.assertEqual(self.pack(apply_it=True), 0)
        self.assertIn("the 1 extra members are the four manifests", self.output())

    def test_all_three_checks_are_reported(self):
        self.pack(apply_it=True)
        said = self.output()
        for step in ("1/3 member list", "2/3 tar -d", "3/3 sha256"):
            self.assertIn(step, said)

    def test_it_says_the_mirror_is_untouched(self):
        r"""HE DELETES, NOT THIS TOOL -- and the run has to end by saying so."""
        self.assertEqual(TOOL.main(["--name", "v9", "--source-root", self.source_root,
                                    "--target-root", self.target_root, "--apply"]), 0)

    def test_the_source_tree_still_holds_every_file(self):
        before = sorted(os.listdir(os.path.join(self.source_root, "v9")))
        self.pack(apply_it=True)
        after = sorted(os.listdir(os.path.join(self.source_root, "v9")))
        self.assertEqual(before, after)


@NEEDS_GNU_TAR
class WhenSomethingIsWrong(Fixture):
    def setUp(self):
        Fixture.setUp(self)

    def test_a_manifest_naming_a_file_that_is_not_there(self):
        r"""-> MISSING, not a crash and not a pass."""
        rows = dict((rel, None) for rel in self.files)
        rows["gone.bff"] = "00" * 32
        self.write_manifest(rows)
        self.assertEqual(self.pack(apply_it=True), 1)
        self.assertIn("MISSING 1", self.output())

    def test_a_manifest_with_a_wrong_digest(self):
        r"""The member is present at the right size, so only check 3 can catch this."""
        rows = dict((rel, None) for rel in self.files)
        rows["one.bff"] = "11" * 32
        self.write_manifest(rows)
        self.assertEqual(self.pack(apply_it=True), 1)
        said = self.output()
        self.assertIn("extra members are the four manifests", said)   # check 1 was content
        self.assertIn("1 wrong", said)                                # check 3 caught it

    def test_and_it_names_which_member_failed(self):
        rows = dict((rel, None) for rel in self.files)
        rows["one.bff"] = "11" * 32
        self.write_manifest(rows)
        self.pack(apply_it=True)
        self.assertIn("v9/one.bff: sha256 differs", self.output())

    def test_a_tar_that_does_not_match_the_tree_any_more(self):
        r"""Check 2 reads tar's words, not its status: `Contents differ` is the failure."""
        self.write_manifest()
        self.assertEqual(self.pack(apply_it=True), 0)
        # EXACTLY THE SAME LENGTH as "first file\n", or check 1 reports a wrong size and returns
        # before check 2 ever runs -- which is how this test first passed for the wrong reason
        # while `tar -d` was not running at all.
        write(os.path.join(self.source_root, "v9", "one.bff"), "CHANGED!!!\n")
        self.assertEqual(self.pack(check_only=True), 1)
        self.assertIn("Contents differ", self.output())

    def test_a_changed_mtime_alone_is_not_a_failure(self):
        r"""MEASURED, AND THE REASON THE STATUS IS NOT TRUSTED: tar -d exits 1 for a re-dated
        file whose bytes are identical. Treating that as damage would condemn every tree that
        was ever touched by a copy."""
        self.write_manifest()
        self.assertEqual(self.pack(apply_it=True), 0)
        where = os.path.join(self.source_root, "v9", "one.bff")
        os.utime(where, (0, 0))
        self.assertEqual(self.pack(check_only=True), 0)
        self.assertIn("mtime only", self.output())


@NEEDS_GNU_TAR
class CheckingWithoutTheMirror(Fixture):
    r"""Check 3 is the one that still works after the subtree is gone, so it is pinned alone."""

    def test_digests_are_checked_straight_out_of_the_tar(self):
        self.write_manifest()
        self.pack(apply_it=True)
        want = TOOL.manifest_rows(os.path.join(self.source_root, "v9", common.SUMS_FILE))
        checked, bad = TOOL.check_digests(
            os.path.join(self.target_root, "v9", "v9.tar"), want, "v9", self.report)
        self.assertEqual((checked, bad), (3, []))

    def test_nothing_is_extracted_to_disk(self):
        """It streams; a drive with no room for 92 GB must still be able to run the check."""
        self.write_manifest()
        self.pack(apply_it=True)
        folder = os.path.join(self.target_root, "v9")
        before = sorted(os.listdir(folder))
        want = TOOL.manifest_rows(os.path.join(self.source_root, "v9", common.SUMS_FILE))
        TOOL.check_digests(os.path.join(folder, "v9.tar"), want, "v9", self.report)
        self.assertEqual(sorted(os.listdir(folder)), before)


class TheDocumentedReasons(unittest.TestCase):
    r"""The measurements behind the design, kept where a later reader will look for them."""

    def source(self):
        with io.open(os.path.join(HERE, "tar-subtree.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_it_records_why_rar_cannot_take_this_input(self):
        self.assertIn("165 files", TOOL.__doc__)
        self.assertIn("275 paths", TOOL.__doc__)

    def test_it_records_that_seven_zip_is_not_an_option(self):
        self.assertIn("Duplicate filename on disk", TOOL.__doc__)

    def test_it_records_the_measured_tar_d_statuses(self):
        """So nobody later replaces the output test with a status test."""
        doc = TOOL.__doc__
        self.assertIn("exit 0 and no output", doc)
        self.assertIn("Unexpected EOF", doc)

    def test_it_states_that_it_does_not_delete(self):
        self.assertIn("NEVER DELETES ANYTHING", TOOL.__doc__)

    def test_the_closing_line_says_the_mirror_is_untouched(self):
        self.assertIn("UNTOUCHED", self.source())

    def test_the_case_sensitive_comparison_is_explained_where_it_happens(self):
        self.assertIn("4542", TOOL.compare.__doc__)


# THE DRIVE-LETTER CASES ARE WINDOWS-ONLY BY NATURE, not by accident. `posix()` turns
# `X:\tarTarget\v3.tar` into `/x/tarTarget/v3.tar` because this MSYS tar reads `X:\...` as
# host:path -- and it goes through `os.path.abspath`, which on Linux reads `X:` as an ordinary
# directory name and answers `/cwd/X:/tarTarget/v3.tar`. There is no drive letter to translate on a
# POSIX host, so the cases that assert the translation are skipped there rather than asserted
# wrongly; `check_tar_binary` and the three real checks still run everywhere GNU tar exists.
ONLY_WITH_DRIVE_LETTERS = unittest.skipUnless(os.name == "nt", "drive letters are Windows-only")


@NEEDS_GNU_TAR
class TheBinaryAndItsPaths(unittest.TestCase):
    r"""The two findings that made check 2 a check which could not fail.

    `tar.exe` BY NAME GETS bsdtar. Windows searches System32 before the PATH, so a subprocess
    asking for "tar.exe" is handed bsdtar 3.8.8, which has no -d and answers with a four-line
    usage text and a non-zero status. The old check parsed that text for "Contents differ", found
    none, and declared the tar verified -- over an archive it had never compared once.

    AND GNU TAR READS A DRIVE LETTER AS host:path: "Cannot connect to C: resolve failed", exit
    128. `--force-local` fixes creation and then mangles the same path inside -d. The POSIX form
    is what this build understands, and all three operations behave with it.
    """

    @ONLY_WITH_DRIVE_LETTERS
    def test_a_drive_letter_becomes_a_posix_root(self):
        self.assertEqual(TOOL.posix("X:" + os.sep + "tarTarget" + os.sep + "v3.tar"),
                         "/x/tarTarget/v3.tar")

    @ONLY_WITH_DRIVE_LETTERS
    def test_the_drive_letter_is_lower_cased(self):
        """`/X/...` is not a path this binary resolves; `/x/...` is."""
        self.assertTrue(TOOL.posix("Q:" + os.sep + "mirror").startswith("/q/"))

    @ONLY_WITH_DRIVE_LETTERS
    def test_no_backslash_survives(self):
        self.assertNotIn(os.sep, TOOL.posix("X:" + os.sep + "a" + os.sep + "b"))

    def test_the_tool_names_gnu_tar_by_its_full_path(self):
        """Not by name, which is exactly what resolved to bsdtar."""
        self.assertTrue(os.path.isabs(TOOL.GNU_TAR))
        self.assertNotEqual(os.path.basename(TOOL.GNU_TAR), TOOL.GNU_TAR)

    def test_the_binary_is_verified_to_be_gnu_tar(self):
        said = []
        self.assertTrue(TOOL.check_tar_binary(report=said.append))
        self.assertIn("GNU tar", "\n".join(said))

    def test_a_binary_that_is_not_gnu_tar_is_refused(self):
        r"""bsdtar is on this machine, in System32, and is the one a bare name finds."""
        bsd = os.path.join(os.environ.get("SystemRoot", "C:" + os.sep + "Windows"),
                           "System32", "tar.exe")
        if not os.path.exists(bsd):
            self.skipTest("no bsdtar on this machine to test against")
        said = []
        self.assertFalse(TOOL.check_tar_binary(bsd, report=said.append))
        self.assertIn("is not GNU tar", "\n".join(said))

    def test_a_missing_binary_is_refused(self):
        said = []
        self.assertFalse(TOOL.check_tar_binary("X:" + os.sep + "nope.exe", report=said.append))
        self.assertIn("no GNU tar", "\n".join(said))


@NEEDS_GNU_TAR
class NothingTarSaysIsIgnored(Fixture):
    r"""The lesson from the silent pass: an unrecognised line must stop the run.

    When check 2 was broken, tar printed five lines of usage text. The classifier knew two shapes,
    counted zero of each, and passed. Now any line it cannot place is a failure.
    """

    def test_every_line_is_accounted_for(self):
        self.write_manifest()
        self.assertEqual(self.pack(apply_it=True), 0)
        self.assertIn("0 unrecognised", self.output())

    def test_the_counts_add_up_to_what_tar_printed(self):
        import re
        self.write_manifest()
        self.pack(apply_it=True)
        line = [one for one in self.said if "tar exited" in one][0]
        numbers = [int(n) for n in re.findall(r"[0-9]+", line)]
        status, total, content, dated, unknown = numbers[:5]
        self.assertEqual(content + dated + unknown, total)

    def test_an_unplaceable_line_fails_the_check(self):
        """Simulated by handing the classifier a usage text, which is what really happened."""
        self.write_manifest()
        self.pack(apply_it=True)
        self.assertIn("2/3 tar -d", self.output())


if __name__ == "__main__":
    unittest.main(verbosity=2)
