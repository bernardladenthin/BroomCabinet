#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Four checksums per file, in formats somebody else's tools already read.

WHY THREE WEAKER ALGORITHMS BESIDE A STRONG ONE. Not for strength -- sha256 settles every
verification this collection makes. For INTEROPERABILITY, because the parties that could give a
second opinion about these bytes do not speak sha256:

    sha1    Backblaze B2 records one per file (X-Bz-Content-Sha1)
    md5     the Internet Archive publishes one for every file in an item
    crc32   RAR and ZIP store one per member, and .sfv carries one on disk

Measured on this collection's own IA-METADATA.json, 2026-10-02: md5 present on 204 of 204 files,
crc32 and sha1 on 203, **sha256 on none**. An index of sha256 alone cannot be compared with the
Internet Archive for a single file -- and the Archive is where this collection looks when an
origin is gone.

THE COST IS ONE READ AND NO WALL CLOCK, measured the same day on a 470 MB file with the disk out
of the picture: sha256 alone 1551 MB/s, all four together 309 MB/s, against a disk that delivers
208 MB/s cold. Four digests still outrun the disk, so the pass stays disk-bound. md5 is the
expensive one at 658 MB/s and is what takes the headroom from 2.8x to 1.5x.

WHAT THESE TESTS ARE FOR, and it is not the arithmetic -- hashlib is not on trial. They pin the
two things that would quietly produce a manifest nobody can use:

  * THE SFV COLUMNS ARE REVERSED. `sha256sum` writes `<hash> *<path>`; an .sfv writes
    `<path> <hash>`. A writer that gets this the wrong way round produces a file that still looks
    like an .sfv and verifies nothing.
  * FOUR MANIFESTS OF ONE TREE MUST AGREE. Eight tools here once each kept their own idea of
    which files were bookkeeping, and no two of the 28 pairs agreed. A manifest that disagrees
    with its neighbours is worse than a missing one: it looks like evidence.

