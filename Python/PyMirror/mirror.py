#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Mirror whole archives, one producer thread feeding a pool of downloaders.

Twelve archives, 2.8 TB: AIX packages and IBM's own distribution tree, plus the hardware
documentation an emulator has to be written against. ARCHIVES names each one and why it
is here; README.md carries the longer account and the defects found in each source.

What they have in common is the reason for copying them at all -- most are served by one
person from one machine, none has an obvious successor, and several have already lost a
maintainer once. Archives with a funded host behind them are deliberately not here.

WHERE THE MIRROR LIVES
    Not next to this script, and it must be said out loud. Until 2026-08-29 the tool used
    its own directory, which was true only because script and archives happened to sit in
    the same place. They no longer do: this file is version-controlled, the 2.8 TB is not.
    An assumed root would have written terabytes into a git checkout, so there is no
    default -- see resolve_root().

WHY THIS REPLACED wget --mirror
    wget uses one connection and waits on it. Measured against oss4aix: 5.8 requests/s at
    an average file size of 85 KB, so roughly 1.7 GB/h -- while single files transferred at
    1.1-1.9 MB/s. The link was never the limit; per-request latency was. The archive is
    193 GB, which put the single-threaded run at about 4.7 days.

    So: one producer thread walks the directory listings and pushes file URLs onto a
    bounded queue; WORKERS threads pull from it and download. The bound is what makes the
    producer stop enumerating when the workers fall behind, instead of building a
    136000-entry list in memory before the first byte is fetched.

USAGE
    python mirror.py --root /srv/mirror  resume -- skip files already present at full size
    MIRROR_ROOT=/srv/mirror              ... or name the tree once, in the environment
    python mirror.py --fresh             delete the target directories first
    python mirror.py --archive oss4aix.org
    python mirror.py --workers 8 --queue 128
    python mirror.py --verify        download nothing; check each tree against its marker
    python mirror.py --index         download nothing; refresh the checksum index

    Run it detached; it takes many hours.

CHECKSUMS
    Each mirror carries `.mirror-index.csv` (path, size, mtime_ns, sha256 -- the master) and
    `.sha256sum` derived from it in the format `sha256sum -c` reads. A mirroring run refreshes
    both afterwards unless --no-index, so re-mirroring keeps them current as a side effect.

    The index is incremental: a file is re-hashed only when its size or its mtime moved. That
    is what the two extra columns buy -- an unchanged 702 GB archive re-indexes in the time it
    takes to stat it, instead of the twenty minutes it takes to read it.

    Building an index does not need the network. Prefer --index over a full re-mirror when the
    checksums are all you are after: a re-mirror re-enumerates a few thousand directory
    listings on someone's privately run server and learns nothing the local tree does not
    already know.

POLITENESS
    WORKERS is the number of simultaneous connections to someone's privately run server.
    Eight is already generous. Do not raise it because the run feels slow.
