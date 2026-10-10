#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for fixity. Standard library only: python fixity_test.py"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import time
import unittest
import unittest.mock
import zlib
from datetime import datetime
from pathlib import Path

import fixity as fx
from fixity import Entry as E


def s3_etag(data: bytes, part_size: int) -> str:
    """Reference S3 multipart ETag, written independently of StreamHasher."""
    chunks = [data[i:i + part_size] for i in range(0, len(data), part_size)]
    return hashlib.md5(b"".join(hashlib.md5(c).digest() for c in chunks)).hexdigest() + f"-{len(chunks)}"


def reference_digests(data: bytes) -> dict[str, str]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "sha1": hashlib.sha1(data).hexdigest(),
            "md5": hashlib.md5(data).hexdigest(), "crc32": "%08X" % (zlib.crc32(data) & 0xFFFFFFFF)}


def chunked(data: bytes, sizes: list[int]):
    i, k = 0, 0
    while i < len(data):
        n = sizes[k % len(sizes)]
        yield data[i:i + n]
        i, k = i + n, k + 1


def digest_results(manifests: dict[str, str]) -> list[str]:
    """What happened to the four digest manifests, leaving out .s3etag."""
    return [what for name, what in manifests.items() if name != fx.ETAG_MANIFEST]


def paths(entries) -> list[str]:
    return [e.path for e in entries]


def quiet(_line: str) -> None:
    pass


def damage(path: Path) -> None:
    """Flip one byte and put the modification time back: what bit rot looks like."""
    st = path.stat()
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


class Tree:
    """A throwaway tree with an index outside it."""

    def __init__(self, files: dict[str, bytes]):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root, self.index = base / "tree", base / "state" / "tree.csv"
        for rel, data in files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()


