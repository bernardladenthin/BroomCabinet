#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The three fictitious returns in example/, end to end: python examples_test.py

Their amounts were drawn at random. The expected figures (and the `bescheid` block of the two 2025
examples) were worked out by hand from the rules, with plain arithmetic and without this library;
the simulation has to arrive at exactly the same numbers. A real 2025 assessment notice was matched
the same way, to the euro -- that test stays with its owner, because its numbers are personal.
"""
import contextlib
import io
import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

import pytaxde
from taxde import rechne
from taxde import gesamt
from taxde.ergebnis import als_dict, als_json, lesen, unterschiede

BEISPIELE = Path(__file__).resolve().parent / "example"


def eintrag(e, formular, feld_anfang):
    treffer = [x for x in e.eintraege if x.formular == formular and x.feld.startswith(feld_anfang)]
    assert len(treffer) == 1, (formular, feld_anfang, treffer)
    return treffer[0]


class Jobwechsel2025(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = rechne(BEISPIELE / "beispiel-2025-jobwechsel.yaml")

    def test_items_as_entered_in_elster(self):
        for schluessel, erwartet in [
            ("entfernungspauschale_brutto", "738"),      # 60 × (20 × 0.30 + 13 × 0.38) + 30 × 9 × 0.30 = 737.40, up
            ("entfernungspauschale", "726"),             # minus 12 € tax-free from the employer
            ("homeoffice", "594.00"),                    # (80 + 19) × 6 €
            ("arbeitsmittel", "352"),                    # 287 + 65 (half of 129.90, rounded up)
            ("fortbildung", "268"),                      # 221 + 47
            ("weitere", "295"),                          # 95 + 43 + 16 + 105 + 36
            ("werbungskosten", "2235"),
            ("sonstige_einkuenfte", "1191"),             # 1,459 − 208 − 60
            ("spenden", "426"),                          # 12 × 27 + 102
            ("35a_dienstleistungen_ermaessigung", "54.20"),
            ("35a_handwerker_ermaessigung", "109.20"),
            ("berufsunfaehigkeit", "519"),               # 12 × 43.21 = 518.52
            ("zumutbare_belastung", "3259"),             # 767 + 2,147.40 + 4,923 × 7 % = 3,259.01, whole euros down
            ("krankheitskosten_wirksam", "0"),
        ]:
            with self.subTest(schluessel):
                self.assertEqual(self.e.werte[schluessel], D(erwartet))

    def test_working_days_per_employer(self):
        self.assertEqual(self.e.werte["nicht_buero_tage_Beispiel GmbH"], 107)        # 80 + 22 + 5
        self.assertEqual(eintrag(self.e, "Anlage N", "Muster AG: einfache Entfernung").wert, 9)
        self.assertEqual(eintrag(self.e, "Anlage N", "Beispiel GmbH: Arbeitstage").zeile, 29)

    def test_telecom_with_a_changing_monthly_amount(self):
        weitere = next(a for a in self.e.abschnitte if a.titel == "Anlage N: Weitere Werbungskosten")
        mobil = next(b for b in weitere.posten if b.bezeichnung.startswith("Mobilfunk"))
        self.assertEqual((mobil.exakt, mobil.eintrag), (D("42.55"), D("43")))      # 6 × 3.246 + 6 × 3.846

    def test_simulation_meets_the_hand_calculation(self):
        s = self.e.simulation
        self.assertEqual(s.fehlt, [])
        self.assertTrue(s.abgleich)
        for name, bescheid, simuliert in s.abgleich:
            with self.subTest(name):
                self.assertEqual(simuliert, bescheid)
        self.assertEqual(s.werte["erstattung"], D("-1319.00"))       # a back payment
        self.assertEqual(s.werte["kv_pv_basis"], D("6010"))          # 4,882 − 193 + 1,371 − 50: own contributions up

    def test_levers(self):
        hebel = " ".join(self.e.simulation.hebel)
        self.assertIn("Sonstige Vorsorge wirkt nicht", hebel)
        self.assertIn("zumutbaren Belastung", hebel)
        self.assertIn("Soli: festzusetzende ESt", hebel)

    def test_nothing_open(self):
        self.assertEqual((self.e.offen, self.e.hinweise), ([], []))


class HohesEinkommen2025(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = rechne(BEISPIELE / "beispiel-2025-hohes-einkommen.yaml")

    def test_simulation_meets_the_hand_calculation(self):
        for name, bescheid, simuliert in self.e.simulation.abgleich:
            with self.subTest(name):
                self.assertEqual(simuliert, bescheid)
        self.assertEqual(len(self.e.simulation.abgleich), 11)

    def test_below_the_employee_allowance(self):
        self.assertEqual(self.e.werte["werbungskosten"], D("968"))                 # 94 (93.60 up) + 858 + 16
        self.assertTrue(any(h.startswith("Werbungskosten 968,00 € liegen unter") for h in self.e.simulation.hebel))

    def test_other_income_below_the_exemption_limit_counts_nothing(self):
        self.assertEqual(self.e.werte["sonstige_einkuenfte"], 76)
        self.assertEqual(self.e.simulation.werte["gde"], D("96700"))

    def test_medical_costs_above_the_reasonable_burden(self):
        self.assertEqual(self.e.werte["zumutbare_belastung"], D("6104"))           # on 96,700, not on 96,776; 6,104.30 down
        self.assertEqual(self.e.werte["krankheitskosten_wirksam"], D("1070"))      # 7,174 − 6,104

    def test_solidarity_surcharge_in_the_phase_in_zone(self):
        # min(22,063 × 5.5 % = 1,213.46, (22,063 − 19,950) × 11.9 % = 251.447) -> 251.44
        self.assertEqual(self.e.simulation.werte["soli"], D("251.44"))


class LaufendesJahr2026(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = rechne(BEISPIELE / "beispiel-2026-laufendes-jahr.yaml")

    def test_open_items_are_reported_not_counted(self):
        offen = " | ".join(self.e.offen)
        for teil in ("Dezember noch nicht erfasst", "Schreibtisch", "Monitor", "Hochwasserhilfe", "Badsanierung"):
            with self.subTest(teil):
                self.assertIn(teil, offen)
        self.assertEqual(self.e.werte["arbeitsmittel"], 36)          # the mouse only
        self.assertEqual(self.e.werte["spenden"], 180)

    def test_2026_commuting_allowance(self):
        self.assertEqual(self.e.werte["entfernungspauschale"], D("1034"))          # 68 × 40 × 0.38 = 1,033.60, up

    def test_simulation_on_an_estimate(self):
        w = self.e.simulation.werte
        self.assertEqual((w["gde"], w["zve"], w["tarif"], w["erstattung"]),
                         (D("57970"), D("45938"), D("9150"), D("1572")))
        self.assertFalse(any("Höchstbetrag Altersvorsorge fehlt" in h for h in self.e.simulation.hebel))   # 30,826 € in 2026

    def test_without_income_the_simulation_says_what_is_missing(self):
        from taxde import Rechner
        from taxde.rechner import laden
        daten = laden(BEISPIELE / "beispiel-2026-laufendes-jahr.yaml")
        daten["lohnsteuerbescheinigungen"][0]["brutto"] = None
        del daten["vorsorge"]
        s = Rechner(daten).rechnen().simulation
        self.assertEqual(len(s.fehlt), 2)
        self.assertEqual(s.schritte, [])
        self.assertTrue(any(h.startswith("Homeoffice") for h in s.hebel))   # the levers that need no income


class Kommandozeile(unittest.TestCase):
    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pytaxde.main(list(argv))
        return code, out.getvalue()

    def test_every_example_prints(self):
        for datei in sorted(BEISPIELE.glob("*.yaml")):
            with self.subTest(datei.name):
                code, text = self.run_main(str(datei), "--details")
                self.assertIn(code, (None, 0))
                self.assertIn("# ELSTER-Einträge", text)
                self.assertIn("# Rechenweg", text)

    def test_receipts(self):
        code, text = self.run_main(str(BEISPIELE / "beispiel-2025-jobwechsel.yaml"), "--belege")
        self.assertEqual((code, text.strip()), (0, "0 Belege, 0 nicht gefunden, 0 Dateinamen nur im Kommentar"))

    def test_self_test_of_every_example(self):
        """The built-in self-test: each example meets its block in Steuererklärungen.json (and its notice)."""
        for datei in sorted(BEISPIELE.glob("*.yaml")):
            with self.subTest(datei.name):
                code, text = self.run_main(str(datei), "--pruefen")
                self.assertEqual(code, 0, text)
                self.assertIn("gleich wie in Steuererklärungen.json", text)

    def test_self_test_of_the_folder(self):
        code, text = self.run_main(str(BEISPIELE), "--pruefen")
        self.assertEqual(code, 0, text)
        self.assertIn("(3 Steuererklärungen)", text)
        self.assertIn("beispiel-2025-jobwechsel.yaml: Bescheid 17 von 17 getroffen · gleich", text)
        code, text = self.run_main(str(BEISPIELE), "--pruefen", "--jahr", "2026")
        self.assertEqual((code, text.count("yaml:")), (0, 1))

    def test_self_test_shows_what_changed(self):
        quelle = (BEISPIELE / "beispiel-2025-jobwechsel.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as d:
            kopie = Path(d) / "kopie.yaml"
            kopie.write_text(quelle, encoding="utf-8")
            self.assertEqual(self.run_main(str(kopie), "--pruefen")[0], 2)          # not stored yet
            code, text = self.run_main(str(kopie), "--json")
            self.assertEqual(code, 0)
            self.assertIn("Steuererklärungen.json: neu angelegt", text)
            self.assertTrue((Path(d) / "Steuererklärungen.json").exists())
            self.assertEqual(self.run_main(str(kopie), "--pruefen")[0], 0)

            # one more donation of 100 € and a new open item
            geaendert = quelle.replace('{bezeichnung: "Einzelspende Katastrophenhilfe", betrag: 101.57}',
                                       '{bezeichnung: "Einzelspende Katastrophenhilfe", betrag: 201.57}\n'
                                       '  - {bezeichnung: "Neue Spende", offen: true}')
            self.assertNotEqual(geaendert, quelle)
            kopie.write_text(geaendert, encoding="utf-8")
            code, text = self.run_main(str(kopie), "--pruefen")
            self.assertEqual(code, 1)
            self.assertIn("geändert  werte › spenden: 426 → 526", text)
            self.assertIn("geändert  simulation › werte › zve: 44306 → 44206", text)
            self.assertIn("neu       offen › Sonderausgaben: Spenden und Mitgliedsbeiträge: Neue Spende", text)
            self.assertIn("geändert  posten › Sonderausgaben: Spenden und Mitgliedsbeiträge › "
                          "posten › Einzelspende Katastrophenhilfe › eintrag: 102 → 202", text)
            self.assertIn("Bescheid 12 von 17 getroffen", text)                # moved: Sonderausgaben, zvE, tax, refund

            code, text = self.run_main(str(kopie), "--json")
            self.assertIn("Unterschiede übernommen", text)
            self.assertEqual(self.run_main(str(kopie), "--pruefen")[0], 1)     # the notice still differs

    def test_accepting_one_year_leaves_the_others(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("beispiel-2025-jobwechsel.yaml", "beispiel-2026-laufendes-jahr.yaml"):
                (Path(d) / name).write_text((BEISPIELE / name).read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(self.run_main(d, "--json")[0], 0)
            j25 = Path(d) / "beispiel-2025-jobwechsel.yaml"
            j25.write_text(j25.read_text(encoding="utf-8").replace("betrag: 101.57", "betrag: 201.57"), encoding="utf-8")
            self.assertEqual(self.run_main(d, "--pruefen", "--jahr", "2026")[0], 0)
            self.run_main(d, "--json", "--jahr", "2026")                         # 2025 is not accepted with it
            code, text = self.run_main(d, "--pruefen")
            self.assertEqual(code, 1)
            self.assertIn("beispiel-2025-jobwechsel.yaml: Bescheid 12 von 17 getroffen · 22 Unterschiede", text)
            self.run_main(d, "--json", "--jahr", "2025")
            code, text = self.run_main(d, "--pruefen", "--jahr", "2025")
            self.assertEqual(code, 1)                                           # its notice still differs
            self.assertIn("gleich wie in Steuererklärungen.json", text)

    def test_a_broken_return_does_not_hide_the_others(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "gut.yaml").write_text((BEISPIELE / "beispiel-2026-laufendes-jahr.yaml").read_text(encoding="utf-8"),
                                              encoding="utf-8")
            (Path(d) / "kaputt.yaml").write_text("jahr: 2025\nveranlagung: getrennt\n", encoding="utf-8")
            self.run_main(d, "--json")
            code, text = self.run_main(d, "--pruefen")
            self.assertEqual(code, 1)
            self.assertIn("kaputt.yaml: FEHLER ValueError", text)
            self.assertIn("gut.yaml: gleich", text)


class Gesamt(unittest.TestCase):
    """Steuererklärungen.json: the self-test's snapshot and the viewer's data."""

    @classmethod
    def setUpClass(cls):
        cls.d = gesamt.bauen(BEISPIELE)

    def punkte(self, cid):
        c = next(c for c in self.d["uebergreifend"]["cluster"] if c["id"] == cid)
        return {(Path(p["quelle"]).stem, p["person"]): p for p in c["punkte"]}

    def test_every_return_has_its_block(self):
        self.assertEqual(sorted(self.d["erklaerungen"]), sorted(p.name for p in BEISPIELE.glob("*.yaml")))
        b = self.d["erklaerungen"]["beispiel-2025-jobwechsel.yaml"]
        self.assertEqual(set(b), {"geprueft", "anzeige"})
        self.assertEqual(b["geprueft"]["posten"]["Sonderausgaben: Spenden und Mitgliedsbeiträge"]["summe"], 426)

    def test_clusters_against_the_caps_of_the_year(self):
        wk = self.punkte("werbungskosten")[("beispiel-2025-jobwechsel", "A")]
        self.assertEqual((wk["wert"], wk["grenze"], wk["teile"]["fahrt"]), (2235, 1230, 726))
        av = self.punkte("altersvorsorge")[("beispiel-2025-jobwechsel", "")]
        self.assertEqual((av["wert"], av["grenze"]), (10621, 29344))          # 5,311 + 5,310 against the 2025 cap
        sp = self.punkte("spenden")[("beispiel-2025-jobwechsel", "")]
        self.assertEqual(sp["grenze"], 11210)                                  # 20 % of 56,053
        ho = self.punkte("homeoffice")[("beispiel-2025-jobwechsel", "A")]
        self.assertEqual((ho["wert"], ho["grenze"]), (594, 1260))
        fahrt = self.punkte("fahrt")[("beispiel-2025-jobwechsel", "A")]
        self.assertEqual((fahrt["grenze"], fahrt["gilt"]), (4500, False))     # cap shown, but by car it does not bind

    def test_time_series_and_sums(self):
        u = self.d["uebergreifend"]
        self.assertEqual([z["jahr"] for z in u["zeitreihe"]], [2025, 2025, 2026])
        self.assertEqual(u["summen"]["erstattung"], D("-1319") + D("2859.25") + D("1572"))

    def test_the_stored_file_is_current(self):
        self.assertEqual(lesen(als_json(self.d)), gesamt.lesen_datei(BEISPIELE))


class Anzeige(unittest.TestCase):
    """The viewer's server: only the viewer, the data and the receipts' files, by number."""

    def test_serves_viewer_data_and_named_files_only(self):
        import threading
        import urllib.error
        import urllib.request

        from taxde import anzeige
        s = anzeige.server(BEISPIELE)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        basis = f"http://127.0.0.1:{s.server_address[1]}/"

        def hole(pfad):
            try:
                with urllib.request.urlopen(basis + pfad) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, b""
        try:
            code, html = hole("")
            self.assertEqual(code, 200)
            self.assertIn("<title>Steuererklärungen</title>".encode("utf-8"), html)
            code, daten = hole("daten.json")
            d = json.loads(daten)
            self.assertEqual(len(d["erklaerungen"]), 3)
            erster = sorted(d["links"].items())[0]
            self.assertEqual(hole(erster[1])[0], 200)                          # a YAML of the folder
            for pfad in ("datei/999", "datei/..%2Fpytaxde.py", "pytaxde.py", "taxde/viewer.html"):
                with self.subTest(pfad):
                    self.assertEqual(hole(pfad)[0], 404)
        finally:
            s.shutdown()
            s.server_close()

    def test_viewer_is_one_file_without_anything_from_outside(self):
        html = (Path(gesamt.__file__).with_name("viewer.html")).read_text(encoding="utf-8")
        self.assertNotRegex(html, r"(?i)(src|href)\s*=\s*[\"']https?:")      # works offline, loads nothing else


class ErgebnisJson(unittest.TestCase):
    def test_round_trip_and_numbers(self):
        e = rechne(BEISPIELE / "beispiel-2025-jobwechsel.yaml")
        d = lesen(als_json(als_dict(e, "x.yaml")))
        self.assertEqual(d["werte"]["entfernungspauschale"], D("726"))
        self.assertEqual(d["simulation"]["abgleich"]["erstattung"], {"bescheid": D("-1319"), "simuliert": D("-1319")})
        self.assertEqual(d["elster"]["Anlage N"]["Weitere Werbungskosten"]["zeile"], 62)
        self.assertNotIn("hebel", d["simulation"])                           # prose, not compared

    def test_differences(self):
        alt = {"quelle": "a.yaml", "werte": {"x": D("690.00"), "weg": 1}, "offen": ["A", "B"]}
        neu = {"quelle": "b.yaml", "werte": {"x": D("690"), "dazu": 2}, "offen": ["B", "C"]}
        self.assertEqual(unterschiede(alt, neu), [
            ("entfällt", ("werte", "weg"), 1, None),
            ("entfällt", ("offen", "A"), "A", None),
            ("neu", ("werte", "dazu"), None, 2),
            ("neu", ("offen", "C"), None, "C"),
        ])
        self.assertEqual(unterschiede(alt, alt), [])

    def test_where_the_file_lives(self):
        with tempfile.TemporaryDirectory() as d:
            jahr = Path(d) / "2025 Steuererklärung"
            jahr.mkdir()
            self.assertEqual(gesamt.finde_gesamt(jahr / "Steuererklärung 2025.yaml"), Path(d).resolve())
            self.assertEqual(gesamt.finde_gesamt(Path(d) / "x.yaml"), Path(d).resolve())


if __name__ == "__main__":
    unittest.main()
