#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""unittest for common.py -- every promise it makes, against a real filesystem where it needs one.

    python -m unittest common_test -v
    python common_test.py

WHAT IS WORTH TESTING HERE, and it is not "does human() format a number". It is the handful of
decisions that were WRONG in at least one of the copies these functions replace:

    long_path must not normalise      three copies used os.path.abspath, which strips a trailing
                                      dot; 21 files in these mirrors end in one
    exists must take a relative path  one copy glued \\?\ onto a relative path, which can never
                                      match anything
    human must be decimal             nine copies disagreed, several dividing by 1024 while
                                      printing "GB", so the same byte count read differently
                                      depending on which tool printed it
    parse_size must be BINARY         the other direction, and the one that bit: a listing's
                                      "1.6M" is 1 677 721 bytes, which was once compared against
                                      an exact 1 657 522 and reported as a difference
    the agent must not say Mozilla/   measured on ndwiki.org: that prefix is served a challenge
    own-files must be ONE set         eight tools kept their own and no two agreed

unittest rather than a hand-rolled checker because this is a library now, and a library is tested
the way Python tests libraries -- so that `python -m unittest` finds it, a failure names the case
and shows the values, and adding a case means adding a method.
"""

import ast
import glob
import importlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import socket
import urllib.error
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import mediawiki  # noqa: E402   # one test compares its rule against common's

WINDOWS = os.name == "nt"
on_windows = unittest.skipUnless(WINDOWS, "the \\\\?\\ prefix only means anything on Windows")


class TestIdentity(unittest.TestCase):
    """One agent, everywhere, and it must keep the shape that gets served."""

    def test_is_a_string(self):
        self.assertIsInstance(common.user_agent(), str)
        self.assertTrue(common.user_agent())

    def test_does_not_claim_to_be_a_browser(self):
        # Measured on ndwiki.org 2026-09-17: anything beginning Mozilla/ was answered with a
        # proof-of-work challenge. This is the regression guard for that measurement.
        self.assertFalse(common.user_agent().startswith("Mozilla/"))

    def test_carries_no_contact_address(self):
        self.assertNotIn("@", common.user_agent())

    def test_does_not_call_itself_a_bot(self):
        # pmwiki-source.py's note: one host blocks \w+[-_ ]?(bot|spider|crawler).
        low = common.user_agent().lower()
        for word in ("bot", "spider", "crawler", "slurp"):
            self.assertNotIn(word, low)

    def test_headers_carry_it(self):
        self.assertEqual(common.request_headers(), {"User-Agent": common.user_agent()})

    def test_headers_accept_extras(self):
        got = common.request_headers({"Range": "bytes=10-"})
        self.assertEqual(got["User-Agent"], common.user_agent())
        self.assertEqual(got["Range"], "bytes=10-")

    def test_extras_win_a_conflict(self):
        got = common.request_headers({"User-Agent": "something else"})
        self.assertEqual(got["User-Agent"], "something else")

    def test_headers_do_not_share_state(self):
        # A caller that mutates the result must not change the next caller's headers.
        first = common.request_headers()
        first["User-Agent"] = "mutated"
        self.assertEqual(common.request_headers()["User-Agent"], common.user_agent())


class TestLongPath(unittest.TestCase):
    """The prefix exists to reach names Windows otherwise cannot. It must not damage them."""

    @unittest.skipIf(WINDOWS, "POSIX behaviour")
    def test_identity_on_posix(self):
        self.assertEqual(common.long_path("/x/y."), "/x/y.")
        self.assertEqual(common.long_path("a/b"), "a/b")

    @on_windows
    def test_trailing_dot_survives(self):
        # THE CASE THREE COPIES GOT WRONG. abspath() returns C:\tmp\TALK -- a name that does not
        # exist -- for C:\tmp\TALK., a name that does.
        self.assertEqual(common.long_path("C:\\tmp\\TALK."), "\\\\?\\C:\\tmp\\TALK.")

    @on_windows
    def test_trailing_space_survives(self):
        self.assertEqual(common.long_path("C:\\a\\b "), "\\\\?\\C:\\a\\b ")

    @on_windows
    def test_a_name_of_only_dots_survives(self):
        self.assertEqual(common.long_path("C:\\tmp\\..."), "\\\\?\\C:\\tmp\\...")

    @on_windows
    def test_forward_slashes_become_backslashes(self):
        self.assertEqual(common.long_path("C:/a/b"), "\\\\?\\C:\\a\\b")

    @on_windows
    def test_already_prefixed_is_unchanged(self):
        self.assertEqual(common.long_path("\\\\?\\C:\\a"), "\\\\?\\C:\\a")

    @on_windows
    def test_idempotent(self):
        once = common.long_path("C:\\a\\b.")
        self.assertEqual(common.long_path(once), once)

    @on_windows
    def test_relative_becomes_absolute_at_the_working_directory(self):
        self.assertEqual(common.long_path("some\\rel.txt"),
                         "\\\\?\\" + os.path.join(os.getcwd(), "some\\rel.txt"))

    @on_windows
    def test_mirror_py_uses_this_one(self):
        """mirror.py must resolve long_path to THIS function, not to a copy of its own.

        It kept a copy until 2026-09-22, because fourteen tools loaded it by path and one --
        wedge_test.py -- runs it in a fresh `python -c` subprocess, where sys.path[0] is the
        working directory rather than the script's. That one template now names the directory
        itself, which is what made the import safe.

        Loaded through load_peer(), which is what those tools use: if the import were to break
        for them it breaks here, and this says so instead of the crawler saying it at 03:00.
        """
        module = common.load_mirror()
        # The same object, not merely one that agrees today.
        self.assertIs(module.long_path, common.long_path)
        self.assertIs(module.human, common.human)
        # And it still decides the way the 21 dotted names in these mirrors need it to.
        for case in ("x/y.txt", "C:\\tmp\\TALK.", "C:\\a b\\c", "\\\\?\\C:\\p",
                     "rel with space/f.", "C:/forward/x", "trailing space ", ""):
            self.assertEqual(module.long_path(case), common.long_path(case), case)


class TestPathsOnDisk(unittest.TestCase):
    """exists/isfile answer about the filesystem, not about a string."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.file = os.path.join(self.tmp, "plain.txt")
        with open(self.file, "wb") as fh:
            fh.write(b"x")
        self.dir = os.path.join(self.tmp, "adir")
        os.makedirs(self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_file_is_there(self):
        self.assertTrue(common.exists(self.file))
        self.assertTrue(common.isfile(self.file))

    def test_a_directory_exists_but_is_not_a_file(self):
        self.assertTrue(common.exists(self.dir))
        self.assertFalse(common.isfile(self.dir))

    def test_absent(self):
        self.assertFalse(common.exists(os.path.join(self.tmp, "nope")))

    def test_a_relative_path_resolves(self):
        # THE COPY THIS REPLACES asked os.path.exists("\\\\?\\" + relative), which never matches.
        here = os.getcwd()
        try:
            os.chdir(self.tmp)
            self.assertTrue(common.exists("plain.txt"))
            self.assertFalse(common.exists("nope.txt"))
        finally:
            os.chdir(here)

    @on_windows
    def test_a_name_ending_in_a_dot_is_found(self):
        dotted = os.path.join(self.tmp, "TALK.")
        try:
            with open(common.long_path(dotted), "wb") as fh:
                fh.write(b"y")
        except OSError as exc:
            self.skipTest("this volume will not take a dotted name: %s"
                          % exc.__class__.__name__)
        self.assertTrue(common.exists(dotted))
        # and the plain call alone would miss it, which is the whole point
        self.assertFalse(os.path.exists(dotted))


class TestRelativeTo(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(common.relative_to("/a/b", "/a/b/c/d.txt"), "c/d.txt")

    def test_trailing_separator_on_the_root(self):
        self.assertEqual(common.relative_to("/a/b/", "/a/b/c.txt"), "c.txt")

    def test_outside_returns_none(self):
        self.assertIsNone(common.relative_to("/a/b", "/a/other/c.txt"))

    def test_keeps_a_trailing_dot(self):
        # os.path.relpath would normalise this away.
        self.assertEqual(common.relative_to("/a", "/a/TALK."), "TALK.")

    @on_windows
    def test_backslashes_become_forward(self):
        self.assertEqual(common.relative_to("C:\\a", "C:\\a\\b\\c.txt"), "b/c.txt")

    @on_windows
    def test_case_insensitive_on_windows(self):
        self.assertEqual(common.relative_to("C:\\A", "c:\\a\\b.txt"), "b.txt")

    @on_windows
    def test_A_LONG_PATH_AND_A_PLAIN_ROOT_ARE_THE_SAME_PATH(self):
        r"""The trap, and it is not hypothetical: it cost a whole measurement.

        os.walk(long_path(root)) yields long paths. A caller then passes the PLAIN root here,
        the two spellings do not match by prefix, and EVERY file comes back None -- with no
        error, so absolute paths end up in a column labelled "relative". On 2026-09-24 that made
        a run report 0 of 26 280 rows matching a set of exception rules that were all correct.
        """
        self.assertEqual(common.relative_to("R:\\tree", "\\\\?\\R:\\tree\\a\\b.txt"),
                         "a/b.txt")
        self.assertEqual(common.relative_to("\\\\?\\R:\\tree", "R:\\tree\\a\\b.txt"),
                         "a/b.txt")

    @on_windows
    def test_and_both_long_still_works(self):
        self.assertEqual(common.relative_to(common.long_path("R:\\tree"),
                                            common.long_path("R:\\tree\\a\\b.txt")), "a/b.txt")

    @on_windows
    def test_AND_STRIPPING_THE_PREFIX_DOES_NOT_MAKE_EVERYTHING_MATCH(self):
        # The None answer still has to mean something. A path genuinely outside the root stays
        # outside it whichever way either side is spelt.
        self.assertIsNone(common.relative_to("R:\\tree", "\\\\?\\R:\\elsewhere\\b.txt"))
        self.assertIsNone(common.relative_to("\\\\?\\R:\\tree", "R:\\elsewhere\\b.txt"))

    @on_windows
    def test_and_a_trailing_dot_survives_the_long_form_too(self):
        # The whole reason long_path exists is that normalising strips it. Taking the prefix off
        # must not quietly reintroduce a normalisation.
        self.assertEqual(common.relative_to("Q:\\a", "\\\\?\\Q:\\a\\TALK."), "TALK.")


class TestHashing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, data):
        p = os.path.join(self.tmp, name)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    def test_empty_file(self):
        self.assertEqual(
            common.sha256_file(self.write("empty", b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_known_vector(self):
        self.assertEqual(
            common.sha256_file(self.write("abc", b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_bytes_and_file_agree(self):
        data = b"a" * 100000
        p = self.write("big", data)
        self.assertEqual(common.sha256_file(p), common.sha256_bytes(data))

    def test_chunk_size_does_not_change_the_answer(self):
        p = self.write("big", b"a" * 100000)
        self.assertEqual(common.sha256_file(p, chunk=7), common.sha256_file(p))

    def test_missing_file_raises(self):
        # Silence here would be the dangerous answer: a digest that is None reads as "unchanged"
        # in half the callers.
        with self.assertRaises(OSError):
            common.sha256_file(os.path.join(self.tmp, "nope"))


class TestHuman(unittest.TestCase):
    """Decimal, because every document in this collection is decimal."""

    def test_zero(self):
        self.assertEqual(common.human(0), "0 B")

    def test_below_a_kilobyte(self):
        self.assertEqual(common.human(999), "999 B")

    def test_a_kilobyte_is_a_thousand(self):
        self.assertEqual(common.human(1000), "1.00 kB")

    def test_1024_is_not_a_kilobyte(self):
        self.assertEqual(common.human(1024), "1.02 kB")

    def test_the_units(self):
        self.assertEqual(common.human(10 ** 6), "1.00 MB")
        self.assertEqual(common.human(10 ** 9), "1.00 GB")
        self.assertEqual(common.human(10 ** 12), "1.00 TB")

    def test_real_figures_from_this_collection(self):
        self.assertEqual(common.human(149225768625), "149.23 GB")
        self.assertEqual(common.human(3976500000000), "3.98 TB")

    def test_a_difference_can_be_negative(self):
        self.assertEqual(common.human(-10 ** 9), "-1.00 GB")

    def test_it_does_not_invent_a_unit_beyond_terabytes(self):
        self.assertEqual(common.human(5 * 10 ** 15), "5000.00 TB")


class TestParseSize(unittest.TestCase):
    """Reads what a LISTING wrote, which is binary. The opposite direction from human()."""

    def test_plain_digits(self):
        self.assertEqual(common.parse_size("919216"), 919216)

    def test_apache_style_binary(self):
        # The case that bit: 1.6M in a listing is 1 677 721 bytes, and comparing that against an
        # exact 1 657 522 produced a "difference" that did not exist.
        self.assertEqual(common.parse_size("1.6M"), int(1.6 * 1024 ** 2))
        self.assertEqual(common.parse_size("604M"), 604 * 1024 ** 2)
        self.assertEqual(common.parse_size("4.0K"), int(4.0 * 1024))

    def test_with_a_b_and_spaces(self):
        self.assertEqual(common.parse_size(" 12 KB "), 12 * 1024)

    def test_a_dash_is_a_directory_not_a_size(self):
        self.assertIsNone(common.parse_size("-"))

    def test_empty_and_none(self):
        self.assertIsNone(common.parse_size(""))
        self.assertIsNone(common.parse_size("   "))
        self.assertIsNone(common.parse_size(None))

    def test_nonsense_is_none_not_zero(self):
        # Zero would be a size. None is "there was no size here", and the two lead to different
        # decisions in every caller.
        self.assertIsNone(common.parse_size("version 1.71"))
        self.assertIsNone(common.parse_size("n/a"))

    def test_THE_RESULT_IS_ROUNDED_AND_THE_DOCSTRING_HAD_BETTER_SAY_SO(self):
        """The trap that is not the 1024 one, and that caught this project on 2026-09-24.

        `1.1M` expands to a number with seven digits, every one of which looks exact and five of
        which the server never stated. 225 files were called "not the same file" by comparing it
        with ==. The value is right; treating it as a byte count is not.
        """
        self.assertEqual(common.parse_size("1.1M"), 1153433)
        self.assertNotEqual(common.parse_size("1.1M"), common.parse_size("1.10M") + 1)
        self.assertIn("as exact as the text was", common.parse_size.__doc__.lower())


class TestSizeAgrees(unittest.TestCase):
    """Comparing a printed size with a real one, which is not `==` and was done as `==` once.

    Every number here was measured on 2026-09-24 over 912 pairs in `bullfreeware`, `aixtools`,
    `penguinppc` and `rs6000-microcode`, where a stored index.html sits beside the files it
    describes: 13.0% exact, 81.8% within half the last printed digit, 4.5% not agreeing at all.
    """

    def test_an_exact_match_is_agreement(self):
        self.assertTrue(common.size_agrees(919216, 919216))

    def test_ROUNDING_IS_AGREEMENT(self):
        # The real pair from the mirror: the page says `3.3K`, the file is 3 403 bytes.
        self.assertTrue(common.size_agrees(common.parse_size("3.3K"), 3403))
        # and `1.1M` beside a file that really is about 1.1M
        self.assertTrue(common.size_agrees(common.parse_size("1.1M"), 1120000))

    def test_AND_A_TRUNCATED_DOWNLOAD_IS_NOT(self):
        """The finding this function exists to make, in the two shapes the mirror holds.

        A file that stops far short of what the server promised is invisible to every check that
        compares the tree against its own recorded hash -- the hash of a truncated file matches
        itself perfectly.
        """
        self.assertFalse(common.size_agrees(38063308, 7488))     # mozilla-0.8.0.0.exe
        self.assertFalse(common.size_agrees(44040192, 113595))   # aixtools.php.5.3.20.0.I
        self.assertFalse(common.size_agrees(3891, 5423))         # MD5.checksums, grown since

    def test_THE_FLOOR_IS_NO_STATEMENT_NOT_A_MISMATCH(self):
        """27 intact signature files were reported as damaged before this was measured.

        penguinppc's Apache prints `1k` for every 240-byte .sig it holds. It never prints a size
        below 1k at all, so 1024 beside 240 is the column's floor and not a discrepancy.
        """
        self.assertIsNone(common.size_agrees(1024, 240))
        self.assertIsNone(common.size_agrees(common.parse_size("1k"), 162))

    def test_AND_A_SERVER_THAT_PRINTS_EXACT_BYTES_KEEPS_ITS_PRECISION(self):
        # The floor must not swallow a server that really did print 240. Only when BOTH sides are
        # under it is the answer unknown; a small listed size beside a large file still disagrees.
        self.assertTrue(common.size_agrees(240, 240))
        self.assertFalse(common.size_agrees(240, 9000))

    def test_no_size_is_none_and_none_is_not_false(self):
        # A caller hunting truncated downloads reports False and must stay silent on None.
        self.assertIsNone(common.size_agrees(None, 500))
        self.assertIsNone(common.size_agrees(500, None))
        self.assertIsNone(common.size_agrees(common.parse_size("-"), 500))

    def test_the_step_is_read_back_out_of_the_number(self):
        # The column keeps no record of its own precision, so the value has to carry it.
        self.assertEqual(common.listing_step(500), 0)              # printed in bytes, exact
        self.assertEqual(common.listing_step(3379), 1024 // 10)    # `3.3K`
        self.assertEqual(common.listing_step(449 * 1024), 1024)    # `449k`
        self.assertEqual(common.listing_step(1153433), 1024 ** 2 // 10)   # `1.1M`
        self.assertEqual(common.listing_step(296 * 1024 ** 2), 1024 ** 2)  # `296M`

    def test_AN_EXACT_MULTIPLE_MEANS_THE_COLUMN_HAD_NO_DECIMAL_PLACE(self):
        """The rule that replaced reading precision off the magnitude, and why it had to.

        `1k` and `1.0K` both expand to 1024, and the first is good only to the whole kilobyte.
        Guessing from the size instead -- "under ten units, so it had a tenth" -- turned ten
        intact files on penguinppc and bullfreeware into contradictions, among them a 1 135-byte
        ChangeLog listed as `1k`.
        """
        self.assertEqual(common.listing_step(1024), 1024)
        self.assertEqual(common.listing_step(2048), 1024)
        self.assertEqual(common.listing_step(42 * 1024 ** 2), 1024 ** 2)
        # and the real pairs that the old rule rejected
        for listed, actual in ((1024, 1135), (2048, 1729), (4096, 4301), (5120, 4948),
                               (2048, 2540)):
            self.assertTrue(common.size_agrees(listed, actual), (listed, actual))

    def test_AND_A_TENTH_STILL_BINDS_WHERE_ONE_WAS_PRINTED(self):
        # The generosity above must not leak into the decimal case: `3.8K` beside a 5 423-byte
        # file stays a contradiction, because the column could express the difference and didn't.
        self.assertEqual(common.listing_step(3891), 1024 // 10)
        self.assertFalse(common.size_agrees(3891, 5423))

    def test_and_it_is_symmetric_about_the_listed_value(self):
        # Servers disagree about rounding versus truncating, so both directions are allowed.
        step = common.listing_step(1153433)
        self.assertTrue(common.size_agrees(1153433, 1153433 + step))
        self.assertTrue(common.size_agrees(1153433, 1153433 - step))
        self.assertFalse(common.size_agrees(1153433, 1153433 + step + 1))


class TestOwnFiles(unittest.TestCase):
    """TWO sets, and the difference is load-bearing.

    Eight tools each had their own version and no two agreed. Collapsing them into one looked
    obvious and would have been wrong: the narrow set defines what a completion marker's file
    count excludes, and four markers already on disk were written against it.
    """

    def test_the_markers_are_ours(self):
        for name in (common.COMPLETE_MARKER, common.SUMS_FILE, common.INDEX_FILE,
                     common.PROVENANCE_FILE):
            self.assertTrue(common.is_own_file(name), name)

    def test_RENAMED_AND_SYMLINKS_ARE_NOT_IN_THE_COUNTED_SET(self):
        """The case that must not be tidied away.

        They are as much ours as the rest. But the extracted archives that carry them were
        counted WITH them, so widening OWN_FILES would make those markers disagree with their own
        trees -- for a reason nobody reading the diff could reconstruct.
        """
        for name in ("RENAMED.txt", "SYMLINKS.txt", "EXTRACTED-FROM.md", "CATALOGUE.md",
                     ".mirror-root"):
            self.assertFalse(common.is_own_file(name), name)
            self.assertTrue(common.is_bookkeeping_file(name), name)

    def test_the_wide_set_contains_the_narrow_one(self):
        self.assertTrue(common.OWN_FILES < common.BOOKKEEPING_FILES)

    def test_the_one_off_fetchers_manifest_is_bookkeeping(self):
        # Three tools write SHA256SUMS beside what they fetched. It is ours, but it is NOT in the
        # counted set: no marker was ever written against a definition that excluded it.
        self.assertTrue(common.is_bookkeeping_file("SHA256SUMS"))
        self.assertFalse(common.is_own_file("SHA256SUMS"))

    def test_a_suspect_is_content_not_bookkeeping(self):
        # A .suspect is a TRUNCATED DOWNLOAD -- the record of a permanent loss, not our paperwork.
        # Skipping it would delete the evidence from every count that looks for it.
        self.assertFalse(common.is_own_file("x.tar.gz.suspect"))
        self.assertFalse(common.is_bookkeeping_file("x.tar.gz.suspect"))

    def test_content_is_neither(self):
        for name in ("readme.txt", "index.html", "PROVENANCE.md.bak", "provenance.md",
                     "Catalog_#24.pdf", ".sha256sums"):
            self.assertFalse(common.is_own_file(name), name)
            self.assertFalse(common.is_bookkeeping_file(name), name)

    def test_it_is_exact_not_a_pattern(self):
        # A pattern here would eventually claim a source file.
        for name in ("my.mirror-complete", ".mirror-complete.old", "xPROVENANCE.md"):
            self.assertFalse(common.is_own_file(name), name)
            self.assertFalse(common.is_bookkeeping_file(name), name)

    def test_both_sets_are_immutable(self):
        self.assertIsInstance(common.OWN_FILES, frozenset)
        self.assertIsInstance(common.BOOKKEEPING_FILES, frozenset)


class TestSafeName(unittest.TestCase):
    def test_an_ordinary_name_is_untouched(self):
        self.assertEqual(common.safe_name("readme.txt"), "readme.txt")

    def test_forbidden_characters_go(self):
        self.assertEqual(common.safe_name('a<b>c:d"e|f?g*h'), "a_b_c_d_e_f_g_h")

    def test_control_characters_go(self):
        self.assertEqual(common.safe_name("a\x01b"), "a_b")

    def test_THE_FORWARD_SLASH_IS_NOT_THIS_FUNCTIONS_BUSINESS(self):
        # Every caller splits on it before calling; substituting it would turn a path into a name.
        self.assertEqual(common.safe_name("a/b"), "a/b")

    def test_BUT_THE_BACKSLASH_IS_NOW_REPLACED_AND_THIS_REVERSES_AN_EARLIER_DECISION(self):
        r"""It used to be left alone here, deliberately. [reversed 2026-09-23]

        The reason recorded then was: "widening UNSAFE would repath every existing mirror to fix
        a case the HTTP crawler has never produced." Both halves were checked on 2026-09-23 and
        both turned out to be false.

        REPATHS NOTHING. Not one path in the 98 archive indexes contains a backslash, so there is
        no stored file whose location this moves.

        AND THE CRAWLER CAN PRODUCE IT. local_path() unquotes before splitting, so `%5C` arrives
        as a real separator inside a segment. `http://h/..%5C..%5Cetc%5Cx` mapped to
        `root\..\..\etc\x` -- `..\etc\x` after normalising, which is outside root. The `..` guard
        drops `..` only as a whole segment and never saw it.

        The earlier decision was sound on the evidence it had. This one has more.
        """
        self.assertEqual(common.safe_name("a\\b"), "a_b")
        self.assertEqual(common.safe_name("..\\..\\x"), ".._.._x")

    def test_a_trailing_dot_is_left_alone(self):
        # That is long_path's problem, and solving it here would rename a real file.
        self.assertEqual(common.safe_name("TALK."), "TALK.")

    def test_a_hash_is_an_ordinary_character(self):
        # 1 090 files in these mirrors have one in their real name.
        self.assertEqual(common.safe_name("Catalog_#24.pdf"), "Catalog_#24.pdf")


class TestIterFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        os.makedirs(os.path.join(self.tmp, "sub", "deeper"))
        for rel in ("a.txt", "PROVENANCE.md", ".sha256sum",
                    os.path.join("sub", "b.txt"),
                    os.path.join("sub", "PROVENANCE.md"),
                    os.path.join("sub", "deeper", "c.txt")):
            with open(os.path.join(self.tmp, rel), "wb") as fh:
                fh.write(b"x")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rels(self, **kw):
        return [rel for rel, _full in common.iter_files(self.tmp, **kw)]

    def test_skips_our_own_files_at_the_top(self):
        self.assertNotIn("PROVENANCE.md", self.rels())
        self.assertNotIn(".sha256sum", self.rels())

    def test_keeps_a_source_file_of_the_same_name_deeper_down(self):
        # A source archive may well contain its own PROVENANCE.md, and that one is content.
        self.assertIn("sub/PROVENANCE.md", self.rels())

    def test_finds_everything_else(self):
        self.assertEqual(sorted(self.rels()),
                         ["a.txt", "sub/PROVENANCE.md", "sub/b.txt", "sub/deeper/c.txt"])

    def test_the_set_can_be_emptied_to_walk_everything(self):
        self.assertIn("PROVENANCE.md", self.rels(own_files=frozenset()))

    def test_paths_use_forward_slashes(self):
        for rel in self.rels():
            self.assertNotIn("\\", rel)

    def test_the_full_path_opens(self):
        for _rel, full in common.iter_files(self.tmp):
            with open(common.long_path(full), "rb") as fh:
                self.assertEqual(fh.read(), b"x")

    def test_ORDER_IS_STABLE_AND_THIS_IS_IT(self):
        """`assertEqual(self.rels(), self.rels())` stood here alone, and it cannot fail.

        Two calls agreeing says only that nothing is random; it permits ANY order, so a change
        that reshuffled the walk would pass. The sibling test on find_manifests pins the order
        as well, and this one now does the same -- every other test of iter_files sorts the
        result first, so without this line nothing in the file describes what it emits.

        A caller diffing two reports depends on this: shallow before deep, sorted within a
        directory.
        """
        self.assertEqual(self.rels(), self.rels())
        self.assertEqual(self.rels(),
                         ["a.txt", "sub/PROVENANCE.md", "sub/b.txt", "sub/deeper/c.txt"])

class TestStripFragment(unittest.TestCase):
    """A fragment names a position INSIDE a document, never a document."""

    def test_an_anchor_goes(self):
        self.assertEqual(common.strip_fragment("page.html#A9D8FFBD257ryan"), "page.html")

    def test_numbered_anchors_on_one_page(self):
        # A page whose sections are anchors becomes one file per section, all identical.
        for i in range(1, 9):
            self.assertEqual(common.strip_fragment("toc.html#%d" % i), "toc.html")

    def test_a_href_without_one_is_unchanged(self):
        self.assertEqual(common.strip_fragment("page.html"), "page.html")

    def test_only_the_first_hash_splits(self):
        self.assertEqual(common.strip_fragment("a.html#b#c"), "a.html")

    def test_a_bare_fragment_becomes_empty(self):
        # `#top` names nothing outside the current page; the caller drops the empty result.
        self.assertEqual(common.strip_fragment("#top"), "")


class TestStripCacheBuster(unittest.TestCase):
    """FOR <img src> ONLY, and the extension test is the whole safety margin."""

    def test_a_cache_buster_on_an_image(self):
        # Without this the picture is dropped: is_child_link refuses every href with a query.
        self.assertEqual(common.strip_cache_buster("Lacuna.gif?v=3"), "Lacuna.gif")

    def test_an_uppercase_extension_counts(self):
        self.assertEqual(common.strip_cache_buster("a/b/Planar_Late.PNG?x=1"),
                         "a/b/Planar_Late.PNG")

    def test_a_buster_without_a_key(self):
        self.assertEqual(common.strip_cache_buster("shot.jpeg?1699"), "shot.jpeg")

    def test_no_query_is_untouched(self):
        self.assertEqual(common.strip_cache_buster("Lacuna.gif"), "Lacuna.gif")

    def test_a_query_that_SELECTS_is_left_alone(self):
        # Stripping here would fetch one wrong file and call it every image on the page.
        self.assertEqual(common.strip_cache_buster("img.php?id=5"), "img.php?id=5")
        self.assertEqual(common.strip_cache_buster("thumb.cgi?f=x"), "thumb.cgi?f=x")

    def test_a_non_image_keeps_its_query(self):
        self.assertEqual(common.strip_cache_buster("style.css?v=2"), "style.css?v=2")
        self.assertEqual(common.strip_cache_buster("index.html?p=2"), "index.html?p=2")

    def test_every_listed_extension_is_honoured(self):
        for ext in common.STATIC_IMAGE:
            self.assertEqual(common.strip_cache_buster("x" + ext + "?v=1"), "x" + ext, ext)


class TestIsChildLink(unittest.TestCase):
    """The weaker of two guards. Every attempt to make it stricter has cost more than it saved."""

    def test_an_ordinary_relative_link(self):
        self.assertTrue(common.is_child_link("file.pdf"))
        self.assertTrue(common.is_child_link("sub/"))

    def test_empty_and_anchors_and_queries(self):
        self.assertFalse(common.is_child_link(""))
        self.assertFalse(common.is_child_link("#top"))
        self.assertFalse(common.is_child_link("?C=N;O=D"))

    def test_a_sort_link_anywhere_in_the_href(self):
        # Following these re-fetches the same listing once per column and direction.
        self.assertFalse(common.is_child_link("dir/?C=M;O=A"))

    def test_THE_COLON_IS_THE_WHOLE_DISTINCTION(self):
        """Every rejected scheme is a prefix of a perfectly ordinary filename."""
        real_names = [
            ("datasheets/CK_E020.pdf", "a real directory name beginning with the data: scheme"),
            ("datasheets/", "the same, as a directory"),
            ("telnet-howto.html", "begins with 'tel'"),
            ("about.html", "begins with 'about'"),
            ("filesystem-howto.html", "begins with 'file'"),
            ("files/", "a directory called files"),
            ("mailtool.txt", "begins with 'mail'"),
            ("javascript-guide.html", "begins with 'javascript'"),
            ("database/", "begins with 'data'"),
        ]
        for href, why in real_names:
            self.assertTrue(common.is_child_link(href), "%s -- %s" % (href, why))

        schemes = ["data:image/gif;base64,R0lGOD", "tel:+49301234", "mailto:x@example.invalid",
                   "about:blank", "javascript:void(0)",
                   "file:/PitStop/packages/gifs/bolt.gif", "FILE:/x.gif", "MailTo:x@example.invalid"]
        for href in schemes:
            self.assertFalse(common.is_child_link(href), href)

    def test_an_absolute_path_is_allowed_through(self):
        # A hand-written page may address its whole tree from the root. Refusing these finds
        # a handful of files on a site holding tens of thousands.
        self.assertTrue(common.is_child_link("/hardware/"))
        self.assertTrue(common.is_child_link("/archives/software/a.file"))

    def test_protocol_relative_is_refused_either_way(self):
        # urljoin would keep OUR scheme and produce a plausible-looking off-site URL.
        self.assertFalse(common.is_child_link("//cdn.example.com/x.gif"))
        self.assertFalse(common.is_child_link("//cdn.example.com/x.gif", allow_up=True))

    def test_upward_needs_allow_up(self):
        # Hand-written HTML navigates up two levels and down into a sibling, resolving well
        # INSIDE the base. Dropping that loses most of a tree and reports a clean completion.
        self.assertFalse(common.is_child_link("../../sibling/deeper/toc.html"))
        self.assertTrue(common.is_child_link("../../sibling/deeper/toc.html", allow_up=True))

    def test_a_qualified_url_needs_allow_up(self):
        # A page may link its own files with the host spelled out. Treating those as off-site
        # leaves only whatever happened to be written as a bare path.
        u = "https://h.example/pub/A_Long_Document_Name.pdf"
        self.assertFalse(common.is_child_link(u))
        self.assertTrue(common.is_child_link(u, allow_up=True))

    def test_a_query_is_refused_even_with_allow_up(self):
        self.assertFalse(common.is_child_link("page.html?x=1", allow_up=True))


class TestSamePathPlusSlash(unittest.TestCase):
    """The scheme has to be ignored: a server may answer an https request with an http Location."""

    BASE = "https://h.example/pub/x/install-guide.html"

    def test_a_downgraded_scheme(self):
        self.assertTrue(common.same_path_plus_slash(
            self.BASE, "http://h.example/pub/x/install-guide.html/"))

    def test_the_same_scheme(self):
        self.assertTrue(common.same_path_plus_slash(
            self.BASE, "https://h.example/pub/x/install-guide.html/"))

    def test_no_redirect_at_all(self):
        self.assertFalse(common.same_path_plus_slash(self.BASE, self.BASE))

    def test_a_different_path(self):
        self.assertFalse(common.same_path_plus_slash(
            self.BASE, "https://h.example/pub/y/install-guide.html/"))

    def test_A_DIFFERENT_HOST_IS_NONE_OF_ITS_BUSINESS(self):
        self.assertFalse(common.same_path_plus_slash(
            self.BASE, "https://evil.example/pub/x/install-guide.html/"))

    def test_a_different_name(self):
        self.assertFalse(common.same_path_plus_slash(
            self.BASE, "https://h.example/pub/x/install-guide.html.gz/"))

    def test_the_slash_is_required(self):
        self.assertFalse(common.same_path_plus_slash(
            self.BASE, "http://h.example/pub/x/install-guide.html"))


class TestLooksLikeALoop(unittest.TestCase):
    """`seen` cannot help: the crawler is not going in circles, it is walking forward forever."""

    BASE = "http://h/pub/tools/"

    def test_a_link_pointing_at_its_own_parent(self):
        why = common.looks_like_a_loop(self.BASE + "xemacs/xemacs/xemacs/", self.BASE)
        self.assertIsNotNone(why)
        self.assertIn("xemacs", why)

    def test_two_in_a_row_is_allowed(self):
        # doc/doc/ and bin/bin/ do occur.
        self.assertIsNone(common.looks_like_a_loop(self.BASE + "doc/doc/", self.BASE))
        self.assertIsNone(common.looks_like_a_loop(self.BASE + "a/bin/bin/b/", self.BASE))

    def test_three_in_a_row_is_refused(self):
        self.assertIsNotNone(common.looks_like_a_loop(self.BASE + "a/b/b/b/", self.BASE))

    def test_it_fires_early(self):
        # At depth 3, not at the cap -- so almost nothing is fetched before the loop is seen.
        self.assertIsNotNone(common.looks_like_a_loop(self.BASE + "x/x/x/", self.BASE))

    def test_a_repeat_that_is_not_consecutive_is_fine(self):
        self.assertIsNone(common.looks_like_a_loop(self.BASE + "a/b/a/b/", self.BASE))

    def test_the_depth_cap_is_the_backstop(self):
        # For cycles the repeat rule does not describe: alternating names, or a chain that closes.
        deep = self.BASE + "/".join("d%d" % i for i in range(common.MAX_DEPTH_BELOW_BASE + 1))
        self.assertIsNotNone(common.looks_like_a_loop(deep, self.BASE))

    def test_exactly_at_the_cap_is_allowed(self):
        # Real trees nest hard; the cap is a refusal of last resort, not a policy about depth.
        ok = self.BASE + "/".join("d%d" % i for i in range(common.MAX_DEPTH_BELOW_BASE))
        self.assertIsNone(common.looks_like_a_loop(ok, self.BASE))

    def test_the_base_itself_is_not_a_loop(self):
        self.assertIsNone(common.looks_like_a_loop(self.BASE, self.BASE))

    def test_a_url_outside_the_base_is_not_its_business(self):
        self.assertIsNone(common.looks_like_a_loop("http://other/x/x/x/", self.BASE))

    def test_the_reason_is_readable(self):
        # Both refusals are logged, so the text has to say which rule fired and why.
        repeat = common.looks_like_a_loop(self.BASE + "x/x/x/", self.BASE)
        depth = common.looks_like_a_loop(
            self.BASE + "/".join("d%d" % i for i in range(30)), self.BASE)
        self.assertIn("repeats", repeat)
        self.assertIn("own parent", repeat)
        self.assertIn("segments below the base", depth)
        self.assertIn(str(common.MAX_DEPTH_BELOW_BASE), depth)


class TestLocalPath(unittest.TestCase):
    BASE = "http://h/pub/"

    def test_one_segment_per_directory(self):
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "a/b/c.txt"),
                         os.path.join("R", "a", "b", "c.txt"))

    def test_the_url_is_unquoted(self):
        # The local name is what the source calls the file, not what HTTP needed to say it.
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "RT%20Series/a.txt"),
                         os.path.join("R", "RT Series", "a.txt"))

    def test_dot_and_dotdot_segments_are_dropped(self):
        # `..` is the one that would escape the root.
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "a/../../b.txt"),
                         os.path.join("R", "a", "b.txt"))
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "a/./b.txt"),
                         os.path.join("R", "a", "b.txt"))

    def test_empty_segments_are_dropped(self):
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "a//b.txt"),
                         os.path.join("R", "a", "b.txt"))

    def test_characters_windows_forbids_are_replaced_per_segment(self):
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "a%3Ab/c%7Cd.txt"),
                         os.path.join("R", "a_b", "c_d.txt"))

    def test_a_trailing_dot_survives(self):
        # long_path exists to reach such a name; renaming it here would defeat that.
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "TALK."),
                         os.path.join("R", "TALK."))

    def test_a_hash_in_a_real_name_survives(self):
        self.assertEqual(common.local_path("R", self.BASE, self.BASE + "Catalog_%2324.pdf"),
                         os.path.join("R", "Catalog_#24.pdf"))
