<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# One 1970s disk, enough of it to settle 43 files

`audit.ZERO_IN_THE_MEDIUM` records 43 files that are entirely zeros and are
*not* damage: the OS/8 disk image they were extracted from is zero in exactly
those blocks. `zero-in-the-medium-test.py` re-derives that claim here, from the
extractor's own index and a recorded block map — no mirror, no network.

## What is here

| file | what it is |
|---|---|
| `dec-s8-lftna-a-ua1.xml` | the extractor's index, real: per file, the octal block range it occupies |
| `blockmap.json` | derived: one character per block of the image, `0` = entirely zero, plus the image's SHA-256 |
| `block-01162.bin` | 512 real bytes of the image, the one block the tests read as bytes |

## Why the image is not here

It is 377 344 bytes of DEC's software and 363 of its 737 blocks are zeros.
Copying a third of a megabyte to prove that some of it is nothing would be
copying it for no reason. The block map says everything the tests ask, in 737
characters.

That leaves one thing to take on trust — that the map is a true statement about
the image — so the test does not take it on trust. `WhenTheMirrorIsHere`
re-derives the map from the image and compares the SHA-256, and skips itself
where the collection is not mounted.

## Why one real block is kept

A block table that is off by a constant would make every zero check pass and
mean nothing. Block 01162 is where `acos.ra` starts, and `acos.ra` is RALF
assembler source, whose comment character is `/`. OS/8 stores text with the high
bit set, so those bytes have to read `AF 08 8D 0A`. That is the single
assumption arithmetic cannot check, so it is checked against bytes.

## Two units, and they are not interchangeable

A block is 256 twelve-bit words. In the image each word takes two bytes, so a
block is **512 bytes there**. The extractor packs the same 3 072 bits into
**384 bytes here**. Confusing the two is the mistake this directory exists to
make impossible.
