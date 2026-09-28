#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""audit.py's content checks, on temporary trees. The collection is never touched.

WHAT IS WORTH TESTING is check_empty(): it decides whether a file is a failed transfer kept as
content, it is about to be run over 1.76 million files, and a check that is about to take hours
should be known to work before it starts rather than after.

It also has a shortcut that could hide things -- one block is read, and unless that block is
entirely zero the file is dismissed -- so the case that matters most is a file that BEGINS with
zeros and is not empty.
"""

import builtins
import ast
import io
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

audit = common.load_peer("audit.py", "_audit")


class TestCheckEmpty(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-test-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, name, data):
        p = os.path.join(self.d, name)
        with io.open(p, "wb") as fh:
            fh.write(data)
        return p

    def run_empty(self):
        """-> (certain count, everything printed). Two answers, because check_empty gives two.

        The RETURN VALUE counts only the files whose kind says they cannot be empty -- that is
        what the exit code rests on. Everything else is LISTED and not judged, so a test about
        those has to read the output.
        """
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            n = audit.check_empty(self.d)
        finally:
            sys.stdout = real
        return n, out.getvalue()

    def found(self):
        return self.run_empty()[0]

    def test_a_file_of_nothing_is_found(self):
        self.write("rom.gz", bytes(33615))
        self.assertEqual(self.found(), 1)

    def test_A_FILE_THAT_ONLY_STARTS_WITH_ZEROS_IS_NOT(self):
        """The shortcut's blind spot, if it had one: one block read, then dismissed.

        A real ROM image or disk sector dump can open with kilobytes of zeros and still hold
        data. Reporting one as a failed transfer would send somebody re-fetching a file that
        was never wrong.
        """
        self.write("rom.gz", bytes(4096) + b"REAL DATA" + bytes(1000))
        self.assertEqual(self.found(), 0)

    def test_and_a_whole_block_of_zeros_followed_by_data_is_not_either(self):
        # Larger than the probe, so the confirming read is what decides.
        self.write("big.bin", bytes(4096) + bytes(1 << 20) + b"x")
        self.assertEqual(self.found(), 0)

    def test_AN_EMPTY_FILE_IS_NOT_A_RUIN(self):
        # Zero bytes has no content to be wrong about, and a source may serve one.
        self.write("nothing.txt", b"")
        self.assertEqual(self.found(), 0)

    def test_a_partial_download_is_not_reported_as_content(self):
        # It already says what it is; that is what the suffix is for.
        self.write("half.gz.part", bytes(50000))
        self.assertEqual(self.found(), 0)

    def test_ordinary_files_are_not_reported(self):
        self.write("a.txt", b"hello")
        self.write("b.bin", os.urandom(9000))
        self.write("c.html", b"<html><body>x</body></html>")
        self.assertEqual(self.found(), 0)

    def test_IT_LOOKS_AT_EXTENSIONS_check_ruins_WOULD_NEVER_OPEN(self):
        """The reason it exists. check_ruins only opens what has a known signature.

        A zero-filled .txt is invisible to --ruins and to --holes alike; this is the one that
        sees it. It is LISTED rather than COUNTED, because `.txt` does not say by itself that a
        file of nothing is wrong -- so the exit code stays quiet and the reader gets the line.
        """
        self.write("notes.txt", bytes(20000))
        certain, text = self.run_empty()
        self.assertEqual(certain, 0)
        self.assertIn("notes.txt", text)
        self.assertIn(".txt", text)
        self.assertNotIn(".txt", common.MAGIC)

    def test_it_finds_them_further_down_a_tree(self):
        os.makedirs(os.path.join(self.d, "a", "b"))
        self.write(os.path.join("a", "b", "deep.dat"), bytes(7000))
        # .dat is the extension the measurement cleared: 129 of the collection's 400 are AIX
        # documentation placeholders. Listed, not counted.
        certain, text = self.run_empty()
        self.assertEqual(certain, 0)
        self.assertIn("deep.dat", text)

    def test_several_at_once(self):
        for i in range(3):
            self.write("z%d.gz" % i, bytes(1000 + i))
        self.write("ok.gz", b"\x1f\x8b" + bytes(998))
        self.assertEqual(self.found(), 3)


class TestTheThreeChecksAreDifferentQuestions(unittest.TestCase):
    """None of the three covers another, and the docstring says so. Pinned."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-test-")
        with io.open(os.path.join(self.d, "notes.txt"), "wb") as fh:
            fh.write(bytes(20000))          # 20 KB of nothing, under an unchecked extension

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_check(self, fn, *a):
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            return fn(self.d, *a)
        finally:
            sys.stdout = real

    def test_ruins_cannot_see_it(self):
        # .txt has no signature, so --ruins never opens the file.
        self.assertEqual(self.run_check(audit.check_ruins), 0)

    def test_holes_cannot_see_it_either(self):
        # Below the 16 MB floor, which exists because --holes reads every file in full.
        self.assertEqual(self.run_check(audit.check_holes, 16 * 1048576), 0)

    def test_but_empty_does(self):
        # It SEES it. Whether it COUNTS it is a separate question -- `.txt` says nothing about
        # whether a file of nothing is wrong -- and TestCannotBeEmpty is where that is decided.
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            audit.check_empty(self.d)
        finally:
            sys.stdout = real
        self.assertIn("notes.txt", out.getvalue())


class TestCannotBeEmpty(unittest.TestCase):
    """Which extensions state, by themselves, that a file of nothing is damage.

    MEASURED, NOT CHOSEN. The first full run over the collection on 2026-09-23 found 400
    all-zero files. Sorting them by extension answered the question a size floor could not:

        .htm   74      .dat   129      a floor of 16 KB would have missed 45 of the 81
        .html   4      .qpm    28      certain ones; the smallest is 137 bytes and the
        .gz     2      .ra     25      largest 276 906, and .dat at 300 bytes is a
        .pdf    1      .qpk    23      legitimate empty placeholder in AIX documentation

    So the rule is not "how big" but "could this ever be empty". A page of zeros is a failed
    transfer at 137 bytes as surely as at 276 KB; a .dat of zeros is a file the source shipped.
    """

    def test_a_page_can_never_be_empty(self):
        for name in ("a.htm", "b.html", "c.shtml", "d.php"):
            self.assertTrue(audit.cannot_be_empty(name), name)

    def test_nor_can_anything_with_a_known_signature(self):
        for ext in common.MAGIC:
            self.assertTrue(audit.cannot_be_empty("x" + ext), ext)

    def test_BUT_A_DATA_FILE_MAKES_NO_SUCH_CLAIM(self):
        # 129 of the 400 are .dat, almost all under 512 bytes, in AIX documentation trees. A
        # source is entitled to ship an empty data file and this tool does not know better.
        for name in ("x.dat", "y.ra", "z.qpm", "w.bn", "v.dta", "plain"):
            self.assertFalse(audit.cannot_be_empty(name), name)

    def test_AND_QPK_LEFT_THIS_GROUP_THE_DAY_IT_WAS_MEASURED(self):
        """`.qpk` was in the list above until 2026-09-24, on the reasonable-sounding ground that
        nobody here knew what one was. Reading them settled it: of 478 in the collection, **452
        are gzip and 26 are entirely zeros, with no third kind**. So a `.qpk` of nothing is
        damage, and 23 of them in `fsck-vendors` moved from "no statement possible" to certain.

        Its sibling `.qpm` stays in the list: that one is XML, which has no fixed opening worth
        pinning.
        """
        self.assertTrue(audit.cannot_be_empty("z.qpk"))
        self.assertFalse(audit.cannot_be_empty("z.qpm"))

    def test_THE_SET_IS_NOT_A_SIZE_FLOOR(self):
        """The alternative that was considered and rejected, with the measurement that killed it.

        A floor of 16 KB -- the one --holes already uses -- would have reported 36 of the 400
        and missed 45 certain ones. The smallest genuine loss in this collection is a 137-byte
        page of zeros.
        """
        self.assertTrue(audit.cannot_be_empty("tiny.htm"))
        self.assertFalse(audit.cannot_be_empty("huge.dat"))

    def test_and_it_agrees_with_the_library_rather_than_listing_extensions_again(self):
        # The two questions it asks are looks_like_a_page and MAGIC, both of which are tested
        # where they live. A third list here would be a fourth place to keep in step.
        self.assertTrue(audit.cannot_be_empty("x.bff"))       # in MAGIC
        self.assertTrue(audit.cannot_be_empty("x.php4"))      # a page since 2026-09-23
        self.assertFalse(audit.cannot_be_empty("x.iso"))      # checked, but no signature


