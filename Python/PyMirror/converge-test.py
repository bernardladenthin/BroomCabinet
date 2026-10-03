# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Does the loop stop, and does it stop for the right reason?

WHAT IS AT STAKE. converge.py exists because one harvest describes one LAYER of a tree whose
listing pages are themselves files. dreamlandbbs-os2 needed six rounds -- 5 330, then 1 521, 395,
113, 5, 0 -- and after the FIRST round it looked finished. Taking it then, into a solid archive
that by design is never modified again, would have frozen it 2 034 files short for ever.

SO THE INTERESTING CASES ARE THE STOPS, NOT THE SUCCESS. A loop that fetches from a stranger's
server has to be able to end itself, and the register holds the counter-example: retro's
`Jumper Reference/` stopped yielding new files at page 950 with 99 000 pages still queued, because
per-board pages cross-link to the same files for ever. A round cap alone would have spent 27 hours
there. The throwaway loop this tool replaces had only the cap, set to five, and that was luck.

NO NETWORK. converge() takes the two steps as injected callables, so every case here is a shape of
history rather than a web server. The subprocess wiring is exercised separately against an archive
already at its fixed point.
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

CONVERGE = common.load_peer("converge.py", "_converge", HERE)


class Fake(object):
    """A tree that opens in layers: each round's fetch reveals the next round's count."""

    def __init__(self, layers):
        self.layers = list(layers)
        self.harvests = 0
        self.fetches = 0
        self.said = []

    def outstanding(self, _root, _archive, _out):
        n = self.layers[self.harvests] if self.harvests < len(self.layers) else 0
        self.harvests += 1
        return n, "  %d FILES NAMED AND NOT ON DISK" % n

    def fetch(self, _archive, _base, _list, _delay, _give_up, report=None):
        self.fetches += 1
        return (1, 0, 0)

    def report(self, msg):
        self.said.append(msg)

    def run(self, max_rounds=8, min_gain=1, go=True):
        return CONVERGE.converge("root", "an-archive", "http://x.invalid/", 0.0,
                                 max_rounds, min_gain, 1, go, report=self.report)

    def text(self):
        return "\n".join(self.said)


def patched(fake, fn):
    """Run fn with converge.py's two steps replaced. Restored afterwards, always."""
    o_out, o_fetch = CONVERGE.outstanding, CONVERGE.fetch
    CONVERGE.outstanding, CONVERGE.fetch = fake.outstanding, fake.fetch
    try:
        return fn()
    finally:
        CONVERGE.outstanding, CONVERGE.fetch = o_out, o_fetch


class ItRunsUntilNothingIsNamed(unittest.TestCase):

    def test_THE_DREAMLAND_SHAPE_TAKES_SIX_ROUNDS(self):
        """The case this tool was built for, with that archive's own figures."""
        f = Fake([5330, 1521, 395, 113, 5, 0])
        history = patched(f, f.run)
        self.assertEqual([h[1] for h in history], [5330, 1521, 395, 113, 5, 0])
        self.assertEqual(f.fetches, 5)
        self.assertIn("FIXED POINT", f.text())

    def test_an_archive_already_closed_fetches_nothing(self):
        """A first round of 0 is an answer, not an error -- ardent-tool reads this way."""
        f = Fake([0])
        history = patched(f, f.run)
        self.assertEqual(history, [(1, 0, 0)])
        self.assertEqual(f.fetches, 0)

    def test_the_fixed_point_is_only_claimed_after_a_harvest_that_read_new_pages(self):
        """The zero must come from a harvest run AFTER a fetch, not from the fetch's own report:
        the pages that name the next layer only become readable once they are on disk."""
        f = Fake([3, 0])
        patched(f, f.run)
        self.assertEqual(f.harvests, 2)
        self.assertEqual(f.fetches, 1)


class TheTwoBrakes(unittest.TestCase):

    def test_the_round_cap_stops_a_figure_that_is_still_falling(self):
        f = Fake([100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0])
        history = patched(f, lambda: f.run(max_rounds=3))
        self.assertEqual(len(history), 3)
        self.assertIn("--max-rounds 3 reached", f.text())
        self.assertNotIn("FIXED POINT", f.text())

    def test_A_ROUND_THAT_GAINS_NOTHING_STOPS_THE_RUN(self):
        """THE JUMPER REFERENCE SHAPE: pages keep naming files the fetch cannot reduce. Without
        this brake the loop spends somebody else's bandwidth until the cap, learning nothing."""
        f = Fake([500, 500, 500, 500])
        history = patched(f, lambda: f.run(min_gain=1))
        self.assertEqual(len(history), 1)
        self.assertIn("below --min-gain", f.text())

    def test_min_gain_can_demand_real_progress(self):
        """A figure creeping down by one a round is the same trap more slowly."""
        f = Fake([500, 499, 498, 497])
        history = patched(f, lambda: f.run(min_gain=50))
        self.assertEqual(len(history), 1)
        self.assertIn("below --min-gain 50", f.text())

    def test_and_it_says_WHICH_brake_fired(self):
        """Two stops that look alike in a log are one stop nobody can act on."""
        cap = Fake([9, 8, 7, 6])
        patched(cap, lambda: cap.run(max_rounds=2))
        stall = Fake([9, 9])
        patched(stall, lambda: stall.run(min_gain=1))
        self.assertIn("--max-rounds", cap.text())
        self.assertNotIn("--min-gain", cap.text())
        self.assertIn("--min-gain", stall.text())
        self.assertNotIn("--max-rounds", stall.text())


