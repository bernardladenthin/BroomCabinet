#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Nothing in this project may name the author's machine, data or keys.

WHY A TEST. This tool is run against private collections, whose paths and file names are nobody
else's business. All of that lives OUTSIDE the repository by design, and this test is
the ratchet that keeps it there: a sweep by hand is only as good as the day it was run.

WHAT IT REFUSES, and what each pattern is for:

  * a drive letter that is not a documented example. Examples use `D:\data` and `D:/backup`, which
    name nobody's disk. A bare drive letter without a separator ("moved off Z:") is caught too --
    PyMirror's identical test once missed exactly that shape.
  * an e-mail address other than the author's own copyright line, which is a public licence header.
  * anything shaped like a B2 key: a 25-hex-digit application key id, a `K0..` application key, or
    a 42-hex-digit master key.
  * a home directory (`/home/<name>`, `/Users/<name>`).
  * a control byte, the kind that survives a shell and looks like nothing.

WHAT IT CANNOT DO is know private file or folder names, because listing them here would publish them.
Those are checked by hand before each commit: `git grep -i <private term> -- Python/PyFixity`.

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
KEYS = [re.compile(r"\b[0-9a-f]{25}\b"), re.compile(r"\bK0\d\d[A-Za-z0-9+/]{20,}"),
        re.compile(r"\b00[0-9a-f]{40}\b")]
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
        out += [f"{where}: looks like a B2 key" for pattern in KEYS if pattern.search(line)]
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
               "keyId=0123456789abcdef012345678\nfrom /home/someone\n").encode() + b"\x0c"
        kinds = " ".join(findings("probe", bad))
        for expected in ("drive letter", "e-mail", "B2 key", "home directory", "form feed"):
            self.assertIn(expected, kinds)
        self.assertEqual(findings("probe", b"localRoot=D:/backup  and  D:\\data\\x.bin\n"), [])


if __name__ == "__main__":
    unittest.main()
