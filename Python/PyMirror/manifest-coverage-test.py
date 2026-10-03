# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Does anything notice a manifest that covers one file out of four thousand?

THE CASE, FOUND ON 2026-10-03 AND NOT BY A TOOL. nice-next carried an index of 4 540 files and a
.sha256sum of 4 540 -- and a .sha1sum, .md5sum and .sfv of ONE LINE EACH:

    e70d352339f73b6ee6c97d1a027ce072ec41e305 *developer/languages/c/_gcc-i386...README.html

One README had been fetched the day before, and an INCREMENTAL index run wrote the three weaker
manifests from just that file. read_manifests' read-back cannot carry over digests that were never
there, and those three manifests did not exist yet. build_index DOES print "N of M files carry the
weaker digests" when it notices; the line was printed and nobody acted on it.

A MANIFEST COVERING ONE FILE LOOKS EXACTLY LIKE A MANIFEST COVERING ALL OF THEM, and `md5sum -c`
over it reports success. That is what makes this worth a check rather than a warning.

AND WHAT HID IT AFTERWARDS WAS A CHECK OF MY OWN. Asked to confirm the collection-wide digest run,
I tested whether the four files EXIST. All 113 archives answered yes -- including this one. The
answer "113 / 113 complete" was wrong, and only a second pass that counted LINES found it.
Existence is not coverage.

NO NETWORK AND NO COLLECTION. Each case builds an archive of its own and throws it away.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402

MIRROR = os.path.join(HERE, "mirror.py")
KNOWN = "gsi-collection"      # a name mirror.py's ARCHIVES table knows, so --archive matches


class Archive(object):
    """A tree of real files, with whichever manifests the case wants written over it."""

    def __init__(self, count=4):
        self.root = tempfile.mkdtemp(prefix="cover-")
        self.path = os.path.join(self.root, KNOWN)
        os.makedirs(self.path)
        self.rels = []
        for i in range(count):
            rel = "f%d.bin" % i
            self.rels.append(rel)
            with io.open(os.path.join(self.path, rel), "wb") as fh:
                fh.write(("content %d" % i).encode("ascii"))

    def digests_for(self, rels):
        """-> {rel: {algo: hex}} computed the way the real writer computes them."""
        out = {}
        for rel in rels:
            out[rel] = common.digests_of_file(os.path.join(self.path, rel))
        return out

    def write_sha256(self):
        """`.sha256sum` IS NOT write_manifests' JOB and that is deliberate: it is derived from the
        CSV index, so the two can never disagree. A fixture that forgets this reports sha256 as 0
        for a complete archive -- which is what the first draft of this file asserted against, and
        the mistake was mine rather than the function's."""
        rows = {}
        for rel in self.rels:
            full = os.path.join(self.path, rel)
            st = os.stat(full)
            rows[rel] = (st.st_size, st.st_mtime_ns,
                         common.digests_of_file(full, want=("sha256",))["sha256"])
        common.write_index(os.path.join(self.path, common.INDEX_FILE),
                           os.path.join(self.path, common.SUMS_FILE), rows)

    def write_all(self):
        self.write_sha256()
        common.write_manifests(self.path, self.digests_for(self.rels))

    def write_only_one(self):
        """THE nice-next SHAPE: full sha256, and the other three holding a single file."""
        self.write_sha256()
        common.write_manifests(self.path, self.digests_for(self.rels))
        thin = self.digests_for(self.rels[:1])
        for algo in ("sha1", "md5", "crc32"):
            path = os.path.join(self.path, common.MANIFEST_FILES[algo])
            with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
                rel = self.rels[0]
                if algo == "crc32":
                    fh.write(common.sfv_line(thin[rel]["crc32"], rel))
                else:
                    fh.write(common.sums_line(thin[rel][algo], rel))

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class WhatAManifestActuallyCovers(unittest.TestCase):

    def test_no_manifest_at_all_is_zero_and_not_an_error(self):
        """An archive indexed before the weaker digests existed is the common case, not a fault."""
        a = Archive()
        try:
            self.assertEqual(common.manifest_coverage(a.path),
                             {"sha256": 0, "sha1": 0, "md5": 0, "crc32": 0})
        finally:
            a.close()

    def test_sha256_alone_is_what_every_archive_looked_like_before_2026_10_02(self):
        """And it must read as 4/0/0/0 rather than as complete: that state is exactly what the
        one-time full pass existed to leave behind."""
        a = Archive(count=4)
        try:
            a.write_sha256()
            self.assertEqual(common.manifest_coverage(a.path),
                             {"sha256": 4, "sha1": 0, "md5": 0, "crc32": 0})
        finally:
            a.close()

    def test_all_four_written_cover_every_file(self):
        a = Archive(count=4)
        try:
            a.write_all()
            self.assertEqual(common.manifest_coverage(a.path),
                             {"sha256": 4, "sha1": 4, "md5": 4, "crc32": 4})
        finally:
            a.close()

    def test_THE_NICE_NEXT_SHAPE_IS_VISIBLE(self):
        """The whole point. Four files, sha256 covering all four, the rest covering one."""
        a = Archive(count=4)
        try:
            a.write_only_one()
            self.assertEqual(common.manifest_coverage(a.path),
                             {"sha256": 4, "sha1": 1, "md5": 1, "crc32": 1})
        finally:
            a.close()

    def test_a_missing_archive_directory_does_not_raise(self):
        """Same precondition read_sfv and read_sums already answer for: a caller may ask about a
        path that is not there, and a reader that raises makes every caller guard."""
        self.assertEqual(common.manifest_coverage(os.path.join(tempfile.gettempdir(), "nope-x")),
                         {"sha256": 0, "sha1": 0, "md5": 0, "crc32": 0})

    def test_it_counts_the_crc32_file_too_and_not_only_the_sums(self):
        """The .sfv has its columns REVERSED against the sum files -- `<path> <hash>` -- so it
        needs its own reader, and an implementation that forgot that would report crc32 as 0 for
        a complete archive."""
        a = Archive(count=3)
        try:
            a.write_all()
            self.assertEqual(common.manifest_coverage(a.path)["crc32"], 3)
        finally:
            a.close()


