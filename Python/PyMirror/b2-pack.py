# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Plan the WinRAR units that carry this collection to cold storage. Prints; does not run.

WHY A PLANNER AND NOT A SCRIPT. The collection is 4.06 TB in 113 archives and 1.83 million files.
Whatever packs it will be run a handful of times over years, by hand, and every run costs hours.
A command that is printed, read and then executed is the right shape for that; a command that runs
because a script reached line 300 is not. So `--execute` is opt-in and the default prints.

THE UNIT IS THE THING THAT GETS REBUILT. A multi-volume RAR cannot be appended to, so any later
correction means repacking a whole unit. That single fact decides the grouping: a unit is a set of
mirrors that belong to one subject AND tend to change together. Nineteen of them, listed in
`UNITS`, each with the reason it is one unit written next to it.

WHAT THE MEASUREMENTS SAID, because the grouping is not taste:

  * 66.6 % of the collection is already entropy-coded -- `pdf` alone is 1.21 TB of scanned paper.
    The whole count is in measurements/collection-composition-2026-09-26.md, taken read-only from
    the per-archive indexes.
    Only 0.5 % is text. So the compression LEVEL barely matters and `-m1` is the default; the
    handful of units that hold uncompressed containers say so in their own override.
  * 171.37 GB are byte-identical files held more than once. This grouping keeps 120.96 GB of that
    INSIDE a unit, where a solid block collapses it, and leaves 50.41 GB crossing a boundary --
    70.6 % captured, counted per file by `b2-cluster.py` rather than by summing the pair table,
    which double-counts a file held in three archives. A solid block collapses those to nearly nothing -- but only if the copies are
    ADJACENT, which is why the file list is sorted by (extension, size, digest, path) and not by
    directory. Identical files share all three leading keys, so they end up next to each other.
  * A solid block gains nothing beyond one dictionary. `-sv` therefore costs almost no ratio and
    keeps each volume an independent solid block, so fetching one file means fetching ONE OR TWO
    volumes instead of every volume from the start of the set. Measured: `-sv` does NOT stop RAR
    splitting a file across a volume boundary, even one smaller than a volume, so "one" is the
    common case and not a guarantee.

THREE THINGS THIS TOOL DOES NOT DO. It never writes into the collection -- it reads the per-archive
`.mirror-index.csv` and nothing else. It never puts the password in the printed plan. And it never
guesses a RAR switch: everything uncertain is in `VERIFY_AGAINST_YOUR_RAR` with what to check.

    python b2-pack.py                               the whole plan, nothing executed
    python b2-pack.py --only misc --verbose          one unit, with its file list
    python b2-pack.py --sizes                       what each unit weighs, from the indexes
    python b2-pack.py --execute                     actually pack (refuses without rar)

HOW TO START A UNIT SO IT SURVIVES THE SESSION. A unit takes hours -- misc is the smallest at
144 GB -- and a packer started from an agent session, a terminal or an SSH login dies with it. On
Windows, `Start-Process` hands the process to the operating system instead:

    powershell -NoProfile -Command "Start-Process -FilePath 'python' -ArgumentList '-u',
      'b2-pack.py','--root','Q:/mirror','--out','X:/mirrorPacked',
      '--work','X:/mirrorPackedWork','--only','misc','--execute'
      -WorkingDirectory '<the directory holding b2-pack.py>'
      -RedirectStandardOutput '<--out>\misc-run.log'
      -RedirectStandardError  '<--out>\misc-run.err'
      -WindowStyle Hidden"

    (one line in the shell; `-u` so the log is not buffered, and the two redirects MUST be
     different files -- Start-Process refuses one file for both)

THE LOGS GO TO --out, AND THAT IS THE WHOLE POINT OF THE SPLIT. One drive holds the collection and
is READ; the other receives everything this run produces and is WRITTEN. The owner, 2026-10-05:
"damit auf dem einen datenträger nur gelesen wird auf dem anderen geschrieben". Keeping the log
anywhere else blurs that line, and the line is what makes "the mirror is read-only" a statement
somebody can check with a disk counter rather than a promise.

IT ALSO MEANS THE LOGS TRAVEL TO B2 beside the volumes, because --out is the upload directory.
That is wanted: how a unit was packed, by which switches and with what rar said, is provenance,
and provenance that stays on the packing machine is provenance that is eventually lost.

THREE THINGS THAT BIT ON THE FIRST REAL RUN, 2026-10-05:

  THE DESTINATION DIRECTORY MUST EXIST OR BE CREATABLE. RAR does not create it and answers
  `Kann ... nicht erstellen. Das System kann den angegebenen Pfad nicht finden.` with exit code 9.
  `execute()` creates it; the failure was a directory removed by hand between two attempts.

  A KILLED RUN LEAVES A PARTIAL FIRST VOLUME. Remove it before restarting, or `rar a` treats the
  set as one to be updated rather than created.

  MEASURED MEMORY: 12.9 GB with -md6g -m5. rar.txt gives only two anchors -- about 7 GB for a
  1 GB dictionary and about 96 GB for 64 GB -- and nothing between, so this is the figure to
  reuse rather than an interpolation.

HOW TO CHECK A FINISHED UNIT, AND WHAT EACH CHECK COSTS. Measured against misc on 2026-10-05,
98.62 GB in 468 volumes:

    rar l   <unit>.part001.rar              what is inside. No dictionary, no decompression.
    rar lt  <unit>.part001.rar              the same plus the CRC32 OF EVERY FILE, read from the
                                            archive headers, and the parameters it was packed
                                            with ("Gepackt mit: RAR 5.0(v70) -m5 -md=6g").
                                            Still no dictionary.
    rar t -mdx6g <unit>.part001.rar         the real thing: every byte decompressed and checked
                                            against its CRC. 7 minutes and 3.8 GB of memory for
                                            misc, and it REFUSES without -mdx (see execute()).
    rar rc  <unit>.part001.rar              rebuild missing volumes from the .rev files.

SO THERE ARE TWO LEVELS AND THE CHEAP ONE NEEDS NOTHING. `rar lt`'s CRC32 can be held against the
`.sfv` that is packed INSIDE the unit -- a list built independently, by us, from the files
themselves -- and that comparison reads no compressed data at all. It is also the reason the four
manifests had to go in: without them there is nothing for those CRCs to be checked against.

