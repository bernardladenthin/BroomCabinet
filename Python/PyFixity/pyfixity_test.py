#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The command line, end to end, on throwaway trees: python pyfixity_test.py"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import fixity
import pyfixity


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = pyfixity.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def damage(path: Path) -> None:
    st = path.stat()
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.tree, self.index = base / "tree", base / "state" / "tree.csv"
        self.files = {"a.bin": os.urandom(3000), "sub dir/b.bin": os.urandom(500), "big.bin": os.urandom(2500)}
        for rel, data in self.files.items():
            p = self.tree / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, command: str, *extra: str) -> tuple[int, str]:
        return run(command, str(self.tree), "--index", str(self.index), *extra)

    def test_help_needs_nothing(self):
        code, out = run("--help")
        self.assertEqual(code, 0)
        self.assertIn("manifests", out)

    def test_index_writes_manifests_a_standard_tool_can_check(self):
        code, out = self.cmd("index")
        self.assertEqual(code, 0, out)
        # What `sha256sum -c` would do: every line's digest equals the file's.
        lines = (self.tree / ".sha256sum").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            digest, rel = line.split(" *", 1)
            self.assertEqual(hashlib.sha256((self.tree / rel).read_bytes()).hexdigest(), digest)
        for name in (".sha1sum", ".md5sum", ".sfv"):
            self.assertTrue((self.tree / name).is_file(), name)

    def test_by_default_the_folder_keeps_its_own_record_and_never_lists_it(self):
        code, out = run("index", str(self.tree))
        self.assertEqual(code, 0, out)
        self.assertTrue((self.tree / fixity.STATE_FILE).is_file())
        self.assertFalse((self.tree / fixity.DEFAULT_INDEX).exists())
        listed = set(fixity.read_sums(self.tree / ".md5sum"))
        self.assertEqual(listed, set(self.files))
        code, out = run("verify", str(self.tree))
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3", out)

    def test_verify_finds_silent_damage(self):
        self.cmd("index")
        self.assertEqual(self.cmd("verify")[0], 0)
        damage(self.tree / "a.bin")
        code, out = self.cmd("verify")
        self.assertEqual(code, 1, out)
        self.assertIn("! a.bin", out)

    def test_force_keeps_good_checksums_and_says_so(self):
        self.cmd("index")
        before = (self.tree / ".sha256sum").read_text(encoding="utf-8")
        damage(self.tree / "a.bin")
        code, out = self.cmd("index", "--force")
        self.assertEqual(code, 1, out)
        self.assertIn("possible silent damage", out)
        self.assertEqual((self.tree / ".sha256sum").read_text(encoding="utf-8"), before)

    def test_parts_file_adds_the_etag(self):
        layouts = self.tree.parent / "parts.csv"
        layouts.write_text("path,parts,etag\nbig.bin,\"1000*2,500\",x-3\n", encoding="utf-8")
        code, out = self.cmd("index", "--parts", str(layouts))
        self.assertEqual(code, 0, out)
        big = {e.path: e for e in fixity.read_index(self.index)}["big.bin"]
        self.assertTrue(big.etag and big.etag.endswith("-3"))
        self.assertEqual(big.parts, [1000, 1000, 500])

    def test_s3etag_by_default_with_the_options_and_switched_off(self):
        code, out = self.cmd("index")  # real defaults: no test file is above 200 MiB
        self.assertEqual(code, 0, out)
        self.assertIn(".s3etag: not needed (no file larger than 209715200 bytes)", out)
        # The same rule scaled down: parts of 1000 bytes above 2000 -> only big.bin and a.bin.
        code, out = self.cmd("index", "--s3-part-size", "1000", "--s3-cutoff", "2000")
        self.assertEqual(code, 0, out)
        self.assertIn(".s3etag: written", out)
        part_size, etags = fixity.read_etags(self.tree / fixity.ETAG_MANIFEST)
        self.assertEqual((part_size, sorted(etags)), (1000, ["a.bin", "big.bin"]))
        self.assertTrue(etags["big.bin"].endswith("-3"))
        (self.tree / fixity.ETAG_MANIFEST).unlink()
        code, out = self.cmd("manifests", "--s3-part-size", "1000", "--s3-cutoff", "2000")
        self.assertIn(".s3etag: written", out)  # rebuilt from the index, reading nothing
        code, out = self.cmd("index", "--s3-part-size", "0")
        self.assertNotIn(".s3etag", out)

    def test_threads_change_the_speed_and_nothing_else(self):
        code, out = self.cmd("index", "--threads", "1", "--hash-threads", "1")
        self.assertEqual(code, 0, out)
        one = {e.path: (e.digests(), e.etag) for e in fixity.read_index(self.index)}
        manifest = (self.tree / ".sha256sum").read_text(encoding="utf-8")
        self.index.unlink()
        with unittest.mock.patch.object(fixity, "PARALLEL_MIN_SIZE", 0):  # tiny files through the threads too
            code, out = self.cmd("index", "--threads", "3", "--hash-threads", "5")
        self.assertEqual(code, 0, out)
        self.assertEqual({e.path: (e.digests(), e.etag) for e in fixity.read_index(self.index)}, one)
        self.assertIn(".sha256sum: unchanged", out)
        self.assertEqual((self.tree / ".sha256sum").read_text(encoding="utf-8"), manifest)
        code, out = self.cmd("verify", "--threads", "2", "--hash-threads", "4")
        self.assertEqual(code, 0, out)

    def test_manifests_from_the_index(self):
        self.cmd("index")
        (self.tree / ".md5sum").unlink()
        code, out = self.cmd("manifests")
        self.assertEqual(code, 0, out)
        self.assertIn(".md5sum: written", out)
        self.assertIn(".sha256sum: unchanged", out)

    def test_selection_and_not_a_directory(self):
        self.cmd("index")
        code, out = self.cmd("verify", "--max-size", "1K")
        self.assertEqual(code, 0, out)
        self.assertIn("Current 1 files", out)
        self.assertEqual(run("verify", str(self.tree / "missing"))[0], 2)


if __name__ == "__main__":
    unittest.main()
