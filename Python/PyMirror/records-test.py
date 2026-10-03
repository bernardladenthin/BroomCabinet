#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Three corrections of 2026-10-02, each pinned so it cannot come back.

None of the three was found by a test. Each was found by reading what a tool had just written and
not believing it, which is the opposite of a ratchet -- hence this file.

  1. A REPAIR RECORDED UNDER THE WRONG DATE. remove-fragment-copies.py had "2026-09-13" written
     into two strings: the day it was authored. A removal performed on 2026-10-02 was therefore
     recorded in an archive's own marker as having happened three weeks earlier. The marker is what
     somebody reads in a year, and `completed` beside it is deliberately NOT touched precisely so
     that the two dates mean different things -- which makes a wrong second date worse than none.

  2. A RECORD FILE COUNTED AS CONTENT. FRAGMENT-COPIES-REMOVED.txt was in neither bookkeeping set,
     while the tool's own docstring calls it "the same reasoning as RENAMED.txt beside an extracted
     tree" -- and RENAMED.txt is in the wide set. Four archives carry one.

  3. THE SAME SITE UNDER ANOTHER SPELLING, FOR THE THIRD TIME IN ONE DAY. manifest-fetch.py still
     tested its url list against the base with a plain startswith. The first list that met it was
     zx-sgi-freeware-old's: the sitemap writes https, the archive is registered on http, and all
     4 404 urls were reported OUTSIDE THE BASE. The run ended "0 paths, 0 missing, DONE fetched 0"
     -- a clean zero that read as nothing to do. pages-to-urllist.py and find-sitemaps.py had both
     been fixed hours earlier; this one was overlooked.

