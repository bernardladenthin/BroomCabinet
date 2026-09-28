#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""`contract-mutations.py` must refuse to run twice at once.

WHY THIS EXISTS. That script edits the library IN PLACE -- it breaks a rule, runs the suite, and
puts the original back -- so two of it at once is not a slow run but a corrupt one. On 2026-09-25
two gate runs overlapped: one read `common.py` while the other had it mutated and reported the
suite red, and then the second removed the first's working copy, which died with
`FileNotFoundError`. Nothing was lost, and only because the mutation happened to be restorable.

The fix is small because the machinery was already there: the script copies each target to
`<file>.mutating` before touching it, so the existence of one of those IS the lock. What it needed
was to look before it wrote.

IT DOES NOT DISTINGUISH A LEFTOVER FROM A LIVE INSTANCE, and that is deliberate. Either something
is running now, or something died holding the original; in both cases the file on disk may not be
the file somebody wrote, and that is a person's decision rather than a flag to clear. The refusal
prints the `diff` that answers it.

WHAT THIS TEST GUARDS ABOVE ALL: that the refusal happens BEFORE anything is written. A lock that
refuses after copying would be a lock that still corrupts.
"""
import hashlib
import importlib.util
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load():
    path = os.path.join(HERE, "contract-mutations.py")
    spec = importlib.util.spec_from_file_location("contract_mutations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load()
LIBRARY = os.path.join(HERE, "common.py")
LOCK = LIBRARY + ".mutating"


def digest(path):
    with io.open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class TheLock(unittest.TestCase):

    def setUp(self):
        self.assertFalse(os.path.exists(LOCK),
                         "a working copy is lying around before the test even starts -- "
                         "something died holding it, and that is what this test is about")
        self.before = digest(LIBRARY)

    def tearDown(self):
        if os.path.exists(LOCK):
            os.remove(LOCK)
        self.assertEqual(digest(LIBRARY), self.before, "the library changed during the test")

    def run_tool(self):
        out = io.StringIO()
        keep_out, keep_argv = sys.stdout, sys.argv
        sys.stdout, sys.argv = out, ["contract-mutations.py", "--apply"]
        try:
            code = TOOL.main()
        finally:
            sys.stdout, sys.argv = keep_out, keep_argv
        return code, out.getvalue()

    def test_IT_REFUSES_AND_WRITES_NOTHING(self):
        """The whole point: the refusal happens before the first byte is copied."""
        with io.open(LOCK, "wb") as fh:
            fh.write(b"pretend another run is holding this")
        code, text = self.run_tool()
        self.assertEqual(code, 2)
        self.assertIn("REFUSING TO RUN", text)
        self.assertEqual(digest(LIBRARY), self.before)

    def test_it_names_the_file_it_found(self):
        """A refusal that does not say what is in the way is a refusal nobody can act on."""
        with io.open(LOCK, "wb") as fh:
            fh.write(b"x")
        _code, text = self.run_tool()
        self.assertIn("common.py.mutating", text)

    def test_it_says_how_to_decide_rather_than_how_to_clear_it(self):
        """Deleting the working copy blind is how a mutation becomes permanent.

        So the message must offer the comparison, not an --force flag. This checks that the
        instruction is a `diff`, which is the one command that answers which file is the good one.
        """
        with io.open(LOCK, "wb") as fh:
            fh.write(b"x")
        _code, text = self.run_tool()
        self.assertIn("diff", text)
        self.assertNotIn("--force", text)

    def test_the_working_copy_of_ANY_target_is_enough_to_stop_it(self):
        """The lock is derived from the mutations, like the backups are.

        A hand-written list of lock files would be the same bug the backups already avoided:
        a mutation added for a new module, and that module left unguarded.
        """
        targets = {t for _label, t, _old, _new in TOOL.MUTATIONS}
        self.assertGreater(len(targets), 1)
        other = sorted(t for t in targets if os.path.basename(t) != "common.py")[0]
        lock = other + ".mutating"
        with io.open(lock, "wb") as fh:
            fh.write(b"x")
        try:
            code, text = self.run_tool()
            self.assertEqual(code, 2)
            self.assertIn(os.path.basename(other), text)
        finally:
            os.remove(lock)


class TheMutationsThemselves(unittest.TestCase):
    """Cheap structural checks that do not run anything."""

    def test_every_mutation_names_a_file_that_exists(self):
        for _label, target, _old, _new in TOOL.MUTATIONS:
            self.assertTrue(os.path.exists(target), target)

    def test_every_mutation_has_a_label(self):
        for label, _t, _o, _n in TOOL.MUTATIONS:
            self.assertTrue(label.strip())

    def test_no_mutation_is_a_no_op(self):
        # old == new would pass silently for ever: the suite stays green because nothing changed.
        for label, _t, old, new in TOOL.MUTATIONS:
            self.assertNotEqual(old, new, label)

    def test_without_apply_it_touches_nothing(self):
        out = io.StringIO()
        keep_out, keep_argv = sys.stdout, sys.argv
        sys.stdout, sys.argv = out, ["contract-mutations.py"]
        try:
            before = digest(LIBRARY)
            code = TOOL.main()
        finally:
            sys.stdout, sys.argv = keep_out, keep_argv
        self.assertEqual(code, 0)
        self.assertEqual(digest(LIBRARY), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
