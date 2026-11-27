# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Simulates the tax office's calculation, step by step as an assessment notice (Bescheid) shows it,
and lists levers: allowances not used yet, and what a further euro would be worth.

Order as in a notice: income -> Gesamtbetrag der Einkünfte -> Sonderausgaben with a cap
(insurance) -> without cap (donations) -> extraordinary burdens -> Riester (§ 10a) -> Einkommen ->
hardship allowance (§ 46 (3)) -> zvE (taxable income) -> tariff, split for a joint assessment ->
§ 35a -> Riester allowance added back -> assessed income tax -> solidarity surcharge -> compared
with the wage tax withheld. Checked against real notices for 2017 to 2020, 2021 to 2023 (joint), 2024 and 2025, every
figure to the euro. Not modelled: church tax, Progressionsvorbehalt, children.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP
from decimal import Decimal as D

from .posten import dec, entfernungspauschale, euro_ab, euro_auf, fmt


def prozent(x) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


@dataclass
class Simulation:
    werte: dict = field(default_factory=dict)
    schritte: list = field(default_factory=list)     # (text, amount)
    hebel: list = field(default_factory=list)        # texts
    fehlt: list = field(default_factory=list)
    abgleich: list = field(default_factory=list)     # (figure, per notice, simulated)


# The figures of the tax office's calculation ("Berechnung des Finanzamts", as ELSTER shows it with the
# notice) that a `bescheid:` block may state, in the notice's order: key -> (s = simulation, e = return, key).
# Every one stated is compared; the more of the notice is copied in, the more the self-test checks.
BESCHEID_FELDER = {
    "bruttoarbeitslohn": ("s", "bruttoarbeitslohn"),
    "entfernungspauschale": ("e", "entfernungspauschale_brutto"),     # before the employer's tax-free travel allowance
    "arbeitsmittel": ("e", "arbeitsmittel"),
    "homeoffice_tagespauschale": ("e", "homeoffice"),
    "fortbildungskosten": ("e", "fortbildung"),
    "reisekosten": ("e", "reisekosten"),
    "weitere_werbungskosten": ("e", "weitere"),
    "werbungskosten": ("s", "werbungskosten_abzug"),                   # or the employee allowance, if higher
    "einkuenfte_nichtselbstaendige_arbeit": ("s", "einkuenfte_n"),
    # the second person of a joint assessment
    "bruttoarbeitslohn_b": ("s", "bruttoarbeitslohn_b"),
    "entfernungspauschale_b": ("e", "entfernungspauschale_brutto_b"),
    "arbeitsmittel_b": ("e", "arbeitsmittel_b"),
    "homeoffice_tagespauschale_b": ("e", "homeoffice_b"),
    "fortbildungskosten_b": ("e", "fortbildung_b"),
    "reisekosten_b": ("e", "reisekosten_b"),
    "weitere_werbungskosten_b": ("e", "weitere_b"),
    "werbungskosten_b": ("s", "werbungskosten_abzug_b"),
    "einkuenfte_nichtselbstaendige_arbeit_b": ("s", "einkuenfte_n_b"),
    "sonstige_einkuenfte": ("s", "sonstige"),
    "einkuenfte_vermietung": ("s", "vermietung"),                      # both persons together
    "gesamtbetrag_der_einkuenfte": ("s", "gde"),
    "altersvorsorge_summe": ("s", "altersvorsorge_summe"),
    "altersvorsorge": ("s", "altersvorsorge"),
    "kuerzung_krankengeld": ("s", "kv_kuerzung"),
    "kranken_pflege_basis": ("s", "kv_pv_basis"),
    "beschraenkt_abziehbare_sonderausgaben": ("s", "beschraenkt"),
    "unbeschraenkt_abziehbare_sonderausgaben": ("s", "unbeschraenkt"),
    "altersvorsorgebeitraege": ("s", "riester"),                       # § 10a: contributions plus allowance
    "einkommen": ("s", "einkommen"),
    "haerteausgleich": ("s", "haerteausgleich"),                       # § 46 (3) and (5)
    "zu_versteuerndes_einkommen": ("s", "zve"),
    "tarifliche_einkommensteuer": ("s", "tarif"),
    "ermaessigung_haushaltsnahe_dienstleistungen": ("s", "erm_dienstleistungen"),
    "ermaessigung_handwerker": ("s", "erm_handwerker"),
    "altersvorsorgezulage": ("s", "zulage_hinzurechnung"),
    "festgesetzte_einkommensteuer": ("s", "festgesetzt"),
    "solidaritaetszuschlag": ("s", "soli"),
    "abzug_vom_lohn": ("s", "lohnsteuer"),
    "erstattung": ("s", "erstattung"),
}


