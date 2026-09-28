#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""HOLES_AT_SOURCE -- three files that are damaged, and not damaged by us.

WHERE THEY CAME FROM. The first full `--holes` run over the collection, 2026-09-25: 99 archives,
2.39 TB, 67 files with whole empty blocks inside them. Three of the 67 are not a media format
being itself:

    AlphaStations.avi   18 of 19 blocks empty, 94.7 %
    DU11 ... .pdf       27 of 29 blocks empty, 93.1 %
    RMS-11 ... .pdf     56 of 76 blocks empty, 73.7 %

THE AVI IS WHY `--holes` EXISTS. Its RIFF header declares 0x012D4F18 + 8 = 19 746 592 bytes, which
is exactly the size on disk. Right length, right signature, right self-declared length -- and 94.7
per cent of it is nothing. `--verify` hashes it to itself and is content; `--empty` sees a file
that is not empty; `--ruins` reads a head that is a perfectly good RIFF. Nothing else in this
collection can see this file.

AND ASKING FOR THE LENGTH VERY NEARLY CLOSED IT THE WRONG WAY. All three sources answer HEAD with
EXACTLY the length held here. That reads like "the source has the same broken file" and it is not
evidence: a source holding the INTACT file at the same length is precisely the case where a repair
is possible, and from a HEAD request the two are indistinguishable. So all three were fetched
whole -- 130 MB -- and compared. Byte for byte identical, all three. Our copies are faithful;
copying from the source would change nothing.

WHAT THIS FILE CHECKS, and what it cannot. It re-takes the LOCAL half of the measurement: the
files are still there, still those bytes, still that damaged, and `holes_at_source()` still
recognises them. It does not re-fetch 130 MB on every test run. The remote half is a recorded
SHA-256, and the day somebody wants it re-checked the record says exactly which digest to compare
against -- which is the whole reason the digest is in the table rather than a length.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402
import common  # noqa: E402

COLLECTION = common.MIRROR_ROOT
BLK = 1 << 20


def held(rel):
    return common.long_path(os.path.join(COLLECTION, rel.replace("/", os.sep)))


class TheTableItself(unittest.TestCase):
    """What can be checked without touching the collection."""

    def test_it_holds_the_three_the_run_found(self):
        self.assertEqual(len(audit.HOLES_AT_SOURCE), 3)

    def test_every_row_is_a_path_a_size_and_a_digest(self):
        for rel, size, sha in audit.HOLES_AT_SOURCE:
            self.assertNotIn("\\", rel)
            self.assertFalse(rel.startswith("/"))
            self.assertGreater(size, 16 * BLK, rel)   # under the floor it would never be read
            self.assertEqual(len(sha), 64, rel)
            self.assertEqual(sha, sha.lower().strip(), rel)
            int(sha, 16)                              # raises if it is not hex

    def test_no_path_appears_twice(self):
        paths = [rel for rel, _s, _h in audit.HOLES_AT_SOURCE]
        self.assertEqual(len(paths), len(set(paths)))

    def test_it_does_not_overlap_the_three_zero_tables(self):
        """A file is either entirely zero or partly zero. It cannot be recorded as both."""
        mine = {rel for rel, _s, _h in audit.HOLES_AT_SOURCE}
        for other in (audit.ZERO_AT_SOURCE, audit.ZERO_IN_CAPTURE, audit.ZERO_IN_THE_MEDIUM):
            self.assertEqual(mine & {rel for rel, _s in other}, set())