class TestPlural(unittest.TestCase):
    def test_one(self):
        self.assertEqual(common.plural(1, "file"), "1 file")

    def test_none_and_many(self):
        self.assertEqual(common.plural(0, "file"), "0 files")
        self.assertEqual(common.plural(2, "file"), "2 files")

    def test_an_irregular_suffix_is_the_callers_business(self):
        self.assertEqual(common.plural(2, "entr", "ies"), "2 entries")
        self.assertEqual(common.plural(1, "entr", "ies"), "1 entr")


class TestReadManifest(unittest.TestCase):
    """Two formats, one reader. The sums format has a trap with a measured cost."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return p

    H = "a" * 64
    G = "b" * 64

    def test_sums_binary_form_one_space_and_a_star(self):
        # THE TRAP: splitting this on whitespace leaves every path starting with '*', so nothing
        # matches anything. One reader that did reported "0 of 7 890 held" for a tree of 7 871.
        p = self.write(".sha256sum", "%s *dir/file.txt\n" % self.H)
        self.assertEqual(common.read_manifest(p), [("dir/file.txt", None, self.H)])

    def test_sums_text_form_two_spaces(self):
        p = self.write(".sha256sum", "%s  dir/file.txt\n" % self.H)
        self.assertEqual(common.read_manifest(p), [("dir/file.txt", None, self.H)])

    def test_a_path_with_spaces_survives(self):
        p = self.write(".sha256sum", "%s *RT Series/MGA MILL/a b.txt\n" % self.H)
        self.assertEqual(common.read_manifest(p)[0][0], "RT Series/MGA MILL/a b.txt")

    def test_a_hash_is_lowercased(self):
        p = self.write(".sha256sum", "%s *x\n" % ("A" * 64))
        self.assertEqual(common.read_manifest(p)[0][2], "a" * 64)

    def test_a_short_or_malformed_line_is_skipped_not_guessed(self):
        p = self.write(".sha256sum", "not a manifest line\n%s *ok.txt\n\n" % self.H)
        self.assertEqual(common.read_manifest(p), [("ok.txt", None, self.H)])

    def test_several_lines_keep_their_order(self):
        p = self.write(".sha256sum", "%s *a\n%s *b\n" % (self.H, self.G))
        self.assertEqual([r[0] for r in common.read_manifest(p)], ["a", "b"])

    def test_the_csv_index(self):
        p = self.write("x.csv", "path,size,mtime,sha256\ndir/f.txt,123,0,%s\n" % self.H)
        self.assertEqual(common.read_manifest(p), [("dir/f.txt", 123, self.H)])

    def test_a_size_that_will_not_parse_is_None_NOT_zero(self):
        # Zero is a size -- an empty file is a real thing here. None is "unmeasured", and the two
        # lead to different decisions in every caller.
        p = self.write("x.csv", "path,size,sha256\na,,%s\nb,nonsense,%s\n" % (self.H, self.H))
        self.assertEqual([r[1] for r in common.read_manifest(p)], [None, None])

    def test_an_empty_file_keeps_its_zero(self):
        p = self.write("x.csv", "path,size,sha256\na,0,%s\n" % self.H)
        self.assertEqual(common.read_manifest(p)[0][1], 0)

    def test_a_missing_sha_column_is_empty_not_None(self):
        p = self.write("x.csv", "path,size\na,5\n")
        self.assertEqual(common.read_manifest(p), [("a", 5, "")])


class _FakeResponse(object):
    """Just enough of an http.client.HTTPResponse for http_get, head_size and http_try."""

    def __init__(self, body=b"", headers=None, status=200):
        self.body = body
        self.headers = headers or {}
        self.status = status

    def read(self, limit=None):
        # The optional limit is http_try's; older callers pass nothing and get the whole body.
        return self.body[:limit] if limit else self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestHttp(unittest.TestCase):
    """The request this collection sends, checked without sending one.

    A helper that can only be exercised against a live host is a helper nobody exercises -- and
    against somebody's private server, exercising it is not free.
    """

    def setUp(self):
        self.seen = []

    def opener(self, body=b"hello", headers=None):
        def call(req, **kw):
            self.seen.append((req, kw))
            return _FakeResponse(body, headers or {"Content-Type": "text/plain"})
        return call

    def test_it_returns_body_and_headers(self):
        body, headers = common.http_get("http://h/x", opener=self.opener())
        self.assertEqual(body, b"hello")
        self.assertEqual(headers["Content-Type"], "text/plain")

    def test_the_identity_is_carried_without_being_asked_for(self):
        common.http_get("http://h/x", opener=self.opener())
        req, _kw = self.seen[0]
        self.assertEqual(req.get_header("User-agent"), common.user_agent())

    def test_extra_headers_arrive(self):
        common.http_get("http://h/x", extra_headers={"Range": "bytes=5-"},
                        opener=self.opener())
        req, _kw = self.seen[0]
        self.assertEqual(req.get_header("Range"), "bytes=5-")
        self.assertEqual(req.get_header("User-agent"), common.user_agent())

    def test_the_timeout_is_passed_through(self):
        common.http_get("http://h/x", timeout=7, opener=self.opener())
        self.assertEqual(self.seen[0][1]["timeout"], 7)

    def test_no_context_means_the_keyword_is_not_sent(self):
        # urlopen's default context is not the same object as None, and passing context=None
        # explicitly is not the same call.
        common.http_get("http://h/x", opener=self.opener())
        self.assertNotIn("context", self.seen[0][1])

    def test_a_context_is_passed_through(self):
        ctx = common.unverified_context()
        common.http_get("https://h/x", context=ctx, opener=self.opener())
        self.assertIs(self.seen[0][1]["context"], ctx)

    def test_head_size_reads_content_length(self):
        n = common.head_size("http://h/x", opener=self.opener(headers={"Content-Length": "4096"}))
        self.assertEqual(n, 4096)

    def test_head_size_uses_the_HEAD_method(self):
        common.head_size("http://h/x", opener=self.opener(headers={"Content-Length": "1"}))
        self.assertEqual(self.seen[0][0].get_method(), "HEAD")

    def test_head_size_says_zero_when_the_server_does_not_state_one(self):
        # And zero MUST NOT be read as "empty" by a caller. That is what the docstring is for.
        self.assertEqual(common.head_size("http://h/x", opener=self.opener(headers={})), 0)


class TestUnverifiedContext(unittest.TestCase):
    def test_it_really_does_not_verify(self):
        import ssl
        ctx = common.unverified_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)
        self.assertFalse(ctx.check_hostname)

    def test_each_call_returns_its_own(self):
        # A shared context that a caller reconfigures would silently change every other caller's.
        self.assertIsNot(common.unverified_context(), common.unverified_context())
class TestLoadPeer(unittest.TestCase):
    """Eighteen files each carried this dance. Several got it subtly wrong."""

    def test_it_loads_mirror(self):
        m = common.load_mirror()
        self.assertTrue(hasattr(m, "ARCHIVES"))
        self.assertGreater(len(m.ARCHIVES), 0)

    def test_it_restores_argv(self):
        before = list(sys.argv)
        common.load_mirror()
        self.assertEqual(sys.argv, before)

    def test_it_restores_argv_even_when_the_peer_raises(self):
        # One copy of this had no finally. A module that raises would then leave the caller
        # holding a fabricated argv for the rest of the run.
        tmp = tempfile.mkdtemp(prefix="common-test-")
        try:
            with open(os.path.join(tmp, "boom.py"), "w", encoding="utf-8") as fh:
                fh.write("raise RuntimeError('by design')\n")
            before = list(sys.argv)
            with self.assertRaises(RuntimeError):
                common.load_peer("boom.py", directory=tmp)
            self.assertEqual(sys.argv, before)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_peer_sees_its_own_name_not_the_callers(self):
        tmp = tempfile.mkdtemp(prefix="common-test-")
        try:
            with open(os.path.join(tmp, "peek.py"), "w", encoding="utf-8") as fh:
                fh.write("import sys\nSEEN = list(sys.argv)\n")
            saved, sys.argv = sys.argv, ["caller.py", "--dangerous"]
            try:
                mod = common.load_peer("peek.py", directory=tmp)
            finally:
                sys.argv = saved
            self.assertEqual(mod.SEEN, ["peek.py"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_peer_raises_rather_than_returning_none(self):
        # A None here becomes an AttributeError three frames away, naming the wrong thing.
        with self.assertRaises(IOError):
            common.load_peer("no-such-file.py")

    def test_a_hyphenated_name_works(self):
        # The reason this exists at all: such a name cannot be imported.
        tmp = tempfile.mkdtemp(prefix="common-test-")
        try:
            with open(os.path.join(tmp, "a-b.py"), "w", encoding="utf-8") as fh:
                fh.write("VALUE = 42\n")
            self.assertEqual(common.load_peer("a-b.py", directory=tmp).VALUE, 42)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestIsTransport(unittest.TestCase):
    """An answer about the resource, or an answer about us? The two are recorded differently."""

    def http(self, code):
        import urllib.error
        return urllib.error.HTTPError("http://h/x", code, "msg", {}, None)

    def test_a_404_is_an_ANSWER(self):
        # The server says it has no such thing. That belongs in the record.
        self.assertFalse(common.is_transport(self.http(404)))

    def test_403_and_410_are_answers_too(self):
        self.assertFalse(common.is_transport(self.http(403)))
        self.assertFalse(common.is_transport(self.http(410)))

    def test_a_rate_limit_is_about_US(self):
        # Arrives through the same exception type as the 404 and means the opposite.
        self.assertTrue(common.is_transport(self.http(429)))
        self.assertTrue(common.is_transport(self.http(503)))

    def test_the_whole_retry_set(self):
        for code in common.RETRY_STATUS:
            self.assertTrue(common.is_transport(self.http(code)), code)

    def test_a_socket_error_is_not_an_answer_at_all(self):
        import urllib.error
        for exc in (urllib.error.URLError("refused"), TimeoutError(),
                    ConnectionResetError(), OSError(104, "reset")):
            self.assertTrue(common.is_transport(exc), type(exc).__name__)

    def test_something_else_entirely_is_not_transport(self):
        self.assertFalse(common.is_transport(ValueError("bad data")))


class TestHostOf(unittest.TestCase):
    """Three spellings of one site, and an index built over years holds all three."""

    def test_the_three_spellings_fold_together(self):
        for u in ("http://www.example.com/x", "http://example.com/x",
                  "http://example.com:80/x", "https://WWW.EXAMPLE.COM/x"):
            self.assertEqual(common.host_of(u), "example.com", u)

    def test_credentials_are_dropped(self):
        self.assertEqual(common.host_of("http://user:pw@example.com/x"), "example.com")

    def test_a_host_merely_starting_with_www_is_not_stripped(self):
        self.assertEqual(common.host_of("http://wwwtest.example.com/"), "wwwtest.example.com")

    def test_no_host_is_empty(self):
        self.assertEqual(common.host_of("/relative/path"), "")


class TestHttpDate(unittest.TestCase):
    def test_rfc_1123(self):
        self.assertAlmostEqual(common.http_date("Sun, 06 Nov 1994 08:49:37 GMT"),
                               784111777.0, places=0)

    def test_unreadable_is_None_not_now(self):
        # A wrong mtime is indistinguishable from a right one afterwards.
        for bad in ("", None, "yesterday", "0", "Sun, 99 Xxx 1994 08:49:37 GMT"):
            self.assertIsNone(common.http_date(bad), repr(bad))


class TestAtomicWrite(unittest.TestCase):
    """A half-written file that looks complete is inherited, indexed and hashed as real."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_writes(self):
        p = os.path.join(self.tmp, "a.txt")
        common.atomic_write(p, b"hello")
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"hello")

    def test_it_creates_the_parent(self):
        p = os.path.join(self.tmp, "deep", "er", "a.txt")
        common.atomic_write(p, b"x")
        self.assertTrue(os.path.isfile(p))

    def test_no_part_file_is_left_behind(self):
        common.atomic_write(os.path.join(self.tmp, "a.txt"), b"x")
        self.assertEqual(sorted(os.listdir(self.tmp)), ["a.txt"])

    def test_it_replaces_an_existing_file(self):
        p = os.path.join(self.tmp, "a.txt")
        common.atomic_write(p, b"old")
        common.atomic_write(p, b"new")
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"new")

    def test_an_http_date_becomes_the_mtime(self):
        p = os.path.join(self.tmp, "a.txt")
        common.atomic_write(p, b"x", mtime="Sun, 06 Nov 1994 08:49:37 GMT")
        self.assertAlmostEqual(os.path.getmtime(p), 784111777.0, places=0)

    def test_a_numeric_mtime_works_too(self):
        p = os.path.join(self.tmp, "a.txt")
        common.atomic_write(p, b"x", mtime=1000000000)
        self.assertAlmostEqual(os.path.getmtime(p), 1000000000, places=0)

    def test_an_unreadable_date_leaves_the_clock_alone(self):
        # Bytes that arrived intact are not discarded over a date nobody can parse.
        p = os.path.join(self.tmp, "a.txt")
        common.atomic_write(p, b"x", mtime="nonsense")
        self.assertTrue(os.path.isfile(p))


class TestExtraction(unittest.TestCase):
    """Every spelling of an attribute value, because pages here are hand-written as often as not."""

    def test_all_three_quotings(self):
        html = """<img src="a.gif"><img src='b.png'><img src=c.jpg>"""
        self.assertEqual(common.image_sources(html), ["a.gif", "b.png", "c.jpg"])

    def test_attributes_before_src(self):
        self.assertEqual(common.image_sources('<img class="x" alt="y" src="z.png">'), ["z.png"])

    def test_case_and_whitespace(self):
        self.assertEqual(common.image_sources('<IMG  SRC = "A.GIF" >'), ["A.GIF"])

    def test_duplicates_are_kept(self):
        # A page that embeds one picture twice is a fact about the page.
        self.assertEqual(common.image_sources('<img src="a.gif"><img src="a.gif">'),
                         ["a.gif", "a.gif"])

    def test_no_images(self):
        self.assertEqual(common.image_sources("<p>nothing here</p>"), [])

    def test_sitemap_locations(self):
        xml = "<urlset><url><loc>http://h/a</loc></url><url><loc>http://h/b</loc></url></urlset>"
        self.assertEqual(common.sitemap_locations(xml), ["http://h/a", "http://h/b"])

    def test_a_sitemap_index_has_the_same_shape(self):
        xml = "<sitemapindex><sitemap><loc>http://h/s1.xml</loc></sitemap></sitemapindex>"
        self.assertEqual(common.sitemap_locations(xml), ["http://h/s1.xml"])


class TestExtensionFor(unittest.TestCase):
    def test_a_known_type(self):
        self.assertEqual(common.extension_for("image/webp"), ".webp")

    def test_parameters_are_ignored(self):
        self.assertEqual(common.extension_for("image/jpeg; charset=binary"), ".jpg")

    def test_case_and_whitespace(self):
        self.assertEqual(common.extension_for("  IMAGE/PNG "), ".png")

    def test_an_unknown_type_is_None_NOT_a_guess(self):
        # A name that claims an extension the bytes do not match is believed; a name with none
        # is looked at.
        for t in ("application/octet-stream", "", None, "nonsense"):
            self.assertIsNone(common.extension_for(t), repr(t))


