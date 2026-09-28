#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Every `time.sleep` left in a tool must be one somebody argued for.

WHAT THIS RATCHET IS FOR. On 2026-09-25 this collection held **41 `time.sleep` calls across 17
tools**, and they were not one thing written 41 times. Read one by one they carried three
different meanings, and the arithmetic of the commonest one was wrong in sixteen of seventeen
places:

    a RATE      "do not contact this host more often than every N seconds"   -> common.Pacer
    a LADDER    "wait longer after each failure, longer still on 429/503"    -> common.Backoff
    a COOLDOWN  neither: no host, or no failure                              -> stays a sleep

A delay of 2 s means "not more often than every 2 s", not "idle 2 s after every request": a fetch
that itself took 1.9 s has already paid it. Only `nginx-autoindex-gallery.py` did that arithmetic
correctly; every other tool waited the full delay ON TOP of however long the server took, which is
close to double at the rates this collection uses.

THE POINT IS NOT THAT SLEEPING IS FORBIDDEN. Four calls survive and all four are right. The point
is that the next one has to be argued for HERE, in a table with a reason per entry, rather than
appearing as the forty-second copy of something the library already does. That is the same shape
`audit.py` uses for `ZERO_AT_SOURCE` and `SOURCE_CONVENTIONS`, turned on this codebase instead of
on the collection.

WHAT IT DOES NOT CHECK. It does not read the reason and judge it. A test that tried would be
asserting a form rather than a fact. It asserts that a reason was written down and that no
unlisted call exists.
"""
import ast
import io
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

# Every remaining `time.sleep` in a tool, and why it is not `Pacer` or `Backoff`.
#
# Keyed by file. Adding a row here is the deliberate act; the reason is what a reader gets
# instead of having to reconstruct the argument from the call site.
ALLOWED = {
    "mirror.py": (
        "the rsync retry, which is policy and not a ladder: 900 s after a refusal, an ordinary "
        "min(60 * attempt, 300) otherwise, and it GIVES UP after two refusals -- 'repeating a "
        "question is not a technique for getting a different answer'. Backoff has no opinion "
        "about giving up, and it should not."),
    "wayback-salvage.py": (
        "BACKOFF = (5, 20, 60, 120, 180), a hand-tuned table. It grows 4x, 3x, 2x, 1.5x -- "
        "neither geometric nor arithmetic. Somebody chose those five numbers against this "
        "service's behaviour, and reshaping them to fit a class would change what the tool does "
        "in order to tidy how it is written."),
    "suspect-reconsider.py": (
        "a cooldown after a replay that failed outright. There is no attempt counter -- the item "
        "is abandoned, not retried -- and it is longer than the ordinary pace on purpose, "
        "because a failed replay is a sign the service is unhappy."),
    "move-mirror.py": (
        "a cooldown for HARDWARE, budgeted in gigabytes written rather than in requests made: a "
        "USB drive's write cache needs somewhere to go. No host, no failure, nothing to pace."),
}

# What the library offers instead, so the message a failure prints can name it.
OFFERED = "common.Pacer (a rate) or common.Backoff (a retry ladder)"


def tools():
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".py") and "test" not in name:
            yield name


def sleeps_in(name):
    """-> [line numbers] of literal `time.sleep(...)` calls.

    `time.sleep` SPECIFICALLY, not any `.sleep()`. `wayback-salvage.Pace.sleep()` is a method of
    its own and counting it made an earlier version of this count read 13 where it should read
    12 -- a counter that is wrong about its own subject is worse than no counter.
    """
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), name)
    return sorted(node.lineno for node in ast.walk(tree)
                  if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == "sleep"
                  and isinstance(node.func.value, ast.Name) and node.func.value.id == "time")


class NoUnlistedSleep(unittest.TestCase):

    def test_every_remaining_sleep_is_in_the_table(self):
        stray = {name: sleeps_in(name) for name in tools() if sleeps_in(name)
                 and name not in ALLOWED}
        self.assertEqual(stray, {},
                         "a new time.sleep: use %s, or add a row to ALLOWED saying why not"
                         % OFFERED)

    def test_the_table_names_no_file_that_has_stopped_sleeping(self):
        """A row that no longer applies is a reason nobody can check any more."""
        stale = [name for name in ALLOWED
                 if not os.path.exists(os.path.join(HERE, name)) or not sleeps_in(name)]
        self.assertEqual(stale, [])

    def test_each_listed_file_has_exactly_one(self):
        """One argued-for sleep per file. A second would hide behind the first one's reason."""
        for name in ALLOWED:
            self.assertEqual(len(sleeps_in(name)), 1, name)

    def test_every_row_carries_a_reason_worth_reading(self):
        for name, why in ALLOWED.items():
            self.assertGreater(len(why), 80, name)

    def test_the_count_is_what_the_record_says(self):
        """41 across 17 tools, down to 4 across 4, each survivor with its reason in ALLOWED."""
        total = sum(len(sleeps_in(name)) for name in tools())
        self.assertEqual(total, 4)
        self.assertEqual(len(ALLOWED), 4)


class TheLibraryIsActuallyUsed(unittest.TestCase):
    """The other half: the ratchet would also pass if every tool simply stopped pacing."""

    def users(self, symbol):
        out = []
        for name in tools():
            with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
                if symbol in fh.read():
                    out.append(name)
        return out

    def test_the_pacer_has_many_callers(self):
        # It replaced the rate in most of the seventeen. A number that collapses means a
        # conversion was undone, not that the problem went away.
        self.assertGreaterEqual(len(self.users("Pacer")), 10)

    def test_the_backoff_has_callers(self):
        self.assertGreaterEqual(len(self.users("Backoff")), 2)

    def test_the_two_are_importable_and_distinct(self):
        import common
        self.assertIn("Pacer", common.__all__)
        self.assertIn("Backoff", common.__all__)
        self.assertIsNot(common.Pacer, common.Backoff)


if __name__ == "__main__":
    unittest.main(verbosity=2)
