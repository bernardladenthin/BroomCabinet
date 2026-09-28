#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""ask-the-source.py, without asking anybody.

WHAT IS UNDER TEST AND WHAT IS NOT. Every host this tool talks to is somebody else's and may be
gone tomorrow -- that is the whole reason the tool exists -- so a test that reached out would fail
for the one reason that says nothing about the code. What is testable is all of it except the
socket: which rows can be asked at all, how an address is built from the register, and which of
the six verdicts a given answer earns. `http_try` is replaced for the verdict cases.

THE ONE THAT WOULD HAVE COST MOST is `test_every_verdict_is_in_ORDER`. The summary loops over
`ORDER` and prints what it finds; a verdict missing from that tuple would vanish from the report
while still being counted, which is how "51 the same, 0 different" could come out of a run that
had found something different. The tool checks its own arithmetic at runtime and returns 2 -- this
makes sure the check can never be needed.
"""
import importlib.util
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402
import common  # noqa: E402


def load(name):
    """Import a hyphenated script as a LIVE module.

    `runpy.run_path` returns a COPY of the globals, so replacing `http_try` in it changes nothing
    and the tests reach the network instead -- which is how three of them first went green
    against a real server and one silently proved the opposite of what it claimed.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("ask-the-source")

REGISTER = {"an-archive": "https://example.invalid/pub/",
            "over-rsync": "rsync://example.invalid/mod/",
            "trailing": "https://example.invalid/pub",
            # A SECOND HOST, because pacing per host and pacing per archive cannot be told apart
            # with only one domain in the table -- `an-archive` and `trailing` share example.invalid.
            "elsewhere": "https://other.invalid/files/"}


class WhichRowsCanBeAskedAtAll(unittest.TestCase):

    def test_a_plain_row_becomes_an_address(self):
        self.assertEqual(TOOL.address("an-archive/dir/file.htm", REGISTER),
                         "https://example.invalid/pub/dir/file.htm")

    def test_a_space_in_a_path_is_encoded(self):
        """`fsck-vendors/QNX/QNX 6/...` is a real row and a bare space is not a URL."""
        self.assertEqual(TOOL.address("an-archive/QNX 6/x", REGISTER),
                         "https://example.invalid/pub/QNX%206/x")

    def test_a_slash_in_the_path_stays_a_slash(self):
        # quote() must be applied per segment. Applied to the whole tail it escapes the
        # separators too, and every request 404s for a reason nobody would guess.
        self.assertNotIn("%2F", TOOL.address("an-archive/a/b/c", REGISTER))

    def test_a_missing_trailing_slash_does_not_produce_a_double_one(self):
        self.assertEqual(TOOL.address("trailing/x", REGISTER),
                         "https://example.invalid/pub/x")

    def test_an_rsync_archive_cannot_be_asked(self):
        self.assertIsNone(TOOL.address("over-rsync/dir/file", REGISTER))

    def test_an_archive_not_in_the_register_cannot_be_asked(self):
        self.assertIsNone(TOOL.address("never-heard-of-it/file", REGISTER))

    def test_THE_ROW_IS_SPLIT_AT_THE_FIRST_SLASH_AND_NOWHERE_ELSE(self):
        """This tool's own rule, and the only part of addressing that is still its own.

        Its rows are COLLECTION-relative; common.source_url() takes an archive and a path within
        it. Splitting on the last slash, or on every slash, both produce a URL that looks
        plausible and 404s.
        """
        self.assertEqual(TOOL.address("an-archive/a/b/c.pdf", REGISTER),
                         "https://example.invalid/pub/a/b/c.pdf")

    def test_A_ROW_THAT_IS_ONLY_AN_ARCHIVE_NAME_ASKS_FOR_ITS_ROOT(self):
        """Not expected in these tables. None would be a second, silent reason for UNASKABLE."""
        self.assertEqual(TOOL.address("an-archive", REGISTER), "https://example.invalid/pub/")

    def test_AN_RSYNC_ARCHIVE_WITH_AN_HTTP_FACE_IS_NOW_ASKABLE_HERE_TOO(self):
        """The behaviour this tool GAINED on 2026-09-27, and the reason for the consolidation.

        It held its own copy of source_url() without the HTTP_FACE fallback, so every bitsavers
        row came back UNASKABLE while holes-vs-source.py answered a working URL for the same
        input. Two tools agreeing and a third quietly asking less, with no test able to see it.
        """
        register = dict(REGISTER, bitsavers="rsync://bitsavers.org/bits/")
        got = TOOL.address("bitsavers/pdf/x.zip", register)
        self.assertEqual(got, "https://bitsavers.org/pdf/x.zip")

    def test_the_register_is_read_and_not_guessed(self):
        """The register really is mirror.ARCHIVES, and every row's archive is in it.

        A row whose archive has been renamed would come back UNASKABLE -- quietly, and for a
        reason that has nothing to do with the host.
        """
        register = TOOL.prefixes()
        self.assertGreater(len(register), 20)
        unaskable = sorted({rel.split("/")[0] for rel, _s in audit.ZERO_AT_SOURCE
                            if TOOL.address(rel, register) is None})
        self.assertEqual(unaskable, [])


