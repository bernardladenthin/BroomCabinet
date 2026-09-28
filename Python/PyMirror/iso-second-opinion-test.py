#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""iso-second-opinion.py, without 7-Zip and without the collection.

WHAT THE TOOL IS FOR, in one line: `--declared` can tell that an ISO is smaller than its own
volume descriptor says, and cannot tell whether that is truncation. 7-Zip can. This file checks
everything except 7-Zip itself -- which findings are read out of a report, which verdict a listing
earns, and that a missing 7-Zip stops the run instead of being guessed around.

THE TWO THAT MATTER MOST, and both are about refusing to answer:

  * **`Errors` beats a total that fits.** 7-Zip listing 1.33 kB of a 327 MB image and complaining
    is not evidence that the image is fine; it is evidence that nobody can read it. An earlier
    version of this classification counted those as "fits", which turned 52 unreadable images
    into 52 clean bills of health.

  * **No 7-Zip means no run.** Falling back to the volume descriptor alone would be exactly the
    guess this tool exists to replace, and it would print a confident verdict with nothing behind
    it.

WHY THE SUBPROCESS IS STUBBED AND NOT RUN. A test that depended on 7-Zip being installed would
fail on a machine where it is not, for a reason that says nothing about the code -- and the tool
already reports that case itself. The stub returns the shapes 7-Zip really produced, taken from
the run on 2026-09-25.
"""
import io
import importlib.util
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("iso-second-opinion")

# Real shapes, abridged, from the run of 2026-09-25.
TRUNCATED_OUT = """
2004-12-16 21:46:21 .....      7887963      7887963  02BP222_067_067.rpm
------------------- ----- ------------ ------------  ------------------------
2004-12-16 21:49:27           48467805     48467805  5 files

Errors: 1
"""
CLEAN_OUT = """
1995-02-14 09:00:00 .....       565248       565248  TOOL/etc/update
------------------- ----- ------------ ------------  ------------------------
1995-02-14 19:49:40            1323692      1330688  34 files, 11 folders

Warnings: 1
"""
FRAGMENT_OUT = """
------------------- ----- ------------ ------------  ------------------------
2001-02-06 16:45:14               1360         1360  2 files

ERROR = Incorrect big-endian headers
Errors: 2
"""
NOTHING_OUT = "7-Zip 24.09\n\nERROR: Cannot open the file as archive\n"


class Result:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0


def runner(stdout):
    return lambda *a, **k: Result(stdout)


class WhichFindingsItReads(unittest.TestCase):
    """The report is the input, and only its ISO lines are."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iso-opinion-test-")
        self.report = os.path.join(self.tmp, "declared.txt")
        with io.open(self.report, "w", encoding="utf-8") as fh:
            fh.write(
                "=== Declared: files that state their own length and do not have it ===\n"
                "  A FILE SHORTER THAN IT SAYS IT IS -- these are losses\n"
                "         2.43 GB missing  82.11 MB of 2.52 GB  ISO 9660  arc/a.iso\n"
                "       559.56 MB missing  2.89 MB of 562.45 MB  RIFF      arc/b.wav\n"
                "        28.09 MB missing  20.45 MB of 48.54 MB  ISO 9660  arc/deep/c.iso\n"
                "    205 files\n"
                "  and 327 files whose own record is GONE -- a zip must end with a central directory:\n"
                "         5.24 MB  ZIP       arc/d.zip\n")

    def test_only_the_iso_rows(self):
        """A RIFF finding is a different question and 7-Zip is not the reader for it."""
        self.assertEqual(TOOL.findings(self.report), ["arc/a.iso", "arc/deep/c.iso"])

    def test_the_zip_section_is_not_mistaken_for_findings(self):
        self.assertNotIn("arc/d.zip", TOOL.findings(self.report))

    def test_a_report_with_no_iso_rows_yields_nothing(self):
        empty = os.path.join(self.tmp, "empty.txt")
        with io.open(empty, "w", encoding="utf-8") as fh:
            fh.write("  A FILE SHORTER THAN IT SAYS IT IS -- these are losses\n    0 files\n")
        self.assertEqual(TOOL.findings(empty), [])


class WhatSevenZipSays(unittest.TestCase):

    def test_it_reads_the_total_and_the_count_from_the_summary(self):
        total, files, note = TOOL.listing("7z", "x.iso", run=runner(TRUNCATED_OUT))
        self.assertEqual((total, files, note), (48467805, 5, "Errors"))

    def test_a_warning_is_not_an_error(self):
        _total, _files, note = TOOL.listing("7z", "x.iso", run=runner(CLEAN_OUT))
        self.assertEqual(note, "Warnings")

    def test_output_with_no_summary_line_is_no_answer(self):
        total, files, _note = TOOL.listing("7z", "x.iso", run=runner(NOTHING_OUT))
        self.assertIsNone(total)
        self.assertIsNone(files)

    def test_it_never_raises(self):
        def boom(*a, **k):
            raise OSError("no such tool")
        total, _files, note = TOOL.listing("7z", "x.iso", run=boom)
        self.assertIsNone(total)
        self.assertEqual(note, "OSError")


