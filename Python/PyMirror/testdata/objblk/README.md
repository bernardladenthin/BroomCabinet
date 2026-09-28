<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# A record that states its own length

Four `OBJBLK??` files from an Ultima VI savegame directory, 3 183 bytes in all.
Each holds the objects on one map chunk: a two-byte count, then eight bytes per
object. So `size == 2 + 8 * count`, and the file carries the number it must be
checked against.

Measured over all 69 in that directory on 2026-09-24: **68 agree exactly.**

## What that settles, in both directions

| file | bytes | its count demands | |
|---|---:|---:|---|
| `OBJBLKAF` | 2 | 2 | a **complete** record saying "no objects here" — not damage |
| `OBJBLKAA` | 18 | 18 | |
| `OBJBLKAC` | 74 | 74 | |
| `OBJBLKDF` | 3 089 | 3 090 | **one byte short** — the last record began and did not finish |

Seven files in that directory are two bytes of zeros. They were never reported
as losses, because `cannot_be_empty()` declines to judge them — but "nobody
complained" is not a finding either. The format answers it: two bytes is the
whole record.

And the same rule, applied to all 69 rather than to the seven in question, found
the one that is actually broken. Nothing in this tool sees `OBJBLKDF`: it is not
empty, its name has no extension `MAGIC` knows, and `--holes` starts at 16 MB.

## Why four files and not 69

The rule is arithmetic over a two-byte header. 134 KB of somebody's savegame
would prove nothing that the header does not. The count over all 69 lives in
`expected.json` as a record of what was measured — and `WhenTheMirrorIsHere`
re-takes it whenever the collection is mounted.
