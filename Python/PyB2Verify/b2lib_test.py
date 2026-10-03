#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for b2lib, the B2 side. The local side is PyFixity's and tested there. python b2lib_test.py"""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import b2lib as lib
import fixity
from b2lib import FileEntry as F


class SnapshotTest(unittest.TestCase):
    def test_roundtrip(self):
        entries = [F("a/b c.txt", 3, 1000, "s" * 40, None, None, "b2", "4_z1", "2026-10-01 10:00:00"),
                   F("Tab\tand \"quote\".bin", 2500, 2000, None, "e" * 32 + "-3", [1000, 1000, 500],
                     "s3", "4_z123", "")]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.tsv"
            lib.write_snapshot(p, {"bucket": "b", "side": "b2", "complete": "yes"}, entries)
            meta, back = lib.read_snapshot(p)
        self.assertEqual(meta, {"bucket": "b", "side": "b2", "complete": "yes"})
        self.assertEqual(back, entries)

    def test_translates_legacy_german_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "legacy.tsv"
            p.write_text("# bucket: b\n# seite: b2\n# erzeugt: 2026-10-01 12:00:00\n# vollstaendig: ja\n"
                         "# verify_vollstaendig: nein (abgebrochen/Zwischenstand)\n"
                         + "\t".join(lib.SNAPSHOT_COLUMNS) + "\n", encoding="utf-8")
            meta, _ = lib.read_snapshot(p)
        self.assertEqual(meta, {"bucket": "b", "side": "b2", "created": "2026-10-01 12:00:00",
                                "complete": lib.YES, "verify_complete": lib.INCOMPLETE})

    def test_b2_entries_compare_with_pyfixity(self):
        # PyFixity's comparison works in nanoseconds and by the strongest common digest.
        local = [fixity.Entry("a", 1, 5_000_000, sha256="x", sha1="s"), fixity.Entry("b", 10, 0, etag="e-2", parts=[5, 5])]
        remote = [F("a", 1, 5, "s"), F("b", 10, 0, None, "e-2", [5, 5])]
        d = fixity.compare(local, remote, check_mtime=True, check_sum=True, mtime_tolerance_ns=0)
        self.assertEqual(d.ok, {"sha1": 1, "etag": 1})
        self.assertFalse(d.has_differences())

    def test_root_manifests(self):
        self.assertTrue(lib.is_root_manifest(".sha256sum"))
        self.assertFalse(lib.is_root_manifest("sub/.sha256sum"))  # only the tree's own


