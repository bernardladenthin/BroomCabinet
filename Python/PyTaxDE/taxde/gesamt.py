# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""All returns of a folder in one JSON: the self-test's snapshot and the viewer's data at once.

    Steuererklärungen/               (any folder)
      2024 Steuererklärung/Steuererklärung 2024.yaml
      2025 Steuererklärung/Steuererklärung 2025.yaml
      Steuererklärungen.json         <- written here, one block per YAML
                                        (or in PyTaxDEConfig/, if the folder has one)

THE YAML FILES ARE THE TRUTH; this file is output, built from them and made for checking and showing. Every
YAML of the folder and of its subfolders (one level) that has a `jahr:` is a return; its block is keyed by
its path relative to the folder, so two returns of one year (or of two people) live side by side.

A block has two parts:
    geprueft   what the self-test compares (taxde/ergebnis.py): ELSTER entries, key figures, the simulation,
               the comparison with a notice, every item with its amount and status, what is open
    anzeige    what the viewer shows besides: levers, the year's rules, the calculation of every item, the
               receipts with the files they name, the clusters with their caps -- rewritten on every
               write, never compared, so rewording a lever raises no alarm
Across all returns, `uebergreifend` holds the time series and the clusters: for every kind of cost or
deduction its value per year against that year's cap (or the threshold from which it counts), so the
viewer shows what is used up and what is not.
"""
import os
from decimal import Decimal as D
from pathlib import Path

from .ergebnis import als_dict, als_json, lesen, unterschiede
from .posten import STUDIE_KATEGORIEN, dec, euro_ab
from .rechner import Rechner, belege, belege_basis, laden

DATEI = "Steuererklärungen.json"
KONFIG = "PyTaxDEConfig"            # optional subfolder for the JSON (and the private scripts, lists)
FORMAT = 2
MAX_DATEIEN = 200                   # files listed per receipt (a folder or a pattern)


# ------------------------------------------------------------------ finding the returns
def finde_yamls(ordner) -> list:
    """Every return of the folder: *.yaml in it and one level below, with a `jahr:`; sorted by year, then path."""
    ordner = Path(ordner)
    gefunden = []
    for p in sorted(list(ordner.glob("*.yaml")) + list(ordner.glob("*/*.yaml"))):
        try:
            d = laden(p)
        except Exception:                                   # not YAML we understand: not a return
            continue
        if isinstance(d, dict) and "jahr" in d:
            gefunden.append((int(d["jahr"]), p.relative_to(ordner).as_posix(), p))
    return [p for _, _, p in sorted(gefunden)]


def schluessel(yaml, ordner) -> str:
    return Path(yaml).resolve().relative_to(Path(ordner).resolve()).as_posix()


def datei(ordner) -> Path:
    """Where the folder's Steuererklärungen.json lives: in its PyTaxDEConfig/ if there is one, else in it."""
    ordner = Path(ordner)
    return ordner / KONFIG / DATEI if (ordner / KONFIG).is_dir() else ordner / DATEI


def finde_gesamt(yaml):
    """The folder whose Steuererklärungen.json holds this YAML: its own folder or the one above (always
    the one above for a YAML in PyTaxDEConfig/).
    Without such a file: the folder above if the YAML sits in a year folder, else its own folder."""
    p = Path(yaml).resolve()
    if p.parent.name == KONFIG:                         # the returns kept in PyTaxDEConfig/ of their folder
        return p.parent.parent
    for o in (p.parent, p.parent.parent):
        if datei(o).exists():
            return o
    return p.parent.parent if p.parent.name.endswith("Steuererklärung") else p.parent


