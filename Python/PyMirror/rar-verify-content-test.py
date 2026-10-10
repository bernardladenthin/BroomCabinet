# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Tests for rar-verify-content.py.

EVERY FIXTURE IS A FRESH tempfile.mkdtemp() AND NOTHING HERE NAMES THE COLLECTION. The tool reads
a mirror and unpacks 144 GB archives, so both roots are always passed explicitly into a temporary
directory. No test extracts a real archive: `compare()` is where the verdict lives and it takes a
directory, so the decisions are tested on directories a test can build.
"""
import hashlib
import io
import os
import shutil
import sys
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common                                                       # noqa: E402

TOOL = common.load_peer("rar-verify-content.py", "_rvc", HERE)


def write(path, data):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    mode = "wb" if isinstance(data, bytes) else "w"
    with io.open(path, mode) as handle:
        handle.write(data)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Extracted(unittest.TestCase):
    """A directory shaped like one `rar x` would produce, plus the digests it should match."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rvc-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def build(self, files):
        want = {}
        for rel, data in files.items():
            write(os.path.join(self.root, *rel.split("/")), data)
            want[rel] = sha(data)
        return want

    def test_everything_matching_reports_no_problem(self):
        want = self.build({"arch/a.txt": b"one", "arch/sub/b.bin": b"two"})
        checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        self.assertEqual((checked, bad), (2, []))

    def test_a_file_with_the_wrong_bytes_is_named(self):
        r"""THE FAULT THIS TOOL EXISTS FOR, and the one the header checks cannot see: the archive
        is internally consistent and holds content that is not what we packed."""
        want = self.build({"arch/a.txt": b"one"})
        want["arch/a.txt"] = sha(b"something else")
        checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        self.assertEqual(checked, 1)
        self.assertEqual(bad, [("arch/a.txt", "sha256 differs")])

    def test_a_file_the_archive_did_not_hold_is_a_different_fault(self):
        """Present-with-wrong-bytes and never-arrived read differently and are counted apart."""
        want = self.build({"arch/a.txt": b"one"})
        want["arch/gone.txt"] = sha(b"never packed")
        _checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        self.assertIn(("arch/gone.txt", "not extracted"), bad)

    def test_a_file_no_manifest_names_is_reported_too(self):
        r"""Expected in practice -- the per-archive manifests and markers are packed with every
        unit and are in no .sha256sum -- but counted rather than swallowed, because the same shape
        would be how a stray file got into a unit."""
        want = self.build({"arch/a.txt": b"one"})
        write(os.path.join(self.root, "arch", "extra.txt"), b"not in any manifest")
        _checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        self.assertIn(("arch/extra.txt", "in the archive, in no .sha256sum"), bad)

    def test_BOTH_DIRECTIONS_ARE_WALKED(self):
        r"""An earlier check in this project compared one way, matched on count, and missed 4542
        absent files. The walk says what is there, the manifest what should be, and neither alone
        is the answer."""
        want = self.build({"arch/a.txt": b"one"})
        want["arch/missing.txt"] = sha(b"x")
        write(os.path.join(self.root, "arch", "surplus.txt"), b"y")
        _checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        whys = sorted(why for _rel, why in bad)
        self.assertEqual(whys, ["in the archive, in no .sha256sum", "not extracted"])

    def test_the_comparison_is_case_sensitive(self):
        r"""THE WHOLE REASON THIS COLLECTION WAS REBUILT. `rar a` silently keeps one of two paths
        differing only in case; a check that folded case would be blind to exactly that.

        The two spellings cannot both exist in an ordinary Windows directory, so the manifest
        names one casing and the directory holds the other -- which must read as one missing and
        one surplus, not as a match.
        """
        self.build({"arch/Thing.txt": b"one"})
        want = {"arch/thing.txt": sha(b"one")}
        _checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        whys = sorted(why for _rel, why in bad)
        self.assertEqual(whys, ["in the archive, in no .sha256sum", "not extracted"])

    def test_an_empty_file_is_hashed_like_any_other(self):
        r"""CRC32 of zero bytes is 00000000 and that ambiguity cost an afternoon in the header
        check; SHA-256 of zero bytes is e3b0c442... and is ambiguous with nothing."""
        want = self.build({"arch/empty.bin": b""})
        checked, bad, _ours = TOOL.compare(self.root, want, report=lambda *_a: None)
        self.assertEqual((checked, bad), (1, []))
        self.assertTrue(want["arch/empty.bin"].startswith("e3b0c442"))

    def test_a_file_is_read_in_chunks_rather_than_whole(self):
        """A 20 GB member must not need 20 GB of memory to hash."""
        data = os.urandom(3 * (1 << 20))
        want = self.build({"arch/big.bin": data})
        self.assertEqual(TOOL.sha256_of(os.path.join(self.root, "arch", "big.bin")),
                         want["arch/big.bin"])


