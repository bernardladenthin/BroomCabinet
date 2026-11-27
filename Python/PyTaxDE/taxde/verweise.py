# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The paths a Markdown note names, and whether they exist -- for the note that goes with a return.

    PyTaxDEConfig/
      Steuererklärung 2025.yaml     belege_ordner: "../2025 Steuererklärung"
      Steuererklärung 2025.md       [the return](<Steuererklärung 2025.yaml>), `2026-05-21 Bescheid\`

Two kinds of reference, each against the folder a reader would take it from:
  * a LINK -- [text](target), [text](<target with spaces>), ![image](target), [ref]: target -- is
    relative to the Markdown file, as in any viewer or editor that follows it;
  * a PATH in a code span -- `2026-05-21 Bescheid\`, `..\2025\Lohnsteuerbescheinigung.pdf` -- is
    relative to the receipts' folder of the YAML file of the same name (its `belege_ordner:`), so the
    note describes the year's folder in the same terms as the return does. Without such a YAML: the
    Markdown file's folder.
A code span counts as a path when it holds a slash or a backslash, or ends in a file extension; one
that reads like a command (`python -B ...`, `$x = ...`) does not. "…" in a name abbreviates it and
matches like `*`, the spaces around it included. Web addresses, anchors and fenced code blocks are not checked.

Standard library only: a link and a code span are simple enough to find line by line, and a
Markdown package would add a dependency to tell us no more.
"""
import os
import re
from pathlib import Path

ZAUN = re.compile(r"^\s*(```|~~~)")
LINK = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>\n]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFERENZ = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>\n]*>|\S+)")
CODE = re.compile(r"(`+)(.+?)\1")
SCHEMA = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]+:")          # http:, mailto: -- two letters at least, so no drive
ENDUNG = re.compile(r"\.[A-Za-z0-9]{1,5}$")
BEFEHL = re.compile(r"^(?:python|py|pip|cd|git|\.\\|\./|-)|[$=|;{}]|\s-{1,2}\w")


def _ziel(roh: str) -> str:
    z = roh[1:-1] if roh.startswith("<") and roh.endswith(">") else roh
    return z.split("#", 1)[0].replace("%20", " ")


def _ist_pfad(code: str) -> bool:
    c = code.strip()
    return bool(c) and not BEFEHL.search(c) and not SCHEMA.match(c) and \
        ("/" in c or "\\" in c or bool(ENDUNG.search(c.rstrip("\\/"))))


def verweise(text: str) -> list:
    """(line, kind, target) for every link ("link") and every path in a code span ("pfad")."""
    out, zaun = [], None
    for nr, zeile in enumerate(text.splitlines(), 1):
        m = ZAUN.match(zeile)
        if m:
            zaun = None if zaun == m.group(1) else (zaun or m.group(1))
            continue
        if zaun:
            continue
        r = REFERENZ.match(zeile)
        if r:
            out.append((nr, "link", _ziel(r.group(1))))
            continue
        for m in LINK.finditer(zeile):
            out.append((nr, "link", _ziel(m.group(1))))
        ohne_links = LINK.sub(" ", zeile)                      # a code span inside a link's text is no path
        out += [(nr, "pfad", c.group(2).strip()) for c in CODE.finditer(ohne_links) if _ist_pfad(c.group(2))]
    return [(nr, art, z) for nr, art, z in out if z and not SCHEMA.match(z)]     # "X:\..." is no scheme


def _gibt_es(ziel: str, basis: Path) -> bool:
    z = re.sub(r"\s*…\s*", "*", ziel.replace("\\", "/"))      # "2026-02-06 … ELSTER ….png": spaces included
    p = Path(z)
    if p.is_absolute() or re.match(r"^[A-Za-z]:/", z):
        if "*" in z or "?" in z:
            return any(Path(p.anchor).glob(str(p.relative_to(p.anchor))))
        return p.exists()
    if "*" in z or "?" in z:
        return any(basis.glob(z.rstrip("/")))
    return Path(os.path.normpath(basis / z)).exists()


def pfad_basis(md: Path) -> Path:
    """Where a code-span path of this note is taken from: the receipts' folder of its YAML, else its folder."""
    from .rechner import belege_basis
    for endung in (".yaml", ".yml"):
        y = md.with_suffix(endung)
        if y.exists():
            return belege_basis(y)
    return md.parent


def verweise_pruefen(md) -> list:
    """(line, kind, target) for every reference of the note that does not exist."""
    md = Path(md)
    pfad = pfad_basis(md)
    out = []
    for nr, art, ziel in verweise(md.read_text(encoding="utf-8")):
        if not _gibt_es(ziel, md.parent if art == "link" else pfad):
            out.append((nr, art, ziel))
    return out