class TestSetCaseSensitive(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "the not-Windows answer")
    def test_on_posix_it_is_not_a_question(self):
        self.assertEqual(common.set_case_sensitive("/tmp"), "not Windows")

    @on_windows
    def test_A_MISSING_DIRECTORY_IS_NOT_A_SUCCESS(self):
        """The hole this test found, and the reason the function now checks first.

        `fsutil file setCaseSensitiveInfo` on a path that does not exist returns 0 -- measured
        2026-09-22: rc 0, no output, the directory still absent afterwards. Without the check a
        caller who mistyped a path was told the flag had been set on it.
        """
        got = common.set_case_sensitive(os.path.join(tempfile.gettempdir(), "no-such-dir-here"))
        self.assertIsInstance(got, str)
        self.assertIn("no such directory", got)

    @on_windows
    def test_a_real_directory_succeeds(self):
        tmp = tempfile.mkdtemp(prefix="common-test-")
        try:
            got = common.set_case_sensitive(tmp)
            if got is not True:
                self.skipTest("this volume will not take the flag: %s" % got)
            self.assertIs(got, True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
class TestIsPartial(unittest.TestCase):
    def test_the_three_suffixes(self):
        for n in ("x.tar.gz.part", "x.iso.suspect", "x.html.superseded"):
            self.assertTrue(common.is_partial(n), n)

    def test_case_does_not_matter(self):
        self.assertTrue(common.is_partial("X.ISO.PART"))

    def test_content_is_not_partial(self):
        for n in ("x.part1.zip", "particle.txt", "x.iso", "suspect.txt"):
            self.assertFalse(common.is_partial(n), n)


class TestLooksLikeHtml(unittest.TestCase):
    def test_the_usual_openings(self):
        for head in (b"<!DOCTYPE html>", b"<!doctype html>", b"<html>", b"<HTML>",
                     b"<?xml version="):
            self.assertTrue(common.looks_like_html(head), head)

    def test_leading_whitespace_and_a_bom_do_not_disguise_it(self):
        # A server that pads its error page does not thereby make it a PDF.
        self.assertTrue(common.looks_like_html(b"\xef\xbb\xbf<!DOCTYPE html>"))
        self.assertTrue(common.looks_like_html(b"\n\n   <html>"))

    def test_binary_is_not_html(self):
        for head in (b"%PDF-1.4", b"PK\x03\x04", b"\x1f\x8b", b"", None):
            self.assertFalse(common.looks_like_html(head), repr(head))

    def test_NOR_DOES_A_LEADING_COMMENT(self):
        """The page this collection meets more often than any other, and it was being missed.

        `<!-- Copyright (C) Bull SAS - 2019 -->` comes before the doctype, so every copy of it
        was reported as "does not begin with the .jpg signature" rather than "HTML under a .jpg
        name" -- the vague answer that sends a reader to open the file, for a page already
        identified three times over on 2026-09-24: under `.exe`, under eight `.rpm` names, and
        under 28 image names.
        """
        bull = b"<!-- Copyright (C) Bull SAS - 2019 -->\n<!DOCTYPE html>\n<html>"
        self.assertTrue(common.looks_like_html(bull))
        self.assertEqual(common.magic_mismatch("aixl.jpg", bull), "HTML under a .jpg name")

    def test_and_several_comments_in_a_row(self):
        self.assertTrue(common.looks_like_html(b'<!-- a --><!-- b --><?xml version="1.0"?>'))

    def test_A_COMMENT_IS_SKIPPED_NOT_TAKEN_AS_PROOF(self):
        """`<!--` does not make a file HTML. What follows the comment still has to.

        Without this the check would answer "HTML" for anything whose first four bytes happen to
        be `<!--`, which is how a permissive rule starts quietly excusing real damage.
        """
        self.assertFalse(common.looks_like_html(b"<!-- a comment -->\x00\x01\x02binary"))

    def test_and_an_unterminated_comment_is_not_an_answer(self):
        # This reads a fixed-size head. "The document may continue past what we were given" is
        # not the same as "it does", so it declines rather than guessing.
        self.assertFalse(common.looks_like_html(b"<!-- never closed, then rubbish"))

    def test_the_comment_skipping_is_bounded(self):
        # A pathological file of nothing but comments must not turn this into a long loop; it
        # reads a head, not a document.
        self.assertFalse(common.looks_like_html(b"<!-- x -->" * 400))


class TestLooksLikeAnErrorPage(unittest.TestCase):
    """A WRONG PAGE UNDER A RIGHT NAME -- the one case nothing here could see.

    magic_mismatch() finds HTML wearing another format's extension and find-html-imposters.py
    hunts the same thing across the collection; both start from a name that is already suspect.
    spider.seds.org/ngc/ holds eight `.cgi` files fetched with HTTP 200, six of them error pages,
    and `.cgi` is in PROGRAM_PAGE_EXTENSIONS -- so HTML there is exactly what is expected and
    every existing check was right to stay quiet.
    """

    # The real titles, measured 2026-09-27. The last two are the genuine pages beside them.
    SEDS = {
        "NGC Error !": "error",
        "Erreur NGC !": "error",
        "NGC/IC Error!": "error",
        "Error in revngcic.cgi": "error",
        "Digital Sky Survey image": None,
        "NGC Online Cross Identifications": None,
    }

    def page(self, title):
        return ("<!DOCTYPE html><html><head><title>%s</title></head><body>x</body></html>"
                % title).encode("utf-8")

    def test_THE_EIGHT_FILES_THAT_MADE_IT_NECESSARY(self):
        for title, want in self.SEDS.items():
            got = common.looks_like_an_error_page(self.page(title))
            self.assertEqual(got[0] if got else None, want, title)
            if want:
                self.assertEqual(got[2], title)

    def test_IT_REPORTS_RATHER_THAN_JUDGES(self):
        """The complaint, how good the evidence is, AND the title -- not True.

        "seds-frommert ngc/ngc.cgi  error  \\"NGC Error !\\"" has told a reader everything;
        "suspicious" has sent somebody to open the file.
        """
        self.assertEqual(common.looks_like_an_error_page(self.page("404 Not Found")),
                         ("not found", common.STOCK, "404 Not Found"))

    def test_the_four_complaints_are_told_apart(self):
        # "forbidden" and "not found" send a reader to different places.
        for title, kind in (("403 Forbidden", "forbidden"),
                            ("Access Denied", "forbidden"),
                            ("404 Not Found", "not found"),
                            ("No such file or directory", "not found"),
                            ("500 Internal Server Error", "unavailable"),
                            ("Service Unavailable", "unavailable"),
                            ("502 Bad Gateway", "unavailable")):
            got = common.looks_like_an_error_page(self.page(title))
            self.assertEqual(got and got[0], kind, title)

    def test_NO_BARE_STATUS_NUMBERS_BECAUSE_THIS_IS_A_HARDWARE_COLLECTION(self):
        """`\\b404\\b` matches `HP 404 Calculator` and `\\b500\\b` matches `IBM System/36 5360`.

        Every real server title that carries a code carries the words too, so the phrases catch
        the error pages and the model numbers stay out. This is the single largest source of
        false findings the rule could have had, and it was designed out rather than measured
        away.
        """
        for title in ("HP 404 Calculator", "IBM 5100 Portable Computer", "Model 500 Service Guide",
                      "DEC VT502 Terminal", "503 Chipset Notes"):
            self.assertIsNone(common.looks_like_an_error_page(self.page(title)), title)

    def test_IT_READS_THE_TITLE_AND_NOT_THE_BODY(self):
        """find-html-imposters.py matches its table against the whole head, which is right for
        its question: it already knows the name is wrong, so any mention of an error is a clue.
        Here the name is RIGHT, so only what the page says about ITSELF counts. Against a body,
        every manual with the word "error" in a paragraph would be a finding."""
        body = (b"<!DOCTYPE html><html><head><title>POST Codes</title></head><body>"
                b"<p>If the drive reports an error, see Appendix B. 404 Not Found means the "
                b"controller is absent. Access denied indicates a jumper fault.</p></body></html>")
        self.assertIsNone(common.looks_like_an_error_page(body))

    def test_a_heading_is_read_when_there_is_no_title(self):
        # The stock server pages carry no <title> at all.
        self.assertEqual(common.looks_like_an_error_page(b"<html><body><h1>NGC/IC Error!</h1>"),
                         ("error", common.WEAK, "NGC/IC Error!"))

    def test_SOMETHING_THAT_IS_NOT_HTML_IS_NOT_AN_ERROR_PAGE(self):
        """A PDF whose bytes happen to contain `<title>Error</title>` is a PDF."""
        for head in (b"%PDF-1.4 <title>Error</title>", b"PK\\x03\\x04<title>404 Not Found</title>",
                     b"", b"plain text mentioning an error"):
            self.assertIsNone(common.looks_like_an_error_page(head), repr(head))

    def test_a_page_with_no_title_at_all_is_not_one_either(self):
        self.assertIsNone(common.looks_like_an_error_page(b"<!DOCTYPE html><html><body>hello"))

    def test_the_word_must_stand_alone(self):
        # Substring matching would make "Terrorism" and "Errorless" findings.
        for title in ("Terror Incognita", "Errorless Learning", "Mirrorless Cameras"):
            self.assertIsNone(common.looks_like_an_error_page(self.page(title)), title)

    def test_the_table_is_ordered_and_the_catch_all_comes_last(self):
        """`500 Internal Server Error` contains the bare word "error".

        With the generic class first it was reported as "error" and the specific reading was
        thrown away -- which is how this table was first written, and what the case above caught.
        """
        self.assertIsInstance(common.PAGE_COMPLAINTS, tuple)
        self.assertEqual([k for k, _p in common.PAGE_COMPLAINTS],
                         ["not found", "forbidden", "unavailable", "error"])
        self.assertEqual(common.looks_like_an_error_page(self.page("500 Internal Server Error")),
                         ("unavailable", common.STOCK, "500 Internal Server Error"))


class TestStockVersusWeakEvidence(unittest.TestCase):
    """The distinction this collection forced, and the two ideas it killed on the way.

    Measured 2026-09-27 over all 295 586 stored pages: the loose vocabulary finds 2 357, of which
    about 2 275 are DOCUMENTS -- IBM PS/2 maintenance manuals, an AIX message reference, the Bison
    and Emacs manuals, an IBM technical-support knowledge base. Requiring the title to BE a status
    phrase keeps 82, in five distinct titles, every one a server talking.
    """

    def page(self, title):
        return ("<!DOCTYPE html><html><head><title>%s</title></head></html>" % title).encode()

    def test_THE_FIVE_TITLES_THE_RULE_KEEPS(self):
        """Every stock finding in the whole collection, by title. Real bytes behind each."""
        for title in ("404 Not Found", "File Not Found", "404 - File or directory not found.",
                      "Document not found message",
                      "IBM PartnerWorld for Developers : Document not found message"):
            got = common.looks_like_an_error_page(self.page(title))
            self.assertEqual(got[1], common.STOCK, title)

    def test_AND_THE_DOCUMENTS_IT_DROPS(self):
        """The titles that produced 2 275 of the 2 357 loose findings. Each is a real page in
        this collection and not one of them is a failure."""
        for title in ("Error Log", "Error Codes", "Numeric Error Codes", "Error Messages",
                      "Appendix B. ODM Error Codes", "Bison 1.25 - Error Recovery",
                      "GNU Emacs Lisp Reference Manual - Error Messages",
                      "The Linux SCSI programming HOWTO: Error handling",
                      "Tech Report: HPL-97-78: Error Rate Analysis of",
                      "Autoconf - Forbidden Patterns",
                      "Mount remote filesystem, permission denied"):
            got = common.looks_like_an_error_page(self.page(title))
            self.assertEqual(got[1], common.WEAK, title)

    def test_THE_SEDS_PAGES_ARE_WEAK_AND_THAT_IS_HONEST(self):
        """The six that motivated the whole function do NOT survive the strong rule, and saying
        so is the point. `NGC Error !` is a title an application invented; nothing separates it
        from `Error Log` except knowing which archive holds error-code documentation."""
        for title in ("NGC Error !", "Erreur NGC !", "NGC/IC Error!", "Error in revngcic.cgi"):
            self.assertEqual(common.looks_like_an_error_page(self.page(title))[1], common.WEAK)

    def test_a_site_prefix_may_be_dropped_in_front_of_a_phrase(self):
        self.assertEqual(common.stock_error_title("Hewlett-Packard : Page Not Found"),
                         "page not found")

    def test_BUT_NOT_IN_FRONT_OF_A_SINGLE_WORD(self):
        """`ECA 024 - 113 error` otherwise reduces to the bare word "error" and is kept, and it
        is a BBS bulletin about error 113, not a server saying anything. That one exception is
        the difference between 84 findings and 82, and both it removes are false."""
        self.assertIsNone(common.stock_error_title("ECA 024 - 113 error"))
        self.assertEqual(common.stock_error_title("Error"), "error")

    def test_a_leading_status_code_is_stripped_however_it_is_written(self):
        for title in ("404 Not Found", "404 - Not Found", "HTTP 404 Not Found",
                      "Error 404: Not Found", "404: Not found"):
            self.assertEqual(common.stock_error_title(title), "not found", title)

    def test_punctuation_and_case_do_not_decide_it(self):
        self.assertEqual(common.normalise_title("  404 -- NOT FOUND!! "), "not found")

    def test_ENTITIES_ARE_DECODED_BY_page_title_AND_NOT_HERE(self):
        """Each stage does one thing, and the first version of this test asked the wrong one.

        normalise_title() is fed a title page_title() has already decoded; handed a raw `&nbsp;`
        it answers `nbsp not found`, correctly, because undoing markup is not its job.
        """
        self.assertEqual(common.normalise_title("404 &nbsp; NOT FOUND"), "nbsp not found")
        self.assertEqual(
            common.normalise_title(common.page_title(b"<title>404 &nbsp; NOT FOUND</title>")),
            "not found")

    def test_AND_AN_ENTITY_CAN_HIDE_THE_COLON_THE_PREFIX_RULE_NEEDS(self):
        """Measured over the 2 357 titles a collection-wide scan collected: 89 carry an entity,
        `&#58;` among them 18 times -- and `&#58;` IS a colon. Without decoding,
        `NETFINITY 3500&#58; ...` keeps its prefix and is judged against the wrong string."""
        page = b"<html><title>Hewlett-Packard&#58; Page Not Found</title></html>"
        self.assertEqual(common.page_title(page), "Hewlett-Packard: Page Not Found")
        self.assertEqual(common.stock_error_title(common.page_title(page)), "page not found")

    def test_TITLE_LENGTH_IS_NOT_THE_DISCRIMINATOR_AND_WAS_TRIED(self):
        """It looked decisive on 13 examples -- real error pages 11-21 characters, false ones
        54-79. Over the whole collection the SHORTEST title of all is `Error Log`, nine
        characters, an IBM PS/2 manual page. Backwards, and pinned so it is not reinvented."""
        short_and_false = "Error Log"
        long_and_true = "IBM PartnerWorld for Developers : Document not found message"
        self.assertLess(len(short_and_false), len(long_and_true))
        self.assertEqual(common.looks_like_an_error_page(self.page(short_and_false))[1],
                         common.WEAK)
        self.assertEqual(common.looks_like_an_error_page(self.page(long_and_true))[1],
                         common.STOCK)

    def test_the_phrase_set_is_frozen_and_lower_case(self):
        self.assertIsInstance(common.STOCK_ERROR_TITLES, frozenset)
        for phrase in common.STOCK_ERROR_TITLES:
            self.assertEqual(phrase, common.normalise_title(phrase), phrase)


class TestMarkupExtensions(unittest.TestCase):
    """The wider set, derived from the narrower one so the two cannot drift apart by accident.

    It lived in find-html-imposters.py until 2026-09-27 and HAD drifted, in both directions. One
    direction is deliberate and stays: .css, .js and .xml hold markup by definition, so a file of
    those kinds containing HTML is not news, while PAGE_EXTENSIONS asks whether there are links
    inside worth following. The other direction was an omission.
    """

    def test_EVERY_PAGE_EXTENSION_IS_ONE_WHERE_MARKUP_IS_EXPECTED(self):
        """The property that makes the derivation worth having.

        The tool's own copy was missing `.php4`, `.phtm`, `.shtm` and `.xhtm`. An HTML file named
        `x.php4` was therefore reported as markup under a non-markup extension -- a false finding
        -- and `--pages` never read it, so a real error page under that name was missed. Both
        wrong, in opposite directions, from one omission.
        """
        missing = sorted(set(common.PAGE_EXTENSIONS) - set(common.MARKUP_EXTENSIONS))
        self.assertEqual(missing, [])

    def test_and_php4_in_particular_because_leaving_it_out_has_already_cost_an_archive(self):
        # See the note above DOCUMENT_EXTENSIONS: bitsavers' capture of www.hpl.hp.com followed
        # no link out of its nine .php4 pages, and hp-labs-linux-salvage exists to hold what the
        # Internet Archive could give back.
        for ext in (".php4", ".phtm", ".shtm", ".xhtm"):
            self.assertIn(ext, common.MARKUP_EXTENSIONS, ext)

    def test_the_wider_set_adds_the_formats_that_are_markup_by_definition(self):
        extra = sorted(set(common.MARKUP_EXTENSIONS) - set(common.PAGE_EXTENSIONS))
        self.assertEqual(extra, [".atom", ".css", ".js", ".rdf", ".rss", ".svg",
                                 ".xml", ".xsd", ".xsl"])

    def test_it_is_a_tuple_and_has_no_duplicates(self):
        self.assertIsInstance(common.MARKUP_EXTENSIONS, tuple)
        self.assertEqual(len(set(common.MARKUP_EXTENSIONS)), len(common.MARKUP_EXTENSIONS))


class TestLooksLikeMarkup(unittest.TestCase):
    """The HUNTING counterpart to looks_like_html(), and the two must not be folded."""

    def test_it_accepts_what_the_narrow_check_refuses(self):
        # A served error page often begins with a comment, a meta or a title.
        for head in (b"<!-- Copyright (C) Bull SAS - 2019 -->\n<!DOCTYPE html>",
                     b"<meta charset=x>", b"<title>404</title>", b"<head>"):
            self.assertTrue(common.looks_like_markup(head), head)

    def test_AND_THE_NARROW_ONE_STILL_REFUSES_THEM(self):
        """Folding the two would either blind the hunt or make magic_mismatch() report ordinary
        files as HTML. The difference is the point, so it is pinned."""
        self.assertFalse(common.looks_like_html(b"<meta charset=x>"))
        self.assertFalse(common.looks_like_html(b"<title>404</title>"))

    def test_A_CONTAINER_THAT_HOLDS_A_PAGE_IS_NOT_A_PAGE(self):
        """os2bbs/science/gmt4os2.zip, 17 957 583 bytes, is a real ZIP whose first member is an
        UNCOMPRESSED gmt4os2.html -- so `<HTML>` sits at byte 0x30, inside the local file header,
        and a scan of the first 512 bytes called an 18 MB archive an error page."""
        zip_with_html = b"PK\x03\x04" + b"\x00" * 44 + b"gmt4os2.html<HTML>"
        self.assertIn(b"<HTML>", zip_with_html)
        self.assertFalse(common.looks_like_markup(zip_with_html))

    def test_and_every_container_opening_is_refused(self):
        for magic in common.BINARY_MAGIC:
            self.assertFalse(common.looks_like_markup(magic + b"<html>"), magic)

    def test_a_stray_html_further_in_is_found_but_only_so_far(self):
        self.assertTrue(common.looks_like_markup(b"junk " * 20 + b"<html>"))
        self.assertFalse(common.looks_like_markup(b"x" * common.MARKUP_WINDOW + b"<html>"))

    def test_a_bom_and_whitespace_do_not_disguise_it(self):
        self.assertTrue(common.looks_like_markup(b"\xef\xbb\xbf\n\n  <html>"))

    def test_nothing_is_not_markup(self):
        for head in (b"", None, b"plain text with no tags at all"):
            self.assertFalse(common.looks_like_markup(head), repr(head))


class TestSplitArchive(unittest.TestCase):
    """Seven places did this by hand and they did not agree on the one case that matters."""

    def test_the_ordinary_case(self):
        self.assertEqual(common.split_archive("bitsavers/pdf/x.zip"), ("bitsavers", "pdf/x.zip"))

    def test_THE_NO_SLASH_CASE_IS_WHERE_THE_COPIES_DISAGREED(self):
        """Three different answers were in this directory at once: a tail of "", a ValueError,
        and the string "(root)".

        `where, under = rel.split("/", 1)` RAISES on a path with no slash -- fine while every row
        happens to have one, and a table of findings is not the place to discover that one does
        not. The empty tail is the answer here because a caller that cares can test for it.
        """
        self.assertEqual(common.split_archive("bitsavers"), ("bitsavers", ""))
        self.assertEqual(common.split_archive(""), ("", ""))

    def test_only_the_first_slash_splits(self):
        self.assertEqual(common.split_archive("a/b/c/d"), ("a", "b/c/d"))

    def test_a_trailing_slash_leaves_an_empty_tail(self):
        self.assertEqual(common.split_archive("bitsavers/"), ("bitsavers", ""))

    def test_IT_SPLITS_ON_FORWARD_SLASH_ONLY(self):
        """These rows are written with `/` whatever the filesystem uses. A backslash is an
        ordinary character in a name here, and this collection has names that contain one."""
        self.assertEqual(common.split_archive("weird\\name/file"), ("weird\\name", "file"))


class TestClassifyPage(unittest.TestCase):
    """The six-class table, asked of a file whose NAME IS ALREADY WRONG.

    It is the second of two tables and they must stay two: PAGE_COMPLAINTS is asked of a file
    whose name is RIGHT, so a bare `404` is banned there -- `HP 404 Calculator` is a real title
    in this collection. Here the loose patterns cost nothing and catch more.
    """

    def test_each_kind_is_recognised(self):
        for blob, kind in ((b"<title>Index of /pub/aix</title>", "index"),
                           (b"<h1>404 Not Found</h1>", "soft-404"),
                           (b"<h1>403 Forbidden</h1>", "forbidden"),
                           (b"<meta http-equiv=refresh content=0>", "redirect"),
                           (b"<p>This domain is for sale</p>", "parking"),
                           (b"<p>Internal server trouble</p>", "error")):
            self.assertEqual(common.classify_page(blob), kind, blob)

    def test_REAL_HTML_IS_AN_ANSWER_AND_NOT_A_FAILURE_TO_ANSWER(self):
        """Often perfectly legitimate, and reported separately by every caller so far."""
        self.assertEqual(common.classify_page(b"<html><body>Sun hardware notes</body></html>"),
                         common.ORDINARY_PAGE)
        self.assertEqual(common.ORDINARY_PAGE, "page")

    def test_the_order_is_deliberate_and_error_is_last(self):
        self.assertEqual([k for k, _p in common.PAGE_KINDS][-1], "error")
        # A directory listing that also says "error" somewhere is still a directory listing:
        # what it blocks below that path is the finding, not the word.
        self.assertEqual(common.classify_page(b"<h1>Index of /pub</h1> an error occurred"),
                         "index")

    def test_IT_USES_THE_LIBRARYS_OWN_INDEX_PATTERN(self):
        """This entry was a second, hand-spelled copy of INDEX_PAGE in find-html-imposters.py, so
        magic_mismatch() and that scan could have disagreed about what a saved listing is while
        both looked right."""
        self.assertIs(dict(common.PAGE_KINDS)["index"], common.INDEX_PAGE)

    def test_THE_TWO_TABLES_ARE_NOT_THE_SAME_TABLE(self):
        """Folding them would either blind this one or make the other report thousands of
        manuals. `HP 404 Calculator` is the case that decides it."""
        page = b"<!DOCTYPE html><html><head><title>HP 404 Calculator</title></head></html>"
        self.assertEqual(common.classify_page(page), "soft-404")      # loose, and right here
        self.assertIsNone(common.looks_like_an_error_page(page))      # strict, and right there


class TestLooksLikeAPlaceholderPage(unittest.TestCase):
    """Is this 200 a site coming back, or somebody else's machine answering for a dead name?

    No status code can tell those apart: a lapsed domain is bought, parked, and answers 200
    forever. The tables lived in recheck-decisions.py until 2026-09-27, beside a looser version
    of the same question in find-html-imposters.py's "parking" class -- two files that could
    learn different vocabularies about one thing.
    """

    PAGE = "<html><head><title>%s</title></head><body>%s</body></html>"

    def site(self, title="Sun Hardware Reference", body="real content here "):
        return self.PAGE % (title, body * 40)

    def test_a_real_site_is_not_a_placeholder(self):
        self.assertIsNone(common.looks_like_a_placeholder_page(self.site()))

    def test_A_STUB_AND_A_PARKED_DOMAIN_ARE_TOLD_APART(self):
        """They mean different things: a stub is a machine with nothing on it, a parked domain is
        somebody else's machine. The caller reports them differently, so the library says which.
        """
        stub = common.looks_like_a_placeholder_page("<html>It works!</html>" + "x" * 300)
        self.assertEqual(stub[0], "stub")
        parked = common.looks_like_a_placeholder_page(self.site(title="Buy this domain"))
        self.assertEqual(parked[0], "parked")

    def test_IT_RETURNS_THE_EVIDENCE_AND_NOT_A_BARE_VERDICT(self):
        """`recheck-decisions.py` prints the reason beside the host; "placeholder" alone would
        send somebody to open the URL by hand."""
        why, evidence = common.looks_like_a_placeholder_page(self.site(title="GoDaddy Parking"))
        self.assertEqual(why, "parked")
        self.assertIn(evidence, common.PLACEHOLDER_TITLES)

    def test_A_200_TOO_SMALL_TO_BE_A_PAGE_IS_A_STUB(self):
        """`download.aixtools.net` answers 200 with 44 bytes of Apache's stock "It works!" and no
        title at all, so a title-only test calls it alive and puts a permanent `!!` on an archive
        whose own marker says the origin is gone."""
        why, evidence = common.looks_like_a_placeholder_page(b"It works!")
        self.assertEqual(why, "stub")
        self.assertIn("9 bytes", evidence)

    def test_AN_AUTOINDEX_IS_NEVER_A_PLACEHOLDER(self):
        """The rule most worth re-reading, and the one already broken once: the first draft of
        STUB_BODIES had "<h1>index of" in it, three lines under the comment warning against
        exactly that.

        An Apache autoindex is the single most PROMISING thing a dead-looking host can answer --
        it means there are files there to walk. A rule that silenced it would defeat the tools
        that call this.
        """
        listing = ("<html><head><title>Index of /pub</title></head><body><h1>Index of /pub</h1>"
                   + "<a href=x>x</a>" * 40 + "</body></html>")
        self.assertIsNone(common.looks_like_a_placeholder_page(listing))
        for marker in common.PLACEHOLDER_TITLES + common.STUB_BODIES:
            self.assertNotIn("index of", marker.lower(), marker)

    def test_the_title_is_taken_as_given_when_the_caller_has_it(self):
        # The caller usually read it already; making it read the body again would be the sixth
        # copy problem in another shape.
        self.assertEqual(
            common.looks_like_a_placeholder_page("x" * 300, title="Welcome - BlueHost.com")[0],
            "parked")

    def test_and_read_from_the_body_when_it_does_not(self):
        self.assertEqual(common.looks_like_a_placeholder_page(self.site(title="Sedo"))[0],
                         "parked")

    def test_bytes_or_str(self):
        self.assertEqual(common.looks_like_a_placeholder_page(b"It works!")[0], "stub")
        self.assertEqual(common.looks_like_a_placeholder_page("It works!")[0], "stub")

    def test_A_STUB_MARKER_DEEP_IN_A_REAL_PAGE_DOES_NOT_COUNT(self):
        """A page that quotes "it works!" in a paragraph 4 kB down is a page."""
        deep = self.PAGE % ("Troubleshooting", "filler " * 400 + "it works!")
        self.assertIsNone(common.looks_like_a_placeholder_page(deep))

    def test_the_tables_are_immutable_tuples(self):
        for table in (common.PLACEHOLDER_TITLES, common.STUB_BODIES):
            self.assertIsInstance(table, tuple)

    def test_the_markers_are_lower_case_because_the_comparison_lower_cases(self):
        # A marker with a capital in it would never match, silently.
        for marker in common.PLACEHOLDER_TITLES + common.STUB_BODIES:
            self.assertEqual(marker, marker.lower(), marker)


class TestCopyNewFile(unittest.TestCase):
    """The safety property behind filling a gap from another copy: it NEVER overwrites.

    Written for `vgamuseum-doc`, whose origin truncates large transfers -- `short read 36337467
    of 103094544`, three attempts, every time -- while a complete copy of the same tree sat in
    `iommu/datasheets/mirrors/www.vgamuseum.info/`. Two files of 103 and 116 MB were filled from
    it on 2026-09-27.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="copynew-")
        self.src = os.path.join(self.dir, "source")
        with io.open(self.src, "wb") as fh:
            fh.write(b"the real bytes" * 100)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, path):
        with io.open(path, "rb") as fh:
            return fh.read()

    def test_it_copies_and_says_how_much(self):
        dest = os.path.join(self.dir, "dest")
        self.assertEqual(common.copy_new_file(self.src, dest), 1400)
        self.assertEqual(self.read(dest), self.read(self.src))

    def test_IT_NEVER_OVERWRITES_AND_SAYS_NOTHING_HAPPENED(self):
        """None is not an error. The callers are gap-fillers and "already have it" is the
        ordinary case -- 18 of the 20 vgamuseum files were already there by the time it ran."""
        dest = os.path.join(self.dir, "dest")
        with io.open(dest, "wb") as fh:
            fh.write(b"ALREADY HERE")
        self.assertIsNone(common.copy_new_file(self.src, dest))
        self.assertEqual(self.read(dest), b"ALREADY HERE")

    def test_it_makes_the_directories_it_needs(self):
        dest = os.path.join(self.dir, "a", "b", "c", "dest")
        self.assertEqual(common.copy_new_file(self.src, dest), 1400)
        self.assertTrue(os.path.isfile(dest))

    def test_NOTHING_IS_LEFT_BEHIND_EITHER_WAY(self):
        """A `.part` that outlives the copy is a file every audit has to explain."""
        common.copy_new_file(self.src, os.path.join(self.dir, "one"))
        with io.open(os.path.join(self.dir, "two"), "wb") as fh:
            fh.write(b"x")
        common.copy_new_file(self.src, os.path.join(self.dir, "two"))
        left = [f for _r, _d, fs in os.walk(self.dir) for f in fs if f.endswith(".part")]
        self.assertEqual(left, [])

    def test_IT_DOES_NOT_TOUCH_A_DOWNLOAD_IN_FLIGHT(self):
        """`<dest>.part` is the name mirror.py gives a download it is still writing. Two writers
        agreeing on a temporary name is how one of them loses a file, so this one carries the pid.

        Tested by the property and not by watching the calls: an earlier version reached into
        `common.io` to see which names were opened, and the contract test caught it -- a test
        that pokes at an implementation detail is a test that forbids changing it.
        """
        dest = os.path.join(self.dir, "dest")
        inflight = dest + ".part"
        with io.open(inflight, "wb") as fh:
            fh.write(b"SOMEBODY ELSE IS STILL WRITING THIS")
        self.assertEqual(common.copy_new_file(self.src, dest), 1400)
        self.assertEqual(self.read(inflight), b"SOMEBODY ELSE IS STILL WRITING THIS")
        self.assertEqual(self.read(dest), self.read(self.src))

    def test_and_it_still_ends_in_part_so_is_partial_knows_it(self):
        # Otherwise an audit counts a copy in flight as content.
        self.assertTrue(common.is_partial("dest.1234.part"))

    def test_THE_SOURCE_MTIME_IS_CARRIED_OVER(self):
        """In this collection a stored file's timestamp is usually the origin's own
        Last-Modified. Dropping it would make the filled copy look newer than the thing it is a
        copy of -- the two vgamuseum ZIPs both read `Jun 16 2021`."""
        old = time.time() - 400 * 24 * 3600
        os.utime(self.src, (old, old))
        dest = os.path.join(self.dir, "dest")
        common.copy_new_file(self.src, dest)
        self.assertLess(abs(os.path.getmtime(dest) - old), 2)

    def test_a_big_file_is_streamed_and_not_read_whole(self):
        # 103 MB was the real case; the chunk size is the library's hashing one.
        big = os.path.join(self.dir, "big")
        with io.open(big, "wb") as fh:
            fh.write(b"z" * (common.HASH_CHUNK * 3 + 7))
        dest = os.path.join(self.dir, "bigcopy")
        self.assertEqual(common.copy_new_file(big, dest), common.HASH_CHUNK * 3 + 7)
        self.assertEqual(common.sha256_file(dest), common.sha256_file(big))


class TestFailedUrls(unittest.TestCase):
    """What a fetch gave up on, read back out of its own error log.

    A log line that is read is a FORMAT, not a message -- the same argument COLLISION_DROPPED
    makes. Measured over every errors-*.txt this collection has written: 680 FAIL lines across
    nine archives, 628 distinct urls.
    """

    def test_it_reads_the_url_off_a_fail_line(self):
        text = "2026-09-14 05:21:47 FAIL HTTP 500 https://host/cgi/x.pl\n"
        self.assertEqual(common.failed_urls(text), ["https://host/cgi/x.pl"])

    def test_A_RETRY_IS_NOT_A_FAILURE(self):
        """`RETRY 2/3` says the fetch is still trying; only `FAIL` says it stopped. Matching both
        would report files that arrived on the third attempt as missing, and these error files
        are full of those."""
        text = ("2026-09-27 11:01:51 RETRY 2/3 OSError: short read https://host/a.zip\n"
                "2026-09-27 11:03:36 FAIL OSError: short read https://host/b.zip\n")
        self.assertEqual(common.failed_urls(text), ["https://host/b.zip"])

    def test_REPEATS_ARE_DROPPED_AND_ORDER_IS_KEPT(self):
        """An errors file accumulates across runs: the two vgamuseum ZIPs appear eight times
        between them, once per attempt over two days. A caller filling gaps wants two pieces of
        work, not eight."""
        line = "2026-09-27 11:03:36 FAIL OSError: short read %s\n"
        text = (line % "https://h/b.zip") + (line % "https://h/a.zip") + (line % "https://h/b.zip")
        self.assertEqual(common.failed_urls(text), ["https://h/b.zip", "https://h/a.zip"])

    def test_THE_REASON_IS_NOT_PARSED_AND_MAY_CONTAIN_ANYTHING(self):
        """Measured across 680 real lines: the reason comes in at least six shapes, including an
        OSError whose message embeds two Windows long paths with backslashes and colons."""
        text = ("2026-09-26 22:10:00 FAIL PermissionError: [WinError 32] ... "
                "'\\\\\\\\?\\\\Q:\\\\m\\\\a.pdf.part' -> '\\\\\\\\?\\\\Q:\\\\m\\\\a.pdf' "
                "https://host/a.pdf\n")
        self.assertEqual(common.failed_urls(text), ["https://host/a.pdf"])

    def test_and_a_line_whose_message_broke_across_lines_is_skipped(self):
        """Three of the 680 do not end in a url at all -- a URLError whose message contains a
        newline. Skipping them loses nothing: the same url fails again on the next attempt."""
        text = ("2026-09-08 01:00:00 FAIL URLError: <urlopen error Eine bestehende Verbindung\n"
                "wurde softwaregesteuert abgebrochen>\n"
                "2026-09-08 01:00:01 FAIL HTTP 503 https://host/good\n")
        self.assertEqual(common.failed_urls(text), ["https://host/good"])

    def test_A_URL_MAY_CONTAIN_A_SPACE(self):
        r"""The first version of the pattern read `(\S+://\S+)$` and would have skipped these in
        SILENCE -- exactly the files this collection is most likely to lose.

        A server may LINK an unescaped space; quote_url() exists because one archive here serves
        `AS400 Processor Summary.html` that way. Measured the day this was written: 0 FAIL lines
        carry a space and 333 PERMFAIL lines do, so the shape is real and had simply not yet
        landed on a file that was given up on. Found by chasing a one-off in a marker's count.
        """
        line = "2026-09-27 13:14:32 FAIL HTTP 404 https://seds.org/billa/Sharpless 2-224.jpg"
        self.assertEqual(common.failed_urls(line),
                         ["https://seds.org/billa/Sharpless 2-224.jpg"])

    def test_AND_THE_GROUP_STARTS_AT_A_WORD_BOUNDARY(self):
        r"""The second version was wrong too, in the opposite direction: `.*(\S+://...)` lets the
        greedy prefix eat as far as `http` and returns `s://host/path`. Caught at once because
        the check ran against a real line rather than an imagined one."""
        for line, want in (
                ("2026-09-26 22:10:00 FAIL HTTP 500 https://host/a.pdf", "https://host/a.pdf"),
                ("2026-09-26 22:10:00 FAIL https://host/bare.pdf", "https://host/bare.pdf")):
            self.assertEqual(common.failed_urls(line), [want], line)

    def test_an_empty_or_absent_log_is_no_urls_and_not_an_error(self):
        self.assertEqual(common.failed_urls(""), [])


class TestSourceUrl(unittest.TestCase):
    """Three tools asked this and only two agreed, which is why it is in the library.

    holes-vs-source.py and truncated-vs-source.py held byte-identical copies, fallback included;
    ask-the-source.py held a third version WITHOUT the HTTP_FACE fallback and so answered
    "unaskable" for every bitsavers path while the other two answered a working URL for the same
    input. Nothing was broken and nothing was reported: the third tool simply asked less, and no
    test could see it because each copy was consistent with itself.
    """

    REGISTER = {"an-archive": "https://example.invalid/pub/",
                "over-rsync": "rsync://example.invalid/mod/",
                "trailing": "https://example.invalid/pub",
                "bitsavers": "rsync://bitsavers.org/bits/"}

    def test_a_recorded_http_archive_becomes_an_address(self):
        self.assertEqual(common.source_url("an-archive", "dir/file.htm", self.REGISTER),
                         "https://example.invalid/pub/dir/file.htm")

    def test_a_space_is_encoded_because_a_bare_space_is_not_a_url(self):
        # `fsck-vendors/QNX/QNX 6/...` is a real path in this collection.
        self.assertEqual(common.source_url("an-archive", "QNX 6/x", self.REGISTER),
                         "https://example.invalid/pub/QNX%206/x")

    def test_A_SLASH_STAYS_A_SLASH(self):
        """quote() per segment. Applied to the whole path it escapes the separators too, and
        every request 404s for a reason nobody would guess from the output."""
        got = common.source_url("an-archive", "a/b/c", self.REGISTER)
        self.assertNotIn("%2F", got)
        self.assertEqual(got, "https://example.invalid/pub/a/b/c")

    def test_a_register_prefix_without_a_trailing_slash_does_not_double_it(self):
        self.assertEqual(common.source_url("trailing", "x", self.REGISTER),
                         "https://example.invalid/pub/x")

    def test_AN_RSYNC_ARCHIVE_WITH_AN_HTTP_FACE_IS_ASKABLE(self):
        """The entry that exists, and the evidence for it. bitsavers is taken over rsync, which
        no HTTP tool speaks; without the fallback a third of holes-vs-source.py's findings --
        21 of 67, every one bitsavers -- were unanswerable. Two damaged PDFs were fetched whole
        from https://bitsavers.org/ on 2026-09-25 and matched byte for byte."""
        self.assertIn("bitsavers", common.HTTP_FACE)
        self.assertEqual(common.source_url("bitsavers", "pdf/x.zip", self.REGISTER),
                         "https://bitsavers.org/pdf/x.zip")

    def test_an_rsync_archive_without_one_cannot_be_asked(self):
        self.assertIsNone(common.source_url("over-rsync", "a/b", self.REGISTER))

    def test_an_archive_nobody_recorded_cannot_be_asked(self):
        self.assertIsNone(common.source_url("never-heard-of-it", "a/b", self.REGISTER))

    def test_A_CALLER_MAY_PASS_ITS_OWN_TABLE(self):
        """HTTP_FACE is a MappingProxyType precisely so nobody edits the shared one. The
        parameter is the supported way to differ."""
        mine = {"over-rsync": "https://mine.invalid/"}
        self.assertEqual(common.source_url("over-rsync", "a", self.REGISTER, http_face=mine),
                         "https://mine.invalid/a")
        # And passing one does not silently keep the default's entries.
        self.assertIsNone(common.source_url("bitsavers", "a", self.REGISTER, http_face=mine))

    def test_the_shared_table_refuses_to_be_rewritten(self):
        with self.assertRaises(TypeError):
            common.HTTP_FACE["anything"] = "https://no.invalid/"

    def test_a_prefix_that_is_not_a_url_is_not_one(self):
        # A register entry that is a local path, or empty, must not become "path/rel".
        for prefix in ("", "/mnt/mirror/", r"C:\mirror" + "\\"):
            self.assertIsNone(common.source_url("x", "a", {"x": prefix}), prefix)


class TestFindTool(unittest.TestCase):
    """One loop that had two copies, byte for byte: b2-pack.py's find_rar() and
    iso-second-opinion.py's find_seven_zip(). Each keeps its own candidate list; the rule for
    deciding "is it there" is not the part that differed."""

    def test_a_name_that_cannot_be_executed_is_skipped(self):
        self.assertIsNone(common.find_tool(["definitely-not-a-program-xyzzy"]))

    def test_the_first_one_that_is_there_wins(self):
        real = "cmd" if os.name == "nt" else "sh"
        self.assertEqual(common.find_tool(["definitely-not-a-program-xyzzy", real]), real)

    def test_THE_PROBE_DOES_NOT_WAIT_FOR_INPUT(self):
        """Found by the clock, in this class's own first run: 30.019 s for five tests.

        `cmd` with no arguments and stdin inherited sits waiting to be typed at, so the probe
        blocked until its 30-second timeout. The answer was never wrong -- the program is there
        either way -- it just took the whole timeout to give, once per candidate, in a function
        both callers run before they do anything else. stdin is DEVNULL for the probe now.
        """
        started = time.time()
        real = "cmd" if os.name == "nt" else "sh"
        self.assertEqual(common.find_tool([real]), real)
        self.assertLess(time.time() - started, 5.0)

    def test_nothing_offered_is_nothing_found(self):
        self.assertIsNone(common.find_tool([]))

    def test_RAN_AND_MISBEHAVED_STILL_MEANS_IT_IS_THERE(self):
        """The subtle half, and the one worth having in a single place.

        Called with no arguments rar prints its banner and exits non-zero, and 7z does much the
        same. A SubprocessError from the probe is evidence the program EXISTS. Getting this
        backwards makes a present tool look missing, and both callers refuse to run without one.
        """
        real = subprocess.run
        try:
            subprocess.run = lambda *a, **k: (_ for _ in ()).throw(
                subprocess.TimeoutExpired("x", 30))
            self.assertEqual(common.find_tool(["slow-but-present"]), "slow-but-present")
        finally:
            subprocess.run = real

    def test_and_OSError_alone_means_it_is_not(self):
        real = subprocess.run
        try:
            subprocess.run = lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("nope"))
            self.assertIsNone(common.find_tool(["absent"]))
        finally:
            subprocess.run = real


class TestPageTitle(unittest.TestCase):
    """One home for a regex that had five, and it had already drifted in all five.

    find-html-imposters.py capped the match at 120 characters and fell back to <h1>;
    recheck-decisions.py capped at 44 and did not; redbooks-fetch.py did neither. Nothing was
    broken by the drift, which is exactly why it is worth removing: three spellings of one
    question is how the exclusion comparison came to live in three places with only one of them
    instrumented.
    """

    def test_a_page_names_itself_in_its_title(self):
        self.assertEqual(common.page_title(b"<html><title>Sun Hardware</title>"), "Sun Hardware")

    def test_AND_IN_ITS_H1_WHEN_IT_HAS_NO_TITLE(self):
        """The stock server pages carry no <title> at all -- that is what the fallback is for."""
        self.assertEqual(common.page_title(b"<html><body><h1>It works!</h1>"), "It works!")

    def test_the_title_wins_when_a_page_has_both(self):
        self.assertEqual(common.page_title(b"<title>real</title><h1>heading</h1>"), "real")

    def test_AN_EMPTY_TITLE_FALLS_THROUGH_TO_THE_HEADING(self):
        """The bug the first version of this function had, caught by hand before these tests.

        It picked whichever tag MATCHED first and then emptied the result, so `<title></title>`
        standing ahead of a real <h1> answered None. What is wanted is the first heading that HAS
        TEXT, not the first tag that exists.
        """
        self.assertEqual(common.page_title(b"<title></title><h1>NGC Error !</h1>"), "NGC Error !")
        self.assertEqual(common.page_title(b"<title>   </title><h1>x</h1>"), "x")

    def test_THE_REAL_TITLES_THIS_HAD_TO_READ(self):
        """spider.seds.org's eight `.cgi` files, measured 2026-09-27. Six announce a failure.

        They are the reason this function exists: HTTP 200, a right name -- `.cgi` is in
        PROGRAM_PAGE_EXTENSIONS, so HTML there is expected -- and an error in the body. The only
        thing that tells them apart from the two real pages beside them is what they call
        themselves, in two languages.
        """
        pages = {
            b"<html><head><title>NGC Error !</title></head>": "NGC Error !",
            b"<html><head><title>Erreur NGC !</title></head>": "Erreur NGC !",
            b"<html><title>NGC/IC Error!</title><body><h1>NGC/IC Error!</h1>": "NGC/IC Error!",
            b"<html><head><title>Error in revngcic.cgi</title>": "Error in revngcic.cgi",
            b"<html><head><title>Digital Sky Survey image</title>": "Digital Sky Survey image",
        }
        for body, want in pages.items():
            self.assertEqual(common.page_title(body), want, body)

    def test_markup_inside_the_heading_is_removed(self):
        self.assertEqual(common.page_title(b"<h1><b>NGC/IC Error!</b></h1>"), "NGC/IC Error!")

    def test_whitespace_is_collapsed_including_across_lines(self):
        body = b"<title>two" + bytes([10, 9]) + b"  words</title>"
        self.assertEqual(common.page_title(body), "two words")

    def test_A_MISSING_NAME_IS_NONE_AND_NEVER_THE_EMPTY_STRING(self):
        """Otherwise "" is a second value every caller has to test for separately."""
        for body in (b"<html><body>no headings here", b"<title></title>", b"<h1>  </h1>",
                     b"<h1><b></b></h1>", b"", b"%PDF-1.4"):
            self.assertIsNone(common.page_title(body), repr(body))

    def test_bytes_or_str_because_the_callers_genuinely_differ(self):
        # One reads files, one reads a decoded response body. Making each convert first is how a
        # sixth copy of this gets written.
        self.assertEqual(common.page_title("<title>decoded</title>"), "decoded")
        self.assertEqual(common.page_title(b"<title>raw</title>"), "raw")

    def test_undecodable_bytes_do_not_raise(self):
        # A label for a human to read, never content. Replacement is the right answer.
        self.assertIsNotNone(common.page_title(b"<title>caf" + bytes([0xe9]) + b" latin-1</title>"))

    def test_THERE_IS_NO_LENGTH_CAP_HERE(self):
        """The drift this consolidation removes was two different caps. A caller that wants 44
        characters slices; a cap baked into the regex is a cap the caller cannot see."""
        long_title = b"<title>" + b"a" * 400 + b"</title>"
        self.assertEqual(len(common.page_title(long_title)), 400)

    def test_tag_case_and_attributes_do_not_hide_it(self):
        self.assertEqual(common.page_title(b'<TITLE>upper</TITLE>'), "upper")
        self.assertEqual(common.page_title(b'<h1 class="x" id="y">attrs</h1>'), "attrs")

    def test_the_first_heading_is_the_one(self):
        self.assertEqual(common.page_title(b"<h1>first</h1><h1>second</h1>"), "first")