No network, no archive touched; everything happens in a temporary directory.
"""
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

BODIES = {
    "a.txt": b"hello world",
    "deep/b.bin": bytes(range(256)) * 40,
    "has space.dat": b"",                       # empty, and a space in the name
    "ümlaut.txt": "grüße".encode("utf-8"),
}


class Tree(object):
    def __init__(self, bodies=None):
        self.root = tempfile.mkdtemp()
        for rel, body in (bodies or BODIES).items():
            full = os.path.join(self.root, *rel.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with io.open(full, "wb") as fh:
                fh.write(body)

    def digests(self):
        out = {}
        for rel in sorted(BODIES):
            out[rel] = common.digests_of_file(os.path.join(self.root, *rel.split("/")))
        return out

    def read(self, name):
        with io.open(os.path.join(self.root, name), encoding="utf-8") as fh:
            return fh.read()

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class OneReadFourAnswers(unittest.TestCase):

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def path(self, rel):
        return os.path.join(self.t.root, *rel.split("/"))

    def test_each_digest_matches_the_one_the_stdlib_gives(self):
        for rel, body in BODIES.items():
            got = common.digests_of_file(self.path(rel))
            self.assertEqual(got["sha256"], hashlib.sha256(body).hexdigest(), rel)
            self.assertEqual(got["sha1"], hashlib.sha1(body).hexdigest(), rel)
            self.assertEqual(got["md5"], hashlib.md5(body).hexdigest(), rel)
            self.assertEqual(got["crc32"], "%08X" % zlib.crc32(body), rel)

    def test_it_agrees_with_the_sha256_the_collection_already_uses(self):
        """A second way to compute the same thing is a second answer unless they are checked."""
        for rel in BODIES:
            self.assertEqual(common.digests_of_file(self.path(rel))["sha256"],
                             common.sha256_file(self.path(rel)), rel)

    def test_the_chunk_size_does_not_change_the_answer(self):
        """Streaming is where a hash goes wrong: a boundary mishandled shows up only on some
        sizes. crc32 is the one carrying state by hand, through zlib's `value` argument."""
        rel = "deep/b.bin"
        whole = common.digests_of_file(self.path(rel))
        for chunk in (1, 7, 4096, 10 ** 7):
            self.assertEqual(common.digests_of_file(self.path(rel), chunk=chunk), whole, chunk)

    def test_an_empty_file_gets_the_empty_digests_and_not_an_error(self):
        got = common.digests_of_file(self.path("has space.dat"))
        self.assertEqual(got["sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual(got["crc32"], "00000000")

    def test_crc32_is_eight_upper_case_hex_digits(self):
        """What every .sfv in the wild carries, and what sfv-verify.py compares against."""
        for rel in BODIES:
            crc = common.digests_of_file(self.path(rel))["crc32"]
            self.assertEqual(len(crc), 8, rel)
            self.assertEqual(crc, crc.upper(), rel)
            int(crc, 16)

    def test_crc32_text_masks_a_negative_value(self):
        """zlib.crc32 is unsigned in Python 3 and was not always; the mask is cheap insurance."""
        self.assertEqual(common.crc32_text(-1), "FFFFFFFF")
        self.assertEqual(common.crc32_text(0), "00000000")

    def test_asking_for_a_subset_returns_only_that(self):
        got = common.digests_of_file(self.path("a.txt"), want=("sha256",))
        self.assertEqual(list(got), ["sha256"])

    def test_the_table_and_the_name_list_cannot_drift(self):
        self.assertEqual(sorted(common.DIGESTS), sorted(common.MANIFEST_FILES))


class TheSfvColumnsAreTheOtherWayRound(unittest.TestCase):
    """The one format hazard here, and the reason a writer and a reader live in one file."""

    def test_a_line_is_name_then_hash(self):
        self.assertEqual(common.sfv_line("DEADBEEF", "a/b.bin"), "a/b.bin DEADBEEF\n")

    def test_sha256sum_puts_them_the_other_way(self):
        """Stated side by side, because getting it backwards produces a plausible-looking file."""
        self.assertTrue(common.sums_line("ab" * 32, "a/b.bin").startswith("ab"))
        self.assertTrue(common.sfv_line("DEADBEEF", "a/b.bin").startswith("a/b.bin"))

    def test_what_we_write_is_what_we_read(self):
        """sfv_line and read_sfv are a pair; the round trip is the only thing that proves it."""
        rows = [("a/b.bin", "DEADBEEF"), ("has space.dat", "0D4A1185"), ("x.bin", "00000000")]
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "t.sfv")
            with io.open(p, "w", encoding="utf-8", newline="") as fh:
                for rel, crc in rows:
                    fh.write(common.sfv_line(crc, rel))
            self.assertEqual(common.read_sfv(p), rows)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_a_name_with_spaces_survives_the_round_trip(self):
        """The reason the reader splits from the right. A left split takes the first word."""
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "t.sfv")
            with io.open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(common.sfv_line("DEADBEEF", "two words three.bin"))
            self.assertEqual(common.read_sfv(p), [("two words three.bin", "DEADBEEF")])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_comments_and_junk_are_skipped_not_guessed_at(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "t.sfv")
            with io.open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write("; RHash wrote this\n\nshort.bin ABC\na.bin DEADBEEF\nb.bin ZZZZZZZZ\n")
            self.assertEqual(common.read_sfv(p), [("a.bin", "DEADBEEF")])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class ReadingBackWhatIsAlreadyThere(unittest.TestCase):
    """read_sums and read_manifests: the half that makes an incremental run possible.

    read_sums also replaces a separator written out by hand in four places before 2026-10-02.
    """

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def put(self, name, text):
        with io.open(os.path.join(self.d, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    # ---- read_sums --------------------------------------------------------------------------
    def test_a_missing_sums_file_is_empty_and_not_an_error(self):
        self.assertEqual(common.read_sums(os.path.join(self.d, "nothing")), {})

    def test_it_splits_on_the_binary_marker_and_not_on_whitespace(self):
        """The reason the separator belongs in one place: a path may contain spaces."""
        self.put("s", "%s *two words three.bin\n" % ("ab" * 20))
        self.assertEqual(common.read_sums(os.path.join(self.d, "s")),
                         {"two words three.bin": "ab" * 20})

    def test_a_path_containing_the_separator_itself_still_splits_at_the_first(self):
        """` *` can occur inside a filename. First occurrence wins, which is what GNU means."""
        self.put("s", "%s *odd *name.bin\n" % ("cd" * 20))
        self.assertEqual(list(common.read_sums(os.path.join(self.d, "s"))), ["odd *name.bin"])

    def test_a_gnu_escaped_line_is_skipped_rather_than_half_read(self):
        """A leading backslash means the path was escaped. Nothing here can produce one, so a
        file that carries one came from elsewhere and is better noticed than guessed at."""
        escaped = chr(92) + ("ef" * 20) + " *weird" + chr(92) + "name"
        self.put("s", escaped + "\n" + ("ab" * 20) + " *fine.bin\n")
        self.assertEqual(list(common.read_sums(os.path.join(self.d, "s"))), ["fine.bin"])

    def test_blank_and_malformed_lines_are_skipped(self):
        self.put("s", "\n\nnot a line\n" + ("ab" * 20) + " *fine.bin\n")
        self.assertEqual(list(common.read_sums(os.path.join(self.d, "s"))), ["fine.bin"])

    # ---- read_sfv ---------------------------------------------------------------------------
    def test_a_missing_sfv_is_empty_and_not_an_error(self):
        """THE BUG THE END-TO-END RUN FOUND. As sfv-verify.parse_sfv this function was only ever
        called on a path a person had typed, so a missing file was their mistake and an exception
        was right. read_manifests calls it on a name that does not exist yet -- the first index run
        of an archive has no .sfv -- and the whole run died on FileNotFoundError. Lifting a
        function into a library gives it callers with different preconditions."""
        self.assertEqual(common.read_sfv(os.path.join(self.d, "nothing.sfv")), [])

    # ---- read_manifests ---------------------------------------------------------------------
    def test_an_archive_with_no_manifests_reads_as_empty(self):
        self.assertEqual(common.read_manifests(self.d), {})

    def test_one_manifest_present_gives_one_algorithm(self):
        """The state every archive is in part-way through: some files, some algorithms."""
        self.put(common.MD5_FILE, "%s *a.txt\n" % ("0" * 32))
        self.assertEqual(common.read_manifests(self.d), {"a.txt": {"md5": "0" * 32}})

    def test_the_three_are_merged_per_path(self):
        self.put(common.MD5_FILE, "%s *a.txt\n" % ("0" * 32))
        self.put(common.SHA1_FILE, "%s *a.txt\n" % ("1" * 40))
        self.put(common.SFV_FILE, "a.txt DEADBEEF\n")
        self.assertEqual(common.read_manifests(self.d),
                         {"a.txt": {"md5": "0" * 32, "sha1": "1" * 40, "crc32": "DEADBEEF"}})

    def test_sha256_is_not_read_back_because_the_csv_is_its_master(self):
        self.put(common.SUMS_FILE, "%s *a.txt\n" % ("2" * 64))
        self.assertEqual(common.read_manifests(self.d), {})


class HashTreeCarriesThemOrDoesNot(unittest.TestCase):
    """The `digests` parameter: absent means the extra work is not done at all."""

    def setUp(self):
        self.t = Tree()
        self.entries = []
        for rel in sorted(BODIES):
            full = os.path.join(self.t.root, *rel.split("/"))
            st = os.stat(full)
            self.entries.append((rel, full, st.st_size, st.st_mtime_ns))

    def tearDown(self):
        self.t.close()

    def run_hash(self, digests):
        rows = {}
        common.hash_tree(self.entries, rows, workers=2, interval=10 ** 6,
                         checkpoint=lambda: None, digests=digests)
        return rows

    def test_without_the_argument_the_rows_are_unchanged_in_shape(self):
        rows = self.run_hash(None)
        for rel, value in rows.items():
            self.assertEqual(len(value), 3, rel)
            self.assertEqual(value[2], common.sha256_file(
                os.path.join(self.t.root, *rel.split("/"))), rel)

    def test_with_the_argument_the_rows_keep_the_same_shape(self):
        """The CSV keeps its four columns: widening it would break every reader of the 113
        indexes already on disk, for three values no verification here decides on."""
        fresh = {}
        rows = self.run_hash(fresh)
        for rel, value in rows.items():
            self.assertEqual(len(value), 3, rel)

    def test_and_the_four_digests_arrive_in_the_dict(self):
        fresh = {}
        self.run_hash(fresh)
        self.assertEqual(sorted(fresh), sorted(BODIES))
        for rel, got in fresh.items():
            self.assertEqual(sorted(got), sorted(common.DIGESTS), rel)

    def test_the_sha256_in_the_row_and_in_the_dict_are_the_same_value(self):
        """Two places, one read. If they could differ, the CSV and .md5sum would describe
        different bytes and nothing downstream could tell."""
        fresh = {}
        rows = self.run_hash(fresh)
        for rel in rows:
            self.assertEqual(rows[rel][2], fresh[rel]["sha256"], rel)


class FourManifestsOfOneTree(unittest.TestCase):

    def setUp(self):
        self.t = Tree()
        self.digests = self.t.digests()

    def tearDown(self):
        self.t.close()

    def test_it_writes_the_three_and_not_the_sha256_one(self):
        """sha256sum is derived from the CSV by write_index, which checkpoints mid-run."""
        common.write_manifests(self.t.root, self.digests)
        for name in (common.SHA1_FILE, common.MD5_FILE, common.SFV_FILE):
            self.assertTrue(os.path.exists(os.path.join(self.t.root, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.t.root, common.SUMS_FILE)))

    def test_every_manifest_covers_exactly_the_same_paths(self):
        """The agreement that makes four manifests evidence rather than four opinions."""
        common.write_manifests(self.t.root, self.digests)
        sha1 = {ln.split(" *", 1)[1] for ln in self.t.read(common.SHA1_FILE).splitlines()}
        md5 = {ln.split(" *", 1)[1] for ln in self.t.read(common.MD5_FILE).splitlines()}
        sfv = {rel for rel, _crc in
               common.read_sfv(os.path.join(self.t.root, common.SFV_FILE))}
        self.assertEqual(sha1, set(BODIES))
        self.assertEqual(md5, set(BODIES))
        self.assertEqual(sfv, set(BODIES))

    def test_the_values_are_the_ones_computed(self):
        common.write_manifests(self.t.root, self.digests)
        for line in self.t.read(common.MD5_FILE).splitlines():
            digest, rel = line.split(" *", 1)
            self.assertEqual(digest, self.digests[rel]["md5"], rel)

    def test_sha1sum_format_is_what_sha1sum_minus_c_expects(self):
        """`<hex> *<path>` with the binary marker, which is what this content is."""
        common.write_manifests(self.t.root, self.digests)
        for line in self.t.read(common.SHA1_FILE).splitlines():
            digest, sep, rel = line.partition(" *")
            self.assertEqual(sep, " *", line)
            self.assertEqual(len(digest), 40, line)
            self.assertIn(rel, BODIES)

    def test_lines_are_sorted_so_two_runs_produce_the_same_file(self):
        """A manifest that reorders itself makes every diff unreadable and every backup differ."""
        common.write_manifests(self.t.root, self.digests)
        first = self.t.read(common.MD5_FILE)
        common.write_manifests(self.t.root, dict(reversed(list(self.digests.items()))))
        self.assertEqual(self.t.read(common.MD5_FILE), first)

    def test_a_missing_digest_is_skipped_rather_than_written_blank(self):
        """A line with an empty hash passes `-c` on nothing and reads as a check that was made."""
        broken = dict(self.digests)
        broken["a.txt"] = {k: v for k, v in broken["a.txt"].items() if k != "md5"}
        common.write_manifests(self.t.root, broken)
        self.assertNotIn("a.txt", self.t.read(common.MD5_FILE))
        self.assertIn("a.txt", self.t.read(common.SHA1_FILE))

    def test_an_empty_manifest_is_NOT_written(self):
        """FOUND ON THE FIRST REAL ARCHIVE. csri-toronto's index was current, nothing was
        re-hashed, nothing was known -- and three empty files appeared beside a populated
        .sha256sum. `md5sum -c` over zero lines reports success: a clean zero that reads as a
        verification. An absent file says "not done yet" and cannot be mistaken for anything."""
        d = tempfile.mkdtemp()
        try:
            self.assertEqual(common.write_manifests(d, {}), [])
            self.assertEqual(os.listdir(d), [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_a_manifest_is_skipped_per_ALGORITHM_and_not_per_run(self):
        """One algorithm known and two not writes one file, not three."""
        d = tempfile.mkdtemp()
        try:
            common.write_manifests(d, {"a.txt": {"md5": "0" * 32}})
            self.assertEqual(os.listdir(d), [common.MD5_FILE])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_nothing_half_written_survives_a_crash(self):
        """Written to a temporary name and renamed: an interrupted write leaves the old file,
        not a shorter one that still looks like a manifest."""
        common.write_manifests(self.t.root, self.digests)
        leftovers = [n for n in os.listdir(self.t.root) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_the_three_names_are_bookkeeping_and_not_content(self):
        """Otherwise each is hashed into the index and reported as a change every single run."""
        for name in (common.SHA1_FILE, common.MD5_FILE, common.SFV_FILE):
            self.assertIn(name, common.OWN_FILES, name)

    def test_a_tree_walk_does_not_count_them(self):
        common.write_manifests(self.t.root, self.digests)
        self.assertEqual(sorted(rel for rel, _f in common.iter_tree(self.t.root)),
                         sorted(BODIES))


class SfvVerifyReadsWhatWeWrite(unittest.TestCase):
    """The loop closed: our .sfv, checked by the tool that was written to read other people's.

    sfv-verify.py had NO TEST of its own until 2026-10-02, the day its parser moved into the
    library -- so the move could have broken it silently, and the only thing that would have
    noticed was somebody verifying an archive by hand. The tool exists because
    `ia-bullfreeware` arrived with two RHash .sfv sets from before its upload; it now also has to
    read ours.
    """

    def setUp(self):
        self.t = Tree()
        common.write_manifests(self.t.root, self.t.digests())

    def tearDown(self):
        self.t.close()

    def verify(self, *extra):
        import subprocess
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "sfv-verify.py"),
             os.path.join(self.t.root, common.SFV_FILE), "--root", self.t.root] + list(extra),
            capture_output=True, text=True, cwd=HERE)
        return out.returncode, out.stdout + out.stderr

    def test_an_untouched_tree_verifies(self):
        code, out = self.verify()
        self.assertEqual(code, 0, out)

    def test_a_changed_byte_is_caught(self):
        """The whole point of a 32-bit check: a flipped bit, a truncated resume, an error page
        saved under a .zip name."""
        with io.open(os.path.join(self.t.root, "a.txt"), "wb") as fh:
            fh.write(b"HELLO WORLD")
        code, out = self.verify()
        self.assertNotEqual(code, 0)
        self.assertIn("a.txt", out)

    def test_a_file_that_went_missing_is_reported_and_not_passed_over(self):
        os.remove(os.path.join(self.t.root, "a.txt"))
        code, _out = self.verify()
        self.assertNotEqual(code, 0)


class TheIndexRunKeepsThemCurrent(unittest.TestCase):
    """Driven through mirror.py, because both bugs here were in the WIRING and not the writer.

    Each was found by hand on 2026-10-02, running the real thing against a synthetic tree before
    letting it near an archive. Neither would have been caught by testing write_manifests alone.
    """

    ARCHIVE = "tvsat-cpc710"          # a registered name; --archive is checked against the register

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.dir = os.path.join(self.root, self.ARCHIVE)
        os.makedirs(os.path.join(self.dir, "deep"))
        with io.open(os.path.join(self.root, common.ROOT_MARKER), "wb"):
            pass
        self.write("a.txt", b"hello world")
        self.write("deep/b b.bin", b"x")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, body):
        with io.open(os.path.join(self.dir, *rel.split("/")), "wb") as fh:
            fh.write(body)

    def index(self):
        import subprocess
        return subprocess.run(
            [sys.executable, os.path.join(HERE, "mirror.py"), "--root", self.root,
             "--archive", self.ARCHIVE, "--index"],
            capture_output=True, text=True, cwd=HERE).stdout

    def counts(self):
        out = {}
        for algo, name in common.MANIFEST_FILES.items():
            path = os.path.join(self.dir, name)
            if not os.path.exists(path):
                out[name] = None
                continue
            with io.open(path, encoding="utf-8") as fh:
                out[name] = len([ln for ln in fh.read().splitlines() if ln.strip()])
        return out

    def test_a_first_run_writes_all_four(self):
        self.index()
        self.assertEqual(set(self.counts().values()), {2})

    def test_an_INCREMENTAL_run_does_not_shrink_them(self):
        """THE FIRST BUG. An index run hashes only what changed, so writing the manifests from
        that run's own results would have cut them down to the one file re-hashed -- and the first
        incremental run after the one-time full pass would have discarded nearly everything."""
        self.index()
        self.write("c.txt", b"third")
        self.index()
        self.assertEqual(set(self.counts().values()), {3})

    def test_a_DELETED_file_falls_out_even_when_there_is_nothing_to_hash(self):
        """THE SECOND BUG, and the sharper one. With nothing to hash the function takes an early
        exit, and the manifests were updated only on the hashing path: .sha256sum dropped the
        deleted file and the other three went on naming it. The comment beside that exit already
        said why -- "a stale manifest listing files that no longer exist is worse than none" --
        written about the sums file, for three manifests that did not exist yet."""
        self.index()
        os.remove(os.path.join(self.dir, "a.txt"))
        self.index()
        self.assertEqual(set(self.counts().values()), {1})
        for name in common.MANIFEST_FILES.values():
            with io.open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                self.assertNotIn("a.txt", fh.read(), name)

    def test_it_says_so_when_only_part_of_the_tree_carries_them(self):
        """Every archive is in this state until the one-time full pass runs."""
        self.index()
        for name in (common.SHA1_FILE, common.MD5_FILE, common.SFV_FILE):
            os.remove(os.path.join(self.dir, name))
        self.assertIn("carry the weaker digests", self.index())


if __name__ == "__main__":
    unittest.main(verbosity=1)