# ------------------------------------------------------------------ the checked part
def geprueft(e) -> dict:
    d = als_dict(e)
    for k in ("format", "erzeugt_von", "quelle"):
        d.pop(k, None)
    d["posten"] = {}
    for ab in e.abschnitte:
        if not ab.posten:
            continue
        titel, n = ab.titel, 1
        while titel in d["posten"]:
            n += 1
            titel = f"{ab.titel} ({n})"
        posten = {}
        for b in ab.posten:
            name, m = b.bezeichnung, 1
            while name in posten:
                m += 1
                name = f"{b.bezeichnung} ({m})"
            posten[name] = {"exakt": b.exakt, "eintrag": b.eintrag, "status": _status(b)}
        d["posten"][titel] = {"summe": ab.summe, "posten": posten}
    return d


def _status(b) -> str:
    return "offen" if b.offen else "nicht anerkannt" if b.nicht_anerkannt else ""


# ------------------------------------------------------------------ receipts with their files
def belegstatus(angabe: str, basis: Path, ordner: Path) -> dict:
    """A receipt as given, whether it exists, and the files it names (a folder or a pattern: its files),
    each relative to the folder of the JSON."""
    if "*" in angabe or "?" in angabe:
        treffer = sorted(basis.glob(angabe))
    else:
        treffer = [basis / angabe] if (basis / angabe).exists() else []
    dateien = []
    for t in treffer:
        if t.is_dir():
            dateien += sorted(f for f in t.rglob("*") if f.is_file())
        else:
            dateien.append(t)
    rel = [Path(os.path.relpath(f, ordner)).as_posix() for f in dateien[:MAX_DATEIEN]]
    return {"angabe": angabe, "gefunden": bool(treffer), "dateien": rel,
            **({"weitere": len(dateien) - MAX_DATEIEN} if len(dateien) > MAX_DATEIEN else {})}


# ------------------------------------------------------------------ clusters: value against the year's cap
def _person(titel: str) -> str:
    return "B" if titel.startswith("Anlage N (Person B)") else "A" if titel.startswith("Anlage N") else ""


