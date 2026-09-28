<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# sweeper — emptying a working directory without emptying the wrong one

A working directory fills up over weeks. Probes, half-downloads, unpacked copies, one-shot
scripts, saved pages, the three files that turned out to matter. At some point it holds ten
thousand files and the only honest answer to *what is in here* is *nobody knows any more*.

Clearing it by extension, by age or by size deletes the wrong things, because **a filename is
not evidence**. It records what somebody hoped the file would be at the moment they created it.
So the decision is made once, per file, in a CSV that records *why* — and these three tools build
that CSV, check it, and carry it out.

| | |
|---|---|
| `inventory.py` | one row per file: size, mtime, SHA-256, a group, and two columns a person fills in. `--held-in` pre-marks whatever is already held in a named collection, **by content**, writing the holding path into the reason |
| `sweep.py` | removes exactly the rows marked `delete` that still describe the file on disk, and refuses everything else out loud. Dry run by default |
| `sweep_test.py` | builds a throwaway tree with a **real junction** in it and proves each guard, including that the file behind the link is still there afterwards |

Standard library only; no dependencies. Works on Windows and on POSIX.

    python inventory.py --root C:\work\scratch --held-in Q:\mirror
    # edit the decision and reason columns
    python sweep.py --root C:\work\scratch
    python sweep.py --root C:\work\scratch --apply

## No path in this repository points at your disk

Everything is a parameter: the root, the inventory, the log, the collections to compare against.
This started life as a script with the directory written into a constant, which is the shape that
works exactly once and is dangerous to reuse. The generalisation is the whole point of the
project — but it removes the one safety property the constant had, so:

**The root must carry a marker.** `--root` alone is refused; the directory must contain a file
called `.sweepable` that you put there by hand. A path is a thing one mistypes, and the single
mistake that matters here is emptying the wrong directory. There is no flag that skips this, and
adding one would give back exactly what the marker was introduced to prevent.

## The guards, and what each one is for

None of these is hypothetical. Each is here because the alternative failed on real data.

| | |
|---|---|
| the root carries `.sweepable` | above |
| every CSV path is relative | a row with a drive letter, a leading separator or a `..` component is refused unread. A CSV is a text file, and text files are untrusted input |
| containment is decided on the **resolved** path | `realpath` follows junctions, so a junction inside the root pointing at `C:\Windows` resolves to `C:\Windows` and fails. This is the check that actually stops that case |
| no reparse point on the way | belt and braces: the file and every directory between it and the root are checked for `FILE_ATTRIBUTE_REPARSE_POINT` |
| long paths use the `\\?\` prefix | without it Windows refuses anything over 259 characters and `lstat` raises |
| the row must still describe the file | size, mtime and SHA-256 are compared against the inventory. A file that changed since is refused: the evidence that justified deleting it described something else |
| a removal is written down **before** it happens | an interrupted run still says what it did |
| a failure is as loud as a success | see below |

### `is_reparse_point` used to lie

An early version returned `True` for anything it could not `lstat`. So 634 files that were simply
**gone** were reported as *sitting behind a junction*. The decision was safe and the reason was
false — and the reason is what a person reads, and acts on. It now distinguishes `FileNotFoundError`
from every other `OSError`, and `sweep_test.py` asserts that a missing file is called missing.

### "removed 495" over 498 candidates

Three files failed on their read-only bit and nothing was said about them; the difference was
visible only to a reader who subtracted. Failures are now listed, counted, and the exit code is
non-zero. The read-only attribute of a file unpacked from an old archive **is** cleared — that
bit is an artefact of the extraction, not a protection anybody set — but the log records that it
was cleared, because a tool that quietly defeats a write protection is not one to trust with a
delete.

## The decision column starts empty

A tool that guesses `delete` and asks for a veto gets that veto only for the files somebody
actually looked at. Here the default is *keep*, by omission: **an unedited inventory sweeps
nothing.** Re-running `inventory.py` carries every decision and reason forward for the paths still
present, so the file survives another pass after the directory has changed.

Nothing is written in place, ever. A complete temp file is renamed over the target — a
`csv.DictWriter(open(CSV, "w"))` without a `with` truncated an inventory once and blocked an
`os.replace` another time.

## `--held-in` matches content, never names

    python inventory.py --root DIR --held-in Q:\mirror --held-in Q:\mirrorLess

Each collection is hashed once, and every file in the working directory whose content is already
in one of them is pre-marked with the path where it is held — `held in Q:\mirror\tuhs\tarball_tocs.txt.gz`,
not `duplicate`. **A reason a person cannot check is not a reason.**

It is by content because the first real run of this idea found a `Makefile` that shared its name
with a member of a tar archive and differed in bytes. Deleting on a name match would have lost
the only copy of the changed one.

## Running the self-test

    python sweep_test.py

Twenty cases against a tree it builds in the system temp directory, with a junction made by
`mklink /J` (a symlink where that is the native thing). Two assertions per refusal: that it said
no, **and that the file behind the link still exists**. A guard that returns the right answer
while something else has already deleted the file is not a guard.

`--keep` leaves the tree behind to look at.

## What this deliberately does not do

- **It does not decide.** No heuristic marks a file for deletion except an exact content match
  against a collection you named. Everything else is a person typing `delete` in a column.
- **It does not move things.** Filing something into a collection is a separate act with separate
  evidence; conflating it with sweeping means a mistake in either one looks like the other.
- **It does not recurse into junctions**, in either tool. Walking through one puts foreign paths
  into the inventory under names that look local, and `sweep.py` would then correctly refuse
  every one of them — after a person had already read the list and believed it.

## Licence

Apache-2.0. See [`../../LICENSES/`](../../LICENSES).
