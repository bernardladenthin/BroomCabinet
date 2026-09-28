<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Directory listings, one per form that actually occurs

Twenty-one files, 116 KB. Each one is a real page a real web server produced,
trimmed to the generator's own output. `listings-test.py` reads them all and
compares what `common.parse_listing` makes of them against `expected.json`.

## Why real pages rather than invented ones

Every matcher in `parse_listing` exists because a real page had a shape the
others missed, and each one cost a run to find:

- a lighttpd table that parsed to nothing, leaving `basil.holloway/` and its
  1 955 PDFs out of an archive that was marked COMPLETE;
- a frameset whose 1.72 GB came back as zero files, with no failure and no
  unreadable listing recorded anywhere;
- a FancyIndexing listing in `DD-Mon-YYYY`, where every file arrived with no
  size and no date -- fetchable, but stamped with the day it was copied.

None of those can be reproduced by an example somebody wrote for the purpose.
The thing under test is what *somebody else's* server writes.

## How they were chosen

On 2026-09-23 all 287 112 stored pages in the collection were read and sorted
by what decides their parse:

    <matcher>-<generator>-<size><date><frames><images>

which gave **21 distinct forms**. The smallest example of each is here. The
selection touched the mirror read-only; nothing was fetched for it.

| part | values |
|---|---|
| matcher | `row` (HTMLTable), `pre` (FancyIndexing), `bare` (link scan only) |
| generator | `apache`, `caddy`, `plain` (names itself nowhere) |
| columns | `s` size, `d` date, `f` frames, `i` embedded images, `-` absent |

`lighttpd` has no file here: the collection holds no lighttpd listing today.
Its matcher stays in the library regardless -- it is the one that found the
1 955 PDFs, and a form that does not occur now is not a form that never will.

## Trimming

Human-written prose around a listing is removed; the table or `<pre>` block and
the head that decides how it is read remain. **Every cut was checked**: a
shortened page that no longer fires the matcher it was chosen for would be a
fixture that tests something else while claiming to test that form, so each
candidate was re-parsed after the cut and the original kept where the cut
changed what it was. One file (`row-apache-sd--`, 12 KB) is uncut for that
reason.

## Changing them

`expected.json` is a pin, not a description. After a deliberate change to the
parser:

    python listings-test.py --rebuild

and read the diff of `expected.json` before committing it. A rebuild makes
every difference disappear, which is the opposite of a test.

## Licensing

Each file has a `.license` sidecar naming the archive it came from, under
`LicenseRef-factual-listing` -- see `LICENSES/` at the repository root for what
that covers and why.