A SINGLE VOLUME CANNOT BE TESTED ON ITS OWN. `rar t <unit>.part200.rar` resolves the whole set and
behaves exactly like testing part001; there is no per-volume check short of the recovery record
doing its work during a repair.
"""
import argparse
import collections
import filecmp
import glob
import io
import math
import os
import re
import shutil
import subprocess
import sys
import time

from common import (BOOKKEEPING_FILES, DIGESTS, INDEX_FILE, MANIFEST_FILES, MIRROR_ROOT,
                    SFV_FILE, exists, find_tool,
                    human, long_path, parse_size, read_index, read_sfv, relative_to, say,
                    split_archive)

# THE VOLUME SIZE IS THE OWNER'S AND IT IS 199 MiB, MEASURED RATHER THAN RECALLED. It was
# 24 200 000 000 bytes until 2026-10-04, then 995 000 000 for a few hours, and that middle figure
# rested on something I had wrong.
#
#   I SAID B2 TAKES A FILE OF UP TO 5 GB IN ONE PIECE. That is the API's limit and it is not the
#   one that binds. The owner's own PyB2Verify snapshots of his live B2 buckets settle it, and
#   they are not named here because the privacy guard is right to want them unnamed: across twelve
#   buckets, 2 950 files carry a whole-file SHA-1 that B2 itself reported, 2 797 carry none and
#   are described only by an S3 ETag over their part MD5s, and the boundary between the two sets
#   is exactly 209 715 200 bytes -- 200 MiB, the uploader's cutoff, not the API's. Several files
#   AT 200 MiB have a SHA-1; the smallest without one is 210 621 984.
#
#   SO 995 MB WOULD HAVE BEEN UPLOADED IN PARTS, with no whole-file digest, which is the thing the
#   size was chosen to avoid. The owner's 25 GB M-Disc RAR sets are the standing example: `sha1`
#   empty, `parts` reading `100000000*250,4758990`, and fixity only through a rebuilt ETag.
#
#   AND NO LARGE FILE IN THOSE SNAPSHOTS CARRIES ONE. `large_file_sha1` in fileInfo would allow it,
#   and two rows looked at first like proof that it happens -- one had its digest adopted from an
#   older snapshot, the other was downloaded and hashed locally (`source=download`). Neither came
#   from B2. The feature exists; this uploader does not use it.
#
# AND ON 2026-10-06 THE 200 MiB CUTOFF WAS IDENTIFIED AND THEN DELIBERATELY ABANDONED. The
# boundary measured above is Cyberduck's: its own documentation says "Files larger than 200MB are
# split into 100MB chunks and uploaded with multiple connections", which is exactly the
# `100000000*250,4758990` in the owner's snapshots. It is not documented as configurable. So
# staying under it was never a property of B2 -- whose single-request limit really is 5 GB -- but
# of one uploader's fixed threshold.
#
# WHAT MADE 199 MiB UNAFFORDABLE WAS THE SOLID BLOCK, not the cutoff. Measured 2026-10-06 at the
# production volume size: plain `-s` is byte-for-byte identical to `-s=v`, so the solid stream
# RESETS AT EVERY VOLUME BOUNDARY (rar.txt says so under -s=v, "vorausgesetzt, es wurden nach dem
# vorangegangenen Zurücksetzen genügend Daten gepackt" -- 199 MiB counts as enough). The effective
# compression window was therefore 199 MiB and never the 6 GB dictionary:
#
#   -s      630 364 279 B   4 volumes      the production setting
#   -s=v    630 364 279 B   4 volumes      identical, which is the proof
#   -s=d    525 383 636 B   3 volumes      100.1 MiB smaller, one duplicate collapsed
#
# So 521.3 GB of byte-identical in-unit duplicates were being stored in full. Removing `-sv` on
# 2026-10-05 "so the dictionary would mean something" achieved nothing: the default already did
# what -sv does.
#
# 3 557 000 000 BYTES, AND EVERY DIGIT OF IT IS A CONSTRAINT:
#
#   FAT32           4 294 967 295 B is the hard maximum file size (2^32 - 1, from the 4-byte
#                   length field in the directory entry). 738 MB of headroom, which also absorbs
#                   a .rev being slightly larger than the volume it protects.
#   a 4 GB stick    3.557e9 fits a nominal 4 GB device with room; 4e9 and 4 149 914 282 do not.
#   EVERY M-DISC    SEVEN volumes on a 25 GB, FOURTEEN on a 50 GB, TWENTY-EIGHT on a 100 GB, and
#                   all three land on 99.50 % of the RAW capacity -- under the owner's ceiling of
#                   99.7 % and on his 99.5 % burn margin, with 120.5 MiB left on a 25 GB disc for
#                   UDF's own structures (one to two MB for seven large files).
#
# 3 900 000 000 WAS THE FIRST ANSWER AND IT WASTED A DISC EVERY TWENTY-NINE. Six of those fill a
# 25 GB disc to 93.5 %, leaving 1.5 GB unused per disc -- 261 GB across the 174 discs the
# collection needs. Seven smaller volumes tile it almost exactly instead. The price is 1142
# volumes rather than 1042 and a 3.56 GB solid block rather than 3.9 GB, which is nothing against
# 261 GB of disc.
#
# THE CAPACITY FIGURE IS THE BD-R ONE AND THAT DISTINCTION MATTERS. A BD-RE reserves a spare area
# for defect management and takes only 24 220 008 448 B -- the figure an ImgBurn user hit when he
# expected 25 025 314 816 and came up 768 MiB short. M-Disc is write-once BD-R, which has no such
# reservation. Both numbers are kept below so neither gets used for the other medium.
#
# WHAT IT COSTS ON B2: Cyberduck will upload each volume as ~39 parts of 100 MB, so B2 stores a
# per-part SHA-1 and no whole-file digest. The owner accepted that -- "lediglich b2 ist dann nicht
# optimal wegen sha, aber das ist nicht ganz so schlimm" -- and it is survivable because THIS
# COLLECTION CARRIES ITS OWN FOUR MANIFESTS. B2's digest was a convenience; .sha256sum is the
# authority, and PyB2Verify already rebuilds the ETag from parts for exactly this case.
#
# WHAT IT BUYS: 1142 volumes instead of ~19 500, a 3.56 GB solid window instead of 199 MiB, and
# -rr1 becoming 35 MB per volume instead of 2 MiB -- the same percentage, eighteen times the
# repair.
VOLUME_BYTES = 3557000000
# The owner's ceiling on how full a disc may be written. A disc filled to its last byte is one
# that may not verify, and UDF needs room for its own descriptors on top of the payload.
M_DISC_MAX_FILL = 0.997
BD_RE_BYTES = 24220008448
M_DISC_BD_R_BYTES = 25025314816
# The owner's burn margins for M-Disc, as raw bytes at 99.5 % of capacity. A disc written to its
# last byte is a disc that may not verify, so the volume size is checked against these and not
# against the figures above.
M_DISC_995 = {25: 24899485696, 50: 49800019968, 100: 99600039936}
# How many volumes fill a 25 GB M-Disc inside that margin. SIX at 3.9e9, where it was 119 at
# 199 MiB and 1 when a volume was 24.2 GB -- which is why the plan counts files and derives discs,
# not the other way. Six also changes what the .rev budget can promise: at 119 per disc, no
# plausible number of .rev files could replace one lost disc; at six, a 3 % budget covers five.
PER_M_DISC = M_DISC_995[25] // VOLUME_BYTES
# FAT32's maximum file size, 2^32 - 1, from the 4-byte length field in a directory entry. Asserted
# rather than trusted: a volume above it cannot be put on the kind of cheap stick that is the
# cheapest off-site copy there is, and the failure would only show up at the moment of copying.
FAT32_MAX_BYTES = 4 * 1024 ** 3 - 1

INDEX_DIR = "index"
INDEX_SUFFIX = ".index.csv"

# `common.INDEX_FILE` names the per-archive index; it is read here and never written.

# PUT TO A REAL WINRAR ON 2026-09-26 with throwaway data, not remembered. 32 volumes, 4 recovery
# volumes, three non-adjacent volumes deleted: `rar rc` rebuilt all three and `rar t` passed.
# Five deleted against four .rev printed "Wiederherstellung unmoeglich" and `rar t` reported
# errors. Full record in measurements/winrar-recovery-2026-09-26.md.
MEASURED_ON_THIS_MACHINE = {
    "-rr and -rv together": "BOTH APPLY AT ONCE. Every volume carried a recovery record AND the "
                            ".rev files were written by the same command. They answer different "
                            "failures: -rr repairs damage INSIDE a volume, -rv replaces a volume "
                            "that is gone. Only -rv survives a lost part file.",
    "-rv<N>%": "ACCEPTED, although `rar -?` lists only `rv[N]`. 20 % of the volume count produced "
               "the expected number of .rev files.",
    "one .rev per lost volume": "N recovery volumes restore any N missing volumes, and N+1 losses "
                                "cannot be restored at all -- there is no partial credit.",
    "rc exit code": "`rar rc` RETURNED 0 EVEN WHEN RECOVERY WAS IMPOSSIBLE. Never trust its exit "
                    "status; count the volumes afterwards, or run `rar t`.",
    "rv as a later command": "`rar rv3 unit.part01.rar` DOES write .rev files for a finished "
                             "volume set, and two deleted volumes were restored from them. It is "
                             "not used: the redundancy is decided once, at packing time, because "
                             "-k in the same command then forbids the later change that would "
                             "invalidate it.",
    "-k in the same command is safe": "packed with -rr10 -rv2 -k, two deleted volumes were "
                                      "restored and `rar t` passed. Running `rar k` AFTERWARDS "
                                      "reported all fourteen volumes as checksum failures and "
                                      "recovery as impossible -- locking rewrites every volume.",
    "do not touch the volumes afterwards": "rar.txt is explicit: once the .rev files exist the "
                                           ".rar volumes must not be modified -- locking them "
                                           "afterwards breaks recovery.",
    "-scfl and not -scul": "THE CHARSET LETTER FOR UTF-8 IS F; U IS UTF-16. On a UTF-8 list file "
                           "with non-ASCII names, `-scfl` stored all five test files, `-scul` "
                           "stored NONE, and no switch at all stored one. This tool wrote -scul "
                           "until it was measured. rar.txt adds that a UTF-16 list without a byte "
                           "order mark makes RAR ignore the switch and read the file as ASCII.",
    "-sv does not prevent splitting": "files SMALLER than a volume are still split across two "
                                      "volumes -- measured with 100 kB files and 300 kB volumes, "
                                      "identically with -s -sv, with -s alone and with no solid "
                                      "mode. -sv bounds the SOLID BLOCK, not the file.",
    "an absolute path keeps its directories": "a file passed by absolute path is stored with every "
                                              "component below the drive letter. A work directory "
                                              "under a home directory would write the account name "
                                              "into every archive; hence WORK_MUST_BE_FLAT.",
}

# WHERE THE WORK DIRECTORY MAY BE, and this is a measured constraint rather than a preference.
# RAR stores a file given by absolute path under its whole path minus the drive letter. The unit
# index is passed that way, so `<drive>:\some\deep\work` would appear inside every archive
# as `some/deep/work/<unit>.index.csv` -- and one under a profile would carry the account
# name into every one of them. One component directly under a drive root keeps it to
# `work/<unit>...`.
WORK_MUST_BE_FLAT = 1
PERSONAL_IN_PATH = ("users", "documents", "desktop", "appdata", "home")

# Switches whose exact behaviour differs between WinRAR versions. Named here rather than assumed,
# because a wrong guess is only visible after hours of packing.
VERIFY_AGAINST_YOUR_RAR = {
    "nothing": "every switch this tool emits was put to a real WinRAR on 2026-09-26, and the four "
               "added since were checked against RAR 7.23's own switch list and accepted by it on "
               "2026-10-05. What is listed above is measured, not assumed. "
               "TWO OF THEM ARE NO LONGER DOCUMENTED: `rar -?` in 7.23 lists neither -ma nor -sv, "
               "yet -ma5 is accepted while -ma4 and -ma7 both answer `Unbekannte Option` -- so "
               "RAR 5.0 is not an old format to be escaped, it is the ONLY format this version "
               "writes. -sv is accepted too and is NOT passed, because measurement on 2026-10-06 "
               "showed it would be a no-op: plain -s is byte-for-byte identical to -s=v, so the "
               "solid stream already resets at every volume boundary. The window is therefore the "
               "volume, which is why the dictionary came down to 4g and why -oi1 does the "
               "deduplication the dictionary was believed to be doing. "
               "The one thing no measurement can settle is whether a restore works twenty years "
               "from now. A dictionary above 4 GB needs WinRAR 7.0 or newer to unpack; on the "
               "command line that is a refusal and in the GUI a dialog -- measured at 5 GiB of "
               "input, `rar t` answers OK on -md4g and exits 3 on -md6g, which is why 4g is the "
               "ceiling.",
}


class Options(object):
    r"""WinRAR settings, immutable. `with_()` returns a copy -- this is the whole builder.

    NOTHING IS DUPLICATED PER UNIT. `DEFAULTS` holds the settings that are right for two thirds of
    the collection, and a unit names only what differs. A table of ten full option sets would
    drift the moment one of them was edited; ten one-line overrides cannot.
    """

    FIELDS = ("archive_format", "method", "dictionary", "solid", "solid_per_volume",
              "volume_bytes", "dedup_references", "recovery_record", "recovery_percent",
              "recovery_volumes_floor",
              "lock", "encrypt_headers",
              "extra")

    def __init__(self, **kw):
        unknown = set(kw) - set(self.FIELDS)
        if unknown:
            raise ValueError("unknown option(s): %s" % ", ".join(sorted(unknown)))
        for field in self.FIELDS:
            setattr(self, field, kw.get(field))

    def with_(self, **kw):
        merged = dict((f, getattr(self, f)) for f in self.FIELDS)
        merged.update(kw)
        return Options(**merged)

    # THE OWNER'S 5 / 10 / 15 RULE, 2026-10-05, replacing a 2 % fraction with a floor. `-rv` takes
    # a count, so a count is what this expresses -- "für kleine reichen 5, mittel 10 und das ganz
    # große hat 15 recovery archive".
    #
    # THE THRESHOLDS ARE IN VOLUMES because that is what a .rev replaces, and they fall between the
    # real units rather than being round numbers for their own sake:
    #
    #     small   < 1 200   misc 698, oldskool 722, workstations 820, ibm-aix-opensource 1 007
    #     medium  < 3 000   ibm-aix-support 1 561, bitsavers-software 1 705, ibm-pc 2 568
    #     large   >=3 000   vendors 3 090, ibm-aix 3 400, bitsavers-paper 4 087
    #
    # WHAT IT COSTS AND WHAT IT GIVES UP, stated plainly: 95 .rev files in all, 19.8 GB, against
    # 398 and 83 GB under the 2 % rule. For bitsavers-paper that is 15 replaceable volumes out of
    # 4 087, which is 0.37 % rather than 2 %. The owner's reason is that this is the THIRD line of
    # defence, not the first: every volume carries its own 1 % record, every volume exists both
    # locally and on B2, and a .rev is for the case where both of those have failed on the same
    # part.

    def recovery_volumes(self, volumes):
        r"""-> how many .rev files this unit gets, for a set of `volumes` volumes.

        A PERCENTAGE, BECAUSE THE FIXED LADDER WAS INVERTED. 5 of 703 volumes is 0.71 % and 15 of
        4087 is 0.37 %: the unit with six times the volumes, and therefore six times the exposure
        to independent loss, got half the relative protection. RARLAB's own default for `-rv` is
        10 % (rar.txt: "Wird der Parameter <N> nicht angegeben, wird er auf 10% gesetzt"), so the
        ladder was running the largest unit at a small fraction of the vendor default.

        AND THERE IS NO PARTIAL CREDIT. N recovery volumes restore any N missing volumes and N+1
        losses restore nothing at all, so the number is not a dial that degrades gracefully -- it
        is a threshold, and it should scale with the set it guards.

        2 %, AND THE "COVERS A WHOLE M-DISC" ARGUMENT FOR 3 % WAS WRONG. It counted the
        collection's 1042 volumes as one set; .rev files protect ONE UNIT. At 3.9 GB a unit is 37
        to 217 volumes, so it spans several discs and a disc carries volumes from more than one
        unit -- no per-unit .rev budget can promise to replace a disc. What is left is the plain
        question of how many volumes of one unit may go missing, and 2 % answers it at 78 GB
        across the collection against 121 GB for 3 %.
        
        TWO PER CENT IS DEFENSIBLE BECAUSE .rev IS THE FOURTH LINE, not the first. Every volume
        exists locally, on B2 (whose 17+3 Reed-Solomon vaults are rated at eleven nines) and on
        M-Disc, and each volume carries its own 1 % record for damage inside it. A .rev is for the
        case where all of that has failed on the same volume.
        
        THE FLOOR IS 2 AND WAS 5, which only became wrong when the volumes grew. At 199 MiB a
        floor of 5 was 1 GB on any unit; at 3.9 GB it is 19.5 GB, and on the 144 GB misc unit that
        would have been 13.5 % -- a floor quietly overriding the percentage it was meant to
        backstop. Two keeps the promise that every unit, however small, can lose a volume and a
        spare.
        """
        if volumes is None or not self.volume_bytes:
            return 0
        from_percent = int(volumes * self.recovery_percent / 100.0)
        return max(from_percent, self.recovery_volumes_floor)

    def switches(self, volumes=None):
        """-> the switch list, in a fixed order so two runs produce the same command.

        `-ma5` IS EXPLICIT rather than left to the default. The archive format decides what can
        read it in twenty years, and a WinRAR that defaults differently would silently produce
        something else.

        `-k` LOCKS THE ARCHIVE, AND ONLY HERE. Measured on 2026-09-26: `-k` in the same `rar a`
        command is harmless -- two deleted volumes were restored from .rev afterwards. Running
        `rar k` LATER, once the .rev files exist, destroyed the whole set: `rar rc` then reported
        "Es fehlen 14 Volumen. Wiederherstellung unmoeglich", because locking rewrites every
        volume and the .rev files no longer match any of them. Locking at creation is what
        PREVENTS such a change, so it protects the recovery volumes rather than competing with
        them. It must never be applied as a separate step.
        """
        out = ["-ma%s" % self.archive_format, "-m%d" % self.method]
        if self.method > 0:
            out.append("-md%s" % self.dictionary)
            if self.solid:
                out.append("-s")
                # -sv IS NEVER PASSED AND THE FIELD IS KEPT ONLY SO A UNIT COULD ASK. Measured
                # 2026-10-06: plain `-s` is byte-for-byte identical to `-s=v`, so the stream
                # already resets at every volume. -sv would be a no-op with a misleading name.
                if self.solid_per_volume:
                    out.append("-sv")
            if self.dedup_references:
                # -oi1 STORES A BYTE-IDENTICAL FILE ONCE AND THE REST AS REFERENCES, and it is the
                # switch that actually does what the 6 GB dictionary was believed to be doing.
                # Measured 2026-10-06 on 600 MiB with a duplicate 500 MiB behind its twin:
                #
                #   -s -md6g           630 364 797 B   4 volumes
                #   -s -oi1 -md256m    525 300 860 B   3 volumes
                #   -s -oi1 -md4g      525 300 860 B   3 volumes   identical to 256m
                #
                # The dictionary makes NO difference to it, because references never go through
                # the match finder -- so it reaches across volume boundaries that the solid reset
                # closes. Aimed at the 521.3 GB of byte-identical duplicates inside units.
                #
                # WHAT IT COSTS, AND rar.txt NAMES IT: the duplicates were accidental redundancy.
                # After -oi1 the volume holding the single stored copy carries every reference to
                # it, and losing that volume loses them all. That is the reason the .rev budget
                # moved to a percentage in the same change -- Reed-Solomon over the whole set is
                # better placed than redundant copies of whichever files happened to repeat.
                out.append("-oi1")
        # No volume split for the index archive: it is small and is meant to be fetched whole.
        if self.volume_bytes:
            out.append("-v%db" % self.volume_bytes)
        if self.recovery_record:
            # `-rr10` and `-rr10p` produced byte-identical archives when measured, so the plain
            # form is used -- it is what the owner's own template says.
            out.append("-rr%s" % self.recovery_record)
        rev = self.recovery_volumes(volumes)
        if rev:
            out.append("-rv%d" % rev)
        if self.lock:
            out.append("-k")
        out.append("-scfl")
        out.extend(self.extra or ())
        return out

    def __repr__(self):
        return "Options(%s)" % ", ".join("%s=%r" % (f, getattr(self, f)) for f in self.FIELDS)


# The settings that are right for most of 4.06 TB: fast, because two thirds of it cannot be
# compressed anyway, but NOT stored -- `-m0` would also switch off the duplicate collapse, and the
# duplicates are worth more than the compression.
# ---------------------------------------------------------------------------------------------
# WHAT THE SWITCHES ACTUALLY BOUGHT: THE WHOLE COLLECTION, nine units packed between 2026-10-06
# and 2026-10-09, every figure read off the run that produced it. The settings below were argued
# from rar.txt and from 600 MiB measurements; this is what they did to 4 061.35 GB of real data.
#
#   unit                   source      archive        %   avg file   -oi1 refs   volumes
#   ibm-aix-opensource   207.96 GB      73.00 GB   35.1 %   1.13 MB      40 012        20
#   ibm-aix-support      322.53 GB     135.67 GB   42.1 %   3.19 MB      14 603        39
#   workstations         169.46 GB      89.00 GB   52.5 %   0.40 MB      30 445        25
#   ibm-aix              702.51 GB     395.00 GB   56.2 %  13.45 MB       2 657       115
#   ibm-pc               530.45 GB     306.86 GB   57.8 %   1.80 MB      20 470        87
#   vendors              638.39 GB     399.00 GB   62.5 %  16.31 MB       1 698       118
#   misc                 144.17 GB      93.88 GB   65.1 %   0.42 MB       8 777        27
#   oldskool             149.22 GB     120.00 GB   80.4 %   1.92 MB       3 120        35
#   bitsavers          1 196.66 GB   1 006.22 GB   84.1 %   6.80 MB       1 880       283
#   ------------------------------------------------------------------------------------------
#   total              4 061.35 GB   2 618.63 GB   64.5 %              123 662       749
#
# plus 69 GB of .rev across the nine units, so 2 688 GB is what leaves for cold storage.
#
# WHAT PREDICTS THE RATIO IS THE REFERENCE SHARE, and nothing else in the table does.
#
# References per file, not references. The nine units differ in file count by a factor of ten, so
# the raw count compares nothing: bitsavers has MORE references than vendors (1 880 vs 1 698) and
# the worst ratio of all nine, because it also has four times the files.
#
#   unit                 files    refs   ref/file    ratio
#   ibm-aix-opensource  184 465  40 012    21.69 %   35.1 %
#   ibm-aix-support     101 086  14 603    14.45 %   42.1 %
#   workstations        420 307  30 445     7.24 %   52.5 %
#   ibm-aix              52 241   2 657     5.09 %   56.2 %
#   ibm-pc              295 280  20 470     6.93 %   57.8 %
#   vendors              39 131   1 698     4.34 %   62.5 %
#   misc                341 969   8 777     2.57 %   65.1 %
#   oldskool             77 624   3 120     4.02 %   80.4 %
#   bitsavers           176 028   1 880     1.07 %   84.1 %
#
# SORTED BY RATIO, THE SHARE COLUMN DESCENDS, with two adjacent transpositions in nine: ibm-aix
# and ibm-pc (56.2 % against 57.8 %, which is within the noise of two different mirror sets), and
# misc and oldskool. Both ends are exact -- the best ratio has the highest share by a factor of
# three over second place, and the worst has the lowest.
#
# OLDSKOOL IS THE ONE REAL OUTLIER and it names the second factor: 4.02 % of its files are
# references, which should put it at misc's place, and it lands second-to-last instead. Its
# content arrives ALREADY ZIPPED -- driver archives downloaded as .zip -- so there is nothing left
# for -m5 to find even where files are unique. bitsavers has the same problem (1.2 TB of JPEG
# streams inside PDF) on top of the lowest share, and the two effects compound into 84.1 %.
#
# TWO CLAIMS WERE WRONG BEFORE THIS ONE, and both were caught by the tests in b2-pack-test.py
# rather than by reading:
#
#   "the fewest references marks the worst ratio" -- vendors has the fewest of all nine, 1 698,
#   and lands mid-table at 62.5 %. Few references only means a unit holds little twice.
#
#   "the three best ratios are the three highest reference counts, in order" -- they are not.
#   ibm-aix-support has 14 603 references against ibm-pc's 20 470 and a ratio 15 points better,
#   because it has a third of the files.
#
# Both failures came from using the count where the share was meant, and the correction is in the
# table above: the share is what was measured, so the share is what is claimed.
#
# FILE SIZE PREDICTS NOTHING HERE. bitsavers averages 6.80 MB and compresses worst; workstations
# averages 0.40 MB and third best; vendors holds the largest files in the collection at 16.31 MB
# and lands in the middle. A dictionary-first reading expects otherwise, which is why -md6g was
# not worth its memory and -oi1 was.
#
# SO THE ORDER IN `switches()` REFLECTS WHAT MATTERS: -m5 and -md4g are the compressor's settings,
# -s makes the solid stream, and -oi1 operates on top of all three by replacing whole files with
# references -- independent of the dictionary, which the 256m measurement showed, and independent
# of the volume boundary, which the solid reset closes.
#
# MEMORY, BY PHASE, reproduced across several units: 0.19 GB while -oi1 pre-hashes every file,
# 9.85 GB once compression starts, 4.02 GB during `rar t`, and 0.12 GB while the .rev files are
# built. The dictionary is allocated when the first block is compressed, not at launch, so a run
# looks free in its first minutes and the .rev phase needs almost nothing. rar.txt's interpolation
# for 4g is about 12 GB; 9.85 GB is as close as two figures it calls rough can be asked to come.
#
# TIME, for planning: bitsavers took 19.1 h to pack, then 1.5 h for `rar t` and 1.1 h for the four
# manifests -- 21.7 h for 1.2 TB. The whole collection was about 70 h of wall clock.
#
# AND WHAT THE RUNS PROVED ABOUT THE EDGES:
#
#   a 98.98 GB member          byCompID.tar spans 28 volumes and passed `rar t` and the CRC32
#                              cross-check without special handling.
#   five members over a volume  vendors holds files of 9.74, 4.40, 4.30, 4.21 and 3.57 GB against
#                              a 3.557 GB volume. Splitting is invisible to both checks.
#   420 307 files              workstations, the largest file count, pre-hashed by -oi1 without
#                              trouble -- the open question from the research pass, now closed.
#   283 volumes                bitsavers, the largest unit. -rv at 2 % gave it 6 .rev files, which
#                              is 2.1 % of the volumes: `max(int(volumes * 2 / 100), 2)` holds.
#   921 empty files            misc. CRC32 of zero bytes is 00000000, which is also what a -oi1
#                              reference carries, and the cross-check had to learn the difference.
#
# EVERY UNIT PASSED BOTH CHECKS: `rar t` over the volumes, and a CRC32-plus-file-count comparison
# against the archive's own .sfv, with each -oi1 reference judged through its target.
# NINE FOR NINE, and 123 662 references resolved through their targets.
# ---------------------------------------------------------------------------------------------
DEFAULTS = Options(
    archive_format="5",
    # -m5, REVERSED FROM -m1 ON 2026-10-04. The old default was fast because two thirds of the
    # collection cannot be compressed anyway; the owner's answer was that this is written once and
    # read for decades -- "da wir langzeit archivieren ist vlt. eine gute kompression besser als
    # schnell, das spart später viel". The cost is CPU hours, once, and no extra memory.
    #
    # A 6 GB DICTIONARY, THE OWNER'S FIGURE, and three documented things make it the right size:
    #
    #   IT COVERS EVERY DUPLICATE IN THE COLLECTION. A solid block collapses two byte-identical
    #   files only if the window still reaches the first one, and `sort_key` puts them adjacent.
    #   Measured per unit on 2026-10-04, the largest duplicate anywhere is 2 000.5 MB (vendors),
    #   then 1 997.5 (ibm-aix) and 1 346.4 (ibm-aix-support). 6 GB clears all of them with room, and
    #   rar.txt says that where the duplicates fit the dictionary, plain -s is the better tool
    #   than -oi: no references, no first-file dependency between volumes.
    #
    #   AND IT IS AIMED AT THE 667 GB OF DISK IMAGES. rar.txt names exactly this case: a larger
    #   dictionary "kann die Komprimierungsrate von großen Dateien mit weit auseinanderliegenden,
    #   sich wiederholenden Datenblöcken verbessern, wie z. B. bei Festplattenabbildern virtueller
    #   Maschinen" and for "eine Sammlung von ISO-Images". This collection is 521 GB of iso, 60 GB
    #   of mdf and 50 GB of img.
    #
    #   WHAT THE READER PAYS, SETTLED BY MEASUREMENT RATHER THAN BY EITHER OF US. Above 4 GB an
    #   archive needs WinRAR 7.0 or newer, and unpacking needs a little more than the dictionary.
    #   I warned that a reader would also need -mdx; the owner answered that the GUI needs no
    #   switch, and WhatsNew.txt backs him -- it "zeigt WinRAR ein Dialog an, der den Benutzer
    #   auffordert zu entscheiden, ob die Datei entpackt oder die Verarbeitung abgebrochen werden
    #   soll". So I wrote the warning off as wrong.
    #
    #   IT WAS NOT WRONG, IT WAS NARROWER THAN I SAID. The first real run's own `rar t` refused:
    #   "Ein 6 GB grosses Woerterbuch ueberschreitet die Obergrenze von 4 GB ... Verwenden Sie die
    #   Schalter -md6g oder -mdx6g". The GUI asks; the COMMAND LINE refuses -- and every tool here
    #   drives the command line, so `execute()` now passes -mdx with the unit's own dictionary. A
    #   human with WinRAR open pays nothing; a script pays one switch, and had better know it.
    #
    # WHAT THE MEMORY COST IS, HONESTLY: rar.txt gives two points -- about 7 GB for a 1 GB
    # dictionary and about 96 GB for 64 GB -- and no figure between them, and calls both "grob
    # geschätzt". So 6 GB lies somewhere in 9 to 42 GB and the documentation will not narrow it.
    # The machine has 63 GB.
    method=5,
    # 4g AND NOT 6g, SETTLED BY MEASUREMENT ON 2026-10-06 at 5 GiB of input (small inputs prove
    # nothing here: RAR clamps the dictionary down to the total input size, so a 40 MB test records
    # a tiny dictionary for every request and all of them pass):
    #
    #   -md4g   rar t without -mdx:  OK
    #   -md6g   rar t without -mdx:  exit 3
    #
    # The archive stays RAR 5.0 either way -- there is no RAR 7 format, `-ma7` answers "Unbekannte
    # Option" -- but above 4 GB it carries a minimum-version requirement, and on the COMMAND LINE
    # that is a refusal rather than the GUI's dialog. This collection is meant to be read in
    # decades, by whatever tool is at hand, so the ceiling is where the refusal stops.
    #
    # AND IT NOW MATCHES THE SOLID BLOCK EXACTLY. The block is the volume, 3.9 GB, so a dictionary
    # above 4 GB could never be filled; the old 6g was unreachable twice over.
    dictionary="4g",
    # AND EVERY UNIT USES THESE, which is the owner's instruction -- "Ich will es einheitlich für
    # alle archive" -- and a measurement turned it from a simplification into a correction.
    #
    # TWO UNITS WERE -m0, STORED RATHER THAN COMPRESSED, on the reasoning that their content is
    # already compressed: oss4aix.org is 100 % rpm and bitsavers-paper is scanned paper. -m0 also
    # switches off the solid block, so identical files are then stored twice in full. Measured per
    # unit on 2026-10-04:
    #
    #   ibm-aix-opensource   208.0 GB holding 116.9 GB of byte-identical files -- 56.2 %
    #   bitsavers-paper  844.4 GB holding   2.0 GB                         --  0.2 %
    #
    # SO -m0 WAS COSTING 117 GB on one of them. I had argued the opposite as recently as the same
    # afternoon, on the grounds that oss4aix.org "appears in none of b2-cluster.py's sharing
    # pairs" -- which is true and was the wrong measurement: those pairs count duplication BETWEEN
    # archives, and this is a package repository duplicating itself, the same rpm under many
    # paths. The question was asked about one unit and answered for all ten.
    #
    # THE WHOLE COLLECTION HOLDS 521.3 GB OF SUCH DUPLICATES INSIDE UNITS, 12.8 % of 4 061 GB, and
    # all of it is now reachable: the largest single duplicate is 2 000.5 MB and the dictionary is
    # 6 GB. Compressing bitsavers-paper's 844 GB of scans buys only its 2.0 GB and costs CPU, and
    # that is the price of one rule instead of ten.
    solid=True,
    # -sv IS GONE, 2026-10-05, AND IT HAD TO GO FOR THE DICTIONARY TO MEAN ANYTHING. The project's
    # own measurement of 2026-09-26 found that what `-sv` buys is "each volume is an independent
    # solid block". A volume is 199 MiB, so with `-sv` the solid stream RESTARTS every 199 MiB and
    # a 6 GB dictionary can never see past it -- the two switches were working against each other,
    # and 521.3 GB of byte-identical files inside units would have been stored twice over.
    #
    # WHAT IT COSTS is selective retrieval: without `-sv`, extracting one file needs every volume
    # from the start of the set, up to 844 GB for bitsavers-paper, where `-sv` kept it to one or
    # two. That was the reason it was there, and the owner retired the reason rather than the
    # measurement: "alle Volumes ab dem ersten ist kein Problem, die liegen eh bei mir da".
    #
    # AND THE DAMAGE CASE IS COVERED TWICE OVER: a solid stream means one broken volume spoils what
    # follows it, which is why every volume still carries its own 1 % recovery record and why the
    # .rev files exist. rar.txt names this cost of -s outright -- "geringe
    # Reparaturwahrscheinlichkeit bei Archivbeschädigungen".
    solid_per_volume=False,
    volume_bytes=VOLUME_BYTES,
    dedup_references=True,
    # 1 %, AND THE DIVISION OF LABOUR IS THE WHOLE ARGUMENT. -rr repairs damage INSIDE a volume;
    # .rev replaces one that is gone. At 199 MiB, 1 % is about 2 MiB per volume, and rar.txt says
    # a recovery record repairs slightly less than its own size in contiguous damage -- so 2 MiB
    # covers a flipped bit, a bad sector (4 KB), or hundreds of them. Anything worse is not worth
    # repairing in place when a whole replacement volume is 199 MiB and there are 398 of them.
    #
    # IT WAS 10 %, THEN 3 %, THEN THIS, in one afternoon, and each step followed the volume size
    # down: at 24.2 GB a volume was precious and worth defending in place; at 199 MiB it is
    # cheaper to replace than to patch. 1 % of 4 061 GB is 41 GB against 406 GB at 10 %.
    recovery_record="1",
    # 2 %, replacing the 5 / 10 / 15 ladder, with a floor of 2. See recovery_volumes() for why a
    # percentage, why two per cent, and why the floor had to come down when the volumes grew.
    recovery_percent=2,
    recovery_volumes_floor=2,
    lock=True,
    # NO ENCRYPTION. The owner's decision on 2026-10-04: "da es öffentliche Daten sind brauche ich
    # kein Passwort / Verschlüsselung, lediglich ECC und recovery archive". Every archive here was
    # fetched from a public host, so a password would protect nothing and would add the one way
    # this collection could become unreadable -- a lost key. The -hp machinery is kept, unused,
    # for a unit that might one day need it; `execute()` demands a password file only if some unit
    # asks for one.
    encrypt_headers=False,
    extra=(),
)


class Unit(object):
    """One RAR set: what goes in, why it is one unit, and what it does differently."""

    def __init__(self, name, members, why, options=None, exclude=()):
        self.name = name
        self.members = tuple(members)
        self.why = why
        self.options = options or DEFAULTS
        self.exclude = tuple(exclude)

    def archives(self):
        """-> the archive directory names this unit draws from, once each."""
        seen = []
        for m in self.members:
            head = split_archive(m)[0]
            if head not in seen:
                seen.append(head)
        return seen

    def claims(self, archive, path):
        """Does this unit take `archive/path`? Members may name a subtree; excludes win."""
        rel = archive + "/" + path.replace("\\", "/")
        for bad in self.exclude:
            if rel == bad or rel.startswith(bad.rstrip("/") + "/"):
                return False
        for m in self.members:
            if rel == m or rel.startswith(m.rstrip("/") + "/"):
                return True
        return False


UNITS = (
    # ---------------------------------------------------------------- IBM, AIX and POWER
    Unit("ibm-aix", ["ibm-aix"],
         "702 GB from one live IBM host, and 51 % of it is tar and bff -- uncompressed "
         "containers, the only large body in the collection where compression level pays, which "
         "is why it keeps -m5 -md1g while everything around it was consolidated. "
         "STILL ALONE AFTER THE 2026-10-04 REGROUPING, and the old reason for it has expired. The "
         "old sentence said `most likely to be re-fetched, and nothing else should be repacked "
         "when it is` -- that argument RETIRED with B2, where nothing is repacked ever again. "
         "What keeps it separate now is the method: folded into ibm-aix-support it would save ONE "
         ".rev file, 995 MB, and cost 702 GB its -m5 -md1g."),

    Unit("ibm-aix-support", ["fsck-aix-media", "fsck-aix-apps",
                         "bull-rpms", "bull-srpms", "bullfreeware", "ia-bullfreeware",
                         "ia-bull-toolbox-43", "ia-bull-aix433-2013", "ia-bull-aix433-2005",
                         "biblionik-bull", "biblionik-goupil",
                         "ibm-redbooks", "ibm-rs6000-support", "gsi-collection",
                         "filibeto-aix-lib", "cmu-shadow", "damage-rt", "AIX5-IA64",
                         "infania-tl1", "infania-tl2", "aixtools", "circle4",
                         "rs6000-microcode", "aix-orphans", "aix-qemu-git", "techsysadm",
                         "typewritten", "aixpdslib", "funet-aix", "ibm-openxl-docs",
                         "iffly-wiki", "misterhayden", "perzl-wiki", "tvsat-cpc710",
                         "csri-toronto"],
         "323 GB: everything you reach for while working on AIX except the operating system "
         "itself -- install media and applications, the whole Bull line, and all 24 documentation "
         "sources from the Redbooks to the QEMU recipes. THE OWNER'S RULE ON 2026-10-04: `wenn "
         "man an AIX Sachen arbeitet, entpackt man vermutlich komplett AIX, da spielen wenige GB "
         "mehr keine Rolle`. "
         "THREE UNITS BECAME ONE FOR THE SUBJECT AND NOT FOR THE BYTES, and the first draft of "
         "this comment got that wrong. It claimed three recovery-volume floors collapsing into "
         "one -- true at 24.2 GB volumes, where a floor wasted whole discs, and FALSE at 995 MB, "
         "where the 10 % fraction decides and barely notices how many units there are. Measured: "
         "this merge saves a single .rev file, and the whole regrouping from nineteen units to ten "
         "is worth 16 GB of 4 581. What it really buys is what was asked for -- one unpack "
         "instead of three. "
         "`fsck-aix-media` and `fsck-aix-apps` are here rather than with their host "
         "fsck.technology BECAUSE OF THE RETRIEVAL TEST: an AIX-under-QEMU project needs exactly "
         "this, and grouping by source would make it fetch 404 GB of other vendors to reach it. "
         "That costs 10.26 GB of duplication with fsck-vendors, paid deliberately -- it is the "
         "price of the rule above. "
         "THE BULL HALF HOLDS 111.46 GB OF BYTE-IDENTICAL DUPLICATES: bull-rpms is contained "
         "100 % in bullfreeware AND 100 % in ia-bullfreeware. Sorted so the copies are adjacent, "
         "a solid block collapses them to about 70 GB -- which is why this unit must never be "
         "-m0, whatever its rpm share suggests. Bull closed in 2022, so that half is finished "
         "forever. `biblionik-goupil` is the other half of the same French host, 37 files of "
         "bootable SMT Goupil G3 images -- not Bull machines, but one server, one operator and "
         "one risk, an EOL CentOS 7 box serving HTTP only. "
         "-m3 IS A COMPROMISE AND NAMED AS ONE: the documentation third wants -m5 and is the only "
         "text-rich body in the collection, the Bull third only needs the solid block that any "
         "method above 0 provides, and the media third is already compressed. Three settings "
         "cannot apply to one unit, so the middle one does."),

    Unit("ibm-aix-opensource", ["oss4aix.org"],
         "208 GB that is 100 % rpm. Stored rather than compressed: there is nothing to win and "
         "-m0 turns the longest packing job in the plan into a copy. NOT folded into ibm-aix-support "
         "on 2026-10-04 although the subject is the same, because -m0 and -m3 are the difference "
         "between a copy and a day of CPU, and this archive holds no internal duplication for a "
         "solid block to find -- it appears in none of b2-cluster.py's sharing pairs. "
         "`rwth-aachen-ftp` LEFT ON 2026-10-03 and the unit's own sentence is why: this one is "
         "all rpm, and that archive held none -- 41 % exe, 25 % zip, 17 % pdf -- so it was being "
         "stored under a rule written for somebody else's content. It shared 0.00 GB with this "
         "unit and 6.30 GB with ibm-pc, where it now is."),

    # ---------------------------------------------------------------- IBM PC, PS/2 and OS/2
    Unit("ibm-pc", ["ps-2.kev009.com", "ardent-tool", "mcamafia", "rwth-aachen-ftp",
                    "fsck-ibm-other", "os2bbs", "zx-hobbes-os2", "infania-unixos2",
                    "dreamlandbbs-os2"],
         "530 GB of IBM personal-computer material: the PS/2 and RS/6000 hardware trees and the "
         "OS/2 software that ran on them. Two units became one on 2026-10-04 for ONE REASON ONLY: "
         "somebody after PS/2 material wants the machine documentation and the software for it in "
         "the same unpack. Measured, it saves no recovery volumes at all -- 39 + 15 apart, 54 "
         "merged -- and no duplication either, because the two halves share nothing above a "
         "gigabyte. The subject is the whole argument, and it is enough. "
         "THE HARDWARE HALF SHARES 16.60 GB WITH ITSELF: ardent-tool is 75 % contained in "
         "ps-2.kev009.com, which redirects its own ohlandl/ subtree there. `mcamafia` is 170 MB of "
         "Peter Wendt's PS/2 technical-reference scans, the same subject and very likely "
         "overlapping. `rwth-aachen-ftp` joined on 2026-10-03 and four separate readings agreed: "
         "0.00 GB shared with its old unit against 6.30 GB here -- 62 % of its own 10.16 GB, "
         "8 490 files of it with ps-2.kev009.com alone. "
         "ps-2.kev009.com REACHED A FIXED POINT ON 2026-10-04 at 216 142 files and 353.58 GB: "
         "every name a held page gives is held or recorded as gone."),

    # ---------------------------------------------------------------- bitsavers
    Unit("bitsavers", ["bitsavers"],
         "1196.66 GB in 176 028 files -- the whole mirror, and the largest unit by a long way. "
         "844 GB of it is scanned paper (pdf, magazines), holding the largest single files in the "
         "collection; the rest is software: bits, components, projects, test_equipment, "
         "communications and two dozen small branches. "
         "THREE UNITS BECAME TWO ON 2026-10-04 AND TWO BECAME ONE ON 2026-10-07, each time "
         "because the reason for the split had expired. `bitsavers/magazines` first stood alone "
         "because it grows a few scans at a time and a multi-volume RAR cannot be appended to -- "
         "after B2 nothing is appended to anything. Paper and software then stood apart because "
         "they are different kinds of thing, which is true and turned out not to matter: the "
         "measured difference was 36 .rev files either way. "
         "WHAT DECIDED IT IS UPDATING, which is the owner's reason and the only one that survives "
         "contact with the next five years: bitsavers is the one mirror here that changes "
         "constantly, so it is the one that will be re-fetched and re-packed. A split meant two "
         "packs, two sets of manifests and a subtraction (`bitsavers` MINUS the paper subtrees) "
         "that had to be got right every time -- and a new top-level directory upstream landing "
         "on the correct side of it. One directory, one unit: there is nothing to get right. "
         "THE PRICE IS A 1.2 TB UNIT, which is sizeable to fetch back. It costs less than it "
         "looks: the solid stream runs through the whole set anyway, so even the old 844 GB unit "
         "had to be fetched from its first volume. 337 volumes rather than 238 plus 100."),

    # ---------------------------------------------------------------- multi-vendor collections
    Unit("vendors", ["fsck-vendors", "vtda"],
         "638 GB from the two large multi-vendor dumps. They share 13.46 GB of byte-identical "
         "files, which a solid block now collapses INSTEAD OF STORING TWICE -- that pair was the "
         "single biggest across-unit duplication in the whole plan. It saves no .rev files "
         "-- 41 + 24 apart, 65 merged -- so those 13.46 GB are the entire byte gain, and they are "
         "the largest one the regrouping produced. "
         "A reader after one vendor's material gets 638 GB instead of 404, which is the trade the "
         "owner named: `wenige GB mehr keine Rolle`."),

    Unit("oldskool", ["oldskool"],
         "149 GB of PC gaming and demo-scene material. Alone because it shares almost nothing "
         "with anything -- 1.17 GB with bitsavers and nothing else above a gigabyte -- and "
         "because no other unit's subject reaches it."),

    # ---------------------------------------------------------------- other platforms
    Unit("workstations", ["irixnet-ftp", "zx-sgi-freeware-old", "sgidepot",
                          "dec-ftp-2006", "zx-gatekeeper-dec", "zx-ultrix-freeware",
                          "zx-kednos-vms", "hp-openvms-2008", "somuchstuff-pdp8",
                          "decromancer-bits", "next-68k-org", "nice-next"],
         "169 GB of non-IBM Unix workstations: SGI/IRIX, the whole DEC lineage from PDP through "
         "VAX, Ultrix and VMS -- including the HP-era OpenVMS tree, which belongs to DEC's "
         "lineage rather than to HP's -- and NeXT. "
         "THREE UNITS OF 61, 70 AND 39 GB BECAME ONE, and that is worth exactly nothing in "
         "recovery volumes: 18 apart, 18 merged. It WAS the largest saving in an earlier draft of "
         "this plan, which assumed 24.2 GB volumes and three wasted floors; the volume size "
         "changed to 995 MB and this justification had to change with it. What remains is that "
         "three uploads became one, and that nobody after a Unix workstation should have to guess "
         "which of three units holds it. "
         "-m3 because the DEC third is 26 % uncompressed containers and worth more than the "
         "default effort; SGI and NeXT lose nothing by it. "
         "`zx-sgi-freeware-old` closed on 2026-10-03 at 5 702 files against the operator's own "
         "sitemap, 5 699 of 5 699."),

    Unit("misc", ["develooper-hpux", "hp-labs-2007", "hp-alphaserver-2008", "agilent-ftp-2009",
                  "zx-alphant-nt", "parisc-firmware", "apollo-clavius", "infania-solaris",
                  "sun3arc", "novasareforever-aviion", "ndwiki-norsk-data",
                  "transputer-classiccmp", "wotug-inmos", "zx-microway", "zx-be-os", "mpoli-bbs",
                  "square7-vintage", "giga-nl-walter", "abc-bladet", "adoxa-dos", "bretjohnson",
                  "dialectronics", "csiph-gallery", "infania-os-history", "ultimate-fastpath",
                  "hp-labs-linux-salvage", "vgamuseum-doc", "obsolyte", "fjkraan", "chipdb",
                  "iommu", "retro-digitalvintage", "kib-x86docs", "seds-frommert",
                  "acpc-amstrad", "openpa",
                  "tuhs", "ibiblio-historic-linux", "crashing-org", "crashing-org-kernel",
                  "crashing-org-www", "penguinppc", "debian-powerpc-boot", "ibiblio-ppc-ports",
                  "devicetree-openfirmware", "linuxfoundation-refspecs", "sco-devspecs",
                  "sco-gabi", "technologists-dellunix", "technologists-sauer", "cryp-to-cwg"],
         "144 GB in 51 archives: HP-UX, Alpha, PA-RISC, Apollo, Solaris, Data General, Norsk "
         "Data, transputers, BeOS, x86 chip documentation, a dozen one-person sites, and the Unix "
         "and early-Linux history trees. THE DELIBERATE REMAINDER -- each too small to upload on "
         "its own and belonging to no platform in particular. Merged with unix-history on "
         "2026-10-04 for one .rev file and for the obvious reason: two remainder units are one "
         "remainder unit's worth of subject. "
         "THE FOUR x86 DOCUMENTATION ARCHIVES STAYED HERE against b2-cluster.py's own --propose "
         "output, which wanted `chipdb`, `iommu`, `kib-x86docs` and `vgamuseum-doc` moved to the "
         "PC unit. Measured, the move is worth about 2.6 GB: those four duplicate EACH OTHER "
         "-- iommu and kib-x86docs alone share 9.00 GB -- so that duplication is already inside "
         "one unit, and most of what is left is shared with bitsavers, which 1.2 TB cannot be "
         "merged with. An advisory clustering is not a reason to break a subject. "
         "`vgamuseum-doc` is the exception that had to be argued: at 3.44 GB it is not small, and "
         "it is coherent rather than leftover -- cross-vendor graphics-card documentation, from "
         "IBM GXT and the RS/6000 adapter books through DEC ZLXp, Sun TechSource and the INMOS "
         "databook to PC chipsets. It is here BECAUSE it belongs to no single platform, which is "
         "what this unit is for; putting it with IBM would have buried the DEC, Sun and SGI half "
         "of it under the wrong subject. `openpa` holds Paul Weissmann's original PA-RISC and HP "
         "9000 articles, under 50 MB, and its doc/ prefix is excluded in mirror.py -- every path "
         "under it answered 404 from three separate addresses."),
)

# The index archive is not one of the units: it is the thing you fetch INSTEAD of a unit.
INDEX_OPTIONS = DEFAULTS.with_(method=5, dictionary="64m", solid_per_volume=False,
                               volume_bytes=None, recovery_record="10")


def sort_key(row):
    """(extension, size, digest, path) -- the ordering that makes duplicates collapse.

    Two byte-identical files necessarily agree on all three leading keys, so they land next to
    each other and even a small dictionary sees the repeat. The extension leads so that similar
    files sit together where there are no exact duplicates, which was the other half of the point.
    """
    path = row["path"]
    base = path.rsplit("/", 1)[-1]
    ext = base.rsplit(".", 1)[1].lower() if "." in base else ""
    return (ext, row["size"], row["digest"], path)


def archive_rows(root, archive):
    """-> [{archive, path, size, digest}] for one mirror, via `common.read_index`.

    WHY THE LIBRARY'S READER AND NOT A LOCAL ONE. `common.read_index` is the reader every other
    tool here uses, and duplicating it is the drift this library exists to end -- a check in
    `common_test.py` catches exactly that, and caught it here.

    AND WHERE THIS TOOL MUST DISAGREE WITH IT. `read_index` returns `{}` for a missing or damaged
    index ON PURPOSE: for every other caller the index is a cache, every row is revalidated against
    the file it describes, and rehashing is the right answer. For a PACKING PLAN it is the opposite.
    An empty result here means a unit that quietly contains nothing, an archive that is quietly not
    in cold storage, and an upload that is quietly smaller than it should be -- which reads as good
    compression. So `main()` checks every index exists before planning, and refuses.
    """
    rows = read_index(os.path.join(root, archive, INDEX_FILE))
    return [{"archive": archive, "path": path.replace("\\", "/"),
             "size": size, "digest": (digest or "").strip()}
            for path, (size, _mtime, digest) in rows.items()]


def bookkeeping_for(unit, root, rows):
    r"""-> the unit's OWN files, which the index deliberately leaves out.

    THE ARCHIVE MUST CARRY ITS OWN FIXITY RECORDS OR IT CANNOT BE CHECKED. `.sha256sum`,
    `.sha1sum`, `.md5sum` and `.sfv` are dotfiles in `common.BOOKKEEPING_FILES`, and `mirror.py`
    keeps them OUT of `.mirror-index.csv` on purpose: the index describes the CONTENT, and
    counting our own notes as content would make every marker wrong. That rule is right for the
    collection and wrong at the moment of packing, where the notes are the most valuable small
    thing in the tree.

    WITHOUT THIS, A RESTORED UNIT COULD ONLY BE CHECKED AGAINST SHA-256 -- the unit index carries
    that one digest per file and nothing else. The four manifests were built and cross-checked
    over four days across 1.8 million files; SHA-1, MD5 and CRC32 would simply not survive.
    Measured on 2026-10-05: 838 such files exist across the collection and only 18 of them are in
    any index, so 820 would have been left behind.

    THEY GO INTO THE @list AND NOT INTO THE UNIT INDEX, the same way empty directories do. The
    index's columns are archive, path, size and sha256, and these files have no sha256 recorded
    anywhere -- writing them in with an empty digest would put a row in the index that no auditor
    could act on.

    WHAT IS ALREADY INDEXED IS NOT ADDED TWICE. Some notes do appear in an index -- RENAMED.txt in
    all seven archives that have one, FRAGMENT-COPIES-REMOVED.txt in four, five of the thirteen
    CONVERGED.md -- because the WIDE bookkeeping set is skipped by auditors but still counted by
    markers. So the test is per file and against this unit's own rows, not against a list of names.
    """
    held = set((r["archive"], r["path"]) for r in rows)
    out = []
    for archive in unit.archives():
        for name in sorted(BOOKKEEPING_FILES):
            if name.endswith(".tmp"):
                continue
            if (archive, name) in held:
                continue
            if os.path.isfile(os.path.join(root, archive, name)):
                out.append("%s/%s" % (archive, name))
    return out


def rows_for(unit, root, cache=None):
    """-> the unit's files, in packing order."""
    rows = []
    for archive in unit.archives():
        got = cache.get(archive) if cache is not None else None
        if got is None:
            got = archive_rows(root, archive)
            if cache is not None:
                cache[archive] = got
        rows.extend(r for r in got if unit.claims(r["archive"], r["path"]))
    rows.sort(key=sort_key)
    return rows


