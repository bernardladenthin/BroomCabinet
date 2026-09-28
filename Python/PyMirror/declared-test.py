#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""`declared_length` and `--declared`: the check that needs nothing but the file.

WHERE IT CAME FROM. An Ultima VI savegame states its object count in its first two bytes, so
`size == 2 + 8 * count`. Measured over all 69 in that directory: 68 agreed and the 69th was one
byte short -- a damaged file that NOTHING in this collection could see. Not empty, no signature
`MAGIC` knows, far under `--holes`' 16 MB floor, and `--verify` hashes it to itself and is
content. This is that hand measurement generalised to the formats that are actually here: 66 439
ZIP-family files, 2 042 `.iso` and 636 RIFF.

THE TWO THINGS MOST WORTH GETTING RIGHT, and both are about NOT inventing findings:

  * **Short is damage; long is not.** A file longer than it declares is ordinary -- a CD image
    padded to a track boundary, a self-extracting archive with a stub before the zip, a RIFF with
    trailing metadata. Reporting those would bury the real findings under the normal ones.

  * **"No opinion" and "damaged" are different answers.** A `.iso` that is not ISO 9660 (plenty
    are UDF or a raw track), a ZIP64 archive whose 32-bit fields are placeholders -- these make
    no statement, and a check that read them as zero-length would report the whole collection.

