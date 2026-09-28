#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""holes-vs-source.py, without asking anybody.

WHAT THE TOOL CLAIMS AND WHAT IS TESTABLE. It decides whether a hole `--holes` found is also in
the source's copy, by asking for that one 1 MiB block instead of the whole file -- a megabyte
instead of four gigabytes. Everything except the socket can be checked here: which findings it
reads out of the run's logs, which blocks it picks, the address it builds, and which of the six
verdicts an answer earns. `http_open` is replaced for the verdict cases.

THE ONE THAT WOULD HAVE COST MOST is `test_a_200_is_not_read_to_the_end`. A server that ignores
the Range header answers 200 and starts sending the WHOLE file. Several of these are gigabytes,
and one of them is 4 GB: reading that response to the end would turn a one-megabyte question into
a download nobody asked for, on somebody else's server, in a tool whose whole point is to be
cheap. It must be recognised and abandoned.

AND ONE THE PROJECT'S OWN CONTRACT CAUGHT BEFORE THIS FILE EXISTED. The first version built its
own `urllib.request.Request`, which meant it asked for a megabyte with no User-Agent at all.
`contract-mutations.py` reported the suite red on `test_urlopen_is_called_in_exactly_one_file` --
a rule that reads like bookkeeping and is not: `common.http_open` is where the collection's
identity is attached, and going around it drops that identity silently.
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("holes-vs-source")
BLK = TOOL.BLK

REGISTER = {"an-archive": "https://example.invalid/pub/",
            "over-rsync": "rsync://example.invalid/mod/"}


