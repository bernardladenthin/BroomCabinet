# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Tests for pack-progress.py.

EVERY FIXTURE IS A FRESH tempfile.mkdtemp() AND NOTHING HERE NAMES THE COLLECTION. The tool only
reads, so there is nothing it could damage -- but `--work` is still always passed explicitly into
a temporary directory, because a test that found the real `X:\tar` would read the live run's
files and report on it instead of on itself.
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

TOOL = common.load_peer("pack-progress.py", "_packprog", HERE)


class Fixture(unittest.TestCase):
    """A work directory with a list, an index and a log, as b2-pack leaves them."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="pp-")
        self.log = os.path.join(self.work, "unit-pack.log")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.work, name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def build(self, rows, log_lines=(), unit="unit"):
        """rows: [(archive, path, size)] in packing order."""
        self.write(unit + ".list",
                   "\n".join("%s\\%s" % (a, p) for a, p, _s in rows) + "\n")
        self.write(unit + ".index.csv",
                   "archive,path,size,sha256\n"
                   + "\n".join("%s,%s,%d,ab" % (a, p, s) for a, p, s in rows) + "\n")
        self.write(unit + "-pack.log", "\n".join(log_lines) + ("\n" if log_lines else ""))

    def said(self, unit="unit"):
        lines = []
        code = TOOL.report(unit, self.work, os.path.join(self.work, unit + "-pack.log"),
                           report_to=lines.append)
        return code, "\n".join(lines)


class ReadingThePackingOrder(Fixture):
    def test_the_list_is_the_order(self):
        self.build([("arch", "b.bff", 10), ("arch", "a.bff", 20)])
        got = TOOL.packing_order(os.path.join(self.work, "unit.list"))
        self.assertEqual(got, ["arch\\b.bff", "arch\\a.bff"])

    def test_forward_slashes_become_backslashes(self):
        r"""The list carries forward slashes and RAR echoes backslashes; one of them has to give,
        and the comparison is against RAR's output."""
        self.write("unit.list", "arch/sub/x.bff\n")
        got = TOOL.packing_order(os.path.join(self.work, "unit.list"))
        self.assertEqual(got, ["arch\\sub\\x.bff"])

    def test_blank_lines_are_skipped(self):
        self.write("unit.list", "arch/a.bff\n\n\narch/b.bff\n")
        self.assertEqual(len(TOOL.packing_order(os.path.join(self.work, "unit.list"))), 2)


class ReadingTheSizes(Fixture):
    def test_the_header_row_is_not_a_file(self):
        self.build([("arch", "a.bff", 7)])
        got = TOOL.sizes_from_index(os.path.join(self.work, "unit.index.csv"))
        self.assertEqual(got, {"arch\\a.bff": 7})

    def test_a_row_with_a_bad_size_is_skipped_rather_than_raising(self):
        self.write("unit.index.csv", "archive,path,size,sha256\narch,a.bff,notanumber,ab\n")
        self.assertEqual(TOOL.sizes_from_index(os.path.join(self.work, "unit.index.csv")), {})

    def test_a_short_row_is_skipped(self):
        self.write("unit.index.csv", "archive,path,size,sha256\narch,a.bff\n")
        self.assertEqual(TOOL.sizes_from_index(os.path.join(self.work, "unit.index.csv")), {})


