#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Nothing in these sources may name the author's machine.

WHY THIS IS A TEST AND NOT A HABIT. On 2026-09-26 every script here was swept by hand for private
information. It found four things, and the interesting part is not that they existed but that each
had survived many readings of the file it was in:

  * `mirror.py` named a private volume AND directory -- `X:\<redacted>` -- in a comment explaining
    where a note about `icdia.co.uk` lives.
  * The same file said "which has moved off X:" in the `DO_NOT_FETCH` entry itself, eleven lines
    further down. **The first sweep missed this one**, because its pattern demanded a separator
    after the colon and this occurrence has none. A check that only sees `X:\` is not a check for
    a drive letter.
  * `refresh-table.py` quoted an absolute path into the author's source tree while describing a
    bug that had already been fixed.
  * `common_test.py` held a literal FORM FEED (0x0c) where `\funet-unix` belonged, because the
    text was written through a shell that ate the backslash. It reads `Q:\mirror` + 0x0c +
    `unet-unix` on disk, so the record it quotes was wrong and no reader could see why.

Four findings, three shapes, one of them invisible to the tool that found the other three. That is
the argument for a ratchet: a sweep is only as good as the day it was run.

WHAT IS ALLOWED AND WHY EACH IS NAMED. Since 2026-10-12 NO real path of the author's machine,
not even the collection's: the paths come from `paths.local` or the environment through
`common.setting()`. Examples use NEUTRAL paths -- `D:\mirror`, `D:\work`, `D:\packed`, `D:\verify`
-- and records of past measurements say `<root>`. Test paths like `C:\tmp` and
`R:\tree` are synthetic and prove path handling. `C:\Program Files\7-Zip` is where somebody else's
installer puts a tool. Everything else is spelled out in `ALLOWED` below, with a reason per entry,
in the same shape as `audit.ZERO_AT_SOURCE` -- because an exception without a reason is a hole
nobody can re-judge later.

PySweeper is a separate project and was swept the same day with the same patterns; it was clean,
and it has no copy of this file. If that changes, this docstring is wrong and should be fixed.
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

# The author's own copyright line is a public licence header, not a leak. It is in all 91 files
# and would drown out every real finding.
LICENCE_MARKER = "SPDX-FileCopyrightText"

# A control character has no business in source here. 0x0c is the one that was actually found;
# the others are in the same family -- a byte that survived a shell and looks like nothing.
FORBIDDEN_BYTES = {0: "NUL", 11: "vertical tab", 12: "form feed", 26: "SUB / DOS end-of-file"}

# THE NEUTRAL EXAMPLE PATHS, which are documentation rather than disclosure: no machine of ours
# has them, and every example and README section uses exactly these. MATCHED AGAINST THE REST OF THE
# LINE, not against the two characters the drive-letter pattern captures: the first version of this
# file compared its allowance with a bare drive letter alone, which can never match. A separator may
# be one backslash (a raw string) or two (an escaped one).
NEUTRAL = re.compile(r"(?i)^D:(?:\\{1,2}|/)(?:mirror|work|packed|verify)\b")

# THIS FILE IS NOT SCANNED, and the reason is not convenience. A detector has to quote what it
# detects: `PATTERNS` spells out `Privat`, `AppData` and the account name, and `ALLOWED` lists a
# drive letter per entry. Scanning it reports 18 matches that are all the check itself, which is
# the same mistake a census of `urlopen` calls in this collection made when it counted the line
# that named `urlopen` in order to look for it. The cost is that this one file is unwatched; it is
# short, it is only ever read while thinking about exactly this question, and a leak hidden inside
# the leak detector is a smaller risk than having no detector.
SELF = os.path.basename(__file__)

PATTERNS = {
    # The apostrophe in the lookbehind is not decoration: without it, "SCOPE IS THE OPERATOR'S:"
    # reads as a drive letter `S:` and the check reports a prose sentence as a leak.
    "a drive letter that is not a neutral example":
        re.compile(r"(?<![A-Za-z0-9_/\\.:%'])([A-Z]:)(?![A-Za-z0-9=:])"),
    "a path inside the author's source tree":
        re.compile(r"(Privat|BroomCabinet)"),
    "a home directory":
        re.compile(r"(?i)([A-Za-z]:[\\/]{1,2}Users[\\/]|/home/|/Users/|%USERPROFILE%|AppData)"),
    "an API that reads who is logged in":
        re.compile(r"\b(expanduser|getlogin|gethostname|getpass\.getuser)\b"),
    "the author's account name outside the licence header":
        re.compile(r"(?i)\b(berna|ladenthin)\b"),
    "something shaped like a credential":
        re.compile(r"(?i)(?:password|passwd|secret|api[_-]?key|token|bearer)\s*[=:]\s*[\"'][^\"']{4,}"),
}

# file -> {matched text -> why it is not a leak}. A reason per entry, deliberately.
ALLOWED = {
    "common.py": {
        "D:": "`common.MIRROR_ROOT = r\"D:\\elsewhere\"` -- the documented way to point the tools "
              "at a different disk in-process, which needs an example that is nobody's real path",
    },
    "common_test.py": {
        "C:": "synthetic paths for long_path() and relative_to(): C:\\tmp\\TALK., C:\\a b\\c",
        "R:": "a synthetic root, chosen as a letter nothing here uses",
        "D:": "the reassignment test for MIRROR_ROOT, and the drive-path pattern the code check uses",
    },
    "iso-second-opinion.py": {
        "C:": "where 7-Zip's installer puts 7z.exe; a candidate list, not a machine of ours",
    },
    "b2-pack-test.py": {
        "D:": "neutral work and out roots passed to plan() so the index-CSV tests read the real unit "
              "table without inventing one -- the call only builds a command line, it runs nothing "
              "and writes nothing, and the roots are given as `\"D:\" + os.sep + ...`",
    },
    "b2-pack.py": {
        "C:": "where WinRAR's installer puts Rar.exe, in the same candidate list shape as "
              "iso-second-opinion.py -- a vendor's default location, not a path of ours",
        "D:": "the example in --work's help text and in its refusal message. A tool that forbids "
              "a deep work directory has to show what a flat one looks like, and an example "
              "without a drive letter would not be one",
        "appdata": "an entry in PERSONAL_IN_PATH, which is the list of words `b2-pack.py` REFUSES "
                   "in a work directory -- because that path is written inside every archive. The "
                   "detector has to name what it detects, exactly as this file does",
    },
    "wayback-salvage.py": {
        "C:": "'C:/Program Files/Git/download/sources/' -- a path a BROKEN REGEX matched, quoted "
              "as the evidence that it matched nothing real",
    },
    "pdf_test.py": {
        "C:": "a PDF string-escape fixture: b\"C:\" + two backslashes + b\"tmp\"",
    },
    "rar-verify-content-test.py": {
        "C:": "the sentence saying every fixture here lives in the system temp directory on C:, "
              "which is the promise that no test of this file writes or deletes on the packing "
              "drive -- the owner's instruction on 2026-10-06",
    },
    "rar-verify-content.py": {
        "C:": "'C:/Program Files/WinRAR' and its (x86) sibling -- where WinRAR's installer puts "
              "Rar.exe, the same candidate-list shape b2-pack.py and iso-second-opinion.py use. "
              "A vendor's default location, not a path of ours",
    },
    "tar-subtree.py": {
        "C:": "'C:/Program Files/Git/usr/bin/tar.exe' -- GNU tar's location from the Git for "
              "Windows installer, in the same candidate shape as b2-pack.py's Rar.exe. It is "
              "named outright because a bare `tar.exe` resolves through System32 to bsdtar, "
              "which has no -d and made the comparison check unable to fail",
        "D:": "the docstring explaining that GNU tar reads `D:\\...` as host:path and resolves a "
              "host called D -- the behaviour needs a drive letter to be described at all",
    },
    "tar-subtree-test.py": {
        "C:": "SystemRoot's default, used to find bsdtar and prove the binary check rejects it",
        "D:": "posix() turns a drive letter into /d/..., which cannot be tested without one; the "
              "letters are synthetic (D:, E:) and name no machine",
        "E:": "the second synthetic letter for posix(), so a test proves the letter is carried over "
              "rather than assumed",
    },
    "README.md": {
        "C:": "the privacy section naming what this check still allows: `C:\\Program Files\\7-Zip` "
              "and the synthetic `C:\\tmp` -- the README has to say what the exceptions are",
        "R:": "the same sentence naming the synthetic `R:\\tree` test root",
    },
    "ARCHIVES-NOTES-2026-09-17.md": {
        "B:": "'196 714 496 B:' -- a byte count followed by a colon, not a drive; the pattern cannot "
              "tell a unit from a letter, and this note records a measurement",
    },
}

