#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The commands that need no B2 account, run end to end: python b2verify_test.py

hash-local, verify-local and compare work on files and checksum files only, so a throwaway tree
and a hand-written B2 checksum file are enough to drive them through the real command line --
configuration, selection, exit status and report included.
"""
from __future__ import annotations

import contextlib
import io
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

import b2lib as lib
import b2verify


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = b2verify.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def damage(path: Path) -> None:
    """Flip one byte and put the modification time back: what bit rot looks like."""
    st = path.stat()
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


@contextlib.contextmanager
def silent_server():
    """A local port that completes TCP and then never says a word -- the failure seen on
    2026-10-02, when a data-centre server reached B2 by TCP and no TLS handshake ever finished.
    Nothing accepts: the kernel's listen backlog completes the TCP handshake on its own."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    try:
        yield ("127.0.0.1", srv.getsockname()[1])
    finally:
        srv.close()


def closed_port() -> tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return ("127.0.0.1", port)


class PreflightTest(unittest.TestCase):
    def test_tls_that_never_answers_fails_fast_and_says_so(self):
        with silent_server() as target:
            start = time.monotonic()
            problem = b2verify.preflight(target, timeout=1.0)
            elapsed = time.monotonic() - start
        self.assertIsNotNone(problem)
        self.assertIn("TLS handshake failed", problem)
        self.assertIn("not a problem of the key", problem)
        self.assertLess(elapsed, 5)

    def test_refused_connection_is_reported(self):
        problem = b2verify.preflight(closed_port(), timeout=1.0)
        self.assertIsNotNone(problem)
        self.assertIn("cannot connect", problem)

    def test_a_b2_command_stops_with_a_message_instead_of_hanging(self):
        with tempfile.TemporaryDirectory() as tmp, silent_server() as target:
            config = Path(tmp) / "b2.properties"
            config.write_text("keyId=x\napplicationKey=y\n", encoding="utf-8")
            saved = b2verify.PREFLIGHT_TARGET, b2verify.PREFLIGHT_TIMEOUT
            b2verify.PREFLIGHT_TARGET, b2verify.PREFLIGHT_TIMEOUT = target, 1.0
            try:
                start = time.monotonic()
                # hash-b2 talks to B2 first thing; verify-b2 would stop earlier, at the missing
                # checksum file, and never reach the network.
                code, out = run("hash-b2", "example-bucket", "--config", str(config), "--no-report")
                elapsed = time.monotonic() - start
            finally:
                b2verify.PREFLIGHT_TARGET, b2verify.PREFLIGHT_TIMEOUT = saved
        self.assertEqual(code, 2, out)
        self.assertIn("B2 is not reachable from this machine", out)
        self.assertLess(elapsed, 5)


class CommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bucket = self.tmp / "data" / "example-bucket"
        for rel, size in (("a.bin", 3000), ("sub/b.bin", 500), ("big.bin", 2500)):
            p = self.bucket / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(os.urandom(size))
        self.config = self.tmp / "b2.properties"
        self.config.write_text(f"keyId=x\napplicationKey=y\nlocalRoot={(self.tmp / 'data').as_posix()}\n"
                               f"stateDir={(self.tmp / 'state').as_posix()}\n", encoding="utf-8")
        self.checksums = self.tmp / "state" / "checksums"

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, *argv: str) -> tuple[int, str]:
        return run(*argv, "--config", str(self.config))

    def write_b2_checksums(self, *, broken: str = "") -> None:
        """What hash-b2 would have recorded: SHA-1 for two files, only an ETag for the big one."""
        entries = []
        for rel in ("a.bin", "sub/b.bin"):
            sha1, _ = lib.hash_file(self.bucket / rel)
            entries.append(lib.FileEntry(rel, (self.bucket / rel).stat().st_size, 0,
                                         sha1="0" * 40 if rel == broken else sha1, source="b2"))
        parts = [1000, 1000, 500]
        _, etag = lib.hash_file(self.bucket / "big.bin", parts, True)
        entries.append(lib.FileEntry("big.bin", 2500, 0, etag=etag, parts=parts, source="s3"))
        meta = lib.new_meta("example-bucket", "b2") | {"complete": lib.YES}
        lib.write_snapshot(self.checksums / "b2" / "example-bucket.tsv", meta, entries)

    def test_help_needs_no_configuration_and_no_dependencies(self):
        code, out = run("--help")
        self.assertEqual(code, 0)
        self.assertIn("verify-b2", out)

    def test_missing_configuration_is_refused(self):
        env = os.environ.pop(b2verify.CONFIG_ENV, None)
        try:
            code, out = run("compare")
        finally:
            if env is not None:
                os.environ[b2verify.CONFIG_ENV] = env
        self.assertEqual(code, 2)
        self.assertIn("no configuration", out)

    def test_hash_compare_and_a_detected_difference(self):
        self.write_b2_checksums()
        code, out = self.cmd("hash-local", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn("1 of them with part MD5s", out)  # the ETag file is cut like B2 cut it

        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3  (SHA-1 2, ETag/part MD5 1)", out)

        self.write_b2_checksums(broken="a.bin")
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 1, out)
        self.assertIn("! a.bin", out)

    def test_selection_narrows_compare(self):
        self.write_b2_checksums(broken="a.bin")
        self.cmd("hash-local", "example-bucket", "--no-report")
        code, out = self.cmd("compare", "example-bucket", "--no-report", "--exclude", r"^a\.bin$")
        self.assertEqual(code, 0, out)
        code, out = self.cmd("compare", "example-bucket", "--no-report", "--min-size", "1K", "--max-size", "2K")
        self.assertEqual(code, 0, out)  # sizes 500, 2500 and 3000 bytes - none lies in [1K, 2K)
        self.assertIn("Local 0 files", out)
        code, out = self.cmd("compare", "example-bucket", "--no-report", "--max-size", "1K")
        self.assertEqual(code, 0, out)  # only sub/b.bin, which is intact
        self.assertIn("Local 1 files", out)

    def test_silent_damage_is_found_and_the_good_checksum_is_kept(self):
        self.write_b2_checksums()
        self.cmd("hash-local", "example-bucket", "--no-report")
        saved_before = (self.checksums / "local" / "example-bucket.tsv").read_text(encoding="utf-8")
        damage(self.bucket / "a.bin")

        code, out = self.cmd("hash-local", "example-bucket", "--no-report", "--force")
        self.assertEqual(code, 1, out)
        self.assertIn("DAMAGE?", out)
        saved_after = (self.checksums / "local" / "example-bucket.tsv").read_text(encoding="utf-8")
        sha1_line = [ln for ln in saved_before.splitlines() if ln.endswith("\ta.bin")][0].split("\t")[2]
        self.assertIn(sha1_line, saved_after)  # the damaged bytes did not replace the good checksum

        code, out = self.cmd("verify-local", "example-bucket")
        self.assertEqual(code, 1, out)
        self.assertIn("silent damage?", out)
        self.assertIn("restorable from B2", out)
        report = (self.tmp / "state" / "reports" / "example-bucket.local.md").read_text(encoding="utf-8")
        self.assertIn("| Checksum differs | 1 |", report)

    def test_b2_side_commands_need_no_local_root(self):
        # A machine that holds only the checksum files: no localRoot, no data.
        self.write_b2_checksums()
        self.cmd("hash-local", "example-bucket", "--no-report")
        self.config.write_text(f"keyId=x\napplicationKey=y\nstateDir={(self.tmp / 'state').as_posix()}\n",
                               encoding="utf-8")
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3", out)
        for command in ("verify-b2", "hash-b2"):
            args = b2verify.build_parser().parse_args([command, "--config", str(self.config)])
            ctx = b2verify.Context(args)  # must not refuse the configuration
            self.assertIsNone(ctx.local_root)
            self.assertEqual(ctx.local_dirs(), set())

    def test_configuration_with_a_byte_order_mark(self):
        self.write_b2_checksums()
        self.cmd("hash-local", "example-bucket", "--no-report")
        text = self.config.read_text(encoding="utf-8")
        self.config.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))  # as Notepad / PowerShell write it
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)

    def test_local_commands_refuse_a_missing_local_root(self):
        self.config.write_text("keyId=x\napplicationKey=y\n", encoding="utf-8")
        for command in ("hash-local", "verify-local", "check"):
            code, out = self.cmd(command, "example-bucket", "--no-report")
            self.assertEqual(code, 2, f"{command}: {out}")
            self.assertIn("'localRoot' is missing", out)

    def test_own_state_inside_local_root_is_no_bucket(self):
        data = self.tmp / "data"
        for name in ("my-reports", "state/checksums/local", ".hidden", "scratch"):
            (data / name).mkdir(parents=True, exist_ok=True)
        self.config.write_text(f"keyId=x\napplicationKey=y\nlocalRoot={data.as_posix()}\n"
                               f"stateDir={(data / 'state').as_posix()}\n"
                               f"reportDir={(data / 'my-reports').as_posix()}\nignoreDirs=scratch\n",
                               encoding="utf-8")
        args = b2verify.build_parser().parse_args(["hash-local", "--config", str(self.config)])
        self.assertEqual(b2verify.Context(args).local_dirs(), {"example-bucket"})

        code, out = self.cmd("hash-local", "--no-report")  # no bucket named: every local directory
        self.assertEqual(code, 0, out)
        written = sorted(p.name for p in (data / "state" / "checksums" / "local").glob("*.tsv"))
        self.assertEqual(written, ["example-bucket.tsv"])

    def test_verify_local_skips_what_was_checked_recently(self):
        self.cmd("hash-local", "example-bucket", "--no-report")
        code, out = self.cmd("verify-local", "example-bucket", "--no-report", "--older-than", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("not read (checked recently): 3", out)
        code, out = self.cmd("verify-local", "example-bucket", "--no-report", "--threads", "3")
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3", out)


if __name__ == "__main__":
    unittest.main()