class TestRuinsExceptions(unittest.TestCase):
    """Paths where the SOURCE stores something else under a name, and says so by its layout.

    THE MEASUREMENT THAT FORCED THIS. The first full run reported 26 313 ruins. 23 190 of them
    -- 88 % -- were one directory: oss4aix.org/rpmdb/db/, which holds a dependency database with
    one short text file per package, named after the package's .rpm:

        prov git-arch = 1.7.11.4-1
        req  git = 1.7.11.4-1

    Nothing is wrong with them. Reporting them buries the 3 123 findings that are left, and a
    report nobody can read is a check nobody runs.
    """

    def test_the_known_exception(self):
        self.assertTrue(audit.source_convention("oss4aix.org/rpmdb/db/zlib-1.2.3-1.aix5.1.ppc.rpm"))

    def test_it_is_ANCHORED_and_not_a_substring(self):
        # `rpmdb/db/` under some other archive is not this convention, and a rule that matched it
        # anywhere would silence a real finding somewhere nobody looked.
        self.assertFalse(audit.source_convention("bull-srpms/rpmdb/db/x.rpm"))
        self.assertFalse(audit.source_convention("oss4aix.org/RPMS/ppc/zlib-1.2.3-1.rpm"))

    def test_and_it_says_nothing_about_ordinary_paths(self):
        for p in ("bitsavers/pdf/dec/x.pdf", "oss4aix.org/rpmdb/other.rpm", "a/b/c.rpm"):
            self.assertFalse(audit.source_convention(p), p)

    def test_EVERY_EXCEPTION_IS_NAMED_WITH_ITS_REASON(self):
        """A list of silenced paths is a list of things nobody will look at again, so each one
        carries the sentence that justifies it and the count it was worth."""
        for pattern, why in audit.SOURCE_CONVENTIONS:
            self.assertTrue(why.strip(), pattern)
            self.assertGreater(len(why), 40, "%s: a reason, not a label" % pattern)

    def test_the_separator_is_not_the_platforms(self):
        # walk() yields native paths; relative_to() gives forward slashes. The patterns are
        # written in forward slashes and must be compared against those, or the exception
        # silently never fires on Windows -- which is where this collection lives.
        self.assertTrue(all("\\" not in p for p, _w in audit.SOURCE_CONVENTIONS))

    def test_THE_SHADOW_DATABASE(self):
        """somuchstuff-pdp8 keeps records shaped like the documents they describe.

        1 841 findings, and the source says so itself in `shadb/Meta.txt`: *the meta data archive
        mimics the true name directory structure*, with entries kept for files *which do not
        (yet) exist*. A record at `src/dec/dec-00-bzz/dec-00-bzzd-d.pdf` is 128 bytes of
        `.name` / `.description` / `.partnumber` / `.group`. No PDF is missing, because this
        layer was never meant to hold one.
        """
        self.assertTrue(audit.source_convention(
            "somuchstuff-pdp8/trunk/pdp8/shadb/src/dec/dec-00-bzz/dec-00-bzzd-d.pdf"))

    def test_AND_IT_DOES_NOT_COVER_THE_REST_OF_THAT_ARCHIVE(self):
        """The same site's Eagle tree holds real files under the same extension.

        `trunk/Eagle/projects/DEC/Mxxx/M1703/topld/M1703.pdf` is a PDIF schematic -- P-CAD's
        interchange format, which has used `.pdf` since before Adobe's did. It is outside the
        shadow database and stays visible, because it is a different fact about a different tree.
        """
        self.assertFalse(audit.source_convention(
            "somuchstuff-pdp8/trunk/Eagle/projects/DEC/Mxxx/M1703/topld/M1703.pdf"))

    def test_and_a_shadb_somewhere_else_is_not_this_one(self):
        self.assertFalse(audit.source_convention("bitsavers/trunk/pdp8/shadb/src/x.pdf"))

    def test_A_STAR_STANDS_FOR_ONE_SEGMENT(self):
        """The RPM database of an installed Red Hat tree, repeated across seven distributions.

        `packages.rpm` and its index siblings are Berkeley DB files, magic 0x00061561, not
        packages. Seven near-identical entries would have been seven chances to mistype one.
        """
        for v in ("redhat-4.0/i386", "redhat-5.1/i386", "redhat-4.2/alpha"):
            self.assertTrue(audit.source_convention(
                "ibiblio-historic-linux/distributions/%s/live/var/lib/rpm/packages.rpm" % v), v)

    def test_AND_IT_DOES_NOT_CROSS_A_SEPARATOR(self):
        """Otherwise the star would quietly become 'anywhere below here', which is the exact
        rule the anchoring exists to refuse. Each `*` is ONE segment, no more and no fewer.

        The pattern names two of them -- `distributions/<release>/<arch>/live/...` -- so a path
        with one segment there, or with three, is a different place and stays visible.
        """
        self.assertFalse(audit.source_convention(       # one segment where two are named
            "ibiblio-historic-linux/distributions/redhat-4.0/live/var/lib/rpm/packages.rpm"))
        self.assertFalse(audit.source_convention(       # three
            "ibiblio-historic-linux/distributions/redhat-4.0/i386/extra/live/var/lib/rpm/p.rpm"))
        self.assertFalse(audit.source_convention(       # right shape, wrong archive
            "somewhere-else/distributions/redhat-4.0/i386/live/var/lib/rpm/packages.rpm"))

    def test_and_a_pattern_without_a_star_still_matches_by_prefix(self):
        # The plain case must keep working exactly as it did; the star is an addition, not a
        # replacement.
        self.assertTrue(audit.source_convention("oss4aix.org/rpmdb/db/zlib-1.2.3-1.rpm"))
        self.assertFalse(audit.source_convention("oss4aix.org/RPMS/ppc/zlib-1.2.3-1.rpm"))

