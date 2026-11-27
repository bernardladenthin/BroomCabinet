#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What goes into ELSTER, from one YAML file per German income tax return -- one return or a whole folder.

One return:
    python pytaxde.py "Steuererklärung 2025.yaml"             entries per form and line, simulation, levers
    python pytaxde.py "Steuererklärung 2025.yaml" --details   with the calculation of every item
    python pytaxde.py "Steuererklärung 2025.yaml" --belege    every receipt exists, no file named only in a comment
    python pytaxde.py "Steuererklärung 2025.yaml" --pruefen   self-test: same as its block in Steuererklärungen.json?
    python pytaxde.py "Steuererklärung 2025.md" --verweise    every link and path of the note exists (taxde/verweise.py)
    python pytaxde.py "Steuererklärung 2025.yaml" --json      accept its result into Steuererklärungen.json

A folder (its YAML files and those one level below, each with a `jahr:`):
    python pytaxde.py D:\data\Steuer                          one line per return
    python pytaxde.py D:\data\Steuer --pruefen [--jahr 2025]  self-test of all returns (or of some years)
    python pytaxde.py D:\data\Steuer --belege                 receipts of all returns
    python pytaxde.py D:\data\Steuer --verweise               links and paths of the notes (*.md) beside the returns
    python pytaxde.py D:\data\Steuer --json [--jahr 2025]     write Steuererklärungen.json (or only those years' blocks)
    python pytaxde.py D:\data\Steuer --anzeigen               the viewer in the browser, data fresh from the YAML files

Steuererklärungen.json sits in the folder, or in its PyTaxDEConfig/ subfolder if it has one (for a single
YAML: in its folder or the one above). The YAML files
are the truth; the JSON is output, made for the self-test and the viewer (taxde/gesamt.py). --pruefen ends
with exit status 0 (all the same, every figure of a `bescheid:` met), 1 (different, or an error) or
2 (a return not in the file yet).

The output is German, like the forms it fills. Needs PyYAML (requirements.txt); --help does not.
"""
import argparse
import sys
from pathlib import Path

from taxde.ergebnis import als_json, lesen, text, unterschiede
from taxde.posten import fmt
from taxde.rechner import belege, belege_pruefen, dateinamen_in_kommentaren, laden, rechne


def bescheid_betrag(name: str, x) -> str:
    """An amount of a notice in euros; the Progressionsvorbehalt rate in per cent with its four decimals."""
    return f"{x:.4f} %".replace(".", ",") if "satz" in name else f"{fmt(x)} €"


def wert_text(e):
    return f"{fmt(e.wert)} €" if e.einheit == "€" else f"{int(e.wert)} {e.einheit}"


def mehrzahl(n, wort, mehrere=None):
    return f"{n} {wort if n == 1 else mehrere or wort + 'e'}"


# ------------------------------------------------------------------ the self-test of one block
def bescheid_text(geprueft: dict):
    """('24 von 24', deviations) of the comparison with a notice, or (None, [])."""
    abgleich = geprueft["simulation"]["abgleich"]
    if not abgleich:
        return None, []
    abw = [(n, v["bescheid"], v["simuliert"]) for n, v in abgleich.items() if v["bescheid"] != v["simuliert"]]
    return f"{len(abgleich) - len(abw)} von {len(abgleich)}", abw


def selbsttest_zeigen(name: str, frisch: dict, unterschied, details=True) -> int:
    """One return's self-test in one line (and its details below); returns 0 (fine), 1 (different,
    an error) or 2 (not stored yet)."""
    if "fehler" in frisch:
        print(f"  {name}: FEHLER {frisch['fehler']}")
        return 1
    teile, unten, status = [], [], 0
    treffer, abw = bescheid_text(frisch["geprueft"])
    if treffer:
        teile.append(f"Bescheid {treffer} getroffen")
        unten += [f"{n}: Bescheid {bescheid_betrag(n, fa)}, simuliert {bescheid_betrag(n, sim)}" for n, fa, sim in abw]
        status = 1 if abw else 0
    if unterschied is None:
        teile.append("noch nicht in Steuererklärungen.json (mit --json übernehmen)")
        status = status or 2
    elif not unterschied:
        teile.append("gleich wie in Steuererklärungen.json")
    else:
        teile.append(f"{mehrzahl(len(unterschied), 'Unterschied')} zu Steuererklärungen.json (gewollt? dann --json)")
        unten += [text(x) for x in unterschied]
        status = 1
    print(f"  {name}: " + " · ".join(teile))
    for z in unten if details else []:
        print(f"    {z}")
    return status


def eine_pruefen(yaml, details=True) -> int:
    from taxde import gesamt
    ordner = gesamt.finde_gesamt(yaml)
    k = gesamt.schluessel(yaml, ordner)
    frisch = lesen(als_json(gesamt.block(yaml, ordner)))
    gesp = ((gesamt.lesen_datei(ordner) or {}).get("erklaerungen") or {}).get(k)
    u = None if not gesp or "geprueft" not in gesp or "fehler" in frisch else unterschiede(gesp["geprueft"], frisch["geprueft"])
    return selbsttest_zeigen(Path(yaml).name, frisch, u, details)


# ------------------------------------------------------------------ receipts
def belege_zeigen(yaml, basis=None, name=None) -> int:
    alle = belege(laden(yaml))
    fehlt = belege_pruefen(yaml, basis)
    nur_kommentar = dateinamen_in_kommentaren(yaml)
    print(f"{name + ': ' if name else ''}{len(alle)} Belege, {len(fehlt)} nicht gefunden, "
          f"{len(nur_kommentar)} Dateinamen nur im Kommentar")
    for stelle, b in fehlt:
        print(f"  FEHLT  {stelle}: {b}")
    for zeile, n in nur_kommentar:
        print(f"  NUR KOMMENTAR  Zeile {zeile}: {n} (in eine belege-Liste, dann wird es geprüft)")
    return 1 if fehlt or nur_kommentar else 0


# ------------------------------------------------------------------ links and paths in the notes
def verweise_zeigen(md, name=None) -> int:
    from taxde.verweise import verweise, verweise_pruefen
    md = Path(md)
    alle = verweise(md.read_text(encoding="utf-8"))
    fehlt = verweise_pruefen(md)
    print(f"{name or md.name}: {mehrzahl(len(alle), 'Verweis', 'Verweise')}, {len(fehlt)} nicht gefunden")
    for nr, art, ziel in fehlt:
        print(f"  FEHLT  Zeile {nr} ({'Link' if art == 'link' else 'Pfad'}): {ziel}")
    return 1 if fehlt else 0


def notizen(ordner, yamls) -> list:
    """The Markdown notes beside the returns: every *.md in a folder that holds a return."""
    return sorted({md for y in yamls for md in Path(y).parent.glob("*.md")})


# ------------------------------------------------------------------ writing the file
def json_schreiben(ordner, nur=None) -> int:
    from taxde import gesamt
    alt = gesamt.lesen_datei(ordner)
    frisch = gesamt.bauen(ordner)
    vorher = gesamt.vergleichen(ordner, nur, frisch)
    d = frisch if nur is None or alt is None else gesamt.bauen(ordner, nur, alt)
    ziel = gesamt.schreiben(d, ordner)
    print(f"{ziel}: {'neu angelegt' if alt is None else 'geschrieben'}")
    for k, u in vorher.items():
        if isinstance(u, str):
            print(f"  {k}: {u}")
        elif u is None:
            print(f"  {k}: neu aufgenommen")
        elif u:
            print(f"  {k}: {mehrzahl(len(u), 'Unterschied')} übernommen")
            for x in u:
                print(f"    {text(x)}")
        else:
            print(f"  {k}: unverändert")
    return 0


# ------------------------------------------------------------------ a folder
def ordner_modus(a) -> int:
    from taxde import gesamt
    ordner = Path(a.pfad)
    yamls = gesamt.finde_yamls(ordner)
    if a.jahr:
        yamls = [y for y in yamls if int(laden(y)["jahr"]) in set(a.jahr)]
    if not yamls:
        print(f"keine Steuererklärung (YAML mit jahr:) in {ordner}" + (f" für {a.jahr}" if a.jahr else ""))
        return 1
    if a.anzeigen:
        from taxde.anzeige import anzeigen
        return anzeigen(ordner, a.port, not a.kein_browser)
    if a.belege:
        return max(belege_zeigen(y, None, gesamt.schluessel(y, ordner)) for y in yamls)
    if a.verweise:
        mds = notizen(ordner, yamls)
        if not mds:
            print(f"keine Notiz (*.md) neben den Steuererklärungen in {ordner}")
            return 0
        return max(verweise_zeigen(md, gesamt.schluessel(md, ordner)) for md in mds)
    if a.json:
        return json_schreiben(ordner, yamls if a.jahr else None)
    frisch = gesamt.bauen(ordner)
    u = gesamt.vergleichen(ordner, yamls, frisch)
    print(f"# Selbsttest {ordner} ({mehrzahl(len(yamls), 'Steuererklärung', 'Steuererklärungen')})")
    codes = [selbsttest_zeigen(k, frisch["erklaerungen"][k], None if isinstance(v, str) else v, a.pruefen)
             for k, v in u.items()]
    if not a.pruefen:
        return 0
    return 1 if 1 in codes else 2 if 2 in codes else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="ELSTER-Einträge aus YAML-Steuererklärungen berechnen, prüfen und anzeigen")
    ap.add_argument("pfad", help="eine Steuererklärung (YAML) oder ein Ordner mit Steuererklärungen")
    ap.add_argument("--details", action="store_true", help="auch jeden Posten mit Rechnung zeigen")
    ap.add_argument("--belege", action="store_true", help="nur prüfen, ob alle Belege existieren")
    ap.add_argument("--verweise", action="store_true",
                    help="prüfen, ob jeder Link und Pfad der Notizen (*.md) existiert; bei einer YAML: ihre .md")
    ap.add_argument("--basis", help="Ordner, gegen den Belege aufgelöst werden (Standard: Ordner der YAML-Datei)")
    ap.add_argument("--json", action="store_true", help="Ergebnis in Steuererklärungen.json übernehmen")
    ap.add_argument("--pruefen", action="store_true",
                    help="Selbsttest: mit Steuererklärungen.json und dem Bescheid vergleichen (Exit 0/1/2)")
    ap.add_argument("--jahr", type=int, nargs="+", help="im Ordner nur diese Jahre (prüfen, übernehmen)")
    ap.add_argument("--anzeigen", action="store_true", help="den Viewer im Browser öffnen (Daten frisch aus den YAML-Dateien)")
    ap.add_argument("--port", type=int, default=0, help="Port des Viewers (Standard: ein freier)")
    ap.add_argument("--kein-browser", action="store_true", help="den Browser nicht selbst öffnen")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    if Path(a.pfad).is_dir():
        return ordner_modus(a)
    if a.belege:
        return belege_zeigen(a.pfad, a.basis)
    if a.verweise:
        md = Path(a.pfad).with_suffix(".md")
        if not md.exists():
            print(f"keine Notiz {md.name} neben {Path(a.pfad).name}")
            return 0
        return verweise_zeigen(md)
    if a.anzeigen:
        from taxde.anzeige import anzeigen
        from taxde.gesamt import finde_gesamt
        return anzeigen(finde_gesamt(a.pfad), a.port, not a.kein_browser)
    if a.json:
        from taxde.gesamt import finde_gesamt
        return json_schreiben(finde_gesamt(a.pfad), [a.pfad])
    if a.pruefen:
        print(f"# Selbsttest {a.pfad}")
        return eine_pruefen(a.pfad)

    e = rechne(a.pfad)
    print(f"# ELSTER-Einträge {e.jahr}" + ("" if e.zeilen_geprueft else "  (Zeilennummern noch nicht an einem Formular geprüft)"))
    formular = None
    for x in e.eintraege:
        if x.formular != formular:
            formular = x.formular
            print(f"\n## {formular}")
        zeile = f"Z. {x.zeile!s:<5}" if x.zeile else "Z. ?    "
        print(f"  {zeile} {x.feld:<70} {wert_text(x):>12}" + (f"   ({x.hinweis})" if x.hinweis else ""))

    w = e.werte
    print("\n## Übersicht")
    print(f"  Werbungskosten gesamt {fmt(w['werbungskosten'])} €, davon über dem Arbeitnehmer-Pauschbetrag "
          f"{fmt(w['ueber_pauschbetrag'])} €")
    if a.details:
        print("\n# Rechenweg")
        for ab in e.abschnitte:
            print(f"\n## {ab.titel}: {fmt(ab.summe)} €")
            for b in ab.posten:
                if b.offen:
                    print(f"  - {b.bezeichnung}: OFFEN" + (f" ({b.notiz})" if b.notiz else ""))
                else:
                    print(f"  - {b.bezeichnung}: {b.rechnung} = {fmt(b.exakt)} € → {fmt(b.eintrag)} €"
                          + (f"  [{b.notiz}]" if b.notiz else ""))
            for z in ab.zeilen:
                print(f"  {z}")
    s = e.simulation
    print("\n# Simulation der Finanzamt-Rechnung")
    if s.fehlt:
        print("  nicht möglich, es fehlt: " + "; ".join(s.fehlt))
    for schritt, betrag in s.schritte:
        print(f"  {schritt:<70} {fmt(betrag):>12} €")
    if s.abgleich:
        print("\n## Abgleich mit dem Bescheid")
        for name, fa, sim in s.abgleich:
            print(f"  {name:<40} Bescheid {bescheid_betrag(name, fa):>14}   simuliert {bescheid_betrag(name, sim):>14}   "
                  + ("✓" if fa == sim else f"Abweichung {bescheid_betrag(name, sim - fa)}"))
    if s.hebel:
        print("\n# Hebel")
        for h in s.hebel:
            print(f"  - {h}")
    if e.offen:
        print("\n## Offen (zählt noch nicht mit)")
        for o in e.offen:
            print(f"  - {o}")
    if e.hinweise:
        print("\n## Hinweise")
        for h in e.hinweise:
            print(f"  - {h}")
    print("\n# Selbsttest")
    eine_pruefen(a.pfad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
