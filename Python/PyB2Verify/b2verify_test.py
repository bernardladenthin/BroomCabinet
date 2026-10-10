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
import types
import unicodedata
import unittest
import unittest.mock
from pathlib import Path

import b2lib as lib
import b2verify
import fixity


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
        # The first real occurrence was a path-MTU black hole; the message must point there.
        self.assertIn("path-MTU", problem)
        self.assertIn("TLS to B2 never completes", problem)
        self.assertLess(elapsed, 5)

    def test_the_readme_section_the_message_points_to_exists(self):
        readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
        self.assertIn("### TCP connects but TLS to B2 never completes", readme)

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


class FakeBucket:
    """Stands in for a b2sdk bucket: only what unfinished_uploads() asks of it."""

    def __init__(self, names=(), error: Exception | None = None):
        self.names, self.error = list(names), error

    def list_unfinished_large_files(self):
        if self.error:
            raise self.error
        return [types.SimpleNamespace(file_name=n, file_id=f"id{i}") for i, n in enumerate(self.names)]


class UnfinishedUploadsTest(unittest.TestCase):
    def test_interrupted_uploads_are_named_and_classified(self):
        # Seen on 2026-10-04: dropped connections during an upload left four multi-part uploads
        # open. They appear in no listing, yet their parts are stored and billed.
        decomposed = unicodedata.normalize("NFD", "Videos/Überblick.mp4")
        bucket = FakeBucket(["Videos/retried.mp4", decomposed])
        names = b2verify.unfinished_uploads(bucket)
        self.assertEqual(names, ["Videos/retried.mp4", "Videos/Überblick.mp4"])  # sorted, NFC

        lines = b2verify.unfinished_report(names, present={"Videos/retried.mp4"})
        self.assertIn("2 unfinished large-file upload(s)", lines[0])
        self.assertIn("lifecycle rule", lines[0])
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[1].strip().startswith("NOT IN B2: Videos/Überblick.mp4"))
        self.assertTrue(lines[2].strip().startswith("leftover:  Videos/retried.mp4"))

    def test_nothing_to_report(self):
        self.assertEqual(b2verify.unfinished_report(b2verify.unfinished_uploads(FakeBucket()), set()), [])

    def test_a_refused_listing_does_not_stop_the_check(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            names = b2verify.unfinished_uploads(FakeBucket(error=PermissionError("listFiles missing")))
        self.assertIsNone(names)
        self.assertIn("cannot list unfinished uploads", out.getvalue())
        self.assertEqual(b2verify.unfinished_report(names, set()), [])


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
            sha1 = fixity.hash_file(self.bucket / rel)[0]["sha1"]
            entries.append(lib.FileEntry(rel, (self.bucket / rel).stat().st_size, 0,
                                         sha1="0" * 40 if rel == broken else sha1, source="b2"))
        parts = [1000, 1000, 500]
        _, etag = fixity.hash_file(self.bucket / "big.bin", parts, True)
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
        self.assertIn("1 with part MD5s", out)  # the ETag file is cut like B2 cut it

        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3  (etag 1, sha1 2)", out)

        self.write_b2_checksums(broken="a.bin")
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 1, out)
        self.assertIn("! a.bin", out)

    def test_hash_local_writes_s3etag_where_b2_layouts_and_the_default_agree(self):
        # PyFixity's default rule, scaled down so the test files are "large": parts of 1000 bytes
        # above 2000. B2's recorded layout of big.bin (1000, 1000, 500) is exactly that rule.
        self.write_b2_checksums()
        with unittest.mock.patch.object(fixity, "DEFAULT_S3", fixity.S3Layout(1000, 2000)):
            code, out = self.cmd("hash-local", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn(".s3etag: written", out)
        _part, etags = fixity.read_etags(self.bucket / fixity.ETAG_MANIFEST)
        self.assertEqual(sorted(etags), ["a.bin", "big.bin"])
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)  # .s3etag at the bucket root is a manifest, never compared
        self.assertIn("checksum identical: 3", out)

    def test_hash_local_and_verify_local_with_threads(self):
        self.write_b2_checksums()
        with unittest.mock.patch.object(fixity, "PARALLEL_MIN_SIZE", 0):
            code, out = self.cmd("hash-local", "example-bucket", "--no-report", "--threads", "2", "--hash-threads", "5")
            self.assertEqual(code, 0, out)
            code, out = self.cmd("compare", "example-bucket", "--no-report")
            self.assertEqual(code, 0, out)
            self.assertIn("checksum identical: 3  (etag 1, sha1 2)", out)
            code, out = self.cmd("verify-local", "example-bucket", "--no-report", "--threads", "2", "--hash-threads", "3")
            self.assertEqual(code, 0, out)

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
        index = self.checksums / "local" / "example-bucket.csv"
        good = {e.path: e.sha256 for e in fixity.read_index(index)}
        damage(self.bucket / "a.bin")

        code, out = self.cmd("hash-local", "example-bucket", "--no-report", "--force")
        self.assertEqual(code, 1, out)
        self.assertIn("DAMAGE?", out)
        # the damaged bytes did not replace the good checksum, neither in the index nor in the manifest
        self.assertEqual({e.path: e.sha256 for e in fixity.read_index(index)}, good)
        self.assertEqual(fixity.read_sums(self.bucket / ".sha256sum")["a.bin"], good["a.bin"])

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
        written = sorted(p.name for p in (data / "state" / "checksums" / "local").glob("*.csv"))
        self.assertEqual(written, ["example-bucket.csv"])

    def test_manifests_are_written_into_the_bucket_and_never_compared(self):
        self.write_b2_checksums()
        code, out = self.cmd("hash-local", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        for name in (".sha256sum", ".sha1sum", ".md5sum", ".sfv"):
            self.assertTrue((self.bucket / name).is_file(), name)
        self.assertEqual(set(fixity.read_sums(self.bucket / ".md5sum")), {"a.bin", "sub/b.bin", "big.bin"})
        # Uploaded with the data, the manifests show up in B2 too -- and are left out on both sides.
        meta, entries = lib.read_snapshot(self.checksums / "b2" / "example-bucket.tsv")
        entries.append(lib.FileEntry(".sha1sum", 99, 0, sha1="f" * 40, source="b2"))
        lib.write_snapshot(self.checksums / "b2" / "example-bucket.tsv", meta, entries)
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn("Local 3 files, B2 3 files", out)

    def test_a_first_version_checksum_file_is_moved_onto_the_index(self):
        self.write_b2_checksums()
        old = []
        for rel in ("a.bin", "sub/b.bin", "big.bin"):
            st = (self.bucket / rel).stat()
            old.append(lib.FileEntry(rel, st.st_size, st.st_mtime_ns // 1_000_000,
                                     fixity.hash_file(self.bucket / rel)[0]["sha1"], source="local"))
        lib.write_snapshot(self.checksums / "local" / "example-bucket.tsv", {"created": "x"}, old)
        code, out = self.cmd("hash-local", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertIn("3 entries adopted", out)
        self.assertTrue((self.checksums / "local" / "example-bucket.tsv.migrated").is_file())
        self.assertTrue(all(e.has_all_digests() for e in fixity.read_index(self.checksums / "local" / "example-bucket.csv")))
        self.assertEqual(self.cmd("compare", "example-bucket", "--no-report")[0], 0)

    def test_compare_hints_at_a_stale_b2_record(self):
        # Seen on 2026-10-04: files uploaded after the last hash-b2 were reported missing in B2.
        self.write_b2_checksums()
        meta, entries = lib.read_snapshot(self.checksums / "b2" / "example-bucket.tsv")
        meta["created"] = "2020-01-01 00:00:00"  # the B2 record is old ...
        lib.write_snapshot(self.checksums / "b2" / "example-bucket.tsv", meta, entries)
        (self.bucket / "new-upload.bin").write_bytes(b"uploaded after the last hash-b2")  # ... this file is new
        self.cmd("hash-local", "example-bucket", "--no-report")
        code, out = self.cmd("compare", "example-bucket")
        self.assertEqual(code, 1, out)
        self.assertIn("+ new-upload.bin", out)
        self.assertIn("1 differing local file(s) are newer", out)
        self.assertIn("Run hash-b2", out)
        report = (self.tmp / "state" / "reports" / "example-bucket.md").read_text(encoding="utf-8")
        self.assertIn("**Hint:**", report)

    def test_no_stale_hint_when_the_b2_record_is_current(self):
        self.cmd("hash-local", "example-bucket", "--no-report")
        self.write_b2_checksums()  # written now, after every local file
        code, out = self.cmd("compare", "example-bucket", "--no-report")
        self.assertEqual(code, 0, out)
        self.assertNotIn("hint:", out)

    def test_verify_local_skips_what_was_checked_recently(self):
        self.cmd("hash-local", "example-bucket", "--no-report")
        code, out = self.cmd("verify-local", "example-bucket", "--no-report", "--older-than", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("not read (checked recently): 3", out)
        code, out = self.cmd("verify-local", "example-bucket", "--no-report", "--threads", "3")
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3", out)


class FakeVaultBucket:
    """Stands in for a b2sdk bucket holding a vault: listing, downloads, unfinished uploads."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def ls(self, prefix="", latest_only=True, recursive=False):
        for i, (name, data) in enumerate(sorted(self.objects.items())):
            if name.startswith(prefix):
                yield types.SimpleNamespace(file_name=name, size=len(data), id_=name, action="upload"), None

    def download_file_by_id(self, file_id):
        data = self.objects[file_id]
        response = types.SimpleNamespace(
            iter_content=lambda n: (data[i:i + n] for i in range(0, len(data), n)), close=lambda: None)
        return types.SimpleNamespace(response=response)

    def list_unfinished_large_files(self):
        return []


class VaultCommandTest(unittest.TestCase):
    """The vault command end to end, against a vault written by VaultBuilder and served by a fake
    bucket: the local cleartext tree, its index, the configuration -- all real."""

    PASSPHRASE = "correct horse battery"

    def setUp(self):
        from cryptomator_test import VaultBuilder
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.clear = self.tmp / "data" / "example-vault-bucket" / "films"
        self.vault = VaultBuilder(self.PASSPHRASE)
        for rel, data in (("Film One/film.mkv", os.urandom(100_000)), ("Film One/film.nfo", b"info"),
                          ("Short.mp4", os.urandom(40_000))):
            p = self.clear / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            self.vault.add_file(rel, data)
        # The passphrase lies beside the cleartext directory, not in it: never indexed, never uploaded.
        (self.clear.parent / "films.key").write_text(self.PASSPHRASE + "\n", encoding="utf-8")
        self.config = self.tmp / "b2.properties"
        self.config.write_text(f"keyId=x\napplicationKey=y\nlocalRoot={(self.tmp / 'data').as_posix()}\n"
                               f"stateDir={(self.tmp / 'state').as_posix()}\n"
                               f"vaults=example-vault-bucket/films\n", encoding="utf-8")
        self.bucket = FakeVaultBucket({})
        self.upload()
        api = types.SimpleNamespace(get_bucket_by_name=lambda name: self.bucket)
        self._patches = [unittest.mock.patch.object(b2verify.Context, "api", property(lambda ctx: api)),
                         unittest.mock.patch.object(b2verify.Context, "thread_bucket", lambda ctx, name: self.bucket)]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def upload(self) -> None:
        """What the client has in B2: the builder's objects below the vault directory."""
        self.bucket.objects = {f"films/{n}": b for n, b in self.vault.objects.items()}

    def cmd(self, *argv: str) -> tuple[int, str]:
        return run(*argv, "--config", str(self.config), "--no-report")

    def test_hash_local_indexes_the_cleartext_and_the_vault_matches(self):
        code, out = self.cmd("hash-local", "example-vault-bucket")
        self.assertEqual(code, 0, out)
        self.assertNotIn(".s3etag", out)  # B2 sees only ciphertext: a cleartext ETag means nothing
        index = self.tmp / "state" / "checksums" / "local" / "example-vault-bucket-films.csv"
        self.assertEqual(sorted(e.path for e in fixity.read_index(index)),
                         ["Film One/film.mkv", "Film One/film.nfo", "Short.mp4"])  # no passphrase file
        self.assertTrue((self.clear / ".sha256sum").is_file())

        code, out = self.cmd("vault")
        self.assertEqual(code, 0, out)
        self.assertIn("keys and signature verified; 3 files in 1 directories", out)
        self.assertIn("in sync", out)
        self.assertIn("every vault is consistent and matches", out)

        code, out = self.cmd("vault", "--download", "--threads", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("checksum identical: 3  (sha256 3)", out)

    def test_a_flipped_bit_in_b2_is_found_only_by_decrypting(self):
        self.cmd("hash-local", "example-vault-bucket")
        obj = next(n for n in self.bucket.objects if n.endswith(".c9r") and len(self.bucket.objects[n]) > 90_000)
        data = bytearray(self.bucket.objects[obj])
        data[50_000] ^= 0x10
        self.bucket.objects[obj] = bytes(data)
        code, out = self.cmd("vault")
        self.assertEqual(code, 0, out)  # names and sizes cannot see it
        code, out = self.cmd("vault", "--download")
        self.assertEqual(code, 1, out)
        self.assertIn("DAMAGED", out)
        self.assertIn("does not authenticate", out)

    def test_an_interrupted_upload_leaves_a_pointer_into_nothing(self):
        # Seen on 2026-10-09: the client stalled between the pointer and the directory.
        self.vault.add_dir("Film Two/Extras")
        target = self.vault.dir_path(self.vault.ids["Film Two/Extras"])
        for n in [n for n in self.vault.objects if n.startswith(target + "/")]:
            del self.vault.objects[n]
        self.upload()
        self.cmd("hash-local", "example-vault-bucket")
        code, out = self.cmd("vault")
        self.assertEqual(code, 1, out)
        self.assertIn("PROBLEM: directory 'Film Two/Extras': points to", out)

    def test_a_file_not_yet_uploaded_and_a_wrong_size(self):
        self.cmd("hash-local", "example-vault-bucket")
        (self.clear / "Later.mkv").write_bytes(b"not uploaded yet")
        (self.clear / "Short.mp4").write_bytes(os.urandom(40_001))
        self.cmd("hash-local", "example-vault-bucket")
        code, out = self.cmd("vault")
        self.assertEqual(code, 1, out)
        self.assertIn("+ Later.mkv", out)
        self.assertIn("Short.mp4", out)

    def test_a_wrong_passphrase_is_reported(self):
        (self.clear.parent / "films.key").write_text("not the passphrase", encoding="utf-8")
        code, out = self.cmd("vault")
        self.assertEqual(code, 1, out)
        self.assertIn("wrong passphrase", out)

    def test_ciphertext_buckets_are_skipped_by_check_and_compare(self):
        for command in ("check", "compare"):
            code, out = self.cmd(command, "example-vault-bucket")
            self.assertEqual(code, 0, out)
            self.assertIn("a Cryptomator vault - B2 holds ciphertext", out)

    def test_verify_local_reads_the_cleartext_directory(self):
        self.cmd("hash-local", "example-vault-bucket")
        code, out = self.cmd("verify-local")
        self.assertEqual(code, 0, out)
        self.assertIn("verifying example-vault-bucket/films locally", out)
        self.assertIn("checksum identical: 3", out)
        damage(self.clear / "Short.mp4")
        code, out = self.cmd("verify-local", "example-vault-bucket")
        self.assertEqual(code, 1, out)
        self.assertIn("! Short.mp4", out)

    def test_a_malformed_vault_entry_in_the_configuration_is_refused(self):
        self.config.write_text(self.config.read_text(encoding="utf-8").replace(
            "vaults=example-vault-bucket/films", "vaults=example-vault-bucket"), encoding="utf-8")
        code, out = self.cmd("vault")
        self.assertEqual(code, 2, out)
        self.assertIn("is not <bucket>/<directory>", out)


if __name__ == "__main__":
    unittest.main()
