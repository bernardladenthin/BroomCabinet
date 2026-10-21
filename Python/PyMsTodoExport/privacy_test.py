#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Nothing in this project may name the author's machine, account or data.

WHY A TEST. This tool reads a whole personal task list -- notes, names, sometimes a password
somebody once wrote into a note. The export and everything made from it live OUTSIDE the
repository by design, and this test is the ratchet that keeps it there: a sweep by hand is only as
good as the day it was run. It was written while the tool was being taken over from a private
working copy, which is exactly when an id or a path slips through.

WHAT IT REFUSES, and what each pattern is for:

  * a drive letter that is not a documented example. Examples use `D:\data` and `D:/backup`, which
    name nobody's disk. A bare drive letter without a separator ("moved off Z:") is caught too.
  * an e-mail address other than the author's own copyright line, which is a public licence header.
  * a To Do account id: the database is called `todo_` plus 16 hex digits, and member ids are the
    same 16 hex digits. Either one identifies the account.
  * an Exchange item id, as To Do stores it (`AQMk...`, `RgAAAA...`, `AAMk...`) or as Outlook's deep
    links carry it. Every task and attachment id is one, and each points into the mailbox.
  * a home directory (`/home/<name>`, `/Users/<name>`).
  * a control byte, the kind that survives a shell and looks like nothing.

WHAT IT CANNOT DO is know private list titles, task titles or names, because listing them here
would publish them. Those are checked by hand before each commit:
`git grep -i <private term> -- Python/PyMsTodoExport`.

THIS FILE IS NOT SCANNED, because a detector has to spell out what it detects.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SELF = os.path.basename(__file__)

LICENCE_MARKER = "SPDX-FileCopyrightText"
# Upper case also without a separator ("moved off Z:"); lower case only before one, because
# `e: FileEntry` is a type hint and not a drive.
DRIVE = re.compile(r"(?<![\w`'\".])(?:[A-Z]:(?=[\\/]|\s|$|[,;)])|[a-z]:(?=[\\/]))")
ALLOWED_DRIVE = re.compile(r"^D:(?:\\{1,2}|/)(?:data|backup)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ACCOUNT = [re.compile(r"todo_[0-9A-Fa-f]{16}"), re.compile(r"\b[0-9A-F]{16}\b"), re.compile(r"\b[0-9a-f]{16}\b")]
EXCHANGE_ID = re.compile(r"(?:AQMk|RgAAAA|AAMk)[A-Za-z0-9+/_%=-]{20,}")
HOME = re.compile(r"(?i)(?:/home/|/users/)[a-z]")
FORBIDDEN_BYTES = {0: "NUL", 11: "vertical tab", 12: "form feed", 26: "SUB"}


def project_files():
    for name in sorted(os.listdir(HERE)):
        path = os.path.join(HERE, name)
        if name == SELF or not os.path.isfile(path) or name.endswith((".pyc", ".tmp")):
            continue
        yield name, path


def findings(name: str, data: bytes) -> list[str]:
    out = [f"{name}: {label} byte" for byte, label in FORBIDDEN_BYTES.items() if byte in data]
    text = data.decode("utf-8", errors="replace")
    for no, line in enumerate(text.splitlines(), 1):
        where = f"{name}:{no}"
        for m in DRIVE.finditer(line):
            if not ALLOWED_DRIVE.match(line[m.start():]):
                out.append(f"{where}: drive letter {line[m.start():m.start() + 12]!r}")
        if LICENCE_MARKER not in line:
            out += [f"{where}: e-mail address" for _ in EMAIL.finditer(line)]
        out += [f"{where}: looks like a To Do account id" for pattern in ACCOUNT if pattern.search(line)]
        if EXCHANGE_ID.search(line):
            out.append(f"{where}: looks like an Exchange item id")
        if HOME.search(line):
            out.append(f"{where}: home directory")
    return out


class PrivacyTest(unittest.TestCase):
    def test_nothing_private_in_the_project(self):
        found = []
        for name, path in project_files():
            with open(path, "rb") as f:
                found += findings(name, f.read())
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_the_detector_still_detects(self):
        # A ratchet that silently stopped matching would pass forever.
        bad = ("see Z:\\somewhere and moved off Z: later, or z:/x; mail someone@example.org\n"
               "db todo_0123456789abcdef, member 0123456789ABCDEF\n"
               "task AQMkAAAAAAAAAAAAAAAAAAAAAAAAAAAA and RgAAAABBBBBBBBBBBBBBBBBBBBBBBBBBB\n"
               "from /home/someone\n").encode() + b"\x0c"
        kinds = " ".join(findings("probe", bad))
        for expected in ("drive letter", "e-mail", "account id", "Exchange item id", "home directory", "form feed"):
            self.assertIn(expected, kinds)
        self.assertEqual(findings("probe", b"python pymstodoexport.py links D:\\data\\todo\\export.json D:/backup\n"), [])


if __name__ == "__main__":
    unittest.main()
