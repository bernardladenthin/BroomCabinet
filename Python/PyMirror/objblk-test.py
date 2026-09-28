#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""A record that states its own length -- and what that settles in both directions.

WHERE THIS CAME FROM. C3 asked about 7 files in an Ultima VI savegame directory that are entirely
zeros. `cannot_be_empty()` already declines to judge them, so they were never reported as losses,
and the easy answer was to leave it there. The files are 2 bytes; their full siblings run from 18
to 14 306 bytes. Two bytes of nothing is not obviously content and not obviously damage, and
"nobody complained" is not a finding either way.

THE FORMAT ANSWERS IT. An `OBJBLK??` file holds the objects on one map chunk: a two-byte count,
then a fixed-size record per object. If that is right, then `size == 2 + 8 * count` -- and the
file states the number it must be checked against. Measured over all 69 in that directory on
2026-09-24: 68 agree exactly. That is not a theory any more.

AND THE SAME RULE DECIDES BOTH CASES, which is why this test is worth having rather than a note:

  * `OBJBLKAF` and six like it hold 0x00 0x00 -- count zero, expected length 2, actual length 2.
    They are COMPLETE records that say "no objects on this chunk". Not damage; the game wrote
    them. A zero-length file would have been damage, and these are not zero-length.

  * `OBJBLKDF` holds 3 089 bytes and its own count demands 3 090. ONE BYTE SHORT. Nothing in this
    tool sees it: it is not empty, its extension is nothing MAGIC knows, and --holes looks for
    16 MB of zeros. It was found only because the rule that cleared the other seven was applied
    to all 69 rather than to the seven in question.