# The Markdown files too: a README section or a findings note publishes a path as surely as a
# comment does, and until 2026-10-12 nothing read them.
FILES = sorted(n for n in os.listdir(HERE) if n.endswith((".py", ".md")) and n != SELF)


def allowed(name, text, rest):
    """`rest` is the line from the match onward, so `Q:` can be judged by what follows it."""
    if NEUTRAL.match(rest):
        return True
    return text in ALLOWED.get(name, {})


class NoPrivatePathsInTheSources(unittest.TestCase):

    def test_there_are_files_to_check(self):
        """A sweep over nothing passes, which is the failure this guards."""
        self.assertGreater(len(FILES), 50, FILES)

    def test_no_pattern_matches_anything_unnamed(self):
        found = []
        for name in FILES:
            with io.open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if LICENCE_MARKER in line:
                        continue
                    for why, pattern in PATTERNS.items():
                        for m in pattern.finditer(line):
                            text = m.group(1) if m.groups() else m.group(0)
                            if allowed(name, text, line[m.start():]):
                                continue
                            found.append("%s:%d  %s  -- %s" % (name, lineno, text, why))
        self.assertEqual(found, [], "\n  " + "\n  ".join(found))

    def test_only_the_neutral_example_paths_are_welcome(self):
        """The allowance is narrow on purpose: four neutral names on D:, not every D: path.

        `D:\\somethingelse` would be a disclosure wearing an example's clothes, and the
        collection's real drive is no longer welcome at all.
        """
        BS = chr(92)
        for good in ("D:" + BS + "mirror" + BS + "tuhs", "D:" + BS + BS + "mirror", "D:/mirror",
                     "D:" + BS + "work", "D:/packed/misc/misc.rar", "D:" + BS + "verify"):
            self.assertTrue(NEUTRAL.match(good), good)
        for bad in ("E:" + BS + "mirror", "F:" + BS + "work", "D:" + BS + "IBM", "D:" + BS + "mirrors",
                    "D:"):
            self.assertIsNone(NEUTRAL.match(bad), bad)


