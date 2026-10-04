# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Walking a source's own listings, and keeping the operator's inventory when it is split up.

TWO THROWAWAY SCRIPTS BECOME TWO TOOLS. Both were written in a temporary directory, used once, and
produced findings that changed what this collection holds -- which is the argument for them being
here rather than there.

listing-to-urllist.py grew out of measuring retro-digitalvintage's `OEMINFO/` and `ROM Archive/`.
Those two branches had sat in EXCLUDE since 2026-09-27 marked "not reached at all", on the
reputation of the branch beside them -- `Jumper Reference/`, which really does cost ~100 000 page
requests for ~42 000 files. A walk of 38 plain Apache directories said 22.1 MB and 62.3 MB, and
taking them cost five minutes. The figure was the only thing missing.

find-sitemaps.py --save grew out of closing zx-sgi-freeware-old. ftp.zx.net.nz publishes its
inventory as an INDEX over 27 parts; saving `sitemap.xml` would have stored a list of urls and none
of the inventory. Two of those 27 name this archive's paths, and they are the evidence that closed
it at 5 699 of 5 699.

NO NETWORK: walk() takes its fetcher by injection.
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

LISTING = common.load_peer("listing-to-urllist.py", "_listing", HERE)


def page(*hrefs):
    rows = "".join("<tr><td><a href=\"%s\">%s</a></td><td>12K</td></tr>" % (h, h) for h in hrefs)
    return "<html><body><table>" + rows + "</table></body></html>"


class Fake(object):
    """A server made of a dict: path -> listing body."""

    def __init__(self, tree):
        self.tree = tree
        self.asked = []

    def http_try(self, url, timeout=None, limit=None):
        self.asked.append(url)
        for path, body in self.tree.items():
            if url.endswith(path):
                return (200, body.encode("utf-8"), "fake")
        return (404, b"", "fake")


def patched(fake, fn):
    saved = LISTING.http_try
    LISTING.http_try = fake.http_try
    try:
        return fn()
    finally:
        LISTING.http_try = saved