"""

# =============================================================================================
# REQUIREMENTS -- what this tool must do, and why each rule exists
# =============================================================================================
#
# Read this before changing anything here. Every rule below was written after something broke,
# and most of the breakages were SILENT: the run ended, printed DONE, wrote a marker, and was
# wrong. A crawler that fails loudly is a nuisance; one that fails quietly destroys the thing it
# was built to protect. Dates name the day a defect was found, so a rule can be traced back.
#
# --- 1. WHAT A MIRROR IS ---------------------------------------------------------------------
#
# R1  A mirror is a byte copy of somebody's tree, complete, under the source's own names. No
#     sorting, no renaming, no normalising extensions, no deduplication -- not even the
#     obviously harmless kind. Those names belong to the source server, not to us.
#
# R2  NOTHING INSIDE A MIRROR IS EVER DELETED AS A DUPLICATE. Not against another mirror, not
#     against itself. oss4aix repeats 97% of RPMS/ inside everything/; removing that would
#     reclaim 109 GB and destroy the only question a mirror exists to answer -- *what did this
#     archive serve, and under which path*. Two identical files at two paths are two answers.
#
# R3  Files we write into a mirror (marker, index, sums, PROVENANCE, README) are not content.
#     They MUST be in OWN_FILES, or every marker becomes wrong the moment the first one is
#     written, and --verify reports MISMATCH on every archive at once.  [2026-08-26]
#
# R4  There must be exactly ONE definition of "what is in this mirror" -- iter_tree(). The
#     counter and the hasher both call it. Two copies of the rules drift, silently, and then the
#     marker and the index disagree about a tree neither of them is wrong about.
#
# --- 2. VERDICTS -----------------------------------------------------------------------------
#
# R5  The completion marker is a CLAIM, not a receipt. Write it only when the run had zero
#     unreadable listings and zero failures. For an rsync archive the verdict is rsync's own
#     exit code.
#
# R6  A VERDICT MUST NOT SURVIVE ITS OWN ERROR LOG. gsi-collection once ended COMPLETE and wrote
#     a marker while 260 files were missing and every one of them was logged as LOST -- because
#     that branch returned "skip" instead of "fail". If a file is lost, the run is not complete.
#     [2026-08-27]
#
# R7  CHECK ALL, THEN JUDGE. all(verify(n) for ...) short-circuits: one unverifiable archive
#     ended the pass and left four mirrors unchecked, with nothing saying so. A verification pass
#     that stops at the first problem does not verify.  [2026-08-27]
#
# R8  An amputated subtree must reach the DONE line AND the exit code. A listing that could not
#     be read takes every file below it with it, and nothing else will ever notice.
#
# --- 3. THE OPERATOR COMES FIRST -------------------------------------------------------------
#
# R9  ROBOTS.TXT IS NOT THE POLICY. bitsavers.org has an EMPTY robots.txt and a front page that
#     has said, since April 2026: "Wget is no longer permitted here... USE ANONYMOUS RSYNC".
#     This project crawled it twice before reading that page. Where a site publishes wishes a
#     machine cannot parse, they belong in RSYNC[] or EXCLUDE[] by hand.  [2026-08-26]
#
# R10 401 is the operator's boundary, not a transfer problem. Parts of the GSI collection answer
#     401; we have no credentials and never will. It belongs in PERMANENT, or it is retried four
#     times for nothing.  [2026-08-26]
#
# R11 Politeness is per-host and per-shape. WORKERS_BY_ARCHIVE: 8 for a package archive, 4 for a
#     volunteer documentation server, 3 for a hand-written site -- an HTML crawl already asks for
#     every page twice.
#
#     Two streams against one host: the answer depends on WHOSE host.
#       - one person's server (bitsavers.org, ps-2.kev009.com, ardent-tool.com): never. These
#         are the machines R9 is about, and bitsavers refused us outright after a day of it.
#       - a funded mirror built to serve a country (rsync.mirrorservice.org carries 142 modules
#         for the University of Kent): two concurrent rsync connections from one client is
#         ordinary load, not an imposition. tuhs and bitsavers ran together there on 2026-08-28.
#     Stated so that the exception is a judgement with a reason rather than a rule quietly
#     broken. If the distinction is ever unclear, treat the host as the first kind.
#
# --- 4. CRAWLING A GENERATED INDEX -----------------------------------------------------------
#
# R12 A listing matcher counts only if it yields at least one CHILD. ROW_RE matching nothing but
#     lighttpd's "Parent Directory" row counted as success, suppressed the fallback, and hid 97%
#     of ps-2.kev009.com -- 5.3 GB where 332 GB stood -- without one error message.
#
# R13 Absolute links (/rs6000/) must pass the link filter. On a generated index they are the
#     parent link; on a hand-written one they are the whole archive. Rejecting them found three
#     directories on a site with 94 899 files.
#
# R14 A subtree nobody links to needs a SEED. There is no way to discover it and no way to
#     notice that it is missing.
#
# R15 Resolve children against the FINAL url, not the requested one. A listing that redirected
#     resolves every relative child one level too high -- urljoin("h/a/dir", "x") is "h/a/x".
#     Latent, and silent when it fires.  [2026-08-26]
#
# --- 5. CRAWLING A HAND-WRITTEN SITE (HTML_CRAWL) --------------------------------------------
#
# R16 An HTML page is BOTH content to keep and a listing to walk. ardent-tool links
#     docs/docs.html, which does not end in a slash; treated as a leaf it would be saved and
#     never opened, and that one page links 87 documents.
#
# R17 A 403/404 while WALKING a hand-written page is a dead link -- the site's own rot -- not an
#     amputated subtree, and the file branch has already counted it. Counting it twice held
#     ardent-tool at INCOMPLETE forever over ten broken links somebody else left behind. On a
#     GENERATED index the opposite holds: there a 404 on a linked directory really is a lost
#     subtree, so this relaxation is HTML_CRAWL only.  [2026-08-26]
#
# R18 A NAME CANNOT BE BOTH A FILE AND A DIRECTORY. A hand-written site serves one name as both;
#     a filesystem cannot. Handle both directions, and detect it at the CAUSE: a 301 onto the
#     same path with a trailing slash means "that is a directory", so do not save the index page
#     it returns. Guard before the transfer AND immediately before the rename -- the directory
#     can appear while the file is downloading, and that surfaces as WinError 5, which reads like
#     a permissions problem and is not one.  [2026-08-26]
#
# R19 A FIX CANNOT UNDO WHAT THE BROKEN VERSION ALREADY WROTE. Seven index pages, saved under
#     directory names by the buggy run, blocked 260 downloads in the fixed run. When a rule
#     changes, ask what the old rule left on disk.  [2026-08-27]
#
# --- 6. TRANSFERS ----------------------------------------------------------------------------
#
# R20 A short read is a failed transfer, not a small file. Without the Content-Length check a
#     truncated download is indistinguishable from a complete one on the next run.
#
# R21 .part files are not content -- not for the marker, not for the index. One outage left 11 of
#     them holding 741 MB, and counting those inflated the very figure --verify compares against.
#     A .part that survives a run is a fragment: bitsavers-motorola-powerpc was once marked
#     COMPLETE holding a 12.5 MB piece of a 39.8 MB file.  [2026-08-23]
#
# R22 Case collisions must be detected, logged and resolved deterministically. On a
#     case-sensitive target both files are wanted; on a case-insensitive one only one can exist,
#     and a logged, deterministic loss beats whichever download happened to finish last.
#
# R23 Windows refuses paths over 260 characters without the \\?\ prefix, and reports it as
#     "No such file or directory" halfway through a run.
#
# R24 A worker must never die, and logging must never kill the thread that was reporting a
#     problem. The log lives on the volume being filled.
#
# --- 7. RSYNC ARCHIVES -----------------------------------------------------------------------
#
# R25 NO --delete, deliberately. bitsavers warns that names and locations change; --delete is
#     what keeps a CURRENT copy. This is a HISTORICAL one, for the same reason as R2. The cost is
#     real -- after a rename the file exists twice and the marker's counts grow -- and it is a
#     decision, not a command line copied off a web page.
#
# R26 A filter must name what comes IN when most of the archive is unwanted, and what stays OUT
#     when most of it is wanted. Naming only the exclusions on a 1.86 TB module pulled in 74 GB
#     nobody asked for: that root has 28 directories, not the 6 its front page names.
#     [2026-08-26]
#
# R27 --dry-run before every filter change. It costs a file list and answers the only question
#     that matters -- how many files, how many bytes, how many deletions -- before the change
#     costs hundreds of gigabytes.
#
# --- 8. THE CHECKSUM INDEX -------------------------------------------------------------------
#
# R28 The CSV is the master; the .sha256sum is DERIVED from it. Two files written by one loop
#     disagree eventually; one written from the other cannot.
#
# R29 Incremental on size AND mtime in NANOSECONDS. Seconds would let a file rewritten inside the
#     same second keep its old hash. This is what makes a refresh cost a stat of the tree rather
#     than a read of 1.3 TB.
#
# R30 A partial index is a valid index. Checkpoint, so an interrupted pass costs the current
#     batch and nothing else. Write to a temporary name and rename, so an interrupted write never
#     leaves half a manifest that still looks like a manifest.
#
# R31 The format is GNU sha256sum: 64 lowercase hex, space, asterisk, path relative to the mirror
#     root, forward slashes, LF, UTF-8, sorted by path. Verified against the real tool, not
#     assumed.
#
# --- 9. MEASURING BEFORE ACTING --------------------------------------------------------------
#
# R32 Ask the archive for its own index before walking it. bitsavers publishes IndexByDate.txt
#     per category; sizing two trees took TWO requests instead of several hundred directory
#     fetches, and the counts matched a full crawl exactly.
#
# R33 FILE COUNTS FROM AN INDEX ARE TRUSTWORTHY. SIZES EXTRAPOLATED FROM A SAMPLE ARE NOT. A
#     22-vendor sample put components/ at 44 GB; rsync said 127.9 GB. The counts were right to
#     two files, the average was wrong by a factor of three.  [2026-08-26]
#
# R34 "Connection refused" and "timed out" are different answers. Refused means there is no
#     service. Timed out means a firewall is dropping packets and the question is unanswered.
#
# R35 A marker's figures are a measurement of one moment. Re-verify after any restructuring, and
#     prove a move by hashing both sides -- path and SHA-256, before and after.
#
# =============================================================================================

import argparse
import concurrent.futures
import csv
import email.utils
import hashlib
import html as html_mod
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# The mirror tree: the directory that holds one subdirectory per archive. Deliberately NOT
# derived from __file__ -- see the module docstring. main() sets both from resolve_root()
# before anything reads them; a caller that skips main() (wedge_test.py) sets them itself.
ROOT = None
LOGDIR = None

# A file placed at the mirror root by hand. It marks a directory as "this is the tree" for a
# bare run with no --root, and it is the one way to point the tool at a git working copy on
# purpose. Empty is fine; only its presence is read.
ROOT_MARKER = ".mirror-root"

# Written into a mirror directory when a run finishes with nothing outstanding. Its presence
# makes --fresh refuse, and its contents are what --verify compares the tree against.
COMPLETE_MARKER = ".mirror-complete"

# The checksum pair, both written into the mirror root next to COMPLETE_MARKER.
#
# INDEX_FILE is the master: path, size, mtime_ns, sha256. The size and mtime are the whole point
# of keeping our own format -- they are what lets the next run skip a file it has already hashed,
# which turns a re-run from 1.3 TB of reading into seconds. SUMS_FILE is derived from it and
# carries nothing extra; it exists because `sha256sum -c` reads it and nothing on earth reads
# the CSV.
INDEX_FILE = ".mirror-index.csv"
SUMS_FILE = ".sha256sum"

# Our own files inside a mirror directory: notes about the copy, not part of it. They are
# excluded from the file and byte counts, so that documenting an archive does not make --verify
# report it as changed -- which it did, for exactly one PROVENANCE.md.
#
# The two checksum files MUST be in here. They live at the top of the mirror, so without this
# every marker would be wrong by +2 files the moment the first index was written, and --verify
# would report MISMATCH on all twelve archives at once -- for a reason nobody would find a
# week later.
# Written and removed within one call of is_case_sensitive(). Both spellings are listed because
# that is the whole point of the probe, and because a process killed between the create and the
# remove would otherwise leave a file the marker counts and --verify then reports as a change.
PROBE_FILE = ".mirror-case-probe"

OWN_FILES = {COMPLETE_MARKER, INDEX_FILE, SUMS_FILE, "PROVENANCE.md", "README.md",
             PROBE_FILE, PROBE_FILE.upper()}

HASH_CHUNK = 1 << 20        # read size while hashing; 1 MB measured no worse than larger
HASH_BATCH = 2000           # files submitted to the pool at once, and the checkpoint interval

ARCHIVES = [
    ("oss4aix.org", "http://www.oss4aix.org/download/"),
    ("rwth-aachen-ftp", "http://john.ccac.rwth-aachen.de:8000/ftp/"),
    ("bull-rpms", "https://dl.power-devops.com/bull/RPMS/"),
    ("bull-srpms", "https://dl.power-devops.com/bull/SRPMS/"),
    ("ps-2.kev009.com", "https://ps-2.kev009.com/"),
    # aix.software.ibm.com, NOT public.dhe.ibm.com. Same tree, same bytes -- index.txt is
    # 2911 bytes on both, and every sampled directory has the same entry count. But
    # public.dhe.ibm.com *omits README files from its directory listings* while still serving
    # them: `aix/README_AIX` answers 200 with 4012 bytes on both hosts, and appears in the
    # listing on only one. A crawler follows links, so mirroring from public.dhe would silently
    # drop every README in the tree -- in a 20-directory sample, 6 of them, including the
    # 1996 FixDist welcome text that explains what this server was.
    ("ibm-aix", "https://aix.software.ibm.com/aix/"),

    # Documentation archives, added 2026-08-23. Each is a narrow subtree, not a whole site:
    # Bitsavers is measured in terabytes and only its PowerPC and RS/6000 branches are wanted.
    # Scanned paper, so the files are large and the counts small -- the opposite shape from the
    # package archives above.
    # Five narrow bitsavers subtrees stood here until 2026-08-26. They were HTTP crawls -- made
    # before anyone read the archive's front page, which has asked for rsync and not for crawlers
    # since April 2026. Their 1285 files were moved into the single `bitsavers` mirror below,
    # proved identical by path and SHA-256, then proved again against the source with a dry run
    # that had nothing to transfer. Leaving the entries behind was its own small defect: --verify
    # reported five archives with no marker, and stopped there.
    # The AIX manual sets IBM no longer serves: releases 5.2, 5.3 and 6.1, plus 28 Redbooks.
    # This is where ktechrf2.pdf, aixfiles.pdf and diagunsd.pdf came from individually.
    ("filibeto-aix-lib", "https://www.filibeto.org/unix/aix/lib/"),

    # --- added 2026-08-26, deliberately whole rather than sliced ---------------------------
    #
    # These are not AIX archives. They are kept because AIX work needs them: an emulator is
    # written against the *chips*, and QEMU's 40p and prep machines are built out of parts whose
    # manuals live in these archives and in very few other places -- the National PC87312 super I/O,
    # the Intel 82378 PCI-ISA bridge, the AMD PCnet and 53C974, the Cirrus CL-GD5446 that
    # hw/display/cirrus_vga.c implements.
    #
    # Taken whole on purpose. A vendor tree cut down to the parts that look relevant today is
    # not a mirror, and the judgement that national/ is "just operational amplifiers" is exactly
    # the judgement that turns out wrong in two years.
    # bitsavers is ONE mirror in the archive's own layout -- pdf/, components/, bits/ and the
    # rest under a single root, so `rsync rsync://bitsavers.org/bitsavers/ bitsavers/` and this
    # directory mean the same thing. It replaced five narrow HTTP mirrors on 2026-08-26; the
    # 1285 files they held were moved into place and proved identical, path and SHA-256, then
    # proved again against the source with a dry run that had nothing to transfer.
    #
    # The URL here is informational: the transfer goes through RSYNC[], not the HTTP crawler.
    ("bitsavers", "rsync://bitsavers.org/bitsavers/"),
    # vtda.org, assembled from five sibling rsync modules on the same daemon. A separate archive
    # from bitsavers despite the shared host -- see RSYNC[] for what is in it and why it is taken
    # whole. The URL here names the daemon; the five module URLs are in RSYNC["vtda"]["sources"].
    ("vtda", "rsync://bitsavers.org/vtda-*/"),
    # The Unix Heritage Society. 12 139 files, 9.33 GB: the original UNIX distribution tapes --
    # V1 through V7, System III and V, the BSD line -- with Documentation/, Applications/,
    # Tools/, Memorabilia/ and Recordings/ beside them, and Caldera-license.pdf, the release
    # under which the early sources may be distributed at all.
    #
    # In scope because AIX descends from System V, and this is the source to the documentation.
    # `pdf/att/unix/7th_Edition/` arrived from bitsavers on 2026-08-27 -- that is the manual;
    # this is the code it describes.
    ("tuhs", "rsync://rsync.mirrorservice.org/tuhs.org/"),
    # The Ardent Tool of Capitalism. Board-level RS/6000 detail no IBM manual here carries:
    # planar specifications for the 7007-7013, CPU cards for POWER1/POWER2/P2SC, adapter pages.
    # A hand-written site, so HTML_CRAWL -- see there.
    ("ardent-tool", "https://ardent-tool.com/"),
    # GSI Darmstadt's vintage collection. Its IBM branch already supplied two RS/6000 adapter
    # books; the directory index is 403, so the pages are the only way in. HTML_CRAWL.
    ("gsi-collection", "https://web-docs.gsi.de/~kraemer/COLLECTION/"),

    # Michael Felt's AIX builds: open-source software packaged as installp/BFF filesets rather
    # than as RPM, targeting AIX 5.3 TL7 and up. Installable without rpm.rte, which is precisely
    # what an old AIX needs and what nothing else here carries -- of a 100-project probe list, 98
    # exist somewhere in these mirrors as RPMs and none as an aixtools fileset.
    #
    # THE ONE THAT GOT AWAY. Between its last capture on 2025-01-14 and 2026-08-29, when this was
    # checked, the site died: both vhosts fell back to Apache's stock "It works!" page under one
    # shared ETag, and `/tools/` answers 404 rather than 403 -- Apache's 403 means "exists,
    # unlisted", 404 means gone. No HTTPS, no rsync, no FTP; the apex domain shows a registrar
    # parking page. This directory is therefore NOT a mirror of that host. It is what the Internet
    # Archive still had, recovered by wayback-salvage.py. See FROZEN and the PROVENANCE.md inside.
    ("aixtools", "http://download.aixtools.net/"),
]

# Archives whose source no longer exists. Not "finished" -- gone.
#
# The distinction earns its keep. A completion marker says a run had nothing outstanding, and the
# cure for anything missing is another run. Here another run cannot help: pointing the crawler at
# the dead host would fetch a tree of 404s and end INCOMPLETE, a verdict that would read as "we
# failed" when it means "there is nothing there any more". So the transfer is refused with the
# reason, while --index and --verify keep working on what was recovered.
#
# This is also the project's own premise arriving: an archive run by one person, with no
# successor, that went away before it was copied.  [2026-08-29]
FROZEN = {
    "aixtools": "download.aixtools.net is gone -- /tools/ answers 404 rather than 403, and the "
                "domain is parked. Recovered from the Internet Archive 2026-08-29; a re-run "
                "cannot add anything the origin no longer serves.",
}

# Archives that are hand-written websites rather than generated directory listings. For these an
# HTML page is both a file to keep and a listing to walk; see producer(). Do not add a generated
# index here -- it costs a second request per page for nothing.
HTML_CRAWL = {"ardent-tool", "gsi-collection"}

# Archives fetched over rsync instead of HTTP, because their operator asks for it.
#
# bitsavers' front page, since April 2026: "Wget is no longer permitted here... People are
# downloading the ENTIRE site through the web interface. The situation has gotten much worse since
# the LLM web scrapers have appeared. USE ANONYMOUS RSYNC.. That's what it's there for!" Its
# robots.txt is empty, which reads as permission; the policy is on the page, written by a person.
# Checking the machine-readable signal is not the same as asking the operator.
#
# `filter` is passed to rsync verbatim, in order. rsync takes the FIRST rule that matches, so an
# include must come before the exclude that would otherwise swallow it -- that is why /pdf/ibm/
# needs three lines and not one. The whole archive is 1.86 TB and does not fit beside this
# collection, so this list is the scope, and it shrinks as room is made.
RSYNC = {
    "bitsavers": {
        # NOT the origin. bitsavers.org refused our connections on 2026-08-28 after we
        # had pulled roughly 700 GB from it in a day -- rc 10, "Connection refused", and
        # HTTP 403 alongside. Its front page lists anonymous rsync mirrors for exactly
        # this reason: so that a 533 GB clone does not land on the origin. eldanna was
        # verified byte-for-byte against it first -- same 28 root directories, and
        # pdf/dec/ identical to the byte at 22 090 files and 274 409 657 425 bytes.
        #
        # The origin remains the authority on WHAT the archive is; a mirror is where the
        # bytes should come from once there are hundreds of gigabytes of them.
        # Measured 2026-08-28, one 98 MB file from each candidate:
        #
        #   rsync.mirrorservice.org (Univ. Kent)     9.29 MB/s   <- this one
        #   eldanna.ocaml.nl                         1.11 MB/s
        #   bitsavers.informatik.uni-stuttgart.de    access denied (their network only)
        #   ftpmirror.infania.net                    no answer
        #
        # Eight times the throughput turns four days into eleven hours, and eldanna's
        # 1.11 MB/s matched what the live run was actually managing -- the benchmark and
        # the transfer agreed, so the number is real and not a fluke of one file.
        #
        # Note the module name differs here: `www.bitsavers.org`, not `bitsavers`.
        "url": "rsync://rsync.mirrorservice.org/www.bitsavers.org/",
        # STAGE 2, 2026-08-27: +310.8 GB on top of stage 1, for ~354 GB in total.
        #
        # Everything except three things. What comes in:
        #
        #   components/       whole, 127.9 GB   the chip layer -- stage 1 took eleven vendors,
        #                                       this takes the other ~300. Which of them matters
        #                                       is a judgement about questions asked later.
        #   pdf/ibm/          whole,  92.8 GB   including 370/ at 16 GB. AIX/370 and AIX/386
        #                                       existed, and so did the PS/2 lineage. Not a
        #                                       foreign branch.
        #   22 root dirs             74.0 GB   mirrors/, projects/, the Queensland scans, and
        #                                       nineteen small ones
        #   bits/IBM/         whole,  38.3 GB   IBM software and disk images
        #   test_equipment/   whole,  12.7 GB   ancot/DSC-202 is a SCSI bus analyser -- the
        #                                       instrument that decodes the wire protocol
        #                                       cfgscsidisk failed on
        #   communications/   whole,   8.5 GB
        #
        # What stays out, and why: bits/ minus IBM is 742 GB, of which NetBSD alone is 607, and
        # does not fit in the 928 GB free. pdf/ minus IBM is 559 GB -- it would fit *instead* of
        # magazines/, not beside it. magazines/ is 192 GB of JPEG2000 scans.
        #
        # --- the stage-1 note, kept because it explains the shape of these rules -------------
        #
        # STAGE 1, 2026-08-26: ~22 GB. Deliberately narrow.
        #
        # The whole module is 1.86 TB and the six named categories are only 280 GB of it -- the
        # module root has 28 directories, not 6, and `mirrors/` alone is 44.9 GB in ten .tar
        # files. A filter that names what it excludes rather than what it includes therefore
        # pulls 74 GB nobody asked for, which is how the first draft of this list came to 354 GB.
        # So: include what is wanted, exclude the rest, and widen it one stage at a time.
        #
        # This stage is chosen to do two jobs at once. It covers every subtree the five old HTTP
        # mirrors held, so a run proves the 2026-08-26 move against the source; and it is exactly
        # the vendors whose parts QEMU's 40p and prep machines implement:
        #
        #   ncr_symbios  53C895 (hw/scsi/lsi53c895a.c), 53C810, 53C90/94 (hw/scsi/esp.c)
        #   national     PC87312 (hw/isa/pc87312.c), the 16550 UART note
        #   intel        82378 (hw/isa/i82378.c), the 8254x e1000 family
        #   amd          Am79C970 PCnet (hw/net/pcnet.c), 53C974 (hw/scsi/esp-pci.c)
        #   cirrusLogic  CL-GD5446 (hw/display/cirrus_vga.c), and the VGA BIOS source
        #   lsiLogic, dallasSemiconductor, stMicroelectronics -- small, and where the M48T59
        #                timekeeper (hw/rtc/m48t59.c) would be if it is anywhere
        #
        # rsync takes the FIRST rule that matches, so every include must precede the exclude that
        # would otherwise swallow it, and a subtree needs its parent directory included first.
        #
        # --- STAGE 3, 2026-08-27: the goal is now the WHOLE module ----------------------------
        #
        # The target changed here, and the filter should be read in that light: this is no longer
        # a selection that might grow, it is a complete mirror with two temporary holes and one
        # permanent one.
        #
        #   permanent   bits/NetBSD/            606.8 GB   BSD release media, complete elsewhere
        #   deferred    pdf/ minus ibm/         559.2 GB   waiting on disk, not on a decision
        #
        # Everything else comes whole -- components/, the rest of bits/, magazines/ entire,
        # test_equipment/, communications/, and the 22 smaller root directories.
        #
        # magazines/ was briefly filtered down to its 141 issues from 1990-1994, on the argument
        # that the RS/6000 was announced in February 1990 and the other 2 856 issues predate the
        # machine. That was a good argument for a selection and a bad one for a mirror:
        # R1 says a mirror is complete, and 7.8 % yield is a reason to skip a directory entirely,
        # never a reason to keep a curated slice of it and call it mirrored. Reverted the same
        # day; the 141 already fetched are simply the first of the 2 997.
        "filter": [
            # ONE rule. Everything in the module comes except this.
            #
            # 12 647 NetBSD ISO archival releases, 606.8 GB -- 78 % of bits/ and a third of the
            # whole archive. bitsavers' own front page names them as the reason it grew. They are
            # BSD release media: complete elsewhere, binary, and unrelated to anything here.
            #
            # Nothing else is excluded any more. pdf/ came in stages only because of disk --
            # ibm/ first, then att/ motorola/ apple/ hp/ ti/ intel/ dg/, and dec/ with its 274.4 GB
            # of VAX and PDP-11 microfiche last. Room was made on 2026-08-27 and the staging is
            # over; the whole 652.1 GB is in scope. If this line ever grows a second rule, the
            # reason belongs beside it, because a mirror with undocumented holes is not a mirror.
            "--exclude=/bits/NetBSD/",
        ],
        # NOT --delete, deliberately. bitsavers warns that "file names, dates and their location
        # in the hierarchy change (these aren't permalinks)", so --delete is what keeps a
        # *current* copy. This is a *historical* one: a file that was renamed upstream stays here
        # under the name it was served as, which is the same reason nothing in a mirror is ever
        # dropped as a duplicate. The cost is real -- after a rename the file exists twice and the
        # marker's counts grow -- and it is a decision, not an inherited command line.
        "delete": False,
    },

    # The Vintage Technology Digital Archive, vtda.org. **Not part of bitsavers** -- a separate
    # project that happens to be served by the same rsync daemon, as five sibling modules rather
    # than one tree. So this is one mirror assembled from five sources, named after the modules
    # with the `vtda-` prefix dropped: `vtda/docs/` is `rsync://bitsavers.org/vtda-docs/`.
    #
    # Taken whole, 234.7 GB. It is a general vintage-technology archive -- radio, telephony,
    # calculators, arcade -- and its IBM branch is only 7.5 GB of that. Kept entire anyway, for
    # the same reason `national/` keeps its operational amplifiers: which 7.5 GB matters is a
    # judgement made today about questions asked later.
    #
    # `vtda-docs/computing/IBM/UNIXSystems/` holds two files worth naming here, because they may
    # close a long-standing gap: `IBM_eServerHIC_Aug2005.iso` and
    # `SK3T-8159-06_IBMeServerHIC-CD_Aug2005.pdf` -- the eServer Hardware Information Center on
    # CD, August 2005. Service documentation for the 9114-275 is hard to find anywhere else, and
    # is the kind of thing that lives on exactly that disc. Unverified until it is opened.
    "tuhs": {
        # Same host as bitsavers -- see there for why Kent rather than an origin. TUHS's own
        # site offers rsync too, but Kent is measured at 9.29 MB/s and is a funded academic
        # mirror rather than one person's server.
        "url": "rsync://rsync.mirrorservice.org/tuhs.org/",
        "filter": [],
        "delete": False,
    },

    "vtda": {
        "sources": [
            ("rsync://bitsavers.org/vtda-docs/",  "docs"),    #  3 862 files,  38.0 GB
            ("rsync://bitsavers.org/vtda-books/", "books"),   #    199 files,   9.9 GB
            ("rsync://bitsavers.org/vtda-pubs/",  "pubs"),    #  9 892 files, 103.6 GB
            ("rsync://bitsavers.org/vtda-bits/",  "bits"),    #  3 531 files,  81.1 GB
            ("rsync://bitsavers.org/vtda-pics/",  "pics"),    # 12 275 files,   2.1 GB
        ],
        "filter": [],
        "delete": False,
    },
}

# Subtrees skipped by name, relative to the archive's base URL. Empty today; kept because the
# mechanism is the difference between "we took the whole branch" and "we took the branch minus
# the one directory that was bigger than everything else in it".
# Subtrees not to descend into, matched against the path below the archive's base URL.
#
# `mirror.py` does not read robots.txt -- it walks what a page links, and an operator's wishes
# live in a file it never opens. Where a site publishes one, its Disallow rules belong here by
# hand. ardent-tool.com allows everything except `/incoming/*`; that directory was never reached
# on 2026-08-26 because nothing links to it, which is luck rather than compliance.
EXCLUDE = {
    "ardent-tool": ("incoming/",),
}

# NOT mirrored, and the reason is worth keeping. `public.dhe.ibm.com/software/server/` is IBM's
# Power service tree -- 43 branches, all AIX-relevant: firmware, diags, hmc, hacmp, gpfs, essl,
# vios, POWER. Measured by full crawl 2026-08-22:
#
#     entire branch      2.2 TB    995 directories, 25876 files
#     without hmc/     777.9 GB    934 directories, 24654 files
#
# Left out as a scope decision, not because it is uninteresting: `/aix/` already covers the
# operating system and its toolbox, and this is the hardware-service side. The four AIX 4.3.3
# and 5.1 fix packs that were wanted from it were fetched individually instead, and are held
# outside this mirror.
#
# To take it after all, put it back in ARCHIVES with EXCLUDE["ibm-software-server"] = ("hmc/",)
# and NEEDS_CASE_SENSITIVE -- it has 162 case collisions of its own.

# Set BEFORE the directory is created -- NTFS inherits the flag only into children made
# afterwards. tuhs.org showed ZERO case collisions in its 12 139 files when measured on
# 2026-08-28, because it ships historical UNIX as tarballs and disk images rather than as
# unpacked trees. It is set anyway: the archive grows, unpacking one of those tarballs
# would produce collisions immediately (V7 has both `README` and `readme`), and the flag
# is free today and unobtainable later.
NEEDS_CASE_SENSITIVE = {"ibm-aix", "tuhs"}

# Extra starting points, because a crawler mirrors what is *linked*, not what *exists*.
#
# ps-2.kev009.com was mirrored from its root, finished without a single unreadable listing, and
# was marked COMPLETE with 1563 PDFs. It was still missing most of the archive: the front page
# does not link `basil.holloway/`, which alone holds **1955 PDFs** (~4.8 GB by sampling), nor the
# subtrees under `rs6000/`. Nothing was broken -- every page that was reachable was fetched. The
# seed was simply not enough, and no counter in the DONE line could have said so, because from
# the crawler's point of view there was nothing left to report.
#
# Found 2026-08-23 by listing the live server and diffing it against the mirror. That comparison
# is the only thing that detects this class of miss, and it is worth repeating on any archive
# whose upstream is a hand-made page rather than a generated index.
#
# Seeds must live under the archive's base URL: local_path() maps a URL by stripping that prefix,
# so a seed outside it would land in the wrong place.
SEEDS = {
    "ps-2.kev009.com": (
        "https://ps-2.kev009.com/basil.holloway/",
        "https://ps-2.kev009.com/rs6000/manuals/",
        "https://ps-2.kev009.com/rs6000/docs/",
        "https://ps-2.kev009.com/rs6000/aix_ps_pdf/",
        "https://ps-2.kev009.com/rs6000/rs6000_ps_pdf/",
        "https://ps-2.kev009.com/rs6000/bull_motorola_pdf/",
        "https://ps-2.kev009.com/rs6000/redbook-cd/",
        "https://ps-2.kev009.com/rs6000/NSM/",
        # /rs6000/ links this one WITHOUT a trailing slash -- see the note on defect 9 in
        # README.md. 49 files and 7.6 GB hung behind it, several of them large ISO images.
        "https://ps-2.kev009.com/rs6000/files/",
    ),
}

# Per-archive connection count, overriding --workers. Empty: 8 for everything.
#
# ibm-aix was briefly raised to 16 and put back. A short probe -- a few seconds per step --
# showed aggregate throughput scaling linearly with connections, so the cap looked per-connection:
#
#     1 connection   0.06 MB/s total      4 -> 0.21      8 -> 0.39     16 -> 0.92
#
# Over hours it does not hold. Measured on the real run:
#
#      8 connections   66.0 min   10.76 GB   2.78 MB/s
#     16 connections   17.8 min    3.00 GB   2.88 MB/s
#
# Identical, while connection timeouts went from 1 to 23. The server caps the *client*, not the
# connection, at roughly 2.9 MB/s; the extra sockets only add failures. A measurement taken over
# seconds does not describe a transfer that runs for days.
WORKERS_BY_ARCHIVE = {
    # Bitsavers and filibeto are volunteer-run documentation archives with far fewer, far larger
    # files than the package mirrors. Four connections is plenty for scanned PDFs and is the
    # polite number for someone else's hobby server.
    "filibeto-aix-lib": 4,
    # Hand-written sites on modest hosting, and the HTML crawl already asks for each page twice.
    "ardent-tool": 3,
    "gsi-collection": 3,
}

UA = "Mozilla/5.0 (compatible; archive-mirror/1.0)"
CHUNK = 1 << 16
CONNECT_TIMEOUT = 30
ATTEMPTS = 4
# Attempts per rsync source. Higher than ATTEMPTS because each one is cheap -- rsync
# resumes from what is on disk -- and these transfers are long enough that a dropped
# connection is routine rather than exceptional: bitsavers closed one after 140 GB of a
# 533 GB run on 2026-08-27.
RSYNC_ATTEMPTS = 12
# rsync exit codes that mean the far end declined the connection rather than lost it.
# 10 is "error in socket IO", which is what "Connection refused" surfaces as. These get
# a long wait and a hard stop, not the ordinary retry ladder -- see rsync_mirror().
RSYNC_REFUSED = (10,)
RSYNC_REFUSAL_LIMIT = 2
# 403/404/410 are the server's settled answer -- retrying only wastes its time. A handful
# of files under SPECS/ and patches/ on oss4aix are served with broken permissions and
# return 403 every time; they are genuinely unreachable, not throttling.
# Statuses no retry can fix for an anonymous client. 401 belongs here for the same reason as 403:
# we have no credentials and will never have any, so four attempts produce four identical refusals
# and one inflated failure count. Parts of the GSI collection answer 401 -- CABLES/, BOARDS/, NIC/
# -- and that is the operator's boundary, not a transfer problem.
PERMANENT = (401, 403, 404, 410)


# --------------------------------------------------------------------------- HTML parsing

# Apache's table-form autoindex, which is what both servers emit:
#   <a href="NAME">NAME</a></td><td align="right">DATE</td><td align="right"> 25K</td>
# The size column is rounded, so it is good enough for an ETA and useless for verification.
ROW_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*>.*?</a>\s*</td>\s*'
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'
    r'<td[^>]*>\s*([0-9.]+\s*[KMG]?|-)\s*</td>',
    re.I | re.S,
)
# lighttpd's table autoindex, which puts the columns the other way round -- name, SIZE, DATE:
#   <td class="link"><a href="NAME/">NAME/</a></td><td class="size">-</td>
#   <td class="date">2015-Jan-12 09:17</td>
#
# ROW_RE cannot read it, and the way it fails is what made this expensive. On such a page ROW_RE
# matches exactly one row: "Parent directory", whose *date* cell is "-" and therefore happens to
# satisfy ROW_RE's size pattern. One match is enough to claim the format, the row is then dropped
# as a parent link, and parse_listing returns an empty list without ever trying the fallback.
#
# A directory that parses to nothing is indistinguishable from an empty directory: no LISTFAIL,
# no warning, no counter. That is how `ps-2.kev009.com` was mirrored, marked COMPLETE, and left
# missing `basil.holloway/` with its 1955 PDFs. Found 2026-08-23.
LIGHTTPD_RE = re.compile(
    r'<td class="link"><a\s+href="([^"]+)"[^>]*>.*?</a></td>\s*'
    r'<td class="size">\s*([0-9.]+\s*[KMGT]?i?B?|-)\s*</td>\s*'
    r'<td class="date">\s*([^<]*?)\s*</td>',
    re.I | re.S,
)
# Apache's other autoindex style, a <pre> block rather than a table. IBM's Toolbox serves this
# one, and without a matcher for it every file comes back with an unknown size -- 21165 files
# reported as 0 bytes, which is not a small error to have in an ETA.
#   <a href="NAME">NAME</a>        2002-04-10 17:08  1.2M
PRE_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*>[^<]*</a>\s+'
    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+'
    r'([0-9.]+\s*[KMG]?|-)',
    re.I)
LINK_RE = re.compile(r'<a\s+href="([^"]+)"', re.I)
# A page to be walked as well as saved, for the HTML_CRAWL archives. Query strings are already
# gone by then -- is_child_link drops anything containing '?'.
HTML_PAGE = re.compile(r"\.s?html?$", re.I)
SUFFIX = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}

# The two date formats the indexes use. An archive's file dates are part of what it is: without
# these every mirrored file claims to have been made on the day it was copied, and a 2005 RPM
# becomes indistinguishable from one built yesterday.
DATE_FORMATS = ("%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%b-%Y %H:%M:%S",
                "%Y-%b-%d %H:%M")   # lighttpd: 2009-Feb-06 10:16


def parse_date(text):
    """Listing date -> epoch seconds, or None. Minute precision, which is what the index gives."""
    text = (text or "").strip()
    if not text or text == "-":
        return None
    for fmt in DATE_FORMATS:
        try:
            return time.mktime(time.strptime(text, fmt))
        except ValueError:
            continue
    return None


def http_date(text):
    """`Last-Modified` header -> epoch seconds, or None. Exact to the second."""
    if not text:
        return None
    try:
        return email.utils.mktime_tz(email.utils.parsedate_tz(text))
    except (TypeError, ValueError):
        return None


def parse_size(text):
    """'25K' -> 25600, '772.8 KiB' -> 791347. None for '-' and anything unparseable.

    Two unit conventions, because two servers use different ones: Apache prints '25K', lighttpd
    prints '772.8 KiB'. Both mean 1024, so only the spelling differs -- but a parser that knows
    only one of them returns None, and a size of None is what makes an ETA meaningless.
    """
    text = text.strip()
    if not text or text == "-":
        return None
    if text.upper().endswith("IB"):          # KiB, MiB, GiB, TiB
        text = text[:-2].strip()
    elif text.upper().endswith("B") and len(text) > 1 and not text[-2].isdigit():
        text = text[:-1].strip()             # KB, MB, ...
    elif text.upper().endswith("B"):
        text = text[:-1].strip()             # plain bytes
    try:
        if text and text[-1].upper() in SUFFIX:
            return int(float(text[:-1].strip()) * SUFFIX[text[-1].upper()])
        return int(float(text))
    except (ValueError, OverflowError):
        # OverflowError is not hypothetical: a size column of a few hundred digits makes
        # float() return inf, and int(inf) raises. This is called from parse_listing(),
        # which the producer invokes outside any handler of its own.
        return None


def is_child_link(href):
    """True for links that might point into this archive. The caller decides for certain.

    This is deliberately the *weaker* of two guards. What actually keeps the crawl inside the
    archive is the `child.startswith(base_url)` test in producer(), applied after urljoin has
    resolved the link. This one only drops what cannot possibly be useful:

      '?...'            the sort links every Apache index carries, once per column and
                        direction. Following them re-fetches every listing six or eight times
                        over -- measured: 26 requests against 34 on a single directory.
      '..'              an upward escape, which urljoin would resolve to somewhere outside
      scheme-qualified  off-site

    **Absolute paths ('/rs6000/') are allowed through.** They were rejected here originally,
    on the assumption that they only ever appear as Apache's "Parent Directory" link. That is
    true of a generated index and false of a hand-written one: ps-2.kev009.com links its whole
    archive absolutely from the landing page, and rejecting those left the crawler finding
    three directories and eight files on a site with tens of thousands. An absolute link that
    resolves above base_url is still dropped by the caller, so nothing is lost by letting it
    through.
    """
    if not href or href.startswith(("?", "#")):
        return False
    if "://" in href or href.startswith("//"):
        return False
    if href.startswith(".."):
        return False
    if "?" in href:
        return False
    return True


def parse_listing(body):
    """-> [(href, size_or_None, mtime_or_None)] for the children of one directory listing.

    Three matchers, tried in order of how much they tell us. The bare link scan is last because
    it yields neither size nor date, which silently turns the ETA into nonsense and stamps every
    file with the day it was copied -- so a new index style is worth a matcher rather than a shrug.
    """
    # (matcher, order of the two trailing groups). A matcher is accepted only if it yields at
    # least one *child* -- not merely at least one match. ROW_RE matching only the "Parent
    # directory" row of a lighttpd page used to count as success and suppressed the fallback,
    # which is how whole subtrees went missing without a single warning.
    for matcher, size_first in ((ROW_RE, False), (LIGHTTPD_RE, True), (PRE_RE, False)):
        out = []
        for h, a, b in matcher.findall(body):
            if not is_child_link(h):
                continue
            z, d = (a, b) if size_first else (b, a)
            out.append((html_mod.unescape(h), parse_size(z), parse_date(d)))
        if out:
            return out
    return [(html_mod.unescape(h), None, None)
            for h in LINK_RE.findall(body) if is_child_link(h)]


# ------------------------------------------------------------------------------- fs paths

ILLEGAL = re.compile(r'[<>:"|?*\x00-\x1f]')


def safe_segment(seg):
    return ILLEGAL.sub("_", seg)


def local_path(root, base_url, url):
    """Map a URL under base_url onto a path under root, one URL segment per directory."""
    rel = urllib.parse.unquote(url[len(base_url):])
    parts = [safe_segment(p) for p in rel.split("/") if p not in ("", ".", "..")]
    return os.path.join(root, *parts)


def is_case_sensitive(root):
    """Ask NTFS whether this directory already carries the case-sensitive flag.

    Needed because the flag survives a run and the script does not. On a resume the target
    directory already exists, so enable_case_sensitivity() is skipped -- and without asking, the
    run would carry on believing the volume folds case and would *drop* every collision it found,
    discarding files the directory is perfectly able to hold. Caught on the ibm-aix resume, where
    one `COLLISION DROPPED` line appeared that could not have been correct.

    MEASURED, NOT ASKED. Until 2026-08-29 this ran `fsutil file queryCaseSensitiveInfo` and
    searched the output for "disabled" or "deaktiviert" -- two of the forty-odd languages Windows
    ships in. On a French host neither word appears, `not (False or False)` is True, and the
    function reports case sensitivity for a directory that has none; the run then writes both
    spellings and the second silently overwrites the first. That is precisely the loss this
    function exists to prevent, manufactured by the function itself. Decoding as cp850 was the
    same assumption a second time.

    So ask the filesystem the question actually at stake -- can it hold both names? -- by making
    one and looking for the other. No locale, no fsutil, no Windows assumption: the old
    `os.name != "nt": return False` claimed ext4 folds case, which would have dropped every
    collision on a Linux host for no reason at all.
    """
    lower = os.path.join(root, PROBE_FILE)
    upper = os.path.join(root, PROBE_FILE.upper())
    try:
        with open(long_path(lower), "wb"):
            pass
    except OSError:
        # Unwritable, or gone. Answer with the side that loses nothing: a run that believes the
        # directory folds case drops collisions loudly, and a logged loss beats a silent one.
        return False
    try:
        # If the directory folds case, the file just created IS the upper-case one.
        return not os.path.exists(long_path(upper))
    finally:
        for probe in (lower, upper):
            try:
                os.remove(long_path(probe))
            except OSError:
                pass


def enable_case_sensitivity(root):
    """Ask NTFS to treat `root` and everything created under it as case-sensitive.

    HTTP paths are case-sensitive, NTFS by default is not. Two remote files differing only
    in case would land on one local file: the second silently overwrites the first and the
    mirror is short by one, with nothing in any log to say so.

    Measured 2026-08-22 across both archives -- 195067 files, **zero** such pairs -- so this
    is off by default. It is here because the measurement is only true of the archives as they
    stand today, and because this class of damage is well known from cloning large source trees
    onto a case-folding filesystem -- the Linux kernel tree alone has hundreds of such pairs.

    The flag is inherited by directories created afterwards, not by existing ones, so it
    only has an effect when set on a fresh root. No elevation needed; NTFS only.
    """
    if os.name != "nt":
        return None
    try:
        subprocess.run(["fsutil", "file", "setCaseSensitiveInfo", os.path.abspath(root), "enable"],
                       check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        return "fsutil failed: %s" % exc


def long_path(path):
    """Windows refuses paths over 260 characters unless they carry the \\\\?\\ prefix.

    Package names in this archive nest deep enough to cross that
    (RPMS/<pkg>/<long-rpm-name>), and without the prefix the failure surfaces as a
    misleading "No such file or directory" partway through the run.

    NOT via os.path.abspath(). abspath() normalises, and normalising STRIPS A TRAILING DOT --
    which is precisely what the \\\\?\\ prefix exists to prevent. 21 files in these mirrors end
    in a dot (`bndstd.`, `HZLDPY.`, `GERMAN.`, `TALK.`, off PDP-8 paper tapes and RSTS/E disk
    images), and for every one of them abspath turned a name that exists into a name that does
    not. The move tool hit it as "file not found" on files that were plainly there; here it
    would be quieter and worse -- a stat that fails is a file the index silently omits and the
    marker never counts. The helper defeated the very thing it was written for.  [2026-08-29]

    So: make it absolute by hand if it is not already, switch the separators, prefix. No
    normalisation anywhere. Safe because ROOT is absolute and everything joined onto it comes
    from os.walk() or from a URL path, never with `..` components.
    """
    if os.name != "nt":
        return path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    path = path.replace("/", "\\")
    if path.startswith("\\\\?\\"):
        return path
    return "\\\\?\\" + path


# --------------------------------------------------------------------------------- output


class Log:
    """One log file per archive, plus a pre-grepped error file, both append-only."""

    def __init__(self, name):
        os.makedirs(LOGDIR, exist_ok=True)
        self._lock = threading.Lock()
        self.write_failures = 0
        self._main = open(os.path.join(LOGDIR, name + ".log"), "a", encoding="utf-8")
        self._err = open(os.path.join(LOGDIR, "errors-" + name + ".txt"), "a", encoding="utf-8")

    def line(self, text, error=False):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock:
                self._main.write("%s %s\n" % (stamp, text))
                self._main.flush()
                if error:
                    self._err.write("%s %s\n" % (stamp, text))
                    self._err.flush()
        except OSError as exc:
            # The log lives under ROOT, on the same volume as the terabytes being written to
            # it, so logging is among the first things to fail when that volume fills up.
            # Logging must not then take down the thread that was trying to report the
            # problem -- it is called from inside download(), outside any handler of its own.
            self.write_failures += 1
            if self.write_failures == 1:
                sys.stderr.write("LOG WRITE FAILED (%s) -- continuing without it\n" % exc)
                sys.stderr.flush()

    def close(self):
        with self._lock:
            self._main.close()
            self._err.close()


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.found = 0          # files the producer has queued
        self.found_bytes = 0    # their rounded sizes, from the listings
        self.dirs = 0
        self.done = 0
        self.skipped = 0
        self.bytes = 0
        self.permfail = 0
        self.failed = 0
        self.retries = 0
        self.collisions = 0
        self.listfail = 0
        self.enum_done = False


def human(n):
    for unit in ("B", "K", "M", "G", "T"):
        if abs(n) < 1024 or unit == "T":
            return "%.1f%s" % (n, unit)
        n /= 1024.0


def reporter(stats, log, stop, interval):
    """A progress line every `interval` seconds.

    Two rates, because they answer different questions: the windowed one says whether the
    run is healthy right now, the average one is what the ETA is built on.
    """
    t0 = time.time()
    last_t, last_done, last_bytes = t0, 0, 0
    while not stop.wait(interval):
        now = time.time()
        with stats.lock:
            done, byts, found = stats.done, stats.bytes, stats.found
            found_bytes, skipped = stats.found_bytes, stats.skipped
            enum_done, permfail, failed = stats.enum_done, stats.permfail, stats.failed
            dirs, retries, collisions = stats.dirs, stats.retries, stats.collisions
            listfail = stats.listfail

        dt = max(now - last_t, 1e-6)
        cur_fps = (done - last_done) / dt
        cur_bps = (byts - last_bytes) / dt
        elapsed = max(now - t0, 1e-6)
        avg_fps = done / elapsed
        avg_bps = byts / elapsed
        last_t, last_done, last_bytes = now, done, byts

        # The denominator only stops moving once enumeration finishes, so say which it is.
        total = "%d" % found if enum_done else "%d+" % found
        if enum_done and avg_bps > 0 and found_bytes > byts:
            eta = (found_bytes - byts) / avg_bps
            eta_s = " eta %dh%02dm" % (eta // 3600, (eta % 3600) // 60)
        else:
            eta_s = ""

        log.line(
            "PROGRESS %d/%s files (%.1f/s now, %.1f/s avg)  %s/%s (%s/s now, %s/s avg)  "
            "dirs %d  skip %d  retry %d  403 %d  fail %d  collide %d  lostdir %d%s"
            % (done, total, cur_fps, avg_fps,
               human(byts), human(found_bytes) if found_bytes else "?",
               human(cur_bps), human(avg_bps),
               dirs, skipped, retries, permfail, failed, collisions, listfail, eta_s)
        )


# ------------------------------------------------------------------------------- transfer


def open_url(url):
    """Open a URL, percent-encoding whatever the server left raw.

    Generated indexes emit properly encoded hrefs. Hand-made pages do not: ps-2.kev009.com links
    files called `AS400 Processor Summary.html`, with the space unescaped, and urllib refuses
    those outright with `InvalidURL: URL can't contain control characters`. Measured before the
    fix: 188 failures in the first 221 files -- better than one in four, silently lost.

    Only the request is quoted. The unencoded URL stays canonical everywhere else, so the local
    filename, the seen-set and the collision key are unaffected. `safe="/%"` leaves an already
    encoded %XX alone rather than turning it into %25XX.
    """
    parts = urllib.parse.urlsplit(url)
    safe = urllib.parse.urlunsplit((
        parts.scheme, parts.netloc,
        urllib.parse.quote(parts.path, safe="/%"),
        urllib.parse.quote(parts.query, safe="=&%"),
        ""))
    req = urllib.request.Request(safe, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT)


def fetch_text(url):
    """Fetch one directory listing, with the same retries a file download gets.

    This must not be a bare request. A listing that fails takes its whole subtree with it --
    every file below it is never queued, never counted, and never missed by anything. The
    earlier wget run over this archive hit 35 transient timeouts, all of which recovered on
    retry; without a retry here each one would have silently amputated a branch, and the run
    would still have ended saying DONE.
    """
    reason = "unknown"
    for attempt in range(ATTEMPTS):
        try:
            with open_url(url) as resp:
                # The FINAL url, not the requested one. A listing that redirected -- `/dir` to
                # `/dir/` is the common case -- must have its relative children resolved against
                # where it ended up, or every one of them lands a level too high and points at
                # something that does not exist. urljoin("http://h/a/dir", "x.pdf") is
                # "http://h/a/x.pdf"; against "http://h/a/dir/" it is "http://h/a/dir/x.pdf".
                # Latent rather than active today, and silent when it fires, which is why it is
                # worth two lines.
                return resp.read().decode("utf-8", "replace"), resp.geturl()
        except urllib.error.HTTPError as exc:
            if exc.code in PERMANENT:
                raise
            reason = "HTTP %d" % exc.code
        except Exception as exc:  # noqa: BLE001
            reason = "%s: %s" % (type(exc).__name__, exc)
        if attempt < ATTEMPTS - 1:
            time.sleep(2 ** attempt)
    raise IOError(reason)


def download(url, dest, stats, log, mtime=None):
    """Fetch one file. Returns 'ok' | 'skip' | 'permfail' | 'fail'.

    `mtime` is the date from the directory listing, used only if the response carries no
    Last-Modified of its own -- the header is exact to the second, the listing to the minute.
    """
    # A server may offer one path as both a file and a directory; a filesystem cannot. Where
    # the directory already exists locally it is the one holding content, so the file form is
    # not fetched -- and saying so beats failing the same rename on every future run.
    #
    # This is the other half of defect 9 in README.md. `/rs6000/` links a subdirectory without a
    # trailing slash, so the crawler asks for it as a file; once the directory is populated the
    # rename onto it fails with PermissionError, forever.
    if os.path.isdir(long_path(dest)):
        log.line("SKIPPED (a directory occupies this path) %s" % url)
        return "skip"

    reason = "unknown"
    for attempt in range(ATTEMPTS):
        try:
            with open_url(url) as resp:
                # A 301 onto the same path with a trailing slash means this was never a file:
                # the server is saying "that is a directory". Both cases that cost us failures
                # on 2026-08-26 were exactly this --
                #   web-docs.gsi.de/.../HPUX/PA/1020 -> .../PA/1020/
                #   ardent-tool.com/615x/AOS_43/Docs -> .../Docs/
                # -- and because urllib follows redirects, what arrived was the directory's own
                # index page, about to be written under the directory's name. Saving it would
                # have been wrong even where the rename happened to succeed: it is not a
                # document, and on the next run it would be re-fetched and re-collide forever.
                # Nothing is lost by skipping, because the slash form is a separate URL that the
                # producer enumerates on its own.
                final = resp.geturl()
                if final != url and final.rstrip("/") == url.rstrip("/") and final.endswith("/"):
                    log.line("SKIPPED (redirects to a directory) %s" % url)
                    return "skip"

                clen = resp.headers.get("Content-Length")
                clen = int(clen) if clen and clen.isdigit() else None
                stamp = http_date(resp.headers.get("Last-Modified")) or mtime

                # Resume: a file already present at exactly the advertised length is done.
                # The listing size is rounded and cannot be used for this -- Content-Length
                # is the only exact figure available.
                if clen is not None:
                    try:
                        if os.path.getsize(long_path(dest)) == clen:
                            return "skip"
                    except OSError:
                        pass

                try:
                    os.makedirs(long_path(os.path.dirname(dest)), exist_ok=True)
                except FileExistsError:
                    # A *file* occupies a path component that has to be a directory. The redirect
                    # check above stops this being *created*, but it cannot undo one that a
                    # previous run already wrote: on 2026-08-27 the fixed gsi-collection run hit
                    # this 260 times, blocked by seven index pages the broken run of the day
                    # before had saved under the names of the directories they describe.
                    #
                    # Returning "fail", not "skip". This IS a lost file, and the first version of
                    # this branch returned "skip" -- so the run counted 260 losses, logged every
                    # one, and still ended COMPLETE and wrote a marker. A verdict that survives
                    # its own error log is worse than no verdict.
                    log.line("LOST (a file occupies a parent directory of this path) %s" % url,
                             error=True)
                    return "fail"
                tmp = dest + ".part"
                got = 0
                with open(long_path(tmp), "wb") as fh:
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        fh.write(chunk)
                        got += len(chunk)

            # A short read is a failed transfer, not a small file. Without this check a
            # truncated download is indistinguishable from a complete one on the next run.
            if clen is not None and got != clen:
                reason = "short read %d of %d" % (got, clen)
                try:
                    os.unlink(long_path(tmp))
                except OSError:
                    pass
                raise IOError(reason)

            # Re-check, because the guard at the top of this function ran before the transfer
            # and a directory can appear at this path meanwhile. On a hand-written site the same
            # name is served both as a page and as a directory -- ardent-tool has
            # `615x/AOS_43/Docs` and `615x/AOS_43/Docs/` -- and whichever worker gets there
            # second raced the other. It surfaced as WinError 5 from os.replace, which reads
            # like a permissions problem and is not one.
            if os.path.isdir(long_path(dest)):
                try:
                    os.unlink(long_path(tmp))
                except OSError:
                    pass
                log.line("SKIPPED (a directory took this path while downloading) %s" % url)
                return "skip"

            os.replace(long_path(tmp), long_path(dest))
            if stamp:
                try:
                    os.utime(long_path(dest), (stamp, stamp))
                except OSError:
                    pass
            with stats.lock:
                stats.bytes += got
            return "ok"

        except urllib.error.HTTPError as exc:
            if exc.code in PERMANENT:
                log.line("PERMFAIL HTTP %d %s" % (exc.code, url), error=True)
                return "permfail"
            reason = "HTTP %d" % exc.code
        except Exception as exc:  # noqa: BLE001 -- socket, DNS, TLS, disk; all retryable
            reason = "%s: %s" % (type(exc).__name__, exc)

        if attempt < ATTEMPTS - 1:
            with stats.lock:
                stats.retries += 1
            log.line("RETRY %d/%d %s %s" % (attempt + 1, ATTEMPTS - 1, reason, url), error=True)
            time.sleep(2 ** attempt)

    log.line("FAIL %s %s" % (reason, url), error=True)
    return "fail"


def worker(q, root, base_url, stats, log):
    while True:
        item = q.get()
        try:
            if item is None:
                return
            # A worker must never die. download() handles what it anticipates; this catches
            # what it does not, because a thread that exits here is gone for the rest of the
            # run -- and once all of them are gone the producer blocks forever on the full
            # queue, silently, with the reporter still claiming the run is alive.
            #
            # THE UNPACK BELONGS INSIDE THIS GUARD. It used to sit one line above it, outside,
            # and that one line was enough: when the queue item grew a third field, anything
            # still pushing the old two-field shape killed all eight workers with a ValueError
            # and the run wedged in precisely the way described above -- no error, no progress,
            # forever. Measured 2026-08-29. The item is logged rather than the URL, because on
            # a malformed item there is no URL yet.  [2026-08-29]
            try:
                url, _size, mtime = item
                result = download(url, local_path(root, base_url, url), stats, log, mtime)
            except Exception as exc:  # noqa: BLE001
                log.line("WORKER-ERROR %s: %s %r" % (type(exc).__name__, exc, item), error=True)
                result = "fail"
            with stats.lock:
                if result == "ok":
                    stats.done += 1
                elif result == "skip":
                    stats.done += 1
                    stats.skipped += 1
                elif result == "permfail":
                    stats.permfail += 1
                else:
                    stats.failed += 1
        finally:
            q.task_done()


def release_workers(q, pool, log):
    """Put one sentinel per worker, on every exit path, without dropping queued work.

    Two hazards make this less trivial than it looks. The queue is bounded, so right after a
    normal enumeration it is typically full and a plain put() would block; and if the
    producer raised, the workers may already be gone, in which case a blocking put() waits
    forever. So: wait for room while at least one worker is alive to make room, and give up
    the moment none are. Queued items are never discarded -- if workers are alive they will
    drain them, and if they are not, the process is ending anyway.
    """
    for _ in pool:
        while True:
            try:
                q.put(None, timeout=10)
                break
            except queue.Full:
                if not any(t.is_alive() for t in pool):
                    log.line("RELEASE: no worker left to receive a sentinel", error=True)
                    return


def put_item(q, item, alive, log):
    """Block until the queue has room, but never past the point where anyone can make room.

    A bounded queue means the producer waits for the workers -- which is the design. It also
    means that if the workers are gone, the producer waits forever, with the reporter still
    printing and nothing in any log to say why the counters stopped. Checking liveness
    turns that silent wedge into an abort with a reason.
    """
    while True:
        try:
            q.put(item, timeout=10)
            return
        except queue.Full:
            if alive is not None and not alive():
                log.line("ABORT: every worker is dead, nothing can take %s" % item[0],
                         error=True)
                raise RuntimeError("all download workers died; see the error log")


def producer(q, base_url, stats, log, case_sensitive=False, alive=None, exclude=(), seeds=(),
             html_crawl=False):
    """Walk the listings depth-first, pushing every file URL onto the queue.

    Blocking on a full queue is the point, not a limitation: it is what keeps memory flat
    and stops the producer from racing 136000 entries ahead of the downloaders.

    `seeds` are extra starting directories under base_url, for trees the base page does not
    link. They are ordinary starting points, not a special case: everything below them is
    walked, deduplicated and collision-checked exactly like everything below base_url.
    """
    starts = [base_url]
    for s in seeds:
        if not s.startswith(base_url):
            # Would be mapped to the wrong local path by local_path(), which strips base_url.
            log.line("SEED IGNORED (outside base URL) %s" % s, error=True)
            continue
        if s not in starts:
            starts.append(s)
    if len(starts) > 1:
        log.line("SEEDS %d extra starting points: %s"
                 % (len(starts) - 1, ", ".join(s[len(base_url):] for s in starts[1:])))
    pending = list(starts)
    seen = set(starts)
    # Case-folded local path -> the first URL that claimed it. On a case-insensitive volume
    # a second claimant would overwrite the first without any error being raised anywhere,
    # so the collision has to be caught here or it is not caught at all.
    claimed = {}
    while pending:
        url = pending.pop()
        try:
            # Rebind url to where the fetch actually ended up, so the relative links below
            # resolve against the right base. See fetch_text().
            body, url = fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            # A dead link on a hand-written site is the site's own rot, not an amputated
            # subtree, and the file branch has already counted it as a permanent 404. Counting
            # it again as a lost listing would hold the mirror at INCOMPLETE forever over ten
            # broken links somebody else left behind -- ardent-tool has exactly that, under
            # CPU/PowerStacker/. A generated index is different: there a linked directory that
            # 404s really does mean a subtree went missing, so this relaxation is HTML_CRAWL
            # only.
            if (html_crawl and isinstance(exc, urllib.error.HTTPError)
                    and exc.code in PERMANENT):
                log.line("DEADLINK HTTP %d %s" % (exc.code, url))
                continue
            # Counted, not just logged: an amputated subtree must be visible in the DONE
            # line and in the exit code, or an incomplete mirror looks like a clean one.
            with stats.lock:
                stats.listfail += 1
            log.line("LISTFAIL %s: %s %s" % (type(exc).__name__, exc, url), error=True)
            continue
        with stats.lock:
            stats.dirs += 1

        for href, size, mtime in parse_listing(body):
            child = urllib.parse.urljoin(url, href)
            if not child.startswith(base_url) or child in seen:
                continue
            seen.add(child)
            if href.endswith("/"):
                rel = child[len(base_url):]
                if any(rel.startswith(x) for x in exclude):
                    log.line("SKIPPED (excluded) %s" % child)
                    continue
                pending.append(child)
            else:
                key = local_path("", base_url, child).lower()
                if key in claimed:
                    with stats.lock:
                        stats.collisions += 1
                    # On a case-sensitive target these are two distinct files and both are
                    # wanted; skipping would be the bug. On a case-insensitive one they
                    # cannot both exist, so keep the first and say which was dropped --
                    # a deterministic, logged loss beats whichever download finished last.
                    log.line("COLLISION%s %s <- %s (already claimed by %s)"
                             % ("" if case_sensitive else " DROPPED", key, child, claimed[key]),
                             error=True)
                    if not case_sensitive:
                        continue
                claimed[key] = child
                with stats.lock:
                    stats.found += 1
                    if size:
                        stats.found_bytes += size
                put_item(q, (child, size, mtime), alive, log)

                # A hand-written site is a tree of pages, not of directories: ardent-tool links
                # `docs/docs.html`, which does not end in `/` and would therefore be fetched as
                # a leaf and never opened. One page there links 87 documents. So for those
                # archives an HTML page is BOTH content to keep and a listing to walk -- queued
                # above, enumerated here. `seen` already holds it, so it is walked once.
                if html_crawl and HTML_PAGE.search(child):
                    pending.append(child)

    with stats.lock:
        stats.enum_done = True
    log.line("ENUM COMPLETE: %d directories, %d files, ~%s, %d unreadable listings"
             % (stats.dirs, stats.found, human(stats.found_bytes), stats.listfail))
    # Sentinels are deliberately NOT queued here. If this function raises, the workers must
    # still be released, so their delivery belongs to the caller's finally -- see mirror().


# ----------------------------------------------------------------------------------- main


def mirror(name, base_url, args):
    if name in FROZEN:
        # Returning None is the same signal an already-complete archive gives: nothing was
        # transferred, and that is not a failure. The exit code must not suggest otherwise.
        print("    FROZEN -- %s" % FROZEN[name], flush=True)
        return None
    if name in RSYNC:
        return rsync_mirror(name, RSYNC[name], args)

    root = os.path.join(ROOT, name)
    marker = os.path.join(root, COMPLETE_MARKER)

    # A completed mirror is 200 GB that took hours and cannot be re-fetched if the source
    # disappears. --fresh deletes it outright, and one absent-minded invocation is all it takes,
    # so a finished mirror has to be un-marked deliberately before it can be destroyed.
    if args.fresh and os.path.exists(marker):
        print("  REFUSED: %s carries %s -- it is a completed mirror." % (name, COMPLETE_MARKER),
              flush=True)
        print("  Delete that file by hand if you really mean to re-fetch it from scratch:",
              flush=True)
        print("      del \"%s\"" % marker, flush=True)
        return None

    fresh_root = args.fresh or not os.path.isdir(root)
    if args.fresh and os.path.isdir(root):
        print("  removing %s" % root, flush=True)
        shutil.rmtree(long_path(root))
    os.makedirs(long_path(root), exist_ok=True)

    log = Log(name)

    # Only meaningful on a directory with nothing in it yet -- the flag is inherited by
    # children created afterwards, never applied retroactively.
    want_cs = args.case_sensitive or name in NEEDS_CASE_SENSITIVE
    case_sensitive = is_case_sensitive(root)
    if want_cs and not case_sensitive:
        if not fresh_root:
            print("  WARNING: %s wants case sensitivity but already exists without it. The flag "
                  "is inherited only by directories created after it is set, so it cannot be "
                  "applied now -- delete the directory and start over, or collisions will be "
                  "dropped." % name, flush=True)
            log.line("CASE-SENSITIVE wanted but directory pre-exists without it", error=True)
        else:
            result = enable_case_sensitivity(root)
            # fsutil's exit code says the command ran, not that the flag took hold. Ask the
            # directory itself -- it is one file create and it is the thing being claimed.
            case_sensitive = is_case_sensitive(root)
            log.line("CASE-SENSITIVE %s" % ("enabled" if case_sensitive else result))
    elif case_sensitive:
        log.line("CASE-SENSITIVE already set on %s" % root)

    stats = Stats()
    q = queue.Queue(maxsize=args.queue)
    stop = threading.Event()

    log.line("=" * 70)
    log.line("START %s <%s> workers=%d queue=%d fresh=%s"
             % (name, base_url, WORKERS_BY_ARCHIVE.get(name, args.workers), args.queue, args.fresh))

    rep = threading.Thread(target=reporter, args=(stats, log, stop, args.interval), daemon=True)
    rep.start()
    # daemon=True so a worker parked in q.get() can never block interpreter shutdown. The
    # sentinel handling below is what normally ends them; this is the backstop for the case
    # where it cannot.
    workers = WORKERS_BY_ARCHIVE.get(name, args.workers)
    pool = [threading.Thread(target=worker, args=(q, root, base_url, stats, log), daemon=True)
            for _ in range(workers)]
    for t in pool:
        t.start()

    t0 = time.time()
    try:
        producer(q, base_url, stats, log, case_sensitive,
                 alive=lambda: any(t.is_alive() for t in pool),
                 exclude=EXCLUDE.get(name, ()),
                 seeds=tuple(SEEDS.get(name, ())) + tuple(args.seed or ()),
                 html_crawl=name in HTML_CRAWL)
    except KeyboardInterrupt:
        log.line("INTERRUPTED -- rerun without --fresh to continue where it stopped",
                 error=True)
        raise
    finally:
        release_workers(q, pool, log)
        for t in pool:
            t.join(timeout=600)
        stop.set()

    elapsed = time.time() - t0
    verdict = "COMPLETE" if not (stats.listfail or stats.failed) else "INCOMPLETE"
    log.line("DONE %s %s in %dh%02dm  files=%d (skip %d)  bytes=%s  403=%d  fail=%d  "
             "retries=%d  collisions=%d  unreadable-listings=%d"
             % (name, verdict, elapsed // 3600, (elapsed % 3600) // 60,
                stats.done, stats.skipped, human(stats.bytes),
                stats.permfail, stats.failed, stats.retries, stats.collisions,
                stats.listfail))
    if stats.listfail:
        # Each of these took a whole subtree with it. Say so in the loudest available place.
        log.line("WARNING %d directory listings could not be read after %d attempts; "
                 "every file below them is missing. Re-run to pick them up."
                 % (stats.listfail, ATTEMPTS), error=True)

    if verdict == "COMPLETE":
        write_marker(root, name, base_url, stats, elapsed)
        print("    marked complete: %s" % os.path.join(name, COMPLETE_MARKER), flush=True)

    log.close()

    # Re-mirroring is how the checksum index stays current: whatever this run changed is exactly
    # what gets re-hashed, and everything it left alone is taken from the previous index by size
    # and mtime. A run that downloaded nothing therefore costs a stat of the tree, not a read of
    # it. Suppress with --no-index when the point of the run was only the download.
    if not args.no_index:
        build_index(name, args.hash_workers, interval=args.interval)

    return stats


def iter_tree(root):
    """Yield (relative path, absolute path) for every file that counts as archive content.

    The single definition of "what is in this mirror". scan_tree() counts what this yields and
    build_index() hashes it, so the completion marker and the checksum index cannot disagree
    about the set of files -- which they would, eventually and silently, if each walked the tree
    with its own copy of the rules.

    `.part` and `.suspect` files are excluded. Both mean "arrived, but is not the file": `.part`
    is a half-finished download -- one outage on 2026-08-23 left 11 of them holding 741 MB --
    and `.suspect` is one that completed and then failed verification, which is how
    wayback-salvage.py sets aside a transfer whose length did not match what the source claimed.
    Counting either would inflate the figure written into the completion marker, which is the
    figure `--verify` later compares the tree against, and would put a truncated file into the
    checksum index under a hash that is perfectly valid for the wrong bytes.  [2026-08-29]

    Relative paths use forward slashes, on every platform, because they are written verbatim
    into a file that `sha256sum -c` has to be able to read on a Unix box.
    """
    for dirpath, dirnames, names in os.walk(root):
        top = os.path.normcase(dirpath) == os.path.normcase(root)
        for f in names:
            if f.endswith(".part") or f.endswith(".suspect"):
                continue
            # only at the top of the mirror -- an archive may legitimately contain a README.md
            if top and f in OWN_FILES:
                continue
            full = os.path.join(dirpath, f)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


# ---------------------------------------------------------------------------------- rsync


def rsync_sources(cfg):
    """-> [(url, subdirectory or "")]. One entry for a single-module archive, several otherwise.

    vtda is five sibling rsync modules with no common parent, so a mirror of it has to be
    assembled rather than copied. bitsavers is one module and lands at the root.
    """
    if "sources" in cfg:
        return list(cfg["sources"])
    return [(cfg["url"], "")]


def rsync_command(cfg, url, dest, dry_run=False):
    """Build the rsync argv, native if rsync is on PATH, in a container otherwise.

    Windows has no rsync and installing one for a single archive is a poor trade; where Docker is
    already available, an alpine container with the package added costs a few megabytes. The
    container form mounts the destination at /m, so the paths inside are fixed and the filter
    rules stay identical between the two forms -- a filter that behaved differently depending on
    how rsync was started would be a trap worth more than the convenience.
    """
    opts = ["-a", "--partial", "--no-motd"]
    if dry_run:
        # No progress meter here: with nothing being transferred it prints a line per file and
        # buries the summary, which is the only part of a dry run anyone reads.
        opts += ["-n", "--stats"]
    elif sys.stdout.isatty():
        # A progress meter is for somebody watching. Redirected to a file it is pure waste:
        # measured 2026-08-29 across 47 captured runs, 494 010 of 494 247 lines were the meter
        # redrawing itself -- 36.5 MB -- and the 182 distinct lines that were not were all
        # duplicates of what the archive's own .log already records, with a timestamp.
        #
        # So it depends on whether anyone is looking. Every long transfer here is started
        # detached, and those now leave the tool's own log as the only record, which is the one
        # worth keeping.
        opts.append("--info=progress2")
    else:
        # Not watching: say what was transferred, once, at the end.
        opts.append("--stats")
    if cfg.get("delete"):
        opts.append("--delete")
    opts += list(cfg.get("filter", ()))

    if shutil.which("rsync"):
        return ["rsync"] + opts + [url, dest + os.sep], False
    if not shutil.which("docker"):
        return None, False
    inner = "apk add --no-cache rsync >/dev/null 2>&1 && exec rsync %s %s /m/" % (
        " ".join("'%s'" % o for o in opts), "'%s'" % url)
    return ["docker", "run", "--rm", "-v", "%s:/m" % dest.replace("\\", "/"),
            "alpine:latest", "sh", "-c", inner], True


def rsync_mirror(name, cfg, args):
    """Fetch one archive with rsync and mark it exactly like an HTTP-crawled one."""
    root = os.path.join(ROOT, name)
    fresh_root = not os.path.isdir(root)
    os.makedirs(long_path(root), exist_ok=True)
    log = Log(name)

    # Same rule as the HTTP path, and for the same reason: the NTFS flag is inherited only by
    # directories created after it is set, never applied retroactively. So it is now or never,
    # and "now" costs nothing. rsync preserves the source's names exactly, which is precisely
    # when two names differing only in case become two files.
    if fresh_root and (args.case_sensitive or name in NEEDS_CASE_SENSITIVE):
        result = enable_case_sensitivity(root)
        enabled = is_case_sensitive(root)          # measured, not taken from the exit code
        log.line("CASE-SENSITIVE %s" % ("enabled" if enabled else result))
        print("    case-sensitive: %s" % ("yes" if enabled else result), flush=True)
    elif not fresh_root and name in NEEDS_CASE_SENSITIVE and not is_case_sensitive(root):
        print("  WARNING: %s wants case sensitivity but already exists without it -- delete the "
              "directory and start over, or names differing only in case will collide." % name,
              flush=True)
        log.line("CASE-SENSITIVE wanted but directory pre-exists without it", error=True)

    sources = rsync_sources(cfg)

    before_n, before_b = scan_tree(root)
    log.line("=" * 70)
    log.line("START %s -- %d source(s)%s"
             % (name, len(sources), " (dry run)" if args.dry_run else ""))
    log.line("FILTER %s" % (" ".join(cfg.get("filter", ())) or "(none)"))

    t0 = time.time()
    worst = 0
    for url, sub in sources:
        dest = os.path.join(root, sub) if sub else root
        os.makedirs(long_path(dest), exist_ok=True)
        cmd, in_docker = rsync_command(cfg, url, dest, dry_run=args.dry_run)
        if cmd is None:
            print("  SKIPPED %s: neither rsync nor docker is available" % name, flush=True)
            log.line("NO RSYNC AND NO DOCKER -- skipped", error=True)
            log.close()
            return None
        log.line("SOURCE %s -> %s via %s" % (url, sub or ".",
                                             "docker/rsync" if in_docker else "rsync"))
        print("    %s -> %s" % (url, sub or "."), flush=True)
        # Retry, for the same reason download() and fetch_text() do: a transfer that stopped is
        # not a transfer that failed. bitsavers dropped the connection after 140 GB of a 533 GB
        # run on 2026-08-27 -- "connection unexpectedly closed", rsync exit 12 -- and that single
        # disconnect ended three hours of work with nothing wrong with it. rsync resumes from
        # what is on disk, so an attempt costs a file-list rebuild and nothing else.
        #
        # A LONG TRANSFER MUST ASSUME IT WILL BE INTERRUPTED. The far end is somebody else's
        # server, under load, and 533 GB is many hours of it.
        rc = None
        refusals = 0
        for attempt in range(RSYNC_ATTEMPTS):
            if attempt:
                # TWO DIFFERENT FAILURES, TWO DIFFERENT ANSWERS.
                #
                #   rc 12  the stream broke mid-transfer. The server was willing and something
                #          went wrong. Retry soon -- rsync resumes from what is on disk.
                #   rc 10  socket I/O, in practice "Connection refused". The server is NOT
                #          willing. That is an answer, not a fault.
                #
                # The first version of this loop treated both alike and knocked on a closed door
                # every five minutes, nine times running, at exactly the archive whose front page
                # asks people not to hammer it. Backing off further is not the fix: after two
                # refusals this gives up and says so. Repeating a question is not a technique for
                # getting a different answer.  [2026-08-28]
                if rc in RSYNC_REFUSED:
                    refusals += 1
                    if refusals > RSYNC_REFUSAL_LIMIT:
                        log.line("REFUSED %dx by %s -- giving up. The server is declining "
                                 "connections. Wait hours, and prefer one of its mirrors."
                                 % (refusals, url), error=True)
                        print("    GIVING UP: %s is refusing connections (%dx). "
                              "Not knocking again." % (url, refusals), flush=True)
                        break
                    wait = 900
                else:
                    wait = min(60 * attempt, 300)
                log.line("RETRY %d/%d in %ds after rc=%d %s"
                         % (attempt + 1, RSYNC_ATTEMPTS, wait, rc, url), error=True)
                print("    rc=%d -- attempt %d/%d in %ds"
                      % (rc, attempt + 1, RSYNC_ATTEMPTS, wait), flush=True)
                time.sleep(wait)
            try:
                rc = subprocess.call(cmd)
            except KeyboardInterrupt:
                log.line("INTERRUPTED -- rsync resumes on the next run", error=True)
                log.close()
                raise
            if rc == 0 or args.dry_run:
                break
        log.line("SOURCE DONE %s rc=%s after %d attempt(s)" % (url, rc, attempt + 1))
        # The worst exit code wins: one failed module must not be hidden by four that worked.
        worst = rc if rc and not worst else worst
    rc = worst
    elapsed = time.time() - t0

    n, total = scan_tree(root)
    log.line("DONE %s rc=%d in %dh%02dm  files %d -> %d  bytes %d -> %d"
             % (name, rc, elapsed // 3600, (elapsed % 3600) // 60,
                before_n, n, before_b, total))
    print("    rc=%d, %d -> %d files, %s -> %s"
          % (rc, before_n, n, human(before_b), human(total)), flush=True)

    if args.dry_run:
        log.close()
        return None
    if rc != 0:
        # rsync's own exit code is the verdict. Marking a tree complete because the transfer
        # merely stopped is exactly the failure the HTTP side already learned about.
        print("    NOT marked complete: rsync exited %d" % rc, flush=True)
        log.line("INCOMPLETE rsync rc=%d" % rc, error=True)
        log.close()
        return None

    class _S:
        permfail = 0
    write_marker(root, name, sources[0][0] if len(sources) == 1
                 else "%d rsync modules" % len(sources), _S(), elapsed)
    print("    marked complete: %s" % os.path.join(name, COMPLETE_MARKER), flush=True)
    log.close()
    if not args.no_index:
        build_index(name, args.hash_workers, interval=args.interval)
    return None


def scan_tree(root):
    """Count the files under root and their total size, ignoring our own files."""
    n = total = 0
    for _, full in iter_tree(root):
        try:
            total += os.path.getsize(full)
            n += 1
        except OSError:
            pass
    return n, total


def write_marker(root, name, base_url, stats, elapsed):
    n, total = scan_tree(root)
    with open(os.path.join(root, COMPLETE_MARKER), "w", encoding="utf-8") as fh:
        fh.write("archive       %s\n" % name)
        fh.write("source        %s\n" % base_url)
        fh.write("completed     %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        fh.write("duration      %dh%02dm\n" % (elapsed // 3600, (elapsed % 3600) // 60))
        fh.write("files         %d\n" % n)
        fh.write("bytes         %d\n" % total)
        fh.write("permanent-404 %d\n" % stats.permfail)
        fh.write("\n"
                 "This mirror is complete. `--fresh` refuses to run while this file exists;\n"
                 "delete it by hand if you really mean to fetch the whole archive again.\n"
                 "`--verify` compares the tree against the two figures above.\n")


# ------------------------------------------------------------------------------ checksums


def sha256_file(path):
    """SHA-256 of one file, read in HASH_CHUNK pieces so a 4 GB ISO does not become 4 GB of RAM."""
    h = hashlib.sha256()
    with open(long_path(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sums_line(digest, rel):
    """One line of GNU sha256sum output.

    `*` is the binary-mode marker, which is what this content is. GNU escapes a path containing
    a backslash or a newline by prefixing the whole line with one backslash; neither character
    can occur in a Windows filename, so this never fires here -- it is written down so that the
    format stays correct rather than accidentally correct.
    """
    if "\\" in rel or "\n" in rel:
        return "\\%s *%s\n" % (digest, rel.replace("\\", "\\\\").replace("\n", "\\n"))
    return "%s *%s\n" % (digest, rel)


def read_index(path):
    """Load a master index: relative path -> (size, mtime_ns, sha256).

    A missing, truncated or malformed file is not an error and is not fatal. The index is a cache
    of work already done, and every row is revalidated against the file's own size and mtime
    before it is reused, so damage here costs time, never correctness.
    """
    out = {}
    try:
        with open(long_path(path), "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    out[row["path"]] = (int(row["size"]), int(row["mtime_ns"]), row["sha256"])
                except (KeyError, TypeError, ValueError):
                    continue
    except OSError:
        return {}
    return out


def write_index(index_path, sums_path, rows):
    """Write the master CSV, then derive the sha256sum manifest from it. Both atomically.

    Two files, one source of truth. Deriving the second from the first -- rather than writing
    both from the same loop -- is what keeps them from ever disagreeing.

    Written to a temporary name and renamed, because the alternative is that an interrupted run
    leaves behind a half-written manifest that still looks like a manifest.
    """
    ordered = sorted(rows.items())

    tmp = index_path + ".tmp"
    with open(long_path(tmp), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(("path", "size", "mtime_ns", "sha256"))
        for rel, (size, mtime_ns, digest) in ordered:
            w.writerow((rel, size, mtime_ns, digest))
    os.replace(long_path(tmp), long_path(index_path))

    tmp = sums_path + ".tmp"
    with open(long_path(tmp), "w", encoding="utf-8", newline="") as fh:
        for rel, (_, _, digest) in ordered:
            fh.write(sums_line(digest, rel))
    os.replace(long_path(tmp), long_path(sums_path))


def hash_tree(entries, rows, workers, interval, checkpoint, label=""):
    """Hash `entries` into `rows`, in bounded batches, checkpointing as it goes.

    `entries` is a list of (relpath, fullpath, size, mtime_ns); `rows` is the index being
    assembled and is mutated in place. `checkpoint` is called with no arguments to persist it.

    Shared by the per-mirror index and the collection-level one so that both hash, batch and
    checkpoint identically -- there is one implementation of this, deliberately.
    """
    done = done_bytes = 0
    total_bytes = sum(e[2] for e in entries)
    failed = []
    t0 = last_print = last_write = time.time()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            for start in range(0, len(entries), HASH_BATCH):
                batch = entries[start:start + HASH_BATCH]
                # One batch in flight at a time. Submitting all 190 000 at once would build the
                # very in-memory list this program was written to avoid -- see the module
                # docstring on the bounded queue.
                futures = [(item, ex.submit(sha256_file, item[1])) for item in batch]
                for (rel, _, size, mtime_ns), fut in futures:
                    try:
                        rows[rel] = (size, mtime_ns, fut.result())
                    except OSError as exc:
                        failed.append((rel, str(exc)))
                        continue
                    done += 1
                    done_bytes += size

                now = time.time()
                if now - last_print >= interval:
                    rate = done_bytes / max(now - t0, 1e-6)
                    left = (total_bytes - done_bytes) / rate if rate else 0
                    print("      %s%d/%d  %s of %s  %.0f MB/s  ~%dm left"
                          % (label, done, len(entries), human(done_bytes), human(total_bytes),
                             rate / 1e6, left / 60), flush=True)
                    last_print = now
                # A partial index is a valid index: everything already hashed is reused by the
                # next run, so an interrupted pass costs the current batch and nothing else.
                if now - last_write >= 60.0:
                    checkpoint()
                    last_write = now
    finally:
        checkpoint()

    return done, done_bytes, failed, time.time() - t0


def build_index(name, workers, force=False, interval=10.0):
    """Bring the checksum index of one mirror up to date, hashing only what changed.

    A file is taken from the previous index when its size AND its mtime both match what was
    recorded. That is the entire reason the CSV carries those two columns: a re-run over an
    unchanged 702 GB archive hashes nothing and finishes in the time it takes to stat 190 000
    files. Only genuinely new or genuinely rewritten files cost anything.

    mtime is compared in nanoseconds, not seconds. A one-second resolution would let a file
    rewritten within the same second as its predecessor keep the old hash.
    """
    root = os.path.join(ROOT, name)
    if not os.path.isdir(root):
        print("  %-24s not a directory -- skipped" % name, flush=True)
        return None
    idx_path = os.path.join(root, INDEX_FILE)
    sums_path = os.path.join(root, SUMS_FILE)

    old = {} if force else read_index(idx_path)
    rows = {}
    todo = []
    todo_bytes = 0

    for rel, full in iter_tree(root):
        try:
            st = os.stat(long_path(full))
        except OSError:
            continue
        prev = old.get(rel)
        if prev is not None and prev[0] == st.st_size and prev[1] == st.st_mtime_ns:
            rows[rel] = prev
        else:
            todo.append((rel, full, st.st_size, st.st_mtime_ns))
            todo_bytes += st.st_size

    total = len(rows) + len(todo)
    if not todo:
        # Nothing to hash. Still rewrite when the tree lost files or an output is missing --
        # a stale manifest listing files that no longer exist is worse than none.
        if rows == old and os.path.exists(idx_path) and os.path.exists(sums_path):
            print("  %-24s %6d files, unchanged" % (name, total), flush=True)
            return total
        write_index(idx_path, sums_path, rows)
        print("  %-24s %6d files, nothing to hash, index rewritten"
              % (name, total), flush=True)
        return total

    print("  %-24s %6d files, %d carried over, %d to hash (%s)"
          % (name, total, len(rows), len(todo), human(todo_bytes)), flush=True)

    done, done_bytes, failed, elapsed = hash_tree(
        todo, rows, workers, interval,
        checkpoint=lambda: write_index(idx_path, sums_path, rows))

    print("  %-24s %6d files indexed, %d hashed in %dm%02ds (%.0f MB/s)"
          % (name, len(rows), done, elapsed // 60, elapsed % 60,
             done_bytes / max(elapsed, 1e-6) / 1e6), flush=True)
    for rel, err in failed[:10]:
        print("      UNREADABLE  %s  (%s)" % (rel, err), flush=True)
    if len(failed) > 10:
        print("      ... and %d more" % (len(failed) - 10), flush=True)
    return len(rows)


def fix_times(name, base_url):
    """Re-read the directory listings and stamp already-mirrored files with their real dates.

    A mirror made before this was added carries the date it was copied on, not the date the file
    was published -- an oss4aix RPM from 2011 showing 2026. That is a real loss for an archive,
    where the dates are part of what is being preserved.

    The cheap fix is the listings, not the files. Asking the server for `Last-Modified` per file
    would be 195 000 requests; the listings carry the same information in 2519. The price is
    precision: an index prints minutes, the header prints seconds. For a twenty-year-old package
    that is not a distinction worth 190 000 requests.
    """
    root = os.path.join(ROOT, name)
    if not os.path.isdir(root):
        print("  %s: does not exist" % name)
        return
    exclude = EXCLUDE.get(name, ())
    pending = [base_url]
    seen = {base_url}
    dirs = stamped = nodate = absent = 0
    t0 = time.time()
    while pending:
        url = pending.pop()
        try:
            body, url = fetch_text(url)
        except Exception:  # noqa: BLE001
            continue
        dirs += 1
        for href, _size, mtime in parse_listing(body):
            child = urllib.parse.urljoin(url, href)
            if not child.startswith(base_url) or child in seen:
                continue
            seen.add(child)
            if href.endswith("/"):
                rel = child[len(base_url):]
                if any(rel.startswith(x) for x in exclude):
                    continue  # never mirrored, so nothing on disk to stamp
                pending.append(child)
                continue
            if mtime is None:
                nodate += 1
                continue
            p = long_path(local_path(root, base_url, child))
            try:
                os.utime(p, (mtime, mtime))
                stamped += 1
            except OSError:
                absent += 1
        if dirs % 200 == 0:
            print("    %d directories, %d files stamped" % (dirs, stamped), flush=True)
    print("  %-20s %d dirs  %d stamped  %d with no date in the index  %d not on disk  %.0fs"
          % (name, dirs, stamped, nodate, absent, time.time() - t0))


def verify(name):
    root = os.path.join(ROOT, name)
    marker = os.path.join(root, COMPLETE_MARKER)
    if not os.path.exists(marker):
        print("  %-20s no %s -- never marked complete" % (name, COMPLETE_MARKER))
        return False
    # Only the leading header is machine-readable; everything after the first blank line is
    # prose for a human. Reading the whole file was a latent trap: a marker written by hand on
    # 2026-08-25 explained the archive's history with lines that began "files" and "bytes", and
    # --verify parsed those instead of the header and died on `int("7826  ->  94899")`.
    rec = {}
    for line in open(marker, encoding="utf-8"):
        if not line.strip():
            break
        parts = line.split(None, 1)
        if len(parts) == 2:
            rec[parts[0]] = parts[1].strip()
    n, total = scan_tree(root)
    want_n, want_b = int(rec.get("files", -1)), int(rec.get("bytes", -1))
    ok = (n == want_n and total == want_b)
    print("  %-20s %s" % (name, "UNCHANGED" if ok else "MISMATCH"))
    print("     files %d (marker says %d)   bytes %d (marker says %d)" % (n, want_n, total, want_b))
    if not ok:
        print("     -> %+d files, %+d bytes against the marker written %s"
              % (n - want_n, total - want_b, rec.get("completed", "?")))

    # Counts and bytes cannot see a file whose content changed while its size stayed the same.
    # The index can, but only for the files it actually covers -- so say how many that is.
    idx = read_index(os.path.join(root, INDEX_FILE))
    if not idx:
        print("     Index: none")
    elif len(idx) == n:
        print("     Index: %d files, covers the tree" % len(idx))
    else:
        print("     Index: %d files, %+d against the tree -- `--index` catches it up"
              % (len(idx), len(idx) - n))
    return ok


# ----------------------------------------------------------------------- where the tree is


def looks_like_mirror_root(path):
    """-> True if this directory already holds mirrors.

    Evidence, not configuration. A subdirectory carrying a completion marker or a checksum
    index was written by this tool and by nothing else, so it is proof the tree is here.
    That is what lets a bare `python mirror.py` work inside an established mirror without
    letting it work in an arbitrary directory that merely happens to be the current one.
    """
    if os.path.isfile(os.path.join(path, ROOT_MARKER)):
        return True
    try:
        entries = os.listdir(path)
    except OSError:
        return False
    return any(os.path.isdir(os.path.join(path, e))
               and (os.path.isfile(os.path.join(path, e, COMPLETE_MARKER))
                    or os.path.isfile(os.path.join(path, e, INDEX_FILE)))
               for e in entries)


def git_worktree(path):
    """-> the working copy `path` lies in, or None. Walks upwards; needs no git binary."""
    path = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def resolve_root(explicit):
    """-> the absolute mirror tree, or exit explaining how to name one.

    THERE IS NO DEFAULT, and that is the whole point. This script used to live inside the tree
    it filled, so os.path.dirname(__file__) was the right answer by accident of layout. Moving
    the script into version control separated the two, and carrying the old default across
    would have been wrong in the one direction that costs something: quietly filling whatever
    directory the tool happens to sit in, which is now a git checkout.

    Order: --root, then $MIRROR_ROOT, then the working directory -- and the last one only if it
    already looks like a mirror tree. A wrong root is not a failed run that can be repeated. It
    is a second copy of terabytes somewhere nobody thought to look.  [2026-08-29]
    """
    root, source = explicit, "--root"
    if not root:
        root, source = os.environ.get("MIRROR_ROOT"), "$MIRROR_ROOT"
    if not root:
        root, source = os.getcwd(), "the working directory"
        if not looks_like_mirror_root(root):
            sys.exit("Where should the mirrors go? Pass --root PATH, or set $MIRROR_ROOT.\n"
                     "  %s holds no mirror, so it is not assumed to be one. Either name the\n"
                     "  directory explicitly, or put an empty %s in it to declare it."
                     % (root, ROOT_MARKER))
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        sys.exit("%s names %s, which is not a directory. Create it first -- this tool fills a\n"
                 "  mirror tree, it does not decide where one belongs." % (source, root))

    repo = git_worktree(root)
    if repo and not os.path.isfile(os.path.join(root, ROOT_MARKER)):
        sys.exit("%s points inside the git working copy\n    %s\n"
                 "  A mirror is measured in terabytes and has no business in version control.\n"
                 "  Point --root at a plain directory -- or, if this genuinely is where you\n"
                 "  want it, create an empty %s there to say so deliberately."
                 % (source, repo, ROOT_MARKER))
    return root


def main():
    global ROOT, LOGDIR
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", metavar="PATH",
                    help="directory holding one subdirectory per archive. Falls back to "
                         "$MIRROR_ROOT, then to the working directory if that already holds "
                         "mirrors. There is deliberately no default beyond that")
    ap.add_argument("--workers", type=int, default=8,
                    help="simultaneous connections per archive (default 8)")
    ap.add_argument("--queue", type=int, default=128,
                    help="bounded queue depth (default 128)")
    ap.add_argument("--interval", type=float, default=10.0,
                    help="seconds between progress lines (default 10)")
    ap.add_argument("--fresh", action="store_true",
                    help="delete the target directory before mirroring")
    ap.add_argument("--case-sensitive", action="store_true",
                    help="NTFS only: make the target directory case-sensitive, so remote "
                         "names differing only in case cannot collide. Measured unnecessary "
                         "for both archives (zero such pairs); only effective on a fresh root")
    ap.add_argument("--archive", action="append",
                    help="mirror only this archive; repeatable")
    ap.add_argument("--verify", action="store_true",
                    help="download nothing; compare each mirror against its completion marker")
    ap.add_argument("--fix-times", action="store_true",
                    help="download nothing; re-read the listings and stamp already-mirrored "
                         "files with the dates the server publishes")
    ap.add_argument("--seed", action="append", metavar="URL",
                    help="extra starting directory under the archive's base URL, for a tree the "
                         "base page does not link to. Repeatable. Added to whatever SEEDS "
                         "already records for the archive.")
    ap.add_argument("--index", action="store_true",
                    help="download nothing; bring each mirror's checksum index up to date. "
                         "Hashes only files whose size or mtime differs from the index, so a "
                         "second run over an unchanged archive costs a stat, not a read")
    ap.add_argument("--index-force", action="store_true",
                    help="with --index: re-hash every file, ignoring the existing index")
    ap.add_argument("--hash-workers", type=int, default=8,
                    help="threads used for hashing (default 8). Purely local work -- this is "
                         "not a number of connections and has nothing to do with --workers")
    ap.add_argument("--no-index", action="store_true",
                    help="do not touch the checksum index after a mirroring run")
    ap.add_argument("--dry-run", action="store_true",
                    help="rsync archives only: report what would transfer, move nothing. Use it "
                         "to check a filter change before it costs a hundred gigabytes")
    args = ap.parse_args()

    # Before anything else: every path in this tool is built on ROOT, including the log
    # directory, so nothing may run before it is known.
    ROOT = resolve_root(args.root)
    LOGDIR = os.path.join(ROOT, "logs")

    todo = [(n, u) for n, u in ARCHIVES if not args.archive or n in args.archive]
    if not todo:
        sys.exit("no archive matched --archive; known: %s" % ", ".join(n for n, _ in ARCHIVES))

    if args.fix_times:
        print("stamping %s from the published listings\n"
              % ", ".join(n for n, _ in todo), flush=True)
        for name, base_url in todo:
            fix_times(name, base_url)
        return

    if args.index or args.index_force:
        print("indexing %s  (%d hash threads)\n"
              % (", ".join(n for n, _ in todo), args.hash_workers), flush=True)
        t0 = time.time()
        for name, _ in todo:
            build_index(name, args.hash_workers, force=args.index_force,
                        interval=args.interval)
        print("\ndone in %dm%02ds" % ((time.time() - t0) // 60, (time.time() - t0) % 60),
              flush=True)
        return

    if args.verify:
        print("verifying %s\n" % ", ".join(n for n, _ in todo), flush=True)
        # A list, not a generator: `all()` short-circuits, so one unverifiable archive
        # used to end the run and leave every later mirror unchecked -- which is the
        # opposite of what a verification pass is for. Check all, then judge.
        results = [verify(n) for n, _ in todo]
        sys.exit(0 if all(results) else 1)

    print("mirroring %s -> %s" % (", ".join(n for n, _ in todo), ROOT), flush=True)
    incomplete = 0
    for name, base_url in todo:
        print("=== %s" % name, flush=True)
        stats = mirror(name, base_url, args)
        if stats is None:      # refused: the archive is already marked complete
            continue
        print("    %d files, %s, %d permanent 403/404, %d failed, %d unreadable listings"
              % (stats.done, human(stats.bytes), stats.permfail, stats.failed, stats.listfail),
              flush=True)
        incomplete += stats.listfail + stats.failed

    # A non-zero exit is the difference between "this finished" and "this finished, and
    # what you have is not the archive". Permanent 403s do not count -- those files do not
    # exist to be fetched.
    if incomplete:
        print("INCOMPLETE: %d failures; re-run without --fresh to retry them" % incomplete,
              flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