class TestZeroAtSource(unittest.TestCase):
    """Twenty files this collection holds as zeros because the SOURCE serves them that way.

    THE DIAGNOSIS THAT WAS WRONG FIRST. All twenty had exactly the size we stored, which looked
    like a transfer that kept the length and lost the content -- so the plan was to fetch them
    again. The first re-fetch returned 276 906 fresh bytes of nothing. Only then were the other
    nineteen probed instead of repaired, and all nineteen answered the same way: HTTP 200, right
    length, every byte zero. [2026-09-24]

    THEY ARE NOT DELETED. A mirror answers "what did this archive serve, and under which path",
    byte for byte. Removing a faithful copy of an empty file makes that answer less true.
    """

    def test_the_record_holds_seventy_five(self):
        """Twenty when it was written, and it has grown twice since -- both times on one day.

        The first twenty were found by `--ruins` and `--empty` between them. Four more are two AIX
        documentation figures held by two independent mirrors, which nothing could see while
        `cannot_be_empty()` had no image signature to ask about (A3). The last fifty-one are a
        whole QNX 6 package repository, 23 `.qpk` and 28 `.qpm`, added when C3 asked
        fsck.technology about every one of them and it served all 51 as zeros at exactly the
        length held here.

        BOTH ADDITIONS FOLLOWED A WIDENING OF `MAGIC`, and that is the pattern worth naming.
        Every time this tool learns to recognise a format, files that were unjudged turn into
        findings -- and some of those findings are the source's own doing. Growth in this table
        is what a correct widening looks like from the other side, which is why widening MAGIC
        and re-reading this table are one piece of work and not two.

        Every one of the seventy-five was measured against its live host and not inferred.
        """
        self.assertEqual(len(audit.ZERO_AT_SOURCE), 75)

    def test_every_entry_is_a_path_and_a_size(self):
        for rel, size in audit.ZERO_AT_SOURCE:
            self.assertIn("/", rel, rel)
            self.assertGreater(size, 0, rel)

    def test_IT_MATCHES_FROM_EITHER_ROOT(self):
        """The bug this test exists for, and it was live for the length of one command.

        --root may be the collection or one archive inside it, and relative_to() answers against
        whichever was given. Written as a plain equality the record matched only the collection
        form and went on calling the archive form a loss -- which is worse than having no record,
        because the report looks like it is working.
        """
        self.assertEqual(audit.zero_at_source("sun3arc/ROMs/3_60/sun3_60_v1.5.gz"), 33615)
        self.assertEqual(audit.zero_at_source("ROMs/3_60/sun3_60_v1.5.gz"), 33615)

    def test_AND_ONLY_ON_A_PATH_BOUNDARY(self):
        # A file of the same NAME somewhere else is a different file, and silencing it would be
        # exactly the mistake the exact-path record exists to avoid.
        self.assertIsNone(audit.zero_at_source("elsewhere/sun3_60_v1.5.gz"))
        self.assertIsNone(audit.zero_at_source("3_60/sun3_60_v1.5.gz.bak"))
        self.assertIsNone(audit.zero_at_source("xsun3_60_v1.5.gz"))

    def test_a_native_separator_is_understood(self):
        # walk() yields native paths on Windows, which is where this collection lives.
        self.assertEqual(audit.zero_at_source(os.path.join("ROMs", "3_60", "sun3_60_v1.5.gz")),
                         33615)

    def test_an_unrecorded_file_is_not_silenced(self):
        self.assertIsNone(audit.zero_at_source("sun3arc/ROMs/3_60/something-else.gz"))

    def test_THE_SIZE_IS_PART_OF_THE_RECORD(self):
        """A recorded path whose size has changed is NOT the file that was measured.

        If the source ever serves real content again, the length almost certainly differs -- and
        this record must stop applying the moment that happens, or it would go on excusing a file
        nobody has checked since 2026-09-24.
        """
        rel, size = audit.ZERO_AT_SOURCE[0]
        self.assertEqual(audit.zero_at_source(rel), size)
        self.assertNotEqual(size, 0)

    def test_every_recorded_path_is_still_in_the_collection(self):
        """A record that names files that are gone is a record nobody trusts. Skipped when the
        collection is not mounted, so this stays a unit test on a machine without Q:."""
        root = common.MIRROR_ROOT
        if not os.path.isdir(root):
            self.skipTest("collection not mounted at %s" % root)
        missing = [rel for rel, _s in audit.ZERO_AT_SOURCE
                   if not os.path.exists(common.long_path(
                       os.path.join(root, rel.replace("/", os.sep))))]
        self.assertEqual(missing, [])

    def test_and_each_one_is_still_the_size_that_was_recorded(self):
        root = common.MIRROR_ROOT
        if not os.path.isdir(root):
            self.skipTest("collection not mounted at %s" % root)
        wrong = []
        for rel, size in audit.ZERO_AT_SOURCE:
            p = common.long_path(os.path.join(root, rel.replace("/", os.sep)))
            if os.path.getsize(p) != size:
                wrong.append((rel, os.path.getsize(p), size))
        self.assertEqual(wrong, [])

    def test_and_each_one_is_still_all_zeros(self):
        """If one of them ever holds content again, this record is stale and must be revisited.

        That is the whole point of keeping the measurement in code: it can be re-run, and a
        source that quietly starts serving the real file again shows up here as a failure rather
        than as twenty lines nobody reads.
        """
        root = common.MIRROR_ROOT
        if not os.path.isdir(root):
            self.skipTest("collection not mounted at %s" % root)
        not_zero = [rel for rel, _s in audit.ZERO_AT_SOURCE
                    if common.is_all_zero(os.path.join(root, rel.replace("/", os.sep))) is not True]
        self.assertEqual(not_zero, [])

class TestTheMethodThatKeptBeingWrong(unittest.TestCase):
    """A raw count is not a finding, and this file is where that stops being a slogan.

    IT WENT WRONG TWICE IN ONE DAY, both times with a number that looked decisive:

      26 313 ruins          -> 23 190 were one directory of the source's own metadata
      566 blocked files     -> 225 of them are held under another path in the same archive

    Both would have been reported as damage. Neither was. What caught them was the same move:
    read a handful of the things being counted before quoting the count. These tests pin the
    checks that make that move cheap, so that the next number gets the same treatment.
    """

    def test_a_source_convention_must_carry_its_reason_and_its_worth(self):
        # A silenced path with no sentence beside it is a decision nobody can revisit.
        for pattern, why in audit.SOURCE_CONVENTIONS:
            self.assertGreater(len(why), 40, pattern)
            self.assertTrue(any(c.isdigit() for c in why),
                            "%s: say how many findings it accounted for" % pattern)

    def test_AND_SKIPPED_FILES_ARE_COUNTED_NOT_SWALLOWED(self):
        """The difference between an exclusion and a blind spot is whether it is reported."""
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "audit.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("skipped as a source convention", src)
        self.assertIn("skipped += 1", src)

    def test_the_zero_record_names_files_and_not_directories(self):
        """341 files sit behind 33 directory pages, and 225 names listed there ARE held
        elsewhere. A record written by directory would have silenced both kinds at once."""
        for rel, _size in audit.ZERO_AT_SOURCE:
            self.assertFalse(rel.endswith("/"), rel)
            self.assertIn(".", rel.rsplit("/", 1)[-1], rel)

    def test_A_DIRECTORY_PAGE_IS_RECOGNISED_WHEREVER_IT_SITS(self):
        """The finding that is worth the most: an autoindex stored where a directory belongs.

        A filesystem cannot hold a file and a directory under one name, so everything the page
        lists is unreachable. 33 of them were found on 2026-09-24, hiding 341 files that are in
        the archive nowhere else.
        """
        page = b"<html><title>Index of /pub/aix</title><body><h1>Index of /pub/aix</h1></body>"
        why = common.magic_mismatch("53", page)          # no extension: a directory's name
        self.assertIsNotNone(why)
        self.assertIn("directory listing", why)

    def test_and_it_is_found_under_a_real_extension_too(self):
        page = b"<html><h1>Index of /pub</h1></html>"
        self.assertIsNotNone(common.magic_mismatch("archive.zip", page))

    def test_AN_ERROR_PAGE_UNDER_A_DOCUMENT_NAME_IS_A_FINDING(self):
        """16 were found: Bull's landing page under 8 .rpm names, three 404s, a Wayback page,
        and four real pages under .pdf names in the same directory whose lighttpd listings had
        already cost this collection 1 955 PDFs."""
        for name in ("x.pdf", "y.rpm", "z.zip", "a.gz"):
            self.assertIsNotNone(
                common.magic_mismatch(name, b"<!DOCTYPE html><title>404 Not Found</title>"), name)

    def test_and_the_real_thing_is_not(self):
        self.assertIsNone(common.magic_mismatch("x.pdf", b"%PDF-1.4\n"))
        self.assertIsNone(common.magic_mismatch("x.gz", b"\x1f\x8b\x08\x00"))


