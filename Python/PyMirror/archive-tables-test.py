#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""`mirror.py` holds fourteen tables keyed by archive name. Nothing made them agree.

WHERE THIS CAME FROM. On 2026-09-26 seven archives were added in one afternoon, each touching
four or five of these tables by hand: ARCHIVES, SEEDS, HTML_CRAWL, MIN_INTERVAL,
WORKERS_BY_ARCHIVE, EXCLUDE. Two mistakes survived the editing and neither was visible by reading:

  * `EXCLUDE["openpa"]` named an archive that does not exist. The exclusion was written while
    deciding about the host and the archive was never added, so the entry sat there governing
    nothing. Harmless today; wrong the day somebody adds an archive under a different name and
    wonders why the exclusion does not apply.
  * a SEED block was pasted into EXCLUDE instead of SEEDS, because both dictionaries have a key
    called `bretjohnson` and the edit matched the first one. `ruff` caught that one -- the four
    seeds collided with an existing key -- but only by luck: had the names differed, four URLs
    would have become four exclusion patterns and the crawler would have started at the root with
    no entry point, reporting a small archive as complete.

THE SECOND ONE IS THE SHAPE THAT MATTERS. A table keyed by name will accept any name, so a typo
or a paste into the wrong dictionary produces a rule that silently governs nothing. That failure
prints no error, and the archive it was meant to protect simply behaves as though nobody had
thought about it.