class CountingHowFarRarHasGot(Fixture):
    r"""The position is the NUMBER of `Archiviere` lines, not the name in the last one.

    RAR TRUNCATES THE NAME to its output column. Measured 2026-10-07 on the oldskool log:

        'oldskool\\misc\\...\\VHS Tutorial Videos\\G'
        'oldskool\\drivers\\Panasonic\\...\\typing and printing on the Panas'

    Those are prefixes cut mid-word, so a name lookup cannot find them in the packing list at all
    -- neither exactly nor by suffix, because a prefix is not a suffix. The first version matched
    whatever it collided with and reported 87.7 %, then 49.0 % minutes later. A figure that walks
    backwards is the symptom that found this.
    """

    def test_the_lines_are_counted(self):
        self.write("unit-pack.log",
                   "Archiviere a\\1       5%\nArchiviere a\\2      12%\n")
        self.assertEqual(TOOL.files_named(self.log), (2, False))

    def test_A_TRUNCATED_NAME_IS_STILL_COUNTED(self):
        r"""Which is the whole point: the name is unusable and the count is not."""
        self.write("unit-pack.log",
                   "Archiviere oldskool\\misc\\very long path cut off at the col      7%\n")
        self.assertEqual(TOOL.files_named(self.log), (1, False))

    def test_the_english_word_is_accepted_too(self):
        """`Adding` on an English build; this machine's RAR speaks German."""
        self.write("unit-pack.log", "Adding    a\\1        7%\n")
        self.assertEqual(TOOL.files_named(self.log), (1, False))

    def test_A_TESTING_LINE_MEANS_PACKING_IS_OVER(self):
        r"""`rar t` follows `rar a` in the same run, and extrapolating a finished phase would
        report time left for work already done."""
        self.write("unit-pack.log",
                   "Archiviere a\\1      99%\nTeste       a\\1      OK\n")
        self.assertEqual(TOOL.files_named(self.log), (1, True))

    def test_an_archiving_line_AFTER_a_test_line_clears_the_flag(self):
        r"""A unit's own `rar t` can be followed by nothing, but a run of several units packs
        again after testing the first -- so the flag has to reflect the LAST phase, not any."""
        self.write("unit-pack.log",
                   "Archiviere a\\1   9%\nTeste a\\1 OK\nArchiviere b\\1   3%\n")
        self.assertEqual(TOOL.files_named(self.log), (2, False))

    def test_no_line_at_all_is_zero_and_not_an_error(self):
        """b2-pack spends minutes building the list before Rar.exe starts."""
        self.write("unit-pack.log", "  misc   341969 files in\n")
        self.assertEqual(TOOL.files_named(self.log), (0, False))


class TheEstimate(Fixture):
    r"""The share is by FILE COUNT, and the two attempts at bytes before it both failed.

    1. A name lookup could not find a long path, because RAR truncates the name to its output
       column. It reported 87.7 % and then 49.0 % minutes later.
    2. Counting the lines fixed the position, but summing the first N entries of the LIST still
       added up the wrong files, because RAR DOES NOT PACK IN LIST ORDER. rar.txt: "Normalerweise
       werden Dateien in soliden Archiven nach ihrer Erweiterung sortiert" -- sorted BY EXTENSION,
       which is what makes -s worth having. Measured on ibm-aix-opensource: all .txt first, .rpm
       much later, while the tool claimed 0.3 % of bytes with 25 GB already written.

    THE SORT COULD BE REPLICATED AND IS NOT. "By extension" is all the documentation gives, the
    tie-breaking is unstated, and a rarfiles.lst may override it -- a byte share built on a
    guessed sort would be wrong invisibly, which is worse than a count that is right about what it
    measures.
    """

    def test_the_position_is_the_count_clamped_to_the_list(self):
        self.assertEqual(TOOL.progress(["a\\1", "a\\2", "a\\3"], 2), (2, 3))

    def test_nothing_named_yet_is_None(self):
        self.assertIsNone(TOOL.progress(["a\\1"], 0))

    def test_MORE_NAMED_THAN_THE_LIST_HOLDS_DOES_NOT_RUN_OFF_THE_END(self):
        r"""Measured: ibm-aix-opensource's log held 184 472 names for 184 465 files and oldskool's
        77 632 for 77 631 -- the index CSV goes to RAR as an extra argument beside the @list."""
        self.assertEqual(TOOL.progress(["a\\1", "a\\2"], 7), (2, 2))

    def test_NO_SIZES_ARE_CONSULTED(self):
        r"""The signature itself is the guard: a byte share cannot be computed from a list whose
        order is not the packing order, so the function is not given the sizes at all."""
        import inspect
        self.assertEqual(list(inspect.signature(TOOL.progress).parameters), ["order", "named"])


class WhatIsWrittenSoFar(Fixture):
    r"""The one physical fact available, reported beside the count and not extrapolated from.

    Without knowing the final ratio it says nothing about the remainder -- the five units so far
    came out between 52.5 % and 80.4 % of their source -- so it is printed and left alone.
    """

    def test_it_sums_the_volumes_and_the_rev_files(self):
        folder = os.path.join(self.work, "out")
        os.makedirs(folder)
        for name, size in (("u.part01.rar", 100), ("u.part02.rar", 200), ("u.part01.rev", 50)):
            with io.open(os.path.join(folder, name), "wb") as handle:
                handle.write(b"x" * size)
        self.assertEqual(TOOL.written_bytes(folder), 350)

    def test_it_ignores_everything_else(self):
        r"""The index CSV and the manifests sit in the same directory and are not archive bytes."""
        folder = os.path.join(self.work, "out2")
        os.makedirs(folder)
        for name in ("u.part01.rar", "u.index.csv", common.SUMS_FILE, "pack.log"):
            with io.open(os.path.join(folder, name), "wb") as handle:
                handle.write(b"x" * 10)
        self.assertEqual(TOOL.written_bytes(folder), 10)

    def test_a_directory_that_is_not_there_yet_is_None_and_not_zero(self):
        """Nothing written and no directory are different states, and only one is worth a line."""
        self.assertIsNone(TOOL.written_bytes(os.path.join(self.work, "never")))


