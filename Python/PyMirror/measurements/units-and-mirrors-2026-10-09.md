<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Which unit packs which mirror, and what each unit became

Taken 2026-10-09, after all nine units were packed and verified.

WHY THIS EXISTS. A unit is what gets repacked when anything in it changes, so a mirror sitting in
two units -- or in none -- would be found only when a correction had to be made. The owner asked
for the tree because the unit names do not match the directory names and the risk is invisible
from the unit table alone.

THE AUTHORITATIVE CHECK IS NOT THIS FILE. `python b2-pack.py --coverage` walks every mirror index
and reports whether every file is claimed exactly once; it printed `every file is claimed exactly
once` over 113 mirrors and 9 units. This document is the readable form of the same facts, and if
the two ever disagree, `--coverage` is right.

## What the nine units became

Packed between 2026-10-06 and 2026-10-09. `ref/file` is the share of files that `-oi1` stored as
a reference to an identical file; it is the column that predicts the ratio, and the reasoning is
recorded in `b2-pack.py` above `DEFAULTS`.

| unit | files | source | archive | ratio | ref/file | volumes |
|---|---|---|---|---|---|---|
| `ibm-aix-opensource` | 184 465 | 207.96 GB | 73.00 GB | 35.1 % | 21.69 % | 20 |
| `ibm-aix-support` | 101 086 | 322.53 GB | 135.67 GB | 42.1 % | 14.45 % | 39 |
| `workstations` | 420 307 | 169.46 GB | 89.00 GB | 52.5 % | 7.24 % | 25 |
| `ibm-aix` | 52 241 | 702.51 GB | 395.00 GB | 56.2 % | 5.09 % | 115 |
| `ibm-pc` | 295 280 | 530.45 GB | 306.86 GB | 57.8 % | 6.93 % | 87 |
| `vendors` | 39 131 | 638.39 GB | 399.00 GB | 62.5 % | 4.34 % | 118 |
| `misc` | 341 969 | 144.17 GB | 93.88 GB | 65.1 % | 2.57 % | 27 |
| `oldskool` | 77 624 | 149.22 GB | 120.00 GB | 80.4 % | 4.02 % | 35 |
| `bitsavers` | 176 028 | 1 196.66 GB | 1 006.22 GB | 84.1 % | 1.07 % | 283 |
| **total** | **1 688 131** | **4 061.35 GB** | **2 618.63 GB** | **64.5 %** | | **749** |

Plus 69 GB of `.rev` across the nine, so 2 688 GB is what leaves for cold storage.

EVERY UNIT PASSED BOTH CHECKS: `rar t` over its volumes, and a CRC32-plus-file-count comparison
against the archive's own `.sfv` with each `-oi1` reference judged through its target. Nine for
nine, 123 662 references resolved. Each unit's directory also holds its `*.index.csv` and the four
manifests (`.sha256sum`, `.sha1sum`, `.md5sum`, `.sfv`) beside the volumes.

STILL OPEN: the index archive -- the small archive carrying all nine `*.index.csv` so the
collection can be searched without fetching a 1 TB unit -- has never been built.

## The mirror tree

Generated from `b2-pack.py`'s unit table and each mirror's own `.mirror-index.csv`.
The **unit name is not the directory name** -- `ibm-aix-opensource` packs the mirror
`oss4aix.org`, and that is the single most confusing thing in this table.

| | |
|---|---|
| mirror directories under `Q:\mirror` | **113** |
| units | **9** |
| mirrors claimed by MORE than one unit | **0** |

**No mirror is claimed by more than one unit.** Each directory belongs to exactly one unit, so nothing is mixed across units.

## The tree

- **bitsavers** -- 1 mirror(s), 176028 files, 1196.66 GB
    - `bitsavers` -- 176028 files, 1196.66 GB

- **ibm-aix** -- 1 mirror(s), 52241 files, 702.51 GB
    - `ibm-aix` -- 52241 files, 702.51 GB

- **vendors** -- 2 mirror(s), 39131 files, 638.39 GB
    - `fsck-vendors` -- 9372 files, 403.65 GB
    - `vtda` -- 29759 files, 234.73 GB

