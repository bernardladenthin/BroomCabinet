#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""robots.py: the parser and the verdict, on invented input.

MOVED OUT OF common_test.py ON 2026-09-23 with the module it tests, unchanged.

TWO TEST FILES, TWO DIFFERENT QUESTIONS, and neither replaces the other:

  this one              does the parser do what it says, on cases chosen to be awkward
  robots_verdict_test.py  what do SEVEN REAL robots.txt files from this collection say

An invented case can be made to cover any rule; only a real file can show that the rule
matters. The real ones are the reason the parser has the shape it has, and they stay in their
own file because they are a corpus, not a unit test.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robots  # noqa: E402

class TestRobotsGroups(unittest.TestCase):
    """The parser, on its own. robots_verdict_test.py holds the seven real files; this holds the
    shapes those files are made of, and the ones they do not happen to contain."""

    def test_one_group(self):
        self.assertEqual(robots.robots_groups("User-agent: *\nDisallow: /pub/"),
                         [(["*"], ["/pub/"])])

    def test_MANY_AGENTS_SHARING_ONE_RULE_ARE_ONE_GROUP(self):
        # A run of agent lines with one Disallow beneath them names many agents once. Splitting it
        # at every User-agent would give each of them an empty rule set and turn a refusal into
        # permission.
        text = "User-agent: A\nUser-agent: B\nUser-agent: C\nDisallow: /"
        self.assertEqual(robots.robots_groups(text), [(["a", "b", "c"], ["/"])])

    def test_a_new_group_starts_after_a_rule(self):
        text = "User-agent: A\nDisallow: /x\nUser-agent: B\nDisallow: /y"
        self.assertEqual(robots.robots_groups(text), [(["a"], ["/x"]), (["b"], ["/y"])])

    def test_several_rules_in_one_group(self):
        text = "User-agent: *\nDisallow: /cgi-bin/\nDisallow: /tmp/"
        self.assertEqual(robots.robots_groups(text), [(["*"], ["/cgi-bin/", "/tmp/"])])

    def test_AN_EMPTY_DISALLOW_IS_KEPT(self):
        # It is the difference between a file that permits everything and a file whose author
        # meant the opposite. Dropping it here would take that decision away from the caller.
        self.assertEqual(robots.robots_groups("User-agent: *\nDisallow:"), [(["*"], [""])])

    def test_comments_and_blank_lines_go(self):
        text = "# a note\n\nUser-agent: *   # inline\n\nDisallow: /x  # also inline\n"
        self.assertEqual(robots.robots_groups(text), [(["*"], ["/x"])])

    def test_everything_is_lower_cased(self):
        self.assertEqual(robots.robots_groups("User-Agent: ClaudeBot\nDisallow: /Pub/"),
                         [(["claudebot"], ["/pub/"])])

    def test_unknown_directives_are_ignored(self):
        text = "User-agent: *\nCrawl-delay: 10\nSitemap: http://h/s.xml\nDisallow: /x"
        self.assertEqual(robots.robots_groups(text), [(["*"], ["/x"])])

    def test_an_empty_file_is_no_groups(self):
        for text in ("", "   \n\n#only a comment\n"):
            self.assertEqual(robots.robots_groups(text), [], repr(text))

    def test_None_is_no_groups_rather_than_an_error(self):
        self.assertEqual(robots.robots_groups(None), [])

    def test_agents_with_no_rule_at_all_are_still_a_group(self):
        # The 4corn shape: the caller has to be able to see that they were named.
        self.assertEqual(robots.robots_groups("User-agent: A\nUser-agent: B"), [(["a", "b"], [])])


