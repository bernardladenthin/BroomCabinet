# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""One item (Posten) of the YAML file and its amount.

An item is a dict with `bezeichnung` and exactly one way to state its amount:

    betrag: 250                          a fixed amount
    monatlich: 24.90, monate: 12         the same amount every month
    betraege: [17.99, 17.99, 22.99]      single amounts (one per month, for example)
    anzahl: 12, je: 5                    count × unit price
    art: bewerbung_online, anzahl: 12    flat rate per online job application (from the rules)
    art: dienstreise, km: 120            km × business-trip rate (from the rules)
    art: entfernung, tage, km[, wege]    days × distance by the commuting-allowance tiers
    art: telekom, monatlich|betraege     20 % per month, at most 20 € per month (from the rules)

Optional: `anteil: 0.5` (work share), `offen: true` (not settled yet: does not count, is reported),
`nicht_anerkannt: "reason"` (filed, but the tax office did not recognise it: does not count, is reported),
`kategorie: homeoffice` (the cluster of the overview it belongs to, where its section is not enough),
`notiz`, `belege` (paths). Other keys (an order number, say) are allowed and ignored.
Expenses are rounded UP to whole euros per item, as a return filed by hand would be.
"""
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR
from decimal import Decimal as D


def dec(x) -> D:
    return x if isinstance(x, D) else D(str(x))


def euro_auf(x: D) -> D:
    return dec(x).quantize(D("1"), rounding=ROUND_CEILING)


def euro_ab(x: D) -> D:
    return dec(x).quantize(D("1"), rounding=ROUND_FLOOR)


def cent(x: D) -> D:
    return dec(x).quantize(D("0.01"))


@dataclass
class Betrag:
    bezeichnung: str
    exakt: D            # computed exactly
    eintrag: D          # rounded, as entered in ELSTER
    rechnung: str       # the calculation, readable
    offen: bool = False
    notiz: str = ""
    nicht_anerkannt: bool = False
    kategorie: str = ""                               # optional cluster of the overview (`kategorie:` of the item)
    belege: list = field(default_factory=list)        # the item's `belege:` as given


def _monatswerte(p):
    if "betraege" in p:
        return [dec(b) for b in p["betraege"]]
    if "monatlich" in p:
        return [dec(p["monatlich"])] * int(p.get("monate", 12))
    raise ValueError(f"{p.get('bezeichnung')}: 'monatlich' oder 'betraege' fehlt")


def entfernungspauschale(tage: int, km: int, regeln) -> D:
    """Days × distance by the tiers of the rules (2025: 0.30 € up to km 20, 0.38 € from km 21)."""
    summe, unten = D("0"), 0
    for bis, satz in regeln.entfernung:
        oben = km if bis is None else min(km, bis)
        if oben > unten:
            summe += tage * (oben - unten) * satz
        unten = oben if bis is None else bis
        if km <= unten:
            break
    return summe


STUDIE_KATEGORIEN = {"studie_fahrt": "fahrten", "studie_parken": "parken", "studie_klein": "kleinausgaben"}


def studie_posten(s: dict, name: str) -> list:
    """The expenses of a paid study (or similar) from its visits, as items for berechne():

        studie:
          termine: 12                 # the number of visits, or a list of their dates
          ort: Klinik                 # optional, for the labels
          km: 35                      # one-way distance; trips by the commuting-allowance tiers
          wege: 2                     # there and back (default)
          parken: [4.50, 6.00]        # parking tickets, single amounts -- or parken_je_termin: 5
          parken_belege: [...]        # optional receipts of the tickets
          kleinausgaben_je_termin: 5  # telephone and the like, a flat amount per visit

    Each comes out as its own item, rounded up like any other, with a `kategorie` for the overview."""
    t = s.get("termine")
    n = len(t) if isinstance(t, list) else int(t or 0)
    if n <= 0:
        raise ValueError(f"{name}: studie.termine fehlt (Zahl der Termine oder Liste der Daten)")
    unbekannt = set(s) - {"termine", "ort", "km", "wege", "parken", "parken_je_termin", "parken_belege",
                          "kleinausgaben_je_termin"}
    if unbekannt:
        raise ValueError(f"{name}: studie: unbekannte Angabe {', '.join(sorted(unbekannt))}")
    if "parken" in s and "parken_je_termin" in s:
        raise ValueError(f"{name}: studie: parken oder parken_je_termin, nicht beides")
    ort = f" zur {s['ort']}" if s.get("ort") else ""
    out = []
    if "km" in s:
        wege = int(s.get("wege", 2))
        out.append({"bezeichnung": f"Fahrten{ort} ({n} Termine, {s['km']} km, "
                                   + ("hin und zurück" if wege == 2 else f"{wege} Wege") + ")",
                    "art": "entfernung", "tage": n, "km": s["km"], "wege": wege, "kategorie": "studie_fahrt"})
    if "parken" in s:
        out.append({"bezeichnung": f"Parktickets ({len(s['parken'])} Stück)", "betraege": s["parken"],
                    "kategorie": "studie_parken", "belege": s.get("parken_belege") or []})
    elif "parken_je_termin" in s:
        out.append({"bezeichnung": "Parken je Termin", "anzahl": n, "je": s["parken_je_termin"],
                    "kategorie": "studie_parken", "belege": s.get("parken_belege") or []})
    if "kleinausgaben_je_termin" in s:
        out.append({"bezeichnung": "Kleinausgaben je Termin", "anzahl": n, "je": s["kleinausgaben_je_termin"],
                    "kategorie": "studie_klein"})
    return out


def fmt(x: D) -> str:
    """German number format: 1.234,56"""
    return f"{cent(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def berechne(p: dict, regeln, rundung=euro_auf) -> Betrag:
    name = p.get("bezeichnung", "?")
    if p.get("offen"):
        return Betrag(name, D("0"), D("0"), "offen", True, p.get("notiz", ""))
    art = p.get("art")
    if art == "telekom":
        werte = _monatswerte(p)
        exakt = sum((min(w * regeln.telekom_anteil, regeln.telekom_deckel_monat) for w in werte), D("0"))
        prozent = f"{regeln.telekom_anteil * 100:.0f} %"
        rechnung = (f"{len(werte)} Monate × {fmt(werte[0])} € × {prozent}" if len(set(werte)) == 1
                    else f"Σ {len(werte)} Monatsbeträge ({fmt(sum(werte, D('0')))} €) × {prozent}")
        rechnung += f", je Monat höchstens {fmt(regeln.telekom_deckel_monat)} €"
    elif art == "entfernung":
        tage, km, wege = int(p["tage"]), int(p["km"]), int(p.get("wege", 1))
        exakt = entfernungspauschale(tage, km, regeln) * wege
        rechnung = f"{tage} Tage × {km} km" + (f" × {wege} Wege" if wege > 1 else "") + " nach Entfernungspauschale"
    elif art == "bewerbung_online":
        n = int(p["anzahl"])
        exakt = n * regeln.bewerbung_online_pauschale
        rechnung = f"{n} × {fmt(regeln.bewerbung_online_pauschale)} €"
    elif art == "dienstreise":
        km = dec(p["km"])
        exakt = km * regeln.dienstreise_km_satz
        rechnung = f"{km} km × {fmt(regeln.dienstreise_km_satz)} €"
    elif art is not None:
        raise ValueError(f"{name}: unbekannte Art {art!r}")
    elif "betrag" in p:
        exakt, rechnung = dec(p["betrag"]), "Betrag"
    elif "anzahl" in p:
        exakt = int(p["anzahl"]) * dec(p["je"])
        rechnung = f"{p['anzahl']} × {fmt(dec(p['je']))} €"
    elif "monatlich" in p or "betraege" in p:
        werte = _monatswerte(p)
        exakt = sum(werte, D("0"))
        rechnung = (f"{len(werte)} × {fmt(werte[0])} €" if len(set(werte)) == 1
                    else " + ".join(fmt(w) for w in werte) + " €")
    else:
        raise ValueError(f"{name}: kein Betrag angegeben")
    if "anteil" in p:
        a = dec(p["anteil"])
        exakt *= a
        rechnung += f" × {a * 100:.0f} % Anteil"
    return Betrag(name, cent(exakt), rundung(exakt), rechnung, False, p.get("notiz", ""))
