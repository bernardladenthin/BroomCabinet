<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyTaxDE — a German income tax return as data, and the tax office's calculation replayed

A German employee's tax return is mostly bookkeeping: every receipt becomes a line in a form, and
next year nobody remembers how a number came about. Here each return is **one YAML file** — every
item with its calculation, its receipts and a comment on where it came from — and the library works
out what goes into which line of ELSTER. It then replays the tax office's calculation step by step,
the way an assessment notice (Bescheid) shows it, down to the refund or back payment. Checked
against nine real notices — 2017 to 2020, 2021 to 2023 (joint assessments), 2024 and 2025 — it met
every one of their 21, 21, 21, 20, 29, 31, 32, 20 and 24 figures to the euro.

During the year the same file answers the more useful question: **where is something left?** —
allowances not used yet, a cap already reached, what one more euro of expenses is worth.

| | |
|---|---|
| `pytaxde.py` | the command line |
| `taxde/steuerjahre.yaml` | **the rules per tax year**: tariff (§ 32a EStG), solidarity surcharge, VAT, flat rates, caps, form line numbers. No personal data; every year a complete block of its own |
| `taxde/rechner.py` | reads a return and computes the ELSTER entries: Anlage N (also business trips and meal allowances), Anlage SO, Anlage V, donations, § 35a, Vorsorgeaufwand, medical costs — for one person or a jointly assessed couple |
| `taxde/simulation.py` | the tax office's calculation (splitting tariff, Riester with its Günstigerprüfung, hardship allowance § 46), the comparison with a notice, and the levers |
| `taxde/ergebnis.py` | what a result holds and how two results differ: the core of the self-test |
| `taxde/gesamt.py` | all returns of a folder in one `Steuererklärungen.json`: the self-test's snapshot and the viewer's data |
| `taxde/viewer.html` | the viewer: one page, no library, opens a `Steuererklärungen.json` |
| `taxde/anzeige.py` | `--anzeigen`: serves the viewer on 127.0.0.1 with the data fresh from the YAML files and the receipts linked |
| `taxde/posten.py` | the forms an item can take (fixed, monthly, count × price, telecom 20 %, commute, ...) |
| `taxde/arbeitstage.py` | working days in Berlin, to check office and home-office days |
| `taxde/verweise.py` | `--verweise`: every link and every path of the Markdown note beside a return exists |
| `example/` | three **fictitious** returns with randomly drawn amounts, and their accepted result `Steuererklärungen.json` |
| `taxde_test.py` | the rules one by one, every expected figure worked out in a comment |
| `examples_test.py` | the three examples end to end, against a calculation by hand made without this library |
| `privacy_test.py` | refuses drive letters, home directories, e-mail addresses, tax numbers, tax IDs and IBANs in this project; given the folder of your real returns, also every word and number of them |

Needs PyYAML (`requirements.txt`); everything else is the standard library. `--help` and the tests'
imports work without it.

    python pytaxde.py "Steuererklärung 2025.yaml"              entries per form and line, simulation, levers
    python pytaxde.py "Steuererklärung 2025.yaml" --details    with the calculation of every item
    python pytaxde.py "Steuererklärung 2025.yaml" --belege     every receipt exists, and no file is named only in a comment
    python pytaxde.py "Steuererklärung 2025.yaml" --pruefen    self-test: exit status 0 same, 1 different, 2 not stored yet
    python pytaxde.py "Steuererklärung 2025.yaml" --json       accept its result into Steuererklärungen.json
    python pytaxde.py "Steuererklärung 2025.yaml" --verweise   its note (Steuererklärung 2025.md): every link and path exists

    python pytaxde.py example                                  a folder: one line per return
    python pytaxde.py example --pruefen [--jahr 2025]          the self-test of all returns, or of some years
    python pytaxde.py example --json [--jahr 2025]             write Steuererklärungen.json, or only those years' blocks
    python pytaxde.py example --verweise                       the notes (*.md) beside the returns: links and paths
    python pytaxde.py example --anzeigen                       the viewer in the browser