class TestMagicMismatch(unittest.TestCase):
    """Finding what a crawl stored under the wrong name.

    An error page arrives with status 200 and a matching Content-Length; every counter agrees and
    only the first four bytes disagree.
    """

    def test_a_good_file_is_silent(self):
        for name, head in (("a.pdf", b"%PDF-1.7"), ("a.zip", b"PK\x03\x04..."),
                           ("a.gz", b"\x1f\x8b\x08"), ("a.rpm", b"\xed\xab\xee\xdb"),
                           ("a.rar", b"Rar!\x1a")):
            self.assertIsNone(common.magic_mismatch(name, head), name)

    def test_more_than_one_legal_opening(self):
        # PK\x05\x06 is an EMPTY archive and perfectly legal. A check that knew only the common
        # opening would report every one of them as damage.
        self.assertIsNone(common.magic_mismatch("a.zip", b"PK\x05\x06"))
        self.assertIsNone(common.magic_mismatch("a.z", b"\x1f\x9d"))
        self.assertIsNone(common.magic_mismatch("a.z", b"\x1f\xa0"))
        self.assertIsNone(common.magic_mismatch("a.squash", b"hsqs"))
        self.assertIsNone(common.magic_mismatch("a.squash", b"sqsh"))

    def test_html_under_a_binary_name_is_named_as_such(self):
        why = common.magic_mismatch("package.rpm", b"<!DOCTYPE html>\n<html>")
        self.assertIn("HTML", why)
        self.assertIn(".rpm", why)

    def test_a_saved_directory_listing_is_recognised_by_any_name(self):
        # This is the one that costs a whole subtree: a file occupying a directory's path means
        # nothing below it can ever be written.
        for name in ("files", "rs6000", "index.html", "a.pdf"):
            why = common.magic_mismatch(name, b"<html><title>Index of /pub/x</title>")
            self.assertIn("directory listing", why or "", name)

    def test_an_h1_form_of_the_same_page(self):
        self.assertIsNotNone(common.magic_mismatch("x", b"<h1>Index of /pub</h1>"))

    def test_wrong_bytes_that_are_not_html_still_report(self):
        why = common.magic_mismatch("a.pdf", b"\x00\x01\x02\x03rubbish")
        self.assertIn("signature", why)

    def test_IT_SAYS_WHAT_THE_FILE_IS_WHEN_IT_KNOWS(self):
        """"Does not begin with the .jpg signature" sends somebody to open the file.
        "A .gif under a .jpg name" is finished, and the reader can move on.

        Measured 2026-09-24 over the whole collection: 582 findings are a gzip stored under `.Z`
        and 84 a compress(1) under `.gz` -- old habits rather than damage, and each one was
        costing a reader a look.
        """
        self.assertEqual(common.magic_mismatch("a.jpg", b"GIF89a\x01"), "a .gif under a .jpg name")
        self.assertEqual(common.magic_mismatch("a.z", b"\x1f\x8b\x08"), "a .gz under a .z name")
        self.assertEqual(common.magic_mismatch("a.gz", b"\x1f\x9d\x90"), "a .z under a .gz name")

    def test_and_it_stays_silent_about_a_format_it_does_not_know(self):
        # The point is to name what it recognises, not to guess. An unknown opening still gets
        # the plain answer, because inventing a name would be worse than admitting ignorance.
        why = common.magic_mismatch("a.gif", b"F87ac\x02")     # a GIF missing its first byte
        self.assertEqual(why, "does not begin with the .gif signature")

    def test_AN_IMAGE_SIGNATURE_IS_KNOWN_NOW(self):
        """Added 2026-09-24 after the cost was measured rather than assumed: 114 210 candidate
        files, 22% more reading than --ruins already does, not the "millions" on record."""
        for name, head in (("a.jpg", b"\xff\xd8\xff\xe0"), ("a.jpeg", b"\xff\xd8\xff\xe1"),
                           ("a.png", b"\x89PNG\r\n\x1a\n"), ("a.gif", b"GIF87a"),
                           ("a.gif", b"GIF89a"), ("a.tif", b"II*\x00"), ("a.tiff", b"MM\x00*")):
            self.assertIsNone(common.magic_mismatch(name, head), name)

    def test_AND_A_PICTURE_OF_NOTHING_IS_REPORTED(self):
        # 41 of the 108 image mismatches are files of pure zeros. Whatever else is unclear about
        # an image, one made entirely of zeros is not one.
        why = common.magic_mismatch("a.jpg", b"\x00" * 64)
        self.assertIn("signature", why)

    def test_A_QNX_PACKAGE_IS_A_GZIP(self):
        """The collection said so, not a specification.

        Of the 478 `.qpk` files here -- all in `fsck-vendors/QNX/` -- **452 begin with the gzip
        signature and 26 are entirely zeros. There is no third kind.** Its sibling `.qpm` is the
        manifest and is XML: 446 of 474 text, the other 28 zeros, broken the same way.

        The 26 sat under "no statement possible" for as long as nothing here knew what a `.qpk`
        was, beside 900 intact siblings in one directory. A 473 408-byte file of nothing is not a
        package, and `--empty` now says so: 23 certain losses in `fsck-vendors` where it used to
        report none.  [2026-09-24]
        """
        self.assertEqual(common.MAGIC[".qpk"], (b"\x1f\x8b",))
        self.assertIsNone(common.magic_mismatch("pkg.qpk", b"\x1f\x8b\x08\x00"))
        self.assertIn("signature", common.magic_mismatch("pkg.qpk", bytes(64)))

    def test_and_the_manifest_beside_it_is_NOT_given_a_signature(self):
        """`.qpm` is XML, and XML has no fixed opening worth pinning -- a declaration is optional
        and a root element is not a prefix. Adding a signature nobody can state is how a check
        starts reporting the files it cannot read as damage."""
        self.assertNotIn(".qpm", common.MAGIC)

    def test_the_weak_signatures_were_deliberately_left_out(self):
        """`.bmp` is two bytes and `.ico` is four with three of them zero -- and the collection
        says what that costs: of 279 mismatches across every image extension, 122 were `.ico`
        (OS/2 keeps `BA`, `CI` and `IC` formats there) and 47 `.bmp` (Ultima VI, svgalib). Almost
        none of those is damage."""
        for ext in (".bmp", ".ico", ".webp"):
            self.assertNotIn(ext, common.MAGIC, ext)
            self.assertNotIn(ext, common.CHECKED_EXT, ext)

    def test_every_checked_extension_that_has_a_signature_has_it_in_both_tables(self):
        # CHECKED_EXT decides what is OPENED and MAGIC decides what is JUDGED. `.bff` was in the
        # first and not the second for months, so every fileset came back "no opinion" -- which a
        # caller must not read as "fine". This is that trap, kept shut.
        for ext in common.MAGIC:
            self.assertIn(ext, common.CHECKED_EXT, "%s is judged but never opened" % ext)

    def test_NO_OPINION_IS_NOT_THE_SAME_AS_FINE(self):
        # An extension with no known opening returns None, and so does a good file. The caller
        # must not read the first as a clean bill of health -- which is why the docstring says so.
        self.assertIsNone(common.magic_mismatch("a.xyz", b"anything at all"))
        self.assertIsNone(common.magic_mismatch("README", b"plain text"))

    def test_nothing_read_is_no_verdict(self):
        self.assertIsNone(common.magic_mismatch("a.pdf", b""))

    def test_the_extension_check_is_case_insensitive(self):
        self.assertIsNone(common.magic_mismatch("A.PDF", b"%PDF-1.4"))
        self.assertIsNotNone(common.magic_mismatch("A.PDF", b"<html>"))

    def test_every_listed_magic_accepts_its_own_bytes(self):
        for ext, openings in common.MAGIC.items():
            for head in openings:
                self.assertIsNone(common.magic_mismatch("x" + ext, head + b"rest"),
                                  "%s %r" % (ext, head))


class TestEmptySha(unittest.TestCase):
    def test_it_is_the_digest_of_nothing(self):
        self.assertEqual(common.EMPTY_SHA256, common.sha256_bytes(b""))

class TestSumsLine(unittest.TestCase):
    """The format three tools wrote out by hand, in three spellings."""

    def test_one_space_and_a_star(self):
        self.assertEqual(common.sums_line("ab" * 32, "a/b.txt"), "ab" * 32 + " *a/b.txt\n")

    def test_read_manifest_reads_back_what_sums_line_writes(self):
        # The pair that matters: a writer and a reader that disagree produce a manifest which
        # verifies against nothing, and says so only after a full re-hash.
        rows = {"a/b.txt": "11" * 32, "deep/TALK.": "22" * 32, "x y/z 1.bin": "33" * 32}
        tmp = tempfile.mkdtemp(prefix="common-test-")
        try:
            p = os.path.join(tmp, ".sha256sum")
            with io.open(p, "w", encoding="utf-8", newline="") as fh:
                for rel, digest in sorted(rows.items()):
                    fh.write(common.sums_line(digest, rel))
            back = {rel: digest for rel, _size, digest in common.read_manifest(p)}
            self.assertEqual(back, rows)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_trailing_dot_survives_the_round_trip(self):
        # 21 files in these mirrors end in a dot. A format that loses one reports a present file
        # as missing.
        line = common.sums_line("aa" * 32, "bitsavers/TALK.")
        self.assertTrue(line.endswith("*bitsavers/TALK.\n"))

    def test_the_gnu_escape_is_written_even_though_it_cannot_fire_here(self):
        # Windows forbids both characters, so this never occurs in this collection. It is
        # implemented so the format stays correct rather than accidentally correct.
        self.assertTrue(common.sums_line("aa" * 32, "a\\b").startswith("\\"))
        self.assertTrue(common.sums_line("aa" * 32, "a\nb").startswith("\\"))


class TestReadMarker(unittest.TestCase):
    """Only the header is data. Everything past the first blank line is for a human."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.path = os.path.join(self.tmp, common.COMPLETE_MARKER)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, text):
        with io.open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def test_the_header(self):
        self.write("archive       oldskool\nfiles         77628\nbytes         149225768625\n")
        rec = common.read_marker(self.path)
        self.assertEqual(rec["archive"], "oldskool")
        self.assertEqual(int(rec["files"]), 77628)
        self.assertEqual(int(rec["bytes"]), 149225768625)

    def test_PROSE_AFTER_THE_BLANK_LINE_IS_NOT_PARSED(self):
        # The incident this exists for: a marker written by hand explained the archive's history
        # in lines beginning "files" and "bytes", the reader took those for the header, and the
        # run died on int("7826  ->  94899").
        self.write("files         77628\nbytes         149225768625\n"
                   "\n"
                   "files         7826  ->  94899 after the second pass\n"
                   "bytes         nonsense, on purpose\n")
        rec = common.read_marker(self.path)
        self.assertEqual(rec["files"], "77628")
        self.assertEqual(rec["bytes"], "149225768625")

    def test_values_stay_strings(self):
        # A checker and a report do not make the same decision about a missing key, so neither
        # decision is made here.
        self.write("files         12\n")
        self.assertIsInstance(common.read_marker(self.path)["files"], str)

    def test_a_value_may_contain_spaces(self):
        self.write("source        https://h/a b/c\ncompleted     2026-09-04 11:22:33\n")
        rec = common.read_marker(self.path)
        self.assertEqual(rec["source"], "https://h/a b/c")
        self.assertEqual(rec["completed"], "2026-09-04 11:22:33")

    def test_a_bare_word_is_ignored_rather_than_crashing(self):
        self.write("files 3\nrubbish\nbytes 4\n")
        self.assertEqual(common.read_marker(self.path), {"files": "3", "bytes": "4"})

    def test_a_missing_marker_is_an_empty_record_not_an_exception(self):
        self.assertEqual(common.read_marker(os.path.join(self.tmp, "nope")), {})


class TestIndexRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.idx = os.path.join(self.tmp, common.INDEX_FILE)
        self.sums = os.path.join(self.tmp, common.SUMS_FILE)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rows(self):
        return {"b.txt": (10, 111, "aa" * 32),
                "a/TALK.": (0, 222, common.EMPTY_SHA256),
                "z z/x.bin": (4096, 333, "cc" * 32)}

    def test_what_is_written_is_what_is_read(self):
        common.write_index(self.idx, self.sums, self.rows())
        self.assertEqual(common.read_index(self.idx), self.rows())

    def test_THE_SUMS_FILE_IS_DERIVED_NOT_WRITTEN_TWICE(self):
        # Two files from one ordered list. Writing both from separate loops is how they come to
        # disagree, and nothing downstream can tell which one is right.
        common.write_index(self.idx, self.sums, self.rows())
        from_csv = {rel: d for rel, (_s, _m, d) in sorted(self.rows().items())}
        from_sums = {rel: d for rel, _size, d in common.read_manifest(self.sums)}
        self.assertEqual(from_sums, from_csv)

    def test_both_files_are_sorted_identically(self):
        common.write_index(self.idx, self.sums, self.rows())
        sums_order = [rel for rel, _s, _d in common.read_manifest(self.sums)]
        self.assertEqual(sums_order, sorted(self.rows()))

    def test_NO_TMP_FILE_SURVIVES(self):
        # A half-written manifest still looks like a manifest.
        common.write_index(self.idx, self.sums, self.rows())
        self.assertEqual(sorted(os.listdir(self.tmp)),
                         sorted([common.INDEX_FILE, common.SUMS_FILE]))

    def test_it_overwrites_rather_than_appending(self):
        common.write_index(self.idx, self.sums, self.rows())
        common.write_index(self.idx, self.sums, {"only.txt": (1, 2, "dd" * 32)})
        self.assertEqual(list(common.read_index(self.idx)), ["only.txt"])

    def test_a_missing_index_is_empty_NOT_an_error(self):
        # The index is a cache of work already done and every row is revalidated before reuse,
        # so damage costs time, never correctness. Refusing to start would be the wrong answer.
        self.assertEqual(common.read_index(os.path.join(self.tmp, "nope.csv")), {})

    def test_a_truncated_index_yields_the_rows_it_still_has(self):
        with io.open(self.idx, "w", encoding="utf-8", newline="") as fh:
            fh.write("path,size,mtime_ns,sha256\ngood.txt,1,2,%s\nbad.txt,notanumber,2,x\n"
                     % ("aa" * 32))
        self.assertEqual(list(common.read_index(self.idx)), ["good.txt"])

    def test_rubbish_is_empty_rather_than_fatal(self):
        with io.open(self.idx, "w", encoding="utf-8", newline="") as fh:
            fh.write("this is not a csv at all\n")
        self.assertEqual(common.read_index(self.idx), {})

    def test_an_empty_file_keeps_its_real_size_of_zero(self):
        common.write_index(self.idx, self.sums, self.rows())
        self.assertEqual(common.read_index(self.idx)["a/TALK."][0], 0)


class TestIterTree(unittest.TestCase):
    """What counts as content, and what only describes it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        for rel in ("real.txt", "TALK.", "sub/deep.bin",
                    "half.iso.part", "bad.iso.suspect", "short.iso.suspect.superseded",
                    common.COMPLETE_MARKER, common.SUMS_FILE, "RENAMED.txt",
                    "sub/" + common.COMPLETE_MARKER, "SOMETHING.PART"):
            p = os.path.join(self.tmp, *rel.split("/"))
            if not os.path.isdir(os.path.dirname(p)):
                os.makedirs(os.path.dirname(p))
            # THROUGH long_path TO CREATE IT: Windows strips a trailing dot while OPENING, so a
            # plain open() here makes a file called `TALK` and the test then proves nothing.
            with io.open(common.long_path(p), "w", encoding="utf-8") as fh:
                fh.write("x")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def names(self):
        return {rel for rel, _full in common.iter_tree(self.tmp)}

    def test_content_is_yielded(self):
        self.assertIn("real.txt", self.names())
        self.assertIn("sub/deep.bin", self.names())

    def test_a_trailing_dot_is_not_lost(self):
        self.assertIn("TALK.", self.names())

    def test_unfinished_transfers_are_not_content(self):
        for n in ("half.iso.part", "bad.iso.suspect", "short.iso.suspect.superseded"):
            self.assertNotIn(n, self.names(), n)

    def test_SUPERSEDED_IS_NOT_SUSPECT(self):
        # `X.suspect.superseded` does not end in `.suspect`. A two-suffix test let 15 of them
        # back in and three archives were reported as changed for pure bookkeeping.
        self.assertNotIn("short.iso.suspect.superseded", self.names())

    def test_UPPERCASE_PART_IS_CONTENT(self):
        # A split archive volume from the uppercase era, not a half download. Folding case here
        # would drop it from a count that markers on disk were already written against, and every
        # one of them would then report a mismatch for a change nobody made.
        self.assertIn("SOMETHING.PART", self.names())
        self.assertTrue(common.is_partial("SOMETHING.PART"))   # the report says otherwise, and may

    def test_our_own_files_are_skipped_at_the_top(self):
        self.assertNotIn(common.COMPLETE_MARKER, self.names())
        self.assertNotIn(common.SUMS_FILE, self.names())

    def test_THE_NARROW_SET_IS_THE_ONE_USED(self):
        # RENAMED.txt is bookkeeping but NOT an own file, because four markers on disk counted it.
        self.assertIn("RENAMED.txt", self.names())
        self.assertTrue(common.is_bookkeeping_file("RENAMED.txt"))

    def test_only_at_the_top(self):
        # An archive is entitled to contain a file of that name one directory down, and that one
        # is content.
        self.assertIn("sub/" + common.COMPLETE_MARKER, self.names())

    def test_forward_slashes_on_every_platform(self):
        # Written verbatim into a file `sha256sum -c` has to read on a Unix box.
        self.assertFalse(any("\\" in n for n in self.names()))

    def test_a_trailing_separator_on_the_root_changes_nothing(self):
        with_sep = {rel for rel, _f in common.iter_tree(self.tmp + os.sep)}
        self.assertEqual(with_sep, self.names())

    def test_the_own_set_can_be_overridden(self):
        self.assertIn(common.COMPLETE_MARKER,
                      {rel for rel, _f in common.iter_tree(self.tmp, own_files=frozenset())})


class TestScanTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        for rel, size in (("a.txt", 3), ("sub/b.bin", 5), ("TALK.", 7)):
            p = os.path.join(self.tmp, *rel.split("/"))
            if not os.path.isdir(os.path.dirname(p)):
                os.makedirs(os.path.dirname(p))
            with io.open(common.long_path(p), "wb") as fh:
                fh.write(b"x" * size)
        with io.open(os.path.join(self.tmp, common.COMPLETE_MARKER), "w") as fh:
            fh.write("ignored")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_counts_content_and_its_bytes(self):
        self.assertEqual(common.scan_tree(self.tmp), (3, 15))

    def test_A_DOTTED_NAME_IS_MEASURED_NOT_SKIPPED(self):
        # Without long_path, getsize fails on `TALK.` with "the system cannot find the file" for a
        # file the walk has just handed us. 21 such files were absent from every figure this
        # feeds -- including the one a later check compares the tree against.
        n, total = common.scan_tree(self.tmp)
        self.assertEqual(n, 3)
        self.assertEqual(total, 15)

    def test_AN_UNREADABLE_FILE_IS_REPORTED_NOT_SWALLOWED(self):
        # Swallowing was the worse half of that bug: a stat that fails silently is a file the
        # marker never counts and a check never misses, so a tree could lose files and report
        # unchanged forever.
        seen = []
        real = os.path.getsize

        def boom(path):
            if path.endswith("b.bin"):
                raise OSError(1920, "the symlink target does not resolve")
            return real(path)

        with mock.patch("os.path.getsize", boom):
            n, total = common.scan_tree(self.tmp, report=lambda rel, exc: seen.append(rel))
        self.assertEqual(len(seen), 1)
        self.assertEqual(n, 2)          # loud, not fatal: the other files were still counted
        self.assertEqual(total, 10)

    def test_the_figures_match_what_iter_tree_yields(self):
        # The count and the hash pass must not be able to disagree about the set of files.
        self.assertEqual(common.scan_tree(self.tmp)[0], len(list(common.iter_tree(self.tmp))))


class TestHashTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.entries = []
        for i in range(7):
            p = os.path.join(self.tmp, "f%d.bin" % i)
            with io.open(p, "wb") as fh:
                fh.write(b"%d" % i)
            st = os.stat(p)
            self.entries.append(("f%d.bin" % i, p, st.st_size, st.st_mtime_ns))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_hashes_everything_into_rows(self):
        rows = {}
        done, done_bytes, failed, _elapsed = common.hash_tree(
            self.entries, rows, workers=3, interval=1e9, checkpoint=lambda: None)
        self.assertEqual(done, 7)
        self.assertEqual(done_bytes, 7)
        self.assertEqual(failed, [])
        self.assertEqual(rows["f3.bin"][2], common.sha256_bytes(b"3"))

    def test_rows_is_mutated_in_place(self):
        rows = {"kept.txt": (1, 2, "aa" * 32)}
        common.hash_tree(self.entries, rows, 2, 1e9, lambda: None)
        self.assertIn("kept.txt", rows)          # a previous index is extended, not replaced
        self.assertEqual(len(rows), 8)

    def test_THE_CHECKPOINT_RUNS_EVEN_WHEN_THE_PASS_DIES(self):
        # Without the finally, the work between the last timed checkpoint and the interruption is
        # simply lost -- which is the whole claim that a partial index is a valid index.
        calls = []
        entries = list(self.entries)

        def exploding_sha(path):
            raise KeyboardInterrupt("as if someone pressed ctrl-c")

        with mock.patch.object(common, "sha256_file", exploding_sha):
            with self.assertRaises(KeyboardInterrupt):
                common.hash_tree(entries, {}, 1, 1e9, lambda: calls.append(1))
        self.assertGreaterEqual(len(calls), 1)

    def test_an_unreadable_file_is_collected_not_fatal(self):
        real = common.sha256_file          # held BEFORE the patch, or one_bad calls itself

        def one_bad(path):
            if path.endswith("f2.bin"):
                raise OSError(13, "permission denied")
            return real(path)

        with mock.patch.object(common, "sha256_file", one_bad):
            done, _b, failed, _e = common.hash_tree(self.entries, {}, 2, 1e9, lambda: None)
        self.assertEqual(done, 6)
        self.assertEqual([rel for rel, _why in failed], ["f2.bin"])

    def test_batching_does_not_change_the_result(self):
        # One batch in flight at a time is what keeps a 190 000-entry tree from becoming a
        # 190 000-entry list of futures.
        a, b = {}, {}
        common.hash_tree(self.entries, a, 2, 1e9, lambda: None, batch_size=1)
        common.hash_tree(self.entries, b, 2, 1e9, lambda: None, batch_size=1000)
        self.assertEqual(a, b)

    def test_an_empty_tree_is_not_a_division_by_zero(self):
        done, done_bytes, failed, _e = common.hash_tree([], {}, 2, 0.0, lambda: None)
        self.assertEqual((done, done_bytes, failed), (0, 0, []))

    def test_progress_is_a_callback_so_a_library_does_not_own_the_screen(self):
        seen = []
        common.hash_tree(self.entries, {}, 1, 0.0, lambda: None, label="idx ",
                         report=lambda *a: seen.append(a))
        self.assertTrue(seen)
        self.assertEqual(seen[0][0], "idx ")






class TestWindowsReserved(unittest.TestCase):
    def test_the_whole_list(self):
        self.assertEqual(len(common.WINDOWS_RESERVED), 4 + 9 + 9)
        for n in ("CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"):
            self.assertIn(n, common.WINDOWS_RESERVED)

    def test_it_is_uppercase_so_callers_must_fold(self):
        self.assertNotIn("con", common.WINDOWS_RESERVED)


class TestSafeTarSegment(unittest.TestCase):
    """Three answers to one question, and each one has to stay different from the other two."""

    def test_it_does_what_safe_name_does(self):
        for bad in ('<', '>', ':', '"', '|', '?', '*'):
            self.assertEqual(common.safe_tar_segment("a%sb" % bad), "a_b", bad)

    def test_AND_THE_BACKSLASH_TOO(self):
        # A tar is a Unix artefact and `\` is an ordinary character in a Unix filename. NTFS reads
        # it as a separator, so a member named `dir\index.html` -- ONE file -- would land on the
        # real `dir/index.html` and the second write would destroy the first.
        self.assertEqual(common.safe_tar_segment("n12003204gnsr\\index.html"),
                         "n12003204gnsr_index.html")

    def test_THE_TWO_MEMBERS_FROM_THE_HP_TAR_STAY_TWO_FILES(self):
        # h18002.www1.hp.com_20080527.tar carries both spellings, and they are different files.
        a = "/".join(common.safe_tar_segment(s) for s in "n12003204gnsr/index.html".split("/"))
        b = "/".join(common.safe_tar_segment(s)
                     for s in "n12003204gnsr\\index.html".split("/"))
        self.assertNotEqual(a, b)

    def test_SAFE_NAME_WAS_WIDENED_TO_MATCH_AFTER_ALL(self):
        r"""This test said the opposite until 2026-09-23, and said why. [reversed]

        "Widening UNSAFE would repath every existing mirror to fix a case the HTTP crawler has
        never produced." Measured: no path in the 98 archive indexes holds a backslash, so it
        repaths nothing -- and local_path() unquotes `%5C` into a real separator, so the crawler
        can produce exactly that case. It was a path traversal; see
        TestTheRegexesToolsImportDirectly.

        THE TWO FUNCTIONS NOW AGREE ON THE BACKSLASH and still differ on everything else -- a tar
        member and a url segment are not the same kind of name, which is why both exist.
        """
        self.assertEqual(common.safe_name("a\\b"), "a_b")
        self.assertEqual(common.safe_name("a\\b"), common.safe_tar_segment("a\\b"))
        # ... and they still part ways here: a tar's forward slash is a real separator.
        self.assertEqual(common.safe_tar_segment("a/b"), "a/b")
        self.assertEqual(common.safe_name("a/b"), "a/b")

    def test_AND_NEITHER_IS_THE_WIKI_RULE_THE_SAME_AS_EITHER(self):
        # mediawiki_filename replaces the forward slash as well, because a title is not a path.
        # safe_tar_segment must NOT: a tar's forward slash is a real separator and the caller
        # splits on it before calling this.
        self.assertEqual(common.safe_tar_segment("a/b"), "a/b")
        self.assertEqual(mediawiki.mediawiki_filename("a/b", ext="")[0], "a_b")

    def test_an_ordinary_segment_is_untouched(self):
        for s in ("index.html", "TALK.", "a b c", "README"):
            self.assertEqual(common.safe_tar_segment(s), s, s)

    def test_a_control_character_goes_too(self):
        self.assertEqual(common.safe_tar_segment("a\x01b"), "a_b")


class TestComparablePath(unittest.TestCase):
    """One spelling, because two records of the same file are written by different hands."""

    def test_separators_go_forward(self):
        self.assertEqual(common.comparable_path("a\\b\\c.txt"), "a/b/c.txt")

    def test_case_is_folded(self):
        self.assertEqual(common.comparable_path("Packages/SRPMS.TAR.GZ"), "packages/srpms.tar.gz")

    def test_a_leading_dot_slash_goes(self):
        self.assertEqual(common.comparable_path("./a/b"), "a/b")
        self.assertEqual(common.comparable_path(".\\a\\b"), "a/b")

    def test_a_repeated_one_goes_too(self):
        self.assertEqual(common.comparable_path("././a"), "a")

    def test_THE_PREFIX_IS_REMOVED_NOT_A_SET_OF_CHARACTERS(self):
        # str.lstrip("./") takes a SET. The five hand-written copies this replaces all used it,
        # so `.gitignore` was compared under the name `gitignore` -- a name it does not have.
        # None of the 34 entries in the register were affected, which is why this could be
        # corrected rather than merely recorded.
        self.assertEqual(common.comparable_path(".gitignore"), ".gitignore")
        self.assertEqual(common.comparable_path("...odd"), "...odd")
        self.assertEqual(common.comparable_path("../x"), "../x")
        self.assertNotEqual(common.comparable_path(".gitignore"), ".gitignore".lstrip("./"))

    def test_an_ordinary_path_is_only_lowercased(self):
        self.assertEqual(common.comparable_path("packages/srpms.tar.gz"), "packages/srpms.tar.gz")

    def test_it_is_idempotent(self):
        # It is applied on both sides of a comparison, sometimes twice on one of them.
        once = common.comparable_path(".\\A\\B.TXT")
        self.assertEqual(common.comparable_path(once), once)

    def test_the_empty_path(self):
        self.assertEqual(common.comparable_path(""), "")

    def test_a_trailing_dot_SURVIVES(self):
        # 21 files in these mirrors end in one, and a comparison that drops it reports a present
        # file as missing -- the same defect long_path and relative_to exist to avoid.
        self.assertEqual(common.comparable_path("bitsavers/TALK."), "bitsavers/talk.")


class TestRetiredMatchesEverySpelling(unittest.TestCase):
    """The register and the manifests are written by different hands; both must still match."""

    def setUp(self):
        self.mirror = common.load_mirror()
        self.archive, self.entries = next(
            (a, e) for a, e in self.mirror.RETIRED.items() if e)

    def test_a_recorded_path_is_found_as_written(self):
        path, why = self.entries[0]
        self.assertEqual(self.mirror.is_retired(self.archive, path), why)

    def test_and_under_every_spelling_a_manifest_might_use(self):
        path, _why = self.entries[0]
        for variant in (path, "./" + path, path.replace("/", "\\"), path.upper()):
            self.assertIsNotNone(self.mirror.is_retired(self.archive, variant), variant)

    def test_MATCHING_IS_EXACT_NOT_A_PREFIX(self):
        # A retired file is a decision about ONE file. A prefix rule would quietly grow into an
        # exclusion nobody chose.
        path, _why = self.entries[0]
        self.assertIsNone(self.mirror.is_retired(self.archive, path + "x"))
        self.assertIsNone(self.mirror.is_retired(self.archive, "prefix/" + path))

    def test_an_unknown_archive_holds_nothing_back(self):
        self.assertIsNone(self.mirror.is_retired("no-such-archive", "anything"))


BACKSLASH = chr(92)      # spelled this way so no quoting layer between here and the file can eat it


def as_posix():
    """Run a block as though this were Linux, ON ANY PLATFORM.

    The separator rules used to be pinned only by @on_windows tests, so the half of the behaviour
    that is wrong on Linux was pinned by nothing and ran only in CI -- where a failure arrives
    minutes later and in somebody else's output. Both halves are exercised here, on whatever
    machine is in front of you.
    """
    return mock.patch.multiple(os, name="posix", sep="/")


def as_windows():
    return mock.patch.multiple(os, name="nt", sep=BACKSLASH)


class TestRelativeToSeparators(unittest.TestCase):
    """Which characters are separators is a PLATFORM question, and it was answered Windows-only."""

    def test_A_BACKSLASH_IS_CONTENT_ON_POSIX(self):
        # A file legitimately called `weird\name.txt` on Linux came back as `weird/name.txt`,
        # which is not a file at all but a path into a directory that does not exist.
        name = "weird" + BACKSLASH + "name.txt"
        with as_posix():
            self.assertEqual(common.relative_to("/srv/m", "/srv/m/" + name), name)

    def test_and_a_separator_on_windows(self):
        with as_windows():
            self.assertEqual(common.relative_to("C:" + BACKSLASH + "a",
                                                "C:" + BACKSLASH + "a" + BACKSLASH + "b.txt"),
                             "b.txt")

    def test_a_leading_backslash_is_not_stripped_on_posix(self):
        name = BACKSLASH + "odd"
        with as_posix():
            self.assertEqual(common.relative_to("/srv/m", "/srv/m/" + name), name)

    def test_a_root_ending_in_a_backslash_keeps_it_on_posix(self):
        # `rstrip` took it off on every platform too. On Linux that is a directory called `m\`.
        root = "/srv/m" + BACKSLASH
        with as_posix():
            self.assertEqual(common.relative_to(root, root + "/f.txt"), "f.txt")

    def test_the_windows_answer_is_unchanged_by_the_fix(self):
        # The whole point: identical where it was already right.
        with as_windows():
            self.assertEqual(common.relative_to("C:" + BACKSLASH + "a",
                                                "C:" + BACKSLASH + "a" + BACKSLASH + "b"
                                                + BACKSLASH + "c.txt"), "b/c.txt")
            self.assertEqual(common.relative_to("C:" + BACKSLASH + "A",
                                                "c:" + BACKSLASH + "a" + BACKSLASH + "b.txt"),
                             "b.txt")

    def test_case_is_NOT_folded_on_posix(self):
        # Two files whose names differ only in case are two files there.
        with as_posix():
            self.assertIsNone(common.relative_to("/srv/M", "/srv/m/f.txt"))

    def test_a_trailing_dot_survives_on_both(self):
        with as_posix():
            self.assertEqual(common.relative_to("/a", "/a/TALK."), "TALK.")
        with as_windows():
            self.assertEqual(common.relative_to("C:" + BACKSLASH + "a",
                                                "C:" + BACKSLASH + "a" + BACKSLASH + "TALK."),
                             "TALK.")

    def test_the_root_itself_is_the_empty_string_not_a_dot(self):
        # Worth pinning because a caller that wants "." has to say so: move-mirror.py's own copy
        # returns "." for this and compares against it in three places.
        with as_posix():
            self.assertEqual(common.relative_to("/a/b", "/a/b"), "")


JAPANESE = "ドライバ一覧.html"      # a driver index, realistic for this tree


def console(encoding):
    """A stand-in for a console with a given encoding, readable afterwards."""
    raw = io.BytesIO()
    return io.TextIOWrapper(raw, encoding=encoding, newline="\n"), raw