class AnUnREADABLEFigureIsNotZero(unittest.TestCase):
    """The failure shape this collection keeps meeting: a clean zero that looks like a finding."""

    def test_a_harvest_whose_number_cannot_be_read_stops_the_run(self):
        class Mute(Fake):
            def outstanding(self, _root, _archive, _out):
                self.harvests += 1
                return None, "something went wrong and no figure was printed"

        f = Mute([0])
        history = patched(f, f.run)
        self.assertEqual(history, [])
        self.assertEqual(f.fetches, 0)
        self.assertIn("could not be read", f.text())

    def test_a_fetch_whose_number_cannot_be_read_stops_the_run(self):
        class Mute(Fake):
            def fetch(self, *_a, **_k):
                self.fetches += 1
                return None

        f = Mute([5, 0])
        history = patched(f, f.run)
        self.assertEqual(history, [])
        self.assertEqual(f.harvests, 1)


class WithoutGoNothingIsRequested(unittest.TestCase):

    def test_it_harvests_once_and_fetches_nothing(self):
        f = Fake([42, 0])
        history = patched(f, lambda: f.run(go=False))
        self.assertEqual(history, [(1, 42, 0)])
        self.assertEqual(f.fetches, 0)
        self.assertIn("nothing fetched", f.text())


class TheRecordItLeaves(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="converge-")
        os.makedirs(os.path.join(self.root, "an-archive"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def read(self):
        with io.open(os.path.join(self.root, "an-archive", CONVERGE.RECORD),
                     encoding="utf-8") as fh:
            return fh.read()

    def test_the_rounds_are_written_into_the_archive(self):
        CONVERGE.write_record(self.root, "an-archive",
                              [(1, 5330, 5330), (2, 1521, 1521), (3, 0, 0)], "http://x.invalid/")
        text = self.read()
        self.assertIn("| 1 | 5330 | 5330 |", text)
        self.assertIn("| 3 | 0 | 0 |", text)
        self.assertIn("NOTHING outstanding", text)

    def test_a_run_that_did_not_converge_says_so_IN_THE_RECORD(self):
        """A table of rounds with no verdict reads as success to anyone skimming it."""
        CONVERGE.write_record(self.root, "an-archive", [(1, 500, 1), (2, 499, 1)],
                              "http://x.invalid/")
        self.assertIn("did NOT reach a fixed point", self.read())

    def test_a_second_run_appends_rather_than_overwriting(self):
        """The first run's rounds are evidence too, and an archive may be revisited months later."""
        CONVERGE.write_record(self.root, "an-archive", [(1, 3, 3), (2, 0, 0)], "http://x.invalid/")
        CONVERGE.write_record(self.root, "an-archive", [(1, 0, 0)], "http://x.invalid/")
        self.assertEqual(self.read().count("| round | outstanding | fetched |"), 2)

    def test_the_record_name_is_known_to_the_bookkeeping_sets(self):
        """Otherwise every auditor reads it as content and every marker counts it -- the mistake
        FRAGMENT-COPIES-REMOVED.txt and HOW-THIS-ARRIVED.md each had to be repaired for."""
        self.assertIn(CONVERGE.RECORD, common.BOOKKEEPING_FILES)
        self.assertNotIn(CONVERGE.RECORD, common.OWN_FILES)


class TheRealWiring(unittest.TestCase):
    """One case through the actual subprocesses, because injected callables prove nothing about
    whether the two tools are invoked correctly."""

    def test_an_archive_at_its_fixed_point_reads_as_zero_end_to_end(self):
        root = tempfile.mkdtemp(prefix="converge-live-")
        try:
            d = os.path.join(root, "tvsat-cpc710")
            os.makedirs(d)
            with io.open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
                fh.write("<HTML><BODY><A HREF='held.bin'>x</A></BODY></HTML>")
            with io.open(os.path.join(d, "held.bin"), "wb") as fh:
                fh.write(b"x")
            env = dict(os.environ)
            env["PYTHONPYCACHEPREFIX"] = tempfile.gettempdir()
            env.pop("MIRROR_ROOT", None)
            p = subprocess.run([sys.executable, os.path.join(HERE, "converge.py"),
                                "--root", root, "--archive", "tvsat-cpc710"],
                               capture_output=True, text=True, env=env)
            out = p.stdout + p.stderr
            self.assertIn("round 1: 0 outstanding", out)
            self.assertIn("FIXED POINT", out)
            self.assertEqual(p.returncode, 0, out)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