- **ibm-pc** -- 9 mirror(s), 295280 files, 530.45 GB
    - `ardent-tool` -- 25821 files, 22.06 GB
    - `dreamlandbbs-os2` -- 7744 files, 18.87 GB
    - `fsck-ibm-other` -- 1327 files, 105.94 GB
    - `infania-unixos2` -- 40 files, 0.00 GB
    - `mcamafia` -- 1770 files, 0.12 GB
    - `os2bbs` -- 21476 files, 10.82 GB
    - `ps-2.kev009.com` -- 215819 files, 353.55 GB
    - `rwth-aachen-ftp` -- 10561 files, 10.27 GB
    - `zx-hobbes-os2` -- 10722 files, 8.83 GB

- **ibm-aix-support** -- 35 mirror(s), 101086 files, 322.53 GB
    - `AIX5-IA64` -- 92 files, 0.33 GB
    - `aix-orphans` -- 303 files, 0.07 GB
    - `aix-qemu-git` -- 167 files, 0.06 GB
    - `aixpdslib` -- 2183 files, 0.01 GB
    - `aixtools` -- 100 files, 0.26 GB
    - `biblionik-bull` -- 275 files, 0.36 GB
    - `biblionik-goupil` -- 37 files, 0.38 GB
    - `bull-rpms` -- 7117 files, 45.81 GB
    - `bull-srpms` -- 1873 files, 19.17 GB
    - `bullfreeware` -- 14869 files, 49.40 GB
    - `circle4` -- 409 files, 0.19 GB
    - `cmu-shadow` -- 33 files, 0.00 GB
    - `csri-toronto` -- 2 files, 0.00 GB
    - `damage-rt` -- 266 files, 0.50 GB
    - `filibeto-aix-lib` -- 174 files, 0.84 GB
    - `fsck-aix-apps` -- 355 files, 16.76 GB
    - `fsck-aix-media` -- 608 files, 70.12 GB
    - `funet-aix` -- 23 files, 0.00 GB
    - `gsi-collection` -- 6272 files, 3.11 GB
    - `ia-bull-aix433-2005` -- 200 files, 0.98 GB
    - `ia-bull-aix433-2013` -- 247 files, 2.36 GB
    - `ia-bull-toolbox-43` -- 271 files, 0.70 GB
    - `ia-bullfreeware` -- 11969 files, 66.16 GB
    - `ibm-openxl-docs` -- 795 files, 0.01 GB
    - `ibm-redbooks` -- 5869 files, 17.14 GB
    - `ibm-rs6000-support` -- 1575 files, 27.12 GB
    - `iffly-wiki` -- 968 files, 0.01 GB
    - `infania-tl1` -- 18769 files, 0.27 GB
    - `infania-tl2` -- 19848 files, 0.25 GB
    - `misterhayden` -- 144 files, 0.00 GB
    - `perzl-wiki` -- 1110 files, 0.00 GB
    - `rs6000-microcode` -- 183 files, 0.08 GB
    - `techsysadm` -- 570 files, 0.04 GB
    - `tvsat-cpc710` -- 1 files, 0.00 GB
    - `typewritten` -- 3409 files, 0.03 GB

- **ibm-aix-opensource** -- 1 mirror(s), 184465 files, 207.96 GB
    - `oss4aix.org` -- 184465 files, 207.96 GB

- **workstations** -- 12 mirror(s), 420307 files, 169.46 GB
    - `dec-ftp-2006` -- 22172 files, 36.04 GB
    - `decromancer-bits` -- 398 files, 0.67 GB
    - `hp-openvms-2008` -- 27373 files, 1.28 GB
    - `irixnet-ftp` -- 2770 files, 53.62 GB
    - `next-68k-org` -- 234759 files, 37.65 GB
    - `nice-next` -- 4540 files, 1.32 GB
    - `sgidepot` -- 2186 files, 0.64 GB
    - `somuchstuff-pdp8` -- 110569 files, 19.17 GB
    - `zx-gatekeeper-dec` -- 9189 files, 8.60 GB
    - `zx-kednos-vms` -- 634 files, 1.17 GB
    - `zx-sgi-freeware-old` -- 5702 files, 6.68 GB
    - `zx-ultrix-freeware` -- 15 files, 2.62 GB

