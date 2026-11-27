# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Working days in Berlin (five-day week, Berlin's public holidays), to check office and home-office days.

Only Berlin so far: the holidays differ by federal state.
"""
import datetime as dt

# One-off additional public holidays in Berlin: 75th and 80th anniversary of the liberation
EINMALIG = {2020: [dt.date(2020, 5, 8)], 2025: [dt.date(2025, 5, 8)]}


def ostersonntag(jahr: int) -> dt.date:
    """Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = jahr % 19, jahr // 100, jahr % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 -- the algorithm's own name
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(jahr, monat, tag)


def feiertage_berlin(jahr: int) -> dict:
    o = ostersonntag(jahr)
    t = {
        dt.date(jahr, 1, 1): "Neujahr",
        o - dt.timedelta(days=2): "Karfreitag",
        o + dt.timedelta(days=1): "Ostermontag",
        dt.date(jahr, 5, 1): "Tag der Arbeit",
        o + dt.timedelta(days=39): "Christi Himmelfahrt",
        o + dt.timedelta(days=50): "Pfingstmontag",
        dt.date(jahr, 10, 3): "Tag der Deutschen Einheit",
        dt.date(jahr, 12, 25): "1. Weihnachtsfeiertag",
        dt.date(jahr, 12, 26): "2. Weihnachtsfeiertag",
    }
    if jahr >= 2019:
        t[dt.date(jahr, 3, 8)] = "Internationaler Frauentag"
    for d in EINMALIG.get(jahr, []):
        t[d] = "Tag der Befreiung"
    return t


def arbeitstage(von: dt.date, bis: dt.date) -> int:
    """Monday to Friday without Berlin's public holidays, both ends included."""
    frei = {}
    for j in range(von.year, bis.year + 1):
        frei.update(feiertage_berlin(j))
    n, d = 0, von
    while d <= bis:
        if d.weekday() < 5 and d not in frei:
            n += 1
        d += dt.timedelta(days=1)
    return n


# ------------------------------------------------------------------ a calendar per calendar week
KALENDER_ZEICHEN = {
    "A": "Arbeit an der Tätigkeitsstätte (Büro)",
    "H": "Homeoffice",
    "U": "Urlaub",
    "K": "krank",
    "F": "frei (Wochenende, Feiertag, nicht beschäftigt)",
}


def aus_kalender(kalender: dict, von: dt.date, bis: dt.date):
    """Counts and hints from a calendar per ISO calendar week of the year of `von`:

        kalender: {1: [F, A, A, H, H, F, F], 2: [...], ...}      Monday to Sunday, one letter per day

    A office, H home office, U leave, K sick, F free. Days before `von` or after `bis` are ignored, so a
    week that starts in the previous year or after leaving the job is written as it is. Leave and sick
    days count on working days only. Returns ({"A": n, "H": n, "U": n, "K": n}, hints)."""
    jahr = von.year
    frei = {}
    for j in range(von.year, bis.year + 1):
        frei.update(feiertage_berlin(j))
    zaehler = {z: 0 for z in "AHUK"}
    hinweise, gesehen = [], set()
    for kw, tage in sorted(kalender.items(), key=lambda x: int(x[0])):
        kw = int(kw)
        tage = [str(t).strip().upper() for t in (tage.split() if isinstance(tage, str) else tage)]
        if len(tage) != 7:
            raise ValueError(f"kalender KW {kw}: {len(tage)} Tage, erwartet 7 (Montag bis Sonntag)")
        for i, z in enumerate(tage):
            if z not in KALENDER_ZEICHEN:
                raise ValueError(f"kalender KW {kw}: Zeichen {z!r}, erlaubt: {', '.join(KALENDER_ZEICHEN)}")
            try:
                tag = dt.date.fromisocalendar(jahr, kw, i + 1)
            except ValueError:
                raise ValueError(f"kalender: KW {kw} gibt es {jahr} nicht") from None
            if tag < von or tag > bis:
                continue
            gesehen.add(tag)
            arbeitstag = tag.weekday() < 5 and tag not in frei
            if z in "AH":
                zaehler[z] += 1
                if not arbeitstag:
                    hinweise.append(f"kalender {tag:%d.%m.%Y}: {KALENDER_ZEICHEN[z]} an einem "
                                    f"{'Feiertag (' + frei[tag] + ')' if tag in frei else 'Wochenende'}")
            elif z in "UK" and arbeitstag:
                zaehler[z] += 1
            elif z == "F" and arbeitstag:
                hinweise.append(f"kalender {tag:%d.%m.%Y}: Arbeitstag als frei markiert")
    fehlen, d = [], von
    while d <= bis:
        if d.weekday() < 5 and d not in frei and d not in gesehen:
            fehlen.append(d)
        d += dt.timedelta(days=1)
    if fehlen:
        wochen = sorted({x.isocalendar()[1] for x in fehlen})
        hinweise.append(f"kalender: {len(fehlen)} Arbeitstage ohne Eintrag (KW {', '.join(map(str, wochen[:12]))}"
                        f"{' …' if len(wochen) > 12 else ''})")
    return zaehler, hinweise
