# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Reads the YAML definition of a tax return and works out what goes into which ELSTER field.

Forms covered: Anlage N (commuting, home office, work equipment, business trips, further
income-related expenses), Anlage SO (other income), Anlage V (rental income), donations, § 35a
(household services and craftsmen), Vorsorgeaufwand (insurance), medical costs with the reasonable
burden (zumutbare Belastung), children (Anlage Kind: allowances, Kindergeld, childcare costs), wage replacement
benefits (§ 32b), church tax as Sonderausgabe. Individual or joint assessment (`veranlagung: zusammen` with a
`person_b` block holding the second person's wage, commute, expenses and insurance), or spouses assessed
separately with their Sonderausgaben halved (`ehegatte:`).
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
    kinder: list = field(default_factory=list)        # per child: name, monate, freibetrag, kindergeld


LSTB_FELDER = {
    "rv_an": "Rentenversicherung Arbeitnehmer (Nr. 23a)",
    "rv_ag": "Rentenversicherung Arbeitgeber (Nr. 22a)",
    "kv_an": "Krankenversicherung Arbeitnehmer (Nr. 25)",
    "pv_an": "Pflegeversicherung Arbeitnehmer (Nr. 26)",
    "av_an": "Arbeitslosenversicherung Arbeitnehmer (Nr. 27)",
    "zuschuss_kv": "steuerfreier Zuschuss Krankenversicherung (Nr. 24a)",
    "zuschuss_pv": "steuerfreier Zuschuss Pflegeversicherung (Nr. 24c)",
    # where a notice states the reduction for sick pay itself (older notices show the contributions already
    # reduced, and no reduction): that amount instead of 4 %
    "kv_kuerzung": "Kürzung Krankengeld laut Bescheid",
}


def laden(pfad) -> dict:
    import yaml   # here, not at the top: `--help` and the imports must work without PyYAML

    with open(pfad, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Rechner:
    def __init__(self, daten: dict, pfad=None, aufteilen: bool = True):
        """`pfad`: the YAML file, needed only to find a spouse's return named relative to it (`ehegatte.datei`);
        `aufteilen=False` computes that spouse's own figures without halving them again."""
        self.d = daten
        self.pfad = None if pfad is None else Path(pfad)
        self.aufteilen = aufteilen
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
        """Medical costs and other extraordinary burdens under § 33 (a stay at a spa, care, ...), both against
        the reasonable burden; `sonstige_belastungen` is the notice's line "sonstige außergewöhnliche Belastungen"."""
        posten, sonstige = self.d.get("krankheitskosten"), self.d.get("sonstige_belastungen")
        if not posten and not sonstige:
            return
        ab = self.liste("Außergewöhnliche Belastungen: Krankheitskosten", posten)
        self.eintrag("Außergewöhnliche Belastungen", None, "Krankheitskosten", ab.summe)
        summe = ab.summe
        if sonstige:
            so = self.liste("Außergewöhnliche Belastungen: sonstige", sonstige)
            self.eintrag("Außergewöhnliche Belastungen", None, "sonstige außergewöhnliche Belastungen", so.summe)
            summe += so.summe
            self.e.werte["aussergewoehnliche_belastungen"] = summe
        from .simulation import einkuenfte
        ek = einkuenfte(self.d, self.e.werte, self.r)
        if ek.fehlt:
            ab.zeilen.append("Zumutbare Belastung: offen, weil der Bruttolohn noch fehlt")
            return
        # the Gesamtbetrag der Einkünfte the way the simulation and the notice form it
        gde = ek.gde
        kinder = sum(1 for k in self.e.kinder if k["monate"])
        zb = zumutbare_belastung(gde, self.r, self.zusammen, kinder)
        abziehbar = max(summe - zb, D("0"))
        ab.zeilen.append(f"Gesamtbetrag der Einkünfte ≈ {fmt(gde)} €, zumutbare Belastung {fmt(zb)} €"
                         + (f" ({kinder} Kinder)" if kinder else "") + f", wirkt sich aus: {fmt(abziehbar)} €")
        self.e.werte["zumutbare_belastung"] = zb
        self.e.werte["krankheitskosten_wirksam"] = abziehbar

    # ---------------------------------------------------------------- Kinder
    @staticmethod
    def _monate(kind, jahr) -> list:
        """The months of the year in which the child counts: from the month of birth on, all twelve if born
        before; `monate: n` states the number (the last n months) where the notice counted differently."""
        if "monate" in kind:
            n = int(kind["monate"])
            if not 0 <= n <= 12:
                raise ValueError(f"Kind {kind.get('name')}: monate {n}, erlaubt 0 bis 12")
            return list(range(13 - n, 13)) if n else []
        geburt = kind.get("geburt")
        if geburt is None or geburt.year < jahr:
            return list(range(1, 13))
        return [] if geburt.year > jahr else list(range(geburt.month, 13))

    def kinder(self):
        """Children (§ 31, § 32 (6) EStG): for every child the allowances for its months of the year and the
        Kindergeld they are weighed against (the simulation does the Günstigerprüfung); childcare costs
        (§ 10 (1) no. 5) as Sonderausgaben, their share capped per child.

            kinder:
              - name: Kind A
                geburt: 2017-03-01
                freibetrag: voll        # voll (default for a joint assessment) or halb (default otherwise)
                betreuungskosten:       # Kita, after-school care: items, receipts as usual
                  - {bezeichnung: Hort, monatlich: 120, monate: 12}

        `kindergeld:` gives the year's claim where it differs from the rules (a third child, a claim for part of
        the year), `monate:` the months counted where the notice counted differently."""
        r = self.r
        kgm = r.kindergeld_monat
        kgm = list(kgm) if isinstance(kgm, list) else [kgm] * 12
        kbk_summe = D("0")
        for k in self.d.get("kinder") or []:
            name = str(k.get("name") or f"Kind {len(self.e.kinder) + 1}")
            art = k.get("freibetrag", "voll" if self.zusammen else "halb")
            if art not in ("voll", "halb"):
                raise ValueError(f"Kind {name}: freibetrag {art!r}, erlaubt: voll, halb")
            faktor = D("1") if art == "voll" else D("0.5")
            monate = self._monate(k, self.jahr)
            freibetrag = euro_ab((r.kinderfreibetrag + r.bea_freibetrag) * len(monate) / 12 * faktor)
            if "kindergeld" in k:
                kindergeld = dec(k["kindergeld"])
            else:
                kindergeld = (sum((kgm[m - 1] for m in monate), D("0")) + (r.kinderbonus if monate else 0)) * faktor
            self.e.kinder.append({"name": name, "monate": len(monate), "freibetrag": freibetrag, "kindergeld": cent(kindergeld)})
            self.e.werte[f"freibetraege_kind_{name}"] = freibetrag
            self.e.werte[f"kindergeld_{name}"] = cent(kindergeld)
            self.eintrag("Anlage Kind", None, f"{name}: Monate", D(len(monate)), "Monate",
                         f"Freibeträge {fmt(freibetrag)} € ({art}), Kindergeld {fmt(kindergeld)} €")
            if k.get("betreuungskosten"):
                ab = self.liste(f"Sonderausgaben: Kinderbetreuungskosten {name}", k["betreuungskosten"])
                # the share of the exact costs, rounded up (1,000.50 × 2 / 3 = 667, not 1,001 × 2 / 3 -> 668)
                exakt = sum((b.exakt for b in ab.posten if not b.offen and not b.nicht_anerkannt), D("0"))
                z, n = r.kinderbetreuung["anteil"]
                abziehbar = min(euro_auf(exakt * z / n), r.kinderbetreuung["hoechstbetrag"])
                ab.zeilen.append(f"{fmt(ab.summe)} € × {r.kinderbetreuung['anteil'][0]}/{r.kinderbetreuung['anteil'][1]}, "
                                 f"höchstens {fmt(r.kinderbetreuung['hoechstbetrag'])} € = {fmt(abziehbar)} € abziehbar")
                self.eintrag("Anlage Kind", None, f"{name}: Kinderbetreuungskosten", ab.summe, hinweis=f"abziehbar {fmt(abziehbar)} €")
                kbk_summe += abziehbar
        if kbk_summe:
            self.e.werte["kinderbetreuung"] = kbk_summe

    # ---------------------------------------------------------------- Progressionsvorbehalt, Kirchensteuer
    def lohnersatz(self):
        """Wage replacement benefits (Elterngeld, Krankengeld, Arbeitslosengeld, ...): tax-free, but they raise
        the rate on the rest (§ 32b EStG). Per person, as `lohnersatz:` items (the benefit office reports them)."""
        personen = [("", "", self.d)] + ([(" (Person B)", "_b", self.d["person_b"])] if self.zusammen else [])
        for wer, sfx, d in personen:
            posten = d.get("lohnersatz")
            if posten:
                summe = sum((berechne(p, self.r, rundung=euro_ab).exakt for p in posten), D("0"))
                self.eintrag("Progressionsvorbehalt", None, "Lohn- und Einkommensersatzleistungen" + wer, euro_ab(summe),
                             hinweis="meldet der Leistungsträger, nur Kontrolle")
                self.e.werte["lohnersatz" + sfx] = euro_ab(summe)

    def kirchensteuer(self):
        """Church tax paid in the year is a Sonderausgabe, less what was refunded in it (§ 10 (1) no. 4); a
        refund above the payments is added to the income (§ 10 (4b) s. 3). `gezahlt` defaults to the church tax
        on the wage tax certificates."""
        ki = self.d.get("kirchensteuer")
        if not ki:
            return
        if "gezahlt" in ki:
            gezahlt = dec(ki["gezahlt"])
        else:
            personen = [self.d] + ([self.d["person_b"]] if self.zusammen else [])
            gezahlt = sum((dec(x.get("kirchensteuer", 0)) for p in personen for x in p.get("lohnsteuerbescheinigungen") or []), D("0"))
        erstattet = dec(ki.get("erstattet", 0))
        self.e.werte["kirchensteuer_gezahlt"] = euro_auf(gezahlt)
        self.e.werte["kirchensteuer_erstattet"] = euro_ab(erstattet)
        self.eintrag("Sonderausgaben", None, "gezahlte Kirchensteuer", euro_auf(gezahlt))
        if erstattet:
            self.eintrag("Sonderausgaben", None, "erstattete Kirchensteuer", euro_ab(erstattet))

    def ehegatte(self):
        """Einzelveranlagung von Ehegatten with the request to halve (§ 26a (2) s. 2 EStG): Sonderausgaben,
        extraordinary burdens and the § 35a reductions of both are added and halved. The spouse's own figures come
        from the spouse's return, named relative to this one:

            ehegatte: {aufteilung: haelftig, datei: "Steuererklärung 2023 Ehegatte.yaml"}"""
        eg = self.d.get("ehegatte") or {}
        if eg.get("aufteilung") in (None, "keine") or not self.aufteilen:
            return None
        if eg["aufteilung"] != "haelftig" or self.zusammen:
            raise ValueError("ehegatte.aufteilung: haelftig (nur bei Einzelveranlagung) oder keine")
        if self.pfad is None:
            raise ValueError("ehegatte.datei: der Pfad dieser Steuererklärung ist nicht bekannt")
        pfad = self.pfad.parent / eg["datei"]
        anderer = Rechner(laden(pfad), pfad, aufteilen=False).rechnen()
        if anderer.simulation.fehlt or int(anderer.jahr) != self.jahr:
            raise ValueError(f"ehegatte.datei {eg['datei']}: nicht berechenbar oder anderes Jahr")
        return dict(anderer.simulation.eigen)       # its own figures, before halving

    def rechnen(self) -> Ergebnis:
        self.kinder()
        self.anlage_n()
        if self.zusammen:
            self.anlage_n(self.d["person_b"], "Anlage N (Person B)", "_b")
        self.lohnersatz()
        self.anlage_so()
        self.anlage_v()
        self.spenden()
        self.kirchensteuer()
        self.haushaltsnah()
        self.vorsorge()
        self.krankheitskosten()
        from .simulation import simuliere
        self.e.simulation = simuliere(self.d, self.e, self.r, self.ehegatte())
        return self.e


def zumutbare_belastung(gde: D, regeln, zusammen: bool = False, kinder: int = 0) -> D:
    """Reasonable burden under § 33 (3) EStG, computed in tiers (BFH VI R 75/14), in whole euros rounded
    down as the notices of 2018 to 2024 show it (the cents dropped): single or jointly assessed without children,
    or with one or two children, or with three or more (then the marital status does not matter)."""
    stufen = (regeln.zumutbar_kinder_3 if kinder >= 3 else regeln.zumutbar_kinder_1_2 if kinder
              else regeln.zumutbar_verheiratet if zusammen else regeln.zumutbar_ledig)
    summe, unten = D("0"), D("0")
    for bis, satz in stufen:
        oben = gde if bis is None else min(gde, bis)
        if oben > unten:
            summe += (oben - unten) * satz
        if bis is None or gde <= bis:
            break
        unten = bis
    return euro_ab(summe)


def rechne(pfad) -> Ergebnis:
    return Rechner(laden(Path(pfad)), pfad).rechnen()


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