class SizeAndFilterTest(unittest.TestCase):
    def test_parse_size(self):
        self.assertEqual(fx.parse_size("64K"), 64 * 1024)
        self.assertEqual(fx.parse_size("1MiB"), 1024 ** 2)
        self.assertEqual(fx.parse_size("1.5G"), int(1.5 * 1024 ** 3))
        for bad in ("", "1X", "-1M", "1,5G"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                fx.parse_size(bad)

    def test_size_split_is_complete_and_disjoint(self):
        files = [E("a", 1_048_575, 0), E("b", 1_048_576, 0), E("c", 5, 0)]
        small = set(paths(fx.FileFilter(max_size=fx.parse_size("1M")).apply(files)))
        large = set(paths(fx.FileFilter(min_size=fx.parse_size("1M")).apply(files)))
        self.assertEqual(small | large, {"a", "b", "c"})
        self.assertEqual(small & large, set())

    def test_regex_include_exclude(self):
        files = [E("Rec/a.MP4", 1, 0), E("Rec/n.txt", 1, 0), E("x.mp4", 1, 0)]
        flt = fx.FileFilter(include=[r"\.mp4$"], exclude=[r"^x"])
        self.assertEqual(paths(flt.apply(files)), ["Rec/a.MP4"])
        with self.assertRaises(re.error):
            fx.FileFilter(include=["*.mp4"])


class StreamHasherTest(unittest.TestCase):
    DATA = os.urandom(10_000) + b"\x00" * 1234

    def test_all_four_digests_match_independent_references(self):
        for sizes in ([1], [7, 13], [4096], [len(self.DATA)]):
            with self.subTest(chunk_sizes=sizes):
                digests, etag, size = fx.hash_chunks(chunked(self.DATA, sizes))
                self.assertEqual(digests, reference_digests(self.DATA))
                self.assertIsNone(etag)
                self.assertEqual(size, len(self.DATA))

    def test_multipart_etag_in_the_same_pass(self):
        part = 4096
        parts = [part] * (len(self.DATA) // part) + [len(self.DATA) % part]
        digests, etag, _ = fx.hash_chunks(chunked(self.DATA, [999]), parts, multipart=True)
        self.assertEqual(etag, s3_etag(self.DATA, part))
        self.assertEqual(digests, reference_digests(self.DATA))

    def test_single_part_etag_is_a_plain_md5(self):
        _, etag, _ = fx.hash_chunks([self.DATA], [len(self.DATA)], multipart=False)
        self.assertEqual(etag, hashlib.md5(self.DATA).hexdigest())

    def test_parts_that_do_not_fit_give_no_etag(self):
        self.assertIsNone(fx.hash_chunks([self.DATA], [len(self.DATA) - 1], True)[1])
        self.assertIsNone(fx.hash_chunks([self.DATA], [len(self.DATA) + 1], True)[1])

    def test_crc32_of_empty_input(self):
        self.assertEqual(fx.hash_chunks([])[0]["crc32"], "00000000")

    def test_stop_cancels_and_closes_the_stream(self):
        stop, closed = threading.Event(), []

        def stream():
            try:
                yield b"a"
                stop.set()
                yield b"b"
            finally:
                closed.append(True)

        with self.assertRaises(fx.Cancelled):
            fx.hash_chunks(stream(), stop=stop)
        self.assertEqual(closed, [True])

    def test_parts_roundtrip(self):
        for parts in ([100, 100, 43], [5], None):
            self.assertEqual(fx.decode_parts(fx.encode_parts(parts)), parts)


class LongPathTest(unittest.TestCase):
    def test_prefix_rules(self):
        lp = fx.long_path
        self.assertEqual(lp(r"D:\data\x.bin", windows=True), "\\\\?\\D:\\data\\x.bin")
        self.assertEqual(lp(r"\\server\share\x.bin", windows=True), "\\\\?\\UNC\\server\\share\\x.bin")
        once = lp(r"D:\data\x.bin", windows=True)
        self.assertEqual(lp(once, windows=True), once)
        self.assertEqual(lp("/srv/x", windows=False), "/srv/x")

    def test_scan_and_hash_beyond_260_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            parts = ["a-directory-with-a-long-name-%02d" % i for i in range(10)]
            deep = os.path.join(tmp, *parts)
            os.makedirs(fx.long_path(deep))
            with open(fx.long_path(os.path.join(deep, "end.bin")), "wb") as f:
                f.write(b"deep")
            entries = fx.scan_tree(Path(tmp))
            self.assertEqual(paths(entries), ["/".join(parts) + "/end.bin"])
            self.assertEqual(fx.hash_file(entries[0].abs_path)[0]["sha1"], hashlib.sha1(b"deep").hexdigest())
            if os.name == "nt":
                os.remove(fx.long_path(os.path.join(deep, "end.bin")))
                for i in range(len(parts), 0, -1):
                    os.rmdir(fx.long_path(os.path.join(tmp, *parts[:i])))


class IndexTest(unittest.TestCase):
    def test_roundtrip(self):
        entries = [E("a/b c.txt", 3, 10**18, "s" * 64, "h" * 40, "m" * 32, "0000ABCD", None, None, "2026-10-04 10:00:00"),
                   E('quote "and, comma".bin', 2500, 5, None, None, None, None, "e" * 32 + "-3", [1000, 1000, 500])]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "i.csv"
            fx.write_index(p, entries)
            self.assertEqual(fx.read_index(p), sorted(entries, key=lambda e: e.path))

    def test_reads_a_pymirror_index(self):
        # PyMirror's .mirror-index.csv carries path,size,mtime_ns,sha256 and nothing else.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".mirror-index.csv"
            p.write_text("path,size,mtime_ns,sha256\nx.bin,5,123," + "a" * 64 + "\n", encoding="utf-8")
            self.assertEqual(fx.read_index(p), [E("x.bin", 5, 123, "a" * 64)])

    def test_first_columns_are_those_pymirror_reads(self):
        self.assertEqual(fx.INDEX_COLUMNS[:4], ["path", "size", "mtime_ns", "sha256"])

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "i.csv"
            fx.write_state(p, {"created": "x", "complete": fx.YES})
            self.assertEqual(fx.read_state(p), {"created": "x", "complete": fx.YES})


class ManifestTest(unittest.TestCase):
    ENTRIES = [E("b/two words.bin", 1, 0, "s2", "h2", "m2", "0000BEEF"),
               E("a.txt", 1, 0, "s1", "h1", "m1", "DEADBEEF")]

    def test_formats_are_the_tools_own(self):
        self.assertEqual(fx.manifest_text(self.ENTRIES, "sha256"), "s1 *a.txt\ns2 *b/two words.bin\n")
        self.assertEqual(fx.manifest_text(self.ENTRIES, "crc32"),
                         "a.txt DEADBEEF\nb/two words.bin 0000BEEF\n")
        self.assertEqual(fx.sums_line("d", "back\\slash"), "\\d *back\\\\slash\n")

    def test_written_manifests_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = fx.write_manifests(root, self.ENTRIES)
            self.assertEqual(set(digest_results(result)), {"written"})
            self.assertIn("not needed", result[fx.ETAG_MANIFEST])  # no file above the cutoff
            self.assertEqual(fx.read_sums(root / ".sha1sum"), {"a.txt": "h1", "b/two words.bin": "h2"})
            self.assertEqual(fx.read_sfv(root / ".sfv"), {"a.txt": "DEADBEEF", "b/two words.bin": "0000BEEF"})

    def test_unchanged_manifests_are_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.write_manifests(root, self.ENTRIES)
            before = (root / ".md5sum").stat().st_mtime_ns
            time.sleep(0.02)
            self.assertEqual(set(digest_results(fx.write_manifests(root, self.ENTRIES))), {"unchanged"})
            self.assertEqual((root / ".md5sum").stat().st_mtime_ns, before)

    def test_partial_or_empty_manifests_are_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            partial = [E("a", 1, 0, "s", None, "m", "C")]
            result = fx.write_manifests(root, partial)
            self.assertIn("missing", result[".sha1sum"])
            self.assertFalse((root / ".sha1sum").exists())
            self.assertTrue((root / ".sha256sum").exists())
            self.assertIsNone(fx.manifest_text([], "sha256"))


class CompareTest(unittest.TestCase):
    def test_strongest_common_digest_decides(self):
        d = fx.compare([E("a", 1, 0, "s", "x"), E("b", 1, 0, None, "h"), E("c", 1, 0, md5="m")],
                       [E("a", 1, 0, "s", "y"), E("b", 1, 0, None, "h"), E("c", 1, 0, md5="z")],
                       check_sum=True)
        self.assertEqual(d.ok, {"sha256": 1, "sha1": 1})  # a by sha256 although sha1 differs
        self.assertEqual(paths(x for x, _ in d.checksum), ["c"])

    def test_etag_needs_the_same_parts(self):
        same = fx.compare([E("x", 10, 0, etag="e-2", parts=[5, 5])], [E("x", 10, 0, etag="e-2", parts=[5, 5])],
                          check_sum=True)
        other = fx.compare([E("x", 10, 0, etag="e-2", parts=[5, 5])], [E("x", 10, 0, etag="e-2", parts=[6, 4])],
                           check_sum=True)
        self.assertEqual(same.ok, {"etag": 1})
        self.assertEqual(len(other.checksum_unknown), 1)

    def test_categories_and_flat(self):
        d = fx.compare([E("n", 1, 0), E("s", 1, 0)], [E("g", 1, 0), E("s", 2, 0)])
        self.assertEqual((paths(d.only_left), paths(d.only_right), len(d.size)), (["n"], ["g"], 1))
        flat = fx.compare([E("x/c", 1, 0, "a"), E("y/c", 1, 0, "a")], [E("c", 1, 0, "a")], flat=True,
                          check_sum=True)
        self.assertEqual([k for k, _, _ in flat.duplicates], ["c"])


class PlanAndParallelTest(unittest.TestCase):
    NOW = datetime(2026, 10, 4, 12, 0, 0)

    def test_plan(self):
        entries = [E("never", 1, 0), E("old", 1, 0, verified="2026-06-01 00:00:00"),
                   E("run", 1, 0, verified="2026-10-04 11:30:00")]
        self.assertEqual(paths(fx.plan_verification(entries, {}, older_than_days=30, now=self.NOW).todo),
                         ["never", "old"])
        state = {"verify_start": "2026-10-04 11:00:00", "verify_complete": fx.INCOMPLETE}
        self.assertEqual(paths(fx.plan_verification(entries, state, resume=True, now=self.NOW).skipped), ["run"])

    def test_run_parallel(self):
        results, errors = {}, {}

        def work(i, stop):
            if i == 3:
                raise OSError("read error")
            time.sleep(0.01)
            return i * 2

        def done(i, r, e):
            (errors if e else results)[i] = str(e) if e else r

        fx.run_parallel(range(8), work, threads=4, on_done=done)
        self.assertEqual(errors, {3: "read error"})
        self.assertEqual(len(results), 7)


class UpdateIndexTest(unittest.TestCase):
    FILES = {"a.bin": os.urandom(3000), "sub/b.bin": os.urandom(500), "big.bin": os.urandom(2500)}

    def test_first_run_reads_everything_and_writes_four_manifests(self):
        with Tree(self.FILES) as t:
            r = fx.update_index(t.root, t.index, out=quiet)
            self.assertTrue(r.complete)
            self.assertEqual(len(r.hashed), 3)
            self.assertEqual(set(digest_results(r.manifests)), {"written"})
            for rel, data in self.FILES.items():
                self.assertEqual(fx.read_sums(t.root / ".sha256sum")[rel], hashlib.sha256(data).hexdigest())
                self.assertEqual(fx.read_sums(t.root / ".md5sum")[rel], hashlib.md5(data).hexdigest())
                self.assertEqual(fx.read_sfv(t.root / ".sfv")[rel], reference_digests(data)["crc32"])

    def test_no_file_describes_itself(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            r = fx.update_index(t.root, t.index, out=quiet)  # second run sees the manifests on disk
            listed = set(fx.read_sums(t.root / ".sha1sum"))
            self.assertEqual(listed, set(self.FILES))
            self.assertEqual(set(digest_results(r.manifests)), {"unchanged"})
            in_tree = Path(t.root) / fx.DEFAULT_INDEX
            fx.update_index(t.root, in_tree, out=quiet)  # an index INSIDE the tree is not content either
            self.assertNotIn(fx.DEFAULT_INDEX, set(fx.read_sums(t.root / ".sha1sum")))

    def test_second_run_reads_nothing(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            self.assertEqual(fx.update_index(t.root, t.index, out=quiet).hashed, [])

    def test_damage_is_reported_and_the_good_digests_kept(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            good = {e.path: e.sha256 for e in fx.read_index(t.index)}
            damage(t.root / "a.bin")
            r = fx.update_index(t.root, t.index, force=True, out=quiet)
            self.assertEqual([e.path for e, _ in r.damaged], ["a.bin"])
            self.assertEqual({e.path: e.sha256 for e in fx.read_index(t.index)}, good)
            self.assertEqual(fx.read_sums(t.root / ".sha256sum")["a.bin"], good["a.bin"])

    def test_part_layouts_add_the_etag(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            layouts = {"big.bin": ([1000, 1000, 500], True)}
            r = fx.update_index(t.root, t.index, layouts=layouts, out=quiet)
            self.assertEqual(paths(r.hashed), ["big.bin"])  # only the file whose ETag was missing
            got = {e.path: e for e in fx.read_index(t.index)}["big.bin"]
            self.assertEqual(got.etag, s3_etag(self.FILES["big.bin"], 1000))

    def test_an_old_index_with_only_sha1_is_completed(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            old = [fx.copy_entry(e, sha256=None, md5=None, crc32=None) for e in fx.read_index(t.index)]
            fx.write_index(t.index, old)
            r = fx.update_index(t.root, t.index, out=quiet)
            self.assertEqual(len(r.hashed), 3)
            self.assertTrue(all(e.has_all_digests() for e in fx.read_index(t.index)))


class S3EtagTest(unittest.TestCase):
    """The ETag a cloud copy reports, computed by default -- seen on 2026-10-10, when 774 files of
    2.5 TB were uploaded in parts and their whole-file digests could not be compared with anything."""

    SMALL = fx.S3Layout(part_size=1000, cutoff=2000)  # the real rule, scaled down
    FILES = {"small.bin": os.urandom(1500), "edge.bin": os.urandom(2000), "big.bin": os.urandom(4500),
             "sub/exact.bin": os.urandom(3000)}

    def test_the_default_is_the_rule_real_uploads_follow(self):
        d = fx.DEFAULT_S3
        self.assertEqual((d.part_size, d.cutoff), (100_000_000, 209_715_200))
        self.assertIsNone(d.parts(209_715_200))  # up to 200 MiB in one piece, with a SHA-1 in B2
        self.assertEqual(d.parts(3_557_000_000), [100_000_000] * 35 + [57_000_000])  # a real volume

    def test_layouts(self):
        s = self.SMALL
        self.assertIsNone(s.parts(2000))
        self.assertEqual(s.parts(4500), [1000, 1000, 1000, 1000, 500])
        self.assertEqual(s.parts(3000), [1000, 1000, 1000])  # no empty last part
        self.assertIsNone(fx.S3Layout(0).parts(10**12))  # switched off

    def test_index_and_s3etag_without_being_told_anything(self):
        with Tree(self.FILES) as t:
            r = fx.update_index(t.root, t.index, out=quiet, s3=self.SMALL)
            self.assertEqual(r.manifests[fx.ETAG_MANIFEST], "written")
            got = {e.path: e for e in fx.read_index(t.index)}
            for rel in ("big.bin", "sub/exact.bin"):
                self.assertEqual(got[rel].etag, s3_etag(self.FILES[rel], 1000), rel)
                self.assertEqual(got[rel].parts, self.SMALL.parts(len(self.FILES[rel])))
            self.assertIsNone(got["edge.bin"].etag)  # at the cutoff: one piece, the SHA-1 covers it
            part_size, etags = fx.read_etags(t.root / fx.ETAG_MANIFEST)
            self.assertEqual(part_size, 1000)
            self.assertEqual(etags, {"big.bin": got["big.bin"].etag, "sub/exact.bin": got["sub/exact.bin"].etag})
            text = (t.root / fx.ETAG_MANIFEST).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# S3 multipart ETags"))
            self.assertIn("files larger than 2000 bytes", text)

    def test_the_manifest_is_stable_and_never_describes_itself(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet, s3=self.SMALL)
            r = fx.update_index(t.root, t.index, out=quiet, s3=self.SMALL)
            self.assertEqual(r.hashed, [])  # the ETag is in the index: nothing is read again
            self.assertEqual(r.manifests[fx.ETAG_MANIFEST], "unchanged")
            self.assertNotIn(fx.ETAG_MANIFEST, fx.read_sums(t.root / ".sha256sum"))

    def test_an_old_index_gets_its_etags_in_one_more_read_of_the_large_files_only(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet, s3=None)  # before this default existed
            self.assertFalse((t.root / fx.ETAG_MANIFEST).exists())
            r = fx.update_index(t.root, t.index, out=quiet, s3=self.SMALL)
            self.assertEqual(paths(r.hashed), ["big.bin", "sub/exact.bin"])
            self.assertEqual(set(digest_results(r.manifests)), {"unchanged"})  # the digests did not move
            self.assertEqual(r.manifests[fx.ETAG_MANIFEST], "written")

    def test_an_explicit_layout_wins_and_then_the_manifest_is_not_written(self):
        with Tree(self.FILES) as t:
            layouts = {"big.bin": ([1500, 1500, 1500], True)}  # a cloud copy cut differently
            r = fx.update_index(t.root, t.index, layouts=layouts, out=quiet, s3=self.SMALL)
            got = {e.path: e for e in fx.read_index(t.index)}["big.bin"]
            self.assertEqual(got.etag, s3_etag(self.FILES["big.bin"], 1500))
            self.assertIn("not written", r.manifests[fx.ETAG_MANIFEST])
            self.assertIn("big.bin", r.manifests[fx.ETAG_MANIFEST])
            self.assertFalse((t.root / fx.ETAG_MANIFEST).exists())

    def test_switched_off_and_a_stale_manifest_removed(self):
        with Tree(self.FILES) as t:
            r = fx.update_index(t.root, t.index, out=quiet, s3=None)
            self.assertNotIn(fx.ETAG_MANIFEST, r.manifests)
            fx.update_index(t.root, t.index, out=quiet, s3=self.SMALL)
            for rel in ("big.bin", "sub/exact.bin"):
                (t.root / rel).write_bytes(b"now small")
            r = fx.update_index(t.root, t.index, out=quiet, s3=self.SMALL)
            self.assertIn("removed", r.manifests[fx.ETAG_MANIFEST])
            self.assertFalse((t.root / fx.ETAG_MANIFEST).exists())


class ParallelHashingTest(unittest.TestCase):
    """The digests of one stream spread over threads, and several files at once in their order --
    the CPU, not the disk, was the bottleneck (202 MB/s for all digests in one thread)."""

    DATA = os.urandom(3 * 1000 + 777)

    def test_every_thread_count_gives_the_same_digests_and_etag(self):
        expected = fx.hash_chunks(chunked(self.DATA, [4096]), [1000, 1000, 1000, 777], True)
        self.assertEqual(expected[1], s3_etag(self.DATA, 1000))
        for threads in (2, 3, 4, 5, 9):
            for sizes in ([1], [999, 1, 3000], [len(self.DATA)]):
                got = fx.hash_chunks(chunked(self.DATA, sizes), [1000, 1000, 1000, 777], True, threads=threads)
                self.assertEqual(got, expected, (threads, sizes))

    def test_the_two_md5s_never_share_a_thread(self):
        costs = [fx._COST[n] for n in ("sha256", "sha1", "md5", "crc32", "etag")]
        groups = fx.spread(costs, 4)
        self.assertEqual(len(groups), 4)
        md5_groups = [i for i, g in enumerate(groups) if 2 in g or 4 in g]
        self.assertEqual(len(set(md5_groups)), 2)
        self.assertEqual(fx.spread(costs, 1), [[2, 4, 0, 1, 3]])
        self.assertEqual(len(fx.spread(costs, 20)), 5)  # never more threads than digests

    def test_a_reused_buffer_cannot_change_what_was_hashed(self):
        h = fx.StreamHasher(threads=4)
        buf = bytearray(b"a" * 5000)
        h.update(buf)
        buf[:] = b"b" * 5000  # a caller reusing its buffer
        h.update(buf)
        self.assertEqual(h.result()[0]["sha256"], hashlib.sha256(b"a" * 5000 + b"b" * 5000).hexdigest())

    def test_an_error_in_a_digest_thread_reaches_the_caller_and_no_thread_is_left(self):
        before = threading.active_count()

        class Broken:
            name, cost = "broken", 1.0

            def update(self, data):
                raise ValueError("digest failed")

        h = fx.StreamHasher(threads=3)
        h._lanes[0].consumers.append(Broken())
        h.update(b"x" * 10_000)
        h.update(b"y" * 10_000)  # the reader must not block behind the failed thread
        with self.assertRaisesRegex(ValueError, "digest failed"):
            h.result()
        self.assertEqual(threading.active_count(), before)

    def test_an_interrupted_stream_ends_its_threads(self):
        before = threading.active_count()
        stop = threading.Event()

        def chunks():
            yield b"a" * 4096
            stop.set()
            yield b"b" * 4096

        with self.assertRaises(fx.Cancelled):
            fx.hash_chunks(chunks(), stop=stop, threads=4)
        self.assertEqual(threading.active_count(), before)

    def test_files_finish_in_their_order_with_at_most_n_at_once(self):
        seen, running, peak, lock = [], [0], [0], threading.Lock()

        def work(i, stop):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.05 if i % 3 == 0 else 0.005)  # some finish long before the one ahead
            with lock:
                running[0] -= 1
            if i == 4:
                raise OSError("unreadable")
            return i * 10

        fx.run_ordered(range(10), work, 3, lambda i, r, e: seen.append((i, r, str(e) if e else None)))
        self.assertEqual([i for i, _r, _e in seen], list(range(10)))
        self.assertEqual(seen[4], (4, None, "unreadable"))
        self.assertEqual(seen[5], (5, 50, None))
        self.assertLessEqual(peak[0], 3)

    def test_update_index_in_parallel_equals_one_thread(self):
        files = {f"f{i}.bin": os.urandom(3000 + 400 * i) for i in range(7)}
        small_rule = fx.S3Layout(part_size=1000, cutoff=2000)
        with unittest.mock.patch.object(fx, "PARALLEL_MIN_SIZE", 0):  # every file through the threads
            with Tree(files) as one, Tree(files) as many:
                lines_one, lines_many = [], []
                fx.update_index(one.root, one.index, out=lines_one.append, s3=small_rule, threads=1, hash_threads=1)
                r = fx.update_index(many.root, many.index, out=lines_many.append, s3=small_rule,
                                    threads=3, hash_threads=5)
                strip = lambda es: [(e.path, e.digests(), e.etag, e.parts) for e in es]  # noqa: E731
                self.assertEqual(strip(fx.read_index(many.index)), strip(fx.read_index(one.index)))
                self.assertEqual([ln.split()[-1] for ln in lines_many[1:8]], sorted(files))  # in order
                self.assertEqual((many.root / fx.ETAG_MANIFEST).read_text(encoding="utf-8"),
                                 (one.root / fx.ETAG_MANIFEST).read_text(encoding="utf-8"))
                self.assertEqual(len(r.hashed), 7)

    def test_verify_with_hash_threads_still_finds_damage(self):
        files = {"a.bin": os.urandom(50_000), "b.bin": os.urandom(60_000)}
        with unittest.mock.patch.object(fx, "PARALLEL_MIN_SIZE", 0):
            with Tree(files) as t:
                fx.update_index(t.root, t.index, out=quiet)
                damage(t.root / "b.bin")
                r = fx.verify_tree(t.root, t.index, threads=2, hash_threads=5, out=quiet)
                self.assertEqual(paths(a for a, _b in r.diff.checksum), ["b.bin"])


class FolderRecordTest(unittest.TestCase):
    """Each folder carries its own record: five manifests and a state file, nothing elsewhere --
    so it can move between machines and be checked anywhere."""

    FILES = {"a.bin": os.urandom(3000), "sub/b.bin": os.urandom(500), "#hash first.txt": b"a name starting with #"}

    def state_rows(self, root: Path) -> dict[str, dict[str, str]]:
        import csv
        import io
        body = fx._split_header((root / fx.STATE_FILE).read_text(encoding="utf-8"))[1]
        return {r["path"]: r for r in csv.DictReader(io.StringIO(body))}

    def test_six_files_and_no_digest_twice(self):
        with Tree(self.FILES) as t:
            r = fx.update_index(t.root, None, out=quiet)
            self.assertTrue(r.complete)
            own = sorted(p.name for p in t.root.iterdir() if p.name.startswith("."))
            self.assertEqual(own, sorted([".fixity-state.csv", ".md5sum", ".sfv", ".sha1sum", ".sha256sum"]))
            rows = self.state_rows(t.root)
            self.assertEqual(set(rows), set(self.FILES))  # including the name that starts with '#'
            for row in rows.values():
                self.assertEqual([row[d] for d in fx.DIGESTS], ["", "", "", ""])  # they are in the manifests
                self.assertTrue(row["verified"])
            self.assertEqual(fx.read_state(t.root / fx.STATE_FILE)["complete"], fx.YES)
            self.assertFalse(fx.state_path(t.root / fx.STATE_FILE).exists())  # run state is inside
            entries, _state = fx.folder_record(t.root)
            self.assertTrue(all(e.has_all_digests() for e in entries))
            self.assertEqual({e.path: e.sha256 for e in entries},
                             {k: hashlib.sha256(v).hexdigest() for k, v in self.FILES.items()})

    def test_a_run_that_finds_nothing_writes_nothing(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, None, out=quiet)
            before = (t.root / fx.STATE_FILE).stat().st_mtime_ns
            time.sleep(0.02)
            r = fx.update_index(t.root, None, out=quiet)
            self.assertEqual(r.hashed, [])
            self.assertEqual((t.root / fx.STATE_FILE).stat().st_mtime_ns, before)

    def test_another_machine_reads_only_what_changed(self):
        import shutil
        with Tree(self.FILES) as t:
            fx.update_index(t.root, None, out=quiet)
            other = t.root.parent / "elsewhere"
            shutil.copytree(t.root, other)  # copy2: times kept, as robocopy and rsync -t keep them
            self.assertEqual(fx.update_index(other, None, out=quiet).hashed, [])
            (other / "a.bin").write_bytes(b"changed there")
            self.assertEqual(paths(fx.update_index(other, None, out=quiet).hashed), ["a.bin"])

    def test_taken_over_from_manifests_alone_without_reading(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, None, out=quiet)
            (t.root / fx.STATE_FILE).unlink()  # a folder copied without it, or made before it existed
            later = t.root / "sub/b.bin"
            later.write_bytes(b"modified after the manifests")
            st = later.stat()
            os.utime(later, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
            r = fx.update_index(t.root, None, out=quiet)
            self.assertEqual(paths(r.hashed), ["sub/b.bin"])  # only the file newer than the manifests
            self.assertEqual(fx.read_sums(t.root / ".sha256sum")["sub/b.bin"],
                             hashlib.sha256(b"modified after the manifests").hexdigest())

    def test_damage_after_a_takeover_is_still_found(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, None, out=quiet)
            (t.root / fx.STATE_FILE).unlink()
            fx.update_index(t.root, None, out=quiet)  # taken over: nothing read
            damage(t.root / "a.bin")
            r = fx.verify_tree(t.root, None, out=quiet)
            self.assertEqual(paths(a for a, _b in r.diff.checksum), ["a.bin"])
            self.assertEqual(self.state_rows(t.root)["a.bin"]["verified"], "")  # failed: read again next time

    def test_an_index_kept_elsewhere_is_taken_over_once_with_its_last_checks(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            old = fx.read_index(t.index)
            old = [fx.copy_entry(e, verified="2026-01-02 03:04:05") for e in old]
            fx.write_index(t.index, old)
            r = fx.update_index(t.root, None, out=quiet, seed=t.index)
            self.assertEqual(r.hashed, [])
            self.assertEqual({row["verified"] for row in self.state_rows(t.root).values()}, {"2026-01-02 03:04:05"})

    def test_the_index_of_earlier_versions_inside_the_tree_is_replaced(self):
        with Tree(self.FILES) as t:
            legacy = t.root / fx.DEFAULT_INDEX
            fx.update_index(t.root, legacy, out=quiet)
            self.assertTrue(fx.state_path(legacy).exists())
            r = fx.update_index(t.root, None, out=quiet)
            self.assertEqual(r.hashed, [])
            self.assertFalse(legacy.exists())
            self.assertFalse(fx.state_path(legacy).exists())
            self.assertIn(fx.STATE_FILE, r.manifests[fx.DEFAULT_INDEX])

    def test_an_interrupted_run_keeps_its_digests_in_the_state_file_until_the_manifests_have_them(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, None, out=quiet, manifests=False)  # as if stopped before the manifests
            rows = self.state_rows(t.root)
            self.assertTrue(all(row["sha256"] for row in rows.values()))
            r = fx.update_index(t.root, None, out=quiet)
            self.assertEqual(r.hashed, [])  # nothing lost, nothing read again
            self.assertTrue(all(row["sha256"] == "" for row in self.state_rows(t.root).values()))

    def test_an_etag_lives_in_s3etag_unless_it_is_over_another_layout(self):
        files = {"big.bin": os.urandom(4500), "other.bin": os.urandom(4500)}
        small = fx.S3Layout(1000, 2000)
        with Tree(files) as t:
            fx.update_index(t.root, None, out=quiet, s3=small)
            rows = self.state_rows(t.root)
            self.assertEqual((rows["big.bin"]["etag"], rows["big.bin"]["parts"]), ("", ""))
            got = {e.path: e for e in fx.folder_record(t.root)[0]}
            self.assertEqual(got["big.bin"].etag, s3_etag(files["big.bin"], 1000))
            self.assertEqual(got["big.bin"].parts, small.parts(4500))
            fx.update_index(t.root, None, out=quiet, s3=small, layouts={"other.bin": ([1500] * 3, True)})
            rows = self.state_rows(t.root)
            self.assertEqual(rows["other.bin"]["etag"], s3_etag(files["other.bin"], 1500))  # not the listed one

    def test_verify_keeps_its_last_checks_in_the_folder(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, None, out=quiet)
            r = fx.verify_tree(t.root, None, out=quiet)
            self.assertEqual(r.diff.identical, 3)
            r = fx.verify_tree(t.root, None, older_than=1, out=quiet)
            self.assertEqual(r.diff.skipped, 3)


class VerifyTreeTest(unittest.TestCase):
    FILES = {"a.bin": os.urandom(3000), "b.bin": os.urandom(800)}

    def test_damage_new_gone_and_timestamps(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            r = fx.verify_tree(t.root, t.index, out=quiet)
            self.assertFalse(r.diff.has_differences())
            self.assertEqual(r.diff.identical, 2)

            damage(t.root / "a.bin")
            (t.root / "new.bin").write_bytes(b"n")
            (t.root / "b.bin").unlink()
            r = fx.verify_tree(t.root, t.index, out=quiet)
            self.assertEqual(paths(x for x, _ in r.diff.checksum), ["a.bin"])
            self.assertEqual(paths(r.diff.only_left), ["new.bin"])
            self.assertEqual(paths(r.diff.only_right), ["b.bin"])
            saved = {e.path: e for e in fx.read_index(t.index)}
            self.assertEqual(saved["a.bin"].verified, "")  # read again by every later run

    def test_older_than_skips_and_quick_reads_nothing(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            r = fx.verify_tree(t.root, t.index, older_than=1, out=quiet)
            self.assertEqual(r.diff.skipped, 2)
            q = fx.verify_tree(t.root, t.index, quick=True, out=quiet)
            self.assertIsNone(q.plan)
            self.assertFalse(q.diff.has_differences())

    def test_threads_and_selection(self):
        with Tree(self.FILES) as t:
            fx.update_index(t.root, t.index, out=quiet)
            r = fx.verify_tree(t.root, t.index, selection=fx.FileFilter(max_size=1000), threads=4, out=quiet)
            self.assertEqual((r.diff.left_count, r.diff.identical), (1, 1))


class AwkwardNamesSurviveEveryFormat(unittest.TestCase):
    r"""A path is DATA, and every format here has a delimiter a path may contain.

    WHY THIS CLASS EXISTS. On 2026-10-09 PyMirror's `<unit>.index.csv` was found to be broken for
    4 476 of 1 688 131 rows: it was written with `"%s,%s,%d,%s" % (...)` and 4 476 paths in that
    collection contain a comma, so `csv.DictReader` read `size` as `bin` and the digest fell into
    the overflow column. Silently, on 0.265 % of rows, for weeks, in the file whose whole job is to
    be read later by something that is not the tool that wrote it.

    PyFixity was already correct -- `csv.writer` for the index, `rpartition(" ")` for the .sfv,
    GNU's backslash escape for the sum files -- and `IndexTest.test_roundtrip` covers the index.
    THE MANIFESTS WERE NOT COVERED, and they are the formats with the nastier delimiters: the sum
    files put the digest FIRST and the .sfv puts it LAST, so one must be split from the left and
    the other from the right. Nothing failed; these are here so nothing starts to.

    Names Windows actually permits, which is the only set worth testing: a space, a comma, a
    quote, a semicolon, multiple spaces, and a tail that looks like the field it sits next to.
    Backslash and newline cannot occur in a Windows name but the escape exists, so it is checked
    too.
    """

    NAMES = [
        "a/b c.txt",                      # a space -- the .sfv delimiter
        'quote "and, comma".bin',         # a comma and a quote -- the CSV delimiters
        "two  spaces.bin",                # consecutive spaces: rpartition must take the LAST
        "trailing 0000ABCD.bin",          # a tail shaped like a CRC32, beside a CRC32 field
        "; not a comment.bin",            # a leading semicolon is an .sfv comment marker
        "star *name.bin",                 # `*` is the sum files' binary-mode marker
        "equals = sign.bin",              # harmless, and the kind of thing that surprises later
    ]

    def entries(self):
        return [E(name, 7, 10 ** 18, "s" * 64, "h" * 40, "m" * 32, "0000ABCD")
                for name in self.NAMES]

    def test_THE_SFV_ROUND_TRIPS_A_NAME_WITH_SPACES(self):
        r"""`<name> <CRC32>` -- the columns the other way round from sha256sum, so a reader must
        split from the RIGHT. A name with its own spaces is what proves it does."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.write_manifests(root, self.entries())
            got = fx.read_sfv(root / fx.MANIFEST_FILES["crc32"])
            self.assertEqual(sorted(got), sorted(self.NAMES))
            for name in self.NAMES:
                self.assertEqual(got[name], "0000ABCD")

    def test_and_the_sum_files_round_trip_the_same_names(self):
        r"""Here the digest comes FIRST, so these must be split from the left -- the opposite rule
        in the same directory, which is exactly how one of them gets written wrong one day."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.write_manifests(root, self.entries())
            for algo in ("sha256", "sha1", "md5"):
                got = fx.read_sums(root / fx.MANIFEST_FILES[algo])
                self.assertEqual(sorted(got), sorted(self.NAMES), algo)

    def test_and_the_index_round_trips_them(self):
        r"""Already covered for two names by IndexTest.test_roundtrip; repeated over the whole set
        so the three formats are checked against ONE list and cannot drift apart."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "i.csv"
            fx.write_index(path, self.entries())
            self.assertEqual([e.path for e in fx.read_index(path)], sorted(self.NAMES))

    def test_A_SEMICOLON_NAME_IS_NOT_READ_AS_AN_SFV_COMMENT(self):
        r"""`;` starts a comment in an .sfv, and `write_manifests` does not write one -- so a file
        whose name begins with `;` must still come back. If a header is ever added, it has to go
        where this test still passes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.write_manifests(root, self.entries())
            got = fx.read_sfv(root / fx.MANIFEST_FILES["crc32"])
            self.assertIn("; not a comment.bin", got)

    def test_a_backslash_or_newline_takes_GNUs_escape(self):
        r"""Neither can occur in a Windows file name, so this is about the FORMAT being right
        rather than a file that exists: `sha256sum -c` expects the leading backslash."""
        line = fx.sums_line("d" * 64, "has" + chr(92) + "back.bin")
        self.assertTrue(line.startswith(chr(92)))
        self.assertIn(chr(92) * 2, line)
        newline = fx.sums_line("d" * 64, "two" + chr(10) + "lines.bin")
        self.assertTrue(newline.startswith(chr(92)))
        self.assertEqual(newline.count(chr(10)), 1, "only the line's own terminator")
        self.assertIn(chr(92) + "n", newline)

    def test_and_a_plain_name_gets_no_escape_for_nothing(self):
        r"""The escape must apply only where it is needed, or every line of every manifest changes
        and `sha256sum -c` reads the backslash as part of the digest."""
        self.assertEqual(fx.sums_line("d" * 64, "plain.bin"), "d" * 64 + " *plain.bin" + chr(10))
        self.assertFalse(fx.sums_line("d" * 64, "a/b c.txt").startswith(chr(92)))

    def test_A_CRC32_SHAPED_TAIL_IS_WHAT_RESCUES_A_SEMICOLON_NAME(self):
        r"""The rule read_sfv applies, stated as its own case: a `;` line that ends in eight hex
        digits is an entry, and one that does not is a comment."""
        self.assertTrue(fx.looks_like_a_crc32("0000ABCD"))
        self.assertTrue(fx.looks_like_a_crc32("deadbeef"))
        self.assertFalse(fx.looks_like_a_crc32("0000ABC"))      # seven
        self.assertFalse(fx.looks_like_a_crc32("0000ABCDE"))    # nine
        self.assertFalse(fx.looks_like_a_crc32("0000ABCG"))     # not hex

    def test_and_an_ordinary_comment_is_still_a_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.sfv"
            p.write_text("; written by something\nfile.bin 0000ABCD\n", encoding="utf-8")
            self.assertEqual(fx.read_sfv(p), {"file.bin": "0000ABCD"})

    def test_THE_MANIFESTS_AGREE_WITH_THE_INDEX_ON_EVERY_NAME(self):
        r"""THE CHECK THE PYMIRROR DEFECT WOULD HAVE FAILED. Four files written from one list must
        name the same set of paths; a quoting bug in any one of them shows up as a difference here
        and nowhere else, because each file on its own looks plausible.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = self.entries()
            fx.write_manifests(root, entries)
            index = Path(tmp) / "i.csv"
            fx.write_index(index, entries)
            from_index = set(e.path for e in fx.read_index(index))
            self.assertEqual(set(fx.read_sfv(root / fx.MANIFEST_FILES["crc32"])), from_index)
            for algo in ("sha256", "sha1", "md5"):
                self.assertEqual(set(fx.read_sums(root / fx.MANIFEST_FILES[algo])), from_index,
                                 algo)


if __name__ == "__main__":
    unittest.main()