def cluster(e, daten, r) -> list:
    """(cluster id, person, value, cap or threshold, parts) of one return, for the overview across years."""
    w, s = e.werte, e.simulation.werte
    zusammen = daten.get("veranlagung") == "zusammen"
    f = 2 if zusammen else 1
    out = []

    def punkt(cid, person, wert, grenze, **extra):
        if wert is not None:
            out.append({"cluster": cid, "person": person, "wert": D(wert),
                        "grenze": None if grenze is None else D(grenze), **extra})

    ho_extra = {}                                   # home-office items filed among the further expenses
    for ab in e.abschnitte:
        for b in ab.posten:
            if b.kategorie == "homeoffice" and not b.offen and not b.nicht_anerkannt:
                ho_extra[_person(ab.titel)] = ho_extra.get(_person(ab.titel), D("0")) + b.eintrag
    personen = [("A", "", daten)] + ([("B", "_b", daten.get("person_b") or {})] if zusammen else [])
    for person, sfx, d in personen:
        if "werbungskosten" + sfx not in w:
            continue
        ho = w.get("homeoffice" + sfx, D("0")) + ho_extra.get(person, D("0"))
        teile = {"fahrt": w.get("entfernungspauschale" + sfx, D("0")), "homeoffice": ho,
                 "arbeitsmittel": w.get("arbeitsmittel" + sfx, D("0")), "fortbildung": w.get("fortbildung" + sfx, D("0")),
                 "reisekosten": w.get("reisekosten" + sfx, D("0")),
                 "weitere": w.get("weitere" + sfx, D("0")) - ho_extra.get(person, D("0"))}
        punkt("werbungskosten", person, w["werbungskosten" + sfx], r.arbeitnehmer_pauschbetrag, teile=teile)
        ho_cap = r.homeoffice_je_tag * r.homeoffice_max_tage
        punkt("homeoffice", person, ho, ho_cap if ho_cap else None)
        # the cap is always shown; it binds only for trips without a car ("gilt"), by car there is none
        ohne_pkw = any(a.get("verkehrsmittel") == "sonstige" for a in d.get("arbeit") or [])
        punkt("fahrt", person, w.get("entfernungspauschale_brutto" + sfx, D("0")),
              r.entfernung_hoechstbetrag_ohne_pkw, gilt=ohne_pkw)
    if daten.get("sonstige_einkuenfte"):              # Anlage SO: studies, surveys -- against the Freigrenze
        teile = {"fahrten": D("0"), "parken": D("0"), "kleinausgaben": D("0"), "weitere": D("0")}
        for ab in e.abschnitte:
            if ab.titel.startswith("Anlage SO: Werbungskosten"):
                for b in ab.posten:
                    if not b.offen and not b.nicht_anerkannt:
                        teile[STUDIE_KATEGORIEN.get(b.kategorie, "weitere")] += b.eintrag
        einnahmen = sum((euro_ab(dec(q["einnahmen"])) for q in daten["sonstige_einkuenfte"]), D("0"))
        punkt("sonstige", "", w.get("sonstige_einkuenfte", D("0")), r.so_freigrenze_leistungen,
              teile=teile, einnahmen=einnahmen)
    if s:
        hb = r.altersvorsorge_hoechstbetrag
        punkt("altersvorsorge", "", s.get("altersvorsorge_summe"), None if hb is None else hb * f)
        if "beschraenkt" in s:
            punkt("sonstige_vorsorge", "", s["sonstige_unwirksam"] + s["beschraenkt"] - s["altersvorsorge"],
                  r.sonstige_vorsorge_hoechstbetrag * f)
        punkt("spenden", "", w.get("spenden"), euro_ab(s["gde"] * r.spenden_hoechstsatz) if "gde" in s else None)
        punkt("soli", "", s.get("festgesetzt"), r.soli["freigrenze"] * f)
        if daten.get("riester"):
            ri = daten["riester"]
            punkt("riester", "", D(str(ri.get("beitraege", 0))) + D(str(ri.get("zulage_sonderausgaben", 0))),
                  r.riester_hoechstbetrag * len(personen))
    else:
        punkt("spenden", "", w.get("spenden"), None)
    punkt("haushaltsnahe", "", w.get("35a_dienstleistungen"), r.p35a_dienstleistung_max / r.p35a_dienstleistung_satz)
    punkt("handwerker", "", w.get("35a_handwerker"), r.p35a_handwerker_max / r.p35a_handwerker_satz)
    if "zumutbare_belastung" in w:
        k = next((a.summe for a in e.abschnitte if a.titel.startswith("Außergewöhnliche")), D("0"))
        punkt("krankheitskosten", "", k, w["zumutbare_belastung"])
    return out


CLUSTER = {   # id: (title, kind, explanation); kind "obergrenze": a cap; "schwelle": counts only above it
    "werbungskosten": ("Werbungskosten", "schwelle",
                       "Werbungskosten je Person; erst über dem Arbeitnehmer-Pauschbetrag wirkt jeder weitere Euro"),
    "fahrt": ("Fahrten zur Arbeit", "obergrenze",
              "Entfernungspauschale gegen den Höchstbetrag; der gilt nur für Wege ohne eigenen Pkw, mit dem Pkw gibt es keine Grenze"),
    "homeoffice": ("Homeoffice", "obergrenze",
                   "Homeoffice-Pauschale (auch wo sie unter den weiteren Werbungskosten erklärt wurde); vor 2020 gab es sie nicht"),
    "altersvorsorge": ("Altersvorsorge", "obergrenze",
                       "Rentenbeiträge (Arbeitnehmer + Arbeitgeber) gegen den Höchstbetrag; darunter wäre Platz für Rürup"),
    "sonstige_vorsorge": ("Sonstige Vorsorge", "obergrenze",
                          "Kranken-, Pflege-, Arbeitslosen- und weitere Versicherungen gegen den Höchstbetrag; "
                          "die Basis-Kranken- und Pflegeversicherung zählt auch darüber"),
    "spenden": ("Spenden", "obergrenze", "Spenden gegen 20 % des Gesamtbetrags der Einkünfte"),
    "haushaltsnahe": ("Haushaltsnahe Dienstleistungen", "obergrenze", "Aufwand gegen den Höchstbetrag (20 % davon, höchstens 4.000 €)"),
    "handwerker": ("Handwerkerleistungen", "obergrenze", "Lohnanteil gegen den Höchstbetrag (20 % davon, höchstens 1.200 €)"),
    "krankheitskosten": ("Krankheitskosten", "schwelle", "wirken erst über der zumutbaren Belastung"),
    "riester": ("Riester", "obergrenze", "Beiträge und Zulage gegen den Höchstbetrag"),
    "sonstige": ("Sonstige Einkünfte (Studien, Umfragen)", "freigrenze",
                 "Einnahmen abzüglich Fahrten, Parken und Kleinausgaben gegen die Freigrenze; darunter steuerfrei, "
                 "ab der Grenze ist alles steuerpflichtig"),
    "soli": ("Solidaritätszuschlag", "schwelle", "festgesetzte Einkommensteuer gegen die Freigrenze; darüber wird Soli fällig"),
}


