# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The comparable result of a return, and the comparison with a stored one: the self-test's core.

Where the stored results live -- one Steuererklärungen.json per folder, a block per return -- is
taxde/gesamt.py; this module says what a result holds and how two of them differ.

WHAT IS IN IT: the ELSTER entries keyed by form and field, the key figures, the simulation's steps
and figures, the comparison with a notice (`bescheid:`), what is missing, open and hinted at. WHAT
IS NOT: the levers -- they are prose and would turn every rewording into a difference -- and the time
of writing, so an unchanged result is an unchanged file (and no new version for a sync tool).
Numbers are JSON numbers and are read back as Decimal; 690 and 690.00 are the same.
"""
import json
from decimal import Decimal as D

def _eindeutig(paare):
    """Pairs (key, value) as a dict; a key that comes twice gets ' (2)', ' (3)', ..."""
    out = {}
    for k, v in paare:
        schluessel, n = k, 1
        while schluessel in out:
            n += 1
            schluessel = f"{k} ({n})"
        out[schluessel] = v
    return out


def als_dict(e, quelle: str = "") -> dict:
    """The comparable content of an Ergebnis (see the module docstring)."""
    elster = {}
    for x in e.eintraege:
        elster.setdefault(x.formular, []).append((x.feld, {"zeile": x.zeile, "wert": x.wert, "einheit": x.einheit}))
    s = e.simulation
    sim = {
        "fehlt": list(s.fehlt),
        "schritte": _eindeutig(s.schritte),
        "werte": dict(s.werte),
        "abgleich": {name: {"bescheid": fa, "simuliert": sim} for name, fa, sim in s.abgleich},
    }
    return {
        "format": 1,
        "erzeugt_von": "PyTaxDE",
        "quelle": quelle,
        "jahr": e.jahr,
        "elster": {f: _eindeutig(felder) for f, felder in elster.items()},
        "werte": dict(e.werte),
        "simulation": sim,
        "offen": list(e.offen),
        "hinweise": list(e.hinweise),
    }


def _zahl(o):
    if isinstance(o, D):
        return int(o) if o == o.to_integral_value() else float(o)   # repr of a float round-trips these
    raise TypeError(f"nicht als JSON darstellbar: {o!r}")


def als_json(daten: dict) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2, default=_zahl) + "\n"


def lesen(text: str) -> dict:
    return json.loads(text, parse_float=D, parse_int=D)


def _flach(x, pfad=()):
    """Leaves as {path: value}. Lists of texts become sets: their order is no difference."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            out.update(_flach(v, pfad + (str(k),)))
        return out
    if isinstance(x, list):
        out = {}
        for i, v in enumerate(x):
            out.update(_flach(v, pfad + ((v,) if isinstance(v, str) else (f"[{i}]",))))
        return out
    return {pfad: x}


def unterschiede(alt: dict, neu: dict) -> list:
    """(kind, path, old, new) for every difference; kind is 'geändert', 'neu' or 'entfällt'."""
    a, n = _flach(alt), _flach(neu)
    out = []
    for p in a.keys() | n.keys():
        if p[:1] == ("quelle",):
            continue                     # a renamed file is the same return
        if p not in n:
            out.append(("entfällt", p, a[p], None))
        elif p not in a:
            out.append(("neu", p, None, n[p]))
        elif a[p] != n[p]:
            out.append(("geändert", p, a[p], n[p]))
    reihenfolge = {p: i for i, p in enumerate(list(a) + [p for p in n if p not in a])}
    return sorted(out, key=lambda u: reihenfolge[u[1]])


def text(unterschied) -> str:
    art, pfad, alt, neu = unterschied
    ort = " › ".join(pfad)
    if art == "geändert":
        return f"geändert  {ort}: {alt} → {neu}"
    if art == "neu":
        return f"neu       {ort}" + ("" if neu is True or isinstance(pfad[-1], str) and neu == pfad[-1] else f": {neu}")
    return f"entfällt  {ort}" + ("" if isinstance(pfad[-1], str) and alt == pfad[-1] else f": {alt}")
