#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Mirror whole archives, one producer thread feeding a pool of downloaders.

97 archives, 1 760 827 files, 3 977 GB: AIX packages and IBM's own distribution tree,
plus the hardware documentation an emulator has to be written against.

  THESE THREE NUMBERS ARE GENERATED, NOT TYPED. They are the sum of the .mirror-complete
  markers; `python catalogue.py --root Q:/mirror --recount` prints them and writes CATALOGUE.md,
  and `refresh-table.py` rebuilds the HELD table below from the same source. A hand-maintained
  headline goes stale silently and did: it read "Thirty archives, 791 631 files, 2 907 GB" while
  the table twenty lines below already summed to 826 162 -- the file disagreeing with itself.
  Re-run both after every fetch.

What they have in common is the reason for copying them at all -- most are served by one
person from one machine, none has an obvious successor, and several have already lost a
maintainer once. Archives with a funded host behind them are deliberately not here, with
one ruled exception noted in the table.

THIS FILE IS THE MASTER RECORD. Every state lives here -- what is held, what is deferred,
what was measured and rejected, and what an operator has forbidden -- so that the status
and the program cannot drift apart. ARCHIVES carries the per-archive reasoning; the table
below is the summary to read first.

===============================================================================================
STATUS -- 2026-09-08
===============================================================================================

HELD                                    files      size   note
  bitsavers                           176 028  1196.7 GB  via rsync.mirrorservice.org
  ibm-aix                             190 974   702.4 GB  IBM's AIX tree incl. the Toolbox
  fsck-vendors                          9 372   403.7 GB  37 vendor trees: SGI, Sun, DEC-Compaq,
                                                          NeXT, HP, Be, QNX, SCO ... 356 of the
                                                          357 failures are ONE QNX directory
  ps-2.kev009.com                     206 410   342.0 GB  RS/6000, AS/400, S/390, PS/2
  vtda                                 29 759   234.7 GB  five rsync modules
  oss4aix.org                         184 465   208.0 GB  Perzl's AIX open-source builds
  oldskool                             77 628   149.2 GB  Trixter's early-PC area: hundreds of raw
                                                          floppy images, MicroProse's own files,
                                                          the Tandy 1000 tree, CopyIIPC Option
                                                          Board. drivers/ taken 2026-09-22, 125.3
                                                          of 313.9 GB; video and SimTel excluded.
                                                          49 listings 404 at the source itself --
                                                          marker written by hand, see it
  fsck-ibm-other                        1 327   105.9 GB  18 non-AIX IBM trees: OS/2, OS/390, z,
                                                          PC-DOS, 3174, 4690, PS/2 support
  fsck-aix-media                          608    70.1 GB  AIX 1.2.1-5.1 media; SUBSET by design
  ia-bullfreeware                      11 969    66.2 GB  the 85 GB whole-site upload made the day
                                                          bullfreeware.com closed. THE ANSWER TO THE
                                                          GCC 4.8.4-for-AIX-7.1 hole. One packages.tar
                                                          with a .sfv manifest beside it
  irixnet-ftp                           2 770    53.6 GB  MIPSpro 7.2/7.3/7.4.3m/7.4.4, IDO 7.1.1
                                                          and ProDev WorkShop -- the IRIX answer to
                                                          the AIX compiler problem this collection
                                                          chased for weeks. Plus IRIX 5.3-6.5
                                                          network installs, a 3.12 GB patch omnibus,
                                                          and nekoware (2 146 files), which has
                                                          already had to move once. THE FIRST RUN
                                                          SAID COMPLETE WITH 230 FILES: ROW_RE
                                                          matched the sortable table header and
                                                          swallowed nekoware/, the first data row
  bullfreeware                         14 869    49.4 GB  SALVAGED; both hosts are gone
  bull-rpms                             7 117    45.8 GB  via the power-devops rescue
  next-68k-org                        234 761    37.7 GB  UNPACKED 2026-09-07 from a tar inside
                                                          fsck-vendors; several NeXT FTP servers
                                                          under one roof. NO third-party manifest
  dec-ftp-2006                         22 172    36.0 GB  UNPACKED from bitsavers/mirrors/; ~3/4 is
                                                          ONE tree served under three names
                                                          (Digital/, DEC/, Compaq/) -- unconfirmed
  ibm-rs6000-support                    1 619    27.1 GB  PReP/CHRP reference boards, and the
                                                          IEEE-1275 bindings as primary
                                                          documents. Held once; a second copy
                                                          under the name dhe-rs6000 was removed
                                                          2026-09-04 -- see its PROVENANCE
  ardent-tool                          25 608    22.0 GB  board-level RS/6000 detail
  somuchstuff-pdp8                    110 572    19.2 GB  Vince Slyngstad's PDP-8 archive: 2.3 GB
                                                          DEC library, 2.2 GB DECUS, 962 MB MAINDEC
                                                          field diagnostics, scans up to 143 MB
                                                          each, and the .lbl labels off the physical
                                                          paper tapes. Hand-written .php pages over
                                                          an Apache tree -- which is why it had ZERO
                                                          Wayback snapshots. Needed
                                                          TIMEOUT_BY_ARCHIVE: three listings take
                                                          90-128 s to generate and were written off
                                                          as unreadable until then, costing 25 984
                                                          files
  bull-srpms                            1 873    19.2 GB  sources for the Bull binaries
  ibm-redbooks                          2 871    16.9 GB  NOT a rescue -- IBM has served these for
                                                          30 years. Taken on request, not on rule
  fsck-aix-apps                           355    16.8 GB  COMMERCIAL AIX software -- VisualAge
                                                          C++, COBOL, Mathematica, SoftWindows.
                                                          ONE SOURCE, no second copy anywhere
  infania-solaris                       2 559    16.4 GB  ibiblio's Solaris packages, sparc + i86pc.
                                                          The Solaris sibling of oss4aix and Bull
  zx-microway                             474    15.7 GB  Microway's customer file server. NOT dead
                                                          material: for-customer/ is CUDA and cluster
                                                          deliveries, and the firm is trading. What is
                                                          gone is only the directory index. Held for
                                                          alphafirmware/, 12 files of DEC Alpha
                                                          firmware. pub/ IS the root -- excluded
  ibiblio-historic-linux              225 110    15.4 GB  sunsite.unc.edu as it stood in Nov 1994 and
                                                          Sep 1996, plus early-ports/ and
                                                          distributions/
  develooper-hpux                         580    12.6 GB  H.Merijn Brand's HP-UX depots. gcc 2.8.1
                                                          to 4.7.2 for 10.20 through 11.31 -- and
                                                          10.20 is what hpux.connect.org.uk does
                                                          NOT cover. 26 Perls, openssl 0.9.7d to
                                                          1.0.2n. Four of its five named mirrors
                                                          are dead and IA holds no depot at all
  os2bbs                               21 476    10.8 GB  IBM's OS/2 BBS incl. its FixPaks. 97%
                                                          held nowhere else here -- every name
                                                          in its own catalogue checked against
                                                          all 560 319 BEFORE fetching
  rwth-aachen-ftp                      10 561    10.3 GB  incl. a copy of IBM's PC BBS
  tuhs                                 12 139     9.3 GB  the original UNIX tapes
  zx-hobbes-os2                        10 722     8.8 GB  Hobbes, the OS/2 archive NMSU closed on
                                                          15 April 2024. 10 722 of the 10 732 its
                                                          own ls-lR names; the ten are absent from
                                                          zx, not from our copy
  zx-gatekeeper-dec                     9 183     8.6 GB  DEC's own FTP server, as ftp.zx.net.nz
                                                          archived it. pub/DEC/ is SRC (Modula-3,
                                                          dcpi), WRL, CRL, the Itsy and 836 MB of
                                                          address traces. FOUR RUNS SAID COMPLETE;
                                                          the source's own Index-byname found 509
                                                          files still missing -- see PROVENANCE
  mpoli-bbs                            23 180     5.7 GB  Metropoli BBS, Helsinki. hardware/ has
                                                          driver disks by vendor AND model, often
                                                          the loose floppy contents. 11 MB of 1990s
                                                          PCBoard PPEs lost: 500 on host, not in IA
  hp-labs-2007                          9 171     4.0 GB  UNPACKED. techreports/Compaq-DEC/ is 525
                                                          DEC lab reports: SRC, WRL, CRL, PRL, NSL
  novasareforever-aviion                  369     4.0 GB  the AViiON SCM PROM image, 196 714 496 B,
                                                          plus DG/UX media. The store 403s on every
                                                          directory; names exist only as hrefs.
                                                          Fetched with the OPERATOR'S PERMISSION --
                                                          see PROVENANCE
  crashing-org-kernel                     757     3.8 GB  kernel.crashing.org -- a DIFFERENT host
                                                          (70.99.78.136), and where the material
                                                          started; captures show it whole in 2001
  zx-ultrix-freeware                       15     2.6 GB  Joachim's ULTRIX Freeware Archive as zx
                                                          captured it in 2008: the Sept 2002 RISC and
                                                          VAX discs, the 2004 bonus and Starfish discs,
                                                          and an ULTRIX 4.5 filesystem image. The index
                                                          page at xanthos.se still answers but holds
                                                          only the PDFs; of the two disc mirrors it
                                                          names, ftp.eagle.y.se is already 404
  agilent-ftp-2009                        814     2.5 GB  UNPACKED. Its own index names SIX discs;
                                                          the tar holds four. cd5+cd6 absent
  ia-bull-aix433-2013                     247     2.4 GB  the same tree in 2013 -- and this one HAS
                                                          the compilers: gcc 2.95.3, 3.0.1, 3.3 as
                                                          native installp filesets
  transputer-classiccmp                 1 062     1.9 GB  INMOS/occam/Helios/Parix. Holds
                                                          EPX-BP-1.9.1-AIX4.tar with a complete AIX
                                                          4 ODM device kit: hsld, cfg/def/ucfg/udef
                                                          methods, bull2_link.odmadd. A FRAMESET
                                                          root -- see PROVENANCE
  ndwiki-norsk-data                     3 843     1.7 GB  Norsk Data. A page per HARDWARE CARD by
                                                          part number -- 1001 (NORD-10 card), 101
                                                          (NORD-1 card). 2 675 pages at current
                                                          revision + 1 164 files, through the
                                                          wiki's own API. 138 of those files are
                                                          unheld anywhere: 89 disk and firmware
                                                          images, 39 of 40 manuals, ND-Nytt 1972
  zx-alphant-nt                           520     1.7 GB  Windows NT for Alpha AXP. The only NT that
                                                          ever ran on a 64-bit RISC, dead since NT 4
                                                          SP6
  nice-next                             4 539     1.3 GB  The Munich Peanuts archive, under the
                                                          NiCE NeXT User Group's name. NeXTSTEP
                                                          and OpenStep software -- m68k AND the HP
                                                          PA-RISC and SPARC ports. peanuts.leo.org
                                                          is gone and next-68k-org is FROZEN, so
                                                          this is the living copy
  hp-openvms-2008                      27 373     1.3 GB  UNPACKED. doc/ per release: 7.3 and 8.x
                                                          complete, 7.2 a stub of 2 files
  zx-kednos-vms                           634     1.2 GB  Kednos Corp's FTP server. pub/ holds bliss/
                                                          and gcc/ -- DEC's systems language and GCC
                                                          for VMS -- plus 59 files of PL/I docs.
                                                          ftp.kednos.com is DNS-DEAD; www.kednos.com
                                                          answers but serves none of it. Last copy
  gsi-collection                        5 752     1.2 GB  3 695 permanent 404s: a deleted NCD
                                                          mirror whose catalogue survives
  hp-alphaserver-2008                  10 202     1.0 GB  UNPACKED. 35 files had a BACKSLASH in
                                                          their Unix name; see RENAMED.txt
  ia-bull-aix433-2005                     200   0.981 GB  Bull freeware for AIX 4.3.3, April 2005.
                                                          NO COMPILERS, though its own TOC names
                                                          three. Do not trust its 00_MD5.txt
  zx-sgi-freeware-old                   1 295   0.944 GB  the retired SGI Freeware tree: IRIX
                                                          tardist packages. Measured 2.40 GB and
                                                          fetched 0.944 GB -- measure-remote counts
                                                          what listings NAME, and this one names
                                                          404s
  filibeto-aix-lib                        174   0.841 GB  AIX manual sets IBM dropped
  crashing-org                          7 231   0.745 GB  gate.crashing.org, the PowerPC kernel
                                                          developers' own machine. ~benh/ holds G5
                                                          cpufreq and SLOF work
  ia-bull-toolbox-43                      271   0.695 GB  a third copy, different uploader. The 19 KB
                                                          htmlfiles.tar.gz is bullfreeware.com's own
                                                          site HTML from the early 2000s
  decromancer-bits                        398   0.668 GB  PERQ and WICAT disk images, 277 of them.
                                                          IA crawled this host 13 902 times and
                                                          holds 19 of 274, ZERO of the 148 WICAT.
                                                          Carries an AIX 4.1.4 boot drive from an
                                                          RS/6000 ThinkPad 860 -- cross-check
                                                          against ps-2.kev009.com. Idle since 2022
  zx-be-os                              1 745   0.539 GB  BeOS. ftp.be.com has been gone since Palm
                                                          bought Be in 2001; this is zx's capture of
                                                          it
  damage-rt                               266   0.504 GB  AIX 2.2.1 (RT) + AOS 4.3
  abc-bladet                              135   0.455 GB  ABC-bladet 1980-2010 complete: the Luxor
                                                          ABC80/ABC800 user club magazine, thirty
                                                          years of Swedish computing culture. The
                                                          club's program bank is already gone
                                                          (ftp.abc.se does not resolve). IA has 68
                                                          of 133
  biblionik-bull                          275   0.361 GB  274 French-language Bull SOLAR and SPS5
                                                          manuals -- the Bull line nobody mirrored.
                                                          CentOS 7, EOL June 2024, HTTP ONLY, and
                                                          that is very likely why IA holds 14
                                                          wrapper pages and not one PDF. One
                                                          connection: least robust host here
  technologists-sauer                      58   0.345 GB  Charles H. Sauer's IBM RT PC and AIX papers.
                                                          SCOPE IS THE OPERATOR'S: robots.txt allows
                                                          /sauer/ and forbids five neighbours
  AIX5-IA64                                92   0.325 GB  Project Monterey: AIX 5.1L on Itanium, 63
                                                          .tar.Z inside a git repository
  giga-nl-walter                          525   0.320 GB  Walter's one-person computer museum (NL),
                                                          still maintained -- entries dated 2026
  infania-tl1                          18 769   0.270 GB  IBM TechLibrary CD, V3R10 (2001)
  aixtools                                100   0.263 GB  SALVAGED; the site is gone
  infania-tl2                          19 848   0.255 GB  IBM TechLibrary CD, V3R2 (1999) --
                                                          a DIFFERENT tree, not an older tl1
  sun3arc                               1 106   0.222 GB  Sun-3 m68k: 539 official SunOS patches, 42
                                                          boot PROM images, the Field Engineer
                                                          Handbook. Its pages are .phtml, which
                                                          HTML_PAGE did not walk -- 227 images
                                                          arrived only after that fix
  circle4                                 409   0.189 GB  Jaqui Lynch's AIX performance work.
                                                          Two crawls found 7 of 212 files and
                                                          reported no error -- see ARCHIVES
  square7-vintage                         397   0.104 GB  ITT 2020 and Basis 108, the European Apple
                                                          II clones, with their CP/M driver disks.
                                                          On FREE web hosting; IA has 59 URLs for
                                                          the whole host and zero disk images
  rs6000-microcode                        183   0.081 GB  RS/6000 firmware, salvaged. 61 .bin,
  hp-labs-linux-salvage                   125   0.004 GB  the level BELOW hp-labs-2007's .php4
                                                          pages, which bitsavers' 2007 capture
                                                          never followed. 105 .php4, 8 .jpg,
                                                          5 .gz. 22 of the 24 the finding named
                                                          60 of them XCOFF32; 24 .exe, all of
                                                          them MZ; + 96 HTML procedure pages.
                                                          3 .suspect remain, 12 superseded
  technologists-dellunix                    5   0.079 GB  working Dell UNIX SVR4 2.2.1 install media
  adoxa-dos                               437   0.076 GB  Jason Hood's console and DOS tools --
                                                          ANSICON, which gave cmd.exe ANSI colour
                                                          a decade before Windows did. TWO PASSES:
                                                          213 of the releases sit behind
                                                          dl.php?f= and the crawler cannot see a
                                                          '?'. The crawl alone held no software
  penguinppc                              601   0.076 GB  PReP residuals for 7043-140, 7025-F40
                                                          and five more; the live host 404s them.
                                                          Tom Gall's ppc64 port patch, quik
  debian-powerpc-boot                      72   0.073 GB  Debian potato PowerPC boot images, 2001
  bretjohnson                              50   0.070 GB  A REAL-MODE USB STACK FOR DOS, 1.65 MB of
                                                          assembler with eight dated snapshots, plus
                                                          TSRs. Frozen 2011. The front page carries
                                                          NO links at all -- seeded, or this would
                                                          have been one file reported COMPLETE
  aix-orphans                             303   0.070 GB  SALVAGED, from Perzl's link list
  infania-os-history                    1 011   0.069 GB  index-fallback fix recovered 29 files;
                                                          thin relevance, kept whole not half
  aix-qemu-git                            167   0.064 GB  3 repos + a gist, WITH HISTORY
  parisc-firmware                          37   0.041 GB  HP 9000 PA-RISC boot ROMs and PDC
                                                          firmware, one directory per machine. THE
                                                          PROJECT IS DEAD -- www.parisc-linux.org
                                                          serves Apache's default page and only this
                                                          ftp vhost has content. One IA capture is
                                                          truncated at 759 KB against a 2 MB file
  techsysadm                              361   0.039 GB  IA holds NO snapshot of the domain
  dialectronics                           276   0.030 GB  Old World Mac booting, an XCOFF bootloader,
                                                          pcc PowerPC codegen -- authored, held
                                                          nowhere else. Complete except a 156-photo
                                                          gallery neither host nor IA still has.
                                                          Host bans by address; do not re-crawl
  typewritten                           3 409   0.025 GB  AIX PS/2 1.2.1, RT 2.2.1, AOS 4.3
  apollo-clavius                          236   0.024 GB  Apollo DOMAIN/Domain‑OS: binaries built
                                                          for a toolchain that no longer exists. Was
                                                          outside HTML_CRAWL on a correct
                                                          observation about links -- which also
                                                          switched off <img src>, and cost 81 files
  cryp-to-cwg                              22   0.022 GB  D. J. Bernstein's 2005 course directory:
                                                          the PowerPC Compiler Writer's Guide and
                                                          IBM's Book I. SEEDED -- the dir 404s
  devicetree-openfirmware                 123   0.017 GB  IEEE-1275 Open Firmware bindings, CHRP
                                                          and PReP. All four mirrors its own index
                                                          names are dead; this is the survivor
  sco-devspecs                             13   0.016 GB  SVR4 gABI and the SVID on Xinuos's remains
                                                          of sco.com. SEEDED: the index is a shell and
                                                          links none of the 13 specs
  csiph-gallery                            43   0.011 GB  hash-checked: none duplicates kev009
  wotug-inmos                              60   0.009 GB  INMOS occam compilers and the D700E TDS.
                                                          tds3-toolset/ has NO Wayback captures at
                                                          all. Two .bat files answer 503 by server
                                                          rule -- marker written by hand
  aixpdslib                             2 182   0.008 GB  UCLA's AIX Public Domain Software Library,
                                                          salvaged; origin times out. XCOFF32
                                                          binaries built for AIX 3.2 and 4.1
  ibiblio-ppc-ports                         2   0.008 GB  Feb and Mar 1996 snapshots of the PowerPC
                                                          Linux port -- among its earliest states
  funet-aix                                42   0.007 GB  ftp.funet.fi's AIX corner. GCC 1.39 for AIX
                                                          on the PS/2 -- a platform with no emulator
                                                          and no other archive. RS6000/ and rs6000/ are
                                                          the same 20 files; the server serves both
  linuxfoundation-refspecs                255   0.007 GB  the ELF spec archive. PPC-elf64abi 1.4.1
                                                          through 1.9, the WHOLE ELFv1 series;
                                                          OpenPOWER publishes only ELFv2
  ibm-openxl-docs                         795   0.007 GB  salvaged from the IA. The DWARF finding:
                                                          AIX defaults to DWARF 3, no -gdwarf-5
  iffly-wiki                              968   0.006 GB  DokuWiki source, GFDL 1.3
  ultimate-fastpath                        37   0.004 GB  Shiva/Kinetics FastPath firmware: PROM
                                                          dumps AND copyprom.c, the tool that made
                                                          them, plus a salvaged copy of Shiva's own
                                                          FTP tree. Zero IA captures on all four
                                                          files checked. A FastPath does not boot
                                                          without these and Shiva is gone
  misterhayden                            144   0.004 GB  domain lapses 2026-10-08
  perzl-wiki                            1 109   0.003 GB  the index to oss4aix.org
  sco-gabi                                135   0.002 GB  the SVR4 gABI in HTML, 8 dated snapshots over
                                                          15 years. Every subdir 403s a listing, so all
                                                          136 URLs are seeded; latest/ is linked nowhere
  tvsat-cpc710                              1  0.0004 GB  IBM CPC710 datasheet
  infania-unixos2                          40  0.0003 GB  <base href> fix recovered 21 of 32 --
                                                          the whole packages/ branch
  csri-toronto                              2  0.0001 GB  two CSRI troff papers
  crashing-org-www                          3  0.0000 GB  the LinuxPPC Developers' Reference

DEFERRED -- measured, wanted, waiting on a larger disk
  ftpmirror.infania.net/sites       5 subtrees  unmeasured  RELEVANCE SETTLED 2026-09-05, and it
                                                          collapses the >=324 GiB headline to
                                                          almost nothing. Of 98 subtrees, ~70 are
                                                          home computers (12 alone for Amstrad
                                                          CPC) plus PC graphics drivers.
                                                          `bitsavers` -- ~85 % of the bytes -- is
                                                          held via rsync. `unixarchive` IS TUHS:
                                                          Distributions/ carries the same ten
                                                          directories and three probes at
                                                          different depths (UCB/4BSD,
                                                          Research, Documentation/Manuals) were
                                                          deckungsgleich, no file on either side
                                                          missing from the other. Held.
                                                          WHAT IS ACTUALLY LEFT: os2bbs.com
                                                          (47 dirs), ftp.compaq.com (pub, 9
                                                          dirs), unixos2.org (14 files),
                                                          os-history.de (11), solaris (4).
                                                          Not sized: the HTTP walk exceeds ten
                                                          minutes and FTP passive data is blocked
                                                          from this host (control connects, then
                                                          WinError 10060) -- the same wall that
                                                          forced the earlier survey into Docker.
                                                          Fetch them without a figure -- but
                                                          NOT on the "8 GB floor guard" this
                                                          line used to cite. MIN_FREE_BYTES is
                                                          1 GB since 2026-09-06, an eighth of
                                                          that. Measure first.
                                                          NEVER bitsavers/ over HTTP.
  fsck.technology/software/BSD/             -           -  Excluded by standing decision, not by
                                                          size: FreeBSD and NetBSD are abundantly
                                                          available and in no danger. The same
                                                          rule keeps bits/NetBSD/ (606.8 GB) out
                                                          of the bitsavers mirror.

  MEASURED 2026-09-06, and the number that governs every infania plan is not size but SPEED.
  The host gives us 100-200 KB/s while our own link does 7 150 KB/s from kernel.org and
  973 KB/s from aix.software.ibm.com in the same minute. The cap is theirs, not ours.
  Use the default 8 workers and run nothing else against the host concurrently -- an earlier
  claim here that fewer connections were faster came from a benchmark taken while a second job
  shared the link, and is corrected at the os2bbs entry. Consequences at ~212 KB/s:

    os2bbs.com          21 476 files   10.82 GB   HELD 2026-09-06, verified, 0 failures. Took
                                                  ten hours. The pre-fetch measurement said
                                                  21 222 files / 9.91 GB and was 254 files short
                                                  because the listing walk timed out on
                                                  graphics/ -- a measurement is a floor.
    ftp.compaq.com     104 944 files  219.71 GB   ~12 DAYS    -- measured in 74 min, 5 492 pages
    unixos2.org             18 files   157.51 KB  COMPLETE, 20 pages, queue exhausted. It is a
                                                  small WEBSITE, not an archive. Take it or
                                                  leave it on content, not on size.
    os-history.de         >=171 files    >2.08 MB  FLOOR: 111 pages still queued at the cap.
                                                  Was "6 files" before the walker was fixed.
    solaris             >=1 514 files  >581.45 MB  FLOOR, and the weakest number here: only 150
                                                  of the 1 514 files got a size, 22 pages were
                                                  still queued. Those 150 average 3.88 MB, which
                                                  WOULD put the tree near 6 GB -- but that is an
                                                  EXTRAPOLATION FROM A TENTH OF THE FILES, and
                                                  extrapolation is exactly how infania came to
                                                  be called "20-60 GB" when it is over 324 GiB.
                                                  Re-measure with --max-heads high before
                                                  believing any total. It is ibiblio's Solaris
                                                  Package Archive, mirrored -- packages, so the
                                                  sizes are probably NOT uniform.

  ftp.compaq.com AT THREE WEEKS OF CONTINUOUS TRANSFER is a different proposition from "a small
  subtree", which is what it was called before anyone measured it. It also will not fit: 219.71 GB
  against 21 GB free.

  THE WEBSITE UNDER-MEASUREMENT IS FIXED, 2026-09-06. Two defects in measure-remote.py, both
  the same shape -- a walker that could not see what it was looking at:

    * It queued a link as a page only when it ended in "/". A mirrored website's pages do not:
      index.html links pages/Downloads.html, which links the archive. Those were counted as
      leaf files and never opened, so unixos2.org measured as 12 files. Now any .html/.htm/
      .php/.asp/extensionless link under the root is BOTH counted as content and walked as a
      listing -- which is mirror.py's own R16, arrived at independently.
    * It ignored <base href>. unixos2.org's mirrored HTML declares
      `<base href="/mirrors/unixos2.org/">`, the path it had on its ORIGINAL host; infania
      serves it at /sites/unixos2.org/ and returns 404 for /mirrors/ entirely. So the author's
      `pub/list/ux2bs/` was resolved against whatever page it appeared on and 404'd. The tool
      now honours <base> and REBASES it onto the mirror root when the declared path is not
      served here. Failed size lookups fell from 19 to 3 and measured bytes tripled.

  A count that rises after a fix is easy to trust; this one FELL, from 30 files to 18, and that
  is the better number -- the extra twelve were URLs the tool had invented.

  www.redbooks.ibm.com              2 673 docs   15-20 GB  RAISED BY THE OWNER 2026-09-07.
                                                          1 624 Redbooks (sg) + 1 049 Redpapers
                                                          (redp) + 272 Technotes, counted from
                                                          the site's own sitemap.xml (3 022
                                                          entries, 2 985 abstract pages).
                                                          The size is an EXTRAPOLATION from 22
                                                          random PDFs, 22/22 reachable, mean
                                                          7.3 MB / median 5.7 MB -- labelled as
                                                          such because this file has been wrong
                                                          twice by extrapolating.
                                                          robots.txt is three lines and permits
                                                          it: Disallow /cgi-bin/, /api/, */api/*.
                                                          Nothing blocks the PDF tree. Read
                                                          directly, not taken on trust.
                                                          PDFs are NOT in the sitemap; they hang
                                                          off the abstract pages at
                                                          /redbooks/pdfs/<id>.pdf and
                                                          /redpapers/pdfs/<id>.pdf, so the id
                                                          list from the sitemap is enough and no
                                                          crawl of 2 985 pages is needed.
                                                          OPEN QUESTION, the owner's to settle:
                                                          all 2 673, or filtered to AIX/Power?
                                                          AND A CAVEAT WORTH STATING: Redbooks do
                                                          not fit this collection's selection rule
                                                          -- one server, one person, no successor.
                                                          IBM has hosted them for thirty years and
                                                          they are widely mirrored. At 20 GB it is
                                                          cheap insurance, but it is insurance,
                                                          not rescue, and should not quietly
                                                          become the precedent for taking things
                                                          that are in no danger.

  --- OS/2 candidates, raised 2026-09-06. Operator wishes CHECKED, sizes NOT yet measured. ---

  www.os2site.com                           -           -  THE OPERATOR ASKS FOR THIS, which is
                                                          rare enough to record precisely. Its
                                                          robots.txt has NO `User-agent: *` rule
                                                          at all; it addresses named agents only.
                                                          Search engines (Googlebot, DuckDuckBot,
                                                          Adsbot, Mediapartners) are Disallowed
                                                          every binary type -- .zip .exe .rar .7z
                                                          .gz .tar .rpm .jar .sys .wpi .xpi and
                                                          the .1dk-.5dk disk images. But BOTH
                                                          archiving agents, `ia_archiver` AND
                                                          `archive.org_bot`, are Allow-listed for
                                                          exactly those same extensions. The
                                                          operator is keeping binaries out of
                                                          SEARCH INDEXES while expressly inviting
                                                          PRESERVATION -- the mirror image of
                                                          rwth-aachen-ftp, where ia_archiver was
                                                          the one agent turned away.
                                                          OFF-LIMITS even so, named in every
                                                          block: /cgi-bin/, /mirrors/,
                                                          /sw/incoming/, /sw/new/, /sw/unknown/.
                                                          `/mirrors/` matters -- it is somebody
                                                          else's tree and excluding it is also
                                                          what stops a mirror-of-mirrors.

  hobbes.nmsu.edu                           -           -  GONE FROM ITS ORIGIN. DNS no longer
                                                          resolves (getaddrinfo fails) while
                                                          nmsu.edu itself resolves fine, so this
                                                          is the archive being withdrawn, not an
                                                          outage. New Mexico State University ran
                                                          the central OS/2 archive for decades.
                                                          IT SURVIVES: hobbesarchive.com resolves
                                                          (96.86.240.81) and serves "Welcome to
                                                          Hobbes". NOT a plain tree -- it is an
                                                          ASP.NET application, /pub/ 404s and
                                                          there is no robots.txt, so enumeration
                                                          has to be worked out before any fetch.
                                                          Highest-value OS/2 candidate we have.

  os2news.warpstock.org                     -           -  Reachable, "OS/2 Warp News and Rumors".
                                                          Its robots.txt permits us -- baiduspider
                                                          and bingbot are Disallowed, `*` is not --
                                                          but sets `Crawl-delay: 30` and
                                                          `Request-rate: 1/30`. ONE REQUEST PER
                                                          THIRTY SECONDS is the operator's price,
                                                          and it is not negotiable: 1 000 files
                                                          would take 8.3 hours of wall clock. Size
                                                          it first; the delay makes a blind fetch
                                                          irresponsible rather than merely slow.

  www.bitwiseworks.com                      -           -  Moved to DO_NOT_FETCH, see there.

  COMPLETED 2026-09-05 and removed from this list: fsck.technology's OS400_i install media
  (219 files, 71.22 GB) and the AIX Install Media remainder (158 files, 50.56 GB). The second
  had been called "duplicates"; by PART NUMBER it was not -- AIX 4.3.3 revision 07, the 12-2000
  Bonus Pack, the 4.3.3 Update, 5.2 LCD4-1133-10, 5.3 LCD4-7463-05 and -14 and TL 5300-12 were
  all absent. A hash comparison afterwards found 27 files that genuinely were duplicates of
  the curated collection, 13.63 GB, and those were removed from the collection side, not here.
  With them, THE WHOLE OF fsck.technology/software/ IS HELD EXCEPT BSD.

REJECTED -- measured; the reason is not size. Do not re-propose.
  minuszerodegrees.net                  7 099   12.42 GB  ZERO files matching aix, RS/6000,
                                                          70xx, PowerPC, Micro Channel or any
                                                          PS/2 model number, across all 7 099
                                                          paths. A fine IBM PC/XT/AT site.
  heha.fwh.is                              15      59 KB  Not enumerable: no directory index,
                                                          and /sitemap.php -- the site's own
                                                          page list -- returns the free-host
                                                          interstitial. 15 files of CSS/JS.
  csiph.com (bulk)                          -          -  An NNTP server, not a file archive.
                                                          The 8 532-file `timc` tree that made
                                                          it a candidate 404s everywhere,
                                                          including in all 7 IA captures of it.
                                                          Its gallery WAS taken.

FORBIDDEN -- the operator said no. Enforced in code, not remembered: see DO_NOT_FETCH.

  NOT forbidden, though it was checked: rwth-aachen-ftp. Its host's robots.txt is 37 bytes and
  names ONE crawler -- `User-agent: ia_archiver` / `Disallow: /` -- with no `User-agent: *`
  rule. It does not reach this copy by its letter, and by its sense it asks not to be put in the
  Wayback Machine, which a private unpublished copy does not do. Settled 2026-09-05. The reading
  holds only while the copy stays private; publishing it would be the act the line objects to.

PERMANENTLY LOST -- 94 files in FOUR archives, counted from the tree rather than from memory:

    bullfreeware      59        penguinppc        21
    aixtools          11        rs6000-microcode   3

  The count is whatever `find Q:/mirror -name "*.suspect"` returns; do not maintain it by hand.
  It read "73 files in three archives" until 2026-09-06 because penguinppc's 21 had never been
  added to the tally -- a fourth archive quietly missing from a list that named itself complete.
  That is the same defect as every other stale number in this file, and the answer is the same:
  the tree is the record, the prose is a copy of it.

  The 2026-09-05 re-check that earned this figure is still the point: each file was tested
  against EVERY Internet Archive capture of its URL, not just the one the salvage happened to
  take. Fifteen files carrying this label were recovered by it -- 12 in rs6000-microcode
  (+30 MB) and 3 in bullfreeware (+201 MB), among them gcc-3.3.0.0.exe at 9 999 682 B held
  against 52 966 597 B available, and samba-3.0.26.0.bff at 130 767 B against 96 051 200 B.
  The superseded short copies are kept as *.suspect.superseded.

  For the 94 that remain, the best capture really is the short one -- measured, per file.

SETTLED WORK -- the lessons, and nothing outstanding

  This was headed OPEN WORK until 2026-09-22, by which time all fifteen entries under it read
  CLOSED or SETTLED and none was open. A reader looking for what still needs doing had 430 lines
  to scan before learning there was nothing. The entries stay because several say in their own
  words why they must -- "THE GENERAL LESSON, which is why this stays here after being closed" --
  and because the most valuable one records a case where markers, counts, checksums and exit
  codes all agreed with each other while describing a tree that was missing 42 GB.

  CLOSED 2026-09-07 -- BULLFREEWARE'S PACKAGE REPOSITORY, which was the largest known gap in
  this collection when it was found on 2026-09-06.

    7 068 files, 42.6 GB, fetched in 640 minutes. ZERO failures: nothing throttled, nothing
    unfetchable, nothing short, nothing broken. The archive went from 7 801 files / 3.6 GB to
    14 869 files / 49.40 GB, and `verify-content.py` reads every byte of it back correctly.

    The 7 068 is exactly what the pre-fetch CDX measurement predicted, which is the rarest
    outcome in this file: a number that was measured, acted on, and turned out right.

    1 191 distinct packages for AIX 5.1 through 7.3 -- the whole gcc line from 4.0 to 10,
    golang, python 2 and 3, boost, php, httpd, bind, samba, perl and the GNOME stack.

  HOW IT WAS MISSED, WHICH IS THE PART WORTH KEEPING. The salvage fetched what the pages LINK,
  and these pages link nothing: they list package names as plain text and download through a
  session endpoint, /download/bin/<id>/<name>. In the Archive that endpoint answers 200 with
  the site's welcome page -- 2 753 bytes of HTML under an .rpm name, Content-Length matching,
  no short transfer, no error. EVERY CHECK THIS COLLECTION HAD PASSED THEM, and 258 such files
  sat in the tree looking like packages for a week.

  It surfaced only when find-html-imposters.py read the FIRST BYTES of all 774 634 files and
  asked what they actually were. A crawler that follows links cannot find what is not linked;
  only comparing content against the catalogue can. The files were at their real paths in the
  Archive the whole time -- packages/RPMS/<arch>/<pkg>/<name> -- where no page links them.

  THE GENERAL LESSON, which is why this stays here after being closed: a completion marker
  proves a run had nothing outstanding. It does not prove the run was ASKED for the right
  things. Counts, byte totals, checksums and exit codes all agreed with each other and all
  described a tree that was missing 42 GB. Only reading the content disagreed.

  SETTLED 2026-09-05 -- all ten archives that lacked a PROVENANCE.md now have one. The last
  three were the biggest (bitsavers, ibm-aix, ps-2.kev009.com, ~2 276 GB) and researching them
  turned up three things that were documented WRONGLY, not merely undocumented:
    * bitsavers.org's .htaccess names ClaudeBot -- now in DO_NOT_FETCH, HTTP only.
    * ps-2.kev009.com's marker said "Nothing we failed to fetch". 153 files were lost to
      case-folding collisions and all 153 are genuinely absent from the tree.
    * ps-2.kev009.com runs nginx now, not the lighttpd that mirror.py and a defect write-up
      both state as fact.
    Seven of the original ten now have one -- gsi-collection, rwth-aachen-ftp,
    filibeto-aix-lib, ardent-tool, tuhs, oss4aix.org and vtda -- each written 2026-09-04 from
    its log and from fresh measurement, not from notes made at the time.

  SETTLED 2026-09-05 -- "vtda's bits/ overlaps the rest of the collection by an UNMEASURED
  amount; nobody has compared it against bitsavers or ps-2.kev009.com." Now measured by
  `containment.py`, which joins every archive's .sha256sum and needs no tree re-read. vtda
  overlaps the collection by 460 of 29 740 files, 15.41 GB of 234.73 GB = 6.6% -- and the fear
  was aimed at the wrong archive: against bitsavers it is 143 files / 0.77 GB and against
  ps-2.kev009.com 14 files / 0.35 GB. The overlap is with fsck-vendors (82 files, 13.46 GB),
  which did not exist when the worry was written.

  THE WHOLE COLLECTION HAS BEEN READ BACK AND CHECKED AGAINST ITS CHECKSUMS. 2026-09-06:

    36 archives, 804 686 files, 3 494.75 GB, 2.0 h at 493 MB/s average
    ZERO mismatches, ZERO missing, ZERO unreadable -- every byte matches its recorded SHA-256

  This had never been done. The checksums were WRITTEN over the months the collection was
  built; nothing had ever read them back. `--verify` cannot do it and says so in its own code:
  "Counts and bytes cannot see a file whose content changed while its size stayed the same" --
  which is precisely how bit rot presents, since a flipped bit does not change a file's length.
  Use `verify-content.py` for this; it is resumable and reports MISMATCH, MISSING and UNREADABLE
  as three different things, because they have three different causes.

  Run it again before any long-term archiving, and after any move between volumes. The 2.0 h
  figure is the cost of knowing, on this hardware, for 3.5 TB.

  CROSS-ARCHIVE CONTAINMENT, whole collection, 2026-09-05. NO ARCHIVE CONTAINS ANOTHER; the
  highest coverage is 61.2% and there is no 100% row, so nothing here is redundant and nothing
  may be dropped in favour of another archive.

    on disk (excl. empty files)  3495.45 GB   797 728 files
    distinct content            3157.83 GB   631 256 hashes
    dedup saving                 337.62 GB   9.7%, 166 472 surplus files
      of which cross-archive      47.59 GB   the rest is duplication WITHIN one archive

    THE PACKAGING CONSEQUENCE: only 47.59 GB of the 337.62 GB redundancy spans archives, so
    packing each archive separately gives away 1.4% of 3.5 TB and keeps every archive
    independently restorable. Pack per archive.

    Highest coverage, direction significant (`A -> B` = of A, exists byte-identically in B):
      fsck-aix-apps    -> fsck-vendors      182 files  10.26 GB  61.2%
      rwth-aachen-ftp  -> ps-2.kev009.com  8 611 files  6.11 GB  59.5%
      ardent-tool      -> ps-2.kev009.com  7 549 files  6.87 GB  29.1%
      infania-tl1 <-> infania-tl2          ~3 240 files 0.10 GB  ~37% each way
    ASYMMETRY IS THE POINT: fsck-aix-apps -> fsck-vendors is 61.2% of 16.76 GB, the reverse
    only 8.8% -- but 38.66 GB. Same files, different denominator. Never quote one direction.

    12 archives overlap nothing at all. 97.0% of distinct contents exist in exactly one archive.

  RETRACTED 2026-09-04 -- "ardent-tool is three files short of its source". IT IS NOT. All
  three are present with byte sizes matching the live source exactly (987 785 / 603 675 /
  950 828). The COLLISION DROPPED lines came from the FIRST run on 2026-08-26; the third run
  on 2026-08-27, by which time `datasheets` carried the NTFS case-sensitive flag, fetched them.
  The claim was made by reading historical log lines as a standing condition without looking at
  the tree. A log records what happened at a moment; only the tree says what is true now.

  SETTLED 2026-09-08 -- every COLLISION DROPPED line in the collection, audited against the tree.
  773 such lines exist across all logs. They are NOT 773 losses:

      ps-2.kev009.com   765 lines, 153 distinct pairs   ALL 153 WERE REAL AND STILL MISSING
      ardent-tool         6 lines,   2 distinct pairs   both healed by the third run
      ibm-aix             2 lines,   2 distinct pairs   both spellings present today

    The 153 were recovered (case-collision-recover.py; see NEEDS_CASE_SENSITIVE). Of the four
    others, one was never a case collision at all: `CK_E020%20Series.pdf` and
    `CK_E020 Series.pdf` are the SAME URL, encoded two ways, and the claim map compared the
    decoded form against the raw one. Harmless -- the file is present once, which is correct --
    but it means the DROPPED counter over-reports, and anyone auditing these lines should decode
    before concluding anything.

    THE METHOD IS THE POINT, and it is the one this file already learned once from ardent-tool:
    parse the log for candidates, then ask the TREE, then -- before calling a difference a loss --
    fetch both spellings and compare bytes. Three of six sampled pairs on ps-2.kev009.com were
    byte-identical, i.e. the same file listed twice. Skipping that last step would have inflated
    153 real losses into a claim about all 765 lines.  [2026-09-08]

  SETTLED 2026-09-08 -- `<img src>` WAS NEVER FOLLOWED, and it cost 12 195 files across eight
  archives that all carried a COMPLETE marker. Link extraction read `<a href="...">` only: not
  single quotes, not unquoted, and never an embedded image. The stored pages named 10 067 inlined
  images that were not on disk, and a sample HEADed against the origins returned 200 for every
  one.

    ardent-tool     +3 421   2524_System_Board_Bottom.gif, penarch.jpg -- board photographs
    crashing-org    +5 800   mostly ~benh/pics/
    gsi-collection  +1 425   DEC 370, MOTOROLA 273, HP9000 201, IBM 136, AIX 126 -- CHIP AND
                             HARDWARE PHOTOGRAPHS. Called "mostly decoration" here on the
                             strength of a sample that happened to hit LOGOS/ and IMAGES/,
                             which hold 16 files between them.

    Fixed via parse_listing(images=...), for HTML_CRAWL archives only: on a generated index the
    only <img> are the server's own /icons/, which resolve outside base_url and are dropped.

  SETTLED 2026-09-11 -- AND THAT FIX REACHED ONLY THE ARCHIVES WHOSE PAGES IT RECOGNISED. Two
  further ways to hold an image back, found the day after the five Tier-1 archives were declared
  finished, both on archives carrying a COMPLETE marker with zero failures:

    sun3arc          +237 files, 227 of them images. Its 134 pages end in **.phtml**, and
                     HTML_PAGE was `\.s?html?$`. Every page was SAVED and none was WALKED, so
                     878 links and 318 <img src> sat on disk unread. Nothing broke, because the
                     SEEDS had opened the directories and the listings covered the linked files.
                     Only the embedded images had no second route, and only they were lost.
    apollo-clavius   +9 images. It was left OUT of HTML_CRAWL on the correct observation that
                     all 264 of its links were reachable from the directory listings -- correct,
                     and beside the point, because that set also decides whether <img src> is
                     followed. The nine Apollo logo variants are embedded and never linked.

    THE SHARED LESSON IS ABOUT THE SECOND ROUTE. A link usually has one: the file it names also
    appears in a directory listing, so missing the link costs nothing and the defect stays
    invisible. An embedded image usually has no second route. That is why every one of these
    eight defects surfaced as missing PICTURES while the link handling looked fine -- the images
    were not more fragile, they were merely the only thing being measured.

  ANSWERED 2026-09-11 -- WHAT THE href-BLIND SPOT ACTUALLY COST: 1 797 FILES, and the shape of
  that number matters more than the number. All nine archives whose stored pages carried links
  the old `<a href="` rule could not see were re-run with the widened parser. 378 468 files
  before, 380 265 after, over roughly 382 GB and eleven hours of directory requests:

    ibiblio-historic-linux  +960   213 759 -> 214 719   the largest gain anywhere
    infania-tl1             +725    18 044 ->  18 769   the IBM RS/6000 Q&A fax pages
    gsi-collection           +50
    ps-2.kev009.com          +24    of 95 052
    infania-os-history       +22
    ardent-tool              +16    of 26 641 -- against 15 478 blind links
    crashing-org               0
    zx-gatekeeper-dec          0    of 9 183
    giga-nl-walter             0

  ROUGHLY 0.5 %, AND THAT CONFIRMS THE RULE RATHER THAN THE ALARM. A blind link is almost never
  a missing file, because the file it names is nearly always in some directory listing too --
  the second route absorbs the defect and nothing shows. Where there is no second route the
  defect is total, which is why the SAME parser weakness cost 227 files on sun3arc and 72 on
  apollo-clavius, both of them images. The right question about any newly-found blind spot is
  never "how many links" but "do those targets have another way in".

  Three of the nine gained NOTHING, which is the other half of the lesson: had this run been
  reported before it was made -- as the funet ranking was -- the claim would have been that
  20 000 blind links meant 20 000 recoverable files.

  A HAND-WRITTEN MARKER SURVIVES ONLY WHILE THE ARCHIVE KEEPS FAILING. ibiblio-historic-linux
  carried one for four days, holding the measured account of four permanent failures and a
  correction to an explanation that had been wrong. On 2026-09-12 the first run that finished
  cleanly OVERWROTE IT -- correctly: .mirror-complete is this tool's file, rewritten by every
  successful run, and the run had earned it. The reasoning went with it, and was recovered only
  because it was still in this session.

  THE MOMENT THE REASON FOR HAND-WRITING A MARKER IS FIXED, THE TOOL TAKES ITS FILE BACK. So
  anything that must outlive that belongs in PROVENANCE.md, which nothing here ever writes. The
  markers for wotug-inmos, misterhayden, cryp-to-cwg, sco-devspecs and sco-gabi are hand-written
  today and each is one successful run away from the same fate; their content is duplicated in
  their PROVENANCE.md for that reason.  [2026-09-12]

  NOT A DEFECT, A PRICE -- `dirs` DOES NOT COUNT DIRECTORIES ONCE AN ARCHIVE IS HTML_CRAWL, and
  the cost it hides is the reason ps-2.kev009.com now takes sixteen hours.

    directories on disk                6 928
    HTML pages on disk                84 262   walked as well as saved, since HTML_CRAWL
    sum                               91 190
    what the run reported as "dirs"   90 390

  The counter is "things enumerated", and for a hand-written site a page IS a listing -- that is
  the whole premise of HTML_CRAWL. Three explanations were tried on that gap before this one and
  all three were WRONG, each disproved by a measurement: the beta/ cross-linked graph (it is
  600-900 directories, walked breadth-first from the source to check), Windows' 260-character
  limit (os.walk under \\?\ returns the identical 6 928), and a runaway in the new container rule
  (2 341 firings, none of them spurious).

  THE PRICE IS PAID IN SOMEBODY ELSE'S BANDWIDTH. To read a page for links, producer() FETCHES IT
  AGAIN, even when the identical bytes are already on disk -- so a re-run of ps-2 costs 84 262
  extra requests to one person's server for content already held, and that, not the downloads,
  is the sixteen hours. Reading the stored copy instead would trade those requests for the risk
  of missing links added since; that is a real trade and not an obvious improvement, so it is
  recorded here rather than quietly made.  [2026-09-12]

    AND THE SLOWNESS IS NOT A THROTTLE ANYWHERE -- measured 2026-09-13, seventeen hours into the
    run, because "we must be rate-limited" is the comfortable answer and it was wrong:

        median 0.684 s per request over ten pages of this site
        a 312-byte page took 0.52 s, a 64 KB page 1.07 s

    Size barely moves it, so this is LATENCY, not bandwidth -- an ordinary transatlantic HTTPS
    round trip. It does not degrade as the run goes on, which a throttle would. And
    ps-2.kev009.com is not in WORKERS_BY_ARCHIVE: it runs at the default EIGHT connections with
    no delay at all.

    0.684 s serially is 1.5 requests/s; the run averaged 2.4/s. THE EIGHT WORKERS DOWNLOAD FILES.
    producer() -- which fetches every listing and every page to read its links -- IS ONE THREAD
    walking `pending` one entry at a time. When every file is already on disk the workers have
    nothing to do and the whole run is producer-bound: one request, wait, next request. Raising
    --workers changes nothing whatsoever.

    So there are exactly two ways to make a confirmation run of this shape faster: read the
    stored pages instead of re-fetching them (the trade above -- worth an explicit flag, never a
    default, or the mirror has quietly stopped looking for anything new), or parallelise the
    producer, which multiplies the load on somebody's hobby server and is the opposite of what
    the politeness rules ask for. The owner chose to let it run.

  SETTLED 2026-09-11 -- A GUARD THAT LOOKED RIGHT AND COMPARED THE WRONG STRINGS. ELEVENTH, and
  the most instructive, because the clause had been in place since 2026-08-26 and its comment was
  accurate about every case except the one that mattered.

    asked     https://www.ibiblio.org/.../install-guide-2.2.2.html
    Location   http://www.ibiblio.org/.../install-guide-2.2.2.html/

  ibiblio DOWNGRADES THE SCHEME in Location -- an Apache whose ServerName carries no https. The
  test was `final.rstrip("/") == url.rstrip("/")`, whole strings, so it failed on `https` vs
  `http` and the "this is a directory" conclusion was never reached. The body that came back was
  the directory's own index page, and it was written under the directory's name: FOUR files of
  122 077 bytes, each byte-identical to the listing it impersonates.

  The cost showed up one run later, and not as a failure to fetch. Each impostor now occupied the
  path its own contents needed: 2 416 files logged `LOST (a file occupies a parent directory of
  this path)`, 604 apiece under redhat-4.0, 4.1 and 4.2. A defect that writes a plausible file is
  worse than one that writes nothing, because the tree looks fuller afterwards.

  same_path_plus_slash() now compares host and path and ignores the scheme. THE GENERAL POINT:
  every comparison in this file that takes two URLs is a comparison between something we asked
  for and something a server said, and the server is free to re-spell its own name. `effective_
  base()` already learned this for http->https on the base URL; this is the same lesson one
  request deeper.

  SETTLED 2026-09-11 -- A CACHE-BUSTER ON AN IMAGE IS NOT A QUERY. NINTH of the shape, found by
  probing the auditor's leftovers against the origin instead of explaining them away.
  ardent-tool writes `<img src="Lacuna.gif?v=3">`, and is_child_link() drops every href
  containing '?'. For a LINK that is right -- on a generated index `?C=N;O=D` is a sort order and
  following those walks the same directory once per column. For an EMBEDDED IMAGE it throws the
  picture away: Lacuna.gif is a photograph of a planar, answers 200 at the source, and was never
  requested. strip_cache_buster() now strips the query for <img src> and ONLY when the part
  before '?' already ends in a static image extension, because `img.php?id=5` really does select
  and stripping there would fetch one wrong file while looking complete.

    Found by asking the ORIGIN about 12 of the auditor's remaining "absent images": 6 answered
    200, 6 answered 404. Half were real gaps and half were the source's own dead references, and
    no amount of reasoning about the paths would have separated them.

  NOT A DEFECT, RESIDUE -- files whose names contain '#'. A fragment names a position inside a
  document, never a document, and ardent-tool held Lacuna.html together with
  Lacuna.html#DirectConnection and Lacuna.html#ECP_support, all three 56 018 bytes and identical.
  strip_fragment() has handled this since 2026-09-03 and nothing new is being created; what
  remains was fetched before that date, and every one of them cost the source a full transfer.

    THE COUNT IS NOT THE CLEANUP LIST, and this is exactly where a careless pass would delete
    real files. Of the 3 422 counted on 2026-09-03, 771 had NO base file beside them and were
    genuine filenames containing '#'. The removable set -- a byte-identical base file present --
    was ardent-tool 1 157, gsi-collection 1 343, ps-2.kev009.com 148, ibm-aix 3: 2 651 files,
    1.87 GB. remove-fragment-copies.py has since taken them.

    RE-MEASURED 2026-09-22 over all 97 indexes: 1 090 files, 7.14 GB, and the earlier caution
    now describes almost the whole set. EIGHT of the 1 090 have a base file. The rest are
    ordinary names in which '#' is an ordinary character:

        bitsavers    721   Tektronix_Catalog_1965_#24.pdf, ADC#1_84241_J30_.../30m.td
        ardent-tool   86   see below
        next-68k-org  70
        somuchstuff-pdp8 61, tuhs 40 (2.9bsd .../box#0/maintenance0.rx50.gz),
        oldskool 39 (Python CD #2.iso, Wave Blaster Disk #1), vtda 37, mpoli-bbs 22, ps-2 8,
        fsck-vendors 3, rwth-aachen-ftp 2, os2bbs 1

    So the 7.14 GB is CONTENT, not waste, and a rule keyed on '#' alone would now delete 1 082
    real files to reclaim nothing. ardent-tool's remaining 86 -- PS55/video/#Video_Connector and
    the like, 27 distinct contents, 3.1 MB -- look like true residue and are not removable
    either: NONE of those 27 exists anywhere in the archive under a name without '#'. The page
    was never fetched separately, so the fragment copies are the only copies there are.

    A THIRD CATEGORY WAS REPORTED HERE AND DID NOT EXIST: "89 files that share a stem and DIFFER
    in content, which want looking at". All 89 were an error in the tool that produced them. A
    name BEGINNING with '#' has no stem, and splitting on '#' gave the empty string, which
    os.path.join turned into the DIRECTORY -- os.path.exists said yes, the digest could not open
    it, and the pair was filed as "different bytes". ardent-tool/8556/#System_FW and #Planar are
    23 007-byte pages generated by MAD-PageGen and signed by Louis Ohland: content, filed under
    "needs explaining" because the test was wrong. The stem must be non-empty AND a FILE.
    Measured again with that fixed: the category is EMPTY.  [corrected 2026-09-12]

  SETTLED 2026-09-15 -- A SORTABLE TABLE HEADER IS ALSO A LINK, and ROW_RE started matches on
  one. NINTH of the shape, and the only one so far inside the listing parser itself rather than
  in what it is pointed at.

    Apache's HTMLTable autoindex and LiteSpeed's both write

        <th><a href="?C=N;O=D">Name</a></th>

    with href as the FIRST attribute, which is exactly what `<a\s+href="` wants. The old `.*?`
    then ran under re.S across </th>, across the next header link, across </tr></thead>, and
    stopped at the first `</a></td>` in the document -- which belongs to THE FIRST DATA ROW. That
    row vanished into the match; the captured href was the sort link and was correctly discarded.

    Measured on ftp.irixnet.org: the first match began at `<a href="?MA">` and spanned 393
    characters, ending inside `nekoware`'s row. The run reported COMPLETE, 0 failures, 0
    unreadable listings -- over 230 files where 2 770 exist. Fixing it recovered 2 540 files and
    36.6 GB.

    WHY IT HID FOR SO LONG, and this is the part worth keeping: on almost every autoindex the
    first data row is the PARENT DIRECTORY link -- `../`, or an absolute path above the base.
    Losing that costs nothing, because startswith(base_url) discards it two steps later anyway.
    The defect only bites where a server puts a real child first, and LiteSpeed's autoindex does
    precisely that because it emits no parent link at all.

    AUDITED ACROSS THE COLLECTION rather than assumed: each archive's base listing fetched once
    and parsed with BOTH patterns. 18 of 73 reachable archives differed; in 16 of them the
    difference was the parent link. Two were real -- irixnet-ftp (fixed) and one file in
    misterhayden, `Stevens/L3Guide.html`, which that archive already holds because it is fetched
    by autoindex-tls-broken.py and not by this crawler.

    The audit could not reach 15 archives (FROZEN, rsync, FTP, or simply slow), so it is a floor
    and not a proof. Deeper directories were not compared either. What it does establish is which
    servers emit the shape at all, and that only one held archive was materially short.

  SETTLED 2026-09-11 -- THE AUDITOR HAD THE SAME DISEASE. crawl-gap-audit.py reported 0 absent
  images for sun3arc while a direct call to its own check_refs() said 213. Its containment test
  compared `os.path.normpath(target)` -- which rewrites "/" as "\" -- against a `base` built
  straight from --root. Invoked as `--root Q:/mirror` the two differ from the third character on,
  every target was skipped as out-of-archive, and the tool printed a clean bill of health for the
  whole collection having compared nothing. A checker that reads nothing and a checker that finds
  nothing print the identical line. THAT is the thing to keep testing for, in the tools as much as
  in the crawler.

  SETTLED 2026-09-08 -- EXCLUDE APPLIED TO DIRECTORIES ONLY, which was invisible until the line
  above was fixed. The test sat inside the `endswith("/")` branch, harmless only while a file
  under an excluded subtree could not be reached without entering that subtree. Following
  <img src> ended that: crashing-org excludes `icons/` and its pages embed
  `<img src="../icons/next.gif">`. Four icons landed before it was noticed. An exclusion is a
  decision about a subtree, not about one way of arriving at it. Hoisted in BOTH walks.

  SETTLED 2026-09-10 -- A DIRECTORY THAT SERVES A DOCUMENT CANNOT BE ENUMERATED. On
  gatekeeper.dec.com, `.../SRC/research-reports/SRC-021-html/` returns the research paper, not a
  listing. parse_listing() read a paper as an index, took the figures it links, and could not see
  evolve.css, footnode.html, the backup files ending in `~`, or a subdirectory named `icons.gif/`.
  The paper itself was parsed and DISCARDED, because the crawler's page test matches URLs ending
  in .html and a directory URL ends in "/" -- twelve DEC SRC papers were held as illustrations
  with no text. (That test was HTML_PAGE then and is looks_like_a_document now; the limit is the
  same, and it is the trailing slash that causes it, not the extension set.)

    THIS IS A LIMIT, NOT A DEFECT. Nothing links to those files, so no crawl can find them. What
    closed it was Index-byname, the source's OWN listing. Two figures, kept apart because they
    measure different things: the FIRST complete run held 8 674 files and the finished archive
    holds 9 183, so four runs added 509. Against the manifest, /pub/DEC/ alone was 473 short
    after run 1 and still 271 short after two more. Every one of those answered 200 at the
    source -- nothing had failed, the files were never asked for. manifest-fetch.py exists for this, and it is why bitsavers' .tar.txt and bullfreeware's
    .sfv are kept rather than treated as clutter.  [2026-09-10]

  - A "permanent 404" count is an UPPER BOUND on dead links, not a measurement of them.
    filibeto-aix-lib's third 404 was a request for `rel/5.2/kdb.htm'))` -- link extraction
    took surrounding punctuation out of a JavaScript href. Harmless per request, but anything
    reading those counts as site rot is reading them wrong.  [2026-09-04]

  - rwth-aachen-ftp and ps-2.kev009.com overlap by 6.11 GB. Measured by SHA-256, not assumed:
    8 616 of the 9 020 files in rwth's ps2supersite mirror (96 %) are byte-identical to
    something in kev009. The other 404 files, 245.7 MB, exist nowhere else here -- IBM PC BBS
    material kev009's copy lacks. NOTHING IS TO BE DELETED on the strength of that 96 %:
    finding duplicates is a reporting job, and 404 unique files would go with them.
  SETTLED 2026-09-04 -- gsi-collection's 3 695 permanent 404s. Neither a crawler defect nor a
  gap in the copy: 3 538 of the 3 653 DISTINCT 404 URLs (97 %) are one subtree, NCDWARE/
  ftp.ncd.com/. GSI once mirrored NCD's X-terminal FTP archive and DELETED THE FILES WHILE
  LEAVING THE CATALOGUE -- its index.html pages, ls-lR/ls-ogR listings and fonts.dir files are
  still served and name thousands of files that no longer exist. The crawler followed them and
  correctly got 404 on each. The rest of the site is healthy: of 111 links on the landing page,
  72 are 200, 30 need auth, 1 is 403 and only 3 are dead. What we hold is the CATALOGUE of
  NCD's archive, which is worth having -- the Internet Archive has 118 URLs for ftp.ncd.com,
  almost all corporate about-pages, and exactly ONE under /pub/*. Full account in that
  archive's PROVENANCE.md.
  SETTLED 2026-09-04 -- the trailing-dot blind spot, which was two defects, not one.
  iter_tree() built its relative path with os.path.relpath(), which NORMALISES: `TALK.` became
  `TALK`, so bitsavers' 21 paper-tape and RSTS/E files would have entered the checksum index
  under names that do not exist on disk. And scan_tree() called getsize() WITHOUT long_path()
  and swallowed the OSError, so those same 21 were absent from every marker and from the figure
  --verify compares a tree against -- meaning a tree could lose files and report UNCHANGED
  forever. Both fixed; the bitsavers index went from 176 012 to 176 033 entries, and those 21
  files are covered by a checksum for the first time. tuhs's dangling symlink
  (Documentation/TUHS/Old/mirroring.html) now gets its own loud UNREADABLE line each run
  instead of vanishing.

  RETRACTED 2026-09-05 -- "an index write that fails still exits 0". mirror.py DOES exit 1:
  hash_tree's `finally: checkpoint()` lets the PermissionError propagate, and Python returns 1.
  What returned 0 was the SHELL PIPELINE the run was invoked through -- `python mirror.py ... |
  tail -6` reports tail's status, not Python's. Verified both ways; `set -o pipefail` gives 1.

  The bug was in the invocation, and it was attributed to the tool without checking. Worth
  keeping as a defect class of its own: PIPING A COMMAND THROUGH `tail` OR `head` DISCARDS ITS
  EXIT CODE, so a run that died looks exactly like a run that succeeded -- the same shape as
  every other failure recorded here, arriving this time through the shell rather than the code.
  It also cost two hours earlier: `| tail -20` buffers everything until the process ends, so
  three background fetches wrote nothing to their logs and could not be monitored at all.

  SETTLED 2026-09-04 -- damage-rt/BSD44-RT-LITE/src.tar.gz. The question was how much of its
  124 MB duplicates 4.4BSD-Lite already in `tuhs`. Answer: NONE. tuhs/Distributions/UCB carries
  4.4BSD-ALPHA, 4.3BSD-Reno, 4.3BSD-Tahoe and Net2 -- not Lite. Listed (not extracted): 27 816
  files, 311.1 MB uncompressed, of which src/sys/rt/ is 1 001 files whose kernel configs are
  named AUSTIN_* after IBM Austin. Both halves are unique here. The note is kept rather than
  deleted because the answer inverted the question, which is the useful part.

===============================================================================================
DO NOT TIDY THE MIRROR TREE
===============================================================================================

Migrated from the mirror tree's own README.md on 2026-09-04, so the rules live with the tool
that enforces them rather than in a file inside the tree they protect. Every one has cost
something at least once.

  * NOTHING IS EVER DELETED AS A DUPLICATE -- not against another mirror, not against itself.
    `everything/` repeating 97 % of `RPMS/` is not waste; it is what the source served, and
    under which path. Two identical files at two paths are two answers.
    Measured example, 2026-09-04: 96 % of rwth-aachen-ftp's ps2supersite mirror (8 616 files,
    6.11 GB) is byte-identical to ps-2.kev009.com. Deleting on that basis would also have taken
    404 files, 245.7 MB, that exist nowhere else here.

  * NOTHING IS SORTED, RENAMED, OR GIVEN A NORMALISED EXTENSION. The names belong to the source
    server. The one exception on record is 162 files a fetcher had itself misnamed `index.html`
    while they were WebP -- correcting our own error, not the source's.

  * DO NOT DELETE A COMPLETION MARKER to make --fresh work. It refuses on purpose: hundreds of
    gigabytes behind it took days and may no longer be re-fetchable.

  * .mirror-complete, .mirror-index.csv, .sha256sum and PROVENANCE.md are OURS, not content, and
    are excluded from the counts -- but only AT THE ARCHIVE ROOT. oss4aix.org ships 2 071 real
    SHA256SUMS files of its own, one per package directory.

  * A copy that also exists OUTSIDE the mirrors may go. A copy inside one may not.

  * The mirror tree is third-party material copied verbatim. Nothing in it was extracted,
    disassembled or derived; each archive carries whatever terms its source carries.

===============================================================================================
COVERAGE -- what the collection is for, and where the holes are
===============================================================================================

THE PURPOSE, stated so that scope decisions have something to appeal to: hold what is needed to
UNDERSTAND AND IMPROVE emulation of this hardware -- QEMU above all, and the operating systems
that exercise it. AIX first, then the IBM systems around it. Something belongs here if a person
fixing a QEMU defect, or bringing up an old system, would want it and could not easily get it.

EXPLICITLY NOT WANTED, however good: operating systems that are abundantly available and in no
danger. NetBSD and FreeBSD are the standing example -- bits/NetBSD/ is 606.8 GB and excluded by
name in RSYNC["bitsavers"]["filter"]. Absence of such material here is a decision, not a gap.

THE CATEGORY MOST AT RISK is commercial AIX software. Open-source AIX builds have three
independent sources here (oss4aix, bullfreeware, aixtools) and a living community. Commercial
software has none of that: it was sold, the vendors are gone or have forgotten it, and nobody is
allowed to redistribute it, so it survives only where a private copy happens to sit. When a
source of it appears, treat it as the perishable one.

-----------------------------------------------------------------------------------------------
1. AIX OPERATING SYSTEM MEDIA
-----------------------------------------------------------------------------------------------
HELD   PS/2 lineage    1.2.1, 1.3.0                       fsck-aix-media; 1.3 diskettes held privately
       RT lineage      2.1.1, 2.2.1                       fsck-aix-media, damage-rt
       RS/6000         3.2.0, 3.2.5, 4.1.3, 4.1.5, 4.2.1, 4.3.2, 4.3.3, 5.1, 5.2, 5.3,
                       6.1, 7.1, 7.2, 7.3
       Apple NS        4.1.4                              fsck-aix-media
MISSING -- named because a gap nobody has written down is a gap nobody will fill:
       * AIX 3.1  -- the FIRST RS/6000 release (1990). Not held in any form. The most
         conspicuous hole in the sequence.
       * AIX 3.2.1 - 3.2.4, the interim 3.2 levels
       * AIX 4.1.0, 4.1.1, 4.1.2, and 4.1.4 for RS/6000 (only the Apple NS variant is held)
       * AIX 4.2.0, 4.3.0, 4.3.1
       * AIX 1.1 and 1.2.0 (PS/2), AIX 2.0 / 2.1.0 (RT)
       * AIX/ESA -- the System/370 product, a different lineage entirely. Never sought.
UNKNOWN: whether any of the above survive anywhere. None has been searched for by name.

-----------------------------------------------------------------------------------------------
2. COMMERCIAL AIX SOFTWARE  -- the perishable category
-----------------------------------------------------------------------------------------------
HELD   XL C/C++ for AIX                                   held privately
       PowerSC 2.1, PowerVC 2.1.1, PowerVM WPAR Manager, Systems Director 6.2   same
       VisualAge C++ 4.0.2 + 5.0.2, IBM COBOL 2.0.0       fsck-aix-apps
       Mathematica 2.2 / 3.0.1.1 / 5.2, Maple 6.0, IMSL   fsck-aix-apps
       SoftWindows 1.0 + 2.0 (x86 under AIX)              fsck-aix-apps
       Corel WordPerfect 5.2-7.0 UNIX, CorelDraw 3.5      fsck-aix-apps
       Netscape Navigator 1.0, Communicator 4.0.6         fsck-aix-apps
       Pro/Engineer, Cadence, Altera, Modeltech, MentalRay, Sybase 11.9.2, TecPlot
MISSING or unsearched:
       * XL Fortran for AIX, in any version
       * IBM C Set++ / C for AIX 3.x and 4.x era compilers
       * DB2 for AIX, Informix, Oracle for AIX
       * CATIA, and the rest of the CAD that ran on RS/6000 workstations
       * Tivoli, ADSM/TSM
ONE SOURCE ONLY. Everything in fsck-aix-apps comes from a single host. There is no second copy
of any of it in this collection, and no other source has been looked for.

-----------------------------------------------------------------------------------------------
3. AIX OPEN-SOURCE SOFTWARE  -- well covered, three independent sources
-----------------------------------------------------------------------------------------------
HELD   oss4aix.org (Perzl) 208 GB, bull-rpms + bull-srpms 65 GB, bullfreeware's pre-RPM .exe
       filesets and GNOME 2.6 for AIX 5.1, aixtools installp/BFF filesets, IBM's AIX Toolbox
       inside ibm-aix, aix-orphans (Firefox 1.0.8 for 4.3.3, OpenSSH AIX patches)
No known gap. This is the one category with redundancy.

-----------------------------------------------------------------------------------------------
4. DOCUMENTATION
-----------------------------------------------------------------------------------------------
HELD   IBM TechLibrary CDs V3R2 (1999) + V3R10 (2001)     infania-tl2, infania-tl1
       AIX 5.2 / 5.3 / 6.1 manual sets, 28 redbooks        filibeto-aix-lib
       man pages: AIX PS/2 1.2.1, AIX RT 2.2.1, AOS 4.3    typewritten
       BSD-to-AIX admin, porting BSD to AIX (CSRI)         csri-toronto
       one French engineer's DokuWiki, 288 AIX pages       iffly-wiki
       a private documentation collection, held outside this mirror
MISSING or thin:
       * Redbooks in bulk. 28 held against several hundred published for AIX and RS/6000.
       * InfoExplorer databases for AIX 3.x and 4.x -- the pre-HTML documentation format
       * hardware service guides per machine type: 7006, 7007, 7008, 7009, 7011, 7012, 7013,
         7015, 7017, 7024, 7025, 7026, 7043, 7044, 7046, 7248 -- coverage is partial and has
         never been enumerated against the list of types that exist
       * PSSP, LoadLeveler, HACMP documentation (SP2/SP3 cluster era)

-----------------------------------------------------------------------------------------------
5. HARDWARE DOCUMENTATION AND SPECIFICATIONS  -- what emulation is written against
-----------------------------------------------------------------------------------------------
HELD   PReP/CHRP reference boards: Longtrail and Harley schematics with BOMs, Zapatos,
       27-82660 host bridge with IBIS models                ibm-rs6000-support
       IEEE-1275 Open Firmware bindings as PRIMARY documents: chrpv17a, chrpv15d, ppc-2_1,
       isav04d, isa-pic-1_1d, plus working drafts            ibm-rs6000-support/OpenFirmware/
       CPC710 PCI/memory bridge datasheet                    tvsat-cpc710
       SGS-Thomson M48T59 / M48T08 / M48T58 TIMEKEEPER       held privately
       board-level RS/6000 detail                            ardent-tool
       the general computing documentation archive           bitsavers, vtda
MISSING or unverified:
       * PAPR / LoPAPR in an authoritative copy -- the QEMU work cites it constantly and it is
         not established that a copy is held
       * PowerPC Architecture Book I/II/III for the relevant generations
       * POWER3, POWER4, RS64 user's manuals
       * datasheets for the other bridge and I/O chips in these machines

-----------------------------------------------------------------------------------------------
6. FIRMWARE, ROMS, MICROCODE  -- vanishes first, because it lived on support portals
-----------------------------------------------------------------------------------------------
HELD   40p OpenFirmware ROMs, serial + VGA                  held privately
       HMC firmware, ~20 GB                                 ibm-rs6000-support/hmc/
       AIX 5.3 Machine Code Update Files and Discovery Tool  held privately
MISSING:
       * system firmware / SMS for most machine types
       * adapter microcode, service processor images
       * diagnostic CDs
This category has no systematic coverage at all -- what is here arrived incidentally.

-----------------------------------------------------------------------------------------------
7. EMULATION AND DEVELOPMENT KNOWLEDGE  -- the reason for the rest
-----------------------------------------------------------------------------------------------
HELD   3 GitHub repos + a gist on AIX under QEMU, WITH HISTORY   aix-qemu-git
       an AIX 7.2-on-POWER8 walkthrough, IA has NO snapshot       techsysadm
       level-3 service procedures, 7043-270 / 7044-170 / 7044-270 misterhayden
       this project's own campaign: 22 patches, 14 defects, the guest-free test suite, and the
       write-up including the refuted theories   -- in the workspace repository, not here
MISSING:
       * QEMU's own history and mailing list as they concern ppc/spapr
       * other emulator projects' PowerPC work

-----------------------------------------------------------------------------------------------
8. THE IBM SYSTEMS AROUND AIX  -- in scope, and I got this wrong once
-----------------------------------------------------------------------------------------------
A private IBM collection is held alongside this mirror, and it is not confined to AIX: it
holds OS/2, iSeries Client Access and a partial zOS ADCD. Its scope is "everything
IBM-related", which is the fact that matters here.

On 2026-09-04 I told the owner that fsck.technology's OS/2, OS/390, OS/400, PC-DOS, 3174 and
4690 trees were "not this collection's subject" and declined to measure them. That was wrong,
and it was the kind of wrong that quietly loses material: a scope claim made from memory instead
of from the collection's own README. Those trees were measured afterwards -- see DEFERRED.

The boundary that DOES hold is minuszerodegrees.net's: IBM PC/XT/AT hardware documentation, with
zero AIX, RS/6000, PowerPC, Micro Channel or PS/2 content. That was measured, not assumed.

===============================================================================================
WHAT KEEPS GOING WRONG -- read this before trusting a "complete" run
===============================================================================================

A SAFEGUARD IS CODE, AND UNTESTED CODE BREAKS THINGS -- INCLUDING THE THING IT GUARDS.
2026-09-06: a free-space floor was added to download() so an unattended overnight run could not
fill the volume, and it was put straight into that run without a test. It called disk_usage() on
os.path.dirname(dest) -- a directory download() CREATES LATER. Every file whose parent did not
yet exist raised FileNotFoundError [WinError 3] before one byte was requested, and the fetch
ended `INCOMPLETE: 20719 failures` in seconds. The guard against losing the archive was the only
thing that lost it.
  Two rules follow. A check may only touch a path CERTAIN to exist -- ROOT, not the destination.
  And a guard must never be able to fail the operation it guards: if the check itself throws, say
  so once and continue unguarded, because an unguarded fetch is recoverable and a dead one is
  work thrown away. Both are now in the code, with a test that reproduces the exact failure.

CLEAN TERMINATION IS NOT EVIDENCE OF COMPLETENESS. This is the defect class that has cost the
most here, and it has never once announced itself. On 2026-09-03 alone:
  - This tool crawled a Blogger site, found 0 files, and WROTE A COMPLETION MARKER.
  - This tool fetched 6 523 of infania-tl1's files and reported "0 failed, 0 unreadable
    listings". The re-fetch got 17 875 -- manuals/ went from 44 files to 13 374. Cause:
    is_child_link dropped '..', and that CD navigates upward-then-sideways. See the note there.
  - A survey crawler reported 2 812 files with a cleanly exhausted queue; its navigation
    filter had missed the master index, whose filename contains neither "toc" nor "nav".
    Corrected, it found 21 059.
Every one of those runs reported success. What caught each was EXTERNAL -- an independent
count of what should have been there. The lesson is not "check the exit code"; it is that a
mirror cannot validate its own completeness, so the source has to be measured separately.

AN EDIT SCRIPT THAT REWRITES EVERY LINE HAS DESTROYED THE EVIDENCE OF WHAT IT CHANGED.
2026-09-20: the drivers/ selection was inverted by a script that read this file and wrote it back
with `open(p, "w", encoding="utf-8")`. Forty-five lines were meant to change. All 6 906 did --
Python's text mode translates "\n" to "\r\n" on Windows, and this file is LF. `diff` answered
with one hunk covering the whole file, and the real change was invisible inside it. The same
script had done it to an archive's PROVENANCE.md, where every other one in the collection is LF.
  Nothing was corrupted and no test failed, which is the point: the file still parsed, the tests
  still passed, and only a diff against a backup showed it. Had that diff not been asked for, the
  commit would have read as a rewrite of the whole file.
  THE RULE: a script that edits a file in place reads and writes it in BINARY, or passes
  newline="" -- and it diffs its own output before the work is called done. A backup is not
  deleted on the strength of "the tests pass"; it is deleted after a diff that accounts for every
  removed line, and after each piece of removed data has been located somewhere else by name.

A FILENAME DIFF IS NOT A CONTENT DIFF. Comparing fsck.technology by filename said 59 GB was
new; comparing by RELEASE said 19.56 GB, and the release comparison was right. Uploaders
rename, so names differ where content does not.

A DIGEST-SET COUNT IS NOT A FILE COUNT. ps-2.kev009.com has 94 899 files and 87 117 distinct
SHA-256 values -- 7 782 internal duplicates, normal for a mirror-of-mirrors.

MEASURE THE THING, NOT A PROXY FOR IT. Apache autoindex sizes are rounded (apr_strfsize: exact
below 973 B, then 0.1K, then 1K granularity) -- usable as a bound, never as a measurement.
Internet Archive `length` is the compressed WARC record size and is not a file size at all:
live PDFs ran 1.33x their IA-stored size in aggregate, spread from 0.43x to 2.18x per file.

THE SAME TREE CAN BE FETCHED TWICE UNDER TWO NAMES. On 2026-09-03 and again on 2026-09-04,
https://public.dhe.ibm.com/rs6000/ was mirrored as `ibm-rs6000-support` and as `dhe-rs6000`:
1 619 files and 27 116 134 440 bytes each, identical URL, a day apart. A policy question was
raised, put to the owner and decided -- about a tree that was already on disk. Nothing noticed,
because nothing looked. main() now refuses to start when two ARCHIVES entries share a source URL.

A CASE-INSENSITIVE PATH COMPARISON IS NOT SAFE HERE. Verifying that duplicate took three attempts.
A 12-file sample said identical and had missed everything interesting. A full manifest comparison
said 8 files differed -- it had lowercased the paths, and lscftp/micro/ holds EIGHT PAIRS of names
differing only in case (7026H50F.BIN beside 7026h50f.bin), genuinely distinct files on a directory
carrying the NTFS case-sensitive flag. Lowercasing compared one file's digest against the other's.
A byte diff of two "differing" files showed zero differing bytes, which is what exposed it. Only
the case-sensitive comparison was right: 1 619 = 1 619, zero mismatches.

A .SUSPECT IS FINAL ONLY WHEN THE *BEST* CAPTURE IS SHORT. wayback-salvage.py sets a file aside
when the bytes received are shorter than the capture claimed, and its own docstring calls that "a
COMPLETED evaluation, not an outstanding item" -- correct, but only for a URL with ONE capture. It
takes one capture per URL; when that one is truncated it never asks whether another is whole.

This collection recorded 73 such files as unrecoverable, in markers, in PROVENANCE files and in
this table, with the explanation that their stored WARC records were themselves short. For 58 of
them that was true. For 15 it was not: the truncation belonged to a particular crawl, and a later
one had the whole file. gcc-3.3.0.0.exe was held at 9 999 682 bytes with 52 966 597 available;
samba-3.0.26.0.bff at 130 767 against 96 051 200. Recovering them cost one CDX query each.

The tell was uniformity: all 15 rs6000-microcode truncations were EXACTLY 1 048 257 bytes, 1 MiB
minus 319. A ceiling, not fifteen coincidences -- and a ceiling belongs to a crawler at a moment,
so another moment may not have it. Those files came from 2000 captures; the 2001 ones are whole.

An assumption that is true of most cases and written down as true of all is the hardest kind to
notice, because every spot check confirms it.  [2026-09-05]

The check is now a tool rather than a session: suspect-reconsider.py ranks every capture of every
.suspect and installs one only when the bytes that arrive are strictly longer. Dry run by default.

AND THE CORRECTION HAD TO BE CHASED INTO THREE PLACES, which is the part worth remembering. This
entry was right from the day it was written; wayback-salvage.py's own docstring, aixtools'
completion marker and bullfreeware's PROVENANCE.md all went on stating the superseded reason for
another eight days. A master record that is right does not make the copies right -- and every one
of those copies reads as authoritative to whoever opens that file first.  [2026-09-13]

THE DECISION LISTS NOW GET RE-CHECKED TOO. LOST, FROZEN and CANDIDATES are claims about the world
outside this collection, and nothing on disk changes when one of them stops being true. A wrong
entry in LOST is worse than a missing file: the list exists to stop anyone looking again, so a
wrong one is a closed question. recheck-decisions.py probes them; robots_verdict_test.py pins the
seven robots.txt readings that have been argued about here. First full pass 2026-09-13: 52
hostnames and 27 candidate URLs, ZERO drift -- the record held everywhere.

It found seven defects all the same, every one in ITSELF, and the first is the one to remember.
FROZEN is keyed by ARCHIVE NAME, not by hostname. The first run resolved none of its nine entries,
sent not one request, and printed "none answer under either name -- the record still holds." That
sentence is indistinguishable from a real all-clear. It is the identical failure crawl-gap-audit.py
had, and the identical failure the nine COMPLETE-but-short crawls had: A CHECKER THAT READS NOTHING
AND A CHECKER THAT FINDS NOTHING PRINT THE SAME LINE. The tool now says "NOTHING WAS CHECKED. This
is not an all-clear." and counts unresolved entries as drift, because the only safe default for an
audit is to accuse itself.

The others, briefly, because each is a different way to be confidently wrong:
  - a multi-host key (`rootvg.net / aixmind.com / ppckernel.org / ...`) was cut at the first "/",
    so four of five hosts were never asked while the line looked complete;
  - `import io` was missing and a bare `except Exception` reported the NameError as "no origin in
    a marker" -- a code defect wearing the costume of a finding;
  - HTTP 522/521 is Cloudflare saying the ORIGIN is dead; counting it as alive flags a host that
    is exactly as gone as the record says;
  - a 200 is not a return: `spscicomp.org` serves a BlueHost placeholder and
    `download.aixtools.net` serves 44 bytes of Apache's "It works!", so the title AND the body
    must be read;
  - a robots verdict covers THE PATH IT WAS ASKED ABOUT -- hpux.connect.org.uk is open at its apex
    and disallows /ftp/, the entire binary tree;
  - and the notes already explained two of the three "findings" (`support.bull.com` is recorded as
    "a Salesforce login shell"), so an alarm that fires forever teaches the reader to skim.

Twice during that work "Index of /" was nearly added as a placeholder marker. An autoindex is the
single most promising thing a dead host can start serving again. A suppression list is the easiest
place in any checker to delete the finding you built it for.  [2026-09-13]

ASK WHETHER WE ALREADY HOLD IT, BEFORE ASKING WHETHER IT IS WORTH HOLDING. A candidate note is
written when a tree is FOUND, and it records what is remarkable about that tree. It does not
record what this collection acquired afterwards, so a note ages into an argument for fetching
something that is already downstairs.

Two of the three prizes named in the oldskool-drivers note turned out to be here already:

    IBM_PC_BBS             9 022 files   5.92 GB     9 021 held
    ftp.bocaresearch.com   1 239 files   0.27 GB     1 239 held

IBM_PC_BBS is spread across ps-2.kev009.com/pccbbs/ (7 090), os2bbs (426) and ardent-tool (339);
ftp.bocaresearch.com sits complete under ps-2.kev009.com/bocaresearch/. Fetching both would have
cost 6.19 GB of one volunteer's bandwidth to gain ONE file of 11 MB.

THE CHECK IS CHEAP AND SHOULD BE ROUTINE: every archive's `.sha256sum` already lists every
filename it holds -- 901 254 of them across 95 archives, read in seconds. Where the source
publishes its own catalogue, as IBM's BBS does in allfiles.txt, compare against that rather than
against a crawl.

TWO ENTRIES ABOVE BEAR ON THIS AND POINT DIFFERENT WAYS, which is why both are worth reading
before acting on an overlap figure:

  * A FILENAME DIFF IS NOT A CONTENT DIFF -- filename comparison OVERSTATES how much is new,
    because uploaders rename. That makes it the safe instrument for the question asked here:
    a high overlap is trustworthy evidence that a tree is already held, while a low overlap
    proves nothing and still needs a real comparison before anything is fetched.
  * THE SAME TREE CAN BE FETCHED TWICE UNDER TWO NAMES -- main() now refuses to start when two
    ARCHIVES entries share a source URL. That guard cannot see this case at all. Here the URLs
    are entirely different hosts, and only the CONTENT is the same; no check on sources will
    ever catch that, which is why the check has to be on names or hashes.

Both of the tools written to do this comparison were wrong on their first run, and both failed the
same way -- SILENTLY, WITH A CLEAN ZERO. One split `.sha256sum` on two spaces where the format is
`<hash> *<path>` with one, and reported 0 of 7 890 held. The other carried its own autoindex row
pattern, met the second of the two Apache styles that host serves, and reported a 1 239-file
directory as empty. Neither raised an error. Both were caught only because the number was not
believed and a handful of names were looked up by hand.

That is not a method to rely on. The second tool was rewritten to call parse_listing, which has
three matchers and twenty regression tests behind it, and the lesson is the smaller and duller
one: WHEN A TESTED PARSER EXISTS IN THIS DIRECTORY, USE IT. A survey is not a good reason to write
a fourth.  [2026-09-17]

A LOG THAT TRUNCATES THE PATH DESTROYS ITS OWN EVIDENCE. The fsck-vendors fetcher printed
failures as `FAIL %-52s`, so `CascConnect-4.0-bld37-Cogent.qpk` was recorded as
`CascConnect-4.0`. When 320 failures appeared in one directory, testing the logged names against
the server returned 404 for every one -- which looked like confirmation and was an artefact: a
truncated name 404s whatever the truth is. The question was only settled by diffing the live
listing against the tree, i.e. by a measurement taken from outside the log.

Print the whole path in a failure line, or print nothing. A log that looks complete and is not is
worse than one that is plainly partial.  [2026-09-05]

A PATH THAT ENDS IN A SPACE OR A DOT IS NOT THE PATH YOU TYPED. Windows normalises away a
trailing space or dot when it parses a path, so a directory name and that same name plus one
trailing blank are THE SAME directory to every ordinary tool -- Explorer, PowerShell, cmd, and
Python without the extended-path prefix. Only the extended-path form reaches the real name,
which is why long_path() exists and why it must never normalise.

Three consequences, each of which has already happened here:

  * A DELETE COMMAND FOR THE "OTHER ONE" HITS THE ONLY ONE. On 2026-09-04 a listing was misread
    as showing two directories, one an empty leftover; a Remove-Item was recommended for the
    name without the trailing space. There was only ever one directory, it held two
    freshly-fetched files, and the command resolved straight onto it. The files were re-fetched.
    THE RULE: never issue a deletion for a path with a trailing space or dot, in either form.
    If something there really must go, use the extended-path form, on purpose and once.

  * A COUNT CAN BE DOUBLE OR SHORT DEPENDING ON THE TOOL. os.walk() descends into such a
    directory (the OS normalises for it) and counts its files once -- but a hand-written "and
    now add the extended-path listing" on top counts them twice. Both mistakes were made within
    ten minutes of each other, in opposite directions.

  * WRITING NEEDS THE PREFIX OR THE FILE VANISHES QUIETLY. os.makedirs() without it creates the
    NORMALISED name, and the subsequent open() of the un-normalised file path then fails with
    "No such file or directory" -- which reads like a missing source file and is not one.

A FRAGMENT IS NOT A FILE. `page.html#A9D8FFBD257ryan` names a position in a document, not a
document. Left in, each becomes its own file -- 1 987 duplicates in a single run. See
strip_fragment().

AN ARCHIVE ON DISK IS NOT AN ARCHIVE IN ARCHIVES. Four -- fsck-aix-media, aix-qemu-git,
csri-toronto, tvsat-cpc710 -- were fetched by one-off scripts and never registered, so
`--verify` skipped 19.7 GB and reported success. Three more were registered but missing from
EXTERNAL, which meant a full run would have pointed the HTML crawler at hosts needing a
dedicated fetcher and, per that comment, "quietly produce a second, worse copy alongside the
good one". Found by diffing ARCHIVES against os.listdir, not by anything failing.  [2026-09-04]

===============================================================================================
WHAT THE ESTIMATES SAID, AND WHAT MEASURING SAID
===============================================================================================

Every candidate below had a written size before it had a measured one. The gap is the reason
this file insists on measurement, and the reason no figure here is an extrapolation.

  source                        estimated      measured   how measured
  infania.net TL1+TL2         300-650 MB        312 MB    32 312 files enumerated; 1 555 HEADs,
                                                          stratified sample (a bound, not a sum).
                                                          ACTUALLY FETCHED: 37 489 files, 513 MB
                                                          -- the enumeration was a lower bound,
                                                          because Options -Indexes hides any file
                                                          no page links to.
  damage.fi/slas/rt/             ~470 MB   504 033 090 B  266 HEADs, zero misses -- exact
  ftpmirror.../sites            20-60 GB    >=324 GiB     FTP LIST -R, exact per-file sizes
  public.dhe.ibm.com/rs6000/  unmeasured     25.25 GiB    662 HEADs = 99.1 % of the bytes
  minuszerodegrees.net          10-20 GB      12.42 GB    2 266 HEADs
  heha.fwh.is                    1-3 GB        59 551 B   15 files; the rest is not enumerable
  fsck.technology (new part)     19.05 GB      19.56 GB   the one estimate that held up

FOUR PREMISES WERE FALSE -- not imprecise. Each had been written down as fact.

  "infania.net returns 403 on every directory, so the tree is unreachable." Options -Indexes IS
  on, so directories WITHOUT an index page 403 -- but both TechLibrary CDs ship IBM's own HTML
  table of contents and return 200. The way in was never missing.

  "csiph.com has a `timc` subtree of 8 532 PS/2 files." It 404s over https, http and www, as do
  /pub/ /files/ /ftp/ /download/ /mirror/ /ps2/ /archive/. The Internet Archive holds seven
  captures of it and all seven are 404s. The site is an NNTP server.

  "ftpmirror's /sites is 20-60 GB." Extrapolated from ftp.leo.org -- measured at 1.79 GiB, and
  an OS/2 archive whose `unix` directory holds 12 files. The real figure is ~2.2 TB.

  "minuszerodegrees.net is worth 10-20 GB to us." Its size was never the question: across all
  7 099 enumerated paths there are ZERO files matching aix, RS/6000, 70xx, PowerPC, Micro
  Channel or any PS/2 model number.

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
# R3  Files we write into a mirror (marker, index, sums, PROVENANCE) are not content. They
#     MUST be in OWN_FILES, or every marker becomes wrong the moment the first one is written,
#     and --verify reports MISMATCH on every archive at once.  [2026-08-26]
#
#     README IS NOT ONE OF THEM, and this rule listed it until 2026-09-10. No tool here writes a
#     README into a mirror -- but a SOURCE can ship one, and AIX5-IA64 does. While README.md sat
#     in OWN_FILES that file was outside the index, outside the marker's counts and outside every
#     verify-content pass, silently. Obeying the rule as it was written re-creates the defect it
#     was meant to prevent. See the note beside OWN_FILES.  [2026-09-07]
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
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse

from common import (COMPLETE_MARKER, INDEX_FILE, MIN_FREE_BYTES, ROOT_MARKER, SUMS_FILE,
                    Backoff, Pacer, Patience, local_failure,
                    comparable_path, hash_tree, http_date, http_open, human,
                    iter_tree, local_path, long_path, looks_like_a_document,
                    looks_like_a_loop,
                    parse_listing, read_index, read_marker, resolution_base,
                    same_path_plus_slash, scan_tree, write_index,
                    write_marker as common_write_marker)

# The mirror tree: the directory that holds one subdirectory per archive. Deliberately NOT
# derived from __file__ -- see the module docstring. main() sets both from resolve_root()
# before anything reads them; a caller that skips main() (wedge_test.py) sets them itself.
ROOT = None
LOGDIR = None

# Written into a mirror directory when a run finishes with nothing outstanding. Its presence
# makes --fresh refuse, and its contents are what --verify compares the tree against.

# The checksum pair, both written into the mirror root next to COMPLETE_MARKER.
#
# INDEX_FILE is the master: path, size, mtime_ns, sha256. The size and mtime are the whole point
# of keeping our own format -- they are what lets the next run skip a file it has already hashed,
# which turns a re-run from 1.3 TB of reading into seconds. SUMS_FILE is derived from it and
# carries nothing extra; it exists because `sha256sum -c` reads it and nothing on earth reads
# the CSV.

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

# "README.md" WAS IN THIS SET AND WAS REMOVED ON 2026-09-07. It belonged here while the mirror
# tree carried a README of its own; that file was migrated into this module on 2026-09-04 and
# NOTHING HAS WRITTEN ONE SINCE. The entry then stopped protecting anything and started hiding
# something: `AIX5-IA64/README.md` is the cloned repository's own file, 6 727 bytes describing what
# its 63 packages are, and it sits at the archive root -- exactly where the `top and` guard below
# applies. So it was left out of .sha256sum, out of the marker's counts, and out of every
# verify-content pass, without a word.
#
# The guard itself is right and stays: an archive may legitimately contain a README.md deeper in
# its tree, and those were always indexed. What was wrong was assuming the ROOT one must be ours.
# Checked before removing: no tool in this directory writes a README.md into a mirror, and
# AIX5-IA64 holds the only one in all 49 archives.
#
# RE-CHECKED 2026-09-08 across all 70: still the only one. Worth re-testing rather than
# inheriting, because 21 archives were added since -- and this claim is the entire reason
# README.md is absent from OWN_FILES. A real repository README treated as ours would drop out of
# the index and the marker count without a word, which is the failure mode that produced the
# guard in the first place.

# THE BASE URL IS THE MOUNT POINT, AND IT BELONGS AT THE NATURAL ROOT OF THE TREE -- not at the
# subdirectory that happens to hold what you came for. Written down on 2026-09-26, after FIVE of
# nine candidates from one reconnaissance turned out to name a subfolder and were nearly added
# that way:
#
#   contrib.andrew.cmu.edu/~shadow/ibmrt/     -> ~shadow/      one person is tree, RT is part of it
#   vintagecomputer.net/fjkraan/comp/ibm6150/ -> /fjkraan/     one machine out of a whole museum
#   spider.seds.org/ps2/ps2.html              -> spider.seds.org/  a PAGE, not even a directory
#   iommu.com/datasheets/                     -> iommu.com/    the root is two links
#   vgamuseum.info/images/doc/                -> vgamuseum.info/   and this one was already
#                                                              mounted wrong before anyone checked
#
# WHY IT MATTERS, in three ways that each cost something different:
#   1. A subfolder mount CANNOT GROW. When the author adds a sibling directory next year it falls
#      outside the archive, and nothing reports it -- the mirror stays "complete".
#   2. THE MEASUREMENT LIES. fjkraan/comp/ibm6150/ measured 593 kB; it is one machine page in a
#      museum listing dozens. This collection has made that error before and recorded it:
#      mpoli-bbs was measured at one subdirectory and came in five times larger.
#   3. THE STORED PATH LOSES ITS CONTEXT. ibm6150/... says nothing about whose museum it is.
#
# AND THE ROOT IS THE MOUNT POINT, NOT NECESSARILY THE ENTRY. Measured the same day: ~shadow/
# reaches 0 files, because the homepage is a CV that never links the RT tree, and /fjkraan/
# reaches 18 because the museum index lives one level down. Mount at the root so the tree can
# extend, and put the entry in SEEDS so the crawler can start. Those are two different questions,
# and conflating them is exactly what produces a subfolder mount.
#
# THE EXCEPTION IS A SCOPE DECISION, and it belongs in EXCLUDE rather than in a truncated base
# URL -- so that it is visible, reversible, and cannot be mistaken for the whole site.
# fsck.technology is legitimately deep because each subtree is a separate archive by the owner is
# choice; that is not the same as an accident of where a search result pointed.

ARCHIVES = [
    ("oss4aix.org", "http://www.oss4aix.org/download/"),
    ("rwth-aachen-ftp", "http://john.ccac.rwth-aachen.de:8000/ftp/"),
    ("bull-rpms", "https://dl.power-devops.com/bull/RPMS/"),
    ("bull-srpms", "https://dl.power-devops.com/bull/SRPMS/"),
    ("ps-2.kev009.com", "https://ps-2.kev009.com/"),
    # ibm-aix -- see PROVENANCE.md in the archive.
    ("ibm-aix", "https://aix.software.ibm.com/aix/"),
    # filibeto-aix-lib -- see PROVENANCE.md in the archive.
    ("filibeto-aix-lib", "https://www.filibeto.org/unix/aix/lib/"),
    # bitsavers -- see PROVENANCE.md in the archive.
    ("bitsavers", "rsync://bitsavers.org/bitsavers/"),
    # vtda.org, assembled from five sibling rsync modules on the same daemon. A separate archive
    # from bitsavers despite the shared host -- see RSYNC[] for what is in it and why it is taken
    # whole. The URL here names the daemon; the five module URLs are in RSYNC["vtda"]["sources"].
    ("vtda", "rsync://bitsavers.org/vtda-*/"),
    # tuhs -- see PROVENANCE.md in the archive.
    ("tuhs", "rsync://rsync.mirrorservice.org/tuhs.org/"),
    # The Ardent Tool of Capitalism. Board-level RS/6000 detail no IBM manual here carries:
    # planar specifications for the 7007-7013, CPU cards for POWER1/POWER2/P2SC, adapter pages.
    # A hand-written site, so HTML_CRAWL -- see there.
    ("ardent-tool", "https://ardent-tool.com/"),
    # Peter H. Wendt's one-man PS/2 site, added 2026-09-26. MEASURED FIRST: 1 467 files,
    # 170.43 MB, of which 104.91 MB was read off listings and 65.52 MB measured by HEAD; 11 files
    # returned no size, so that figure is a floor. His own page-image scans -- deliberately not
    # OCR'd -- of the PS/2 Hardware Interface Technical Reference, including the Common Technical
    # October-1990 release WITH the July-1992 extended DMA Controller Architecture section, the
    # BIOS/ABIOS TR, the VGA/XGA/XGA-2 TRM, the 557-page PS/2 Server HMM and the 3363 WORM TRM.
    # Frozen since 2003-2007 on shared hosting. HTTP ONLY: the TLS certificate is *.kasserver.com
    # and does not match, so https would fail the chain rather than merely warn. Hand-written
    # HTML 4.01, so HTML_CRAWL. The ADFs here are probably redundant against ardent-tool above --
    # taken anyway, because "probably" is not a measurement and 170 MB is not worth the argument.
    ("mcamafia", "http://www.mcamafia.de/"),
    # VGA Legacy MKIII's documentation subtree, added 2026-09-26. A SUBTREE AND NOT THE SITE: the
    # rest of vgamuseum.info is card photography, and this directory is the documentation.
    # MEASURED FIRST: 2 261 files, 3.44 GB, every byte by HEAD because the listings carry no size
    # column. That is twenty times what the candidate note guessed, and the note had said
    # "unknown" rather than guessing -- which is why it was measured before being added.
    # Holds the answer to a question this collection had open: IBM GXT2000P/3000P/4000P/4500P/
    # 6500P/800P specifications and installation guides, plus the RS/6000 adapter-and-cable books
    # SA38-0516 and SA38-0533. Also 30 TechSource Raptor/GFX spec sheets for Sun graphics that
    # appear to be archived nowhere else, DEC ZLXp and TGA2, and the INMOS Graphics Databook.
    # A GENERATED autoindex (<ul><li>, no sizes), so deliberately NOT in HTML_CRAWL.
    # robots.txt is stock Joomla and excludes only CMS paths; /images/ is not among them.
    ("vgamuseum-doc", "https://www.vgamuseum.info/images/doc/"),

    # ---------------------------------------------------- added 2026-09-26, all measured first
    # Every one of these was measured at its ROOT before being written down, and four of the six
    # needed a SEED because the root does not link downwards. See the header of this list.
    #
    # Ian Mapleson's SGI/FutureTech centre. MEASURED 728 files, 497.38 MB -- the candidate note
    # said "unknown", and the first two attempts measured ZERO because the tool could not take a
    # page as a root. The root is a 71-byte meta-refresh stub, so the entry is sgi.html; see
    # SEEDS. THE RISK IS DEMONSTRATED, not guessed: the page advertises three mirrors of itself
    # and futuretech.blinkenlights.nl, the European one, has no DNS record at all any more.
    ("sgidepot", "http://www.sgidepot.co.uk/"),
    # A one-man workstation site that, by its own front page, is served from a SPARC IPX with
    # 64 MB of RAM and a 500 MB disk. MEASURED 289 files, 23.24 MB -- the candidate note guessed
    # "a few hundred MB" and was an order of magnitude out. Sun 3 through SS10, SGI Iris through
    # Indy, NeXT and DEC Multia: his own teardown photography and hardware notes, plus hosted
    # vendor PDFs. ONE CONNECTION AND A TWO-SECOND PACE -- see WORKERS_BY_ARCHIVE and
    # MIN_INTERVAL. A 1991 workstation is not a host to open eight sockets on.
    ("obsolyte", "http://www.obsolyte.com/"),
    # Fred Jan Kraan's guest tree on Bill Degnan's site. MEASURED AT THE ROOT: 243 files,
    # 30.17 MB. The candidate named .../comp/ibm6150/, which measures 22 files and 593 kB --
    # ONE MACHINE OUT OF A MUSEUM, and a factor of 51 in bytes. That near-miss is why the header
    # of this list now says what a base URL is for. His own site electrickery.nl forbids PDFs in
    # robots.txt; this host serves none, and the guest copy is the one taken.
    ("fjkraan", "http://www.vintagecomputer.net/fjkraan/"),
    # Derrick Brashear's IBM RT PC page on a CMU contrib server still answering on Apache/2.2.16.
    # MEASURED 32 files, 1.58 MB. The root is a CV that does not link the RT tree at all -- it
    # measures ZERO from there -- so the entry is in SEEDS. The full Mark Whetzel RT FAQ set,
    # kept because, in his own words, they "started to disappear from FTP sites".
    ("cmu-shadow", "http://www.contrib.andrew.cmu.edu/~shadow/"),
    # Manufacturer datasheets, ~75 folders, nearly every one frozen at January or February 2008.
    # MEASURED 2 939 files, 2.26 GB, and that is a floor: 535 size lookups failed. The first
    # measurement said 1.68 GB and was cut off at a page cap -- the number here is the one taken
    # without a cap. robots.txt carries NO User-agent or Disallow line at all, only Cloudflare
    # content-signals boilerplate reserving AI-TRAINING rights, which is not what this is.
    ("chipdb", "https://datasheets.chipdb.org/"),
    # Component datasheets, actively curated -- scsi/qlogic was touched on 2026-09-23. NOT
    # anonymous, which the reconnaissance had assumed: the root's two links are "Datasheets" and
    # a Blog pointing at www.kev009.com, so this is Kevin Bowling, the same person as
    # ps-2.kev009.com which this collection already holds. The overlap is in KIND, not content:
    # ps-2 carries 1 062 datasheet paths but they are TTL and logic parts under ohlandl/, while
    # this holds CPU manuals -- 604 ESP, MPC601UM, PowerPC-AS Books 1-3, PowerISA v3.1C.
    # mirrors/ IS EXCLUDED, 78.8 GB of it: those are other people's archives, and two of them
    # (chipdb, vgamuseum) are being taken at their origin in this same batch. Taking somebody's
    # mirror instead of the origin is how you inherit their gaps. ~5.0 GB remains.
    ("iommu", "http://iommu.com/"),
    # Hartmut Frommert's own homepage on the Students for the Exploration and Development of
    # Space volunteer server. MEASURED AT THE ROOT: 1 310 files, 51.32 MB, and that is a floor --
    # 276 pages lay beyond the page cap.
    #
    # THE WHOLE ROOT, AND THE SCOPE WAS ARGUED RATHER THAN ASSUMED. What this collection came
    # for is 24 files and about 1 MB: his PS/2 and OS/2 pages, which keep LOCAL COPIES of
    # documents whose originals died -- the withdrawn Personal System Reference 1992-1995, the
    # PS/2 Hardware Maintenance Manual of MAY 1995 (S52G-9971-02, where ardent-tool holds the
    # OCTOBER 1994 edition), and 9577i/9577s parts lists from IBM Germany, IBM Canada and IBM
    # Direct USA snapshotted 05/05/97. The other 98 % is astronomy: the Messier catalogue work,
    # telescope building, Mars.
    #
    # Taking only /ps2/ and /os2/ would be exactly the subfolder mount the header of this list
    # now forbids, and an EXCLUDE naming his astronomy sections would rot the day he adds one.
    # So the root is taken whole. It is the first content here that is not about computers, and
    # that is a deliberate 50 MB rather than an accident.
    #
    # 2.5 s AND TWO CONNECTIONS. The site carries a notice about spiders that go "way too fast"
    # and says access may be blocked -- and this collection was blocked by vgamuseum.info the
    # same day for exactly that. A stated request is cheaper to honour than a block is to undo.
    ("seds-frommert", "https://spider.seds.org/"),
    # Added 2026-09-27 AT ITS OWN ORIGIN, not through iommu.com's copy of it -- a mirror of a
    # mirror inherits the gaps the middle party had on the day they copied, and this one is
    # alive: 94.19.50.86, HTTP 200, no robots.txt at all (404).
    #
    # MEASURED FIRST AND THAT IS WHY IT IS FENCED. The measurement ran for 318.7 minutes over
    # 20 000 pages and reported **137 098 files, 1.83 TB** -- and stopped there as a FLOOR, with
    # 2 968 pages still beyond the cap and 2 730 size lookups failed. The true figure is larger.
    #
    # THAT IS NEARLY HALF THIS ENTIRE COLLECTION, which is 4.01 TB, and the volume holding it
    # had 175 GB free. Three interim readings were taken while the measurement ran -- 106 GB,
    # then 425 GB, then 1.83 TB -- and each looked like an answer at the time. A measurement
    # that is still queueing pages is not a size; it is a lower bound that has not finished
    # falling upwards.
    #
    # So the archive is mounted whole -- the root is the root, and the tree can grow into it --
    # and everything except one branch is excluded.
    #
    # WHAT IS TAKEN TODAY: Hardware Info/Manuals Archive/, which holds exactly one directory,
    # Siemens MX300. THE EXCLUSIONS ARE THE MECHANISM because EXCLUDE can only subtract: to fetch
    # one branch, every sibling at every level above it is named. Eight at the top, three inside
    # Hardware Info, and none below -- Manuals Archive holds nothing else.
    #
    # TO WIDEN IT, delete a line. That is the whole procedure, and it is why the archive is
    # mounted at the root rather than at the Siemens directory: a subfolder mount cannot grow,
    # and the header of this list says what that costs.
    ("retro-digitalvintage", "https://retro.digitalvintage.ru/"),
    # Konstantin Belousov's x86 documentation collection, added 2026-09-27. MEASURED FIRST,
    # twice: 14.75 GB over 21 914 files, the second run without a page cap after the first hit
    # one at 4 000 pages. The high file count is ARM's XML ISA releases, unpacked -- thousands of
    # small HTML pages per release; the bytes are what matter for storage.
    #
    # /x86docs/ IS THE ROOT HERE, AND THAT IS NOT A SUBFOLDER MOUNT. The header of this list
    # argues for mounting at the natural root of the tree, and this is it: the operator himself
    # publishes exactly this subtree as a unit, as the rsync module rsync://anon@kib.kiev.ua/
    # x86docs. The host root above it is his personal page plus FreeBSD work, and robots.txt
    # disallows /cgi-bin/, /git/, /viewvc/, /poudriere/ and /speedtest/ -- everything there that
    # is not this. Mounting the host would add a homepage and nothing else.
    #
    # ALREADY HELD IN PART, AND TAKEN ANYWAY: iommu.com mirrors 8.07 GB of it in 1 401 files,
    # which is most of the bytes and a fifteenth of the files -- Intel/ and POWER/ only, and
    # POWER/ flat where the origin has ABI/, BOOKS/ and ISA/ with 21 files the copy lacks. The
    # ~8 GB overlap is deliberate and both live in the same b2-pack unit, so a solid block
    # collapses it rather than paying twice.
    #
    # THE OS2MUSEUM QUESTION, because the page states its own provenance: "Historic collection
    # of x86 SDMs initially created by Michal Necasek (www.os2museum.com)", and os2museum.com is
    # in DO_NOT_FETCH. That refusal is NOT about these documents -- it reads `Crawl-delay: 45`
    # and `Disallow: /files/`, which is server load and a closed download area. Belousov
    # republishes under his own name, with attribution, a link back, and an rsync invitation.
    # robots.txt here allows /x86docs/ outright.
    #
    # FULL SPEED, no MIN_INTERVAL: a public rsync module is an invitation to bulk transfer, and
    # nothing on the host asks for restraint.
    ("kib-x86docs", "https://kib.kiev.ua/x86docs/"),
    # GSI Darmstadt's vintage collection. Its IBM branch already supplied two RS/6000 adapter
    # books; the directory index is 403, so the pages are the only way in. HTML_CRAWL.
    ("gsi-collection", "https://web-docs.gsi.de/~kraemer/COLLECTION/"),
    # aixtools -- see PROVENANCE.md in the archive.
    ("aixtools", "http://download.aixtools.net/"),
    # perzl-wiki -- see PROVENANCE.md in the archive.
    ("perzl-wiki", "http://v14700.1blu.de/aix/index.php"),
    # bullfreeware -- see PROVENANCE.md in the archive.
    ("bullfreeware", "http://www.bullfreeware.com/"),
    # aix-orphans -- see PROVENANCE.md in the archive.
    ("aix-orphans", "http://linkitup.de/"),
    # ibm-rs6000-support -- see PROVENANCE.md in the archive.
    ("ibm-rs6000-support", "https://public.dhe.ibm.com/rs6000/"),
    # typewritten -- see PROVENANCE.md in the archive.
    ("typewritten", "https://typewritten.org/Manual/IBM/"),
    # iffly-wiki -- see PROVENANCE.md in the archive.
    ("iffly-wiki", "http://emmanuel.iffly.free.fr/doku.php"),
    # misterhayden -- see PROVENANCE.md in the archive.
    ("misterhayden", "https://misterhayden.com/Stevens/"),
    # techsysadm -- see PROVENANCE.md in the archive.
    ("techsysadm", "https://techsysadm.blogspot.com/"),
    # infania-tl1 -- see PROVENANCE.md in the archive.
    ("infania-tl1", "http://infania.net/misc/rs6000-tl1/"),
    ("infania-tl2", "http://infania.net/misc/rs6000-tl2/"),
    # damage-rt -- see PROVENANCE.md in the archive.
    ("damage-rt", "http://damage.fi/slas/rt/"),
    # csiph-gallery -- see PROVENANCE.md in the archive.
    ("csiph-gallery", "https://csiph.com/gallery/albums/"),
    # fsck-aix-media -- see PROVENANCE.md in the archive.
    ("fsck-aix-media", "https://fsck.technology/software/IBM/AIX%20Install%20Media/"),
    # fsck-aix-apps -- see PROVENANCE.md in the archive.
    ("fsck-aix-apps", "https://fsck.technology/software/IBM/AIX%20Applications/"),
    # fsck-ibm-other -- see PROVENANCE.md in the archive.
    ("fsck-ibm-other", "https://fsck.technology/software/IBM/"),
    # fsck-vendors -- see PROVENANCE.md in the archive.
    ("fsck-vendors", "https://fsck.technology/software/"),
    # rs6000-microcode -- see PROVENANCE.md in the archive.
    ("rs6000-microcode", "http://www.rs6000.ibm.com/support/micro/"),
    # aixpdslib -- see PROVENANCE.md in the archive.
    ("aixpdslib", "http://aixpdslib.seas.ucla.edu/"),
    # hp-labs-linux-salvage -- see PROVENANCE.md in the archive.
    ("hp-labs-linux-salvage", "http://www.hpl.hp.com/research/linux/"),
    # penguinppc -- see PROVENANCE.md in the archive.
    ("penguinppc", "http://penguinppc.org/"),
    # circle4 -- see PROVENANCE.md in the archive.
    ("circle4", "https://www.circle4.com/"),
    # aix-qemu-git -- see PROVENANCE.md in the archive.
    ("aix-qemu-git", "https://github.com/mjsamp/AIX-on-qemu-ppc64"),
    # csri-toronto -- see PROVENANCE.md in the archive.
    ("csri-toronto", "https://ftp.csri.toronto.edu/doc/aix/"),
    # tvsat-cpc710 -- see PROVENANCE.md in the archive.
    ("tvsat-cpc710", "http://www.tvsat.com.pl/PDF/C/CPC710_IBM.pdf"),
    # os2bbs -- see PROVENANCE.md in the archive.
    ("os2bbs", "http://ftpmirror.infania.net/sites/os2bbs.com/"),
    # ibm-openxl-docs -- see PROVENANCE.md in the archive.
    ("ibm-openxl-docs", "https://www.ibm.com/docs/en/openxl-c-and-cpp-aix"),
    # infania-solaris -- see PROVENANCE.md in the archive.
    ("infania-solaris", "http://ftpmirror.infania.net/sites/solaris/"),

    # A mirrored WEBSITE, not a directory listing -- which is why it first measured as 6 files.
    # measure-remote.py had to learn to follow HTML pages AND to honour <base href> before it
    # could see the tree at all. FLOOR: 171 files, 2.08 MB, 111 pages still queued at the cap.
    ("infania-os-history", "http://ftpmirror.infania.net/sites/os-history.de/"),
    # infania-unixos2 -- see PROVENANCE.md in the archive.
    ("infania-unixos2", "http://ftpmirror.infania.net/sites/unixos2.org/"),
    # ibm-redbooks -- see PROVENANCE.md in the archive.
    ("ibm-redbooks", "https://www.redbooks.ibm.com/"),
    # agilent-ftp-2009 -- see PROVENANCE.md in the archive.
    ("agilent-ftp-2009", "ftp://ftp.agilent.com/pub/callpub/"),
    # hp-alphaserver-2008 -- see PROVENANCE.md in the archive.
    ("hp-alphaserver-2008", "http://h18002.www1.hp.com/"),
    # hp-openvms-2008 -- see PROVENANCE.md in the archive.
    ("hp-openvms-2008", "http://h71000.www7.hp.com/"),
    # hp-labs-2007 -- see PROVENANCE.md in the archive.
    ("hp-labs-2007", "http://www.hpl.hp.com/"),
    # dec-ftp-2006 -- see PROVENANCE.md in the archive.
    ("dec-ftp-2006", "ftp://ftp.digital.com/pub/"),
    # next-68k-org -- see PROVENANCE.md in the archive.
    ("next-68k-org", "http://next.68k.org/"),
    # AIX5-IA64 -- see PROVENANCE.md in the archive.
    ("AIX5-IA64", "https://github.com/johnsonjh/AIX5-IA64"),
    # crashing-org -- see PROVENANCE.md in the archive.
    ("crashing-org", "http://gate.crashing.org/"),
    # dialectronics -- see PROVENANCE.md in the archive.
    ("dialectronics", "http://www.dialectronics.com/"),
    # technologists-sauer -- see PROVENANCE.md in the archive.
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
    # giga-nl-walter -- see PROVENANCE.md in the archive.
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
    # linuxfoundation-refspecs -- see PROVENANCE.md in the archive.
    ("linuxfoundation-refspecs", "https://refspecs.linuxfoundation.org/ELF/"),
    # devicetree-openfirmware -- see PROVENANCE.md in the archive.
    ("devicetree-openfirmware", "https://www.devicetree.org/open-firmware/bindings/"),
    # funet-aix -- see PROVENANCE.md in the archive.
    ("funet-aix", "https://ftp.funet.fi/pub/unix/AIX/"),
    # cryp-to-cwg -- see PROVENANCE.md in the archive.
    ("cryp-to-cwg", "https://cr.yp.to/2005-590/"),
    # sco-devspecs -- see PROVENANCE.md in the archive.
    ("sco-devspecs", "http://www.sco.com/developers/devspecs/"),
    # crashing-org-www -- see PROVENANCE.md in the archive.
    ("crashing-org-www", "http://www.crashing.org/"),
    # technologists-dellunix -- see PROVENANCE.md in the archive.
    ("technologists-dellunix", "https://technologists.com/DellUnix2.2.1/"),
    # crashing-org-kernel -- see PROVENANCE.md in the archive.
    ("crashing-org-kernel", "https://kernel.crashing.org/"),
    # sco-gabi -- see PROVENANCE.md in the archive.
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
    # REMOVED FROM THE LIVE LIST ON 2026-09-26, and the reasoning above is kept because it is
    # still the reasoning. The entry read ("funet-unix", "https://ftp.funet.fi/pub/unix/") and
    # was STILL LIVE: Q:\mirror\funet-unix was deleted on 2026-09-10 after the symlink-loop
    # incident, so there is no completion marker to stop anything, and a bare `mirror.py` run
    # with no --archive would have re-fetched the whole of /pub/unix/ -- including the BSD trees
    # that a standing decision excludes. `looks_like_a_loop()` would now prevent the 64 GB of
    # repetition; it would not prevent the 67 GB of material nobody wants.
    #
    # THE DECISION ITSELF IS NOT NEW. The retraction note further up already said this entry
    # "is not going to be run at all". That sentence lived in a comment while the tuple lived in
    # the list, which is the exact failure DO_NOT_FETCH's own header describes: a rule that
    # exists only in prose does not exist. Found by a test, not by reading -- b2-pack-test.py's
    # EveryArchiveMirrorKnowsAboutHasAUnit asked which declared archives have no unit, and this
    # was the only answer.
    #
    # NOT in DO_NOT_FETCH: that list is keyed by HOST, and `funet-aix` is held from the same
    # ftp.funet.fi. Blocking the host to stop one subtree would break the archive next to it.
    # If /pub/unix/ is ever wanted again, the scope belongs at the second level with the 74-entry
    # EXCLUDE described above -- not at this base URL.
    # ibiblio-historic-linux -- see PROVENANCE.md in the archive.
    ("ibiblio-historic-linux", "https://www.ibiblio.org/pub/historic-linux/"),
    # zx-gatekeeper-dec -- see PROVENANCE.md in the archive.
    ("zx-gatekeeper-dec", "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/"),
    # zx-hobbes-os2 -- see PROVENANCE.md in the archive.
    ("zx-hobbes-os2", "http://ftp.zx.net.nz/pub/archive/hobbes.nmsu.edu/"),
    # zx-ultrix-freeware -- see PROVENANCE.md in the archive.
    ("zx-ultrix-freeware", "http://ftp.zx.net.nz/pub/archive/ultrix-freeware/"),
    # zx-kednos-vms -- see PROVENANCE.md in the archive.
    ("zx-kednos-vms", "http://ftp.zx.net.nz/pub/archive/ftp.kednos.com/"),
    # zx-microway -- see PROVENANCE.md in the archive.
    ("zx-microway", "http://ftp.zx.net.nz/pub/archive/data.microway.com/"),
    # zx-alphant-nt -- see PROVENANCE.md in the archive.
    ("zx-alphant-nt", "http://ftp.zx.net.nz/pub/archive/ftp.alphant.com/"),
    # zx-sgi-freeware-old -- see PROVENANCE.md in the archive.
    ("zx-sgi-freeware-old", "http://ftp.zx.net.nz/pub/archive/sgi-freeware-old/"),
    # zx-be-os -- see PROVENANCE.md in the archive.
    ("zx-be-os", "http://ftp.zx.net.nz/pub/archive/ftp.be.com/"),
    # sun3arc -- see PROVENANCE.md in the archive.
    ("sun3arc", "https://www.sun3arc.org/"),
    # transputer-classiccmp -- see PROVENANCE.md in the archive.
    ("transputer-classiccmp", "http://transputer.classiccmp.org/"),
    # novasareforever-aviion -- see PROVENANCE.md in the archive.
    ("novasareforever-aviion", "https://www.novasareforever.org/archives/"),
    # apollo-clavius -- see PROVENANCE.md in the archive.
    ("apollo-clavius", "https://apollo.clavius.jp/apollo/"),
    # wotug-inmos -- see PROVENANCE.md in the archive.
    ("wotug-inmos", "http://www.wotug.org/parallel/occam/compilers/inmos/"),
    # ultimate-fastpath -- see PROVENANCE.md in the archive.
    ("ultimate-fastpath", "http://ftp.ultimate.com/FastPath/"),
    # parisc-firmware -- see PROVENANCE.md in the archive.
    ("parisc-firmware", "http://ftp.parisc-linux.org/firmware/"),
    # somuchstuff-pdp8 -- see PROVENANCE.md in the archive.
    ("somuchstuff-pdp8", "https://so-much-stuff.com/pdp8/"),
    # bretjohnson -- see PROVENANCE.md in the archive.
    ("bretjohnson", "https://bretjohnson.us/"),
    # square7-vintage -- see PROVENANCE.md in the archive.
    ("square7-vintage", "http://vintagecomputers.square7.ch/Vintage/"),
    # biblionik-bull -- see PROVENANCE.md in the archive.
    ("biblionik-bull", "http://www.biblionik.fr/Info/Bull/SOLAR/"),
    # ONLY THE ARTICLES -- see EXCLUDE["openpa"] for the robots.txt rule that binds us and the
    # one that does not. Measured 2026-09-27 to a floor of 492 files / 47.80 MB.
    #
    # REGISTERED, ROLLED BACK, AND REGISTERED AGAIN, which is worth one line rather than a
    # silence: the first fetch on 2026-09-27 drew a timeout on its very first request because a
    # measuring run half an hour earlier had gone at 0.5 s, so everything was removed again --
    # an archive holding nothing is a phantom in every report. A single probe on 2026-09-28
    # answered HTTP 200 in 0.4 s. The block was a rate limit sleeping off, not a refusal.
    #
    # IN HTML_CRAWL, AND THE FIRST ANSWER WAS WRONG. It was checked before the first fetch --
    # the front page links its 81 children relatively and all 81 resolve inside the base without
    # the flag -- and the conclusion drawn was that the flag was unnecessary. THE FRONT PAGE IS
    # NOT THE SITE: pages under systems/ navigate sideways with `../doc/din800.txt` and
    # `../doc/a2263-62045.txt`, which is_child_link drops unless allow_up is set.
    #
    # THE FETCH THEN REPORTED `122 files, 0 failed` AND MARKED THE ARCHIVE COMPLETE, over a tree
    # the measurement had already put at 492 files and 47.80 MB. A quarter of the files, a
    # seventeenth of the bytes, and nothing in the run said so.
    #
    # THE EVIDENCE WAS THERE BEFORE THE FETCH AND WENT UNREAD. measure-remote.py crawls with
    # allow_up=True, so its count IS what a flagged crawl reaches. When a fetch lands far under a
    # measurement of the same tree, that gap is the finding -- not a rounding error, and not the
    # measurement being generous. Compare the two before believing a COMPLETE.
    #
    # `<img src>` COMES WITH THE FLAG and is its one real cost here, because openpa's scans live
    # under the two paths robots.txt forbids to everyone. EXCLUDE["openpa"] holds them out, and
    # the dead-pattern report at the end of a run says whether it actually bit.
    ("openpa", "https://www.openpa.net/"),

    # THE OS/2 BRANCH OF A LIVE FIDONET BBS, and the base is `/gfd/` rather than the site root
    # for the same reason acpc-amstrad's is `/ACME/`: rooted at the host, a crawl would start on
    # a front page that links 807 file areas and 88.5 GB, of which 70 GB is games, Windows
    # shareware, Flight Simulator aircraft and 1990s antivirus signature updates. Rooted at
    # /gfd/, nothing outside OS/2 is reachable -- the area pages link their own files with the
    # host spelled out, and every other area resolves outside the base and is dropped.
    #
    # `/gfd/` ITSELF ANSWERS 403, so there is no listing to start from and the 61 area pages are
    # SEEDS. They were not typed: they come from the table MBSE generates on the front page,
    # which carries a row per area with its file count and size. See CANDIDATES["dreamlandbbs"]
    # for the full inventory and for what was declined.
    #
    # http AND NOT https, WHICH IS NOT A DETAIL. The site answers both, but MBSE writes every
    # file link with `http://` spelled out, and scope is decided by testing the RESOLVED url
    # against this base. Registered as https, all 91 links on an area page resolve OUTSIDE the
    # base and are dropped -- measured, after a run that fetched the 61 index pages, reported
    # `61 files, 0 failed` and marked the archive COMPLETE over a tree missing 99.4 % of itself.
    # The base must be spelled the way the source spells its own links.
    ("dreamlandbbs-os2", "http://www.dreamlandbbs.com/gfd/"),

    # The other half of the same host. Measured 2026-09-27 before it was added: 37 files,
    # 381.64 MB, 12 pages, every size read off the listings, no failures and no cap reached.
    ("biblionik-goupil", "http://www.biblionik.fr/Info/SMT-GOUPIL/"),

    # abc-bladet -- see PROVENANCE.md in the archive.
    ("abc-bladet", "https://www.abc.se/bladet/"),
    # decromancer-bits -- see PROVENANCE.md in the archive.
    ("decromancer-bits", "https://archive.decromancer.ca/bits/"),
    # irixnet-ftp -- see PROVENANCE.md in the archive.
    ("irixnet-ftp", "https://ftp.irixnet.org/"),
    # develooper-hpux -- see PROVENANCE.md in the archive.
    ("develooper-hpux", "https://mirrors.develooper.com/hpux/"),
    # ndwiki-norsk-data -- see PROVENANCE.md in the archive.
    ("ndwiki-norsk-data", "https://www.ndwiki.org/"),
    # nice-next -- see PROVENANCE.md in the archive.
    ("nice-next", "https://ftp.nice.ch/pub/next/"),
    # adoxa-dos -- see PROVENANCE.md in the archive.
    ("adoxa-dos", "http://adoxa.altervista.org/"),

    # THE BASE IS `/ACME/` AND NOT THE SITE ROOT, and that choice is a safety fence rather than
    # a detail. acpc.me publishes a 2.7 MB front page that links, among much else, 206 magazine
    # scans averaging ~126 MB -- some 26 GB this collection does not want. Rooted at the site,
    # an ordinary `mirror.py` run with no --archive would start at that page and take them all.
    # Rooted at /ACME/, the crawler asks for a directory that answers HTTP 403, finds nothing to
    # follow, and fetches nothing: the front page is ABOVE the base and out of scope.
    #
    # An EXCLUDE fence was tried first and rejected. Keeping three branches out of the 35 the
    # catalogue names would take 39 patterns, several of them parse artefacts of the JavaScript
    # page (`HARDWARE*0*12/`). A fence nobody can check is not a fence; a base URL that cannot
    # be escaped is.
    #
    # WHAT IS HERE CAME FROM A URL LIST, not a crawl -- every directory on that host is 403, so
    # there is nothing to walk. See PROVENANCE.md in the archive.
    ("acpc-amstrad", "https://acpc.me/ACME/"),

    # Metropoli BBS, Helsinki -- hardware/ driver disks by vendor and model. Four large trees are
    # excluded (see EXCLUDE) and three PCBoard directories are lost. See PROVENANCE.md.
    # Its listing shows sizes in a form parse_listing does not read, so the ETA here is guesswork.
    ("mpoli-bbs", "https://files.mpoli.fi/"),

    # Jim Leonard's (Trixter) oldskool.org file area -- early-PC hardware, software and history.
    # Taken 2026-09-19 WITHOUT drivers/ (measured only as a floor of >= 250 GB; decided separately)
    # and without the trees listed in EXCLUDE. See PROVENANCE.md. robots.txt 404.
    #
    # SECOND PASS 2026-09-20/22, 39h53m, drivers/ included: 77 561 files, 149.23 GB, 0 failed.
    # It ends INCOMPLETE on 49 listings that answer 404, ALL under
    # drivers/Miscellaneous/vintagecomputer.ca/files/ -- and a re-run cannot mend them.
    #
    #   AN INDEX COPIED FROM ANOTHER SERVER STILL DESCRIBES THAT SERVER. What is served at
    #   .../vintagecomputer.ca/files/SWTPC/6800 Computer System/ is not this host's autoindex;
    #   it is a saved page of the original site's file browser, <title>vintagecomputer.ca</title>
    #   and a stylesheet at /files/.abba/css/style.css -- absolute, rooted at THAT server. It
    #   names 17 subdirectories and all 17 answer 404 here. The crawler was right to try them and
    #   right to report the failure; the page describes a tree this copy does not contain.
    #
    # Measured rather than reasoned: all 49 asked again individually on 2026-09-22, 49/49 still
    # 404. And www.vintagecomputer.ca/files/ answers 200 with 71 top-level directories against
    # the 113 this copy holds, while /files/SWTPC/ is 404 there too -- the live site has been
    # reorganised and is SMALLER. The missing levels were never inside ftp.oldskool.org/pub/, so
    # INCOMPLETE here is the counter being honest, not a transfer that fell short.
    ("oldskool", "http://ftp.oldskool.org/pub/"),
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
    "bullfreeware": "Atos closed www.bullfreeware.com on 1 March 2022 and gnome.bullfreeware.com "
                    "with it; both time out. Recovered from the Internet Archive 2026-08-30 with "
                    "wayback-salvage.py. THE RPMS ARE DELIBERATELY NOT IN THIS ARCHIVE: 8 935 of "
                    "the 8 955 the index lists are already held in bull-rpms/ and bull-srpms/ "
                    "from dl.power-devops.com, so 59 GB was declined and only what that rescue "
                    "did not carry was taken -- the catalogue, the .spec files, Bull's own "
                    "pre-RPM .exe packages and 20 RPMs power-devops missed. Revive this by "
                    "re-running with a shorter --skip-listed if those two archives ever go.",
    "aix-orphans": "Two dead sites from the list on Michael Perzl's homepage, which is the last "
                   "record that either existed: linkitup.de (parked -- Firefox and Mozilla builds "
                   "for AIX 4.3.3 and 5.1, with the build notes) and zipworld.com.au/~dtucker "
                   "(NXDOMAIN -- Darren Tucker's OpenSSH AIX patches, account-policy notes and "
                   "the original portable OpenNTPD). Neither is large enough to be an archive on "
                   "its own; together they are the salvage of one page's outbound links.",
    "agilent-ftp-2009": "ftp.agilent.com still resolves and does not answer. Nothing here was "
                        "fetched in any case -- it was unpacked on 2026-09-07 out of bitsavers' "
                        "`mirrors/ftp.agilent.com_CDs_20091212.tar` with extract-container-tar.py, "
                        "and verified three ways: against the tar's headers, against bitsavers' "
                        "own `tar -t` manifest from 2025 (1 016 entries, zero differences), and "
                        "against the index the CDs carry, which is older than both. That index "
                        "also proves the hole: it describes SIX discs and the tar holds four. "
                        "A re-run could not close it -- there is nowhere left to run against.",
    "hp-alphaserver-2008": "h18002.www1.hp.com does not resolve. Nothing here was fetched: it was "
                           "unpacked on 2026-09-07 out of bitsavers' "
                           "`mirrors/h18002.www1.hp.com_20080527.tar`, a capture of HP's "
                           "AlphaServer and ProLiant product web made 2008-05-27. Verified three "
                           "ways by verify-extraction.py -- 12 519 manifest entries matched with "
                           "zero differences, 10 201 sizes correct, 10 201 members re-hashed out "
                           "of the tar with zero mismatches.",
    "hp-openvms-2008": "h71000.www7.hp.com does not resolve. Unpacked on 2026-09-07 out of "
                       "bitsavers' `mirrors/h71000.www7.hp.com_20080527.tar`, HP's OpenVMS site as "
                       "it stood 2008-05-27 -- including 763 MB of release documentation, complete "
                       "for 7.3 and 8.x and a stub for 7.2. Verified three ways by "
                       "verify-extraction.py: 28 095 "
                       "manifest entries matched with zero differences, 27 372 sizes correct, "
                       "27 372 members re-hashed out of the tar with zero mismatches.",
    "hp-labs-2007": "www.hpl.hp.com resolves and does not answer. Unpacked on 2026-09-07 out of "
                    "bitsavers' `mirrors/www.hpl.hp.com_20070827.tar`, HP Labs as it stood "
                    "2007-08-27 -- the Technical Report series plus researcher home pages. "
                    "Verified three ways by verify-extraction.py.",
    "dec-ftp-2006": "ftp.digital.com does not resolve. Unpacked on 2026-09-07 out of bitsavers' "
                    "`mirrors/ftp.digital.com_20060831.tar`, DEC's public FTP server as it stood "
                    "2006-08-31 -- 22 170 files, 36.04 GB, of which roughly three quarters is "
                    "APPARENTLY one tree served under three names (Digital/, DEC/, Compaq/) and "
                    "crawled three times. Paths and sizes agree; content has not been compared. "
                    "Verified three ways by verify-extraction.py.",
    "next-68k-org": "next.68k.org is gone. Unpacked on 2026-09-07 -- NOT from bitsavers but from "
                    "this collection's own fsck-vendors archive, "
                    "`NeXT/next.68k.org Archive/next.68k.org.tar`. 234 760 files, 37.64 GB, the "
                    "largest by file count of the six container tars. THE ONLY ONE WITH NO "
                    "THIRD-PARTY MANIFEST: its listing was generated locally with GNU tar, a "
                    "second implementation, which proves consistency but cannot prove "
                    "completeness. The tar itself is known intact -- its SHA-256 is in "
                    "fsck-vendors/.sha256sum and was read back from disk on 2026-09-07.",
}

# Archives whose source is alive but which a DIFFERENT tool fetches. Not the same as FROZEN: there
# the source has gone, here the source is fine and this crawler is simply the wrong instrument.
#
# The distinction matters because the remedy differs. A FROZEN archive can never be improved. One
# of these can -- by re-running the tool that made it. Pointing the HTML crawler at it would not
# fail; it would quietly produce a second, worse copy alongside the good one.
EXTERNAL = {
    "ndwiki-norsk-data":
        "a MediaWiki. Fetched by mediawiki-source.py through the wiki's own API -- not crawled.\n"
        "    python mediawiki-source.py --base https://www.ndwiki.org --root <mirror> \\\n"
        "        --archive ndwiki-norsk-data            # 2 675 pages, current revisions, 54 requests\n"
        "    python mediawiki-source.py ... --images    # 1 164 files, 1.60 GB, sha1-checked\n"
        "CURRENT REVISIONS ONLY, by decision. Special:Export is the better-known route and would "
        "have returned full history for 7 877 edits; `prop=revisions` returns exactly one, and "
        "the tool aborts if it ever sees more.\n"
        "THE FILES ARE NOT TAKEN FROM /images/ EITHER, and that was measured rather than assumed. "
        "The directory IS an open autoindex, but it carries thumb/ (EIGHT generated thumbnails per "
        "image), archive/ (superseded versions, i.e. history), plus temp/, deleted/ and lockdir/. "
        "Its listing has no size and no date column, so a crawl would have to fetch every file to "
        "learn its size and would stamp each with the day it was copied. Enumerating thumb/ alone "
        "is a 16x16 fan-out plus one directory per image -- about 1 400 requests to find out what "
        "is there. `list=allimages` answers the same question in THREE, with url, size, mime, "
        "upload timestamp and the wiki's OWN SHA-1 for every file.\n"
        "A file whose bytes disagree with that sha1 is NOT written. It is a different file, and "
        "storing it under the right name would hide that permanently.\n"
        "USER-AGENT: must not begin `Mozilla/` -- see the note in CANDIDATES and the measurement "
        "table in mediawiki-source.py. mirror.py's own UA is challenged by this host.",
    "perzl-wiki": "a PmWiki. Fetched by pmwiki-source.py, which asks it for its own page list in "
                  "one request and then takes each page as raw markup -- smaller, cheaper for the "
                  "server, and closer to what the wiki actually stores than any crawl of the "
                  "rendered HTML would be.",
    "iffly-wiki": "a DokuWiki. Fetched by dokuwiki-source.py, which walks the wiki's own "
                  "`?do=index` tree namespace by namespace and then takes each page through "
                  "`?id=<page>&do=export_raw`. Refresh with:\n"
                  "    python dokuwiki-source.py --base http://emmanuel.iffly.free.fr/doku.php \\\n"
                  "        --root <mirror> --archive iffly-wiki --delay 1.5",
    "misterhayden": "an open directory whose TLS chain is incomplete -- the leaf validates but "
                    "the issuer is not served, so every stdlib client refuses it and a run here "
                    "ends in `1 unreadable listings`. Fetched by autoindex-tls-broken.py, which "
                    "disables verification and compensates with SHA256SUMS. Plain http "
                    "redirects to https, so there is no way around it.",
    "techsysadm": "a Blogger site. Its front page is an infinite-scroll widget, so a link crawl "
                  "walks the month hubs into a fan of `?updated-max=` permutations and still "
                  "finds no posts -- a run here found 0 files AND WROTE A COMPLETION MARKER. "
                  "Fetched by blogger-sitemap.py from /sitemap.xml, which is authoritative.",
    "csiph-gallery": "a small nginx autoindex whose robots.txt asks for Crawl-delay: 2. Fetched "
                     "by nginx-autoindex-gallery.py, which honours it. Only the gallery is "
                     "taken; the rest of the host is daily INN statistics and an NNTP corpus.",
    "fsck-aix-media": "a large HTTP directory tree taken as a deliberate SUBSET -- the releases "
                      "already held were left upstream. A crawl from the root would fetch all "
                      "66.87 GB, which is the opposite of what was decided.",
    "aix-qemu-git": "git repositories, not a file tree. Refresh with `git -C <dir> fetch --all`; "
                    "the clones keep their remotes, so a later fetch can be diffed against what "
                    "is recorded here if upstream rewrites history.",
    "AIX5-IA64": "a git repository, not a file tree, and cloned by the owner rather than fetched "
                 "by this tool. Refresh with `git -C <dir> fetch --all`; the clone keeps its "
                 "remote, so a later fetch can be diffed against what is recorded here if "
                 "upstream rewrites history. Same handling as aix-qemu-git.",
    "csri-toronto": "two named files off a 15.57 GB host. A crawl would take the other 15.57 GB, "
                    "which was explicitly decided against.",
    "tvsat-cpc710": "one PDF on an unrelated hobby site. There is nothing to crawl.",
    "fsck-aix-apps": "same host and same h5ai index as fsck-aix-media; fetched by the same "
                     "dedicated script. Its `Wavefunction Inc Spartan ` directory ends in a "
                     "SPACE, so anything touching it needs long_path() -- see the defect notes.",
    "fsck-vendors": "37 vendor trees under one root, taken in relevance order and WITHOUT the "
                    "BSD tree. A crawl from /software/ would also pull IBM (already held as "
                    "three separate archives) and BSD (excluded by standing decision).\n"
                    "    ONE FILE IN HERE IS NOW REDUNDANT AND THERE IS NO FILTER TO SAY SO. "
                    "`NeXT/next.68k.org Archive/next.68k.org.tar` (37.86 GB) was unpacked into "
                    "the `next-68k-org` archive on 2026-09-07. The five equivalent tars in "
                    "bitsavers are protected by --exclude lines in RSYNC[]; this archive is "
                    "fetched by a URL-list tool that skips files already present, so deleting "
                    "the tar here means the NEXT RUN OF THAT TOOL FETCHES 37.86 GB AGAIN. "
                    "THERE IS NOW SOMEWHERE MECHANICAL TO WRITE IT, and it is written there: "
                    "RETIRED[\"fsck-vendors\"] names this exact path and is_retired() is wired "
                    "into producer(). This paragraph said 'has to leave that URL out by hand' "
                    "until 2026-09-10 -- it was the sentence RETIRED's own header calls out as "
                    "the thing that does not stop a script at three in the morning.",
    "rs6000-microcode": "salvaged from the Internet Archive with wayback-salvage.py; the origin "
                        "is gone. Refresh is meaningless -- there is nothing left to refresh "
                        "from. 3 .suspect files are final: the stored WARC records are "
                        "themselves short. It said 15 until 2026-09-05, when checking EVERY "
                        "capture instead of one recovered 12 of them.",
    "aixpdslib": "salvaged from the Internet Archive with wayback-salvage.py; the origin times "
                 "out. Same terms as the other salvages.",
    "hp-labs-linux-salvage":
        "salvaged from the Internet Archive with wayback-salvage.py; www.hpl.hp.com resolves "
        "and does not answer. IT EXISTS BECAUSE hp-labs-2007 IS INCOMPLETE, and not through "
        "any fault of that extraction: bitsavers' 2007 capture saved the .php4 pages linked "
        "from index.html and did not follow the links OUT of them, so the level below is "
        "missing from the tar itself -- the same defect that cost sun3arc its .phtml pages. "
        "Kept apart rather than merged in, because hp-labs-2007 promises to be a byte copy "
        "of one tar of one day and these captures span 2003-2016.",
    "penguinppc": "a SUBSET salvaged from the Internet Archive -- /dev/prep/, /historical/ and "
                  "/bootloaders/ only. The live host still exists but 404s these paths, so the "
                  "Archive is the source; a crawl of the live site would find none of it.",
    "circle4": "a live site whose documents are reachable only through linked pages, and whose "
               "own links mix http and https. Fetched by a dedicated crawler scoped on the "
               "HOST; mirror.py's producer scopes on base_url and would drop the http half.",
    "fsck-ibm-other": "18 separate trees under one root, INCLUDING OS400_i Install Media "
                      "(219 files, 71.22 GB), which was fetched 2026-09-05 after being left "
                      "behind once. Contains a filename ending in a full stop.",
}

# Archives that are hand-written websites rather than generated directory listings. For these an
# HTML page is both a file to keep and a listing to walk; see producer(). Do not add a generated
# index here -- it costs a second request per page for nothing.
# ------------------------------------------------------------------- hosts we do not fetch
#
# THE OPERATOR SAID NO. This is policy, not preference, and it is enforced rather than
# remembered: blocked_host() refuses any URL whose host matches, and the fetch path consults it
# before a request is made, so a candidate cannot be added by accident later. (This comment
# named `resolve_archive()` until 2026-09-06. There has never been a function by that name --
# a safeguard described by the wrong name is one nobody can check.) Until 2026-09-03 this list existed only in conversation and in a
# prose file, which is to say it did not exist -- nothing would have stopped a future run.
#
# EVIDENCE QUALITY IS RECORDED PER ENTRY, because it is not uniform and pretending otherwise
# would be the same mistake as an unmeasured size. Only `icdia.co.uk` ever had a written note,
# in SEARCH-BRIEF.md in the curated IBM collection, which moved to another volume in September
# 2026. THE PATH IS DELIBERATELY NOT WRITTEN HERE -- it named a private tree, and a helpful
# future edit that puts it back would undo the reason it is missing. The rest were
# each checked when they came up and the finding was carried in conversation rather than
# committed anywhere, which is why they read `recheck`.
#
# A "recheck" entry is still binding -- refusing to fetch costs nothing and is reversible; the
# other error is not. But before any of them is ever removed from this list, the page must be
# read again and the quote written down.
DO_NOT_FETCH = {
    # host                    evidence
    "bitwiseworks.com":       "robots.txt names ClaudeBot with Disallow: / , and a separate "
                              "User-agent: * block disallows EVERY download path -- /docs/, "
                              "/download/linux/, /download/os2/, /download/win/ and "
                              "/download/old_stuff/. Its Cloudflare content signals are SET "
                              "(search=yes, ai-train=no, use=reference), unlike fsck.technology "
                              "where none were, so the Article 4 reservation is a live one. Two "
                              "independent refusals covering exactly the files worth having. "
                              "The company still sells OS/2 ports; this is a going concern "
                              "protecting its product, not an abandoned archive.  [2026-09-06]",
    # --- added 2026-09-07 from the candidate reconnaissance. Every one of these was read, not
    # --- assumed; the quotes are from the file as served on that date.
    "floodgap.com":           "robots.txt NAMES US: `User-agent: anthropic-ai` and "
                              "`User-agent: ClaudeBot`, both Disallow: / , alongside GPTBot, "
                              "PerplexityBot and archive.org_bot. For `*` it additionally blocks "
                              "*.zip *.lzh *.lha *.gz *.d64 *.prg *.jpg *.gif -- that is, exactly "
                              "the files. Two refusals, one of them addressed to this client by "
                              "name.  [2026-09-07]",
    "ibmfiles.retropc.se":    "`User-agent: *` / `Disallow: /`. Blanket. A live IBM retro archive "
                              "with ThinkPad 850 PowerPC and AIX PCI Audio Adapter material -- "
                              "wanted, and refused.  [2026-09-07]",
    "macintoshgarden.org":    "`User-agent: *` / `Disallow: /`. Blanket. AND IT IS THE ONLY PLACE "
                              "LinuxPPC 1999/2000 MEDIA WAS FOUND TO SURVIVE -- its own pages "
                              "state MkLinux DR3 599.53 MB, R2 RC5 614.80 MB, DR2.1 383.90 MB, "
                              "DR1 217.64 MB. Recorded so the refusal is not mistaken for "
                              "absence: the material exists, and we may not take it.  [2026-09-07]",
    "winworldpc.com":         "`Disallow: /download/` and `/search/`. The catalogue pages are "
                              "open and list AIX RT v1.1 (1986), v2.1, v2.2, v2.2.1 plus AIX "
                              "PS/2, 3.x, 4.1.x, 4.3.x, 5.1 -- the downloads are not.  [2026-09-07]",
    "os2museum.com":          "`Crawl-delay: 45`, `Disallow: /files/`, "
                              "`Disallow: /wp/wp-content/uploads/`. The download area is closed "
                              "and 45 s per request would make a mirror impractical anyway. Two "
                              "reasons, either sufficient.  [2026-09-07]",
    "iecc.com":               "`Disallow: /linker` -- which is John Levine's *Linkers and "
                              "Loaders* in full, the book that documents XCOFF and the AIX "
                              "binder. compilers.iecc.com allows general crawlers but blocks "
                              "GPTBot and Google-Extended with Disallow: / .  [2026-09-07]",
    "jepstone.net":           "returns HTTP 403 to automated fetches outright -- a refusal "
                              "expressed in the response rather than in a file.  [2026-09-07]",
    "icdia.co.uk":            "blocks automated retrieval; noted in SEARCH-BRIEF.md, in the "
                              "curated IBM collection -- which is not on this volume and whose "
                              "path is deliberately not recorded here",
    "chmod666.org":           "recheck -- restriction found on the page, quote not recorded",
    "sharktastica.co.uk":     "recheck -- restriction found on the page, quote not recorded",
    "ibmfiles.com":           "sitewide footer forbids mirrors; a /rants.htm section names "
                              "Claude and Anthropic by name",
    "unixhealthcheck.com":    "recheck -- restriction found on the page, quote not recorded",
    "migano.de":              "recheck -- restriction found on the page, quote not recorded",
    "polarhome.com":          "recheck -- restriction found on the page, quote not recorded",
    "softpanorama.org":       "recheck -- restriction found on the page, quote not recorded",
    "bhami.com":              "recheck -- restriction found on the page, quote not recorded",
    "bitsavers.org":          "its .htaccess refuses by User-Agent and NAMES US: line 5 lists "
                              "(ClaudeBot|GPT|CCBot|perplexity|amzn-searchbot|msnbot|amazonbot), "
                              "a second rule adds python-requests, curl, powershell and wget, "
                              "each ending RewriteRule ^.*$ - [F,L]. The index page carries the "
                              "matching notice, April 2026: 'Wget is no longer permitted here'. "
                              "OVER HTTP ONLY -- rsync.mirrorservice.org is the sanctioned path "
                              "and is what RSYNC['bitsavers'] uses. Fetching the origin with a "
                              "browser UA would be spoofing past a control that names ClaudeBot.",
    # www.hpmuseum.net AND www.openpa.net STOOD HERE FOR ONE HOUR ON 2026-09-26 and were taken
    # out again by the owner, who is right and whose reasoning is worth recording because it
    # draws a line this list had not drawn before.
    #
    # Both name ClaudeBot with Disallow: /. This list had treated that as binding, by analogy
    # with bitsavers.org above. THE ANALOGY DOES NOT HOLD, and the difference is in the files
    # themselves: bitsavers blocks AUTOMATION -- its rules name python-requests, curl, powershell
    # and wget alongside ClaudeBot, and its index page says "Wget is no longer permitted here",
    # and it offers rsync as the sanctioned path. hpmuseum.net blocks AI TRAINING crawlers by
    # name under its own heading saying so, and explicitly ALLOWS Googlebot and Bingbot with a
    # crawl delay. One operator refuses robots; the other refuses a use. This collection is not
    # that use, and it is not ClaudeBot -- it is mirror/1.0, fetching for preservation.
    #
    # WHAT SURVIVES THE CHANGE, because it is not a ClaudeBot rule at all: openpa.net's WILDCARD
    # block. `User-agent: *` disallows /images/ and /systems/images/, which binds every crawler
    # including this one, and that is where the scans live. The articles may be taken; the images
    # may not. That is in EXCLUDE["openpa"], not here, because a host block would forbid the part
    # that is allowed. hpmuseum.net's wildcard disallows only /capcha/ -- take it at the crawl
    # delay its own file grants search engines, since its stated reason is bandwidth.
}
#
# ON THE bitsavers ENTRY ABOVE, which is in DO_NOT_FETCH and is the one entry that does not mean
# "never touch this". It blocks HTTP ONLY -- blocked_host() ignores rsync:// URLs by scheme --
# so RSYNC["bitsavers"] is unaffected and the archive here is compliant. Its index
# page, April 2026 -- "As of April, 2026 due to the level of web traffic, Wget is no longer
# permitted here." / "People are downloading the ENTIRE site through the web interface." The
# rsync module is the sanctioned path and is what RSYNC["bitsavers"] uses, so the archive here
# is compliant; what must never happen is fetching it over HTTP from a mirror-of-mirrors such
# as ftpmirror.infania.net/sites/bitsavers/.


def blocked_host(url):
    """-> the DO_NOT_FETCH note for this URL's host, or None.

    Subdomains count: a restriction on `example.org` covers `www.example.org` and
    `files.example.org`, because it is the operator being respected and not a string.

    HTTP AND HTTPS ONLY. Every entry in that list is an HTTP-layer statement -- a robots.txt, an
    .htaccess User-Agent rule, a sentence in a page footer. None of them says anything about
    rsync, and bitsavers explicitly OFFERS rsync as the way to take its material in bulk.

    That distinction is not academic: ARCHIVES carries bitsavers as `rsync://bitsavers.org/...`,
    so a scheme-blind check refused the archive outright -- and since the guard runs before
    anything else, it refused --verify and --index too, operations that touch no network at all.
    One over-broad rule made the whole collection unverifiable.  [2026-09-05]
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https", ""):
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    for bad, why in DO_NOT_FETCH.items():
        if host == bad or host.endswith("." + bad):
            return why
    return None


# ---------------------------------------------------------------- Internet Archive items, taken
#
# Archives fetched with `ia-item-fetch.py`, NOT with this file's crawler. They live in their own
# list for a reason worth stating: an entry in ARCHIVES is a base URL that the crawler walks, and
# pointing that at archive.org would be both wrong and rude. The Archive publishes an exact file
# list at `https://archive.org/metadata/<item>` -- one request, authoritative, with per-file MD5 --
# so there is nothing to crawl and no excuse for crawling it.
#
# WHAT THE FETCHER GUARANTEES that a crawl cannot: completeness is measured against the item's own
# manifest rather than against a guessed directory listing, and every file's MD5 is compared with
# the Archive's before the run is called done. `bad 0` in the log means every byte matched.
#
# Archive-generated files (`*_files.xml`, `*_meta.xml`, `*_meta.sqlite`, `*_archive.torrent`) are
# skipped -- they are the Archive's bookkeeping, not the uploader's content. The item record is
# kept as `IA-METADATA.json` in each archive instead.
#
# (name, item id, files, bytes, fetched, state)
IA_ITEMS = [
    ("ia-bull-toolbox-43", "GroupeBullAIXToolbox4.3",
     2, 529529436, "2026-09-07",
     "COMPLETE, 0 bad. Two files: `toolbox.aix43.tar.gz` and an 18.9 KB capture of Groupe Bull's "
     "own website HTML from the early 2000s -- the index that says which fileset belonged to "
     "which release. NOT YET UNPACKED, so whether it duplicates ia-bull-aix433-2013 is unknown."),

    ("ia-bull-aix433-2005", "bull-freeware-aix433-April05",
     200, 980733782, "2026-09-08",
     "COMPLETE, 0 bad. 189 .bff filesets, April 2005. HAS NO GCC -- its own 00_TOC.txt names "
     "three gnu.gcc-2.95.3 packages that are absent from the item. See PROVENANCE.md: the five "
     "00_* metadata files are byte-identical to the 2013 item's, describe neither, and date to "
     "early 2001. Do not verify against 00_MD5.txt; it lists .exe installers, not .bff."),

    ("ia-bull-aix433-2013", "bull-freeware-aix433-2013",
     247, 2361734227, "2026-09-08",
     "COMPLETE, 0 bad. 237 .bff filesets. THE COMPILERS ARE HERE and not in the 2005 item: "
     "gcc-3.3.0.0, gcc-3.0.1.0, gnu.gcc-2.95.3.0, gnu.gcc.g++-2.95.3.0, gnu.gcc.info-2.95.3.0. "
     "AIX-native installp form, which no RPM-based source in this collection provides."),

    ("ia-bullfreeware", "bullfreeware",
     None, None, None,
     "IN PROGRESS as of 2026-09-08 09:00 -- 63 small files complete, `packages.tar` resuming at "
     "67 of 85.06 GB over HTTP Range. THE ANSWER TO A KNOWN HOLE: this collection's `bullfreeware` "
     "archive holds eight .rpm files that are 2.7 KB HTML landing pages, seven of them the GCC "
     "4.8.4 toolchain for AIX 7.1, unfetchable since 2014. A whole-site upload made 2022-03-01, "
     "the day bullfreeware.com closed. `packages.sfv` beside the tar is an independent manifest. "
     "Members are individually addressable at /download/bullfreeware/packages.tar/<path>, but A "
     "NONEXISTENT MEMBER ALSO ANSWERS 200 with an empty body -- read the listing, never trust the "
     "status. Taken whole rather than per-member because the .sfv can then verify it. "
     "COMPLETE since 2026-09-08; 85 045 125 120 bytes, verified three ways. "
     "DRY-RUN 2026-09-12: packages.tar unpacks CLEANLY on NTFS -- 13 075 entries, 11 884 files "
     "(85.04 GB) and 1 190 directories, with ZERO renames needed, zero links or devices to skip, "
     "zero path escapes, zero destination collisions, zero case-only clashes, longest path 146 "
     "characters. The cleanest container this collection has measured. Its 24 zip/gz siblings all "
     "read without error and hold 10.3 MB of Internet Archive OCR derivatives (_jp2.zip are page "
     "scans, _chocr.html.gz their OCR) of six short PDFs about the shutdown -- no software, "
     "nothing to unpack. "
     "AND THE TAR IS NOT A SECOND COPY: comparing packages.sfv against bullfreeware/.sha256sum by "
     "basename gives 8 815 shared, 4 058 only in the live mirror (readmes, index pages), and "
     "1 877 ONLY IN THE TAR -- .src.rpm sources (a2ps, aalib, acme, afterstep ...) and the "
     "numbered RPMS_ZIPS/*.with-deps.zip bundles, which the crawl never reached. So unpacking "
     "would add content, not redundancy. NOT UNPACKED: that is 85 GB of disk and the owner's "
     "call. Everything needed to decide is in this note; the check does not have to be repeated. "
     "THE 24 SMALL CONTAINERS WERE UNPACKED IN PLACE on 2026-09-12 as a rehearsal of every step "
     "the tar would need -- 44 files, 10 278 752 bytes, all verified against the size the "
     "container recorded; the tree went 63 -> 107 files. The containers were KEPT, because a "
     "_jp2.zip is the form the Archive published and deleting it would leave this copy unable to "
     "say what the item contained. Nothing removed, so NO RETIRED entry here; if they were ever "
     "deleted one would be needed, and until 2026-09-12 it would not have worked -- "
     "ia-item-fetch.py did not consult RETIRED at all. It does now, proved by inserting a real "
     "entry, watching `RETIRED, not fetched: Bullfreeware_News_jp2.zip` and the count fall from "
     "63 to 62, and taking the entry out again."),
]


# ---------------------------------------------------------------- candidates, not yet taken
#
# Leads from the reconnaissance of 2026-09-07, recorded so they are neither lost nor researched a
# second time. NOTHING HERE HAS BEEN FETCHED. A candidate moves into ARCHIVES only after it has
# been measured and a decision written down.
#
# Sizes marked MEASURED were observed directly. The Internet Archive ones came from
# `https://archive.org/metadata/<item>`, which returns the exact file list in one request -- better
# than any crawl and the interface the Archive offers for the purpose. Everything else is marked
# unverified, and unverified means unverified.
#
# THE RECONNAISSANCE ITSELF WAS LIMITED and the limits belong here rather than in a footnote: the
# search budget was exhausted before it began, Google/Bing/DuckDuckGo/Brave/Mojeek/Startpage were
# CAPTCHA- or 403-walled, web.archive.org was hard-blocked, and HTTP-only legacy hosts could not be
# tested at all. One of four topic sweeps -- AIX INSTALL MEDIA AND RS/6000 HARDWARE DOCUMENTATION --
# never returned. That ground is NOT covered. A normal search-backed pass would find more.
#
CANDIDATES = [
    # (name, url, size, state)
    #
    # The four Bull items that stood here from 2026-09-07 have been TAKEN and moved to IA_ITEMS
    # above: ia-bull-toolbox-43, ia-bull-aix433-2005, ia-bull-aix433-2013, ia-bullfreeware.
    # Three are complete with 0 MD5 mismatches; the 85 GB one is still downloading.
    #
    # One thing the fetch corrected, and it belongs here because it is what a candidate note gets
    # wrong: the 2005 entry was described as "the same tree eight years earlier ... a second point
    # in time rather than a duplicate". True, but it undersold the difference. The 2005 item HAS
    # NO COMPILERS AT ALL, while listing three of them in its own table of contents. A measurement
    # of size and file count -- which is what MEASURED meant -- cannot see that. Only reading the
    # thing after fetching it can.
    #
    # MARKED TAKEN 2026-09-22 -- develooper-hpux, mpoli-bbs, nice-next and adoxa-dos, all of which
    # had been fetched days earlier while their state field still read MEASURED or NOT CRAWLABLE.
    # A fifth, ndwiki-norsk-data, already said so. They are NOT removed: ndwiki's own note gives
    # the reason -- the reasoning that got to an archive is worth finding from the candidate side
    # too -- and each now carries what the estimate turned out to be worth:
    #
    #   develooper-hpux   571 files / ~13 GB estimated  ->    580 /  12.61 GB   held
    #   nice-next       7 245 files / ~1.3 GB estimated ->  4 539 /   1.32 GB   bytes yes, count no
    #   adoxa-dos         405 files estimated           ->    437 /   0.08 GB
    #   mpoli-bbs       4 708 files / ~1.07 GiB         -> 23 180 /   5.66 GB   only hardware/ was
    #                                                                           measured; the rest
    #                                                                           of /files/ was 5x
    #
    # WHICH IS THE POINT OF KEEPING THEM. A candidate note is a prediction, and the only way to
    # learn what these predictions are worth is to write the outcome next to the guess. Three of
    # four were close. The fourth was low by a factor of five, and it was low because the survey
    # measured ONE SUBDIRECTORY and the note reported that figure as if it were the archive.

    # ============================================================ reconnaissance of 2026-09-13/15
    #
    # Five parallel searches with deliberately different angles -- firmware, disk images, DOS,
    # commercial Unix, non-English -- against a digest of everything this collection already held,
    # rejected or lost. Nine were taken the same day and are in ARCHIVES above. What follows is
    # the rest, recorded so nobody researches it twice.
    #
    # EVERY STATUS BELOW WAS OBSERVED BY A LIVE REQUEST, not read off a search result. All five
    # searchers had their web-search budget exhausted before they began and worked by direct HTTP
    # probing, Marginalia and link-following instead -- which makes the findings harder and the
    # coverage lopsided. Japanese, Korean, Chinese, Baltic and Iberian sources are NOT exhausted;
    # Dutch produced no live candidate at all.

    # --- measured and wanted ------------------------------------------------------------------
    ("develooper-hpux", "https://mirrors.develooper.com/hpux/", "TAKEN 2026-09-16",
     "NO LONGER A CANDIDATE -- 580 files / 12.61 GB. The estimate of 571 files and ~13 GB was "
     "close, which is worth one line: the measurement held. "
     "H. Merijn Brand's HP-UX depots -- and the piece hpux.connect.org.uk does not "
     "cover: gcc 3.3.2 through 4.2.2 for HP-UX 10.20/hppa1.1, plus Perl and OpenSSL. Frozen "
     "2017-12-29. Its own page names five mirrors; FOUR ARE DEAD -- perl.org 404, nluug.nl "
     "NXDOMAIN, hpux.ws is now an unrelated WordPress blog. IA holds the index page and no "
     "depots. robots: none."),
    ("mpoli-bbs", "https://www.mpoli.fi/files/", "TAKEN 2026-09-19",
     "NO LONGER A CANDIDATE -- 23 180 files / 5.66 GB, against an estimate that had only "
     "measured hardware/ (4 708 files, ~1.07 GiB). The rest of /files/ was five times that. "
     "The strongest single find of the sweep. Metropoli BBS, Finland, re-indexed "
     "2025-12-19. Driver disks foldered by vendor AND exact model -- 41 display-chip vendors, "
     "the proprietary-interface CD drives (Mitsumi, Panasonic, Chinon), 26 network-card "
     "directories -- often as the loose unpacked contents of the support floppy. Original BBS "
     "dates survive in Last-Modified. THE INTERNET ARCHIVE HOLDS 910 URLs UNDER /files/ AND "
     "EXACTLY ONE IS A REAL FILE; drivers_1/, tlr/ and sekalaiset/ have zero captures. robots "
     "allows /files/."),
    ("oldskool-drivers", "http://ftp.oldskool.org/pub/drivers/", "169.7 GB NOT taken",
     "MEASURED IN FULL 2026-09-20 and then decided. The two earlier walks reported 250.43 GB as "
     "a FLOOR because both were cut off by their own page budget; the third was not, and the "
     "answer is 344 vendor directories, 71 916 files, 292.38 GB. Per-vendor figures are in "
     "`drivers-measure-2026-09-20.tsv`. 122.7 GB of it is being taken into the `oldskool` "
     "archive -- see DRIVERS_OUT / DRIVERS_OUT_SUB for what is not, and why. "
     "THE SELECTION WAS INVERTED ON THE OWNER'S INSTRUCTION: a positive list of 103 chosen "
     "vendors was written first, then dropped for a list of 13 excluded brands and 35 excluded "
     "subdirectories. A positive list has to be revisited whenever the site grows; an exclusion "
     "list lets a new small directory arrive on its own. It costs ~63 GB more, and 304 of the "
     "344 vendors hold under 1 GB each anyway -- 29 GB for the whole tail. "
     "Also left outside the archive: misc/Video + misc/temp (146 GB of recordings), simtelnet "
     "(87.8 GB, mirrored everywhere), MindCandy (34.8 GB of demoscene DVDs as video), mp3 trees. "
     "IBM_PC_BBS AND ftp.bocaresearch.com ARE NOT CANDIDATES AT ALL: both are already held, "
     "7 871 of 7 890 and 1 239 of 1 239, under ps-2.kev009.com / os2bbs / ardent-tool. This note "
     "named them as prizes because it was written when they were FOUND, not after the collection "
     "acquired them elsewhere -- see the lesson ASK WHETHER WE ALREADY HOLD IT. "
     "THE WEB FRONT END IS BROKEN: www.oldskool.org/pub/ answers 404 with a Zope error page, so "
     "the archive is reachable only via the ftp. hostname. robots.txt 404. R11: one person's "
     "server, one connection -- the first 22.2 GB took 19h27m."),
    ("nice-next", "https://ftp.nice.ch/pub/next/", "TAKEN 2026-09-17",
     "NO LONGER A CANDIDATE -- 4 539 files / 1.32 GB. The byte estimate of ~1.3 GB was right "
     "and the file count of 7 245 was not; a listing counts entries, a fetch counts files. "
     "THE MUNICH PEANUTS ARCHIVE, surviving under the NiCE NeXT User Group name. "
     "peanuts.leo.org no longer resolves and this collection next-68k-org is FROZEN. Covers "
     "NeXTSTEP on HP PA-RISC and SPARC as well as m68k; /pub/next/developer/ is the toolchain "
     "tree. IA has the directory listings and no files. robots: no Disallow."),
    ("ndwiki-norsk-data", "https://www.ndwiki.org/", "TAKEN 2026-09-17",
     "NO LONGER A CANDIDATE -- it is an archive. 3 843 files / 1.60 GB: 2 675 pages of "
     "wikitext at their current revision and 1 164 uploaded files, fetched through the "
     "wiki's own API by mediawiki-source.py rather than crawled. Kept in this list as a "
     "pointer, because the reasoning that got here is worth finding from the candidate "
     "side too: the Anubis challenge keys on the literal token `Mozilla/` in the "
     "user-agent and on nothing else, /robots.txt is a 301 to Main_Page so no rules exist, "
     "and /images/ is an open autoindex that is still the wrong instrument -- eight "
     "generated thumbnails per image, no size or date column, ~1 400 requests to enumerate "
     "against THREE for list=allimages. See ARCHIVES, EXTERNAL and the PROVENANCE."),
    ("acpc-amstrad", "https://acpc.me/ACME/",
     "THREE BRANCHES TAKEN 2026-09-27: 34 files, 1.24 GB. The rest declined.",
     "THE REST IS DECLINED ON SCOPE rather than size. The part this entry used to call the "
     "valuable one is MAGAZINES -- `REVUES` is French for exactly that -- and the owner has "
     "ruled magazines out of this collection. "
     "WHAT WAS TAKEN: HARDWARE, DOCUMENTS_TECHNIQUES and LITTERATURE/MANUELS, with "
     "manifest-fetch.py from a URL list, because every directory on the host answers 403 and "
     "there is nothing to crawl. See PROVENANCE.md in the archive -- including the two typos in "
     "the site's own catalogue that cost 36 MB until they were probed out, and why the "
     "registered base is /ACME/ rather than the site root. "
     "MEASURED 2026-09-27 so nobody repeats it. Every directory answers HTTP 403: /ACME/, "
     "/ACME/LITTERATURE/, /ACME/LITTERATURE/REVUES/ and a language folder were each tried, so "
     "listing is off and only individual files are served. The `?path=` and "
     "`?action=download&file=` forms this entry used to describe are GONE from the site -- the "
     "root is now one 2.7 MB page embedding 2 343 ACME paths, 435 of which name a file. That "
     "page is a front-page SELECTION and not the catalogue, so its counts do not match the "
     "per-language figures this entry carried, which came from an earlier and fuller "
     "enumeration. Of the 435: 206 LITTERATURE/REVUES, 63 LITTERATURE/LIVRES, 32 HARDWARE, "
     "18 DOCUMENTS_COMMERCIAUX, 4 LITTERATURE/MANUELS, 3 DOCUMENTS_TECHNIQUES, and ~109 "
     "photographs, videos, podcasts and 3D-printing goodies. "
     "THE FILES ARE ENORMOUS, and that is the figure worth carrying: three HEADs gave a Greek "
     "book at 175.7 MB and two Danish magazine issues at 90.3 and 111.3 MB. At ~126 MB apiece "
     "the `20-40 GB subset` this entry promised was low by a wide margin -- the four minority "
     "languages alone would be over 100 GB. "
     "WHAT WOULD BE IN SCOPE IS A FEW DOZEN FILES: the HARDWARE branch (Hitachi HFD305S/SX "
     "3-inch drive service manuals, DMP-1 printer manuals), DOCUMENTS_TECHNIQUES (a DKTronics "
     "peripheral manual, a Z80 die photograph) and LITTERATURE/MANUELS. Perhaps 39 front-page "
     "files, drive and printer documentation of the kind bitsavers and chipdb already carry, "
     "reachable only by transcribing URLs out of a JavaScript front page because the "
     "directories refuse to list. Not worth it."),
    ("biblionik-goupil", "http://www.biblionik.fr/Info/SMT-GOUPIL/",
     "MEASURED 2026-09-27: 37 files, 381.64 MB",
     "The other half of the host already held as biblionik-bull: bootable SMT Goupil G3 images "
     "(FLEX9.IMD, CPM86.IMD, DOS2-G3.TD0). Same EOL CentOS 7, same HTTP-only, same reason IA "
     "has nothing. Small; take it with the next biblionik run. "
     "THE MEASUREMENT WAS CLEAN: 12 pages, 0.1 minutes, every size read off the listings, no "
     "HEAD needed, no failures and no cap reached. `robots.txt` is a single `User-agent: *` "
     "with no rule under it."),
    ("adoxa-dos", "http://adoxa.altervista.org/", "TAKEN 2026-09-17",
     "NO LONGER A CANDIDATE -- 437 files / 0.08 GB, fetched with pages-to-urllist.py and "
     "manifest-fetch.py exactly as the note below prescribed. "
     "NOT CRAWLABLE by mirror.py: downloads go through dl.php?f=<name> and is_child_link drops "
     "every href "
     "containing a query string -- correctly, since on a generated index that is a sort order. "
     "Needs pages-to-urllist.py plus manifest-fetch.py. SHSUCDX (the CD-ROM redirector on nearly "
     "every DOS boot disk) and DOSLFN. ON FREE HOSTING, and the author own page carries a "
     "mailto link with subject Takeover SHSUCD -- he is publicly asking someone to take it "
     "over."),
    ("dreamlandbbs", "https://www.dreamlandbbs.com/",
     "ENUMERATED 2026-09-27: 807 areas, 108 043 files, 88.5 GB -- exactly, from one page",
     "A live MBSE BBS publishing a full FidoNet FILEBONE, plus the files that doorgames.org "
     "still-served catalogue names but no longer delivers (its FTP answers 530). IA covers ~9% "
     "at file level. Large for what it is; a quarter of current free space. robots: 404. "
     "COUNTED EXACTLY WITHOUT CRAWLING ANYTHING. The root is a 220 kB page MBSE generates -- one "
     "table row per file area carrying its description, file count and total size -- so the whole "
     "inventory costs ONE request: 807 areas, 108 043 files, 88.5 GB, which confirms the "
     "self-reported figure. The breakdown is what decides this, and only one group is on subject: "
     "GFD 7 663 files / 17.96 GB is OS/2 (http servers, browsers, compilers, TCP/IP, GNU tools); "
     "GN 40 391 / 18.00 GB is games (emulators, action, card, Macintosh, `old stuff`); "
     "VIR 1 620 / 8.71 GB is Norton, McAfee and AVP SIGNATURE UPDATES from the 1990s; "
     "FS 9 227 / 6.30 GB is Flight Simulator aircraft; W32 and WIN together 4 188 / 9.43 GB are "
     "Windows 9x utilities and games; NASA 12 747 / 2.96 GB is Earth and space science imagery; "
     "SND 4 327 / 3.85 GB is sound files; FIDO 2 647 / 0.24 GB is nodelists, echo rules and "
     "weekly newsletters -- the FidoNet record itself, tiny and the one genuinely irreplaceable "
     "part; BBS 1 727 / 0.43 GB is BBS software (Remote Access, EleBBS, doorgames, LORD); "
     "UTL 1 841 / 0.43 GB is DOS utilities, archivers and Y2K test programs. "
     "AND THE OS/2 GROUP IS THE ONE WE MOST LIKELY ALREADY HAVE. This collection holds "
     "zx-hobbes-os2 (10 722 files, 8.83 GB -- Hobbes is THE OS/2 archive) and os2bbs (21 476 "
     "files, 10.82 GB): 19.65 GB of OS/2 against the GFD filebone's 17.96 GB. Whether GFD adds "
     "anything is a file-level question nobody has asked, and it is the question to ask first. "
     "IT WOULD NEED HTML_CRAWL. MBSE writes its own links FULLY QUALIFIED, and is_child_link "
     "drops a fully-qualified href unless allow_up is set. Measured on the saved page: 1 link "
     "found without the flag, 805 with it. Not a defect -- the flag exists for exactly this -- "
     "but a GENERATED index that spells out its own host is an unusual combination, and a run "
     "without HTML_CRAWL would report one link and look like it had worked."),
    ("decromancer-thinkpad", "https://archive.decromancer.ca/bits/IBM/", "cross-check",
     "NOT A NEW HOST -- decromancer-bits is held. Recorded as a TASK: its AIX 4.1.4 boot drive "
     "from an RS/6000 ThinkPad 860 (281.9 MiB) should be cross-checked against ps-2.kev009.com, "
     "which carries RS/6000 material from a different direction."),

    # --- needs the operator permission, the way novasareforever did ---------------------------
    ("hpux-porting-centre", "http://hpux.connect.org.uk/", "6.32 GB, 1 065 packages, 3 373 files",
     "MEASURED over FTP from the per-category DATABASE files, and a floor: sub-category "
     "databases are not in the sum. The only surviving general open-source port tree for HP-UX "
     "11.11/11.23/11.31 -- SD-UX depot.gz for PA-RISC and Itanium, with per-package build "
     "recipes. STILL BUILDING: newest packages 2026-09-11. IA holds only 2002-2004 directory "
     "indexes of ~700 bytes and zero packages. BLOCKED: robots.txt disallows /ftp/, the entire "
     "binary tree. Run by a small UK web agency with no mirrors named anywhere."),
    ("migano-aix-tools", "https://migano.de/aix/aixtools.zip", "179 890 B, 39 entries",
     "DOWNLOADED AND LISTED, then left alone. A German consultant AIX 3.2 tool suite: CHKINST "
     "reconciles an LPP installation WITH THE ODM, LPPDEL removes filesets from the filesystem "
     "AND the ODM. Directly on point for this collection AIX 5.3 ODM work. IA has ONE capture, "
     "2016, at 179 081 bytes -- the live file is 179 890, so the only good snapshot is not the "
     "current content. BLOCKED: robots.txt disallows /aix/."),

    # --- refused, and why. Do not re-propose --------------------------------------------------
    ("os2site.com", "http://www.os2site.com/", "-",
     "OPERATOR REFUSAL, explicit. Serves a file named /sw/new/0.do.not.mirror.this.site reading "
     "PLEASE do not mirror this web site ... I will add your subnet to the banned list, and "
     "robots.txt ends User-agent: * / Disallow: /. It EXPLICITLY ALLOWS ia_archiver and "
     "archive.org_bot -- the operator has chosen the Internet Archive as his preservation route "
     "and chosen against private mirrors. Belongs in DO_NOT_FETCH."),
    ("archives.loomcom.com", "https://archives.loomcom.com/3b2/software/", "-",
     "NAMES US. robots.txt carries both User-agent: ClaudeBot / Disallow: / AND a blanket "
     "User-agent: * / Disallow: /. The rwth-aachen reading does NOT transfer -- there the "
     "exclusion was targeted at archive.org with no * rule. AT&T 3B2 System V 2.0.5-3.2 stays "
     "where it is."),
    ("update.uu.se", "ftp://ftp.update.uu.se/pub/", "-",
     "NAMES US, on a different vhost. www.update.uu.se and dfupdate.se both list anthropic-ai, "
     "Claude-Web and ClaudeBot under Disallow: /; ftp.update.uu.se itself answers 404 for "
     "robots.txt. SAME CLUB, SAME PEOPLE: a 404 on one host is not permission when they have "
     "said no on another. Holds VAXstation 4000/90 KA49 CPU firmware (cougar_fw.zip, verified "
     "by download before the robots.txt was read) and is structurally invisible to the Wayback "
     "Machine because /pub/ is FTP-only. Worth a human asking the club; not worth a crawler."),
    ("greekrcm.gr", "https://greekrcm.gr/", "~800 files, ~27 GB",
     "NAMES US. User-agent: ClaudeBot / Disallow: /, plus Content-Signal: ai-train=no and an "
     "EU DSM Article 4 rights reservation. Search crawling is allowed. 27 Greek computing "
     "magazine titles, and IA has zero successful captures of any download endpoint. Needs the "
     "same deliberate decision rwth-aachen got, from a human."),
    ("nj7p.org", "http://nj7p.org/Computers/ROMs.html", "25 .7z archives",
     "BLANKET REFUSAL: robots.txt is User-agent: * / Disallow: /. Intel Intellec/MDS/iSBC "
     "monitor PROMs including SIM8-01 Rev 4 from 1972, still being added to in 2025, and NOT "
     "ARCHIVED ANYWHERE. Also decaying on its own: www.nj7p.org no longer resolves."),
    ("4corn.co.uk", "https://www.4corn.co.uk/archive/", "~70-100 .ADF",
     "HONOURED INTENT, NOT SYNTAX. robots.txt names ~45 AI crawlers including anthropic-ai and "
     "ClaudeBot -- and the directive closing that group is an EMPTY Disallow:, which means "
     "allow-all. The block is technically a no-op. Somebody who lists 45 agents by name does not "
     "want them, and a missing slash does not change that."),
    ("pelikonepeijoonit.net", "https://pelikonepeijoonit.net/", "-",
     "COMPROMISED, DO NOT INGEST. Every response carries TWO html documents; the outer one is a "
     "Turkish admin panel with a password prompt, consistent with auto_prepend_file or a "
     "malicious plugin. The Finnish site underneath has no downloads anyway. The operator should "
     "be told."),

    # --- checked and NOT worth taking, with the measurement that settled it --------------------
    ("mcamafia.de", "https://www.mcamafia.de/", "923 .adf",
     "REDUNDANT, measured not assumed: the held ardent-tool carries 1 278 ADF files and only 64 "
     "of mcamafia are absent from it, mostly variant-suffixed revisions of files ardent has "
     "under other names. ~93 % duplicate."),
    ("walshcomptech.com", "http://www.walshcomptech.com/selectpccbbs/", "133 zips",
     "REDUNDANT: the same IBM PC Company BBS material the held ps-2.kev009.com/pccbbs/ carries "
     "as the original self-extracting .exe, plus refdisks/, adf_files/ and eprm/. The site calls "
     "itself a miniature archive."),
    ("l8r.net-amiga", "https://www.l8r.net/install/", "229 .DMS, 87.3 MB",
     "ALREADY SAFE: the Internet Archive holds 295 unique image paths -- MORE than the live "
     "site."),
    ("gona.mactar.hu", "https://gona.mactar.hu/", "19 .IMG",
     "ALREADY SAFE: the complete Hungarian-localised System 7.5.3 floppy set, all 19 archived."),
    ("deramp.com", "https://deramp.com/downloads/", "9 703 files, 10.94 GB, 558 disk images",
     "ALREADY SAFE for the images: IA holds 799 archived image URLs. Mike Douglas plus the "
     "Martin Eberhard S-100 archive; a second copy rather than a rescue. Note the PDFs were not "
     "measured against IA."),
    ("crynwr.com", "http://crynwr.com/drivers/", "~41 drivers",
     "ALREADY SAFE: the original Crynwr packet drivers, still served by the author, and IA has "
     "them from 2000, 2006, 2007 and 2015. ALSO A METHOD NOTE: www.crynwr.com does NOT resolve "
     "while crynwr.com answers on 45.79.140.191. A host declared dead on the strength of one "
     "name may be alive under the other -- every LOST entry here was re-tested at both after "
     "this turned up, and none of them changed."),

    # --- gone since this collection last looked -----------------------------------------------
    ("oldcomputers.dyndns.org", "http://oldcomputers.dyndns.org/", "-",
     "CLOSED JULY 2026 -- roughly two months before this sweep. Everything answers 401; its "
     "robots.txt explains in German that the site went members-only for the VzEkC club, behind "
     "OpenID against the club forum. A formerly public German archive, no public bytes left. The "
     "last open copy of part of it is a third-party FTP mirror whose .td0 files are IMPLAUSIBLY "
     "SMALL -- 33 bytes for one of them -- and would need per-file validation before being "
     "called recovered."),
    ("criggie.org.nz-ncd", "http://criggie.org.nz/ncd/explora/", "-",
     "THE BYTES ARE ALREADY GONE, only the metadata survives. The page still advertises NCDware "
     "5.0.129 and 5.1.140 for NCD Explora X terminals; NCDware-5.1.140.tar.bz2 is 404 and only "
     "its .md5sum remains. The mirror it names, explora.pacn.com, is also gone. X-terminal boot "
     "firmware, lost."),

    # ============================================================ OUTCOME OF THE 2026-09-26 SCOUT
    #
    # Nine candidates were proposed on 2026-09-26; eight were measured, taken and are now in
    # ARCHIVES above. This block is the prediction written next to the result, which is what this
    # list is for -- the 2026-09-13/15 block says why: "A candidate note is a prediction, and the
    # only way to learn what these predictions are worth is to write the outcome next to the
    # guess."
    #
    #   archive          estimated              fetched                     off by
    #   mcamafia         1 467 f / 170.43 MB    1 770 f / 114.31 MB         +21 % files, -33 % B
    #   sgidepot         728 f / 497.38 MB      2 186 f / 609.92 MB         3.0x files
    #   obsolyte         289 f / 23.24 MB       650 f / 35.64 MB            2.2x files
    #   fjkraan          243 f / 30.17 MB       2 832 f / 2 900.55 MB       96x BYTES
    #   cmu-shadow       32 f / 1.58 MB         33 f / 1.50 MB              exact
    #   chipdb           2 939 f / 2.26 GB      2 404 f / 2.16 GB           -18 % files
    #   iommu            ~83.86 GB total        8 207 f / 19.07 GB          fenced, see EXCLUDE
    #   seds-frommert    1 310 f / 51.32 MB     2 928 f / 140 MB            2.2x files
    #
    # THE MEASUREMENT WAS LOW SEVEN TIMES OUT OF EIGHT AND NEVER HIGH. That is not bad luck, it
    # is three separate causes, and naming them is the point of writing this down:
    #
    #   1. THE MEASURING TOOL HAD ITS OWN LISTING PARSER and it was blinder than the crawler's.
    #      Its pattern ended in `(.*)$` to reach the size column, so it saw ONLY THE FIRST LINK
    #      OF EACH LINE -- correct for mod_autoindex, wrong for every hand-written page. Measured
    #      over 1 790 stored pages: common.parse_listing finds 2 008 links it missed. The private
    #      parser is deleted; measure-remote.py now calls the library. THIS EXPLAINS cmu-shadow
    #      BEING EXACT -- it is a plain Apache autoindex, one row per line, the only case the old
    #      parser was built for.
    #   2. PAGE CAPS I SET MYSELF, and then discarded the warning by piping the run through
    #      `tail`. chipdb measured 1.68 GB at --max-pages 400 and 2.26 GB without a cap; sgidepot
    #      and seds-frommert were capped too. measure-remote.py has --log for exactly this.
    #   3. A SUBFOLDER MEASURED AS IF IT WERE THE ARCHIVE. fjkraan is the extreme case and the
    #      reason the header of ARCHIVES now argues about mount points: the candidate named
    #      .../comp/ibm6150/, which is 22 files and 593 kB. The archive is 2 832 files and 2.9 GB.
    #
    # WHAT THAT COSTS IF IT IS NOT FIXED: a candidate is judged on its size, and a size that is
    # low by 96x is the difference between "take it tonight" and "measure it first".

    # ============================================================ reconnaissance of 2026-09-26
    #
    # Aimed narrowly at SMALL archives of DOCUMENTATION AND DATASHEETS -- the category this
    # collection is thinnest in and the one that disappears most quietly, because a one-man PDF
    # page costs nobody anything to switch off. Every candidate below was fetched live rather than
    # read off a search result, and every robots.txt quoted here was re-read by hand afterwards.
    #
    # TWO FINDINGS WENT INTO DO_NOT_FETCH INSTEAD, and it is worth saying why here because the
    # reconnaissance argued the other way: www.hpmuseum.net and www.openpa.net both name ClaudeBot
    # with Disallow: /, and both would let an ordinary crawler through under their wildcard rule.
    # That is the argument this list already rejected for bitsavers.org -- arriving under another
    # name does not answer a control that names us. Both are worth an email; neither is worth a
    # crawl.
    #
    # AND ONE DIRECTION IS EXHAUSTED WITHOUT RESULT, which is worth as much as a find. Japanese,
    # Finnish, German and French queries for RS/6000, PS/2 and PowerPC documentation produced
    # NOTHING new -- not a thin result, an empty one; the Japanese searches returned PlayStation-2
    # manuals and PIC keyboard projects. If that ground is walked again it should be with a
    # different instrument, not the same queries. Separately, no open archive of IBM POWER1/POWER2
    # chip-level documentation appears to exist anywhere, and no scanned run of AIXpert, the AIX
    # Developers Magazine, could be found -- those are want-ads, not crawl targets.

    ("mcamafia", "http://www.mcamafia.de/", "~70 MB of PDF, 150-250 MB with ADFs",
     "Peter H. Wendt's one-man PS/2 site, frozen since 2003-2007. His OWN page-image scans -- "
     "explicitly not OCR'd -- of the PS/2 Hardware Interface Technical Reference including the "
     "Common Technical Oct-1990 release WITH a July-1992 extended DMA Controller Architecture "
     "section, the BIOS/ABIOS TR, the VGA/XGA/XGA-2 TRM, the 557-page PS/2 Server Hardware "
     "Maintenance Manual and the 3363 WORM TRM. No robots.txt (404); HTTPS is broken -- the cert "
     "is *.kasserver.com -- so HTTP only. THE ADFs ARE PROBABLY REDUNDANT against ardent-tool, "
     "which is held; it is the specific scan editions that look distinct, and that is a judgement "
     "rather than a measurement. Note the relation to the refused list: a partial mirror exists at "
     "mcamafia.retropc.se, whose sibling ibmfiles.retropc.se is refused. The mirror is off-limits; "
     "Wendt's original is a different operator and is not."),

    ("iommu-datasheets", "http://iommu.com/datasheets/", "MEASURED 83.86 GB total, ~1.7 GB wanted",
     "An anonymous but ACTIVELY CURATED nginx open directory of component datasheets -- "
     "scsi/qlogic touched 2026-09-23. The measurement is the useful part: 1 101 directories "
     "walked, 83.86 GB, but 78.8 GB of that is mirrors/ and the native archive is ~5.0 GB, of "
     "which x86/ alone is 2.86 GB. The slice this collection wants -- ppc, m88k, m68k, sparc, "
     "tokenring, scsi, vme, video, dsp, s390, pci, atm, uart, ata -- is ~1.7 GB. Holds the 604 "
     "ESP User's Reference Manual June 1996 and the PowerPC-AS Books 1/2/3, the Motorola "
     "EB162/163/164 engineering bulletins, and Tundra VME. No robots.txt. Overlap with bitsavers "
     "components/ is certain for the mainstream Motorola manuals. Its mirrors/ already holds "
     "datasheets.chipdb.org and www.vgamuseum.info, so taking this would partly subsume two other "
     "candidates -- but taking somebody's mirror rather than the origin is how you inherit their "
     "gaps, so prefer the origins while they still answer."),

    ("vgamuseum-doc", "https://www.vgamuseum.info/images/doc/", "unknown -- listing has no sizes",
     "THE BEST ANSWER FOUND TO THE GXT QUESTION, and A SUBTREE ONLY: the rest of the site is card "
     "photography. doc/ibm/ has GXT2000P/3000P/4000P/4500P/6500P/800P specifications and "
     "installation guides, ibm_vgaxga_trm2 and trm5, and the RS/6000 adapter-and-cable books "
     "SA38-0516 and SA38-0533. doc/techsource/ has 30 spec sheets for Raptor/GFX Sun cards that "
     "are essentially unarchived elsewhere. doc/nonpc/ has DEC ZLXp-E and ZLXp-L, TGA2, J300 and "
     "the AT and T Pixel Machine PXM900. robots.txt is stock Joomla and does not exclude "
     "/images/."),

    ("seds-frommert", "https://spider.seds.org/ps2/ps2.html", "small, well under 100 MB",
     "Hartmut Frommert's PS/2 and OS/2 pages on the Students for the Exploration and Development "
     "of Space volunteer server, sitting next to his Messier-catalogue work. He keeps LOCAL "
     "COPIES of documents whose originals died: the withdrawn Personal System Reference "
     "1992-1995, the PS/2 Hardware Maintenance Manual of MAY 1995 (S52G-9971-02) -- ardent-tool's "
     "copy is the OCTOBER 1994 edition -- and 9577i/9577s parts lists from IBM Germany, IBM "
     "Canada and IBM Direct USA snapshotted 05/05/97. robots.txt allows; it is a Drupal default. "
     "But the site carries a notice about fast spiders and threatens to block them, so throttle "
     "hard. A volunteer astronomy society hosting one member's 1990s computing hobby is exactly "
     "what does not survive a server migration."),

    ("cmu-shadow-ibmrt", "http://www.contrib.andrew.cmu.edu/~shadow/ibmrt/", "a few MB",
     "Derrick Brashear's IBM RT PC page, nothing modified since 1995, on a CMU contrib server "
     "still answering on Apache/2.2.16 (Debian) -- a decade past end of life. The full Mark "
     "Whetzel RT FAQ set: General, RT Hardware, IBM AOS, AIX Operating System in four parts, AIX "
     "Software in three, AIX Porting, AIX-specific Hardware. His own stated purpose is that they "
     "started to disappear from FTP sites. robots.txt allows. Fragments survive on archive.org; a "
     "consolidated live copy costs a few MB."),

    ("obsolyte", "http://www.obsolyte.com/", "unknown, a few hundred MB",
     "A one-man workstation site served, by its own front page, from a SPARC IPX running Red Hat "
     "6.0/UltraLinux with 64 MB of RAM. Newest item June 2006, still carrying 2006-era AdSense "
     "tags. sun3 through sun_ss10, sgi_iris through sgi_indy, next/, dec/multia -- his own "
     "teardown photography and hardware notes mixed with hosted vendor PDFs such as the "
     "SPARCstation 10 Service Manual 800-6358-11 Rev A. No robots.txt. The photography exists "
     "nowhere else by definition, and two of the four sites it links to are already dead."),

    ("sgidepot", "http://www.sgidepot.co.uk/index2.html", "unknown -- root returns an empty body",
     "Ian Mapleson's SGI/N64/FutureTech centre, including his own HTML re-typesetting of the "
     "Indigo2 and POWER Indigo2 Technical Report, Nov 1994. No robots.txt. THE RISK IS "
     "DEMONSTRATED RATHER THAN GUESSED: the page still advertises three mirrors of itself, and "
     "futuretech.blinkenlights.nl, the European one, no longer has an A or AAAA record at all. "
     "ftp.irixnet.org, which is held, is a software archive and carries none of his writing."),

    ("chipdb-datasheets", "https://datasheets.chipdb.org/", "unknown -- names only, no sizes",
     "About 75 manufacturer folders, nearly every one frozen at January or February 2008. The "
     "additive ones are likely Soviet/, Synertek/, Mostek/, Weitek/ and INMOS/Transputer/; the "
     "rest overlaps bitsavers components/ unpredictably. robots.txt contains NO User-agent or "
     "Disallow line at all -- only Cloudflare content-signals boilerplate reserving AI-training "
     "rights under EU DSM Art. 4, which reserves training and not archiving. Already partly "
     "inside iommu.com's mirrors/."),

    ("openpa", "https://www.openpa.net/",
     "TAKEN 2026-09-28 after the 2026-09-27 block slept off. Floor was 492 files, 47.80 MB",
     "Paul Weissmann's 160+ original PA-RISC and HP 9000 articles. IT STOOD IN DO_NOT_FETCH FOR "
     "AN HOUR ON 2026-09-26 and was taken out again: robots.txt names ClaudeBot with "
     "Disallow: /, and the owner's position -- correct -- is that this collection is mirror/1.0 "
     "fetching for preservation, not Anthropic's training crawler. See the note in DO_NOT_FETCH "
     "for why that is NOT the bitsavers case. "
     "WHAT SURVIVES THAT, AND IS NOT ABOUT ANY PARTICULAR CRAWLER: the WILDCARD rule. "
     "`User-agent: *` disallows /images/ and /systems/images/, which binds every crawler "
     "including this one -- and that is where the scans live. So the articles may be taken and "
     "the images may not. The EXCLUDE entry for that was written and then removed again, "
     "because an exclusion for an archive that does not exist is a dangling key; it goes back "
     "the moment this is fetched, as EXCLUDE[\"openpa\"] = (\"images/\", \"systems/images/\"). "
     "MEASURED 2026-09-27 with `measure-remote.py --exclude images/ --exclude systems/images/`, "
     "which is that wildcard group written in the measuring tool's own vocabulary: 177 pages, "
     "492 files, 47.80 MB, every size obtained by HEAD because the site states none. "
     "IT IS A FLOOR AND THE RUN WAS STOPPED RATHER THAN FINISHED. 44 pages were still queued "
     "when the host began answering with connection timeouts -- six in a row on /doc/ pages, "
     "WinError 10060. Stopped at once instead of retried, which is the standing lesson from "
     "dialectronics and vgamuseum: a host that stops answering is not asked harder. The delay "
     "was 0.5 s, too fast for a site this small; use 2-4 s next time. The true total is somewhat "
     "above 48 MB and the shape is already clear -- a few hundred hand-written articles, tiny. "
     "THEN THE FETCH FOUND THE COST OF THAT MEASUREMENT. Started 16:42 the same day at a 3 s "
     "interval with the wildcard exclusion in place, it drew a timeout on the VERY FIRST "
     "request -- `https://www.openpa.net/`, four attempts, WinError 10060 -- and ended with 0 "
     "files. A single polite probe four minutes later also timed out after 42 seconds. The host "
     "is not answering this machine at all. "
     "IT WAS REGISTERED AND THEN ROLLED BACK: the ARCHIVES entry, EXCLUDE, MIN_INTERVAL, the "
     "worker count and the B2 unit membership were all written before the fetch and all removed "
     "after it, and the empty archive directory -- which held nothing but the two bookkeeping "
     "files the failed run itself wrote -- was deleted. An archive that holds nothing is not an "
     "archive, and leaving it declared would put a phantom in every report. "
     "THE LESSON IS MINE AND NOT THE HOST'S. 0.5 s was too fast for a one-person site of a few "
     "hundred pages; the measurement took what it needed and cost the fetch. Before trying "
     "again: leave it alone for days rather than hours, probe ONCE with recheck-decisions.py, "
     "and if it answers use 4 s and a single connection. Everything needed to re-register is in "
     "this note -- the exclusion is EXCLUDE[\"openpa\"] = (\"images/\", \"systems/images/\")."),

    ("fjkraan-ibm6150", "http://www.vintagecomputer.net/fjkraan/comp/ibm6150/", "~40-50 MB",
     "Fred Jan Kraan's IBM PC RT pages as a guest subtree on Bill Degnan's site: board-by-board "
     "photography of a 6151 down to the ROMP card's MMI PALs, the mouse connector pinout for IBM "
     "part OOF2383 transcribed pin by pin, Megapel DIP-switch and 5081 monitor timings, and 23 "
     "IMD images of AIX 2.2.1 and VRM 2.2.1 media with per-disk part numbers. "
     "READ THE ROBOTS NOTE BEFORE CHOOSING A HOST: his OWN site, www.electrickery.nl, publishes "
     "Disallow: /.pdf and Disallow: *.pdf with Crawl-delay: 30, so the PDFs there are explicitly "
     "off-limits. vintagecomputer.net serves no robots.txt. Either take the guest copy or write "
     "to him -- he is an active cctalk regular."),
]

# Sources confirmed GONE, with no successor found. Recorded so that nobody spends an evening
# rediscovering an NXDOMAIN. A negative result is a result, and this list is the most useful thing
# the 2026-09-07 reconnaissance produced.
LOST = {
    "pware.hvcc.edu": "Hudson Valley Community College -- the real host behind the `pw@re` AIX "
                      "packages. NXDOMAIN. A Wayback snapshot exists (20130825203542, HTTP 200) "
                      "but could not be inspected, and an archive.org full-text search for "
                      "pware+AIX returns ZERO items. The same failure as bullfreeware, one step "
                      "further along -- and there, somebody uploaded the site the day it closed. "
                      "Here nobody did.",
    "www.spscicomp.org": "ScicomP, the IBM HPC user group. Its 1999-2015 proceedings carried the "
                         "XL C/C++ and XL Fortran compiler-internals talks -- probably the best "
                         "source on XL internals outside IBM. Now a parked placeholder.",
    "www-frec.bull.com": "the pre-bullfreeware.com Bull tree, named by the comp.unix.aix FAQ as "
                         "THE source of precompiled GCC for AIX. DNS resolves (129.185.32.216); "
                         "port 443 refuses and port 80 times out.",
    "support.bull.com": "Bull's AIX documentation portal, historically a full mirror of the IBM "
                        "AIX library plus the Escala manuals. Now a Salesforce login shell -- "
                        "three different doc paths return the identical 388 761-byte page.",
    "linuxppc.org": "HTTP 522 (Cloudflare front, origin unreachable). www.linuxppc.com NXDOMAIN. "
                    "Gary Thomas' users/gdt/redhat/RPMS/ppc/ archive is lost from its home.",
    "users.linpro.no/ingvar/43p/images/": "NXDOMAIN. Was the best collection of ready-made PReP "
                                          "BOOT IMAGES FOR THE RS/6000 43P. www.solinno.co.uk/"
                                          "7043-140/ (the E15 framebuffer patch) is now empty.",
    "tenox.pdp11.nu": "Antoni Sawicki's large one-person commercial-Unix archive. No longer "
                      "resolves.",
    "the.wall.riscom.net": "held the HTML edition of the PowerPC Compiler Writer's Guide inside "
                          "what the path implies was a whole processor-documentation tree. Does "
                          "not resolve.",
    "yellowdoglinux.com": "NO SURVIVING FTP TREE ANYWHERE. yellowdoglinux.com and "
                          "ftp.yellowdoglinux.com NXDOMAIN, fixstars.com/en/products/ydl/ 404. "
                          "About 25 mirrors checked and empty -- mirrorservice.org, "
                          "ftp.acc.umu.se, mirror.aarnet.edu.au, ftp.tu-chemnitz.de, "
                          "ftp.heanet.ie, mirror.switch.ch, ftp.icm.edu.pl, ftp.gwdg.de, "
                          "ftp.uni-erlangen.de, ftp.fu-berlin.de, ftp.jaist.ac.jp, ftp.riken.jp, "
                          "ftp.iij.ad.jp, mirror.yandex.ru, ftp.osuosl.org, ftp.uni-stuttgart.de, "
                          "ibiblio and more. Survives only as scattered ISO uploads.",
    "publibn.boulder.ibm.com": "IBM's own AIX documentation host. Dead, as is publibfi.",
    "www.rootvg.net / www.aixmind.com / ppckernel.org / mach-linux.org / gd.tuwien.ac.at":
        "all DNS-dead or refusing. Recorded together because each was checked and none is worth "
        "its own paragraph.",
}

# AN ARCHIVE BELONGS HERE WHEN SOME OF ITS DIRECTORY URLS RETURN A DOCUMENT RATHER THAN A
# LISTING -- not only when the whole site is hand-written. A mixed tree needs it just as much,
# and that case is easy to miss because the archive looks like a plain autoindex from the root.
#
# zx-gatekeeper-dec ADDED 2026-09-10, after the first run had already reported COMPLETE with
# 8 674 files and zero failures. gatekeeper.dec.com's own Index-byname named 3 972 files under
# /pub/DEC/ and 473 of them were absent; every one HEADed 200 on the source, so they had not
# been withdrawn, we simply never asked.
#
# The cause: `.../SRC/technical-notes/SRC-1997-003-html/` does not serve an index page, it
# serves THE PAPER. parse_listing() dutifully read a research paper as a directory listing and
# extracted the three figures it links with <a href>, missing the ones it embeds with <img src>
# -- and, worse, never saved the paper itself, because outside HTML_CRAWL a directory body is
# parsed and discarded. TWELVE SRC papers were held as figures with no text.
#
# Checked before switching it on: on a REAL listing here, images=True yields the server's own
# /icons/*.gif, and every one of those resolves outside base_url and is dropped by producer().
# Nine real entries kept, five icons refused.
HTML_CRAWL = {"adoxa-dos", "develooper-hpux", "crashing-org", "crashing-org-www", "crashing-org-kernel", "dialectronics", "technologists-sauer", "technologists-dellunix", "giga-nl-walter", "ardent-tool", "gsi-collection", "typewritten", "techsysadm",
              "infania-tl1", "infania-tl2", "damage-rt", "os2bbs",
              # ADDED 2026-09-28 AFTER A FETCH WITHOUT IT reported 122 files and COMPLETE over a
              # tree measured at 492. See the note beside ARCHIVES["openpa"]: the front page is
              # all relative links and every page under systems/ is not.
              "openpa",
              # A GENERATED INDEX THAT SPELLS OUT ITS OWN HOST, which is an unusual combination
              # and the reason this entry is not optional. MBSE writes every file link as
              # `http://www.dreamlandbbs.com/gfd/<area>/<file>`, and is_child_link drops a
              # fully-qualified href unless allow_up is set. MEASURED on one area page: 2 links
              # found without this, 91 with it. A run without it would report two links per page
              # and look exactly like a run that had worked.
              "dreamlandbbs-os2",
              "infania-solaris", "infania-os-history", "infania-unixos2",
              "zx-gatekeeper-dec",
              # A FRAMESET SITE IS NECESSARILY ONE OF THESE. FRAME_RE finds topic.html and
              # main_page.html on transputer.classiccmp.org, but a page is only WALKED when
              # html_crawl is set -- so the first run after that fix fetched the two frames
              # and stopped, 2 files over a 1.72 GB archive. Finding a link and following it
              # are two different switches, and fixing one without the other buys nothing.
              "transputer-classiccmp",
              # A CMS whose pages ARE the navigation: /archives/ links /archives/software/
              # dg.aviion and so on, and each of those is another page to open, not a
              # directory to list.
              "novasareforever-aviion",
              # Its pages live inside their directories and link each other; the seeds open
              # the directories, this walks the pages. NOTE its pages are .phtml -- see
              # HTML_PAGE, which did not know that extension and so walked none of them.
              "sun3arc",
              # A hand-written museum page. Left out of this set at first because its 264 links
              # were all reachable from the directory listings anyway -- which was true, and
              # missed the point: membership here also decides whether <img src> is followed,
              # and the nine Apollo logo variants exist ONLY as embedded images. On a
              # hand-written site the pictures ARE content.
              "apollo-clavius",
              # 95 076 files and 332 GB make this LOOK like a plain tree, and its root is a
              # hand-written page with a Google search box. Both, in different subtrees -- so it
              # was crawled as a tree and 2 450 embedded images were never followed, most of them
              # Louis Ohland's photographs under ohlandl/PS55, ohlandl/docs and ohlandl/RS6000.
              #
              # MEASURED 2026-09-11 rather than argued: ohlandl/PS55/, ohlandl/RS6000/,
              # ForAIX/Firefox/ and AIXtip/ all answer 200 with hand-written pages and NO
              # autoindex sort links; ohlandl/docs/ answers 403 and cannot be listed at all.
              # AIXtip/images/ IS a real autoindex -- and holds 0 files here, because the only
              # thing that ever names it is `<img src="images/aixtipshead.gif">` on the page
              # above it. A directory nothing links is a directory nothing finds.
              "ps-2.kev009.com",

              # 2026-09-13. All three were checked before being listed, not assumed: their base
              # pages carry ordinary <a href> links and no autoindex markers. somuchstuff-pdp8
              # additionally needs the crawler's page test to know .php -- it does, in
              # common.DOCUMENT_EXTENSIONS, which is where that story is now written down.
              "somuchstuff-pdp8", "bretjohnson", "abc-bladet",

              # 2026-09-26. Hand-written HTML 4.01 from 2003, no autoindex anywhere on the host:
              # every page is both a file to keep and the only way to the next one. Its sibling
              # candidate vgamuseum-doc is deliberately NOT here -- that one IS a generated
              # index, and adding it would cost a second request per directory for nothing.
              "mcamafia",

              # 2026-09-26, all four checked rather than assumed: hand-written pages, no
              # autoindex markers anywhere on the host. chipdb and iommu are deliberately absent
              # -- both are generated indexes, and listing them would cost a second request per
              # directory for nothing.
              "sgidepot", "obsolyte", "fjkraan", "cmu-shadow", "seds-frommert"}

# Refuse to fetch below this much free space. Set to 1 GB by the owner on 2026-09-06, down from
# the 8 GB the fsck.technology runs used -- his disk, and the number that matters is small: the
# checksum index for a 21 000-file archive is a few MB, so 1 GB still leaves room to record what
# was taken. What it does NOT leave is room for the next large file to land, so a run that hits
# this floor will stop with the archive INCOMPLETE rather than part-written.
_disk_floor_hit = False

# --- DEFERRED: measured, wanted, waiting on disk ---------------------------------------------
#
# Everything below was MEASURED on 2026-09-03 (method and full numbers in this file, under CANDIDATES; there is no CANDIDATES.md and never was) and is
# not here because it did not fit. A larger disk is expected. When it arrives, this is the
# work-list -- in this order, because the first two are the only ones whose value is established.
#
# The measurements are the point. Every figure in this block is a sum of observed byte counts,
# not an estimate; the round that produced them exists because the previous round's estimates
# were wrong by 3x, 10x and 40-100x in three separate places. Do not replace these with fresh
# guesses -- re-measure or use what is written down.
#
# 1. ftpmirror.infania.net/sites -- SELECTED SUBTREES ONLY, never the whole thing.
#    Measured floor 324.09 GiB across 59 of 97 subtrees (FTP `LIST -R` gives exact per-file
#    sizes in one request -- that is the method, there is no ls-lR on this host). With its
#    bitsavers mirror it is ~2.2 TB.
#      - bitsavers/ (~85% of the tree): DO NOT TAKE. Already mirrored here properly via
#        rsync.mirrorservice.org, and the mirrored index page carries bitsavers' own notice,
#        April 2026: "Wget is no longer permitted here ... People are downloading the ENTIRE
#        site through the web interface." Taking it again over HTTP would be exactly what that
#        asks people to stop doing. rsync module `bitsavers` is the sanctioned path if ever
#        needed.
#      - 38 of 97 subtrees were never measured; aminet.net, modland and guru3d are plausibly
#        multi-GB. No range is given for them because there is no basis for one.
#      - 14 subtrees are LOWER BOUNDS: the FTP server caps `LIST -R` at exactly 10 000 entries.
#        Verified, not assumed -- 13 of the 14 returned files+dirs == 10000 exactly.
#      - AIX RELEVANCE IS UNESTABLISHED and is the thing to settle first. The old "20-60 GB"
#        estimate was extrapolated from ftp.leo.org, measured here at 1.79 GiB -- and leo.org is
#        an OS/2 archive whose `unix` directory holds 12 files. Do not repeat that shape of
#        error: identify the AIX-relevant subtrees BEFORE sizing anything.
#
# 2. public.dhe.ibm.com/rs6000/ -- 25.25 GiB measured (662 HEADs = 99.1% of bytes).
#    BLOCKED ON A DECISION, not on space. The host itself injects into every autoindex page
#    "The content on this page is publicly available information. The directory structure is
#    accessible and traversable by design." and serves no robots.txt. IBM's corporate terms say
#    "You may not mirror any of the content from this site on another Web site or in any other
#    media", scoped to "ibm.com and any related IBM websites". Two statements from one operator
#    that contradict each other. `aix.software.ibm.com` is ALREADY mirrored here under the same
#    banner, so whichever way this goes, the two should agree. Owner's call. (An earlier version pointed at a CANDIDATES.md that does not exist.)
#
# 3. fsck.technology -- the ~39.7 GB deliberately left behind. AIX 4.3.3, 5.2 and 5.3 media,
#    duplicates of releases already held. Only worth taking if the goal becomes completeness of
#    that host rather than of the collection.
#
# NOT DEFERRED -- MEASURED AND REJECTED. Do not re-propose these; the reason is not size.
#   minuszerodegrees.net  12.42 GB, and ZERO files matching aix, RS/6000, 70xx, PowerPC, Micro
#                         Channel or any PS/2 model number, across all 7 099 enumerated paths.
#                         An excellent IBM PC/XT/AT site. Wrong collection.
#   heha.fwh.is           Not enumerable: no directory index, and /sitemap.php -- the site's own
#                         page list -- returns the free-host interstitial. 15 files served real
#                         content, 59 551 bytes total, all CSS/JS/icons.
#   csiph.com (bulk)      Not a file archive; an NNTP server. The 8 532-file `timc` tree that
#                         made it a candidate 404s everywhere, including in all 7 Internet
#                         Archive captures of it. The gallery WAS taken -- see `csiph-gallery`.

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
        # module root has 28 directories, not 6, and `mirrors/` alone is 44.9 GB in ten files,
        # five of them .tar. A filter that names what it excludes rather than what it includes
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

            # THE SECOND RULE, AND ITS REASON. 2026-09-07.
            #
            # /mirrors/ holds ten files: five .tar and the `tar -t` manifest of each. The tars are
            # not documents but PACKAGING -- each wraps a crawl of a website or FTP server that is
            # now dead, made by somebody else years ago as a convenience. bitsavers would never
            # have been asked for these sites as tarballs; the tar is a box, not the thing in it.
            #
            # Their contents are being unpacked into archives of their own -- `agilent-ftp-2009`
            # is the first, on 2026-09-07 -- because a closed tar is invisible to everything here:
            # no checksum index, no duplicate analysis, no HTML-imposter scan, and a search has to
            # open a 36 GB file to answer any question.
            #
            # THESE LINES MUST EXIST BEFORE ANY OF THOSE TARS IS DELETED. This mirror runs with
            # delete=False, so rsync treats a missing local file as one to fetch again: removing
            # the 36 GB ftp.digital.com tar without its exclude means downloading it once more on
            # the very next refresh.
            #
            # NAMED ONE BY ONE RATHER THAN `--exclude=/mirrors/`. Two reasons. The .txt manifests
            # must keep coming: they are Al Kossow's own listing of each tar, made years ago on
            # another machine, and they are the independent record every extraction is verified
            # against -- the agilent tree matched its manifest at 1 016 entries with zero
            # differences, and that check is worth more than the 4.7 MB it costs. And a sixth tar
            # appearing upstream should arrive and be noticed, not be silently excluded by a rule
            # written for five files that existed in 2026.
            #
            # The cost, stated plainly: these five names will never be refreshed again. Upstream
            # replacing one with a better capture would go unseen. That is a hole in the mirror,
            # and it is in writing here rather than in somebody's memory.
            "--exclude=/mirrors/ftp.agilent.com_CDs_20091212.tar",
            "--exclude=/mirrors/ftp.digital.com_20060831.tar",
            "--exclude=/mirrors/h18002.www1.hp.com_20080527.tar",
            "--exclude=/mirrors/h71000.www7.hp.com_20080527.tar",
            "--exclude=/mirrors/www.hpl.hp.com_20070827.tar",
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


# ---------------------------------------------------------------- deliberately removed files
#
# Files that WERE in a mirror, were taken out on purpose, and must not come back.
#
# NOT THE SAME THING AS DO_NOT_FETCH, and the difference is who decided. DO_NOT_FETCH records an
# OPERATOR'S refusal -- robots.txt, terms, an explicit request -- and is binding on us. This
# records OUR OWN decisions, and its whole purpose is to stop a later run from silently undoing
# one.
#
# NOT THE SAME THING AS EXCLUDE either. That names subtrees never taken. These were taken,
# unpacked into archives of their own, and then removed; the bytes are still in the collection,
# under a different name, indexed and verified. Re-fetching would restore a duplicate of something
# already held -- 82.7 GB of it, in the case below.
#
# WHY IT HAS TO BE MECHANICAL. The five bitsavers tars are covered by --exclude lines in RSYNC[],
# because rsync has a filter and rsync runs with delete=False, so a locally missing file is one it
# fetches again. `fsck-vendors` has no such mechanism: it is fetched by a URL-list tool that skips
# files already present, which means a deleted file is one it downloads again. Until this list
# existed, the only protection there was a sentence in a comment, and a sentence does not stop a
# script at three in the morning.
#
# HOW TO USE IT. Every fetching tool should ask before writing:
#
#     if is_retired(archive_name, relative_path):
#         continue
#
# `retired_urls(archive_name, base_url)` gives the same answer as a set of absolute URLs, for
# tools that work from a URL list rather than from paths.
#
# Paths are relative to the archive root, with forward slashes, exactly as they appear in
# .sha256sum.
RETIRED = {
    # THE 24 SMALL CONTAINERS OF THE bullfreeware ITEM, unpacked in place on 2026-09-12 and
    # then deleted. Their contents are in this archive under the same names minus the suffix --
    # 44 files, 10 278 752 bytes -- and every one was verified BY CONTENT before its container
    # went: CRC32 from the zip header for zip members, SHA-256 over the decompressed stream for
    # gzip. A size match was not accepted as proof; the extraction had already reported one.
    #
    # WITHOUT THESE ENTRIES the next refresh of the item fetches all 24 back, and it would look
    # like a clean run: fetching a file the item's own manifest lists is precisely what
    # ia-item-fetch.py is for. That tool learned to read this list on 2026-09-12; before then it
    # did not, which is why this is the first archive here to need it.
    #
    # THE GROUPE BULL AIX TOOLBOX FOR AIX 4.3, unpacked in place on 2026-09-13 and then removed.
    # The archive had consisted of exactly two files, both containers -- half a gigabyte opaque to
    # every tool here. It now holds 278 files.
    #
    # Verified BY CONTENT before either was deleted: each member decompressed in the stream and
    # its SHA-256 compared with the file on disk. 260 identical and 11 identical, 0 differing,
    # 0 absent. Sizes had already matched, and a size match is not a content match.
    #
    # THE EVIDENCE IS WEAKER HERE THAN FOR ia-bullfreeware, which belongs in the record rather
    # than in a footnote. Bull shipped 00_MD5.txt inside the tar, but it is OLDER THAN THE
    # DIRECTORY IT SITS IN: 140 of 260 confirmed, 11 same-name-different-bytes, 31 named and
    # absent. Updates.txt, also inside, is a changelog to September 2001 whose first entry adds
    # webmin-0.88.0.0.exe while the manifest still names 0.81. Bull kept updating the toolbox
    # without regenerating the manifest, so the independent confirmation covers 140 of 260 and
    # not 11 884 of 11 884.
    #
    # What carries the deletion instead: the Internet Archive's own MD5 for the container as
    # served, the tar's table of contents for the 260 sizes, and the stream comparison for the
    # 260 contents. The item is still online.
    "ia-bull-toolbox-43": (
        ("toolbox.aix43.tar.gz",
         "529 507 298 B. Unpacked 2026-09-13 -> toolbox.aix43/ in this archive, 260 files, each "
         "confirmed byte-identical in the stream before the container went. SHA-256 "
         "e1a5b2cdd78df0a3742894acc48b8b9eefc49cc975196326426c35122aee445a"),
        ("htmlfiles.tar.gz",
         "18 857 B. Unpacked 2026-09-13 -> htmlfiles/ in this archive, 11 files, all confirmed "
         "byte-identical. It carried its own top-level directory, so no prefix was needed. "
         "SHA-256 3ba83bf26bd9eb1e8a21ceaf65c0227708e14aa6d16cdbc0f210750fdbbb00f7"),
    ),

    "ia-bullfreeware": (
        # THE 85 GB ONE. Unpacked 2026-09-12 into packages/ inside this same archive -- 11 884
        # files, 85.04 GB -- and deleted afterwards. This is the only entry in RETIRED for which
        # NO LOCAL COPY OF THE CONTAINER WAS KEPT, because 85 GB does not fit anywhere to keep it,
        # so the evidence has to stand on its own:
        #
        #   11 884 of 11 884 files match packages.sfv -- CRC32 written by RHash v1.4.0 on
        #   2022-02-28, at the origin, before the upload. An INDEPENDENT party and a different
        #   algorithm from the MD5 the Internet Archive served the download under. 11.9 minutes
        #   of reading, 0 mismatched, 0 missing.
        #
        #   11 884 sizes matched the tar's own table of contents during extraction, 0 wrong.
        #
        #   The container itself is recorded rather than kept: SHA-256
        #   c5384ece67eb00cf57b554d70148303370bb89e65b0290def482f5fc8125f936, CRC32 37CDDCAF
        #   (packages.tar.sfv, also 2022-02-28), size 85 045 125 120 bytes exactly.
        #
        # WHAT WAS GIVEN UP, stated plainly: the tar AS AN OBJECT. This collection can no longer
        # demonstrate that a file with that CRC32 was here -- only that its contents are. The
        # item is still on archive.org, and the figures above would identify a fresh copy.
        ("packages.tar",
         "85 045 125 120 B. Unpacked 2026-09-12 -> packages/ in this archive, 11 884 files, "
         "every one verified against packages.sfv (CRC32, RHash 2022-02-28). Re-fetching it "
         "would download 85 GB of content already held, indexed and independently verified."),

        # A SECOND CONTAINER, FOUND INSIDE THE FIRST. packages/SRPMS.tar.gz is 18 899 559 881 B --
        # bullfreeware's own downloadable snapshot of its source tree, shipped alongside the tree
        # itself. It looked like an obvious duplicate and was not: 1 862 members against 2 382
        # files in SRPMS/, so the snapshot was the SMALLER copy, and a smaller copy can still hold
        # something the larger one lost.
        #
        # It did. Compared member by member IN THE STREAM -- decompressed in memory and hashed,
        # nothing written, no 18.9 GB of scratch -- 1 858 were byte-identical, 0 differed, and
        # FOUR WERE ABSENT FROM THE TREE ENTIRELY:
        #
        #     SRPMS/openldap/openldap-2.4.35-1.src.rpm    5 467 685
        #     SRPMS/protobuf/protobuf-2.4.1-1.src.rpm     1 770 120
        #     SRPMS/redis/redis-2.6.16-1.src.rpm          1 010 698
        #     SRPMS/snappy/snappy-1.1.0-1.src.rpm         1 611 221
        #
        # Source RPMs bullfreeware withdrew between rolling the snapshot and the day the site was
        # captured. 9.86 MB, inside 18.9 GB, and NONE OF THE FOUR IS NAMED IN packages.sfv --
        # that manifest describes the site as it was captured, and by then they were gone. They
        # were written into SRPMS/ first, each verified by size and SHA-256 and read back, and
        # only then was the snapshot re-compared: 1 862 of 1 862 identical, 0 absent.
        #
        # THE COST OF REMOVING IT IS A PERMANENT FOOTNOTE, not a loss: packages.sfv names
        # `packages/SRPMS.tar.gz` on its very first line, so every future run of sfv-verify.py
        # would have reported one file MISSING for ever. That is why sfv-verify.py now reads this
        # list and prints RETIRED instead -- an alarm that fires on schedule is an alarm people
        # stop reading.
        ("packages/SRPMS.tar.gz",
         "18 899 559 881 B. bullfreeware's own snapshot of its SRPMS tree, deleted 2026-09-13 "
         "after all 1 862 members were confirmed byte-identical to files in packages/SRPMS/. "
         "Four of them existed ONLY here -- openldap 2.4.35, protobuf 2.4.1, redis 2.6.16, "
         "snappy 1.1.0 -- and were rescued into SRPMS/ BEFORE the deletion. They are absent from "
         "packages.sfv, which describes the site as captured and no longer had them."),
        ("Bullfreeware_Closing_chocr.html.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Closing_chocr.html"),
        ("Bullfreeware_Closing_hocr_pageindex.json.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Closing_hocr_pageindex.json"),
        ("Bullfreeware_Closing_hocr_searchtext.txt.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Closing_hocr_searchtext.txt"),
        ("Bullfreeware_Closing_jp2.zip",
         "unpacked in place 2026-09-12 -> Bullfreeware_Closing_jp2/"),
        ("Bullfreeware_Contact_chocr.html.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Contact_chocr.html"),
        ("Bullfreeware_Contact_hocr_pageindex.json.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Contact_hocr_pageindex.json"),
        ("Bullfreeware_Contact_hocr_searchtext.txt.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Contact_hocr_searchtext.txt"),
        ("Bullfreeware_Contact_jp2.zip",
         "unpacked in place 2026-09-12 -> Bullfreeware_Contact_jp2/"),
        ("Bullfreeware_Home_chocr.html.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Home_chocr.html"),
        ("Bullfreeware_Home_hocr_pageindex.json.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Home_hocr_pageindex.json"),
        ("Bullfreeware_Home_hocr_searchtext.txt.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Home_hocr_searchtext.txt"),
        ("Bullfreeware_Home_jp2.zip",
         "unpacked in place 2026-09-12 -> Bullfreeware_Home_jp2/"),
        ("Bullfreeware_Howto_chocr.html.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Howto_chocr.html"),
        ("Bullfreeware_Howto_hocr_pageindex.json.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Howto_hocr_pageindex.json"),
        ("Bullfreeware_Howto_hocr_searchtext.txt.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_Howto_hocr_searchtext.txt"),
        ("Bullfreeware_Howto_jp2.zip",
         "unpacked in place 2026-09-12 -> Bullfreeware_Howto_jp2/"),
        ("Bullfreeware_News_chocr.html.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_News_chocr.html"),
        ("Bullfreeware_News_hocr_pageindex.json.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_News_hocr_pageindex.json"),
        ("Bullfreeware_News_hocr_searchtext.txt.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_News_hocr_searchtext.txt"),
        ("Bullfreeware_News_jp2.zip",
         "unpacked in place 2026-09-12 -> Bullfreeware_News_jp2/"),
        ("Bullfreeware_TOS_chocr.html.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_TOS_chocr.html"),
        ("Bullfreeware_TOS_hocr_pageindex.json.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_TOS_hocr_pageindex.json"),
        ("Bullfreeware_TOS_hocr_searchtext.txt.gz",
         "unpacked in place 2026-09-12 -> Bullfreeware_TOS_hocr_searchtext.txt"),
        ("Bullfreeware_TOS_jp2.zip",
         "unpacked in place 2026-09-12 -> Bullfreeware_TOS_jp2/"),
    ),
    "fsck-vendors": (
        ("NeXT/next.68k.org Archive/next.68k.org.tar",
         "37.86 GB. Unpacked into the `next-68k-org` archive on 2026-09-07 -- 234 760 files, "
         "verified three ways. THIS ARCHIVE HAS NO OTHER PROTECTION: it is fetched by a URL-list "
         "tool, so without this entry the next refresh downloads 37.86 GB of a tar whose contents "
         "are already here."),
    ),
    # Also covered by --exclude lines in RSYNC["bitsavers"]["filter"]. Listed here as well so that
    # ONE place answers "what did we remove, and why" for the whole collection -- and so that a
    # future tool which is not rsync inherits the answer without anyone remembering to tell it.
    "bitsavers": (
        ("mirrors/ftp.agilent.com_CDs_20091212.tar", "2.47 GB -> agilent-ftp-2009, 2026-09-07"),
        ("mirrors/h18002.www1.hp.com_20080527.tar", "1.06 GB -> hp-alphaserver-2008, 2026-09-07"),
        ("mirrors/h71000.www7.hp.com_20080527.tar", "1.30 GB -> hp-openvms-2008, 2026-09-07"),
        ("mirrors/www.hpl.hp.com_20070827.tar", "3.99 GB -> hp-labs-2007, 2026-09-07"),
        ("mirrors/ftp.digital.com_20060831.tar", "36.05 GB -> dec-ftp-2006, 2026-09-07"),
    ),
}


def is_retired(archive, rel):
    """-> the reason this path was removed, or None. `rel` uses forward slashes.

    Matching is exact and case-insensitive. Exact rather than prefix: a retired file is a decision
    about ONE file, and a prefix rule here would quietly grow into an EXCLUDE without anyone
    choosing that.
    """
    rel = comparable_path(rel)
    for path, why in RETIRED.get(archive, ()):
        if comparable_path(path) == rel:
            return why
    return None


def retired_urls(archive, base_url):
    """-> {absolute url: reason} for tools that work from a URL list rather than from paths.

    Each path segment is quoted the way a server would serve it, so a name with spaces -- and
    `NeXT/next.68k.org Archive/` has one -- matches the URL a list actually contains.
    """
    out = {}
    for path, why in RETIRED.get(archive, ()):
        quoted = "/".join(urllib.parse.quote(p) for p in path.split("/"))
        out[base_url.rstrip("/") + "/" + quoted] = why
    return out


def retired_report():
    """-> a human-readable summary. Used by catalogue.py so the removals appear in the catalogue."""
    lines = []
    for archive, items in sorted(RETIRED.items()):
        for path, why in items:
            lines.append("%s/%s -- %s" % (archive, path, why))
    return lines

# Subtrees skipped by name, relative to the archive's base URL. THREE ENTRIES as of
# 2026-09-10 -- ardent-tool, crashing-org, zx-microway. This line read "Empty today" for three
# days after the first was added, which is how long it takes a comment to start lying. Kept
# because the
# mechanism is the difference between "we took the whole branch" and "we took the branch minus
# the one directory that was bigger than everything else in it".
# Subtrees not to descend into, matched against the path below the archive's base URL.
#
# `mirror.py` does not read robots.txt -- it walks what a page links, and an operator's wishes
# live in a file it never opens. Where a site publishes one, its Disallow rules belong here by
# hand. ardent-tool.com allows everything except `/incoming/*`; that directory was never reached
# on 2026-08-26 because nothing links to it, which is luck rather than compliance.
# ftp.oldskool.org/pub/drivers/ -- 344 vendor directories, 71 916 files, 292.38 GB measured in
# full on 2026-09-20 (no directory truncated; 49 listings unreadable, 960 files without a size).
# The per-vendor figures are in `drivers-measure-2026-09-20.tsv` beside this file.
#
# EVERYTHING IS FETCHED EXCEPT WHAT IS NAMED BELOW. The first cut ran the other way -- a
# positive list of 103 chosen vendors -- and it was dropped on 2026-09-20. A positive list has
# to be revisited every time the site grows, and it buys little: 304 of the 344 vendors hold
# less than 1 GB each, 29 GB together. Taking that tail unexamined is cheaper than judging it,
# and the tail is where the rare hardware sits.
#
# The rule: out goes what a machine old enough to need emulation never had. A modern brand goes
# whole; a vendor that spans both eras loses only its modern directories.
#
# 122.7 GB of 292.38 GB (42 %) remain. Against the positive list the convenience costs about
# 63 GB -- the price of not judging two hundred small vendors one at a time.
#
# NOTHING HERE WAS TYPED BY HAND. Every name was read back from the live listing on 2026-09-20
# and checked to exist, because EXCLUDE matches the ENCODED path and a misspelling excludes
# nothing while reporting success.

DRIVERS_OUT = (
    # Modern brands, whole. 82.17 GB together.
    'KATT/',                   # 21.98 GB, a single directory "KATT Games Master Keyboard",
                               #          dated October 2025 -- 22 GB for a keyboard means
                               #          game images, not drivers
    'LG/',                     # 13.83    a 2017 monitor, two 2018 OLED TVs, DVD/BD burners
    'AOOSTAR/',                # 11.57    one directory, "N1 PRO N150" -- Intel N150, 2024
    'Gigabyte/',               # 11.43    B450 AORUS, Z370, Z690, GTX 1070
    'MSI/',                    #  7.37    Z690, B350, Afterburner; the oldest is a 1999 board
    'Blackmagic%20Design/',    #  3.43    video production
    'Insta360/',               #  2.54    action cameras
    'Samsung/',                #  2.52    990 Pro SSD, washing machines, dishwashers, Galaxy Tab
    'EVGA/',                   #  2.29    modern graphics cards
    'Atomos/',                 #  1.51    video recorders
    'Google/',                 #  1.31    Pixel
    'x-rite/',                 #  1.30    colour calibration
    'USB-AVCPT%20video%20DVD%20maker/',   # 1.09   USB capture
)

DRIVERS_OUT_SUB = (
    # Vendors that span both eras: the modern part only. ~87.5 GB together.

    # Dell, 34.30 GB. What stays: 210, 316LT, 316SX -- 386 laptops from 1989 -- and GXpro.
    'drivers/Dell/Dimension%204700/',
    'drivers/Dell/Inspiron%2013%207368%202-in-1/',
    'drivers/Dell/Inspiron%2015R%20N5110/',
    'drivers/Dell/Inspiron%2015R%20SE%207520/',
    'drivers/Dell/Inspiron%20400/',
    'drivers/Dell/Inspiron%207368/',
    'drivers/Dell/Precision%20470/',
    'drivers/Dell/Studio%201555/',
    'drivers/Dell/T110/',
    'drivers/Dell/T1600/',
    'drivers/Dell/Unknown%202003%20computer/',

    # nvidia, 15.19 GB -- and only 0.65 GB of it is old, but that 0.65 GB is the point:
    # NV1 (1995), win3.1, Win9x, 98, and `older_drivers` with 1 873 files. Those stay, along
    # with the 54 loose XP-era driver .exe in the vendor root. These eight go, 12.04 GB:
    'drivers/nvidia/Vista64_7_8/',        # 3.44 GB
    'drivers/nvidia/GT%20730/',           # 1.93
    'drivers/nvidia/win2kxp/',            # 1.70
    'drivers/nvidia/personal/',           # 1.51
    'drivers/nvidia/Windows%2010/',       # 1.39
    'drivers/nvidia/WinXPx64/',           # 1.11
    'drivers/nvidia/Linux/',              # 0.67
    'drivers/nvidia/broadcast/',          # 0.29

    # HP, 12.19 GB. What stays: 200LX (the palmtop), Colorado Tape, LaserJet 4L / 4ML / 5P,
    # Voodoo, and the small Laserjet 1000.
    'drivers/HP/HP%20Pavillion%20p6000/',
    'drivers/HP/Z2%20Mini%20G4%20workstation/',
    'drivers/HP/HP%20Scanjet%203970/',
    'drivers/HP/LP2475w/',

    # Compaq, 9.42 GB, and it is one block: 14 357 files in twenty numbered SoftPaq ranges,
    # sp0000 to sp10000, evenly sized, so no cut inside it separates old from new. They are
    # Compaq system updates for Deskpro and Presario up to about 2001 -- no device in them is
    # one an emulator offers. Deskpro, Portable and Portable III stay: 24 files.
    'drivers/Compaq/Softpaq%20files%20(partial)/',

    # Fujitsu, 9.59 GB -- modern scanner software. `M2551A` stays.
    'drivers/Fujitsu/ScanSnap%20SV600/',
    'drivers/Fujitsu/ScanSnap%20ix500/',
    'drivers/Fujitsu/fi-5530C2/',

    # Matrox, 8.68 GB. `RT Series` is the RT2000/RT2500 video-editing cards of 2000-2002, and
    # m3D, Marvel G200, Mystique and Millennium I stay, ~2.97 GB.
    #
    # NARROWED 2026-09-22, AND THE REASON IS WHY THE 5.71 GB WAS A FLOOR. The 2026-09-20 survey
    # could not finish measuring `RT Series/` and excluded it whole. Walked properly it is not one
    # tree but twelve, and two of them are graphics cards, not video editing:
    #
    #     MGA_MILL/            56 files      5.9 MB   Millennium
    #     G400FLEX/            11 files      9.2 MB   G400
    #     ------------------------------------------- kept, 15.1 MB
    #     RTX.100/            523 files   3687.7 MB
    #     RT2000/             158 files    874.5 MB
    #     RTX100XtremePro/      5 files    587.6 MB
    #     dvdit/                3 files    431.0 MB
    #     Premiere Upgrade/     3 files    355.5 MB
    #     utilities/, PROPack/, documentation/, misc/, VFW/   18 files    55.2 MB
    #     ------------------------------------------- out, 6.0 GB
    #
    # The exclusion named a DIRECTORY and the directory's name described only part of what was
    # under it -- the same shape as `Miscellaneous` and `unsorted`, which were nearly dropped for
    # reading like leftovers.
    #
    #   AND THEN THE TWO KEPT BRANCHES TURNED OUT TO BE COPIES. Fetched 2026-09-22, 70 files,
    #   17.0 MB. Hashed against the archive's own index afterwards: 68 of them were ALREADY HERE,
    #   under `drivers/unsorted/MATROX/`, at the SAME relative paths -- G400FLEX 11 of 11,
    #   MGA_MILL 56 of 56. That tree holds 204 files and 139.6 MB and is a near-superset: 66 of
    #   the 68 distinct contents, plus 89 more. The whole exercise gained TWO files, 1.88 MB:
    #   `PCILatencyTool31-[Guru3D.com].exe` and `matrox_pci_optimizer.zip`.
    #
    #   TWO MISTAKES PRODUCED THAT, and both are cheap to avoid. First, the evidence for "not
    #   redundant" was `1677_412.EXE` at "1 677 721 bytes remote against 1 657 522 local". The
    #   two files are byte-identical; 1 677 721 is int(1.6 * 1024**2), the LISTING's rounded
    #   "1.6M" -- the exact trap the resume path warns about at the Content-Length check. Second,
    #   the local search was scoped to `drivers/Matrox/` because the question was about Matrox.
    #   The right scope is the whole archive by content, and .mirror-index.csv had all 77 558
    #   hashes ready to answer it in one pass.
    #
    #   The rule below is still right -- it keeps 6.0 GB of video-editing software out and
    #   describes the tree as it is. Its JUSTIFICATION was wrong, and that is what this note
    #   corrects. R2 keeps the 68 duplicates where they are: nothing inside a mirror is deleted
    #   as a duplicate, not even one we created ourselves.
    #
    # THIS RULE FAILS OPEN AND THE OLD ONE FAILED CLOSED. Ten names instead of one means a
    # thirteenth branch added upstream is fetched silently -- and this tree does grow: most
    # entries are dated 2016 and 2020, but `RTX.100/` and `RT2000/` are 2022-02-02.
    # drivers-exclude-test.py carries a case for exactly that.
    'drivers/Matrox/RT%20Series/PROPack/',
    'drivers/Matrox/RT%20Series/Premiere%20Upgrade/',
    'drivers/Matrox/RT%20Series/RT2000/',
    'drivers/Matrox/RT%20Series/RTX.100/',
    'drivers/Matrox/RT%20Series/RTX100XtremePro/',
    'drivers/Matrox/RT%20Series/VFW/',
    'drivers/Matrox/RT%20Series/documentation/',
    'drivers/Matrox/RT%20Series/dvdit/',
    'drivers/Matrox/RT%20Series/misc/',
    'drivers/Matrox/RT%20Series/utilities/',

    # ASUS, 4.75 GB. `older mainboards` and P4PE stay; Blu-ray drive, two routers, a 2013
    # board and the loose driver-DVD image go.
    'drivers/ASUS/BW-16D1HT/',
    'drivers/ASUS/RT-AC66U/',
    'drivers/ASUS/rt-66ac/',
    'drivers/ASUS/C60M1-I/',
    'drivers/ASUS/BDP1000_XAA_110324_01.iso.zip',
    'drivers/ASUS/asus_m4a88t_v_evo_driver_dvd.iso',
    'drivers/ASUS/asus_m4a88t_v_evo_driver_dvd.mds',

    # Creative, 6.56 GB, almost all of it wanted -- SB16 and AWE64 are emulated, and so is the
    # ES1370/1371 of the AudioPCI and PCI128 discs. Only these three are out of era, 1.05 GB:
    'drivers/Creative/CDs/SB_X-Fi/',
    'drivers/Creative/CDs/SB_Live1024/',
    'drivers/Creative/CDs/SB_Live5.1/',

    # An outdated copy of ardent-tool, which this collection holds in full and current as its
    # own archive. Its own filename says "outdated_mirror".
    'drivers/IBM/ardent_tool_outdated_mirror_ohlandl.ipv7.net.7z',
)

# Two large directories stay in DELIBERATELY, against first appearance:
#   Miscellaneous  13.92 GB   Truevision (TARGA), ibm-pc.org, vintagecomputer.ca, hiren.info
#   unsorted       10.39 GB   234 directories: 3Dfx, Adlib Gold, BocaResearch, CIRRUS, CMedia,
#                             Crystal, Weitek P9100, Creatix, Adaptec -- the target era exactly.
# A directory named "unsorted" reads like leftovers. Here it is the opposite.

# ITS OWN SITEMAP FOUND 32 PAGES THE CRAWL NEVER SAW, 2026-10-02, and it is the first time any
# COMPLETE marker in this collection was checked against something other than our own method.
# find-sitemaps.py read https://ardent-tool.com/sitemap.xml -- declared in robots.txt, 2430
# entries -- and 32 of them were absent here. Not excluded (`incoming/` is the only pattern), not
# among the 42 permanent-404 the marker records, and NOT in unreached branches: the directories
# were held in full. Apricot/prodcode had td,te,tf,tg.html and lacked jp,np,qf,qp,sb.html; SSA had
# 4-G and 4-I and lacked 4-D; complex/ had 270 entries and lacked its own index.html. So the crawl
# stood inside those directories and these pages are LINKED BY NOTHING.
#
# All 32 answered 200. None was a 404, none an error page -- they are ordinary articles, "Qi 300
# (Jupiter)", "SSA Adapter 4-D", "Processor Complex". Fetched by url list at 2 s, marker restated,
# --verify UNCHANGED at 25733 files.
#
# WHAT IT MEANS FOR EVERY OTHER MARKER, said here because this is the register and not a log: each
# one rests on link-following, and so does measure-remote.py, which is why a measurement cannot
# close this gap -- it rediscovers the same reach at one HEAD per file. A sitemap is the operator's
# statement rather than ours, for two requests. 7 of 104 archives publish one; the other 97 have no
# such check available and their markers say only "everything we could find".
#
# STILL OPEN HERE, and deliberately not acted on: a harvest of the 1866 stored pages names 1617
# files the tree lacks. 1434 are `?v=2` cache-busting variants of files already held -- the site
# writes both spellings -- which leaves 183 candidates. ardent-tool is also the archive that once
# carried 15 478 links the old parser could not see and lost nothing at all, so these 183 are a
# question and not a figure.

EXCLUDE = {
    "ardent-tool": ("incoming/",),

    # ONE OF THE TWO SUB-MIRRORS, HELD BACK UNTIL IT IS MEASURED -- and the pattern below was
    # tested against a real child URL before this line was written, because the previous attempt
    # at an iommu exclusion named a directory that does not exist and downloaded 16 GB in
    # silence. Patterns are matched against the path RELATIVE TO THE ARCHIVE ROOT, and this
    # archive's root is iommu.com/ while everything hangs under /datasheets/.
    #
    # WHAT IT IS: retro.digitalvintage.ru has two branches, `Abandonware Archives/` and
    # `Computer Collection/`, the latter holding dozens of per-machine folders -- AST Ascentia,
    # Abit BP6, Acer TravelMate, Alpha Boards, Apple Macintosh LC630, Baikal, Canon Notejet,
    # Compaq and on. The 13 GB this collection fetched before the size was noticed was ONE of
    # them: `Computer Collection/_IBM Thinkpads/`, and all of it recovery images. The owner
    # deleted it by hand on 2026-09-26.
    #
    # A driver-and-recovery archive is not out of scope here -- oldskool/drivers is 125 GB and
    # deliberate -- but its SIZE IS UNKNOWN and the one sample was disc images rather than
    # documentation. So it waits for a measurement, which is the same rule every other candidate
    # got today. The other sub-mirror, www.vgamuseum.info/ at 3.2 GB, stays IN: it is the
    # complete copy of an archive this collection could not finish at the origin.
    # EVERYTHING EXCEPT ONE BRANCH, spelled out because EXCLUDE subtracts and cannot include.
    # Names are URL-ENCODED, taken from the server's own listing rather than typed: the spaces
    # are %20, and a pattern written with real spaces would match nothing and say nothing.
    # Checked against real child URLs before this was written.
    #
    # THE THREE INSIDE Hardware Info/ WERE MEASURED ON 2026-09-27, and the answer is a floor with
    # a reason. `Jumper Reference/` alone reached 41 944 files / 221.16 MB and then STOPPED
    # FINDING ANYTHING: from page 950 to page 3 875 the file count and the byte total did not
    # move at all while the queue still held 99 000 pages. The branch cross-links its per-board
    # pages so heavily that thousands of distinct page URLs reach the same files, and the crawl
    # was draining that queue at one page per second -- 27 more hours of requests to a stranger's
    # server for nothing new. Stopped rather than finished.
    #
    # A FROZEN FILE COUNT BESIDE A RISING PAGE COUNT IS THE SIGNAL that a measurement has learned
    # everything it is going to. Worth recognising by eye until something recognises it in code:
    # the whole-site run in September showed the same shape and was read as progress.
    #
    # SO THE FIGURE TO WEIGH IS ~222 MB FOR Jumper Reference, with OEMINFO/ and ROM Archive/ not
    # reached at all. Tiny, and on subject -- jumper settings and ROM dumps for old boards. The
    # cost is not bytes but PATIENCE: taking it means a crawl that walks ~100 000 pages to fetch
    # ~42 000 files, and mirror.py has no page cap.
    #
    # Delete a line to take that branch. The eight below are the top level; the three after them
    # are inside Hardware Info/.
    "retro-digitalvintage": (
        "Abandonware%20Archives/",
        "Computer%20Collection/",
        "Drivers/",
        "Games/",
        "Operating%20Systems/",
        "Photographic%20Materials/",
        "SERVERGHOST%20Builds/",
        "Software/",
        "Hardware%20Info/Jumper%20Reference/",
        "Hardware%20Info/OEMINFO/",
        "Hardware%20Info/ROM%20Archive/",
    ),

    "iommu": (
        # THE WHOLE RUSSIAN SUB-MIRROR, HELD BACK FOR SPACE -- measured, not guessed, and the
        # measurement is why. Finished on 2026-09-27 after 318.7 minutes: **137 098 files,
        # 1.83 TB**, and still a floor -- 2 968 pages beyond the cap, 2 730 size lookups failed.
        # Nearly half of this entire 4.01 TB collection, against 175 GB free. That is the whole
        # argument; nothing about the content is being judged here.
        #
        # THE ARCHIVE IS TAKEN AT ITS OWN ORIGIN INSTEAD, fenced to one branch -- see
        # ARCHIVES["retro-digitalvintage"]. Widening it is deleting a line there, and this
        # figure is what to weigh before deleting one.
        #
        # THIS ENTRY WAS NARROWER FOR AN HOUR and that was wrong. It read
        # `.../Computer%20Collection/_IBM%20Thinkpads/Recovery/` on the reasoning that the
        # recovery disc images were unwanted while the Docs/ and Drivers/ beside them were not.
        # True in itself -- and `_IBM Thinkpads` is ONE of dozens of machine folders under
        # `Computer Collection/`: AST Ascentia, Abit BP6, Acer TravelMate, Alpha Boards, Apple
        # Macintosh, Baikal, Canon Notejet, Compaq and on. Excluding one folder while the branch
        # holds a hundred gigabytes is arithmetic, not curation.
        #
        # WHAT IS NOT EXCLUDED, deliberately: `www.vgamuseum.info/` (3.2 GB, the complete copy of
        # an archive this collection could not finish at its origin) and `kib.kiev.ua-x86docs/`
        # (2.5 GB). Those are the two the owner called extremely valuable, and together they are
        # under 6 GB.
        #
        # WHERE THE 1.83 TB IS, measured per branch on 2026-09-27 because the figure above says
        # HOW MUCH and not WHERE, and that is the question anyone weighing this will ask:
        #
        #     Computer Collection/    44 031 files   464.19 GB   a complete walk, 10 049 pages
        #     everything else       ~93 000 files    ~1.37 TB    by subtraction
        #
        # SO ONE QUARTER OF IT IS ONE BRANCH, and that branch is not documentation. Its contents
        # are per-machine DRIVER AND RECOVERY trees -- Dell, `_IBM Thinkpads`, Sony Vaio, Compaq,
        # Canon -- with whole installer trees nested inside them: paths like
        # `_IBM Thinkpads/Drivers/560E/to load/Distrib/WINNT/I386/INETSRV/...` and an Intel
        # graphics plugin tree seven levels deep under a Vaio. That matches what the single
        # 13 GB sample taken before the size was noticed turned out to be.
        #
        # A NOTE ON HOW NOT TO ANSWER THIS. The per-branch split was first RECONSTRUCTED from the
        # 94 LISTFAIL lines of the whole-site run, which were the only place a URL appeared: it
        # put 1.62 TB in `Abandonware Archives/` and 109 GB here. The direct measurement says
        # 464 GB -- wrong by a factor of four. Waypoints say where a crawl WAS, not what it
        # counted while it was there. measure-remote.py now logs the branch on every progress
        # line so the question can be answered by reading rather than by inference.
        #
        # TO TAKE IT LATER: delete this line. The branch is recorded in CANDIDATES with its
        # measurement, so nobody has to rediscover what it is.
        "datasheets/mirrors/retro.digitalvintage.ru/",
    ),

    # 78.8 GB of OTHER PEOPLE'S ARCHIVES, out of 83.86 GB measured. iommu.com/mirrors/ carries
    # datasheets.chipdb.org and www.vgamuseum.info among others -- and both of those are being
    # taken AT THEIR ORIGIN in the same batch as this. Taking somebody's mirror instead of the
    # origin is how you inherit the gaps they had on the day they copied it. What remains is the
    # ~5.0 GB Bowling assembled himself, which is what this archive is for.
    # NO ENTRY FOR iommu, AND THE ROUND TRIP IS WORTH RECORDING because both positions were
    # held on the same day and the second was reached by LOOKING.
    #
    # It began as EXCLUDE["iommu"] = ("mirrors/",), on the reasoning that 78.8 GB of the 83.86 GB
    # measured is other people's archives and that taking somebody's mirror rather than the
    # origin is how you inherit the gaps they had on the day they copied it. Sound in general.
    #
    # THE PATTERN WAS ALSO WRONG, and that is the durable lesson. Patterns match the path
    # RELATIVE TO THE ARCHIVE ROOT -- `rel = child[len(base_url):]` -- and this archive's root is
    # iommu.com/ while every file hangs under /datasheets/. So `mirrors/` named a directory that
    # does not exist, matched nothing, and SAID NOTHING: a wrong pattern and a right one look
    # identical in the source and produce identical output. 16 GB arrived before the total was
    # noticed by eye. A pattern that never fires is now reported at the end of a run.
    #
    # AND THEN THE 16 GB WAS LOOKED AT, which settled it the other way:
    #     retro.digitalvintage.ru/   13 GB   a Russian retro archive held NOWHERE ELSE here
    #     www.vgamuseum.info/       3.2 GB   the site that blocked this collection the same day
    # The second is the striking one. vgamuseum-doc is stuck at 1 142 of 2 261 files because the
    # origin stopped answering; Bowling's copy is complete. Taking it is not evading the block --
    # the host objected to a REQUEST RATE, automatically, not to anyone holding its files, and
    # getting them from somebody who already has them is gentler than trying the origin again.
    #
    # So the whole archive is taken, mirrors and all. The duplication against chipdb, which is
    # fetched at its origin in the same batch, is real and will show up in b2-cluster.py's
    # duplicate count -- where it can be seen and judged, rather than guessed at here.

    # A DIRECTORY THAT LISTS ITS OWN NAME. bretjohnson.us/programs/ is an ordinary Apache index
    # whose entries are `/`, 24 .zip files -- and `programs/`. Following that gives
    # /programs/programs/, which answers HTTP 500 and was the run's only failure. Nothing is
    # missing: the entry is the directory naming itself, not a subdirectory.
    #
    # Excluded rather than tolerated, because an archive held at INCOMPLETE by a self-reference
    # teaches the next reader to ignore the word.
    "bretjohnson": ("programs/programs/",),

    # THE WILDCARD GROUP OF openpa.net's robots.txt, and the only part of that file that reaches
    # this collection. Its named rule -- `User-Agent: ClaudeBot / Disallow: /` -- does not: this
    # is mirror/1.0 fetching for preservation, the position recorded in CANDIDATES. But
    # `User-agent: *` disallows /images/ and /systems/images/, which binds every crawler
    # including this one, and that is where the scans live. So the articles come and the images
    # do not.
    #
    # WRITTEN AND REMOVED TWICE BEFORE THIS, both times because an exclusion for an archive that
    # does not exist is a dangling key archive-tables-test.py rejects.
    #
    # AND REVERSED BY THE OWNER ON 2026-10-01. Everything above stays as written, because it is
    # what was decided on 2026-09-26 and acted on for five days; the entry below it is gone. His
    # position: this is not a robot but a browser, mirroring privately, once, with no
    # redistribution -- so the wildcard group is not read as binding here. That is his call on his
    # own collection and his own relationship with the host, and it is recorded rather than
    # argued, as the 2026-09-26 position was.
    #
    # WHAT THE REVERSAL COSTS, so nobody has to rediscover it: 580 files (229 under images/, 351
    # under systems/images/), named by pages already on disk and therefore known for zero
    # requests. Total bytes UNKNOWN -- the 2026-09-27 measurement of 492 files / 47.80 MB was
    # taken WITH these paths excluded, so the floor says nothing about them. [The "~60 requests a
    # day" this paragraph originally used for planning was wrong by a factor of six -- see the
    # MIN_INTERVAL note. 300 of the 580 came in one session the same evening.]
    #
    # WHAT WAS NOT DONE, AND WHY IT WOULD NOT HAVE WORKED EITHER. A browser User-Agent and a
    # rotating agent string were asked for on the same day and are not here. The block on this
    # host is at the TRANSPORT layer: WinError 10060 is a dropped SYN, so no HTTP request reaches
    # the server at all and no header we send can be read. The distinguishing measurement is
    # already in this file -- a KNOWN-GOOD held page times out identically to anything else once
    # the block is on, which is how we know it is host-wide and not about particular URLs. It
    # meters the address, not the agent. Beyond that, mirror/1.0 is the only way an operator can
    # tell who we are and reach us, and the rule two tables down is the collection's own: "not
    # another user agent. Route-shopping around a block is the thing this collection does not do."


    # SIXTEEN FILES THE SERVER EXECUTES INSTEAD OF SERVING -- .py, .php AND .pl, every one
    # answering HTTP 500. Measured twice rather than inferred, in two different directories:
    #
    #   simh/cmake/   twelve neighbours answer 200, INCLUDING cmake-builder.ps1 and
    #                 cmake-builder.sh -- so being a script is not the problem
    #   repair/       nine neighbours answer 200, including a 22 MB PDF, an .xls, a .zip and a
    #                 .csv -- and only the three .pl files fail
    #
    # THE FIRST PASS FOUND .py AND .php AND STOPPED THERE, and .pl surfaced only because the
    # re-run still reported three failures. The rule is not "these two extensions": it is every
    # extension this server has an interpreter wired to. Anything else ending .cgi, .rb, .sh
    # would very likely behave the same way, and the next run that reports a 500 on a script
    # should be read that way rather than investigated from scratch.
    #
    # Third instance of this shape here -- wotug-inmos loses two .bat files to a 503 rule, and
    # ibiblio loses database.var to mod_negotiation claiming *.var. Different servers, same
    # lesson: a file that exists can be unreachable because of what it is called.
    #
    # WHAT IS ACTUALLY LOST IS NEARLY NOTHING, and that is worth stating so nobody spends a day
    # on it. Eleven are SIMH's cmake build scripts, which live on GitHub in a thousand copies;
    # four are the site's OWN helpers (xx.php, foo.pl, mkcsv.pl, sorttab.pl) -- the machinery
    # that generates its pages, not content; one belongs to an RK05 emulator utility whose
    # sources sit beside it. None of the sixteen is PDP-8 material. They are excluded so the
    # archive can report COMPLETE honestly instead of carrying failures that mean nothing.
    "somuchstuff-pdp8": (
        "trunk/pdp8/simh/cmake/generate.py",
        "trunk/pdp8/simh/cmake/simgen/basic_simulator.py",
        "trunk/pdp8/simh/cmake/simgen/cmake_container.py",
        "trunk/pdp8/simh/cmake/simgen/ibm1130_simulator.py",
        "trunk/pdp8/simh/cmake/simgen/packaging.py",
        "trunk/pdp8/simh/cmake/simgen/parse_makefile.py",
        "trunk/pdp8/simh/cmake/simgen/pdp10_simulator.py",
        "trunk/pdp8/simh/cmake/simgen/sim_collection.py",
        "trunk/pdp8/simh/cmake/simgen/text_file.py",
        "trunk/pdp8/simh/cmake/simgen/utils.py",
        "trunk/pdp8/simh/cmake/simgen/vax_simulators.py",
        "trunk/pdp8/src/dec/xx.php",
        "trunk/pdp8/vintagetek/rk05/build/RK05_Emulator_Tester_System_v2/_rke_files/"
        "RK05_Emulator_RK11D_Utility/RK11DUtils.py",
        # .pl, found by the re-run. Site scripts, not PDP-8 material.
        "documents/foo.pl",
        "repair/mkcsv.pl",
        "repair/sorttab.pl",
    ),

    # ONE CGI FORM HANDLER, AND IT CONFIRMS THE PREDICTION MADE DIRECTLY ABOVE. The
    # somuchstuff-pdp8 entry ends "anything else ending .cgi, .rb, .sh would very likely behave
    # the same way, and the next run that reports a 500 on a script should be read that way
    # rather than investigated from scratch." This is that next run, and the prediction held --
    # so this is the fourth instance of the same shape, after somuchstuff-pdp8's sixteen,
    # wotug-inmos's two .bat files and ibiblio's database.var.
    #
    # MEASURED, three times: https://spider.seds.org/ngc/ngc_sel.cgi answers HTTP 500 with the
    # same 538 bytes on every request. It is the SUBMIT TARGET of the NGC search form, and a
    # form handler called with no parameters has nothing to do but fail. There is no file behind
    # it, so nothing is lost and no re-run can succeed.
    #
    # ITS EIGHT NEIGHBOURS ARE NOT EXCLUDED, on purpose, and they are the more interesting half.
    # They answer HTTP 200 and SIX OF THEM STORE AN ERROR PAGE -- titled `NGC Error !`,
    # `Erreur NGC !`, `NGC/IC Error!`, `Error in revngcic.cgi`, 150 to 1 303 bytes each. Nothing
    # reported them: find-html-imposters.py is right not to, because `.cgi` is in
    # common.PROGRAM_PAGE_EXTENSIONS and HTML under a `.cgi` name is exactly what is expected.
    # A wrong page under a RIGHT name was a hole in the vocabulary, and it is now
    # common.looks_like_an_error_page() -- see measurements/error-pages-2026-09-27.md.
    #
    # They stay fetched rather than excluded: they are what that url serves, they are reported
    # now, and an excluded path leaves the stored file behind as an orphan nothing accounts for.
    "seds-frommert": ("ngc/ngc_sel.cgi",),

    # FOUR PATHS THE SOURCE CANNOT SERVE, so ibiblio can stop being asked for them. They
    # reproduced identically on three runs (2026-09-08 twice, 2026-09-11 once) and made every
    # one of those runs end INCOMPLETE over 214 719 files. MEASURED, not read off the codes:
    #
    #   .../slackware-2.1/usr/lib/apsfilter/bin/database.var        HTTP 500
    #       Ten of the eleven files in that directory serve 200 on the same connection --
    #       including database.FIX, same stem, 47 bytes, and have_locate, which is 0 bytes, so
    #       neither smallness nor emptiness is the trigger. An INVENTED name ending .var gets a
    #       plain 404, so the handler only fires once the file has been found. The extension is
    #       the cause: Apache's mod_negotiation claims *.var as a type-map, tries to parse a
    #       file that is not one, and fails. A query string does not bypass it. Same shape as
    #       wotug-inmos's two .bat files -- a server rule keyed on the extension, not a broken
    #       file and not a transient fault. THE FILE EXISTS AND WE CANNOT HAVE IT.
    #
    #   .../redhat-mothers-day-1.1/bootstrap/bootstrap/var/spool/cron/    HTTP 404
    #   .../redhat-mothers-day-1.1/bootstrap/bootstrap/usr/spool/cron/    HTTP 404
    #   .../redhat-mothers-day-1.1/bootstrap/bootstrap/etc/sysconfig/     HTTP 404
    #       Their parents serve, and every sibling serves: lpd/ mail/ mqueue/ uucp/ beside
    #       cron/, and X11/ rc.d/ skel/ beside sysconfig/, all 200. The decisive test is the
    #       TRAILING SLASH. Asked without one, var/spool/lpd answers 301 and adds it back --
    #       mod_dir redirects because the directory is really there -- while all three of these
    #       stay 404. The paths DO NOT RESOLVE: they are names the parent's readdir reports and
    #       which stat cannot follow, dangling links or entries whose targets are gone. A 403
    #       would have meant permissions; a 404 with no redirect means there is nothing behind
    #       them. NOTHING IS MISSING FROM THIS COPY -- the source has nothing to give.
    #
    # Excluded rather than retried: a retry costs ibiblio four hours of directory requests to
    # reproduce a conclusion three runs have already reached.
    "ibiblio-historic-linux": (
        "distributions/slackware-2.1/usr/lib/apsfilter/bin/database.var",
        "distributions/redhat-mothers-day-1.1/bootstrap/bootstrap/var/spool/cron/",
        "distributions/redhat-mothers-day-1.1/bootstrap/bootstrap/usr/spool/cron/",
        "distributions/redhat-mothers-day-1.1/bootstrap/bootstrap/etc/sysconfig/",
    ),

    # Apache's own stock artwork alias, not site content. The directory 403s anyway.
    #
    # The five user directories that stood here until 2026-09-08 -- ~fray/, ~paul/, ~benh/pics/ on
    # gate, and fray/, hail/ on kernel -- are now taken. They were excluded on a research pass's
    # description of their contents which this session never checked; the owner, who is in contact
    # with the site's users and who looked at the tree, decided otherwise. An exclusion resting on
    # an unverified second-hand impression is not one worth keeping against the judgement of
    # somebody with first-hand knowledge.
    "crashing-org": ("icons/",),
    # pub/ is the root itself, verified byte for byte -- see the ARCHIVES entry.
    # Without this the crawler walks pub/pub/ before looks_like_a_loop() stops it
    # at the third repetition, fetching the whole 12 GB tree twice over.
    "zx-microway": ("pub/",),
    # transputer-classiccmp HAS NO EXCLUSION, and the one it briefly had is worth
    # recording. documentation/inmos/dvd_pw424/VIDEO_TS/VTS_01_1.VOB (349 MB) was
    # excluded as "a DVD video rip, not documentation". That was read off the filename:
    # VIDEO_TS/VTS_01_1.VOB is simply how every DVD-Video disc is laid out, and it says
    # nothing whatever about the content.
    #
    # Checked instead of assumed: documentation/inmos/ is 53 numbered INMOS document
    # PDFs -- 1126, 1625, 1857, 2186 -- and `pw424` follows that numbering. The person
    # who built this archive filed the disc as DOCUMENTATION. Its VIDEO_TS.IFO is a
    # genuine DVD-Video VMG whose provider ID is UNDEFINED, so the disc cannot name
    # itself either.
    #
    # A training film or a demonstration recording for a dead architecture is precisely
    # the artefact that exists once. 349 MB is not a reason to guess.
    # The operator's own robots.txt. /archives/ is allowed and is the base URL,
    # but the crawler can reach these through site navigation.
    "novasareforever-aviion": ("../system/", "../vendor/", "../cache/", "../bin/",
                               "../backup/", "../tmp/", "../logs/", "../tests/",
                               "../assets/", "../.github/", "../.phan/",
                               "../webserver-configs/"),

    # GENERATED ITRC FORUM STATISTICS, one page and one graph per date: `id-20100310.html`,
    # `sp-20070808.png`. They are not HP-UX software and they are not this site's subject --
    # they are the author's own posting statistics for a support forum that HP shut down.
    #
    # EXCLUDED ON THREE MEASUREMENTS, not on taste:
    #
    #   they are most of the archive   750 of 790 files, 1.23 GB of 2.26 GB -- 54.5%
    #   they lead nowhere              id-20100310.html carries 22 165 <a href> and yields
    #                                  ZERO children: every one points at forums2.itrc.hp.com,
    #                                  another host, correctly refused by is_child_link
    #   they cost more than everything Each page is ~5.4 MB and HTML_CRAWL fetches every page
    #                                  again to read its links. At 401 pages that is 2 GB of
    #                                  somebody's bandwidth spent to learn nothing.
    #
    # They are also what exposed the quadratic ROW_RE -- see there. THAT DEFECT IS FIXED
    # SEPARATELY AND ON PURPOSE: excluding the pages that trip a bug is not repairing the bug,
    # and the next archive with a big page would have hit the same wall. The exclusion stands on
    # its own grounds, which is that the content is out of scope.
    #
    # Prefix match, and checked against the tree before being written: 750 files begin `id-` or
    # `sp-`, all of them YYYYMMDD statistics, and NOTHING ELSE in this archive does. The 40 that
    # remain are the subject -- gcc 3.2 through 4.2.4 for HP-UX 10.20/11.00/11.11/11.31,
    # caljd, bzip2 and four real pages.  [2026-09-16]
    "develooper-hpux": ("id-", "sp-"),

    # 8.96 GB of `tmp/`, left out on the owner's decision after he looked at it.
    #
    # `unpacked/` IS NOT UNPACKED. It looks like the server's extraction of every archive in
    # drivers_1/, hardware/, skene/, software/ and tlr/ -- one folder per archive, one file per
    # member -- but every file in it is an HTML PAGE from the "Metropoli-Retro-Viewer", a DOS-styled
    # web view of that member. dizit34.zip holds DIZALL.BAT at 51 bytes; unpacked/ has a 3 789-byte
    # web page called dizall.bat. DIZIT.EXE is 50 180 bytes; unpacked/ has a 1.47 MB page of hex
    # dump called dizit.exe. Not the bytes, not runnable, fully derived from originals this archive
    # holds, and ~90 000 files whose names claim .exe/.bat/.com while their content is HTML.
    #
    # It is absent from the root listing -- the crawler reached it through links inside the
    # directories -- which is why neither the host's stated sizes nor any measurement showed it.
    # The first run spent 62.66 GB, 97.7 % of what it fetched, on this view before it was
    # stopped.  [2026-09-19]
    #
    # `sekalaiset/ns0.sorbs.net/` is 37.52 of sekalaiset's 37.74 GB and is the OUTPUT OF A
    # REVERSE-DNS SCAN over IPv4 -- one text file per address block, directories dated 2004-2015
    # (191 of 240 from 2015). Checked line by line over the 1.2 GB already fetched, 13.27 M lines:
    # 11.92 M PTR answers (`0.0.27.94.in-addr.arpa. domain name pointer ll-0.0.27.94.kv...`),
    # ~1.28 M failed lookups (NXDOMAIN, timeouts, "no data"), and a few hundred WHOIS header
    # lines per /8. Nothing else. The other ~97 % was not fetched to check; its layout is the same.
    # Network measurement data, nothing to do with the board. The rest of sekalaiset (~230 MB) is kept: mpolivanhat is Metropoli's
    # own user guide and hardware 1996-97, plus USBDM, HCS12X, a monitor-repair course and 1997 IP
    # allocations.
    #
    # `ifsc2.ifsc.usp.br/` is 14.08 GB of a Brazilian university's Windows driver set, 2005-2014 --
    # printers 7.3 GB, mainboards 3.5 GB, scanners 1.8 GB. Excluded on the owner's decision: far
    # newer than this collection's subject, and mostly still available from the vendors.
    #
    # ORDER MATTERS HERE and is worth knowing: producer() pops `pending` from the END, so the root
    # listing is walked last-first -- tlr, software, skene, sekalaiset, ifsc2, hardware, drivers_1.
    # Without these exclusions `hardware/`, the reason this archive was taken, would have come
    # second to last, behind 51 GB of the two trees above.  [2026-09-19]
    "mpoli-bbs": ("tmp/", "unpacked/", "sekalaiset/ns0.sorbs.net/", "ifsc2.ifsc.usp.br/"),

    # oldskool, decided 2026-09-19 after a survey of all 22 directories under /pub/:
    #   drivers/            >= 250 GB, a FLOOR -- measured separately before any decision
    #   misc/Video, temp    135 + 10.6 GB of mp4/mpg/mkv
    #   simtelnet/          87.8 GB, SimTel -- mirrored in many places
    #   MindCandy/          34.8 GB, demoscene DVDs as video, commercially published
    #   IBM_PC_BBS/, ftp.bocaresearch.com/   ALREADY HELD, 99.99 % under ps-2.kev009.com
    #   misc/Audio, DJ Trixter, GameAudioCassettes, WaveMemories   mp3 recordings
    #   ANORMAL executable tools, Lightscribe   modern compilation packs / disc-burning software
    # rel is compared ENCODED (child[len(base_url):] is never unquoted), so names with spaces
    # appear in both forms.
    "oldskool": (
                 # drivers/ is fetched EXCEPT for DRIVERS_OUT / DRIVERS_OUT_SUB above.
                 "misc/Video/",
                 "misc/temp/",
                 "misc/Audio/",
                 "misc/DJ%20Trixter/",
                 "misc/DJ Trixter/",
                 "simtelnet/",
                 "MindCandy/",
                 "IBM_PC_BBS/",
                 "ftp.bocaresearch.com/",
                 "GameAudioCassettes/",
                 "WaveMemories/",
                 "ANORMAL%20executable%20tools/",
                 "ANORMAL executable tools/",
                 "Lightscribe/",
    ) + tuple("drivers/" + v for v in DRIVERS_OUT) + DRIVERS_OUT_SUB,
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
# Archives whose SOURCE holds names differing only in case. Without the NTFS flag the crawler
# cannot store both, keeps the first, and logs COLLISION DROPPED -- a logged, deterministic loss,
# but a loss.
#
# ps-2.kev009.com ADDED 2026-09-08, AFTER IT COST 153 FILES. The August runs dropped them; a
# September audit of the DROPPED lines found every one still absent from the tree. Six pairs were
# then fetched under both spellings and compared by SHA-256: THREE WERE BYTE-IDENTICAL (the same
# file listed twice) and THREE WERE GENUINELY DIFFERENT -- `pccbbs/eprm/epr2f.inf` at 1 155 162
# against 1 397 388 bytes, and two locale catalogues differing by tens of bytes. So the source is
# case-sensitive and the drops were real content. Recovered with `case-collision-recover.py`.
#
# THE FLAG IS NOT RETROACTIVE. Adding a name here only helps directories created afterwards.
# For an archive already on disk, the repair is that script -- it sets the flag per affected
# directory and fetches only what is missing, rather than re-crawling someone's server.
#
# ardent-tool is deliberately NOT here: its 2 DROPPED lines are from the first run of 2026-08-26
# and were healed by the third run on 2026-08-27. Checked against the tree, not the log.
NEEDS_CASE_SENSITIVE = {"ibm-aix", "tuhs", "ps-2.kev009.com"}

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
    # THE 61 OS/2 FILE AREAS, one page each, because `/gfd/` answers 403 and there is no index
    # above them. Generated from the front page's own table on 2026-09-27 rather than typed.
    "dreamlandbbs-os2": (
        "http://www.dreamlandbbs.com/gfd/apparc/index.html",
        "http://www.dreamlandbbs.com/gfd/appback/index.html",
        "http://www.dreamlandbbs.com/gfd/appcomm/index.html",
        "http://www.dreamlandbbs.com/gfd/appdb/index.html",
        "http://www.dreamlandbbs.com/gfd/appdemo/index.html",
        "http://www.dreamlandbbs.com/gfd/appedit/index.html",
        "http://www.dreamlandbbs.com/gfd/appews/index.html",
        "http://www.dreamlandbbs.com/gfd/appfile/index.html",
        "http://www.dreamlandbbs.com/gfd/appgame/index.html",
        "http://www.dreamlandbbs.com/gfd/appgfx/index.html",
        "http://www.dreamlandbbs.com/gfd/appjava/index.html",
        "http://www.dreamlandbbs.com/gfd/appmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/appmmpm/index.html",
        "http://www.dreamlandbbs.com/gfd/csdcpp/index.html",
        "http://www.dreamlandbbs.com/gfd/csdls/index.html",
        "http://www.dreamlandbbs.com/gfd/csdmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/csdwrp4/index.html",
        "http://www.dreamlandbbs.com/gfd/devinfo/index.html",
        "http://www.dreamlandbbs.com/gfd/devjava/index.html",
        "http://www.dreamlandbbs.com/gfd/devmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/devrexx/index.html",
        "http://www.dreamlandbbs.com/gfd/devtool/index.html",
        "http://www.dreamlandbbs.com/gfd/devxmpl/index.html",
        "http://www.dreamlandbbs.com/gfd/dosmdos/index.html",
        "http://www.dreamlandbbs.com/gfd/dosmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/doswos2/index.html",
        "http://www.dreamlandbbs.com/gfd/ftnbbs/index.html",
        "http://www.dreamlandbbs.com/gfd/ftndoor/index.html",
        "http://www.dreamlandbbs.com/gfd/ftnedit/index.html",
        "http://www.dreamlandbbs.com/gfd/ftnmail/index.html",
        "http://www.dreamlandbbs.com/gfd/ftnmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/ftntoss/index.html",
        "http://www.dreamlandbbs.com/gfd/gnuapps/index.html",
        "http://www.dreamlandbbs.com/gfd/gnudev/index.html",
        "http://www.dreamlandbbs.com/gfd/gnumisc/index.html",
        "http://www.dreamlandbbs.com/gfd/gnusrc/index.html",
        "http://www.dreamlandbbs.com/gfd/gnutool/index.html",
        "http://www.dreamlandbbs.com/gfd/infapps/index.html",
        "http://www.dreamlandbbs.com/gfd/infmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/infnews/index.html",
        "http://www.dreamlandbbs.com/gfd/infos2/index.html",
        "http://www.dreamlandbbs.com/gfd/intmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/intsrv/index.html",
        "http://www.dreamlandbbs.com/gfd/netconn/index.html",
        "http://www.dreamlandbbs.com/gfd/netls/index.html",
        "http://www.dreamlandbbs.com/gfd/netmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/netnw/index.html",
        "http://www.dreamlandbbs.com/gfd/nettcp/index.html",
        "http://www.dreamlandbbs.com/gfd/netwww/index.html",
        "http://www.dreamlandbbs.com/gfd/sysdisk/index.html",
        "http://www.dreamlandbbs.com/gfd/sysdisp/index.html",
        "http://www.dreamlandbbs.com/gfd/sysdrv/index.html",
        "http://www.dreamlandbbs.com/gfd/sysmisc/index.html",
        "http://www.dreamlandbbs.com/gfd/sysnet/index.html",
        "http://www.dreamlandbbs.com/gfd/sysprnt/index.html",
        "http://www.dreamlandbbs.com/gfd/syssnd/index.html",
        "http://www.dreamlandbbs.com/gfd/systool/index.html",
        "http://www.dreamlandbbs.com/gfd/wpsbmp/index.html",
        "http://www.dreamlandbbs.com/gfd/wpsfont/index.html",
        "http://www.dreamlandbbs.com/gfd/wpsicon/index.html",
        "http://www.dreamlandbbs.com/gfd/wpstool/index.html",
    ),

    # A FRONT PAGE WITH NO LINKS IS NOT AN EMPTY SITE. bretjohnson.us serves 22 412 bytes of
    # hand-written HTML describing every program he wrote -- and carries NOT ONE <a href>. The
    # files sit in two ordinary Apache autoindexes that nothing on the site points at. Measured
    # before this entry was written: the root yields 0 links, /programs/ yields 30.
    #
    # Without these two lines the archive would report COMPLETE with a single file, which is the
    # shape this collection has now met eight times.
    # FOUR ROOTS THAT DO NOT LINK DOWNWARDS, all measured on 2026-09-26 before being written:
    #   sgidepot.co.uk/      71 bytes of <meta http-equiv="Refresh"> and nothing else
    #   ~shadow/             a CV page; the RT tree is reachable only by knowing the URL -- 0 files
    #   /fjkraan/            18 files, 20 kB; the museum index lives one level down -- 243 files
    #   iommu.com/           two links, one of them the datasheets tree
    # The root is where the archive is MOUNTED so it can grow; the seed is where the crawler can
    # start. Conflating those two is what produces a subfolder mount.
    "sgidepot": ("http://www.sgidepot.co.uk/sgi.html",),
    "cmu-shadow": ("http://www.contrib.andrew.cmu.edu/~shadow/ibmrt/",),
    "fjkraan": ("http://www.vintagecomputer.net/fjkraan/comp/",),
    "iommu": ("http://iommu.com/datasheets/",),

    "bretjohnson": (
        "https://bretjohnson.us/programs/",
        "https://bretjohnson.us/source/",
    ),

    "ps-2.kev009.com": (
        "https://ps-2.kev009.com/basil.holloway/",
        "https://ps-2.kev009.com/rs6000/manuals/",
        "https://ps-2.kev009.com/rs6000/docs/",
        "https://ps-2.kev009.com/rs6000/aix_ps_pdf/",
        "https://ps-2.kev009.com/rs6000/rs6000_ps_pdf/",
        "https://ps-2.kev009.com/rs6000/bull_motorola_pdf/",
        "https://ps-2.kev009.com/rs6000/redbook-cd/",
        "https://ps-2.kev009.com/rs6000/NSM/",
        # /rs6000/ links this one WITHOUT a trailing slash -- see the lighttpd column-order
        # note in README.md's defect list, which is unnumbered prose; this comment cited a
        # "defect 9" that the list has never had. Formerly in
        # README.md. 49 files and 7.6 GB hung behind it, several of them large ISO images.
        "https://ps-2.kev009.com/rs6000/files/",
    ),
    "crashing-org": tuple(
        # The document tree nothing links to. 30 of 30 answered 200 on 2026-09-07.
        ["http://gate.crashing.org/doc/ppc/doc%03d.htm" % i for i in range(1, 29)]
        + ["http://gate.crashing.org/doc/ppc/",
           "http://gate.crashing.org/doc/ppc/doc000.htm",
           # The guide's ONLY figure. Referenced by doc013 and missed by the first fetch.
           "http://gate.crashing.org/doc/ppc/bootx.gif",
           "http://gate.crashing.org/doc/icons/",
           "http://gate.crashing.org/glibc21.shtml",
           "http://gate.crashing.org/penguin.html",
           # UNLINKED FROM ANYWHERE ON THE SITE, found only in the Apache index: photographs from
           # the week of Macworld San Francisco, January 1999, and March 1999. Six directories.
           "http://gate.crashing.org/pictures/",
           "http://gate.crashing.org/pictures/jan6/",
           "http://gate.crashing.org/pictures/jan8/",
           "http://gate.crashing.org/pictures/jan9/",
           "http://gate.crashing.org/pictures/jan10/",
           "http://gate.crashing.org/pictures/march/",
           # The PowerPC kernel developers' own published directories. Deliberately served with
           # indexing on; this is the material the archive is for.
           "http://gate.crashing.org/~benh/",
           "http://gate.crashing.org/~galak/",
           "http://gate.crashing.org/~galak/fsl_ddr.20080609/",
           "http://gate.crashing.org/~jwboyer/",
           # Taken 2026-09-08 on the owner's instruction; see the note beside EXCLUDE.
           "http://gate.crashing.org/~fray/",
           "http://gate.crashing.org/~paul/",
           "http://gate.crashing.org/~benh/pics/",
           ]),
    "crashing-org-kernel": (
        "https://kernel.crashing.org/fray/",
        "https://kernel.crashing.org/hail/",
        "https://kernel.crashing.org/penguin.html",
    ),
    "technologists-sauer": (
        # 38 of the 57 files here were missed by the first crawl -- several names carry
        # URL-encoded spaces and parentheses. Seeded rather than diagnosed: a seed is
        # cheap, and a missing IBM primary document is not. All confirmed 200 on
        # 2026-09-08. `cams/` is disallowed by robots.txt and is NOT here.
        "https://technologists.com/sauer/The_Virtual_Resource_Manager.pdf",
        "https://technologists.com/sauer/Advanced%20Interactive%20Executive%20(AIX)%20Operating%20System%20Overview.pdf",
        "https://technologists.com/sauer/Statelessness_and_Statefulness_in_Distributed_Services.pdf",
        "https://technologists.com/sauer/Presenting_a_Single_System_Image_with_Fine_Granularity_Mounts.pdf",
        "https://technologists.com/sauer/Unix_The_Force_Behind_Personal_Computing.pdf",
        "https://technologists.com/sauer/Meaningful_Indicators_of_System_Performance.pdf",
        "https://technologists.com/sauer/Saving_the_Day.pdf",
        "https://technologists.com/sauer/20070228transcriptof20070129.pdf",
        "https://technologists.com/sauer/DellStation.txt",
        "https://technologists.com/sauer/DellSVR4.txt",
        "https://technologists.com/sauer/199414-Bloomberg-NEXTSTEP486.pdf",
        "https://technologists.com/sauer/RC6341.pdf",
        "https://technologists.com/sauer/RC8001.pdf",
        "https://technologists.com/sauer/RC8364.pdf",
        "https://technologists.com/sauer/RC8986.pdf",
        "https://technologists.com/sauer/RA138.pdf",
        "https://technologists.com/sauer/RA139.pdf",
        "https://technologists.com/sauer/RA144.pdf",
        "https://technologists.com/sauer/04311908278.pdf",
        "https://technologists.com/sauer/The_Evolution_of_the_Research_Queueing_Package.pdf",
        "https://technologists.com/sauer/1983TOCSv1n1-Sauer-...withCorrigendum.pdf",
        "https://technologists.com/sauer/TucciSauer-TheTreeMVAAlgorithm.pdf",
        "https://technologists.com/sauer/RESQPPP.pdf",
        "https://technologists.com/sauer/RESQbibliography.html",
        "https://technologists.com/sauer/CHSauer.pdf",
        "https://technologists.com/sauer/CHSauerCV.pdf",
        "https://technologists.com/sauer/CHSauerCVwithCC.pdf",
        "https://technologists.com/sauer/CHSprojects.pdf",
        "https://technologists.com/sauer/CHSpubs.pdf",
        "https://technologists.com/sauer/CodianTechnicalTutorial.pdf",
        "https://technologists.com/sauer/TECS.pdf",
        "https://technologists.com/sauer/19911028Infoworld111.jpg",
        "https://technologists.com/sauer/asgchs91.gif",
        "https://technologists.com/sauer/TECS45x140.jpg",
        "https://technologists.com/sauer/0201847477_m.gif",
        "https://technologists.com/sauer/chs_bio.html",
        "https://technologists.com/sauer/index.html",
    ),
    "dialectronics": (
        # THE ROOT LISTING DOES NOT REACH THIS MACHINE. Four retry runs ended identically
        # -- 30 files, unchanged, one unreadable listing -- while individual files answer
        # in 60 ms and a research pass read the whole site without trouble. A network
        # path, not a server fault, and retrying cannot fix it.
        #
        # So the section INDEX PAGES are seeded instead of the files: they are ordinary
        # documents, they fetch, and each links its own section, so the crawl proceeds
        # from them as it would have from the root.
        #
        # WAYBACK IS NOT A FALLBACK HERE. The archived .xcf bootloaders are half-size
        # truncations and RISCV/riscv32.tar.gz was never archived at all. The live host
        # is the only complete source, and it announced a move to mpjanson.org in 2024.
        "http://www.dialectronics.com/index.shtml",
        "http://www.dialectronics.com/archived_news.shtml",
        "http://www.dialectronics.com/about.shtml",
        "http://www.dialectronics.com/mission.shtml",
        "http://www.dialectronics.com/trips.shtml",
        "http://www.dialectronics.com/RISCV/",
        "http://www.dialectronics.com/bootloader/",
        "http://www.dialectronics.com/PowerPC/",
        "http://www.dialectronics.com/Words/",
        "http://www.dialectronics.com/OpenFirmware/",
        "http://www.dialectronics.com/OldWorldMacs/",
        "http://www.dialectronics.com/Minix/",
        "http://www.dialectronics.com/Lua/",
        "http://www.dialectronics.com/trip/",
        "http://www.dialectronics.com/trip2/",
        "http://www.dialectronics.com/trip3/",
        "http://www.dialectronics.com/HomeRepair/",
        "http://www.dialectronics.com/RISCV/riscv32.tar.gz",
        "http://www.dialectronics.com/RISCV/code.c",
        "http://www.dialectronics.com/RISCV/local.c",
        "http://www.dialectronics.com/RISCV/local2.c",
        "http://www.dialectronics.com/RISCV/table.c",
        "http://www.dialectronics.com/RISCV/macdefs.h",
        "http://www.dialectronics.com/RISCV/order.c",
        "http://www.dialectronics.com/RISCV/flocal.c",
        "http://www.dialectronics.com/RISCV/match.c.patch",
        "http://www.dialectronics.com/RISCV/optim2.c.patch",
        "http://www.dialectronics.com/bootloader/boot25j.xcf",
        "http://www.dialectronics.com/bootloader/boot25k.xcf",
        "http://www.dialectronics.com/bootloader/boot25c.xcf",
        "http://www.dialectronics.com/bootloader/boot25a.xcf",
        "http://www.dialectronics.com/bootloader/boot24z.mac",
        "http://www.dialectronics.com/bootloader/L2bootloader.txt",
        "http://www.dialectronics.com/bootloader/code/loadfile.c",
        "http://www.dialectronics.com/bootloader/code/Locore.c",
        "http://www.dialectronics.com/bootloader/code/cread.c",
        "http://www.dialectronics.com/bootloader/code/boot.c",
        "http://www.dialectronics.com/bootloader/code/of_mfs.c",
        "http://www.dialectronics.com/bootloader/code/fix-coff.c",
        "http://www.dialectronics.com/bootloader/code/Makefile.boot.mac",
        "http://www.dialectronics.com/PowerPC/part_I.shtml",
        "http://www.dialectronics.com/PowerPC/part_II.shtml",
        "http://www.dialectronics.com/PowerPC/part_III.shtml",
        "http://www.dialectronics.com/PowerPC/local2.c.diff",
        "http://www.dialectronics.com/PowerPC/code.c.diff",
        "http://www.dialectronics.com/PowerPC/local.c.diff",
        "http://www.dialectronics.com/PowerPC/macdefs.h.diff",
        "http://www.dialectronics.com/PowerPC/table.c.diff",
        "http://www.dialectronics.com/PowerPC/code/L2Config.c",
        "http://www.dialectronics.com/PowerPC/code/bcopy.S",
        "http://www.dialectronics.com/PowerPC/code/fourbytes.s",
        "http://www.dialectronics.com/Words/OF_Part_I.shtml",
        "http://www.dialectronics.com/Words/OF_Part_II.shtml",
        "http://www.dialectronics.com/Words/OF_Part_III.shtml",
        "http://www.dialectronics.com/Words/ten.shtml",
        "http://www.dialectronics.com/Words/virt.shtml",
        "http://www.dialectronics.com/Words/Part_I_images/2dup.gif",
        "http://www.dialectronics.com/Words/Part_I_images/3minus2eq1.gif",
        "http://www.dialectronics.com/Words/Part_I_images/baking.gif",
        "http://www.dialectronics.com/Words/Part_I_images/chainadd.gif",
        "http://www.dialectronics.com/Words/Part_I_images/dryingredients.gif",
        "http://www.dialectronics.com/OldWorldMacs/post1.txt",
        "http://www.dialectronics.com/OldWorldMacs/post2.txt",
        "http://www.dialectronics.com/OldWorldMacs/post3.txt",
        "http://www.dialectronics.com/OldWorldMacs/code/bsdOF",
        "http://www.dialectronics.com/OldWorldMacs/code/bsdOWc.rd",
        "http://www.dialectronics.com/OldWorldMacs/code/boot24d.mac",
        "http://www.dialectronics.com/OldWorldMacs/code/boot24t.mac",
        "http://www.dialectronics.com/OldWorldMacs/code/if_sis.c",
        "http://www.dialectronics.com/OldWorldMacs/code/machdep.c",
        "http://www.dialectronics.com/OldWorldMacs/code/locore.S",
        "http://www.dialectronics.com/OldWorldMacs/code/zs.c",
        "http://www.dialectronics.com/OldWorldMacs/code/bandit_host.c",
        "http://www.dialectronics.com/OldWorldMacs/code/bandit_host.h",
        "http://www.dialectronics.com/OldWorldMacs/code/bus.h",
        "http://www.dialectronics.com/OldWorldMacs/code/cpu.c",
        "http://www.dialectronics.com/OldWorldMacs/code/cpu.h",
        "http://www.dialectronics.com/OldWorldMacs/code/ofw_machdep.c",
        "http://www.dialectronics.com/OldWorldMacs/code/macintr.c",
        "http://www.dialectronics.com/OldWorldMacs/code/vci_addr_fixup.c",
        "http://www.dialectronics.com/OldWorldMacs/code/vci.c",
        "http://www.dialectronics.com/OldWorldMacs/code/vgafb.c",
        "http://www.dialectronics.com/OldWorldMacs/code/vgafb_control.c",
        "http://www.dialectronics.com/OldWorldMacs/code/ofdev.c",
        "http://www.dialectronics.com/OldWorldMacs/code/OWRAMDISK",
        "http://www.dialectronics.com/OldWorldMacs/code/openfirm.c",
        "http://www.dialectronics.com/OldWorldMacs/code/openfirm.h",
        "http://www.dialectronics.com/OldWorldMacs/code/hid.h",
        "http://www.dialectronics.com/OldWorldMacs/code/files.macppc",
        "http://www.dialectronics.com/OldWorldMacs/code/mainbus.c",
        "http://www.dialectronics.com/OldWorldMacs/code/db_interface.c",
        "http://www.dialectronics.com/Minix/rtl8111.c",
        "http://www.dialectronics.com/Minix/rtl8111.h",
        "http://www.dialectronics.com/Minix/pcireg.h",
        "http://www.dialectronics.com/Minix/Makefile",
        "http://www.dialectronics.com/Lua/ldis_out.txt",
        "http://www.dialectronics.com/Lua/code/BinDecHex.shtml",
        "http://www.dialectronics.com/formmail.html",
        "http://www.dialectronics.com/graphics/logo.gif",
        "http://www.dialectronics.com/logon.jpg",
        "http://www.dialectronics.com/pgsql/fe-auth.c.v.1.136.diff.txt",
    ),
    "cryp-to-cwg": (
        # The DIRECTORY 404s while every file answers 200 -- so the whole archive is
        # seeds. 22 files, all confirmed 200 on 2026-09-08. Its index is one level UP,
        # at cr.yp.to/2005-590.html, which is outside this base URL and cannot be walked
        # from here; that is why a crawl of the directory finds nothing at all.
        #
        # powerpc.pdf is IBM's PowerPC User Instruction Set Architecture, Book I --
        # identified from the PDF metadata, /Title (PUB1M), and from the course page's
        # own prose. The filename says nothing.
        "https://cr.yp.to/2005-590/ultrasparc3.pdf",
        "https://cr.yp.to/2005-590/x86-volume1.pdf",
        "https://cr.yp.to/2005-590/sparcv9.pdf",
        "https://cr.yp.to/2005-590/x86-volume2a.pdf",
        "https://cr.yp.to/2005-590/x86-volume2b.pdf",
        "https://cr.yp.to/2005-590/powerpc-cwg.pdf",
        "https://cr.yp.to/2005-590/carter.pdf",
        "https://cr.yp.to/2005-590/powerpc.pdf",
        "https://cr.yp.to/2005-590/fog.pdf",
        "https://cr.yp.to/2005-590/brent.pdf",
        "https://cr.yp.to/2005-590/goldberg.pdf",
        "https://cr.yp.to/2005-590/courtois.pdf",
        "https://cr.yp.to/2005-590/stein.ps",
        "https://cr.yp.to/2005-590/wiener.pdf",
        "https://cr.yp.to/2005-590/hong.pdf",
        "https://cr.yp.to/2005-590/schneier.pdf",
        "https://cr.yp.to/2005-590/0110.pdf",
        "https://cr.yp.to/2005-590/aes.c",
        "https://cr.yp.to/2005-590/speed1.cpp",
        "https://cr.yp.to/2005-590/cpucycles-sparc.S",
        "https://cr.yp.to/2005-590/cpucycles-x86.S",
        "https://cr.yp.to/2005-590/cpucycles-powerpc.S",
    ),
    "sco-devspecs": (
        # 13 files. TWO ARE LINKED FROM NOWHERE: vol3.pdf, because the index offers
        # Volume 3 only as PostScript, and mipsabi.pdf, the MIPS psABI supplement, which
        # is not even named in the page text.
        #
        # The SVID volumes are vol1a/1b/2/3. An earlier guess at svid4v1..v4.pdf 404d --
        # the names came from the edition title, not from the server.
        "https://www.sco.com/developers/devspecs/gabi41.pdf",
        "https://www.sco.com/developers/devspecs/gabi41.ps",
        "https://www.sco.com/developers/devspecs/gabi40.pdf",
        "https://www.sco.com/developers/devspecs/gabi40.ps",
        "https://www.sco.com/developers/devspecs/abi386-4.pdf",
        "https://www.sco.com/developers/devspecs/abi386-4.ps",
        "https://www.sco.com/developers/devspecs/vol1a.pdf",
        "https://www.sco.com/developers/devspecs/vol1b.pdf",
        "https://www.sco.com/developers/devspecs/vol2.pdf",
        "https://www.sco.com/developers/devspecs/vol3.pdf",
        "https://www.sco.com/developers/devspecs/vol3_ps.ps",
        "https://www.sco.com/developers/devspecs/mipsabi.pdf",
        "https://www.sco.com/developers/devspecs/pdficon.gif",
    ),
    "sco-gabi": (
        # Eight dated snapshots of the SVR4 generic ABI, 1998-2013, 17 files each. The
        # subdirectories answer 403 to a listing while every file inside answers 200, so
        # nothing here can be walked and all 136 are named.
        #
        # `latest/` IS LINKED FROM NOWHERE and is dated 10 June 2013 -- two and a half
        # years newer than 2012-12-31/, the newest the index will take you to, whose own
        # heading reads 19 October 2010.
        "https://www.sco.com/developers/gabi/1998-04-29/contents.html",
        "https://www.sco.com/developers/gabi/1998-04-29/revision.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch4.intro.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch5.intro.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/1998-04-29/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/1998-04-29/contents.gif",
        "https://www.sco.com/developers/gabi/1998-04-29/next.gif",
        "https://www.sco.com/developers/gabi/1998-04-29/previous.gif",
        "https://www.sco.com/developers/gabi/1998-04-29/warning.gif",
        "https://www.sco.com/developers/gabi/1998-04-29/init_example.gif",
        "https://www.sco.com/developers/gabi/2000-07-17/contents.html",
        "https://www.sco.com/developers/gabi/2000-07-17/revision.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch4.intro.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch5.intro.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/2000-07-17/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/2000-07-17/contents.gif",
        "https://www.sco.com/developers/gabi/2000-07-17/next.gif",
        "https://www.sco.com/developers/gabi/2000-07-17/previous.gif",
        "https://www.sco.com/developers/gabi/2000-07-17/warning.gif",
        "https://www.sco.com/developers/gabi/2000-07-17/init_example.gif",
        "https://www.sco.com/developers/gabi/2001-04-24/contents.html",
        "https://www.sco.com/developers/gabi/2001-04-24/revision.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch4.intro.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch5.intro.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/2001-04-24/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/2001-04-24/contents.gif",
        "https://www.sco.com/developers/gabi/2001-04-24/next.gif",
        "https://www.sco.com/developers/gabi/2001-04-24/previous.gif",
        "https://www.sco.com/developers/gabi/2001-04-24/warning.gif",
        "https://www.sco.com/developers/gabi/2001-04-24/init_example.gif",
        "https://www.sco.com/developers/gabi/2003-12-17/contents.html",
        "https://www.sco.com/developers/gabi/2003-12-17/revision.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch4.intro.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch5.intro.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/2003-12-17/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/2003-12-17/contents.gif",
        "https://www.sco.com/developers/gabi/2003-12-17/next.gif",
        "https://www.sco.com/developers/gabi/2003-12-17/previous.gif",
        "https://www.sco.com/developers/gabi/2003-12-17/warning.gif",
        "https://www.sco.com/developers/gabi/2003-12-17/init_example.gif",
        "https://www.sco.com/developers/gabi/2007-03-26/contents.html",
        "https://www.sco.com/developers/gabi/2007-03-26/revision.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch4.intro.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch5.intro.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/2007-03-26/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/2007-03-26/contents.gif",
        "https://www.sco.com/developers/gabi/2007-03-26/next.gif",
        "https://www.sco.com/developers/gabi/2007-03-26/previous.gif",
        "https://www.sco.com/developers/gabi/2007-03-26/warning.gif",
        "https://www.sco.com/developers/gabi/2007-03-26/init_example.gif",
        "https://www.sco.com/developers/gabi/2009-10-26/contents.html",
        "https://www.sco.com/developers/gabi/2009-10-26/revision.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch4.intro.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch5.intro.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/2009-10-26/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/2009-10-26/contents.gif",
        "https://www.sco.com/developers/gabi/2009-10-26/next.gif",
        "https://www.sco.com/developers/gabi/2009-10-26/previous.gif",
        "https://www.sco.com/developers/gabi/2009-10-26/warning.gif",
        "https://www.sco.com/developers/gabi/2009-10-26/init_example.gif",
        "https://www.sco.com/developers/gabi/2012-12-31/contents.html",
        "https://www.sco.com/developers/gabi/2012-12-31/revision.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch4.intro.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch5.intro.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/2012-12-31/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/2012-12-31/contents.gif",
        "https://www.sco.com/developers/gabi/2012-12-31/next.gif",
        "https://www.sco.com/developers/gabi/2012-12-31/previous.gif",
        "https://www.sco.com/developers/gabi/2012-12-31/warning.gif",
        "https://www.sco.com/developers/gabi/2012-12-31/init_example.gif",
        "https://www.sco.com/developers/gabi/latest/contents.html",
        "https://www.sco.com/developers/gabi/latest/revision.html",
        "https://www.sco.com/developers/gabi/latest/ch4.intro.html",
        "https://www.sco.com/developers/gabi/latest/ch4.eheader.html",
        "https://www.sco.com/developers/gabi/latest/ch4.sheader.html",
        "https://www.sco.com/developers/gabi/latest/ch4.strtab.html",
        "https://www.sco.com/developers/gabi/latest/ch4.symtab.html",
        "https://www.sco.com/developers/gabi/latest/ch4.reloc.html",
        "https://www.sco.com/developers/gabi/latest/ch5.intro.html",
        "https://www.sco.com/developers/gabi/latest/ch5.pheader.html",
        "https://www.sco.com/developers/gabi/latest/ch5.dynamic.html",
        "https://www.sco.com/developers/gabi/latest/ch5.prog_loading.html",
        "https://www.sco.com/developers/gabi/latest/contents.gif",
        "https://www.sco.com/developers/gabi/latest/next.gif",
        "https://www.sco.com/developers/gabi/latest/previous.gif",
        "https://www.sco.com/developers/gabi/latest/warning.gif",
        "https://www.sco.com/developers/gabi/latest/init_example.gif",
    ),

    # THE PAGE THAT IS ALSO THE DIRECTORY. 22 URLs, each one an index.html that no link on this
    # host points at -- because the directory listing IS that page. Ask for `.../SRC-1997-003-html/`
    # and the server hands back the research paper; there is nothing to link to it from.
    #
    # mirror.py fetched every one of those bodies, parsed each as a listing, harvested the figures
    # and THREW THE TEXT AWAY. The page test matches URLs ENDING in .html and a directory URL
    # ends in "/", so the page was never queued as content. The archive held twelve DEC SRC
    # papers as illustrations with no prose, and reported COMPLETE.
    #
    # SEEDED RATHER THAN FIXED IN THE CRAWLER, deliberately. The general repair -- save every
    # directory body as index.html -- would also write the generated listing of every autoindex in
    # eighteen other archives, and this is a bounded set: MEASURED at 25 of 508 directories here,
    # by asking each for its index.html. On a generated index the server answers 404, so the
    # absence is the measurement. 22 of the 25 were missing; three were already held.
    #
    # Mostly DEC SRC technical notes and research reports -- SRC-1997-003 through SRC-2001-004,
    # the dcpi papers, SRC-021 and SRC-139a.

    # THE DIRECTORIES ARE LISTABLE AND NOTHING LINKS THEM. sun3arc's pages live inside their
    # directories -- the root links `ROMs/eprom.phtml`, never `ROMs/` -- so the first run took 23
    # pages, 62.5 KB, and reported COMPLETE over an archive whose ROMs/ alone holds ten model
    # subdirectories of boot PROMs.
    #
    # Each of these was probed on 2026-09-11 and returned a listing; the entry counts are what
    # came back. BootTapes/, Compiler/ and WAN/ list EMPTY and are deliberately not seeded --
    # a seed that yields nothing is a request per run for nothing.
    # THE SITE LINKS ITSELF UNDER A DIFFERENT HOSTNAME. Its pages point at
    # http://www.classiccmp.org/transputer/documentation/... -- the old domain, which 301s to
    # transputer.classiccmp.org. producer()'s startswith(base_url) test drops every one of them,
    # correctly and fatally: nothing on the site links /software/ or /documentation/ under the
    # name the crawler is using.
    #
    # Same shape as sco-devspecs' http->https, one layer out: there the scheme differed, here the
    # host does. Both end with a site that cannot reach its own content.
    #
    # Probed 2026-09-11: /software/ lists 19 entries, /documentation/ lists 27.
    "transputer-classiccmp": (
        "http://transputer.classiccmp.org/software/",
        "http://transputer.classiccmp.org/documentation/",
    ),
    "sun3arc": (
        "https://www.sun3arc.org/Sun-Patches/",                       # 538 Eintraege
        "https://www.sun3arc.org/precompiled/",                       # 33 Eintraege
        "https://www.sun3arc.org/Misc-Patches/",                      # 22 Eintraege
        "https://www.sun3arc.org/install/",                           # 14 Eintraege
        "https://www.sun3arc.org/ROMs/",                              # 10 Eintraege
        "https://www.sun3arc.org/FAQ/",                               # 9 Eintraege
        "https://www.sun3arc.org/hardpatches/",                       # 9 Eintraege
        "https://www.sun3arc.org/Errormsg/",                          # 8 Eintraege
        "https://www.sun3arc.org/FEH/",                               # 7 Eintraege
        "https://www.sun3arc.org/bench/",                             # 7 Eintraege
        "https://www.sun3arc.org/papers/",                            # 5 Eintraege
        "https://www.sun3arc.org/PALs/",                              # 4 Eintraege
        "https://www.sun3arc.org/text/",                              # 4 Eintraege
        "https://www.sun3arc.org/harddisk/",                          # 3 Eintraege
        "https://www.sun3arc.org/NetBSD/",                            # 2 Eintraege
        "https://www.sun3arc.org/schematics/",                        # 1 Eintraege
        "https://www.sun3arc.org/tune/",                              # 1 Eintraege
    ),
    "zx-gatekeeper-dec": (
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/dcpi/html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/publications/mds/LkMarian/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/research-reports/SRC-021-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/research-reports/SRC-139a-figs/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/research-reports/SRC-139a-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-003-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-010-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-015-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-016-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-018-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-023-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-027a-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-028-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-029-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1997-033-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1998-016-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1999-001-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-1999-003-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-2000-006-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/DEC/SRC/technical-notes/SRC-2001-004-html/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/net/infosys/NCSA/Web/Mosaic/Windows/Archive/index.html",
        "http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/pub/net/infosys/lynx/current/index.html",
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
    # ONE. obsolyte.com says on its own front page what it runs on: a SPARC IPX, 64 MB of RAM,
    # a 500 MB disk, Red Hat 6.0/UltraLinux. The default of eight parallel connections is more
    # sockets than that machine has memory to be comfortable with, and the archive is 23 MB.
    "obsolyte": 1,

    # Two, because the site asks for restraint in so many words. See MIN_INTERVAL.
    "seds-frommert": 2,

    # One person's server (R11: never two streams). The drivers/ measurement therefore runs
    # AFTER the fetch, not beside it.
    "oldskool": 1,

    # Two, because the index page carries `<meta name="robots" content="noindex,nofollow">`. The
    # decision to fetch it at all is argued in the ARCHIVES entry; `nofollow` is the half of that
    # tag which really is about crawling, and the answer to a directive one has chosen to read
    # narrowly is to take up as little of the host as possible. One person's mirror machine, 13 GB.
    "develooper-hpux": 2,

    # ftp.zx.net.nz describes ITSELF as "an entirely unsupported service", and its robots.txt
    # blocks eight SEO bots with the comment "they just waste bandwidth". Two connections. The
    # operator has said in as many words what he thinks of traffic he did not ask for, and this
    # collection has already been cut off by two hosts for ignoring exactly that signal.
    "zx-gatekeeper-dec": 2,
    "zx-hobbes-os2": 2,
    "zx-ultrix-freeware": 2,
    "zx-kednos-vms": 2,
    "zx-microway": 2,
    "zx-alphant-nt": 2,
    "zx-sgi-freeware-old": 2,
    "zx-be-os": 2,
    # All five are one person's server or a dormant university page. Two
    # connections, and sun3arc gets one -- see its entry for why it is the most
    # fragile thing in the collection.
    "sun3arc": 1,
    "transputer-classiccmp": 2,
    "novasareforever-aviion": 2,
    "apollo-clavius": 2,
    "wotug-inmos": 2,
    # Bitsavers and filibeto are volunteer-run documentation archives with far fewer, far larger
    # files than the package mirrors. Four connections is plenty for scanned PDFs and is the
    # polite number for someone else's hobby server.
    "filibeto-aix-lib": 4,
    # Hand-written sites on modest hosting, and the HTML crawl already asks for each page twice.
    "ardent-tool": 3,

    # THE THREE crashing.org HOSTS RAN AT THE DEFAULT EIGHT UNTIL 2026-09-13, which nobody had
    # decided -- they were simply never added to this table. kernel.crashing.org, gate and www are
    # one kernel developer's machines, the exact shape R9 names, and this collection fetches them
    # with the operator's permission. Eight connections against a personal server is what cost us
    # dialectronics on 2026-09-08: a seeded run with the default issued several hundred requests
    # in minutes, and then 783 x WinError 10060 -- the host stopped answering curl as well.
    #
    # Three. Not because anything has gone wrong here, but because being cut off is discovered
    # after the fact and cannot be undone, and this collection has already been cut off twice.
    "crashing-org": 3,
    "crashing-org-www": 3,
    "crashing-org-kernel": 3,

    # The eight taken on 2026-09-13. Every one is a private person, a club or a dying vhost --
    # square7.ch is FREE hosting, biblionik.fr is an EOL CentOS 7 with no TLS at all, and
    # ftp.parisc-linux.org is the last living part of a project whose website already serves the
    # Apache default page. Two connections, and biblionik gets one: an unmaintained PHP 5.4 box
    # is the least robust thing in this table.
    "ultimate-fastpath": 2,
    "parisc-firmware": 2,
    "somuchstuff-pdp8": 2,
    "bretjohnson": 2,
    "square7-vintage": 2,
    "biblionik-bull": 1,
    "biblionik-goupil": 1,          # same host, same EOL CentOS 7, same single connection
    # ONE. See MIN_INTERVAL: a pacer spaces requests but does not stop eight being in flight,
    # and eight is what broke the dreamlandbbs fetch an hour after it broke this one.
    "openpa": 1,
    # ONE, because eight was what actually broke this fetch -- see MIN_INTERVAL above. A pacer
    # spaces requests; it does not stop eight of them being in flight at the same moment.
    "dreamlandbbs-os2": 1,
    "abc-bladet": 2,
    "decromancer-bits": 2,

    # A hobby community host serving 50 GB. Three connections: enough to keep a 50 GB fetch
    # moving, few enough that it stays a background load on somebody's volunteer machine. The
    # nekoware community has already had to relocate once.
    "irixnet-ftp": 3,

    # ONE CONNECTION, AND THE REASON IS A MISTAKE THIS PROJECT MADE. On 2026-09-08 a seeded run
    # against dialectronics.com used the default eight workers and issued several hundred requests
    # in a few minutes. It began cleanly -- 197 files -- and then EVERYTHING timed out: 783 ×
    # WinError 10060, and `curl`, which had answered the same host in 0.06 s forty minutes
    # earlier, stopped getting through as well.
    #
    # The likeliest reading is that the server, or something in front of it, started refusing us.
    # A research pass reading the same site with single unhurried requests had no trouble at all.
    # So this is not a network fault to be retried harder; it is a small server that was leaned on
    # too heavily, and the remedy is to stop leaning.
    #
    # One connection. If that still fails, the answer is to wait a day, not to add workers.
    "dialectronics": 1,
    "gsi-collection": 3,
}

CHUNK = 1 << 16
CONNECT_TIMEOUT = 30

# A HOST THAT IS SLOW TO *GENERATE* A LISTING IS NOT A HOST THAT IS DOWN, and 30 s cannot tell
# the difference. so-much-stuff.com is the case: `trunk/pdp8/src/dec/` and `src/decus/` answer
# 200 with 108 KB and 136 KB -- small pages -- but take 90 s and 128 s to produce. Four retries
# at 30 s each is four failures and a WARNING, not a recovery, because the problem is not
# transient and more attempts do not make the server faster.
#
# What was at stake: those two listings carry 1 295 and 1 750 links. They ARE the DEC and DECUS
# program libraries, i.e. the reason the site was taken at all. A run that reported INCOMPLETE
# with three unreadable listings had quietly missed the point of the archive.
#
# Per archive rather than global: raising it everywhere would make a genuinely dead host hold a
# worker for two minutes before saying so, and most of this collection's hosts answer in under a
# second.  [2026-09-14]
TIMEOUT_BY_ARCHIVE = {
    "somuchstuff-pdp8": 240,
}
_timeout_state = {"value": CONNECT_TIMEOUT}


def set_timeout(archive):
    """Called once per run, beside set_pace(). No entry means the ordinary 30 s."""
    _timeout_state["value"] = TIMEOUT_BY_ARCHIVE.get(archive, CONNECT_TIMEOUT)
    return _timeout_state["value"]


ATTEMPTS = 4

# 1, 2, 4 seconds before the second, third and fourth attempt -- exactly what two hand-written
# `time.sleep(2 ** attempt)` calls did. Named once so the two retry loops cannot drift apart, and
# so the shape is visible without reading either of them.
RETRY = Backoff(first=1, factor=2)

# The pacer keys per host; a run mirrors one archive, so there is one key and its name says so.
PACE_KEY = "the archive being mirrored"
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


# HTML_PAGE LIVED HERE, AND IS RETIRED. [2026-09-23] It was `\.(?:[psx]?html?|php)$` -- "a page
# to be walked as well as saved, for the HTML_CRAWL archives" -- and that question is now
# common.looks_like_a_document(), which answers it for every tool rather than for this one.
#
# The name is left standing in the notes above and below because the extension set it knew is
# part of two defects this file records, and those happened to HTML_PAGE; renaming them would
# make the record say something that is not true. The incident prose moved to common.py, beside
# DOCUMENT_EXTENSIONS, which is where it explains something.
#
# WHAT CHANGED AND WHAT DID NOT. The library's set is a strict superset of the pattern's nine
# extensions, and adds `.xht` and `.php3`.
#
# THE FIRST MEASUREMENT OF "IT LOSES NOTHING" SAID THE CLAIM WAS FALSE. Over all 9 255 290 raw
# hrefs in the collection the two disagree 50 times: every one an href ending in a NEWLINE, where
# the pattern's `$` matches and endswith does not. The reasoning that had called that impossible
# -- an attribute pattern cannot cross a newline -- was simply wrong, and only measuring said so.
#
# Reading the 50 settled it the other way round. All of them are absolute URLs to OTHER hosts,
# in two link-list archives (gsi-collection, hp-alphaserver-2008), and so are the only six links
# the wider set gains -- `.php3`, none of them on a host we mirror. Re-measured over the 4 907 357
# CHILDREN rather than the raw hrefs: the two answers disagree ZERO times.
#
# NOTE WHICH GUARD DOES THAT, because it is not the obvious one. parse_listing drops an off-host
# href by itself only when allow_up is false -- and allow_up IS html_crawl, so on exactly the
# archives where this page test runs, off-host links come through. What stops them is
# `child.startswith(base_url)` above, ~90 lines before this. A test pinning only the first guard
# would pass while saying nothing about the path that matters; common_test.py pins the ORDER of
# the two, together with the retired pattern itself, because after this point nothing else in
# the tree remembers what HTML_PAGE was.
#
# Query strings are still gone by then: is_child_link drops anything containing '?'.


# Names a web server would serve for a bare directory. A link to one of these that 404s may still
# have its directory served as a generated listing -- see index_page_parent().
INDEX_NAMES = ("index.html", "index.htm", "index.php", "index.shtml",
               "default.html", "default.htm", "default.asp")


def index_page_parent(url, base_url):
    """-> the directory URL to try when `url` is a missing index page, else None.

    `http://h/site/betas/index.html` -> `http://h/site/betas/`. Returns None for anything that is
    not an index page, or whose directory would fall outside base_url -- the second guard matters
    because the root's own index.html would otherwise resolve to the parent of the whole archive.
    """
    path = urllib.parse.urlsplit(url).path
    if path.rsplit("/", 1)[-1].lower() not in INDEX_NAMES:
        return None
    parent = url[:url.rindex("/") + 1]
    return parent if parent.startswith(base_url) and parent != url else None


# WHAT THE LINK RULES COST BEFORE THEY WERE RULES
#
# The rules themselves moved to common.py on 2026-09-22 and are abstract there, as they should
# be: `is_child_link` has no business knowing which archive taught it something. What it cost,
# and where, is archive knowledge and belongs here, beside the urls.
#
# Each of these was a run that reported SUCCESS. Not one of them failed, retried or logged an
# error -- which is why they are written down rather than remembered.
#
#   A FRAGMENT KEPT AS A FILENAME. IBM's TechLibrary CD links its own pages by anchor, and the
#   crawler stored `toc.html#1` through `toc.html#8` as eight files beside the real page. 1 300
#   such files, every one a byte-identical duplicate, and the source was asked for each of them.
#   -> common.strip_fragment  [2026-09-03]
#
#   SORT LINKS FOLLOWED AS CONTENT. Every Apache index carries `?C=N;O=D` once per column and
#   direction. Measured on one directory: 34 requests where 26 would do, and the same listing
#   parsed six times over. -> the query rule in common.is_child_link
#
#   ABSOLUTE PATHS REFUSED AS "PARENT DIRECTORY" LINKS. ps-2.kev009.com addresses its whole
#   archive from the landing page with paths rooted at `/`. Rejecting those found THREE
#   DIRECTORIES AND EIGHT FILES on a site holding tens of thousands, and the run reported
#   complete. -> the absolute-path allowance in common.is_child_link
#
#   `..` REFUSED ON A HAND-WRITTEN TREE. The TechLibrary CD navigates from
#   manuals/adoclib/aixgen/wxinfnav/aixprggd.html to ../../aixprggd/kernextc/toc.html -- up two,
#   then down into a sibling, resolving well inside base_url. Dropping it fetched 6 523 files
#   where 15 298 exist, with zero failures reported. -> allow_up  [2026-09-03]
#
#   A QUALIFIED URL TREATED AS OFF-SITE. technologists.com/sauer/ links its own PDFs as
#   https://technologists.com/sauer/<name>.pdf. ONE file was fetched from a directory of
#   thirteen -- the only one written as a bare path -- and the run reported complete.
#   -> allow_up  [2026-09-08]
#
#   A DIRECTORY STORED AS A FILE. ibiblio answers an https request with an http Location, so a
#   whole-string comparison of "same path plus slash" failed on the scheme. Four directories
#   named *.html were written as 122 KB index pages, and on the next run each blocked its own
#   contents: 2 416 files logged LOST, "a file occupies a parent directory of this path". The
#   clause meant to prevent exactly this had been in place since 2026-08-26.
#   -> common.same_path_plus_slash  [2026-09-11]
#
#   A CACHE-BUSTER ON A PHOTOGRAPH. ardent-tool writes its planar photographs as
#   `<img src="Lacuna.gif?v=3">`. The query rule above is right for links and wrong for images;
#   Lacuna.gif answers 200 at the source and was never requested. Found by asking the ORIGIN
#   about 12 of the auditor's remaining "absent images": six answered 200 and six answered 404,
#   half real gaps and half the source's own dead references, and no amount of reasoning about
#   paths would have separated them. -> common.strip_cache_buster  [2026-09-11]
#
#   THE SYMLINK CYCLE. ftp.funet.fi/pub/unix/tools/less/ holds a link named `xemacs` pointing
#   back into itself. Over HTTP that is an infinitely deep tree of urls that are each one new, so
#   `seen` never fires. 42 levels and 68.69 GB -- the same files fetched forty times -- inside a
#   directory whose real content is a few hundred kilobytes. Killed by hand; the wreckage, 64.59
#   GB of which 64.55 GB was repetition, was deleted on 2026-09-10. The full account is in the
#   funet-unix entry in ARCHIVES. -> common.looks_like_a_loop  [2026-09-08]


def effective_base(base_url):
    """-> the base URL to actually use, following an http -> https redirect of the base itself.

    A SITE THAT UPGRADES TO HTTPS OTHERWISE LOSES EVERY FILE, SILENTLY. The producer resolves each
    link against the page's FINAL url -- correct, and since 2026-08-26 deliberate -- and then keeps
    it only if `child.startswith(base_url)`. When base_url is `http://host/path/` and the host
    redirects to `https://`, every resolved child begins `https://` and the test fails for all of
    them. The crawl fetches the landing page, finds nothing under the root, and reports COMPLETE
    over an empty archive.

    Found on 2026-09-08 at www.sco.com/developers/devspecs/, where a reachability probe with the
    same flaw reported "0 of 43 links stay under the root" for a page that links its files
    perfectly normally. The archive was saved only because it also had seeds. TWENTY-SIX of this
    file's archives carry an `http://` base; any of them that starts redirecting acquires this
    failure silently and without warning.

    Asking once, here, costs one request per archive per run and fixes it at the root rather than
    patching the comparison in the three places that make it. Only a SCHEME change is followed: a
    redirect to a different host or path is a different question, and is left alone so that the
    later `startswith` still catches it.
    """
    if not base_url.startswith("http://"):
        return base_url
    try:
        with http_open(base_url, timeout=30, method="HEAD") as r:
            final = r.geturl()
    except Exception:                                          # noqa: BLE001
        # Unreachable, or a host that dislikes HEAD. Not this function's problem: the crawl will
        # report the failure properly. Guessing a scheme here would be worse than leaving it.
        return base_url
    if final == "https://" + base_url[len("http://"):]:
        print("    base URL upgraded to https by the server: %s" % final, flush=True)
        return final
    return base_url


# UNESCAPE BEFORE EVERY OTHER TEST, and the reason is a twenty-year-old anti-spam trick.
# www.abc.se writes its address as
#     href="&#109;&#097;&#105;&#108;&#116;&#111;&#058;info@..."
# which is `mailto:` in numeric character references. Until 2026-09-15 the entities were decoded
# only at the very END of parse_listing, so every test before that saw the raw string: the scheme
# rejection could not recognise `mailto:`, and strip_fragment() split the text at the '#' of
# `&#109;` and returned a single ampersand. is_child_link('&') is True, so the crawler requested
# `<base>/&` and counted the 404 among the archive's permanent losses.
#
# Nothing was lost -- no such file exists anywhere in this collection -- but the noise was real,
# and a genuine filename written with entities would have been mangled exactly the same way.
# Found by pages-to-urllist.py on its first run against a second archive, which is the whole
# argument for testing a new tool somewhere other than the case it was written for.


# ------------------------------------------------------------------------------- fs paths


# Paths this run may skip without asking the source, and the count of times that happened.
# Empty unless --trust-index is given, so every other run behaves exactly as before.
_TRUSTED = frozenset()


def load_trusted_index(root, log):
    """-> the set of absolute paths listed in this archive's .sha256sum, for --trust-index.

    WHY THIS EXISTS. download() cannot tell that a file is already held until AFTER it has
    requested it: the size in a directory listing is rounded, and Content-Length is the only
    exact figure. So a re-run over a finished archive spends one HTTP request per held file to
    confirm what it already has -- 26 323 of them for `oldskool`, two hours at one connection,
    and every one of those requests lands on somebody else's server.

    The index is better evidence than the request anyway. `--index` hashed these files and
    `verify-content.py` read them back; a rounded listing size never established that much.

    WHAT IT GIVES UP, SAID PLAINLY: a file the SOURCE has replaced since the index was written
    will not be noticed, because nothing asks the source about it. That is why this is a flag
    and not the default. Use it on an archive whose index is current -- the run after a
    verify -- and leave it off when the point of the run is to pick up changes upstream.

    The format is `<hash> *<path>`, ONE space and a star. Splitting it wrong has already cost
    this collection a "0 of 7 890 held" that was really 7 871 -- see the lesson on clean zeros.
    """
    path = os.path.join(root, SUMS_FILE)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        log.line("TRUST-INDEX UNAVAILABLE: %s (%s) -- every held file will be re-checked "
                 "against the source, as without the flag" % (path, exc.__class__.__name__))
        return frozenset()

    out = set()
    malformed = 0
    for ln in lines:
        if not ln.strip():
            continue
        part = ln.split(" *", 1)
        if len(part) != 2 or not part[1]:
            malformed += 1
            continue
        out.add(os.path.join(root, *[p for p in part[1].split("/") if p]))

    # A LOUD REFUSAL BEATS A QUIET HALF-TRUST. If the file did not parse the way this function
    # expects, the right answer is to trust none of it rather than a fraction, because the
    # fraction that failed to parse is exactly the fraction that would then be re-fetched or,
    # worse, silently considered absent.
    if malformed:
        log.line("TRUST-INDEX REFUSED: %d of %d lines in %s are not `<hash> *<path>` -- "
                 "falling back to asking the source for every file"
                 % (malformed, len(lines), path), error=True)
        return frozenset()
    return frozenset(out)


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
        self.trusted = 0        # skipped on the index, without asking the source
        self.listfail = 0
        self.enum_done = False
        # WHAT STOPS A RUN WHOSE HOST HAS GONE AWAY. See `abandon` in worker() and in the
        # producer; the limit is set in the run itself, because a Stats() is built before the
        # arguments are known.
        self.patience = Patience()
        self.abandon = None
        # download() leaves the last attempt's verdict here: a short label when the request never
        # reached the wire, None when the host was actually asked and stayed silent.
        self.unreached = None


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

        # A DENOMINATOR SMALLER THAN THE NUMERATOR IS NOT A DENOMINATOR. found_bytes only counts
        # sizes the listing supplied, and an <img src> supplies none -- so on an image-heavy
        # hand-written site the estimate is a small fraction of what is really being fetched.
        # crashing-org printed "188.6M/2.9M", which reads as either 6000% complete or a broken
        # counter. Zero was already shown as "?"; a provably-too-small figure now is too, because
        # it is exactly as unknown and considerably more misleading.
        if found_bytes and found_bytes >= byts:
            total_bytes = human(found_bytes)
        else:
            total_bytes = "?"

        log.line(
            "PROGRESS %d/%s files (%.1f/s now, %.1f/s avg)  %s/%s (%s/s now, %s/s avg)  "
            "dirs %d  skip %d  retry %d  403 %d  fail %d  collide %d  lostdir %d%s"
            % (done, total, cur_fps, avg_fps,
               human(byts), total_bytes,
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
    _pace()
    return http_open(url, timeout=_timeout_state["value"], quote=True)


# CONNECTIONS AND RATE ARE TWO DIFFERENT THINGS, and until 2026-09-13 this file had a lever for
# only one of them. dialectronics.com is the case that proves they are not the same:
#
#   2026-09-08  a run at the default EIGHT workers -> 783 x WinError 10060, and the host stopped
#               answering curl as well. Set to ONE connection.
#   2026-09-13  a run at ONE connection -> 19 failures and 18 unreadable listings, same error.
#               So concurrency was never the trigger.
#   2026-09-13  five requests by hand, FOUR SECONDS APART: every one answered 200 in 0.07-0.28 s,
#               including the two files stuck as *.part since the incident.
#
# One connection with no pause is still ten requests a second, because each answer arrives in a
# tenth of a second and the next request leaves immediately. The host limits the RATE. Nothing in
# WORKERS_BY_ARCHIVE can express that.
#
# The floor is global per run, not per thread: with three workers, three threads each sleeping
# "their" interval would still produce three times the rate. One lock, one timestamp.
MIN_INTERVAL = {
    # 1.5 s. Not measured against a refusal -- this host has given no sign of minding -- but
    # chosen for the same reason as the two workers above: the page asked crawlers not to follow
    # its links, we decided the request does not reach a preservation copy, and the least we owe
    # it is a pace nobody would notice. 571 files at 1.5 s is a quarter of an hour.
    "develooper-hpux": 1.5,

    # 4.0 s, AND THE FIRST GUESS WAS 1.0 s. That guess was not measured -- it was picked because
    # it sounded generous next to ten requests a second, and it failed the same way as before:
    # PACED 1.00 s in the log, and still WinError 10060, five FAIL, six LISTFAIL and seventeen
    # retries by the hundredth file. The only thing actually measured was FOUR SECONDS, which is
    # what the hand probe used when all five requests answered 200. So that is the number here.
    #
    # 372 files plus ~106 listings at 4 s is about half an hour for a 23 MB archive. That is the
    # honest price of a host that will not be hurried, and it is cheaper than the alternative,
    # which is being unable to fetch it at all.
    #
    # AND 4.0 s IS STILL UNTESTED AGAINST A FULL RUN, because the 1.0 s attempt cost us the
    # chance to try it. TWO MINUTES after that run was stopped, the SITE ROOT -- which had
    # answered in 0.21 s twenty minutes earlier -- timed out as well. So this host does not
    # throttle the next request, it PUTS THE CALLER IN A PENALTY STATE that outlasts a two-minute
    # pause and reaches pages we were not even asking for.
    #
    # Third time this collection has tripped it, and the second time by guessing instead of
    # measuring. Before any attempt: leave it alone for hours, then confirm BY HAND that the root
    # answers, and only then start a run.
    #
    # AND 4.0 s FAILED TOO, WHICH FINALLY SETTLED WHAT THIS HOST LIMITS. The 2026-09-13 run at
    # 4 s ran CLEAN FOR SIXTEEN MINUTES and then collapsed into WinError 10060:
    #
    #     15:09:45  start, paced 4.00 s, hand probe beforehand: 200 in 0.18 s
    #     15:25:43  first failure, at 122 files + 105 directories = 227 REQUESTS
    #
    # IT IS A COUNT PER WINDOW. Not a rate, not concurrency. Slowing down does not avoid the
    # quota, it only postpones reaching it -- which is why one connection failed, why 1 s failed,
    # and why 4 s failed at about the same place. Three diagnoses in a row, each plausible, each
    # disproved by the next measurement, and each of them mine.
    #
    # WHAT WORKS IS A SCHEDULE, and the evidence is that every attempt still gains ground:
    # 199 -> 235 -> 240 -> 255 files over four runs, and the last one completed both leftover
    # *.part files. One run costs the host ~230 requests and costs us an hour of penalty
    # afterwards. Two or three more sessions, hours apart, should finish the archive.
    #
    # The 4.0 s stays. It is not what unblocks this host, but it is what a 23 MB archive on one
    # person's server deserves either way.
    #
    # AND ON 2026-09-16 THE SCHEDULE STOPPED WORKING, which is the part that changes the plan.
    # The prediction above was "two or three more sessions should finish the archive", on the
    # evidence that every run gained: 199 -> 235 -> 240 -> 255. This run gained NOTHING.
    #
    #     hand probe first: root answered 200 in 0.2 s
    #     07:05 - 07:20    clean, zero failures        (sixteen minutes, exactly as before)
    #     07:21 - 07:50    6 ok/min with 2-4 failures
    #     07:51 - 07:57    CLEAN AGAIN -- it recovers mid-run
    #     07:58 - 08:02    mixed, then the run ended
    #     totals           377 ok, 108 failed, 259 files before and 259 after
    #
    # WHY A RUN CAN SPEND 377 REQUESTS AND GAIN NOTHING. HTML_CRAWL means producer() re-fetches
    # every page it already holds in order to read its links -- see the ps-2 note. The window
    # budget is therefore spent on RE-ENUMERATION FIRST and on missing files last. Early runs
    # gained because little was held, so new files came early in the walk; now 259 of ~372 are
    # held, the re-walk consumes the budget, and the penalty starts before the walk reaches
    # anything new. THE PROGRESS CURVE FLATTENS BY CONSTRUCTION, and 255 -> 259 -> 259 is that
    # curve reaching zero. More sessions will not fix it; they will each buy one or two files.
    #
    # The failures are WinError 10060 at exactly 21.1 s -- Windows' TCP CONNECT timeout, not a
    # read timeout. So TIMEOUT_BY_ARCHIVE cannot help, and this is not about file size either:
    # /Minix/index.shtml is a few kilobytes and fails identically to a 2 MB photograph. 79 of the
    # 108 failures fall under /HomeRepair/ only because that is where the walk happened to be.
    #
    # WHAT TO DO INSTEAD: fetch the KNOWN-MISSING LIST DIRECTLY, with http-subset-fetch.py. This
    # run left a precise one -- 19 directory listings that could not be read, 21 files given up
    # after four attempts, 2 genuine 404s -- and that list is EVIDENCE, not claims: every entry is
    # something the crawler actually requested and actually failed to get. That is the distinction
    # that killed the earlier attempt here, when a list built from page links produced two answers
    # and both were 404. About 40 requests, every one of them buying a missing file, against a
    # budget of roughly 227.
    #
    # After this run the root is unreachable again -- DNS resolves to 89.58.44.21, no connection.
    # Leave it alone for hours; the penalty outlasts the run.  [2026-09-16]
    #
    # SECOND WINDOW THE SAME DAY, AND THE TARGETED APPROACH WORKED. Root hand-probed at 10:31 --
    # 200 in 0.38 s, two and a half hours after the crawl was stopped. Then subset-refetch.py
    # instead of a crawl: 28 requests total, 20 files gained, ZERO transport failures.
    #
    #     259 -> 279 files. The whole of trip/ -- post1..post17, equip, TheLastPiece.
    #
    # AND THE "40 MISSING" LIST WAS WRONG, which is worth more than the files. The crawl's own
    # warning reads "19 directory listings could not be read; every file below them is missing."
    # For an HTML_CRAWL archive that sentence is misleading: 36 of those 40 URLs were ALREADY ON
    # DISK with their 2009 Last-Modified intact. What failed was re-fetching pages we hold in
    # order to walk their links -- not the content below them. Only four were genuinely absent,
    # and one of those (PowerPC/RISCV) is a 404.
    #
    # THE 158 THAT LOOK MISSING ARE 156 PHOTOGRAPHS THE SERVER NO LONGER HAS. Walking every
    # stored page finds 268 internal references and 158 with nothing on disk -- the same 158 that
    # produced a fetch list in an earlier session, where two were checked and both 404. This time
    # the IMAGES themselves were checked rather than the two HTML pages: trip2/images/P0000004.jpg
    # and P0000031.jpg, both 404. trip2/index.shtml and trip2/images2.html are 404 as well. The
    # trip2 gallery was removed from the server; its pages still link every photograph.
    #
    # STILL ONLY A SAMPLE OF TWO. A third window should test perhaps ten spread across the range
    # before the gallery is written down as a loss -- when it was tried here the host had already
    # stopped answering, and an unanswered question is not a no. Everything else is held.
    #   [2026-09-16]
    #
    # THIRD WINDOW, AND THE TOLERANCE IS NOT CONSTANT -- IT SHRINKS. Root hand-probed at 12:04:
    # 200 in 0.26 s, so the penalty had lifted after about seventy minutes. The ten-image sample
    # then died after FIVE requests:
    #
    #     crawl        07:05    377 requests before the first failure
    #     targeted     10:31     28 requests, every one clean
    #     sample       12:04      2 clean, then three connect failures in a row
    #
    # 377, then 28 clean, then 2. Each trip costs tolerance in the NEXT window as well as the
    # current one, which is how fail2ban and its relatives are normally configured -- the ban
    # lengthens and the threshold drops with repeat offences on the same day.
    #
    # SO THE RULE FOR THIS HOST IS ONE TARGETED RUN PER DAY, NOT ONE PER WINDOW. The 10:31 run is
    # the model: hand-probe, spend a small measured list, stop while it is still answering. What
    # broke the pattern today was going back a third time for a sample that could have waited --
    # the files were already safe, and the question being answered was only "how shall this loss
    # be worded".
    #
    # Sample now stands at THREE of 156 -- P0000004, P0000025, P0000031, all 404, plus
    # trip2/index.shtml and trip2/images2.html. The gallery is very probably gone. 153 remain
    # untested and MUST NOT be written into a marker as confirmed losses on that basis.
    #   [2026-09-16]
    #
    # "ONE TARGETED RUN PER DAY" WAS WRONG TOO, and it lasted a day. The rule above assumed the
    # tolerance refills overnight. Measured 2026-09-17 at 08:07, about twenty hours after the
    # last trip:
    #
    #     08:07  root answers 200 in 0.20 s        <- looks recovered
    #            sample: P0000004 404, P0000025 404, then three connect timeouts
    #     08:20  ROOT ITSELF fails at 21.1 s, and so does a page we already hold
    #
    # Two requests. The same two that worked yesterday, the same three that did not. The root
    # probe that precedes every attempt is itself one of the requests, so the budget after a full
    # night was about THREE -- not the 28 of yesterday's targeted run and nowhere near 377.
    #
    # The distinguishing measurement was asking for a KNOWN-GOOD url after the failures: the root
    # and a held page both time out identically, so it is a host-wide block and not something
    # about those image URLs. Without that one request the obvious reading would have been "those
    # files are simply unreachable", which is the wrong shape entirely.
    #
    # SO THIS ARCHIVE IS DONE AT 279 FILES. Not because the question is answered but because the
    # host will not grant the requests to answer it, and each attempt spends goodwill on a
    # volunteer's machine for a gallery that three independent 404s say is gone. Stop asking.
    # If it is ever revisited, the first probe is the budget -- there is no free look.  [2026-09-17]
    #
    # CLOSED 2026-09-19 WITHOUT ANOTHER REQUEST TO THE HOST: 276 files, marker written, every byte
    # verified. The open question was settled from the INTERNET ARCHIVE in one CDX prefix query:
    # it captured all sixteen trip2 pages on 2020-10-29 and NOT ONE of the 156 images they link.
    # With the host's three 404s that is two independent sources saying the gallery is gone, and
    # the claim written into the marker is "on no source we can reach", not "deleted". A local walk
    # of all 268 references on the stored pages found nothing else missing. When a host will not
    # answer, ask the Archive before asking the host again.
    #
    # 2026-09-15: A SHORTCUT WAS TRIED AND IT FAILED TWICE OVER. pages-to-urllist.py read the 41
    # stored pages and produced 158 files they name and the tree lacks -- the idea being to spend
    # the whole quota on files instead of losing half of it re-walking 118 known directories.
    #
    # The host cut us off after TWO answers, so the quota from 2026-09-13 had not reset, or the
    # hand probes beforehand re-armed it. Nothing was fetched.
    #
    # And both answers were HTTP 404. 156 of the 158 were images in one directory that the pages
    # link and the server does not have. The list was a list of LINKS, presented here as a list of
    # missing files -- the exact confusion this file warns about everywhere else, made by the
    # person writing the warnings.
    #
    # THE CRAWL REMAINS THE RIGHT INSTRUMENT for this archive, and the reason is now explicit: it
    # works from DIRECTORY LISTINGS, which are the server's own statement of what it has. The
    # pages are somebody's claim about what it had. 372 files is a listing figure and can be
    # trusted; 158 was a page figure and could not.
    "dialectronics": 4.0,

    # 4.0 s, AND IT IS A REPEAT OF THE ENTRY ABOVE -- same symptom, same cause, three weeks later.
    #
    # vgamuseum-doc was added on 2026-09-26 and run at the defaults: eight connections, no pause.
    # The first pass took 1 142 of 2 261 files (1.91 GB) with 2 failures and 34 unreadable
    # listings. The retry attempted 195 files and fetched ZERO BYTES, with 18 failures and 60
    # unreadable listings. A single request by hand afterwards did not complete the TLS handshake
    # at all. That progression -- works, degrades, then refuses at the transport layer -- is the
    # dialectronics penalty state, on a small Joomla site run by one person.
    #
    # NOTHING WAS RETRIED AFTER THAT, and no second route was tried: not HTTP instead of HTTPS,
    # not another user agent. Route-shopping around a block is the thing this collection does not
    # do, and a block is the operator answering even when no human typed it.
    #
    # THE LESSON WAS ALREADY WRITTEN DOWN AND DID NOT APPLY ITSELF. Everything needed to avoid
    # this sits in dialectronics own note above. What was missing is that a NEW archive inherits
    # the defaults silently: nothing asks whether the host is a national mirror or one person is
    # hobby before the first run at eight connections.
    #
    # 4.0 s is copied from dialectronics because it is the only interval ever MEASURED against a
    # refusal here; for this host it is a guess. The archive stays INCOMPLETE until the block
    # lifts, and a retry should be days away and at this pace from the very first request.
    "vgamuseum-doc": 4.0,

    # ADDED BEFORE THE FIRST RUN ON 2026-09-26, AND MOST OF THEM TAKEN OUT AGAIN THE SAME DAY.
    # The first version limited all six new archives out of caution, one hour after vgamuseum.info
    # blocked this collection. That was the right reflex and the wrong rule, and the owner said so:
    # only TWO hosts have ever actually refused us. A limit costs an hour of wall clock every time
    # the archive is re-fetched, forever, and a limit nobody can point to a reason for is a cost
    # with no purchase.
    #
    # SO THE RULE IS NOW: a host keeps a limit when it has SAID something -- by refusing, or in
    # words on its own pages. Precaution alone is not enough.
    #
    #   dialectronics    REFUSED, twice, measured at 4.0 s              kept
    #   vgamuseum-doc    REFUSED -- TLS handshake, same day             kept
    #   develooper-hpux  its page asks crawlers not to follow links     kept, pre-existing
    #   seds-frommert    says in words that fast spiders may be blocked kept
    #   obsolyte         says on its front page it runs on a SPARC IPX
    #                    with 64 MB of RAM -- the host describing its
    #                    own frailty is a statement too                 kept
    #   sgidepot, fjkraan, cmu-shadow, chipdb, iommu                    REMOVED
    #
    # iommu is the clearest of the five: the same person runs ps-2.kev009.com, from which this
    # collection has already taken 342 GB at eight connections and no pause, without incident.
    # That is evidence, not optimism. chipdb sits behind Cloudflare, so the origin is barely
    # touched at any rate we would use.
    #
    # 2.0 s and one connection. obsolyte.com states on its own front page what it is served from:
    # a SPARC IPX, 64 MB of RAM, a 500 MB disk, Red Hat 6.0/UltraLinux. Eight sockets onto a 1991
    # workstation is not a thing to do, and the archive is 38 MB either way.
    "obsolyte": 2.0,
    # 2.5 s. Not a refusal -- ASKED FOR IN WORDS, which is better evidence than silence: the site
    # says some spiders go "way too fast" and that access may be blocked.
    "seds-frommert": 2.5,

    # WHAT THIS HOST ACTUALLY DOES, measured across five runs over two days, because the pace is
    # NOT the variable it responds to:
    #
    #   2026-09-27 14:21  measuring at 0.5 s   177 pages, then timeouts
    #   2026-09-27 16:42  fetch at 3 s          timeout on the FIRST request
    #   2026-09-28 07:55  one probe             HTTP 200 in 0.4 s -- recovered overnight
    #   2026-09-28 08:12  fetch at 5 s, 1 conn  122 files, clean
    #   2026-09-28 08:52  fetch at 5 s, 1 conn  another ~24 files, then 45 outright failures
    #   2026-09-28 11:25  one probe             no answer, 42 s
    #
    # IT IS A REQUEST BUDGET AND NOT A RATE. Roughly 120 to 180 requests are served, whatever the
    # spacing, and then the host stops answering this address for hours. Slowing down further
    # does not buy more; it only stretches the same budget over a longer wall clock. 144 of the
    # measured 492 files are here after two days of trying.
    #
    # SO THE PACE BELOW IS NOT THE FIX AND NOTHING HERE IS. Either this archive is completed a
    # hundred files a day over a week of single runs, or it is left at what it has. That is a
    # decision about somebody else's server and it belongs to a person, not to a table.
    #
    # FIVE SECONDS, CHOSEN BY THE OWNER AFTER TWO HOSTS WERE LOST IN ONE DAY. A measuring run
    # at 0.5 s on 2026-09-27 cost this host for the rest of the day; the note in CANDIDATES
    # suggested 4 s and the instruction was 5. It is one person's site of a few hundred
    # hand-written articles and the whole archive is under 50 MB, so the slower figure costs
    # about ten minutes and buys the thing that actually matters.
    #
    # PROBED ONCE ON 2026-09-28 AT 23:18, twelve hours after the last request, and the answer was
    # the SAME REFUSAL rather than a new one. One HEAD on a page this collection already holds --
    # /about.html, chosen because a held path cannot be blamed for the silence -- gave URLError
    # after 42.4 s. The 2026-09-27 hand probe gave 42 s. Two measurements a day apart agreeing to
    # the second is not noise: it is a firewall dropping the SYN on a fixed timer, which is the
    # same state, not a deteriorating or a lifting one.
    #
    # WHY THE DURATION IS WORTH WRITING DOWN AT ALL. "Still blocked" is what both probes say and
    # it is the less useful half. A refusal that CHANGED its timing would mean somebody touched
    # the rule, and that is the only cheap signal available from outside -- there is nothing else
    # to read from a host that sends no bytes. So the next probe records its seconds too, and a
    # figure that is not 42 is the thing worth acting on.
    #
    # AND ON 2026-09-29 AT 09:10 THE FIGURE WAS NOT 42. The same probe, the same held page, ten
    # hours after the last one: HTTP 200 in 1.0 s. That is the signal the paragraph above was
    # written to look for, and it arrived the very next morning -- so the ban was roughly a day
    # long and not the "days" this note feared.
    #
    # WHAT WAS THEN TAKEN, AND WHAT WAS DELIBERATELY NOT. 30 urls the 2026-09-27/28 runs had given
    # up on, fetched by manifest-fetch.py --url-list at 5 s, ONE connection: 30 fetched, 0 gone,
    # 0 failed, 2.5 MB, every one a genuine article or image (find-html-imposters.py --pages found
    # no error page wearing a 200). The archive is at 174 files. NO CRAWL WAS RUN AND NO MARKER
    # WAS WRITTEN. The measurement floor is 492, so roughly 318 files remain, and reaching them
    # means walking the 46 pages whose links were never followed -- which is the decision the
    # paragraph above hands to a person, not a thing to do because the host happens to answer.
    #
    # THE URL LIST IS A RECORD, NOT A SCRATCH FILE: logs/openpa-wanted-2026-09-29.txt, built from
    # logs/errors-openpa.txt (FAIL + LISTFAIL), minus what was already held, minus the robots.txt
    # wildcard group. 91 urls named, 60 already held, 30 wanted, 0 forbidden -- the arithmetic is
    # in the file's header so the next run can check it rather than trust it.
    #
    # THE WILDCARD GROUP WAS RE-READ FROM THE HOST rather than from EXCLUDE, and it is worth the
    # request: 13 of the 30 sit under risc/images/, which LOOKS like the disallowed images/ and is
    # not it. robots.txt path rules anchor at the root, so `Disallow: /images/` reaches /images/
    # and nothing else. Matching it as a substring would have refused 13 files nobody refused.
    #
    # A CRAWL FOLLOWED AT 10:19 THE SAME MORNING AND THE HOST SHUT IT OFF AFTER FIVE MINUTES.
    # 5 s, one connection, --trust-index. It went perfectly and then stopped dead:
    #
    #     10:24  135 files  2.2/s   fail 0  lostdir 0
    #     10:29  181 files  0.0/s   fail 0  lostdir 0   first timeout at 10:28:27
    #     10:34  184 files  0.0/s   fail 2  lostdir 2
    #     10:55  184 files  0.0/s   fail 9  lostdir 9   killed by hand
    #
    # NOT ONE FILE AFTER 10:29, and twenty-six minutes of asking anyway. The budget today was
    # about 90 requests -- 30 clean on the url list at 09:20, then ~60 on the crawl. Compare
    # dialectronics: 377, then 28, then 2. The shape is the same and 5 s did not change it.
    #
    # SO THE 5 s IS NOT WHAT IS WRONG AND NEITHER IS THE CONNECTION COUNT. This host meters
    # REQUESTS PER DAY, not requests per second, and no pace expressible in this table can buy
    # more of them. The archive is at 184 files against a floor of 492. Either it is filled a
    # hundred a day over a week, or it stays where it is -- still a decision for a person.
    #
    # WHAT THE RUN ITSELF GOT WRONG, AND IS NOW FIXED. Nothing stopped it. common.Patience had
    # been written that same morning for manifest-fetch.py -- the tool that walks 30 urls in two
    # minutes with somebody watching -- and NOT for the tool that runs unattended for hours. The
    # nine "unreadable listings" it recorded are the worst of it: each is written down as a lost
    # subtree whose standing advice is "re-run to pick them up", and not one of them was
    # unreadable. See --give-up, the ABANDONED verdict, and give-up-test.py.
    #
    # 2026-09-30: THE SAME THING AGAIN, TO THE MINUTE, WHICH SETTLES WHAT IT IS. 36 hours of
    # quiet, one probe -> HTTP 200 in 0.3 s (0.3, against 1.0 the day before and 42 s of silence
    # before that -- the host recovers fully, and quickly). Then a url-list fetch of the 9 files
    # the cut-off crawl had failed on: 9 of 9, 0 failed, 1.0 MB, flawless at 5 s. Then a crawl at
    # the same 5 s and the same single connection:
    #
    #     23:17  135 files  2.2/s   fail 0      23:22  181  0.0/s  retry 1
    #     23:18  143 files  0.1/s   fail 0      23:24  181  0.0/s  fail 1
    #     23:19  170/177+   0.4/s   fail 0      23:27  184  0.0/s  fail 2   stopped here
    #     23:21  181/208+   0.1/s   fail 0
    #
    # Line for line the same progression as 2026-09-29, five minutes of health and then nothing.
    # TWO MEASUREMENTS A DAY APART AGREEING THIS CLOSELY ARE NOT A HOST HAVING A BAD DAY. This
    # host meters REQUESTS PER DAY -- roughly 60 on a crawl, ~90 counting the url list -- and no
    # figure in this table can buy more of them. The pace is not the lever; the only lever is how
    # many requests a session spends and on what.
    #
    # ^^ THAT PARAGRAPH IS WRONG AND IS KEPT BECAUSE OF HOW IT WAS GOT WRONG. On 2026-10-01 this
    # host answered 371 CONSECUTIVE REQUESTS WITHOUT ONE FAILURE -- 64 by hand, then 307 of a
    # 568-url list at 61 s -- before it stopped. Six times the ceiling asserted above.
    #
    # THE ERROR WAS NOT THE NUMBER, IT WAS THE WORD "DAY". Two crawls were cut off after about 60
    # requests each, which is a true observation; "therefore the budget is 60 a day" is an
    # explanation, and it was written in the voice of a measurement. The sentence that did the
    # damage is the one that sounds most careful -- "two measurements a day apart agreeing this
    # closely are not a host having a bad day". They agreed because they were the same experiment
    # run twice, and a repeated experiment confirms repeatability, not the reason. Both were
    # CRAWLS. Nothing had ever counted requests of another shape until the list runs did.
    #
    # WHAT IS MEASURED NOW, and stated as narrowly as the measurements allow:
    #
    #   371 url-list requests in one day   fine, 0 failures, 61 s apart        2026-10-01
    #    41 url-list requests in 6 minutes fine, 0 failures, ~7 per minute     2026-10-01
    #    ~60 crawl requests                cut off, twice, five minutes in     09-29, 09-30
    #
    # So it is not the count and not the rate. What differs is WHAT IS ASKED FOR: a crawl fetches
    # pages and directory listings, a list fetches static files. That is a hypothesis with one
    # distinguishing experiment left -- run a crawl AFTER a clean list run; if the crawl is cut
    # off while the list was not, the shape of the request is the variable. Until that is done,
    # "we do not know" is the honest entry, and it replaces an entry that claimed to know.
    #
    # ONE COINCIDENCE WORTH RECORDING WITHOUT A THEORY ATTACHED. dialectronics stopped at 377
    # requests; this host stopped at 371. Two unrelated one-person servers within 2 % of each
    # other suggests a common default -- fail2ban or a hoster's rule -- rather than two decisions.
    # Not acted on, because two points are two points; written down so a third can be compared.
    #
    # SO THE URL LIST IS THE INSTRUMENT FOR THIS ARCHIVE AND THE CRAWL IS NOT. A crawl spends its
    # whole budget re-walking pages already on disk -- 181 of the 184 it touched were skips --
    # while the url list spent 9 requests and got 9 files. --trust-index removes the DOWNLOADS
    # but not the LISTING requests, and on a hand-written site every page is both.
    #
    # --give-up 6 IS TOO GENEROUS HERE, AND THE REASON IS ARITHMETIC I DID NOT DO. The default
    # was chosen by counting incidents -- five in a row preceded every one -- without costing
    # them: a failure here is three retries against a ~40 s timeout, so ~2 minutes, and six of
    # those is twelve minutes of knocking. Use --give-up 2 on this host. The default stays 6
    # because the cost of a failure is a property of the run, not of the register.
    #
    # 2026-10-01: 40 FILES IN TWO URL-LIST RUNS, 0 FAILED, AND THE BAN LIFTS FASTER THAN FEARED.
    # Probe after only 12 hours -> HTTP 200 in 0.2 s. Then the prepared list: 16 documents first
    # (html, txt, pdf -- the substance, and each page names further links so the next harvest is
    # better for having them), then the 24 images. 4.6 + 1.6 MB, one 404, nothing failed. The
    # archive is at 233 files / 14 MB against a floor of 492 / 47.80 MB.
    #
    # THAT IS THE METHOD FOR THIS HOST, SETTLED OVER FOUR DAYS: probe once, spend a MEASURED LIST
    # of a few dozen urls, stop. Three crawls were cut off after five minutes each; three
    # url-list runs took 9, 16 and 24 files with not one failure. Same host, same pace, same day
    # in two of the cases -- the difference is that a crawl spends its budget re-walking pages
    # that are already on disk.
    #
    # THE ONE 404 IS WORTH ITS OWN PARAGRAPH, because it is a hole in EXCLUDE that no rule of
    # ours is wrong about. pa-risc_fabrication.html carries
    #
    #     <a href="mages/hp_ns-1_1987.jpg"><img src="images/hp_ns-1_1987.jpg" ...></a>
    #
    # -- the author's own typo, the `i` lost from the href while the img src beside it is right.
    # `images/hp_ns-1_1987.jpg` is refused by EXCLUDE and by robots.txt; `mages/...` is not,
    # because an exclusion is a PATH PREFIX and that path does not have the prefix. So a typo on
    # somebody else's page produced a request for a resource we are forbidden to ask for, under a
    # name we are allowed to ask for, and nothing in this file was wrong at any point.
    #
    # NOTHING IS BEING CHANGED ABOUT IT, AND THAT IS A DECISION RATHER THAN AN OVERSIGHT.
    # robots.txt disallows /images/; it does not disallow /mages/, and inventing a near-miss rule
    # -- refuse anything one edit away from an excluded prefix -- would have this collection
    # guessing at intent where the standard speaks about paths. The server answered 404, which is
    # the settled and correct answer, and no byte was taken. What is left is the knowledge that
    # if this site HAD served /mages/ as a second copy of /images/, we would have fetched it with
    # a clean conscience. Worth knowing; not worth a heuristic.
    #
    # 2026-10-01, THE EVENING RUN, AND THE FIRST TIME THE GUARD WAS THE ONE THAT STOPPED A RUN.
    # 568 urls at 61 s -- 61 and not 60 on the owner's reasoning, that a 60 s delay can drift two
    # requests into one 60-second accounting bucket while 61 s cannot. After 5.2 hours:
    #
    #     DONE fetched 300, gone from the source 5, failed 2, 29.6 MB
    #     STOPPED: 2 requests in a row went unanswered (URLError)
    #     261 of 568 urls were never tried. Nothing here says they are gone.
    #
    # COMPARE 2026-09-29 LINE BY LINE, because that is what the work in between bought: that run
    # kept asking for twenty-six minutes after the host went quiet, was ended by hand, and wrote
    # nine directories into the record as lost subtrees that had never been unreadable. This one
    # stopped itself after two silences, said how many urls it had NOT tried, and said that
    # nothing follows from that about whether they exist. Exit 1, no marker.
    #
    # THE ARCHIVE IS AT 556 FILES / 45 MB, which also corrects something unspoken: the measured
    # floor of 492 files / 47.80 MB was taken with images/ and systems/images/ excluded, so it
    # described the smaller half. The images are the bulk of this archive, not a supplement to it.
    # 261 urls remain, 0 of the 300 fetched were error pages wearing an image name, no .part was
    # left behind.
    "openpa": 5.0,

    # 0.3 s WAS WRONG AND THE HOST SAID SO WITHIN A MINUTE. The reasoning was that a BBS
    # filegate is built to serve downloads, unlike one person's homepage -- true, and beside the
    # point: MIN_INTERVAL paces requests, and --workers defaults to EIGHT, so eight connections
    # were opening against it at once. Sixty seconds in, eight urls had timed out twice each and
    # not one file below the index pages had arrived; a probe three minutes later timed out at
    # 21 s on both a page and a zip. Stopped at once.
    #
    # THE SECOND HOST LOST THE SAME WAY ON THE SAME DAY, after openpa. Both times the pace was
    # chosen from what the SITE looked like rather than from what the collection had already
    # learned, which is written in this very table: the four entries above are all hosts that
    # objected, and every one of them is at 1.5 s or slower.
    #
    # 4 s AND ONE WORKER when this is tried again, and not before the host has been left alone
    # for days -- see WORKERS_BY_ARCHIVE below, which is the half that actually mattered here.
    #
    # PROBED ONCE ON 2026-09-28 AT 23:19, twenty-four hours after the last request: one HEAD on
    # gfd/apparc/index.html, a page already held, URLError after 21.2 s. The 2026-09-27 probe was
    # 21 s on a page and a zip. Same reading as openpa above and for the same reason -- the timer
    # is stable, so the rule behind it is untouched, and a day is not the "days" this note asks
    # for. Both probes cost one request each and are logged in logs/probe-2026-09-28.log.
    "dreamlandbbs-os2": 4.0,

}
# ONE PACER FOR THE RUN, shared by every worker. This was six lines of lock-and-arithmetic here
# until 2026-09-25 and is now `common.Pacer`, which does the same thing and one thing better:
# it reserves a caller's slot and sleeps OUTSIDE the lock. The version here held the lock across
# the sleep -- correct, because a run paces one archive and therefore one host, and wrong the
# moment two hosts were paced by one object, since every worker would then queue behind whoever
# was sleeping however unrelated their host. Nothing in this file needs that yet; the library does.
_pacer = Pacer(0.0)
_pace_state = {"interval": 0.0}


def set_pace(archive):
    """Called once per run. No entry means no pause -- unchanged for every other archive."""
    _pace_state["interval"] = MIN_INTERVAL.get(archive, 0.0)
    _pacer.pause = _pace_state["interval"]
    return _pace_state["interval"]


def _pace():
    """Hold the floor between requests, across all workers. A no-op when no floor is set."""
    if not _pace_state["interval"]:
        return
    _pacer.wait(PACE_KEY)


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
            RETRY.wait(attempt)
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
    # This is the other half of the lighttpd column-order defect, written up in README.md. `/rs6000/` links a subdirectory without a
    # trailing slash, so the crawler asks for it as a file; once the directory is populated the
    # rename onto it fails with PermissionError, forever.
    if os.path.isdir(long_path(dest)):
        log.line("SKIPPED (a directory occupies this path) %s" % url)
        return "skip"

    # --trust-index: the archive's own verified index already says this file is held, so do not
    # spend a request on the question. Local stat only -- the file has to actually be there.
    if _TRUSTED and dest in _TRUSTED and os.path.exists(long_path(dest)):
        with stats.lock:
            stats.trusted += 1
        return "skip"

    # STOP BEFORE THE VOLUME IS FULL. Added 2026-09-06, when os2bbs was left to run unattended
    # overnight with 21 GB free on a 3.7 TB volume and this tool had no floor at all -- the
    # one-shot fsck-finish.py had one, the permanent tool did not. A filled disk does not just
    # end the fetch: it breaks every other writer on the volume, and this collection's own
    # checksum indexes are written to it.
    #
    # ASK THE ROOT, NOT THE DESTINATION. The first version of this guard called disk_usage() on
    # os.path.dirname(dest) -- a directory this function CREATES LATER, further down. Every file
    # whose parent did not exist yet raised FileNotFoundError [WinError 3] before a single byte
    # was requested, and the run ended `INCOMPLETE: 20719 failures` within seconds. A guard that
    # destroys the tool it protects is worse than no guard; the check must touch only a path that
    # is certain to exist, and ROOT is set in main() before any worker starts.
    #
    # Reported ONCE and then quietly, because the alternative is one identical line per queued
    # file, and a log that drowns its own conclusion is a log nobody reads to the end.
    global _disk_floor_hit
    try:
        free = shutil.disk_usage(ROOT if ROOT else os.path.abspath(os.sep)).free
    except OSError as exc:
        # Never let the guard itself fail a fetch -- that is the defect it was born from. Say so
        # once, loudly, and carry on unguarded rather than silently.
        if not _disk_floor_hit:
            _disk_floor_hit = True
            log.line("DISK FLOOR DISABLED: cannot read free space (%s) -- fetching unguarded"
                     % exc.__class__.__name__)
        free = None
    if free is not None and free < MIN_FREE_BYTES:
        if not _disk_floor_hit:
            _disk_floor_hit = True
            log.line("DISK FLOOR: under %.0f GB free -- stopping fetches. The archive stays "
                     "INCOMPLETE and resumes when there is room." % (MIN_FREE_BYTES / 1e9))
        return "fail"

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
                if final != url and same_path_plus_slash(url, final):
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

            # RETRIED, BECAUSE THE LAST STEP CAN LOSE A RACE. The rename fails on Windows with
            # WinError 32 -- "the process cannot access the file because it is being used by
            # another process" -- while the bytes are already on disk and already checked
            # against Content-Length. The download SUCCEEDED; only the rename lost.
            #
            # THE FIRST DIAGNOSIS WRITTEN HERE WAS WRONG, and it is left in the record because
            # the mistake is instructive. It said a virus scanner was holding the freshly
            # written .part file. Plausible, and not what happened: TWO mirror.py PROCESSES WERE
            # RUNNING AGAINST THE SAME ARCHIVE. A TaskStop had ended the shell wrapper and left
            # the Python process alive, a restart added a second, and the two raced each other
            # on the same .part names. The giveaway was two interleaved PROGRESS streams in one
            # log, with different file counts and different byte totals -- visible for an hour
            # before anyone read them side by side.
            #
            # 1 475 occurrences in that log, 104 of them final failures, nine .part fragments
            # left on disk, and every one of those files downloaded TWICE -- because the caller
            # retries the whole transfer when the write step fails.
            #
            # THE RETRY IS STILL RIGHT. A scanner really can hold a new file, single-run or not,
            # and the cost of being wrong in this direction is 1.5 s. It is NOT a bare retry
            # loop: only this rename, only PermissionError, and it re-raises after the last
            # attempt so a real permissions problem still surfaces as one. What it cannot fix is
            # two processes writing one tree -- nothing here can, and nothing here pretends to.
            rename_with_retry(tmp, dest)
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
            unreached = None
        except Exception as exc:  # noqa: BLE001 -- socket, DNS, TLS, disk; all retryable
            reason = "%s: %s" % (type(exc).__name__, exc)
            # DID THE REQUEST REACH THE WIRE AT ALL? Carried out of here because worker() decides
            # whether to abandon the run and cannot see this exception. Without it a dropped wifi
            # is written down as the host refusing us -- measured on manifest-fetch.py's openpa run
            # of 2026-10-02, which blamed a host that answered 200 a minute later.
            unreached = local_failure(exc)

        if attempt < ATTEMPTS - 1:
            with stats.lock:
                stats.retries += 1
            log.line("RETRY %d/%d %s %s" % (attempt + 1, ATTEMPTS - 1, reason, url), error=True)
            RETRY.wait(attempt)

    log.line("FAIL %s %s" % (reason, url), error=True)
    # THE LAST ATTEMPT'S VERDICT IS THE ONE THAT COUNTS. A file whose first try hit a dead resolver
    # and whose third timed out was reaching the host by the end, and the host is what the run has
    # to decide about.
    with stats.lock:
        stats.unreached = unreached
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
            # ONCE THE RUN IS ABANDONED THE QUEUE IS DRAINED, NOT WORKED. Every item still in
            # it is one more request at a host that has stopped answering, and the queue holds
            # up to 128 of them. They are not counted as failures either -- they were never
            # tried, and a file nobody asked for is not a file that is gone.
            with stats.lock:
                giving_up = stats.abandon is not None
            if giving_up:
                continue
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
                # THREE OF THE FOUR ARE THE SERVER ANSWERING and only the fourth is silence.
                # `permfail` is a 404 it chose to send, `skip` means the file is already here,
                # `ok` speaks for itself. `fail` is what is left after download() exhausted its
                # retries: a timeout, a refused connection, a reset -- or a 5xx repeated until
                # the ladder ran out, which is a host in trouble and equally a reason to stop.
                #
                # AND `fail` SPLITS AGAIN, which is the 2026-10-02 lesson: a failure that never
                # reached the wire -- DNS gone, no route, the wifi dropped -- is not the host's
                # silence and must not be recorded as it. download() leaves its verdict in
                # stats.unreached; see Patience.unreachable and local_failure.
                if result == "fail":
                    note = getattr(stats, "unreached", None)
                    spent = (stats.patience.unreachable(note) if note
                             else stats.patience.went_quiet("download"))
                    if spent and not stats.abandon:
                        stats.abandon = stats.patience.reason
                        log.line(stats.abandon, error=True)
                else:
                    stats.patience.answered()
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


# HOW OFTEN EACH EXCLUSION PATTERN ACTUALLY FIRED, per run. Module level because the producer
# walks in one thread and the report is written after it returns.
#
# WHY THIS EXISTS. On 2026-09-26 EXCLUDE["iommu"] read ("mirrors/",) while the path it had to
# match was `datasheets/mirrors/...` -- the archive's root is iommu.com/ and its content hangs
# one level down. The pattern named a directory that does not exist, matched nothing, and SAID
# NOTHING: 16 GB of the 78.8 GB it was written to prevent arrived before the total was noticed by
# eye. A wrong pattern and a right one are indistinguishable in the source and produce identical
# output.
#
# THE MATCHER WAS NEVER THE PROBLEM -- `rel.startswith(pattern)` does exactly what it says. What
# was missing is that nothing observed the pattern's EFFECT. A rule that governs nothing is the
# same shape as a rule that is working perfectly, and only a count can tell them apart.
EXCLUDE_HITS = {}


# How long to keep trying the final rename, and how long to wait between attempts. Five
# attempts over about 1.5 s: long enough for a scanner to let go, short enough that a genuine
# permissions problem is still reported promptly.
RENAME_ATTEMPTS = 5
RENAME_BACKOFF = 0.1


def rename_with_retry(tmp, dest, attempts=RENAME_ATTEMPTS, backoff=RENAME_BACKOFF,
                      sleep=time.sleep):
    """Move the finished download onto its real name, retrying a lost race.

    WHY THIS IS NOT PARANOIA. The bytes are already on disk and verified against Content-Length
    by the caller; the only thing that can fail here is the rename, and on Windows it fails for a
    reason that has nothing to do with this program -- a scanner holding the file it just saw
    appear. Giving up throws away a complete download.

    WHY IT IS STILL NARROW. Only PermissionError is retried, only this one operation, and the
    last attempt re-raises. A directory that has taken the path is handled above and separately;
    a real access problem still stops the file with its own error rather than being smoothed over.
    """
    for attempt in range(attempts):
        try:
            os.replace(long_path(tmp), long_path(dest))
            return attempt
        except PermissionError:
            if attempt == attempts - 1:
                raise
            sleep(backoff * (attempt + 1))
    raise AssertionError("unreachable")


def is_excluded(rel, patterns, name):
    """-> the pattern that matched, or None. THE ONLY PLACE THE COMPARISON IS WRITTEN.

    THERE WERE THREE COPIES, and that is how the counter came to be useless. `producer()` carries
    two -- one for a child link, one for the container a link reaches past -- and `fix_times()`
    carries a third. On 2026-09-27 a hit counter was added to the third, tested by eye, and
    reported nothing for a real run: --fix-times is rarely used and the crawl never reaches that
    line. The comment sitting six lines above the copy that was instrumented says exactly this --
    "a guard added to one of a pair is a guard the other walks past" -- and was read afterwards.

    So the comparison lives here, all three call it, and a test asserts that no fourth copy has
    been written. Counting is a side effect on purpose: a caller cannot use the check and forget
    to record it.
    """
    for pattern in patterns:
        if rel.startswith(pattern):
            EXCLUDE_HITS[(name, pattern)] = EXCLUDE_HITS.get((name, pattern), 0) + 1
            return pattern
    return None


def report_unused_excludes(name, log):
    """Name every exclusion pattern that never fired. Called once, after the walk."""
    patterns = EXCLUDE.get(name, ())
    if not patterns:
        return []
    dead = [p for p in patterns if not EXCLUDE_HITS.get((name, p))]
    for p in dead:
        log.line("EXCLUDE PATTERN NEVER FIRED: %r -- it governs nothing. Either the tree no "
                 "longer holds it, or the pattern is wrong. Patterns match the path RELATIVE TO "
                 "THE ARCHIVE ROOT, so a base URL of host/ needs `sub/dir/` and not `dir/`."
                 % p, error=True)
    for p in patterns:
        if EXCLUDE_HITS.get((name, p)):
            log.line("excluded %d path(s) by %r" % (EXCLUDE_HITS[(name, p)], p))
    return dead


def producer(q, base_url, stats, log, case_sensitive=False, alive=None, exclude=(), seeds=(),
             html_crawl=False, name_for_retired=None):
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
    # Directories NOBODY LINKED -- deduced from a file path that reached past the current
    # directory. Kept apart from the rest because a permanent error on one of these means
    # something different: see where it is read, below.
    inferred = set()
    # Case-folded local path -> the first URL that claimed it. On a case-insensitive volume
    # a second claimant would overwrite the first without any error being raised anywhere,
    # so the collision has to be caught here or it is not caught at all.
    claimed = {}

    # A SEED THAT IS A PAGE MUST BE KEPT, NOT ONLY WALKED. Seeds go into `pending`, which is the
    # queue of things to ENUMERATE; nothing put them on `q`, which is the queue of things to SAVE.
    # For a directory seed that is exactly right. For a page it silently loses the very file the
    # seed was written for.
    #
    # gate.crashing.org is the case. Its landing page links none of `doc/ppc/`, so 30 seeds were
    # added -- doc001.htm through doc028.htm, the Linux PowerPC Installation Guide. All 30 answered
    # 200. THREE FILES LANDED, and the run wrote a completion marker over them: `doc000.htm`, which
    # arrived only because one of the walked pages happened to link it, plus two images. The 28
    # documents the seeds named were read, parsed for links, and thrown away.
    #
    # This is R16 -- an HTML page is both content and a listing -- applied to discovered links and
    # not to seeds. The asymmetry is invisible in the log: the SEEDS line says 30, and the DONE
    # line says 3, and nothing connects them.  [2026-09-07]
    for s in starts[1:]:
        if s.endswith("/"):
            continue
        claimed[local_path("", base_url, s).lower()] = s
        with stats.lock:
            stats.found += 1
        put_item(q, (s, None, None), alive, log)

    while pending:
        # THE PRODUCER CHECKS TOO, and it has to: the workers stop asking for files, but
        # enumeration is a separate stream of requests -- one per directory listing -- and on
        # 2026-09-29 those were most of what kept reaching openpa.net after it had gone quiet.
        with stats.lock:
            if stats.abandon:
                log.line("ENUMERATION ABANDONED with %d listings unread. They are NOT recorded "
                         "as lost -- nothing asked for them." % len(pending), error=True)
                break
        url = pending.pop()
        try:
            # Rebind url to where the fetch actually ended up, so the relative links below
            # resolve against the right base. See fetch_text().
            body, url = fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            # BEFORE GIVING UP ON A MISSING index.html, ASK FOR ITS DIRECTORY.
            #
            # A mirrored site does not necessarily keep the shape it had. os-history.de linked
            # `betas/index.html`, `experimente/index.html`, `faq/index.html` and the rest, because
            # those files existed on its own host. infania mirrored the CONTENT of those
            # directories and not the entry pages, and its Apache generates a listing instead --
            # so `betas/index.html` is 404 while `betas/` answers 200 with everything in it.
            #
            # Without this, the crawler took the 404 at face value and stopped: 30 permanent 404s,
            # all of the form `<branch>/index.html`, and 165 files (2.43 MB) sitting one request
            # away behind them -- most of the site. Measured 2026-09-07 by asking for each
            # directory directly; every one answered 200.
            #
            # Narrow on purpose. Only a PERMANENT failure, only a URL whose last segment is an
            # index page, only a directory still inside base_url and not already seen. The 404 for
            # the file itself is still recorded, because that file really is absent -- what is
            # recovered is the subtree, not the page.  [2026-09-07]
            parent = index_page_parent(url, base_url)
            if (isinstance(exc, urllib.error.HTTPError) and exc.code in PERMANENT
                    and parent and parent not in seen):
                seen.add(parent)
                pending.append(parent)
                log.line("INDEX 404, TRYING ITS DIRECTORY %s -> %s" % (url, parent))
                continue
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
            # A DIRECTORY WE DEDUCED IS NOT A DIRECTORY THE SERVER PROMISED. `inferred` holds the
            # containers derived from file paths that reached past the current directory -- a
            # question this crawler asked on its own initiative, not a link anybody published. A
            # permanent error on one of those is the ANSWER to that question, not an amputated
            # subtree, and counting it as a lost listing holds the archive at INCOMPLETE over a
            # directory that does not exist.
            #
            # ibiblio's .../bootstrap/usr/doc/HTML/ is a hand-written page linking
            # ldp/META-FAQ.html, ldp/HOWTO-INDEX.html and four more. `ldp/` answers 404, and so
            # does every file the page names inside it -- while acc/demo.html beside them serves
            # 200 and `acc` redirects like a real directory should. Nothing is missing: the page
            # points at a directory that is not there. Measured before this branch was written.
            if isinstance(exc, urllib.error.HTTPError) and exc.code in PERMANENT \
                    and url in inferred:
                log.line("INFERRED DIRECTORY DOES NOT EXIST, HTTP %d %s -- nothing is missing, "
                         "no link named it" % (exc.code, url))
                continue
            # Counted, not just logged: an amputated subtree must be visible in the DONE
            # line and in the exit code, or an incomplete mirror looks like a clean one.
            with stats.lock:
                stats.listfail += 1
            log.line("LISTFAIL %s: %s %s" % (type(exc).__name__, exc, url), error=True)
            continue
        with stats.lock:
            stats.dirs += 1

        resolve_from = resolution_base(body, url, base_url)
        # images=html_crawl: follow <img src> on hand-written sites only. On a generated
        # directory index the only <img> are the server's own folder/file icons, which are noise
        # and are what EXCLUDE entries like ("icons/",) already exist to refuse.
        for href, size, mtime in parse_listing(body, allow_up=html_crawl, images=html_crawl):
            child = urllib.parse.urljoin(resolve_from, href)
            if not child.startswith(base_url) or child in seen:
                continue
            seen.add(child)

            # EXCLUDE APPLIES TO FILES TOO, and until 2026-09-08 it did not: the test sat inside
            # the `endswith("/")` branch, which was harmless only for as long as a file under an
            # excluded subtree could not be reached without first entering that subtree.
            #
            # Following <img src> ended that. `crashing-org` excludes `icons/`, and its pages
            # embed `<img src="../icons/next.gif">` -- a FILE reference that walked straight past
            # a rule the archive states explicitly. An exclusion is a decision about a subtree,
            # not about one way of arriving at it.
            #
            # Hoisted in BOTH walks. This function and fix_times() carry the same loop, and a
            # guard added to one of a pair is a guard the other walks past -- which is exactly how
            # the <base href> rule came to live in measure-remote.py and not here.
            rel = child[len(base_url):]
            if is_excluded(rel, exclude, name_for_retired):
                log.line("SKIPPED (excluded) %s" % child)
                continue

            if href.endswith("/"):
                loop = looks_like_a_loop(child, base_url)
                if loop:
                    log.line("LOOP REFUSED %s -- %s" % (child, loop), error=True)
                    continue
                pending.append(child)
            else:
                _why = is_retired(name_for_retired, child[len(base_url):])
                if _why:
                    # Removed on purpose once; fetching it again would undo that silently.
                    log.line("RETIRED, not fetched: %s -- %s" % (child, _why))
                    continue
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

                # A DIRECTORY REACHED ONLY THROUGH A FILE INSIDE IT IS NEVER LISTED, and that is
                # a hole no counter can show: the file arrives, the run is clean, and everything
                # ELSE in that directory is simply never known about.
                #
                # ibiblio's monkey-6.0/ is the case. It is a hand-written index page sitting
                # inside an otherwise generated tree, and it links exactly two things:
                # `docs/english.htm` and `docs/czech.htm`. Both were fetched, correctly. But
                # nothing ever named `docs/` ITSELF -- every reference pointed INTO it -- so the
                # directory was never enumerated, and changes.txt, ls-r.txt, cz.gif, gb.gif and
                # orangeba.gif were never asked for. All five answer 200 today.
                #
                # THE HREF HAVING A SLASH IN IT IS THE WHOLE SIGNAL. On a generated index every
                # file href is a bare name, so `container` is the directory being walked and this
                # never fires; it costs nothing on the 70-odd archives that are plain trees. It
                # fires exactly where a link reaches PAST the current directory, which is the
                # only shape that can hide one.  [2026-09-11]
                container = child.rsplit("/", 1)[0] + "/"
                if (container != url and container.startswith(base_url)
                        and container not in seen):
                    crel = container[len(base_url):]
                    if is_excluded(crel, exclude, name_for_retired):
                        log.line("SKIPPED (excluded) %s" % container)
                    elif looks_like_a_loop(container, base_url):
                        log.line("LOOP REFUSED %s -- reached via a file inside it" % container,
                                 error=True)
                    else:
                        seen.add(container)
                        inferred.add(container)
                        pending.append(container)
                        log.line("DIRECTORY REACHED ONLY VIA A FILE INSIDE IT, listing it: %s"
                                 % container)

                # A hand-written site is a tree of pages, not of directories: ardent-tool links
                # `docs/docs.html`, which does not end in `/` and would therefore be fetched as
                # a leaf and never opened. One page there links 87 documents. So for those
                # archives an HTML page is BOTH content to keep and a listing to walk -- queued
                # above, enumerated here. `seen` already holds it, so it is walked once.
                if html_crawl and looks_like_a_document(child):
                    pending.append(child)

    with stats.lock:
        stats.enum_done = True
    log.line("ENUM COMPLETE: %d directories, %d files, ~%s, %d unreadable listings"
             % (stats.dirs, stats.found, human(stats.found_bytes), stats.listfail))
    # Sentinels are deliberately NOT queued here. If this function raises, the workers must
    # still be released, so their delivery belongs to the caller's finally -- see mirror().


# ----------------------------------------------------------------------------------- main


def mirror(name, base_url, args):
    if name in EXTERNAL:
        print("    EXTERNAL -- %s" % EXTERNAL[name], flush=True)
        return None
    if name in FROZEN:
        # Returning None is the same signal an already-complete archive gives: nothing was
        # transferred, and that is not a failure. The exit code must not suggest otherwise.
        print("    FROZEN -- %s" % FROZEN[name], flush=True)
        return None
    if name in RSYNC:
        return rsync_mirror(name, RSYNC[name], args)

    base_url = effective_base(base_url)

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
    stats.patience = Patience(limit=args.give_up)
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
    _iv = set_pace(name)
    _to = set_timeout(name)
    if _to != CONNECT_TIMEOUT:
        log.line("TIMEOUT %d s instead of %d -- this host is slow to GENERATE listings, which is "
                 "not the same as being down" % (_to, CONNECT_TIMEOUT))
    if _iv:
        log.line("PACED %.2f s minimum between requests, across all %d workers -- this host "
                 "limits the RATE, not the concurrency" % (_iv, workers))
    global _TRUSTED
    _TRUSTED = load_trusted_index(root, log) if args.trust_index else frozenset()
    if _TRUSTED:
        log.line("TRUST-INDEX %d paths from %s will be skipped without a request if they are "
                 "present locally; a file CHANGED AT THE SOURCE will not be noticed"
                 % (len(_TRUSTED), SUMS_FILE))

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
                 name_for_retired=name,
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

    # BEFORE THE VERDICT, because a dead exclusion is a reason to look at the run and the DONE
    # line is where people stop reading. It is not counted as a failure: the pattern may simply
    # describe a directory the source has since removed, which is worth saying and not worth
    # failing over.
    report_unused_excludes(name, log)

    elapsed = time.time() - t0
    # THREE VERDICTS AND NOT TWO. A run that was abandoned is incomplete in the same way a run
    # with one unreadable listing is incomplete, and saying so in the same word loses the thing
    # worth knowing: the rest of the tree was never asked for. INCOMPLETE invites "re-run to pick
    # them up", which is the sentence printed below and the wrong advice at a host that has just
    # stopped answering. A marker cannot be written for either -- abandoning takes at least
    # `--give-up` failures, so stats.failed is non-zero and always was -- but the WORD is what
    # anyone reads.
    if stats.abandon:
        verdict = "ABANDONED"
    else:
        verdict = "COMPLETE" if not (stats.listfail or stats.failed) else "INCOMPLETE"
    log.line("DONE %s %s in %dh%02dm  files=%d (skip %d, of which %d trusted to the index "
             "and never requested)  bytes=%s  403=%d  fail=%d  retries=%d  collisions=%d  "
             "unreadable-listings=%d"
             % (name, verdict, elapsed // 3600, (elapsed % 3600) // 60,
                stats.done, stats.skipped, stats.trusted, human(stats.bytes),
                stats.permfail, stats.failed, stats.retries, stats.collisions,
                stats.listfail))
    if stats.listfail and not stats.abandon:
        # Each of these took a whole subtree with it. Say so in the loudest available place.
        log.line("WARNING %d directory listings could not be read after %d attempts; "
                 "every file below them is missing. Re-run to pick them up."
                 % (stats.listfail, ATTEMPTS), error=True)
    elif stats.abandon:
        log.line("%s  The %d unreadable listings above are a SYMPTOM of that and not %d separate "
                 "losses; do NOT re-run to pick them up."
                 % (stats.abandon, stats.listfail, stats.listfail), error=True)
        print("    " + stats.abandon, flush=True)

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


MARKER_PROSE = (
    "This mirror is complete. `--fresh` refuses to run while this file exists;\n"
    "delete it by hand if you really mean to fetch the whole archive again.\n"
    "`--verify` compares the tree against the two figures above.")


def write_marker(root, name, base_url, stats, elapsed):
    """Mark this mirror complete. The FORMAT is common.write_marker's; the words are ours."""
    n, total = scan_tree(root)
    return common_write_marker(
        os.path.join(root, COMPLETE_MARKER),
        {"archive": name,
         "source": base_url,
         "completed": time.strftime("%Y-%m-%d %H:%M:%S"),
         "duration": "%dh%02dm" % (elapsed // 3600, (elapsed % 3600) // 60),
         "files": n,
         "bytes": total,
         "permanent-404": stats.permfail},
        MARKER_PROSE)


# ------------------------------------------------------------------------------ checksums


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
    # NO LOCAL COPY OF THE EXCLUSION LIST. One stood here and was read inline further down, which
    # made this the third place the comparison was written; the shared helper below is now the
    # only one, and it takes the table itself. Removed while merging that consolidation against
    # an upstream lint fix that had tidied the inline version rather than deleted it.
    #
    # THE HELPER IS NOT NAMED WITH ITS BRACKETS ANYWHERE IN THIS COMMENT, ON PURPOSE.
    # archive-tables-test.py counts the helper's name immediately followed by an opening bracket
    # and expects one definition and three callers. A mention in prose is indistinguishable from
    # a fourth caller to a string count -- which this comment proved twice over, once when it
    # named the helper and again when it quoted the string it must not contain.
    pending = [base_url]
    seen = {base_url}
    dirs = stamped = nodate = absent = 0
    t0 = time.time()
    while pending:
        url = pending.pop()
        try:
            body, url = fetch_text(url)
        # WHAT FETCH_TEXT ACTUALLY RAISES, which is IOError after its retries and HTTPError for
        # a permanent code -- both OSError. It was `except Exception: continue`, and that shape
        # cannot tell "this listing did not answer" from "this file has a typo in it": a
        # NameError here would skip EVERY directory, silently, and the run would still end
        # saying DONE. Exactly that happened in recheck-decisions.py, found 2026-09-24.
        except OSError:
            continue
        dirs += 1
        # Same resolution rule as producer(). Fixed here in the same change, because the whole
        # reason this bug existed is that one tool learned the rule and its twin did not.
        resolve_from = resolution_base(body, url, base_url)
        for href, _size, mtime in parse_listing(body):
            child = urllib.parse.urljoin(resolve_from, href)
            if not child.startswith(base_url) or child in seen:
                continue
            seen.add(child)

            # EXCLUDE APPLIES TO FILES TOO, and until 2026-09-08 it did not: the test sat inside
            # the `endswith("/")` branch, which was harmless only for as long as a file under an
            # excluded subtree could not be reached without first entering that subtree.
            #
            # Following <img src> ended that. `crashing-org` excludes `icons/`, and its pages
            # embed `<img src="../icons/next.gif">` -- a FILE reference that walked straight past
            # a rule the archive states explicitly. An exclusion is a decision about a subtree,
            # not about one way of arriving at it.
            #
            # Hoisted into both walks -- but this is fix_times(), NOT producer(), and the two do
            # not share a scope. The first version of this hoist was applied to both call sites
            # with one search-and-replace and left `exclude` and `log` undefined here: neither is
            # a parameter of this function and neither is a global. `--fix-times` raised
            # NameError on the first non-excluded child of the first listing it read, for two
            # days, and nothing noticed because the flag is rarely used.
            #
            # The comment that shipped with the break said "Hoisted in BOTH walks ... a guard
            # added to one of a pair is a guard the other walks past" -- written from inside the
            # half it had just broken. Copying a guard is not the same as copying its context.
            rel = child[len(base_url):]
            if is_excluded(rel, EXCLUDE.get(name, ()), name):
                print("    SKIPPED (excluded) %s" % child, flush=True)
                continue

            if href.endswith("/"):
                loop = looks_like_a_loop(child, base_url)
                if loop:
                    print("    LOOP REFUSED %s -- %s" % (child, loop), flush=True)
                    continue
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
    rec = read_marker(marker)
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
    ap.add_argument("--give-up", type=int, default=6, metavar="N",
                    help="abandon the archive after N CONSECUTIVE requests that got no answer "
                         "at all (default 6). A 404 is an answer and resets the count. MEASURED "
                         "2026-09-29: openpa.net answered for five minutes, stopped, and this "
                         "run spent the next 26 asking anyway -- 28 retries, 9 failures, nine "
                         "subtrees recorded as lost that were never truly asked for. Six is one "
                         "more than the five in a row that preceded every such incident here, "
                         "so a genuinely lumpy archive is not cut short")
    ap.add_argument("--interval", type=float, default=10.0,
                    help="seconds between progress lines (default 10)")
    ap.add_argument("--fresh", action="store_true",
                    help="delete the target directory before mirroring")
    ap.add_argument("--case-sensitive", action="store_true",
                    help="NTFS only: make the target directory case-sensitive, so remote "
                         "names differing only in case cannot collide. NOT optional where "
                         "it matters: IBM's tree holds 4 019 such pairs, and this flag's "
                         "absence cost ps-2.kev009.com 153 files. Only effective on a "
                         "FRESH root -- NTFS never applies it retroactively, so an "
                         "existing tree needs case-collision-recover.py instead")
    ap.add_argument("--archive", action="append",
                    help="mirror only this archive; repeatable")
    ap.add_argument("--verify", action="store_true",
                    help="download nothing; compare each mirror against its completion marker")
    ap.add_argument("--fix-times", action="store_true",
                    help="download nothing; re-read the listings and stamp already-mirrored "
                         "files with the dates the server publishes")
    ap.add_argument("--trust-index", action="store_true",
                    help="skip a file that the archive's own .sha256sum lists and that is "
                         "present locally, WITHOUT asking the source. Turns a re-run over a "
                         "finished archive from one request per held file into none. A file "
                         "replaced at the source will not be noticed, so use it on an archive "
                         "whose index is current.")
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

    # --verify and --index read the LOCAL TREE and open no socket, so they apply perfectly well to
    # the Internet Archive archives even though this file's crawler never fetches them. Leaving
    # them out meant `--verify ia-bull-aix433-2013` answered "no archive matched" over 2.36 GB
    # that was sitting right there with a marker and an index. Fetching still ignores IA_ITEMS --
    # ia-item-fetch.py owns that, and pointing this crawler at archive.org would be wrong.
    if args.verify or args.index or args.index_force:
        known = {n for n, _ in todo}
        todo += [(n, "https://archive.org/details/%s" % item)
                 for n, item, _f, _b, _d, _s in IA_ITEMS
                 if n not in known and (not args.archive or n in args.archive)]

    if not todo:
        sys.exit("no archive matched --archive; known: %s"
                 % ", ".join([n for n, _ in ARCHIVES] + [n for n, *_r in IA_ITEMS]))

    # Both guards below are about FETCHING. --verify and --index read the local tree and open
    # no socket, so refusing them on a source-URL rule would be refusing the wrong thing -- and
    # did, once: a DO_NOT_FETCH entry meant for HTTP matched an rsync:// URL and made the entire
    # collection unverifiable. Check the guards only when a run is actually going to fetch.
    if not (args.verify or args.index or args.index_force or args.fix_times):
        _check_fetch_guards(todo)
        _refuse_a_dry_run_that_would_not_be_one(args, todo)
    return _main_after_guards(args, todo)


def _refuse_a_dry_run_that_would_not_be_one(args, todo):
    """--dry-run is an rsync feature. Over HTTP it does nothing, so say so instead of fetching.

    THE FLAG PROMISES MORE THAN IT DELIVERS, and its help text has always said so -- "rsync
    archives only". That is not enough. On 2026-09-27 a `--dry-run` on an HTTP archive ran a
    REAL FETCH: 61 pages taken, a completion marker written, and the run reported
    `61 files, 0 failed` over a tree that was missing 99.4 % of itself. Nothing warned, because
    from the code's point of view nothing unusual happened.

    A FLAG WHOSE NAME MEANS "CHANGE NOTHING" MUST NOT CHANGE ANYTHING, and where it cannot
    honour that it has to refuse. The refusal costs a re-run without the flag; the alternative
    cost a fetch, a wrong marker and half an hour of working out why the tree was empty.
    """
    over_http = sorted(n for n, url in todo if not url.startswith("rsync://"))
    if args.dry_run and over_http:
        sys.exit(
            "--dry-run does nothing for an archive fetched over HTTP, and this run would have\n"
            "FETCHED: %s\n"
            "It is an rsync feature -- `rsync -n` -- and there is no equivalent here: finding\n"
            "out what a crawl would take means crawling. Use measure-remote.py to size a tree\n"
            "without committing disk, or drop --dry-run to fetch."
            % ", ".join(over_http))


def _check_fetch_guards(todo):
    """Refuse to START A FETCH that would duplicate an archive or touch a forbidden host.

    Split out of main() so the two conditions sit together, and so the callers that do not fetch
    can skip it -- see blocked_host() for what including them cost once.
    """
    # TWO ARCHIVES MUST NOT SHARE A SOURCE. On 2026-09-04 `ibm-rs6000-support` and `dhe-rs6000`
    # were found to be the same 27.1 GB tree, fetched from https://public.dhe.ibm.com/rs6000/
    # one day apart under two names -- 1 619 files and 27 116 134 440 bytes each, every relative
    # path shared, sampled bytes identical. Nothing in the tool noticed, because nothing looked.
    # A whole policy discussion was held about whether to take a tree that was already on disk.
    # This check is three lines and would have cost nothing; the omission cost 27 GB.
    by_url = {}
    for name, url in ARCHIVES:
        by_url.setdefault(url.rstrip("/").lower(), []).append(name)
    dupes = {u: ns for u, ns in by_url.items() if len(ns) > 1}
    if dupes:
        lines = ["TWO ARCHIVES SHARE A SOURCE URL -- one of them is a duplicate of the other:"]
        for u, ns in sorted(dupes.items()):
            lines.append("  %s" % u)
            lines.append("      %s" % ", ".join(sorted(ns)))
        lines.append("Resolve it in ARCHIVES before running. If both are wanted (different "
                     "subsets, say),")
        lines.append("give them distinct URLs so that this stays true.")
        sys.exit(os.linesep.join(lines))

    # DO_NOT_FETCH is enforced here rather than trusted to whoever edits ARCHIVES. It fires
    # before the root is touched or a single request is made, and it is fatal rather than a
    # warning: a run that quietly skipped the blocked entry and mirrored the rest would look
    # like a success, and the whole point of the list is that this particular failure must be
    # loud. Removing an entry is a decision someone has to make deliberately, in the file.
    for name, url in todo:
        why = blocked_host(url)
        if why:
            sys.exit("REFUSING %s (%s)\n"
                     "  The operator of this host has said no: %s\n"
                     "  See DO_NOT_FETCH. If that finding is stale, re-read the page and\n"
                     "  record the quote before removing the entry." % (name, url, why))


def _main_after_guards(args, todo):
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