class TestRobotsVerdictLibrary(unittest.TestCase):
    """What robots_verdict_test.py's seven real files do not happen to cover."""

    def test_the_three_answers_are_three(self):
        self.assertEqual(robots.robots_verdict(None, "/x")[0], "OPEN")
        self.assertEqual(robots.robots_verdict("User-agent: *\nDisallow: /", "/x")[0], "BLOCKED")
        many = "\n".join("User-agent: bot%d" % i for i in range(12)) + "\nDisallow:"
        self.assertEqual(robots.robots_verdict(many, "/x")[0], "NO-OP BLOCK")

    def test_OURS_IS_A_PARAMETER(self):
        """A caller asking on behalf of something else says so.

        ONE FILE, THREE ANSWERS, ALL CORRECT. `Disallow: /` under a named agent that is not
        us, with no `User-agent: *` anywhere, refuses that agent and nobody else -- which is
        the irixnet case in robots_verdict_test.py, and the reading this collection nearly
        got wrong. Whether it reaches the asker depends entirely on who the asker is, so who
        the asker is cannot be a constant inside the function.
        """
        text = "User-agent: SomeOtherBot" + chr(10) + "Disallow: /"
        self.assertEqual(robots.robots_verdict(text, "/x")[0], "OPEN")
        self.assertEqual(robots.robots_verdict(text, "/x", ours=("someotherbot",))[0],
                         "BLOCKED")
        self.assertEqual(robots.robots_verdict(text, "/x", ours=("nobody",))[0], "OPEN")

    def test_a_substring_match_is_deliberate(self):
        # `anthropic-ai` and `anthropic` are both listed, and a file writing `Anthropic-AI/1.0`
        # still means us.
        got, why = robots.robots_verdict("User-agent: Anthropic-AI/1.0\nDisallow: /", "/x")
        self.assertEqual(got, "BLOCKED")
        self.assertIn("anthropic", why)

    def test_BEING_NAMED_BEATS_A_BLANKET_RULE(self):
        # The reason a reader is given should be the most specific true one.
        text = "User-agent: *\nDisallow: /\n\nUser-agent: ClaudeBot\nDisallow: /pub/"
        got, why = robots.robots_verdict(text, "/pub/")
        self.assertEqual(got, "BLOCKED")
        self.assertIn("names us", why)

    def test_and_a_blanket_rule_beats_a_path_match(self):
        text = "User-agent: *\nDisallow: /\nDisallow: /pub/"
        self.assertIn("Disallow: /", robots.robots_verdict(text, "/pub/")[1])

    def test_a_trailing_star_in_a_rule_is_a_prefix(self):
        self.assertEqual(robots.robots_verdict("User-agent: *\nDisallow: /pub*", "/pub/x")[0],
                         "BLOCKED")

    def test_a_rule_that_does_not_reach_the_path(self):
        self.assertEqual(robots.robots_verdict("User-agent: *\nDisallow: /cgi-bin/", "/pub/")[0],
                         "OPEN")

    def test_the_path_comparison_ignores_case(self):
        self.assertEqual(robots.robots_verdict("User-agent: *\nDisallow: /pub/", "/PUB/x")[0],
                         "BLOCKED")

    def test_A_NO_OP_BLOCK_IS_NOT_OPEN(self):
        # A machine may not read a typo as consent. A caller that collapses this into OPEN has
        # decided something it was not asked to decide.
        many = "\n".join("User-agent: bot%d" % i for i in range(15)) + "\nDisallow:"
        verdict, why = robots.robots_verdict(many, "/anything")
        self.assertNotEqual(verdict, "OPEN")
        self.assertIn("intent", why)

    def test_a_SHORT_agent_list_with_an_empty_disallow_is_open(self):
        # Two or three agents with nothing disallowed is an ordinary, correct file. The "broken
        # block" reading needs a list long enough to be a copied blocklist.
        self.assertEqual(robots.robots_verdict("User-agent: A\nUser-agent: B\nDisallow:", "/x")[0],
                         "OPEN")

    def test_NAMING_US_WITH_AN_EMPTY_DISALLOW_IS_STILL_NOT_OPEN(self):
        # However short the list. Being named at all is the signal.
        got, _why = robots.robots_verdict("User-agent: ClaudeBot\nDisallow:", "/x")
        self.assertEqual(got, "NO-OP BLOCK")

    def test_no_robots_txt_says_which_it_is(self):
        # "OPEN" here is a statement about this file only -- a host that serves none while the
        # same organisation refused elsewhere is not open, and nothing here knows that.
        self.assertEqual(robots.robots_verdict(None, "/x"), ("OPEN", "no robots.txt"))

    def test_an_empty_robots_txt_is_open_too_but_for_another_reason(self):
        verdict, why = robots.robots_verdict("", "/x")
        self.assertEqual(verdict, "OPEN")
        self.assertNotEqual(why, "no robots.txt")


class TestOurAgentNamesNoTestTouched(unittest.TestCase):
    """One export no test mentioned, measured 2026-09-24. No caller outside robots.py."""

    def test_they_are_the_names_an_operator_would_write_to_refuse_us(self):
        self.assertIn("anthropic-ai", robots.OUR_AGENT_NAMES)
        self.assertTrue(all(n == n.lower() for n in robots.OUR_AGENT_NAMES),
                        "robots.txt agent matching is case-insensitive; keep these folded")

    def test_AND_A_RULE_NAMING_ONE_OF_THEM_IS_ABOUT_US(self):
        verdict, _why = robots.robots_verdict(
            "User-agent: anthropic-ai\nDisallow: /pub/", "/pub/x")
        self.assertEqual(verdict, "BLOCKED")

    def test_while_a_rule_for_somebody_else_is_not(self):
        verdict, _why = robots.robots_verdict(
            "User-agent: SomeOtherBot\nDisallow: /pub/", "/pub/x")
        self.assertNotEqual(verdict, "BLOCKED")

if __name__ == "__main__":
    unittest.main()