- **oldskool** -- 1 mirror(s), 77624 files, 149.22 GB
    - `oldskool` -- 77624 files, 149.22 GB

- **misc** -- 51 mirror(s), 341969 files, 144.17 GB
    - `abc-bladet` -- 135 files, 0.45 GB
    - `acpc-amstrad` -- 39 files, 1.25 GB
    - `adoxa-dos` -- 437 files, 0.08 GB
    - `agilent-ftp-2009` -- 814 files, 2.47 GB
    - `apollo-clavius` -- 236 files, 0.02 GB
    - `bretjohnson` -- 53 files, 0.07 GB
    - `chipdb` -- 2404 files, 2.26 GB
    - `crashing-org` -- 7231 files, 0.74 GB
    - `crashing-org-kernel` -- 757 files, 3.81 GB
    - `crashing-org-www` -- 3 files, 0.00 GB
    - `cryp-to-cwg` -- 22 files, 0.02 GB
    - `csiph-gallery` -- 43 files, 0.01 GB
    - `debian-powerpc-boot` -- 72 files, 0.07 GB
    - `develooper-hpux` -- 580 files, 12.61 GB
    - `devicetree-openfirmware` -- 123 files, 0.02 GB
    - `dialectronics` -- 276 files, 0.03 GB
    - `fjkraan` -- 2847 files, 3.04 GB
    - `giga-nl-walter` -- 527 files, 0.32 GB
    - `hp-alphaserver-2008` -- 10202 files, 1.05 GB
    - `hp-labs-2007` -- 9171 files, 3.98 GB
    - `hp-labs-linux-salvage` -- 125 files, 0.00 GB
    - `ibiblio-historic-linux` -- 224978 files, 15.44 GB
    - `ibiblio-ppc-ports` -- 2 files, 0.01 GB
    - `infania-os-history` -- 1011 files, 0.07 GB
    - `infania-solaris` -- 2559 files, 16.44 GB
    - `iommu` -- 8207 files, 19.99 GB
    - `kib-x86docs` -- 16241 files, 14.81 GB
    - `linuxfoundation-refspecs` -- 255 files, 0.01 GB
    - `mpoli-bbs` -- 23180 files, 5.66 GB
    - `ndwiki-norsk-data` -- 3844 files, 1.72 GB
    - `novasareforever-aviion` -- 369 files, 3.96 GB
    - `obsolyte` -- 650 files, 0.04 GB
    - `openpa` -- 821 files, 0.07 GB
    - `parisc-firmware` -- 37 files, 0.04 GB
    - `penguinppc` -- 601 files, 0.08 GB
    - `retro-digitalvintage` -- 172 files, 0.10 GB
    - `sco-devspecs` -- 13 files, 0.02 GB
    - `sco-gabi` -- 135 files, 0.00 GB
    - `seds-frommert` -- 2926 files, 0.14 GB
    - `square7-vintage` -- 397 files, 0.10 GB
    - `sun3arc` -- 1113 files, 0.26 GB
    - `technologists-dellunix` -- 5 files, 0.08 GB
    - `technologists-sauer` -- 58 files, 0.34 GB
    - `transputer-classiccmp` -- 1062 files, 1.86 GB
    - `tuhs` -- 12139 files, 9.33 GB
    - `ultimate-fastpath` -- 37 files, 0.00 GB
    - `vgamuseum-doc` -- 2261 files, 3.44 GB
    - `wotug-inmos` -- 60 files, 0.01 GB
    - `zx-alphant-nt` -- 520 files, 1.66 GB
    - `zx-be-os` -- 1745 files, 0.54 GB
    - `zx-microway` -- 474 files, 15.65 GB

## Every mirror directory, alphabetically, and who packs it

