#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""ZERO_IN_THE_MEDIUM, proved from the medium's own index rather than from the collection.

WHAT THIS TEST IS FOR. `audit.ZERO_IN_THE_MEDIUM` says of 43 files: they are all zeros, and that
is not damage, because the disk they were extracted from is zero in exactly those blocks. That is
a claim about somebody else's 1970s medium, and a table of 43 paths and sizes carries no trace of
why anybody believed it. This test re-derives the whole claim from two stored fixtures, so the
table can never quietly drift away from its evidence.

IT NEEDS NEITHER THE MIRROR NOR A NETWORK, which is the whole reason this third table was worth
separating from the other two. ZERO_AT_SOURCE can only be re-checked while the host answers, and
`update.uu.se` and `hpux.connect.org.uk` have already stopped. ZERO_IN_CAPTURE rests on a packing
list somebody else wrote in 2008. This one rests on arithmetic over a block index, and arithmetic
does not go offline.

WHY THE IMAGE ITSELF IS NOT STORED. It is 377 344 bytes of DEC's software, and 363 of its 737
blocks are zeros -- copying a third of a megabyte to prove that some of it is nothing would be
copying it for no reason. What is stored instead is `blockmap.json`, one character per block
recording whether that block is entirely zero, plus the image's SHA-256 so the map can be re-tied
to the image whenever it is at hand. `mirror_is_here()` below does exactly that when it is.