WHAT IT CATCHES THAT NOTHING ELSE DOES. A download that simply stopped: no zeros, just fewer
bytes. And a zero-length `.zip`, which `check_empty` skips outright because it tests `size == 0`
and moves on.
"""
import io
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402
import common  # noqa: E402


def riff(payload=b"WAVEfake", declared=None):
    """A RIFF whose size field says `declared` (default: the truth)."""
    body = payload
    size = len(body) if declared is None else declared
    return b"RIFF" + struct.pack("<I", size) + body


def zip_bytes(entry=b"PK\x03\x04" + b"\x00" * 26, comment=b""):
    """A minimal zip: one local header, an empty central directory, and an EOCD."""
    cd_at = len(entry)
    cd = b""
    eocd = (b"PK\x05\x06" + struct.pack("<HHHH", 0, 0, 0, 0)
            + struct.pack("<II", len(cd), cd_at) + struct.pack("<H", len(comment)))
    return entry + cd + eocd + comment


def iso_bytes(blocks=40, block_size=2048, pad_to=None):
    """An ISO 9660 image whose primary volume descriptor declares blocks x block_size."""
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    struct.pack_into("<I", pvd, 80, blocks)
    struct.pack_into("<H", pvd, 128, block_size)
    blob = bytearray(common.ISO_PVD_AT) + pvd
    want = blocks * block_size if pad_to is None else pad_to
    if len(blob) < want:
        blob += bytes(want - len(blob))
    return bytes(blob[:want]) if want < len(blob) else bytes(blob)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="declared-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, blob):
        path = os.path.join(self.tmp, name)
        with io.open(path, "wb") as fh:
            fh.write(blob)
        return path


class WhatMakesNoStatement(Tmp):
    """"No opinion" must never be confused with "damaged"."""

    def test_an_extension_nobody_listed(self):
        self.assertIsNone(common.declared_length(self.write("x.txt", b"hello")))

    def test_a_riff_file_that_does_not_start_with_RIFF(self):
        # That is --ruins' question, not this one.
        self.assertIsNone(common.declared_length(self.write("x.avi", b"not a riff at all")))

    def test_an_iso_that_is_not_ISO_9660(self):
        """Plenty of `.iso` are UDF, HFS, or one raw track. A missing PVD is not damage."""
        self.assertIsNone(common.declared_length(self.write("x.iso", bytes(100000))))

    def test_an_iso_too_short_to_hold_a_descriptor(self):
        self.assertIsNone(common.declared_length(self.write("x.iso", b"CD001" * 10)))

    def test_a_ZIP64_archive_whose_fields_are_placeholders(self):
        """0xFFFFFFFF is "look in the zip64 record", not a length.

        Answering from it would make every zip64 archive four gigabytes short.
        """
        eocd = (b"PK\x05\x06" + struct.pack("<HHHH", 0, 0, 0, 0)
                + struct.pack("<II", 0xFFFFFFFF, 0xFFFFFFFF) + struct.pack("<H", 0))
        self.assertIsNone(common.declared_length(self.write("x.zip", b"PK\x03\x04" + eocd)))

    def test_a_file_that_cannot_be_opened(self):
        self.assertIsNone(common.declared_length(os.path.join(self.tmp, "does-not-exist.zip")))


class RIFF(Tmp):

    def test_a_correct_riff_declares_its_own_length(self):
        blob = riff(b"WAVEdata1234")
        got = common.declared_length(self.write("a.wav", blob))
        self.assertEqual(got, (len(blob), "RIFF"))

    def test_the_size_field_counts_everything_after_itself(self):
        """Eight bytes, not zero and not twelve -- the classic off-by-a-header."""
        blob = riff(b"WAVE" + b"x" * 100)
        expected, _fmt = common.declared_length(self.write("a.wav", blob))
        self.assertEqual(expected, 8 + 4 + 100)

    def test_a_truncated_riff_is_shorter_than_it_says(self):
        blob = riff(b"WAVE" + b"x" * 100)[:60]
        expected, _fmt = common.declared_length(self.write("a.avi", blob))
        self.assertGreater(expected, 60)

    def test_webp_and_ani_are_riff_too(self):
        for name in ("a.webp", "a.ani"):
            self.assertEqual(common.declared_length(self.write(name, riff()))[1], "RIFF")


class ZIP(Tmp):

    def test_a_correct_zip_declares_its_own_length(self):
        blob = zip_bytes()
        self.assertEqual(common.declared_length(self.write("a.zip", blob)), (len(blob), "ZIP"))

    def test_a_comment_after_the_record_counts(self):
        blob = zip_bytes(comment=b"written by somebody")
        self.assertEqual(common.declared_length(self.write("a.zip", blob))[0], len(blob))

    def test_A_ZIP_WITH_NO_CENTRAL_DIRECTORY_IS_THE_FINDING(self):
        """The record is not optional, so its absence is the damage itself.

        This is what a download that stopped mid-transfer looks like: a valid `PK\\x03\\x04`
        header, real compressed data, and then nothing.
        """
        got = common.declared_length(self.write("a.zip", b"PK\x03\x04" + b"\xff" * 5000))
        self.assertEqual(got, (None, "ZIP"))

    def test_AN_EMPTY_ZIP_IS_A_FINDING_TOO(self):
        """`check_empty` tests `size == 0` and moves on, so nothing else in this collection
        can see a zero-length archive at all."""
        self.assertEqual(common.declared_length(self.write("a.zip", b"")), (None, "ZIP"))

    def test_FOUR_MATCHING_BYTES_ARE_NOT_A_RECORD(self):
        """The accident that would have produced this check's largest finding.

        The four-byte end-of-directory signature is and deflate output is effectively random, so the signature
        turns up inside compressed data. `mpoli-bbs/.../SYNC.ZIP` is 5 697 bytes and contains one
        at offset 4 093 whose fields decode to a central directory at 3 301 229 764 and a
        50 372-byte comment: "6.60 GB missing". Three neighbours gave the identical figure --
        four files claiming exactly the same loss, which is what a parser error looks like and
        damage does not.

        The format provides the check: the comment is the last thing in the file, so
        `position + 22 + comment == size` must hold exactly.
        """
        # A fake record in the middle, whose comment length cannot fit, then more data after it.
        eocd = b"PK" + bytes([5, 6])
        liar = (b"PK" + bytes([3, 4]) + bytes([0x11]) * 100
                + eocd + struct.pack("<HHHH", 0, 0, 0, 0)
                + struct.pack("<II", 0xC4C4C4C4, 0xC4C4C4C4) + struct.pack("<H", 50372)
                + bytes([0x22]) * 500)
        self.assertEqual(common.declared_length(self.write("a.zip", liar)), (None, "ZIP"))

    def test_and_a_real_record_is_still_found_behind_an_accident(self):
        """The search must not stop at the first candidate -- it keeps looking backwards.

        The accident here is a bare signature with nothing behind it; the real record sits after
        it. The answer is the whole file, because the length a record implies is measured from
        where the RECORD is, not from where the archive begins -- so whatever sits in front of it
        is already accounted for.
        """
        real = zip_bytes()
        liar = b"PK" + bytes([3, 4]) + b"PK" + bytes([5, 6]) + bytes([0xFF]) * 40
        blob = liar + real
        self.assertEqual(common.declared_length(self.write("a.zip", blob)), (len(blob), "ZIP"))

    def test_the_whole_zip_family_is_covered(self):
        for name in ("a.jar", "a.apk", "a.docx", "a.odt", "a.epub", "a.xpi"):
            self.assertEqual(common.declared_length(self.write(name, zip_bytes()))[1], "ZIP")

    def test_A_SELF_EXTRACTING_STUB_DOES_NOT_MAKE_IT_LOOK_SHORT(self):
        """An .exe with a zip glued on the end is ordinary and must not become a finding.

        The record is found in the tail regardless of what precedes it, and the length it implies
        is counted from the record -- so the stub is simply part of the file and the arithmetic
        comes out exact. An earlier version measured from the archive's own start instead, which
        made every self-extracting archive read as shorter than it is.
        """
        blob = b"MZ" + bytes(4096) + zip_bytes()
        self.assertEqual(common.declared_length(self.write("a.zip", blob)), (len(blob), "ZIP"))


class ISO(Tmp):

    def test_it_reads_the_primary_volume_descriptor(self):
        blob = iso_bytes(blocks=40, block_size=2048)
        self.assertEqual(common.declared_length(self.write("a.iso", blob)),
                         (40 * 2048, "ISO 9660"))

    def test_a_padded_image_is_longer_than_declared(self):
        blob = iso_bytes(blocks=20, block_size=2048, pad_to=20 * 2048 + 4096)
        expected, _fmt = common.declared_length(self.write("a.iso", blob))
        self.assertLess(expected, len(blob))

    def test_a_descriptor_claiming_zero_says_nothing(self):
        self.assertIsNone(common.declared_length(self.write("a.iso", iso_bytes(blocks=0))))


class TheCheck(Tmp):
    """check_declared over a small tree."""

    def run_check(self):
        out = io.StringIO()
        keep = sys.stdout
        sys.stdout = out
        try:
            found = audit.check_declared(self.tmp)
        finally:
            sys.stdout = keep
        return found, out.getvalue()

    def test_a_clean_tree_reports_nothing(self):
        self.write("ok.zip", zip_bytes())
        self.write("ok.wav", riff())
        found, text = self.run_check()
        self.assertEqual(found, 0)
        self.assertIn("0 files", text)

    def test_a_short_file_is_a_finding(self):
        self.write("cut.wav", riff(b"WAVE" + b"x" * 100)[:60])
        found, text = self.run_check()
        self.assertEqual(found, 1)
        self.assertIn("cut.wav", text)
        self.assertIn("missing", text)

    def test_a_zip_without_its_record_is_a_finding(self):
        self.write("cut.zip", b"PK\x03\x04" + b"\xff" * 5000)
        found, text = self.run_check()
        self.assertEqual(found, 1)
        self.assertIn("record is GONE", text)

    def test_A_LONGER_FILE_IS_COUNTED_AND_NOT_REPORTED(self):
        """The asymmetry, end to end. Padding is ordinary; listing it buries the real findings."""
        self.write("padded.wav", riff(b"WAVE" + b"x" * 8, declared=4))
        found, text = self.run_check()
        self.assertEqual(found, 0)
        self.assertIn("longer than declared", text)
        self.assertNotIn("padded.wav", text.split("longer than declared")[0])

    def test_files_that_say_nothing_are_not_counted_as_asked(self):
        self.write("x.txt", b"hello")
        self.write("one.zip", zip_bytes())
        _found, text = self.run_check()
        self.assertIn("1 file asked", text)


class ItIsWiredIntoTheTool(unittest.TestCase):

    def test_the_flag_exists_and_says_what_it_is_for(self):
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        out = subprocess.run([sys.executable, os.path.join(here, "audit.py"), "--help"],
                             capture_output=True, text=True, cwd=here).stdout
        self.assertIn("--declared", out)

    def test_it_cannot_write_anything(self):
        """The same structural guarantee the other four checks carry."""
        import ast
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "audit.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), "audit.py")
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "check_declared")
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                self.assertNotIn(name, ("remove", "rename", "replace", "makedirs", "rmtree",
                                        "atomic_write", "write_marker", "unlink"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
