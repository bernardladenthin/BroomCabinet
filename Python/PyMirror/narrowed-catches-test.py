#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Do the narrowed catches still catch what they must, and no longer catch what they must not?

WHAT D9 CHANGED AND WHY IT NEEDED ITS OWN TESTS. Nine handlers across nine tools said
`except Exception:` and then carried on -- returning `{}`, `None`, `""`, or `continue`. Every one
of them was replaced with the exceptions the code below it actually raises. That is two promises,
and the discipline test in common_test.py only checks the second:

  * THE FAILURE IT WAS FOR IS STILL HANDLED. A dead host, an absent mirror.py, an unparseable
    date: these are facts about the world and the tool must keep going.
  * A DEFECT IN THE FILE IS NOT. A NameError, an AttributeError, a typo'd keyword -- those now
    take the run down, which is right, because a check that cannot run has not found nothing.

Narrowing without the first half would be worse than the bug: it would turn every transient
network failure into a crash. So both are asserted, per site.

THE BUG THIS ALL CAME FROM. `recheck-decisions.py` called `http_open`, which was never imported.
`NameError` is an `Exception`, so every probe fell through and the tool reported EVERY HOST IN
THE COLLECTION as dead -- including two this project fetched files from the same day. Found by
ruff on 2026-09-24, which until then ran only in CI.

Nothing here touches the network or the mirror: every failure is injected.
"""
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class Swapped(object):
    """Replace one attribute of a module for the duration of a block, and put it back."""

    def __init__(self, module, name, value):
        self.module, self.name, self.value = module, name, value

    def __enter__(self):
        self.old = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)
        return self

    def __exit__(self, *_exc):
        setattr(self.module, self.name, self.old)
        return False


def raiser(exc):
    def fn(*_a, **_kw):
        raise exc
    return fn


class TestProbeStillAnswersAndNoLongerHides(unittest.TestCase):
    """`recheck-decisions.probe()` -- the one that was wrong about every host in the collection."""

    def setUp(self):
        self.rd = common.load_peer("recheck-decisions.py", "_rd_narrowed")

    def test_A_HOST_THAT_DOES_NOT_RESOLVE_IS_STILL_no_DNS(self):
        # gaierror is what gethostbyname really raises, and it is an OSError. Measured.
        with Swapped(self.rd.socket, "gethostbyname", raiser(socket.gaierror(11001, "no such"))):
            self.assertEqual(self.rd.probe("nowhere.invalid", timeout=1),
                             ("no DNS", False))

    def test_and_a_name_too_long_to_encode_as_well(self):
        # UnicodeError, which is NOT an OSError -- it is named separately for that reason.
        with Swapped(self.rd.socket, "gethostbyname", raiser(UnicodeError("too long"))):
            self.assertEqual(self.rd.probe("x" * 300, timeout=1), ("no DNS", False))

    def test_A_TYPO_IN_THIS_FILE_NOW_TAKES_THE_RUN_DOWN(self):
        """The whole point. It used to answer "DNS resolves, nothing answers" instead -- for
        every host, for weeks, with no error anywhere."""
        with Swapped(self.rd, "socket", _NoSocket()):
            with self.assertRaises(NameError):
                self.rd.probe("example.invalid", timeout=1)

    def test_and_so_does_one_in_the_request(self):
        with Swapped(self.rd.socket, "gethostbyname", lambda *_a: "127.0.0.1"):
            with Swapped(self.rd, "http_open", raiser(NameError("http_opne"))):
                with self.assertRaises(NameError):
                    self.rd.probe("example.invalid", timeout=1)

    def test_but_a_refused_connection_is_still_just_a_dead_host(self):
        with Swapped(self.rd.socket, "gethostbyname", lambda *_a: "127.0.0.1"):
            with Swapped(self.rd, "http_open", raiser(OSError(61, "refused"))):
                self.assertEqual(self.rd.probe("example.invalid", timeout=1),
                                 ("DNS resolves, nothing answers", False))


class _NoSocket(object):
    """A stand-in whose every attribute access is a NameError, standing for a typo'd import."""

    def __getattr__(self, name):
        raise NameError("name 'socket.%s' is not defined" % name)


class TestTheRegisterReadersFailLoudly(unittest.TestCase):
    """Three tools read mirror.py's ARCHIVES and fall back to an empty register.

    "mirror.py is not beside this script" is a fact and a legitimate fallback. "ARCHIVES has been
    renamed" is a defect, and the same broad catch swallowed both -- so the day the register moved
    every one of these tools would have reported a clean pass over nothing.
    """

    TOOLS = (("crawl-gap-audit.py", "base_urls", ()),
             ("pages-to-urllist.py", "base_urls", (HERE,)))

    def test_AN_ABSENT_MIRROR_PY_IS_STILL_AN_EMPTY_REGISTER(self):
        for name, fn, args in self.TOOLS:
            mod = common.load_peer(name, "_narrowed_" + fn + name.replace("-", "_"))
            with Swapped(mod, "load_mirror", raiser(FileNotFoundError(2, "no mirror.py"))):
                self.assertEqual(getattr(mod, fn)(*args), {}, name)

    def test_AND_A_RENAMED_REGISTER_IS_NOT(self):
        for name, fn, args in self.TOOLS:
            mod = common.load_peer(name, "_narrowed2_" + fn + name.replace("-", "_"))
            with Swapped(mod, "load_mirror", raiser(AttributeError("ARCHIVES"))):
                with self.assertRaises(AttributeError, msg=name):
                    getattr(mod, fn)(*args)

    def test_and_a_broken_mirror_py_is_a_fact_not_a_defect(self):
        # ImportError means the file is there and will not load -- still "no register", still a
        # thing about the world rather than about this file.
        mod = common.load_peer("crawl-gap-audit.py", "_narrowed3")
        with Swapped(mod, "load_mirror", raiser(ImportError("cannot import"))):
            self.assertEqual(mod.base_urls(), {})


class TestTheDateParserStillReturnsNone(unittest.TestCase):
    """`common.http_date()` answers None for junk, and None is a legitimate answer -- which is
    exactly why a broad catch there was dangerous: a typo would have answered None for every
    header in the collection and looked completely normal."""

    JUNK = ("", "nonsense", "Mon, 99 Xyz 9999", "2026-13-45", None)

    def test_every_kind_of_junk_still_gives_none(self):
        # Named directly. The first version said `getattr(common, "http_date", None) or
        # getattr(common, "parse_http_date", None)`, a fallback to a name that does not exist --
        # a branch that can never be taken, which is the same shape as a guard that never fires.
        for bad in self.JUNK:
            self.assertIsNone(common.http_date(bad), repr(bad))

    def test_and_a_real_date_is_still_read(self):
        # The direction that matters: narrowing the catch must not have broken the success path.
        self.assertEqual(common.http_date("Fri, 20 Feb 1998 21:28:58 GMT"), 888010138.0)


if __name__ == "__main__":
    unittest.main()
