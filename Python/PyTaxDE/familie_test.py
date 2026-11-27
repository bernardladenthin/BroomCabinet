#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Children, wage replacement benefits, church tax, spouses assessed separately, capital income:
python familie_test.py

The rules behind these tests were met to the euro by a family's real notices 2018 to 2024 (joint and separate
assessments, Elterngeld, church tax for one spouse); the figures here are FICTITIOUS, each expected value worked
out by hand in the comment next to it.
"""
import datetime as dt
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from taxde import Rechner, zumutbare_belastung
from taxde.regeln import regeln

JAHR_2024 = {"von": dt.date(2024, 1, 1), "bis": dt.date(2024, 12, 31)}
OHNE_SV = {"lohnsteuerbescheinigung": {"rv_an": 0, "rv_ag": 0, "kv_an": 0, "pv_an": 0}}


def ledig_2024(brutto, lohnsteuer=0, **extra):
    """A single person in 2024 without insurance figures, so the arithmetic stays short."""
    d = {"jahr": 2024, "arbeit": [], "werbungskosten": {}, "vorsorge": OHNE_SV,
         "lohnsteuerbescheinigungen": [{"arbeitgeber": "X", **JAHR_2024, "brutto": brutto, "lohnsteuer": lohnsteuer}]}
    d.update(extra)
    return d


class Progressionsvorbehalt(unittest.TestCase):
    def test_the_special_rate(self):
        from taxde.simulation import steuer
        r = regeln(2024)
        # tariff(30,000 + 10,000) = 7,461; 7,461 / 40,000 = 0.186525 (18.6525 %); × 30,000 = 5,595.75 -> 5,595
        self.assertEqual(steuer(D("30000"), D("10000"), r), (D("5595"), D("0.186525")))
        self.assertEqual(steuer(D("30000"), D("0"), r)[1], None)                    # no benefits: the plain tariff
        self.assertEqual(steuer(D("0"), D("10000"), r)[0], 0)

    def test_benefits_less_the_unused_employee_allowance(self):
        # § 32b (2) no. 1 a: a wage of 600 € uses only 600 of the 1,230 € allowance; 630 come off the benefits
        d = ledig_2024(600, lohnersatz=[{"bezeichnung": "Elterngeld", "betrag": 9000}])
        s = Rechner(d).rechnen().simulation
        self.assertEqual(s.werte["progressionsvorbehalt"], 8370)
        self.assertEqual(s.werte["festgesetzt"], 0)
        self.assertTrue(any(x[0].startswith("tarifliche Einkommensteuer mit Progressionsvorbehalt") for x in s.schritte))


class Kinder(unittest.TestCase):
    def test_months_and_shares(self):
        # born in July: 6 of 12 months; half for a single assessment (9,540 / 2 × 6 / 12 = 2,385), Kindergeld
        # 6 × 250 / 2 = 750; the full share where stated
        e = Rechner(ledig_2024(30000, kinder=[{"name": "K", "geburt": dt.date(2024, 7, 15)}])).rechnen()
        self.assertEqual(e.kinder, [{"name": "K", "monate": 6, "freibetrag": 2385, "kindergeld": D("750.00")}])
        e = Rechner(ledig_2024(30000, kinder=[{"name": "K", "geburt": dt.date(2020, 1, 1), "freibetrag": "voll"}])).rechnen()
        self.assertEqual((e.kinder[0]["freibetrag"], e.kinder[0]["kindergeld"]), (9540, 3000))
        # `monate` overrides the count where a notice counted differently
        e = Rechner(ledig_2024(30000, kinder=[{"name": "K", "geburt": dt.date(2024, 10, 1), "monate": 12}])).rechnen()
        self.assertEqual(e.kinder[0]["freibetrag"], 4770)
        with self.assertRaisesRegex(ValueError, "freibetrag"):
            Rechner(ledig_2024(30000, kinder=[{"name": "K", "freibetrag": "drittel"}])).rechnen()

    def test_allowance_where_it_beats_the_kindergeld(self):
        # 101,230 − 1,230 − 36 flat rate = 99,964; half allowances 4,770 save tariff(99,964) − tariff(95,194)
        # = 31,348 − 29,345 = 2,003 > Kindergeld 1,500: deducted, and the Kindergeld added to the tax
        kind = [{"name": "K", "geburt": dt.date(2020, 1, 1)}]
        w = Rechner(ledig_2024(101230, kinder=kind)).rechnen().simulation.werte
        self.assertEqual((w["einkommen"], w["freibetraege_kinder"], w["zve"]), (99964, 4770, 95194))
        self.assertEqual((w["tarif"], w["kindergeld_hinzurechnung"], w["festgesetzt"]), (29345, 1500, 30845))
        self.assertEqual(w["bemessungsgrundlage_soli"], 29345)                      # Soli: without Kindergeld

    def test_kindergeld_where_it_is_better(self):
        # 21,230 − 1,230 − 36 = 19,964: the allowances would save 1,716 − 588 = 1,128 < 1,500 Kindergeld; the zvE
        # stays, but the base of Soli and church tax is the tax on 19,964 − 4,770 = 15,194
        w = Rechner(ledig_2024(21230, kinder=[{"name": "K"}])).rechnen().simulation.werte
        self.assertEqual((w["zve"], w["freibetraege_kinder"], w["kindergeld_hinzurechnung"]), (19964, 0, 0))
        self.assertEqual((w["zve_kinderfreibetraege"], w["bemessungsgrundlage_soli"]), (15194, 588))

    def test_childcare_costs(self):
        def abziehbar(jahr, kosten):
            d = ledig_2024(30000, jahr=jahr, kinder=[{"name": "K", "betreuungskosten": [{"bezeichnung": "Kita", "betrag": kosten}]}])
            return Rechner(d).rechnen().werte["kinderbetreuung"]
        self.assertEqual(abziehbar(2024, 1000.50), 667)       # 2/3 of the exact 1,000.50 = 667.00
        self.assertEqual(abziehbar(2024, 7200), 4000)         # 2/3 = 4,800, capped at 4,000
        self.assertEqual(abziehbar(2025, 7200), 4800)         # from 2025: 80 % = 5,760, capped at 4,800

    def test_reasonable_burden_with_children(self):
        r = regeln(2024)
        # one or two children: 15,340 × 2 % + 24,660 × 3 % = 306.80 + 739.80 = 1,046.60 -> 1,046
        self.assertEqual(zumutbare_belastung(D("40000"), r, False, 2), 1046)
        # three or more: 15,340 × 1 % + 24,660 × 1 % = 400
        self.assertEqual(zumutbare_belastung(D("40000"), r, True, 3), 400)


class Kirchensteuer(unittest.TestCase):
    def paar(self, **ki):
        jahr = {"von": dt.date(2023, 1, 1), "bis": dt.date(2023, 12, 31)}
        d = {"jahr": 2023, "veranlagung": "zusammen", "vorsorge": OHNE_SV, "kirchensteuer": {"satz": 0.09, **ki},
             "lohnsteuerbescheinigungen": [{"arbeitgeber": "X", **jahr, "brutto": 50000, "lohnsteuer": 9000}],
             "person_b": {"vorsorge": OHNE_SV, "lohnsteuerbescheinigungen": [
                 {"arbeitgeber": "Y", **jahr, "brutto": 20000, "lohnsteuer": 2000, "kirchensteuer": 100}]}}
        return Rechner(d).rechnen().simulation.werte

    def test_only_one_spouse_in_a_church(self):
        # Sonderausgabe: the 100 € withheld (above the flat rate of 72); zvE 48,770 + 18,770 − 100 = 67,440;
        # splitting 2 × tariff(33,720) = 11,638. Person B's share: tariff on each one's Summe der Einkünfte,
        # 10,890 (A) and 1,645 (B): 11,638 × 1,645 / 12,535 = 1,527.28; 9 % = 137.45
        w = self.paar(person="B")
        self.assertEqual((w["zve"], w["festgesetzt"]), (67440, 11638))
        self.assertEqual((w["kirchensteuer_bemessung"], w["kirchensteuer"]), (D("1527.28"), D("137.45")))
        # 11,000 − 11,638 income tax + 100 − 137.45 church tax
        self.assertEqual(w["erstattung"], D("-675.45"))
        self.assertEqual(self.paar(person="beide")["kirchensteuer"], D("1047.42"))    # 9 % of 11,638

    def test_a_refund_above_the_payments_is_added(self):
        # paid 100, refunded 260: no Sonderausgabe (the flat rate of 72 instead), 160 added to the income
        w = self.paar(person="B", erstattet=260)
        self.assertEqual((w["kirchensteuer_sonderausgaben"], w["unbeschraenkt"]), (0, 72))
        self.assertEqual((w["erstattungsueberhang_kirchensteuer"], w["zve"]), (160, 67628))   # 67,540 − 72 + 160


class EhegattenHaelftig(unittest.TestCase):
    @staticmethod
    def datei(brutto, rv, kita, anderer):
        kinder = f'[{{name: K, betreuungskosten: [{{bezeichnung: Kita, betrag: {kita}}}]}}]' if kita else "[]"
        return (f'jahr: 2024\nveranlagung: einzeln\nehegatte: {{aufteilung: haelftig, datei: "{anderer}"}}\n'
                f"lohnsteuerbescheinigungen: [{{arbeitgeber: X, von: 2024-01-01, bis: 2024-12-31, brutto: {brutto}, lohnsteuer: 0}}]\n"
                f"vorsorge: {{lohnsteuerbescheinigung: {{rv_an: {rv}, rv_ag: 0, kv_an: 0, pv_an: 0}}}}\n"
                f"kinder: {kinder}\n")

    def test_both_spouses_halved(self):
        # Two separate returns of 2024, halved on request (§ 26a (2) s. 2). Spouse A has pension contributions of 4,000,
        # childcare 1,500 (2/3 = 1,000); spouse B pension contributions of 3,000, nothing else. Each gets half of both.
        from taxde.rechner import rechne
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "a.yaml").write_text(self.datei(40000, 4000, 1500, "b.yaml"), encoding="utf-8")
            (Path(t) / "b.yaml").write_text(self.datei(30000, 3000, 0, "a.yaml"), encoding="utf-8")
            a, b = rechne(Path(t) / "a.yaml").simulation.werte, rechne(Path(t) / "b.yaml").simulation.werte
        # Vorsorge: 4,000 / 2 + 3,000 / 2 = 3,500 for both
        self.assertEqual((a["vorsorge_eigen"], a["vorsorge_haelfte"], a["vorsorge_ehegatte"], a["beschraenkt"]),
                         (4000, 2000, 1500, 3500))
        self.assertEqual(b["beschraenkt"], 3500)
        # Sonderausgaben: A keeps half of its 1,000 = 500; B, with none of its own, gets the flat rate 36 AND half of A's
        self.assertEqual((a["unbeschraenkt"], b["unbeschraenkt"]), (500, 536))

    def test_the_spouse_file_is_needed(self):
        with self.assertRaisesRegex(ValueError, "Pfad"):
            Rechner(ledig_2024(30000, veranlagung="einzeln", ehegatte={"aufteilung": "haelftig", "datei": "x.yaml"})).rechnen()


class Kapitalertraege(unittest.TestCase):
    def test_within_the_savers_allowance_the_withheld_tax_comes_back(self):
        kap = {"ertraege": 600, "kapitalertragsteuer": 150, "soli": 8.25}
        w = Rechner(ledig_2024(30000, kapitalertraege=kap)).rechnen().simulation.werte
        self.assertEqual((w["kapitalertragsteuer"], w["kapitalertragsteuer_festgesetzt"]), (150, 0))
        self.assertEqual(w["erstattung"] - (w["lohnsteuer"] - w["festgesetzt"]), D("158.25"))
        # above it: 1,600 − 1,000 = 600 × 25 % = 150 due, nothing back; Soli 5.5 % of 150 = 8.25
        kap = {"ertraege": 1600, "kapitalertragsteuer": 150, "soli": 8.25}
        w = Rechner(ledig_2024(30000, kapitalertraege=kap)).rechnen().simulation.werte
        self.assertEqual(w["erstattung"] - (w["lohnsteuer"] - w["festgesetzt"]), 0)


class BescheidFelder(unittest.TestCase):
    def test_older_notices_without_the_sick_pay_reduction(self):
        sv = {"lohnsteuerbescheinigung": {"rv_an": 0, "rv_ag": 0, "kv_an": 1000, "pv_an": 200, "kv_kuerzung": 0}}
        self.assertEqual(Rechner(ledig_2024(30000, vorsorge=sv)).rechnen().simulation.werte["kv_pv_basis"], 1200)

    def test_a_stated_figure_that_is_not_computed_is_reported(self):
        e = Rechner(ledig_2024(30000, bescheid={"kirchensteuer": 0})).rechnen()
        self.assertTrue(any("kirchensteuer wird für diese Erklärung nicht berechnet" in h for h in e.hinweise))

    def test_other_burdens_count_with_medical_costs(self):
        # 2024, no children: 15,340 × 5 % + 13,430 × 6 % = 767 + 805.80 = 1,572.80 -> 1,572 on 30,000 − 1,230;
        # 1,000 + 800 − 1,572 = 228
        d = ledig_2024(30000, krankheitskosten=[{"bezeichnung": "Zahnarzt", "betrag": 1000}],
                       sonstige_belastungen=[{"bezeichnung": "Kur", "betrag": 800}])
        w = Rechner(d).rechnen().werte
        self.assertEqual((w["aussergewoehnliche_belastungen"], w["zumutbare_belastung"], w["krankheitskosten_wirksam"]),
                         (1800, 1572, 228))


if __name__ == "__main__":
    unittest.main()