class ReadingOurOwnDigests(unittest.TestCase):
    r"""expected_digests() reads the .sha256sum WE wrote, which is the point of the check."""

    class FakeUnit(object):
        def __init__(self, archives, claims=None):
            self._archives = archives
            self._claims = claims

        def archives(self):
            return self._archives

        def claims(self, archive, rel):
            return self._claims is None or (archive, rel) in self._claims

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rvc-m-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def manifest(self, archive, lines):
        write(os.path.join(self.root, archive, common.SUMS_FILE), "\n".join(lines) + "\n")

    def test_it_reads_a_digest_and_a_path(self):
        self.manifest("arch", ["ab12 *dir/x.bff"])
        got = TOOL.expected_digests(self.FakeUnit(["arch"]), self.root, report=lambda *_a: None)
        self.assertEqual(got, {"arch/dir/x.bff": "ab12"})

    def test_a_path_with_spaces_survives(self):
        self.manifest("arch", ["ab12 *lib/IBM C Set.bff"])
        got = TOOL.expected_digests(self.FakeUnit(["arch"]), self.root, report=lambda *_a: None)
        self.assertIn("arch/lib/IBM C Set.bff", got)

    def test_two_casings_are_two_entries(self):
        self.manifest("arch", ["aa *A.TBL", "bb *a.TBL"])
        got = TOOL.expected_digests(self.FakeUnit(["arch"]), self.root, report=lambda *_a: None)
        self.assertEqual(len(got), 2)

    def test_only_what_the_unit_claims_is_expected(self):
        """A unit is a selection, not an archive: expecting a file another unit packs would report
        it missing from every archive but one."""
        self.manifest("arch", ["aa *mine.bff", "bb *theirs.bff"])
        unit = self.FakeUnit(["arch"], claims={("arch", "mine.bff")})
        got = TOOL.expected_digests(unit, self.root, report=lambda *_a: None)
        self.assertEqual(sorted(got), ["arch/mine.bff"])

    def test_several_archives_are_merged_under_their_own_names(self):
        self.manifest("one", ["aa *x.bff"])
        self.manifest("two", ["bb *x.bff"])
        got = TOOL.expected_digests(self.FakeUnit(["one", "two"]), self.root,
                                    report=lambda *_a: None)
        self.assertEqual(sorted(got), ["one/x.bff", "two/x.bff"])

    def test_a_missing_manifest_is_said_out_loud_rather_than_skipped(self):
        said = []
        TOOL.expected_digests(self.FakeUnit(["absent"]), self.root, report=said.append)
        self.assertIn("no .sha256sum", "\n".join(said))

    def test_blank_lines_and_comments_are_skipped(self):
        self.manifest("arch", ["; a note", "", "aa *x.bff"])
        got = TOOL.expected_digests(self.FakeUnit(["arch"]), self.root, report=lambda *_a: None)
        self.assertEqual(got, {"arch/x.bff": "aa"})


