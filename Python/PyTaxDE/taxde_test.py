#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The rules one by one, independent of any particular return: python taxde_test.py

Every expected figure here is worked out by hand in the comment next to it. Nothing reads a file
before a test runs, so `--help` works without PyYAML.
"""
import datetime as dt
import os
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from taxde import Rechner, belege, belege_pruefen, zumutbare_belastung
from taxde.arbeitstage import arbeitstage, aus_kalender, ostersonntag
from taxde.posten import berechne, entfernungspauschale, euro_auf, fmt
from taxde.regeln import STANDARD, alle_jahre, regeln
from taxde.simulation import grenzsteuersatz, haerteausgleich, soli, tarif, tarif_veranlagung


def minimal(**extra):
    d = {"jahr": 2025, "arbeit": [], "werbungskosten": {}}
    d.update(extra)
    return d


class Posten(unittest.TestCase):
    def setUp(self):
        self.r25, self.r26 = regeln(2025), regeln(2026)

    def test_entfernungspauschale_2025_two_tiers(self):
        # 41 days × (20 km × 0.30 + 17 km × 0.38) = 41 × 12.46
        self.assertEqual(entfernungspauschale(41, 37, self.r25), D("510.86"))
        self.assertEqual(entfernungspauschale(10, 15, self.r25), D("45.00"))          # first tier only
        self.assertEqual(entfernungspauschale(10, 20, self.r25), D("60.00"))          # exactly at the border

    def test_entfernungspauschale_2026_from_the_first_km(self):
        self.assertEqual(entfernungspauschale(100, 47, self.r26), D("1786.00"))       # 100 × 47 × 0.38

    def test_telecom_capped_at_20_euros_a_month(self):
        b = berechne({"bezeichnung": "teuer", "art": "telekom", "monatlich": 150, "monate": 12}, self.r25)
        self.assertEqual(b.exakt, D("240.00"))                                         # 12 × at most 20 €

    def test_forms_of_an_item(self):
        r = self.r25
        self.assertEqual(berechne({"bezeichnung": "x", "anzahl": 12, "je": 10}, r).eintrag, 120)
        self.assertEqual(berechne({"bezeichnung": "x", "betraege": [1.10, 2.20]}, r).exakt, D("3.30"))
        self.assertEqual(berechne({"bezeichnung": "x", "betrag": 99, "anteil": 0.5}, r).eintrag, 50)   # 49.50 up
        self.assertEqual(berechne({"bezeichnung": "x", "art": "dienstreise", "km": 245}, r).exakt, D("73.50"))
        self.assertEqual(berechne({"bezeichnung": "x", "art": "bewerbung_online", "anzahl": 7}, r).exakt, D("35.00"))
        # 7 days × (20 × 0.30 + 11 × 0.38 = 10.18) × 2 ways
        self.assertEqual(berechne({"bezeichnung": "x", "art": "entfernung", "tage": 7, "km": 31, "wege": 2}, r).exakt,
                         D("142.52"))

    def test_expenses_round_up_per_item(self):
        self.assertEqual(euro_auf(D("0.01")), 1)
        self.assertEqual(euro_auf(D("181.00")), 181)

    def test_unknown_form_is_an_error(self):
        with self.assertRaises(ValueError):
            berechne({"bezeichnung": "x"}, self.r25)
        with self.assertRaises(ValueError):
            berechne({"bezeichnung": "x", "art": "gibtsnicht"}, self.r25)

    def test_german_number_format(self):
        self.assertEqual(fmt(D("1234567.8")), "1.234.567,80")


class Arbeitstage(unittest.TestCase):
    def test_easter(self):
        self.assertEqual(ostersonntag(2025), dt.date(2025, 4, 20))
        self.assertEqual(ostersonntag(2026), dt.date(2026, 4, 5))

    def test_working_days_berlin(self):
        # 2025: 261 weekdays, 10 holidays on Mon-Fri (8 May 2025 was a one-off holiday)
        self.assertEqual(arbeitstage(dt.date(2025, 1, 1), dt.date(2025, 12, 31)), 251)
        # 2026: 261 weekdays, 7 holidays on Mon-Fri (8 Mar is a Sunday, 3 Oct and 26 Dec a Saturday)
        self.assertEqual(arbeitstage(dt.date(2026, 1, 1), dt.date(2026, 12, 31)), 254)



class Ablage(unittest.TestCase):
    def test_the_json_goes_into_pytaxdeconfig_if_there_is_one(self):
        import tempfile
        from pathlib import Path

        from taxde import gesamt
        with tempfile.TemporaryDirectory() as t:
            o = Path(t)
            self.assertEqual(gesamt.datei(o), o / "Steuererklärungen.json")
            (o / "PyTaxDEConfig").mkdir()
            (o / "2025 Steuererklärung").mkdir()
            self.assertEqual(gesamt.datei(o), o / "PyTaxDEConfig" / "Steuererklärungen.json")
            gesamt.schreiben({"format": 2}, o)
            self.assertTrue((o / "PyTaxDEConfig" / "Steuererklärungen.json").exists())
            self.assertFalse((o / "Steuererklärungen.json").exists())
            self.assertEqual(gesamt.finde_gesamt(o / "2025 Steuererklärung" / "x.yaml"), o.resolve())


class Studie(unittest.TestCase):
    """Anlage SO for a paid study: the expenses from the visits, the Freigrenze of 256 €."""

    @staticmethod
    def so(jahr, einnahmen, **studie):
        daten = minimal(jahr=jahr, sonstige_einkuenfte=[{"bezeichnung": "Studie", "einnahmen": einnahmen,
                                                          "studie": studie}])
        rechner = Rechner(daten)
        return rechner.rechnen(), daten, rechner.r

    def test_2025_trips_by_the_tiers(self):
        # 12 visits × 2 ways × (20 km × 0.30 + 15 km × 0.38 = 11.70) = 280.80 -> 281; 12 × 4 € = 48; 1,200 − 329
        e, *_ = self.so(2025, 1200, termine=12, ort="Klinik", km=35, kleinausgaben_je_termin=4)
        so = next(a for a in e.abschnitte if a.titel.startswith("Anlage SO"))
        self.assertEqual([(b.bezeichnung, b.eintrag) for b in so.posten],
                         [("Fahrten zur Klinik (12 Termine, 35 km, hin und zurück)", 281),
                          ("Kleinausgaben je Termin", 48)])
        self.assertEqual(e.werte["sonstige_einkuenfte"], 871)

    def test_2026_parking_tickets_and_dates(self):
        # 3 visits × 2 × 35 km × 0.38 (from the first km in 2026) = 79.80 -> 80; tickets 4.50 + 6.00 = 10.50 -> 11
        termine = [dt.date(2026, 3, 2), dt.date(2026, 3, 9), dt.date(2026, 4, 1)]
        e, daten, r = self.so(2026, 900, termine=termine, km=35, parken=[4.50, 6.00])
        self.assertEqual(e.werte["sonstige_einkuenfte"], 900 - 80 - 11)
        from taxde import gesamt
        p = next(x for x in gesamt.cluster(e, daten, r) if x["cluster"] == "sonstige")
        self.assertEqual((p["wert"], p["grenze"], p["einnahmen"]), (809, 256, 900))
        self.assertEqual(p["teile"], {"fahrten": 80, "parken": 11, "kleinausgaben": 0, "weitere": 0})

    def test_the_freigrenze(self):
        # 2 × 2 × 10 km × 0.38 = 15.20 -> 16: 284 € is 28 € above the limit, 29 € more expenses make it tax-free
        e, *_ = self.so(2026, 300, termine=2, km=10)
        self.assertTrue(any("knapp über der Freigrenze" in h and "mit 29,00 €" in h for h in e.hinweise))
        e, *_ = self.so(2026, 250, termine=2, km=10)
        self.assertTrue(any("unter der Freigrenze" in h for h in e.hinweise))

    def test_a_loss_is_not_set_off(self):
        from taxde.simulation import einkuenfte
        e, daten, r = self.so(2026, 50, termine=2, km=100)            # 2 × 2 × 100 × 0.38 = 152 -> −102
        self.assertEqual(e.werte["sonstige_einkuenfte"], -102)
        self.assertTrue(any("nicht mit anderen Einkünften verrechenbar" in h for h in e.hinweise))
        self.assertEqual(einkuenfte(daten, e.werte, r).sonstige, 0)

    def test_wrong_input_is_refused(self):
        for studie, text in (({}, "termine fehlt"), ({"termine": 2, "kilometer": 5}, "unbekannte Angabe kilometer"),
                             ({"termine": 2, "parken": [3], "parken_je_termin": 3}, "nicht beides")):
            with self.subTest(text), self.assertRaisesRegex(ValueError, text):
                self.so(2026, 100, **studie)


class Kalender(unittest.TestCase):
    """A calendar per ISO week: Monday to Sunday, A office, H home office, U leave, K sick, F free."""
    VON, BIS = dt.date(2026, 1, 1), dt.date(2026, 12, 31)

    def test_a_week_with_a_holiday(self):
        # KW 14 2026: 30.03.-05.04., Good Friday 03.04.: office Tue-Thu, home office Monday
        z, h = aus_kalender({14: ["H", "A", "A", "A", "F", "F", "F"]}, dt.date(2026, 3, 30), dt.date(2026, 4, 5))
        self.assertEqual(z, {"A": 3, "H": 1, "U": 0, "K": 0})
        self.assertEqual(h, [])

    def test_days_outside_the_job_are_ignored(self):
        # KW 1 2026 starts on 29.12.2025: Monday to Wednesday belong to 2025 and are ignored. 01.01. is New
        # Year; office on a holiday is still a trip to work, so it counts, with a hint to check it
        z, h = aus_kalender({1: "A A A A A F F"}, self.VON, dt.date(2026, 1, 4))
        self.assertEqual(z["A"], 2)
        self.assertEqual(len(h), 1)
        self.assertIn("Neujahr", h[0])

    def test_leave_and_sickness_count_on_working_days_only(self):
        z, h = aus_kalender({52: ["U", "U", "U", "U", "U", "U", "U"]}, dt.date(2026, 12, 21), dt.date(2026, 12, 27))
        self.assertEqual(z["U"], 4)                     # 25.12. is a holiday, the weekend is free anyway
        self.assertEqual(h, [])

    def test_hints_for_a_free_working_day_and_missing_weeks(self):
        z, h = aus_kalender({2: ["F", "A", "A", "A", "H", "F", "F"]}, dt.date(2026, 1, 5), dt.date(2026, 1, 18))
        self.assertEqual(z["A"], 3)
        self.assertTrue(any("05.01.2026: Arbeitstag als frei" in x for x in h))
        self.assertTrue(any("5 Arbeitstage ohne Eintrag (KW 3)" in x for x in h))

    def test_wrong_input_is_refused(self):
        with self.assertRaisesRegex(ValueError, "6 Tage"):
            aus_kalender({2: ["A"] * 6}, self.VON, self.BIS)
        with self.assertRaisesRegex(ValueError, "Zeichen 'X'"):
            aus_kalender({2: ["X"] * 7}, self.VON, self.BIS)
        with self.assertRaisesRegex(ValueError, "KW 54"):
            aus_kalender({54: ["F"] * 7}, self.VON, self.BIS)

    def test_the_calendar_drives_commute_and_home_office(self):
        woche = ["H", "A", "A", "A", "H", "F", "F"]
        ag = {"arbeitgeber": "X", "von": dt.date(2026, 1, 5), "bis": dt.date(2026, 1, 18), "km": 20,
              "kalender": {2: woche, 3: woche}}
        e = Rechner(minimal(jahr=2026, arbeit=[ag])).rechnen()
        self.assertEqual(e.werte["homeoffice"], D("24.00"))            # 4 days × 6 €
        self.assertEqual(e.werte["nicht_buero_tage_X"], 4)
        # 2026: 0.38 €/km from the first km: 6 × 20 × 0.38 = 45.60, rounded up
        self.assertEqual(e.werte["entfernungspauschale"], D("46.00"))

    def test_calendar_and_totals_together_are_refused(self):
        ag = {"arbeitgeber": "X", "von": self.VON, "bis": self.BIS, "km": 20, "buero_tage": 3,
              "kalender": {2: ["A"] * 5 + ["F"] * 2}}
        with self.assertRaisesRegex(ValueError, "kalender und buero_tage"):
            Rechner(minimal(jahr=2026, arbeit=[ag])).rechnen()


class Belastung(unittest.TestCase):
    def test_reasonable_burden_in_tiers(self):
        r = regeln(2025)
        # 15,340 × 5 % + (40,000 − 15,340) × 6 % = 767 + 1,479.60
        self.assertEqual(zumutbare_belastung(D("40000"), r), D("2246.60"))
        self.assertEqual(zumutbare_belastung(D("10000"), r), D("500.00"))
        # 767 + 35,790 × 6 % + 8,870 × 7 % = 767 + 2,147.40 + 620.90
        self.assertEqual(zumutbare_belastung(D("60000"), r), D("3535.30"))


class Rechnen(unittest.TestCase):
    def test_open_items_do_not_count_and_are_reported(self):
        e = Rechner(minimal(spenden=[{"bezeichnung": "A", "betrag": 10},
                                     {"bezeichnung": "B", "offen": True, "notiz": "Betrag fehlt"}])).rechnen()
        self.assertEqual(e.werte["spenden"], 10)
        self.assertEqual(e.offen, ["Sonderausgaben: Spenden und Mitgliedsbeiträge: B – Betrag fehlt"])

    def test_home_office_at_most_210_days(self):
        ag = {"arbeitgeber": "X", "von": dt.date(2025, 1, 1), "bis": dt.date(2025, 12, 31), "km": 10,
              "buero_tage": 0, "homeoffice_tage": 240}
        self.assertEqual(Rechner(minimal(arbeit=[ag])).rechnen().werte["homeoffice"], D("1260.00"))

    def test_too_many_days_gives_a_hint(self):
        ag = {"arbeitgeber": "X", "von": dt.date(2025, 10, 1), "bis": dt.date(2025, 12, 31), "km": 10,
              "buero_tage": 50, "homeoffice_tage": 20}
        e = Rechner(minimal(arbeit=[ag])).rechnen()
        self.assertTrue(any("mögliche Arbeitstage" in h for h in e.hinweise))

    def test_work_equipment_above_the_limit_is_open_until_its_depreciation_is_given(self):
        teuer = {"bezeichnung": "Schreibtisch", "betrag": 1500}
        e = Rechner(minimal(werbungskosten={"arbeitsmittel": [teuer, {"bezeichnung": "Maus", "betrag": 20}]})).rechnen()
        self.assertEqual(e.werte["arbeitsmittel"], 20)
        self.assertTrue(any("Schreibtisch" in o and "AfA" in o for o in e.offen))
        afa = {"bezeichnung": "Schreibtisch, AfA 1/13", "betrag": 1500 / 13, "afa": True}
        e = Rechner(minimal(werbungskosten={"arbeitsmittel": [afa]})).rechnen()
        self.assertEqual(e.werte["arbeitsmittel"], 116)                         # 115.38 up
        self.assertEqual(e.offen, [])

    def test_not_recognised_by_the_tax_office_is_shown_not_counted(self):
        wk = {"weitere": [{"bezeichnung": "Arbeitszimmer", "betrag": 1250, "nicht_anerkannt": "kein Mittelpunkt"},
                          {"bezeichnung": "Telefon", "betrag": 120}]}
        e = Rechner(minimal(werbungskosten=wk)).rechnen()
        self.assertEqual(e.werte["weitere"], 120)
        self.assertEqual(e.offen, [])
        self.assertTrue(any("Arbeitszimmer" in h and "nicht anerkannt: kein Mittelpunkt" in h for h in e.hinweise))

    def test_exactly_at_the_limit_counts(self):
        e = Rechner(minimal(werbungskosten={"arbeitsmittel": [{"bezeichnung": "x", "betrag": 952}]})).rechnen()
        self.assertEqual(e.werte["arbeitsmittel"], 952)

    def test_unknown_key_in_the_wage_tax_certificate_is_an_error(self):
        with self.assertRaises(ValueError):
            Rechner(minimal(vorsorge={"lohnsteuerbescheinigung": {"rv_xx": 1}})).rechnen()

    def test_receipts_are_collected_and_checked(self):
        daten = {"bescheid": {"belege": ["notice.pdf"]},
                 "spenden": [{"bezeichnung": "Verein", "betrag": 10, "belege": ["bescheinigung-*.pdf"]}]}
        self.assertEqual(belege(daten), [("bescheid", "notice.pdf"), ("Verein", "bescheinigung-*.pdf")])
        with tempfile.TemporaryDirectory() as d:
            yaml_datei = Path(d) / "x.yaml"
            yaml_datei.write_text('jahr: 2025\nbescheid: {belege: ["notice.pdf"]}\n'
                                  'spenden: [{bezeichnung: Verein, betrag: 10, belege: ["bescheinigung-*.pdf"]}]\n',
                                  encoding="utf-8")
            (Path(d) / "bescheinigung-2025.pdf").write_bytes(b"")
            self.assertEqual(belege_pruefen(yaml_datei), [("bescheid", "notice.pdf")])

    def test_misspelt_notice_key_is_reported(self):
        e = Rechner(minimal(bescheid={"erstatung": 100, "datum": "2026-05-21"})).rechnen()
        self.assertTrue(any("unbekannter Schlüssel 'erstatung'" in h for h in e.hinweise))
        self.assertEqual(e.simulation.abgleich, [])

    def test_file_names_only_in_comments_are_reported(self):
        from taxde.rechner import dateinamen_in_kommentaren
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.yaml"
            p.write_text("\n".join([
                'jahr: 2025          # aus Notiz.txt übernommen',
                'bescheid: {belege: ["bescheid.pdf"]}   # das ist geprüft',
                'spenden:',
                '  - {bezeichnung: "Spende #1", betrag: 5}   # Quittung im Ordner, siehe Scan 0001.JPG',
                '# Kontoauszug_2025.pdf, Seite 3',
            ]) + "\n", encoding="utf-8")
            # "bescheid.pdf" is in a list and "#1" inside quotes: neither counts
            self.assertEqual(dateinamen_in_kommentaren(p), [(1, "Notiz.txt"), (4, "0001.JPG"), (5, "Kontoauszug_2025.pdf")])

    def test_year_without_rules(self):
        with self.assertRaises(KeyError):
            regeln(2010)


class Tarif(unittest.TestCase):
    def test_2025_points(self):
        r = regeln(2025)
        self.assertEqual(tarif(12096, r), 0)
        self.assertEqual(tarif(12097, r), 0)            # first euro above the basic allowance: 0.14 € -> 0
        # zone 3: y = (44,307 − 17,443) / 10,000 = 2.6864; (176.64 y + 2,397) y + 1,015.13 = 8,729.19
        self.assertEqual(tarif(44307, r), D("8729"))
        self.assertEqual(tarif(79398, r), D("22435"))   # 0.42 × 79,398 − 10,911.92 = 22,435.24
        self.assertEqual(grenzsteuersatz(D("100000"), r), D("0.42"))

    def test_2017_points_and_the_lower_gwg_limit(self):
        r = regeln(2017)
        self.assertEqual(tarif(8820, r), 0)
        # y = (40,000 − 13,769) / 10,000 = 2.6231; (223.76 y + 2,397) y + 939.57 = 8,766.76
        self.assertEqual(tarif(40000, r), D("8766"))
        self.assertEqual(r.gwg_grenze_brutto, D("487.90"))                  # 410 € net until 2017

    def test_2018_points_and_the_flat_rate_without_donations(self):
        r = regeln(2018)
        self.assertEqual(tarif(9000, r), 0)
        # y = (40,000 − 13,996) / 10,000 = 2.6004; (220.13 y + 2,397) y + 948.49 = 8,670.19
        self.assertEqual(tarif(40000, r), D("8670"))
        d = minimal(jahr=2018, lohnsteuerbescheinigungen=[{"brutto": 30000, "lohnsteuer": 4000}],
                    vorsorge={"lohnsteuerbescheinigung": {"rv_an": 0, "rv_ag": 0, "kv_an": 0, "pv_an": 0}})
        self.assertEqual(Rechner(d).rechnen().simulation.werte["unbeschraenkt"], 36)   # no donations: the flat rate

    def test_2019_points_meal_allowances_and_no_home_office(self):
        r = regeln(2019)
        self.assertEqual(tarif(9168, r), 0)
        # y = (40,000 − 14,254) / 10,000 = 2.5746; (216.16 y + 2,397) y + 965.58
        self.assertEqual(tarif(40000, r), D("8569"))
        wk = {"reisekosten": [{"bezeichnung": "Fahrt", "betrag": 30}], "reisekosten_ersatz": 7.20,
              "verpflegung": {"tage_8h": 1, "an_abreise": 2, "tage_24h": 2, "kuerzung": 10, "ersatz": 5}}
        # (30 − 7 reimbursed, rounded down) + (3 × 12 + 2 × 24 − 10 − 5 = 69) = 23 + 69
        e = Rechner(minimal(jahr=2019, werbungskosten=wk)).rechnen()
        self.assertEqual(e.werte["reisekosten"], 92)
        ag = {"arbeitgeber": "X", "von": dt.date(2019, 1, 1), "bis": dt.date(2019, 12, 31), "km": 10, "buero_tage": 200}
        s = Rechner(minimal(jahr=2019, arbeit=[ag])).rechnen().simulation   # no home-office allowance, no lever
        self.assertFalse(any(h.startswith("Homeoffice") for h in s.hebel))

    def test_2020_points_and_the_old_solidarity_surcharge(self):
        r = regeln(2020)
        self.assertEqual(tarif(9408, r), 0)
        # y = (40,000 − 14,532) / 10,000 = 2.5468; (212.02 y + 2,397) y + 972.79 = 8,452.x
        self.assertEqual(tarif(40000, r), D("8452"))
        self.assertEqual(entfernungspauschale(10, 30, r), D("90.00"))       # 0.30 € for every kilometre
        self.assertEqual(soli(D("972"), r), 0)                              # the old exemption limit
        self.assertEqual(soli(D("1500"), r), D("82.50"))                    # min(5.5 % = 82.50, 20 % of 528 = 105.60)
        self.assertEqual(soli(D("1000"), r), D("5.60"))                     # min(55, 20 % of 28 = 5.60)

    def test_2021_points_and_wage_tax_per_certificate(self):
        r = regeln(2021)
        # y = (40,000 − 14,753) / 10,000 = 2.5247; (208.85 y + 2,397) y + 950.96 = 8,333.89
        self.assertEqual(tarif(40000, r), D("8333"))
        self.assertEqual(entfernungspauschale(10, 30, r), D("95.00"))       # 10 × (20 × 0.30 + 10 × 0.35)
        d = minimal(jahr=2021, lohnsteuerbescheinigungen=[{"brutto": 20000, "lohnsteuer": 1000.10},
                                                          {"brutto": 10000, "lohnsteuer": 500.10}],
                    vorsorge={"lohnsteuerbescheinigung": {"rv_an": 0, "rv_ag": 0, "kv_an": 0, "pv_an": 0}})
        # each certificate rounded up: 1,001 + 501, not 1,500.20 -> 1,500
        self.assertEqual(Rechner(d).rechnen().simulation.werte["lohnsteuer"], 1502)

    def test_2022_points_and_the_94_percent_share(self):
        r = regeln(2022)
        self.assertEqual(tarif(10347, r), 0)
        # y = (40,000 − 14,926) / 10,000 = 2.5074; (206.43 y + 2,397) y + 869.32 = 8,177.39
        self.assertEqual(tarif(40000, r), D("8177"))
        d = minimal(jahr=2022, lohnsteuerbescheinigungen=[{"brutto": 30000, "lohnsteuer": 4000}],
                    vorsorge={"lohnsteuerbescheinigung": {"rv_an": 1000.50, "rv_ag": 1000.50, "kv_an": 100, "pv_an": 10}})
        # (1,001 own share up + 1,000 employer share down) × 94 % = 1,880.94 -> 1,881, minus 1,000
        self.assertEqual(Rechner(d).rechnen().simulation.werte["altersvorsorge"], 881)

    def test_2024_points(self):
        r = regeln(2024)
        self.assertEqual(tarif(11784, r), 0)
        # y = (40,000 − 17,005) / 10,000 = 2.2995; (181.19 y + 2,397) y + 991.21 = 7,461.20
        self.assertEqual(tarif(40000, r), D("7461"))
        self.assertEqual(soli(D("18130"), r), 0)                 # the 2024 exemption limit

    def test_2026_points(self):
        r = regeln(2026)
        self.assertEqual(tarif(12348, r), 0)
        # y = (45,941 − 17,799) / 10,000 = 2.8142; (173.10 y + 2,397) y + 1,034.87 = 9,151.67
        self.assertEqual(tarif(45941, r), D("9151"))

    def test_continuous_at_every_zone_border(self):
        """A wrong coefficient shows as a jump at a zone border."""
        for jahr in sorted(alle_jahre(str(STANDARD))):
            r = regeln(jahr)
            for zone in r.tarif[:-1]:
                g = int(zone["bis"])
                with self.subTest(jahr=jahr, grenze=g):
                    self.assertLessEqual(abs(tarif(g + 1, r) - tarif(g, r)), 1)

    def test_solidarity_surcharge(self):
        r = regeln(2025)
        self.assertEqual(soli(D("19950"), r), 0)                 # exemption limit
        self.assertEqual(soli(D("20950"), r), D("119.00"))       # 11.9 % of the 1,000 € above it
        self.assertEqual(soli(D("60000"), r), D("3300.00"))      # the full 5.5 %


class Zusammenveranlagung(unittest.TestCase):
    """A fictitious couple, 2023. Every figure worked out by hand in the comments, without the library."""

    def paar(self, **extra):
        d = {
            "jahr": 2023, "veranlagung": "zusammen",
            "lohnsteuerbescheinigungen": [{"arbeitgeber": "X", "von": dt.date(2023, 1, 1), "bis": dt.date(2023, 12, 31),
                                           "brutto": 40000, "lohnsteuer": 5000}],
            "vorsorge": {"lohnsteuerbescheinigung": {"rv_an": 3720, "rv_ag": 3720, "kv_an": 3420, "pv_an": 680}},
            "person_b": {
                "lohnsteuerbescheinigungen": [{"arbeitgeber": "Y", "von": dt.date(2023, 1, 1), "bis": dt.date(2023, 12, 31),
                                               "brutto": 30000, "lohnsteuer": 3000}],
                "vorsorge": {"lohnsteuerbescheinigung": {"rv_an": 2790, "rv_ag": 2790, "kv_an": 2565, "pv_an": 510}},
            },
            "vermietung": [{"bezeichnung": "Zimmer", "person": "A", "einnahmen": 500}],
        }
        d.update(extra)
        return Rechner(d).rechnen().simulation

    def test_couple_step_by_step(self):
        w = self.paar().werte
        # (40,000 − 1,230) + (30,000 − 1,230) + 500 rent: each person has its own employee allowance
        self.assertEqual((w["einkuenfte_n"], w["einkuenfte_n_b"], w["gde"]), (38770, 28770, 68040))
        self.assertEqual(w["altersvorsorge"], 6510)                 # 13,020 − 6,510 employer shares
        self.assertEqual(w["kv_kuerzung"], 238)                     # per person, down: 4 % of 3,420 = 136.80 + of 2,565 = 102.60
        self.assertEqual(w["kv_pv_basis"], 6937)                    # 5,985 − 238 + 1,190
        self.assertEqual(w["unbeschraenkt"], 72)                    # the flat rate, doubled
        self.assertEqual(w["einkommen"], 54521)                     # 68,040 − 13,447 − 72
        self.assertEqual(w["haerteausgleich"], 320)                 # rent 500 € between 410 and 820: 820 − 500
        self.assertEqual(w["zve"], 54201)
        # splitting: 2 × tariff(27,100); y = 1.1101; (192.59 y + 2,397) y + 966.53 = 3,864.77
        self.assertEqual(w["tarif"], 7728)
        self.assertEqual(w["erstattung"], 272)                      # 5,000 + 3,000 − 7,728

    def test_riester_deducted_when_the_saving_beats_the_allowance(self):
        w = self.paar(riester={"beitraege": 2000, "zulage_sonderausgaben": 175, "zulage_hinzurechnung": 175}).werte
        self.assertEqual((w["riester"], w["einkommen"], w["zve"]), (2175, 52346, 52026))
        self.assertEqual(w["tarif"], 7120)                          # saving 608 € > allowance 175 €
        self.assertEqual(w["festgesetzt"], 7295)                    # the allowance is added back
        s = self.paar(riester={"beitraege": 2000, "zulage_sonderausgaben": 175, "zulage_hinzurechnung": 1000})
        self.assertEqual(s.werte["riester"], 0)                     # 608 € < 1,000 €: the allowance stays
        self.assertTrue(any(h.startswith("Riester") for h in s.hebel))

    def test_second_person_is_required(self):
        with self.assertRaises(ValueError):
            Rechner({"jahr": 2023, "veranlagung": "zusammen"})
        s = self.paar(person_b={"vorsorge": {}})
        self.assertTrue(any("(Person B)" in f for f in s.fehlt))

    def test_splitting_soli_and_reasonable_burden_double(self):
        r = regeln(2023)
        self.assertEqual(tarif_veranlagung(D("54201"), r, True), 2 * tarif(D("27100"), r))
        self.assertEqual(soli(D("35086"), r, True), 0)              # 2 × 17,543
        self.assertEqual(soli(D("35086"), r), D("1929.73"))         # single: min(5.5 % = 1,929.73, 11.9 % of 17,543 = 2,087.62)
        # 15,340 × 4 % + 24,660 × 5 % = 613.60 + 1,233
        self.assertEqual(zumutbare_belastung(D("40000"), r, True), D("1846.60"))


class Arbeitswege(unittest.TestCase):
    def test_groups_by_means_of_transport_each_rounded_up(self):
        ag = {"von": dt.date(2023, 1, 1), "bis": dt.date(2023, 12, 31)}
        e = Rechner(minimal(jahr=2023, arbeit=[
            {**ag, "arbeitgeber": "X", "km": 13, "buero_tage": 37},                               # 144.30 -> 145
            {**ag, "arbeitgeber": "Y", "km": 27, "buero_tage": 23, "verkehrsmittel": "sonstige"},  # 199.18 -> 200
        ])).rechnen()
        self.assertEqual(e.werte["entfernungspauschale_brutto"], 345)   # not 344 from the sum

    def test_without_a_car_capped_at_4500(self):
        ag = {"arbeitgeber": "X", "von": dt.date(2023, 1, 1), "bis": dt.date(2023, 12, 31),
              "km": 100, "buero_tage": 220, "verkehrsmittel": "sonstige"}               # 220 × 36.40 = 8,008
        self.assertEqual(Rechner(minimal(jahr=2023, arbeit=[ag])).rechnen().werte["entfernungspauschale_brutto"], 4500)

    def test_meal_allowances(self):
        wk = {"reisekosten": [{"bezeichnung": "Hotel", "betrag": 89.50}],
              "verpflegung": {"tage_8h": 1, "an_abreise": 2, "tage_24h": 2, "kuerzung": 14}}
        # 90 + (1 + 2) × 14 + 2 × 28 − 14 = 90 + 84
        self.assertEqual(Rechner(minimal(jahr=2023, werbungskosten=wk)).rechnen().werte["reisekosten"], 174)

    def test_hardship_allowance(self):
        r = regeln(2025)
        self.assertEqual([haerteausgleich(D(x), r) for x in (0, 300, 410, 500, 820, 2000)], [0, 300, 410, 320, 0, 0])


class Steuerjahre(unittest.TestCase):
    def test_every_year_complete_and_self_contained(self):
        alle = alle_jahre(str(STANDARD))
        schluessel = {j: set(v) for j, v in alle.items()}
        erstes = next(iter(schluessel.values()))
        for j, k in schluessel.items():
            self.assertEqual(k, erstes, f"{j}: different keys {k ^ erstes}")
            self.assertNotIn("erbt_von", k)

    def test_gwg_limit_from_net_and_vat(self):
        self.assertEqual(regeln(2025).gwg_grenze_brutto, D("952.00"))

    def test_other_rules_file_by_environment(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "jahre.yaml"
            p.write_text("2099: {grundfreibetrag: 1}\n", encoding="utf-8")
            alt = os.environ.get("PYTAXDE_STEUERJAHRE")
            os.environ["PYTAXDE_STEUERJAHRE"] = str(p)
            try:
                self.assertEqual(regeln(2099).grundfreibetrag, 1)
            finally:
                if alt is None:
                    del os.environ["PYTAXDE_STEUERJAHRE"]
                else:
                    os.environ["PYTAXDE_STEUERJAHRE"] = alt


if __name__ == "__main__":
    unittest.main()
