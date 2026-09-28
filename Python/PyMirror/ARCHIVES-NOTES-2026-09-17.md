<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# mirror.py's ARCHIVES notes, as they stood on 2026-09-17

**This file exists so that a question does not have to be argued.** On 2026-09-17 the per-archive
prose was moved out of `mirror.py`'s `ARCHIVES` block and into each archive's own `PROVENANCE.md`
— the file that travels with the data, which `mirror.py` does not. That took the block from
1 451 lines to 337 and the whole file from 7 822 lines to 6 764.

Moving 1 056 lines of prose raises exactly one question: **was anything lost?** Three separate
automated comparisons were run and all three disagreed with each other, because sentence matching
across re-wrapped text is a bad instrument and every one of them produced a different set of
"missing" sentences. Rather than tune a fourth heuristic, the block is reproduced here verbatim.

It is a snapshot, not a maintained document. The live text is in each archive's `PROVENANCE.md`;
this is the thing they were made from. If the two ever disagree, the `PROVENANCE.md` is right.

**ANSWERED ON 2026-09-25, and the answer is that this file cannot leave.**
[`measurements/archives-notes-recoverable-2026-09-25.md`](measurements/archives-notes-recoverable-2026-09-25.md)
put the question to all 98 `PROVENANCE.md` files with whitespace collapsed on both sides — which is
the whole fix, because re-wrapping changes nothing else — and **92 of 539 sentences are not in the
collection at all**. They are not archive descriptions: they are the measurement errors, the
retractions and the wrong turns, which is exactly what a `PROVENANCE.md` has no place for. One
archive named here, `funet-unix`, was deleted on 2026-09-10 and has no `PROVENANCE.md` to hold any
of it. Keeping this file is not caution; it is the only copy.