class WhichVerdictAnAnswerEarns(unittest.TestCase):
    """The six outcomes, with the socket replaced."""

    def setUp(self):
        self.real = TOOL.http_try
        self.rows = [("an-archive/f", 10)]

    def tearDown(self):
        TOOL.http_try = self.real

    def answer_row(self, status, body):
        TOOL.http_try = lambda url, timeout=None: (status, body)
        return TOOL.ask(self.rows, REGISTER, pause=0)[0]

    def answer(self, status, body):
        return self.answer_row(status, body)[0]

    def test_zeros_at_the_recorded_length_are_unchanged(self):
        self.assertEqual(self.answer(200, bytes(10)), TOOL.SAME)

    def test_content_where_zeros_were_is_the_finding_worth_having(self):
        self.assertEqual(self.answer(200, b"\x89PNG\r\n\x1a\n\x00\x00"), TOOL.CHANGED)

    def test_zeros_at_a_different_length_are_not_the_same_row(self):
        """Still empty, but no longer the file that was measured -- so the record is stale.

        Reporting this as unchanged would let the table go on describing a file that no longer
        exists at that length, which is the quiet failure this tool is against.
        """
        self.assertEqual(self.answer(200, bytes(11)), TOOL.LENGTH)

    def test_a_server_that_answers_without_the_file_is_not_the_same_as_no_server(self):
        """THE BUG THIS TEST WAS WRITTEN TO CATCH, and it caught it on the first run.

        `http_try` returns bytes ALWAYS -- empty on failure -- and puts the distinction in
        `status`: an int when a server answered, a string naming the failure when none did. This
        tool branched on `isinstance(body, bytes)`, which is true even for a 404, so the
        "nobody answered" branch could never be taken. So could the branch in the throwaway
        script that first filled `ZERO_AT_SOURCE`: its "0 unreachable" was a line that could not
        have said anything else.

        The measurement survived -- an empty body has length 0, fails the same-length test and
        lands in another bucket, and that bucket was empty -- but a report that cannot say "gone"
        is not a report.
        """
        self.assertEqual(self.answer(404, b""), TOOL.REFUSED)
        self.assertEqual(self.answer(500, b""), TOOL.REFUSED)
        self.assertEqual(self.answer("URLError", b""), TOOL.GONE)
        self.assertEqual(self.answer("TimeoutError", b""), TOOL.GONE)

    def test_the_failure_is_named_in_the_detail(self):
        """"nobody answered" alone does not tell you whether to try again next week."""
        got = self.answer_row("URLError", b"")
        self.assertIn("URLError", got[3])
        got = self.answer_row(404, b"")
        self.assertIn("404", got[3])

    def test_a_row_with_no_address_is_reported_and_not_dropped(self):
        TOOL.http_try = lambda url, timeout=None: self.fail("must not ask")
        got = TOOL.ask([("over-rsync/f", 10)], REGISTER, pause=0)
        self.assertEqual(got[0][0], TOOL.UNASKABLE)

    def test_every_row_gets_exactly_one_verdict(self):
        TOOL.http_try = lambda url, timeout=None: (200, bytes(10))
        rows = [("an-archive/a", 10), ("over-rsync/b", 10), ("an-archive/c", 10)]
        got = TOOL.ask(rows, REGISTER, pause=0)
        self.assertEqual(len(got), len(rows))
        self.assertEqual([r[1] for r in got], [r[0] for r in rows])


class TheSummaryCannotLoseAnything(unittest.TestCase):

    def test_every_verdict_is_in_ORDER(self):
        named = {getattr(TOOL, n)
                 for n in ("SAME", "CHANGED", "LENGTH", "REFUSED", "GONE", "UNASKABLE")}
        self.assertEqual(set(TOOL.ORDER), named)
        self.assertEqual(len(TOOL.ORDER), len(named))

    def test_the_two_that_need_acting_on_come_first(self):
        # A report read top-down must open with what changed, not with 75 rows of agreement.
        self.assertEqual(TOOL.ORDER[:2], (TOOL.CHANGED, TOOL.LENGTH))

    def test_the_verdicts_are_distinct_strings(self):
        # They key a dict. Two equal ones would merge two outcomes into one count in silence.
        self.assertEqual(len(set(TOOL.ORDER)), 6)