def euro_rund(x):
    return dec(x).quantize(D("1"), rounding=ROUND_HALF_UP)


def tarif(zve, r) -> D:
    """Income tax by the § 32a EStG tariff zones of the year (whole euros, rounded down)."""
    x = euro_ab(max(dec(zve), D("0")))
    for zone in r.tarif:
        if zone["bis"] is None or x <= zone["bis"]:
            art = zone["art"]
            if art is None:
                return D("0")
            if art == "quadratisch":
                t = (x - zone["von"]) / D("10000")
                return euro_ab((zone["a"] * t + zone["b"]) * t + zone["c"])
            if art == "linear":
                return euro_ab(zone["satz"] * x - zone["abzug"])
            raise ValueError(f"Tarifzone mit unbekannter Art {art!r}")
    raise ValueError("Tarif hat keine offene letzte Zone")


def tarif_veranlagung(zve, r, zusammen=False) -> D:
    """§ 32a (5) EStG: a joint assessment pays twice the tax on half the income (splitting)."""
    if not zusammen:
        return tarif(zve, r)
    return 2 * tarif(euro_ab(dec(zve) / 2), r)


def soli(est, r, zusammen=False) -> D:
    s = r.soli
    frei = s["freigrenze"] * (2 if zusammen else 1)
    if est <= frei:
        return D("0.00")
    return min(est * s["satz"], (est - frei) * s["milderung"]).quantize(D("0.01"), rounding="ROUND_DOWN")


def grenzsteuersatz(zve, r, zusammen=False) -> D:
    return (tarif_veranlagung(zve + 1000, r, zusammen) - tarif_veranlagung(zve, r, zusammen)) / D("1000")


@dataclass
class Einkuenfte:
    personen: list = field(default_factory=list)      # (label, sfx, gross wage, expenses deducted, income)
    sonstige: D = D("0")
    vermietung: D = D("0")
    gde: D = D("0")
    fehlt: list = field(default_factory=list)


def einkuenfte(daten: dict, w: dict, r) -> Einkuenfte:
    """Gesamtbetrag der Einkünfte the way the notice forms it, one or two persons."""
    ek = Einkuenfte()
    personen = [("", "", daten)]
    if daten.get("veranlagung") == "zusammen":
        personen.append((" (Person B)", "_b", daten.get("person_b") or {}))
    for label, sfx, d in personen:
        lstb = d.get("lohnsteuerbescheinigungen") or []
        brutto = [x.get("brutto") for x in lstb]
        if not lstb or any(b is None for b in brutto):
            ek.fehlt.append("Bruttoarbeitslohn" + label + " (Lohnsteuerbescheinigung oder Schätzung)")
            continue
        bl = euro_ab(sum((dec(b) for b in brutto), D("0")))
        abzug = max(euro_auf(w.get("werbungskosten" + sfx, D("0"))), r.arbeitnehmer_pauschbetrag)
        ek.personen.append((label, sfx, bl, abzug, bl - abzug))
    so = w.get("sonstige_einkuenfte", D("0"))
    ek.sonstige = D("0") if so < r.so_freigrenze_leistungen else so      # below the Freigrenze, or a loss: 0
    ek.vermietung = w.get("vermietung", D("0")) + w.get("vermietung_b", D("0"))
    ek.gde = sum((n for *_, n in ek.personen), D("0")) + ek.sonstige + ek.vermietung
    return ek


def haerteausgleich(neben, r) -> D:
    """§ 46 (3) EStG and § 70 EStDV: other income of an employee up to 410 € is left untaxed, and the
    relief tapers off until 820 €."""
    if neben <= 0:
        return D("0")
    if neben <= r.haerteausgleich_grenze:
        return neben
    return max(r.haerteausgleich_obergrenze - neben, D("0"))


