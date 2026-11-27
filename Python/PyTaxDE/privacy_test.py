#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Nothing in this project may name a real taxpayer, the author's machine or anybody's data.

WHY A TEST. A tax return is about as personal as data gets, and this library is used on real ones.
Those stay OUTSIDE the repository by design -- each return next to its own receipts, with its own
private tests -- and this test is the ratchet that keeps them out: a sweep by hand is only as good
as the day it was run. The examples in example/ are fictitious and must stay that way.

WHAT IT REFUSES, in every file of the project (subdirectories included):

  * a drive letter that is not a documented example (`D:\data`, `D:/backup`). Also without a
    separator ("moved off Z:") -- but not "Anlage N:", which is a form, nor `-> D:`, a Decimal.
  * an e-mail address other than the author's own copyright line, which is a public licence header.
  * a home directory (`/home/<name>`, `/Users/<name>`) or a OneDrive folder.
  * a German tax number (Steuernummer, like 12/345/67890 or 123/456/78901), an 11-digit tax ID
    (Steuer-ID) and a German IBAN.
  * a control byte, the kind that survives a shell and looks like nothing.

REAL NAMES, EMPLOYERS, PLACES AND AMOUNTS cannot be listed here, because listing them would publish
them. So the returns themselves are the list: with PYTAXDE_PRIVATE set to the folder of the real
returns, every word and every number of four digits or more in their YAML files (values and comments,
not the keys) is looked for in the project, and each one found fails the test:

    PYTAXDE_PRIVATE="<folder of the returns>" python -m unittest privacy_test

Words that a return shares with the library by nature ("Werbungskosten", "nicht", the 1,900 € cap)
are accepted one by one in privacy_allowlist.txt in that private folder or its PyTaxDEConfig/ -- one term per line,
`#` for comments -- so the allowance stays private too. A further privacy_terms.txt there lists
terms that are in no return but must not appear either (a name, a street). Without the variable the
test is skipped, as in CI. Licence lines are not searched: they carry the author's name on purpose.

THIS FILE IS NOT SCANNED, because a detector has to spell out what it detects.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SELF = os.path.basename(__file__)

LICENCE_MARKER = "SPDX-FileCopyrightText"
# Upper case also without a separator ("moved off Z:"); lower case only before one, because
# `e: FileEntry` is a type hint and not a drive. "Anlage N:" is an ELSTER form, `-> D:` a return
# annotation (Decimal).
DRIVE = re.compile(r"(?<![\w`'\".])(?<!Anlage )(?<!-> )(?:[A-Z]:(?=[\\/]|\s|$|[,;)])|[a-z]:(?=[\\/]))")
ALLOWED_DRIVE = re.compile(r"^D:(?:\\{1,2}|/)(?:data|backup)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
HOME = re.compile(r"(?i)(?:/home/|/users/|\\users\\)[a-z]|onedrive")
STEUERNUMMER = re.compile(r"(?<![\d/])\d{2,3}/\d{3,4}/\d{4,5}(?![\d/])")
STEUER_ID = re.compile(r"(?<![\d.,])\d{11}(?!\d|[.,]\d)")     # not the digits of a decimal number
IBAN = re.compile(r"\bDE\d{2}(?: ?\d{4}){4} ?\d{2}\b")
FORBIDDEN_BYTES = {0: "NUL", 11: "vertical tab", 12: "form feed", 26: "SUB"}
SKIP_DIRS = {"__pycache__", ".ruff_cache", ".pytest_cache"}


def project_files():
    for root, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), HERE)
            if rel == SELF or name.endswith((".pyc", ".tmp")):
                continue
            yield rel, os.path.join(root, name)


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
        if HOME.search(line):
            out.append(f"{where}: home directory or OneDrive")
        out += [f"{where}: looks like a tax number" for _ in STEUERNUMMER.finditer(line)]
        out += [f"{where}: looks like a tax ID" for _ in STEUER_ID.finditer(line)]
        out += [f"{where}: looks like an IBAN" for _ in IBAN.finditer(line)]
    return out


PRIVATE_ENV = "PYTAXDE_PRIVATE"
ALLOWLIST, TERMS = "privacy_allowlist.txt", "privacy_terms.txt"
# a word of four letters or more, or a short all-capitals abbreviation (an employer, a bank);
# numbers with their separators, compared by their digits ("3.160", "3,160" and "3160" alike)
WORD = re.compile(r"(?<![\w])(?:[^\W\d_][\w&-]{3,}|[A-ZÄÖÜ]{2,4})(?![\w])")
NUMBER = re.compile(r"(?<![\w.,])\d[\d.,]*\d(?![\w])")
KEY = re.compile(r"([\w-]+)\s*:(?:\s|$)")
YEAR = range(1990, 2041)


