<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# C6: every hole `--holes` found, asked of its own source

2026-09-25, `holes-vs-source.py`. All **67** findings of the first full `--holes` run, each
checked against the source by asking for the empty 1 MiB blocks themselves — up to three per
file, the first, middle and last.

| | |
|---|---:|
| the source has the same holes | **67** |
| **the source has content where we have nothing** | **0** |
| the server ignored the range request | 0 |
| the server answered, but not with the file | 0 |
| nobody answered | 0 |
| **cost** | **133 range requests, 139 MB** |

Two runs: 46 from the archives whose register entry is an HTTP address (104 requests, 109 MB),
then 21 from `bitsavers` through the `HTTP_FACE` entry (29 requests, 30 MB).

## Why this is worth keeping rather than re-running

It is a measurement against **live servers**, and this collection exists because those do not
stay live. Two of the four hosts in `robots_verdict_test.py` had already stopped answering by the
day it was written. Re-taking this in a year may be impossible; the numbers above are what there
will be.

## What it proves, and what it does not

Three blocks is a **sample**. A file whose three agree is consistent with the source, not proven
identical to it — the three that were fetched whole keep the stronger record in
`audit.HOLES_AT_SOURCE`. That is enough to stop reporting them as losses, which was the question.

A disagreement would have been the best finding this collection can produce: the source having
content where we hold nothing is a **re-fetchable** loss, and nothing else here can see one.
There were none.

## Why not simply exempt the extensions

`.udf`, `.usb` and `.efs` were flagged at 100 %, `.toast` at 57.6 %. Exempting them would have
closed C6 in one line and cost a whole class of real findings — because 57.6 % means **fourteen
of thirty-three `.toast` came back clean**. The format does not always have holes, so a truncated
one would have become invisible forever. The damaged files found by C4 sit at 73–95 % empty and
the media images at 0.2–1.6 %, which looks like a threshold would work; asking the server is
better than a threshold, because it is evidence rather than a guess about somebody else's format.
