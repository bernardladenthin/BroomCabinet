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
        self.probes = 0
        self.said = []

    def outstanding(self, _root, _archive, _out):
        n = self.layers[self.harvests] if self.harvests < len(self.layers) else 0
        self.harvests += 1
        urls = ["http://x.invalid/f%d" % i for i in range(n)]
        return n, urls, "  %d FILES NAMED AND NOT ON DISK" % n

    def probe(self, urls, _delay, pacer=None, report=None):
        """Every candidate is fetchable unless a case says otherwise. The probe has its own tests;
        these cases are about the SHAPE OF THE HISTORY, and a fake that answered 404 here would
        make every one of them a test of the probe instead."""
        self.probes += 1
        return {"get": list(urls), "gone": [], "refused": []}

    def fetch(self, _archive, _base, _list, _delay, _give_up, report=None):
        self.fetches += 1
        return (1, 0, 0)

    def report(self, msg):
        self.said.append(msg)

    def run(self, max_rounds=8, min_gain=1, go=True, use_probe=True):
        """A TEMPORARY ROOT AND NOT THE STRING "root". converge() creates `<root>/logs/` for its
        per-round url lists, so a relative name made that directory INSIDE THE SOURCE TREE and
        five files of test debris were committed on 2026-10-04 before anybody looked at the diff.
        A test that writes where it is run from is a test that pollutes whatever runs it."""
        self.root = tempfile.mkdtemp(prefix="converge-run-")
        try:
            return CONVERGE.converge(self.root, "an-archive", "http://x.invalid/", 0.0,
                                     max_rounds, min_gain, 1, go, report=self.report,
                                     use_probe=use_probe)
        finally:
            shutil.rmtree(self.root, ignore_errors=True)

    def text(self):
        return "\n".join(self.said)


def patched(fake, fn):
    """Run fn with converge.py's three steps replaced. Restored afterwards, always."""
    saved = (CONVERGE.outstanding, CONVERGE.probe, CONVERGE.fetch)
    CONVERGE.outstanding, CONVERGE.probe, CONVERGE.fetch = (
        fake.outstanding, fake.probe, fake.fetch)
    try:
        return fn()
    finally:
        CONVERGE.outstanding, CONVERGE.probe, CONVERGE.fetch = saved


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
                return None, [], "something went wrong and no figure was printed"

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


class AskBeforeFetching(unittest.TestCase):
    """probe(), the step that turns a list of candidates into three different facts.

    MEASURED OVER THREE BATCHES on 2026-10-03/04: of 1 607 outstanding paths, 1 202 answered 404 --
    pages naming files their own server no longer has. Fetching each costs a full request and an
    error page to discard; asking costs a header.

        infania-os-history   54 outstanding, 54 x 404
        somuchstuff-pdp8    480 outstanding, 480 x 404
        dialectronics       158 outstanding, 158 x 404
        seds-frommert       118 outstanding, 115 x 404 + 3 x 403

    THE SAVING IS NOT THE HEAD, IT IS NOT REPEATING IT. A 404 learned here is written straight into
    .mirror-gone, because a HEAD is the source answering and that file holds what the source
    answered. Going back with a GET for a second opinion would spend the 1 202 requests this step
    exists to avoid.

    NO NETWORK: http_open is replaced in converge.py's own namespace, which is where
    `from common import ...` binds it.
    """

    def setUp(self):
        self.real = CONVERGE.http_open
        self.asked = []

    def tearDown(self):
        CONVERGE.http_open = self.real

    def fake(self, answers):
        """answers: {url-suffix: status or Exception}."""
        import contextlib
        import urllib.error

        @contextlib.contextmanager
        def open_it(url, timeout=None, method=None):
            self.asked.append((url, method))
            want = answers[url]
            if isinstance(want, type) and issubclass(want, Exception):
                raise want("nope")
            if want != 200:
                raise urllib.error.HTTPError(url, want, "no", {}, None)

            class R(object):
                status = want
            yield R()

        CONVERGE.http_open = open_it

    def test_it_splits_into_fetchable_gone_and_refused(self):
        urls = ["u/a", "u/b", "u/c", "u/d"]
        self.fake({"u/a": 200, "u/b": 404, "u/c": 410, "u/d": 403})
        got = CONVERGE.probe(urls, 0.0, report=lambda _m: None)
        self.assertEqual(got["get"], ["u/a"])
        self.assertEqual([c for _u, c in got["gone"]], [404, 410])
        self.assertEqual([c for _u, c in got["refused"]], [403])

    def test_IT_ASKS_WITH_HEAD(self):
        """A GET would download the error page this step exists to avoid."""
        self.fake({"u/a": 404})
        CONVERGE.probe(["u/a"], 0.0, report=lambda _m: None)
        self.assertEqual(self.asked, [("u/a", "HEAD")])

    def test_A_TIMEOUT_IS_NOT_GONE(self):
        """Our side of the wire, or a host having a bad minute. Writing it into .mirror-gone would
        record our own trouble as the source's answer -- and develooper-hpux answered 503 on one
        probe and 404 on the next, which is exactly why these are kept apart."""
        self.fake({"u/a": TimeoutError})
        got = CONVERGE.probe(["u/a"], 0.0, report=lambda _m: None)
        self.assertEqual(got["gone"], [])
        self.assertEqual(got["get"], [])
        self.assertEqual(len(got["refused"]), 1)

    def test_a_500_is_refused_and_not_gone(self):
        """bretjohnson.us/forum answers 500 and record_gone takes 404 and 410 only."""
        self.fake({"u/a": 500})
        got = CONVERGE.probe(["u/a"], 0.0, report=lambda _m: None)
        self.assertEqual([c for _u, c in got["refused"]], [500])

    def test_only_404_and_410_are_treated_as_gone(self):
        """The set is the library's, not a second copy written here."""
        self.assertEqual(set(common.GONE_STATUS), {404, 410})

    def test_an_empty_list_asks_nothing(self):
        self.fake({})
        got = CONVERGE.probe([], 0.0, report=lambda _m: None)
        self.assertEqual((got["get"], got["gone"], got["refused"]), ([], [], []))
        self.assertEqual(self.asked, [])


