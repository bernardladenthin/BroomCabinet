# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Reads the YAML definition of a tax return and works out what goes into which ELSTER field.

Forms covered: Anlage N (commuting, home office, work equipment, business trips, further
income-related expenses), Anlage SO (other income), Anlage V (rental income), donations, § 35a
(household services and craftsmen), Vorsorgeaufwand (insurance), medical costs with the reasonable
burden (zumutbare Belastung). Individual or joint assessment (`veranlagung: zusammen` with a
`person_b` block holding the second person's wage, commute, expenses and insurance).
"""
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal as D
from pathlib import Path

from .arbeitstage import arbeitstage, aus_kalender
from .posten import berechne, cent, dec, entfernungspauschale, euro_ab, euro_auf, fmt, studie_posten
from .regeln import regeln as regeln_fuer


@dataclass
class Eintrag:
    formular: str
    zeile: object          # int, None (line unknown) or text
    feld: str
    wert: D
    einheit: str = "€"
    hinweis: str = ""


@dataclass
class Abschnitt:
    titel: str
    posten: list = field(default_factory=list)       # list[Betrag]
    summe: D = D("0")
    zeilen: list = field(default_factory=list)       # explanatory lines (calculations)


@dataclass
class Ergebnis:
    jahr: int
    eintraege: list = field(default_factory=list)
    abschnitte: list = field(default_factory=list)
    werte: dict = field(default_factory=dict)        # key figures for tests and the summary
    offen: list = field(default_factory=list)
    hinweise: list = field(default_factory=list)
    zeilen_geprueft: bool = True
    simulation: object = None                         # simulation.Simulation


LSTB_FELDER = {
    "rv_an": "Rentenversicherung Arbeitnehmer (Nr. 23a)",
    "rv_ag": "Rentenversicherung Arbeitgeber (Nr. 22a)",
    "kv_an": "Krankenversicherung Arbeitnehmer (Nr. 25)",
    "pv_an": "Pflegeversicherung Arbeitnehmer (Nr. 26)",
    "av_an": "Arbeitslosenversicherung Arbeitnehmer (Nr. 27)",
    "zuschuss_kv": "steuerfreier Zuschuss Krankenversicherung (Nr. 24a)",
    "zuschuss_pv": "steuerfreier Zuschuss Pflegeversicherung (Nr. 24c)",
}


def laden(pfad) -> dict:
    import yaml   # here, not at the top: `--help` and the imports must work without PyYAML

    with open(pfad, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Rechner:
    def __init__(self, daten: dict):
        self.d = daten
        self.jahr = int(daten["jahr"])
        self.r = regeln_fuer(self.jahr)
        self.e = Ergebnis(self.jahr, zeilen_geprueft=self.r.zeilen_geprueft)
        self.e.hinweise += daten.get("hinweise", []) or []
        art = daten.get("veranlagung", "einzeln")
        if art not in ("einzeln", "zusammen"):
            raise ValueError(f"veranlagung {art!r}, erlaubt: einzeln, zusammen")
        self.zusammen = art == "zusammen"
        if self.zusammen and not isinstance(daten.get("person_b"), dict):
            raise ValueError("veranlagung: zusammen braucht einen Block person_b")

    # ---------------------------------------------------------------- helpers
    def zeile(self, formular, schluessel):
        return self.r.zeilen.get((formular.split(" (")[0], schluessel))     # "Anlage N (Person B)": lines of Anlage N

    def eintrag(self, formular, schluessel, feld, wert, einheit="€", hinweis=""):
        self.e.eintraege.append(Eintrag(formular, self.zeile(formular, schluessel), feld, wert, einheit, hinweis))

    def liste(self, titel, posten) -> Abschnitt:
        a = Abschnitt(titel)
        for p in posten or []:
            b = berechne(p, self.r)
            b.kategorie = str(p.get("kategorie") or "")
            b.belege = [p["belege"]] if isinstance(p.get("belege"), str) else list(p.get("belege") or [])
            a.posten.append(b)
            if b.offen:
                self.e.offen.append(f"{titel}: {b.bezeichnung}" + (f" – {b.notiz}" if b.notiz else ""))
            elif p.get("nicht_anerkannt"):
                # filed, but not recognised by the tax office: shown, not counted, so the return still reads as
                # filed and the simulation still meets the notice
                b.nicht_anerkannt = True
                b.notiz = f"vom Finanzamt nicht anerkannt: {p['nicht_anerkannt']}"
                self.e.hinweise.append(f"{titel}: {b.bezeichnung} ({fmt(b.eintrag)} €) – {b.notiz}")
            else:
                a.summe += b.eintrag
        self.e.abschnitte.append(a)
        return a

    # ---------------------------------------------------------------- Anlage N
    def anlage_n(self, d=None, formular="Anlage N", sfx=""):
        """Anlage N of one person: d is the return (person A) or its `person_b` block, sfx '' or '_b'."""
        d = self.d if d is None else d
        arbeit = d.get("arbeit", []) or []
        a = Abschnitt(f"{formular}: Wege zur ersten Tätigkeitsstätte")
        gruppen, ho_tage = {}, 0
        for ag in arbeit:
            name = ag["arbeitgeber"]
            von, bis = ag["von"], ag["bis"]
            moeglich = arbeitstage(von, bis)
            if ag.get("kalender"):
                # the days counted from a calendar per calendar week instead of given as totals
                doppelt = [k for k in ("buero_tage", "homeoffice_tage", "urlaub", "krank") if k in ag]
                if doppelt:
                    raise ValueError(f"{name}: kalender und {', '.join(doppelt)} zugleich; nur eines von beiden")
                z, kal_hinweise = aus_kalender(ag["kalender"], von, bis)
                buero, ho, urlaub, krank = z["A"], z["H"], z["U"], z["K"]
                self.e.hinweise += [f"{name}: {h}" for h in kal_hinweise]
            else:
                buero, ho = int(ag.get("buero_tage", 0)), int(ag.get("homeoffice_tage", 0))
                urlaub, krank = int(ag.get("urlaub", 0)), int(ag.get("krank", 0))
            nicht_buero = ho + urlaub + krank
            ep = entfernungspauschale(buero, int(ag["km"]), self.r)
            mittel = ag.get("verkehrsmittel", "pkw")
            if mittel not in ("pkw", "sonstige"):
                raise ValueError(f"{name}: verkehrsmittel {mittel!r}, erlaubt: pkw, sonstige")
            gruppen[mittel] = gruppen.get(mittel, D("0")) + ep
            ho_tage += ho
            a.zeilen.append(f"{name} ({von:%d.%m.}–{bis:%d.%m.%Y}): {moeglich} mögliche Arbeitstage, "
                            f"{buero} Büro, {ho} Homeoffice, {urlaub} Urlaub, {krank} krank; "
                            f"{buero} Tage × {ag['km']} km = {fmt(ep)} €" + ("" if mittel == "pkw" else " (ohne Pkw)"))
            if buero + nicht_buero > moeglich:
                self.e.hinweise.append(f"{name}: Büro + Homeoffice + Urlaub + krank = {buero + nicht_buero} "
                                       f"> {moeglich} mögliche Arbeitstage")
            if ag.get("offen"):
                self.e.offen.append(f"Arbeitstage {name}: {ag['offen']}")
            self.eintrag(formular, "buero_tage", f"{name}: Arbeitstage an der Tätigkeitsstätte", D(buero), "Tage")
            self.eintrag(formular, "nicht_buero_tage", f"{name}: Tage ohne Fahrt (Homeoffice, Urlaub, krank)", D(nicht_buero), "Tage")
            self.eintrag(formular, "entfernung", f"{name}: einfache Entfernung", D(ag["km"]), "km",
                         ag.get("km_hinweis", "") or ("" if mittel == "pkw" else "nicht mit dem Pkw"))
            self.e.werte[f"moegliche_tage_{name}"] = moeglich
            self.e.werte[f"nicht_buero_tage_{name}"] = nicht_buero
        # The notice forms the allowance per group of means of transport, each rounded up to whole euros;
        # without a car it is capped (§ 9 (2) s. 2 EStG).
        brutto_ep = D("0")
        for mittel, summe in gruppen.items():
            gruppe = euro_auf(summe)
            if mittel == "sonstige" and gruppe > self.r.entfernung_hoechstbetrag_ohne_pkw:
                a.zeilen.append(f"ohne Pkw gedeckelt auf {fmt(self.r.entfernung_hoechstbetrag_ohne_pkw)} €")
                gruppe = self.r.entfernung_hoechstbetrag_ohne_pkw
            brutto_ep += gruppe
        frei = dec(d.get("arbeitgeber_fahrtkosten_steuerfrei", 0))
        netto_ep = brutto_ep - frei
        a.zeilen.append(f"Entfernungspauschale {fmt(brutto_ep)} € − steuerfreie Arbeitgeberleistungen {fmt(frei)} € "
                        f"= {fmt(netto_ep)} € (ELSTER rechnet das selbst)")
        a.summe = cent(netto_ep)
        self.e.abschnitte.append(a)
        self.e.werte["entfernungspauschale_brutto" + sfx] = cent(brutto_ep)
        self.e.werte["entfernungspauschale" + sfx] = cent(netto_ep)

        ho = min(ho_tage, self.r.homeoffice_max_tage)
        ho_betrag = ho * self.r.homeoffice_je_tag
        h = Abschnitt(f"{formular}: Homeoffice-Pauschale", summe=ho_betrag,
                      zeilen=[f"{ho_tage} Tage × {fmt(self.r.homeoffice_je_tag)} € = {fmt(ho_betrag)} €"
                              + (f" (gedeckelt auf {self.r.homeoffice_max_tage} Tage)" if ho_tage > ho else "")])
        self.e.abschnitte.append(h)
        self.eintrag(formular, "homeoffice", "Homeoffice-Pauschale: Anzahl Tage", D(ho), "Tage", f"= {fmt(ho_betrag)} €")
        self.e.werte["homeoffice" + sfx] = ho_betrag

        wk = d.get("werbungskosten", {}) or {}
        # Above the limit for immediate deduction an item is open, not counted: only its depreciation
        # (AfA) for the year is deductible, and that amount is the user's to state, marked `afa: true`.
        arbeitsmittel = []
        for p in wk.get("arbeitsmittel") or []:
            if not p.get("offen") and not p.get("afa"):
                b = berechne(p, self.r)
                if b.exakt > self.r.gwg_grenze_brutto:
                    p = {**p, "offen": True, "notiz": f"{fmt(b.exakt)} € über {fmt(self.r.gwg_grenze_brutto)} € brutto, "
                         "nur die AfA des Jahres ist absetzbar: Betrag eintragen und `afa: true` setzen "
                         "(Computer-Hardware und Software: Nutzungsdauer 1 Jahr, BMF 22.02.2022)"}
            arbeitsmittel.append(p)
        am = self.liste(f"{formular}: Arbeitsmittel", arbeitsmittel)
        fb = self.liste(f"{formular}: Fortbildung", wk.get("fortbildung"))
        rk = self.reisekosten(formular, wk)
        we = self.liste(f"{formular}: Weitere Werbungskosten", wk.get("weitere"))
        for schl, ab, feld in [("arbeitsmittel", am, "Arbeitsmittel"), ("fortbildung", fb, "Fortbildungskosten"),
                               ("reisekosten", rk, "Reisekosten bei Auswärtstätigkeiten"),
                               ("weitere", we, "Weitere Werbungskosten")]:
            if schl != "reisekosten" or rk.posten or rk.summe:
                self.eintrag(formular, schl, feld, ab.summe)
            self.e.werte[schl + sfx] = ab.summe
        gesamt = netto_ep + ho_betrag + am.summe + fb.summe + rk.summe + we.summe
        self.e.werte["werbungskosten" + sfx] = cent(gesamt)
        self.e.werte["ueber_pauschbetrag" + sfx] = cent(max(gesamt - self.r.arbeitnehmer_pauschbetrag, D("0")))

    def reisekosten(self, formular, wk) -> Abschnitt:
        """Business trips: travel costs as items, plus the meal allowances (Verpflegungspauschalen)."""
        ab = self.liste(f"{formular}: Reisekosten", wk.get("reisekosten"))
        # what the employer reimbursed tax-free is deducted: from the travel costs (`reisekosten_ersatz`)
        # and from the meal allowances (`verpflegung: {ersatz: ...}`)
        ersatz = euro_ab(wk.get("reisekosten_ersatz", 0))
        if ersatz:
            ab.zeilen.append(f"Reisekosten {fmt(ab.summe)} € − steuerfrei ersetzt {fmt(ersatz)} €")
            ab.summe = max(ab.summe - ersatz, D("0"))
        vp = wk.get("verpflegung") or {}
        if vp:
            t8, an, t24 = (int(vp.get(k, 0)) for k in ("tage_8h", "an_abreise", "tage_24h"))
            kuerz, vp_ersatz = dec(vp.get("kuerzung", 0)), dec(vp.get("ersatz", 0))
            betrag = (t8 + an) * self.r.verpflegung_8h + t24 * self.r.verpflegung_24h - kuerz - vp_ersatz
            ab.zeilen.append(f"Verpflegung: ({t8} Tage über 8 h + {an} An-/Abreisetage) × {fmt(self.r.verpflegung_8h)} € "
                             f"+ {t24} Tage × {fmt(self.r.verpflegung_24h)} € − Kürzung Mahlzeiten {fmt(kuerz)} € "
                             + (f"− steuerfrei ersetzt {fmt(vp_ersatz)} € " if vp_ersatz else "") + f"= {fmt(betrag)} €")
            ab.summe += euro_auf(max(betrag, D("0")))
        return ab

    # ---------------------------------------------------------------- Anlage SO
    def anlage_so(self):
        summe_einkuenfte = D("0")
        quellen = self.d.get("sonstige_einkuenfte", []) or []
        for q in quellen:
            posten = studie_posten(q["studie"] or {}, q["bezeichnung"]) if "studie" in q else []
            ab = self.liste(f"Anlage SO: Werbungskosten {q['bezeichnung']}",
                            posten + list(q.get("werbungskosten") or []))
            ein = euro_ab(q["einnahmen"])
            eink = ein - ab.summe
            ab.zeilen.append(f"Einnahmen {fmt(ein)} € − Werbungskosten {fmt(ab.summe)} € = Einkünfte {fmt(eink)} €")
            self.eintrag("Anlage SO", None, f"{q['bezeichnung']}: Einnahmen", ein)
            self.eintrag("Anlage SO", None, f"{q['bezeichnung']}: Werbungskosten", ab.summe)
            summe_einkuenfte += eink
        self.e.werte["sonstige_einkuenfte"] = summe_einkuenfte
        # § 22 Nr. 3 EStG: a Freigrenze, not an allowance -- below it all is tax-free, from it on all is taxed;
        # a loss is not set off against other income (only against such income of the year before or after)
        fg = self.r.so_freigrenze_leistungen
        if quellen and summe_einkuenfte < 0:
            self.e.hinweise.append(f"Anlage SO: Verlust {fmt(-summe_einkuenfte)} € – nicht mit anderen Einkünften "
                                   "verrechenbar, nur mit Leistungs-Einkünften des Vor- oder Folgejahrs")
        elif quellen and summe_einkuenfte < fg:
            self.e.hinweise.append(f"Anlage SO: Einkünfte {fmt(summe_einkuenfte)} € unter der Freigrenze von "
                                   f"{fmt(fg)} € – steuerfrei")
        elif quellen and summe_einkuenfte - fg < 100:
            self.e.hinweise.append(f"Anlage SO: Einkünfte {fmt(summe_einkuenfte)} € knapp über der Freigrenze von "
                                   f"{fmt(fg)} € – mit {fmt(summe_einkuenfte - fg + 1)} € mehr Werbungskosten wäre "
                                   "alles steuerfrei")

    # ---------------------------------------------------------------- Anlage V
    def anlage_v(self):
        """Rental income per object: income minus its costs, assigned to person A or B (`person:`)."""
        summen = {"A": D("0"), "B": D("0")}
        for q in self.d.get("vermietung", []) or []:
            person = str(q.get("person", "A")).upper()
            if person not in summen:
                raise ValueError(f"vermietung {q['bezeichnung']}: person {person!r}, erlaubt: A, B")
            ab = self.liste(f"Anlage V: Werbungskosten {q['bezeichnung']}", q.get("werbungskosten"))
            ein = euro_ab(q["einnahmen"])
            eink = ein - ab.summe
            ab.zeilen.append(f"Einnahmen {fmt(ein)} € − Werbungskosten {fmt(ab.summe)} € = Einkünfte {fmt(eink)} € (Person {person})")
            self.eintrag("Anlage V", None, f"{q['bezeichnung']}: Einnahmen", ein)
            self.eintrag("Anlage V", None, f"{q['bezeichnung']}: Werbungskosten", ab.summe)
            summen[person] += eink
        if self.d.get("vermietung"):
            self.e.werte["vermietung"] = summen["A"]
            self.e.werte["vermietung_b"] = summen["B"]

    # ---------------------------------------------------------------- Sonderausgaben
    def spenden(self):
        ab = self.liste("Sonderausgaben: Spenden und Mitgliedsbeiträge", self.d.get("spenden"))
        self.eintrag("Sonderausgaben", None, "Zuwendungen an steuerbegünstigte Organisationen", ab.summe)
        self.e.werte["spenden"] = ab.summe

    # ---------------------------------------------------------------- § 35a
    def haushaltsnah(self):
        hh = self.d.get("haushaltsnahe", {}) or {}
        for schl, titel, satz, maxi in [
            ("dienstleistungen", "Haushaltsnahe Dienstleistungen", self.r.p35a_dienstleistung_satz, self.r.p35a_dienstleistung_max),
            ("handwerker", "Handwerkerleistungen (Lohnanteil)", self.r.p35a_handwerker_satz, self.r.p35a_handwerker_max),
        ]:
            ab = self.liste(f"§ 35a: {titel}", hh.get(schl))
            ermaessigung = min(ab.summe * satz, maxi)
            ab.zeilen.append(f"Steuerermäßigung {satz * 100:.0f} % von {fmt(ab.summe)} € = {fmt(ermaessigung)} €")
            self.eintrag("Haushaltsnahe Aufwendungen", schl, titel, ab.summe, hinweis=f"Ermäßigung {fmt(ermaessigung)} €")
            self.e.werte[f"35a_{schl}"] = ab.summe
            self.e.werte[f"35a_{schl}_ermaessigung"] = cent(ermaessigung)

    # ---------------------------------------------------------------- Vorsorge
    def vorsorge(self):
        v = self.d.get("vorsorge", {}) or {}
        for schl, feld in [("kv_ueber_basis", "Kranken-/Pflegeversicherung über die Basisabsicherung hinaus"),
                           ("wahlleistungen", "Wahlleistungen und Zusatzversicherungen"),
                           ("berufsunfaehigkeit", "Berufsunfähigkeitsversicherung"),
                           ("unfall_haftpflicht_risiko", "Unfall-, Haftpflicht- und Risikoversicherungen")]:
            ab = self.liste(f"Vorsorgeaufwand: {feld}", v.get(schl))
            self.eintrag("Vorsorgeaufwand", schl, feld, ab.summe)
            self.e.werte[schl] = ab.summe
        personen = [("", v)]
        if self.zusammen:
            personen.append((" (Person B)", (self.d["person_b"].get("vorsorge") or {})))
        for wer, vp in personen:
            for k, wert in (vp.get("lohnsteuerbescheinigung") or {}).items():
                if k not in LSTB_FELDER:
                    raise ValueError(f"vorsorge.lohnsteuerbescheinigung: unbekannter Schlüssel {k!r}, erlaubt: {', '.join(LSTB_FELDER)}")
                self.eintrag("Vorsorgeaufwand", None, f"LStB {LSTB_FELDER[k]}{wer}", dec(wert),
                             hinweis="kommt per eDaten, nur Kontrolle")
        if v.get("erstattete_beitraege"):
            self.eintrag("Vorsorgeaufwand", None, "Erstattete Beiträge (z. B. Bonus der Krankenkasse)",
                         dec(v["erstattete_beitraege"]), hinweis="meldet die Kasse, nur Kontrolle")

    # ---------------------------------------------------------------- außergewöhnliche Belastungen
    def krankheitskosten(self):
        posten = self.d.get("krankheitskosten")
        if not posten:
            return
        ab = self.liste("Außergewöhnliche Belastungen: Krankheitskosten", posten)
        self.eintrag("Außergewöhnliche Belastungen", None, "Krankheitskosten", ab.summe)
        from .simulation import einkuenfte
        ek = einkuenfte(self.d, self.e.werte, self.r)
        if ek.fehlt:
            ab.zeilen.append("Zumutbare Belastung: offen, weil der Bruttolohn noch fehlt")
            return
        # the Gesamtbetrag der Einkünfte the way the simulation and the notice form it
        gde = ek.gde
        zb = zumutbare_belastung(gde, self.r, self.zusammen)
        abziehbar = max(ab.summe - zb, D("0"))
        ab.zeilen.append(f"Gesamtbetrag der Einkünfte ≈ {fmt(gde)} €, zumutbare Belastung {fmt(zb)} €, "
                         f"wirkt sich aus: {fmt(abziehbar)} €")
        self.e.werte["zumutbare_belastung"] = zb
        self.e.werte["krankheitskosten_wirksam"] = abziehbar

    def rechnen(self) -> Ergebnis:
        self.anlage_n()
        if self.zusammen:
            self.anlage_n(self.d["person_b"], "Anlage N (Person B)", "_b")
        self.anlage_so()
        self.anlage_v()
        self.spenden()
        self.haushaltsnah()
        self.vorsorge()
        self.krankheitskosten()
        from .simulation import simuliere
        self.e.simulation = simuliere(self.d, self.e, self.r)
        return self.e


def zumutbare_belastung(gde: D, regeln, zusammen: bool = False) -> D:
    """Reasonable burden under § 33 (3) EStG, computed in tiers (BFH VI R 75/14); no children,
    single or jointly assessed."""
    summe, unten = D("0"), D("0")
    for bis, satz in (regeln.zumutbar_verheiratet if zusammen else regeln.zumutbar_ledig):
        oben = gde if bis is None else min(gde, bis)
        if oben > unten:
            summe += (oben - unten) * satz
        if bis is None or gde <= bis:
            break
        unten = bis
    return cent(summe)


def rechne(pfad) -> Ergebnis:
    return Rechner(laden(Path(pfad))).rechnen()


def belege(daten) -> list:
    """Every entry under a key `belege` (at any depth), as (where, path or pattern)."""
    gefunden = []

    def gehe(x, stelle):
        if isinstance(x, dict):
            name = x.get("bezeichnung") or x.get("arbeitgeber")
            hier = name or stelle
            for k, v in x.items():
                if k == "belege":
                    for b in [v] if isinstance(v, str) else v:
                        gefunden.append((hier or "(oben)", b))
                else:
                    gehe(v, hier if name else (f"{stelle}/{k}" if stelle else k))
        elif isinstance(x, list):
            for v in x:
                gehe(v, stelle)

    gehe(daten, "")
    return gefunden


DATEINAME = re.compile(r"[^\s\"'(),;:]*\.(?:pdf|png|jpe?g|gif|txt|elfo|xlsx?|ods|odt|docx?|eml|msg|csv|zip|html?)\b",
                       re.IGNORECASE)


def _kommentar(zeile: str) -> str:
    """The comment part of a YAML line: from the first # that is not inside quotes."""
    quote = None
    for i, ch in enumerate(zeile):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or zeile[i - 1] in " \t"):
            return zeile[i + 1:]
    return ""


