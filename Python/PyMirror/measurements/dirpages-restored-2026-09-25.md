<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# B1's removed listings, put back where a listing belongs

**32 directory pages, restored 2026-09-25 as `<directory>/index.html` in `gsi-collection`.**

## What they were, and why removing them was right

Each was an Apache index page stored **as a directory's name** — `…/floppies/200` was a file, so
the crawler could not create the directory and everything behind it was unreachable. B1 removed
them and fetched what they had been blocking: 543 of 544 files.

## Why putting them back is also right

They are not damage in themselves; they are **the source's own statement about what each directory
contains**, and that is what `audit.py --listed` compares against. The 32 directories had no
listing at all, so `--listed` could say nothing about them. Stored *inside* the directory — where
the crawler puts a listing normally — nothing is blocked and the check works again.

Before: `--listed` read no listing for these directories.
After: **28 listings with a size column, 537 files compared**, 534 agreeing.

## Two findings that only became visible again

**`floppies/2530/root.2` — advertised and not served.** The listing named it at 1 468 006 bytes,
then and now. `GET` returns **404**, while `boot.1`, `root.3` and `root.4` in the same directory
all answer 200 with real bytes. So the source's own index names a file the source will not give.
Not our loss, and not re-fetchable: this is the one file behind B1's "543 of 544".

**`floppies/200/root.3` — truncated at the source.** The listing says 1.2 MB; the file is **8 197
bytes**, 99.3 per cent short. The server today serves exactly 8 197 bytes. Our copy is faithful.

Its neighbours `root.2` and `root.4` hold 1 228 800 against a listed 1 258 291 and are **not**
findings: the column prints `1.2M` and `parse_size` expands it, so the figure is as exact as the
text was. `size_agrees()` tolerates that and still catches a file missing 99 per cent of itself —
which is the whole reason it is three-valued rather than an equality.

## What this cost and what it changed

132 945 bytes, 32 files. `gsi-collection`'s marker was restated from 6 239 to 6 271 files with the
reason written into it, and its `completed` date left as the crawl's — the archive was completed
then and repaired now, and those are different facts.