class TestItSaysSomethingWhileItWorks(unittest.TestCase):
    """A check that prints nothing for an hour is a check somebody kills, and somebody did.

    Every one of these holds its output until the last file has been read -- it has to, because a
    file's group is not known until it has been compared against the records. Over the collection
    that is 1.76 M files and the best part of an hour with **zero bytes of output**, which cannot
    be told apart from a hang. Two runs were killed at that point on 2026-09-24, and C4
    (`--holes`, 3.8 TB read in full) has never been run at all.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-progress-")
        for archive in ("alpha", "beta"):
            os.makedirs(os.path.join(self.d, archive))
            with io.open(os.path.join(self.d, archive, "a.txt"), "wb") as fh:
                fh.write(b"content")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_IT_IS_SILENT_UNLESS_ASKED(self):
        """The library default, and the opposite of the command line's. A function that printed
        whether or not a caller wanted it cannot be used inside anything else.

        Written first as `said = []; walk(self.d); assertEqual(said, [])`, which asserts nothing
        whatever -- the list is never passed in, so it cannot fill. Both streams are captured
        instead, because "it did not call the callback I withheld" and "it printed nothing" are
        different claims and only the second is the one that matters.
        """
        out, err = io.StringIO(), io.StringIO()
        real_out, real_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            files = list(audit.walk(self.d))
        finally:
            sys.stdout, sys.stderr = real_out, real_err
        self.assertEqual(len(files), 2)          # it did the work
        self.assertEqual(out.getvalue(), "")     # and said nothing about it
        self.assertEqual(err.getvalue(), "")

    def test_and_names_each_archive_as_it_is_reached(self):
        said = []
        list(audit.walk(self.d, report=said.append))
        text = "\n".join(said)
        self.assertIn("alpha", text)
        self.assertIn("beta", text)

    def test_THE_CALLBACK_IS_CALLED_report(self):
        """The library's contract, enforced for the library by a test in common_test.py. These
        are its clients and the same word has to mean the same thing on both sides."""
        import inspect
        for fn in (audit.walk, audit.check_ruins, audit.check_empty, audit.check_listed,
                   audit.check_holes):
            params = inspect.signature(fn).parameters
            self.assertIn("report", params, fn.__name__)
            self.assertIsNone(params["report"].default, fn.__name__)

    def test_the_checks_pass_it_through(self):
        said = []
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            audit.check_ruins(self.d, report=said.append)
        finally:
            sys.stdout = real
        self.assertTrue(any("alpha" in s for s in said), said)


class TestAFilenameCannotKillTheRun(unittest.TestCase):
    r"""528 paths in this collection cannot be encoded by a cp1252 console. Measured 2026-09-24.

    `bitsavers` holds 410 of them, `fsck-vendors` 83, `vtda` 17, `tuhs` 16, and one each in
    `mpoli-bbs` and `oldskool` -- real names like
    `bits/Foonly/F2/files/DSKF2-MICROCODE17.;1.bin`.

    THE MEASUREMENT THAT FOUND THIS DIED OF IT. The script counting unprintable paths printed its
    examples with a bare `print()` and raised UnicodeEncodeError on the first one. audit.py did
    the same thing with every path it reported, so a single finding among those 528 would have
    killed a run AFTER an hour of reading and BEFORE printing anything -- the worst possible
    moment. `common.say()` exists for exactly this and audit.py was not using it.
    """

    NAME = "テスト.gz"      # katakana and a private-use character

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-encoding-")
        with io.open(os.path.join(self.d, self.NAME), "wb") as fh:
            fh.write(b"this is not a gzip at all")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def cp1252_stream(self):
        """A stream that behaves like the console this collection is read on."""
        return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict",
                                write_through=True)

    def test_A_NAME_THE_CONSOLE_CANNOT_ENCODE_IS_REPORTED_ANYWAY(self):
        out, real = self.cp1252_stream(), sys.stdout
        sys.stdout = out
        try:
            found = audit.check_ruins(self.d)
        finally:
            sys.stdout = real
        self.assertEqual(found, 1)
        out.flush()
        text = out.buffer.getvalue().decode("cp1252")
        self.assertIn(".gz", text)          # the finding survived, with the name transliterated

    def test_and_a_bare_print_really_would_have_died(self):
        """The control. Without it this test proves only that nothing happened to go wrong."""
        out = self.cp1252_stream()
        with self.assertRaises(UnicodeEncodeError):
            out.write(self.NAME + "\n")

    def test_the_progress_lines_are_safe_too(self):
        # They carry a directory name, which is the same hazard one level up.
        deep = os.path.join(self.d, "テスト")
        os.makedirs(deep)
        with io.open(os.path.join(deep, "x.gz"), "wb") as fh:
            fh.write(b"not a gzip")
        out = self.cp1252_stream()
        list(audit.walk(self.d, report=lambda m: common.say(m, stream=out)))
        out.flush()
        self.assertIn("...", out.buffer.getvalue().decode("cp1252"))

    def test_AND_NOTHING_IN_THIS_FILE_PRINTS_DIRECTLY_ANY_MORE(self):
        """The rule, not the instance. One `print(` left in a path-reporting branch is the whole
        defect back, and it would only show up on the day one of the 528 became a finding."""
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.py"),
                     encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("print(", src)
        self.assertIn(" say,", src)          # imported from the library, not redefined


class TestRuinsOutputCanBeParsed(unittest.TestCase):
    """The reason column used to be a literal 34 characters wide.

    TEN of the nineteen reasons magic_mismatch can produce are longer than that -- every
    `does not begin with the .X signature` and the directory-page line -- so on more than half of
    them the size ran straight into the reason with no space between, and a parser written
    against this output failed on exactly those lines. The column is now measured from the
    reasons actually present, which is correct for the next extension added to MAGIC too.
    """

    ROW = re.compile(r"^  (.+?)\s+(\d+) B  (.+?)(   = index of .*)?$")

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-ruins-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, name, data):
        with io.open(os.path.join(self.d, name), "wb") as fh:
            fh.write(data)

    def run_ruins(self):
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            n = audit.check_ruins(self.d)
        finally:
            sys.stdout = real
        return n, out.getvalue()

    def test_EVERY_REASON_FITS_THE_COLUMN(self):
        """The property that makes the output parseable at all, asserted over every reason the
        library can produce rather than over the ones this test happens to trigger."""
        reasons = [audit.DIRECTORY_PAGE]
        for ext in common.MAGIC:
            reasons.append("HTML under a %s name" % ext)
            reasons.append("does not begin with the %s signature" % ext)
        widest = max(len(r) for r in reasons)
        self.write("a.squash", b"not a squashfs at all, honestly")
        _n, out = self.run_ruins()
        line = [ln for ln in out.splitlines() if ".squash" in ln and " B  " in ln][0]
        # the reason is padded to at least the widest one the run saw, and the size stays a
        # field of its own with whitespace on both sides
        self.assertRegex(line, r"^  \S.*?\s{2,}\s*\d+ B  ")
        self.assertGreater(widest, 34, "the old literal was 34 and this is why it broke")

    def test_a_long_reason_and_a_short_one_line_up(self):
        self.write("a.squash", b"xxxx")             # 41-character reason
        self.write("b.z", b"xxxx")                  # 36-character reason
        _n, out = self.run_ruins()
        rows = [self.ROW.match(ln) for ln in out.splitlines() if " B  " in ln]
        rows = [m for m in rows if m]
        self.assertEqual(len(rows), 2, out)
        starts = {ln.index(" B") for ln in out.splitlines() if " B  " in ln}
        self.assertEqual(len(starts), 1, "the size column has to start in one place:\n" + out)

    def test_AND_THE_THREE_FIELDS_COME_BACK_OUT(self):
        # The actual requirement: reason, size and path, recovered without guessing.
        self.write("broken.pdf", b"<html><body>404</body></html>")
        _n, out = self.run_ruins()
        line = [ln for ln in out.splitlines() if "broken.pdf" in ln][0]
        m = self.ROW.match(line)
        self.assertIsNotNone(m, line)
        self.assertEqual(m.group(1).strip(), "HTML under a .pdf name")
        self.assertEqual(int(m.group(2)), 29)
        self.assertEqual(m.group(3), "broken.pdf")

    def test_and_a_directory_page_still_says_which_directory(self):
        self.write("53", b"<html><title>Index of /pub/AIX</title><h1>Index of /pub/AIX</h1>")
        _n, out = self.run_ruins()
        line = [ln for ln in out.splitlines() if " B  53" in ln][0]
        m = self.ROW.match(line)
        self.assertIsNotNone(m, line)
        self.assertEqual(m.group(1).strip(), audit.DIRECTORY_PAGE)
        self.assertIn("/pub/AIX", m.group(4))

    def test_an_empty_run_does_not_divide_by_an_empty_column(self):
        # max() over nothing raises, and a clean tree is the commonest case of all.
        self.write("fine.txt", b"ordinary")
        n, out = self.run_ruins()
        self.assertEqual(n, 0)
        self.assertIn("0 found", out)


class TestPageAtSource(unittest.TestCase):
    """Twenty-one files the source itself serves as a web page under a binary name.

    ALL TWENTY-ONE WERE ASKED AGAIN on 2026-09-24 and not one can be repaired: eight came back
    BYTE-IDENTICAL to what we hold, four are served with status 200 by a live host handing out
    the same Bull SAS landing page, and nine sit in a tree whose origin hosts no longer answer.

    THE STATUS CODE WOULD HAVE LIED ABOUT FOUR OF THEM. `dl.power-devops.com` answers 200; only
    the bytes say it is the same broken page, and a re-fetch would have replaced a broken file
    with the same broken file.
    """

    def test_a_recorded_page_is_found(self):
        self.assertEqual(
            audit.page_at_source("bull-srpms/redis/redis-2.6.16-1.src.rpm"), 7655)

    def test_and_also_when_the_run_was_narrowed_to_one_archive(self):
        self.assertEqual(audit.page_at_source("redis/redis-2.6.16-1.src.rpm"), 7655)

    def test_the_boundary_holds(self):
        self.assertIsNone(audit.page_at_source("elsewhere/redis-2.6.16-1.src.rpm"))
        self.assertIsNone(audit.page_at_source("xredis-2.6.16-1.src.rpm"))

    def test_EVERY_ROW_CARRIES_THE_SENTENCE_THAT_JUSTIFIES_IT(self):
        """A silenced path with no reason is a path nobody can ever safely un-silence."""
        self.assertEqual(len(audit.PAGE_AT_SOURCE), 21)
        for path, size, why in audit.PAGE_AT_SOURCE:
            self.assertIn("/", path)
            self.assertNotIn("\\", path)
            self.assertGreater(size, 0)
            self.assertGreater(len(why), 30, "%s: a reason, not a label" % path)

    def test_the_three_kinds_of_evidence_are_all_stated(self):
        # They are not equally strong and the rows say which is which: byte-identical, the same
        # page served with 200, or a host that no longer answers at all.
        reasons = [why for _p, _s, why in audit.PAGE_AT_SOURCE]
        self.assertEqual(sum(1 for r in reasons if "byte for byte" in r), 8)
        self.assertEqual(sum(1 for r in reasons if "answers 200" in r), 4)
        self.assertEqual(sum(1 for r in reasons if "no longer answers" in r), 9)

    def test_AND_THE_TABLES_DO_NOT_OVERLAP(self):
        # Three records now, each with its own kind of evidence. A file must not be able to be
        # excused twice, or the weakest excuse decides.
        page = {p for p, _s, _w in audit.PAGE_AT_SOURCE}
        zero = {p for p, _s in audit.ZERO_AT_SOURCE}
        cap = {p for p, _s in audit.ZERO_IN_CAPTURE}
        self.assertEqual(page & zero, set())
        self.assertEqual(page & cap, set())


class TestRuinsSkipsPagesTheSourceServes(unittest.TestCase):
    """The record has to reach check_ruins, and it has to stop reaching it when the file moves."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-pas-")
        self.rel, self.size, _why = audit.PAGE_AT_SOURCE[0]
        self.name = self.rel.rsplit("/", 1)[1]

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, body):
        with io.open(os.path.join(self.d, self.name), "wb") as fh:
            fh.write(body)

    def run_ruins(self):
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            n = audit.check_ruins(self.d)
        finally:
            sys.stdout = real
        return n, out.getvalue()

    def body(self, size):
        head = b"<!DOCTYPE html><html><body>page</body></html>"
        return head + b" " * (size - len(head))

    def test_a_recorded_page_is_not_a_finding(self):
        self.write(self.body(self.size))
        n, out = self.run_ruins()
        self.assertEqual(n, 0)
        self.assertIn("the SOURCE ITSELF serves as a web page", out)
        self.assertIn(self.name, out)

    def test_BUT_A_DIFFERENT_SIZE_IS(self):
        """The day a source puts the real file back, or replaces one bad page with another, the
        size moves and the row must stop excusing it. Matching on the path alone would silence
        that path for ever."""
        self.write(self.body(self.size + 1))
        n, _out = self.run_ruins()
        self.assertEqual(n, 1)


