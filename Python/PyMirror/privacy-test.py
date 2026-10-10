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

WHAT IS ALLOWED AND WHY EACH IS NAMED. `Q:\mirror` is the collection, documented in
`common.MIRROR_ROOT` and printed in `--help` output on purpose. Test paths like `C:\tmp` and
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

# The collection's own drive, which is documentation rather than disclosure. MATCHED AGAINST THE
# REST OF THE LINE, not against the two characters the drive-letter pattern captures: the first
# version of this file compared `COLLECTION` with `"Q:"` alone, which can never match, so every
# documented `--root Q:\mirror` example counted as a leak. A separator may be one backslash (a raw
# string) or two (an escaped one).
COLLECTION = re.compile(r"(?i)^Q:(?:\\{1,2}|/)mirror")

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
    "a drive letter other than the collection's":
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
    "move-mirror.py": {
        "X:": "two bare drive letters with no path, in the branch that explains WinError 17 -- "
              "this tool exists to move between volumes, so naming them is the explanation",
        "Q:": "the other half of the same sentence",
    },
    "common.py": {
        "D:": "`common.MIRROR_ROOT = r\"D:\\elsewhere\"` -- the documented way to point the tools "
              "at a different disk, which needs an example that is not the real one",
        "Q:": "MIRROR_ROOT itself, and the comment recording the 27 files it replaced",
    },
    "common_test.py": {
        "C:": "synthetic paths for long_path() and relative_to(): C:\\tmp\\TALK., C:\\a b\\c",
        "R:": "a synthetic root, chosen as a letter nothing here uses",
        "Q:": "the needle this file's own class checks for, plus Q:\\a as a synthetic root",
        "D:": "the reassignment test for MIRROR_ROOT",
    },
    "iso-second-opinion.py": {
        "C:": "where 7-Zip's installer puts 7z.exe; a candidate list, not a machine of ours",
    },
    "b2-pack-test.py": {
        "X:": "the work and out roots passed to plan() so the index-CSV tests read the real unit "
              "table without inventing one -- the call only builds a command line, it runs "
              "nothing and writes nothing",
        "Q:": "the docstring naming Q: as read-only to this tool, which is why the index CSV "
              "cannot be passed by a path relative to the collection",
    },
    "b2-pack.py": {
        "X:": "the comment explaining that the index CSV is passed by absolute path and RAR then "
              "stores every component below the drive letter, so X:/tar/<unit>.index.csv becomes "
              "tar/<unit>.index.csv inside the archive -- the example needs the drive to make "
              "sense, and it is the same behaviour WORK_MUST_BE_FLAT exists for",
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
    "pack-progress.py": {
        "X:": "the default --work, 'X:/tar': the flat working directory b2-pack.py writes its "
              ".list and .index.csv into, and the only place this tool reads",
    },
    "pack-progress-test.py": {
        "X:": "the sentence saying a test must never find the real X:/tar, or it would report on "
              "the live run instead of on its own fixture",
    },
    "rar-verify-content.py": {
        "C:": "'C:/Program Files/WinRAR' and its (x86) sibling -- where WinRAR's installer puts "
              "Rar.exe, the same candidate-list shape b2-pack.py and iso-second-opinion.py use. "
              "A vendor's default location, not a path of ours",
        "X:": "the default --scratch, 'X:/verify': this check unpacks a whole unit somewhere, and "
              "a default that is not the collection's drive is the point of naming one",
        "Q:": "the docstring line saying Q: is read for the .sha256sum files and nothing else -- "
              "the one promise this tool makes about the collection",
    },
    "tar-subtree.py": {
        "C:": "'C:/Program Files/Git/usr/bin/tar.exe' -- GNU tar's location from the Git for "
              "Windows installer, in the same candidate shape as b2-pack.py's Rar.exe. It is "
              "named outright because a bare `tar.exe` resolves through System32 to bsdtar, "
              "which has no -d and made the comparison check unable to fail",
        "X:": "the tar target drive in TARGET_ROOT -- the packing scratch space, named beside "
              "the collection root it reads from, which comes from common.MIRROR_ROOT",
    },
    "tar-subtree-test.py": {
        "C:": "SystemRoot's default, used to find bsdtar and prove the binary check rejects it",
        "X:": "posix() turns a drive letter into /x/..., which cannot be tested without one; "
              "also the docstring saying which two drives a test must never be pointed at",
        "Q:": "the same two: posix() on the collection's letter, and the warning in the "
              "docstring that no fixture here may name the collection",
    },
    "ask-the-source.py": {
        "Q:": "a --help example naming the collection",
    },
    "audit-test.py": {
        "Q:": "a skip message: this stays a unit test on a machine without the collection",
    },
}

FILES = sorted(n for n in os.listdir(HERE) if n.endswith(".py") and n != SELF)


def allowed(name, text, rest):
    """`rest` is the line from the match onward, so `Q:` can be judged by what follows it."""
    if COLLECTION.match(rest):
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

    def test_the_collection_path_is_the_only_bare_drive_it_welcomes(self):
        """The allowance is narrow on purpose: `Q:\\mirror`, not every Q: path.

        `Q:\\somethingelse` would be a second disclosure wearing the first one's clothes.
        """
        BS = chr(92)
        self.assertTrue(COLLECTION.match("Q:" + BS + "mirror" + BS + "tuhs"))
        self.assertTrue(COLLECTION.match("Q:" + BS + BS + "mirror"))    # an escaped separator
        self.assertTrue(COLLECTION.match("Q:/mirror"))
        self.assertIsNone(COLLECTION.match("Q:" + BS + "IBM"))
        self.assertIsNone(COLLECTION.match("X:" + BS + "mirror"))
        self.assertIsNone(COLLECTION.match("Q:"))                       # the first version's bug


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
        """The record this file quotes is a measurement; a mangled path makes it unreadable."""
        with io.open(os.path.join(HERE, "common_test.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Q:" + chr(92) + "mirror" + chr(92) + "funet-unix", text)


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
        self.assertIn("a drive letter other than the collection's", self.caught(line))

    def test_2_a_bare_drive_letter_with_no_separator(self):
        """THE ONE THE FIRST SWEEP MISSED. `X:` ends the fragment; nothing path-like follows."""
        line = '                              "curated collection -- which has moved off X: and is not "'
        self.assertIn("a drive letter other than the collection's", self.caught(line))

    def test_3_an_absolute_path_into_the_source_tree(self):
        line = "`X:" + self.BS + "Privat" + self.BS + "OpenSource" + self.BS \
               + "...` twice and `Q:" + self.BS + "mirror` twice more"
        why = self.caught(line, "refresh-table.py")
        self.assertIn("a path inside the author's source tree", why)
        self.assertIn("a drive letter other than the collection's", why)

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
            "used to hold an absolute path into the author's own source tree twice and `Q:"
            + self.BS + "mirror` twice more",
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
