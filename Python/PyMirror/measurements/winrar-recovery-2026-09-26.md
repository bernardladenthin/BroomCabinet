<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# The WinRAR settings for cold storage, measured against a real WinRAR

Every switch `b2-pack.py` emits was put to a real WinRAR with throwaway data rather than remembered.
Two of them were WRONG in the tool until this was done, and one of those would have dropped files
silently. Nothing in the collection was touched; the test data was generated in a scratch directory.

The first half below answers the question that started it -- can `-rr` and `-rv` both be used, and
does a lost part file really come back -- and the second half settles the remaining four switches.

## The two are different mechanisms and both apply at once

| | `-rr[N]` recovery **record** | `-rv[N]` recovery **volumes** |
|---|---|---|
| where it lives | inside each volume | separate `.rev` files beside them |
| what it repairs | damage **within** a volume | a volume that is **missing or destroyed** |
| repaired with | `rar r` | `rar rc` |
| a lost part file | **cannot help** | **this is what it is for** |
| default size | 3 % of the archive | none; `N` is a count |

`rar.txt` (WinRAR's own manual, German edition, lines 525 and 585) states both, and the measurement
below confirms they coexist: one `rar a -m1 -v1m -rr3p -rv2` produced volumes that `rar l -v`
reports as carrying *Wiederherstellungsdaten* **and** the matching `.rev` files.

## What was measured

Throwaway data, half compressible and half random.

**1 · `-rv` accepts a percentage.** `rar -?` lists only `rv[N]`, so `-rv20%` looked like a guess.
It is not: the command returned 0 and wrote the expected `.rev` files. The percentage is of the
**volume count**, not of the byte size.

**2 · Both switches in one command.** `rar a -m1 -v1m -rr3p -rv2 both.rar data/` produced:

```
1048576 both.part01.rar     1048627 both.part01.rev
 828016 both.part02.rar     1048627 both.part02.rev
```

`rar l -v` on each volume: `Details: RAR 5, Volume 1, Wiederherstellungsdaten`.

**3 · Three lost volumes, restored.** 32 volumes, 4 recovery volumes, then
`many.part03.rar`, `many.part07.rar` and `many.part11.rar` deleted — non-adjacent, to avoid
measuring a single contiguous gap:

```
Es fehlen 3 Volumen.
Stelle Daten wieder her...
Erstelle many.part03.rar.
Erstelle many.part07.rar.
Erstelle many.part11.rar.
Fertig
```

32 volumes again, and `rar t` answered **Alles OK**.

**4 · The boundary fails, and fails loudly.** Five volumes deleted against four `.rev`:

```
Es fehlen 5 Volumen.
Wiederherstellung unmöglich.
```

`rar t` on the incomplete set: `Fehler insgesamt: 2`. There is no partial credit — N recovery
volumes restore any N losses and nothing beyond.

## Two things that would have bitten later

**`rar rc` returned exit code 0 when recovery was impossible.** The text said
*Wiederherstellung unmöglich* and the archive stayed broken, but a script checking `$?` would have
concluded success. Any automation must count the volumes afterwards, or run `rar t`, and not trust
the status.

**The volumes must not be modified after the `.rev` files exist.** `rar.txt` is explicit: the
recovery algorithm reads both the `.rev` files and the `.rar` volumes, so changing a volume
afterwards — locking it, for instance — makes recovery of a missing volume fail. Whatever order the
build script uses, `-rv` is last.

## What this settles for the plan

`-rr3p -rv10%` in `b2-pack.py`'s defaults is correct and the two are not redundant. For a 30-volume
unit, 10 % is three `.rev` files: three whole parts may be lost from Backblaze or from a shelf of
discs and the unit still restores completely. The record is there for the other failure — a disc
that is scratched rather than gone — which `.rev` also covers but only by spending a whole volume's
worth of redundancy on it.

`rar.txt` also documents `rv` as a **command** against a finished volume set. It was exercised
afterwards and it works -- see the last section, and the reason it is deliberately not used.


---

# The other four switches, settled the same day

The plan needed four more answers, and two of them were wrong in the tool until they were measured.

## `-k` may be given at packing time and **never** afterwards

The owner's long-standing template carries `-rr10 -rv2 -k` in one command, and `rar.txt` warns that
modifying the volumes after the `.rev` files exist breaks recovery -- naming *locking* as the
example. Both directions were tried.

| | result |
|---|---|
| `rar a -ma5 -m0 -v300000b -rr10 -rv2 -k`, then delete 2 of 14 volumes | `rar rc` restored both, `rar t` **Alles OK** |
| pack without `-k`, then `rar k` on every volume, then delete 2 | `Prüfsummenfehler` · **`Es fehlen 14 Volumen. Wiederherstellung unmöglich.`** |

Locking rewrites every volume, so the `.rev` files match none of them any more -- all fourteen, not
just the two that were deleted. The redundancy becomes worthless silently: nothing announces it
until the day it is needed.

**The rule:** `-k` belongs in the `rar a` command and must never become a separate step. Locking at
creation is what *prevents* the later change that would invalidate the recovery volumes, so it
protects them rather than competing with them.

## The charset letter for UTF-8 is `F`, not `U`

`b2-pack.py` emitted `-scul` until this was measured. Five files with non-ASCII names -- umlauts,
Cyrillic, CJK, an accent -- listed in a UTF-8 list file:

| switch | files stored, of five |
|---|---:|
| `-scfl` (F = UTF-8) | **5** |
| `-scul` (U = UTF-16) | **0** |
| none | 1 |

`rar.txt` adds why: a UTF-16 list file without a byte order mark makes RAR ignore the switch and read
the file as ASCII. The exit code was 10 in the failing cases, so a build script that checks it would
notice -- but the archive would otherwise simply be missing files, which reads as nothing at all.

This matters only because this plan feeds RAR a **sorted list file**, which it needs so that
identical files sit next to each other. The owner's own template uses `-r dir*` and reads names from
the filesystem, where the charset switch is irrelevant; nothing packed that way is affected.

## `-sv` bounds the solid block, not the file

Eight 100 kB files against 300 kB volumes -- every file smaller than a volume:

| mode | files appearing in more than one volume |
|---|---|
| `-s -sv` | `f2.bin`, `f5.bin` |
| `-s` | `f2.bin`, `f5.bin` |
| no solid mode | `f2.bin`, `f5.bin` |

So `-sv` does not stop a file being split. What it buys is that each volume is an independent solid
block, which keeps single-file retrieval to one or two volumes instead of every volume from the start
of the set. "One volume" is the common case and not a guarantee, and the tool's docstring was
corrected to say so.

## An absolute path keeps every directory below the drive letter

The unit index is passed to RAR as an absolute path, because the `@list` entries are relative to the
collection and a second base cannot be mixed into one command. What RAR stored was the whole path
minus the drive letter -- profile directory, temporary directory, account name, all of it.

A work directory under a profile would therefore write the account name into all nineteen archives,
permanently, since they are locked. With `-ep1` the name collapses to the bare file name, but `-ep1`
also strips the leading component from the relative list entries, which breaks them.

**The rule, now enforced:** `--work` must be one directory directly under a drive root, and
`b2-pack.py` refuses a path that is deeper or that contains a profile directory name. The index then
reads as one directory plus the file name inside every archive.

## And one that is deliberately not used

`rar rv3 unit.part01.rar` **does** write recovery volumes for a finished set, and two deleted volumes
were restored from them. It is not used: the redundancy is decided once, at packing time, because
`-k` in the same command then forbids the later change that would invalidate it. It remains the
escape hatch if more redundancy is ever wanted -- at the price of unlocking, which means repacking.
