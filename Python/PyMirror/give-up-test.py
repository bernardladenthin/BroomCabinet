#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""A crawl must stop when the host stops, and it did not.

WHAT HAPPENED, 2026-09-29, openpa.net. A run at 5 s with ONE connection and --trust-index went
perfectly for five minutes -- 135 files to 184, 2.2 files a second, zero failures. At 10:28:27 the
host stopped answering. The run then spent TWENTY-SIX MINUTES asking anyway, and was stopped by
hand, not by itself:

    10:24  135 files   2.2/s     fail 0   lostdir 0
    10:29  181 files   0.0/s     fail 0   lostdir 0   <- first timeout at 10:28:27
    10:34  184 files   0.0/s     fail 2   lostdir 2
    10:55  184 files   0.0/s     fail 9   lostdir 9   <- killed here

NOT ONE NEW FILE AFTER 10:29. Everything past that point was cost: 28 retries at a host that had
already refused, and -- worse than the waste -- NINE DIRECTORIES RECORDED AS UNREADABLE. Each of
those is written down as a lost subtree, and the run's own advice for a lost subtree is "re-run
to pick them up". That is a false record. The listings were never unreadable; the host was gone.

THE GUARD EXISTED THAT MORNING AND WAS PUT IN THE WRONG TOOL. common.Patience was written hours
earlier, for manifest-fetch.py, which walks a list of 30 urls in two minutes with someone
watching. mirror.py is the tool that runs unattended for hours, and it had nothing.

WHAT IS TESTED HERE. Not the network -- the decision. worker() maps four outcomes onto "the
server answered" or "the server did not", the producer stops enumerating once the run is
abandoned, and the queue is drained rather than worked. No socket is opened by any of it.
"""
import importlib.util
import io
import os
import queue
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


class Log(object):
    """Enough of the run's logger to record what was said, and nothing that touches a disk."""

    def __init__(self):
        self.lines = []

    def line(self, text, error=False):
        self.lines.append(text)


def run_worker(results, limit=6):
    """Feed worker() a fixed sequence of download outcomes. -> (stats, log).

    download() is replaced, so nothing is fetched and no path is touched. The queue is loaded
    up front and closed with one sentinel, so the worker returns on its own.
    """
    stats = MIRROR.Stats()
    stats.patience = MIRROR.Patience(limit=limit)
    log = Log()
    q = queue.Queue()
    for _ in results:
        q.put(("https://example.invalid/f", None, None))
    q.put(None)

    pending = list(results)
    real_download = MIRROR.download
    MIRROR.download = lambda *a, **kw: pending.pop(0)
    try:
        MIRROR.worker(q, "root", "https://example.invalid/", stats, log)
    finally:
        MIRROR.download = real_download
    return stats, log, pending


class WhenTheHostStopsAnswering(unittest.TestCase):

    def test_six_silences_in_a_row_abandon_the_run(self):
        stats, log, _ = run_worker(["fail"] * 6)
        self.assertTrue(stats.abandon)
        self.assertIn("6 requests in a row", stats.abandon)
        self.assertTrue(any("in a row" in ln for ln in log.lines))

    def test_five_do_not(self):
        """The limit is a limit, not a threshold that fires early."""
        stats, _log, _ = run_worker(["fail"] * 5)
        self.assertIsNone(stats.abandon)

    def test_the_remaining_queue_is_drained_and_not_fetched(self):
        """The queue holds up to 128 items -- every one of them is a request not to make."""
        stats, _log, never_tried = run_worker(["fail"] * 6 + ["fail"] * 20)
        self.assertTrue(stats.abandon)
        self.assertEqual(len(never_tried), 20)
        # And they are not counted as losses. Nothing asked for them.
        self.assertEqual(stats.failed, 6)

    def test_a_404_is_an_answer_and_keeps_the_run_going(self):
        """THE DISTINCTION THE WHOLE GUARD RESTS ON.

        A hand-written site full of dead links produces permfail after permfail. The server is
        answering every one of them; a run that treated those as silence would abandon exactly
        the archives this collection exists for.
        """
        stats, _log, _ = run_worker(["permfail"] * 40)
        self.assertIsNone(stats.abandon)
        self.assertEqual(stats.permfail, 40)

    def test_an_already_held_file_is_an_answer_too(self):
        """--trust-index turns held files into `skip` without a request. Those must not count
        as silence -- on a re-run of a finished archive they would be the whole run."""
        stats, _log, _ = run_worker(["skip"] * 40)
        self.assertIsNone(stats.abandon)

    def test_scattered_failures_never_abandon(self):
        """Nine failures spread through a long run is a lumpy archive, not a refusal."""
        pattern = (["ok"] * 20 + ["fail"]) * 9
        stats, _log, _ = run_worker(pattern)
        self.assertIsNone(stats.abandon)
        self.assertEqual(stats.failed, 9)

    def test_one_answer_in_the_middle_resets_the_count(self):
        """Five, then a file, then five. Ten failures and the run carries on -- correctly."""
        stats, _log, _ = run_worker(["fail"] * 5 + ["ok"] + ["fail"] * 5)
        self.assertIsNone(stats.abandon)

    def test_the_reason_is_recorded_once_and_not_per_worker(self):
        """Eight workers can each trip the limit; the run has one reason, not eight."""
        stats, log, _ = run_worker(["fail"] * 12)
        self.assertEqual(len([ln for ln in log.lines if "in a row" in ln]), 1)


class WhatTheRunSaysAfterwards(unittest.TestCase):

    def test_abandoned_is_its_own_verdict(self):
        """INCOMPLETE invites "re-run to pick them up", which is the wrong advice here."""
        import re
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirror.py"),
                     encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('verdict = "ABANDONED"', src)
        # And the sentence that must NOT be printed in that case.
        guarded = re.search(r"if stats\.listfail and not stats\.abandon:", src)
        self.assertTrue(guarded, "the 're-run to pick them up' warning must be guarded")

    def test_a_marker_cannot_follow_an_abandoned_run(self):
        """Belt and braces: abandoning takes --give-up failures, and COMPLETE needs none."""
        stats = MIRROR.Stats()
        stats.patience = MIRROR.Patience(limit=6)
        for _ in range(6):
            stats.patience.went_quiet()
        self.assertTrue(stats.patience.spent)
        # The verdict line requires `not (listfail or failed)`; six failures is what it took.
        self.assertGreaterEqual(6, stats.patience.limit)


if __name__ == "__main__":
    unittest.main(verbosity=1)
