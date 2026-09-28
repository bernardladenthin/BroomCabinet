<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# C4: the first full `--holes` run over the collection

2026-09-25, 00:23:32 to 05:50:41 — **5 h 27 min**, 99 of 99 archives, **0 failed**, error
channel empty. Written by `holes-run.py`, one log per archive.

| | |
|---|---:|
| archives | 99 |
| files read in full | 33 734 |
| bytes read | 2.39 TB |
| **findings** | **67** |

## What is here

`<archive>.log` — one per archive, written atomically by `common.atomic_write`, so a log
exists only if that archive was read to the end. That is also the runner's entire notion of
what is already done: delete a log and a re-run redoes that archive and nothing else.

`RUN-<timestamp>.out` / `.err` — the runner's own progress and error channel.

## These are the record, not a report

The counts in this file are derived from the logs and can be re-derived from them:

    awk '/incomplete files/{for(i=1;i<=NF;i++) if($(i+1)=="incomplete") s+=$i} END{print s}' *.log

`holes-record-test.py` does exactly that and compares it against what the run claimed, so the
summary above cannot drift away from the logs it came out of.

## Three of the 67 are real damage, and none of it is ours

`HOLES_AT_SOURCE` in `audit.py` carries them with the full argument. Short version: an AVI whose
RIFF header declares exactly its own size and is 94.7 % zeros, and two PDFs whose last `%%EOF`
sits in the first kilobyte of 30 and 79 MB. All three were fetched from their sources and are
**byte for byte identical** to what is held here — so the copies are faithful and there is
nothing to re-fetch.

Asking only for the length would have got this wrong: all three sources answer HEAD with exactly
our length, and a source holding the *intact* file at the same length is precisely the repairable
case. Only the bytes separate the two.

The other 64 are open as **C6**.