def simuliere(daten: dict, e, r) -> Simulation:
    s = Simulation()
    w = e.werte
    zusammen = daten.get("veranlagung") == "zusammen"
    f = 2 if zusammen else 1                       # caps and allowances that double for a couple
    personen = [daten] + ([daten.get("person_b") or {}] if zusammen else [])
    lstb = [x for d in personen for x in (d.get("lohnsteuerbescheinigungen") or [])]
    v = daten.get("vorsorge") or {}
    svs = [{k: dec(x) for k, x in ((d.get("vorsorge") or {}).get("lohnsteuerbescheinigung") or {}).items()}
           for d in personen]
    ek = einkuenfte(daten, w, r)
    s.fehlt += ek.fehlt
    for i, sv in enumerate(svs):
        fehlende_sv = [k for k in ("rv_an", "rv_ag", "kv_an", "pv_an") if k not in sv]
        if fehlende_sv:
            s.fehlt.append("Sozialversicherung aus der Lohnsteuerbescheinigung" + (" (Person B)" if i else "")
                           + ": " + ", ".join(fehlende_sv))

    wk = euro_auf(w["werbungskosten"])
    pausch = r.arbeitnehmer_pauschbetrag
    grenz = None
    if not s.fehlt:
        # --- Einkünfte und Gesamtbetrag der Einkünfte
        for label, sfx, bl, abzug, n in ek.personen:
            s.schritte += [("Bruttoarbeitslohn" + label, bl),
                           ("ab Werbungskosten" + (" (Pauschbetrag)" if abzug == pausch and pausch > euro_auf(w.get("werbungskosten" + sfx, 0)) else "") + label, -abzug),
                           ("Einkünfte nichtselbständige Arbeit" + label, n)]
            s.werte.update({"bruttoarbeitslohn" + sfx: bl, "werbungskosten_abzug" + sfx: abzug, "einkuenfte_n" + sfx: n})
        so, gde = ek.sonstige, ek.gde
        s.schritte.append(("Sonstige Einkünfte", so))
        if "vermietung" in w:
            s.schritte.append(("Einkünfte aus Vermietung und Verpachtung", ek.vermietung))
            s.werte["vermietung"] = ek.vermietung
        s.schritte.append(("Gesamtbetrag der Einkünfte", gde))

        # --- Vorsorgeaufwendungen (beschränkt abziehbar)
        # Whole euros the way the notice forms them (seen in a 2024 notice with cents on the certificate):
        # own contributions up (KV 10,122.36 -> 10,123), the employer's share, tax-free subsidies and
        # refunds down (5,061.24 -> 5,061) -- each rounding in the taxpayer's favour, per person.
        def summe(schluessel, runden):
            return sum((runden(sv.get(schluessel, 0)) for sv in svs), D("0"))
        rv_an, rv_ag = summe("rv_an", euro_auf), summe("rv_ag", euro_ab)
        kv_an, pv_an = summe("kv_an", euro_auf), summe("pv_an", euro_auf)
        zkv, zpv = summe("zuschuss_kv", euro_ab), summe("zuschuss_pv", euro_ab)
        av_summe = rv_an + rv_ag
        hb = r.altersvorsorge_hoechstbetrag
        # the deductible share (94 % in 2022) rounded up: 21,226 × 0.94 = 19,952.44 -> 19,953 (a 2022 notice)
        av = euro_auf((min(av_summe, hb * f) if hb is not None else av_summe) * r.altersvorsorge_quote) - rv_ag
        if hb is None:
            s.hebel.append("Höchstbetrag Altersvorsorge fehlt in der steuerjahre-Datei; ohne Deckel gerechnet")
        erst = euro_ab(v.get("erstattete_beitraege", 0))
        # the reduction for sick pay per person, each rounded down: a 2022 notice has 186 + 150 = 336,
        # where 4 % of the couple's 8,442 would be 337 (2023: 195 + 161 = 356)
        kuerzung = sum((euro_ab((euro_auf(sv.get("kv_an", 0)) - (erst if i == 0 else 0) - euro_ab(sv.get("zuschuss_kv", 0)))
                               * r.kv_kuerzung_krankengeld) for i, sv in enumerate(svs)), D("0"))
        basis = kv_an - kuerzung + pv_an - erst - zkv - zpv
        weitere = summe("av_an", euro_auf) + sum(w.get(k, D("0")) for k in
                                                ("kv_ueber_basis", "wahlleistungen", "berufsunfaehigkeit", "unfall_haftpflicht_risiko"))
        sonst_hb = r.sonstige_vorsorge_hoechstbetrag * f
        sonstige = max(basis, min(basis + weitere, sonst_hb))
        beschraenkt = av + sonstige
        s.schritte += [("Altersvorsorge (RV AN + AG − AG-Anteil)", av),
                       (f"Kranken-/Pflegeversicherung Basis (Kürzung Krankengeld {fmt(kuerzung)} €)", basis),
                       ("weitere sonstige Vorsorge (wirksam)", sonstige - basis),
                       ("Summe beschränkt abziehbare Sonderausgaben", -beschraenkt)]

        # --- Spenden (unbeschränkt) und außergewöhnliche Belastungen
        spenden = min(w.get("spenden", D("0")), euro_ab(gde * r.spenden_hoechstsatz))
        sa = max(spenden, r.sonderausgaben_pauschbetrag * f)
        agb = w.get("krankheitskosten_wirksam", D("0"))
        s.schritte += [("Spenden" + (" (Sonderausgaben-Pauschbetrag)" if sa > spenden else ""), -sa)]
        if agb:
            s.schritte.append(("außergewöhnliche Belastungen", -agb))
        vor_riester = gde - beschraenkt - sa - agb

        # --- Riester (§ 10a): deducted only where the tax saving beats the allowance, which is then
        # added back to the tax (Günstigerprüfung). Contributions plus allowance, capped per person.
        ha = haerteausgleich(so + ek.vermietung, r)
        ri = daten.get("riester") or {}
        riester, zulage = D("0"), D("0")
        if ri:
            moeglich = min(dec(ri.get("beitraege", 0)) + dec(ri.get("zulage_sonderausgaben", 0)),
                           r.riester_hoechstbetrag * len(personen))
            zulage = dec(ri.get("zulage_hinzurechnung", 0))
            ersparnis = (tarif_veranlagung(euro_ab(vor_riester) - ha, r, zusammen)
                         - tarif_veranlagung(euro_ab(vor_riester - moeglich) - ha, r, zusammen))
            if ersparnis > zulage:
                riester = moeglich
                s.schritte.append(("Altersvorsorgebeiträge (Riester) mit Zulage", -riester))
            else:
                zulage = D("0")
                s.hebel.append(f"Riester: Sonderausgabenabzug ({fmt(ersparnis)} € Ersparnis) lohnt nicht gegen die Zulage")
        einkommen = euro_ab(vor_riester - riester)
        zve = einkommen - ha
        if riester or ha:
            s.schritte.append(("Einkommen", einkommen))
        if ha:
            s.schritte.append(("ab Härteausgleich § 46 Abs. 3 EStG", -ha))
        s.schritte.append(("zu versteuerndes Einkommen", zve))

        # --- Steuer
        t = tarif_veranlagung(zve, r, zusammen)
        erm = euro_auf(w.get("35a_dienstleistungen_ermaessigung", 0)) + euro_auf(w.get("35a_handwerker_ermaessigung", 0))
        fest = max(t - min(erm, t), D("0")) + zulage
        sz = soli(fest, r, zusammen)
        # wage tax withheld, each certificate rounded up: a 2021 notice credits 8,210 + 10,375 = 18,585
        # for 8,209.83 and 10,374.27, where the rounded sum would be 18,584
        lst = sum((euro_auf(x.get("lohnsteuer", 0)) for x in lstb), D("0"))
        soli_lst = sum((dec(x.get("soli", 0)) for x in lstb), D("0"))
        erstattung = lst + soli_lst - fest - sz
        grenz = grenzsteuersatz(zve, r, zusammen)
        s.schritte += [("tarifliche Einkommensteuer" + (" (Splittingtarif)" if zusammen else ""), t),
                       ("ab § 35a-Ermäßigungen", -min(erm, t))]
        if zulage:
            s.schritte.append(("dazu Altersvorsorgezulage", zulage))
        s.schritte += [("festzusetzende Einkommensteuer", fest), ("Solidaritätszuschlag", sz),
                       ("Lohnsteuer und Soli bereits abgezogen", lst + soli_lst),
                       ("Erstattung (+) / Nachzahlung (−)", erstattung)]
        s.werte.update(sonstige=so,
                       gde=gde, altersvorsorge_summe=av_summe, altersvorsorge=av, kv_kuerzung=kuerzung,
                       kv_pv_basis=basis, beschraenkt=beschraenkt, unbeschraenkt=sa, einkommen=einkommen, zve=zve, tarif=t,
                       erm_dienstleistungen=euro_auf(w.get("35a_dienstleistungen_ermaessigung", 0)),
                       erm_handwerker=euro_auf(w.get("35a_handwerker_ermaessigung", 0)),
                       ermaessigung_35a=erm, festgesetzt=fest, soli=sz, lohnsteuer=lst, soli_abzug=soli_lst,
                       erstattung=erstattung, grenzsteuersatz=grenz, sonstige_unwirksam=basis + weitere - sonstige)
        if ri:
            s.werte.update(riester=riester, zulage_hinzurechnung=zulage)
        if ha:
            s.werte["haerteausgleich"] = ha

        # --- Hebel, die das Einkommen brauchen
        if basis >= sonst_hb and weitere:
            s.hebel.append(f"Sonstige Vorsorge wirkt nicht: {fmt(weitere)} € (Arbeitslosenversicherung, Zeilen 22, 27, 45, 46) "
                           f"bleiben ohne Wirkung, weil Kranken-/Pflegeversicherung ({fmt(basis)} €) den Höchstbetrag "
                           f"von {fmt(sonst_hb)} € schon ausschöpft. Eintragen schadet nicht.")
        if hb is not None and av_summe < hb * f:
            platz = hb * f - av_summe
            s.hebel.append(f"Altersvorsorge: bis {fmt(platz)} € zusätzliche Beiträge zur Basisrente (Rürup) wären abziehbar; "
                           f"Wirkung je 1.000 € etwa {fmt(grenz * 1000)} € (Grenzsteuersatz {prozent(grenz)}).")
        s.hebel.append(f"Grenzsteuersatz {prozent(grenz)} (ohne Soli): jeder weitere Euro Werbungskosten oder Spende spart etwa "
                       f"{grenz * 100:.0f} Cent.")
        if fest <= r.soli["freigrenze"] * f:
            s.hebel.append(f"Soli: festzusetzende ESt {fmt(fest)} € liegt unter der Freigrenze {fmt(r.soli['freigrenze'] * f)} €.")

    # --- Hebel ohne Einkommen
    if wk < pausch:
        s.hebel.append(f"Werbungskosten {fmt(wk)} € liegen unter dem Arbeitnehmer-Pauschbetrag {fmt(pausch)} €: "
                       f"erst ab {fmt(pausch - wk)} € mehr wirkt jeder weitere Euro.")
    # no home-office allowance before 2020: the year's rules carry 0 € and 0 days, and there is no lever
    ho_tage = w.get("homeoffice", D("0")) / r.homeoffice_je_tag if r.homeoffice_je_tag else D("0")
    arbeit = daten.get("arbeit") or []
    if arbeit and ho_tage < r.homeoffice_max_tage:
        rest = r.homeoffice_max_tage - int(ho_tage)
        km = int(arbeit[-1]["km"])
        ep_tag = entfernungspauschale(1, km, r)
        s.hebel.append(f"Homeoffice: {int(ho_tage)} von {r.homeoffice_max_tage} Tagen eingetragen, noch {rest} möglich. "
                       f"Jeder gearbeitete Tag zählt genau einmal: ein Bürotag bringt {fmt(ep_tag)} € Entfernungspauschale "
                       f"({km} km), ein Homeoffice-Tag {fmt(r.homeoffice_je_tag)} €. Wichtig ist, dass alle Tage erfasst sind.")
    for schl, satz, maxi, name in [("dienstleistungen", r.p35a_dienstleistung_satz, r.p35a_dienstleistung_max, "haushaltsnahe Dienstleistungen"),
                                   ("handwerker", r.p35a_handwerker_satz, r.p35a_handwerker_max, "Handwerker-Lohnkosten")]:
        rest = maxi / satz - w.get(f"35a_{schl}", D("0"))
        if rest > 0:
            s.hebel.append(f"§ 35a {name}: noch {fmt(rest)} € Aufwand mit {satz * 100:.0f} % Steuerermäßigung möglich "
                           f"(direkt von der Steuer, unabhängig vom Grenzsteuersatz).")
    # --- Abgleich mit dem Bescheid, falls vorhanden
    b = daten.get("bescheid") or {}
    for schl in b:
        if schl not in BESCHEID_FELDER and schl not in ("datum", "belege", "notiz"):
            e.hinweise.append(f"bescheid: unbekannter Schlüssel {schl!r}, wird nicht verglichen "
                              f"(erlaubt: {', '.join(BESCHEID_FELDER)})")
    for schl, (quelle, wert) in BESCHEID_FELDER.items():
        werte = s.werte if quelle == "s" else w
        if schl in b and wert in werte:
            # expenses of the return appear in the notice in whole euros, rounded up (1,267.64 -> 1,268)
            s.abgleich.append((schl.replace("_", " "), dec(b[schl]), werte[wert] if quelle == "s" else euro_auf(werte[wert])))

    if "zumutbare_belastung" in w:
        zb = w["zumutbare_belastung"]
        k = next((a.summe for a in e.abschnitte if a.titel.startswith("Außergewöhnliche")), D("0"))
        if k < zb:
            s.hebel.append(f"Krankheitskosten {fmt(k)} € liegen unter der zumutbaren Belastung {fmt(zb)} €: "
                           f"sie wirken erst ab {fmt(zb - k)} € mehr (Brille, Zahnarzt, Medikamente mit Rezept, Fahrten zum Arzt).")
    return s