```python
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

    # Michael Perzl's wiki -- the index to `oss4aix.org`, which is already mirrored above. One
    # page per package: which build belongs to which AIX level, what breaks after a service pack,
    # where the sources came from. The packages do not carry any of that.
    #
    # THE ONE THAT WAS ALMOST FORGOTTEN, and the way it nearly happened is worth more than the
    # copy. It sat in the search brief from the start, under the project's vanity name
    # `www.perzl.org/aix/`, parked as low priority with the reason "a wiki needs different
    # handling from a file tree". That reason expired on 2026-08-26, when HTML_CRAWL arrived for
    # exactly that shape -- and nothing pointed back at the entry. It was also recorded twice
    # under two hostnames that nobody connected: the vanity name 301-redirects here.
    #
    # The lesson is the mirror-side inverse of the one in AIX/README.md about reading lists:
    # RECORD AN EXCLUSION WITH THE CONDITION THAT WOULD REVIVE IT. An exclusion written as a fact
    # about the target ("a wiki is not a file tree") is never revisited. One written as a limit of
    # this tool would have been revisited the day the tool changed.  [2026-08-30]
    ("perzl-wiki", "http://v14700.1blu.de/aix/index.php"),

    # Bull Freeware, closed by Atos on 1 March 2022, with its GNOME subdomain. The packages were
    # already rescued -- dl.power-devops.com is one volunteer's copy, and it is `bull-rpms` and
    # `bull-srpms` above. What that rescue did not carry is everything AROUND the packages, and
    # that is what this is: the catalogue of what existed (4 071 pages, `affichage.php?id=NNNN`),
    # the .spec files each package was built from, Bull's own pre-RPM `.exe` filesets from the
    # AIX 4.3 era, and a complete GNOME 2.6 desktop for AIX 5.1 that Perzl never built -- his
    # oss4aix has ORBit2 and gtk2 but no GConf2, nautilus, metacity or gnome-panel.
    #
    # A rescue is not the same as a copy of the site. Measured 2026-08-30: 8 935 of the 8 955 RPMs
    # the index lists are already held, so the RPMs are declined here by --skip-listed rather than
    # fetched a second time. The condition that would revive them is in FROZEN.
    ("bullfreeware", "http://www.bullfreeware.com/"),

    # The last two entries on the list of other AIX sites on Perzl's homepage. All five on that
    # list are dead; three are handled above and in `bullfreeware`, and these two are too small to
    # be archives on their own -- linkitup.de is 21 indexed URLs. Kept together because what they
    # share is that page, which is now the only record either existed. Two hosts, so each gets its
    # own top-level directory. See FROZEN and the PROVENANCE.md inside.
    ("aix-orphans", "http://linkitup.de/"),

    # IBM's RS/6000 support tree -- NOT the AIX distribution tree, which is `ibm-aix` above and
    # deliberately came from aix.software.ibm.com instead of this host. This is the other thing on
    # the same server: PPC_support/ with the 27-82660 host-bridge manuals and IBIS models, and
    # reference_designs/{harley,longtrail,zapatos} -- the actual PReP/CHRP boards, with schematics,
    # bills of material and Gerber fab data. Plus OpenFirmware/{bindings,devices,practices} and
    # chrptech/. These are the primary sources for the machine QEMU's `40p` and `prep` emulate, and
    # measured 2026-09-02, zapatos/harley/longtrail/660_bridge/chrptech return ZERO hits anywhere
    # in this collection.
    #
    # IBM IS A FUNDED HOST AND THIS ENTRY BENDS THE SELECTION RULE. It is here on evidence rather
    # than sentiment: the sibling path aix.software.ibm.com/rs6000/ already answers 404, this tree
    # is frozen at 2000-07-13, it is unlinked and has no sitemap, and its own readme points at a
    # hostname that no longer resolves. IBM is dismantling these servers one at a time.
    #
    # Consent is explicit rather than inferred. The index page carries, in its own words: "The
    # content on this page is publicly available information. The directory structure is accessible
    # and traversable by design." Copyright is asserted in /rs6000/readme, so this is a private
    # preservation copy, not a redistribution.
    ("ibm-rs6000-support", "https://public.dhe.ibm.com/rs6000/"),

    # Typewritten Software's rendered manual trees for the ROMP/RT ancestry of AIX: AIX PS/2 1.2.1,
    # AIX RT 2.2.1 and IBM's Academic Operating System 4.3. Hand-written HTML, so HTML_CRAWL.
    #
    # The overlap with `ardent-tool/AIX_1-3/aix_man_pages/` is real but shallow, and measuring it
    # was what justified taking the whole thing rather than a delta: our 2 298 files carry 1 920
    # distinct command names, and against them 1.2.1 is 25% new, RT 2.2.1 is 41% new and AOS 4.3 is
    # 67% new -- 1 217 names we have nothing for. The names that DO overlap are different releases
    # of the same command, which is the comparison a version question needs and which a delta copy
    # would have destroyed.
    #
    # Scoped to /Manual/IBM/. The site's /Software/ tree is already in the Internet Archive.
    ("typewritten", "https://typewritten.org/Manual/IBM/"),

    # Emmanuel Iffly's DokuWiki: twenty years of one French engineer's AIX notes -- ODM repair,
    # NIM, VIOS, HMC, WPAR, boot failures, and a maintained page on running AIX under QEMU -- plus
    # some thirty other namespaces. 968 pages.
    #
    # The reason it is here rather than in the Internet Archive is structural, and it is the same
    # reason perzl-wiki is: a DokuWiki addresses pages as query strings reachable only from its own
    # per-page sidebar, so a crawler finds the namespace index and stops. Measured: the Archive
    # holds 436 URLs from this host, most of them crawler-trap variants (`do=edit`, `do=backlink`,
    # sort parameters), and only ~71 are content against 237 live AIX pages.
    #
    # Consent is affirmative, not inferred: the footer carries GFDL 1.3 with `rel="license"`, and
    # the export endpoints are deliberately left enabled. RETAIN THE GFDL NOTICE WITH THE COPY.
    #
    # Fetched by dokuwiki-source.py -- see EXTERNAL.
    ("iffly-wiki", "http://emmanuel.iffly.free.fr/doku.php"),

    # ~150 procedure documents, `StevesKnow*` and `SH_WEA_*`: firmware and service-processor
    # upgrade walkthroughs for the 7044-170, 7044-270 and 7043-270, AIX 5.1 install and NIM,
    # mixed-OS installs. Procedural rather than reference -- the actual sequence for getting
    # firmware onto a CHRP machine, which IBM's own documents describe only abstractly, and
    # exactly the machines this collection's emulation work sits on.
    #
    # One person's knowledge dump in an open directory on shared hosting. Every file carries the
    # same 2023-02-24 timestamp: a one-shot re-upload of early-2000s material, then nothing.
    # 121 of its 143 files are absent from the Internet Archive, which crawled only the front-page
    # hubs. THE DOMAIN EXPIRES 2026-10-08 on a one-year renewal cycle.
    #
    # NOT FETCHABLE BY THIS TOOL -- use `autoindex-tls-broken.py`. The host serves an incomplete
    # certificate chain (leaf validates, issuer not sent), so every stdlib client refuses it and a
    # run here ends in `1 unreadable listings`. Listed anyway so `--verify` covers the tree.
    ("misterhayden", "https://misterhayden.com/Stevens/"),

    # A working AIX 7.2 / QEMU POWER8 recipe, among 198 posts. HTML_CRAWL.
    #
    # The reason it is here is a number rather than a judgement: the Internet Archive holds ZERO
    # snapshots of anything on this domain -- confirmed by CDX with no filter and by the
    # availability API. An eleven-month-old free Blogger account with no copy anywhere.
    #
    # It sits on Google infrastructure, which is funded by any reading, so this bends the selection
    # rule the way ibm-rs6000-support does. The argument is that the fragility is account-level
    # rather than infrastructure-level: nothing keeps the account alive but its author.
    #
    # NOT FETCHABLE BY THIS TOOL -- use `blogger-sitemap.py`. Blogger's front page is an
    # infinite-scroll widget, so a link crawl walks the month hubs into a fan of `?updated-max=`
    # permutations and still finds no posts. The first attempt found 0 files AND MARKED THE ARCHIVE
    # COMPLETE, which is the failure worth remembering: an empty archive that vouches for itself.
    ("techsysadm", "https://techsysadm.blogspot.com/"),

    # IBM's RS/6000 Technical Library, the CD-ROM edition, as two releases:
    #   tl1 = Version 3 Release 10 (2001), tl2 = Version 3 Release 2 (1999)
    # The whole AIX documentation library -- Commands Reference, the aixbman/aixins/aixprggd
    # books, InfoExplorer's HTML descendant -- plus the fixes catalogue and the Q&A database, as
    # IBM shipped it to customers who had no reliable internet in 1999.
    #
    # 32 312 files across the two, measured; ~312 MB. THE INTERNET ARCHIVE HAS 54 URLs OF IT --
    # 0.02 % -- because `Options -Indexes` hides anything not reachable by link and its crawler
    # never found the CDs' own tables of contents.
    #
    # HTML_CRAWL, and it must be: the directories 403, and the ONLY way in is each CD's shipped
    # index.html. A previous survey concluded from those 403s that the tree was unreachable. It
    # is not -- every content directory returns 200 for its index page.
    #
    # Scoped to the two CD roots on purpose. Seeding at /misc/ would work and would also drag in
    # the site's large IBM PC and PS/2 hub, which is not what was asked for.
    ("infania-tl1", "http://infania.net/misc/rs6000-tl1/"),
    ("infania-tl2", "http://infania.net/misc/rs6000-tl2/"),

    # AIX 2.2.1 for the IBM RT PC, and IBM's Academic Operating System 4.3 -- the ROMP ancestry,
    # from a Finnish hobby association's own box. 504 MB measured exactly (266 HEADs, zero
    # misses): three tarballs plus the same three trees served expanded, so a single file can be
    # read without pulling 160 MB.
    #
    # HTTP ONLY -- port 443 refuses connections. robots.txt is "User-agent: *" with no Disallow.
    # The association's own rules name "the free, safe flow of information" and the sensible use
    # of decommissioned computing resources as its purpose.
    #
    # Open question, deliberately not guessed at: BSD44-RT-LITE/src.tar.gz is 124 MB, half the
    # collection, and how much of it is ROMP-specific rather than stock 4.4BSD-Lite that `tuhs`
    # already holds is UNMEASURED. Settle it after the fetch, by comparison -- not by estimate.
    ("damage-rt", "http://damage.fi/slas/rt/"),

    # 43 photographs, 11 166 403 bytes: the only part of csiph.com worth keeping. 25 of them sit
    # under Users/kev009/ in AIX/ and RS6000/ subfolders -- the same kev009 whose site is mirrored
    # here as `ps-2.kev009.com`, so they looked like duplicates. They are not: all 43 were hashed
    # and compared against that archive's complete 94 899-row manifest, and NONE matches.
    #
    # csiph.com is an NNTP server for comp.sys.ibm.ps2.hardware, not a file archive. Its
    # /innreport/ is daily server statistics; its Usenet corpus is not on HTTP at all. The
    # 8 532-file `timc` tree that made this a candidate 404s on every path, including in all
    # seven Internet Archive captures of it.
    #
    # NOT FETCHABLE BY THIS TOOL -- use `nginx-autoindex-gallery.py`, which honours the
    # Crawl-delay: 2 that robots.txt asks for. Listed here so `--verify` covers the tree.
    ("csiph-gallery", "https://csiph.com/gallery/albums/"),

    # (`dhe-rs6000` stood here until 2026-09-04 and has been removed: it was the SAME tree as
    # `ibm-rs6000-support` above, fetched from the identical URL one day later. Verified
    # byte-identical case-sensitively -- 1 619 paths each, zero mismatches -- then deleted,
    # recovering 27.12 GB. The whole policy argument about whether an IBM host may be mirrored
    # was conducted over a tree already on disk. The guard in main() now makes this
    # unrepeatable; its account lives in ibm-rs6000-support/PROVENANCE.md.)

    # --- fetched by dedicated scripts, registered here so `--verify` covers them --------------
    #
    # These four were acquired before they were listed, which meant `--verify` silently skipped
    # 19.7 GB. All are in EXTERNAL, so a full run reports them and moves on rather than pointing
    # the HTML crawler at them.

    # AIX 1.2.1 through 5.1 install media -- the releases this collection did not hold in any
    # form: PS/2 1.2.1 and 1.3.0, RT 2.1.1 and 2.2.1, RS/6000 3.2.0, 3.2.5, 4.1.3, 4.1.5, 4.2.1,
    # 4.3.2, 5.1, and AIX 4.1.4 for the Apple Network Server.
    #
    # 608 files, 70.12 GB. COMPLETE: the server lists 608 and the tree holds 608.
    #
    # IT WAS A SUBSET AND IS NOT ONE ANY MORE. Until 2026-09-05 this read "450 files, 19.56 GB,
    # a subset by design -- the ~39.7 GB of AIX 4.3.3/5.2/5.3 discs are duplicates of releases
    # already here and were left upstream." The remainder was fetched that day and the sentence
    # was left behind, so the comment went on describing a decision that had been reversed.
    #
    # AND THE DECISION ITSELF HAD BEEN WRONG. Those discs were called duplicates on a RELEASE
    # comparison; by PART NUMBER they were not. AIX 4.3.3 revision 07, the 12-2000 Bonus Pack,
    # the 4.3.3 Update, 5.2 LCD4-1133-10, 5.3 LCD4-7463-05 and -14 and TL 5300-12 were all
    # absent. Comparing by FILENAME had said 59 GB was new (wrong -- uploaders rename); comparing
    # by RELEASE said 19.56 GB (also wrong -- one release ships many part numbers). Only hashing
    # settled it, and it found 27 genuine duplicates, 13.63 GB, removed from the curated
    # collection rather than from here.
    ("fsck-aix-media", "https://fsck.technology/software/IBM/AIX%20Install%20Media/"),

    # Commercial AIX software -- THE MOST PERISHABLE CATEGORY HERE. Open-source AIX builds have
    # three independent sources in this collection and a living community; commercial software
    # has neither. It was sold, the vendors are gone or have forgotten it, nobody may
    # redistribute it, and it survives only where a private copy happens to sit. ALL OF IT COMES
    # FROM THIS ONE HOST and no second source has been looked for.
    #
    # The compilers are why it matters most: IBM VisualAge C++ Professional 4.0.2, VisualAge
    # 5.0.2 and IBM COBOL 2.0.0. IBM does not distribute them, and building anything for an old
    # AIX means having one. Also Mathematica 2.2/3.0.1.1/5.2, Maple, IMSL, Pro/Engineer, Cadence,
    # Altera, Modeltech VHDL, WordPerfect for UNIX, Netscape, Sybase -- and Insignia SoftWindows,
    # x86 emulation running UNDER AIX.
    ("fsck-aix-apps", "https://fsck.technology/software/IBM/AIX%20Applications/"),

    # The IBM systems around AIX, 18 trees: OS/2 (Install Media, Applications, Demos, Patches),
    # OS/390, z, PC-DOS, the 3174 Establishment Controller, 4690 OS, terminal emulators, PS/2
    # support disks, and OS400_i Install Media.
    #
    # 1 327 files, 105.94 GB.
    #
    # THESE WERE ONCE DECLARED OUT OF SCOPE, WRONGLY. The claim was made from memory rather than
    # from the private collection's own README, whose scope is "everything IBM-related" and is
    # not confined to AIX. Declining to MEASURE something on a mistaken premise loses material
    # silently and leaves no trace that anything was lost.
    #
    # OS400_i IS HERE, 219 files and 71.22 GB of it, fetched 2026-09-05. This comment said the
    # opposite -- "NOT here, it did not fit, AS/400 is a different lineage" -- for a day after it
    # arrived, and the tree count said 17 while 18 directories sat on disk. Both were the same
    # omission: the fetch was done and nothing wrote it down. That is why the file's counts are
    # now generated from the markers rather than typed.
    ("fsck-ibm-other", "https://fsck.technology/software/IBM/"),

    # Everything under /software/ EXCEPT IBM and BSD: 37 vendor trees, fetched in relevance order
    # rather than alphabetically -- DEC-Compaq, HP, Silicon Graphics, Sun, NeXT, Dynix, SCO,
    # Xenix, x86 Unix and ROM Dumps first, because that is the Unix-workstation world AIX stood
    # in and their firmware and install media are the same kind of endangered artefact. PC and
    # home-computer trees last. BSD is excluded at the owner's instruction: FreeBSD and NetBSD
    # are abundantly available and in no danger -- the same standing exclusion that keeps
    # bits/NetBSD/ out of the bitsavers mirror.
    ("fsck-vendors", "https://fsck.technology/software/"),

    # RS/6000 firmware and microcode, salvaged from the Internet Archive; the origin is gone.
    # 61 .bin and 24 .exe images plus 96 HTML pages (75 .html + 21 .htm) of the procedures that
    # go with them.
    #
    # WHAT IS AND IS NOT XCOFF32, checked by reading the first two bytes of all 85, not sampled:
    # 60 of the 61 .bin carry magic 01df -- genuine RS/6000 executables for 4mm/8mm tape, DLT and
    # CD-ROM drives. The 61st, support/micro/smp0951.bin, does not. ALL 24 .exe begin `MZ`: they
    # are DOS/Windows loaders, which is what IBM shipped for updating an RS/6000 from a PC, and
    # calling them XCOFF32-verified -- as this comment did -- was wrong about every one of them.
    #
    # 3 files remain .suspect. That figure was 15 until 2026-09-05, when re-checking EVERY
    # Internet Archive capture rather than the one the salvage happened to take recovered 12 of
    # them (+30 MB); their short copies are kept beside them as *.suspect.superseded. The old
    # "15, final" was true of one capture and false of the URL.
    #
    # This is the first deliberate entry against the coverage map's worst gap, which read
    # "firmware, ROMs, microcode ... this category has no systematic coverage at all".
    # robots.txt from 2002 granted ia_archiver everything except /cgi-bin.
    ("rs6000-microcode", "http://www.rs6000.ibm.com/support/micro/"),

    # The AIX Public Domain Software Library at UCLA -- origin dead (connect timeout), salvaged
    # from the Internet Archive. Verified before taking: /pub/fping/RISC/3.2/exec/fping.1.20.tar.Z
    # decompresses to a setuid `fping` dated 1994 whose own magic is 01df, i.e. a real RS/6000
    # AIX executable, not a source tarball and not a soft-404. Also carries the CONTENTS_ESA_*
    # manifests for AIX/ESA 2.2, a lineage this collection holds nothing else of.
    ("aixpdslib", "http://aixpdslib.seas.ucla.edu/"),

    # Linux-on-PowerPC, but taken for three things Linux people kept and nobody else did: decoded
    # PReP residual data for the 7043-140 and 7025-F40 (the live host 404s these; the Internet
    # Archive is the only source), Tom Gall's original ppc64 port patch, and the quik bootloader.
    # A SUBSET -- 601 files of the domain's 10 218 captures; the rest is distribution material.
    # The figure read 74 until 2026-09-06: that was the count of one early pass, never revised
    # after the salvage finished. The marker and PROVENANCE.md have said 601 all along.
    ("penguinppc", "http://penguinppc.org/"),

    # Jaqui Lynch's AIX performance and technical-university material: AIX VUG presentations,
    # eServer articles, papers. Live host.
    #
    # A CRAWLER LESSON LIVES HERE. Two runs found 7 documents where an independent HEAD-sum had
    # measured 212 files / 122.19 MB, and neither reported an error. The subtrees are
    # `Options -Indexes` (ptechu/, papers/, jaqui/eserver/, jaqui/zips/ all 403), so documents
    # exist only as links -- and the site links its OWN pages as `http://www.circle4.com/...`
    # while the crawl was scoped with `startswith("https://www.circle4.com/")`. Every http link
    # was discarded as off-site. Scope on the HOST, never on a scheme-qualified prefix.
    ("circle4", "https://www.circle4.com/"),

    # Three GitHub repositories and one gist on running AIX under QEMU, cloned WITH FULL HISTORY.
    # For this material the history is the content: a working command line is one line of a
    # README, but the commits show which flags were tried, which were reverted, and what the
    # author said when a change fixed a hang. GitHub is not at risk; these accounts are.
    ("aix-qemu-git", "https://github.com/mjsamp/AIX-on-qemu-ppc64"),

    # Two compressed troff papers from the University of Toronto's CSRI: BSD-to-AIX administration
    # differences, and porting BSD software to AIX. Source kept rather than a rendering -- it is
    # what was written, and it still formats. 63 324 bytes.
    #
    # Deliberately ONLY these two files. The host carries 15.57 GB more that is uncharacterised
    # and largely held elsewhere; a 63 KB verification does not license taking 15 GB along.
    ("csri-toronto", "https://ftp.csri.toronto.edu/doc/aix/"),

    # IBM's CPC710 datasheet -- the PCI host bridge and memory controller in the CHRP RS/6000s
    # (7043-150, 7044-170, 7025-F80), whose configuration registers the firmware programs during
    # early boot and which QEMU's hw/pci-host/ models. Found on a Polish satellite-TV hobby site;
    # that is the whole provenance chain, and NOT verified against an IBM-published original.
    ("tvsat-cpc710", "http://www.tvsat.com.pl/PDF/C/CPC710_IBM.pdf"),

    # --- added 2026-09-06, the first of the infania subtrees taken whole ---------------------
    #
    # IBM's OS/2 BBS file collection, via infania's mirror of os2bbs.com. MEASURED FIRST, then
    # taken: 48 directories, 21 222 files, 9.91 GB read off the listings -- and that figure is a
    # FLOOR, because `graphics/` timed out while being listed and contributes nothing to it.
    #
    # WHY OS/2 BELONGS IN AN AIX COLLECTION. `fixes20`, `fixes30`, `fixes4x`, `fixes_o` and
    # `fixes_v` are IBM's own FixPaks, and `drivers`/`pdrivers`/`vdrivers` are IBM hardware
    # support for the same PS/2 and PowerPC-era machines this collection documents from the AIX
    # side. `gnu/` is the contemporary GNU port set, `rexx/` the scripting layer IBM shared
    # across OS/2 and AIX, and `tips/` is 1 470 .FAX files -- IBM support bulletins in the format
    # they were faxed in.
    #
    # This is a mirror-of-a-mirror, so the copy is one hop from the source and the source is
    # gone. os2bbs.com itself no longer serves it.
    #
    # HTML_CRAWL: Apache autoindex, HTMLTable form -- the size column is in a <td>, not at end
    # of line, which is what measure-remote.py had to learn.
    #
    # USE THE DEFAULT 8 WORKERS, and never run a second job against this host at the same time.
    # Observed on the live fetch, 2026-09-06:
    #
    #     4 workers, measure-remote.py crawling compaq on the same host    7 files/min,  94 KB/s
    #     8 workers, host to ourselves                                   137 files/min, 212 KB/s
    #
    # A SPOT TEST THAT SAID THE OPPOSITE, AND WHY IT WAS WRONG. A 24-file benchmark run while
    # measure-remote.py was hammering the same server gave 120 files/min at 4 connections and 78
    # at 16, and was written up here as "infania throttles per IP, more connections are slower".
    # It was measuring the contention, not the host: with the crawler stopped, 8 workers beat 4
    # by twentyfold. A concurrency benchmark taken while something else shares the link measures
    # the something else. The competing job is the variable that matters, not --workers.
    #
    # The host does cap us at roughly 100-200 KB/s regardless -- our own link does 7 150 KB/s
    # from kernel.org and 973 KB/s from aix.software.ibm.com in the same minute -- so 9.91 GB is
    # a long fetch however it is arranged. Budget half a day, not an evening.
    #
    # The operator permits this: robots.txt is `Allow: /pub`, `Allow: /sites`, with no
    # Crawl-delay; /mirror, /debian, /slackware, /ubuntu and friends are Disallowed, and
    # facebookexternalhit is refused outright. `sites` is where this lives.
    #
    # The tree's own catalogue arrives with it: ALLFILES.ZIP and allfiles.txt (3.8 MB) in the
    # root are the BBS's inventory, so completeness can one day be checked against what the
    # SOURCE said it held rather than against our own count of what we took. It already earns
    # its keep twice over:
    #
    #   * IT AGREES WITH US. The catalogue names 21 428 files; walking the listings counted
    #     21 222. Two independent counts of the same tree, one of them the source's own.
    #   * IT JUSTIFIED THE 23 HOURS. Before committing a day of transfer, every name in the
    #     catalogue was checked against all 560 319 distinct filenames in this collection.
    #     ONLY 657 MATCHED -- 3.1%, and mostly in ps-2.kev009.com (565) and rwth-aachen-ftp
    #     (455), which hold IBM's PC Company BBS rather than its OS/2 one. 97% is material held
    #     nowhere here under any name. A name match is weak evidence that two files are the same;
    #     a name MISS is strong evidence that they are not, and that is the direction that
    #     decided this.
    ("os2bbs", "http://ftpmirror.infania.net/sites/os2bbs.com/"),

    # --- added 2026-09-07 -------------------------------------------------------------------
    #
    # IBM Open XL C/C++ for AIX documentation, all five releases 17.1.0 through 17.1.4, 794 pages.
    #
    # NOT FETCHABLE FROM IBM AND NOT BECAUSE IBM FORBIDS IT. www.ibm.com/docs answers HTTP 403 to
    # every automated client on every path, including the PDFs -- while its robots.txt disallows
    # only /docs/api and publishes a sitemap for /docs/en/. The policy permits reading it; the
    # bot-protection layer refuses to serve it. That distinction is worth keeping straight: this
    # is not an operator saying no, it is an operator saying yes through a door that is locked.
    # No attempt was made to defeat it.
    #
    # So it is a SALVAGE, via wayback-salvage.py. web.archive.org/robots.txt returns 404.
    #
    # WHY IT WAS TAKEN: to settle whether Open XL emits DWARF call-site information on AIX. The
    # page 17.1.2@topic=cc-symbolic-debugger-support states that the compiler supports only DWARF,
    # defaults to DWARF 3, offers -gdwarf-2/-3/-4 and NOT -gdwarf-5, and tunes for DBX by default.
    # DW_TAG_call_site is a DWARF 5 construct, so those names can never appear; upstream Clang
    # emits call sites only above -O0 and with DWARF 5 or DWARF 4 plus GDB/LLDB tuning, so on AIX
    # the working combination is -gdwarf-4 -ggdb -O1 and it yields DW_TAG_GNU_call_site instead.
    # IBM documents none of that. The absence is the finding.
    #
    # A PAGE AND A DIRECTORY UNDER ONE NAME. .../openxl-c-and-cpp-aix is a page AND the parent of
    # 802 more. The first run lost 78 of its first 80 URLs to WinError 183 before this was
    # understood; wayback-salvage.py now moves the page to index.html inside the directory.
    ("ibm-openxl-docs", "https://www.ibm.com/docs/en/openxl-c-and-cpp-aix"),

    # --- the last three infania subtrees, 2026-09-07. Same host as os2bbs: ONE JOB AT A TIME,
    # default 8 workers, ~100-200 KB/s whatever you do. See the os2bbs entry for the measurement.
    #
    # ibiblio's Solaris Package Archive, mirrored. Measured as a FLOOR of 1 514 files / 581 MB --
    # only 150 of them got a size before the HEAD cap, and 22 pages were still queued. The 150
    # average 3.88 MB, which would suggest ~6 GB, but that is an extrapolation from a tenth and
    # this file has been wrong twice that way. Take it and then measure the tree.
    ("infania-solaris", "http://ftpmirror.infania.net/sites/solaris/"),

    # A mirrored WEBSITE, not a directory listing -- which is why it first measured as 6 files.
    # measure-remote.py had to learn to follow HTML pages AND to honour <base href> before it
    # could see the tree at all. FLOOR: 171 files, 2.08 MB, 111 pages still queued at the cap.
    ("infania-os-history", "http://ftpmirror.infania.net/sites/os-history.de/"),

    # 18 files, 157.51 KB, and that measurement is COMPLETE -- 20 pages, queue exhausted. A small
    # website about the Unix layer for OS/2, not an archive. Taken on content, not on size.
    # Its mirrored HTML declares <base href="/mirrors/unixos2.org/">, the path it had on its
    # ORIGINAL host; infania serves it at /sites/ and 404s /mirrors/ entirely.
    ("infania-unixos2", "http://ftpmirror.infania.net/sites/unixos2.org/"),

    # IBM Redbooks. NOT a rescue and recorded as such: IBM has hosted these for thirty years and
    # they are widely mirrored, so this breaks the collection's own selection rule -- one server,
    # one person, no successor. The owner asked for it on 2026-09-07 and 20 GB is cheap insurance;
    # it should not become the precedent for taking things that are in no danger.
    #
    # NOT CRAWLED. The PDFs are not in the sitemap and the abstract pages are not worth 2 985
    # requests: sitemap.xml yields 2 985 ids, and the PDF for each is a pure function of the id --
    # sg -> /redbooks/pdfs/<id>.pdf, redp -> /redpapers/pdfs/<id>.pdf, tips -> /technotes/<id>.pdf.
    # Fetched by redbooks-fetch.py, which builds those URLs directly.
    #
    # robots.txt, read directly and quoted in full because it is three lines:
    #   User-agent: *  /  Disallow: /cgi-bin/  /  Disallow: /api/  /  Disallow: */api/*
    # Nothing touches the PDF tree.
    ("ibm-redbooks", "https://www.redbooks.ibm.com/"),

    # --- unpacked out of a tar this collection already held, 2026-09-07 --------------------
    #
    # THE URL IS AN EPITAPH, NOT A SOURCE. Nothing here was fetched. bitsavers serves
    # `mirrors/ftp.agilent.com_CDs_20091212.tar`, 2.47 GB of packaging around a 2009 capture of
    # Agilent's public instrument-publications tree, and while the tar stayed closed its 814 files
    # were invisible to every tool here -- no checksum index, no duplicate analysis, no
    # HTML-imposter scan, and any search had to open a 2.47 GB file to answer a question.
    #
    # Unpacked in place it would have become bitsavers/mirrors/ftp.agilent.com/, a mirror inside a
    # mirror -- the shape os2site.com's /mirrors/ is excluded for -- and would have inherited a
    # provenance that describes an rsync clone. So it stands on its own, with its own account.
    #
    # Its own index says it is INCOMPLETE and that is worth carrying here: the combined index on
    # each disc describes six CDs, the tar holds four. cd5 and cd6, roughly 527 files, are named
    # and absent, and bitsavers has no second Agilent tar.
    ("agilent-ftp-2009", "ftp://ftp.agilent.com/pub/callpub/"),

    # h18002.www1.hp.com, captured 2008-05-27, unpacked 2026-09-07 out of the same bitsavers
    # /mirrors/ tar shelf as agilent-ftp-2009 -- see that entry for why these become archives of
    # their own instead of directories inside bitsavers.
    #
    # HP's AlphaServer and ProLiant product web, 10 201 files. The host does not resolve.
    #
    # 38 names could not be written as they stood, and 35 of those are the same defect: the
    # capture holds files whose Unix names CONTAIN A BACKSLASH, such as
    # `products/servers/management/hpsim/info-library\mxauth.1m.html`. NTFS reads that as a
    # separator, so each would have been filed one directory deeper than it belongs and one of
    # them would have landed on top of a real file. See RENAMED.txt in the archive for the list.
    ("hp-alphaserver-2008", "http://h18002.www1.hp.com/"),

    # h71000.www7.hp.com, captured the same day as hp-alphaserver-2008 and unpacked from the same
    # bitsavers /mirrors/ shelf on 2026-09-07. The host does not resolve.
    #
    # This is the OpenVMS site, and its weight is in one place: `doc/` is 14 980 of the 28 095
    # entries, 763 MB, one directory per release. NOT EVENLY: 73final 5 570 files, 82final 4 181,
    # 83final 2 585, 731final 1 206, 732FINAL 935 -- and then 72final 103 and 721FINAL **2**. The
    # 7.3 and 8.x sets are there; 7.2 is a stub, and calling this "seven releases" without that
    # sentence would be a claim the tree does not support.
    #
    # `wizard/` is another 8 592: the OpenVMS "Ask The Wizard" question archive.
    #
    # 27 names carry a `?`, all of them OpenVMS Journal article links of the form
    # `fb_journal.html?Bringing Seismic Data to the Web with OpenVMS` -- a query string the capture
    # stored as part of the filename. See RENAMED.txt in the archive.
    ("hp-openvms-2008", "http://h71000.www7.hp.com/"),

    # www.hpl.hp.com, captured 2007-08-27, unpacked 2026-09-07 from the same bitsavers /mirrors/
    # shelf. The host resolves and does not answer.
    #
    # HP Labs: `techreports/` (5 123 entries, 1.6 GB, one directory per year 1990-2007) and
    # `personal/` (2 991 entries, 2.1 GB -- researcher home pages, of which 19 demo videos are
    # 1.17 GB on their own, one .wmv alone 222 MB).
    #
    # AND `techreports/Compaq-DEC/`, 1 056 files and 278 MB, which is the reason this is not the
    # weakest of the six. It is the DEC research-lab report series HP inherited through Compaq --
    # 525 documents, each as PDF plus an HTML abstract, from five laboratories that no longer
    # exist:
    #
    #     SRC  238   Systems Research Center, Palo Alto   RR-1 .. RR-177, TN-1994 .. TN-2002
    #     WRL  150   Western Research Laboratory          86-1 .. 2002-1, plus 40 TN notes
    #     CRL   95   Cambridge Research Lab               90-1 .. 2002-5
    #     PRL   35   Paris Research Laboratory            RR-1 .. RR-39
    #     NSL    7   Network Systems Laboratory
    #
    # WRL-86-1 is the Titan System Manual. This is primary-source computer-architecture literature
    # from the company that built the Alpha, sitting one directory below a page of demo videos --
    # which is exactly the argument for taking a mirror whole rather than by judgement.
    ("hp-labs-2007", "http://www.hpl.hp.com/"),

    # ftp.digital.com, captured 2006-08-31, unpacked 2026-09-07 -- the largest of the bitsavers
    # /mirrors/ tars at 36.04 GB and 22 170 files. The host does not resolve.
    #
    # Digital Equipment Corporation's public FTP server. What is in it, by branch:
    #
    #   pub/Digital/   5 588 files  11.73 GB )  the same tree under three names -- see below
    #   pub/DEC/       5 209 files  11.60 GB )
    #   pub/Compaq/    5 205 files  11.60 GB )
    #   pub/X11/       3 150 files   0.86 GB    X11 releases and contrib
    #   pub/recipes/     575 files              yes, recipes. An FTP server is a place, not a
    #                                           product, and this one had a kitchen.
    #   pub/misc/ VMS/ news/ doc/ athena/ NIST/ games/ maps/ -- the rest, under 200 MB together
    #
    # THREE NAMES, PROBABLY ONE TREE -- AND "PROBABLY" IS THE HONEST WORD HERE. Digital became
    # Compaq became HP, the server kept serving the old paths, and the crawler followed all three.
    # What is MEASURED, from the manifest: the three branches agree on most paths and sizes;
    # `Digital/` holds 380 paths the others lack; ~1 500 shared paths differ by a few bytes, which
    # is consistent with the server writing the directory NAME into every generated index.html.
    #
    # What is NOT measured: whether the payload files are byte-identical. Sizes matching is not
    # content matching, and this file does not get to assume it. The comparison is cheap once the
    # checksum index exists and is DEFERRED, not done -- see PROVENANCE.md in the archive.
    #
    # 12 SYMLINKS, ALL POINTING AT pub/DEC (`pub/Compaq.1`, `pub/digital.6`, and ten more), stamped
    # 2012-02-21 -- six years after the capture. Somebody's later attempt to collapse the
    # duplication on a case-insensitive filesystem, not part of the original server. Windows cannot
    # create them; they are recorded in SYMLINKS.txt in the archive.
    #
    # 5 064 names carry `?`, `>` or `:`. The bulk are Apache directory-sort links --
    # `index.html?C=D;O=A` and its seven siblings, saved once per directory as though they were
    # files. This is the tar the collision check in extract-container-tar.py was written for; it
    # found none.
    ("dec-ftp-2006", "ftp://ftp.digital.com/pub/"),

    # next.68k.org, unpacked 2026-09-07 -- and the odd one out of the six container tars in three
    # ways worth stating before anything else.
    #
    # IT IS NOT FROM BITSAVERS. It sat inside this collection's own `fsck-vendors` archive, at
    # `NeXT/next.68k.org Archive/next.68k.org.tar`, beside seven directories that hold one Apache
    # listing page each and nothing else -- the crawler saw the subdirectories and could not
    # enumerate them, because the content was in the tar all along.
    #
    # THERE IS NO THIRD-PARTY MANIFEST. The five bitsavers tars each ship a `tar -t` listing Al
    # Kossow made years ago on another machine, and that is what every extraction here has been
    # checked against. This one has none, so the listing was generated locally with GNU tar 1.35 --
    # a different implementation from the Python `tarfile` the extractor uses, which catches a bug
    # in either reader. It proves CONSISTENCY, not COMPLETENESS: if the tar was packed incomplete
    # in 2010, nothing available here could show it. Said plainly in the archive's PROVENANCE.md
    # rather than hidden behind four green checks.
    #
    # IT IS THE BIGGEST BY FILE COUNT BY AN ORDER OF MAGNITUDE: 234 760 files, 8 356 directories,
    # 37.64 GB. And 126 912 of those names carry a `?` -- more than half the archive is Apache
    # directory-sort links (`index.html?M=D.html` and its siblings, saved in both `.html` and
    # `.orig` form) that the crawler stored as files.
    #
    #   next/                 124 745 files   the site's own tree
    #   otto/                  68 628
    #   next-ftp.peak.org/     18 244   ) mirrors of other NeXT FTP servers, gathered under one roof
    #   ftp.peak.org/          18 231   )
    #   ftp.funet.fi/           3 672   )
    #   other1/                 1 049
    #   ftp.idsoftware.com/        69   id Software shipped Doom and Quake off NeXT hardware
    #   hartley.cc.purdue.edu/     68
    #
    # 24 PAIRS OF NAMES DIFFER ONLY IN CASE (`Index`/`index`, `README`/`readme`,
    # `DoorBell.snd`/`Doorbell.snd`), deep in the tree. They survive only because NTFS
    # case-sensitivity is set on Q:\mirror and cascades to directories created during extraction --
    # tested before the run by writing both spellings five levels below the root and looking for
    # both, not by trusting the flag. Without it, 24 files would have been overwritten in silence.
    #
    # There is also a directory named, literally, `\`.
    ("next-68k-org", "http://next.68k.org/"),

    # --- cloned by the owner on 2026-09-07, not fetched by this tool -------------------------
    #
    # PROJECT MONTEREY: AIX 5.1L on Itanium. 63 `.tar.Z` packages committed into the repository
    # itself rather than into Releases -- gcc-3.1.1-2, gcc-bootstrap-3.1.1-1, binutils-2.14p2-1,
    # gmake-3.81_132-1 among them. Binaries for a platform that shipped, sold badly and vanished;
    # they exist essentially nowhere else.
    #
    # Cloned WITH ITS HISTORY, 86 commits: 159.1 MB of files and 159 MB of `.git`. The same choice
    # as aix-qemu-git, and for the same reason -- for a repository the commit sequence IS part of
    # the artefact, and a snapshot of the working tree throws away who added what and when.
    #
    # ON GITHUB'S robots.txt. It disallows `/*/tree/`, `/*/raw/`, `/*/archive/`, `*/tarball/` and
    # `*/zipball/` -- the HTTP paths a crawler would use. This arrived by `git clone`, which is the
    # git transport rather than those paths, and the owner made that call deliberately on
    # 2026-09-07. Recorded here rather than left to be re-argued: the distinction is real, and it
    # is also the kind of distinction that deserves to be written down where somebody can disagree
    # with it.
    #
    # The name is the repository's, hence the capitals -- every other archive here is
    # lower-case-hyphenated. Left as the owner created it rather than renamed behind his back.
    ("AIX5-IA64", "https://github.com/johnsonjh/AIX5-IA64"),

    # --- taken 2026-09-07 from the candidate list, both whole, both tiny ---------------------
    #
    # Mark Hatle's server, frozen around 1999-2000. The value is `doc/ppc/doc001.htm`-`doc028.htm`,
    # the Linux PowerPC Installation Guide rev PPCInst-1.0-HTML 04/99 -- whose PReP chapter is
    # literally stubbed `[Fill this section out!]` -- and `doc/ppc/doc003.htm`, "History of Linux
    # for the PowerPC", Mark Hatle, February 1999, a primary source on Gary Thomas' original port.
    # `glibc21.shtml` records that the CVS repository is defunct and offline.
    #
    # THE LANDING PAGE LINKS NONE OF IT. Measured on 2026-09-07 it came to ONE file and 2.90 KB;
    # seeded with the known paths, 30 of 30 answer 200. This is R14 arriving from the measurement
    # side, and it is why the SEEDS entry below is not optional: without it the fetch reproduces
    # the measurement and reports a clean completion over an empty archive.
    #
    # penguinppc, held here, does not carry this -- it is the era before penguinppc existed.
    # HTTP only, one owner, a note about limited bandwidth, no successor. robots.txt 404.
    ("crashing-org", "http://gate.crashing.org/"),

    # One person's site: /PowerPC/, /bootloader/ (an XCOFF bootloader, boot25j.xcf),
    # /OpenFirmware/, /OldWorldMacs/, and pcc PowerPC stack-frame and ELF-ABI codegen work dated
    # 2022 with before-and-after assembly. AUTHORED work rather than a mirror of somebody else's
    # manuals, so by definition it exists nowhere else. robots.txt 404.
    #
    # Measured 68 files / 1.83 MB WITH FOURTEEN CONNECTION TIMEOUTS -- a floor and a slow server,
    # not a small site. Expect the fetch to take longer than the size suggests, and expect it to
    # find more than 68.
    ("dialectronics", "http://www.dialectronics.com/"),

    # --- taken 2026-09-08 from the candidate list ---------------------------------------------
    #
    # Charles H. Sauer, the IBM Austin engineer who worked on the RT PC Virtual Resource Manager
    # and later on Dell UNIX. IBM primary sources as PDF: Convergence_of_AIX_and_4.3BSD.pdf,
    # RT_PC_Distributed_Services.pdf, Technology_Infusion_and_Integration_in_AIX_3.pdf,
    # SA23-1057_IBM_RT_Personal_Computer_Technology_1986.pdf.
    #
    # THE SCOPE IS THE OPERATOR'S, NOT OURS. robots.txt disallows /library, /images, /chips,
    # /forum and /sauer/cams; `/sauer/` itself is not disallowed. That is the line, and it is why
    # this entry stops where it does rather than at the site root.
    ("technologists-sauer", "https://technologists.com/sauer/"),

    # The canonical PReP and CHRP boot image set for Debian potato, 2001: prep/bootfull.bin,
    # prep/drivers.tgz, prep/linux, chrp/drivers.tgz, chrp/linux, plus apus/ and images-1.44/.
    #
    # The least endangered thing in this whole collection -- Debian institutional, mirrored
    # everywhere -- and taken anyway because it is 70 MB and it is the boot images the RS/6000 43P
    # notes elsewhere in this file keep referring to. The level above is all of potato; there is
    # no wider root worth having, so this directory is the archive.
    ("debian-powerpc-boot",
     "https://archive.debian.org/debian/dists/potato/main/disks-powerpc/current/"),

    # Walter's one-person computer museum, actively maintained with 2026 entries. Documents the
    # IBM RT 6151 model 115, an RS/6000 7012-390 running AIX 5.1, and a PowerPC 7248-133 (PReP),
    # and hosts EPROM/ROM archives and boot tapes made from images. No robots.txt at all.
    #
    # STOPS AT /walter/computers/ ON PURPOSE. The level above is the author's whole personal site.
    # Nothing forbids taking it; it simply was not what was offered, and a mirror that helps
    # itself to the rest of somebody's homepage because the directory happened to be open is not
    # a mirror this collection wants to be.
    ("giga-nl-walter", "https://www.giga.nl/walter/computers/"),

    # linuxppc-030396.tar.gz and linuxppc-260296.tar.gz -- the FEBRUARY AND MARCH 1996 PowerPC
    # Linux port snapshots, 7.7 MB together. Two files, and they are two of the earliest surviving
    # states of the port whose history gate.crashing.org documents.
    #
    # /pub/historic-linux/ above it may well be worth having. It would be a DIFFERENT archive
    # about early Linux ports generally, not a widening of this one, so the question is left open
    # rather than answered by accident here.
    ("ibiblio-ppc-ports",
     "https://www.ibiblio.org/pub/historic-linux/early-ports/PowerPC/"),

    # --- taken 2026-09-08, the last of the reconnaissance candidates -------------------------
    #
    # TAKEN ONE LEVEL WIDER THAN THE CANDIDATE SAID. The lead was /ELF/ppc64/, 16 files and
    # 3.55 MB. /ELF/ measures 255 files and 6.61 MB -- twice the content for the same trouble, and
    # the tree then has the shape it would need anyway if the scope is ever widened again. Under
    # it: the 64-bit PowerPC ELF ABI Supplement in its whole VERSION SERIES (1.4.1, 1.7, 1.7.1,
    # 1.8, 1.9), which matters because OpenPOWER publishes only ELFv2 and these intermediate
    # ELFv1 revisions exist nowhere else, plus elfspec_ppc.pdf, the SVR4 32-bit PowerPC psABI.
    #
    # Apache 2.4.6 on CentOS 7, EOL since mid-2024, untouched since 2015-01-28. robots.txt 404.
    ("linuxfoundation-refspecs", "https://refspecs.linuxfoundation.org/ELF/"),

    # The surviving playground.sun.com IEEE-1275 archive: CHRP 1.5d through 1.8a and PReP d0.1
    # through d0.3 as PostScript, with the /ppc/ release and draft sets. 125 files, 16.55 MB.
    # robots.txt says `Allow: /`.
    #
    # EVERY MIRROR ITS OWN INDEX NAMES IS GONE -- playground.sun.com, bananjr6000.apple.com,
    # openfirmware.org, noho.eng.sun.com. devicetree.org is maintained, but this subtree is
    # inherited dead weight and one redesign removes it. The level above, /open-firmware/, links
    # nothing and measures zero files, so this IS the root here.
    ("devicetree-openfirmware", "https://www.devicetree.org/open-firmware/bindings/"),

    # PS2/gcc-1.39-aixps2.bin.tar.Z -- COMPLETE GCC BINARIES FOR AIX ON THE INTEL PS/2, dated
    # 1991-04-08, with the contributor's note. RS6000/ holds monitor 1.12/1.14/2.1.5, a Sound
    # Blaster Pro MCV driver, xcd, xmuseq, xntp, 1993-1998. 42 files, 6.98 MB. Directory
    # timestamps 1999-08-11: nothing has moved in 27 years. robots.txt 404.
    #
    # NOTE FOR LATER, AND IT IS A REAL DECISION RATHER THAN A FORMALITY: the level above,
    # /pub/unix/, is a frozen vendor-Unix tree -- AUX/, DEC/, MIPS/, convex/, ctix/, apollo/,
    # Sony-NEWS/ -- measuring AT LEAST 4 534 files and 7.69 GB, and that figure is a floor with
    # 2 246 pages left uncounted. Widening to it would roughly double the non-IBM commercial-Unix
    # material here. Not decided; measured, so that it can be.
    #
    # It also holds RS6000/ and rs6000/ side by side. They survive only because NTFS
    # case-sensitivity is set on this volume.
    ("funet-aix", "https://ftp.funet.fi/pub/unix/AIX/"),

    # The PowerPC Compiler Writer's Guide, powerpc-cwg.pdf, 1 150 106 bytes, Last-Modified
    # 2004-10-13, on djb's machine and untouched for 21 years. Beside it powerpc.pdf (996 984
    # bytes, CONTENTS NOT IDENTIFIED), fog.pdf and cpucycles-powerpc.S.
    #
    # THE DIRECTORY 404s WHILE THE FILES ANSWER 200, so this archive is entirely seed-driven and
    # the run WILL end INCOMPLETE with one unreadable listing. That is the correct outcome, not a
    # failure: there is no listing to read, and pretending otherwise would mean inventing one.
    #
    # The server sends both Content-Length and Transfer-Encoding, which makes strict HTTP clients
    # fail with a parse error. If this archive comes back empty, that is where to look first.
    ("cryp-to-cwg", "https://cr.yp.to/2005-590/"),

    # The SVR4 GENERIC ABI -- gabi40 and gabi41 in pdf and ps -- and the Intel386 psABI 4th
    # edition. The base document every PowerPC psABI supplement extends. 6 files, ~5.6 MB.
    #
    # ALSO SEED-DRIVEN, for a different reason: /devspecs/ is a NAVIGATION SHELL. It carries 43
    # links and not one stays under it; the six specification files are named in the page text and
    # linked from nowhere. A crawl of it fetches the nav page and stops, and would have reported
    # COMPLETE over it. Checked by hand 2026-09-08: all six answer 200, the four SVID volumes 404.
    #
    # robots.txt soft-404s. The host redirects http to https and carries Xinuos branding on SCO
    # markup with live links to a 2005 forum -- a museum piece that is still serving.
    ("sco-devspecs", "http://www.sco.com/developers/devspecs/"),

    # www.crashing.org is a CNAME for gate.crashing.org on the same IP, and Apache serves it as a
    # SEPARATE VIRTUAL HOST with a completely disjoint document root -- so it is a different
    # archive, not a subtree of the one above. Six files, fully linked from its own landing page:
    # the LinuxPPC Developers' Reference Release home, the Release 1.0 and 1.1 press releases,
    # `historic/`, the "Think Different. Think Linux!" image from Macworld SF January 1999, and
    # `mirrors.txt` -- the pointer to the mirrors gate's landing page asks visitors to prefer.
    #
    # Both press releases have GROWN since their Internet Archive captures (1528 -> 2510 bytes and
    # 1547 -> 2864), so the live copies are the better ones.
    ("crashing-org-www", "http://www.crashing.org/"),

    # Dell UNIX SVR4 2.2.1 install media, on the same host as technologists-sauer but a different
    # path, so a different archive: netinst.tar.gz (74.1 MB, the NFS install tree), boot.img,
    # system.img and inet.img (1.44 MB diskette images each), plus the index's own 86Box recipe
    # for installing from them. 78.6 MB, six files, media dated 2021-12-24.
    #
    # Dell UNIX is Charles Sauer's other subject -- he worked on it after IBM -- and working
    # install media for a dead commercial Unix is exactly this collection's kind of thing.
    ("technologists-dellunix", "https://technologists.com/DellUnix2.2.1/"),

    # kernel.crashing.org -- a DIFFERENT MACHINE from gate/www (70.99.78.136 against 63.228.1.57),
    # and the original home: the Installation Guide and glibc21.shtml were served from here in
    # 2001 before moving to gate, and the guide's own copyright page still names
    # this host as the contact.
    #
    # What is left live is a stub landing page, two files identical to gate's copies, and the
    # fray/ and hail/ directories. Its TLS certificate validates cleanly (Let's Encrypt, renewed;
    # an earlier report of a broken chain was stale).
    ("crashing-org-kernel", "https://kernel.crashing.org/"),

    # The SVR4 generic ABI as HTML, in eight dated snapshots from 1998 to 2013 -- the revision
    # history of the document every processor-specific ABI supplement extends. `sco-devspecs`
    # holds the PDF and PostScript editions; this is the version series behind them.
    #
    # Entirely seed-driven: the subdirectories answer 403 to a listing while every file inside
    # answers 200, so there is nothing to walk. 8 snapshots x 17 files.
    ("sco-gabi", "https://www.sco.com/developers/gabi/"),

    # --- the wider roots, taken 2026-09-08 ---------------------------------------------------
    #
    # funet.fi's frozen vendor-Unix tree. AUX/, DEC/, MIPS/, convex/, ctix/, apollo/, Sony-NEWS/
    # and AIX/ under one root, directory timestamps around 1999, one national mirror, no
    # maintainer. This is the commercial-Unix layer that disappears first, for the vendors this
    # collection does not otherwise cover.
    #
    # SIZE IS A FLOOR, NOT A FIGURE: measured at 4 534 files and 7.69 GB with 2 246 pages still
    # unwalked at the page cap. It may be several times that. Recorded as a floor so nobody later
    # reads 7.69 GB as a measurement.
    #
    # SUPERSEDES funet-aix, which holds the same AIX/ subtree at 42 files and 6.98 MB. That
    # archive was taken on 2026-09-08 before this decision; it is now redundant and can be removed
    # once this one completes. The overlap is 7 MB and is documented rather than avoided, because
    # avoiding it would mean an exclude that makes THIS tree incomplete -- and a mirror with an
    # undocumented hole is worse than seven megabytes stored twice.
    #
    # ^^ THAT SENTENCE IS NOW A LIVE INSTRUCTION TO DELETE SOMETHING, AND ITS PREMISE IS GONE.
    # RETRACTED 2026-09-09: **funet-aix STAYS.** This entry will never complete -- it is not
    # going to be run at all (see below), so "once this one completes" is a condition that
    # cannot occur, and acting on the sentence would delete the only copy of that subtree this
    # collection holds. Left in place rather than edited away so the reasoning chain is visible:
    # a conditional deletion whose condition quietly became impossible is a trap, not a plan.
    # DO NOT RUN THIS ENTRY AS IT STANDS. It is left here as a record and a warning; the scope
    # must be narrowed before it is used again. Two things went wrong on 2026-09-08 and only one
    # of them was a tool defect.
    #
    # THE SCOPE WAS WRONG AND WAS NEVER CHECKED. This was registered as "funet's frozen
    # vendor-Unix tree -- AUX, DEC, MIPS, convex, ctix, apollo, Sony-NEWS" on the strength of a
    # measurement. /pub/unix/ also holds FreeBSD/, NetBSD/, OpenBSD/, 4.3bsd/, BSDi/, Linux/,
    # Solaris/, TeX/, X11/, games/, graphics/, editors/, databases/, emulators/ and more. BSD is
    # excluded from this collection by standing decision -- bitsavers drops bits/NetBSD/ at
    # 606.8 GB for exactly that reason. One request for the directory listing would have shown
    # this, and it was not made until 67 GB had been fetched.
    #
    # AND THE CRAWLER WALKED INTO A SYMLINK CYCLE. /pub/unix/tools/less/ carries a link named
    # `xemacs` pointing back into itself. Over HTTP that is not a cycle but an infinitely deep
    # tree of URLs that are each one new, so `seen` never fires. The run reached 42 levels and
    # 68.69 GB -- the same files fetched forty times -- inside a directory whose real content is a
    # few hundred kilobytes of a pager. It had to be killed by hand. looks_like_a_loop() was
    # written that night and is now in both crawl loops.
    #
    # Q:\mirror\funet-unix\ HELD 64.59 GB of which 64.55 GB was the same files
    # repeated. It had no marker, no index and no provenance, deliberately: it was not an
    # archive, it was the wreckage of a run.
    #
    # DELETED 2026-09-10, in two stages: the loop subtree first (+64.63 GB in 79 s), then the 223
    # real files after confirming they had survived it. Checked first for reparse points -- zero
    # in 43 330 entries, so Remove-Item could not follow a junction out of the tree -- and for
    # path length: 44 054 entries over 260 characters, longest 392, which this system handles
    # because LongPathsEnabled is 1. Past tense from here on; this paragraph described a
    # directory that no longer existed.
    #
    # ---------------------------------------------------------------------------------------
    # MEASURED PROPERLY ON 2026-09-08 -- 54 branches, two levels deep, with mirror.py's own
    # parser and 0.7 s between requests. Tables in Q:\mirror\logs\funet-measure.out and
    # funet-live.out. The sizes are FLOORS: level 3 and deeper was not walked.
    #
    #     all 54 branches        6 267 files   8.58 GB
    #     live mirrors           4 029 files   7.61 GB    <- OpenBSD alone is 6.3 GB
    #     COMPLETELY FROZEN      2 238 files   0.97 GB    <- 38 branches
    #
    # THOSE THREE LINES ARE A FLOOR AND THE FLOOR IS BADLY LOW -- correction added the same day.
    # Two levels is not enough. A RECURSIVE measurement of sun/ with measure-remote.py returned
    # 1 017 files and 1.58 GB against the 18 MB the two-level pass reported: a factor of NINETY.
    # BSDi/ is around 416 MB against 4 MB. The frozen set is therefore SEVERAL GIGABYTES, not
    # one, and any plan made from the 0.97 GB figure is planning for a different archive.
    #
    # Kept rather than deleted, because what the two-level pass was FOR -- which branches are
    # frozen and which are live -- holds exactly. Only the sizes are wrong, and a floor that is
    # labelled a floor and is still off by 90x is worth leaving visible next to its correction.
    #
    # RECURSIVE FIGURES, measure-remote.py, ten branches, 2026-09-08 (funet-frozen2.out):
    #
    #     sun       1 017 files   1.84 GB      irc     949 files  157.01 MB
    #     Solaris     443 files   1.26 GB      osi     237 files   62.58 MB
    #     386ix     4 020 files 593.35 MB      sgi     106 files   33.87 MB
    #     BSDi      4 088 files 557.08 MB      DEC      99 files   22.53 MB
    #                                          local    19 files    1.73 MB
    #                                          src      10 files  523.50 KB
    #     ---------------------------------------------------------------------
    #     TOTAL    10 988 files  4.50 GB   -- and still a floor: 66 files have no size
    #
    # 386ix/ is the surprise: 4 020 files of the pre-Linux 386 Unix landscape -- xenix/, sco/,
    # esix/, isc/, svr4/, bsd386/, Solaris.x86/. Every one of those vendors is gone. irc/ is
    # 949 files rather than the 224 the shallow pass saw.
    #
    # A FIRST ATTEMPT AT THIS RECURSIVE PASS ALSO FAILED, and quietly: run with
    # --no-follow-html, measure-remote.py stayed on one page per URL and reported sun/ as
    # ZERO FILES. The flag suppresses opening HTML pages as listings, which on this host is
    # every listing. Third measurement error in one afternoon, all the same shape -- a tool or
    # pattern returning confident numbers for something other than what was asked.
    #
    # ---------------------------------------------------------------------------------------
    # THE WHOLE FROZEN TREE ALREADY HAS A SECOND COPY:
    #
    #     http://ftp.zx.net.nz/pub/archive/ftp.funet.fi/pub/unix/
    #
    # BYTE-IDENTICAL, verified here on 2026-09-08 across four unrelated branches. Not merely
    # equal sizes -- the same Apache ETag, which is derived from inode, size and mtime:
    #
    #     ctix/gnu/gcc.cpio          644096  "9d400-2779815914e80"   both hosts
    #     MIPS/mips-gdb-3.5-diffs.Z   61643  "f0cb-25c9f3cadcd40"    both hosts
    #     apollo/x11r4.tar.Z         570770  "8b592-262831ad7a800"   both hosts
    #     Sony-NEWS/off.tar.Z          2465  "9a1-234e7586c3ec0"     both hosts
    #
    # It carries 4.3bsd/, 386ix/, AIX/, AUX/, apollo/, convex/, DEC/, MIPS/, Sony-NEWS/, sgi/,
    # sun/, ctix/ and the rest, plus the 1992 ChangeLog. `irc/` likewise has a complete copy on
    # the Internet Archive.
    #
    # THIS CHANGES THE SELECTION ARGUMENT. The rule here is "one person's server, no successor".
    # funet is a national academic archive with a second copy behind it -- so on the collection's
    # own terms this material is NOT endangered, whatever its historical interest. The counter-
    # weight is that zx.net.nz self-describes as "an entirely unsupported service", so the second
    # copy is fragile even though the first is not.
    #
    # HOW THIS WAS FOUND, and the lesson is the method rather than the answer: an adversarial
    # pass was run over every "nothing else has this" claim, with the refuters told to default to
    # refuted when uncertain. 24 OF 26 CLAIMS FELL. Among the casualties: irc/ as "the original
    # distribution point held nowhere else", ISIS in misc/, troffcvt in text/ (actively packaged
    # today), and ~325 MB of Solaris/ (CDE and Wabi, both on archive.org). Only two survived,
    # one of them AUX/X11R5pl15/ -- and that one only after two Internet Archive items and the
    # whole of aux-penelope.com were enumerated to prove it is absent from all three.
    #
    # The ranking was reported to the owner BEFORE those refutations were read. That was the
    # error: an adversarial pass is worth exactly nothing if its output arrives after the
    # conclusion has already been sent.
    #
    # THE TREE IS A FOSSIL, and that is the point. /pub/unix/ChangeLog's last entry is
    # 22 January 1992; most directories carry a mass re-stamp of 1999-08-11 and nothing since.
    # This is the early-1990s Unix world, not a current mirror -- which is exactly why it is
    # worth having and exactly why nobody is maintaining it.
    #
    # A FIRST ATTEMPT AT THIS MEASUREMENT PRODUCED A TABLE OF CONFIDENT ZEROES. It hand-rolled a
    # regex for Apache's <td> table layout; funet serves the older <pre> form, so every size read
    # 0.0 MB and every date read "?" -- and the table looked perfectly plausible. parse_listing()
    # already knows three listing shapes and is the only parser here tested against real hosts.
    #
    # THE SCOPE BELONGS AT THE SECOND LEVEL. Neither "one entry per vendor" nor "this base with a
    # short EXCLUDE" is right, because a branch looks alive when ONE CHILD of it is a live mirror:
    # tcpip/ has 17 children of which only bind/ (980 subdirectories) and dhcp/ are current, and
    # the other fifteen have not moved since 1999. Same shape in languages/ (1 of 48), mail/
    # (1 of 24), shells/ (2 of 9), tools/ (2 of 27), news/ (3 of 17).
    #
    # 74 live subdirectories were found, listed in funet-live.out ready to paste as an EXCLUDE.
    # ONE OF THEM IS THE CULPRIT ABOVE: `tools/less/`, last modified 2025-10-01, is a live GNU
    # less mirror -- and `tools/less/xemacs/` is the symlink that produced the 68.69 GB. A
    # date-based exclusion would have prevented the incident this warning is about.
    #
    # WORTH TAKING, by measurement rather than impression. Dead vendors, every one frozen at
    # 1999-08-11, about 600 MB together:
    #     Solaris 458 MB (1992-2004, pre-Oracle)    sgi 33 MB     convex 35 MB     sun 18 MB
    #     DEC 16 MB      apollo 14 MB     AUX 11 MB      os9 12 MB      ctix 2.6 MB
    #     MIPS -- ONE FILE.     Sony-NEWS -- TWO FILES, dated 1989.
    #
    # And two that are singular rather than merely rare: irc/ (224 files -- IRC was written at
    # the University of Oulu in 1988 and this is the original distribution point, not a mirror
    # of one) and osi/ (213 files of a protocol stack with no surviving community at all).
    # doc/ holds something dated 1983.
    #
    # BSD STAYS OUT by standing decision, even though 4.3bsd/ holds genuine net2/, reno/, tahoe/
    # and i386-jolitz/. TUHS covers those -- and 4.3bsd/ also contains the symlinks into the live
    # FreeBSD and NetBSD mirrors that make walking it expensive.
    ("funet-unix", "https://ftp.funet.fi/pub/unix/"),

    # ibiblio's historic-linux collection. The PowerPC entry that led here -- the February and
    # March 1996 port snapshots -- sits in early-ports/PowerPC/, and the tree around it is the
    # same era for every other architecture, plus the OSF MkLinux / Mach sources.
    #
    # ALSO A FLOOR: 5 351 files and 3.77 GB with 2 575 pages unwalked. robots.txt sets
    # Crawl-delay: 2 and does not disallow /pub/, so this will be slow by instruction rather than
    # by accident -- at two seconds a directory it is an overnight job by design.
    #
    # CONTAINS ibiblio-ppc-ports (2 files, 7.7 MB) -- and that archive STAYS.
    #
    # This line used to read "SUPERSEDES ibiblio-ppc-ports, on the same terms as above", where
    # "above" was the funet-aix sentence offering removal once the larger fetch completed. That
    # sentence was retracted on 2026-09-09 as a trap; this one inherited the trap by reference,
    # and unlike funet-aix ITS CONDITION HAS ACTUALLY OCCURRED. ibiblio-historic-linux completed
    # 2026-09-08 with 213 759 files, and both PowerPC snapshots are in it:
    #
    #     early-ports/PowerPC/linuxppc-030396.tar.gz   ce92cc3d...  3.9 MB   identical
    #     early-ports/PowerPC/linuxppc-260296.tar.gz   fcaa5bfa...  3.9 MB   identical
    #
    # Verified by SHA-256 on 2026-09-10, both byte-for-byte. So the removal WOULD have worked --
    # which is exactly why it is being refused in writing rather than left implicit.
    #
    # It stays because this collection's own rule says so: finding duplicates is a REPORTING job,
    # not a cleanup job. ibiblio-ppc-ports carries its own PROVENANCE.md recording why those two
    # snapshots were sought and what they are; deleting the archive discards that account to save
    # 7.7 MB out of 3.7 TB. A conditional deletion buried in a cross-reference is the worst shape
    # such an instruction can take: nobody re-reads the clause it points at.
    ("ibiblio-historic-linux", "https://www.ibiblio.org/pub/historic-linux/"),

    # --- ftp.zx.net.nz, found 2026-09-08 ------------------------------------------------------
    #
    # HOW THIS HOST WAS FOUND IS THE POINT, and it is not flattering. It did not come from the
    # 2026-09-07 reconnaissance -- that ran with an exhausted search budget, CAPTCHA walls at six
    # engines and web.archive.org hard-blocked, and one of its four topic sweeps never returned.
    # It surfaced BY ACCIDENT the next day, when an adversarial agent was asked to prove that
    # funet's ctix/ was not unique and went looking for a second copy.
    #
    # It holds 61 ARCHIVED FTP SITES under /pub/archive/, including gatekeeper.dec.com,
    # service.boulder.ibm.com, hobbes.nmsu.edu, ftp.sgi.com, ultrix-freeware, ftp.kednos.com and
    # jagubox.gsfc.nasa.gov. A host of that size slipping through means the candidate list is not
    # empty, it is unexamined.
    #
    # robots.txt names eight SEO bots and blocks them; there is no `User-agent: *` rule and the
    # file advertises a sitemap. Mirroring is permitted. But the operator's own comment on those
    # bots is "they just waste bandwidth", and the site describes itself as "an entirely
    # unsupported service" -- so this gets 2 connections, not 8.
    #
    # MEASURED BEFORE TAKING, and two of the four obvious targets turned out to be worthless:
    #   playground.sun.com        1 file, 0 bytes. A directory skeleton -- bin/, dev/, etc/,
    #                             pub/ -- with nothing in it. It was written up as "the surviving
    #                             copy of a host our own PROVENANCE calls dead" on the strength
    #                             of that root listing, before anything was counted.
    #   service.boulder.ibm.com   13 186 files, 14.12 GB -- but software/visualagecpp/ measures
    #                             ZERO and everything is under ps/. PS/2 material, and this
    #                             collection already holds two PS/2 mirrors. Overlap unmeasured,
    #                             so NOT taken yet.
    #
    # gatekeeper.dec.com carries its own Index-byname: 986 543 lines, 96.8 MB, one request
    # instead of a crawl. The ORIGINAL was ~358 GB, of which pub/BSD alone is 795 134 files and
    # 187.7 GB. zx mirrored NINE of its fifteen branches and left out exactly the bulk -- BSD,
    # linux, micro, GNU, cygwin, usenet -- keeping DEC's own material. That curation is why this
    # entry is ~12 GB rather than 358.
    #
    # The prize is pub/DEC/ at 3 972 files: SRC (Modula-3, dcpi), WRL (research-reports, and 836
    # MB of the WRL address traces), CRL, and itsy-stuff. Also taken: etc/, six files that are
    # the FTP server's own passwd/services/resolv.conf, and the two Index files, which are an
    # independent manifest of the same shape as bitsavers' .tar.txt.
    ("zx-gatekeeper-dec", "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/"),

    # Hobbes, the OS/2 archive, as zx captured it. 10 732 files and 8.41 GB, read off the host's
    # own ls-lR.gz in one request rather than crawled to find out.
    #
    # New Mexico State University closed the original hobbes.nmsu.edu on 15 April 2024 after
    # thirty years. Sits beside `os2bbs` and the OS/2 material in `fsck-ibm-other`.
    ("zx-hobbes-os2", "http://ftp.zx.net.nz/pub/archive/hobbes.nmsu.edu/"),

    # Joachim's ULTRIX Freeware Archive, as zx captured it on 17 August 2008. 15 files, 2.44 GB,
    # and most of that is ISO images: the September 2002 freeware discs for RISC and VAX, the
    # 2004 RISC/VAX bonus disc, the Starfish disc, and ultrix-risc-os-v4.5.mode1.ufs.bz2.
    #
    # THE ORIGIN IS HALF ALIVE, which is the reason to take this rather than assume either way.
    # www.xanthos.se/~joachim/ufa.html still answers -- but it carries only the five
    # documentation PDFs, and it names TWO mirrors for the discs themselves:
    #     ftp.eagle.y.se/pub/ultrix/ultrix_freeware/   404. Already gone.
    #     musall.de/mirrors/ultrix/freeware/           alive, the same four ISOs as .iso.bz2
    # One of the two named mirrors has died since that page was written. Taken from zx because
    # that copy carries the docs, the README recording the provenance, and the ISOs uncompressed.
    #
    # A first check called xanthos.se dead: a HEAD request timed out. A GET returns 200. Whatever
    # else this file records, "the origin is gone" should never rest on one request shape.
    ("zx-ultrix-freeware", "http://ftp.zx.net.nz/pub/archive/ultrix-freeware/"),

    # Kednos Corporation's FTP server. 635 files, 1.09 GB. pub/ holds bliss/ and gcc/ -- DEC's own
    # systems programming language, and GCC for VMS -- plus basic/, kermit/, mmk/, netlib/, mx/.
    #
    # ftp.kednos.com is DNS-DEAD. www.kednos.com still answers 200, so the company's web presence
    # outlived its file server -- but /pub/ and /pl1/ there are both 404. The site is alive and
    # the files are not on it. This copy is the survivor.
    ("zx-kednos-vms", "http://ftp.zx.net.nz/pub/archive/ftp.kednos.com/"),

    # Microway's customer file server, as zx captured it. ~12 GB.
    #
    # NOT AN ARCHIVE OF DEAD MATERIAL, and the entry says so plainly: for-customer/ holds CUDA,
    # deep-learning and cluster deliveries, and the tree also carries infiniband/, mpi/, pbs/,
    # nvidia/ and win7-update-fixes/. Microway is a live HPC vendor. What is gone is only the
    # directory INDEX at data.microway.com -- the host still answers, with a landing page.
    #
    # The part that belongs in this collection is alphafirmware/, 12 files and 12.3 MB of DEC
    # Alpha firmware. alpha/ lists the same twelve, so it is very likely the same branch twice.
    # Taken whole on the owner's instruction rather than sliced.
    #
    # `pub/` IS THE ROOT. Byte for byte the same 23 entries, and pub/pub/pub/ answers with them
    # again -- a self-reference, infinitely deep. It is excluded below, which costs NOTHING:
    # verified that pub/ contains no name and no size the root does not already have.
    #
    # THE 284 GB THIS WAS FIRST REPORTED AS WAS THAT LOOP, counted over and over by
    # measure-remote.py. Same shape as funet's tools/less/xemacs, but produced by our own
    # MEASUREMENT rather than by a fetch -- which is worse in one way: a bad measurement is what
    # a decision gets made on. The real figure is 5.8 GB at the first level and 6.8 GB one deeper.
    ("zx-microway", "http://ftp.zx.net.nz/pub/archive/data.microway.com/"),

    # Windows NT ON DEC ALPHA. 520 files, 1.55 GB. Drivers/ is the tell: 3c905B-axp.exe,
    # 3com90xDEC.zip, A961206dec_40.exe, DECTAPE.ZIP -- the `axp` and `dec` suffixes are the
    # Alpha builds. Also Applications/, Graphics/, Internet/, Games/, Miscellany/.
    #
    # Microsoft shipped NT for Alpha from 3.1 to 4.0 and dropped it in 1999 with NT 5 already in
    # beta; the Alpha port of what became Windows 2000 was cancelled outright. Third-party
    # software for it had a nine-year window and no successor platform to migrate to. It sits
    # beside gatekeeper.dec.com's pub/DEC/ and the SRM console firmware in zx-microway.
    ("zx-alphant-nt", "http://ftp.zx.net.nz/pub/archive/ftp.alphant.com/"),

    # The OLDER SGI Freeware set: beta/, source/ and cd-1 through cd-4, 2 764 files and 901 MB.
    # `sgi-freeware` (5 791 files, 5.76 GB) is the later one and is measured but NOT yet taken --
    # the two are separate captures, not one superseding the other, and this is the smaller and
    # the more likely to have vanished elsewhere.
    ("zx-sgi-freeware-old", "http://ftp.zx.net.nz/pub/archive/sgi-freeware-old/"),

    # BE INC'S OWN FTP SERVER. 1 745 files, 514 MB: beos/, beos_updates/, bebits/, docs/,
    # experimental/, gnu/, marketing/, and a directory named `contrib_now_closed` that says what
    # happened without further comment.
    #
    # Be Inc sold its assets to Palm in 2001 and the company was wound up. BeOS is outside this
    # collection's AIX/RS-6000 centre, but it is squarely inside its RULE: a commercial Unix-like
    # system whose vendor no longer exists, on a server that is only reachable as someone else's
    # archived copy.
    ("zx-be-os", "http://ftp.zx.net.nz/pub/archive/ftp.be.com/"),

    # --- found 2026-09-10 by a six-angle search with an adversarial check on every candidate ---
    #
    # 52 proposed, 44 REFUTED -- almost all of them because the Internet Archive already holds
    # the material byte-identically, in several cases confirmed by hash rather than by index
    # lookup. These five had to survive a check that fetched before it kept anything.
    #
    # Worth recording as a result in itself: NOT ONE NEW AIX / RS-6000 / PowerPC HOST SURFACED.
    # Every survivor is adjacent silicon -- Apollo m68k, AViiON m88k, Sun-3, transputer. That
    # ground appears to be worked out, and the growth is now at the edges.

    # SUN-3 BOOT PROMs AND PAL FUSE MAPS -- the pieces an emulator cannot boot without.
    # 23 of the 30 boot PROM binaries have NO Wayback copy: every 3/50, 3/110, 3/160, 3/260,
    # 3/460, 3/80, 3/E and both Sun-2/50 PROMs. All 44 PAL JEDEC fuse maps unarchived. 13 of 15
    # schematic GIFs unarchived. bitsavers -- held here in full -- has SunOS media under
    # bits/Sun/sun2/ and sun3/ and NO PROMs and NO PALs anywhere. Zero overlap.
    #
    # Spot-checked rather than trusted: seven ROMs from six models each decompress to exactly
    # 65 536 bytes, and the 3/80 is 360 492 B of Intel HEX at 0xFEF..... -- the correct sun3x
    # PROM address space. Real dumps, not placeholders.
    #
    # THE MOST ENDANGERED THING IN THIS LIST. Dormant since 2016 on a UNIVERSITAT KAISERSLAUTERN
    # network (RIPE: TU-KAISERSLAUTERN, DFN). A personal page on a university net dies with the
    # account, not with an unpaid invoice, and there is no billing failure to warn anyone. One
    # migration has already half-broken it: PHP no longer processes .phtml, so every page ships
    # its literal `<? include ... ?>` with the headers and footers gone.
    ("sun3arc", "https://www.sun3arc.org/"),

    # Ram Meenakshisundaram's Transputer Archive. 742 files, 1.72 GB listed.
    #
    # 456 of those 742 files (0.905 GB, 52.7 % of the bytes) have no Wayback 200 capture.
    # bitsavers has NO inmos/ directory at all -- checked directly against the mirrorservice copy
    # held here, 1 133 vendor directories, none of them inmos. transputer.net is alive and
    # maintained but explicitly refuses to host "Compiler, TDS, Helios or other commercial
    # products", and its own "ram's archive" link points HERE. The living community site treats
    # this host as upstream and does not mirror it.
    #
    # AND IT HOLDS AIX MATERIAL NOBODY WAS LOOKING FOR. Inside
    # software/oses/parix/stuff/EPX-Package-1.9-AIX-SunOS-Solaris.tar.gz is EPX-BP-1.9.1-AIX4.tar,
    # 579 entries including twelve XCOFF binaries and a complete AIX 4 device-driver kit:
    #     dd/hsld                                   178 KB kernel driver
    #     dd/{cfghsl,defhsl,ucfghsl,udefhsl}        the full config/define method chain
    #     dd/ODM/{bull2_link.odmadd,.odmdel,...}    predefined-device stanzas
    # A real 1995 third-party AIX 4 ODM device set with its method chain -- the subsystem behind
    # the cfgscsidisk rc 77 / ODM status=1 failure this project is currently debugging. It is a
    # BULL adapter, and Bull's own hosts are already on the LOST list.
    # Also: documentation/parsytec/parsy_ibm.pdf, languages/ansic/ppc/ppc.tar.gz (which ships
    # include/ppc/portable/rs6k.h and bin/config.sp2.mak -- RS/6000 and SP2 host support).
    #
    # HTTP ONLY. Port 443 is ECONNREFUSED on 208.77.18.143. Any client that force-upgrades to
    # HTTPS fails here, and effective_base() must NOT be allowed to "fix" the scheme.
    ("transputer-classiccmp", "http://transputer.classiccmp.org/"),

    # Novas Are Forever -- the AViiON and DG/UX slice. Whole site measures 39.44 GB across 7 446
    # files; this entry is scoped to the parts that matter and is ~3.75 GB.
    #
    # The 13 ISOs are the only genuinely uncaptured binaries. The headline is
    # 068-003055-17__AV_SCM_Athena-Iliad-Zeus_Update_Utility_Media_R17.00_prom_4.4.0__1993-1996.iso
    # at 196 714 496 B: the System Control Monitor PROM update media for m88k AViiON -- a single
    # point of failure for AViiON emulation. Verified by reading the image rather than the
    # filename: it carries "132.107 DG/UX PassO Arch m88k", "DG/UX System Release R4.11
    # Bootstrap", and DG/UX Virtual Disk Manager structures.
    #
    # robots.txt is a Grav CMS policy: it disallows /system/, /vendor/, /cache/, /bin/, /backup/,
    # /tmp/, /logs/, /tests/, /.github/, /.phan/, /assets/, /webserver-configs/ and /user/ except
    # pages, themes and images -- and carries `Allow: /`. /archives/ is permitted. The disallowed
    # paths are in EXCLUDE below so the crawler cannot wander into them.
    ("novasareforever-aviion", "https://www.novasareforever.org/archives/"),

    # Takanobu Ishimura's Apollo Domain/OS archive. 20 payload archives, 17 787 445 bytes
    # measured, all fetched at 200.
    #
    # Apache 1.2.1/1.3.0 binaries and PORTING PATCH KITS for SR10.4, sendmail 8.8.7/8.8.8/8.9.0,
    # BIND 4.9.7, Samba 1.9.16p9, UW IMAP 4.1, qpopper 2.3, plus GNU tar/make/m4/patch/diffutils.
    # And the hardware layer: DS[345]x00 LED-during-selftest tables, selftest_status.txt, a
    # 190 KB all_stcode.txt status and CRASH_STATUS list, CPU/MEM/DISP/NIC/PS compatibility
    # matrices, a jumper gallery.
    #
    # Wayback holds 387 URLs for this host and ZERO tarballs. jim.rees.org/apollo-archive closed
    # in September 2024 and its Internet Archive successor is one opaque 2 391 500 800-byte
    # apollo-ar.tar with no per-file index -- and Rees never held these kits anyway: he LINKED
    # OUT to apollo.pictinc.co.jp, an older domain of this same site, now dead. The canonical
    # archive delegated upstream and the pointer has already rotted.
    #
    # The LED-pattern-to-fault tables are the same class of artefact as the AIX LED 0554 hunt.
    # /apollo/english/ and /apollo/ are separate content -- the Japanese tree is Shift-JIS.
    ("apollo-clavius", "https://apollo.clavius.jp/apollo/"),

    # WoTUG / IPCA, the INMOS toolchain section. 66 files, 9 487 176 bytes, full recursive crawl.
    #
    # The irreplaceable part is tds3-toolset/ (~1.28 MB), which has NO WAYBACK CAPTURES AT ALL:
    # Michael Poole's plain-ASCII conversion of the INMOS D700E TDS sources. It is not a
    # repackaging of the archived tds3-tds/ -- those .tsr files are TDS-folded binary, and the
    # README states they "require a TDS3 to read and compile them". Poole's conversion is the
    # only readable form, and producing it required someone with a working TDS3. Lose it and the
    # surviving source can only be read by first emulating the product whose source it is.
    #
    # The headline oc-src.tar.gz IS byte-identical in Wayback (sha256 445df2d3...). That was not
    # the reason to take this.
    ("wotug-inmos", "http://www.wotug.org/parallel/occam/compilers/inmos/"),

    # ------------------------------------------------------------------ 2026-09-13, eight small
    # From a five-angle reconnaissance (firmware / disk images / DOS / commercial Unix /
    # non-English). Every one was checked HERE before being written down: alive, robots.txt read
    # in full, and the page SHAPE established -- autoindex or hand-written -- because an entry
    # written without that is how an archive ends up COMPLETE with zero files.
    #
    # A ninth, adoxa.altervista.org, is deliberately NOT here: its downloads are `dl.php?f=...`
    # and is_child_link drops every href containing '?'. That rule is right -- on a generated
    # index a query string is a sort order -- so adoxa needs a URL list, not a crawl.

    # 5 MB. Shiva/Kinetics FastPath AppleTalk-Ethernet gateway firmware: fp4prom/ holds the PROM
    # dumps AND copyprom.c, the tool used to read them; shiva-ftp/ is a salvaged copy of Shiva's
    # own FTP tree with an ls-lR giving an exact inventory. Shiva is gone and the boxes do not
    # boot without these. ZERO Wayback captures on all four files checked. robots.txt 404.
    ("ultimate-fastpath", "http://ftp.ultimate.com/FastPath/"),

    # 41 MB, 37 files. HP 9000 PA-RISC boot ROMs (.frm) and PDC processor firmware, one directory
    # per machine from the 712 to the C8000. THE PROJECT IS ALREADY DEAD: www.parisc-linux.org
    # now serves Apache's stock "It works" page and only this ftp vhost still has content. HP
    # pulled these from hp.com years ago. Wayback is thin and one capture looks truncated --
    # 759 KB against a ~2 MB file. robots.txt permits this vhost (the www one is Disallow: /).
    ("parisc-firmware", "http://ftp.parisc-linux.org/firmware/"),

    # DECmate and VT78 EPROM dumps by DEC part number, ~28 S-record dumps, plus RX01/TU56 media.
    # HAND-WRITTEN .php PAGES THAT LINK INTO AN APACHE TREE, which is exactly why it has ZERO
    # Wayback snapshots: crawlers do not descend through the indirection. Its robots.txt answers
    # 200 with an EMPTY BODY -- nothing blocked. HTML_CRAWL, and see HTML_PAGE for .php.
    ("somuchstuff-pdp8", "https://so-much-stuff.com/pdp8/"),

    # Bret Johnson's DOS TSRs, frozen since 2011 -- and among them a REAL-MODE USB STACK for DOS:
    # usbsourc.zip is 1.65 MB of x86 assembler, with eight dated development snapshots beside it.
    # THE ROOT PAGE CARRIES NO LINKS AT ALL, 22 KB of text; /programs/ and /source/ are ordinary
    # autoindexes. Seeded for that reason. Wayback has 15 of 24 programs and nothing after 2013.
    ("bretjohnson", "https://bretjohnson.us/"),

    # 104 MB, 397 files. ITT 2020 and Basis 108 -- the European Apple II clones -- including the
    # CP/M driver disks (CPMDRVRS.DSK), plus Wang 2200, SWTPC, Sinclair QL, HP-75D. ON FREE WEB
    # HOSTING (square7.ch), and the Internet Archive holds 59 URLs for the whole host of which
    # ZERO have a disk-image extension. robots.txt 404.
    ("square7-vintage", "http://vintagecomputers.square7.ch/Vintage/"),

    # ~343 MB, 274 manuals. Bull SOLAR and SPS5 -- French-language documentation for Bull's own
    # Unix minicomputers, on a plain Apache index. CentOS 7 with PHP 5.4, EOL since June 2024,
    # HTTP ONLY (port 443 refused), which is very likely why the Internet Archive holds 14 URLs
    # under /Info* and NOT ONE PDF. This collection already carries Bull's AIX side; this is the
    # part nobody mirrored. robots.txt has no Disallow.
    ("biblionik-bull", "http://www.biblionik.fr/Info/Bull/SOLAR/"),

    # 490 MB, 133 PDFs. ABC-bladet 1980-2010 complete -- the Luxor ABC80/ABC800 user club's
    # magazine, the Swedish home-computer record. The club's program bank is ALREADY GONE
    # (ftp.abc.se does not resolve); this is what survived. Hand-written, so HTML_CRAWL.
    # Wayback has 68 of the 133, i.e. a real 49% gap rather than the total absence first
    # reported -- corrected by the researcher's own second pass, and worth keeping as a figure.
    ("abc-bladet", "https://www.abc.se/bladet/"),

    # 0.62 GB, 398 files, 277 of them .IMD disk images. PERQ (Accent, PNX, POS) and WICAT
    # (UniPlus System V, WMCS) -- machines almost nothing else preserves. The Internet Archive
    # has crawled this host 13 902 times and holds 19 of 274 images, ZERO of the 148 WICAT ones.
    # AND IT CARRIES ONE THING SQUARELY IN THIS COLLECTION'S SUBJECT: an AIX 4.1.4 boot drive
    # from an RS/6000 ThinkPad 860, 281.9 MiB -- cross-check against ps-2.kev009.com once held.
    # Idle since 2022, tied to a one-person hardware business. robots.txt 404.
    ("decromancer-bits", "https://archive.decromancer.ca/bits/"),

    # ------------------------------------------------------------------------- 2026-09-15, big
    # 49.94 GB, 2 770 files, 140 directories -- MEASURED by walking the host's own index, not
    # estimated. LiteSpeed autoindex, fully browsable.
    #
    # WHY: sgi-irix/development/ holds MIPSpro 7.2, 7.3, 7.4.3m and 7.4.4, IDO 7.1.1, the Fortran
    # compilers and ProDev WorkShop. That is the IRIX counterpart of the thing this collection
    # spent weeks chasing on the AIX side -- a working vendor C compiler for a dead commercial
    # Unix. SGI's own distribution is gone and these sets are not sold, licensed or mirrored.
    # Also sgi-irix/ itself (IRIX 5.3 through 6.5 network-install trees and 615 patch files),
    # nekoware/ in four architectures, and sgi-tools/ with the L3 console emulator.
    #
    # ROBOTS, BECAUSE TWO RESEARCHERS CONTRADICTED EACH OTHER AND BOTH WERE RIGHT. This host --
    # ftp.irixnet.org -- answers 404 for robots.txt; so does tru64.irixnet.org. The apex
    # irixnet.org and www. serve a 189-line file, which is where the disagreement came from.
    #
    # Read in full rather than grepped: it is the decades-old "bad bot" blocklist that circulates
    # in webmaster forums -- Alexibot, BackDoorBot/1.0, BlowFish/1.0, BunnySlippers, Xenu's Link
    # Sleuth, Zeus -- 188 named agents sharing one `Disallow: /`, and archive.org_bot sits in it
    # because the list's author put it there years ago, not as a statement about preservation.
    # THERE IS NO `User-agent: *` ANYWHERE IN IT. An agent that is not named has no rule.
    #
    # We are not named. That is a different situation from update.uu.se, where the club names
    # anthropic-ai, Claude-Web and ClaudeBot explicitly and its ftp host is therefore off limits
    # despite carrying no robots.txt of its own -- same organisation, same people, and a 404 on
    # one vhost is not permission when they have said no on another.
    #
    # The nekoware community has already moved once: nekochan.net is gone and the front page now
    # points onward to a 2025 continuation at nekoware.me.
    ("irixnet-ftp", "https://ftp.irixnet.org/"),

    # --- taken 2026-09-16 from the candidate list ---------------------------------------------
    #
    # H.Merijn Brand's HP-UX depot page, hosted on Ask Bjorn Hansen's mirror machine. gcc 3.3.2
    # through 4.2.2 built for HP-UX 10.20/hppa1.1, plus Perl and OpenSSL -- and gcc 10.20 is
    # precisely the part hpux.connect.org.uk does NOT cover. Frozen 2017-12-29.
    #
    # WHY IT IS URGENT RATHER THAN MERELY INTERESTING. The page names five mirrors of itself and
    # FOUR ARE ALREADY DEAD: perl.org answers 404, nluug.nl does not resolve, and hpux.ws is now
    # an unrelated WordPress blog. The Internet Archive holds the index page and NOT ONE DEPOT.
    # This host is the last copy, and it is one machine.
    #
    # `<meta name="robots" content="noindex,nofollow">` IS ON THE INDEX PAGE, and there is no
    # robots.txt (404). This was put to the collection's owner rather than decided here, because
    # this project honours intent over syntax and has twice chosen to ask an operator instead of
    # fetching. The decision, 2026-09-16, was to fetch, on these grounds: `noindex` governs search
    # INDEXES and a preservation mirror is not one; the page's own words are "for ITRC members",
    # i.e. an author keeping a support page out of Google rather than out of existence; and the
    # machine is called `mirrors.develooper.com` and exists to redistribute software.
    #
    # `nofollow` is the half of that tag that does address crawling, so the run is deliberately
    # small and slow -- see WORKERS_BY_ARCHIVE and MIN_INTERVAL. Recording the argument matters
    # more than the conclusion: a later reader must be able to see that this was weighed and by
    # whom, not assume nobody noticed the tag.
    #
    # Measured ~13 GB / 571 files. The index itself carries 226 links of which only 41 are local;
    # the rest are ftp:// and http:// pointers to other people's sites and are correctly refused
    # by is_child_link.
    ("develooper-hpux", "https://mirrors.develooper.com/hpux/"),

    # NORSK DATA -- the Oslo minicomputer maker whose NORD-1, NORD-10 and ND-100 ran much of
    # Scandinavian research computing, CERN included. 936 articles, and the granularity is the
    # point: there is a page per HARDWARE CARD, by part number -- `1001 (NORD-10 card)`,
    # `101 (NORD-1 card)` -- which is documentation that exists at this level nowhere else.
    #
    # 1 164 uploaded files, of which 138 are the part that is genuinely unheld: 89 floppy and
    # firmware images, 40 scanned manuals, the ND110 emulator sources, and the ND-Nytt house
    # magazine from May 1972. The Internet Archive holds 1 231 of the photographs and ONE PDF.
    #
    # NOT CRAWLED. Fetched through the wiki's own API by mediawiki-source.py -- see EXTERNAL for
    # why, including why /images/ is not walked even though it is an open autoindex. Listed here
    # so `--index` and `--verify` can see the tree; mirror.py must never be pointed at the base
    # URL itself, which is a MediaWiki and would be copied as rendered HTML plus every
    # action=history and oldid= variant of every page.
    ("ndwiki-norsk-data", "https://www.ndwiki.org/"),

    # THE MUNICH PEANUTS ARCHIVE, surviving under the NiCE NeXT User Group name. peanuts.leo.org
    # no longer resolves, and this collection's `next-68k-org` is FROZEN -- so this is the living
    # copy of the NeXTSTEP/OpenStep software archive. /pub/next/developer/ is the toolchain tree,
    # and the coverage reaches beyond m68k to the HP PA-RISC and SPARC ports.
    #
    # MEASURED 2026-09-17: 2 957 files, 1.22 GB. The candidate note said "7 245 files, ~1.3 GB
    # estimated" -- the size was close, the COUNT was not, and the difference is that the old
    # figure was extrapolated while this one was walked.
    #
    # ITS LISTING IS NOT AN AUTOINDEX. Each row is
    #     <div class="odd">…<a class="name" href="audio/">audio/</a>…</div>
    # so `href` is not the first attribute and there is no size or date column. mirror.py reads it
    # through LINK_ODD_RE; measure-remote.py could NOT, and reported this host as 0 files / 0 B
    # until that was fixed the same day -- see the note on A_RE there. Files therefore arrive
    # without a listing date and are stamped from Last-Modified instead.
    #
    # The root page also links /peanuts/GeneralData/Usenet/, which is OUTSIDE this base URL and
    # correctly refused. That tree is not taken here.
    #
    # robots.txt exists and names only Bingbot, plus a sitemap index.
    ("nice-next", "https://ftp.nice.ch/pub/next/"),

    # Jason Hood's DOS and Win32 tools -- ANSICON, the console driver that gave Windows ANSI
    # colour for a decade before the OS did, plus DOS utilities and patches. One person's site on
    # free hosting, unchanged for years.
    #
    # MEASURED 2026-09-17 IN TWO PARTS, because the whole point of this entry is that one part is
    # invisible to a crawler:
    #     directly linked       438 files    65.67 MB   (16 size lookups failed -- a floor)
    #     behind dl.php?f=      216 files    50.28 MB   (216 of 216 measured, 0 failures)
    #                           654         115.95 MB
    # `is_child_link` rejects every href containing '?', which is right for a crawler -- on a
    # generated index those are sort links and traps. Here it means THE ACTUAL PROGRAMS are the
    # part that gets skipped: ansicon, bew, win32, win64, each served as application/zip by
    # dl.php?f=<name>. This archive therefore needs a second pass over an explicit URL list; the
    # crawl alone would look complete and contain no software at all.
    #
    # robots.txt 404.
    ("adoxa-dos", "http://adoxa.altervista.org/"),

    # METROPOLI BBS, Helsinki -- one of the largest Finnish boards, its file areas kept online.
    # `hardware/` is what made this a candidate: driver disks foldered by VENDOR AND EXACT MODEL,
    # often as the loose unpacked contents of the support floppy rather than as an archive --
    # display chips, the proprietary-interface CD drives (Mitsumi, Panasonic, Chinon), network
    # cards, printers, ROMs. Original BBS dates survive in Last-Modified.
    #
    # THE HOST STATES ITS OWN DIRECTORY SIZES, which is rarer than it sounds and made a crawl to
    # measure it unnecessary. Taken 2026-09-17 on the owner's decision, everything but `tmp/`:
    #
    #     sekalaiset          37.74 GB      ifsc2.ifsc.usp.br   14.08 GB
    #     software             2.33 GB      hardware             1.40 GB
    #     skene                0.82 GB      drivers_1            0.42 GB
    #     tlr                  0.12 GB      ---------------------------
    #     tmp                  8.96 GB  EXCLUDED                56.92 GB
    #
    # www.mpoli.fi/files/ 301s to files.mpoli.fi, so the canonical host is used directly. Both
    # robots.txt were read: the files host has none that reach us (only commented-out sitemaps),
    # and www disallows three personal directories -- /~pervert/, /~jalmari/, /~olli/roska/ --
    # none of which is under /files/.
    #
    # ITS LISTING CARRIES SIZES THAT parse_listing DOES NOT READ. The index shows "424.54 MB" per
    # directory in a form none of the three column matchers recognises, so children arrive with
    # size=None and the ETA is guesswork for this archive. Harmless -- sizes come from the
    # transfer -- but it is why the progress line here is less useful than elsewhere.
    ("mpoli-bbs", "https://files.mpoli.fi/"),
]
```
