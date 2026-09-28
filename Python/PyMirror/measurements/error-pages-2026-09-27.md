<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# A wrong page under a right name, measured over the whole collection

`common.looks_like_an_error_page()` exists because of eight files. It ships with a strength
field because of 2 357.

Everything below was measured against the collection on 2026-09-27, read-only. The work-list is
`error-pages-2026-09-27.csv` beside this file, one row per finding.

## What started it

`spider.seds.org/ngc/` holds eight `.cgi` files. All eight were fetched with HTTP 200 and stored.
Six of them are error pages:

| file | bytes | its own title |
|---|---:|---|
| `ngc-new.cgi` | 881 | `NGC Error !` |
| `ngc-old.cgi` | 881 | `NGC Error !` |
| `ngc.cgi` | 1 038 | `NGC Error !` |
| `ngc_fr.cgi` | 1 303 | `Erreur NGC !` |
| `ngcic.cgi` | 150 | `NGC/IC Error!` |
| `revngcic.cgi` | 188 | `Error in revngcic.cgi` |
| `ngcdss.cgi` | 866 | `Digital Sky Survey image` — a real page |
| `ngcdss_fr.cgi` | 1 014 | `Digital Sky Survey image` — a real page |

**Nothing reported them, and nothing was broken.** `.cgi` is in
`common.PROGRAM_PAGE_EXTENSIONS`, so HTML under that name is exactly what is expected;
`magic_mismatch()` and `find-html-imposters.py` both start from a name that is already suspect.
A wrong page under a *right* name was a hole in the vocabulary, not a bug in a check.

A ninth file, `ngc/ngc_sel.cgi`, answers HTTP 500 with the same 538 bytes on every request — it
is the submit target of the NGC search form. It is excluded in `mirror.EXCLUDE`, which is the
fourth instance of a shape `somuchstuff-pdp8`'s entry had already predicted in writing.

## The rule, and the two discriminators that are measurably wrong

The first version asked one question: does the page's own `<title>` contain an error word? Run
over every stored page in the collection — **295 586 files in 106 archives, 80.4 minutes** — it
answers:

| | findings |
|---|---:|
| `error` | 2 225 |
| `not found` | 120 |
| `forbidden` | 12 |
| **total** | **2 357** |

About 2 275 of those are **documents**. This collection holds an IBM technical-support knowledge
base, IBM PS/2 hardware-maintenance manuals, an AIX message reference, and the Bison and Emacs
manuals. Their pages are titled `Error Log`, `Numeric Error Codes`, `Appendix B. ODM Error
Codes`, `Bison 1.25 - Error Recovery`, `The Linux SCSI programming HOWTO: Error handling`. A rule
that reports those is not a rule.

Two ways of separating them were tried. **Both are backwards, and both looked convincing before
they were measured.**

**Title length.** On the 13 examples in hand it was decisive: real error pages had titles of
11–21 characters, the HP Labs false positives 54–79. Over the whole collection the *shortest
title of all* is `Error Log` — nine characters, an IBM PS/2 manual page.

**File size.** An error page is a stub, so a body threshold should separate it from a document.
The *smallest findings in the collection* are 284-byte PS/2 manual frames. Below every threshold
tried, the findings stay dominated by `ps-2.kev009.com`:

| threshold | findings | largest archive |
|---:|---:|---|
| ≤ 600 B | 312 | ps-2.kev009.com 287 |
| ≤ 1 000 B | 340 | ps-2.kev009.com 294 |
| ≤ 2 000 B | 522 | ps-2.kev009.com 348 |
| ≤ 4 096 B | 1 142 | ps-2.kev009.com 852 |

## What does work

A stock error page's title **is** the status phrase. A document's title is a sentence that
contains one. Requiring the former — after stripping a leading status code and, in front of a
phrase of two words or more, a site prefix — keeps **82 of the 2 357**, in five distinct titles:

| count | title | reduces to |
|---:|---|---|
| 67 | `404 Not Found` | not found |
| 9 | `IBM PartnerWorld for Developers : Document not found message` | document not found message |
| 3 | `Document not found message` | document not found message |
| 2 | `File Not Found` | file not found |
| 1 | `404 - File or directory not found.` | file or directory not found |

Every one is a server talking. They sit in `infania-tl2` (41), `sgidepot` (24),
`ps-2.kev009.com` (12), `mpoli-bbs` (2), `bitsavers`, `infania-os-history` and `oldskool` (1
each).

The single-word exception is worth stating: a site prefix may be dropped only in front of a
phrase of **two words or more**. Without that, `ECA 024 - 113 error` reduces to the bare word
`error` and is kept — and it is a BBS bulletin about error 113, not a server saying anything.
That exception is the difference between 84 findings and 82, and both it removes are false.

## So the answer carries its own strength

`looks_like_an_error_page()` returns `(kind, strength, title)`. `STOCK` is the 82; `WEAK` is
everything else the loose vocabulary finds.

**The six seds pages are WEAK**, and that is the honest shape of this problem rather than
something to fix later. `NGC Error !` is a title an application invented. Nothing separates it
from `Error Log` except knowing that `spider.seds.org` holds no error-code documentation and
`ps-2.kev009.com` is made of it — knowledge about an archive, which is a caller's to have and
not a library's.

So: `find-html-imposters.py --pages` reports STOCK only, and `--weak` adds the rest. A sweep of
the collection is usable on STOCK; WEAK is for one archive at a time, where a person reads the
handful that come back. On `seds-frommert`: 0 findings without `--weak`, 6 with, all correct.

## What the rule will still miss, and it is the larger half

The **commonest** error page in this collection is titled `Bull Freeware`. The GeoCities one is
`Yahoo! GeoCities`, the Wayback one `Internet Archive Wayback Machine`. Each is a site's own
template served where a file was expected, and none admits to anything.

| | caught by |
|---|---|
| wrong name, any content | `magic_mismatch()` — Bull, GeoCities, Wayback |
| right name, admitted failure | `looks_like_an_error_page()` — the seds pages |
| right name, **silent** wrong page | **nothing here** |

The third row is written down so it is not discovered twice. Fixtures for all three are in
`testdata/heads/`, with real bytes.

## Two things found on the way

**89 of the 2 357 titles carry an HTML entity** — `&quot;` 107 times, `&#58;` 18, `&amp;` 6, em
and en dashes 11. `&#58;` is a colon, and the site-prefix rule looks for one, so
`NETFINITY 3500&#58; ERROR LED RESET` would have kept its prefix and been judged against the
wrong string. `page_title()` decodes entities since this measurement.

**The extension list had drifted.** `find-html-imposters.py` carried its own set of "extensions
where markup is expected" and it was missing `.php4`, `.phtm`, `.shtm` and `.xhtm`, four
spellings the library already knew. **119 files in two archives** (`hp-labs-2007`,
`hp-labs-linux-salvage`) were affected: each was reported as markup under a non-markup extension
— a false finding — and none was read by `--pages`, so a real error page under `.php4` would have
been missed. The set is now derived from `PAGE_EXTENSIONS` in the library. After the fix those
two archives report 18 imposters instead of 137, none of them `.php4`.

## How to repeat it

```
python find-html-imposters.py --pages --csv measurements/error-pages-<date>.csv
python find-html-imposters.py --pages --weak --archive seds-frommert
```

The scan is read-only, writes a CSV, and deletes, renames and re-fetches nothing.