class ItDeletesNothing(unittest.TestCase):
    r"""THE OWNER'S INSTRUCTION ON 2026-10-06: no delete operation on the packing drive.

    "Hoellisch aufpassen auf x! Nicht loeschoperationen oder tests dort ausfuehren!" -- said while
    136 GB of this tool's own extraction was sitting there. The first version of --clean called
    shutil.rmtree on it, and only did not fire because the run had already returned a failure.
    That drive also holds every packed volume, so a wrong path costs the archive itself.
    """

    def source(self):
        with io.open(os.path.join(HERE, "rar-verify-content.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_source_calls_no_tree_removal_at_all(self):
        src = self.source()
        self.assertNotIn("rmtree", src)
        self.assertNotIn("os.remove", src)
        self.assertNotIn("os.unlink", src)

    def test_clean_only_prints_a_command(self):
        src = self.source()
        self.assertIn("DOES NOT REMOVE IT", src)
        self.assertIn("To remove it yourself", src)

    def test_and_the_docstring_promises_it(self):
        self.assertIn("DELETES NOTHING ANYWHERE", TOOL.__doc__)


class WhatWindowsCannotExtract(unittest.TestCase):
    r"""The run that was supposed to prove the archive instead proved something about the host.

    MEASURED 2026-10-06 against the real misc archive: `rar x` exited 9 after 895 seconds, with
    "Versuche den ungueltigen Datei- oder Verzeichnisnamen zu korrigieren" over paths holding
    `aux` -- a RESERVED DEVICE NAME on Windows, with con, prn, nul and com1. The collection has
    several, among them `.../swt/aux/spelling/...` and `.../slackware-2.1/usr/lib/nn/aux`.

    THE ARCHIVE IS CORRECT. RAR stored the real names; Windows cannot write them back, so RAR
    renames them on extraction and a path comparison then reports those files as missing AND
    surplus for a fault belonging to the filesystem. Which is why the two header checks are the
    better ones on this host: they never touch a filename at all.
    """

    RESERVED = ("aux", "prn", "com1")

    def test_the_tool_warns_about_this_before_the_extraction_is_attempted(self):
        self.assertIn("aux", TOOL.__doc__)
        self.assertIn("DIRECTORY COMPONENT", TOOL.__doc__)

    def test_it_records_the_measured_exit_status_and_cost(self):
        """So nobody spends another fifteen minutes discovering it."""
        self.assertIn("exit 9 after 895 seconds", TOOL.__doc__)
        self.assertIn("FOUR warnings", TOOL.__doc__)

    def test_it_records_that_only_four_files_were_affected(self):
        """A failure of four files in 341 969 is a footnote, not a verdict on the method."""
        self.assertIn("341 965 of 341 969", TOOL.__doc__)

    def test_IT_RECORDS_THAT_THE_FIRST_EXPLANATION_WAS_WRONG(self):
        r""""Windows cannot hold the name" was the first conclusion and the measurement refuses it:
        given an ABSOLUTE path, `aux` is created as an ordinary file and appears in the directory.
        The host can hold it; RAR's path handling gives up. Keeping the retraction in the
        docstring is the only thing that stops it being concluded again."""
        self.assertIn("WOULD BE TOO STRONG", TOOL.__doc__)
        self.assertIn("RAR's own path handling is what gives up", TOOL.__doc__)

    def test_WHETHER_A_RELATIVE_RESERVED_NAME_IS_REFUSED_IS_THE_HOSTS_ANSWER(self):
        r"""The half of the folklore that holds -- ON WINDOWS. It asserted all three names were
        refused, which is true there and false on Linux, where `aux` is an ordinary file. So it
        passed on the machine the collection lives on and failed on the runner with
        `[] != ['aux', 'prn', 'com1']`: a test reading the platform instead of the behaviour.

        AND A HOST THAT ACCEPTS THEM IS NOT AN EXCEPTION, IT IS THE ESCAPE ROUTE. The tool's own
        docstring names a Linux filesystem as one of the two ways this content check could work at
        all, because there these names extract cleanly. So both answers are recorded as correct
        and the test says which one it saw -- all refused, or none.
        """
        folder = tempfile.mkdtemp(prefix="rvc-res-")
        was = os.getcwd()
        try:
            os.chdir(folder)
            blocked = []
            for name in self.RESERVED:
                try:
                    handle = io.open(name, "w")
                    handle.write("x")
                    handle.close()
                except OSError:
                    blocked.append(name)
            # ALL OR NOTHING: a host that refuses some but not others would be a third behaviour
            # neither the tool nor its docstring accounts for, and worth stopping on.
            self.assertIn(blocked, ([], list(self.RESERVED)), blocked)
            if not blocked:
                self.assertIn("Linux filesystem", TOOL.__doc__,
                              "a host that accepts these is the documented escape route")
        finally:
            os.chdir(was)
            shutil.rmtree(folder, ignore_errors=True)

    def test_AND_AN_ABSOLUTE_ONE_IS_NOT(self):
        """Which is the measurement that corrected the explanation."""
        folder = tempfile.mkdtemp(prefix="rvc-abs-")
        try:
            where = os.path.join(folder, "aux")
            handle = io.open(where, "w")
            handle.write("x")
            handle.close()
            self.assertIn("aux", os.listdir(folder))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_it_names_the_two_ways_a_content_check_could_still_work(self):
        doc = TOOL.__doc__
        self.assertIn("Linux filesystem", doc)
        self.assertIn("rar p", doc)


class EndToEndWithARealArchive(unittest.TestCase):
    r"""The whole chain on a tiny archive, built with the production switches.

    THE DELETE QUESTION IS ANSWERED HERE AND NOT BY READING THE SOURCE. The other tests assert
    that `rmtree` does not appear; this one runs the tool with --apply --clean to a successful
    exit -- the path where a removal would be most plausible -- and then checks that the
    extraction is still on disk.

    EVERYTHING IS UNDER tempfile.mkdtemp() ON C:. The owner's instruction on 2026-10-06 was that
    no test may run a delete operation on the packing drive, and the fixture this removes is one
    it created in the system temp directory two lines earlier.

    IT ALSO EXERCISES WHAT THE UNIT TESTS CANNOT: -oi1 collapsing a real duplicate, an empty file
    whose sha256 is e3b0c442..., a real volume split with -rr1 and -rv2, and a manifest that does
    not list itself. The last of those is what the first end-to-end run found: our own bookkeeping
    was being reported as a fault, which on misc would have been 367 of them and would have made
    every real run read as a failure.
    """

    class FakeUnit(object):
        name = "tiny"

        def archives(self):
            return ["arch"]

        def claims(self, _archive, _rel):
            return True

    class FakePacker(object):
        @staticmethod
        def first_volume(archive):
            import glob
            found = sorted(glob.glob(glob.escape(archive[:-4]) + ".part*.rar"))
            return found[0] if found else archive

    def setUp(self):
        if not TOOL.find_rar():
            self.skipTest("no Rar.exe on this machine")
        self.base = tempfile.mkdtemp(prefix="rvc-e2e-")
        self.was = TOOL.load_packer

    def tearDown(self):
        TOOL.load_packer = self.was
        shutil.rmtree(self.base, ignore_errors=True)

    def build(self):
        root = os.path.join(self.base, "mirror")
        tree = os.path.join(root, "arch")
        os.makedirs(os.path.join(tree, "sub"))
        payload = os.urandom(300 * 1024)
        files = {"one.txt": b"the first file\n", "sub/two.bin": payload,
                 "sub/empty.bin": b"", "sub/dup.bin": payload}
        lines = []
        for rel in sorted(files):
            write(os.path.join(tree, *rel.split("/")), files[rel])
            lines.append("%s *%s" % (sha(files[rel]), rel))
        write(os.path.join(tree, common.SUMS_FILE), "\n".join(lines) + "\n")
        return root

    def pack(self, root):
        out = os.path.join(self.base, "packed")
        os.makedirs(out)
        archive = os.path.join(out, "tiny.rar")
        done = subprocess.run(
            [TOOL.find_rar(), "a", "-ma5", "-m5", "-md256m", "-s", "-oi1", "-v200000b",
             "-rr1", "-rv2", "-k", "-scfl", "-idq", archive, "arch"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(done.returncode, 0,
                         done.stdout.decode("utf-8", "replace")[:300])
        return archive

    def run_tool(self, root, archive, *extra):
        packer = self.FakePacker()
        packer.UNITS = [self.FakeUnit()]
        TOOL.load_packer = lambda: packer
        scratch = os.path.join(self.base, "verify")
        return TOOL.main(["--archive", archive, "--unit", "tiny", "--root", root,
                          "--scratch", scratch] + list(extra)), os.path.join(scratch, "tiny")

    def test_the_whole_chain_comes_out_clean(self):
        root = self.build()
        archive = self.pack(root)
        code, _where = self.run_tool(root, archive, "--apply")
        self.assertEqual(code, 0)

    def test_AND_CLEAN_DOES_NOT_REMOVE_THE_EXTRACTION(self):
        r"""THE POINT OF THIS CLASS. Exit 0 is the path where a removal would be most plausible."""
        root = self.build()
        archive = self.pack(root)
        code, where = self.run_tool(root, archive, "--apply", "--clean")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isdir(where), "the extraction was removed")
        got = [f for _d, _s, fs in os.walk(where) for f in fs]
        self.assertEqual(len(got), 5)        # four files and the manifest

    def test_a_duplicate_and_an_empty_file_both_verify(self):
        r"""-oi1 turns the duplicate into a reference with no CRC32 of its own, and the empty file
        is the shape that confused the CRC32 check for an afternoon. Both hash correctly."""
        root = self.build()
        archive = self.pack(root)
        code, where = self.run_tool(root, archive, "--apply")
        self.assertEqual(code, 0)
        with io.open(os.path.join(where, "arch", "sub", "dup.bin"), "rb") as handle:
            dup = handle.read()
        with io.open(os.path.join(where, "arch", "sub", "two.bin"), "rb") as handle:
            self.assertEqual(dup, handle.read())
        self.assertEqual(os.path.getsize(os.path.join(where, "arch", "sub", "empty.bin")), 0)

    def test_OUR_OWN_MANIFEST_IS_COUNTED_AND_NOT_FAULTED(self):
        r"""What the first end-to-end run found: `.sha256sum` is in the archive and in no
        `.sha256sum`, because a manifest does not list itself. Reported as a fault it would have
        been 367 of them on misc, and every real run would have read as a failure."""
        root = self.build()
        archive = self.pack(root)
        code, where = self.run_tool(root, archive, "--apply")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(where, "arch", common.SUMS_FILE)))

    def test_a_tampered_file_fails_the_check(self):
        r"""And the whole thing is worthless if it cannot fail. One byte changed in the manifest's
        expectation, and the run must come back non-zero."""
        root = self.build()
        manifest = os.path.join(root, "arch", common.SUMS_FILE)
        with io.open(manifest, encoding="utf-8") as handle:
            text = handle.read()
        write(manifest, text.replace(text[:8], "ffffffff", 1))
        archive = self.pack(root)
        code, _where = self.run_tool(root, archive, "--apply")
        self.assertEqual(code, 1)


class TheDocumentedReasons(unittest.TestCase):
    r"""Why this check exists beside two cheaper ones, kept where a later reader will look."""

    def source(self):
        with io.open(os.path.join(HERE, "rar-verify-content.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_it_records_what_rar_t_cannot_notice(self):
        self.assertIn("both sides of that comparison come", TOOL.__doc__)

    def test_it_records_what_the_crc32_check_found(self):
        self.assertIn("165 wrong files", TOOL.__doc__)

    def test_it_records_why_it_is_not_the_default(self):
        self.assertIn("144 GB of scratch", TOOL.__doc__)

    def test_it_records_the_oi1_reason(self):
        """The reference question is what this tool answers without reasoning."""
        self.assertIn("reference carries no CRC32", TOOL.__doc__)

    def test_it_states_that_the_collection_is_only_read(self):
        self.assertIn("NEVER TOUCHES THE COLLECTION", TOOL.__doc__)

    def test_a_failure_leaves_the_extraction_in_place(self):
        """Evidence is worth more than disk: --clean removes nothing after a bad result."""
        src = self.source()
        self.assertIn("left at %s to be looked at", src)
        self.assertLess(src.index("THE CONTENT CHECK FAILED"), src.index("if args.clean"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