# ------------------------------------------------------------------ the display part
REGELN = ("grundfreibetrag", "arbeitnehmer_pauschbetrag", "entfernung", "homeoffice_je_tag", "homeoffice_max_tage",
          "altersvorsorge_hoechstbetrag", "altersvorsorge_quote", "sonstige_vorsorge_hoechstbetrag",
          "sonderausgaben_pauschbetrag", "soli", "verpflegung_8h", "verpflegung_24h", "gwg_grenze_netto")


def anzeige(e, daten, yaml: Path, ordner: Path, r) -> dict:
    basis = belege_basis(yaml, daten)
    abschnitte = []
    for ab in e.abschnitte:
        abschnitte.append({
            "titel": ab.titel, "summe": ab.summe, "zeilen": list(ab.zeilen),
            "posten": [{"bezeichnung": b.bezeichnung, "rechnung": b.rechnung, "exakt": b.exakt, "eintrag": b.eintrag,
                        "status": _status(b), "notiz": b.notiz, "kategorie": b.kategorie,
                        "belege": [belegstatus(x, basis, ordner) for x in b.belege]} for b in ab.posten],
        })
    personen = [{"person": "A", "name": (daten.get("steuerpflichtig") or {}).get("name", "")}]
    if daten.get("veranlagung") == "zusammen":
        personen.append({"person": "B", "name": (daten.get("person_b") or {}).get("name", "")})
    return {
        "jahr": e.jahr,
        "veranlagung": daten.get("veranlagung", "einzeln"),
        "personen": personen,
        "zeilen_geprueft": e.zeilen_geprueft,
        "hebel": list(e.simulation.hebel),
        "regeln": {k: r.get(k) for k in REGELN},
        "abschnitte": abschnitte,
        "belege": [dict(stelle=stelle, **belegstatus(x, basis, ordner)) for stelle, x in belege(daten)],
        "cluster": cluster(e, daten, r),
    }


# ------------------------------------------------------------------ one block, all blocks
def block(yaml, ordner) -> dict:
    yaml, ordner = Path(yaml), Path(ordner)
    try:
        daten = laden(yaml)
        rechner = Rechner(daten, yaml)
        e = rechner.rechnen()
    except Exception as fehler:                              # one broken return must not hide the others
        return {"fehler": f"{type(fehler).__name__}: {fehler}"}
    return {"geprueft": geprueft(e), "anzeige": anzeige(e, daten, yaml, ordner, rechner.r)}