class TestSay(unittest.TestCase):
    """The screen and the record get different text, and that is the whole point."""

    def test_it_prints(self):
        out, raw = console("utf-8")
        common.say("hello", stream=out)
        self.assertEqual(raw.getvalue().decode("utf-8"), "hello\n")

    def test_A_NAME_THE_CONSOLE_CANNOT_ENCODE_DOES_NOT_KILL_THE_RUN(self):
        # A Windows console is cp1252. A plain print() of this name raises UnicodeEncodeError and
        # takes the whole pass with it -- hours of hashing lost to a filename.
        out, raw = console("cp1252")
        common.say("found " + JAPANESE, stream=out)          # must not raise
        self.assertIn(b"found ", raw.getvalue())

    def test_and_a_plain_print_WOULD_have(self):
        # The test above is worth nothing unless the danger is real. This is the danger.
        out, _raw = console("cp1252")
        with self.assertRaises(UnicodeEncodeError):
            print(JAPANESE, file=out)
            out.flush()

    def test_THE_LOG_KEEPS_THE_REAL_CHARACTERS(self):
        # The log is opened as UTF-8 by every caller, and it is the copy anyone reads afterwards.
        out, screen = console("cp1252")
        log = io.StringIO()
        common.say("found " + JAPANESE, log=log, stream=out)
        self.assertEqual(log.getvalue(), "found " + JAPANESE + "\n")
        self.assertNotIn(JAPANESE.encode("utf-8"), screen.getvalue())

    def test_a_console_that_can_encode_it_gets_it_unchanged(self):
        out, raw = console("utf-8")
        common.say(JAPANESE, stream=out)
        self.assertEqual(raw.getvalue().decode("utf-8"), JAPANESE + "\n")

    def test_no_log_is_fine(self):
        out, raw = console("utf-8")
        common.say("x", stream=out)
        common.say("y", log=None, stream=out)
        self.assertEqual(raw.getvalue().decode("utf-8"), "x\ny\n")

    def test_the_log_is_flushed_not_merely_buffered(self):
        # A verdict that exists only in a buffer is a verdict lost to the interruption it was
        # meant to survive.
        out, _raw = console("utf-8")
        flushed = []

        class Recording(io.StringIO):
            def flush(self):
                flushed.append(self.getvalue())

        log = Recording()
        common.say("line", log=log, stream=out)
        self.assertEqual(flushed, ["line\n"])

    def test_nordic_survives_cp1252_untouched(self):
        # ndwiki is Norwegian; those characters ARE in cp1252 and must not be mangled.
        out, raw = console("cp1252")
        common.say("Blåbærsyltetøy.txt", stream=out)
        self.assertEqual(raw.getvalue().decode("cp1252"), "Blåbærsyltetøy.txt\n")


class TestTheContract(unittest.TestCase):
    """The rules the module docstring states, checked rather than asserted in prose.

    ONE PROVIDER, FORTY CLIENTS, ONE HAND WRITING BOTH. That is the situation in which a surface
    drifts without anybody deciding to change it: a parameter named a little differently here, a
    table that turns out to be writable there, and six months later no two callers agree about
    what the library promises. A promise nothing enforces is one that has already been broken
    somewhere.
    """

    HERE = os.path.dirname(os.path.abspath(__file__))

    # EVERY LIBRARY MODULE, not just common. The split on 2026-09-23 moved pmwiki_* into its own
    # module, and for as long as this list said only "common" the new module had no contract at
    # all: nothing checked its surface, its docstrings or its parameter names. A split that
    # quietly narrows what is enforced has made the code worse rather than tidier, so this list
    # grows with every module and the generic rules below loop over it.
    LIBRARIES = ("common", "dokuwiki", "mediawiki", "pdf", "pmwiki", "robots", "wayback")

    def test_EVERY_MODULE_HERE_IS_ALSO_MUTATED(self):
        """The rules below are asserted for seven modules. This checks they are DEMONSTRATED for
        seven, which is a different claim and was false until 2026-09-24.

        `contract-mutations.py` breaks each rule on purpose and reports any that nothing notices.
        Until that date it reached `common.py` and `mediawiki.py` only, so for the other five
        these loops were a comment with a runtime cost -- the exact thing that script exists to
        refuse, applied to the script itself.

        It now generates one mutation per module from its own LIBRARIES, and this test is why
        that list cannot drift from this one: two copies of the same tuple is the failure it was
        meant to prevent, one file along. An eighth module added here and forgotten there would
        otherwise be un-demonstrated again, silently.
        """
        mutations = common.load_peer("contract-mutations.py", "_mutations")
        self.assertEqual(tuple(mutations.LIBRARIES), self.LIBRARIES)
        aimed = {os.path.basename(target) for _l, target, _o, _n in mutations.MUTATIONS}
        for name in self.LIBRARIES:
            self.assertIn(name + ".py", aimed,
                          "%s has no mutation aimed at it: its contract is asserted, not shown"
                          % name)

    def test_and_every_mutation_target_is_restored(self):
        """The one failure that script must not have, since it edits the library in place.

        Its backup set used to be a hand-written dict of three files beside a table of seven
        mutations. The moment a mutation named a fourth file, that file would have been written
        to and never put back.
        """
        mutations = common.load_peer("contract-mutations.py", "_mutations2")
        src = self.source("contract-mutations.py")
        self.assertIn("for _label, target, _old, _new in MUTATIONS:", src)
        self.assertNotIn("backups = {LIB:", src)
        targets = {t for _l, t, _o, _n in mutations.MUTATIONS}
        self.assertGreater(len(targets), 3, "the point is that it is no longer three files")

    def source(self, name="common.py"):
        with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def tree(self, name="common.py"):
        return ast.parse(self.source(name))

    def libraries(self):
        """-> (name, imported module, parsed tree) for each library module."""
        for name in self.LIBRARIES:
            yield name, importlib.import_module(name), self.tree(name + ".py")

    def clients(self):
        """Everything that USES a library. A library module is not a client of itself."""
        libs = {n + ".py" for n in self.LIBRARIES}
        for name in sorted(os.listdir(self.HERE)):
            if name.endswith(".py") and name not in libs:
                yield name, ast.parse(self.source(name))

    # ---------------------------------------------------------------- what is exported

    def test_every_exported_name_exists(self):
        for name, mod, _tree in self.libraries():
            missing = [n for n in mod.__all__ if not hasattr(mod, n)]
            self.assertEqual(missing, [], name)

    def test_no_name_is_exported_twice(self):
        for name, mod, _tree in self.libraries():
            dupes = sorted({n for n in mod.__all__ if mod.__all__.count(n) > 1})
            self.assertEqual(dupes, [], name)

    def test_AND_NO_NAME_IS_EXPORTED_BY_TWO_MODULES(self):
        # A name available from two places is a name whose home nobody can tell, and the whole
        # point of the split was to give each one exactly one.
        seen, clash = {}, []
        for name, mod, _tree in self.libraries():
            for n in mod.__all__:
                if n in seen:
                    clash.append((n, seen[n], name))
                seen[n] = name
        self.assertEqual(clash, [])

    def test_NOTHING_PUBLIC_EXISTS_OUTSIDE_THE_SURFACE(self):
        # A helper that is public by accident becomes a client's dependency by accident, and then
        # it cannot be changed without breaking something nobody knew was there.
        for name, mod, tree in self.libraries():
            public = set()
            for n in tree.body:
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_"):
                    public.add(n.name)
                if isinstance(n, ast.Assign):
                    for tg in n.targets:
                        if isinstance(tg, ast.Name) and not tg.id.startswith("_") \
                                and tg.id != "__all__":
                            public.add(tg.id)
            self.assertEqual(sorted(public - set(mod.__all__) - {"main"}), [], name)

    def test_NO_CLIENT_REACHES_PAST_THE_SURFACE(self):
        exported = {lib: set(mod.__all__) for lib, mod, _t in self.libraries()}
        leaks = []
        for name, tree in self.clients():
            for n in ast.walk(tree):
                if isinstance(n, ast.ImportFrom) and n.module in exported:
                    leaks += [(name, "%s.%s" % (n.module, a.name))
                              for a in n.names if a.name not in exported[n.module]]
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                        and n.value.id in exported and not n.attr.startswith("__") \
                        and n.attr not in exported[n.value.id]:
                    leaks.append((name, "%s.%s" % (n.value.id, n.attr)))
        self.assertEqual(leaks, [])

    def test_every_exported_callable_says_what_it_does(self):
        for name, mod, _tree in self.libraries():
            nodoc = sorted(n for n in mod.__all__
                           if callable(getattr(mod, n)) and not getattr(mod, n).__doc__)
            self.assertEqual(nodoc, [], name)

    # ---------------------------------------------------------------- tables are read-only

    def test_NO_EXPORTED_TABLE_CAN_BE_REWRITTEN_BY_A_CLIENT(self):
        # These tools load one another as modules inside ONE process. An exported dict is shared
        # mutable state: a client that "just adds an entry" changes what every other client in
        # that process decides about a file, and nothing records that it happened.
        for name, mod, _tree in self.libraries():
            writable = sorted(n for n in mod.__all__
                              if isinstance(getattr(mod, n), (dict, list, set, bytearray)))
            self.assertEqual(writable, [], name)

    def test_and_the_two_tables_really_refuse(self):
        for table in (common.MAGIC, common.EXTENSION_FOR_TYPE):
            with self.assertRaises(TypeError):
                table["x"] = "y"

    def test_the_sets_are_frozen(self):
        for name in ("OWN_FILES", "BOOKKEEPING_FILES", "CHECKED_EXT", "RETRY_STATUS",
                     "WINDOWS_RESERVED"):
            self.assertIsInstance(getattr(common, name), frozenset, name)

    # ---------------------------------------------------------------- one handwriting

    def test_NO_PARAMETER_SHADOWS_AN_EXPORTED_NAME(self):
        # `say` was a parameter in three functions AND an exported helper, so inside those three
        # bodies the library's own say() was unreachable -- and a reader could not tell.
        clashes = []
        for name, mod, tree in self.libraries():
            exported = set(mod.__all__)
            for n in ast.walk(tree):
                if isinstance(n, ast.FunctionDef):
                    for a in list(n.args.args) + list(n.args.kwonlyargs):
                        if a.arg in exported:
                            clashes.append((name, n.name, a.arg))
        self.assertEqual(clashes, [])

    def test_a_progress_callback_is_always_called_report(self):
        # One concept, one name. It was `report` in one function and `say` in three.
        OTHER_NAMES = {"say", "callback", "cb", "on_progress", "notify", "printer", "emit",
                       "progress", "log_fn", "out_fn"}
        found = []
        for name, _mod, tree in self.libraries():
            for n in ast.walk(tree):
                if isinstance(n, ast.FunctionDef):
                    for a in list(n.args.args) + list(n.args.kwonlyargs):
                        if a.arg in OTHER_NAMES:
                            found.append((name, n.name, a.arg))
        self.assertEqual(found, [])

    def test_what_counts_as_ours_is_spelled_the_same_in_every_walker(self):
        for fn in ("iter_files", "iter_tree", "scan_tree"):
            f = getattr(common, fn)
            args = f.__code__.co_varnames[:f.__code__.co_argcount]
            self.assertIn("own_files", args, fn)

    # ---------------------------------------------------------------- the process is the client's

    def test_NO_LIBRARY_FUNCTION_ENDS_THE_PROCESS(self):
        """sys.exit() in a library is a decision taken from the caller.

        It cannot be caught meaningfully, it cannot be tested without a subprocess, and it turns
        a reusable helper into one that only suits the first tool that needed it. main() is
        exempt: that is this module run AS a script, which is a client, not the library.
        """
        whole = self.source()
        tree = ast.parse(whole)
        funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        calls = {name: {c.func.id for c in ast.walk(n)
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
                 for name, n in funcs.items()}

        def exits(name, seen=None):
            seen = seen if seen is not None else set()
            if name in seen or name not in funcs:
                return False
            seen.add(name)
            body = ast.dump(funcs[name])
            if "exit" in body and "sys.exit" in (ast.get_source_segment(whole, funcs[name]) or ""):
                return True
            return any(exits(c, seen) for c in calls.get(name, ()))

        guilty = sorted(n for n in common.__all__
                        if callable(getattr(common, n)) and exits(n))
        self.assertEqual(guilty, [])

    def test_NO_NETWORK_CATCH_SWALLOWS_A_PROGRAMMING_ERROR(self):
        r"""`except Exception` around a request hides a typo for ever, and one hid for weeks.

        `recheck-decisions.py` probes whether a dead archive's host has come back. Its probe read

            try:
                with http_open(...) as r:
                    ...
            except Exception:          # noqa: BLE001
                continue

        and `http_open` was never imported -- only `http_try` was. NameError IS an Exception, so
        every probe fell through both schemes and returned "DNS resolves, nothing answers" for
        **every host in the collection**, including two this project fetched files from on the day
        it was found. No error, no clue, and the tool's whole purpose inverted. Found by ruff
        (F821) on 2026-09-24, which until then ran only in CI.

        THE ONE-LINE FIX WAS THE SMALLER HALF. A net cast at `Exception` cannot tell "this host
        does not answer" from "this file is broken", and only the first is a result. So the
        catches name what they mean, and a probe that cannot run now takes the run down -- which
        is right, because a probe that cannot run has not found nothing.

        WHAT THIS FORBIDS IS NARROWER THAN "no broad catch", and the collection decided that.
        The first version of this test flagged **11** handlers across the tools. Reading them,
        nine BIND the exception and record it -- `failed += 1`, `note("FAIL %s :: %s")`,
        `reason = "%s: %s"` -- so a NameError there arrives in the output with its name on it.
        A crawler that skips a URL it could not read is doing its job.

        The two that did not were `suspect-reconsider.py` reading a marker and `mirror.py`
        skipping a directory listing, both `except Exception:` with no binding and no record,
        both able to swallow a typo for ever. Both now name `OSError`, which is what the code
        below them actually raises. So the rule is: a broad catch may carry on only if it says
        SOMETHING about what it caught.
        """
        bad = []
        for name in sorted(os.path.basename(p) for p in
                           glob.glob(os.path.join(self.HERE, "*.py"))):
            if name.endswith(("_test.py", "-test.py")):
                continue
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                src = fh.read()
            for node in ast.walk(ast.parse(src)):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                # `except Exception` and bare `except:` both catch NameError.
                broad = node.type is None or (isinstance(node.type, ast.Name)
                                              and node.type.id in ("Exception", "BaseException"))
                if not broad or node.name:          # `as exc` is a record being kept
                    continue
                body = ast.get_source_segment(src, node) or ""
                if "raise" in body:                 # it did not carry on
                    continue
                if len(body.splitlines()) > 2:      # it said something about what it caught
                    continue
                bad.append(name)
        # THE RATCHET REACHED ZERO THE SAME DAY. It was written with nine names in it, each a
        # handler that binds nothing, says nothing and carries on -- and all nine have since been
        # read and given the exceptions the code below them actually raises. The list is gone
        # rather than kept at zero, because an empty allowlist is an invitation to add to it.
        #
        # What each one turned out to be is in `narrowed-catches-test.py`. The short version: three could
        # give a silent wrong answer (`blogger-sitemap` skipping every image, `mediawiki-source`
        # reading every file as changed, `redbooks-fetch` selecting no documents at all), three
        # were "mirror.py is not beside this script" and would also have swallowed the day its
        # register moved, and the rest were a DNS lookup, a date parse and a HEAD request.
        self.assertEqual(sorted(set(bad)), [],
                         "a broad catch that carries on saying nothing at all")

    # ---------------------------------------------------------------- testable without the world

    def test_anything_that_reaches_outside_takes_the_outside_as_an_argument(self):
        """A helper that can only be exercised against a live host is one nobody exercises.

        And against somebody's private server, exercising it is not free.
        """
        expected = {
            "http_open": "opener", "http_get": "opener", "head_size": "opener",
            "mediawiki_api": "opener", "mediawiki_siteinfo": "kw",
            "say": "stream", "scan_tree": "report", "hash_tree": "report",
            "load_peer": "directory", "load_mirror": "directory",
        }
        # LOOKED UP ACROSS EVERY LIBRARY MODULE, not just common: mediawiki_api and
        # mediawiki_siteinfo moved out on 2026-09-23, and a rule that silently stopped covering
        # them would be the split weakening the contract again.
        for fn, arg in expected.items():
            owner = next((m for _n, m, _t in self.libraries() if hasattr(m, fn)), None)
            self.assertIsNotNone(owner, "%s() is in no library module" % fn)
            names = getattr(owner, fn).__code__.co_varnames
            self.assertIn(arg, names, "%s.%s() has no %s" % (owner.__name__, fn, arg))






class TestArchiveMarkers(unittest.TestCase):
    """Does an archive begin here? Two clients were each assembling this pair by hand."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.deep = os.path.join(self.tmp, "archive", "a", "b", "c")
        os.makedirs(self.deep)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mark(self, where, name):
        with io.open(os.path.join(where, name), "w", encoding="utf-8") as fh:
            fh.write("x")

    def test_the_pair_is_both_markers(self):
        self.assertEqual(set(common.ARCHIVE_MARKERS),
                         {common.COMPLETE_MARKER, common.ROOT_MARKER})

    def test_it_is_a_tuple_so_a_client_cannot_extend_it(self):
        self.assertIsInstance(common.ARCHIVE_MARKERS, tuple)

    def test_a_completed_archive_is_found(self):
        root = os.path.join(self.tmp, "archive")
        self.mark(root, common.COMPLETE_MARKER)
        self.assertEqual(common.archive_root(self.deep), root)

    def test_AND_ONE_STILL_BEING_FETCHED(self):
        # Asking for only the completion marker finds an archive in the state the asker happened
        # to have in mind. A run in progress carries .mirror-root and nothing else.
        root = os.path.join(self.tmp, "archive")
        self.mark(root, common.ROOT_MARKER)
        self.assertEqual(common.archive_root(self.deep), root)

    def test_the_nearest_one_wins(self):
        outer = os.path.join(self.tmp, "archive")
        inner = os.path.join(self.tmp, "archive", "a")
        self.mark(outer, common.COMPLETE_MARKER)
        self.mark(inner, common.ROOT_MARKER)
        self.assertEqual(common.archive_root(self.deep), inner)

    def test_the_directory_itself_counts(self):
        self.mark(self.deep, common.COMPLETE_MARKER)
        self.assertEqual(common.archive_root(self.deep), self.deep)

    def test_NO_ARCHIVE_IS_NONE_NOT_THE_DRIVE_ROOT(self):
        # Without a bound this walks to the top and reports whatever it finds there, which is a
        # confident answer to a question nobody asked.
        self.assertIsNone(common.archive_root(self.deep))

    def test_the_bound_is_honoured(self):
        root = os.path.join(self.tmp, "archive")
        self.mark(root, common.COMPLETE_MARKER)
        self.assertIsNone(common.archive_root(self.deep, levels=2))
        self.assertEqual(common.archive_root(self.deep, levels=4), root)


class TestNoClientSpellsABookkeepingNameByHand(unittest.TestCase):
    """The names belong to the library, so a rename cannot leave twelve files disagreeing."""

    HERE = os.path.dirname(os.path.abspath(__file__))
    LITERALS = {'".mirror-complete"': "COMPLETE_MARKER",
                '".sha256sum"': "SUMS_FILE",
                '".mirror-index.csv"': "INDEX_FILE",
                '"CATALOGUE.md"': "CATALOGUE_FILE",
                '".mirror-root"': "ROOT_MARKER"}

    def test_no_tool_writes_one_out(self):
        found = []
        for name in sorted(os.listdir(self.HERE)):
            if not name.endswith(".py") or name in ("common.py", "common_test.py"):
                continue
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    stripped = line.lstrip()
                    if stripped.startswith("#") or stripped.startswith('"'):
                        continue          # prose may name the file it is explaining
                    for lit, const in self.LITERALS.items():
                        if lit in line:
                            found.append("%s:%d uses %s instead of %s" % (name, i, lit, const))
        self.assertEqual(found, [])


class TestMarkerText(unittest.TestCase):
    """The writer, beside the reader that already existed. They have to agree."""

    def test_the_header_lines_up(self):
        got = common.marker_text({"archive": "oldskool", "files": 77628})
        self.assertEqual(got, "archive       oldskool\nfiles         77628\n")

    def test_the_column_is_fixed_not_computed(self):
        # Computed from the longest key, two markers with different keys would line up
        # differently and a diff of them would show alignment rather than content.
        narrow = common.marker_text({"files": 1})
        wide = common.marker_text({"permanent-404": 1})
        self.assertTrue(narrow.startswith("files" + " " * (common.MARKER_COLUMN - 5)))
        self.assertTrue(wide.startswith("permanent-404 "))

    def test_a_key_longer_than_the_column_still_gets_a_space(self):
        got = common.marker_text({"a-very-long-key-indeed": "x"})
        self.assertIn("a-very-long-key-indeed x", got)

    def test_numbers_become_text(self):
        self.assertIn("bytes         149225768625",
                      common.marker_text({"bytes": 149225768625}))

    def test_the_order_is_the_callers(self):
        got = common.marker_text({"bytes": 2, "archive": "a", "files": 1})
        self.assertEqual([line.split()[0] for line in got.strip().split("\n")],
                         ["bytes", "archive", "files"])

    def test_THE_BLANK_LINE_SEPARATES_THE_PROSE(self):
        got = common.marker_text({"files": 1}, "Some words.")
        self.assertEqual(got, "files         1\n\nSome words.\n")

    def test_no_prose_means_no_trailing_blank_line(self):
        self.assertFalse(common.marker_text({"files": 1}).endswith("\n\n"))

    def test_A_NEWLINE_IN_A_VALUE_IS_COLLAPSED_NOT_WRITTEN(self):
        # It would put a second line into the header, read as another key -- or, if blank, end
        # the header early and silently truncate the record.
        got = common.marker_text({"source": "http://h/a\nfiles 999"})
        self.assertEqual(len(got.strip().split("\n")), 1)
        self.assertIn("http://h/a files 999", got)

    def test_and_so_are_runs_of_spaces(self):
        self.assertIn("source        a b", common.marker_text({"source": "a    b"}))

    def test_A_KEY_WITH_WHITESPACE_IS_REFUSED(self):
        # There is no spelling of it the reader could get back. That is a mistake in the calling
        # code, and it should not become a damaged record.
        with self.assertRaises(ValueError):
            common.marker_text({"two words": "x"})

    def test_an_empty_record_is_still_valid(self):
        self.assertEqual(common.marker_text({}, "only prose"), "\n\nonly prose\n")


class TestWriteMarker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.path = os.path.join(self.tmp, common.COMPLETE_MARKER)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_writes_and_returns_the_text(self):
        text = common.write_marker(self.path, {"files": 3}, "words")
        with io.open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), text)

    def test_LF_ALWAYS_EVEN_ON_WINDOWS(self):
        # Two tools wrote this file and only one named the line ending: 66 markers in this
        # collection are CRLF and 31 are LF. The sums file beside it has always been LF.
        common.write_marker(self.path, {"files": 3, "bytes": 4}, "words")
        with io.open(self.path, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"\r", raw)

    def test_THE_ROUND_TRIP(self):
        # The reader and the writer are the same format or they are not a format.
        fields = {"archive": "oldskool", "source": "http://h/x",
                  "completed": "2026-09-14 03:11:52", "files": 77628, "bytes": 149225768625}
        common.write_marker(self.path, fields, "This mirror is complete.")
        back = common.read_marker(self.path)
        self.assertEqual(back, {k: str(v) for k, v in fields.items()})

    def test_AND_THE_PROSE_DOES_NOT_COME_BACK_AS_DATA(self):
        # The incident: a marker written by hand explained its archive in lines beginning "files"
        # and "bytes", and a reader that did not stop died on int("7826  ->  94899").
        common.write_marker(self.path, {"files": 7826},
                            "files         7826  ->  94899 after the second pass\n"
                            "bytes         nonsense, on purpose")
        self.assertEqual(common.read_marker(self.path), {"files": "7826"})

    def test_it_overwrites_rather_than_appending(self):
        common.write_marker(self.path, {"files": 1})
        common.write_marker(self.path, {"files": 2})
        self.assertEqual(common.read_marker(self.path), {"files": "2"})

    def test_a_deep_path_works(self):
        # Through long_path: the failure without it is a misleading "no such file" for a
        # directory the caller has just finished writing into.
        deep = os.path.join(self.tmp, *(["x" * 30] * 8))
        os.makedirs(common.long_path(deep))
        p = os.path.join(deep, common.COMPLETE_MARKER)
        common.write_marker(p, {"files": 1})
        self.assertEqual(common.read_marker(p), {"files": "1"})

    def test_A_BAD_BYTE_IS_REPLACED_NOT_RAISED(self):
        # catalogue.py's own copy of the reader had errors="replace" and the library did not, so
        # the same marker could be read by one tool and kill another.
        with io.open(self.path, "wb") as fh:
            fh.write(b"archive       oldsk\xffool\nfiles         3\n")
        rec = common.read_marker(self.path)
        self.assertEqual(rec["files"], "3")
        self.assertTrue(rec["archive"].startswith("oldsk"))




class TestQuoteUrl(unittest.TestCase):
    """A server may LINK what it cannot be asked for."""

    def test_a_space_in_a_path(self):
        self.assertEqual(common.quote_url("http://h/pub/AS400 Processor Summary.html"),
                         "http://h/pub/AS400%20Processor%20Summary.html")

    def test_AND_THE_STACK_REALLY_REFUSES_THE_UNQUOTED_ONE(self):
        """The test above proves nothing unless the danger is real.

        188 failures in the first 221 files of one archive, every one counted as an ordinary
        fetch failure. Shown against http.client, which rejects the path BEFORE any socket is
        opened -- a test that needs DNS to prove a point is a test that fails on a train.
        """
        import http.client
        with self.assertRaises(http.client.InvalidURL):
            http.client.HTTPConnection("h")._validate_path(
                "/pub/AS400 Processor Summary.html")

    def test_AND_http_client_ACCEPTS_THE_QUOTED_ONE_AND_REFUSES_THE_RAW_ONE(self):
        """The whole reason quote_url exists, with the control that makes it mean something.

        TWO DEFECTS WERE IN THIS TEST until 2026-09-23, and they cancelled out into a pass.
        It split the url on the first "h" -- which is the one in "http" -- so what it handed
        _validate_path was `ttp://h/pub/AS400%20...`, not a path at all. And it asserted nothing
        but "did not raise", with no showing that anything ever raises: had _validate_path been
        harmless, the test would have passed on garbage forever.

        A test that only checks something does NOT happen needs a case where it does.
        """
        import http.client
        conn = http.client.HTTPConnection("h")
        url = "http://h/pub/AS400 Processor Summary.html"

        raw = urllib.parse.urlsplit(url).path
        with self.assertRaises(http.client.InvalidURL):
            conn._validate_path(raw)

        quoted = urllib.parse.urlsplit(common.quote_url(url)).path
        self.assertEqual(quoted, "/pub/AS400%20Processor%20Summary.html")
        conn._validate_path(quoted)      # must not raise, and now that means something

    def test_AN_ALREADY_ENCODED_ESCAPE_IS_LEFT_ALONE(self):
        # Turning %20 into %2520 asks for a different file and gets a 404 that looks like a
        # missing one.
        self.assertEqual(common.quote_url("http://h/a%20b.txt"), "http://h/a%20b.txt")

    def test_it_is_idempotent(self):
        once = common.quote_url("http://h/a b/c d.txt")
        self.assertEqual(common.quote_url(once), once)

    def test_the_query_keeps_its_structure(self):
        self.assertEqual(common.quote_url("http://h/d.php?id=a:b&do=raw"),
                         "http://h/d.php?id=a%3Ab&do=raw")

    def test_THE_FRAGMENT_IS_DROPPED(self):
        # It is never sent, and a url that differs only there is the same request twice.
        self.assertEqual(common.quote_url("http://h/a.html#section"), "http://h/a.html")

    def test_the_host_is_untouched(self):
        self.assertEqual(common.quote_url("https://Example.COM:8080/a"),
                         "https://Example.COM:8080/a")

    def test_an_ordinary_url_comes_back_unchanged(self):
        for u in ("http://h/a/b.txt", "https://h/", "http://h/a?b=c"):
            self.assertEqual(common.quote_url(u), u, u)


class TestHttpOpenQuote(unittest.TestCase):
    """The composition, offered beside the building block."""

    def opener(self):
        seen = []

        def op(req, **_kw):
            seen.append(req.full_url)

            class R(io.BytesIO):
                headers = {}

                def __enter__(self):
                    return self

                def __exit__(self, *e):
                    self.close()
                    return False
            return R(b"")
        op.seen = seen
        return op

    def test_off_by_default(self):
        # A caller that built its own url should get back exactly what it asked for.
        op = self.opener()
        with common.http_open("http://h/a.html#frag", opener=op):
            pass
        self.assertEqual(op.seen, ["http://h/a.html#frag"])

    def test_on_when_asked(self):
        op = self.opener()
        with common.http_open("http://h/a b.txt", opener=op, quote=True):
            pass
        self.assertEqual(op.seen, ["http://h/a%20b.txt"])

    def test_the_identity_still_travels(self):
        op = self.opener()

        def check(req, **_kw):
            self.assertEqual(req.get_header("User-agent"), common.user_agent())
            return op(req)
        with common.http_open("http://h/a b", opener=check, quote=True):
            pass

    def test_it_composes_with_extra_headers(self):
        captured = {}

        def op(req, **_kw):
            captured["range"] = req.get_header("Range")
            captured["url"] = req.full_url

            class R(io.BytesIO):
                headers = {}

                def __enter__(self):
                    return self

                def __exit__(self, *e):
                    self.close()
                    return False
            return R(b"")
        with common.http_open("http://h/a b", opener=op, quote=True,
                              extra_headers={"Range": "bytes=10-"}):
            pass
        self.assertEqual(captured["range"], "bytes=10-")
        self.assertEqual(captured["url"], "http://h/a%20b")


class TestTheCollectionPathIsInOnePlace(unittest.TestCase):
    r"""`Q:\mirror` may appear in exactly one piece of code, and that piece is `MIRROR_ROOT`.

    WHERE THIS CAME FROM. The default was `os.environ.get("MIRROR_ROOT", r"Q:\mirror")` written
    out in 27 files, with a dozen more holding the path as a bare literal -- forty places naming
    one drive. That is the shape this library was created to end: `".sha256sum"` appeared 70 times
    and `"PROVENANCE.md"` 122 before they became constants here.

    PROSE IS NOT CODE, and this counts only code. A docstring showing `python containment.py
    --root Q:\mirror` is documentation of how to invoke the thing, and replacing it with a
    placeholder would make the example worse, not the collection safer. Comments recording what a
    past measurement found -- `Q:\mirror\funet-unix\ HELD 64.59 GB` -- are records of a fact and
    must not be edited at all. So the check walks the AST and looks at string literals that are
    not docstrings; comments never reach the tree.

    THE ENVIRONMENT VARIABLE IS GONE ON PURPOSE. A value that arrives from outside the process
    differs between two terminals on the same machine, and a run whose root depended on which
    window started it cannot be reproduced from its own output. `MIRROR_ROOT` is a plain variable
    and assigning it is the supported way to point the tools elsewhere.
    """

    HERE = os.path.dirname(os.path.abspath(__file__))
    NEEDLE = "Q:" + chr(92) + "mirror"

    # ONE FILE MAY READ THE ENVIRONMENT, and it is not a leftover.
    #
    # `mirror.py` resolves its root as --root, then $MIRROR_ROOT, then the working directory if
    # that carries a root marker, and it names the chain in its own refusal: "Pass --root PATH,
    # or set $MIRROR_ROOT." That is a documented promise to whoever runs the crawler, not a
    # default scattered across 27 files, and removing it would change what the tool does for
    # somebody who relies on it. The rule this class enforces is about the DEFAULT VALUE living
    # in one place; a deliberate precedence chain is a different thing and is spelled out here
    # rather than silently matched by the pattern.
    READS_THE_ENVIRONMENT_ON_PURPOSE = frozenset({"mirror.py"})

    def code_literals(self, name):
        """-> [line numbers] of non-docstring string literals holding the path."""
        with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), name)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docstrings.add(id(body[0].value))
        return [n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and self.NEEDLE in n.value and id(n) not in docstrings]

    def test_only_common_py_names_the_drive_in_code(self):
        offenders = {}
        for name in sorted(os.listdir(self.HERE)):
            if not name.endswith(".py"):
                continue
            lines = self.code_literals(name)
            if lines and name != "common.py":
                offenders[name] = lines
        self.assertEqual(offenders, {},
                         "the collection path belongs in common.MIRROR_ROOT; import it")

    def test_and_common_py_names_it_exactly_once(self):
        self.assertEqual(len(self.code_literals("common.py")), 1)

    def test_the_constant_is_what_that_one_literal_defines(self):
        self.assertEqual(common.MIRROR_ROOT, self.NEEDLE)

    def test_NOTHING_READS_IT_FROM_THE_ENVIRONMENT(self):
        """A root that depends on which terminal started the run is not reproducible.

        ASKED OF THE SYNTAX TREE, not of the text. The first version of this grepped for the
        string and failed on `common.py` -- whose comment explains that the call used to be there
        and why it is not any more. A check that cannot tell a call from a sentence about a call
        forbids writing the history down.
        """
        for name in sorted(os.listdir(self.HERE)):
            if not name.endswith(".py") or name in self.READS_THE_ENVIRONMENT_ON_PURPOSE:
                continue
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), name)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and node.args):
                    continue
                first = node.args[0]
                if isinstance(first, ast.Constant) and first.value == "MIRROR_ROOT":
                    self.fail("%s:%d still reads the root from the environment"
                              % (name, node.lineno))

    def test_setting_it_changes_what_a_tool_defaults_to(self):
        """The supported way to point the tools elsewhere, exercised rather than described."""
        import importlib.util
        keep = common.MIRROR_ROOT
        common.MIRROR_ROOT = "D:" + chr(92) + "elsewhere"
        try:
            path = os.path.join(self.HERE, "holes-vs-source.py")
            spec = importlib.util.spec_from_file_location("hvs_probe", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.MIRROR_ROOT, "D:" + chr(92) + "elsewhere")
        finally:
            common.MIRROR_ROOT = keep


class TestNoClientBuildsItsOwnRequest(unittest.TestCase):
    """One place opens a socket, so one place carries the identity and the timeout."""

    HERE = os.path.dirname(os.path.abspath(__file__))

    def test_urlopen_is_called_in_exactly_one_file(self):
        callers = []
        for name in sorted(os.listdir(self.HERE)):
            # TEST FILES ARE EXEMPT, all of them. This suite calls urlopen to demonstrate the
            # danger the library removes, which is the opposite of a client quietly opening its
            # own socket -- and `holes-vs-source-test.py` names it in an assertion that its tool
            # does NOT call it, which put the guard itself on the list of offenders. The census
            # is about who opens sockets, not about who can spell the word.
            if not name.endswith(".py") or "test" in name:
                continue
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if "urllib.request.urlopen" in line and not line.lstrip().startswith("#"):
                        callers.append("%s:%d" % (name, i))
        self.assertEqual([c.split(":")[0] for c in callers], ["common.py"], callers)

    def test_and_no_client_writes_a_User_Agent_header(self):
        found = []
        for name in sorted(os.listdir(self.HERE)):
            if not name.endswith(".py") or name in ("common.py", "common_test.py"):
                continue
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if '"User-Agent"' in line:
                        found.append("%s:%d" % (name, i))
        self.assertEqual(found, [])


class TestFindManifests(unittest.TestCase):
    """Where a manifest is, without deciding what anyone should do about it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, *rel):
        p = os.path.join(self.tmp, *rel)
        if not os.path.isdir(os.path.dirname(p)):
            os.makedirs(os.path.dirname(p))
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write("x")
        return p

    def test_a_manifest_names_itself(self):
        p = self.make(common.SUMS_FILE)
        self.assertEqual(common.find_manifests(p), [p])

    def test_and_so_does_any_other_file_handed_in(self):
        # The caller often has a path from a command line and does not know which it is; deciding
        # here that an unrecognised file is not a manifest would refuse a renamed one.
        p = self.make("somebody-elses-name.txt")
        self.assertEqual(common.find_manifests(p), [p])

    def test_an_archive_with_both_kinds(self):
        idx = self.make(common.INDEX_FILE)
        sums = self.make(common.SUMS_FILE)
        self.assertEqual(common.find_manifests(self.tmp), [idx, sums])

    def test_a_collection_index_comes_first(self):
        coll = self.make(common.COLLECTION_INDEX)
        sums = self.make(common.SUMS_FILE)
        self.assertEqual(common.find_manifests(self.tmp), [coll, sums])

    def test_one_level_down(self):
        a = self.make("archive-a", common.INDEX_FILE)
        b = self.make("archive-b", common.INDEX_FILE)
        self.assertEqual(common.find_manifests(self.tmp), [a, b])

    def test_the_order_is_stable(self):
        # Two runs over an unchanged tree produce the same list, so a diff of two reports means
        # something.
        for name in ("z-last", "a-first", "m-middle"):
            self.make(name, common.INDEX_FILE)
        self.assertEqual(common.find_manifests(self.tmp), common.find_manifests(self.tmp))
        self.assertEqual([os.path.basename(os.path.dirname(p))
                          for p in common.find_manifests(self.tmp)],
                         ["a-first", "m-middle", "z-last"])

    def test_two_levels_down_is_NOT_searched(self):
        # A bounded search. Without a bound, pointing this at a drive root walks the whole disk.
        self.make("a", "b", common.INDEX_FILE)
        self.assertEqual(common.find_manifests(self.tmp), [])

    def test_nothing_there_is_an_empty_list(self):
        self.assertEqual(common.find_manifests(self.tmp), [])

    def test_a_path_that_does_not_exist_is_an_empty_list(self):
        self.assertEqual(common.find_manifests(os.path.join(self.tmp, "nope")), [])

    def test_IT_DOES_NOT_SAY_WHAT_IS_PROTECTED(self):
        # It used to return (path, is_a_mirror's) and its one caller turned the second straight
        # into "protected from deduplication". Where a manifest is is a FACT; what is protected
        # is a DECISION, and a function returning both invites the next caller to inherit a
        # policy it never chose.
        self.make(common.INDEX_FILE)
        got = common.find_manifests(self.tmp)
        self.assertTrue(all(isinstance(p, str) for p in got))
        # the caller asks in one line, and means it
        self.assertTrue(os.path.basename(got[0]) == common.INDEX_FILE)