class TheReport(Fixture):
    def test_it_names_the_share_and_the_time_left(self):
        self.build([("a", "1", 100), ("a", "2", 100), ("a", "3", 800)],
                   ["Archiviere a\\1       50%", "Archiviere a\\2       10%"])
        # the list's mtime is the start, so push it back an hour
        path = os.path.join(self.work, "unit.list")
        os.utime(path, (os.path.getatime(path), os.path.getmtime(path) - 3600))
        code, text = self.said()
        self.assertEqual(code, 0)
        self.assertIn("file 2 of 3", text)
        self.assertIn("66.7 % of the work list", text)
        self.assertIn("IF THE REST AVERAGES THE SAME", text)

    def test_it_says_when_packing_is_done(self):
        self.build([("a", "1", 100)], ["Archiviere a\\1      99%", "Teste a\\1    OK"])
        code, text = self.said()
        self.assertEqual(code, 0)
        self.assertIn("packing is DONE", text)
        self.assertNotIn("left for packing", text)

    def test_it_says_when_the_list_is_still_being_built(self):
        self.build([("a", "1", 100)], ["  unit   1 files in"])
        _code, text = self.said()
        self.assertIn("still building the list", text)

    def test_too_early_is_said_rather_than_a_wild_number(self):
        r"""One file of a thousand read is not a rate worth extrapolating from."""
        rows = [("a", "%d" % n, 1) for n in range(1, 1001)]
        rows[0] = ("a", "1", 1)
        self.build(rows, ["Archiviere a\\1      1%"])
        _code, text = self.said()
        self.assertIn("too early", text)

    def test_A_MISSING_FILE_IS_A_REFUSAL_AND_NAMES_WHICH(self):
        self.build([("a", "1", 100)], ["Archiviere a\\1      5%"])
        os.remove(os.path.join(self.work, "unit.index.csv"))
        code, text = self.said()
        self.assertEqual(code, 2)
        self.assertIn("unit.index.csv", text)

    def test_EVERY_FILE_NAMED_IS_SAID_PLAINLY(self):
        r"""The last volume can take minutes after the last file is read, and "99.9 %, 0 min left"
        would be a worse answer than naming the phase."""
        self.build([("a", "1", 100)], ["Archiviere a\\1      5%", "Archiviere a\\1     99%"])
        code, text = self.said()
        self.assertEqual(code, 0)
        self.assertIn("every file has been named", text)


class HowTheDurationReads(unittest.TestCase):
    def test_minutes_below_an_hour_and_a_half(self):
        self.assertEqual(TOOL.as_hours(20 * 60), "20 min")
        self.assertEqual(TOOL.as_hours(89 * 60), "89 min")

    def test_hours_above_it(self):
        self.assertEqual(TOOL.as_hours(2.4 * 3600), "2.4 h")

    def test_nine_hours_reads_as_hours(self):
        """bitsavers-paper is the reason this tool exists; nine hours must not print as 540 min."""
        self.assertEqual(TOOL.as_hours(9 * 3600), "9.0 h")


class TheDocumentedReasons(unittest.TestCase):
    def test_it_records_why_bytes_and_not_count(self):
        doc = TOOL.__doc__
        self.assertIn("87.7 %", doc)
        self.assertIn("nach ihrer Erweiterung sortiert", doc)

    def flat(self, text):
        """Docstrings wrap, and an assertion against a wrapped sentence tests the wrapping."""
        return " ".join((text or "").split())

    def source(self):
        with io.open(os.path.join(HERE, "pack-progress.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_it_records_that_it_reads_nothing_expensive(self):
        self.assertIn("Nothing reads the collection or the archive", self.flat(TOOL.__doc__))

    def test_it_records_why_the_list_mtime_is_the_start_time(self):
        r"""The alternative -- the first volume's mtime -- appears only after 3.5 GB have been
        compressed, which on bitsavers-paper is half an hour of having nothing to say."""
        self.assertIn("THE LIST IS WRITTEN IMMEDIATELY BEFORE Rar.exe STARTS",
                      self.flat(self.source()))

    def test_it_records_what_a_Teste_line_means(self):
        self.assertIn("PACKING IS OVER", self.flat(TOOL.files_named.__doc__))


if __name__ == "__main__":
    unittest.main(verbosity=2)
