# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Do the checking tools say NO with their exit code, and not only with their text?

WHY THIS FILE EXISTS, AND IT IS NOT A DEFECT REPORT. On 2026-09-24 `mirror.py --verify` was
written up as "reports MISMATCH and exits 0", which would have made it useless as a gate. It was
measured like this:

    python mirror.py --verify ... | tail -10; echo "rc=$?"

`$?` after a pipeline is the LAST command's status, so that read `tail`'s success. The tool had
been returning 1 all along. The same mistake was made twice in one session, on `--verify` and on
`--index`, and nearly produced a "fix" to code that was already right.

So the exit codes are pinned here instead of being re-measured by hand. A test runs the tool as a
subprocess and reads returncode, where no pipeline can get in the way.

EVERY CASE BUILDS ITS OWN TREE. Nothing here touches the real collection; a fake root with a real
archive NAME is enough, because --verify only ever looks under --root.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import common

HERE = os.path.dirname(os.path.abspath(__file__))
MIRROR = os.path.join(HERE, "mirror.py")

# A name mirror.py's own ARCHIVES table knows, so --archive matches. Which one does not matter:
# --verify reads the tree under --root and never reaches the network.
KNOWN = "gsi-collection"


def run(*args):
    """-> (returncode, output). No shell, no pipeline, nothing between us and the status."""
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = tempfile.gettempdir()
    env.pop("MIRROR_ROOT", None)          # or an inherited root would answer for us
    p = subprocess.run([sys.executable, MIRROR] + list(args), capture_output=True, env=env)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


class Fake(object):
    """A root holding one archive, its files, and whatever marker the case wants."""

    def __init__(self, files=(), marker=None):
        self.root = tempfile.mkdtemp(prefix="exitcodes-")
        self.path = os.path.join(self.root, KNOWN)
        os.makedirs(self.path)
        for name, body in files:
            with io.open(os.path.join(self.path, name), "wb") as fh:
                fh.write(body)
        if marker is not None:
            common.write_marker(os.path.join(self.path, common.COMPLETE_MARKER), marker,
                                "This mirror is complete.")

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestVerifyExitCode(unittest.TestCase):

    def test_a_tree_that_matches_its_marker_exits_0(self):
        f = Fake(files=[("a.bin", b"x" * 10)],
                 marker={"archive": KNOWN, "files": "1", "bytes": "10"})
        try:
            rc, out = run("--root", f.root, "--verify", "--archive", KNOWN)
            self.assertIn("UNCHANGED", out)
            self.assertEqual(rc, 0, out)
        finally:
            f.close()

    def test_A_MISMATCH_EXITS_1(self):
        """The case the write-up got wrong, and the reason this file exists.

        A gate calls this and reads the status. If MISMATCH came back as 0 the gate would go
        green while the tool was saying the archive disagrees with its own marker.
        """
        f = Fake(files=[("a.bin", b"x" * 10), ("b.bin", b"y" * 5)],
                 marker={"archive": KNOWN, "files": "1", "bytes": "10"})
        try:
            rc, out = run("--root", f.root, "--verify", "--archive", KNOWN)
            self.assertIn("MISMATCH", out)
            self.assertEqual(rc, 1, out)
        finally:
            f.close()

    def test_AND_SO_DOES_AN_ARCHIVE_THAT_WAS_NEVER_MARKED_COMPLETE(self):
        # "no marker" is not "nothing to check". An unmarked archive is one whose crawl never
        # finished, which a verification pass must not report as fine.
        f = Fake(files=[("a.bin", b"x" * 10)])
        try:
            rc, out = run("--root", f.root, "--verify", "--archive", KNOWN)
            self.assertIn("never marked complete", out)
            self.assertEqual(rc, 1, out)
        finally:
            f.close()

    def test_one_bad_archive_does_not_stop_the_others_being_checked(self):
        """`all()` short-circuits, and a list is what stops it doing so here.

        The comment in mirror.py says a generator once ended the run on the first failure and
        left every later mirror unchecked -- the opposite of what a verification pass is for.
        """
        f = Fake(files=[("a.bin", b"x" * 10)],
                 marker={"archive": KNOWN, "files": "99", "bytes": "99"})
        try:
            second = os.path.join(f.root, "ardent-tool")
            os.makedirs(second)
            with io.open(os.path.join(second, "c.bin"), "wb") as fh:
                fh.write(b"z" * 4)
            common.write_marker(os.path.join(second, common.COMPLETE_MARKER),
                                {"archive": "ardent-tool", "files": "1", "bytes": "4"},
                                "This mirror is complete.")
            rc, out = run("--root", f.root, "--verify", "--archive", KNOWN,
                          "--archive", "ardent-tool")
            self.assertIn("MISMATCH", out)
            self.assertIn("UNCHANGED", out)      # the second one was still reached
            self.assertEqual(rc, 1, out)
        finally:
            f.close()


class TestRefusalExitCodes(unittest.TestCase):
    """A run that did nothing must not report success, which is the same rule one step earlier."""

    def test_no_root_anywhere_exits_nonzero(self):
        rc, out = run("--index", "--archive", KNOWN)
        self.assertIn("Where should the mirrors go", out)
        self.assertNotEqual(rc, 0, out)

    def test_an_unknown_archive_name_exits_nonzero(self):
        f = Fake()
        try:
            rc, out = run("--root", f.root, "--verify", "--archive", "no-such-archive-here")
            self.assertIn("no archive matched", out)
            self.assertNotEqual(rc, 0, out)
        finally:
            f.close()

    def test_and_help_exits_0(self):
        # The other direction, so "non-zero" does not quietly become the answer to everything.
        rc, out = run("--help")
        self.assertEqual(rc, 0)
        self.assertIn("--verify", out)


class TestAuditExitCode(unittest.TestCase):
    """The other tool a gate would call, held to the same rule.

    audit-test.py talks about the exit code in two docstrings and never runs the tool to see it.
    Talking about a status is not testing it, which is precisely what went wrong with --verify.
    """

    def audit(self, *args):
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = tempfile.gettempdir()
        p = subprocess.run([sys.executable, os.path.join(HERE, "audit.py")] + list(args),
                           capture_output=True, env=env)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")

    def test_a_clean_tree_exits_0(self):
        d = tempfile.mkdtemp(prefix="auditexit-")
        try:
            a = os.path.join(d, "an-archive")
            os.makedirs(a)
            with io.open(os.path.join(a, "real.txt"), "wb") as fh:
                fh.write(b"this file holds something\n")
            rc, out = self.audit("--empty", "--root", d)
            self.assertEqual(rc, 0, out)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_A_FINDING_EXITS_1(self):
        # A .gz of a plausible size holding nothing but zeros cannot be a .gz, which is the one
        # thing --empty is certain about.
        d = tempfile.mkdtemp(prefix="auditexit-")
        try:
            a = os.path.join(d, "an-archive")
            os.makedirs(a)
            with io.open(os.path.join(a, "broken.gz"), "wb") as fh:
                fh.write(b"\0" * 40000)
            rc, out = self.audit("--empty", "--root", d)
            self.assertEqual(rc, 1, out)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_and_asking_for_nothing_is_refused_rather_than_reported_as_clean(self):
        rc, out = self.audit()
        self.assertIn("Nothing to do", out)
        self.assertNotEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
