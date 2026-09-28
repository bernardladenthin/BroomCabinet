<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# What `audit.py --ruins --empty` found across the collection, 2026-09-24

A full read-only pass over 1.76 million files. This records what the numbers mean, because the
raw counts are misleading in both directions and were misread twice before they were understood.

## The headline numbers are not findings

| | raw | after the obvious exclusions |
|---|---:|---:|
| ruins | 26 313 | **3 123** |
| all-zero files | 400 | **81 certain**, 20 of those explained |

**23 190 of the 26 313 were one directory.** `oss4aix.org/rpmdb/db/` holds a dependency database
the site publishes: one short text file per package, named after that package's `.rpm`, holding
`prov`/`req` lines. Nothing is wrong with them. Reporting "23 239 broken RPMs" would have been
badly wrong, and the only reason it was not reported is that the number was implausible enough to
check. It is now `SOURCE_CONVENTIONS` in `audit.py`, named with its reason.

## Categorised: 49 findings where the file is certainly not what its name says

### 33 directory pages saved as files — 341 files behind them

> **PARTLY SUPERSEDED ON 2026-09-25 — do not read this section as the current state.** The 32
> `gsi-collection` pages were restored into the collection as `<dir>/index.html`, so the blocker
> below is gone: the page and the directory now coexist, and the listings are readable again.
> What did **not** change is the 341 absent files — restoring a listing does not fetch what it
> lists. See
> [`measurements/dirpages-restored-2026-09-25.md`](measurements/dirpages-restored-2026-09-25.md)
> for the restore and [`dirpages-before-2026-09-24.json`](dirpages-before-2026-09-24.json) for the
> state it was made from. The table stays as measured, because a record that is edited to match
> today cannot show that the fix worked.

A server's generated index, stored at the path where a directory belongs. A filesystem cannot
hold both, so **nothing below that path can exist**.

| archive | pages | listed | present elsewhere | absent |
|---|---:|---:|---:|---:|
| `gsi-collection` | 32 | 540 | 225 | **315** |
| `ardent-tool` | 1 | 26 | 0 | **26** |
| | **33** | **566** | **225** | **341** |

The middle column is why "566 blocked" would have been wrong: `gsi-collection` mirrors the same
software under `SOFTWARE/DOWNLOAD/` and `SOFTWARE/ftp.ntnu.no/`, so 225 of the names listed behind
a blocked page are held under another path. **341 are genuinely absent.**

The largest single one is `SOFTWARE/DOWNLOAD/AIX/POWER/53`: 17 874 bytes of HTML listing 111
entries, 75 of which exist nowhere in the archive.

### 16 pages stored under an archive or document name

Each was identified by reading its `<title>`:

| what it actually is | count | example |
|---|---:|---|
| Bull's landing page instead of the package | 8 | `gcc-4.8.4-1.aix7.1.ppc.rpm` -> *Welcome to Bull AIX freeware site* |
| a real page under a `.pdf` name | 4 | `sa380544.pdf` -> *IBM eServer - UNIX Servers features and benefits* |
| a 404 page | 3 | `964N3S3.ZIP` -> *404 File Not Found* |
| a Wayback Machine page | 1 | `rcm204a.tar.z` -> *Internet Archive Wayback Machine* |

Four of the `.pdf` ones are in `ps-2.kev009.com/basil.holloway/ALL PDF/` -- the same directory
whose lighttpd listings parsed to nothing and left 1 955 PDFs behind in 2026-09.

## Not categorised: 3 074 signature mismatches

`.pdf` 2 016, `.z` 739, `.gz` 176, `.zip` 93, `.rpm` 49, `.rar` 1. Concentrated in
`somuchstuff-pdp8` (1 877) and `ibiblio-historic-linux` (526).

**These have NOT been checked.** A signature mismatch is not damage by itself -- a `.z` that is
not `compress(1)` may be a pack(1) file, a `.pdf` may be a PostScript document somebody renamed,
and the `rpmdb` case showed how a source's own convention can account for thousands at once.
Nobody should quote this number as a defect count until a sample has been read.

## 81 all-zero files, of which 20 are explained

| | count | |
|---|---:|---|
| the SOURCE serves zeros | 20 | measured against the live host: HTTP 200, right length, every byte zero. Our copy is faithful. Recorded exactly in `ZERO_AT_SOURCE`. |
| in `hp-alphaserver-2008` | 61 | that archive is FROZEN, unpacked from bitsavers' `h18002.www1.hp.com_20080527.tar`. `verify-extraction.py` re-hashed **10 201 members out of the tar with zero mismatches**, so our copy is byte-identical and the emptiness is HP's 2008 capture. Second archive of this shape after `hp-labs-2007`. |

The first diagnosis of the 20 was wrong. All twenty had exactly the size we stored, which looked
like a transfer that kept the length and lost the content -- so the first was re-fetched. It came
back as 276 906 fresh bytes of nothing. That is the only reason the other nineteen were probed
instead of repaired.

## What this says about the verification chain

Every one of the 20 zero files matched its own recorded SHA-256. The marker, the index and
`--verify` compare the tree **against itself**: they catch any later change and nothing that was
already wrong when the index was built. `--empty` is the first check that asks whether the content
could be content at all.

