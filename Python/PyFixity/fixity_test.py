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
            self.assertEqual(set(result.values()), {"written"})
            self.assertEqual(fx.read_sums(root / ".sha1sum"), {"a.txt": "h1", "b/two words.bin": "h2"})
            self.assertEqual(fx.read_sfv(root / ".sfv"), {"a.txt": "DEADBEEF", "b/two words.bin": "0000BEEF"})

    def test_unchanged_manifests_are_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.write_manifests(root, self.ENTRIES)
            before = (root / ".md5sum").stat().st_mtime_ns
            time.sleep(0.02)
            self.assertEqual(set(fx.write_manifests(root, self.ENTRIES).values()), {"unchanged"})
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
            self.assertEqual(set(r.manifests.values()), {"written"})
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
            self.assertEqual(set(r.manifests.values()), {"unchanged"})
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