WHY ONE REAL BLOCK IS STORED. A block table that is off by a constant would make every check here
pass and mean nothing. `block-01162.bin` is the real 512 bytes at the offset this test computes
for `acos.ra`, and it has to decode to the RALF assembler's comment character -- which is what an
`.ra` source file actually begins with. That is the one assumption that cannot be checked by
arithmetic, so it is checked against bytes.
"""
import hashlib
import io
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "testdata", "medium")

# An OS/8 block is 256 twelve-bit words. The image stores each word in two bytes, so a block is
# 512 bytes THERE; the extractor packs the same 3 072 bits into 384 bytes HERE. Both numbers are
# needed and they are not interchangeable -- confusing them is the mistake this test exists for.
IN_IMAGE = 512
WHEN_EXTRACTED = 384

# Where the 43 rows point. Kept as one string because every row shares it, and because a test
# that spelled the prefix out 43 times would pass after somebody edited 42 of them.
UNDER = "somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/"
IMAGE_IN_MIRROR = os.path.join(common.MIRROR_ROOT, "somuchstuff-pdp8", "trunk", "pdp8",
                               "src", "dec", "dec-s8-lftna",
                               "dec-s8-lftna-a-ua1.dsk")


def load():
    with io.open(os.path.join(DATA, "blockmap.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    with io.open(os.path.join(DATA, "dec-s8-lftna-a-ua1.xml"), encoding="utf-8",
                 errors="replace") as fh:
        xml = fh.read()
    rows = {}
    for name, start, end, mode in re.findall(
            r"<file name='([^']*)' start=(\d+) end=(\d+) mode=(\w+)", xml):
        rows[name.split("/")[-1]] = (int(start, 8), int(end, 8), mode)
    return plan, rows


class TheIndexAndTheMap(unittest.TestCase):
    """The two fixtures, before anything is concluded from them."""

    def setUp(self):
        self.plan, self.rows = load()

    def test_the_map_covers_the_whole_image(self):
        self.assertEqual(len(self.plan["map"]), self.plan["blocks"])
        self.assertEqual(self.plan["blocks"] * self.plan["block_size"], self.plan["bytes"])
        self.assertEqual(self.plan["map"].count("0"), self.plan["zero_blocks"])

    def test_the_index_names_every_file_once(self):
        # A duplicated name would make the lookups below answer about the wrong block range, and
        # the arithmetic would still come out clean.
        with io.open(os.path.join(DATA, "dec-s8-lftna-a-ua1.xml"), encoding="utf-8",
                     errors="replace") as fh:
            names = re.findall(r"<file name='([^']*)'", fh.read())
        bases = [n.split("/")[-1] for n in names]
        self.assertEqual(len(bases), len(set(bases)))
        self.assertEqual(len(bases), 126)

    def test_every_block_range_lies_inside_the_image(self):
        for base, (start, end, _mode) in self.rows.items():
            self.assertLessEqual(start, end, base)
            self.assertLess(end, self.plan["blocks"], base)

    def test_the_block_to_offset_mapping_is_right(self):
        """The one thing arithmetic cannot check: that block 01162 is where we think it is.

        `acos.ra` starts at block 01162 and is a RALF assembler source, whose comment character is
        `/`. OS/8 stores text with the high bit set, so a `/` followed by CR LF reads as
        0xAF 0x08 0x8D 0x0A. If the mapping were off by even one block this would be something
        else entirely -- and every zero check in this file would go on passing.
        """
        with io.open(os.path.join(DATA, "block-01162.bin"), "rb") as fh:
            block = fh.read()
        self.assertEqual(len(block), IN_IMAGE)
        self.assertEqual(block[:4], b"\xaf\x08\x8d\x0a")
        self.assertEqual(self.rows["acos.ra"][0], 0o1162)
        self.assertEqual(self.plan["map"][0o1162], "x")  # and the map agrees it is not empty


class TheTableAgreesWithTheMedium(unittest.TestCase):
    """The 43 rows, each one re-derived rather than trusted."""

    def setUp(self):
        self.plan, self.rows = load()
        self.mine = [(rel, size) for rel, size in audit.ZERO_IN_THE_MEDIUM if UNDER in rel]

    def test_all_forty_three_rows_are_from_this_disk(self):
        self.assertEqual(len(self.mine), len(audit.ZERO_IN_THE_MEDIUM))
        self.assertEqual(len(self.mine), 43)

    def test_no_row_appears_twice(self):
        paths = [rel for rel, _s in audit.ZERO_IN_THE_MEDIUM]
        self.assertEqual(len(paths), len(set(paths)))

    def test_every_recorded_size_is_what_its_block_range_demands(self):
        """size == blocks x 384. This is the arithmetic the table rests on."""
        for rel, size in self.mine:
            base = rel.rsplit("/", 1)[1]
            self.assertIn(base, self.rows, base)
            start, end, _mode = self.rows[base]
            self.assertEqual(size, (end - start + 1) * WHEN_EXTRACTED,
                             "%s: %d B but blocks %o..%o" % (base, size, start, end))

    def test_every_recorded_file_sits_on_blocks_the_image_holds_as_zeros(self):
        for rel, _size in self.mine:
            start, end, _mode = self.rows[rel.rsplit("/", 1)[1]]
            span = self.plan["map"][start:end + 1]
            self.assertEqual(span, "0" * len(span), rel)

    def test_and_the_other_way_round_nothing_zero_was_left_out(self):
        """The direction that catches a table somebody stopped maintaining.

        Checking only that the 43 are zero would still pass if the disk had 60 zero-filled files
        and 17 had been dropped from the table. So: every file in the index whose blocks are all
        zeros must be in the table, and every file whose blocks are not must be absent from it.
        """
        listed = {rel.rsplit("/", 1)[1] for rel, _s in self.mine}
        zero_by_the_map, live_by_the_map = set(), set()
        for base, (start, end, _mode) in self.rows.items():
            if base.startswith("."):
                continue  # `.boot`, `.dir`, `.730` -- index entries with no filename at all
            span = self.plan["map"][start:end + 1]
            (zero_by_the_map if span == "0" * len(span) else live_by_the_map).add(base)
        self.assertEqual(zero_by_the_map - listed, set())
        self.assertEqual(listed - zero_by_the_map, set())
        self.assertEqual(listed & live_by_the_map, set())
        self.assertEqual(len(live_by_the_map), 80)


class TheLookupFunction(unittest.TestCase):
    """zero_in_the_medium(), which is what --empty actually calls."""

    def test_it_answers_the_recorded_size(self):
        rel, size = audit.ZERO_IN_THE_MEDIUM[0]
        self.assertEqual(audit.zero_in_the_medium(rel), size)

    def test_it_matches_from_the_right_because_root_may_be_narrower(self):
        """--root can be the collection or one directory inside it, and both must work."""
        rel, size = audit.ZERO_IN_THE_MEDIUM[0]
        short = rel.split("/", 1)[1]
        self.assertEqual(audit.zero_in_the_medium(short), size)
        self.assertEqual(audit.zero_in_the_medium(rel.rsplit("/", 2)[-2] + "/"
                                                  + rel.rsplit("/", 1)[1]), size)

    def test_it_matches_on_a_path_boundary_and_not_on_a_suffix(self):
        """`cos.ra` is in the table; `xcos.ra` somewhere else entirely must not match it."""
        self.assertIsNotNone(audit.zero_in_the_medium(UNDER + "cos.ra"))
        self.assertIsNone(audit.zero_in_the_medium("elsewhere/xcos.ra"))
        self.assertIsNone(audit.zero_in_the_medium("cos.rax"))

    def test_it_accepts_a_windows_path(self):
        rel, size = audit.ZERO_IN_THE_MEDIUM[0]
        self.assertEqual(audit.zero_in_the_medium(rel.replace("/", os.sep)), size)

    def test_an_unknown_file_gets_no_answer(self):
        self.assertIsNone(audit.zero_in_the_medium("somewhere/else.ra"))


class TheThreeTablesStayApart(unittest.TestCase):
    """Each table's opening sentence has to stay true for every one of its rows.

    A file in two of them would mean two different stories about the same bytes, and --empty
    would report whichever branch it reached first. That is the kind of contradiction a reader
    cannot see and a test can.
    """

    def test_no_file_is_in_two_tables(self):
        a = {rel for rel, _s in audit.ZERO_AT_SOURCE}
        b = {rel for rel, _s in audit.ZERO_IN_CAPTURE}
        c = {rel for rel, _s in audit.ZERO_IN_THE_MEDIUM}
        self.assertEqual(a & b, set())
        self.assertEqual(a & c, set())
        self.assertEqual(b & c, set())

    def test_the_tables_are_the_sizes_the_record_says(self):
        self.assertEqual(len(audit.ZERO_AT_SOURCE), 75)
        self.assertEqual(len(audit.ZERO_IN_CAPTURE), 79)
        self.assertEqual(len(audit.ZERO_IN_THE_MEDIUM), 43)

    def test_every_row_everywhere_is_a_path_and_a_positive_size(self):
        for table in (audit.ZERO_AT_SOURCE, audit.ZERO_IN_CAPTURE, audit.ZERO_IN_THE_MEDIUM):
            for rel, size in table:
                self.assertIsInstance(rel, str)
                self.assertNotIn("\\", rel)
                self.assertFalse(rel.startswith("/"))
                self.assertGreater(size, 0)


class WhenTheMirrorIsHere(unittest.TestCase):
    """Tie the stored map back to the image -- skipped where the collection is not mounted.

    This is the step that would otherwise be taken on trust. The map was derived from the image
    once, on 2026-09-24; without this, a map edited by hand afterwards would satisfy every other
    test in the file.
    """

    def setUp(self):
        self.plan, _rows = load()
        path = audit.long_path(IMAGE_IN_MIRROR)
        if not os.path.exists(path):
            self.skipTest("the collection is not mounted here")
        self.path = path

    def test_the_stored_map_is_a_true_statement_about_the_image(self):
        with io.open(self.path, "rb") as fh:
            img = fh.read()
        self.assertEqual(len(img), self.plan["bytes"])
        self.assertEqual(hashlib.sha256(img).hexdigest(), self.plan["sha256"])
        size = self.plan["block_size"]
        fresh = "".join("0" if img[i * size:(i + 1) * size].strip(bytes(1)) == b"" else "x"
                        for i in range(self.plan["blocks"]))
        self.assertEqual(fresh, self.plan["map"])

    def test_the_stored_block_is_really_from_the_image(self):
        with io.open(self.path, "rb") as fh:
            fh.seek(0o1162 * IN_IMAGE)
            from_image = fh.read(IN_IMAGE)
        with io.open(os.path.join(DATA, "block-01162.bin"), "rb") as fh:
            self.assertEqual(fh.read(), from_image)


if __name__ == "__main__":
    unittest.main(verbosity=2)
