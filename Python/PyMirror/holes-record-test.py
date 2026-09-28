#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The C4 run record must agree with what C4 is said to have found.

WHY. `measurements/holes-run/README.md` states the outcome of the first full `--holes` run: 99
archives, 0 failed, 67 findings. Those numbers were read off a run that took five and a half hours
and will never be repeated casually, so from here on the 99 log files ARE the evidence and the
prose is a summary of them. A summary that quietly stops matching its evidence is worse than no
summary, because it reads exactly the same.

IT USED TO CHECK `TODO.md` TOO, and that half went when the file did on 2026-09-25 -- its last two
items closed and the twenty-two before them had already moved into the things they were about. The
guard did not weaken: the README beside the logs is where this run is written down now, and it is
the copy somebody reading the logs will actually find.

WHAT IT DOES NOT DO. It does not re-read the collection -- that is the five and a half hours. It
re-derives the numbers from the logs, which is the operation the README prints for a human to run
by hand, turned into something that runs by itself.
"""
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "measurements", "holes-run")
README = os.path.join(LOGS, "README.md")

# What the run is recorded as having found. Changing one of these means the run was re-done or
# the record was edited, and either way somebody should have to say so here.
ARCHIVES = 99
FINDINGS = 67

SUMMARY = re.compile(r"^  (\d+) incomplete files?, ", re.M)


def logs():
    return sorted(n for n in os.listdir(LOGS) if n.endswith(".log"))


def read(name):
    with io.open(os.path.join(LOGS, name), encoding="utf-8", errors="replace") as fh:
        return fh.read()


class TheLogsAreComplete(unittest.TestCase):

    def test_there_is_one_log_per_archive(self):
        self.assertEqual(len(logs()), ARCHIVES)

    def test_every_log_says_its_archive_finished(self):
        """A log without the marker is an archive that raised -- there were none."""
        for name in logs():
            self.assertIn(audit and "=== archive finished ===", read(name), name)

    def test_no_log_records_a_failure(self):
        for name in logs():
            self.assertNotIn("THIS ARCHIVE FAILED", read(name), name)

    def test_nothing_was_left_half_written(self):
        # `.part` is what atomic_write leaves behind when it dies mid-write.
        leftovers = [n for n in os.listdir(LOGS) if n.endswith(".part")]
        self.assertEqual(leftovers, [])

    def test_the_error_channel_was_empty(self):
        errs = [n for n in os.listdir(LOGS) if n.endswith(".err")]
        self.assertTrue(errs, "no error channel recorded at all")
        for name in errs:
            self.assertEqual(read(name).strip(), "", name)


class TheFindingsAddUp(unittest.TestCase):

    def total(self):
        return sum(int(m) for name in logs() for m in SUMMARY.findall(read(name)))

    def test_the_logs_total_what_the_run_reported(self):
        self.assertEqual(self.total(), FINDINGS)

    def test_the_runner_output_says_the_same(self):
        """Two independent statements: the per-archive logs, and the runner's own last line."""
        outs = [n for n in os.listdir(LOGS) if n.endswith(".out")]
        self.assertTrue(outs)
        text = "".join(read(n) for n in outs)
        self.assertIn("%d archive(s) read, %d finding(s), 0 failed" % (ARCHIVES, FINDINGS), text)

    def test_every_log_has_exactly_one_summary_line(self):
        # Two would mean a log was appended to rather than written whole, which would break the
        # arithmetic above without breaking anything visible.
        for name in logs():
            self.assertEqual(len(SUMMARY.findall(read(name))), 1, name)


class ThePoseAgreesWithTheEvidence(unittest.TestCase):
    """The numbers in the prose, against the numbers in the logs."""

    def prose(self):
        with io.open(README, encoding="utf-8") as fh:
            return fh.read()

    def test_the_readme_states_the_finding_count(self):
        self.assertIn(str(FINDINGS), self.prose())

    def test_the_readme_states_the_archive_count(self):
        self.assertIn(str(ARCHIVES), self.prose())

    def test_the_three_settled_files_are_recorded_and_counted_as_such(self):
        """3 in the table, and 67 - 3 = 64 left over -- the README says both."""
        self.assertEqual(len(audit.HOLES_AT_SOURCE), 3)
        self.assertIn("64", self.prose())

    def test_the_readme_is_there_at_all(self):
        # A directory of 99 logs and no explanation is a directory nobody dares delete from.
        self.assertTrue(os.path.exists(README))


if __name__ == "__main__":
    unittest.main(verbosity=2)