class NoControlCharacters(unittest.TestCase):
    """The form-feed finding, kept as a check because prose cannot show an invisible byte."""

    def test_no_source_file_holds_one(self):
        found = []
        for name in FILES:
            with io.open(os.path.join(HERE, name), "rb") as fh:
                raw = fh.read()
            for code, label in sorted(FORBIDDEN_BYTES.items()):
                if bytes([code]) in raw:
                    at = raw.find(bytes([code]))
                    found.append("%s: %s (0x%02x) at line %d, near %r"
                                 % (name, label, code, raw[:at].count(b"\n") + 1,
                                    raw[max(0, at - 30):at + 20]))
        self.assertEqual(found, [], "\n  " + "\n  ".join(found))

    def test_the_repaired_line_reads_correctly_now(self):
        """The record is a measurement; a mangled path makes it unreadable.

        It was quoted in common_test.py, where the form feed was found; that docstring was
        rewritten on 2026-10-12, and the record itself lives on in mirror.py with `<root>` in place
        of the drive. The backslash before `funet-unix` must have survived there."""
        with io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("<root>" + chr(92) + "funet-unix" + chr(92) + " HELD 64.59 GB", text)


class ItCatchesTheFourThingsItWasWrittenFor(unittest.TestCase):
    r"""The check, put to the text that was actually in these files on 2026-09-26.

    A ratchet that passes on the repaired sources and would also have passed on the broken ones
    guards nothing. These are the four findings verbatim, with the private parts restored, and each
    must be caught by name. The second one is the one that matters most: it has no separator after
    the colon, and the sweep that found the other three could not see it.
    """

    BS = chr(92)

    def caught(self, line, name="mirror.py"):
        out = []
        for why, pattern in PATTERNS.items():
            for m in pattern.finditer(line):
                text = m.group(1) if m.groups() else m.group(0)
                if not allowed(name, text, line[m.start():]):
                    out.append(why)
        return out

    def test_1_a_private_volume_and_directory(self):
        line = "# in SEARCH-BRIEF.md in the curated collection -- WHICH IS NO LONGER AT X:" \
               + self.BS + "IBM; that directory"
        self.assertIn("a drive letter that is not a neutral example", self.caught(line))

    def test_2_a_bare_drive_letter_with_no_separator(self):
        """THE ONE THE FIRST SWEEP MISSED. `X:` ends the fragment; nothing path-like follows."""
        line = '                              "curated collection -- which has moved off X: and is not "'
        self.assertIn("a drive letter that is not a neutral example", self.caught(line))

    def test_3_an_absolute_path_into_the_source_tree(self):
        line = "`X:" + self.BS + "Privat" + self.BS + "OpenSource" + self.BS \
               + "...` twice and `Q:" + self.BS + "mirror` twice more"
        why = self.caught(line, "refresh-table.py")
        self.assertIn("a path inside the author's source tree", why)
        self.assertIn("a drive letter that is not a neutral example", why)

    def test_4_the_form_feed(self):
        """Not a pattern match -- a byte. It is invisible, which is why prose could not hold it."""
        broken = ("    past measurement found -- `Q:" + self.BS + "mirror"
                  + chr(12) + "unet-unix").encode()
        self.assertTrue(any(bytes([c]) in broken for c in FORBIDDEN_BYTES))

    def test_and_the_repaired_wording_is_not_caught(self):
        """The other half: the fix must actually pass, or the ratchet just forbids the sentence."""
        for line in (
            "# in SEARCH-BRIEF.md in the curated IBM collection, which moved to another volume",
            '                              "curated IBM collection -- which is not on this volume "',
            "used to hold an absolute path into the author's own source tree twice and the "
            "collection's path twice more",
        ):
            self.assertEqual(self.caught(line), [], line)


class EveryExceptionIsJustified(unittest.TestCase):
    """The table is only worth having if nobody can add to it silently."""

    def test_every_allowance_names_a_file_that_exists(self):
        for name in ALLOWED:
            self.assertIn(name, FILES, name)

    def test_every_allowance_carries_a_reason(self):
        for name, entries in ALLOWED.items():
            for text, why in entries.items():
                self.assertGreater(len(why), 30, "%s / %s: a reason, not a label" % (name, text))

    def test_no_allowance_is_dead(self):
        """An exception for something that is no longer there hides the next real match."""
        dead = []
        for name, entries in ALLOWED.items():
            with io.open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            for wanted in entries:
                if wanted not in text:
                    dead.append("%s no longer contains %r" % (name, wanted))
        self.assertEqual(dead, [], "\n  " + "\n  ".join(dead))


if __name__ == "__main__":
    unittest.main(verbosity=2)