**German on purpose.** Keys, identifiers and output use the words of the forms (Werbungskosten,
Anlage N, Zeile 62), because that is what has to be found again in ELSTER. The documentation is
English.

## A return is a YAML file

```yaml
jahr: 2025
lohnsteuerbescheinigungen:
  - {arbeitgeber: Beispiel GmbH, von: 2025-01-01, bis: 2025-12-31, brutto: 41110.15, lohnsteuer: 5294.36}
arbeit:
  - {arbeitgeber: Beispiel GmbH, von: 2025-01-01, bis: 2025-12-31, km: 33,
     buero_tage: 60, homeoffice_tage: 80, urlaub: 22, krank: 5}
werbungskosten:
  arbeitsmittel:
    - {bezeichnung: "Drucker, beruflicher Anteil", betrag: 129.90, anteil: 0.5}
  weitere:
    - {bezeichnung: "Internet Festnetz", art: telekom, monatlich: 39.47, monate: 12}
    - bezeichnung: "Fachzeitschrift, Jahresabo"
      betrag: 89.40
      belege: ["Belege/Rechnung Fachzeitschrift.pdf"]   # relative to the YAML file (or belege_ordner:), * allowed
spenden:
  - {bezeichnung: "Tierschutzverein", monatlich: 27, monate: 12}
  - {bezeichnung: "Spende", offen: true, notiz: "Zuwendungsbestätigung fehlt"}
```

YAML and not JSON because of the comments: where a number came from — a receipt, a bank statement,
a note — is written right next to it, for a person and for an agent reading the file later. A *file*,
though, goes into a `belege:` list (anywhere in the file; a top-level `quellen: {belege: [...]}` holds
what belongs to the whole return), because there `--belege` checks that it exists. A file name that
appears only in a comment is reported, so a reference cannot quietly go stale.
`example/` shows every section; `taxde/posten.py` lists the forms of an item.

**Days at work: totals or a calendar.** An `arbeit` entry gives its days as totals (`buero_tage`,
`homeoffice_tage`, `urlaub`, `krank`), or as a `kalender` per ISO calendar week, Monday to Sunday,
from which the totals are counted -- for the commuting allowance (Anlage N lines 28/29) and the
home-office allowance alike:

```yaml
    kalender:          # A office, H home office, U leave, K sick, F free
      14: [H, A, A, A, F, F, F]     # 30.03.-05.04.2026, Good Friday on 03.04.
      15: [F, A, A, A, H, F, F]     # Easter Monday on 06.04.
      16: "H A A A H F F"           # a string works too
```

Days outside the entry's `von`/`bis` are ignored, so a week reaching into the previous year or past
the end of a job is written as it is, and each employer has its own calendar. A working day without
an entry, a working day marked free, or office or home office on a weekend or a Berlin public holiday
gives a hint. Leave and sickness count on working days only. An entry has either totals or a
calendar, not both.

**Paid studies (Anlage SO).** For a clinical study or a similar paid participation, a `studie`
block states the visits, and the expenses are computed from them: the trips by the
commuting-allowance tiers per way (there and back by default), parking tickets one by one or per
visit, and a flat amount of small expenses per visit. Further items go under `werbungskosten` as usual.

```yaml
sonstige_einkuenfte:
  - bezeichnung: "Probandenhonorar Studie X"
    einnahmen: 1200
    studie:
      termine: 12                 # the number of visits, or the list of their dates
      ort: Klinik
      km: 35                      # one way
      parken: [4.50, 6.00]        # or parken_je_termin: 5
      kleinausgaben_je_termin: 5
```

Such income (§ 22 Nr. 3 EStG) has a Freigrenze of 256 € a year: below it, all is tax-free; from it
on, all is taxed. A hint says when the result is below it or just above it (with the extra expenses
that would bring it below), and a loss is not set off against other income. The viewer shows the
income per year against that limit, split into the taxable part, trips, parking and small expenses.
The limit is counted for the return as a whole, not per spouse.