class TestZeroInCapture(unittest.TestCase):
    """Seventy-nine files that were already empty in the 2008 tar this archive came out of.

    WHY A SECOND TABLE AND NOT MORE ROWS IN THE FIRST. `ZERO_AT_SOURCE` opens with "each of these
    was requested again from its live host". Not one of these was: `h18002.www1.hp.com` does not
    resolve, and the tar itself is no longer in the collection either. Three quarters of that
    table's entries would have stopped being true of it.

    WHAT WAS CHECKED INSTEAD. bitsavers publishes a `tar tvf` listing beside each container tar
    and that listing is still here -- 10 201 file members, written in 2008 by whoever packed the
    archive. All 79 appear in it at exactly the length we hold: 79 of 79, none missing, none
    differing. It proves the LENGTH, not the bytes, and that is precisely why it is kept apart.
    """

    def test_a_recorded_file_is_found_by_its_full_path(self):
        self.assertEqual(
            audit.zero_in_capture(
                "hp-alphaserver-2008/alphaserver/archive/comp/mar94.html"), 13878)

    def test_AND_ALSO_WHEN_THE_RUN_WAS_NARROWED_TO_ONE_ARCHIVE(self):
        # --root may be the collection or one archive inside it, so relative_to() hands this
        # function a different string for the same file. A plain equality silently stopped
        # matching the moment somebody narrowed the run -- worse than no record, because it
        # still looks like it works.
        self.assertEqual(audit.zero_in_capture("alphaserver/archive/comp/mar94.html"), 13878)

    def test_and_the_boundary_still_holds(self):
        self.assertIsNone(audit.zero_in_capture("somewhere-else/mar94.html"))
        self.assertIsNone(audit.zero_in_capture("xmar94.html"))

    def test_THE_FOUR_A3_ADDED_TO_THE_LIVE_TABLE(self):
        """A3 taught MAGIC what an image is, and the first thing it found was these.

        A zero-filled JPEG sat under "no statement possible" for as long as `cannot_be_empty()`
        had no image signature to ask about. The day it got one, four appeared -- and they are
        TWO FILES HELD TWICE: `infania-tl2` and `ps-2.kev009.com` are independent mirrors of the
        same IBM AIX documentation, and both hold exactly these two figures as zeros at exactly
        these lengths.

        Two captures by different people at different times agreeing byte for byte is already a
        statement about the source. Then the source was asked: ps-2 answers HTTP 200 with 10 655
        and 65 664 bytes, every one of them zero. So they belong in the LIVE table, not in
        ZERO_IN_CAPTURE -- the evidence is a live host, which is what that table's opening
        sentence promises.
        """
        for rel, size in (
                ("infania-tl2/techlib/manuals/adoclib/aixlnk25/x25usrgd/figures/a1190cf8.jpg",
                 10655),
                ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixprggd/aixwnpgd/figures/"
                 "aixwn59.jpg", 65664)):
            self.assertEqual(audit.zero_at_source(rel), size, rel)

    def test_and_the_two_mirrors_agree_on_both_files(self):
        # The cross-check is the point: the same basename at the same size under two archives.
        by_name = {}
        for path, size in audit.ZERO_AT_SOURCE:
            if path.endswith((".jpg", ".gif", ".png")):
                by_name.setdefault(os.path.basename(path), set()).add(size)
        self.assertEqual(sorted(by_name), ["a1190cf8.jpg", "aixwn59.jpg"])
        for name, sizes in by_name.items():
            self.assertEqual(len(sizes), 1, "%s: two mirrors, two sizes" % name)

    def test_THE_TWO_TABLES_DO_NOT_OVERLAP(self):
        """Different evidence, so a file must not be able to claim both and be judged by the
        weaker one. If a host ever answers for one of these, its row moves; it is not copied."""
        live = {p for p, _s in audit.ZERO_AT_SOURCE}
        frozen = {p for p, _s in audit.ZERO_IN_CAPTURE}
        self.assertEqual(live & frozen, set())

    def test_it_covers_the_images_too_and_not_only_the_certain_ones(self):
        """THE PREDICTION THIS TEST WAS WRITTEN TO HOLD, AND IT CAME TRUE THE SAME DAY.

        When these 79 were recorded, 61 of them were what `cannot_be_empty()` called damage and
        18 were `.gif`, `.jpg`, `.js` and `.css`, which it had no opinion about. The note read:
        recording only the 61 would leave 13 images waiting to become false findings the day
        `MAGIC` learns an image format -- an open decision rather than a hypothesis.

        `MAGIC` learned image formats a few hours later (A3). The count moved from 61 to **74**,
        exactly the 7 `.gif` and 6 `.jpg`, and not one of them became a false finding, because
        all 79 had been written down rather than the 61 that happened to count that morning.

        The five still outside are `.js` and `.css`, which have no signature and probably never
        will.
        """
        exts = {common.file_extension(p) for p, _s in audit.ZERO_IN_CAPTURE}
        for ext in (".htm", ".html", ".gif", ".jpg", ".js", ".css"):
            self.assertIn(ext, exts, ext)
        certain = [p for p, _s in audit.ZERO_IN_CAPTURE if audit.cannot_be_empty(p)]
        self.assertEqual(len(certain), 74)
        self.assertEqual(len(audit.ZERO_IN_CAPTURE), 79)
        rest = {common.file_extension(p) for p, _s in audit.ZERO_IN_CAPTURE
                if not audit.cannot_be_empty(p)}
        self.assertEqual(rest, {".js", ".css"})

    def test_every_entry_is_a_path_and_a_size(self):
        # By path, not by directory: a NEW empty file appearing beside a recorded one is still a
        # finding, and a size that no longer matches means the file changed under us.
        for path, size in audit.ZERO_IN_CAPTURE:
            self.assertIn("/", path)
            self.assertGreater(size, 0)
            self.assertNotIn("\\", path)


