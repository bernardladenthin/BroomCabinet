#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""A tool that produces or consumes a URL LIST must honour the archive's EXCLUDE.

WHAT HAPPENED, openpa, 2026-09-30. pages-to-urllist.py read 160 stored pages, found 621 urls the
tree does not hold, and printed a manifest-fetch.py command as the obvious next step. 580 of
those 621 sit under images/ and systems/images/ -- openpa.net's robots.txt WILDCARD group, a rule
binding every crawler and not a preference of ours. The tool did not know EXCLUDE existed, and
manifest-fetch.py did not check either, so the pair would have asked for 580 forbidden paths and
reported a clean run.

IT WAS CAUGHT BY HAND. Twice, on two consecutive days, by someone who happened to remember the
rule while reading the output. That is luck wearing the clothes of a process, and it is the same
shape as every other incident here: the evidence was on screen and nothing compared it to
anything.

THE TRAP INSIDE THE FIX, which is why these are tests and not a one-line filter. 13 of the openpa
urls sit under risc/images/, which LOOKS like the disallowed images/ and is not: robots.txt path
rules anchor at the root, so Disallow: /images/ reaches /images/ and nothing else. A substring
test would have refused 13 files nobody refused -- and an over-refusal is INVISIBLE, because the
file simply never appears in the list. The failure mode that leaves no trace is tested first.

NOTHING HERE READS THE REGISTER FOR ITS EXPECTATIONS. Cases are built from whatever patterns
mirror.py happens to carry, so each test states a PROPERTY -- under the pattern is refused, past
the pattern is kept -- and cannot go stale when an EXCLUDE entry is edited.

No network, and no archive is written to.
"""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, HERE)
HARVEST = load("pages-to-urllist")
MIRROR = load("mirror")

# Archives that really carry exclusions, taken from the register rather than named here, so this
# file does not need editing when the register is edited.
WITH_PATTERNS = sorted(n for n, pats in MIRROR.EXCLUDE.items() if pats)


class TheCheckerComesFromTheRegister(unittest.TestCase):

    def test_there_is_something_to_test(self):
        """A register with no exclusions would make every case below vacuously pass."""
        self.assertTrue(WITH_PATTERNS, "no archive in EXCLUDE carries a pattern")

    def test_refusals_hands_back_mirrors_own_comparison(self):
        """Not a copy of it. There were once three copies, which is exactly how a hit counter
        came to be added to the one copy no run ever reaches.

        Identity is the wrong test and was tried first: load_mirror() imports its own instance of
        the module, so the function is the same code at a different address. What has to hold is
        that the code came out of mirror.py -- a private copy inside this tool would not.
        """
        patterns, checker = HARVEST.refusals(HERE, WITH_PATTERNS[0])
        self.assertTrue(patterns)
        self.assertEqual(checker.__name__, MIRROR.is_excluded.__name__)
        self.assertEqual(os.path.basename(checker.__code__.co_filename), "mirror.py")

    def test_an_unknown_archive_has_no_patterns_and_refuses_nothing(self):
        patterns, checker = HARVEST.refusals(HERE, "no-such-archive-anywhere")
        self.assertEqual(patterns, ())
        self.assertIsNotNone(checker)

    def test_a_missing_register_is_reported_as_missing_and_not_as_empty(self):
        """The difference decides whether a list may be fetched unread."""
        empty = tempfile.mkdtemp()
        try:
            patterns, checker = HARVEST.refusals(empty, "anything")
            self.assertEqual(patterns, ())
            self.assertIsNone(checker, "None is what makes the caller print its warning; an "
                                       "empty tuple alone cannot be told apart from 'nothing "
                                       "is excluded in this archive'")
        finally:
            shutil.rmtree(empty, ignore_errors=True)


class UnderThePatternAndPastIt(unittest.TestCase):
    """The property itself, for every archive the register excludes anything in."""

    def test_a_path_under_the_pattern_is_refused(self):
        for name in WITH_PATTERNS:
            patterns, checker = HARVEST.refusals(HERE, name)
            for pattern in patterns:
                rel = pattern + "a-file.bin"
                self.assertTrue(checker(rel, patterns, name),
                                "%s: %r must be refused by %r" % (name, rel, pattern))

    def test_the_same_name_one_level_down_is_NOT_refused(self):
        """risc/images/ is not images/. A prefix rule is not a substring rule, and an
        over-refused file never appears anywhere for anyone to miss."""
        for name in WITH_PATTERNS:
            patterns, checker = HARVEST.refusals(HERE, name)
            for pattern in patterns:
                rel = "somewhere-else/" + pattern + "a-file.bin"
                self.assertFalse(checker(rel, patterns, name),
                                 "%s: %r must NOT be refused by %r" % (name, rel, pattern))


def run(tool, *argv):
    out = subprocess.run([sys.executable, os.path.join(HERE, tool + ".py")] + list(argv),
                         capture_output=True, text=True, cwd=HERE)
    return out.stdout + out.stderr


class TheFetcherRefusesWhatTheListShouldNotHaveCarried(unittest.TestCase):
    """manifest-fetch.py checks as well, and the duplication is deliberate.

    A url list is a file: hand-written, carried over from another day, or made by a tool that did
    not know about EXCLUDE -- which is precisely what happened. Filtering only where the list is
    produced leaves the fetch open to every list produced some other way.
    """

    def setUp(self):
        self.archive = WITH_PATTERNS[0]
        self.patterns, _ = HARVEST.refusals(HERE, self.archive)
        self.pattern = self.patterns[0]
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, self.archive))
        self.list = os.path.join(self.root, "urls.txt")
        base = "https://example.invalid/"
        with io.open(self.list, "w", encoding="utf-8") as fh:
            fh.write(base + self.pattern + "refused.bin\n")
            fh.write(base + "somewhere-else/" + self.pattern + "kept.bin\n")
            fh.write(base + "plain-file.bin\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def fetch(self):
        return run("manifest-fetch", "--root", self.root, "--archive", self.archive,
                   "--base", "https://example.invalid/", "--url-list", self.list, "--dry-run")

    def test_a_forbidden_url_is_refused_and_never_requested(self):
        out = self.fetch()
        self.assertIn("REFUSED", out)
        self.assertIn(self.pattern + "refused.bin", out)

    def test_the_lookalike_one_level_down_survives(self):
        self.assertIn("somewhere-else/" + self.pattern + "kept.bin", self.fetch())

    def test_the_count_is_what_is_left_after_refusing(self):
        """A headline figure still counting the refused urls would promise what it cannot keep.
        The refusal line is printed BEFORE that figure for the same reason."""
        self.assertIn("names 2 paths", self.fetch())


if __name__ == "__main__":
    unittest.main(verbosity=1)
