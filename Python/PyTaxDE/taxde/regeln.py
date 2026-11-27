# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Tax rules per year, loaded from a shared YAML file (default: steuerjahre.yaml next to this module).

EVERY YEAR IS A COMPLETE, SELF-CONTAINED BLOCK. Nothing is inherited from the year before, because
the things that "never change" do change (the VAT rate did in 2020). A test checks that every year
carries the same keys. Another file can be used through the environment variable PYTAXDE_STEUERJAHRE
or `regeln(jahr, datei=...)`.

Numbers come back as Decimal, lists of [up to, rate] as tuples. PyYAML is imported only when a file is
actually read, so `--help` works without it installed.
"""
import os
from decimal import Decimal as D
from functools import lru_cache
from pathlib import Path

STANDARD = Path(__file__).with_name("steuerjahre.yaml")
UMGEBUNG = "PYTAXDE_STEUERJAHRE"


def _dec(x):
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, (int, float)):
        return D(str(x))
    if isinstance(x, list):
        return [_dec(v) for v in x]
    if isinstance(x, dict):
        return {k: _dec(v) for k, v in x.items()}
    return x


class Regeln:
    """The rules of one year; every key of the year's block is an attribute."""

    def __init__(self, jahr: int, werte: dict):
        self.jahr = jahr
        self._w = werte

    def __getattr__(self, name):
        try:
            return self._w[name]
        except KeyError:
            raise AttributeError(f"steuerjahre {self.jahr}: Wert '{name}' fehlt") from None

    def get(self, name, standard=None):
        return self._w.get(name, standard)

    @property
    def entfernung(self):
        return tuple((None if b is None else int(b), s) for b, s in self._w["entfernung"])

    @property
    def zumutbar_ledig(self):
        return tuple((b, s) for b, s in self._w["zumutbar_ledig"])

    @property
    def gwg_grenze_brutto(self):
        return self._w["gwg_grenze_netto"] * (1 + self._w["umsatzsteuer"]["regel"])

    @property
    def zeilen(self):
        return {(f, k): z for f, felder in (self._w.get("zeilen") or {}).items() for k, z in felder.items()}


@lru_cache(maxsize=None)
def alle_jahre(datei: str = str(STANDARD)) -> dict:
    """Every year block of the file, raw (each year self-contained, no inheritance)."""
    import yaml

    with open(datei, encoding="utf-8") as f:
        roh = yaml.safe_load(f)
    return {int(k): v for k, v in roh.items()}


def regeln(jahr: int, datei=None) -> Regeln:
    datei = str(datei or os.environ.get(UMGEBUNG) or STANDARD)
    alle = alle_jahre(datei)
    if int(jahr) not in alle:
        raise KeyError(f"Keine Regeln für {jahr}; bitte in der steuerjahre-Datei einen vollständigen Block ergänzen")
    return Regeln(int(jahr), _dec(alle[int(jahr)]))