class TheLookup(unittest.TestCase):
    """holes_at_source(), which is what --holes calls."""

    def setUp(self):
        self.rel, self.size, self.sha = audit.HOLES_AT_SOURCE[0]

    def test_it_recognises_a_recorded_file(self):
        self.assertTrue(audit.holes_at_source(self.rel, self.sha))

    def test_THE_DIGEST_IS_PART_OF_THE_KEY(self):
        """The whole reason this table is not keyed like the other three.

        If the path alone were enough, a source that later replaced the file with an intact one
        of the same length would go on being recognised -- and a repairable loss would be
        suppressed by a record of the damage it used to have.
        """
        self.assertFalse(audit.holes_at_source(self.rel, "0" * 64))

    def test_it_matches_from_the_right_because_root_may_be_narrower(self):
        short = self.rel.split("/", 1)[1]
        self.assertTrue(audit.holes_at_source(short, self.sha))

    def test_it_matches_on_a_path_boundary(self):
        tail = self.rel.rsplit("/", 1)[1]
        self.assertTrue(audit.holes_at_source(tail, self.sha))
        self.assertFalse(audit.holes_at_source("x" + tail, self.sha))

    def test_it_accepts_a_windows_path(self):
        self.assertTrue(audit.holes_at_source(self.rel.replace("/", os.sep), self.sha))

    def test_an_unknown_file_is_not_recognised(self):
        self.assertFalse(audit.holes_at_source("somewhere/else.avi", self.sha))


class WhenTheCollectionIsHere(unittest.TestCase):
    """The local half of the measurement, re-taken. Skipped where the collection is not mounted."""

    def setUp(self):
        if not os.path.isdir(common.long_path(COLLECTION)):
            self.skipTest("the collection is not mounted here")

    def test_each_file_is_still_there_at_the_recorded_size_and_digest(self):
        for rel, size, sha in audit.HOLES_AT_SOURCE:
            path = held(rel)
            self.assertTrue(os.path.exists(path), rel)
            self.assertEqual(os.path.getsize(path), size, rel)
            self.assertEqual(common.sha256_file(path), sha, rel)

    def test_each_one_really_does_have_whole_empty_blocks(self):
        """The claim the table makes. A row for an intact file would suppress a real finding."""
        zero = bytes(BLK)
        for rel, _size, _sha in audit.HOLES_AT_SOURCE:
            empty = total = 0
            with io.open(held(rel), "rb") as fh:
                while True:
                    b = fh.read(BLK)
                    if not b:
                        break
                    total += 1
                    if b == zero[:len(b)]:
                        empty += 1
            self.assertGreater(empty, 0, rel)
            self.assertGreater(empty / total, 0.5, rel)   # all three are over 70 %

    def test_the_avi_declares_its_own_length_and_is_right_about_it(self):
        """The finding in one line: the file is exactly as long as it says, and mostly absent."""
        rel = next(r for r, _s, _h in audit.HOLES_AT_SOURCE if r.endswith(".avi"))
        path = held(rel)
        with io.open(path, "rb") as fh:
            head = fh.read(12)
        self.assertEqual(head[:4], b"RIFF")
        self.assertEqual(head[8:12], b"AVI ")
        declared = int.from_bytes(head[4:8], "little") + 8
        self.assertEqual(declared, os.path.getsize(path))

    def test_both_pdfs_open_correctly_and_end_in_nothing(self):
        """A valid header and no end marker after the first-page cross reference."""
        for rel, size, _sha in audit.HOLES_AT_SOURCE:
            if not rel.endswith(".pdf"):
                continue
            with io.open(held(rel), "rb") as fh:
                blob = fh.read()
            self.assertEqual(blob[:5], b"%PDF-", rel)
            self.assertEqual(blob[-4096:], bytes(4096), rel)
            # The last %%EOF sits in the first kilobyte of a file of tens of megabytes.
            self.assertLess(blob.rfind(b"%%EOF"), 1024, rel)

    def test_the_check_no_longer_calls_them_losses(self):
        """End to end: --holes over one of those archives must report 0 incomplete files."""
        rel = next(r for r, _s, _h in audit.HOLES_AT_SOURCE if r.endswith(".avi"))
        archive = os.path.join(COLLECTION, rel.split("/")[0])
        out = io.StringIO()
        keep = sys.stdout
        sys.stdout = out
        try:
            found = audit.check_holes(archive, 16 * BLK)
        finally:
            sys.stdout = keep
        self.assertEqual(found, 0)
        self.assertIn("SOURCE SERVES WITH THE SAME HOLES", out.getvalue())
        self.assertIn("AlphaStations.avi", out.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