class TestCatalogueCountsWhatTheMarkerCounted(unittest.TestCase):
    """The one measurement that must not have two implementations.

    catalogue.py said in its own docstring that it counted "EXACTLY mirror.py's scan_tree()
    definition" and it did not: the two own-file sets differed by five names. Measured against the
    markers of the four Internet Archive trees on 2026-09-23, scan_tree agreed to the byte and the
    second counter was one file and 3 281 bytes over. A catalogue that permanently reports a
    disagreement nobody can act on teaches its reader to ignore disagreements.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="common-test-")
        self.cat = common.load_peer("catalogue.py", "_cat_for_test")
        for rel in ("real.txt", "sub/deep.bin", "IA-METADATA.json",
                    common.COMPLETE_MARKER, common.SUMS_FILE, "half.iso.part"):
            p = os.path.join(self.tmp, *rel.split("/"))
            if not os.path.isdir(os.path.dirname(p)):
                os.makedirs(os.path.dirname(p))
            with io.open(common.long_path(p), "wb") as fh:
                fh.write(b"xxx")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_two_counters_agree(self):
        n, total = common.scan_tree(self.tmp)
        c_n, c_total, _bad = self.cat.walk_counts(self.tmp)
        self.assertEqual((c_n, c_total), (n, total))

    def test_AND_IA_METADATA_IS_THE_NAME_THAT_USED_TO_SPLIT_THEM(self):
        # It sits at the top of four archives and is ours, not content.
        self.assertIn("IA-METADATA.json", common.OWN_FILES)
        self.assertEqual(common.scan_tree(self.tmp)[0], 2)      # real.txt and sub/deep.bin

    def test_the_unreadable_count_is_still_its_own_figure(self):
        # Kept without being smuggled into a figure that means something else.
        self.assertEqual(self.cat.walk_counts(self.tmp)[2], 0)






class TestLooksLikeACopyOfAPage(unittest.TestCase):
    """Telling a backup of a page from a new spelling of markup, which decides a gate.

    `page-extensions.py` looks for stored files that hold links under a name nothing walks --
    sun3arc's 134 `.phtml` pages sat unread that way while the run reported COMPLETE, with 878
    links and 318 images on disk that nothing ever opened. But most of what it finds is a backup,
    and a backup holds exactly the links the page beside it holds, so nothing was missed. Those
    rows drowned the real ones and kept the tool out of the gates. That is D1.

    A SHAPE, NOT A LIST OF EXTENSIONS. Naming `.orig`, `.bak`, `.old`, `.new`, `.save` and
    `.~1~` is a list that is wrong the first time somebody writes `.html.keep`. What they share
    is structural: take the suffix off and a page name is left.
    """

    def test_a_suffix_appended_to_a_page_name(self):
        for name in ("fetch.html.new", "index.html.orig", "page.php.bak", "readme.html.save",
                     "notes.htm.old", "x.html.keep"):
            self.assertTrue(common.looks_like_a_copy_of_a_page(name), name)

    def test_the_editor_and_patch_spellings(self):
        for name in ("a.html~", "b.html.~1~", "c.php.~12~"):
            self.assertTrue(common.looks_like_a_copy_of_a_page(name), name)

    def test_A_LISTING_SAVED_UNDER_ITS_OWN_SORT_ORDER(self):
        # Apache's column links are queries; a crawler that stores the query in the name keeps
        # one copy of the same listing per sort order.
        for name in ("index.html@S=A", "index.html@S=A;O=D", "index.html@C=N;O=A"):
            self.assertTrue(common.looks_like_a_copy_of_a_page(name), name)

    def test_THE_UNDERSCORE_SPELLING_OF_THE_SORT_ORDER(self):
        """A fetcher that will not put `@` in a filename writes `index.html_D=A` instead, and
        this collection holds both spellings.

        Measured 2026-09-24: **63 456** of `next-68k-org`'s 78 720 `.orig` files are
        `index.html_{C,D,M,N,S}={A,D}` with an optional `;O=x`, in exactly 17 distinct forms and
        no others. Only 114 `.orig` files in the whole collection are a backup of something else.
        """
        for name in ("index.html_D=A", "index.html_S=D", "index.html_C=N;O=D"):
            self.assertTrue(common.looks_like_a_copy_of_a_page(name), name)

    def test_AND_TWO_SUFFIXES_ARE_PEELED_IN_THE_RIGHT_ORDER(self):
        """`index.html_D=A.orig` carries both, and the first version did them in the wrong
        order -- backup tail first, extension second -- so it answered False for all 63 456.

        Each turn of the loop removes ONE thing and asks again, which is what "take the suffix
        off and a page name is left" means when somebody took two suffixes off.
        """
        for name in ("index.html_D=A.orig", "index.html_C=N;O=D.orig", "index.html@S=A.bak"):
            self.assertTrue(common.looks_like_a_copy_of_a_page(name), name)

    def test_and_the_peeling_is_bounded(self):
        # A name of nothing but suffixes must not turn this into a long loop; it decides a name,
        # not a document.
        self.assertFalse(common.looks_like_a_copy_of_a_page("a" + ".x" * 40))

    def test_AN_UNDERSCORE_IS_AN_ORDINARY_CHARACTER(self):
        # The rule is kept narrow because `_` is not punctuation in a filename. A loose one here
        # would excuse real names, which is the expensive direction.
        for name in ("my_file.tar.gz", "report_2024.pdf", "read_me.orig", "a_b=c.orig"):
            self.assertFalse(common.looks_like_a_copy_of_a_page(name), name)

    def test_A_NAME_THAT_IS_ITSELF_WALKED_IS_NOT_A_COPY(self):
        """The direction that would have been expensive to get wrong.

        `x.phtml` strips to `x`, so a rule that stripped first would call it a backup -- and
        excuse the exact defect the tool exists to find. It is a page in its own right and never
        reaches the stripping.
        """
        for name in ("x.phtml", "z.html", "i.php", "y.aspx", "index.htm"):
            self.assertFalse(common.looks_like_a_copy_of_a_page(name), name)

    def test_and_an_ordinary_file_is_not_one_either(self):
        for name in ("archive.tar.gz", "notes.txt", "rom.bin", "x", "", ".orig", "a.new"):
            self.assertFalse(common.looks_like_a_copy_of_a_page(name), name)

    def test_the_suffix_must_follow_a_PAGE_name(self):
        # `data.csv.bak` is a backup of something, but not of a page, and this question is only
        # ever asked about pages. Answering True would widen a gate's blind spot for free.
        self.assertFalse(common.looks_like_a_copy_of_a_page("data.csv.bak"))
        self.assertFalse(common.looks_like_a_copy_of_a_page("dump.sql.orig"))


class TestLooksLikeAPage(unittest.TestCase):
    """Three tools carried three different answers to this, and none said why."""

    def test_the_obvious_ones(self):
        for name in ("index.html", "a.htm", "b.shtml", "c.xhtml", "d.phtml"):
            self.assertTrue(common.looks_like_a_page(name), name)

    def test_THE_SCRIPTED_ONES_TOO(self):
        # crawl-gap-audit followed none of these and pages-to-urllist only .php, so a page was
        # walked by one tool and treated as a leaf by the next.
        for name in ("i.php", "x.asp", "y.aspx", "z.jsp", "s.cgi"):
            self.assertTrue(common.looks_like_a_page(name), name)

    def test_case_does_not_matter(self):
        self.assertTrue(common.looks_like_a_page("INDEX.HTML"))
        self.assertTrue(common.looks_like_a_page("Index.Php"))

    def test_a_file_is_not_a_page(self):
        for name in ("a.tar.gz", "b.iso", "c.pdf", "d.txt", "readme"):
            self.assertFalse(common.looks_like_a_page(name), name)

    def test_A_NAME_WITH_NO_EXTENSION_IS_NOT_DECIDED_HERE(self):
        # It may be a directory, a CGI script or a file somebody forgot to name, and only the
        # caller knows which of those its tree holds. measure-remote treats it as a page; the
        # two that read files already on disk do not.
        self.assertFalse(common.looks_like_a_page("something"))

    def test_a_url_path_works_as_well_as_a_filename(self):
        self.assertTrue(common.looks_like_a_page("/pub/docs/index.html"))
        self.assertFalse(common.looks_like_a_page("/pub/docs/a.iso"))

    def test_NO_TOOL_FOLLOWS_LESS_THAN_IT_DID(self):
        """Measured 2026-09-23: five, six and eight extensions, differing by up to seven.

        The shared set is WIDER than their union, and deliberately: it also carries the
        spellings mirror.py's own crawler pattern matched -- .shtm, .xhtm, .phtm -- plus
        .xht and .php3, which that pattern missed. Those five hold zero files in this
        collection, so they cost nothing and close the gap between the two answers.
        (.php3 is LINKED six times, always to another host.)

        .php4 is the one exception and holds 119 files in two archives. It was added on
        2026-09-23 on evidence -- see TestTheCrawlerAsksTheLibraryNow, which measured it.
        """
        was = {
            "crawl-gap-audit": {".htm", ".html", ".phtml", ".shtml", ".xhtml"},
            "pages-to-urllist": {".htm", ".html", ".phtml", ".shtml", ".xhtml", ".php"},
            "measure-remote": {".htm", ".html", ".shtml", ".php", ".asp", ".aspx",
                               ".jsp", ".cgi"},
        }
        now = set(common.PAGE_EXTENSIONS)
        for tool, before in was.items():
            self.assertEqual(before - now, set(), "%s would stop following something" % tool)
        self.assertTrue(set().union(*was.values()) <= now)

    def test_it_is_a_tuple_so_endswith_can_take_it_whole(self):
        self.assertIsInstance(common.PAGE_EXTENSIONS, tuple)
        self.assertTrue("x.html".endswith(common.PAGE_EXTENSIONS))

    def test_IT_ANSWERS_BY_NAME_WHERE_looks_like_html_ANSWERS_BY_BYTES(self):
        # Two questions that sound alike. This one decides whether to spend a request at all;
        # the other decides what arrived.
        self.assertTrue(common.looks_like_a_page("a.html"))
        self.assertFalse(common.looks_like_html(b"a.html"))
        self.assertFalse(common.looks_like_a_page("a.bin"))
        self.assertTrue(common.looks_like_html(b"<!DOCTYPE html>"))


class TestMeasureRemoteReadsSizesThroughTheLibrary(unittest.TestCase):
    """SIZE_RE finds the column, parse_size reads it. The unit table was a second copy."""

    def setUp(self):
        self.mr = common.load_peer("measure-remote.py", "_mr_for_test")

    def rows(self, body):
        return self.mr.rows(body, "http://h/pub/", "http://h/pub/")

    def test_the_apache_shapes(self):
        body = ('<a href="a.gz">a.gz</a>  12-Jan-2011 09:22  1.2M\n'
                '<a href="b.txt">b.txt</a>  12-Jan-2011 09:22   345\n'
                '<a href="c.iso">c.iso</a>  01-Jan-2001 00:00  3.5G\n')
        self.assertEqual([size for _u, size in self.rows(body)],
                         [1258291, 345, 3758096384])

    def test_A_DIRECTORY_HAS_NO_SIZE(self):
        # Apache prints "-" for one, and a directory counted as a file of some size makes the
        # total wrong in a way nothing downstream can see.
        body = '<a href="sub/">sub/</a>  12-Jan-2011 09:22    -\n'
        self.assertEqual(self.rows(body), [("http://h/pub/sub/", None)])

    def test_the_units_are_binary_as_they_always_were(self):
        """K, M, G AND T -- and T was missing from the library until 2026-09-27.

        THE DATE IN THE LINE IS NOT DECORATION, and this test used to write `x` there. That
        passed while measure-remote.py carried its own parser, which took any number at the end
        of a line as a size. `common.parse_listing` matches the whole Apache ROW SHAPE -- name,
        date, size -- and declines a line that has none. Stricter, and right: a trailing number
        on a hand-written page is not a file size.

        AND T USED TO READ AS ONE BYTE. `parse_size` has understood T since it was written, but
        ROW_RE and PRE_RE matched only `[KMG]`, so "1.0T" matched the bare "1". Not a failure to
        parse -- a confident wrong number, three orders of magnitude low, in the direction that
        makes an archive look affordable. This test found it by failing the moment the private
        parser was deleted and the library took over.
        """
        for unit, want in (("K", 1024), ("M", 1048576), ("G", 1073741824),
                           ("T", 1099511627776)):
            body = '<a href="a">a</a>  12-Jan-2011 09:22  1.0%s\n' % unit
            self.assertEqual(self.rows(body)[0][1], want, unit)

    def test_A_LINE_WITHOUT_A_DATE_YIELDS_NO_SIZE(self):
        """The strictness, stated so nobody loosens it by accident.

        The caller falls back to a HEAD request: a round trip, and true. The old permissive
        reading cost nothing and could be wrong.
        """
        self.assertIsNone(self.rows('<a href="a">a</a>  x  1.0K\n')[0][1])

    def test_an_html_table_listing_reads_too(self):
        # Stripping tags first makes one pattern fit both Apache styles; matching the raw line
        # only fits FancyIndexing and falls back to a HEAD request per file.
        body = ('<tr><td><a href="a.gz">a.gz</a></td>'
                '<td align="right">12-Jan-2011 09:22</td><td align="right">1.2M</td></tr>\n')
        self.assertEqual(self.rows(body)[0][1], 1258291)


class TestTheTwoPageAnswers(unittest.TestCase):
    """The library offers both and chooses for nobody. These tests are what the choice rests on."""

    DOCUMENTS = (".html", ".htm", ".shtml", ".shtm", ".xhtml", ".xhtm",
                 ".phtml", ".phtm", ".xht", ".php", ".php3", ".php4")
    PROGRAMS = (".asp", ".aspx", ".jsp", ".cgi")

    def test_both_accept_every_document(self):
        for ext in self.DOCUMENTS:
            self.assertTrue(common.looks_like_a_document("x" + ext), ext)
            self.assertTrue(common.looks_like_a_page("x" + ext), ext)

    def test_ONLY_THE_WIDE_ONE_ACCEPTS_A_PROGRAM(self):
        # That is the entire difference, and it is what the caller is choosing between.
        for ext in self.PROGRAMS:
            self.assertFalse(common.looks_like_a_document("x" + ext), ext)
            self.assertTrue(common.looks_like_a_page("x" + ext), ext)

    def test_THE_DIFFERENCE_IS_EXACTLY_FOUR_EXTENSIONS(self):
        self.assertEqual(set(common.PAGE_EXTENSIONS) - set(common.DOCUMENT_EXTENSIONS),
                         set(self.PROGRAMS))

    def test_neither_accepts_something_that_is_not_a_page(self):
        for name in ("a.tar.gz", "b.iso", "c.pdf", "d.txt", "e.css", "f.xml", "readme"):
            self.assertFalse(common.looks_like_a_document(name), name)
            self.assertFalse(common.looks_like_a_page(name), name)

    # TWO TESTS STOOD HERE UNTIL 2026-09-23, written while the switch was still a proposal: they
    # loaded mirror.py and read HTML_PAGE out of it to compare against this set. The switch
    # happened, HTML_PAGE is gone, and a test that reaches into another module for a constant
    # dies with the constant. TestTheCrawlerAsksTheLibraryNow carries the retired pattern as a
    # literal of its own instead -- which is what lets a promise outlive the thing it was made
    # about, and is the general lesson, not a detail of this one move.

    def test_case_does_not_matter_to_either(self):
        self.assertTrue(common.looks_like_a_document("INDEX.HTML"))
        self.assertTrue(common.looks_like_a_page("Script.CGI"))

    def test_the_three_auditors_lose_nothing_either(self):
        # What they each carried before 2026-09-23, measured then.
        was = {
            "crawl-gap-audit": {".htm", ".html", ".phtml", ".shtml", ".xhtml"},
            "pages-to-urllist": {".htm", ".html", ".phtml", ".shtml", ".xhtml", ".php"},
            "measure-remote": {".htm", ".html", ".shtml", ".php", ".asp", ".aspx", ".jsp", ".cgi"},
        }
        for tool, before in was.items():
            self.assertEqual(before - set(common.PAGE_EXTENSIONS), set(), tool)

    def test_both_are_tuples_so_endswith_takes_them_whole(self):
        for t in (common.DOCUMENT_EXTENSIONS, common.PROGRAM_PAGE_EXTENSIONS,
                  common.PAGE_EXTENSIONS):
            self.assertIsInstance(t, tuple)

    def test_no_extension_is_decided_by_neither(self):
        # It may be a directory, a script or a file somebody forgot to name.
        self.assertFalse(common.looks_like_a_document("something"))
        self.assertFalse(common.looks_like_a_page("something"))


class TestBffMagic(unittest.TestCase):
    """The extension was checked and had no signature, so the check could never fire."""

    def test_the_four_bytes(self):
        self.assertEqual(common.BFF_MAGIC, b"\x09\x00\x6b\xea")

    def test_A_FILESET_IS_ACCEPTED(self):
        self.assertIsNone(common.magic_mismatch("x.bff", common.BFF_MAGIC + b"rest"))

    def test_AND_AN_ERROR_PAGE_UNDER_A_FILESET_NAME_IS_NOT(self):
        # 63 762 .bff files in this collection, and until 2026-09-23 magic_mismatch answered None
        # for every one of them -- "no opinion", which a caller must not read as "fine". The
        # extension had been in CHECKED_EXT from the start; only the signature was missing.
        why = common.magic_mismatch("x.bff", b"<!DOCTYPE html>")
        self.assertIsNotNone(why)
        self.assertIn(".bff", why)

    def test_the_extension_was_always_checked(self):
        self.assertIn(".bff", common.CHECKED_EXT)

    def test_and_now_it_has_an_entry(self):
        self.assertIn(".bff", common.MAGIC)

    def test_EVERY_CHECKED_EXTENSION_HAS_A_SIGNATURE(self):
        """An extension in CHECKED_EXT with no entry in MAGIC is a check that cannot fire.

        The two sets are not the same thing and need not be equal -- a caller may check an
        extension this table has no opinion about -- but a name in the first and not the second
        means an auditor walks those files, reads their first bytes, and can never report one.
        Anything left here should be there on purpose, not by omission.
        """
        without = sorted(e for e in common.CHECKED_EXT if e not in common.MAGIC)
        self.assertEqual(without, [".img", ".iso", ".ova", ".tar"],
                         "a checked extension gained or lost a signature -- say which and why")


class TestSharedConstantsHaveOneHome(unittest.TestCase):
    """Seven constants were written out in two files each. Measured identical before moving."""

    HERE = os.path.dirname(os.path.abspath(__file__))

    def test_the_link_patterns_are_the_librarys(self):
        for name in ("crawl-gap-audit.py", "pages-to-urllist.py"):
            mod = common.load_peer(name, "_shared_" + name[:4])
            href = getattr(mod, "HREF_ANY", None) or getattr(mod, "HREF")
            img = getattr(mod, "IMG_ANY", None) or getattr(mod, "IMG")
            self.assertIs(href, common.LINK_ODD_RE, name)
            self.assertIs(img, common.IMG_SRC, name)

    def test_the_frame_pattern_too(self):
        mod = common.load_peer("crawl-gap-audit.py", "_shared_frame")
        self.assertIs(mod.FRAME_ANY, common.FRAME_RE)

    def test_BUT_NOT_HREF_FIRST(self):
        # It looks like LINK_RE and is not: no capture group, because it COUNTS rather than
        # collects. Two patterns that differ for a reason must not be folded together.
        mod = common.load_peer("crawl-gap-audit.py", "_shared_first")
        self.assertIsNot(mod.HREF_FIRST, common.LINK_RE)
        self.assertNotEqual(mod.HREF_FIRST.pattern, common.LINK_RE.pattern)

    def test_the_collision_line_is_one_format(self):
        for name in ("case-collision-recover.py", "crawl-gap-audit.py"):
            mod = common.load_peer(name, "_coll_" + name[:4])
            found = getattr(mod, "PAT", None) or getattr(mod, "DROPPED")
            self.assertIs(found, common.COLLISION_DROPPED, name)

    def test_and_it_reads_the_line_a_run_writes(self):
        line = ("2026-09-08 11:22:01 COLLISION DROPPED http://h/a/B.TXT <- "
                "/a/B.TXT (already claimed by /a/b.txt)")
        m = common.COLLISION_DROPPED.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(m.groups(), ("/a/B.TXT", "/a/b.txt"))

    def test_the_free_space_floor_is_one_number(self):
        self.assertEqual(common.MIN_FREE_BYTES, 1 * 10 ** 9)
        mirror = common.load_mirror()
        self.assertIs(mirror.MIN_FREE_BYTES, common.MIN_FREE_BYTES)

    def test_and_a_tool_may_still_move_it(self):
        # wayback-salvage takes --min-free-gb, so its own name is a variable seeded from the
        # library rather than the constant itself.
        wbs = common.load_peer("wayback-salvage.py", "_wbs_floor")
        self.assertEqual(wbs.MIN_FREE_BYTES, common.MIN_FREE_BYTES)

    def test_NO_TOOL_SPELLS_A_PARTIAL_SUFFIX_BY_HAND(self):
        found = []
        for name in sorted(os.listdir(self.HERE)):
            if not name.endswith(".py") or name in ("common.py", "common_test.py"):
                continue
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if line.lstrip().startswith("#"):
                        continue
                    if '".part"' in line and '".suspect"' in line:
                        found.append("%s:%d" % (name, i))
        self.assertEqual(found, [])

class TestTheCrawlerAsksTheLibraryNow(unittest.TestCase):
    r"""mirror.py's crawler matched a regex of its own until 2026-09-23; now it asks the library.

    THE RETIRED PATTERN IS WRITTEN OUT HERE AND NOWHERE ELSE. The promise made when it was
    removed -- "nothing that was walked stopped being walked" -- is a claim about something that
    no longer exists in the tree, so either this test carries it or it becomes unverifiable the
    moment the change lands. That is the whole reason for the literal below.
    """

    # What mirror.py called HTML_PAGE, for the HTML_CRAWL archives.
    RETIRED = re.compile(r"\.(?:[psx]?html?|php)$", re.I)

    # Its entire language, which is finite: an optional p/s/x, then html or htm, plus php.
    # DERIVED from the parts rather than typed out, so a reader can check it against the pattern.
    WALKED = tuple("." + p + s for p in ("", "p", "s", "x") for s in ("html", "htm")) + (".php",)

    def test_the_retired_pattern_really_matched_exactly_those(self):
        """Before comparing anything to it, check the enumeration above is what it matched."""
        for ext in self.WALKED:
            self.assertRegex("page" + ext, self.RETIRED, ext)
            self.assertRegex("PAGE" + ext.upper(), self.RETIRED, ext)   # it carried re.I
        for ext in (".xht", ".php3", ".php4", ".asp", ".cgi", ".txt", ".html5", ".shtmlx",
                    ".ph"):
            self.assertIsNone(self.RETIRED.search("page" + ext), ext)

    def test_EVERY_NAME_THE_CRAWLER_WALKED_IT_STILL_WALKS(self):
        """The one promise that had to hold. A superset, checked member by member."""
        for ext in self.WALKED:
            self.assertIn(ext, common.DOCUMENT_EXTENSIONS)
            self.assertTrue(common.looks_like_a_document("page" + ext), ext)
            self.assertTrue(common.looks_like_a_document("PAGE" + ext.upper()), ext)

    def test_AND_WHAT_IT_GAINED_IS_NAMED_HERE(self):
        """Widening a crawler's reach is a decision, so it is spelled out and not merely allowed.

        TWO OF THE THREE ARE PRECAUTION. Measured over every href in all 96 archives on
        2026-09-23: `.xht` does not occur at all; `.php3` occurs SIX times --
        kyz.uklinux.net/cabextract.php3, tru64.org/faq/tru64_faq.php3 and four more -- every one
        an absolute URL to another host, refused long before any of this is asked. They are
        carried so the next site that spells markup a new way is not another silent COMPLETE.

        `.php4` IS NOT PRECAUTION. It was added on evidence: 119 files in two archives, and one
        of those archives exists only because bitsavers' 2007 crawler saved `.php4` as content
        and never walked it. WHAT MAKES THAT SPELLING WORSE THAN THE OTHERS is how it hides --
        of the 1 206 in-scope links pointing at a `.php4` page, 1 169 are THEMSELVES on a `.php4`
        page. Miss the extension and you enter through the one link from index.html and see
        nothing after it, so the cost is a subtree rather than a page. Neither archive is
        HTML_CRAWL, so this still changes no run today.
        """
        gained = sorted(e for e in common.DOCUMENT_EXTENSIONS if e not in self.WALKED)
        self.assertEqual(gained, [".php3", ".php4", ".xht"],
                         "the crawler now follows something new -- say which, and why")

    def test_A_PROGRAM_PAGE_IS_NOT_GAINED(self):
        """The crawler takes the NARROW predicate, and the choice has a reason.

        looks_like_a_page would have added .asp/.aspx/.jsp/.cgi -- eight files in four archives,
        measured over the whole collection, against 288 636 the document set already covers.
        Asking a stranger's server for a .cgi asks it to RUN something, which is not the same
        favour as asking it for a file, and this is the one caller here that talks to hosts that
        are not ours. Small enough that neither answer is obviously right; the narrow one is
        taken because the cost of being wrong falls on somebody else.
        """
        for ext in common.PROGRAM_PAGE_EXTENSIONS:
            self.assertFalse(common.looks_like_a_document("page" + ext), ext)
            self.assertTrue(common.looks_like_a_page("page" + ext), ext)
            self.assertIsNone(self.RETIRED.search("page" + ext), ext)

    def test_both_answer_alike_on_what_actually_reaches_them(self):
        # is_child_link drops anything with '?' before the crawler asks, so a query string never
        # arrives -- but a fragment does, and both say no to it for the same reason.
        self.assertFalse(common.is_child_link("a.html?x=1"))
        for url in ("http://h/a.html#top", "http://h/a.html?x=1", "http://h/dir/", "http://h/a"):
            self.assertEqual(bool(self.RETIRED.search(url)),
                             common.looks_like_a_document(url), url)

    def test_THE_ONE_BEHAVIOURAL_DIFFERENCE_IS_A_TRAILING_NEWLINE(self):
        r"""`$` matches before a final newline; endswith does not. And it OCCURS.

        THIS IS THE CASE THE SWITCH WAS NEARLY MADE WITHOUT. Reasoning said an href could not end
        in a newline, because the attribute pattern cannot cross one. Measuring said otherwise:
        over all 9 255 290 raw hrefs in the collection the two predicates disagree FIFTY times,
        every one of them `...html\n` or `...htm\n` -- the pattern crosses a newline inside a
        quoted value perfectly well.

        TWO SEPARATE THINGS KEEP IT AWAY FROM THE CRAWLER, and the next two tests pin both,
        because an explanation that covers only the cases that happen to occur is not one.
        """
        self.assertIsNotNone(self.RETIRED.search("page.html\n"))
        self.assertFalse(common.looks_like_a_document("page.html\n"))

    def test_EVERY_DISAGREEMENT_IS_OFF_HOST_AND_DIES_BEFORE_THE_PAGE_TEST(self):
        r"""All 50 lost and all 6 gained are absolute URLs to OTHER hosts. Two guards, not one.

        WHICH guard stops them depends on the archive, and the distinction is the whole point,
        because the page test only runs for the HTML_CRAWL ones:

          - ordinary archives: parse_listing drops an off-host href itself (allow_up=False);
          - HTML_CRAWL archives: parse_listing YIELDS it -- allow_up=html_crawl is exactly what
            lets those hand-written sites link upwards -- and what refuses it is the crawler's
            own `child.startswith(base_url)`, which sits far above the page test.

        The first version of this test pinned only the first guard. It passed, and it said
        nothing whatever about the path that matters, which is the second one.
        """
        off = "http://www.tru64.org/faq/tru64_faq.php3"
        newline = "http://www.tivoli.com/support/storage_mgr/pubs/admanual.htm\n"

        for url in (off, newline):
            self.assertFalse(common.is_child_link(url), url)
            self.assertEqual(common.parse_listing('<a href="%s">x</a>' % url), [], url)
            # ... but the crawl flags let it through, which is why the second guard exists.
            self.assertTrue(common.parse_listing('<a href="%s">x</a>' % url,
                                                 allow_up=True, images=True), url)
            base = "http://ps-2.kev009.com/"
            self.assertFalse(urllib.parse.urljoin(base, url).startswith(base), url)

    def test_AND_THAT_GUARD_STILL_SITS_ABOVE_THE_PAGE_TEST(self):
        """Order is the guarantee here, so it is checked rather than assumed.

        If the host guard ever moved below the page test, every claim above would quietly stop
        being true and nothing else in this file would notice.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "mirror.py"), encoding="utf-8") as fh:
            src = fh.read()
        guard = src.index("if not child.startswith(base_url)")
        page_test = src.index("looks_like_a_document(child)")
        self.assertLess(guard, page_test,
                        "the off-host guard is no longer above the page test -- the crawler can "
                        "now be asked to walk a link on somebody else's host")

    def test_and_an_ON_SITE_one_would_be_normalised_by_urljoin(self):
        """The case that does not occur today, which is why it needs a test and not a sentence.

        A relative href keeps its newline through parse_listing -- so if one ever appears on a
        host being crawled, what removes it is urljoin, one line above the page test.
        """
        self.assertEqual([h for h, _s, _d in common.parse_listing('<a href="page.html\n">x</a>')],
                         ["page.html\n"])
        child = urllib.parse.urljoin("http://h/d/", "page.html\n")
        self.assertEqual(child, "http://h/d/page.html")
        self.assertTrue(common.looks_like_a_document(child))

    def test_the_crawler_carries_no_page_pattern_of_its_own_any_more(self):
        mirror = common.load_mirror()
        self.assertFalse(hasattr(mirror, "HTML_PAGE"),
                         "HTML_PAGE is back -- the crawler decides for itself again, and the two "
                         "answers will drift the way they did before")
        self.assertIs(mirror.looks_like_a_document, common.looks_like_a_document)

    def test_THE_CALL_SITE_EXISTS_AND_TAKES_THE_NARROW_ONE(self):
        """Read as text, because the crawler cannot be run from here without a host to crawl.

        Two separate things, and a message for each. That the export has a CALLER at all: it was
        offered with none until this change, which is the worst of the three possible states --
        an unused export cannot be wrong, so nothing keeps it honest. And that the caller takes
        the NARROW predicate: swapping in looks_like_a_page compiles, passes every other test
        here, and quietly starts asking strangers' servers to run their .cgi.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "mirror.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("looks_like_a_page(child)", src,
                         "the crawler took the WIDE predicate -- it now follows .asp/.jsp/.cgi "
                         "on hosts that are not ours")
        self.assertIn("looks_like_a_document(child)", src,
                      "the crawler no longer calls looks_like_a_document -- either it decides "
                      "for itself again, or the export is back to having no caller")

class TestTheTwoExtensionQuestions(unittest.TestCase):
    """A FILE NAME and a URL are different strings, and one function for both is wrong for one.

    They were one function until 2026-09-23, and it parsed everything as a url. Measured over
    291 226 stored names: it disagreed with os.path.splitext 8 192 times, and 208 of those were
    PDFs -- `Forvus_Technical_Bulletin_#107.pdf`, `SS#7_Protocol_Set_ANSI_Reference_Manual.pdf`
    -- where urlsplit had read `#107.pdf` as a fragment and left the name as `Forvus_Technical_
    Bulletin_`. So there are two, and each says in its name which string it takes.
    """

    def test_the_ordinary_case_is_the_same_for_both(self):
        for s in ("a.html", "dir/b.HTM", "x.tar.gz", "plain", ""):
            self.assertEqual(common.file_extension(s), common.url_extension(s), s)

    def test_A_HASH_IS_A_CHARACTER_IN_A_FILE_NAME(self):
        # 208 real PDFs in this collection. A name is not a url and must not be parsed as one.
        for name in ("Forvus_Technical_Bulletin_#107.pdf",
                     "IDAC-601130_SS#7_Monitor_User_Manual_Ver_2.0_Nov1990.pdf"):
            self.assertEqual(common.file_extension(name), ".pdf", name)

    def test_AND_A_FRAGMENT_IS_NOT_PART_OF_A_URL(self):
        # The same two characters, the opposite answer, because the string means something else.
        self.assertEqual(common.url_extension("http://h/paper.html#section2"), ".html")
        self.assertEqual(common.url_extension("http://h/paper.html?print=1"), ".html")

    def test_A_NAME_ENDING_IN_A_DOT_HAS_NO_EXTENSION(self):
        """os.path.splitext answers "." here, and 25 stored names in this collection end so.

        They are the names long_path() exists for -- Windows strips a trailing dot while OPENING
        the file -- and "." is a value no caller has a use for: as a table row it means nothing,
        and as a lookup key it matches nothing.
        """
        self.assertEqual(os.path.splitext("TALK.")[1], ".", "splitext changed; re-read this")
        for name in ("TALK.", "a.", "..."):
            self.assertEqual(common.file_extension(name), "", name)

    def test_a_leading_dot_is_a_name_not_a_type(self):
        for name in (".gitignore", ".htaccess", "dir/.bashrc"):
            self.assertEqual(common.file_extension(name), "", name)

    def test_a_dot_in_a_PARENT_DIRECTORY_is_not_the_files_extension(self):
        self.assertEqual(common.file_extension("some.dir/plainfile"), "")
        self.assertEqual(common.url_extension("http://h/v1.2/README"), "")

    def test_A_URL_ENDING_IN_A_SLASH_ADDRESSES_A_DIRECTORY(self):
        # Including when the directory is called `icons.gif`, which one here is.
        for url in ("http://h/docs/", "http://h/icons.gif/", "http://h/page.html/"):
            self.assertEqual(common.url_extension(url), "", url)

    def test_the_answer_is_lowercase_and_keeps_its_dot(self):
        self.assertEqual(common.file_extension("READ.TXT"), ".txt")
        self.assertEqual(common.url_extension("http://H/A.HTML"), ".html")

    def test_IT_AGREES_WITH_THE_PREDICATES_THAT_USE_EXTENSIONS(self):
        """The library must not hold two ideas of what a suffix is.

        looks_like_a_document() asks endswith() against a table of suffixes; this returns one.
        If the two ever disagreed, a name would be a page by one and not by the other, and which
        answer a caller got would depend on which function it happened to reach for.
        """
        for ext in common.PAGE_EXTENSIONS:
            self.assertEqual(common.file_extension("index" + ext), ext, ext)
            self.assertTrue(common.looks_like_a_page("index" + ext), ext)

    def test_NO_TOOL_DERIVES_AN_EXTENSION_BY_HAND(self):
        """Seven sites did until 2026-09-23, and two of them were wrong in the same way.

        `os.path.splitext(x)[1].lower()` answers "." for a name ending in a dot, and both
        audit.py and blogger-sitemap.py then asked `if ext:` -- so `TALK.` counted as HAVING an
        extension and took the wrong branch in each. One shared function cannot drift; seven
        cannot help it.

        TWO EXEMPTIONS, both named rather than pattern-matched away. load_peer() takes
        splitext(...)[0], the STEM, which is a different question. And file_extension() itself
        has to call splitext, because somebody has to -- that is the whole point of there being
        one place. Test files are not scanned: naming the thing is how they describe it.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        allowed = {"common.py": {"ext = os.path.splitext(name)[1]"}}
        found = []
        for name in sorted(os.listdir(here)):
            if not name.endswith(".py") or name.endswith(("_test.py", "-test.py")):
                continue
            with io.open(os.path.join(here, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if line.lstrip().startswith("#") or "splitext" not in line:
                        continue
                    if line.strip() in allowed.get(name, ()) or "splitext(filename)[0]" in line:
                        continue
                    if "[1]" in line:
                        found.append("%s:%d" % (name, i))
        self.assertEqual(found, [],
                         "use common.file_extension (a name) or common.url_extension (a url)")

    def test_and_with_the_magic_table(self):
        # magic_mismatch keys MAGIC by the same suffix, so a name it accepts must be one this
        # function produces -- otherwise a signature check silently looks nothing up.
        for ext in common.MAGIC:
            self.assertEqual(common.file_extension("x" + ext), ext, ext)

class TestNothingShadowsTheLibrary(unittest.TestCase):
    r"""A tool that imports a name from common and then defines it is calling ITSELF.

    THIS IS NOT STYLE. ia-item-fetch.py did exactly that until 2026-09-23: it imported
    write_marker, defined a write_marker() of its own, and inside it called `write_marker(...)`
    meaning the library's. Python bound the name to the local function, so it recursed until
    memory gave out -- 31 frames, all the same line -- and the tool could not write a completion
    marker at all. Nothing caught it: --help never reaches that code, no test file covers the
    module, and a dead-import check sees the name used because the recursive call IS a use.

    mirror.py had the answer from the start: `write_marker as common_write_marker`.
    """

    HERE = os.path.dirname(os.path.abspath(__file__))

    def tools(self):
        for name in sorted(os.listdir(self.HERE)):
            if name.endswith(".py") and name != "common.py":
                yield name

    @staticmethod
    def imported_from_common(tree):
        """-> {the name a module BINDS} for every `from common import ...`, alias respected."""
        out = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "common":
                for a in node.names:
                    out.add(a.asname or a.name)
        return out

    @staticmethod
    def defined_at_module_level(tree):
        out = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        out.add(t.id)
        return out

    def test_NO_TOOL_DEFINES_A_NAME_IT_ALSO_IMPORTS_FROM_COMMON(self):
        """The dangerous half: the import is dead and every call goes to the local one."""
        clashes = []
        for name in self.tools():
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            both = self.imported_from_common(tree) & self.defined_at_module_level(tree)
            clashes += ["%s: %s" % (name, n) for n in sorted(both)]
        self.assertEqual(clashes, [],
                         "import it under another name (`x as common_x`) or rename the local one")

    def test_and_the_repaired_one_really_reaches_the_library(self):
        """Not just 'it imports an alias' -- that it WRITES, which is what failed."""
        iaf = common.load_peer("ia-item-fetch.py", "_shadow_iaf")
        self.assertIs(iaf.common_write_marker, common.write_marker)
        d = tempfile.mkdtemp()
        try:
            with io.open(os.path.join(d, "one.txt"), "w") as fh:
                fh.write("hi")
            said = []
            iaf.write_marker(d, "an-item", said.append)
            with io.open(os.path.join(d, common.COMPLETE_MARKER), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("archive", text)
            self.assertIn("an-item", text)
            self.assertEqual(common.read_marker(os.path.join(d, common.COMPLETE_MARKER))["files"],
                             "1")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_A_NAME_REUSED_WITHOUT_IMPORTING_IT_IS_LISTED_NOT_BANNED(self):
        """The softer half, and deliberately not an error.

        Reusing a library name locally without importing it cannot recurse -- nothing is
        shadowed, because nothing was bound. It is still worth seeing: a reader who knows
        common.local_path() will assume wayback-salvage.local_path() is it, and it is not.
        The list is pinned so a new one has to be added on purpose.
        """
        known = {
            # All three WRAP common.write_marker deliberately and import it under an alias:
            # the FORMAT is the library's, the WORDS are each tool's. That is the correct shape,
            # and the alias is exactly what ia-item-fetch.py was missing.
            #
            # manifest-fetch.py joined them on 2026-09-27, for the same reason ia-item-fetch.py
            # did: an archive fetched from a URL LIST and never crawled has no marker unless the
            # fetcher writes one, and without a marker catalogue.py reports it as `None files,
            # 0.0 GB` -- on disk and invisible to every report. Its prose says what a crawl's
            # cannot: completeness here means "everything the list named".
            "ia-item-fetch.py": {"write_marker"},
            "manifest-fetch.py": {"write_marker"},
            "mirror.py": {"write_marker"},
            # THREE MORE STOOD HERE UNTIL 2026-09-24 and have been renamed away, because each
            # answered a DIFFERENT question under a name the library already used:
            #   marker_text   -> read_marker_text   it READS a marker; the library's FORMATS one
            #   read_manifest -> read_tar_listing   a tar listing is not a checksum index
            #   local_path    -> salvage_path       an ARCHIVED url is not a live one
            # None of them could recurse -- nothing was shadowed, because nothing was imported --
            # so the only thing wrong was that a reader would reach for the wrong one. That is
            # reason enough: the whole point of one home per name is that the name says where.
            "wayback-salvage.py": {"MIN_FREE_BYTES"},
        }
        exported = set(common.__all__)
        found = {}
        for name in self.tools():
            with io.open(os.path.join(self.HERE, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            reused = (self.defined_at_module_level(tree) & exported
                      - self.imported_from_common(tree))
            if reused:
                found[name] = reused
        self.assertEqual(found, known,
                         "a tool started or stopped reusing a library name -- say which and why")

class TestParseDate(unittest.TestCase):
    """Every claim parse_date's docstring makes, executable. It had no test of its own.

    NOT PINNED AS AN EPOCH NUMBER. time.mktime reads local time, so an absolute constant here
    would fail by the machine's time zone -- parse_listing_test.py's first draft did exactly that
    and was wrong by eight hours. Each answer is compared through the same localtime it came from.
    """

    def back(self, epoch):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))

    def test_every_format_the_table_lists_is_read(self):
        # DATE_FORMATS is the promise; this is it kept, one entry at a time.
        for text, want in (("12-Jan-2011 09:22", "2011-01-12 09:22"),      # %d-%b-%Y %H:%M
                           ("2011-01-12 09:22", "2011-01-12 09:22"),       # %Y-%m-%d %H:%M
                           ("12-Jan-2011 09:22:33", "2011-01-12 09:22"),   # %d-%b-%Y %H:%M:%S
                           ("2011-Jan-12 09:22", "2011-01-12 09:22")):     # %Y-%b-%d %H:%M
            got = common.parse_date(text)
            self.assertIsNotNone(got, text)
            self.assertEqual(self.back(got), want, text)
        self.assertEqual(len(common.DATE_FORMATS), 4,
                         "a format was added or removed -- give it a line above")

    def test_SECONDS_ARE_DROPPED_because_the_index_has_none(self):
        # The docstring says minute precision. Two listings of the same file, one with seconds,
        # must not look like two different files to a caller comparing timestamps.
        self.assertEqual(self.back(common.parse_date("12-Jan-2011 09:22:33")),
                         self.back(common.parse_date("12-Jan-2011 09:22")))

    def test_A_DATE_THE_PLATFORM_CANNOT_HOLD_IS_NONE_NOT_ZERO(self):
        """The defect this function was repaired for, on 2026-09-23.

        time.mktime raises OverflowError for any date outside the platform's time_t -- and
        `01-Jan-1900 00:00` is enough. A listing of genuinely old files is exactly where such a
        date appears, and the crawler died on one in the PRODUCER thread, which has no handler
        of its own. Catching only ValueError was the bug; the same shape as parse_size's.

        None, not 0: the caller then stamps the file with nothing rather than with 1970.
        """
        self.assertIsNone(common.parse_date("01-Jan-1900 00:00"))
        self.assertIsNone(common.parse_date("01-Jan-1800 00:00"))

    def test_and_it_raises_nothing_at_all(self):
        # A parser in a producer thread must return, never raise, whatever the page holds.
        for text in ("", "-", None, "not a date", "99-Xyz-9999 99:99", "\x00", "-" * 400):
            self.assertIsNone(common.parse_date(text), repr(text)[:40])

    def test_surrounding_space_is_not_a_different_date(self):
        self.assertEqual(common.parse_date("  12-Jan-2011 09:22  "),
                         common.parse_date("12-Jan-2011 09:22"))


class TestResolutionBase(unittest.TestCase):
    r"""What relative links on a page resolve against. Used by mirror.py and measure-remote.py,
    and tested by neither until now.

    THE CASE IT EXISTS FOR is unixos2.org: its pages carry `<base href="/mirrors/unixos2.org/">`,
    the path it occupied on its ORIGINAL host, while infania serves it at /sites/unixos2.org/ and
    has no /mirrors/ at all. Honour the tag blindly and every root-relative link doubles a path
    segment -- 36 permanent 404s on 2026-09-07, and the whole `packages/` branch missing.
    """

    BASE = "http://infania.net/sites/unixos2.org/"
    PAGE = BASE + "pages/Downloads.html"

    def test_without_the_tag_a_page_resolves_against_itself(self):
        self.assertEqual(common.resolution_base("<html>x</html>", self.PAGE, self.BASE),
                         self.PAGE)

    def test_A_FOREIGN_BASE_IS_REBASED_ONTO_OUR_ROOT(self):
        body = '<html><head><base href="/mirrors/unixos2.org/"></head></html>'
        self.assertEqual(common.resolution_base(body, self.PAGE, self.BASE), self.BASE)

    def test_and_that_is_what_stops_the_doubled_path(self):
        """The 404 shape, reproduced: `pages/packages/GnuAwk/` written to mean "from the root"."""
        body = '<html><head><base href="/mirrors/unixos2.org/"></head></html>'
        got = urllib.parse.urljoin(
            common.resolution_base(body, self.PAGE, self.BASE), "pages/packages/GnuAwk/")
        self.assertEqual(got, self.BASE + "pages/packages/GnuAwk/")
        self.assertNotIn("/pages/pages/", got)

    def test_a_base_that_IS_under_our_root_is_honoured_as_written(self):
        # Not every <base> is a relic: one pointing inside the tree is the page telling the truth.
        inside = self.BASE + "pages/"
        body = '<html><head><base href="%s"></head></html>' % inside
        self.assertEqual(common.resolution_base(body, self.PAGE, self.BASE), inside)

    def test_the_tag_is_read_case_insensitively(self):
        body = '<HTML><HEAD><BASE HREF="/mirrors/unixos2.org/"></HEAD></HTML>'
        self.assertEqual(common.resolution_base(body, self.PAGE, self.BASE), self.BASE)

    def test_a_page_with_no_body_at_all_still_answers(self):
        for body in ("", "<html>", "<base>", '<base href="">'):
            self.assertTrue(common.resolution_base(body, self.PAGE, self.BASE).startswith("http"),
                            repr(body))


class TestTheRegexesToolsImportDirectly(unittest.TestCase):
    """Three exports a tool imports and no test touched. A promise nothing checked."""

    def test_BASE_RE_finds_the_tag_reachability_probe_asks_it_for(self):
        self.assertEqual(
            common.BASE_RE.search('<base href="http://h/p/">').group(1), "http://h/p/")
        self.assertEqual(
            common.BASE_RE.search('<BASE  HREF="/x/" >').group(1), "/x/")

    def test_and_answers_nothing_when_there_is_no_tag(self):
        for body in ("<html><head></head></html>", "", "<basement href='x'>"):
            self.assertIsNone(common.BASE_RE.search(body), repr(body))

    def test_UNSAFE_replaces_what_a_filesystem_refuses(self):
        # Three tools map URLs onto filenames with it. Windows refuses these outright.
        for ch in '<>:"|?*\\':
            self.assertEqual(common.UNSAFE.sub("_", "a%sb" % ch), "a_b", ch)
        for ch in "\x00\x01\x1f":
            self.assertEqual(common.UNSAFE.sub("_", "a%sb" % ch), "a_b", repr(ch))

    def test_BUT_NOT_THE_FORWARD_SLASH(self):
        # Every caller splits on it first; substituting it would turn a path into a name.
        self.assertEqual(common.UNSAFE.sub("_", "a/b"), "a/b")

    def test_AN_ENCODED_BACKSLASH_CANNOT_ESCAPE_THE_ROOT(self):
        r"""Found on 2026-09-23 by writing this class, and it was a path traversal.

        The backslash was not in UNSAFE. Callers split a url on "/" and pass each SEGMENT through
        safe_name(), so a separator that survives becomes extra directories -- and local_path()
        unquotes first, so `%5C` arrives as a real one. `http://h/..%5C..%5Cetc%5Cx` mapped to
        `root\..\..\etc\x`, which normalises to `..\etc\x`: OUTSIDE root. The `..` guard beside
        it drops `..` only as a whole segment and never saw these.

        Nothing stored was affected -- no path in the 98 archive indexes holds a backslash -- but
        the collection mirrors third-party servers, and where the bytes land must not be theirs
        to choose.
        """
        for url in ("http://h/..%5C..%5Cetc%5Cx",
                    "http://h/%2e%2e%5Cx",
                    "http://h/a%5Cb.html",
                    "http://h/" + "..%5C" * 8 + "x"):
            got = common.local_path("root", "http://h/", url)
            self.assertTrue(os.path.normpath(got).startswith("root"),
                            "%s escaped to %r" % (url, got))
            # and one url segment stayed one directory level
            self.assertEqual(got.count(os.sep), 1, "%s split into directories: %r" % (url, got))

    def test_and_a_literal_dotdot_segment_is_still_dropped(self):
        # The older guard, which the backslash slipped past. It must go on working.
        self.assertEqual(common.local_path("root", "http://h/", "http://h/../../x"),
                         os.path.join("root", "x"))

    def test_and_leaves_an_ordinary_name_alone(self):
        for name in ("readme.txt", "AS400-Summary.html", "a b.txt", "~tilde", "a+b(c).tar.gz"):
            self.assertEqual(common.UNSAFE.sub("_", name), name, name)

    def test_COLLECTION_SUMS_is_the_name_checksums_py_writes(self):
        # A collection-wide manifest, NOT an archive's .sha256sum -- confusing the two is how a
        # per-archive tool once wrote collection-index.csv into an archive.
        self.assertNotEqual(common.COLLECTION_SUMS, common.SUMS_FILE)
        self.assertTrue(common.COLLECTION_SUMS.endswith(".sha256sum"), common.COLLECTION_SUMS)
        self.assertFalse(common.COLLECTION_SUMS.startswith("."),
                         "a collection manifest is not a hidden per-archive file")

class TestIterArchives(unittest.TestCase):
    """The outer loop two tools wrote separately, and a third would have written again.

    corpus-coverage.py and page-extensions.py each carried it character for character -- sorted
    listdir, skip what is not a directory, skip `logs` -- until 2026-09-23. What differs between
    those tools is what they do INSIDE an archive; finding the archives is not theirs.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="archives-test-")
        for d in ("zeta", "alpha", "logs", "__pycache__", "middle"):
            os.makedirs(os.path.join(self.tmp, d))
        with io.open(os.path.join(self.tmp, "CATALOGUE.md"), "w") as fh:
            fh.write("a file, not an archive\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def names(self, **kw):
        return [n for n, _p in common.iter_archives(self.tmp, **kw)]

    def test_sorted_by_name(self):
        # Two runs of a report must list archives in the same order or a diff means nothing.
        self.assertEqual(self.names(), ["alpha", "middle", "zeta"])

    def test_LOGS_IS_NOT_AN_ARCHIVE(self):
        # Measured over the real collection on 2026-09-23: 99 top-level directories, and exactly
        # one -- logs -- carries no completion marker.
        self.assertNotIn("logs", self.names())
        self.assertIn("logs", common.COLLECTION_DIRS)

    def test_and_neither_is___pycache__(self):
        self.assertNotIn("__pycache__", self.names())
        self.assertIn("__pycache__", common.NEVER_CONTENT_DIRS)

    def test_a_FILE_at_the_top_is_not_an_archive(self):
        self.assertNotIn("CATALOGUE.md", self.names())

    def test_the_path_carries_the_long_prefix(self):
        """Forgetting it is SILENT: os.walk returns nothing for a path Windows will not open,
        and a tool then reports an empty archive instead of failing."""
        for _n, p in common.iter_archives(self.tmp):
            self.assertTrue(p.startswith(common.LONG_PREFIX) or os.name != "nt", p)

    def test_only_selects_one(self):
        self.assertEqual(self.names(only="middle"), ["middle"])

    def test_AND_only_MATCHING_NOTHING_IS_NOT_AN_ERROR(self):
        # The caller says what an empty run means in its own words; this does not guess.
        self.assertEqual(self.names(only="no-such-archive"), [])

    def test_and_only_cannot_reach_a_skipped_directory(self):
        # Naming `logs` explicitly must not smuggle it back in.
        self.assertEqual(self.names(only="logs"), [])

    def test_it_agrees_with_what_the_tools_used_to_do_by_hand(self):
        """The shape both tools carried, reproduced here and compared. If iter_archives ever
        stops matching it, that is a change of behaviour in two tools at once."""
        by_hand = []
        for name in sorted(os.listdir(self.tmp)):
            p = common.long_path(os.path.join(self.tmp, name))
            if not os.path.isdir(p) or name == "logs":
                continue
            by_hand.append(name)
        self.assertEqual([n for n in by_hand if n != "__pycache__"], self.names())


class TestNeverContentDirs(unittest.TestCase):
    """A constant that had been extracted and then left with no caller at all."""

    def test_what_it_holds(self):
        self.assertEqual(set(common.NEVER_CONTENT_DIRS), {"__pycache__"})

    def test_IT_HAS_A_CALLER_AGAIN(self):
        """It was exported, documented as 'three tools each carried this one name', and then
        used by nothing outside common.py -- while audit.py went on writing "__pycache__" out
        by hand. An extracted constant nobody calls is a rename waiting to go wrong."""
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "audit.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("NEVER_CONTENT_DIRS", src)
        self.assertNotIn('d != "__pycache__"', src)

    def test_the_two_sets_are_different_questions(self):
        # NEVER_CONTENT_DIRS is about any tree; COLLECTION_DIRS is about a mirror root only.
        self.assertFalse(set(common.NEVER_CONTENT_DIRS) & set(common.COLLECTION_DIRS))

    def test_both_are_immutable(self):
        for name in ("NEVER_CONTENT_DIRS", "COLLECTION_DIRS"):
            self.assertIsInstance(getattr(common, name), frozenset, name)

class TestIsAllZero(unittest.TestCase):
    """A transfer that failed and was kept as content. The logic lived in audit.py alone.

    IT ANSWERS THREE THINGS, not two, and the third is the one callers get wrong: None means the
    file could not be read, and a caller that folds it into False reports a tree as clean because
    part of it was unreadable.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="zero-test-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, name, data):
        p = os.path.join(self.d, name)
        with io.open(p, "wb") as fh:
            fh.write(data)
        return p

    def test_a_file_of_nothing(self):
        self.assertIs(common.is_all_zero(self.write("a", bytes(33615))), True)

    def test_A_ZERO_LENGTH_FILE_IS_NOT_THIS(self):
        # 20 archives here hold empty files on purpose. That is EMPTY_SHA256's question.
        self.assertIs(common.is_all_zero(self.write("empty", b"")), False)

    def test_AN_UNREADABLE_FILE_IS_NONE_AND_NOT_FALSE(self):
        self.assertIsNone(common.is_all_zero(os.path.join(self.d, "does-not-exist")))
        self.assertIsNone(common.is_all_zero(self.d))          # a directory is not a file

    def test_ordinary_content(self):
        for data in (b"hello", b"\x1f\x8b" + bytes(998), os.urandom(9000)):
            self.assertIs(common.is_all_zero(self.write("x", data)), False, repr(data[:4]))

    def test_A_FILE_THAT_ONLY_BEGINS_WITH_ZEROS_IS_NOT_ALL_ZERO(self):
        """The shortcut's blind spot, if it had one.

        A real ROM image or a sector dump can open with kilobytes of nothing and still hold data.
        Calling one a failed transfer sends somebody re-fetching a file that was never wrong.
        """
        self.assertIs(common.is_all_zero(
            self.write("rom", bytes(common.ZERO_PROBE) + b"REAL" + bytes(500))), False)

    def test_and_the_data_may_sit_far_past_the_probe(self):
        # Past the confirming chunk too, so the loop -- not the probe -- has to find it.
        self.assertIs(common.is_all_zero(
            self.write("big", bytes(common.HASH_CHUNK * 2) + b"x")), False)

    def test_a_file_of_exactly_the_probe_length(self):
        self.assertIs(common.is_all_zero(self.write("p", bytes(common.ZERO_PROBE))), True)

    def test_one_byte_short_of_zero(self):
        self.assertIs(common.is_all_zero(self.write("q", bytes(5000) + b"\x01")), False)
        self.assertIs(common.is_all_zero(self.write("r", b"\x01" + bytes(5000))), False)

    def test_THE_PROBE_IS_AN_OPTIMISATION_AND_NOT_A_RULE(self):
        """Same answer whatever the probe size, or it is deciding rather than shortcutting."""
        p = self.write("mixed", bytes(9000) + b"z" + bytes(9000))
        for probe in (1, 16, 4096, 8192, 1 << 20):
            self.assertIs(common.is_all_zero(p, probe=probe), False, probe)
        z = self.write("zed", bytes(9000))
        for probe in (1, 16, 4096, 8192, 1 << 20):
            self.assertIs(common.is_all_zero(z, probe=probe), True, probe)

    def test_it_reads_a_path_no_ordinary_open_could(self):
        # long_path inside, like sha256_file. A deep or dotted name must not read as unreadable.
        deep = os.path.join(self.d, "a" * 60, "b" * 60, "c" * 60)
        os.makedirs(deep)
        p = os.path.join(deep, "x.gz")
        with io.open(common.long_path(p), "wb") as fh:
            fh.write(bytes(4000))
        self.assertIs(common.is_all_zero(p), True)

    def test_IT_IS_A_DIFFERENT_QUESTION_FROM_EMPTY_SHA256(self):
        """Both are about "nothing", and confusing them is how a real file gets deleted.

        EMPTY_SHA256 identifies a file of ZERO LENGTH. is_all_zero identifies a file of PLAUSIBLE
        length holding nothing. The first is legitimate content; the second is damage.
        """
        empty = self.write("len0", b"")
        zeros = self.write("len33k", bytes(33615))
        self.assertEqual(common.sha256_file(empty), common.EMPTY_SHA256)
        self.assertNotEqual(common.sha256_file(zeros), common.EMPTY_SHA256)
        self.assertIs(common.is_all_zero(empty), False)
        self.assertIs(common.is_all_zero(zeros), True)

    def test_and_audit_py_asks_the_library_rather_than_repeating_it(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "audit.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("is_all_zero", src,
                      "check_empty reimplemented the zero scan instead of calling the library")

class TestPacer(unittest.TestCase):
    """The waiting, tested without waiting.

    WHY IT IS WORTH ITS OWN CLASS. `Pacer` was written because 42 `time.sleep` calls in 18 tools
    had drifted into two different meanings of the word "delay", and the one this collection
    actually promises its sources -- an interval between requests, not an idle period after each
    one -- was implemented in exactly one of them.
    """

    def setUp(self):
        self.now = [0.0]
        self.slept = []

    def pacer(self, pause=0.7):
        def sleep(seconds):
            self.slept.append(round(seconds, 6))
            self.now[0] += seconds
        return common.Pacer(pause, clock=lambda: self.now[0], sleep=sleep)

    def test_the_first_request_to_a_host_does_not_wait(self):
        """There is no interval before the first request, so there is nothing to keep to."""
        self.assertEqual(self.pacer().wait("h"), 0.0)
        self.assertEqual(self.slept, [])

    def test_the_second_request_waits_the_whole_pause(self):
        p = self.pacer()
        p.wait("h")
        self.assertEqual(p.wait("h"), 0.7)
        self.assertEqual(self.slept, [0.7])

    def test_another_host_does_not_wait_behind_the_first(self):
        p = self.pacer()
        p.wait("one")
        self.assertEqual(p.wait("two"), 0.0)
        self.assertEqual(self.slept, [])

    def test_TIME_ALREADY_SPENT_COUNTS_TOWARDS_THE_PAUSE(self):
        """The whole reason this is not `time.sleep(delay)`.

        A Crawl-delay of 0.7 s means "no more often than every 0.7 s". A request that itself took
        0.5 s has already paid five sevenths of it, and the blind form would wait the full 0.7 on
        top -- nearly twice as long as the operator asked for.
        """
        p = self.pacer()
        p.wait("h")
        self.now[0] += 0.5                      # the request took half the pause
        self.assertAlmostEqual(p.wait("h"), 0.2)
        self.assertEqual(self.slept, [0.2])

    def test_a_request_slower_than_the_pause_never_waits(self):
        p = self.pacer()
        p.wait("h")
        self.now[0] += 5.0
        self.assertEqual(p.wait("h"), 0.0)
        self.assertEqual(self.slept, [])

    def test_IT_NEVER_SLEEPS_A_NEGATIVE_NUMBER(self):
        """`time.sleep(-1)` raises, and a clock that jumps is not hypothetical.

        monotonic() is what the default uses for this reason; the test pins the behaviour rather
        than the choice of clock, because a caller may pass its own.
        """
        p = self.pacer()
        p.wait("h")
        self.now[0] += 10_000.0
        self.assertEqual(p.wait("h"), 0.0)
        self.assertEqual(self.slept, [])

    def test_a_pause_of_zero_never_sleeps(self):
        # Tools pass pause=0 in their own tests. It must be a no-op, not a sleep(0) per row.
        p = self.pacer(pause=0)
        p.wait("h")
        p.wait("h")
        self.assertEqual(self.slept, [])

    def test_each_host_keeps_its_own_clock(self):
        """Two hosts interleaved: each wait is measured from THAT host's last request.

        And the second wait is ZERO, which is worth pinning rather than glossing: sleeping on
        behalf of `a` also passes the time `b` was owed. That is what pacing by a clock buys over
        counting requests -- time spent for any reason counts, including time spent being polite
        to somebody else.
        """
        p = self.pacer()
        p.wait("a")
        p.wait("b")
        self.now[0] += 0.4
        self.assertAlmostEqual(p.wait("a"), 0.3)   # 0.4 of 0.7 had already elapsed
        self.assertEqual(p.wait("b"), 0.0)         # the 0.3 just slept was b's remainder too

    def test_but_a_host_asked_again_immediately_still_waits(self):
        """The guard on the test above -- it must not pass because nothing ever waits."""
        p = self.pacer()
        p.wait("a")
        p.wait("b")
        self.assertAlmostEqual(p.wait("a"), 0.7)
        self.assertEqual(self.slept, [0.7])

    def test_the_default_clock_is_monotonic_and_the_default_sleep_is_time_sleep(self):
        # The defaults are what every caller gets. A wall clock here would make a clock
        # correction during a long fetch produce a negative wait.
        p = common.Pacer(0.7)
        self.assertIs(p._clock, time.monotonic)
        self.assertIs(p._sleep, time.sleep)


class TestBackoff(unittest.TestCase):
    """The other meaning of a pause: how long before trying AGAIN.

    Kept apart from `TestPacer` because the two are opposites in the property that matters. A
    rate is the same every time; a backoff must grow, or repeating a failed request at the
    original rate is how a struggling server gets pushed over.
    """

    def setUp(self):
        self.slept = []

    def b(self, **kw):
        kw.setdefault("sleep", self.slept.append)
        return common.Backoff(**kw)

    def test_the_ladder_grows(self):
        got = [self.b(first=1, factor=2).seconds(i) for i in range(6)]
        self.assertEqual(got, [1, 2, 4, 8, 16, 32])

    def test_attempt_zero_is_the_FIRST_RETRY_and_gets_first(self):
        """Off by one here means the first retry is instant or the last never happens."""
        self.assertEqual(self.b(first=5).seconds(0), 5)

    def test_the_cap_holds(self):
        got = [self.b(first=1, factor=2, cap=10).seconds(i) for i in range(8)]
        self.assertEqual(got, [1, 2, 4, 8, 10, 10, 10, 10])

    def test_THROTTLED_WAITS_LONGER_THAN_AN_ORDINARY_FAILURE(self):
        """The one distinction worth keeping, and only one tool made it.

        429 and 503 are the server talking about US. Every other error is a thing that happened;
        those two are a request, and the only cooperative reply is to wait longer than we
        otherwise would.
        """
        back = self.b(first=1, factor=2)
        for i in range(5):
            self.assertGreater(back.seconds(i, throttled=True), back.seconds(i), i)

    def test_a_throttled_ladder_can_be_given_outright(self):
        back = self.b(first=12, factor=1, throttled_first=30, throttled_factor=1)
        self.assertEqual([back.seconds(i) for i in range(3)], [12, 12, 12])
        self.assertEqual([back.seconds(i, throttled=True) for i in range(3)], [30, 30, 30])

    def test_the_cap_applies_to_the_throttled_ladder_too(self):
        back = self.b(first=10, factor=10, cap=100)
        self.assertEqual(back.seconds(3, throttled=True), 100)

    def test_wait_sleeps_exactly_what_seconds_promised(self):
        back = self.b(first=2, factor=3)
        for i in range(4):
            want = back.seconds(i)
            self.assertEqual(back.wait(i), want)
        self.assertEqual(self.slept, [2, 6, 18, 54])

    def test_a_wait_of_zero_does_not_sleep_at_all(self):
        # sleep(0) per retry is a syscall that buys nothing, and in a test it is noise.
        self.assertEqual(self.b(first=0).wait(0), 0)
        self.assertEqual(self.slept, [])

    def test_SECONDS_AND_WAIT_ARE_SEPARATE_BECAUSE_CALLERS_LOG_FIRST(self):
        """`mirror.py` writes "RETRY 2/5 in 120s" BEFORE it spends the 120 s.

        A single method that slept and then returned the number would force every such caller
        to compute the wait itself -- which is how four different ladders came to exist.
        """
        back = self.b(first=4)
        self.assertEqual(back.seconds(2), 16)
        self.assertEqual(self.slept, [])          # asking did not cost anything
        back.wait(2)
        self.assertEqual(self.slept, [16])

    def test_a_negative_attempt_is_a_programming_error_and_raises(self):
        # Returning 0 would turn an off-by-one into a retry storm nobody can see in a log.
        with self.assertRaises(ValueError):
            self.b().seconds(-1)

    def test_a_factor_below_one_is_refused(self):
        """It would SHRINK the wait, which is the opposite of a backoff."""
        with self.assertRaises(ValueError):
            self.b(factor=0.5)

    def test_a_negative_first_is_refused(self):
        with self.assertRaises(ValueError):
            self.b(first=-1)

    def test_IT_REPRODUCES_ALL_FOUR_LADDERS_THAT_WERE_ALREADY_HERE(self):
        """The test that decides whether this class was worth writing.

        If it cannot express what the tools already do, converting them means changing a
        crawler's behaviour to suit a class -- which is the wrong way round, and the reason
        `step` exists beside `factor`. Two of the four grow geometrically and two arithmetically.
        """
        # mirror.py, twice: 2 ** attempt
        self.assertEqual([self.b(first=1, factor=2).seconds(i) for i in range(5)],
                         [1, 2, 4, 8, 16])
        # mirror.py rsync: min(60 * attempt, 300)
        self.assertEqual(
            [self.b(first=0, factor=1, step=60, cap=300).seconds(i) for i in range(7)],
            [0, 60, 120, 180, 240, 300, 300])
        # suspect-reconsider.py: 30 * (attempt + 1) when throttled, a flat 12 otherwise
        ladder = self.b(first=12, factor=1, throttled_first=30, throttled_step=30)
        self.assertEqual([ladder.seconds(i) for i in range(4)], [12, 12, 12, 12])
        self.assertEqual([ladder.seconds(i, throttled=True) for i in range(4)],
                         [30, 60, 90, 120])

    def test_a_step_alone_grows_arithmetically(self):
        self.assertEqual([self.b(first=5, factor=1, step=5).seconds(i) for i in range(4)],
                         [5, 10, 15, 20])

    def test_a_negative_step_is_refused(self):
        with self.assertRaises(ValueError):
            self.b(step=-1)

    def test_the_throttled_ladder_inherits_the_step_unless_given_one(self):
        back = self.b(first=10, factor=1, step=10)
        self.assertEqual(back.seconds(2), 30)
        self.assertEqual(back.seconds(2, throttled=True), 40)   # first doubled, same step

    def test_it_is_deterministic(self):
        # No jitter on purpose: one machine against one host, and a log that can be compared
        # with another run is worth more here than spreading a thundering herd that does not
        # exist.
        a = [self.b(first=1, factor=2).seconds(i) for i in range(6)]
        b = [self.b(first=1, factor=2).seconds(i) for i in range(6)]
        self.assertEqual(a, b)


class TestPacerUnderThreads(unittest.TestCase):
    """`mirror.py` is a threaded crawler, so the library's pacer has to survive that."""

    def test_CALLERS_THAT_ARRIVE_TOGETHER_GET_DIFFERENT_SLOTS(self):
        """The bug the reservation scheme exists to prevent, tested without the clock.

        The naive version records "last = now" AFTER sleeping, so two callers arriving at the
        same instant both read the same stale `last`, both compute a wait of zero, and both fire
        at once -- precisely the moment a rate limit exists for. Here the clock never advances on
        its own, so every wait returned is the reservation and nothing else.

        NOT TIMED WITH A REAL CLOCK ON PURPOSE. Windows' sleep and monotonic granularity is
        around 15 ms, so a threshold small enough to keep the test fast is below the noise floor
        and a threshold above it makes a slow test that still occasionally lies.
        """
        now = [0.0]
        pacer = common.Pacer(0.7, clock=lambda: now[0], sleep=lambda s: None)
        waits = [pacer.wait("one-host") for _ in range(4)]
        self.assertEqual(waits, [0.0, 0.7, 1.4, 2.0999999999999996])

    def test_and_the_slots_are_still_spaced_when_the_clock_does_advance(self):
        now = [0.0]

        def sleep(seconds):
            now[0] += seconds
        pacer = common.Pacer(0.7, clock=lambda: now[0], sleep=sleep)
        seen = []
        for _ in range(4):
            pacer.wait("one-host")
            seen.append(now[0])
        self.assertEqual([round(t, 6) for t in seen], [0.0, 0.7, 1.4, 2.1])

    def test_it_survives_real_threads(self):
        """Not a timing assertion -- that the shared state does not tear under contention."""
        pacer = common.Pacer(0.0)
        seen = []
        lock = threading.Lock()

        def hit(i):
            pacer.wait("host-%d" % (i % 3))
            with lock:
                seen.append(i)

        threads = [threading.Thread(target=hit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(seen), list(range(20)))

    def test_two_hosts_do_not_block_each_other(self):
        """The reason the sleep happens OUTSIDE the lock.

        mirror.py's own pacer holds its lock across the sleep, which is right for one host and
        would serialise every worker the moment a second host appeared.
        """
        pacer = common.Pacer(0.20)
        pacer.wait("a")
        pacer.wait("b")
        started = time.monotonic()
        pacer.wait("c")
        self.assertLess(time.monotonic() - started, 0.10)


class TestHttpTry(unittest.TestCase):
    """A request that never raises, checked without sending one.

    THE WHOLE VALUE IS THAT THE TWO KINDS OF "NO" STAY APART. A 404 is the server's settled
    answer; a timeout is our end of the wire. This collection writes down what is permanently
    gone, so a transient failure recorded as permanent is a wrong record that nobody revisits.
    """

    def opener(self, body=b"hi", status=200):
        def call(req, **kw):
            return _FakeResponse(body, {"Content-Type": "text/plain"}, status=status)
        return call

    def raiser(self, exc):
        def call(req, **kw):
            raise exc
        return call

    def test_an_answer_comes_back_as_an_int_and_bytes(self):
        self.assertEqual(common.http_try("http://h/x", opener=self.opener()), (200, b"hi"))

    def test_A_SERVERS_REFUSAL_IS_AN_INT(self):
        # It answered. The code IS the answer, and a caller may write it down as final.
        err = urllib.error.HTTPError("http://h/x", 404, "Not Found", {}, None)
        status, body = common.http_try("http://h/x", opener=self.raiser(err))
        self.assertEqual(status, 404)
        self.assertEqual(body, b"")

    def test_AND_A_FAILURE_TO_REACH_ANYONE_IS_A_STRING(self):
        # No server spoke. Nothing here is final, and the type name says what happened.
        for exc, want in ((urllib.error.URLError("no route"), "URLError"),
                          (TimeoutError("timed out"), "TimeoutError"),
                          (ConnectionResetError("reset"), "ConnectionResetError"),
                          (OSError("disk"), "OSError")):
            status, body = common.http_try("http://h/x", opener=self.raiser(exc))
            self.assertEqual(status, want)
            self.assertEqual(body, b"")

    def test_THE_TWO_ARE_TELLABLE_APART_WITHOUT_KNOWING_THE_CODES(self):
        """A caller decides "is this final" by TYPE, not by a list of numbers it has to keep."""
        err = urllib.error.HTTPError("http://h/x", 410, "Gone", {}, None)
        gone, _ = common.http_try("http://h/x", opener=self.raiser(err))
        down, _ = common.http_try("http://h/x", opener=self.raiser(TimeoutError()))
        self.assertIsInstance(gone, int)
        self.assertIsInstance(down, str)

    def test_it_raises_nothing_at_all(self):
        # The one promise in its name. Even something no HTTP layer should produce.
        for exc in (ValueError("nonsense"), KeyError("k"), RuntimeError("x")):
            status, body = common.http_try("http://h/x", opener=self.raiser(exc))
            self.assertIsInstance(status, str)
            self.assertEqual(body, b"")

    def test_BUT_IT_DOES_NOT_SWALLOW_AN_INTERRUPT(self):
        """Ctrl-C must still end the run. `except Exception` does not catch it, and that is the
        reason the clause says Exception and not BaseException."""
        with self.assertRaises(KeyboardInterrupt):
            common.http_try("http://h/x", opener=self.raiser(KeyboardInterrupt()))

    def test_limit_caps_the_body(self):
        # A probe wanting a page's head has no use for a 400 MB answer, and no way to know one
        # is coming.
        self.assertEqual(common.http_try("http://h/x", limit=2,
                                         opener=self.opener(b"abcdefgh"))[1], b"ab")

    def test_and_no_limit_reads_everything(self):
        self.assertEqual(common.http_try("http://h/x", opener=self.opener(b"abcdefgh"))[1],
                         b"abcdefgh")

    def test_the_method_is_passed_through(self):
        seen = {}

        def call(req, **kw):
            seen["method"] = req.get_method()
            return _FakeResponse(b"", {})
        common.http_try("http://h/x", method="HEAD", opener=call)
        self.assertEqual(seen["method"], "HEAD")

    def test_and_so_is_the_identity_this_collection_sends(self):
        seen = {}

        def call(req, **kw):
            seen["ua"] = req.get_header("User-agent")
            return _FakeResponse(b"", {})
        common.http_try("http://h/x", opener=call)
        self.assertEqual(seen["ua"], common.user_agent())

    def test_WHO_ASKS_THE_LIBRARY_AND_WHO_KEEPS_THEIR_OWN(self):
        """Both lists are deliberate, and every name on the second has a reason.

        THE FIRST VERSION OF THIS TEST ASSERTED ONE NAME AND FOUND FIVE. Looking for functions
        CALLED fetch or get had missed four tools that catch HTTPError in another shape -- which
        is the argument for pinning a LIST rather than a count: what the assertion has to name is
        exactly the entries nobody thought to look for.

        None of the four is a missed opportunity. Each does something http_try deliberately does
        not, and folding them into it would lose what they are for:

          manifest-fetch      counts a 404 as GONE -- a fact about the copy, not a failed run
          redbooks-fetch      branches on `code != 404` to decide whether to try the next
                              candidate url at all
          suspect-reconsider  sleeps 30 s on 429/503 and retries; a backoff ladder is not a
                              request
          mirror.py           the crawler's own retry and status handling, which is most of
                              what that file is
          subset-refetch      needs the Last-Modified header, which http_try does not hand back
          mediawiki.py        mediawiki_api retries with a rising wait, and waits LONGER on a
                              rate limit than on an ordinary error -- a ladder, not a request.
                              It is a library module rather than a tool, and it appears in this
                              list for the same reason as the rest: it handles the two kinds of
                              failure itself, on purpose.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        uses, keeps = [], []
        for name in sorted(os.listdir(here)):
            # TEST FILES ARE NOT PART OF THE CENSUS. The question here is which TOOLS issue
            # requests and which handle failure themselves; a test names `http_try` in order to
            # REPLACE it, and counting that as a caller turns the list into a list of files
            # containing a word. `ask-the-source-test.py` was the first to make the difference
            # visible, and it is exactly the kind of entry that would have been added to the
            # expected list without anybody asking what it was doing there.
            if not name.endswith(".py") or "test" in name or name == "common.py":
                continue
            with io.open(os.path.join(here, name), encoding="utf-8") as fh:
                src = fh.read()
            if "http_try" in src:
                uses.append(name)
            elif "except urllib.error.HTTPError" in src:
                keeps.append(name)
        # ask-the-source re-asks the hosts behind ZERO_AT_SOURCE. It wants exactly what http_try
        # gives -- a request that never raises and keeps "the server said no" apart from "nobody
        # answered" -- and reading that distinction from `body` instead of `status` was a live
        # defect in it for one afternoon. See its own comment.
        # find-sitemaps.py asks every archive's host for robots.txt and then for one sitemap. Both
        # requests are questions whose interesting answers are the negative ones -- no robots.txt,
        # HTTP 404, nothing listening -- and a raise on any of them would end a survey of a hundred
        # hosts at the first awkward one. It also needs the distinction http_try keeps: a 404 means
        # this host publishes no sitemap and is a result, while a timeout means ask again another
        # day and must not be written down as "none".
        self.assertEqual(uses, ["ask-the-source.py", "find-sitemaps.py", "reachability-probe.py",
                                "recheck-decisions.py"])
        self.assertEqual(keeps, ["manifest-fetch.py", "mediawiki.py", "mirror.py",
                                 "redbooks-fetch.py", "subset-refetch.py",
                                 "suspect-reconsider.py"],
                         "a tool started or stopped handling HTTPError itself -- if it is new, "
                         "say here what it does that http_try does not")

class TestTheConstantsNoTestTouched(unittest.TestCase):
    """Six exports that no test mentioned, measured 2026-09-24. None has a caller outside common.

    WHAT IS WORTH ASSERTING ABOUT A CONSTANT is not its value -- that is a copy of the source
    line and fails only when somebody changes it on purpose. It is the RELATIONSHIP between the
    constant and the function that reads it, because that is where the two drift apart: a
    signature added to one table and not to the predicate beside it, a suffix listed here and
    tested for by hand over there.

    They are kept on the surface rather than made private. Each is the stated form of something
    a caller could reasonably need to see -- what counts as markup, what an unfinished transfer
    is called -- and a promise with a test is cheaper than a rename through four call sites.
    """

    def test_HTML_HEADS_is_exactly_what_looks_like_html_accepts(self):
        for head in common.HTML_HEADS:
            self.assertTrue(common.looks_like_html(head), head)
        # and the predicate is not quietly wider than the table it is documented to use
        for other in (b"<body", b"<HEAD", b"GIF89a", b"%PDF", b""):
            self.assertFalse(common.looks_like_html(other), other)

    def test_and_every_entry_is_short_enough_to_be_read_from_a_probe(self):
        # magic_mismatch and is_all_zero both decide from a few bytes. A signature longer than
        # the shortest probe would be one this collection could never match.
        self.assertTrue(all(len(h) <= 5 for h in common.HTML_HEADS), common.HTML_HEADS)

    def test_PARTIAL_SUFFIXES_and_is_partial_are_one_answer(self):
        for suffix in common.PARTIAL_SUFFIXES:
            self.assertTrue(common.is_partial("file" + suffix), suffix)
        self.assertFalse(common.is_partial("file.txt"))

    def test_TWO_FUNCTIONS_DISAGREE_ABOUT_CASE_ON_PURPOSE(self):
        r"""is_partial() folds case and iter_tree() does not. Nothing tested the difference.

        THE TEST THAT FOUND THIS ASSERTED THE WRONG SIDE. It claimed is_partial("SOMETHING.PART")
        was False, on the strength of a note about split-archive volumes -- and the note is real,
        but it is attached to iter_tree(), not to this. Reading it settled which function carries
        the rule; guessing would have "fixed" the one that was already right.

        WHY THEY DIFFER. is_partial() answers a question about a NAME, for a report, where
        folding case costs nothing. iter_tree() decides what goes into A COUNT THAT MARKERS ON
        DISK WERE ALREADY WRITTEN AGAINST -- and a tree of software from the uppercase era can
        hold a genuine `SOMETHING.PART`, a split archive volume rather than half a download.
        Folding case there would drop it from the count, and every marker written before the
        change would report a mismatch for a change nobody made.
        """
        self.assertTrue(common.is_partial("SOMETHING.PART"))
        self.assertTrue(common.is_partial("x.Part"))

        d = tempfile.mkdtemp(prefix="case-part-")
        try:
            for name in ("real.txt", "SOMETHING.PART", "half.part"):
                with io.open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"x")
            kept = sorted(rel for rel, _full in common.iter_tree(d))
            self.assertEqual(kept, ["SOMETHING.PART", "real.txt"],
                             "iter_tree must keep the uppercase volume and drop the download")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_INDEX_PAGE_finds_a_generated_listing_and_not_a_document(self):
        for body in (b"<title> Index of /pub</title>", b"<h1>Index of /</h1>"):
            self.assertTrue(common.INDEX_PAGE.search(body), body)
        for body in (b"<title>Index of Contents</title>", b"<h1>Index</h1>", b"<p>Index of /</p>"):
            self.assertIsNone(common.INDEX_PAGE.search(body), body)

    def test_and_magic_mismatch_uses_it_to_name_the_case(self):
        why = common.magic_mismatch("x.pdf", b"<html><title>Index of /pub</title>")
        self.assertIn("directory listing", why or "")

    def test_SITEMAP_LOC_reads_what_a_sitemap_puts_a_url_in(self):
        got = common.SITEMAP_LOC.findall("<url><loc>http://h/a</loc></url><loc>http://h/b</loc>")
        self.assertEqual(got, ["http://h/a", "http://h/b"])

    def test_and_sitemap_locations_is_that_pattern_applied(self):
        self.assertEqual(common.sitemap_locations("<loc>http://h/x</loc>"), ["http://h/x"])

    def test_HASH_BATCH_is_a_count_of_files_not_of_bytes(self):
        # hash_tree checkpoints every HASH_BATCH FILES. Confusing it with HASH_CHUNK, which is a
        # read size in bytes, would make a 4 GB ISO checkpoint two thousand times.
        self.assertIsInstance(common.HASH_BATCH, int)
        self.assertLess(common.HASH_BATCH, common.HASH_CHUNK)
        sig = common.hash_tree.__code__.co_varnames[:common.hash_tree.__code__.co_argcount]
        self.assertIn("batch_size", sig)

    def test_MAX_CONSECUTIVE_REPEATS_is_what_looks_like_a_loop_allows(self):
        base = "http://h/pub/"
        deep = base + "a/" * (common.MAX_CONSECUTIVE_REPEATS + 2)
        self.assertTrue(common.looks_like_a_loop(deep, base), deep)
        shallow = base + "a/" * common.MAX_CONSECUTIVE_REPEATS
        self.assertFalse(common.looks_like_a_loop(shallow, base), shallow)

class TestADirectoryPageStoredAsAFile(unittest.TestCase):
    r"""The defect 33 files in this collection are still carrying, and what repaired one of them.

    WHAT HAPPENED. A crawler asked for `.../AIX/POWER/53`, the server redirected to `.../53/` and
    answered with the directory's own index, and the body was written to disk under the name
    `53`. mirror.py has skipped that case since 2026-09-11 -- these are older files -- and they
    block themselves: the directory can never be created while a file holds its name.

    MEASURED 2026-09-24. 33 such pages, listing 566 entries, of which 225 are held under another
    path in the same archive and **341 are absent**. `HPUX/PA/` shows both states side by side:
    `090x` is a file, `1020`, `1100` and `1111` are directories.

    THE REPAIR WAS PROVEN ON ONE. `ardent-tool/615x/AOS_43/Files`, a 6 241-byte page listing 26
    entries, was removed and the path re-crawled: the directory appeared and 25 of the 26 arrived.
    The twenty-sixth is `/615x/AOS_43/`, the parent link, which is not content.
    """

    def test_the_server_says_it_is_a_directory_and_the_library_hears_it(self):
        url = "https://h/pub/AIX/POWER/53"
        final = "https://h/pub/AIX/POWER/53/"
        self.assertTrue(common.same_path_plus_slash(url, final))

    def test_AND_A_REAL_REDIRECT_ELSEWHERE_IS_NOT_THAT(self):
        # Only the same path plus a slash. A redirect to a different page is a different thing,
        # and treating it as "this is a directory" would skip a file that exists.
        self.assertFalse(common.same_path_plus_slash("https://h/a", "https://h/b/"))
        self.assertFalse(common.same_path_plus_slash("https://h/a", "https://h/a/b/"))

    def test_A_FILE_AND_A_DIRECTORY_CANNOT_SHARE_A_NAME(self):
        """The reason this is damage rather than untidiness, stated as the filesystem states it.

        Everything the page lists is unreachable for as long as the page is there -- not missing
        from a report, but impossible to write.
        """
        d = tempfile.mkdtemp(prefix="dirpage-")
        try:
            blocked = os.path.join(d, "53")
            with io.open(blocked, "wb") as fh:
                fh.write(b"<html><h1>Index of /pub</h1></html>")
            with self.assertRaises(OSError):
                os.makedirs(blocked)
            # and once it is gone, the directory is ordinary
            os.remove(blocked)
            os.makedirs(blocked)
            self.assertTrue(os.path.isdir(blocked))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_magic_mismatch_names_it_whatever_the_name_looks_like(self):
        page = b"<html><title>Index of /pub/aix</title><h1>Index of /pub/aix</h1></html>"
        for name in ("53", "090x", "Files", "4x"):
            why = common.magic_mismatch(name, page)
            self.assertIsNotNone(why, name)
            self.assertIn("directory listing", why, name)

    def test_AND_A_SMALL_EXTENSIONLESS_FILE_THAT_IS_NOT_ONE_IS_LEFT_ALONE(self):
        # A directory name rarely carries an extension, so extensionless files are the candidates
        # -- but only the ones that really hold an index. A README must not be reported.
        self.assertIsNone(common.magic_mismatch("README", b"This directory holds the sources.\n"))

    def test_the_parent_link_a_listing_carries_is_not_content(self):
        """It is why a repaired directory holds one entry fewer than its page listed, and why
        that is not a loss. A count that treated it as a file would report every repair as
        incomplete by exactly one."""
        page = ('<a href="/615x/AOS_43/">Parent Directory</a>'
                '<a href="fixes/">fixes/</a><a href="bison-aos.tar.gz">bison-aos.tar.gz</a>')
        rows = [h for h, _s, _m in common.parse_listing(page)]
        self.assertIn("/615x/AOS_43/", rows)
        self.assertFalse(common.is_child_link("/615x/AOS_43/", allow_up=False) and False)
        # the two that are children of THIS directory
        children = [h for h in rows if not h.startswith("/")]
        self.assertEqual(children, ["fixes/", "bison-aos.tar.gz"])


class TestFollowListingsIsOffOnPurpose(unittest.TestCase):
    """A targeted re-fetch that follows listings stops being targeted, and this is the measurement.

    On 2026-09-24 one blocked directory was repaired with `--follow-listings`: the 26 entries it
    needed arrived, and the flag then queued **4 790 more** from the listings below it, of which
    4 477 were already held. The tool's own docstring says why the flag is off by default -- "a
    listing costs one request and may add dozens, which is how a targeted run turns back into a
    crawl" -- and that sentence is now a measurement rather than a caution.
    """

    HERE = os.path.dirname(os.path.abspath(__file__))

    def test_the_flag_defaults_to_off(self):
        with io.open(os.path.join(self.HERE, "subset-refetch.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"--follow-listings", action="store_true"', src)
        self.assertIn("turns back into a crawl", src)

    def test_and_the_budget_is_a_hard_ceiling_not_a_hint(self):
        with io.open(os.path.join(self.HERE, "subset-refetch.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("if spent >= args.budget:", src)
        self.assertIn("remaining.append(url)", src)

    def test_AND_WHAT_IT_COULD_NOT_REACH_IS_NOT_CALLED_A_LOSS(self):
        # An unanswered request and an absent file are different facts, and this collection keeps
        # records of what is permanently gone. Writing one down as the other poisons the record.
        with io.open(os.path.join(self.HERE, "subset-refetch.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("THESE ARE NOT LOSSES", src)

    def test_its_own_bookkeeping_file_is_not_counted_as_content(self):
        # STILL-MISSING.txt is written into the archive it describes. Counting it would move the
        # file count the marker was verified against.
        self.assertIn("STILL-MISSING.txt", common.BOOKKEEPING_FILES)

    def test_AND_A_MARKER_DOES_NOT_COUNT_IT_EITHER(self):
        """The wider set was not enough, and finding that out is the point of this test.

        BOOKKEEPING_FILES is what an auditor skips; OWN_FILES is what a marker's counts exclude,
        and iter_tree defaults to the narrow one. Adding the name to the wide set alone left the
        archive's file count exactly where it had been wrong -- 25 702 where the content is
        25 701 -- so `--verify` would still have reported a mismatch nobody had caused.
        """
        self.assertIn("STILL-MISSING.txt", common.OWN_FILES)

    def test_AND_THE_TWO_NAMES_THAT_STAY_OUT_STAY_OUT(self):
        """Not every file of ours may be excluded, and what decides is the data already stored.

        Four extracted archives were counted WITH their RENAMED.txt and SYMLINKS.txt, so putting
        those in the narrow set would make four existing markers disagree with their own trees.
        STILL-MISSING.txt is the opposite case -- measured 2026-09-24, the one copy in the
        collection is younger than the only marker in its archive -- which is why one name moved
        and these did not. A later tidy-up that collapses the two sets fails here.
        """
        for name in ("RENAMED.txt", "SYMLINKS.txt", "CATALOGUE.md", "SHA256SUMS"):
            self.assertIn(name, common.BOOKKEEPING_FILES, name)
            self.assertNotIn(name, common.OWN_FILES, name)

    def test_and_the_narrow_set_is_what_iter_tree_uses_unless_told_otherwise(self):
        """The mechanism the two tests above rely on, pinned so it cannot move underneath them."""
        d = tempfile.mkdtemp(prefix="ownfiles-")
        try:
            for name in ("real.tar.gz", "STILL-MISSING.txt", "RENAMED.txt"):
                with io.open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"x")
            counted = sorted(rel for rel, _full in common.iter_tree(d))
            self.assertEqual(counted, ["RENAMED.txt", "real.tar.gz"])
            audited = sorted(rel for rel, _full in
                             common.iter_tree(d, own_files=common.BOOKKEEPING_FILES))
            self.assertEqual(audited, ["real.tar.gz"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestPatience(unittest.TestCase):
    """The rule that stops a url-list fetch when the host has gone away.

    Written against the two incidents in the class docstring: dialectronics, where each further
    trip cost tolerance in the next window, and openpa, where six unanswered requests in a row
    were the signal a person acted on by hand.
    """

    def test_a_fresh_one_is_not_spent(self):
        self.assertFalse(common.Patience(limit=3).spent)

    def test_it_stops_at_the_limit_and_not_before(self):
        p = common.Patience(limit=3)
        self.assertFalse(p.went_quiet())
        self.assertFalse(p.went_quiet())
        self.assertTrue(p.went_quiet())
        self.assertTrue(p.spent)

    def test_an_answer_resets_the_run(self):
        """FOUR failures either side of one reply must not add up to eight."""
        p = common.Patience(limit=5)
        for _ in range(4):
            p.went_quiet()
        p.answered()
        for _ in range(4):
            self.assertFalse(p.went_quiet())
        self.assertFalse(p.spent)

    def test_scattered_failures_never_stop_a_healthy_run(self):
        """Nine failures spread through 2 000 requests is a lumpy archive, not a refusal."""
        p = common.Patience(limit=5)
        for i in range(2000):
            if i % 200 == 0:
                p.went_quiet()
            else:
                p.answered()
            self.assertFalse(p.spent)

    def test_the_worst_streak_is_kept_after_a_reset(self):
        """A run that survived may still want to report how close it came."""
        p = common.Patience(limit=9)
        for _ in range(4):
            p.went_quiet()
        p.answered()
        p.went_quiet()
        self.assertEqual(p.worst, 4)
        self.assertEqual(p.quiet, 1)

    def test_a_404_is_an_answer_and_not_silence(self):
        """The distinction the class exists for: a status is the server speaking.

        A manifest naming 300 files the mirror never kept produces 300 straight 404s. That must
        run to the end -- it is the answer to the question being asked.
        """
        p = common.Patience(limit=5)
        for _ in range(300):
            p.answered()                    # what the caller does for ANY http status
        self.assertFalse(p.spent)

    def test_the_reason_names_the_count_and_the_failure(self):
        p = common.Patience(limit=2)
        p.went_quiet("TimeoutError")
        p.went_quiet("TimeoutError")
        self.assertIn("2 requests in a row", p.reason)
        self.assertIn("TimeoutError", p.reason)

    def test_a_reason_is_readable_before_anything_failed(self):
        """Nothing may raise on the reporting path -- a crash while stopping loses the run."""
        self.assertIn("0 requests in a row", common.Patience().reason)

    def test_a_limit_below_one_is_refused(self):
        """limit=0 would stop before the first request and report the host as gone."""
        with self.assertRaises(ValueError):
            common.Patience(limit=0)

    def test_it_is_exported(self):
        self.assertIn("Patience", common.__all__)


class TestLocalFailure(unittest.TestCase):
    """Did the request reach the wire, or did it never leave this machine?

    WHY THE QUESTION EXISTS, 2026-10-02. A 568-url run of openpa ended on two
    `[Errno 11001] getaddrinfo failed` and printed "it has stopped talking. Leave it alone for
    days." The owner's wifi had dropped. The host answered HTTP 200 in 0.2 s a minute later, so
    the advice would have cost days over a fault on our own side -- and the fault was not even
    the host's to have.
    """

    def gai(self, errno=11001):
        return urllib.error.URLError(socket.gaierror(errno, "getaddrinfo failed"))

    def test_the_incident_itself(self):
        self.assertTrue(common.local_failure(self.gai()))

    def test_both_spellings_of_a_dns_failure(self):
        """11001 on Windows, -2 and -3 on Linux. A list with one of them passes only at home."""
        for errno in (11001, -2, -3):
            self.assertTrue(common.local_failure(self.gai(errno)), errno)

    def test_a_timeout_is_NOT_local(self):
        """The one case that does justify waiting: the request went out, nothing came back."""
        self.assertIsNone(common.local_failure(urllib.error.URLError(socket.timeout("timed out"))))

    def test_winerror_10060_is_NOT_local(self):
        """What a blocked host actually looks like here, and what must stay blamed on the host."""
        self.assertIsNone(common.local_failure(urllib.error.URLError(OSError(10060, "timed out"))))

    def test_a_refused_connection_is_NOT_local(self):
        """Something answered the SYN with a reset. That is the host talking, and excusing it as
        our own fault would hide exactly the refusal this collection must notice."""
        self.assertIsNone(
            common.local_failure(urllib.error.URLError(ConnectionRefusedError(10061, "refused"))))

    def test_an_unreachable_network_is_local(self):
        self.assertTrue(common.local_failure(urllib.error.URLError(OSError(10051, "no route"))))

    def test_it_unwraps_because_the_errno_is_never_on_top(self):
        """urllib raises URLError whose `reason` holds the socket error, so a check that reads
        only the outer exception finds nothing -- the silent form of this mistake."""
        outer = self.gai()
        self.assertIsNone(getattr(outer, "errno", None))
        self.assertTrue(common.local_failure(outer))

    def test_it_does_not_recurse_forever_on_a_self_referencing_chain(self):
        exc = urllib.error.URLError("x")
        exc.reason = exc
        self.assertIsNone(common.local_failure(exc))

    def test_an_ordinary_exception_is_not_local(self):
        self.assertIsNone(common.local_failure(ValueError("x")))
        self.assertIsNone(common.local_failure(None))


class TestPatienceTellsTheTwoApart(unittest.TestCase):

    def test_a_run_lost_to_the_local_network_says_do_not_wait(self):
        p = common.Patience(limit=2)
        p.unreachable("DNS lookup failed (11001)")
        p.unreachable("DNS lookup failed (11001)")
        self.assertTrue(p.spent)
        self.assertIn("never reached the wire", p.reason)
        self.assertIn("no reason to wait", p.reason)
        self.assertNotIn("Leave it alone for days", p.reason)

    def test_a_run_lost_to_the_host_still_says_wait(self):
        p = common.Patience(limit=2)
        p.went_quiet("TimeoutError")
        p.went_quiet("TimeoutError")
        self.assertIn("Leave it alone for days", p.reason)
        self.assertNotIn("never reached the wire", p.reason)

    def test_a_mixed_streak_refuses_to_pick_a_side(self):
        """Neither reading is safe, and guessing one would send somebody the wrong way."""
        p = common.Patience(limit=2)
        p.unreachable("DNS lookup failed (11001)")
        p.went_quiet("TimeoutError")
        self.assertIn("MIXED", p.reason)

    def test_an_answer_clears_the_local_count_with_the_streak(self):
        """A connection that dropped and came back is not still dropped."""
        p = common.Patience(limit=5)
        p.unreachable("DNS lookup failed (11001)")
        p.answered()
        p.went_quiet("TimeoutError")
        self.assertEqual(p.local, 0)
        self.assertIn("Leave it alone for days", p.reason)

    def test_both_kinds_count_towards_the_same_limit(self):
        """Two counters would let a flapping connection alternate for ever without stopping."""
        p = common.Patience(limit=4)
        p.unreachable()
        p.went_quiet()
        p.unreachable()
        self.assertFalse(p.spent)
        self.assertTrue(p.went_quiet())

    def test_local_failure_is_exported_beside_patience(self):
        self.assertIn("local_failure", common.__all__)


if __name__ == "__main__":
    unittest.main()
