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
figure to the euro. Modelled since, and checked against a family's notices 2018 to 2024: children (allowances
against Kindergeld, § 31; childcare costs), wage replacement benefits (Progressionsvorbehalt, § 32b), church tax
(as Sonderausgabe and assessed, also for one spouse of a joint assessment), the separate assessment of spouses
halved on request (§ 26a (2)), and capital income taxed at source within the saver's allowance.
"""
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP
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
    eigen: dict = field(default_factory=dict)        # own Sonderausgaben etc. before halving with a spouse (§ 26a)


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
    "lohnersatz": ("s", "progressionsvorbehalt"),                       # § 32b, both persons, after § 32b (2)
    "sonstige_einkuenfte": ("s", "sonstige"),
    "einkuenfte_vermietung": ("s", "vermietung"),                      # both persons together
    "gesamtbetrag_der_einkuenfte": ("s", "gde"),
    "altersvorsorge_summe": ("s", "altersvorsorge_summe"),
    "altersvorsorge": ("s", "altersvorsorge"),
    "kuerzung_krankengeld": ("s", "kv_kuerzung"),
    "kranken_pflege_basis": ("s", "kv_pv_basis"),
    "beschraenkt_abziehbare_sonderausgaben": ("s", "beschraenkt"),
    "vorsorge_eigen": ("s", "vorsorge_eigen"),                          # § 26a halved: own before halving ...
    "vorsorge_haelfte": ("s", "vorsorge_haelfte"),                      # ... its half ...
    "vorsorge_ehegatte": ("s", "vorsorge_ehegatte"),                    # ... and half of the spouse's
    "spenden": ("e", "spenden"),
    "gezahlte_kirchensteuer": ("e", "kirchensteuer_gezahlt"),
    "erstattete_kirchensteuer": ("e", "kirchensteuer_erstattet"),
    "kinderbetreuungskosten": ("s", "kinderbetreuung"),                 # the deductible share
    "unbeschraenkt_abziehbare_sonderausgaben": ("s", "unbeschraenkt"),
    "aussergewoehnliche_belastungen": ("e", "aussergewoehnliche_belastungen"),
    "zumutbare_belastung": ("e", "zumutbare_belastung"),
    "abziehbar_nach_33": ("s", "agb"),
    "erstattungsueberhang_kirchensteuer": ("s", "erstattungsueberhang_kirchensteuer"),
    "altersvorsorgebeitraege": ("s", "riester"),                       # § 10a: contributions plus allowance
    "einkommen": ("s", "einkommen"),
    "haerteausgleich": ("s", "haerteausgleich"),                       # § 46 (3) and (5)
    "freibetraege_kinder": ("s", "freibetraege_kinder"),               # deducted, where better than Kindergeld
    "zu_versteuerndes_einkommen": ("s", "zve"),
    "progressionssatz": ("s", "progressionssatz"),                     # in per cent, four decimals
    "tarifliche_einkommensteuer": ("s", "tarif"),
    "ermaessigung_haushaltsnahe_dienstleistungen": ("s", "erm_dienstleistungen"),
    "ermaessigung_handwerker": ("s", "erm_handwerker"),
    "ermaessigung_35a": ("s", "ermaessigung_35a"),                     # both together (after halving)
    "altersvorsorgezulage": ("s", "zulage_hinzurechnung"),
    "kindergeld": ("s", "kindergeld_hinzurechnung"),                   # added where the allowances were deducted
    "festgesetzte_einkommensteuer": ("s", "festgesetzt"),
    "freibetraege_kinder_soli": ("s", "freibetraege_kinder_alle"),     # the base of Soli and church tax ...
    "zve_soli": ("s", "zve_kinderfreibetraege"),
    "bemessungsgrundlage_soli": ("s", "bemessungsgrundlage_soli"),     # ... the tax on it
    "solidaritaetszuschlag": ("s", "soli"),
    "kirchensteuer_bemessungsgrundlage": ("s", "kirchensteuer_bemessung"),
    "kirchensteuer": ("s", "kirchensteuer"),
    "abzug_vom_lohn": ("s", "lohnsteuer"),
    "soli_abzug": ("s", "soli_abzug"),
    "kirchensteuer_abzug": ("s", "kirchensteuer_abzug"),
    "kapitalertragsteuer_abzug": ("s", "kapitalertragsteuer"),
    "erstattung_einkommensteuer": ("s", "erstattung_einkommensteuer"),  # the income tax column alone
    "erstattung": ("s", "erstattung"),                                 # all columns: income tax, Soli, church tax
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


def steuer(zve, pv, r, zusammen=False):
    """The tax on the taxable income; with wage replacement benefits `pv` at the special rate of § 32b EStG:
    the tariff on zvE + benefits over that sum, cut after four decimals of the per cent (as the notices print it,
    e.g. "mit 12,3456 %"), times the zvE, rounded down. Returns (tax, rate or None)."""
    if not pv:
        return tarif_veranlagung(zve, r, zusammen), None
    basis = euro_ab(dec(zve) + pv)
    if basis <= 0 or zve <= 0:
        return D("0"), D("0")
    satz = (tarif_veranlagung(basis, r, zusammen) / basis).quantize(D("0.000001"), rounding=ROUND_DOWN)
    return euro_ab(dec(zve) * satz), satz


def prozent4(x) -> str:
    return f"{x * 100:.4f}".replace(".", ",") + " %"


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


def simuliere(daten: dict, e, r, ehegatte=None) -> Simulation:
    """`ehegatte`: the spouse's own figures (Rechner.ehegatte) for a separate assessment halved on request."""
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
        # a notice that states the reduction itself (`kv_kuerzung`, older notices show none) is taken as it is
        kuerzung = sum((sv["kv_kuerzung"] if "kv_kuerzung" in sv else
                        euro_ab((euro_auf(sv.get("kv_an", 0)) - (erst if i == 0 else 0) - euro_ab(sv.get("zuschuss_kv", 0)))
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

        # --- unbeschränkt abziehbare Sonderausgaben: donations, church tax paid less refunded (§ 10 (1) no. 4),
        # childcare (§ 10 (1) no. 5) -- together at least the Sonderausgaben-Pauschbetrag; a church-tax refund above
        # the payments is added to the income instead (§ 10 (4b) s. 3). Then the extraordinary burdens.
        spenden = min(w.get("spenden", D("0")), euro_ab(gde * r.spenden_hoechstsatz))
        kist_gez = w.get("kirchensteuer_gezahlt")
        kist_erst = w.get("kirchensteuer_erstattet", D("0"))
        kist_sa = max(kist_gez - kist_erst, D("0")) if kist_gez is not None else D("0")
        ueberhang = max(kist_erst - kist_gez, D("0")) if kist_gez is not None else D("0")
        kbk = w.get("kinderbetreuung", D("0"))
        unbeschraenkt_summe = spenden + kist_sa + kbk
        agb = w.get("krankheitskosten_wirksam", D("0"))
        erm = euro_auf(w.get("35a_dienstleistungen_ermaessigung", 0)) + euro_auf(w.get("35a_handwerker_ermaessigung", 0))
        s.eigen = {"beschraenkt": beschraenkt, "unbeschraenkt_summe": unbeschraenkt_summe, "agb": agb,
                   "ermaessigung_35a": erm}
        if ehegatte is not None:
            # Einzelveranlagung von Ehegatten, halved on request (§ 26a (2) s. 2): each spouse gets half of both
            # spouses' Sonderausgaben, extraordinary burdens and § 35a reductions (as a pair of 2023 notices shows:
            # "abziehbare Vorsorgeaufwendungen aufgrund der hälftigen Aufteilung" plus "... von Ihrem Ehegatten")
            def haelfte(x):
                return euro_ab(dec(x) / 2)
            s.werte.update(vorsorge_eigen=beschraenkt, vorsorge_haelfte=haelfte(beschraenkt),
                           vorsorge_ehegatte=haelfte(ehegatte["beschraenkt"]))
            beschraenkt = haelfte(beschraenkt) + haelfte(ehegatte["beschraenkt"])
            # the own half at least the flat rate, plus half of the spouse's: a 2023 notice gives a spouse without
            # Sonderausgaben of his own the flat rate of 36 € AND half of the other's childcare costs
            sa = max(haelfte(unbeschraenkt_summe), r.sonderausgaben_pauschbetrag) + haelfte(ehegatte["unbeschraenkt_summe"])
            unbeschraenkt_summe = haelfte(unbeschraenkt_summe) + haelfte(ehegatte["unbeschraenkt_summe"])
            agb = haelfte(agb) + haelfte(ehegatte["agb"])
            erm = haelfte(erm) + haelfte(ehegatte["ermaessigung_35a"])
            s.schritte.append(("Vorsorgeaufwendungen nach hälftiger Aufteilung (eigene und Ehegatte je zur Hälfte)", -beschraenkt))
        else:
            sa = max(unbeschraenkt_summe, r.sonderausgaben_pauschbetrag * f)
        neu = kist_gez is not None or kbk or ehegatte is not None
        if not neu:
            s.schritte += [("Spenden" + (" (Sonderausgaben-Pauschbetrag)" if sa > spenden else ""), -sa)]
        else:
            teile = [n for n, x in (("Spenden", spenden), ("Kirchensteuer", kist_sa), ("Kinderbetreuung", kbk)) if x]
            s.schritte += [("unbeschränkt abziehbare Sonderausgaben" + (f" ({', '.join(teile)})" if teile else "")
                            + (" (Sonderausgaben-Pauschbetrag)" if sa > unbeschraenkt_summe else ""), -sa)]
        if agb:
            s.schritte.append(("außergewöhnliche Belastungen", -agb))
        if ueberhang:
            s.schritte.append(("hinzu Erstattungsüberhang aus Kirchensteuern", ueberhang))
        vor_riester = gde - beschraenkt - sa - agb + ueberhang

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

        # --- § 32b: wage replacement benefits, less what is left of the employee allowance (§ 32b (2) no. 1 a)
        pv = D("0")
        for label, sfx, bl, abzug, n in ek.personen:
            leistung = w.get("lohnersatz" + sfx)
            if leistung:
                rest = max(pausch - bl, D("0")) if euro_auf(w.get("werbungskosten" + sfx, 0)) <= pausch else D("0")
                pv += leistung - min(rest, leistung)

        # --- children (§ 31): a child's allowances are deducted only where they save more tax than its Kindergeld,
        # which is then added to the tax; checked child by child
        basis_zve = einkommen - ha
        fb_abzug, kg_hinzu, fb_alle = D("0"), D("0"), D("0")
        for k in e.kinder:
            fb_alle += k["freibetrag"]
            if not k["freibetrag"]:
                continue
            ohne, _ = steuer(basis_zve - fb_abzug, pv, r, zusammen)
            mit, _ = steuer(basis_zve - fb_abzug - k["freibetrag"], pv, r, zusammen)
            if ohne - mit > k["kindergeld"]:
                fb_abzug += k["freibetrag"]
                kg_hinzu += k["kindergeld"]
                s.hebel.append(f"Kind {k['name']}: Freibeträge {fmt(k['freibetrag'])} € sparen {fmt(ohne - mit)} € Steuer, "
                               f"mehr als das Kindergeld {fmt(k['kindergeld'])} € – Freibeträge abgezogen, Kindergeld hinzugerechnet")
            else:
                s.hebel.append(f"Kind {k['name']}: Kindergeld {fmt(k['kindergeld'])} € ist günstiger als die Freibeträge "
                               f"(Ersparnis {fmt(ohne - mit)} €)")
        zve = basis_zve - fb_abzug
        if riester or ha or e.kinder:
            s.schritte.append(("Einkommen", einkommen))
        if ha:
            s.schritte.append(("ab Härteausgleich § 46 Abs. 3 EStG", -ha))
        if fb_abzug:
            s.schritte.append(("ab Freibeträge für Kinder", -fb_abzug))
        s.schritte.append(("zu versteuerndes Einkommen", zve))

        # --- Steuer
        t, satz = steuer(zve, pv, r, zusammen)
        fest = max(t - min(erm, t), D("0")) + zulage + kg_hinzu
        # the solidarity surcharge and church tax are assessed on the tax as if all children's allowances were
        # deducted, without Kindergeld (§ 3 (2) SolZG, § 51a (2) EStG)
        if e.kinder:
            zve_kfb = basis_zve - fb_alle
            t_kfb, _ = steuer(zve_kfb, pv, r, zusammen)
            bemessung = max(t_kfb - min(erm, t_kfb), D("0")) + zulage
        else:
            bemessung = fest
        sz = soli(bemessung, r, zusammen)
        # wage tax withheld: the sum of the certificates rounded up -- a 2021 notice credits 18,585 for 8,209.83 +
        # 10,374.27; a 2020 notice (another couple) credits one euro less than the certificates each rounded up
        lst = euro_auf(sum((dec(x.get("lohnsteuer", 0)) for x in lstb), D("0")))
        soli_lst = sum((dec(x.get("soli", 0)) for x in lstb), D("0"))
        erstattung = lst + soli_lst - fest - sz

        # --- church tax: a rate of the assessment base; where only one spouse of a joint assessment belongs to a
        # church, of that spouse's share of it, split in the ratio of the basic tariff on each one's Summe der
        # Einkünfte, cut to the cent (met to the cent by a 2021 notice: "auf die Ehefrau entfallen")
        ki = daten.get("kirchensteuer") or {}
        if ki:
            person = str(ki.get("person", "beide")).upper()
            if person not in ("A", "B", "BEIDE"):
                raise ValueError(f"kirchensteuer.person {person!r}, erlaubt: A, B, beide")
            kist_basis = bemessung
            if zusammen and person != "BEIDE":
                eink = {"A": w.get("vermietung", D("0")) + so, "B": w.get("vermietung_b", D("0"))}
                for label, sfx, bl, abzug, n in ek.personen:
                    eink["B" if sfx else "A"] += n
                ta, tb = tarif(eink["A"], r), tarif(eink["B"], r)
                kist_basis = (bemessung * (ta if person == "A" else tb) / (ta + tb)).quantize(D("0.01"), rounding=ROUND_DOWN) \
                    if ta + tb else D("0")
            kist = (kist_basis * dec(ki.get("satz", "0.09"))).quantize(D("0.01"), rounding=ROUND_DOWN)
            kist_abzug = sum((dec(x.get("kirchensteuer", 0)) for x in lstb), D("0"))
            erstattung += kist_abzug - kist

        # --- capital income taxed at source (§ 32d): within the saver's allowance the withheld tax comes back
        kap = daten.get("kapitalertraege") or {}
        if kap:
            pflichtig = max(euro_ab(dec(kap.get("ertraege", 0))) - r.sparer_pauschbetrag * f, D("0"))
            kapest = (pflichtig * D("0.25")).quantize(D("0.01"), rounding=ROUND_DOWN)
            kapsoli = (kapest * r.soli["satz"]).quantize(D("0.01"), rounding=ROUND_DOWN)
            kap_einb, kap_soli = dec(kap.get("kapitalertragsteuer", 0)), dec(kap.get("soli", 0))
            erstattung += kap_einb - kapest + kap_soli - kapsoli

        grenz = grenzsteuersatz(zve, r, zusammen)
        s.schritte += [("tarifliche Einkommensteuer" + (" (Splittingtarif)" if zusammen else "")
                        + (f" mit Progressionsvorbehalt {prozent4(satz)}" if satz is not None else ""), t),
                       ("ab § 35a-Ermäßigungen", -min(erm, t))]
        if zulage:
            s.schritte.append(("dazu Altersvorsorgezulage", zulage))
        if kg_hinzu:
            s.schritte.append(("dazu Kindergeld", kg_hinzu))
        s.schritte += [("festzusetzende Einkommensteuer", fest), ("Solidaritätszuschlag", sz)]
        if ki:
            s.schritte.append((f"Kirchensteuer {dec(ki.get('satz', '0.09')) * 100:.0f} % von {fmt(kist_basis)} €", kist))
        s.schritte.append(("Lohnsteuer und Soli bereits abgezogen", lst + soli_lst))
        if ki:
            s.schritte.append(("Kirchensteuer bereits abgezogen", kist_abzug))
        if kap:
            s.schritte.append(("Kapitalertragsteuer und Soli darauf, bereits abgezogen", kap_einb + kap_soli))
        s.schritte.append(("Erstattung (+) / Nachzahlung (−)", erstattung))
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
        if neu:
            s.werte.update(unbeschraenkt_summe=unbeschraenkt_summe, kinderbetreuung=kbk, spenden=spenden)
        if kist_gez is not None:
            s.werte.update(kirchensteuer_sonderausgaben=kist_sa, erstattungsueberhang_kirchensteuer=ueberhang)
        if pv:
            s.werte.update(progressionsvorbehalt=pv, progressionssatz=satz * 100)
        if e.kinder:
            s.werte.update(freibetraege_kinder=fb_abzug, kindergeld_hinzurechnung=kg_hinzu, freibetraege_kinder_alle=fb_alle,
                           zve_kinderfreibetraege=zve_kfb, bemessungsgrundlage_soli=bemessung, agb=agb)
        elif ehegatte is not None:
            s.werte["agb"] = agb
        if ki:
            s.werte.update(kirchensteuer_bemessung=kist_basis, kirchensteuer=kist, kirchensteuer_abzug=kist_abzug,
                           erstattung_einkommensteuer=lst - fest)
        if kap:
            s.werte.update(kapitalertragsteuer=kap_einb, kapitalertragsteuer_festgesetzt=kapest,
                           erstattung_einkommensteuer=lst - fest + kap_einb - kapest)

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
        elif schl in b and not s.fehlt:
            # stated but not computed for this return (no children, no church tax, ...): said, not silently skipped
            e.hinweise.append(f"bescheid: {schl} wird für diese Erklärung nicht berechnet und nicht verglichen")

    if "zumutbare_belastung" in w:
        zb = w["zumutbare_belastung"]
        k = next((a.summe for a in e.abschnitte if a.titel.startswith("Außergewöhnliche")), D("0"))
        if k < zb:
            s.hebel.append(f"Krankheitskosten {fmt(k)} € liegen unter der zumutbaren Belastung {fmt(zb)} €: "
                           f"sie wirken erst ab {fmt(zb - k)} € mehr (Brille, Zahnarzt, Medikamente mit Rezept, Fahrten zum Arzt).")
    return s
