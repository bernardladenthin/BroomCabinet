<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# File heads, one per way a file can lie about what it is

Thirteen files of 512 bytes each (one is shorter: the file itself is 177 bytes). Every one is the opening of a real file in this
collection, and `heads-test.py` reads them all and compares what
`common.magic_mismatch` makes of them against `expected.json`.

## Why 512 bytes and not the file

`magic_mismatch` reads a head and never more, so a head is the whole of what is
under test. Copying 282 KB of somebody else's JPEG to prove something about its
first four bytes would be copying it for no reason.

## Why real files rather than invented ones

The same argument as [`../listings/`](../listings/README.md), and it has the
same evidence behind it. Every one of these was found by a check that was
already running, and two of them were found only because the check was widened
on the day they were captured:

| file | what it is |
|---|---|
| `gif-missing-first-byte.head` | opens `F87ac` — a GIF one byte into `GIF87a`. The first byte is simply gone |
| `jpeg-header-overwritten.head` | opens `yOya` where `FF D8 FF E0` belongs, with `JFIF` still legible two bytes later |
| `html-behind-a-comment.jpg.head` | an HTML page under an image name that opens with a **comment**, not with the doctype |
| `html-behind-a-comment.rpm.head` | the same page under a package name — how it was first found |
| `zero-filled.jpg.head` | an image of nothing at all |
| `http-response-kept.pdf.head` | a raw HTTP response stored as the file, `HTTP/1.1 200` and all. **The source serves it this way**; our copy is faithful |
| `directory-page.head` | a generated directory index, the shape that blocks a whole subtree when it is saved under a directory's name |
| `installshield-under-dot-z.head` | an **InstallShield 3.x Z archive** under a `.Z` name. `13 5D 65 8C`, a DOS date at offset 12, and it sits in `DISK1`/`WIN31`/`OS2` install sets. compress(1) also claims `.Z`, so this is a collision rather than damage |
| `pdf-damaged-at-the-source.head` | a PDF whose header is gone and whose tail stops mid-object, 5 600 objects and no `%%EOF`. **Byte-identical to what ps-2.kev009.com still serves** |
| `geocities-under-pdf.head` | a **Yahoo! GeoCities** shutdown page where a manual should be. The source still serves it |
| `ibm-marketing-under-pdf.head` | an **IBM eServer** marketing page under a manual's name, to this day |
| `wayback-under-tar-z.head` | an **Internet Archive Wayback** page stored as a compressed tarball |
| `notfound-under-zip.head` | a 404 page under a `.ZIP` name. 177 bytes, so this fixture is the WHOLE file |

Nobody would have invented the first two. A file missing exactly one byte, and a
file whose four-byte header was overwritten while the rest survived, are the kind
of damage that only turns up in thirty-year-old archives — and both are invisible
to every other check here, because the length is right, the hash matches what was
recorded, and nothing in the file is zero.

## The one that is not damage

`html-behind-a-comment.*` is the reason this directory exists at all.
`looks_like_html()` skipped a leading byte-order mark and leading whitespace, and
not a leading comment. The page it missed —

    <!-- Copyright (C) Bull SAS - 2019 -->
    <!DOCTYPE html>

— is the most common error page in this whole collection: found under an `.exe`
name by `--listed`, under eight `.rpm` names and under 28 image names by
`--ruins`, all on 2026-09-24. Every one of them was being reported as
*"does not begin with the .jpg signature"*, the vague answer that sends a reader
to open the file, instead of *"HTML under a .jpg name"*, which is finished.

A fixture for that case cannot be written from imagination, because the thing
under test is where somebody else's CMS chose to put its copyright line.

## How to add one

Take the first 512 bytes of the real file, drop it here, add a `.license`
sidecar naming where it came from, and put its expected verdict in
`expected.json`. `heads-test.py` will pick it up. If `magic_mismatch` cannot
yet name it, record what it currently answers rather than what it ought to —
a fixture that documents a gap is worth more than one that hides it.

## Captured while the sources still answered

Four of these were fetched on 2026-09-24 specifically because their hosts were
still up. They are four flavours of one shape -- **the source itself serves a
web page where a binary belongs** -- and they are the reason `PAGE_AT_SOURCE`
exists: none of the 21 files in that record can be repaired, because what the
server hands back is the page.

Half the evidence for that record is already unreachable. Nine of the 21 sit
behind `bullfreeware`'s two origin hosts, which do not answer at all.