class MigrationTest(unittest.TestCase):
    def test_first_version_tsv_moves_onto_the_index_without_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "bucket", Path(tmp) / "state"
            root.mkdir()
            (root / "same.bin").write_bytes(b"same")
            (root / "changed.bin").write_bytes(b"changed")
            st_same, st_changed = (root / "same.bin").stat(), (root / "changed.bin").stat()
            old = [F("same.bin", 4, st_same.st_mtime_ns // 1_000_000, hashlib.sha1(b"same").hexdigest(),
                     source="local", verified="2026-10-01 12:00:00"),
                   F("changed.bin", 7, st_changed.st_mtime_ns // 1_000_000 - 5000, "old", source="local"),
                   F("gone.bin", 1, 0, "x", source="local")]
            tsv, index = state / "bucket.tsv", state / "bucket.csv"
            lib.write_snapshot(tsv, {"bucket": "bucket", "side": "local", "created": "c"}, old)

            adopted, dropped = lib.migrate_local_tsv(tsv, index, root, [])
            self.assertEqual((adopted, dropped), (1, 2))
            entries = {e.path: e for e in fixity.read_index(index)}
            self.assertEqual(list(entries), ["same.bin"])
            self.assertEqual(entries["same.bin"].sha1, hashlib.sha1(b"same").hexdigest())
            self.assertEqual(entries["same.bin"].mtime_ns, st_same.st_mtime_ns)
            self.assertEqual(entries["same.bin"].verified, "2026-10-01 12:00:00")
            self.assertFalse(tsv.exists())
            self.assertTrue((state / "bucket.tsv.migrated").exists())
            self.assertNotEqual(fixity.read_state(index).get("complete"), lib.YES)

            # The next update reads the adopted file once to add the missing digests.
            r = fixity.update_index(root, index, out=lambda _line: None)
            self.assertEqual(sorted(e.path for e in r.hashed), ["changed.bin", "same.bin"])
            self.assertTrue(r.complete)
            self.assertEqual(r.damaged, [])

    def test_damage_since_the_first_version_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "bucket", Path(tmp) / "state"
            root.mkdir()
            p = root / "a.bin"
            p.write_bytes(b"now different bytes")
            st = p.stat()
            lib.write_snapshot(state / "bucket.tsv", {}, [F("a.bin", st.st_size, st.st_mtime_ns // 1_000_000,
                                                             "0" * 40, source="local")])
            lib.migrate_local_tsv(state / "bucket.tsv", state / "bucket.csv", root, [])
            r = fixity.update_index(root, state / "bucket.csv", out=lambda _line: None)
            self.assertEqual([e.path for e, _ in r.damaged], ["a.bin"])
            self.assertEqual(fixity.read_index(state / "bucket.csv")[0].sha1, "0" * 40)  # kept, not replaced


class ExpectedFromMetadataTest(unittest.TestCase):
    def test_s3_source_compares_by_etag_even_with_a_known_sha1(self):
        p = F("x", 10, 0, "learned-sha1", "e-2", [5, 5], source="s3")
        exp = lib.expected_from_metadata(p)
        self.assertIsNone(exp.sha1)
        self.assertEqual(p.sha1, "learned-sha1")
        self.assertTrue(fixity.checksums_match(F("x", 10, 0, "other", "e-2", [5, 5]), exp)[0])
        self.assertFalse(fixity.checksums_match(F("x", 10, 0, "learned-sha1", "f-2", [5, 5]), exp)[0])

    def test_b2_and_download_sources_compare_by_sha1(self):
        for source in ("b2", "download"):
            exp = lib.expected_from_metadata(F("x", 3, 0, "abc", source=source))
            self.assertTrue(fixity.checksums_match(F("x", 3, 0, "abc"), exp)[0])
            self.assertFalse(fixity.checksums_match(F("x", 3, 0, "abd"), exp)[0])

    def test_truncated_content_never_matches(self):
        exp = lib.expected_from_metadata(F("x", 10, 0, "abc", source="b2"))
        self.assertFalse(fixity.checksums_match(F("x", 9, 0, "abc"), exp)[0])


class StateTest(unittest.TestCase):
    def test_b2_state(self):
        saved, now = fixity.Entry("a", 10, 0, sha1="good"), fixity.Entry("a", 10, 0, sha1="bad")
        self.assertIn("restorable", lib.b2_state(now, saved, [F("a", 10, 0, "good")]))
        self.assertIn("same content", lib.b2_state(now, saved, [F("a", 10, 0, "bad")]))
        self.assertIn("differs from both", lib.b2_state(now, saved, [F("a", 10, 0, "other")]))
        self.assertIn("not in B2", lib.b2_state(now, saved, []))
        self.assertIn("no B2", lib.b2_state(now, saved, None))

    def test_local_state(self):
        content = F("a", 10, 0, "x")
        self.assertIn("identical", lib.local_state(content, [fixity.Entry("a", 10, 0, sha1="x")]))
        self.assertIn("differs", lib.local_state(content, [fixity.Entry("a", 10, 0, sha1="y")]))
        self.assertIn("not present", lib.local_state(content, []))


class UnfinishedUploadsTest(unittest.TestCase):
    def test_leftover_versus_missing(self):
        leftovers, missing = lib.classify_unfinished(["b/r.mp4", "a/n.mp4", "b/r.mp4"], {"b/r.mp4", "c"})
        self.assertEqual((leftovers, missing), (["b/r.mp4"], ["a/n.mp4"]))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    unittest.main()