class FakeResponse:
    def __init__(self, code, body=b""):
        self._code = code
        self._body = body
        self.read_calls = []

    def getcode(self):
        return self._code

    def read(self, n=None):
        self.read_calls.append(n)
        return self._body if n is None else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class WhichFindingsItReads(unittest.TestCase):
    """The logs are the record -- re-running --holes to find out is 2.39 TB and five hours."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="holes-vs-source-")
        with io.open(os.path.join(self.tmp, "arc.log"), "w", encoding="utf-8") as fh:
            fh.write("=== Holes: entirely empty blocks in the middle of a file ===\n"
                     "  (reads every file of 16 MB or more in full)\n"
                     "    99.3 MB     1/ 100 blocks empty (1.0 %)  dir/one.toast\n"
                     "   314.0 MB    48/ 315 blocks empty (15.2 %)  dir/two.iso\n"
                     "  2 incomplete files, 500 files read in full\n"
                     "\n=== archive finished ===  arc  10.0 s\n")

    def test_it_finds_the_rows_and_not_the_summary(self):
        got = TOOL.findings(self.tmp)
        self.assertEqual(got, [("arc", "dir/one.toast"), ("arc", "dir/two.iso")])

    def test_a_log_with_no_findings_contributes_nothing(self):
        with io.open(os.path.join(self.tmp, "clean.log"), "w", encoding="utf-8") as fh:
            fh.write("  0 incomplete files, 3 files read in full\n\n=== archive finished ===\n")
        self.assertEqual(len(TOOL.findings(self.tmp)), 2)

    def test_the_archive_name_comes_from_the_file_name(self):
        self.assertEqual({a for a, _r in TOOL.findings(self.tmp)}, {"arc"})


class WhichBlocksItPicks(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="holes-vs-source-")

    def write(self, pattern):
        """pattern: a string of 'x' (content) and '0' (a whole empty block)."""
        path = os.path.join(self.tmp, "f.bin")
        with io.open(path, "wb") as fh:
            for ch in pattern:
                fh.write(bytes(BLK) if ch == "0" else b"\xff" * BLK)
        return path

    def test_it_finds_every_empty_block_when_there_are_few(self):
        picks, total = TOOL.empty_blocks(self.write("x0x0x"))
        self.assertEqual(picks, [1, 3])
        self.assertEqual(total, 5)

    def test_FIRST_MIDDLE_AND_LAST_when_there_are_many(self):
        """Spread across the file on purpose.

        One block agreeing could be luck -- a disc image is zeros nearly everywhere, so hitting
        one says nothing about the file. Three spread out is a statement about the shape of the
        damage.
        """
        picks, total = TOOL.empty_blocks(self.write("x00000000x"), limit=3)
        self.assertEqual(len(picks), 3)
        self.assertEqual(picks[0], 1)
        self.assertEqual(picks[-1], 8)
        self.assertEqual(total, 10)

    def test_a_file_with_no_empty_block_yields_nothing_to_ask(self):
        picks, _total = TOOL.empty_blocks(self.write("xxx"))
        self.assertEqual(picks, [])

    def test_a_short_last_block_still_counts_as_empty(self):
        path = os.path.join(self.tmp, "short.bin")
        with io.open(path, "wb") as fh:
            fh.write(b"\xff" * BLK)
            fh.write(bytes(100))
        picks, total = TOOL.empty_blocks(path)
        self.assertEqual((picks, total), ([1], 2))


class TheAddressItBuilds(unittest.TestCase):

    def test_a_plain_row(self):
        self.assertEqual(TOOL.source_url("an-archive", "a/b.toast", REGISTER),
                         "https://example.invalid/pub/a/b.toast")

    def test_a_space_is_encoded_and_a_slash_is_not(self):
        got = TOOL.source_url("an-archive", "QNX 6/x", REGISTER)
        self.assertEqual(got, "https://example.invalid/pub/QNX%206/x")
        self.assertNotIn("%2F", got)

    def test_rsync_cannot_be_asked(self):
        self.assertIsNone(TOOL.source_url("over-rsync", "a/b", REGISTER))

    def test_an_unknown_archive_cannot_be_asked(self):
        self.assertIsNone(TOOL.source_url("never-heard-of-it", "a/b", REGISTER))


class WhichVerdictAnAnswerEarns(unittest.TestCase):

    def ask(self, code, body=b""):
        resp = FakeResponse(code, body)
        self.last = resp
        return TOOL.one_block("https://example.invalid/x", 3,
                              opener=lambda *a, **k: resp)

    def test_a_206_of_zeros_is_no_problem_and_returns_the_bytes(self):
        problem, blob = self.ask(206, bytes(BLK))
        self.assertIsNone(problem)
        self.assertTrue(TOOL.judge(blob))

    def test_a_206_with_content_is_the_finding_worth_having(self):
        problem, blob = self.ask(206, b"MZ" + bytes(BLK - 2))
        self.assertIsNone(problem)
        self.assertFalse(TOOL.judge(blob))

    def test_A_200_IS_NOT_READ_TO_THE_END(self):
        """A server that ignores the Range starts sending the whole file -- up to 4 GB here.

        The verdict must come from the status alone, and the response must be abandoned. Reading
        it would turn a one-megabyte question into a download nobody asked for.
        """
        problem, blob = self.ask(200, b"x" * 1000)
        self.assertEqual(problem, TOOL.NO_RANGE)
        self.assertEqual(blob, b"")
        self.assertEqual(self.last.read_calls, [])

    def test_any_other_status_is_the_server_refusing(self):
        for code in (204, 416, 403):
            self.assertEqual(self.ask(code)[0], TOOL.REFUSED, code)

    def test_an_http_error_is_a_refusal_and_a_socket_error_is_not(self):
        """`http_try`'s distinction, kept here too: a 404 is settled, a timeout is not."""
        def raise_http(*a, **k):
            exc = OSError("nope")
            exc.code = 404
            raise exc

        def raise_socket(*a, **k):
            raise TimeoutError("nobody home")

        # A REAL URL, because `http_open` parses it before the opener is ever reached. The
        # first version of this test passed "u" and got GONE for both cases -- from
        # `ValueError: unknown url type`, which is the tool correctly reporting a failure that
        # had nothing to do with either branch under test.
        url = "https://example.invalid/x"
        self.assertEqual(TOOL.one_block(url, 0, opener=raise_http)[0], TOOL.REFUSED)
        self.assertEqual(TOOL.one_block(url, 0, opener=raise_socket)[0], TOOL.GONE)

    def test_it_never_raises(self):
        def boom(*a, **k):
            raise ValueError("anything at all")
        self.assertEqual(TOOL.one_block("https://example.invalid/x", 0, opener=boom)[0],
                         TOOL.GONE)


class TheSummaryCannotLoseAnything(unittest.TestCase):

    def test_every_verdict_is_in_ORDER(self):
        named = {getattr(TOOL, n) for n in
                 ("SAME", "CONTENT", "NO_RANGE", "REFUSED", "GONE", "UNASKABLE")}
        self.assertEqual(set(TOOL.ORDER), named)
        self.assertEqual(len(TOOL.ORDER), len(named))

    def test_the_one_that_needs_acting_on_comes_first(self):
        self.assertEqual(TOOL.ORDER[0], TOOL.CONTENT)

    def test_the_verdicts_are_distinct(self):
        self.assertEqual(len(set(TOOL.ORDER)), 6)


class ItGoesThroughTheLibrary(unittest.TestCase):
    """The contract that caught the first version, asserted here so it stays caught."""

    def test_it_does_not_call_urlopen_itself(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(here, "holes-vs-source.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("urllib.request.urlopen", src)
        self.assertNotIn("urllib.request.Request", src)
        self.assertIn("http_open", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
