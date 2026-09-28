#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""`--dry-run` must not fetch, and over HTTP it cannot do anything else -- so it refuses.

WHAT HAPPENED. `--dry-run` is an rsync feature: the flag is handed to `rsync -n`, which reports
what would transfer and moves nothing. Its help text has always said "rsync archives only".
That was not enough. On 2026-09-27 a `--dry-run` on an HTTP archive ran a REAL CRAWL: it fetched
61 pages, wrote a completion marker, and reported `61 files, 0 failed` over a tree that was
missing 99.4 % of itself. Nothing warned, because from the code's point of view nothing unusual
had happened -- the flag was simply never consulted on that path.

A FLAG WHOSE NAME MEANS "CHANGE NOTHING" MUST NOT CHANGE ANYTHING. Where it cannot honour that,
it has to refuse. The refusal costs a re-run without the flag; not refusing cost a fetch, a wrong
marker, and the half hour it took to work out why the tree was empty.

NO NETWORK AND NO COLLECTION. The guard is a pure function of the flag and the archive list.
"""
import importlib.util
import io
import os
import sys
import unittest


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MIRROR = load("mirror")

HTTP = ("an-archive", "https://example.invalid/pub/")
HTTP2 = ("another", "http://other.invalid/files/")
RSYNC = ("bits", "rsync://example.invalid/bits/")


class Args(object):
    def __init__(self, dry_run):
        self.dry_run = dry_run


class WhatTheGuardRefuses(unittest.TestCase):

    def guard(self, dry_run, todo):
        return MIRROR._refuse_a_dry_run_that_would_not_be_one(Args(dry_run), todo)

    def test_IT_REFUSES_A_DRY_RUN_OVER_HTTP(self):
        """The case that happened. Without this the run proceeds and fetches."""
        with self.assertRaises(SystemExit) as caught:
            self.guard(True, [HTTP])
        self.assertIn("--dry-run does nothing", str(caught.exception))

    def test_AND_NAMES_WHAT_WOULD_HAVE_BEEN_FETCHED(self):
        """"It would have fetched something" is a warning; naming the archive is a finding."""
        with self.assertRaises(SystemExit) as caught:
            self.guard(True, [HTTP, HTTP2])
        message = str(caught.exception)
        self.assertIn("an-archive", message)
        self.assertIn("another", message)

    def test_and_says_what_to_use_instead(self):
        # A refusal that leaves somebody stuck is half a refusal.
        with self.assertRaises(SystemExit) as caught:
            self.guard(True, [HTTP])
        self.assertIn("measure-remote.py", str(caught.exception))

    def test_AN_RSYNC_ARCHIVE_IS_UNTOUCHED(self):
        """There the flag does exactly what its name says, and has since it was added."""
        self.assertIsNone(self.guard(True, [RSYNC]))

    def test_A_MIXED_RUN_IS_REFUSED_FOR_THE_HTTP_HALF(self):
        """Half a dry run is the worst outcome: rsync reports, HTTP fetches, and the summary
        reads as one run."""
        with self.assertRaises(SystemExit) as caught:
            self.guard(True, [RSYNC, HTTP])
        message = str(caught.exception)
        self.assertIn("an-archive", message)
        self.assertNotIn("bits", message)

    def test_without_the_flag_nothing_is_refused(self):
        for todo in ([HTTP], [RSYNC], [HTTP, RSYNC], []):
            self.assertIsNone(self.guard(False, todo), todo)

    def test_THE_HELP_TEXT_STILL_SAYS_WHOSE_FLAG_IT_IS(self):
        """The text was right all along and was not enough on its own -- but if it ever stopped
        saying `rsync`, the refusal above would be the only thing left explaining the flag.

        Read from the SOURCE and not from a rendered --help: argparse wraps and re-flows, and a
        test that greps wrapped output fails for the width of a terminal.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "mirror.py"), encoding="utf-8") as fh:
            src = fh.read()
        at = src.index('ap.add_argument("--dry-run"')
        block = src[at:at + 400]
        self.assertIn("rsync", block.lower())


if __name__ == "__main__":
    unittest.main()
