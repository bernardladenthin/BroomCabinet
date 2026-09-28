<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Is there anything in this collection worth re-fetching?

**No.** 2026-09-25, and it was asked three separate ways.

| what was asked | how | result |
|---|---|---|
| 67 files with whole empty blocks | a range request for the empty blocks themselves | 67 of 67 the source's own holes, **0 re-fetchable** |
| 3 of those, the ones that are genuinely damaged | fetched whole, 130 MB, compared byte for byte | identical, **0 re-fetchable** |
| 532 files short of their own declared length | one HEAD each | **0 re-fetchable** |

## The 532

| | |
|---|---:|
| **the source has more — re-fetchable** | **0** |
| the source is the same length — broken there too | 516 |
| nobody answered | 13 |
| the source is SHORTER than our copy | 2 |
| no source URL recorded | 1 |

The two where the source has less are the mirror doing exactly what it is for:
`ndwiki-norsk-data/images/ND110-22-12-2019-2.zip` is 10.93 MB here and **0 bytes** at the source
today; `perzl-wiki/Main.Zip` likewise. Those copies are now the only ones.

The 13 unanswered are dead hosts — `ftp.agilent.com`, `dec-ftp`, `ftp.peak.org`.

## And yet two files WERE rescued, which is the caveat that matters

`Q:\DEC` holds intact copies of two DEC manuals that this collection held as 93 % and 74 % zeros.
They were not found by any of the work above, because **every method here asks the source the file
came from** — and that source is broken. They were found by looking somewhere else entirely.

**So "our copy is faithful" and "no better copy exists" are different questions**, and only the
first one is answered by this record. The DU11 manual makes the point sharply: the intact copy has
**exactly the same byte count** as the broken one, so every size-based check — including the 532
HEAD requests above — says "same, broken there too" and is right about the source and wrong about
the world.

## What this does settle

Every defect this collection can detect, traced to the source it was taken from, belongs to that
source. Nothing was lost in transit, in storage, or in the unpacking. That conclusion has now been
reached three times by three unrelated routes: C3 (zero-length files), C4 (files with holes), and
`--declared` (files short of their own claim).