**Rules of the calculation.** Expenses are rounded up to whole euros per item, income down — as a
return filed by hand would be. The insurance figures of a wage tax certificate keep their cents in
the YAML; the simulation rounds them the way the notice does: own contributions up, the employer's
share, tax-free subsidies, refunds and the reduction for sick pay (per person) down, the deductible
share of pension contributions (84 % in 2017, 86 % in 2018, 88 % in 2019, 90 % in 2020, 92 % in 2021, 94 % in 2022) up, and the wage tax withheld up per
certificate. An item marked `offen: true` does not count; it is listed under
"Offen" with its note, so a return in progress shows what is missing. An item the tax office did not
recognise stays in the file as filed, marked `nicht_anerkannt: "reason"`: it does not count either, is
reported with its reason, and the simulation meets the notice. Work equipment above the limit
for immediate deduction (952 € gross) is open until its depreciation for the year is entered with
`afa: true`. Office days, home-office days, holidays and sick days are checked against the working
days of the period.

## The tax office's calculation, and the levers

With the wage tax certificate (`brutto`, `lohnsteuer`) and its insurance figures
(`vorsorge.lohnsteuerbescheinigung`) the simulation runs the notice's steps: Gesamtbetrag der
Einkünfte, capped and uncapped Sonderausgaben, extraordinary burdens, taxable income (zvE), tariff,
§ 35a, solidarity surcharge, and the difference to the wage tax withheld. During the year, an
estimate projected from a payslip is enough.

Once the notice is there, copy the figures of its calculation ("Berechnung des Finanzamts", the PDF
ELSTER shows with it) into a `bescheid:` block — up to 24 of them, from `bruttoarbeitslohn` through
`werbungskosten`, `kranken_pflege_basis` and `zu_versteuerndes_einkommen` to `erstattung`
(`BESCHEID_FELDER` in `taxde/simulation.py` lists them; a misspelt key is reported, not ignored).
Each one is compared on every run, so a mistake shows at the step where it happens, not only in
the refund.

The levers it reports, for example:

- **insurance without effect** — once health and care insurance exceed the 1,900 € cap, further
  insurance (unemployment, liability, disability) changes nothing;
- **room for a Rürup pension** below the cap, and what 1,000 € of it would save at the marginal rate;
- **the marginal rate** itself: what one more euro of expenses or donations is worth;
- **expenses below the employee allowance** of 1,230 €, and how much more it takes to matter;
- **home office versus office day**: which of the two a day is worth more as;
- **§ 35a** room for household services and craftsmen (a reduction of the tax itself);
- **medical costs below the reasonable burden**.

## The rules per year

`taxde/steuerjahre.yaml` holds one complete block per year, keyed by the year. **No inheritance**:
what rarely changes is repeated anyway, because "rarely" is not "never" (VAT changed in 2020). A new
year is the previous block copied and corrected; `taxde_test.py` refuses a year whose keys differ and
a tariff that jumps at a zone border, which is how a mistyped coefficient shows. Another file can
be used with the environment variable `PYTAXDE_STEUERJAHRE`.

2017 to 2025 are checked against real notices. 2026 is entered from the law but not checked yet,
its pension cap is still missing (the simulation says so), and its form line numbers are 2025's.

## The self-test: all results in one file

The YAML files are the truth. What the program computes from them goes into **one**
`Steuererklärungen.json` per folder (`taxde/gesamt.py`), a block per return, keyed by the YAML's path:
the folder's YAML files and those one level below, each with a `jahr:`. A block has two parts:

| | |
|---|---|
| `geprueft` | what the self-test compares: the ELSTER entries by form and field, the key figures, every step of the simulation, the comparison with the notice, every item with its amount and status, what is open |
| `anzeige` | what the viewer shows besides: the levers, the year's rules, the calculation of every item, the receipts with the files they name, the clusters below -- rewritten on every write, never compared |

From then on **every run compares** with the stored block and says `gleich`, or what is different, path
by path:

    beispiel-2025-jobwechsel.yaml: Bescheid 12 von 17 getroffen · 26 Unterschiede zu Steuererklärungen.json
      geändert  werte › spenden: 426 → 526
      neu       offen › Sonderausgaben: Spenden und Mitgliedsbeiträge: Neue Spende