def _number(token: str) -> str | None:
    digits = re.sub(r"[.,]", "", token)
    return digits if len(digits) >= 4 and not (len(digits) == 4 and int(digits) in YEAR) else None


def tokens(text: str) -> set[str]:
    """The words (lower case) and numbers (as digits) of a text; a compound also by its parts
    ("XYZ-Gerät" is "xyz-gerät", "xyz" and "gerät")."""
    words = [w.strip("-&") for w in WORD.findall(text)]
    words += [t for w in words if "-" in w for t in w.split("-") if WORD.fullmatch(t)]
    found = {w.lower() for w in words}
    found |= {n for n in map(_number, NUMBER.findall(text)) if n}
    return {t for t in found if t}


def _listed(path: str) -> set[str]:
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {ln.split("#")[0].strip().lower() for ln in f} - {""}


def private_terms(folder: str) -> set[str]:
    """Every term of the real returns below `folder`, minus the YAML keys (the format's own words)
    and minus what the private allowlist accepts, plus the private extra terms."""
    terms, keys = set(), set()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith((".yaml", ".yml")):
                with open(os.path.join(root, name), encoding="utf-8", errors="replace") as f:
                    text = f.read()
                keys |= {k.lower() for k in KEY.findall(text)}
                terms |= tokens(text)
    orte = (folder, os.path.join(folder, "PyTaxDEConfig"))
    erlaubt = set().union(*(_listed(os.path.join(o, ALLOWLIST)) for o in orte))
    extra = set().union(*(_listed(os.path.join(o, TERMS)) for o in orte))
    return (terms - keys - erlaubt) | extra


def shared(terms: set[str]) -> list[str]:
    """Where a private term occurs in the project, licence lines left out."""
    out = []
    for name, path in project_files():
        with open(path, encoding="utf-8", errors="replace") as f:
            for no, line in enumerate(f, 1):
                if LICENCE_MARKER not in line:
                    out += [f"{name}:{no}: {t}" for t in sorted(tokens(line) & terms)]
    return out


class PrivacyTest(unittest.TestCase):
    def test_no_term_of_the_real_returns(self):
        folder = os.environ.get(PRIVATE_ENV)
        if not folder:
            self.skipTest(f"{PRIVATE_ENV} not set: the real returns are not at hand")
        self.assertTrue(os.path.isdir(folder), folder)
        found = shared(private_terms(folder))
        self.assertEqual(found, [], f"\nterms of the real returns in the project (move a generic one to "
                                    f"{ALLOWLIST} in the private folder):\n" + "\n".join(found))

    def test_the_cross_check_still_detects(self):
        text = "arbeitgeber: Muster & Söhne GmbH   # 3.160 € laut Kontoauszug, Juli 2025\nkm: 42\n"
        self.assertTrue({"muster", "söhne", "gmbh", "3160", "kontoauszug"} <= tokens(text))
        self.assertFalse({"2025", "42"} & tokens(text))                   # a year, a short number
        self.assertTrue({"xyz-gerät", "xyz", "gerät"} <= tokens("wegen des XYZ-Geräts: XYZ-Gerät"))
        self.assertEqual(tokens("1,900 and 1.900 and 1900"), {"1900"})    # "and": too short a word
        self.assertEqual(KEY.findall(text), ["arbeitgeber", "km"])

    def test_nothing_private_in_the_project(self):
        found = []
        for name, path in project_files():
            with open(path, "rb") as f:
                found += findings(name, f.read())
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_the_detector_still_detects(self):
        # A ratchet that silently stopped matching would pass forever.
        bad = ("see Z:\\somewhere and moved off Z: later, or z:/x; mail someone@example.org\n"
               "from /home/someone and C:\\Users\\someone\\OneDrive\n"
               "Steuernummer 123/456/78901, Steuer-ID 12345678901, IBAN DE12 3456 7890 1234 5678 90\n"
               ).encode() + b"\x0c"
        kinds = " ".join(findings("probe", bad))
        for expected in ("drive letter", "e-mail", "home directory", "tax number", "tax ID", "IBAN", "form feed"):
            self.assertIn(expected, kinds)
        harmless = ("def cent(x: D) -> D:  Anlage N: {entfernung: 27}  localRoot=D:/backup  and  D:\\data\\x.bin\n"
                    "datum: 2026-05-21, brutto: 97930.26, 1/2 of 3/4, 12/2025\n").encode()
        self.assertEqual(findings("probe", harmless), [])


if __name__ == "__main__":
    unittest.main()
