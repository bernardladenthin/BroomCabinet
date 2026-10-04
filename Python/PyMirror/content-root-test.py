# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Where do an archive's files actually live, when the base URL does not say?

FOUR ARCHIVES KEEP A HOST DIRECTORY LEVEL. A wayback salvage and a multi-host fetch write
`<host>/<path>`, so the tree carries a level the registered base says nothing about:

    aixpdslib        aixpdslib.seas.ucla.edu/ + ftp.aixpdslib.seas.ucla.edu/
    bullfreeware     bullfreeware.com/ + gnome.bullfreeware.com/   (base says www.)
    ibm-openxl-docs  ibm.com/                                      (base says www.)
    techsysadm       techsysadm.blogspot.com/ + blogger.googleusercontent.com/

WHAT IT COST, 2026-10-04. techsysadm's completeness check reported 402 paths outstanding. It
mapped `https://techsysadm.blogspot.com/2025/09/x.html` onto `<archive>/2025/09/x.html` while the
file sits at `<archive>/techsysadm.blogspot.com/2025/09/x.html`. 199 of those 203 pages were HELD.
Four were genuinely absent.

A CHECK WRONG BY A FACTOR OF FIFTY CANNOT DECIDE WHETHER AN ARCHIVE MAY BE FROZEN, which is the
only reason this matters: the next step for these mirrors is a solid archive that is never
modified again.

AND THE FETCHER HAD THE SAME GAP. manifest-fetch.py wrote those four pages to `techsysadm/p/`,
beside `techsysadm/techsysadm.blogspot.com/` rather than inside it, and they had to be moved by
hand. A fetch that puts a file next to the tree instead of in it is worse than one that fails: the
file is there, the check cannot see it, and the next survey fetches it again.

NO NETWORK AND NO COLLECTION.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402


class Tree(object):
    """An archive directory with whichever top-level directories the case wants."""

    def __init__(self, dirs=()):
        self.root = tempfile.mkdtemp(prefix="contentroot-")
        self.path = os.path.join(self.root, "an-archive")
        os.makedirs(self.path)
        for d in dirs:
            os.makedirs(os.path.join(self.path, *d.split("/")))

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class WhereTheBasesPathsLive(unittest.TestCase):

    def test_an_ordinary_archive_answers_with_itself(self):
        """The common case, and it must stay cheap and boring: no host directory, no change."""
        t = Tree(dirs=("pub", "docs"))
        try:
            self.assertEqual(common.content_root(t.path, "https://example.org/"), t.path)
        finally:
            t.close()

    def test_A_HOST_DIRECTORY_IS_FOUND(self):
        t = Tree(dirs=("example.org", "other.example.net"))
        try:
            self.assertEqual(common.content_root(t.path, "https://example.org/"),
                             os.path.join(t.path, "example.org"))
        finally:
            t.close()

    def test_BOTH_SPELLINGS_ARE_TRIED(self):
        """bullfreeware is registered on `www.bullfreeware.com` and its tree says
        `bullfreeware.com`. A salvage writes the host it actually fetched, which need not be the
        spelling somebody typed into the register."""
        t = Tree(dirs=("example.org",))
        try:
            self.assertEqual(common.content_root(t.path, "https://www.example.org/"),
                             os.path.join(t.path, "example.org"))
        finally:
            t.close()
        t = Tree(dirs=("www.example.org",))
        try:
            self.assertEqual(common.content_root(t.path, "https://example.org/"),
                             os.path.join(t.path, "www.example.org"))
        finally:
            t.close()

    def test_a_directory_named_after_ANOTHER_host_is_not_taken(self):
        """An archive may legitimately hold a subtree of somebody else's site. Only the base's own
        host counts, so a `cdn.example.net/` folder inside an example.org mirror is content."""
        t = Tree(dirs=("cdn.example.net", "pub"))
        try:
            self.assertEqual(common.content_root(t.path, "https://example.org/"), t.path)
        finally:
            t.close()

    def test_the_deeper_level_is_only_one_deep(self):
        """It resolves ONE host level, not a chain. Nothing in the collection nests two, and a
        recursive search would turn a coincidence into a wrong answer."""
        t = Tree(dirs=("example.org/example.org",))
        try:
            got = common.content_root(t.path, "https://example.org/")
            self.assertEqual(got, os.path.join(t.path, "example.org"))
        finally:
            t.close()

    def test_a_missing_archive_directory_answers_with_itself(self):
        """Callers ask about paths that do not exist yet -- the first fetch of a new archive."""
        gone = os.path.join(tempfile.gettempdir(), "no-such-archive-xyz")
        self.assertEqual(common.content_root(gone, "https://example.org/"), gone)

    def test_a_base_with_no_host_answers_with_itself(self):
        """rsync modules and local paths reach this function too."""
        t = Tree(dirs=("pub",))
        try:
            for base in ("", None, "rsync://", "not a url"):
                self.assertEqual(common.content_root(t.path, base), t.path, repr(base))
        finally:
            t.close()


class EveryToolThatMapsAUrlToAPathUsesIt(unittest.TestCase):
    """THREE TOOLS, ONE RESOLUTION. Two checks and one fetcher had to agree, and when they did not
    the fetcher wrote outside the tree the checks were reading."""

    TOOLS = ("pages-to-urllist.py", "find-sitemaps.py", "manifest-fetch.py")

    def source(self, name):
        with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def test_each_one_calls_content_root(self):
        for name in self.TOOLS:
            self.assertIn("content_root(", self.source(name), name)

    def test_the_fetcher_says_so_when_it_applies(self):
        """Silently writing somewhere other than the archive root is how this went unnoticed; the
        line is cheap and a reader of the log can see which tree was written."""
        self.assertIn("keeps a host directory level", self.source("manifest-fetch.py"))

    def test_the_four_known_archives_are_still_registered_that_way(self):
        """If one is ever re-fetched flat, this case stops meaning anything -- better that it says
        so by failing than that it keeps passing for the wrong reason."""
        mirror = common.load_mirror(HERE)
        if mirror is None:
            self.skipTest("mirror.py not readable")
        bases = dict(mirror.ARCHIVES)
        for name in ("aixpdslib", "bullfreeware", "ibm-openxl-docs", "techsysadm"):
            self.assertIn(name, bases, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