That makes every return its own test. A change to a YAML shows exactly where it lands; a change to
this library shows at once whether it moved a number of a return already filed. For a filed year
together with its `bescheid:` block it is the strongest test there is: `--pruefen` exits 0 only when
the result is unchanged and every figure of the notice is met. `--jahr` checks or accepts some years
and leaves the others' blocks as they were; a return that cannot be computed shows its error and does
not hide the others. Levers and timestamps stay out of the compared part, so an unchanged result is an
unchanged file.

## The viewer: every year, every item, every cap

`taxde/viewer.html` is one page without any library or anything loaded from outside. It shows a
`Steuererklärungen.json`:

- **Überblick**: income, taxable income and tax over the years, the refund of every year, the average
  and the marginal tax rate;
- **Grenzen**: for every cluster -- Werbungskosten (stacked: commute, home office, work equipment,
  training, business trips, further), commute, home office, pension, other insurance, donations,
  household services, craftsmen, medical costs, Riester, solidarity surcharge -- the value of every year
  as a bar against **that year's cap as a red line** (dashed where it is a threshold from which the
  cost counts), so it shows what is used up and what is not;
- **Erklärungen**: every return to unfold, down to each item with its calculation and its receipts;
- **Posten**: every item of every year, searchable; **Belege**: every receipt and its files.

Two ways to open it, and the page is never copied:

- `python pytaxde.py <folder> --anzeigen` serves it on 127.0.0.1 (nobody else can reach it) with the
  data computed from the YAML files on every reload -- nothing is written -- and the receipts as links;
  only files a `belege:` list names can be fetched, by number;
- or open `viewer.html` from disk and drop a `Steuererklärungen.json` on it; everything shows, except
  the links (a page from disk may not open other files).

An item that belongs to another cluster than its section's -- a home-office allowance filed among the
further expenses, as it had to be until 2022 -- says so with `kategorie: homeoffice`.

## Your own returns stay with you

Keep the returns next to their receipts, outside this repository, with the folder's
`Steuererklärungen.json` beside them -- or, if the folder has a subfolder `PyTaxDEConfig/`, in there,
next to whatever else belongs to the tooling rather than to a year. Nothing else is needed: no test
file of your own, no copy of your numbers here.

The YAML files themselves may live in `PyTaxDEConfig/` too, all years side by side, while each year's
receipts stay in its own folder. A top-level `belege_ordner:` then says where the receipts are,
relative to the YAML file, and every `belege:` entry keeps its path relative to that folder:

```yaml
jahr: 2025
belege_ordner: "../2025 Steuererklärung"
```

A note in Markdown beside the YAML (`Steuererklärung 2025.md`: what was filed, what lies where) is
checked by `--verweise`: every link must exist relative to the note, as in any editor that follows it,
and every path in a code span (`` `2026-05-21 Bescheid\` ``) relative to the receipts' folder, as in
the YAML. "…" abbreviates a long file name; commands, web addresses and code blocks are left alone.

Before a commit, let the privacy test read your real returns: it then fails on any of their words or
numbers that made it into this project (an example modelled on your own year, say). It keeps no list
of its own; words a return shares with the library by nature are accepted in a
`privacy_allowlist.txt` in your folder (or its `PyTaxDEConfig/`), so that list stays private as well.

    PYTAXDE_PRIVATE="<your folder>" python -m unittest privacy_test

## Two persons

A joint assessment is `veranlagung: zusammen` plus a `person_b:` block holding the second person's
wage tax certificates, commute, expenses and insurance figures — the same keys as the return itself.
Each person keeps their own employee allowance; caps, the solidarity-surcharge exemption and the
Sonderausgaben flat rate double; the tariff is split. Rental income (`vermietung:`) names its person.

## Not covered

Church tax, Progressionsvorbehalt (e.g. sick pay), children, self-employment, capital income, the
costs side of rental income beyond plain items. Working days know Berlin's holidays only.

No warranty, no tax advice.