class AnUnknownArchiveIsNotACleanRun(unittest.TestCase):
    """--under with a name the table does not carry.

    Filtering to nothing and returning 0 is how somebody checks an archive, sees no findings and
    believes it -- having asked about zero files. The same shape as the branch that could never
    be taken, one level up: a run that cannot fail is not a check.
    """

    def run_tool(self, *argv):
        out = io.StringIO()
        keep = sys.stdout
        sys.stdout = out
        try:
            code = TOOL.main(list(argv))
        finally:
            sys.stdout = keep
        return code, out.getvalue()

    def test_a_typo_is_refused_rather_than_reported_as_nothing_found(self):
        code, text = self.run_tool("--under", "fsck-vendorz")
        self.assertEqual(code, 2)
        self.assertIn("fsck-vendorz", text)

    def test_and_it_names_the_archives_that_do_have_rows(self):
        _code, text = self.run_tool("--under", "nope")
        for archive in {rel.split("/")[0] for rel, _s in audit.ZERO_AT_SOURCE}:
            self.assertIn(archive, text)

    def test_it_asks_nobody_while_refusing(self):
        self.real, TOOL.http_try = TOOL.http_try, lambda *a, **k: self.fail("must not ask")
        try:
            self.assertEqual(self.run_tool("--under", "nope")[0], 2)
        finally:
            TOOL.http_try = self.real


class ItPacesItselfPerHost(unittest.TestCase):
    """That this tool USES the pacing -- the pacing itself is tested in `common_test.py`.

    The two are different questions and the split is on purpose. `TestPacer` proves the waiting
    is right; these prove `ask()` actually calls it, once per request, per host, and not for a
    row it never asked about. A tool can import a correct helper and forget to use it.
    """

    def setUp(self):
        self.real = TOOL.http_try
        TOOL.http_try = lambda url, timeout=None: (200, bytes(10))
        self.now = [0.0]
        self.slept = []

    def tearDown(self):
        TOOL.http_try = self.real

    def clock(self):
        return self.now[0]

    def sleep(self, seconds):
        self.slept.append(round(seconds, 6))
        self.now[0] += seconds

    def run_rows(self, rows, pause=0.7):
        return TOOL.ask(rows, REGISTER,
                        pacer=common.Pacer(pause, clock=self.clock, sleep=self.sleep))

    def test_the_first_request_to_a_host_does_not_wait(self):
        self.run_rows([("an-archive/a", 10)])
        self.assertEqual(self.slept, [])

    def test_the_second_request_to_the_same_host_waits(self):
        self.run_rows([("an-archive/a", 10), ("an-archive/b", 10)])
        self.assertEqual(self.slept, [0.7])

    def test_a_different_host_does_not_wait_behind_the_first(self):
        """Two hosts do not share a wait -- the whole reason the pause is per host."""
        self.run_rows([("an-archive/a", 10), ("elsewhere/b", 10)])
        self.assertEqual(self.slept, [])

    def test_two_archives_of_the_SAME_host_do_share_the_wait(self):
        """`an-archive` and `trailing` are different archives on one domain.

        Pacing by archive would let them fire back to back at the same server, which is the
        politeness this is for. Without a second domain in REGISTER the two rules are
        indistinguishable, which is why there is one.
        """
        self.run_rows([("an-archive/a", 10), ("trailing/b", 10)])
        self.assertEqual(self.slept, [0.7])

    def test_time_already_spent_on_the_request_counts_towards_the_wait(self):
        """A slow server has already paid the pause. Sleeping the full amount on top doubles it."""
        rows = [("an-archive/a", 10), ("an-archive/b", 10)]

        def slow(url, timeout=None):
            self.now[0] += 0.5          # the request itself took half the pause
            return (200, bytes(10))
        TOOL.http_try = slow
        self.run_rows(rows)
        self.assertEqual(self.slept, [0.2])

    def test_a_request_slower_than_the_pause_never_waits(self):
        def slower(url, timeout=None):
            self.now[0] += 5.0
            return (200, bytes(10))
        TOOL.http_try = slower
        self.run_rows([("an-archive/a", 10), ("an-archive/b", 10)])
        self.assertEqual(self.slept, [])

    def test_an_unaskable_row_costs_nothing(self):
        # Nobody was asked, so there is nobody to be polite to.
        self.run_rows([("over-rsync/a", 10), ("over-rsync/b", 10)])
        self.assertEqual(self.slept, [])


class TheProgressReportIsOptional(unittest.TestCase):
    """A library says nothing unless asked -- the same rule the four checks in audit.py follow."""

    def setUp(self):
        self.real = TOOL.http_try
        TOOL.http_try = lambda url, timeout=None: (200, bytes(10))

    def tearDown(self):
        TOOL.http_try = self.real

    def test_it_is_silent_without_report(self):
        """BOTH STREAMS CAPTURED, because the obvious way to write this asserts nothing.

        `said = []; ask(rows); assertEqual(said, [])` passes whatever the code does -- nothing
        ever appends to that list. It was written that way once in this project and sat green.
        The only way to test silence is to capture the streams the function could actually
        speak on.
        """
        rows = [("an-archive/%d" % i, 10) for i in range(25)]
        out, err = io.StringIO(), io.StringIO()
        keep = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            TOOL.ask(rows, REGISTER, pause=0)
        finally:
            sys.stdout, sys.stderr = keep
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")

    def test_it_speaks_when_asked(self):
        said = []
        rows = [("an-archive/%d" % i, 10) for i in range(25)]
        TOOL.ask(rows, REGISTER, report=said.append, pause=0)
        self.assertTrue(said)
        self.assertTrue(all("asked" in line for line in said))


if __name__ == "__main__":
    unittest.main(verbosity=2)