# WHERE Rar.exe USUALLY IS. The list is this tool's; deciding whether a name is there is not --
# that is common.find_tool(), which iso-second-opinion.py's 7-Zip probe shares since 2026-09-27.
# `Rar.exe` and not `WinRAR.exe`: the GUI binary opens a window and ignores a command line.
RAR_CANDIDATES = (r"C:\Program Files\WinRAR\Rar.exe", "rar", "Rar.exe")


def fixity_over(folder, work, report=say):
    r"""Write the four manifests for the PACKED ARTEFACTS in `folder`. -> True when they are there.

    THE GAP THIS CLOSES. Every check before this one is about what is INSIDE the archive: `rar t`
    decompresses the members, the CRC32 cross-check holds their stored checksums against our own
    `.sfv`, and `<unit>.index.csv` lists them with their digests. NOTHING described the .rar
    volumes THEMSELVES. After an upload, a corrupted volume could only be found by unpacking it.

    THROUGH PyFixity AND NOT A FOURTH IMPLEMENTATION. `../PyFixity/pyfixity.py index` reads every
    file once, computes SHA-256, SHA-1, MD5 and CRC32 in a single pass, and writes
    `.sha256sum .sha1sum .md5sum .sfv` at the root of the tree it is given -- the same four this
    collection carries everywhere, in the same formats `sha256sum -c`, `md5sum -c` and QuickSFV
    read. It is the tool the three ibm-aix tars were given on 2026-10-06, and writing a fifth
    digest pass here would be the drift this project keeps a shared library to avoid.

    THE INDEX GOES TO THE WORK DIRECTORY, not into the tree. PyFixity's own documentation says so
    -- "It changes on every check, so keep it OUTSIDE a tree that gets uploaded or synced" -- and
    this tree is the one that gets uploaded.

    IT COVERS WHAT GOES TO B2 AND NOTHING ELSE: the volumes, the .rev files and
    `<unit>.index.csv`, all in one flat directory, with `*.log` excluded. One `.sha256sum` beside
    them is what makes an upload verifiable without fetching 101 GB back -- and the owner uploads
    that directory as it stands, so a manifest naming a file he does not upload would be a
    manifest that fails on the far side.
    """
    tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "PyFixity", "pyfixity.py")
    if not exists(tool):
        report("  no PyFixity at %s -- the archive's own checksums were NOT written" % tool)
        return False
    index = os.path.join(work, os.path.basename(folder.rstrip("\\/")) + ".fixity.csv")
    started = time.time()
    # THE LOGS ARE EXCLUDED, which is the owner's decision of 2026-10-06: he stripped their lines
    # out of the manifests by hand. A manifest describes the UPLOADABLE set -- the volumes, the
    # .rev files and the index CSV -- and `pack.log` is a local record of how they came to be, 82
    # to 95 MB of one line per file. Covering it would also make the manifest go stale the moment
    # a run appended to the log.
    done = subprocess.run([sys.executable, tool, "index", folder, "--index", index,
                           "--exclude-glob", "*.log"],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = done.stdout.decode("utf-8", "replace")
    if done.returncode != 0:
        report("  PyFixity exited %d -- the archive's own checksums were NOT written"
               % done.returncode)
        for line in [one for one in text.splitlines() if one.strip()][-6:]:
            report("       %s" % line.strip()[:110])
        return False
    # THE FOUR NAMES FROM THE LIBRARY. A list written out here would keep passing after a rename
    # while PyFixity wrote the new spelling, and this check would then report success over four
    # files that are not there.
    missing = [MANIFEST_FILES[algorithm] for algorithm in DIGESTS
               if not exists(os.path.join(folder, MANIFEST_FILES[algorithm]))]
    if missing:
        report("  PyFixity reported success but %s are not there" % ", ".join(missing))
        return False
    report("  the archive's own four manifests are beside it (%.0fs)" % (time.time() - started))
    return True


def fixity_work_for(step):
    r"""-> the directory PyFixity may use as scratch for this step. Never `dirname(None)`.

    THE BUG THIS REPLACES A TEXT SEARCH FOR. The call site used to read
    `os.path.dirname(step["index_path"])` directly, which raises TypeError on the index archive's
    step because that step has no index to place -- and it raised it AFTER vendors had packed
    399 GB, passed `rar t` and passed the cross-check. A guard was added at the call site and a
    test asserted the guard by searching b2-pack.py's own source for it, which pinned the shape of
    the code rather than what it has to do. This function is the thing to ask instead.
    """
    if step.get("index_path"):
        return os.path.dirname(step["index_path"])
    return step["cwd"]


def place_index_beside(step, report=say):
    r"""Copy the unit's own index CSV next to its volumes. -> the destination, or None.

    WHY IT IS COPIED AND NOT MOVED. The work directory's copy is what the NEXT unit's index
    archive is built from -- `rar a ... *.index.csv` over all ten -- so taking it away would
    quietly empty that archive. Both copies exist on purpose.

    AND WHY IT IS NOT LEFT PACKED. The CSV is already inside the archive, as the last argument of
    the pack command, so a unit describes itself. But reading it there costs unpacking a 101 GB
    set, and the whole point of the file is to answer "what is in misc" without fetching misc. The
    owner's instruction on 2026-10-06: upload it beside the volumes, unpacked, every time. 52 MB
    against 101 GB, readable in a browser, and it carries archive, path, size and sha256 for every
    file -- enough to verify any single extracted file afterwards.

    IT NEVER OVERWRITES. A destination that is already there and identical is reported and left;
    one that differs is a REFUSAL, because two different indexes for one archive means one of
    them describes something else and the tool cannot tell which.
    """
    source = step.get("index_path")
    if not source or not exists(source):
        return None
    # BESIDE THE VOLUMES AND IN THE SAME DIRECTORY, which is the shape the owner built by hand on
    # 2026-10-06 and the one he uploads: `<out>/<unit>/` holding the .rar, the .rev, the index CSV
    # and the four manifests, all flat. An earlier version put the index one level up, on the
    # assumption that the volumes had a directory of their own -- they do, and it IS the unit's.
    folder = os.path.dirname(step["archive"])
    target = os.path.join(folder, os.path.basename(source))
    if exists(target):
        if filecmp.cmp(long_path(source), long_path(target), shallow=False):
            report("  the index is already beside the volumes: %s" % target)
            return target
        report("  REFUSING to replace a DIFFERENT index already at %s" % target)
        return None
    try:
        shutil.copy2(long_path(source), long_path(target))
    except OSError as problem:
        report("  cannot place the index beside the volumes: %s" % problem)
        return None
    if not filecmp.cmp(long_path(source), long_path(target), shallow=False):
        report("  the copied index does not match its source -- %s" % target)
        return None
    report("  index placed beside the volumes: %s (%s)"
           % (target, human(os.path.getsize(long_path(target)))))
    return target


def free_memory():
    r"""-> free physical bytes, or None where it cannot be asked.

    THROUGH ctypes AND THE STANDARD LIBRARY ONLY, because this project has no dependencies and a
    packing run must not acquire one in order to tell the truth about why it died.

    WHY IT IS ASKED AT ALL. On 2026-10-06 a workstations run was killed before it wrote a single
    volume: 0.52 GB free of 63.34 GB, with an editor holding 39.59 GB. The run had not reached
    Rar.exe, so nothing in its own output said anything about the cause -- and the same shape six
    hours into a 638 GB unit would have wasted the six hours. The free DISK space has been in the
    plan from the beginning; this is the other resource a pack can run out of.
    """
    if os.name != "nt":
        try:
            with io.open("/proc/meminfo") as handle:
                for line in handle:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            return None
        return None
    try:
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        status = Status()
        status.dwLength = ctypes.sizeof(Status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullAvailPhys)
    # NAMED EXCEPTIONS AND NOT `Exception`, which common_test.py refuses for a reason this very
    # function proves: a bare catch here would have swallowed a misspelled field name in Status
    # and reported "cannot tell how much memory is free" for a bug in this file. AttributeError is
    # the honest one to expect -- `ctypes.windll` does not exist off Windows -- and OSError covers
    # the call itself failing.
    except (AttributeError, OSError, ValueError):
        return None


def memory_estimate(dictionary):
    r"""-> rar.txt's rough figure for packing with `dictionary`, in bytes, or None.

    TWO POINTS AND A STRAIGHT LINE BETWEEN THEM, which is all the documentation offers: about
    7 GB for a 1 GB dictionary and about 96 GB for 64 GB, both called "grob geschaetzt" there.
    That is roughly 1.4 GB of memory per GB of dictionary, so 4g lands near 12 GB.

    AND MEASURED AT 10.00 GB FOR 4g, on 2026-10-06, during the workstations run -- so the line is
    slightly high rather than wrong, which is as much as two rough points can be asked for.

    WHAT THE SAME MEASUREMENT SETTLED ABOUT *WHEN*: Rar.exe held 0.19 GB while `-oi1` pre-hashed
    420 307 files and 10.00 GB once compression started. The dictionary is allocated when the
    first block is compressed, not at launch -- so a run that looks harmless in its first minutes
    is not yet the run whose memory matters, and the figure to watch is the one after the first
    volume appears.
    """
    want = parse_size(dictionary) if dictionary else 0
    if not want:
        return None
    gb = want / float(1 << 30)
    return int((7.0 + (gb - 1.0) * (96.0 - 7.0) / (64.0 - 1.0)) * (1 << 30))


def memory_complaint(dictionary, free=None):
    r"""-> a complaint about there being too little memory, or None.

    THE REFUSAL IS AT A FLOOR NOTHING CAN ARGUE WITH: less free memory than the dictionary itself.
    A 4 GB window cannot live in 3 GB, whatever an estimate says.

    AND NOT AT THE ESTIMATE, deliberately. memory_estimate() interpolates between two figures
    rar.txt itself calls rough, and refusing a run on an interpolation between two estimates would
    stop a pack that would have worked. Above the floor the numbers are printed and the decision
    is the owner's -- he is the one who knows whether the editor holding 39 GB is about to close.
    """
    if free is None:
        free = free_memory()
    if free is None:
        return None
    want = parse_size(dictionary) if dictionary else 0
    if want and free < want:
        return ("only %s of memory free, which is less than the %s dictionary itself -- packing "
                "would fail or page" % (human(free), dictionary))
    return None


def memory_note(dictionary, free=None):
    """-> one line for the plan: what is free, and the documented estimate for this dictionary."""
    if free is None:
        free = free_memory()
    if free is None:
        return "cannot tell how much memory is free"
    guess = memory_estimate(dictionary)
    if guess is None:
        return "%s of memory free" % human(free)
    return ("%s of memory free; rar.txt's two rough estimates put a %s dictionary near %s"
            % (human(free), dictionary, human(guess)))


def find_rar(candidates=RAR_CANDIDATES):
    """-> the first candidate that answers, or None. Nothing is packed without one."""
    return find_tool(candidates)


def empty_directories(root, archive, unit):
    r"""-> [relative path] of directories holding neither a file nor a subdirectory.

    THE ONE THING THE INDEXES CANNOT ANSWER. `.mirror-index.csv` lists FILES, so a directory that
    holds nothing is invisible to every other check here -- including the partition test, which is
    otherwise what makes this plan trustworthy. There are 281 of them across 9 archives, and a file
    list made only of files would have dropped every one without a word.

    Found while reading WinRAR 7.30's changelog, whose new `-ed1` switch is about exactly this
    distinction. Nothing in the changelog applies to this plan; the question it raised does.

    RAR stores a directory named in a list file as a folder entry, measured -- so appending these
    paths is the whole fix. A missing parent is created on extraction, so only the leaf is needed.
    """
    out = []
    base = os.path.join(root, archive)
    for dirpath, dirnames, filenames in os.walk(base):
        if filenames or dirnames:
            continue
        # relative_to AND NOT os.path.relpath, which NORMALISES and strips a trailing dot.
        # No empty directory in the collection ends in one today -- measured 2026-10-03,
        # zero of them -- so this is a latent case rather than a live one. It is changed
        # anyway because this tool writes the archive that is never modified again, and
        # four other files in this directory already carry a comment about this exact
        # defect while three call sites still had it.
        rel = relative_to(base, dirpath)
        if rel != "." and unit.claims(archive, rel):
            out.append(archive + "/" + rel)
    return sorted(out)


def volume_count(size, options):
    """-> how many .rar volumes a unit of `size` bytes needs, recovery record included.

    The record inflates the archive BEFORE it is split, so leaving it out under-counts the volumes
    -- and that count decides both the number of discs and the number of .rev files.
    """
    if not options.volume_bytes:
        return None
    grown = size * (1.0 + float(options.recovery_record or 0) / 100.0)
    return int(math.ceil(grown / options.volume_bytes))


def plan(units, root, out, work, rar="rar", with_dirs=True):
    """-> [{unit, argv, cwd, list_path, index_path, rows}] plus the index archive last.

    NO PASSWORD APPEARS HERE. `-hp` is added only in `execute()`, from a file, so a plan can be
    printed, pasted into a report or committed without leaking one.
    """
    steps = []
    cache = {}
    for unit in units:
        rows = rows_for(unit, root, cache)
        dirs = []
        if with_dirs:
            for archive in unit.archives():
                dirs.extend(empty_directories(root, archive, unit))
        list_path = os.path.join(work, unit.name + ".list")
        index_path = os.path.join(work, unit.name + INDEX_SUFFIX)
        archive = os.path.join(out, unit.name, unit.name + ".rar")
        size = sum(r["size"] for r in rows)
        volumes = volume_count(size, unit.options)
        # THE INDEX CSV LANDS INSIDE THE ARCHIVE AS `tar\<unit>.index.csv` AND THAT IS DELIBERATE.
        # It is passed by ABSOLUTE path, and RAR then stores every component below the drive
        # letter -- `X:\tar\misc.index.csv` becomes `tar\misc.index.csv`. The same behaviour is
        # why WORK_MUST_BE_FLAT: a work directory under a profile would write the account name
        # into every archive.
        #
        # THE THREE WAYS TO MAKE IT TOP-LEVEL WERE LOOKED AT ON 2026-10-07 AND NONE IS WORTH IT.
        # `-ep` strips ALL paths, which for a unit of 342 386 entries means basenames colliding
        # and overwriting each other on extraction, with `rar t` reporting "Alles OK" over it.
        # `-ap<path>` applies to every file in the command, so it would move the 342 385 from the
        # list as well. And adding the CSV in a second `rar a` with cwd=<work> would have to
        # happen BEFORE `-k`, which means locking afterwards -- measured as fatal: a later
        # `rar k` reported every volume as a checksum failure and recovery as impossible.
        #
        # SO IT STAYS, on the owner's reasoning: `tar/` is then a named place inside the archive
        # that more can go into later, which is worth more than a flat name obtained by any of
        # the above. The copy beside the volumes is the one a reader actually uses.
        argv = ([rar, "a"] + unit.options.switches(volumes)
                + [archive, "@" + list_path, index_path])
        steps.append({"unit": unit, "argv": argv, "cwd": root, "list_path": list_path,
                      "index_path": index_path, "archive": archive, "rows": rows,
                      "volumes": volumes, "recovery_volumes": unit.options.recovery_volumes(volumes),
                      "empty_dirs": dirs, "bookkeeping": bookkeeping_for(unit, root, rows)})
    index_archive = os.path.join(out, INDEX_DIR, "index.rar")
    # THE CWD IS THE WORK DIRECTORY, NOT THE OUTPUT ONE. `write_list()` puts each unit's index at
    # `<work>/<unit>.index.csv`, so that is the only place `*.index.csv` matches. Pointing the cwd
    # at the archive's own directory -- which is what this step did until 2026-10-09 -- globs an
    # empty or absent directory and packs nothing. It was never caught because the step crashed
    # earlier, in `write_list()`, in every `--execute` run ever made.
    steps.append({"unit": None, "argv": [rar, "a", "-ep"] + INDEX_OPTIONS.switches()
                  + [index_archive, "*" + INDEX_SUFFIX],
                  "cwd": work, "list_path": None, "index_path": None,
                  "archive": index_archive, "rows": [],
                  # Every step carries the same keys, so a caller never has to ask which kind it
                  # is before reading one. The index archive has no volumes and no directories.
                  "volumes": None, "recovery_volumes": 0, "empty_dirs": [], "bookkeeping": []})
    return steps


def write_list(step, dry_run=True):
    r"""The `@list` file and the unit's index, both OUTSIDE the collection.

    THE INDEX ARCHIVE HAS NEITHER AND THAT CRASHED EVERY --execute RUN THERE HAS BEEN. It packs
    `*.index.csv` by wildcard rather than from a list, so both paths are None and
    `os.path.dirname(None)` raised TypeError -- after the unit had packed, passed `rar t` and
    passed the cross-check. misc, vendors and oldskool all ended that way, each with exit 1 and a
    traceback nobody read, because the archive was finished and correct by then and the three
    checks had already said so.

    THE INDEX ARCHIVE WAS THEREFORE NEVER BUILT. That is the real cost: the small archive that
    bundles every unit's `*.index.csv`, the one meant to be fetched INSTEAD of a unit. It only
    matters once all ten exist, which is why nothing missed it.

    AND I BLAMED MY OWN CODE FOR IT FIRST. The vendors traceback named `write_list` and I read it
    as a guard I had left out in `fixity_over` an hour earlier -- committed that as the cause, and
    was wrong. The line numbers in that traceback pointed at comments, because the file had been
    edited while the run was going, and I read the names rather than checking which call actually
    raised.
    """
    if dry_run:
        return
    if not step.get("list_path") or not step.get("index_path"):
        return
    for path in (step["list_path"], step["index_path"]):
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
    with io.open(step["list_path"], "w", encoding="utf-8", newline="\n") as fh:
        for row in step["rows"]:
            fh.write("%s/%s\n" % (row["archive"], row["path"]))
        # LAST, AND AS DIRECTORIES. They carry no bytes, so their position cannot disturb the
        # solid ordering the files were sorted into, and putting them at the end keeps that
        # ordering readable as exactly what sort_key produced.
        # THE UNIT'S OWN RECORDS, before the empty directories. Their position cannot disturb the
        # solid ordering the content was sorted into -- they are a few hundred small files at the
        # end of a stream of hundreds of thousands.
        for path in step["bookkeeping"]:
            fh.write(path + chr(10))
        for path in step["empty_dirs"]:
            fh.write(path + chr(10))
    with io.open(step["index_path"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write("archive,path,size,sha256\n")
        for row in sorted(step["rows"], key=lambda r: (r["archive"], r["path"])):
            fh.write("%s,%s,%d,%s\n" % (row["archive"], row["path"], row["size"], row["digest"]))


def report(steps, verbose=False, stream=None):
    total_bytes = 0
    total_files = 0
    total_discs = 0
    for step in steps:
        unit = step["unit"]
        if unit is None:
            say("", stream=stream)
            say("=== the index archive -- fetch this INSTEAD of a unit ===", stream=stream)
            say("  %s" % " ".join(step["argv"]), stream=stream)
            say("  cwd  %s" % step["cwd"], stream=stream)
            continue
        size = sum(r["size"] for r in step["rows"])
        total_bytes += size
        total_files += len(step["rows"])
        # FILES, NOT DISCS, and the two stopped being the same thing on 2026-10-04. A volume was
        # 24.2 GB and filled one BD-RE, so counting volumes counted discs; at 199 MiB a 25 GB
        # M-Disc holds 119 of them. The figure a reader needs now is how many FILES go to B2, and
        # the disc count is that divided by PER_M_DISC.
        files_out = step["volumes"] + step["recovery_volumes"]
        total_discs += files_out
        say("", stream=stream)
        extra = ("  + %d empty dir(s)" % len(step["empty_dirs"])) if step["empty_dirs"] else ""
        if step["bookkeeping"]:
            extra += "  + %d own record(s)" % len(step["bookkeeping"])
        say("=== %-22s %10s  %7d files%s  %4d vol + %d rev = %4d file(s) ==="
            % (unit.name, human(size), len(step["rows"]), extra, step["volumes"],
               step["recovery_volumes"], files_out), stream=stream)
        say("  %s" % " ".join(step["argv"]), stream=stream)
        say("  cwd  %s" % step["cwd"], stream=stream)
        if verbose:
            say("  why  %s" % unit.why, stream=stream)
            for row in step["rows"][:8]:
                say("       %12d  %s/%s" % (row["size"], row["archive"], row["path"]),
                    stream=stream)
            if len(step["rows"]) > 8:
                say("       ... %d more" % (len(step["rows"]) - 8), stream=stream)
    say("", stream=stream)
    say("%d unit(s), %s, %d files in, %d file(s) out at %s per volume -- %d M-Disc(s) at %d per 25 GB"
        % (len(steps) - 1, human(total_bytes), total_files, total_discs, human(VOLUME_BYTES),
           int(math.ceil(float(total_discs) / PER_M_DISC)), PER_M_DISC),
        stream=stream)
    return total_bytes, total_files, total_discs


def coverage(units, root):
    """-> (claimed by nobody, claimed twice). The check that makes the plan trustworthy."""
    orphans = collections.Counter()
    doubles = collections.Counter()
    archives = sorted(n for n in os.listdir(root)
                      if os.path.isfile(os.path.join(root, n, INDEX_FILE)))
    for archive in archives:
        for row in archive_rows(root, archive):
            owners = [u.name for u in units if u.claims(archive, row["path"])]
            if not owners:
                orphans[archive] += row["size"]
            elif len(owners) > 1:
                doubles["%s -> %s" % (archive, ", ".join(owners))] += row["size"]
    return orphans, doubles


def hide_password(argv):
    """The plan is printed and pasted into reports; the secret never is."""
    return [a if not a.startswith("-hp") else "-hp***" for a in argv]


# `Name:` and `CRC32:` out of `rar lt`. The listing is localised -- this WinRAR answers in German
# -- but these two keys are not translated, and the values are what matters.
LT_NAME = re.compile(r"^\s*Name:\s*(.+?)\s*$")
LT_CRC = re.compile(r"^\s*CRC32:\s*([0-9A-Fa-f]{8})\s*$")


def case_collisions(rows):
    r"""-> [[path, ...]] for every set of this unit's paths that differ ONLY in case.

    BECAUSE `rar a` LOSES ONE OF THEM AND SAYS NOTHING. Measured on 2026-10-05 with a 14-byte
    a.txt and a 22-byte A.txt in a directory carrying the Windows per-directory case-sensitivity
    flag: passing the directory, passing `-r`, passing an @list, passing `-oni`, and naming both
    files explicitly ALL produced an archive with ONE entry, exit code 0, and no warning. A second
    `rar a` of the other file REPLACED the entry rather than adding it ("Erneuere data\A.txt").
    7-Zip 24.09 at least refuses -- "ERROR: Duplicate filename on disk" -- and writes nothing.

    THE ARCHIVE NAMESPACE ITSELF IS CASE-SENSITIVE, which is the odd part: on a SINGLE-volume
    archive, packing the second file under a staged name and then `rar rn`-ing it to its real name
    produced an archive holding both `data\a.txt` (14 bytes) and `data\A.txt` (22 bytes). The
    same `rar rn` against a 5-volume set printed "Fertig" and changed nothing. So the workaround
    exists and does not reach the shape this plan needs.

    WHY THIS IS A REFUSAL AND NOT A WARNING. Collection-wide on 2026-10-05: 4 542 files in 15
    archives, 3.55 GB, in 3 404 groups of two and 569 of three -- 4 028 of them in ibm-aix. `rar t`
    reports "Alles OK" over the hole, because it only checks what the archive contains. The loss is
    invisible to every check except the CRC32 cross-check against our own .sfv, which is how it was
    found. Packing 4 TB into cold storage with a known silent hole in it is the one thing this tool
    exists to prevent.

    THE MIRROR IS NOT THE PLACE TO FIX IT. Renaming there would break the one property the
    collection has -- being a faithful copy -- and would not survive a re-fetch: which member of a
    pair arrives first is not deterministic, so the rename could not be reproduced. The owner
    settled that on 2026-10-05.
    """
    folded = {}
    for row in rows:
        key = ("%s/%s" % (row["archive"], row["path"])).lower()
        folded.setdefault(key, []).append("%s/%s" % (row["archive"], row["path"]))
    return [sorted(folded[key]) for key in sorted(folded) if len(folded[key]) > 1]


def listing_text(rar, archive, cwd=None):
    r"""-> every volume's `rar lt` output, concatenated.

    ONE VOLUME AT A TIME, BECAUSE A LISTING IS NOT WHOLE. `rar lt <first volume>` on a split set
    lists ONLY the files whose headers sit in that volume -- measured on misc: part001 answered
    67 315 files, part234 answered 127, part468 answered 10, against the 342 489 the set holds. A
    check built on the first volume alone would have compared 20 % of the archive and reported
    success.

    IT IS CHEAP ENOUGH TO DO PROPERLY: headers only, no dictionary, no decompression. Measured,
    468 volumes take about 41 seconds against seven minutes for `rar t`.
    """
    parts = []
    for volume in sorted(glob.glob(glob.escape(archive[:-4]) + ".part*.rar")):
        # -scfr: UTF-8 (`f`) FOR REDIRECTED OUTPUT (`r`), and without it 350 files of misc did not
        # match. RAR writes a pipe in the system codepage by default, so a name like
        # `Embedded Pentium(R) Processor` came back with a character cp1252 could not carry and the
        # comparison called the file missing. It is the same trap as -scfl on the @list side,
        # measured on 2026-09-26 -- the charset letter for UTF-8 is `f`, and `u` is UTF-16 -- only
        # this time on the reading side, where a wrong charset reads as an archive with holes in it.
        done = subprocess.run([rar, "lt", "-scfr", os.path.basename(volume)],
                              cwd=cwd or os.path.dirname(volume) or ".",
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        parts.append(done.stdout.decode("utf-8", "replace"))
    return "".join(parts)


def crc32_from_listing(text):
    r"""-> {path with forward slashes: CRC32 upper-case} out of `rar lt` output.

    READ FROM THE ARCHIVE HEADERS, WHICH COSTS NOTHING. `rar lt` needs no dictionary and
    decompresses nothing -- measured on misc, 98.62 GB in 468 volumes, it answered in seconds
    while `rar t` took seven minutes and 3.8 GB. So this check is affordable after every unit.

    A DIRECTORY HAS A `Name:` AND NO `CRC32:`, so a pair is only taken when the CRC arrives before
    the next name. That also skips anything RAR lists without a checksum rather than guessing one.
    """
    out = {}
    name = None
    for line in text.splitlines():
        hit = LT_NAME.match(line)
        if hit:
            name = hit.group(1).replace("\\", "/")
            continue
        hit = LT_CRC.match(line)
        if hit and name is not None:
            out[name] = hit.group(1).upper()
            name = None
    return out


def crc32_expected(unit, root):
    r"""-> {archive/path: CRC32} from the `.sfv` files WE wrote, for the files this unit claims.

    THE SECOND OPINION. `rar t` proves the archive decompresses to what RAR itself recorded while
    packing; it cannot notice that RAR packed the wrong bytes, because both sides of that
    comparison come from the same read. The `.sfv` was built days earlier, by us, from the files
    on disk -- so holding RAR's stored CRC32 against it compares two independent readings of the
    same file.

    AND IT COUNTS. A CRC that matches on every file still says nothing about a file that never
    reached the archive at all, which is the failure a solid 468-volume set makes easy to miss. The
    caller compares the counts as well, and that is half the value of this check.
    """
    want = {}
    for archive in unit.archives():
        for name, crc in read_sfv(os.path.join(root, archive, SFV_FILE)):
            rel = name.replace("\\", "/")
            if unit.claims(archive, rel):
                want["%s/%s" % (archive, rel)] = crc.upper()
    return want


def crc32_complaint(unit, root, listing_text, packed_rows, want=None):
    r"""-> a complaint about the unit's CRC32s and file count, or None if everything agrees.

    THE COMPARISON IS CASE-SENSITIVE AND THAT IS THE POINT. An earlier version of this function
    folded both sides to lower case, which looked reasonable -- NTFS is case-insensitive, RAR
    stores the name the filesystem reports, so a `.sfv` entry `SPAM.wiki` matching an archive
    entry `Spam.wiki` read like a bookkeeping difference. It is not one. Measured on 2026-10-05:
    that directory carries the per-directory case-sensitivity flag, `SPAM.wiki` is 26 bytes and
    `Spam.wiki` is 30, BOTH EXIST, and the archive holds only one of them. Folding would have
    reported OK over 4 542 missing files.

    WHAT EACH NUMBER MEANS, because a mismatch here is worth reading rather than re-running:

      differs    both sides hold the file and disagree on its CRC32. Two independent reads of one
                 file, days apart, giving different bytes -- or a manifest that was never updated
                 after the file changed, which is what the first run of this check actually found.
      missing    a file the `.sfv` names that the archive does not hold. The serious one, and the
                 shape a case collision takes: `rar a` keeps one of the pair, says nothing about
                 the other and exits 0.
      ours       listed with a CRC we have no `.sfv` line for. Expected: the per-archive manifests
                 and markers packed with every unit are in no `.sfv`. Counted, not faulted.

    `want` IS AN INJECTION POINT so the comparison can be tested without a collection; left out,
    it is read from the archives' own `.sfv` files.
    """
    have = crc32_from_listing(listing_text)
    if want is None:
        want = crc32_expected(unit, root)

    # A -oi1 REFERENCE CARRIES NO CRC32 AND RAR WRITES ZEROS IN ITS PLACE. Measured 2026-10-06:
    # two identical 3 MiB files packed with -oi1 list as CB32BAFD and 00000000, and without -oi1
    # both list as CB32BAFD. The content is present either way -- `rar t` passes and extraction
    # works -- but the header of a reference has nothing to compare against.
    #
    # THE FIRST RUN WITH -oi1 REPORTED 8777 SUCH FILES IN misc AND THAT NUMBER IS THE DEDUPLICATION,
    # not damage: 8777 byte-identical duplicates collapsed into references. Reporting them as
    # "CRC32 differs" would teach a reader to ignore this check, which is the one thing it must
    # never do -- it is what found the 165 real mismatches in the first misc.rar.
    #
    # A REFERENCE IS CORRECT IF ITS TARGET IS, and that is provable here rather than assumed: the
    # reference exists only because RAR found the content byte-identical to a file it did store,
    # and our own manifests independently record the same sha256 for both. So each zero-CRC entry
    # is checked for having a partner -- a path whose .sfv CRC32 equals some entry the archive DID
    # store with a real CRC. One without a partner is a genuine complaint and stays one.
    # AN EMPTY FILE ALSO HAS CRC32 00000000, which is the trap this walked into on its first
    # attempt. 921 files in misc are 0 bytes; RAR lists them as 00000000 and our own .sfv records
    # 00000000, so the two AGREE and there is nothing to resolve. Treating every zero as a
    # reference pulled them out of the ordinary comparison and then reported them as references
    # with no target -- a complaint manufactured out of two sides that matched.
    #
    # So a zero in the LISTING is a reference only when our .sfv says something else for that
    # path: that is the case where RAR had a CRC and chose not to write it. Where both sides read
    # zero, the plain comparison is correct and handles it.
    references = sorted(k for k in have
                        if have[k] == "00000000" and want.get(k, "00000000") != "00000000")
    stored_crcs = set(v for v in have.values() if v != "00000000")
    orphan_refs = sorted(k for k in references if want.get(k) not in stored_crcs)
    for name in references:
        if name not in orphan_refs:
            have.pop(name, None)           # judged through its target, not its own header
            want.pop(name, None)

    differs = sorted(k for k in want if k in have and want[k] != have[k])
    missing = sorted(k for k in want if k not in have)
    ours = sorted(k for k in have if k not in want)
    problems = []
    if differs:
        problems.append("%d file(s) whose CRC32 differs from our own .sfv, e.g. %s"
                        % (len(differs), differs[0]))
    if missing:
        problems.append("%d file(s) in the .sfv that the archive does not hold, e.g. %s"
                        % (len(missing), missing[0]))
    if orphan_refs:
        problems.append("%d reference(s) with no stored file of the same CRC32, e.g. %s"
                        % (len(orphan_refs), orphan_refs[0]))
    if not problems:
        # THE CONTRACT IS "a complaint, or None", AND A REFERENCE COUNT IS NOT A COMPLAINT. An
        # earlier draft of this returned "OK: 8777 reference(s)" here, which the caller would have
        # read as a failure and stopped the run on -- the function's one job is to be falsy when
        # the unit is sound. The count is worth saying out loud, so it is attached for a caller
        # that wants it rather than smuggled into the complaint.
        crc32_complaint.references = len(references)
        return None
    crc32_complaint.references = len(references)
    return ("; ".join(problems)
            + " [%d listed, %d in the .sfv, %d packed rows, %d of our own records, "
              "%d -oi1 reference(s)]"
            % (len(have), len(want), packed_rows, len(ours), len(references)))


def first_volume(archive):
    r"""-> the first volume of a split set, FOUND ON DISK rather than spelled out.

    RAR USES AS MANY DIGITS AS THE VOLUME COUNT NEEDS, and this function used to assume two. The
    first real run packed misc into 468 volumes, so RAR wrote `misc.part001.rar`; `rar t` was then
    pointed at `misc.part01.rar`, answered "Kann ... nicht oeffnen" and exited 10, and the tool
    reported THE ARCHIVE DOES NOT TEST CLEAN for a 98 GB set that was perfectly intact. An alarm
    about the wrong thing is worse than no alarm, because the next one is believed less.

    SO IT ASKS THE FILESYSTEM. A glob cannot be wrong about how many digits RAR chose, and it also
    answers the case where the set has only one volume and carries no `.partN` at all. Sorting is
    lexicographic, which is correct here because RAR pads with zeros -- `part009` sorts before
    `part010` only because of that padding, and RAR guarantees it.
    """
    stem = archive[:-4] if archive.lower().endswith(".rar") else archive
    found = sorted(glob.glob(glob.escape(stem) + ".part*.rar"))
    if found:
        return found[0]
    # NOT SPLIT, OR NOT WRITTEN YET. `plan()` calls this before anything exists, and a reader of
    # the printed plan wants the name RAR will choose -- which for a set this size is three digits.
    return stem + ".part001.rar"


def check_password(text):
    r"""-> a complaint, or None. Called before anything is packed.

    NO UNIT ASKS FOR A PASSWORD ANY MORE, so nothing in the current plan reaches this. It is kept
    because the reasoning that retired it is the reasoning that would have to be reversed first.

    THE ARGUMENT RAN OUT ON 2026-10-04. One password for all nineteen units was decided on
    2026-09-26 on the grounds that the material is public and compartmenting buys nothing. The
    owner followed that to its end: if the material is public, the password protects nothing
    either, and all it adds is the one way 4 TB already on the open web could become unreadable --
    a lost key, twenty years from now.

    WHAT THIS FUNCTION GUARDS, for a unit that is ever marked encrypt_headers=True: a truncated or
    mistyped password file does not fail. It packs silently and opens with a key nobody has, and
    the mistake surfaces years later. So the shape is checked before anything is written, and
    `rar t` is run against every unit as soon as it is.
    """
    if text != text.strip():
        return "the password's line has leading or trailing whitespace"
    if not text:
        return "the password file is empty"
    if len(text) < 32:
        return ("the password is %d characters; a 64-character base64 digest was intended, and a "
                "short one usually means the wrong file or a truncated read" % len(text))
    return None


def execute(steps, rar, password):
    for step in steps:
        write_list(step, dry_run=False)
        argv = list(step["argv"])
        # THE INDEX STEP TAKES INDEX_OPTIONS, and `unit is None` is how it is recognised -- but it
        # USED TO SHORT-CIRCUIT THE WHOLE TEST: `step["unit"] is None or ...` made the index
        # archive unconditionally encrypted, whatever INDEX_OPTIONS said, and then crashed on
        # `"-hp" + None` because `wants_password` below only asks the UNITS. Found 2026-10-09, the
        # first time this step ever ran. Read the options first, then ask them.
        unit_options = step["unit"].options if step["unit"] is not None else INDEX_OPTIONS
        encrypted = unit_options.encrypt_headers
        if encrypted and not password:
            # Refusing beats packing in the clear what was marked for encryption.
            say("  %s wants encrypted headers and no password was given -- stopping"
                % (step["unit"].name if step["unit"] else "the index archive"))
            return 2
        if encrypted:
            argv.insert(2, "-hp" + password)
        parent = os.path.dirname(step["archive"])
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        say("  running %s" % " ".join(hide_password(argv)))
        result = subprocess.run(argv, cwd=step["cwd"])
        if result.returncode not in (0, 1):
            say("  rar exited %d -- stopping" % result.returncode)
            return 2

        # TESTED BEFORE THE NEXT ONE STARTS. `rar t` reads the archive back with the same password,
        # so a key that does not open it is found after ONE unit instead of after all nineteen -- and
        # it also catches a volume that did not finish writing. Reading a locked archive does not
        # modify it, so this is safe after -k and after -rv.
        target = first_volume(step["archive"]) if step["unit"] is not None else step["archive"]
        # -mdx<SIZE> OR THE TEST REFUSES TO RUN, and that is not optional at 6 GB. RAR will not
        # unpack a dictionary larger than 4 GB from the command line unless told to:
        #
        #     Ein 6 GB grosses Woerterbuch ueberschreitet die Obergrenze von 4 GB und benoetigt
        #     mehr als 6 GB Speicher zum Entpacken. Verwenden Sie die Schalter -md6g oder -mdx6g,
        #     um das Entpacken dennoch durchzufuehren.
        #
        # THE FIRST REAL RUN HIT THIS AND IT LOOKED LIKE SUCCESS. `rar t` tested the five .rev
        # files, which carry no compressed stream, printed OK five times, then said "Keine Dateien
        # zum Entpacken" and exited 2 -- so the 98 GB of content was never read at all. A check
        # that passes over the thing it was meant to check is worse than no check.
        #
        # -mdx AND NOT -md: rar.txt is explicit that -mdx applies ONLY when unpacking, so it can
        # sit in a test command without any chance of changing what a later `rar a` would write.
        test = ([rar, "t"] + (["-mdx" + unit_options.dictionary] if unit_options.dictionary else [])
                + (["-hp" + password] if encrypted else []) + [target])
        say("  testing %s" % " ".join(hide_password(test)))
        checked = subprocess.run(test, cwd=step["cwd"])
        if checked.returncode == 0 and step["unit"] is not None:
            # A SECOND OPINION, AND A COUNT. `rar t` proves the archive decompresses to what RAR
            # recorded while packing -- both sides of that comparison come from the same read, so
            # it cannot notice RAR having packed the wrong bytes, nor a file that never arrived.
            # The .sfv was built days earlier from the files themselves, so this holds two
            # independent readings against each other and counts the files while it is there.
            volumes = sorted(glob.glob(glob.escape(step["archive"][:-4]) + ".part*.rar"))
            say("  cross-checking CRC32 against our own .sfv (%d volume listing(s))"
                % len(volumes))
            # step["cwd"] IS THE COLLECTION ROOT for a unit step -- `plan()` sets it, because the
            # @list entries are relative to it. The .sfv files are read from there.
            complaint = crc32_complaint(step["unit"], step["cwd"],
                                        listing_text(rar, step["archive"]), len(step["rows"]))
            # ANY COMPLAINT STOPS THE RUN. There is no "mostly fine" here: a unit whose stored
            # CRC32s do not account for every line of its own .sfv is a unit with a hole in it,
            # and the next unit must not be packed on top of that.
            if complaint:
                say("  THE CRC32 CROSS-CHECK FAILED: %s" % complaint)
                return 2
            refs = getattr(crc32_complaint, "references", 0)
            say("  CRC32 and file count agree with the .sfv%s"
                % (" (%d -oi1 reference(s) judged through their targets)" % refs if refs else ""))
            # AFTER THE CHECKS AND NOT BEFORE. An index placed beside volumes that then failed
            # their cross-check would describe an archive nobody should use, and the file is the
            # one thing a reader trusts without opening the archive.
            place_index_beside(step)
            # AND THEN THE ARCHIVE'S OWN CHECKSUMS, last of all, because they have to cover the
            # index that was just placed. Everything before this describes what is inside the
            # archive; this describes the files that go to B2.
            # THE INDEX ARCHIVE'S STEP HAS NO index_path AND THIS CRASHED A SEVEN-HOUR RUN ON IT.
            # `os.path.dirname(None)` raises TypeError, so vendors packed 399 GB, passed `rar t`
            # and passed the cross-check, and then died before its index was placed or its
            # checksums written.
            #
            # BUT THE GUARD THEN SKIPPED THE MANIFESTS TOO, and the comment here claimed the index
            # archive "has nothing to place and nothing to describe". Half right: it has no index
            # to place, because it IS the index. It still has itself to describe -- it is uploaded
            # like any unit, and without the four manifests a corrupted `index.rar` could only be
            # found by opening it. Corrected 2026-10-09, the first time this step ran at all.
            fixity_over(os.path.dirname(step["archive"]), fixity_work_for(step))
        elif checked.returncode == 0:
            # THE INDEX ARCHIVE, WHICH CANNOT HAVE THE CROSS-CHECK AND STILL NEEDS THE MANIFESTS.
            # Its members are the units' index CSVs, written by this tool into the work directory;
            # they were never part of the collection, so no .sfv exists to hold their stored CRC32s
            # against. SAID OUT LOUD RATHER THAN SKIPPED SILENTLY: a reader comparing this log with
            # a unit's would otherwise wonder which check went missing and why.
            say("  no CRC32 cross-check for the index archive -- its members are not in the "
                "collection, so there is no .sfv to hold them against")
            say("   and the -rr10 recovery record are its checks, and the four manifests "
                "below describe the archive itself")
            fixity_over(os.path.dirname(step["archive"]), fixity_work_for(step))
        if checked.returncode != 0:
            say("  THE ARCHIVE DOES NOT TEST CLEAN (rar t exited %d) -- stopping before the next "
                "unit." % checked.returncode)
            return 2
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=MIRROR_ROOT, help="the collection (default %(default)s)")
    ap.add_argument("--out", default="out", help="where the volumes go (default %(default)s)")
    # NO DEFAULT ON PURPOSE. A relative default resolves against whatever directory the tool was
    # started from, and that path would be written inside all nineteen archives. It has to be
    # chosen, once, deliberately.
    ap.add_argument("--work", required=True,
                    help="one directory at a drive root, e.g. D:%swork -- holds the list and "
                         "index files, and its NAME is stored inside every archive" % os.sep)
    ap.add_argument("--only", action="append", help="one unit, repeatable")
    ap.add_argument("--sizes", action="store_true", help="weigh the units and stop")
    ap.add_argument("--coverage", action="store_true",
                    help="which files no unit claims, and which two units claim")
    ap.add_argument("--verbose", action="store_true", help="the reason and a sample per unit")
    ap.add_argument("--no-empty-dirs", action="store_true",
                    help="skip the walk that finds directories holding nothing. Faster, and it "
                         "DROPS 281 of them -- only for a quick look at the commands")
    # THE HELP SAID "needs --password-file" UNCONDITIONALLY AND THAT WAS NOT TRUE. No unit sets
    # encrypt_headers, because the collection is public material fetched from public hosts, so the
    # demand never fires -- and a reader who believed the old text would conclude a password had
    # to be invented for a 144 GB run that asks for none. The condition lives at the refusal,
    # where it is driven by the units; the help now says the same thing the code does.
    ap.add_argument("--execute", action="store_true",
                    help="actually pack. A unit that asks for encrypted headers also needs "
                         "--password-file; none does today")
    ap.add_argument("--password-file", help="first line is the password; never printed")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        say("no collection at %s" % args.root)
        return 2

    # WHERE THE INDEX LANDS INSIDE EVERY ARCHIVE. Measured: a file passed by absolute path keeps
    # every component below the drive letter. A deep or personal work directory would be written
    # into all nineteen archives, permanently and irreversibly once they are locked.
    parts = [x for x in os.path.abspath(args.work).replace("\\", "/").split("/")
             if x and not x.endswith(":")]
    personal = [x for x in parts if x.lower() in PERSONAL_IN_PATH]
    if personal or len(parts) > WORK_MUST_BE_FLAT:
        why = ("lies under %s" % ", ".join(personal)) if personal             else "is %d levels deep" % len(parts)
        say("REFUSING: --work %s %s, and that path is stored inside every archive."
            % (args.work, why))
        say("Use one directory at a drive root, so the index reads `work/<unit>%s`." % INDEX_SUFFIX)
        return 2

    # ARGUMENT ERRORS BEFORE FILE ERRORS. The first ordering put the missing-index check ahead of
    # this one, so `--execute` with no password file was refused for the wrong reason and the real
    # mistake never reached the reader. Cheap checks first, and each says only what it is about.
    # EVERY REFUSAL COMES BEFORE THE PLAN. Reading the indexes costs 247 MB and a minute, and the
    # first version spent both before noticing that --execute had no password file.
    # A UNIT THAT WOULD LOSE FILES IS NOT PACKED. Checked before anything is written and for
    # every unit in the plan, including on a dry run, because the figure a reader needs is the one
    # from BEFORE they spend two hours packing. See case_collisions() for what RAR does here.
    losing = []
    for unit in (UNITS if not args.only else [u for u in UNITS if u.name in set(args.only)]):
        try:
            groups = case_collisions(rows_for(unit, args.root, {}))
        except OSError:
            continue
        if groups:
            losing.append((unit.name, groups))
    if losing:
        say("REFUSING: %d unit(s) hold files whose paths differ only in case, and `rar a` stores "
            "ONE of each pair without saying so:" % len(losing))
        for name, groups in losing:
            lost = sum(len(g) - 1 for g in groups)
            say("  %-22s %4d group(s), %4d file(s) that would NOT reach the archive"
                % (name, len(groups), lost))
            for group in groups[:2]:
                for path in group:
                    say("       %s" % path)
        say("")
        say("This is measured, not suspected: see case_collisions(). Nothing is packed until the "
            "form is settled -- the mirror must stay a faithful copy, so the fix belongs in the "
            "archive, not in the collection.")
        return 2

    rar = "rar"
    # A PASSWORD IS DEMANDED ONLY IF A UNIT ASKS FOR ONE. Until 2026-10-04 every unit did, and
    # --execute refused without --password-file. The collection is public material fetched from
    # public hosts, so encryption protects nothing and adds the one way this could become
    # unreadable: a lost key. The demand is kept, driven by the units themselves, so a unit that
    # is one day marked encrypt_headers=True cannot be packed in the clear by accident.
    wants_password = args.execute and (INDEX_OPTIONS.encrypt_headers
                                       or any(u.options.encrypt_headers for u in UNITS))
    if args.execute:
        if wants_password and not args.password_file:
            say("--execute needs --password-file: a unit asks for encrypted headers, and the "
                "password is never a command-line argument")
            return 2
        # AND BELOW THE FLOOR IT REFUSES, before a six-hour run starts. The floor is the
        # dictionary size itself, which no estimate can argue with; everything above it is the
        # owner's call and printed rather than enforced.
        short = memory_complaint(DEFAULTS.dictionary)
        if short:
            say("REFUSING: %s" % short)
            say("  Close what is holding it, or pass a unit whose options use a smaller "
                "dictionary.")
            return 2
        rar = find_rar()
        if rar is None:
            say("REFUSING TO RUN: no rar executable found.")
            return 2

    units = UNITS
    if args.only:
        wanted = set(args.only)
        # `--only index` SELECTS THE INDEX ARCHIVE AND NO UNITS. It is the last step of every plan
        # and the only one that is not a unit, so there was no way to ask for it alone -- and it is
        # the step most likely to be wanted alone, because it is rebuilt whenever ANY unit is
        # repacked while the other eight archives stay as they are. `index` cannot collide with a
        # unit name: `UNITS` is checked for it below, which fails the gate rather than a run.
        index_only = INDEX_DIR in wanted
        wanted.discard(INDEX_DIR)
        unknown = wanted - set(u.name for u in UNITS)
        if unknown:
            say("no such unit: %s" % ", ".join(sorted(unknown)))
            return 2
        units = tuple(u for u in UNITS if u.name in wanted)
        if index_only and not units:
            say("  the index archive only -- no unit is repacked")

    # An archive whose index is missing would plan as an EMPTY unit, because `common.read_index`
    # answers {} rather than raising -- right for a cache, wrong for a packing plan. Checked here,
    # before anything is read, so the refusal names the file instead of the archive being silently
    # small. See `archive_rows`.
    # ONCE PER ARCHIVE AND NOT ONCE PER UNIT THAT NAMES IT. `bitsavers` is named by
    # bitsavers-paper (as a subtree) and by bitsavers-software (bare), so the plain comprehension
    # listed it twice and the count disagreed with the number of archives that actually have a
    # problem. A refusal that cannot count is a refusal a reader stops trusting.
    seen = []
    for u in units:
        for a in u.archives():
            if a not in seen and not os.path.isfile(os.path.join(args.root, a, INDEX_FILE)):
                seen.append(a)
    absent = [os.path.join(a, INDEX_FILE) for a in seen]
    if absent:
        say("REFUSING TO PLAN: %d archive(s) have no index, and would pack as nothing:"
            % len(absent))
        for path in absent:
            say("    %s" % path)
        return 2

    if args.coverage:
        orphans, doubles = coverage(UNITS, args.root)
        for name, size in orphans.most_common():
            say("  CLAIMED BY NOBODY  %10s  %s" % (human(size), name))
        for name, size in doubles.most_common():
            say("  CLAIMED TWICE      %10s  %s" % (human(size), name))
        if not orphans and not doubles:
            say("every file is claimed exactly once")
            return 0
        return 1

    steps = plan(units, args.root, args.out, args.work, rar=rar,
                 with_dirs=not args.no_empty_dirs)
    if args.sizes:
        for step in steps[:-1]:
            say("%-24s %10s  %7d files"
                % (step["unit"].name, human(sum(r["size"] for r in step["rows"])),
                   len(step["rows"])))
        return 0

    report(steps, verbose=args.verbose)

    # MEMORY IS REPORTED IN THE PLAN, beside the volume and disc counts, because it is the other
    # resource a pack can run out of and the only one whose exhaustion leaves no trace in the
    # run's own output. On 2026-10-06 a workstations run was killed with 0.52 GB free of 63.34,
    # before Rar.exe had started, and nothing it printed said why.
    say("  %s" % memory_note(DEFAULTS.dictionary))

    if not args.execute:
        say("")
        # NO PASSWORD IS MENTIONED ANY MORE: no unit encrypts, so naming --password-file here
        # would send a reader looking for a file nothing asks for.
        say("NOTHING WAS RUN. Pass --execute to pack.")
        say("")
        say("Measured against a real WinRAR on 2026-09-26:")
        for fact, note in sorted(MEASURED_ON_THIS_MACHINE.items()):
            say("  %-36s %s" % (fact, note))
        say("")
        say("Still to check against your own rar.txt:")
        for switch, note in sorted(VERIFY_AGAINST_YOUR_RAR.items()):
            say("  %-22s %s" % (switch, note))
        return 0

    password = None
    if args.password_file:
        with io.open(args.password_file, encoding="utf-8") as fh:
            # Only the line ending is stripped: check_password complains about stray whitespace
            # rather than removing something that may legitimately belong to the password.
            password = fh.readline().rstrip(chr(13) + chr(10))
        complaint = check_password(password)
        if complaint:
            say("REFUSING: %s." % complaint)
            return 2
        # A password file beside the volumes would be uploaded with them. CHECKED EVEN WHEN NO
        # UNIT IS ENCRYPTED: the file was named, so it exists, and a secret sitting inside --out
        # travels to B2 whether this run used it or not.
        for where, label in ((args.out, "--out"), (args.work, "--work")):
            if os.path.abspath(args.password_file).startswith(os.path.abspath(where) + os.sep):
                say("REFUSING: the password file is inside %s and would be uploaded with the "
                    "archives." % label)
                return 2
    return execute(steps, rar, password)


if __name__ == "__main__":
    sys.exit(main())