def uebergreifend(bloecke: dict) -> dict:
    reihe, punkte = [], {cid: [] for cid in CLUSTER}
    for quelle, b in bloecke.items():
        if "geprueft" not in b:
            continue
        g, a = b["geprueft"], b["anzeige"]
        s = g["simulation"]["werte"]
        zeile = {"quelle": quelle, "jahr": g["jahr"], "veranlagung": a["veranlagung"]}
        if s:
            brutto = s.get("bruttoarbeitslohn", D("0")) + s.get("bruttoarbeitslohn_b", D("0"))
            zeile.update(brutto=brutto, gesamtbetrag=s["gde"], zve=s["zve"], tarif=s["tarif"],
                         festgesetzt=s["festgesetzt"], soli=s["soli"], lohnsteuer=s["lohnsteuer"],
                         erstattung=s["erstattung"], grenzsteuersatz=s["grenzsteuersatz"],
                         durchschnittssteuersatz=(s["festgesetzt"] / s["zve"]).quantize(D("0.0001")) if s["zve"] else D("0"))
        reihe.append(zeile)
        for p in a["cluster"]:
            punkte[p["cluster"]].append({"quelle": quelle, "jahr": g["jahr"], **{k: v for k, v in p.items() if k != "cluster"}})
    reihe.sort(key=lambda z: (z["jahr"], z["quelle"]))
    mit = [z for z in reihe if "erstattung" in z]
    return {
        "zeitreihe": reihe,
        "summen": {"jahre": len(reihe), "festgesetzt": sum((z["festgesetzt"] for z in mit), D("0")),
                   "erstattung": sum((z["erstattung"] for z in mit), D("0"))},
        "cluster": [{"id": cid, "titel": t, "art": art, "erklaerung": erkl,
                     "punkte": sorted(punkte[cid], key=lambda p: (p["jahr"], p["quelle"], p["person"]))}
                    for cid, (t, art, erkl) in CLUSTER.items() if punkte[cid]],
    }


def bauen(ordner, nur=None, alt=None) -> dict:
    """The whole file. `nur`: the YAML paths whose blocks are built anew; every other block is taken from
    `alt` (the file as it was) where it exists there -- so one year can be accepted without the others."""
    ordner = Path(ordner)
    nur = None if nur is None else {schluessel(y, ordner) for y in nur}
    alte = (alt or {}).get("erklaerungen", {})
    bloecke = {}
    for y in finde_yamls(ordner):
        k = schluessel(y, ordner)
        bloecke[k] = alte[k] if nur is not None and k not in nur and k in alte else block(y, ordner)
    # through JSON once, so every block holds the same types whether it was computed or read
    bloecke = lesen(als_json(bloecke))
    return {"format": FORMAT, "erzeugt_von": "PyTaxDE", "erklaerungen": bloecke,
            "uebergreifend": uebergreifend(bloecke)}


def lesen_datei(ordner):
    p = datei(ordner)
    return lesen(p.read_text(encoding="utf-8")) if p.exists() else None


def schreiben(daten: dict, ordner) -> Path:
    ziel = datei(ordner)
    ziel.write_bytes(als_json(daten).encode("utf-8"))
    return ziel


# ------------------------------------------------------------------ the self-test against the file
def vergleichen(ordner, nur=None, frisch=None) -> dict:
    """{key: None (no block stored yet) | "fehler: ..." | [differences]} for every return of the folder,
    or only for the YAML paths in `nur`. Only the checked part is compared."""
    ordner = Path(ordner)
    gespeichert = (lesen_datei(ordner) or {}).get("erklaerungen", {})
    frisch = frisch or bauen(ordner)
    auswahl = None if nur is None else {schluessel(y, ordner) for y in nur}
    out = {}
    for k, b in frisch["erklaerungen"].items():
        if auswahl is not None and k not in auswahl:
            continue
        if "fehler" in b:
            out[k] = "fehler: " + b["fehler"]
        elif k not in gespeichert or "geprueft" not in gespeichert[k]:
            out[k] = None
        else:
            out[k] = unterschiede(gespeichert[k]["geprueft"], b["geprueft"])
    return out
