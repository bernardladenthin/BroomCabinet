<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# C7: the 199 ISO findings, asked of a second reader

`audit.py --declared` reported 205 files shorter than the length they state for themselves. 199
are `.iso`, and the wording "these are losses" was stronger than the evidence.

**What `--declared` actually knows** about an ISO is that the primary volume descriptor states a
volume size, that both endian copies of that field agree, and that the file is smaller than
blocks × block size. That is a real signal and it cannot distinguish *truncated* from *the
descriptor describes more than this image holds*.

**A fourth hand-rolled parser was the wrong answer.** Three ZIP versions had already been wrong
that evening, and each was caught by a second opinion rather than by reading. So: 7-Zip, which is
installed, mature, and independent — the same move `zipfile` settled the ZIP half with.

## How to re-take this

`iso-second-opinion.py`, in this repository:

    python iso-second-opinion.py --report measurements/declared-2026-09-25.txt

It reads the ISO findings out of a `--declared` report, asks 7-Zip about each one, and prints the
three-way split below. **It refuses to run without 7-Zip** rather than falling back to the volume
descriptor, because that fallback is the guess the whole exercise exists to replace. 19 tests,
none of which needs 7-Zip installed.

The script that first produced these numbers lived in a scratch directory and would have gone with
it -- the same gap that `ask-the-source.py` was written to close earlier the same day. A record
nobody can re-take is a claim.

## What 7-Zip was asked

`7z l` walks the directory tree and prints the total size of the files it finds. It reads
metadata, not content, so it is cheap even on gigabyte images. Three outcomes:

| | |
|---|---:|
| **the listing exceeds the file — TRUNCATED** | **11** |
| the filesystem reads cleanly and fits — the descriptor simply overstates | **134** |
| 7-Zip cannot read the filesystem at all — **no verdict possible** | 54 |

## The eleven

    2.26 GB   fsck-ibm-other/…/HMC1/MH01560.iso
  558.75 MB   ps-2.kev009.com/pccbbs/pc_servers_iso/dir5.10_linuxonpowr_test.iso
  297.77 MB   oldskool/drivers/Tandy/Sensation I/…Bookshelf CD.iso
  184.19 MB   ps-2.kev009.com/pccbbs/options/06p4907.iso
  139.00 MB   fsck-aix-media/…/AIX_V4.3.3_Bonus_Pack_12.2000_1_of_4.iso
   28.02 MB   ps-2.kev009.com/rs6000-firmware/01SF222_075_075.iso
   21.93 MB   ps-2.kev009.com/pccbbs/pc_servers/37l6176.iso  (and its rwth-aachen copy)
  553.23 kB   ps-2.kev009.com/pccbbs/thinkcentre_bios/2nj931a.iso
  301.46 kB   fsck-vendors/SCO/…/unixware_701_cd2.iso
  230.16 kB   ps-2.kev009.com/pccbbs/thinkcentre_bios/2jj939a.iso

An image whose own directory needs more bytes than the file contains is truncated and nothing
else. All eleven are in the 532 that `truncated-vs-source.py` asked about: **0 re-fetchable.**

## The fifty-four, and why they are a conclusion rather than a task

7-Zip errors out on these and can list a fragment — 1.33 kB of a 327 MB file — reporting things
like `Incorrect big-endian headers`. Several are HP-UX images that carry a second filesystem
beside ISO 9660: at the offset where a root directory record should be they hold `AA AA` and a
1995 date, which is structure, just not this one's.

**Neither reader can say anything about them**, and "I cannot tell" is an answer. Writing a third
reader for HP-UX LVM to settle images whose sources are all gone would cost more than it could
return. If it ever matters, the note to start from is that the failing images cluster by vendor,
not by archive.

## What changed in the tool

`check_declared`'s ISO wording now says what it can support: the volume descriptor is a claim
about size, and a claim is where a finding starts rather than where it ends.