class VerifySaysSo(unittest.TestCase):
    """The report, because a library function nobody calls is not a check."""

    def run_verify(self, root):
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = tempfile.gettempdir()
        env.pop("MIRROR_ROOT", None)
        p = subprocess.run([sys.executable, MIRROR, "--root", root, "--verify",
                            "--archive", KNOWN],
                           capture_output=True, env=env)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")

    def marked(self, a):
        n, total = common.scan_tree(a.path)
        common.write_marker(os.path.join(a.path, common.COMPLETE_MARKER),
                            {"archive": KNOWN, "files": str(n), "bytes": str(total)},
                            "This mirror is complete.")

    def test_a_complete_set_is_reported_as_covering_the_tree(self):
        a = Archive(count=4)
        try:
            a.write_all()
            self.marked(a)
            code, out = self.run_verify(a.root)
            self.assertEqual(code, 0, out)
            self.assertIn("all four cover the tree", out)
        finally:
            a.close()

    def test_A_THIN_MANIFEST_IS_NAMED_WITH_ITS_NUMBERS(self):
        a = Archive(count=4)
        try:
            a.write_only_one()
            self.marked(a)
            _code, out = self.run_verify(a.root)
            self.assertIn("sha1 covers 1 of 4", out)
            self.assertIn("md5 covers 1 of 4", out)
            self.assertIn("crc32 covers 1 of 4", out)
            self.assertNotIn("sha256 covers", out)
            self.assertIn("--index-force", out)
        finally:
            a.close()

    def test_A_THIN_MANIFEST_IS_NOT_A_MISMATCH(self):
        """--verify answers "is the tree still what the marker says". A thin manifest is a gap in
        OUR bookkeeping, not a change in the archive, and failing on it would turn every archive
        indexed before the weaker digests existed into a MISMATCH -- burying the one finding this
        pass is for. The line is printed; the exit code stays 0."""
        a = Archive(count=4)
        try:
            a.write_only_one()
            self.marked(a)
            code, out = self.run_verify(a.root)
            self.assertEqual(code, 0, out)
            self.assertIn("UNCHANGED", out)
        finally:
            a.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