class NothingFetchableStopsTheRoundEarly(unittest.TestCase):
    """seds-frommert: 118 candidates, 115 gone and 3 refused, and not one GET worth making.

    BEFORE THIS the round fetched anyway, the figure did not move, and the gain brake noticed one
    harvest later -- so a list of nothing but dead links cost a wasted fetch pass. Five paths in
    the collection are permanent refusals that record_gone cannot hold, and each used to cost that.
    """

    def test_the_source_says_so(self):
        with io.open(os.path.join(HERE, "converge.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("nothing here is fetchable", src)
        self.assertIn('if not asked["get"]:', src)

    def test_the_probe_runs_before_the_fetch(self):
        """Order matters and a comment is not an order. The call to probe() must come first."""
        with io.open(os.path.join(HERE, "converge.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertLess(src.index("asked = probe("), src.index("got = fetch("))


class AFigureWithoutAListIsABrokenHarvest(unittest.TestCase):
    """The false closure of 2026-10-04, pinned.

    pages-to-urllist.py announced "3789 FILES NAMED AND NOT ON DISK" for gsi-collection and then
    DIED printing a sample path its Windows console could not encode -- before writing the url
    file. This loop read the figure, found no urls, and reported "nothing here is fetchable".

    HAD THE FIGURE BEEN 0 IT WOULD HAVE CLAIMED A FIXED POINT. The same shape as every other clean
    zero here: an answer that looks like a finding because the thing that should have spoken said
    nothing at all. Two defects were fixed -- the tool now writes its product before printing its
    courtesies -- and this case is the one that stops the loop believing a figure it cannot act on.
    """

    def test_a_count_with_no_urls_stops_the_run(self):
        class Mute(Fake):
            def outstanding(self, _root, _archive, _out):
                self.harvests += 1
                return 3789, [], "  3789 FILES NAMED AND NOT ON DISK"

        f = Mute([3789])
        history = patched(f, f.run)
        self.assertEqual(history, [])
        self.assertEqual(f.probes, 0)
        self.assertEqual(f.fetches, 0)

    def test_and_it_says_the_harvest_is_broken_rather_than_empty(self):
        class Mute(Fake):
            def outstanding(self, _root, _archive, _out):
                self.harvests += 1
                return 3789, [], "  3789 FILES NAMED AND NOT ON DISK"

        f = Mute([3789])
        patched(f, f.run)
        self.assertIn("wrote NO url list", f.text())
        self.assertIn("broken harvest, not an empty one", f.text())
        self.assertNotIn("nothing here is fetchable", f.text())

    def test_a_count_of_zero_with_no_urls_is_STILL_a_fixed_point(self):
        """The honest empty case must survive the guard: a closed archive names nothing and
        therefore writes nothing, and that is the answer the whole tool exists to reach."""
        f = Fake([0])
        history = patched(f, f.run)
        self.assertEqual(history, [(1, 0, 0)])
        self.assertIn("FIXED POINT", f.text())

    def test_the_tool_writes_its_list_before_printing_samples(self):
        """The other half of the fix, in the other file: the product cannot be destroyed by the
        courtesy. Order matters and a comment is not an order."""
        with io.open(os.path.join(HERE, "pages-to-urllist.py"), encoding="utf-8") as fh:
            src = fh.read()
        write_at = src.index('io.open(args.out, "w"')
        print_at = src.index("for u in files[:12]:")
        self.assertLess(write_at, print_at)

    def test_and_that_printing_cannot_raise_on_an_undisplayable_path(self):
        with io.open(os.path.join(HERE, "pages-to-urllist.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('encode(enc, "replace")', src)


class TheProbeIsABetAndCanBeDeclined(unittest.TestCase):
    """--no-probe, added 2026-10-04 on the evidence of the run that disproved the default.

    THE PROBE WINS WHERE MOST CANDIDATES ARE DEAD and loses where most are real:

        five archives     2 099 of 2 504 answered 404     6 098 requests saved
        ps-2.kev009.com   4 906 of 6 098 answered 200     6 098 requests ADDED

    Asking first turned 6 098 requests into 11 004 for that one archive, because every fetchable
    candidate was then fetched anyway. manifest-fetch.py records a 404 by itself, so declining the
    probe loses the saving and nothing else.

    I PREDICTED THE OPPOSITE. Five archives in a row had been all-dead, and I told the owner
    ps-2 would probably behave the same and need no further disk work. It answered 200 for four
    fifths of its list.
    """

    def test_with_no_probe_everything_goes_to_the_fetcher(self):
        f = Fake([3, 0])
        patched(f, lambda: f.run(use_probe=False))
        self.assertEqual(f.probes, 0)
        self.assertEqual(f.fetches, 1)

    def test_the_probe_is_still_the_default(self):
        f = Fake([3, 0])
        patched(f, f.run)
        self.assertEqual(f.probes, 1)

    def test_it_says_which_way_it_went(self):
        """A run whose request count differs by a factor of two must say so in its own output."""
        f = Fake([3, 0])
        patched(f, lambda: f.run(use_probe=False))
        self.assertIn("--no-probe", f.text())

    def test_the_flag_exists_and_explains_the_bet(self):
        out = subprocess.run([sys.executable, os.path.join(HERE, "converge.py"), "--help"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        self.assertIn("--no-probe", out)
        self.assertIn("BET", out)


class WhatTheFetcherSaysIsRELAYED(unittest.TestCase):
    """The filter was a whitelist of three substrings and it hid the reason for everything.

    fetch() relayed only lines containing "DONE fetched", "FAILED" or "ABANDONED". What that threw
    away:

        FAIL   <path> :: <reason>       the reason for every single failure
        GONE HTTP <code>  <path>        which paths the source denied, and with what
        N path(s) UNSTORABLE            a file occupying a parent directory
        N path(s) answered AS A         a redirect to a directory
          DIRECTORY
        OUTSIDE THE BASE, skipped       a url the list named and the fetch would not ask for
        MARKER LEFT ALONE / NO MARKER   why a marker was not written
        WARNING mirror.py could not     an archive's EXCLUDE silently not applied
          be read

    THE LAST ONE IS THE ARGUMENT FOR INVERTING IT. A whitelist keeps what its author thought of,
    and a warning that a forbidden path may have been requested is precisely what nobody thinks of.

    IT COST AN AFTERNOON ON 2026-10-04. Thirty "FAIL ... [WinError 183]" lines were dropped, the
    loop reported only "0 fetched, 30 failed", and I read a local filesystem error as
    ps-2.kev009.com blocking us -- argued about route-shopping, advised waiting a day, and the
    owner restarted his router for nothing. The reason was in a line this filter discarded.
    """

    def test_the_progress_counter_is_the_only_thing_hidden(self):
        for line in ("  125/1521, 51.4 MB", "  1/1, 0.0 MB", "   9999/9999, 1234.5 MB"):
            self.assertTrue(CONVERGE.PROGRESS.match(line), line)

    def test_EVERYTHING_ELSE_IS_RELAYED(self):
        for line in ("  FAIL   x/y :: [WinError 183] blah",
                     "  GONE HTTP 403  a/b.zip",
                     "  692 path(s) UNSTORABLE: a file occupies a parent directory.",
                     "  3 path(s) the server answered AS A DIRECTORY",
                     "  OUTSIDE THE BASE, skipped: http://other.invalid/x",
                     "  WARNING mirror.py could not be read -- NO exclusion was applied",
                     "  MARKER LEFT ALONE: it belongs to whatever wrote it",
                     "  DONE fetched 3, gone from the source 0, failed 0, 0.0 MB"):
            self.assertFalse(CONVERGE.PROGRESS.match(line), line)

    def test_a_count_in_prose_is_not_mistaken_for_progress(self):
        """The pattern is anchored at both ends, so a sentence that happens to contain `3/4` or a
        size is still relayed."""
        for line in ("  took 3/4 of the list, 12.0 MB in", "  12.0 MB of 99/100 done, see above"):
            self.assertFalse(CONVERGE.PROGRESS.match(line), line)

    def test_the_source_relays_by_default_rather_than_by_whitelist(self):
        with io.open(os.path.join(HERE, "converge.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("if not line.strip() or PROGRESS.match(line):", src)
        self.assertNotIn('if "DONE fetched" in line or "FAILED" in line', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
