# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Does one archive's failed index write stop the whole --index run, and what does a crashed
write leave behind?

THIS IS NOT A DEFECT REPORT, and saying so matters more than the fix. On 2026-10-03 the
collection-wide four-digest pass died at archive 54 of 113 with

    PermissionError: [WinError 5] Zugriff verweigert:
      Q:\mirror\ibm-redbooks\.mirror-index.csv.tmp -> .mirror-index.csv

and the cause was A STATUS QUERY OF MY OWN running at that second, which had every archive's
`.mirror-index.csv` open for reading. Windows will not replace a file another process holds open.
mirror.py behaved correctly and os.replace cannot do otherwise; a progress check destroyed the
work it was measuring.

WHAT THE INCIDENT EXPOSED IS REAL ANYWAY, and both halves would fire without anybody's help:

  * ANY transient lock -- a virus scanner, a backup, the Windows Search indexer, an open editor --
    ends a seven-hour run over 113 archives, and the 59 after the failure never get their sha1,
    md5 or crc32. The branch for --verify a few lines further down already carried this exact
    lesson: "one unverifiable archive used to end the run and leave every later mirror
    unchecked". It was never applied to --index.
  * ANY interrupted index write -- power loss, Ctrl-C, a full volume -- leaves `<name>.tmp` on
    disk, and that name was in NEITHER bookkeeping set. The first re-run counted 331 KB of our own
    scratch as content: ibm-redbooks went from 2 871 files to 2 872, in the index AND in all four
    manifests, and had to be repaired by hand.

NO NETWORK AND NO COLLECTION. Each case builds a root of its own and throws it away.
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
# Two names mirror.py's ARCHIVES table knows, so --archive matches both. --index never reaches the
# network, so which two does not matter.
FIRST = "gsi-collection"
SECOND = "csri-toronto"


def run(*args):
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = tempfile.gettempdir()
    env.pop("MIRROR_ROOT", None)
    p = subprocess.run([sys.executable, MIRROR] + list(args), capture_output=True, env=env)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


class Root(object):
    """A root with two archives, each holding one real file."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="indexres-")
        for name in (FIRST, SECOND):
            d = os.path.join(self.root, name)
            os.makedirs(d)
            with io.open(os.path.join(d, "content.bin"), "wb") as fh:
                fh.write(b"x" * 64)

    def block_index_of(self, archive):
        """Make the index unwritable in the one way that needs no permissions at all: put a
        DIRECTORY where the file belongs. os.replace onto a non-empty directory raises OSError on
        every platform, which is what a held-open file does on Windows -- the same failure, got
        portably and without touching an access-control list."""
        d = os.path.join(self.root, archive, common.INDEX_FILE)
        os.makedirs(d)
        with io.open(os.path.join(d, "keep"), "wb") as fh:
            fh.write(b"so the directory cannot be replaced")

    def index_of(self, archive):
        return os.path.join(self.root, archive, common.INDEX_FILE)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class OneArchivesFailureIsNotTheRuns(unittest.TestCase):

    def test_both_archives_are_indexed_when_nothing_is_wrong(self):
        """The control. Without it, a test that sees one index cannot tell success from the bug."""
        r = Root()
        try:
            code, out = run("--root", r.root, "--archive", FIRST, "--archive", SECOND, "--index")
            self.assertEqual(code, 0, out)
            self.assertTrue(os.path.isfile(r.index_of(FIRST)), out)
            self.assertTrue(os.path.isfile(r.index_of(SECOND)), out)
        finally:
            r.close()

    def test_THE_SECOND_ARCHIVE_IS_STILL_INDEXED_AFTER_THE_FIRST_FAILS(self):
        """The case. Before 2026-10-03 the traceback ended the process here."""
        r = Root()
        try:
            r.block_index_of(FIRST)
            _code, out = run("--root", r.root, "--archive", FIRST, "--archive", SECOND, "--index")
            self.assertTrue(os.path.isfile(r.index_of(SECOND)),
                            "the archive after the failure got no index:\n" + out)
            self.assertNotIn("Traceback", out)
        finally:
            r.close()

    def test_it_exits_NON_ZERO_so_a_partial_pass_cannot_read_as_a_complete_one(self):
        r = Root()
        try:
            r.block_index_of(FIRST)
            code, _out = run("--root", r.root, "--archive", FIRST, "--archive", SECOND, "--index")
            self.assertNotEqual(code, 0)
        finally:
            r.close()

    def test_the_failed_archive_is_named_twice(self):
        """Once where it happens and once at the end: in a run over 113 archives the first line
        scrolls away hours before the run finishes."""
        r = Root()
        try:
            r.block_index_of(FIRST)
            _code, out = run("--root", r.root, "--archive", FIRST, "--archive", SECOND, "--index")
            self.assertGreaterEqual(out.count(FIRST), 2, out)
            self.assertIn("did NOT get an index", out)
        finally:
            r.close()

    def test_only_OSError_is_caught(self):
        """A permission error, a full volume or a vanished directory is a fact about one archive.
        Anything else is a defect in this program and must still stop it, so the except clause
        names OSError rather than Exception."""
        with io.open(MIRROR, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("except OSError as e:", src)


class OurOwnScratchNamesAreNotContent(unittest.TestCase):
    """`<name>.tmp` for every file mirror.py writes itself."""

    def test_the_index_tmp_is_recognised(self):
        self.assertIn(common.INDEX_FILE + ".tmp", common.OWN_FILES)
        self.assertIn(common.INDEX_FILE + ".tmp", common.BOOKKEEPING_FILES)

    def test_every_manifest_tmp_is_recognised(self):
        for name in common.MANIFEST_FILES.values():
            self.assertIn(name + ".tmp", common.OWN_FILES, name)

    def test_A_MIRRORED_FILE_CALLED_TMP_IS_STILL_CONTENT(self):
        """THE REASON `.tmp` WAS NOT ADDED TO PARTIAL_SUFFIXES, which was the shorter change and
        the wrong one. A mirrored archive is free to hold a real file named something.tmp, and
        this collection exists to keep such files rather than to hide them."""
        for name in ("setup.tmp", "DRIVER.TMP", "x.tar.tmp"):
            self.assertNotIn(name, common.OWN_FILES, name)
            self.assertNotIn(name, common.BOOKKEEPING_FILES, name)
            self.assertFalse(common.is_partial(name), name)

    def test_it_is_DERIVED_so_a_later_manifest_is_covered_by_arriving(self):
        """Listing the names by hand is how .mirror-index.csv.tmp came to be missing in the first
        place: four manifest names were added on 2026-10-02 and not one of their tmp siblings."""
        for name in common.OWN_FILES:
            if name.endswith(".tmp"):
                self.assertIn(name[:-4], common.OWN_FILES, name)

    def test_a_tree_walk_skips_it_and_so_a_marker_cannot_count_it(self):
        """The behaviour the hand repair of ibm-redbooks had to undo."""
        d = tempfile.mkdtemp(prefix="indexres-own-")
        try:
            for name in ("real.bin", common.INDEX_FILE + ".tmp"):
                with io.open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"x")
            counted = sorted(rel for rel, _f in common.iter_tree(d))
            self.assertEqual(counted, ["real.bin"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