class WhichVerdictAListingEarns(unittest.TestCase):

    def test_a_total_larger_than_the_file_is_truncation(self):
        self.assertEqual(TOOL.judge(20446920, 48467805, "Errors"), TOOL.TRUNCATED)

    def test_a_clean_listing_that_fits_is_not_damage(self):
        """82 MB of file, 1.3 MB of ISO 9660 filesystem, and a descriptor claiming 2.52 GB.

        The image is not short of its own filesystem; the descriptor simply describes more than
        the file holds, which happens and is not a loss.
        """
        self.assertEqual(TOOL.judge(82108416, 1323692, "Warnings"), TOOL.FITS)

    def test_ERRORS_BEAT_A_TOTAL_THAT_FITS(self):
        """The classification mistake this test exists for.

        7-Zip listing 1 360 bytes of a 327 MB image and reporting `Incorrect big-endian headers`
        means it could not read the filesystem -- not that the filesystem is small and healthy.
        Counting those as "fits" turned 52 unreadable images into 52 clean bills of health.
        """
        self.assertEqual(TOOL.judge(343685120, 1360, "Errors"), TOOL.NO_VERDICT)

    def test_a_reader_that_said_nothing_gives_no_verdict(self):
        self.assertEqual(TOOL.judge(1000, None, "no summary"), TOOL.NO_VERDICT)

    def test_every_verdict_is_in_ORDER_and_they_are_distinct(self):
        named = {TOOL.TRUNCATED, TOOL.FITS, TOOL.NO_VERDICT, TOOL.UNREADABLE}
        self.assertEqual(set(TOOL.ORDER), named)
        self.assertEqual(len(TOOL.ORDER), len(named))

    def test_the_one_that_needs_acting_on_comes_first(self):
        self.assertEqual(TOOL.ORDER[0], TOOL.TRUNCATED)


class WithoutSevenZipItRefuses(unittest.TestCase):
    """No second opinion is not the same as a second opinion that agrees."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iso-opinion-test-")
        self.report = os.path.join(self.tmp, "declared.txt")
        with io.open(self.report, "w", encoding="utf-8") as fh:
            fh.write("         2.43 GB missing  82.11 MB of 2.52 GB  ISO 9660  arc/a.iso\n")

    def run_tool(self, *argv):
        out = io.StringIO()
        keep = sys.stdout
        sys.stdout = out
        try:
            code = TOOL.main(list(argv))
        finally:
            sys.stdout = keep
        return code, out.getvalue()

    def test_it_stops_rather_than_falling_back_to_the_descriptor(self):
        real = TOOL.find_seven_zip
        TOOL.find_seven_zip = lambda *a, **k: None
        try:
            code, text = self.run_tool("--report", self.report)
        finally:
            TOOL.find_seven_zip = real
        self.assertEqual(code, 2)
        self.assertIn("REFUSING TO RUN", text)

    def test_and_says_where_it_looked(self):
        real = TOOL.find_seven_zip
        TOOL.find_seven_zip = lambda *a, **k: None
        try:
            _code, text = self.run_tool("--report", self.report)
        finally:
            TOOL.find_seven_zip = real
        for candidate in TOOL.SEVEN_ZIP_CANDIDATES:
            self.assertIn(candidate, text)

    def test_a_report_that_is_not_there_is_refused(self):
        code, _text = self.run_tool("--report", os.path.join(self.tmp, "nope.txt"))
        self.assertEqual(code, 2)

    def test_a_report_with_no_iso_findings_is_refused_rather_than_called_clean(self):
        empty = os.path.join(self.tmp, "empty.txt")
        with io.open(empty, "w", encoding="utf-8") as fh:
            fh.write("nothing here\n")
        code, _text = self.run_tool("--report", empty)
        self.assertEqual(code, 2)


class ItDoesNotReachIntoTheLibrary(unittest.TestCase):
    """`common.py` is standard library only, and this tool must not change that."""

    def test_nothing_in_the_library_imports_it(self):
        """ASKED OF THE IMPORTS, not of the text.

        The first version grepped for the name and failed on `audit.py`, which cites the
        measurement file `measurements/iso-second-opinion-2026-09-25.md` in a docstring. A check
        that cannot tell an import from a pointer to a record forbids writing the pointer down --
        the same mistake two other ratchets in this repository made and had to be taught out of.

        AND IT DOES NOT FORBID `subprocess`. A second version of this test did, on the theory that
        "standard library only" meant "no child processes". It does not: `common.py` runs
        `fsutil file setCaseSensitiveInfo` on purpose, and `subprocess` IS the standard library.
        The rule this collection actually keeps is that nothing outside Python's own distribution
        is required -- 7-Zip is borrowed for one investigation and no check depends on it.
        """
        import ast
        here = os.path.dirname(os.path.abspath(__file__))
        for name in ("common.py", "audit.py"):
            with io.open(os.path.join(here, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for imported in names:
                    self.assertNotIn("iso_second_opinion", imported, name)

    def test_it_uses_the_collection_constant_rather_than_a_path(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "iso-second-opinion.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("MIRROR_ROOT", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