| mirror | files | GB | packed by |
|---|---|---|---|
| `AIX5-IA64` | 92 | 0.33 | ibm-aix-support |
| `abc-bladet` | 135 | 0.45 | misc |
| `acpc-amstrad` | 39 | 1.25 | misc |
| `adoxa-dos` | 437 | 0.08 | misc |
| `agilent-ftp-2009` | 814 | 2.47 | misc |
| `aix-orphans` | 303 | 0.07 | ibm-aix-support |
| `aix-qemu-git` | 167 | 0.06 | ibm-aix-support |
| `aixpdslib` | 2183 | 0.01 | ibm-aix-support |
| `aixtools` | 100 | 0.26 | ibm-aix-support |
| `apollo-clavius` | 236 | 0.02 | misc |
| `ardent-tool` | 25821 | 22.06 | ibm-pc |
| `biblionik-bull` | 275 | 0.36 | ibm-aix-support |
| `biblionik-goupil` | 37 | 0.38 | ibm-aix-support |
| `bitsavers` | 176028 | 1196.66 | bitsavers |
| `bretjohnson` | 53 | 0.07 | misc |
| `bull-rpms` | 7117 | 45.81 | ibm-aix-support |
| `bull-srpms` | 1873 | 19.17 | ibm-aix-support |
| `bullfreeware` | 14869 | 49.40 | ibm-aix-support |
| `chipdb` | 2404 | 2.26 | misc |
| `circle4` | 409 | 0.19 | ibm-aix-support |
| `cmu-shadow` | 33 | 0.00 | ibm-aix-support |
| `crashing-org` | 7231 | 0.74 | misc |
| `crashing-org-kernel` | 757 | 3.81 | misc |
| `crashing-org-www` | 3 | 0.00 | misc |
| `cryp-to-cwg` | 22 | 0.02 | misc |
| `csiph-gallery` | 43 | 0.01 | misc |
| `csri-toronto` | 2 | 0.00 | ibm-aix-support |
| `damage-rt` | 266 | 0.50 | ibm-aix-support |
| `debian-powerpc-boot` | 72 | 0.07 | misc |
| `dec-ftp-2006` | 22172 | 36.04 | workstations |
| `decromancer-bits` | 398 | 0.67 | workstations |
| `develooper-hpux` | 580 | 12.61 | misc |
| `devicetree-openfirmware` | 123 | 0.02 | misc |
| `dialectronics` | 276 | 0.03 | misc |
| `dreamlandbbs-os2` | 7744 | 18.87 | ibm-pc |
| `filibeto-aix-lib` | 174 | 0.84 | ibm-aix-support |
| `fjkraan` | 2847 | 3.04 | misc |
| `fsck-aix-apps` | 355 | 16.76 | ibm-aix-support |
| `fsck-aix-media` | 608 | 70.12 | ibm-aix-support |
| `fsck-ibm-other` | 1327 | 105.94 | ibm-pc |
| `fsck-vendors` | 9372 | 403.65 | vendors |
| `funet-aix` | 23 | 0.00 | ibm-aix-support |
| `giga-nl-walter` | 527 | 0.32 | misc |
| `gsi-collection` | 6272 | 3.11 | ibm-aix-support |
| `hp-alphaserver-2008` | 10202 | 1.05 | misc |
| `hp-labs-2007` | 9171 | 3.98 | misc |
| `hp-labs-linux-salvage` | 125 | 0.00 | misc |
| `hp-openvms-2008` | 27373 | 1.28 | workstations |
| `ia-bull-aix433-2005` | 200 | 0.98 | ibm-aix-support |
| `ia-bull-aix433-2013` | 247 | 2.36 | ibm-aix-support |
| `ia-bull-toolbox-43` | 271 | 0.70 | ibm-aix-support |
| `ia-bullfreeware` | 11969 | 66.16 | ibm-aix-support |
| `ibiblio-historic-linux` | 224978 | 15.44 | misc |
| `ibiblio-ppc-ports` | 2 | 0.01 | misc |
| `ibm-aix` | 52241 | 702.51 | ibm-aix |
| `ibm-openxl-docs` | 795 | 0.01 | ibm-aix-support |
| `ibm-redbooks` | 5869 | 17.14 | ibm-aix-support |
| `ibm-rs6000-support` | 1575 | 27.12 | ibm-aix-support |
| `iffly-wiki` | 968 | 0.01 | ibm-aix-support |
| `infania-os-history` | 1011 | 0.07 | misc |
| `infania-solaris` | 2559 | 16.44 | misc |
| `infania-tl1` | 18769 | 0.27 | ibm-aix-support |
| `infania-tl2` | 19848 | 0.25 | ibm-aix-support |
| `infania-unixos2` | 40 | 0.00 | ibm-pc |
| `iommu` | 8207 | 19.99 | misc |
| `irixnet-ftp` | 2770 | 53.62 | workstations |
| `kib-x86docs` | 16241 | 14.81 | misc |
| `linuxfoundation-refspecs` | 255 | 0.01 | misc |
| `mcamafia` | 1770 | 0.12 | ibm-pc |
| `misterhayden` | 144 | 0.00 | ibm-aix-support |
| `mpoli-bbs` | 23180 | 5.66 | misc |
| `ndwiki-norsk-data` | 3844 | 1.72 | misc |
| `next-68k-org` | 234759 | 37.65 | workstations |
| `nice-next` | 4540 | 1.32 | workstations |
| `novasareforever-aviion` | 369 | 3.96 | misc |
| `obsolyte` | 650 | 0.04 | misc |
| `oldskool` | 77624 | 149.22 | oldskool |
| `openpa` | 821 | 0.07 | misc |
| `os2bbs` | 21476 | 10.82 | ibm-pc |
| `oss4aix.org` | 184465 | 207.96 | ibm-aix-opensource |
| `parisc-firmware` | 37 | 0.04 | misc |
| `penguinppc` | 601 | 0.08 | misc |
| `perzl-wiki` | 1110 | 0.00 | ibm-aix-support |
| `ps-2.kev009.com` | 215819 | 353.55 | ibm-pc |
| `retro-digitalvintage` | 172 | 0.10 | misc |
| `rs6000-microcode` | 183 | 0.08 | ibm-aix-support |
| `rwth-aachen-ftp` | 10561 | 10.27 | ibm-pc |
| `sco-devspecs` | 13 | 0.02 | misc |
| `sco-gabi` | 135 | 0.00 | misc |
| `seds-frommert` | 2926 | 0.14 | misc |
| `sgidepot` | 2186 | 0.64 | workstations |
| `somuchstuff-pdp8` | 110569 | 19.17 | workstations |
| `square7-vintage` | 397 | 0.10 | misc |
| `sun3arc` | 1113 | 0.26 | misc |
| `technologists-dellunix` | 5 | 0.08 | misc |
| `technologists-sauer` | 58 | 0.34 | misc |
| `techsysadm` | 570 | 0.04 | ibm-aix-support |
| `transputer-classiccmp` | 1062 | 1.86 | misc |
| `tuhs` | 12139 | 9.33 | misc |
| `tvsat-cpc710` | 1 | 0.00 | ibm-aix-support |
| `typewritten` | 3409 | 0.03 | ibm-aix-support |
| `ultimate-fastpath` | 37 | 0.00 | misc |
| `vgamuseum-doc` | 2261 | 3.44 | misc |
| `vtda` | 29759 | 234.73 | vendors |
| `wotug-inmos` | 60 | 0.01 | misc |
| `zx-alphant-nt` | 520 | 1.66 | misc |
| `zx-be-os` | 1745 | 0.54 | misc |
| `zx-gatekeeper-dec` | 9189 | 8.60 | workstations |
| `zx-hobbes-os2` | 10722 | 8.83 | ibm-pc |
| `zx-kednos-vms` | 634 | 1.17 | workstations |
| `zx-microway` | 474 | 15.65 | misc |
| `zx-sgi-freeware-old` | 5702 | 6.68 | workstations |
| `zx-ultrix-freeware` | 15 | 2.62 | workstations |