WHAT IS STORED AND WHY SO LITTLE. Four files, 3 183 bytes: one empty, two smallest full ones, and
the damaged one. The rule is arithmetic over a two-byte header, so 134 KB of somebody's savegame
would prove nothing the two-byte header does not. The measurement over all 69 is in
`expected.json`, which is a record of what was counted, not a substitute for counting it.
"""
import hashlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "testdata", "objblk")

HEADER = 2   # the object count, two bytes, little endian
RECORD = 8   # one object

IN_MIRROR = os.path.join(common.MIRROR_ROOT, "oldskool", "CMSSoundPatches",
                         "Games", "ULTIMA6", "SAVEGAME")


def load():
    with io.open(os.path.join(DATA, "expected.json"), encoding="utf-8") as fh:
        return json.load(fh)


def objects(blob):
    """The count the file states about itself."""
    return blob[0] | (blob[1] << 8)


def read(name):
    with io.open(os.path.join(DATA, name), "rb") as fh:
        return fh.read()


class TheStoredFilesAreWhatWasMeasured(unittest.TestCase):
    """Before anything is concluded: are these the same bytes that were counted?"""

    def setUp(self):
        self.record = load()

    def test_each_file_is_byte_for_byte_what_the_record_says(self):
        for case in self.record["cases"]:
            blob = read(case["file"])
            self.assertEqual(len(blob), case["bytes"], case["file"])
            self.assertEqual(hashlib.sha256(blob).hexdigest(), case["sha256"], case["file"])

    def test_the_record_and_the_directory_hold_the_same_files(self):
        listed = {c["file"] for c in self.record["cases"]}
        on_disk = {n for n in os.listdir(DATA)
                   if n.upper().startswith("OBJBLK") and not n.endswith(".license")}
        self.assertEqual(on_disk, listed)

    def test_every_stored_file_carries_its_licence(self):
        # These are somebody else's bytes. A fixture without a sidecar is a REUSE failure that
        # only shows up at release time, which is much later than here.
        for case in self.record["cases"]:
            self.assertTrue(os.path.exists(os.path.join(DATA, case["file"] + ".license")),
                            case["file"])

    def test_every_case_carries_a_reason(self):
        # A fixture nobody wrote a reason for is a fixture nobody can decide about later.
        for case in self.record["cases"]:
            self.assertTrue(case["why"].strip(), case["file"])


class TheRuleHolds(unittest.TestCase):
    """size == 2 + 8 * count, on the files that are stored."""

    def test_the_two_byte_file_is_a_complete_record_of_nothing(self):
        blob = read("OBJBLKAF")
        self.assertEqual(blob, b"\x00\x00")
        self.assertEqual(objects(blob), 0)
        self.assertEqual(len(blob), HEADER + RECORD * objects(blob))

    def test_the_full_files_agree_with_their_own_count(self):
        for name in ("OBJBLKAA", "OBJBLKAC"):
            blob = read(name)
            self.assertEqual(len(blob), HEADER + RECORD * objects(blob), name)

    def test_the_record_size_is_eight_and_not_something_that_also_fits(self):
        """Two witnesses, because one equation has many solutions.

        18 = 2 + 8 x 2 and 74 = 2 + 8 x 9. A record size of 8 satisfies both. Nothing else does:
        from the two lengths, 8 is forced.
        """
        a, b = read("OBJBLKAA"), read("OBJBLKAC")
        fits = [r for r in range(1, 64)
                if len(a) == HEADER + r * objects(a) and len(b) == HEADER + r * objects(b)]
        self.assertEqual(fits, [RECORD])


class TheDamagedOne(unittest.TestCase):
    """OBJBLKDF, and the reason it is kept rather than mentioned."""

    def test_it_is_exactly_one_byte_short_of_what_it_demands(self):
        blob = read("OBJBLKDF")
        want = HEADER + RECORD * objects(blob)
        self.assertEqual(objects(blob), 386)
        self.assertEqual(want, 3090)
        self.assertEqual(len(blob), 3089)
        self.assertEqual(want - len(blob), 1)

    def test_its_last_record_is_cut_and_not_merely_missing(self):
        """A file short by a whole record would be a different fault: a truncated write.

        Short by ONE BYTE means the last record began and did not finish, which is what a copy
        that stopped mid-stream looks like. Saying which of the two it is matters, so it is
        measured rather than asserted in prose.
        """
        blob = read("OBJBLKDF")
        self.assertNotEqual((len(blob) - HEADER) % RECORD, 0)
        self.assertEqual((len(blob) - HEADER) % RECORD, RECORD - 1)

    def test_no_check_in_this_tool_sees_it_today(self):
        """The honest part: this is a finding the tool does not make.

        If one of these ever starts to bite, this test fails and somebody gets to decide whether
        the check found it for the right reason -- which is better than the finding quietly
        becoming a duplicate.
        """
        self.assertFalse(audit.cannot_be_empty("OBJBLKDF"))
        blob = read("OBJBLKDF")
        self.assertNotEqual(blob.strip(bytes(1)), b"")          # not empty, so --empty passes it
        self.assertLess(len(blob), 16 * 1024 * 1024)            # far under --holes' floor
        self.assertIsNone(audit.file_extension("OBJBLKDF") or None)


class WhenTheMirrorIsHere(unittest.TestCase):
    """The count over all 69, re-taken -- skipped where the collection is not mounted."""

    def setUp(self):
        self.record = load()
        path = audit.long_path(IN_MIRROR)
        if not os.path.isdir(path):
            self.skipTest("the collection is not mounted here")
        self.path = path

    def test_sixty_eight_of_sixty_nine_agree_and_the_odd_one_is_the_one_named(self):
        agree, short = 0, []
        names = [n for n in sorted(os.listdir(self.path)) if n.upper().startswith("OBJBLK")]
        for name in names:
            p = os.path.join(self.path, name)
            size = os.path.getsize(p)
            with io.open(p, "rb") as fh:
                count = objects(fh.read(HEADER))
            if size == HEADER + RECORD * count:
                agree += 1
            else:
                short.append([name, size, HEADER + RECORD * count])
        self.assertEqual(len(names), self.record["objblk_files"])
        self.assertEqual(agree, self.record["size_matches_header"])
        self.assertEqual(short, self.record["short"])

    def test_the_stored_files_are_copies_of_the_ones_in_the_collection(self):
        for case in self.record["cases"]:
            with io.open(os.path.join(self.path, case["file"]), "rb") as fh:
                self.assertEqual(fh.read(), read(case["file"]), case["file"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