def dateinamen_in_kommentaren(pfad) -> list:
    """(line, name) for every file name that appears in a comment. A file the return relies on belongs in
    a `belege:` list, where --belege checks that it exists; in a comment nothing checks it."""
    out = []
    for nr, zeile in enumerate(Path(pfad).read_text(encoding="utf-8").splitlines(), 1):
        out += [(nr, m.group(0)) for m in DATEINAME.finditer(_kommentar(zeile))]
    return out


def belege_basis(pfad, daten=None) -> Path:
    """The folder the receipts of a return are relative to: the YAML's own folder, or the one its
    `belege_ordner:` names (relative to the YAML) -- for YAML files kept apart from their receipts."""
    pfad = Path(pfad)
    daten = laden(pfad) if daten is None else daten
    return Path(os.path.normpath(pfad.parent / str((daten or {}).get("belege_ordner") or ".")))


def belege_pruefen(pfad, basis=None) -> list:
    """Checks every receipt relative to belege_basis() (or `basis`); * and ? are allowed.
    Returns (where, receipt) for every receipt that was not found."""
    pfad = Path(pfad)
    daten = laden(pfad)
    basis = Path(basis) if basis else belege_basis(pfad, daten)
    fehlt = []
    for stelle, b in belege(daten):
        if "*" in b or "?" in b:
            ok = any(basis.glob(b))
        else:
            ok = (basis / b).exists()
        if not ok:
            fehlt.append((stelle, b))
    return fehlt