class ItWalksOnlyListings(unittest.TestCase):

    def run_walk(self, fake, branch="", cap=2000):
        return patched(fake, lambda: LISTING.walk("http://x.invalid/", branch,
                                                  common.Pacer(0.0), cap, report=lambda _m: None))

    def test_one_directory_of_files(self):
        f = Fake({"/": page("a.pdf", "b.pdf")})
        files, pages = self.run_walk(f)
        self.assertEqual(sorted(files), ["a.pdf", "b.pdf"])
        self.assertEqual(pages, 1)

    def test_it_follows_a_subdirectory_and_counts_the_request(self):
        f = Fake({"invalid/": page("sub/"), "sub/": page("c.pdf")})
        files, pages = self.run_walk(f)
        self.assertEqual(files, ["sub/c.pdf"])
        self.assertEqual(pages, 2)

    def test_a_link_out_of_the_tree_is_not_a_child(self):
        """`..` is the way out, `?` is a sort order on a generated index, and an absolute url or a
        fragment is the listing talking about something else."""
        f = Fake({"/": page("../up.pdf", "?C=N;O=D", "/root.pdf", "http://other/x", "#top",
                            "keep.pdf")})
        files, _pages = self.run_walk(f)
        self.assertEqual(files, ["keep.pdf"])

    def test_a_directory_is_walked_once_even_if_linked_twice(self):
        f = Fake({"invalid/": page("sub/", "sub/"), "sub/": page("c.pdf")})
        _files, pages = self.run_walk(f)
        self.assertEqual(pages, 2)

    def test_THE_CAP_IS_A_BRAKE_AND_SAYS_SO(self):
        """retro-digitalvintage's Jumper Reference/ still had 99 000 pages queued after it had
        stopped yielding new files. A walk without a brake spends a day on that."""
        tree = {"invalid/": page(*["d%d/" % i for i in range(50)])}
        for i in range(50):
            tree["d%d/" % i] = page("f.pdf")
        f = Fake(tree)
        said = []
        files, pages = patched(f, lambda: LISTING.walk(
            "http://x.invalid/", "", common.Pacer(0.0), 5, report=said.append))
        self.assertEqual(pages, 5)
        self.assertIn("STOPPED at --max-dirs 5", "\n".join(said))
        self.assertIn("FLOOR", "\n".join(said))

    def test_a_directory_that_does_not_answer_is_SAID(self):
        """A hole in this list is what a later fetch calls complete."""
        f = Fake({"invalid/": page("good/", "bad/"), "good/": page("a.pdf")})
        said = []
        patched(f, lambda: LISTING.walk("http://x.invalid/", "", common.Pacer(0.0), 99,
                                        report=said.append))
        self.assertIn("bad/", "\n".join(said))

    def test_it_writes_nothing_into_the_collection(self):
        """The output is a url list for manifest-fetch.py, which is the tool that may write."""
        with io.open(os.path.join(HERE, "listing-to-urllist.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("write_marker", src)
        self.assertNotIn("record_gone", src)


class TheOutputIsForTheNextTool(unittest.TestCase):

    def test_it_writes_absolute_urls_one_per_line_and_names_the_next_command(self):
        d = tempfile.mkdtemp(prefix="l2u-")
        try:
            out = os.path.join(d, "sub", "list.txt")
            env = dict(os.environ)
            env["PYTHONPYCACHEPREFIX"] = tempfile.gettempdir()
            p = subprocess.run([sys.executable, os.path.join(HERE, "listing-to-urllist.py"),
                                "--base", "http://nothing.invalid/", "--out", out,
                                "--delay", "0", "--max-dirs", "1"],
                               capture_output=True, text=True, env=env)
            text = p.stdout + p.stderr
            self.assertIn("NEXT: manifest-fetch.py", text)
            # The directory is created rather than refused: a caller naming logs/ on a fresh
            # machine should not have to make it first.
            self.assertTrue(os.path.isfile(out), text)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_it_names_THE_TWO_TOOLS_IT_IS_NOT(self):
        """measure-remote.py crawls pages AND listings to estimate a SIZE; pages-to-urllist.py
        reads pages ALREADY ON DISK and costs no requests. Confusing this one with the first is how
        a 38-request branch becomes a 100 000-request one.

        READ FROM THE MODULE DOCSTRING and not from --help, because argparse is given only
        `__doc__.split("
")[0]` here -- the first draft of this case asserted against --help and
        failed, which is a test being wrong about where this project keeps its reasoning."""
        mod = common.load_peer("listing-to-urllist.py", "_l2u_doc", HERE)
        self.assertIn("measure-remote.py", mod.__doc__)
        self.assertIn("pages-to-urllist.py", mod.__doc__)


class AnIndexIsNotOneFile(unittest.TestCase):
    """find-sitemaps.py --save, for a host whose inventory is split over parts."""

    def source(self):
        with io.open(os.path.join(HERE, "find-sitemaps.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_a_part_is_kept_only_when_it_names_this_base(self):
        src = self.source()
        self.assertIn("if any(under_site(loc, base) is not None for loc in got):", src)
        self.assertIn("kept_parts.append(", src)

    def test_the_parts_go_into_a_sitemap_directory_beside_the_tree(self):
        self.assertIn('os.path.join(archive_dir, "sitemap")', self.source())

    def test_a_single_sitemap_still_lands_as_sitemap_xml(self):
        """The common case must not change: 20 of the 22 archives that publish one publish a
        single file, and openpa's is stored exactly that way."""
        self.assertIn('dest = os.path.join(archive_dir, "sitemap.xml")', self.source())

    def test_the_part_name_is_made_storable(self):
        """A part url's last segment becomes a filename, and it is not ours to trust."""
        self.assertIn("safe_name(urllib.parse.unquote(part_url.rsplit(", self.source())

    def test_it_says_how_many_of_how_many_it_wrote(self):
        """`[saved 0 of 3]` on a re-run is the useful answer -- it means the evidence is already
        held, not that nothing happened."""
        self.assertIn("saved %d of %d into sitemap/", self.source())


if __name__ == "__main__":
    unittest.main(verbosity=2)