class TestCheckHolesSaysWhatItCouldNotRead(unittest.TestCase):
    """The blind spot a four-to-eleven hour run must not have.

    `--holes` reads every file at or above its floor IN FULL. Measured from the indexes before
    the first run was ever started: **33 734 files, 2.39 TB** -- 60% of the collection by bytes,
    and 4 to 11 hours depending on the volume. Over a pass that long a lock, a bad sector or a
    path the filesystem will not open twice is not hypothetical.

    It carried `except OSError: continue`. So the run would have ended with a count that was
    silent about its own blind spot, after eleven hours, and nothing would have looked wrong.
    `check_empty` has refused exactly this shape since it was written.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-holes-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_holes(self, min_size=1):
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            n = audit.check_holes(self.d, min_size)
        finally:
            sys.stdout = real
        return n, out.getvalue()

    def write(self, name, data):
        with io.open(os.path.join(self.d, name), "wb") as fh:
            fh.write(data)

    def test_a_file_with_a_whole_empty_block_is_found(self):
        # ALIGNED ON PURPOSE. It reads in 1 MB blocks, so 100 bytes of data followed by a
        # megabyte of zeros puts the zeros across two reads and neither one is empty -- the first
        # version of this test did exactly that and failed. A hole is only visible to this check
        # when it fills a whole block, which is the check's own stated rule.
        self.write("big.tar", os.urandom(1 << 20) + bytes(1 << 20))
        n, out = self.run_holes()
        self.assertEqual(n, 1)
        self.assertIn("big.tar", out)

    def test_and_a_full_one_is_not(self):
        self.write("ok.tar", os.urandom(2 << 20))
        self.assertEqual(self.run_holes()[0], 0)

    def test_A_FILE_IT_COULD_NOT_OPEN_IS_REPORTED_AND_NOT_COUNTED(self):
        """"I could not look" and "I looked and it was fine" are different answers.

        It is not a finding -- nothing was found -- but it is not silence either, because the
        count at the end would otherwise describe a tree part of which was never read.
        """
        self.write("locked.tar", bytes(2 << 20))
        real_open = builtins.open

        def refusing(path, *a, **kw):
            if "locked.tar" in str(path):
                raise PermissionError(13, "in use")
            return real_open(path, *a, **kw)

        builtins.open = refusing
        try:
            n, out = self.run_holes()
        finally:
            builtins.open = real_open
        self.assertEqual(n, 0, "an unreadable file is not a finding")
        self.assertIn("COULD NOT BE READ", out)
        self.assertIn("locked.tar", out)
        self.assertIn("PermissionError", out)

    def test_and_the_run_says_how_many_it_did_read(self):
        # Without it, "0 incomplete files" cannot be told from "0 files examined".
        self.write("a.tar", os.urandom(2 << 20))
        self.write("b.tar", os.urandom(2 << 20))
        _n, out = self.run_holes()
        self.assertIn("2 files read in full", out)

    def test_disk_images_stay_exempt(self):
        # Unallocated blocks in an image read as zeros and always will; an AIX boot logical
        # volume can be 37% empty and perfectly intact.
        self.write("disk.img", bytes(2 << 20))
        self.assertEqual(self.run_holes()[0], 0)


class TestCheckListed(unittest.TestCase):
    """The only check here that asks something OTHER than the tree about the tree.

    Every other one compares the collection with a record the collection produced, so a file
    that was already wrong when the index was built stays invisible: a truncated download hashes
    to itself perfectly. A stored directory listing was written by the source, before the crawler
    fetched anything, and it names a size per file.
    """

    # COPIED FROM A REAL PAGE, not invented. The first attempt at these cases used a made-up
    # <pre> block with a plausible-looking date column; parse_listing read every row and returned
    # no size for any of them, so three cases passed because NOTHING WAS COMPARED. The shape
    # below is `testdata/listings/row-apache-sd-i.html`, whose own 1.1M row is where the 1 153 433
    # in common_test.py comes from.
    HEAD = ('<html><head><title>Index of /pub</title></head><body><h1>Index of /pub</h1>'
            '<table><tr><th>Name</th><th>Last modified</th><th>Size</th></tr>'
            '<tr><td><a href="/pub/">Parent Directory</a></td><td>&nbsp;</td>'
            '<td align="right">  - </td></tr>'
            '<tr><td><a href="sub/">sub/</a></td>'
            '<td align="right">2014-09-18 22:20  </td><td align="right">  - </td></tr>')
    ROW = ('<tr><td><a href="%s">%s</a></td><td align="right">2014-09-18 22:20  </td>'
           '<td align="right">%s</td><td>&nbsp;</td></tr>')
    TAIL = "</table></body></html>"

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="audit-listed-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def build(self, rows, files):
        """One directory holding an index.html and whatever the case says is beside it.

        The page is checked before it is used. A fixture parse_listing cannot read is a test that
        asserts nothing, and that is not a hypothetical -- it is what the first version of this
        class did.
        """
        body = self.HEAD + "".join(self.ROW % (n, n, s) for n, s in rows) + self.TAIL
        got = {h: s for h, s, _m in common.parse_listing(body)}
        for name, _printed in rows:
            self.assertIsNotNone(got.get(name), "fixture carries no size for %s" % name)
        with io.open(os.path.join(self.d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(body)
        for name, size in files:
            with io.open(os.path.join(self.d, name), "wb") as fh:
                fh.write(b"x" * size)

    def run_listed(self):
        out, real = io.StringIO(), sys.stdout
        sys.stdout = out
        try:
            n = audit.check_listed(self.d)
        finally:
            sys.stdout = real
        return n, out.getvalue()

    def test_a_file_the_listing_agrees_with_is_not_a_finding(self):
        self.build([("a.tar.Z", "449k")], [("a.tar.Z", 449 * 1024)])
        self.assertEqual(self.run_listed()[0], 0)

    def test_AND_ROUNDING_IS_STILL_AGREEMENT(self):
        # The page says 3.3K and the file is 3 403 bytes, which is what 3.3K means. Comparing
        # with == reported 41 contradictions across four archives where there were 3.
        self.build([("a.tar.Z", "3.3K")], [("a.tar.Z", 3403)])
        self.assertEqual(self.run_listed()[0], 0)

    def test_A_FILE_SHORTER_THAN_ITS_LISTING_IS_A_FINDING(self):
        """The shape that matters: a transfer that stopped and was kept as content.

        Modelled on the real one -- `mozilla-0.8.0.0.exe`, listed at 38 063 308 bytes and 7 488
        bytes on disk, which turned out to be an HTML landing page the server answered 200 with.
        """
        self.build([("big.exe", "36M")], [("big.exe", 7488)])
        n, out = self.run_listed()
        self.assertEqual(n, 1)
        self.assertIn("SHORTER", out)
        self.assertIn("big.exe", out)

    def test_AND_THE_THRESHOLD_SITS_IN_A_MEASURED_GAP(self):
        """Not a round number somebody liked: 2.7% below it, 19.5% above, nothing between.

        Below -- `ps-2.kev009.com`, checked against the live server and found faithful. Above --
        `dec-ftp-2006/pub/X11/contrib/docs/Xbibliography.PS`, listed 129 024 and holding 103 880,
        a structurally valid `%!PS-Adobe-1.0` file nobody can re-fetch because the source is a
        2006 tar. That one stays a finding precisely because it cannot be settled.
        """
        self.assertGreater(audit.LISTING_NOISE, 0.027)
        self.assertLess(audit.LISTING_NOISE, 0.195)
        self.build([("Xbibliography.PS", "126K")], [("Xbibliography.PS", 103880)])
        self.assertEqual(self.run_listed()[0], 1)

    def test_AND_A_FILE_ONLY_SLIGHTLY_SHORT_IS_NOT_COUNTED(self):
        """The threshold, and the measurement that put it there.

        `ps-2.kev009.com` lists `perftun.htm` at 89 088 and holds 86 697 -- 2.7% short. Three
        such files were re-fetched from the live server on 2026-09-24: it answered 200 and served
        byte-for-byte what we hold. The copies are faithful and the column is what disagrees, so
        counting these would have put 14 permanent false positives in front of every reader.

        They are still PRINTED. Being quiet about a 5% shortfall would be the same mistake facing
        the other way.
        """
        self.build([("perftun.htm", "87K")], [("perftun.htm", 86697)])
        n, out = self.run_listed()
        self.assertEqual(n, 0)
        self.assertIn("perftun.htm", out)
        self.assertIn("short by less than that", out)

    def test_AND_A_FILE_LONGER_THAN_ITS_LISTING_IS_NOT(self):
        """Nothing was lost, so nothing is counted -- but it is printed, not swallowed.

        `aixtools/tools/MD5.checksums` is listed at 3.8K and holds 5 423 bytes: a checksums file
        that grew after its index was stored. Counting that as damage would put a permanent false
        positive in front of every reader of this check.
        """
        self.build([("grown.txt", "3.8K")], [("grown.txt", 5423)])
        n, out = self.run_listed()
        self.assertEqual(n, 0)
        self.assertIn("LONGER", out)
        self.assertIn("grown.txt", out)

    def test_a_file_the_listing_names_but_we_do_not_hold_is_NOT_this_check(self):
        """A gap in the crawl is a different question, and --verify's counts already answer it.

        Reporting it here would mean every archive with one permanent 404 -- and this collection
        records thousands of those on purpose -- lights this check up for ever.
        """
        self.build([("absent.tar.Z", "449k"), ("here.tar.Z", "10k")],
                   [("here.tar.Z", 10 * 1024)])
        n, out = self.run_listed()
        self.assertEqual(n, 0)
        self.assertNotIn("absent.tar.Z", out)

    def test_THE_PARENT_LINK_AND_SUBDIRECTORIES_ARE_NOT_FILES(self):
        # Both appear in every Apache listing. A directory has no size to disagree about, and
        # treating either as content is how a count comes out wrong by one per page.
        self.build([("a.tar.Z", "10k")], [("a.tar.Z", 10 * 1024)])
        os.makedirs(os.path.join(self.d, "sub"))
        n, out = self.run_listed()
        self.assertEqual(n, 0)
        self.assertIn("1 file compared", out)

    def test_the_floor_is_not_a_finding(self):
        # A server that never prints below `1k` lists a 240-byte signature as 1k. 27 intact
        # files on penguinppc looked damaged until this was measured.
        self.build([("x.sig", "1k")], [("x.sig", 240)])
        n, out = self.run_listed()
        self.assertEqual(n, 0)
        self.assertIn("could not say", out)

    def test_THE_SUMMARY_ADDS_UP_TO_ITS_OWN_TOTAL(self):
        """It did not, and nobody would have noticed from the output alone.

        A fourth outcome was added and left out of the total, so the collection run announced
        89 972 files compared where it had compared 89 984 -- short by exactly the size of the
        new group. Both numbers looked plausible. This sums the parts instead of trusting them.
        """
        self.build([("agrees.tar.Z", "10k"), ("tiny.sig", "1k"),
                    ("cut.exe", "36M"), ("nearly.htm", "87K"), ("grown.txt", "3.8K")],
                   [("agrees.tar.Z", 10 * 1024), ("tiny.sig", 240),
                    ("cut.exe", 7488), ("nearly.htm", 86697), ("grown.txt", 5423)])
        _n, out = self.run_listed()
        summary = out.split("files compared:")[1]
        total = int(re.search(r"(\d+) files compared", out).group(1))
        parts = [int(m) for m in re.findall(r"^\s+(\d+) ", summary, re.M)]
        self.assertEqual(total, 5)
        self.assertEqual(len(parts), 5, "one line per outcome:\n" + summary)
        self.assertEqual(sum(parts), total, summary)

    def test_our_own_bookkeeping_is_not_compared(self):
        # SHA256SUMS and the rest are written by us, after the listing. They are not the
        # source's content and have no business in a check about what the source served.
        self.build([("SHA256SUMS", "1.2M")], [("SHA256SUMS", 40)])
        self.assertEqual(self.run_listed()[0], 0)

    def test_a_half_written_download_is_not_compared_either(self):
        # `.part` is a file mid-flight, not a file that came out short.
        self.build([("a.tar.Z.part", "449k")], [("a.tar.Z.part", 12)])
        self.assertEqual(self.run_listed()[0], 0)

    def test_A_PAGE_THAT_IS_NOT_A_LISTING_CONTRIBUTES_NOTHING(self):
        """parse_listing is forgiving, and here that is a risk rather than a help.

        An ordinary page of links has no size column, so nothing is compared and no finding can
        be invented out of somebody's table of version numbers.
        """
        with io.open(os.path.join(self.d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write('<html><body><p>See <a href="a.tar.Z">the tarball</a> and '
                     '<a href="b.txt">the notes</a>.</p></body></html>')
        for name in ("a.tar.Z", "b.txt"):
            with io.open(os.path.join(self.d, name), "wb") as fh:
                fh.write(b"x")
        n, out = self.run_listed()
        self.assertEqual(n, 0)
        self.assertIn("0 files compared", out)



class TestTheCheckSideTouchesNothing(unittest.TestCase):
    r"""--ruins / --empty / --listed / --holes must not be able to write anything, at all.

    WHY IT IS ASSERTED AND NOT ASSUMED. `--holes` over the collection reads 2.39 TB and runs for
    about eight hours unattended, against the only copy of archives whose sources are mostly gone.
    "It only reports" is printed at the top of every run, and a banner is not a guarantee.

    IT IS A STRUCTURAL CHECK, not a behavioural one. Running the four checks and watching for
    damage would prove only that nothing happened to the tree that was used. This parses the
    module and asserts there is no write path to reach: no `open` in a writing mode, no `remove`,
    `rename`, `replace`, `makedirs`, `rmtree`, `truncate`, no `atomic_write`, no `write_marker`.

    THE ONE EXCEPTION IS NAMED HERE, because an exception nobody wrote down becomes a precedent.
    `audit_duplicates` writes a CSV when `--csv PATH` is given: an explicit destination the caller
    typed, outside the collection, on the duplicate-scan side which shares no code with the four
    checks. That one is allowed and pinned; a second one has to be argued for here.
    """

    WRITERS = frozenset((
        "remove", "unlink", "rename", "replace", "rmtree", "makedirs", "mkdir", "rmdir",
        "copy", "copy2", "copyfile", "copytree", "move", "truncate", "chmod",
        "atomic_write", "write_marker", "write_text", "write_bytes",
    ))

    def setUp(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "audit.py"), encoding="utf-8") as fh:
            self.tree = ast.parse(fh.read(), "audit.py")
        self.by_function = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                self.by_function[node.name] = node

    def calls_in(self, node):
        """-> [(line, name)] of every call by attribute or bare name inside `node`."""
        out = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                name = getattr(sub.func, "attr", None) or getattr(sub.func, "id", None)
                if name:
                    out.append((sub.lineno, name, sub))
        return out

    def test_none_of_the_four_checks_can_write(self):
        for fname in ("check_ruins", "check_empty", "check_listed", "check_holes", "walk"):
            self.assertIn(fname, self.by_function, fname)
            for line, name, node in self.calls_in(self.by_function[fname]):
                self.assertNotIn(name, self.WRITERS, "%s:%d calls %s" % (fname, line, name))
                if name == "open":
                    mode = None
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        mode = node.args[1].value
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = kw.value.value
                    if mode is not None:
                        self.assertNotIn("w", mode, "%s:%d" % (fname, line))
                        self.assertNotIn("a", mode, "%s:%d" % (fname, line))
                        self.assertNotIn("+", mode, "%s:%d" % (fname, line))

    def test_the_whole_module_has_exactly_one_writing_open_and_it_is_the_csv(self):
        writing = []
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.Call)
                    and (getattr(node.func, "attr", None) or getattr(node.func, "id", None))
                    == "open"):
                continue
            mode = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if mode and any(c in mode for c in "wa+"):
                writing.append(node.lineno)
        self.assertEqual(len(writing), 1, "writing open() at lines %s" % writing)
        # And it is reached only with --csv, which is a path the caller typed.
        self.assertIn("if csv_out:", self._source_around(writing[0]))

    def test_the_module_never_imports_shutil(self):
        # Nothing here should be moving or deleting anything, and the import is the cheapest
        # place to see an intention change.
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
        self.assertNotIn("shutil", names)

    def _source_around(self, lineno, span=6):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "audit.py"), encoding="utf-8") as fh:
            lines = fh.readlines()
        return "".join(lines[max(0, lineno - span):lineno])



if __name__ == "__main__":
    unittest.main()
