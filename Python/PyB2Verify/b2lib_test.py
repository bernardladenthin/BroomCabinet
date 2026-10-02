#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for b2lib. Standard library only, no network: python b2lib_test.py"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path

import b2lib as lib
from b2lib import FileEntry as F


def s3_etag(data: bytes, part_size: int) -> str:
    """Reference S3 multipart ETag, written independently of StreamHasher."""
    chunks = [data[i:i + part_size] for i in range(0, len(data), part_size)]
    return hashlib.md5(b"".join(hashlib.md5(c).digest() for c in chunks)).hexdigest() + f"-{len(chunks)}"


def chunked(data: bytes, sizes: list[int]):
    """Yield data in pieces of changing size, so chunk boundaries fall anywhere."""
    i, k = 0, 0
    while i < len(data):
        n = sizes[k % len(sizes)]
        yield data[i:i + n]
        i, k = i + n, k + 1


def paths(entries) -> list[str]:
    return [e.path for e in entries]


def left_paths(pairs) -> list[str]:
    return [pair[0].path for pair in pairs]


class ParseSizeTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(lib.parse_size("500"), 500)
        self.assertEqual(lib.parse_size("64K"), 64 * 1024)
        self.assertEqual(lib.parse_size("1M"), 1024 ** 2)
        self.assertEqual(lib.parse_size("1mb"), 1024 ** 2)
        self.assertEqual(lib.parse_size("1MiB"), 1024 ** 2)
        self.assertEqual(lib.parse_size("1.5G"), int(1.5 * 1024 ** 3))
        self.assertEqual(lib.parse_size(" 2 T "), 2 * 1024 ** 4)

    def test_invalid(self):
        for text in ("", "abc", "1X", "-1M", "1,5G"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                lib.parse_size(text)


class FileFilterTest(unittest.TestCase):
    FILES = [F("Recordings/a.mp4", 5_000_000, 0), F("Recordings/notes.txt", 100, 0),
             F("Series/Example/S01.MP4", 900_000_000, 0), F("readme.txt", 1_048_576, 0),
             F("Shortcuts/x.lnk", 1_048_575, 0)]

    def select(self, flt: lib.FileFilter) -> list[str]:
        return paths(flt.apply(self.FILES))

    def test_no_filter_selects_all(self):
        flt = lib.FileFilter()
        self.assertFalse(flt.active())
        self.assertEqual(len(flt.apply(self.FILES)), len(self.FILES))

    def test_size_split_is_complete_and_disjoint(self):
        small = set(self.select(lib.FileFilter(max_size=lib.parse_size("1M"))))
        large = set(self.select(lib.FileFilter(min_size=lib.parse_size("1M"))))
        self.assertEqual(small | large, set(paths(self.FILES)))
        self.assertEqual(small & large, set())
        self.assertIn("readme.txt", large)  # exactly 1 MiB -> min_size is inclusive
        self.assertIn("Shortcuts/x.lnk", small)  # one byte less

    def test_extension_ignores_case(self):
        self.assertEqual(self.select(lib.FileFilter(include=[r"\.mp4$"])),
                         ["Recordings/a.mp4", "Series/Example/S01.MP4"])

    def test_folder_include_and_exclude(self):
        self.assertEqual(self.select(lib.FileFilter(include=[r"^Recordings/"])),
                         ["Recordings/a.mp4", "Recordings/notes.txt"])
        self.assertNotIn("Shortcuts/x.lnk", self.select(lib.FileFilter(exclude=[r"^Shortcuts/"])))

    def test_includes_are_or_and_exclude_wins(self):
        flt = lib.FileFilter(include=[r"\.txt$", r"\.lnk$"], exclude=[r"^readme"])
        self.assertEqual(self.select(flt), ["Recordings/notes.txt", "Shortcuts/x.lnk"])

    def test_file_name_only(self):
        self.assertEqual(self.select(lib.FileFilter(include=[r"(^|/)notes\.txt$"])), ["Recordings/notes.txt"])

    def test_path_and_size_combined(self):
        flt = lib.FileFilter(include=[r"\.mp4$"], max_size=lib.parse_size("100M"))
        self.assertEqual(self.select(flt), ["Recordings/a.mp4"])

    def test_a_glob_is_not_a_regex(self):
        with self.assertRaises(re.error):
            lib.FileFilter(include=["*.mp4"])


class PartsTest(unittest.TestCase):
    def test_roundtrip(self):
        for parts in ([100, 100, 43], [5], [7, 7, 7], [1, 2, 3], None):
            with self.subTest(parts=parts):
                self.assertEqual(lib.decode_parts(lib.encode_parts(parts)), parts)
        self.assertEqual(lib.encode_parts([100, 100, 43]), "100*2,43")


class StreamHasherTest(unittest.TestCase):
    DATA = os.urandom(10_000) + b"\x00" * 1234

    def test_sha1_only(self):
        sha1, etag, size = lib.hash_chunks(chunked(self.DATA, [999]))
        self.assertEqual(sha1, hashlib.sha1(self.DATA).hexdigest())
        self.assertIsNone(etag)
        self.assertEqual(size, len(self.DATA))

    def test_multipart_etag_matches_the_s3_reference(self):
        part = 4096
        parts = [part] * (len(self.DATA) // part) + [len(self.DATA) % part]
        for sizes in ([1], [7, 13], [4096], [5000], [len(self.DATA)]):
            with self.subTest(chunk_sizes=sizes):
                sha1, etag, _ = lib.hash_chunks(chunked(self.DATA, sizes), parts, multipart=True)
                self.assertEqual(sha1, hashlib.sha1(self.DATA).hexdigest())
                self.assertEqual(etag, s3_etag(self.DATA, part))

    def test_single_part_etag_is_a_plain_md5(self):
        _, etag, _ = lib.hash_chunks(chunked(self.DATA, [333]), [len(self.DATA)], multipart=False)
        self.assertEqual(etag, hashlib.md5(self.DATA).hexdigest())

    def test_size_mismatch_gives_no_etag(self):
        self.assertIsNone(lib.hash_chunks([self.DATA], [len(self.DATA) - 10], True)[1])
        self.assertIsNone(lib.hash_chunks([self.DATA], [len(self.DATA) + 10], True)[1])

    def test_stop_cancels_and_closes_the_stream(self):
        stop = threading.Event()
        closed = []

        def stream():
            try:
                yield b"a"
                stop.set()
                yield b"b"
                yield b"c"
            finally:
                closed.append(True)

        with self.assertRaises(lib.Cancelled):
            lib.hash_chunks(stream(), stop=stop)
        self.assertEqual(closed, [True])

    def test_hash_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.bin"
            p.write_bytes(self.DATA)
            sha1, etag = lib.hash_file(p, [8000, len(self.DATA) - 8000], True)
            self.assertEqual(sha1, hashlib.sha1(self.DATA).hexdigest())
            self.assertEqual(etag, s3_etag(self.DATA, 8000))


class LongPathTest(unittest.TestCase):
    @staticmethod
    def lp(p: str) -> str:
        return lib.long_path(p, windows=True)

    def test_prefix_rules(self):
        self.assertEqual(self.lp(r"D:\data\x.bin"), "\\\\?\\D:\\data\\x.bin")
        self.assertEqual(self.lp("D:/data/sub/../x.bin"), "\\\\?\\D:\\data\\x.bin")
        self.assertEqual(self.lp(r"\\server\share\x.bin"), "\\\\?\\UNC\\server\\share\\x.bin")
        once = self.lp(r"D:\data\x.bin")
        self.assertEqual(self.lp(once), once)  # applying it twice changes nothing

    def test_unchanged_outside_windows(self):
        self.assertEqual(lib.long_path("/srv/data/x.bin", windows=False), "/srv/data/x.bin")

    def test_scan_and_hash_beyond_260_characters(self):
        data = b"deeply nested"
        with tempfile.TemporaryDirectory() as tmp:
            parts = ["a-directory-with-a-long-name-%02d" % i for i in range(10)]
            rel = "/".join(parts) + "/file-at-the-end.bin"
            deep = os.path.join(tmp, *parts)
            os.makedirs(lib.long_path(deep))
            with open(lib.long_path(os.path.join(deep, "file-at-the-end.bin")), "wb") as f:
                f.write(data)
            self.assertGreater(len(os.path.join(tmp, *rel.split("/"))), 300)

            entries = lib.scan_local(Path(tmp), excludes=[])
            self.assertEqual(paths(entries), [rel])
            self.assertEqual(entries[0].size, len(data))
            self.assertEqual(lib.hash_file(entries[0].abs_path)[0], hashlib.sha1(data).hexdigest())
            if os.name == "nt":
                # Clean up through the long path too, so this passes without LongPathsEnabled.
                os.remove(lib.long_path(os.path.join(deep, "file-at-the-end.bin")))
                for i in range(len(parts), 0, -1):
                    os.rmdir(lib.long_path(os.path.join(tmp, *parts[:i])))

    def test_scan_respects_permanent_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.txt", "Thumbs.db", "sub/x.lnk", "sub/b.txt"):
                p = Path(tmp, *name.split("/"))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"x")
            entries = lib.scan_local(Path(tmp), excludes=["Thumbs.db", "*.lnk"])
            self.assertEqual(paths(entries), ["a.txt", "sub/b.txt"])


class SnapshotTest(unittest.TestCase):
    def test_roundtrip(self):
        entries = [F("a/b c.txt", 3, 1000, "s" * 40, None, None, "local", "", "2026-10-01 10:00:00"),
                   F("Tab\tand \"quote\".bin", 2500, 2000, None, "e" * 32 + "-3", [1000, 1000, 500],
                     "s3", "4_z123", "")]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.tsv"
            lib.write_snapshot(p, {"bucket": "b", "side": "local", "complete": "yes"}, entries)
            meta, back = lib.read_snapshot(p)
        self.assertEqual(meta, {"bucket": "b", "side": "local", "complete": "yes"})
        self.assertEqual(back, entries)

    def test_reads_the_oldest_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "old.tsv"
            p.write_text("# bucket: b\nsize\tmtime_ms\tsha1\tsource\tfile_id\tpath\n"
                         "5\t1\tabc\tlocal\t\tx.txt\n", encoding="utf-8")
            _meta, back = lib.read_snapshot(p)
        self.assertEqual(back, [F("x.txt", 5, 1, "abc", None, None, "local", "", "")])

    def test_translates_legacy_german_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "legacy.tsv"
            p.write_text("# bucket: b\n# seite: local\n# erzeugt: 2026-10-01 12:00:00\n"
                         "# vollstaendig: ja\n# verify_start: 2026-10-02 11:00:00\n"
                         "# verify_vollstaendig: nein (abgebrochen/Zwischenstand)\n"
                         + "\t".join(lib.SNAPSHOT_COLUMNS) + "\n", encoding="utf-8")
            meta, _ = lib.read_snapshot(p)
        self.assertEqual(meta, {"bucket": "b", "side": "local", "created": "2026-10-01 12:00:00",
                                "complete": lib.YES, "verify_start": "2026-10-02 11:00:00",
                                "verify_complete": lib.INCOMPLETE})

    def test_saver_writes_kept_entries_and_the_complete_flag(self):
        entries = [F("a", 1, 0, "x"), F("b", 1, 0)]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.tsv"
            lib.SnapshotSaver(p, {"bucket": "b"}, entries, keep=lambda e: e.sha1).save(complete=False)
            meta, back = lib.read_snapshot(p)
        self.assertEqual(meta["complete"], lib.INCOMPLETE)
        self.assertEqual(paths(back), ["a"])

    def test_new_meta_keeps_the_verification_state(self):
        meta = lib.new_meta("b", "local", {"verify_start": "x", "verify_complete": "yes", "created": "old"})
        self.assertEqual((meta["verify_start"], meta["verify_complete"]), ("x", "yes"))
        self.assertNotEqual(meta["created"], "old")


class CompareTest(unittest.TestCase):
    def test_categories(self):
        left = [F("same", 1, 0, "a"), F("bad", 1, 0, "a"), F("size", 1, 0, "a"), F("onlyL", 1, 0, "a"),
                F("etag", 10, 0, None, "e-2", [5, 5]), F("unknown", 10, 0, "a")]
        right = [F("same", 1, 0, "a"), F("bad", 1, 0, "b"), F("size", 2, 0, "a"), F("onlyR", 1, 0, "a"),
                 F("etag", 10, 0, None, "e-2", [5, 5]), F("unknown", 10, 0, None, "e-2", [5, 5])]
        d = lib.compare(left, right, flat=False, check_sum=True)
        self.assertEqual(paths(d.only_left), ["onlyL"])
        self.assertEqual(paths(d.only_right), ["onlyR"])
        self.assertEqual(left_paths(d.size), ["size"])
        self.assertEqual(left_paths(d.checksum), ["bad"])
        self.assertEqual(left_paths(d.checksum_unknown), ["unknown"])
        self.assertEqual((d.sha1_ok, d.etag_ok), (1, 1))
        self.assertTrue(d.has_differences())

    def test_etag_over_different_parts_is_not_comparable(self):
        d = lib.compare([F("x", 10, 0, None, "e-2", [5, 5])], [F("x", 10, 0, None, "e-2", [6, 4])],
                        flat=False, check_sum=True)
        self.assertEqual(len(d.checksum_unknown), 1)

    def test_flat_mode_and_duplicates(self):
        left = [F("2020/a.mp4", 1, 0, "x"), F("x/c.mp4", 1, 0, "x"), F("y/c.mp4", 1, 0, "x")]
        right = [F("a.mp4", 1, 0, "x"), F("c.mp4", 1, 0, "x")]
        d = lib.compare(left, right, flat=True, check_sum=True)
        self.assertEqual(d.sha1_ok, 1)
        self.assertEqual([k for k, _, _ in d.duplicates], ["c.mp4"])

    def test_skipped_are_counted_not_compared(self):
        d = lib.compare([F("x", 1, 0, None, skipped=True)], [F("x", 1, 0, "a")], flat=False, check_sum=True)
        self.assertEqual((d.skipped, d.sha1_ok, len(d.checksum_unknown)), (1, 0, 0))
        self.assertFalse(d.has_differences())

    def test_attach_errors(self):
        d = lib.compare([F("x", 1, 0), F("y", 1, 0)], [F("x", 1, 0, "a"), F("y", 1, 0, "a")],
                        flat=False, check_sum=True)
        d.attach_errors({"x": "read error"})
        self.assertEqual(left_paths(d.errors), ["x"])
        self.assertEqual(left_paths(d.checksum_unknown), ["y"])
        self.assertEqual(d.notes["x"], "read error")
        self.assertTrue(d.has_differences())

    def test_mtime(self):
        d = lib.compare([F("x", 1, 5000, "a")], [F("x", 1, 1000, "a")], flat=False, check_mtime=True,
                        mtime_tolerance_ms=0)
        self.assertEqual(len(d.mtime), 1)


class ExpectedFromMetadataTest(unittest.TestCase):
    def test_s3_source_compares_by_etag_even_with_a_known_sha1(self):
        p = F("x", 10, 0, "learned-sha1", "e-2", [5, 5], source="s3")
        exp = lib.expected_from_metadata(p)
        self.assertIsNone(exp.sha1)
        self.assertEqual(p.sha1, "learned-sha1")  # the original is untouched
        self.assertTrue(lib.checksums_match(F("x", 10, 0, "other-sha1", "e-2", [5, 5]), exp))
        self.assertFalse(lib.checksums_match(F("x", 10, 0, "learned-sha1", "f-2", [5, 5]), exp))

    def test_b2_and_download_sources_compare_by_sha1(self):
        for source in ("b2", "download"):
            exp = lib.expected_from_metadata(F("x", 3, 0, "abc", source=source))
            self.assertTrue(lib.checksums_match(F("x", 3, 0, "abc"), exp))
            self.assertFalse(lib.checksums_match(F("x", 3, 0, "abd"), exp))

    def test_truncated_content_never_matches(self):
        exp = lib.expected_from_metadata(F("x", 10, 0, "abc", source="b2"))
        self.assertFalse(lib.checksums_match(F("x", 9, 0, "abc"), exp))

    def test_without_a_checksum_it_is_unknown(self):
        self.assertIsNone(lib.checksums_match(F("x", 3, 0, "abc"), lib.expected_from_metadata(F("x", 3, 0))))


class StateTest(unittest.TestCase):
    SAVED = F("a", 10, 0, "good")
    NOW = F("a", 10, 0, "bad")

    def test_b2_state(self):
        self.assertIn("restorable", lib.b2_state(self.NOW, self.SAVED, [F("a", 10, 0, "good")]))
        self.assertIn("same content", lib.b2_state(self.NOW, self.SAVED, [F("a", 10, 0, "bad")]))
        self.assertIn("differs from both", lib.b2_state(self.NOW, self.SAVED, [F("a", 10, 0, "other")]))
        self.assertIn("not in B2", lib.b2_state(self.NOW, self.SAVED, []))
        self.assertIn("no B2", lib.b2_state(self.NOW, self.SAVED, None))

    def test_local_state(self):
        content = F("a", 10, 0, "x")
        self.assertIn("identical", lib.local_state(content, [F("a", 10, 0, "x")]))
        self.assertIn("differs", lib.local_state(content, [F("a", 10, 0, "y")]))
        self.assertIn("not present", lib.local_state(content, []))


class PlanVerificationTest(unittest.TestCase):
    NOW = datetime(2026, 10, 2, 12, 0, 0)
    ENTRIES = [F("never", 1, 0), F("old", 1, 0, verified="2026-06-01 00:00:00"),
               F("today", 1, 0, verified="2026-10-02 11:00:00"),
               F("this_run", 1, 0, verified="2026-10-02 11:30:00")]

    def test_default_reads_everything(self):
        plan = lib.plan_verification(self.ENTRIES, {}, now=self.NOW)
        self.assertEqual(len(plan.todo), 4)
        self.assertEqual(plan.run_start, "2026-10-02 12:00:00")

    def test_older_than(self):
        plan = lib.plan_verification(self.ENTRIES, {}, older_than_days=30, now=self.NOW)
        self.assertEqual(paths(plan.todo), ["never", "old"])

    def test_resume_an_unfinished_run(self):
        meta = {"verify_start": "2026-10-02 11:15:00", "verify_complete": lib.INCOMPLETE}
        plan = lib.plan_verification(self.ENTRIES, meta, resume=True, now=self.NOW)
        self.assertTrue(plan.resumed)
        self.assertEqual(plan.run_start, "2026-10-02 11:15:00")
        self.assertEqual(paths(plan.skipped), ["this_run"])

    def test_resume_after_a_complete_run_starts_fresh(self):
        meta = {"verify_start": "2026-10-02 11:15:00", "verify_complete": lib.YES}
        plan = lib.plan_verification(self.ENTRIES, meta, resume=True, now=self.NOW)
        self.assertFalse(plan.resumed)
        self.assertEqual(len(plan.todo), 4)


class RunParallelTest(unittest.TestCase):
    def test_all_items_are_processed_concurrently(self):
        active, peak, lock = [0], [0], threading.Lock()

        def work(item, stop):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
            return item * 2

        results = {}

        def done(item, result, error):
            results[item] = result

        lib.run_parallel(range(16), work, threads=8, on_done=done)
        self.assertEqual(results, {i: i * 2 for i in range(16)})
        self.assertGreater(peak[0], 1)
        self.assertLessEqual(peak[0], 8)

    def test_errors_are_reported_not_raised(self):
        def work(item, stop):
            if item == 3:
                raise OSError("read error")
            return item

        errors = {}

        def done(item, result, error):
            if error:
                errors[item] = str(error)

        lib.run_parallel(range(5), work, threads=2, on_done=done)
        self.assertEqual(errors, {3: "read error"})

    def test_on_done_runs_in_the_calling_thread(self):
        caller, seen = threading.current_thread(), set()

        def done(item, result, error):
            seen.add(threading.current_thread())

        lib.run_parallel(range(4), lambda i, s: i, threads=4, on_done=done)
        self.assertEqual(seen, {caller})


if __name__ == "__main__":
    unittest.main()
