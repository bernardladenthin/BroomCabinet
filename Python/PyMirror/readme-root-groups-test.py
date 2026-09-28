#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The README's `--root` lists, re-derived and compared -- the fourth time is the last.

WHY THIS FILE EXISTS. One paragraph of `README.md` names every tool by how it treats `--root`:
which default to `Q:\mirror`, which demand it, which take it bare, which have none. It has gone
stale FOUR times, and it says so itself:

    three tools, then still "three" at eleven          (and catalogue.py in the wrong group)
    2026-09-16   eleven -> seventeen                   (sfv-verify.py had grown a default)
    2026-09-21   six -> seven                          (mediawiki-source.py was added)
    2026-09-24   17/7/2 -> 24/8/2, and a fourth group  (8 tools take no --root at all)

The paragraph already ends with the right instruction -- re-derive the lists, and parse the files
rather than reading a grep by eye, because reading by eye got it wrong twice. That instruction has
been there since the second correction and the paragraph went stale twice more underneath it.
**An instruction to check something by hand is a comment with a runtime cost**, which is the one
thing this project refuses everywhere else. So it is a test.

WHY `ast` AND NOT A REGULAR EXPRESSION. The README says why, from experience: a grep missed a
`required=True` split across lines, and a `default=os.environ.get(...)` that spans two more. A
pattern over source text gets this wrong in exactly the cases that matter -- the unusual ones.
The fourth correction was very nearly made with a regex for the same reason.

WHAT IT DOES NOT DO. It does not check that the numbers are spelled out in words correctly beyond
the four it knows, and it does not police prose. It compares two sets of file names: the ones the
README lists in each group, and the ones the source files actually put there.
"""
import ast
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(HERE, "README.md")

# BUILT FROM THE CONSTANT, not spelled out again. The README names the collection path because
# it documents a default; taking that text from `common.MIRROR_ROOT` means changing the constant
# makes this test demand the README change too, instead of leaving a second copy of the path to
# go stale on its own -- which is the failure this whole file exists to prevent, one level up.
DEFAULT_PHRASE = "default `--root` to `" + common.MIRROR_ROOT + "`"
DEFAULT_ANCHOR = DEFAULT_PHRASE + " --"

WORDS = {2: "Two", 8: "Eight", 24: "Twenty-four", 25: "Twenty-five",
         26: "Twenty-six", 27: "Twenty-seven", 28: "Twenty-eight",
         29: "Twenty-nine", 30: "Thirty", 31: "Thirty-one", 32: "Thirty-two"}


def groups():
    """-> {group: {file names}}, parsed out of the scripts themselves."""
    out = {"default": set(), "required": set(), "plain": set(), "none": set()}
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or "test" in name:
            continue
        with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
            src = fh.read()
        if "argparse" not in src:
            continue
        found = None
        for node in ast.walk(ast.parse(src, name)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument" and node.args):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value == "--root":
                found = {kw.arg: kw.value for kw in node.keywords}
        if found is None:
            out["none"].add(name)
        elif isinstance(found.get("required"), ast.Constant) and found["required"].value is True:
            out["required"].add(name)
        elif "default" in found:
            out["default"].add(name)
        else:
            out["plain"].add(name)
    return out


def listed(after, before):
    """The file names the README names between two anchors."""
    with io.open(README, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index(after) + len(after)
    return set(re.findall(r"`([\w.-]+\.py)`", text[start:text.index(before, start)]))


class TheREADMEAgreesWithTheScripts(unittest.TestCase):

    def setUp(self):
        self.real = groups()

    def test_the_tools_that_default_to_the_collection(self):
        self.assertEqual(listed(DEFAULT_ANCHOR, "** demand `--root`"),
                         self.real["default"])

    def test_the_tools_that_demand_a_root(self):
        self.assertEqual(listed("demand `--root` outright (", "); **"), self.real["required"])

    def test_the_tools_that_take_it_bare(self):
        self.assertEqual(listed("take it without a default (", ")"), self.real["plain"])

    def test_the_tools_that_have_no_root_at_all(self):
        self.assertEqual(listed("take no `--root` at all** —", "— because none of them"),
                         self.real["none"])


class TheCountsInWordsMatchTheLists(unittest.TestCase):
    """The numbers are spelled out, and a wrong word reads exactly like a right one."""

    def setUp(self):
        self.real = groups()

    def test_each_group_is_announced_with_its_own_size(self):
        """The word has to sit immediately before the phrase that introduces the group.

        Checking only that "Eight" appears somewhere in the README would pass while the word sat
        in front of the wrong list -- which is the mistake this paragraph has actually made:
        it read "three" for a long time while naming eleven tools.
        """
        with io.open(README, encoding="utf-8") as fh:
            text = fh.read()
        for group, phrase in (("default", DEFAULT_PHRASE),
                              ("required", "demand `--root` outright"),
                              ("plain", "take it without a default"),
                              ("none", "take no `--root` at all")):
            n = len(self.real[group])
            # A group whose size has no word yet fails HERE, with the number, rather than
            # further down with a KeyError nobody can read.
            self.assertIn(n, WORDS, "no word recorded for %d -- add it to WORDS" % n)
            # The RUN-UP to the phrase, not the whole file. Case is not fixed -- the same word is
            # capitalised at the start of a sentence and not mid-sentence -- and neither is what
            # sits between them ("**Eight** demand", "**And eight take"). What must hold is that
            # the number and its list are next to each other.
            where = text.index(phrase)
            self.assertIn(WORDS[n].lower(), text[max(0, where - 40):where].lower(),
                          "%s: %d, but the run-up says %r"
                          % (group, n, text[max(0, where - 40):where]))

    def test_the_four_groups_account_for_every_script_with_a_parser(self):
        total = sum(len(v) for v in self.real.values())
        with io.open(README, encoding="utf-8") as fh:
            self.assertIn("**%d scripts with an argument parser**" % total, fh.read())

    def test_no_script_is_in_two_groups(self):
        seen = set()
        for names in self.real.values():
            self.assertEqual(seen & names, set())
            seen |= names


class TheDerivationIsWorthTrusting(unittest.TestCase):
    """Guards on the parser itself, because every test above compares two derived sets.

    Two empty sets are equal. If `groups()` stopped finding anything -- a renamed attribute, a
    changed layout -- every comparison above would pass in silence, which is the failure this
    file is against one level up.
    """

    def test_it_finds_a_substantial_number_of_scripts(self):
        self.assertGreater(sum(len(v) for v in groups().values()), 30)

    def test_every_group_has_somebody_in_it(self):
        for group, names in groups().items():
            self.assertTrue(names, group)

    def test_the_anchors_still_match_something(self):
        for after, before in ((DEFAULT_ANCHOR, "** demand `--root`"),
                              ("demand `--root` outright (", "); **"),
                              ("take it without a default (", ")"),
                              ("take no `--root` at all** —", "— because none of them")):
            self.assertTrue(listed(after, before), after)

    def test_a_known_case_lands_where_it_belongs(self):
        """`mirror.py` takes --root and has no default -- the fact the whole section is about."""
        self.assertIn("mirror.py", groups()["plain"])
        self.assertIn("catalogue.py", groups()["required"])
        self.assertIn("common.py", groups()["none"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