WHAT IS NOT CHECKED HERE, deliberately: whether a base URL is the right one. That is a judgement
about somebody else's site -- the header of ARCHIVES argues it at length -- and no test can make
it. What a test can do is insist that every rule refers to something real.
"""
import importlib.util
import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import common  # noqa: E402

MIRROR = load("mirror")

# Every table in mirror.py that is keyed by archive name. Listed rather than discovered, so that
# a new one has to be added here on purpose -- discovery would silently skip whatever it missed.
KEYED_BY_ARCHIVE = ("SEEDS", "HTML_CRAWL", "MIN_INTERVAL", "WORKERS_BY_ARCHIVE",
                    "TIMEOUT_BY_ARCHIVE", "EXCLUDE", "RETIRED", "FROZEN",
                    "NEEDS_CASE_SENSITIVE", "UNPACKED")


def known_archives():
    """Every name an archive can be declared under: the crawler, rsync, and Internet Archive."""
    names = set(name for name, _url in MIRROR.ARCHIVES)
    names |= set(getattr(MIRROR, "RSYNC", {}))
    names |= set(item[0] for item in getattr(MIRROR, "IA_ITEMS", ()))
    return names


def same_place(a, b):
    """Is `a` under `b`, ignoring the scheme?

    SCHEME-BLIND ON PURPOSE. `sco-devspecs` is declared as http:// and its thirteen seeds are
    https:// -- a mismatch that predates this test, and one that evidently works, because the
    archive fetched complete. Failing on it would be reporting a naming inconsistency as a
    broken seed. What the test is actually for is a seed pointing at a DIFFERENT PLACE.
    """
    pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return (pa.netloc, pa.path).__str__().startswith("") and \
        pa.netloc == pb.netloc and pa.path.startswith(pb.path)


class EveryRuleRefersToSomethingReal(unittest.TestCase):

    def setUp(self):
        self.known = known_archives()

    def test_no_table_names_an_archive_that_does_not_exist(self):
        dangling = []
        for table in KEYED_BY_ARCHIVE:
            for key in getattr(MIRROR, table):
                if key not in self.known:
                    dangling.append("%s[%r]" % (table, key))
        self.assertEqual(dangling, [],
                         "these rules govern nothing: " + ", ".join(dangling))

    def test_every_table_is_present_and_is_keyed_by_name(self):
        """If a table is renamed, this file must be told -- silence would skip it."""
        for table in KEYED_BY_ARCHIVE:
            self.assertTrue(hasattr(MIRROR, table), table)
            self.assertTrue(len(getattr(MIRROR, table)) > 0, table)

    def test_there_are_archives_at_all(self):
        """Two empty sets agree. The checks above must have something to check."""
        self.assertGreater(len(self.known), 90)



class EveryTreeOnDiskIsDeclared(unittest.TestCase):
    """The direction the other checks do not look in, and the one this collection nearly lost
    an archive to on 2026-09-27.

    `test_no_table_names_an_archive_that_does_not_exist` above asks whether a RULE points at
    nothing. b2-pack-test.py asks whether a backup unit names a tree that is not there, and
    whether a declared archive was left out of the plan. All three start from something written
    down and look for the tree.

    NOTHING ASKED THE OTHER WAY, and an archive that exists only on disk is worse off than one
    that exists only on paper. It cannot be indexed -- `mirror.py --archive X --index` answers
    "no archive matched" -- so it has no `.mirror-index.csv`, no `.sha256sum` and no marker;
    `catalogue.py` reports it as `None files, 0.0 GB`; ask-the-source.py and holes-vs-source.py
    cannot map a path in it back to a URL. It is present, valuable, and outside every check the
    collection has.

    THAT WAS THE PLAN FOR acpc-amstrad FOR HALF AN HOUR. It was fetched from a URL list because
    every directory on its host answers 403, and leaving it unregistered looked like the safe
    choice: a register entry lets `mirror.py` crawl, and that site's front page links 26 GB of
    magazines. The right answer turned out to be a register entry with a NARROW BASE -- rooted
    at `/ACME/`, which answers 403, so a crawl reaches nothing -- and the archive keeps its
    index, its marker and its place in every report. This test is what makes the wrong choice
    loud instead of quiet.

    IT NEEDS THE COLLECTION and skips without it, like the other disk-reading tests here.
    """

    def setUp(self):
        if not os.path.isdir(common.MIRROR_ROOT):
            self.skipTest("the collection is not on this machine")
        self.on_disk = {d for d in os.listdir(common.MIRROR_ROOT)
                        if os.path.isdir(os.path.join(common.MIRROR_ROOT, d))
                        and d != "logs"}

    def declared(self):
        names = {n for n, _u in MIRROR.ARCHIVES}
        names |= {row[0] for row in getattr(MIRROR, "IA_ITEMS", ())}
        return names

    def test_NO_TREE_EXISTS_THAT_NOTHING_DECLARES(self):
        orphans = sorted(self.on_disk - self.declared())
        self.assertEqual(orphans, [], "on disk and in no register: " + ", ".join(orphans))

    def test_and_the_check_has_something_to_check(self):
        """Two empty sets agree. If the collection were unreadable this would pass vacuously."""
        self.assertGreater(len(self.on_disk), 90)
        self.assertGreater(len(self.declared()), 90)

class EverySeedIsInsideItsOwnArchive(unittest.TestCase):
    r"""A seed is where the crawler STARTS; the base URL is what counts as inside.

    A seed outside its own base is fetched and then every link found on it falls outside the
    scope, so the archive comes out as one page and reports itself complete. That is the failure
    this collection has met eight times under other names.
    """

    def setUp(self):
        self.base = dict(MIRROR.ARCHIVES)

    def test_each_seed_lies_under_its_archive(self):
        stray = []
        for archive, seeds in MIRROR.SEEDS.items():
            if archive not in self.base:
                continue                       # covered by the dangling-key test above
            for seed in seeds:
                if not same_place(seed, self.base[archive]):
                    stray.append("%s: %s not under %s" % (archive, seed, self.base[archive]))
        self.assertEqual(stray, [], "\n  " + "\n  ".join(stray))

    def test_the_four_roots_that_needed_one_have_one(self):
        """Measured on 2026-09-26: each of these reaches nothing from its own root."""
        for archive in ("sgidepot", "cmu-shadow", "fjkraan", "iommu"):
            self.assertIn(archive, MIRROR.SEEDS,
                          "%s's root does not link downwards; it needs a seed" % archive)

    def test_the_comparison_ignores_the_scheme_and_nothing_else(self):
        self.assertTrue(same_place("https://h/a/b.html", "http://h/a/"))
        self.assertFalse(same_place("https://other/a/b.html", "http://h/a/"))
        self.assertFalse(same_place("https://h/z/b.html", "http://h/a/"))


class AnExclusionThatGovernsNothingSaysSo(unittest.TestCase):
    r"""A wrong pattern and a right one look identical. Only a count tells them apart.

    ON 2026-09-26, `EXCLUDE["iommu"]` read `("mirrors/",)` while the path it had to match was
    `datasheets/mirrors/...` -- patterns are compared against the path RELATIVE TO THE ARCHIVE
    ROOT, and that archive's root is iommu.com/ while every file hangs under /datasheets/. The
    pattern named a directory that does not exist. It matched nothing and it SAID nothing: 16 GB
    of the 78.8 GB it was written to prevent arrived before the size was noticed by eye.

    THE MATCHER WAS NOT AT FAULT. `rel.startswith(pattern)` does exactly what it says, and no
    test over the library could have caught a pattern that is merely wrong. What was missing is
    that nothing observed the pattern's EFFECT -- so a rule governing nothing was indistinguish-
    able from one working perfectly.

    NOR CAN THE INDEX ANSWER IT, which is worth stating because it is the obvious idea: a
    WORKING exclusion matches nothing in the archive's index either, because the files it
    excluded were never fetched. Absence proves nothing. The signal exists only during a run.
    """

    def setUp(self):
        MIRROR.EXCLUDE_HITS.clear()
        self.log = self.Recorder()

    class Recorder:
        def __init__(self):
            self.lines, self.errors = [], []

        def line(self, msg, error=False):
            self.lines.append(msg)
            if error:
                self.errors.append(msg)

    def test_a_pattern_that_never_fired_is_reported_as_an_error(self):
        dead = MIRROR.report_unused_excludes("iommu", self.log)
        self.assertEqual(dead, list(MIRROR.EXCLUDE["iommu"]))
        self.assertTrue(self.log.errors)
        self.assertIn("NEVER FIRED", self.log.errors[0])

    def test_THE_MESSAGE_SAYS_WHAT_THE_MISTAKE_USUALLY_IS(self):
        """A warning that does not say `relative to the archive root` costs the reader the hour
        it cost the first time."""
        MIRROR.report_unused_excludes("iommu", self.log)
        self.assertIn("RELATIVE TO", self.log.errors[0])

    def test_a_pattern_that_fired_is_counted_and_not_an_error(self):
        pattern = MIRROR.EXCLUDE["iommu"][0]
        MIRROR.EXCLUDE_HITS[("iommu", pattern)] = 4211
        self.assertEqual(MIRROR.report_unused_excludes("iommu", self.log), [])
        self.assertEqual(self.log.errors, [])
        self.assertIn("4211", " ".join(self.log.lines))

    def test_an_archive_with_no_exclusions_reports_nothing(self):
        self.assertEqual(MIRROR.report_unused_excludes("chipdb", self.log), [])
        self.assertEqual(self.log.lines, [])

    def test_the_counter_is_keyed_by_archive_as_well_as_pattern(self):
        """Two archives may share a pattern spelling; one firing must not vouch for the other."""
        pattern = MIRROR.EXCLUDE["iommu"][0]
        MIRROR.EXCLUDE_HITS[("somebody-else", pattern)] = 99
        self.assertEqual(MIRROR.report_unused_excludes("iommu", self.log),
                         list(MIRROR.EXCLUDE["iommu"]))


class TheExclusionComparisonIsWrittenOnce(unittest.TestCase):
    r"""There were three copies of it, and that is how a hit counter came to be useless.

    `producer()` carries two exclusion checks -- one for a child link, one for the container a
    link reaches past -- and `fix_times()` carries a third. On 2026-09-27 a counter was added to
    the THIRD, which only runs under `--fix-times`. A real crawl then fetched two files from an
    archive with eleven exclusion patterns and reported neither a single exclusion nor a single
    dead pattern, because the crawl never reaches that line.

    The comment six lines above the copy that was instrumented already said it: "a guard added to
    one of a pair is a guard the other walks past". It was read afterwards.

    So the comparison lives in `is_excluded()`, counting is a side effect the caller cannot skip,
    and this test refuses a fourth copy.
    """

    def test_no_hand_written_comparison_survives(self):
        import io as _io
        with _io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
            source = fh.read()
        for shape in ("startswith(x) for x in exclude",
                      "startswith(x) for x in EXCLUDE"):
            self.assertNotIn(shape, source,
                             "a fourth copy of the exclusion test: " + shape)

    def test_all_three_call_sites_use_the_one_function(self):
        import io as _io
        with _io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertEqual(source.count("is_excluded("), 4)   # one def, three callers

    def test_it_returns_the_pattern_that_matched_and_counts_it(self):
        MIRROR.EXCLUDE_HITS.clear()
        hit = MIRROR.is_excluded("Games/x.zip", ("Games/", "Software/"), "an-archive")
        self.assertEqual(hit, "Games/")
        self.assertEqual(MIRROR.EXCLUDE_HITS[("an-archive", "Games/")], 1)

    def test_a_miss_returns_none_and_counts_nothing(self):
        MIRROR.EXCLUDE_HITS.clear()
        self.assertIsNone(MIRROR.is_excluded("Docs/x.pdf", ("Games/",), "an-archive"))
        self.assertEqual(MIRROR.EXCLUDE_HITS, {})

    def test_THE_COUNT_IS_A_SIDE_EFFECT_THE_CALLER_CANNOT_FORGET(self):
        """The reason counting lives inside the comparison rather than beside it."""
        MIRROR.EXCLUDE_HITS.clear()
        for _ in range(3):
            MIRROR.is_excluded("Games/x.zip", ("Games/",), "an-archive")
        self.assertEqual(MIRROR.EXCLUDE_HITS[("an-archive", "Games/")], 3)

    def test_the_first_matching_pattern_wins_and_only_it_is_counted(self):
        MIRROR.EXCLUDE_HITS.clear()
        MIRROR.is_excluded("a/b/c", ("a/", "a/b/"), "an-archive")
        self.assertEqual(MIRROR.EXCLUDE_HITS, {("an-archive", "a/"): 1})


class TheFinalRenameSurvivesALostRace(unittest.TestCase):
    r"""The download succeeds and the last step fails, for a reason outside this program.

    MEASURED on the iommu run of 2026-09-27: 1 475 occurrences of WinError 32 in one log --
    "the process cannot access the file because it is being used by another process" -- 104 of
    them final failures, and nine .part fragments left on disk.

    THE CAUSE WAS NOT WHAT THIS DOCSTRING FIRST SAID. It blamed a virus scanner holding the new
    file. The truth was TWO mirror.py PROCESSES ON ONE ARCHIVE: a TaskStop had ended the shell
    wrapper and left the Python process alive, a restart added a second, and they raced on the
    same .part names. Two interleaved PROGRESS streams sat in the log for an hour before anyone
    compared them. The retry is kept anyway -- a scanner really can hold a new file, and being
    wrong in that direction costs 1.5 seconds -- but it cannot fix two writers, and does not
    claim to.

    THE BYTES WERE ALREADY THERE AND ALREADY CHECKED against Content-Length. Giving up threw
    away a complete download AND cost a re-download, because the caller retries the whole
    transfer -- so each of those files was paid for twice and lost anyway.

    THE RETRY IS DELIBERATELY NARROW: this one operation, PermissionError only, and the last
    attempt re-raises so a genuine access problem still stops the file with its own error
    instead of being smoothed into silence.
    """

    def setUp(self):
        self.slept = []

    def fake_sleep(self, seconds):
        self.slept.append(seconds)

    def test_a_rename_that_works_first_time_does_not_wait(self):
        calls = []
        real = MIRROR.os.replace
        MIRROR.os.replace = lambda a, b: calls.append((a, b))
        try:
            attempt = MIRROR.rename_with_retry("x.part", "x", sleep=self.fake_sleep)
        finally:
            MIRROR.os.replace = real
        self.assertEqual(attempt, 0)
        self.assertEqual(self.slept, [])
        self.assertEqual(len(calls), 1)

    def test_A_HELD_FILE_IS_RETRIED_AND_THEN_SUCCEEDS(self):
        state = {"n": 0}

        def flaky(_a, _b):
            state["n"] += 1
            if state["n"] < 3:
                raise PermissionError(32, "being used by another process")

        real = MIRROR.os.replace
        MIRROR.os.replace = flaky
        try:
            attempt = MIRROR.rename_with_retry("x.part", "x", sleep=self.fake_sleep)
        finally:
            MIRROR.os.replace = real
        self.assertEqual(attempt, 2)
        self.assertEqual(state["n"], 3)
        self.assertEqual(len(self.slept), 2)

    def test_THE_WAIT_GROWS_SO_A_SLOW_SCANNER_IS_STILL_CAUGHT(self):
        def always_held(_a, _b):
            raise PermissionError(32, "being used by another process")

        real = MIRROR.os.replace
        MIRROR.os.replace = always_held
        try:
            with self.assertRaises(PermissionError):
                MIRROR.rename_with_retry("x.part", "x", sleep=self.fake_sleep)
        finally:
            MIRROR.os.replace = real
        self.assertEqual(self.slept, sorted(self.slept))
        self.assertGreater(self.slept[-1], self.slept[0])

    def test_A_REAL_PERMISSION_PROBLEM_STILL_RAISES(self):
        """The point of re-raising on the last attempt: silence would be worse than the error."""
        def always_held(_a, _b):
            raise PermissionError(5, "access is denied")

        real = MIRROR.os.replace
        MIRROR.os.replace = always_held
        try:
            with self.assertRaises(PermissionError):
                MIRROR.rename_with_retry("x.part", "x", attempts=2, sleep=self.fake_sleep)
        finally:
            MIRROR.os.replace = real

    def test_nothing_else_is_swallowed(self):
        """Only PermissionError is a lost race. An OSError of another kind is a real fault."""
        def gone(_a, _b):
            raise FileNotFoundError(2, "no such file")

        real = MIRROR.os.replace
        MIRROR.os.replace = gone
        try:
            with self.assertRaises(FileNotFoundError):
                MIRROR.rename_with_retry("x.part", "x", sleep=self.fake_sleep)
        finally:
            MIRROR.os.replace = real
        self.assertEqual(self.slept, [])

    def test_the_caller_uses_it_and_not_a_bare_replace(self):
        import io as _io
        with _io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
            source = fh.read()
        body = source[source.index("def download("):] if "def download(" in source else source
        self.assertIn("rename_with_retry(tmp, dest)", body)


class TheHostsThatSaidSomethingKeepTheirPace(unittest.TestCase):
    r"""Two refused outright, three asked in words. Precaution alone was removed again.

    The rule, decided on 2026-09-26 after all six new archives were limited out of reflex: a host
    keeps a rate limit when it has SAID something -- by refusing, or on its own pages. A limit
    costs an hour of wall clock on every future re-fetch, and one nobody can point to a reason
    for is a cost with no purchase.
    """

    REFUSED = {"dialectronics": 4.0, "vgamuseum-doc": 4.0}
    ASKED = ("develooper-hpux", "seds-frommert", "obsolyte")

    def test_the_two_that_refused_keep_the_pace_that_was_measured(self):
        for archive, pace in self.REFUSED.items():
            self.assertIn(archive, MIRROR.MIN_INTERVAL, archive)
            self.assertGreaterEqual(MIRROR.MIN_INTERVAL[archive], pace, archive)

    def test_the_three_that_asked_in_words_keep_theirs(self):
        for archive in self.ASKED:
            self.assertIn(archive, MIRROR.MIN_INTERVAL, archive)

    def test_THE_FRAGILE_HOST_KEEPS_ITS_SINGLE_CONNECTION(self):
        """obsolyte.com states on its own front page that it runs on a SPARC IPX with 64 MB."""
        self.assertEqual(MIRROR.WORKERS_BY_ARCHIVE.get("obsolyte"), 1)

    def test_no_host_is_paced_without_a_reason_being_findable(self):
        """Every paced archive must be named in a comment near its entry -- checked crudely, by
        asking that the source mentions it within the MIN_INTERVAL block."""
        import io as _io
        with _io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
            source = fh.read()
        block = source[source.index("MIN_INTERVAL = {"):]
        block = block[:block.index("\n}")]
        for archive in MIRROR.MIN_INTERVAL:
            self.assertIn(archive, block, archive)


if __name__ == "__main__":
    unittest.main(verbosity=2)