No network. Everything happens in a temporary directory.
"""
import datetime
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402


def load(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FRAGMENTS = load("remove-fragment-copies")


class ARepairIsDatedWhenItHappened(unittest.TestCase):

    def test_today_is_today(self):
        self.assertEqual(FRAGMENTS.today(), datetime.date.today().isoformat())

    def run_a_removal(self):
        """Build an archive with one fragment duplicate, remove it, -> (marker text, record text).

        TESTED THROUGH THE BEHAVIOUR AND NOT THE SOURCE, after two source-reading attempts failed
        for reasons that had nothing to do with the defect: the first searched the whole file and
        tripped over the incident named in a comment, the second stripped comments by splitting on
        '#' -- and every string this tool writes CONTAINS a '#'. A test that inspects source text
        fails on how the source is written. This one fails only if the wrong date is written.
        """
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        archive = "tvsat-cpc710"
        base = os.path.join(root, archive)
        os.makedirs(base)
        for name in ("page.html", "page.html#anchor"):
            with io.open(os.path.join(base, name), "wb") as fh:
                fh.write(b"the same bytes")
        with io.open(os.path.join(base, common.COMPLETE_MARKER), "w", encoding="utf-8") as fh:
            fh.write("archive       %s\nfiles         2\nbytes         28\n\nprose.\n" % archive)
        subprocess.run(
            [sys.executable, os.path.join(HERE, "remove-fragment-copies.py"),
             "--root", root, "--archive", archive, "--delete"],
            capture_output=True, text=True, cwd=HERE)
        out = []
        for name in (common.COMPLETE_MARKER, "FRAGMENT-COPIES-REMOVED.txt"):
            p = os.path.join(base, name)
            with io.open(p, encoding="utf-8") as fh:
                out.append(fh.read())
        return out

    def test_the_marker_and_the_record_both_carry_TODAY(self):
        """Two strings carried the constant, and fixing one would have left the other lying --
        which is what happened on the first attempt here: one substitution was asserted and two
        were not, so they failed silently and the tool went on writing 2026-09-13."""
        marker, record = self.run_a_removal()
        today = datetime.date.today().isoformat()
        self.assertIn("REMOVED %s:" % today, marker)
        self.assertIn("removed %s because" % today, record)

    def test_and_neither_carries_the_old_constant(self):
        for text in self.run_a_removal():
            self.assertNotIn("2026-09-13", text)

    def test_the_duplicate_really_went_and_the_document_stayed(self):
        """A date test over a removal that did not happen would pass on nothing."""
        marker, record = self.run_a_removal()
        self.assertIn("page.html#anchor", record)
        self.assertIn("-> page.html", record)
        self.assertIn("1 files saved under a URL fragment", marker)

    def test_the_marker_counts_the_record_it_just_wrote(self):
        """Not an oversight -- the convention. A marker goes through the NARROW own-file set, and
        RENAMED.txt, SYMLINKS.txt and EXTRACTED-FROM.md are all in the WIDE one only, so every
        archive's marker counts its own hand-written notes as content. ardent-tool's 25 818 does.
        This test exists because the first draft asserted `files 1` and was wrong about the
        collection rather than about the tool.
        """
        marker, _record = self.run_a_removal()
        self.assertIn("files         2", marker)     # page.html + the record
        self.assertNotIn("bytes         28", marker)  # rewritten from the tree, not left stale


class ARecordFileIsNotContent(unittest.TestCase):

    NAME = "FRAGMENT-COPIES-REMOVED.txt"

    def test_an_auditor_skips_it(self):
        self.assertIn(self.NAME, common.BOOKKEEPING_FILES)

    def test_a_marker_does_NOT(self):
        """THE WIDE SET ONLY, and this is the assertion that makes the change safe. Markers go
        through iter_tree, which skips the NARROW set; adding the name there would move four
        markers by one file each -- and those four were rewritten from the tree the same day and
        agree with it."""
        self.assertNotIn(self.NAME, common.OWN_FILES)

    def test_it_sits_beside_the_precedent_it_was_argued_from(self):
        """RENAMED.txt is the shape the tool's docstring appeals to. If that one ever moved to the
        narrow set, this one's reasoning would have moved with it."""
        self.assertIn("RENAMED.txt", common.BOOKKEEPING_FILES)
        self.assertNotIn("RENAMED.txt", common.OWN_FILES)

    def test_a_tree_walk_still_counts_it_and_an_audit_does_not(self):
        d = tempfile.mkdtemp()
        try:
            for name in ("real.bin", self.NAME):
                with io.open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"x")
            counted = sorted(rel for rel, _f in common.iter_tree(d))
            audited = sorted(rel for rel, _f in
                             common.iter_tree(d, own_files=common.BOOKKEEPING_FILES))
            self.assertEqual(counted, [self.NAME, "real.bin"])
            self.assertEqual(audited, ["real.bin"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class ToolsConnectToTheHostTheBaseNamesAndPaceOnTheFoldedOne(unittest.TestCase):
    """host_of() folds `www.` away. That is right for PACING and wrong for CONNECTING.

    Two archives share one operator when one is spelled `example.org` and the other
    `www.example.org`, and they should share one rate -- that is what the folding is for. But the
    folded name NEED NOT EXIST. Five archives here are registered on a `www.` host whose apex does
    not resolve at all: cmu-shadow, rs6000-microcode, crashing-org-www, sun3arc and
    dreamlandbbs-os2.

    THE SAME DEFECT, IN TWO TOOLS, FOUND A DAY APART. recheck-decisions.py had it and was fixed on
    2026-10-02 with the reason written into its source. find-sitemaps.py had it too and was not
    looked at, so on 2026-10-03 it reported

        dreamlandbbs-os2   no answer (URLError)

    for an archive whose robots.txt answers a clean 404 -- it had asked `dreamlandbbs.com`, which
    does not resolve. Five archives carried a false verdict. None of the five turned out to
    publish a sitemap, so nothing was hidden, but the verdicts were untrue.

    This test exists because fixing one tool and writing a careful comment in it is not a check on
    the next tool. A rule that two files have to follow belongs in a test that reads both.
    """

    TOOLS = ("find-sitemaps.py", "recheck-decisions.py")

    def source(self, name):
        with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def test_each_tool_connects_to_the_hostname_from_the_base(self):
        for name in self.TOOLS:
            self.assertIn("urlsplit(base).hostname", self.source(name), name)

    def test_and_none_of_them_connects_to_the_folded_name(self):
        """`host_of(base)` may appear -- for pacing -- but never as the thing a url is built from.

        The check is textual and therefore coarse; it is a ratchet against the exact shape that
        failed twice, not a proof. What failed was a root url interpolated from the folded name.
        """
        for name in self.TOOLS:
            src = self.source(name)
            for bad in ('"%s://%s/" % (urllib.parse.urlsplit(base).scheme, host_of(base))',
                        'urlsplit(base).scheme, host_of(base))'):
                self.assertNotIn(bad, src, "%s builds a url from the folded host" % name)

    def test_the_folded_name_is_still_what_paces(self):
        """Dropping the folding would be the opposite mistake: two spellings of one operator
        hammering the same machine, which is the shape that has cost this collection two hosts."""
        for name in self.TOOLS:
            self.assertIn("host_of(base)", self.source(name), name)

    def test_the_five_archives_this_was_found_on_still_have_a_www_base(self):
        """If one of them is ever re-registered on its apex, this case stops meaning anything --
        better that it says so by failing than that it keeps passing for the wrong reason."""
        mirror = load("mirror")
        bases = dict(mirror.ARCHIVES)
        for name in ("cmu-shadow", "rs6000-microcode", "crashing-org-www", "sun3arc",
                     "dreamlandbbs-os2"):
            self.assertIn(name, bases)
            self.assertTrue(urllib.parse.urlsplit(bases[name]).hostname.startswith("www."), name)


class AnUnpackedTreeIsRecordedWhereTheMirrorIs(unittest.TestCase):
    """Six archives were taken out of a tar rather than fetched file by file.

    WHY IT HAD TO BE WRITTEN DOWN. On 2026-10-02 the new base-URL check flagged four of the six as
    "DNS FAILS" or "nothing listening on 80 or 443" -- all true, all documented in FROZEN, and all
    exactly what a frozen origin looks like. Nothing in the tooling connected the two, and the
    owner had to say "careful, I unpacked things in three or four archives" before it was noticed.

    The consequence is not cosmetic: an unpacked tree holds MORE files than its origin ever served
    individually, so every comparison of a sitemap, a listing or a harvest against it finds a
    surplus. A reader who does not know that reads the surplus as a defect.
    """

    MIRROR = load("mirror")

    def test_the_table_exists_and_names_real_archives(self):
        names = {n for n, _u in self.MIRROR.ARCHIVES}
        self.assertTrue(self.MIRROR.UNPACKED)
        for key in self.MIRROR.UNPACKED:
            self.assertIn(key, names, key)

    def test_every_one_gives_a_reason(self):
        """A table of bare names would need somebody to remember what it meant."""
        for key, why in self.MIRROR.UNPACKED.items():
            self.assertTrue(why.strip(), key)

    def test_each_is_also_FROZEN(self):
        """Not a rule, a measurement: all six origins went away, which is why they were unpacked
        out of somebody else's container in the first place. If one ever is not, that is worth
        noticing rather than asserting away."""
        for key in self.MIRROR.UNPACKED:
            self.assertIn(key, self.MIRROR.FROZEN, key)

    def test_the_registration_line_says_so_too(self):
        """Where the mirror is ENTERED is where somebody looks first."""
        with io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
            src = fh.read()
        for key in self.MIRROR.UNPACKED:
            self.assertIn("# %s -- UNPACKED" % key, src, key)

    def test_a_tool_that_compares_against_a_source_says_so(self):
        """find-sitemaps.py is the first such tool; the note must survive on the path a frozen
        origin actually takes, which is "no answer" and not a sitemap report."""
        with io.open(os.path.join(HERE, "find-sitemaps.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("UNPACKED", src)
        self.assertIn('no answer (%s)%s', src)


class AUrlListIsJudgedBySiteAndNotBySpelling(unittest.TestCase):
    """manifest-fetch.py, the third tool to need common.under_site."""

    ARCHIVE = "tvsat-cpc710"        # registered name; --archive is checked against the register
    BASE = "http://www.example.invalid/pub/"

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, self.ARCHIVE))
        self.list = os.path.join(self.root, "urls.txt")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def fetch(self, *urls):
        with io.open(self.list, "w", encoding="utf-8") as fh:
            for u in urls:
                fh.write(u + "\n")
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "manifest-fetch.py"),
             "--root", self.root, "--archive", self.ARCHIVE, "--base", self.BASE,
             "--url-list", self.list, "--dry-run"],
            capture_output=True, text=True, cwd=HERE)
        return out.stdout + out.stderr

    def test_the_zx_case_itself(self):
        """https in the list, http in the register. All 4 404 urls were lost to this."""
        out = self.fetch("https://www.example.invalid/pub/a/x.zip")
        self.assertIn("names 1 paths", out)
        self.assertNotIn("OUTSIDE THE BASE", out)

    def test_the_apex_spelling_too(self):
        out = self.fetch("http://example.invalid/pub/a/y.zip")
        self.assertIn("names 1 paths", out)

    def test_a_foreign_host_is_STILL_refused(self):
        """The check must still refuse what it was written to refuse."""
        out = self.fetch("http://somewhere.else.invalid/pub/a/z.zip")
        self.assertIn("OUTSIDE THE BASE", out)
        self.assertIn("names 0 paths", out)

    def test_a_lookalike_host_is_refused(self):
        out = self.fetch("http://www.example.invalid.evil.test/pub/a/z.zip")
        self.assertIn("OUTSIDE THE BASE", out)

    def test_the_same_host_above_the_base_is_refused(self):
        """`/other/` is this site and is not under `/pub/`."""
        out = self.fetch("http://www.example.invalid/other/z.zip")
        self.assertIn("OUTSIDE THE BASE", out)

    def test_the_path_is_cut_at_the_base_and_not_at_the_host(self):
        """A url accepted under a second spelling must still map to the right local path."""
        out = self.fetch("https://example.invalid/pub/deep/down/w.zip")
        self.assertIn("deep/down/w.zip", out)


class AllThreeToolsShareOneRule(unittest.TestCase):
    """One rule, one implementation. Three private copies were how it got written wrong twice."""

    TOOLS = ("manifest-fetch.py", "pages-to-urllist.py", "find-sitemaps.py")

    def test_each_uses_the_library_helper(self):
        for name in self.TOOLS:
            with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
                src = fh.read()
            self.assertIn("under_site", src, name)

    def test_and_none_still_tests_a_base_with_a_bare_startswith(self):
        """The shape that was wrong in all three. A match here is not proof of a defect, but it is
        the line worth looking at, so it fails loudly rather than drifting back in."""
        for name in self.TOOLS:
            with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
                code = [ln.split("#", 1)[0] for ln in fh.read().splitlines()]
            for n, line in enumerate(code, 1):
                self.assertNotIn("startswith(base", line, "%s:%d" % (name, n))


if __name__ == "__main__":
    unittest.main(verbosity=1)