## `--listed`: asking the source's own index instead of asking the tree

Added the same day, after the section above was written. The stored directory listings are the
only statement in the collection that did not come from the tree: the server wrote them, they
name a size per file, and the crawler fetched those files afterwards.

Full collection run:

| outcome | files | |
|---|---:|---|
| agree with the listing | 79 218 | 88.0% |
| the column could not say | 4 919 | servers that never print a size below `1k` |
| **short by more than 10%** | **6** | findings, below |
| short by less | 12 | the source's column disagrees with the source's own files |
| longer | 5 829 | overwhelmingly SSI pages, see below |
| **compared** | **89 984** | out of 2 084 listings |

### The six

| file | listed | on disk | short by |
|---|---:|---:|---:|
| `bullfreeware…/contrib/mozilla-0.8.0.0.exe` | 38 063 308 | 7 488 | 100.0% |
| `aixtools/tools/aixtools.php.5.3.20.0.I` | 44 040 192 | 113 595 | 99.7% |
| `dec-ftp-2006/pub/X11/contrib/docs/Xbibliography.PS` | 129 024 | 103 880 | 19.5% |
| `dec-ftp-2006/pub/X11/R6-contrib/docs/Xbibliography.PS` | 129 024 | 103 880 | 19.5% |
| `dec-ftp-2006/pub/X11/contrib/utilities/ls-lR.Z` | 5 017 | 3 874 | 22.8% |
| `dec-ftp-2006/pub/X11/R6-contrib/utilities/ls-lR.Z` | 5 017 | 3 874 | 22.8% |

The first is the one that justifies the check. `mozilla-0.8.0.0.exe` is not an executable at all:
it opens `<!-- Copyright (C) Bull SAS - 2019 -->`, an HTML landing page the server answered 200
with, stored under the name of the file that was asked for. `--ruins` cannot see it because
`.exe` has no entry in `MAGIC`, `--empty` cannot because it is not zeros, and `--verify` cannot
because **a truncated file hashes to itself perfectly**.

The four `dec-ftp-2006` rows are two files, each held twice. Both are structurally sound — one is
a valid `%!PS-Adobe-1.0`, the other carries the `compress(1)` magic — and they stay findings
precisely because nobody can settle them: that archive was unpacked from bitsavers'
`ftp.digital.com_20060831.tar`, and there is no live source to ask.

### Three things the first run got wrong, and how each was settled

**18 short became 6.** Three of the original findings were re-fetched from the live server. It
answered HTTP 200 and served **byte-for-byte what we hold** — 86 697, 74 512 and 22 465 bytes
against listings of 89 088, 75 776 and 22 528. `ps-2.kev009.com`'s size column does not describe
its own files, by up to 2.7% in both directions. There is a measured gap between that 2.7% and
the smallest shortfall of any other kind (19.5%), so the threshold sits at 10% and the small ones
are printed in their own group rather than counted.

**"The source changed after it was stored" was the wrong caption for the 5 829.** `hp-labs-2007`'s
pages end with `<!-- End Footer server-side include -->`. The listing gives the size of the
`.html` **on the server's disk**; what was fetched is the assembled output. Hence a uniform
~15 kB per page rather than a proportional difference.

**The summary did not add up to itself.** The third group was added and left out of the total, so
a run announced 89 972 files compared where it had compared 89 984 — short by exactly the size of
the group just introduced, with both numbers looking plausible. Outcomes now print one per line
and a test sums them against the stated total.

### What that leaves

An independent record is better than a self-referential one and is still not an authority: a
third of the first run's findings dissolved when the source was asked. The rungs, in order — the
tree about itself, the source's index about the tree, the source itself, and, where it exists, a
signature the source published.

## What the whole day amounts to

Three checks were run over the collection and every count they produced was read rather than
quoted. The collapse from raw count to finding is the point:

| check | raw | after reading | real |
|---|---:|---:|---:|
| `--ruins` | 26 280 | 1 194 after naming the source conventions | **21**, none repairable |
| `--listed` | 89 984 compared | 18 short | **6** |
| `--empty` | 400 all-zero | 81 certain | **20** at the live source, 79 in a frozen capture |

**Not one of the 21 `--ruins` findings can be repaired**, established by asking each source once
on 2026-09-24 and reading the bytes of the answer rather than its status code — which mattered,
because four of them are served with `200` by a host that is alive and simply wrong. Eight came
back byte-identical to what we hold; nine sit behind hosts that no longer answer.

So the collection's condition, after a day of measuring, is: **faithful**. Every defect traced to
the end belongs to a source — a server answering 200 with a landing page, a capture that was
already empty in 2008, a size column that does not describe its own files. What changed is not
the mirror but what can be said about it, and how much of that is written down where the next
person will find it.

Three records now carry that, each named for the evidence it rests on rather than for the
symptom: `ZERO_AT_SOURCE` (a live host was asked), `ZERO_IN_CAPTURE` (the container's own
packing list was checked), `PAGE_AT_SOURCE` (the source still serves a page under that name).
Keeping them apart is the same discipline as reading a sample before quoting a number.
