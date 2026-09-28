<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# What the collection is made of, and why it is nineteen units

The grouping in `b2-pack.py` is not taste. This is the measurement it rests on, taken read-only
from the 98 per-archive `.mirror-index.csv` files -- 247 MB of `path,size,mtime_ns,sha256`. No
mirrored file was opened and nothing was hashed: the digests were already there.

## Three questions, because "which archives belong together" is really three

1. **How compressible is each archive.** A solid archive of `.rpm` and `.gz` buys nothing and costs
   retrieval latency; one of manual pages buys a great deal. This decides the RAR settings, not
   just the grouping.
2. **What do two archives actually share.** Exact duplicate bytes are countable from the SHA-256
   column with no guessing. Duplication INSIDE a unit is a saving, because a solid block collapses
   it; duplication ACROSS units is waste.
3. **What shape is each archive.** Bytes per extension, as the proxy for "similar files next to
   each other" where there are no exact duplicates.

## The number that decided the plan

**Two thirds of the collection cannot be compressed, and 0.5 % of it is text.** A large dictionary
would have almost nothing to work on. The saving is in the DUPLICATES, and those come from
clustering rather than from compression settings.

`pdf` is the largest single kind of content at 1.21 TB, and it is overwhelmingly scanned paper --
image streams inside an already-compressed container. An earlier run of this analysis had no class
for `pdf` at all, so 1.21 TB landed in "other" and the composition table was useless for the one
question it was built to answer. `ps`, `bff`, `tap`, `udf`, `mdf`, `tardist`, `pkg` and `sd` had the
same problem.

## Duplicates: 171.37 GB, and 111.46 GB of it in one group

`bull-rpms` is contained 100 % in `bullfreeware` AND 100 % in `ia-bullfreeware`; `bull-srpms` is
contained 100 % in `ia-bullfreeware`. Put in one unit and sorted so the copies are adjacent, 185 GB
collapses to about 70 GB. That single cluster is worth more than recompressing all 2.65 TB of
already-compressed data.

**It only works if the copies are adjacent**, which is why the file list is sorted by
`(extension, size, digest, path)` rather than by directory: two byte-identical files agree on all
three leading keys, so they end up next to each other and even a small dictionary sees the repeat.

## What the grouping captures, exactly

| | |
|---|---:|
| identical bytes held more than once | **171.37 GB** |
| kept INSIDE a unit, where a solid block collapses them | **120.96 GB** |
| crossing a unit boundary, paid for twice | **50.41 GB** |
| captured | **70.6 %** |

**A CORRECTION TO AN EARLIER FIGURE IN THIS FILE'S OWN HISTORY.** The first estimate said "about
31 GB" cross a boundary, and it came from summing the pair table. That double-counts: a file held in
three archives appears in three pairs, so the pair sum is not a byte total. `b2-cluster.py` counts
per file -- each duplicate contributes `size x (copies - 1)` once -- and gets 50.41 GB. The pair
table is still the right thing to READ, because it says which two archives to think about; it is
just not a quantity to add up.

The largest crossing pair is 13.46 GB between `fsck-vendors` and `vtda`. Capturing it would mean
forcing 639 GB into one unit, and a unit is the thing that gets repacked whenever anything in it
changes. 13 GB is not worth that.

`b2-cluster.py` re-takes all of this on demand and checks it against `b2-pack.py`'s actual grouping,
including that no archive is left unclaimed -- so the numbers above can be compared with today's
rather than trusted.

## The full output

Produced by the script quoted at the end, on 2026-09-26.

```
98 archives, 3.98 TB, 1761470 files

WHAT THE COLLECTION IS MADE OF -- the number that decides the whole plan
------------------------------------------------------------------------------
  precompressed      2649.25 GB    66.6 %
  raw-container       409.18 GB    10.3 %
  disk-image          667.56 GB    16.8 %
  text-like            20.05 GB     0.5 %
  executable          148.20 GB     3.7 %
  unknown              84.24 GB     2.1 %

  biggest single extensions:
    pdf          1213.55 GB  [precompressed]
    iso           521.45 GB  [disk-image]
    rpm           500.62 GB  [precompressed]
    zip           355.26 GB  [precompressed]
    tar           227.53 GB  [raw-container]
    gz            204.30 GB  [precompressed]
    bff           164.52 GB  [raw-container]
    exe           124.67 GB  [executable]
    z              87.23 GB  [precompressed]
    mdf            60.26 GB  [disk-image]
    img            50.32 GB  [disk-image]
    xz             41.47 GB  [precompressed]
    bz2            39.78 GB  [precompressed]
    tgz            30.13 GB  [precompressed]
    7z             29.26 GB  [precompressed]
    jpg            27.01 GB  [precompressed]
    tardist        25.69 GB  [precompressed]
    bin            22.60 GB  [executable]

  identical files held more than once, across the whole collection: 171.37 GB

====================================================================================================
CLUSTERS -- merged where they share real bytes (floor 0.4 GB, cap 500 GB)
====================================================================================================

bitsavers                                              1196.66 GB raw
                                                     precompressed 89%

ibm-aix                                                 702.37 GB raw
                                                     precompressed 48%, raw-container 51%

fsck-aix-apps + fsck-vendors                            420.42 GB raw
                                                        410.15 GB after identical files collapse  (-10.26 GB)
                                                     precompressed 26%, disk-image 69%

ardent-tool + ps-2.kev009.com + rwth-aachen-ftp         374.26 GB raw
                                                        362.36 GB after identical files collapse  (-11.90 GB)
                                                     precompressed 45%, disk-image 25%, executable 27%

tuhs + vtda                                             244.07 GB raw
                                                        243.26 GB after identical files collapse  (-0.81 GB)
                                                     precompressed 88%, disk-image 11%

oss4aix.org                                             207.96 GB raw
                                                     precompressed 100%

bull-rpms + bull-srpms + bullfreeware + ia-bull-tool    181.23 GB raw
                                                         69.77 GB after identical files collapse  (-111.46 GB)
                                                     precompressed 99%

oldskool                                                149.23 GB raw
                                                     precompressed 58%, disk-image 20%, executable 19%

fsck-ibm-other                                          105.94 GB raw
                                                     precompressed 15%, disk-image 80%

fsck-aix-media                                           70.12 GB raw
                                                     precompressed 16%, disk-image 83%

irixnet-ftp                                              53.62 GB raw
                                                     precompressed 100%

dec-ftp-2006 + zx-gatekeeper-dec                         44.63 GB raw
                                                         42.67 GB after identical files collapse  (-1.96 GB)
                                                     precompressed 36%, raw-container 26%, unknown 26%

next-68k-org + nice-next                                 38.97 GB raw
                                                         38.47 GB after identical files collapse  (-0.50 GB)
                                                     precompressed 74%, raw-container 10%

ibm-rs6000-support                                       27.12 GB raw
                                                     precompressed 97%

os2bbs + zx-hobbes-os2                                   19.64 GB raw
                                                         17.81 GB after identical files collapse  (-1.83 GB)
                                                     precompressed 89%

somuchstuff-pdp8                                         19.17 GB raw
                                                     precompressed 62%, text-like 21%, unknown 13%

ibm-redbooks                                             16.94 GB raw
                                                     precompressed 100%

infania-solaris                                          16.44 GB raw
                                                     precompressed 100%

zx-microway                                              15.66 GB raw
                                                     precompressed 80%, disk-image 8%

ibiblio-historic-linux                                   15.44 GB raw
                                                     precompressed 75%, unknown 15%

develooper-hpux                                          12.61 GB raw
                                                     precompressed 100%

mpoli-bbs                                                 5.66 GB raw
                                                     precompressed 66%, executable 23%, unknown 10%

hp-labs-2007                                              3.98 GB raw
                                                     precompressed 75%, text-like 16%, unknown 9%

novasareforever-aviion                                    3.96 GB raw
                                                     precompressed 61%, disk-image 38%

crashing-org-kernel                                       3.81 GB raw
                                                     precompressed 99%

ia-bull-aix433-2005 + ia-bull-aix433-2013                 3.34 GB raw
                                                          2.74 GB after identical files collapse  (-0.60 GB)
                                                     precompressed 25%, raw-container 75%

gsi-collection                                            3.11 GB raw
                                                     precompressed 93%

zx-ultrix-freeware                                        2.62 GB raw
                                                     precompressed 19%, disk-image 81%

agilent-ftp-2009                                          2.47 GB raw
                                                     precompressed 77%, executable 20%

transputer-classiccmp                                     1.86 GB raw
                                                     precompressed 76%, unknown 23%

ndwiki-norsk-data                                         1.72 GB raw
                                                     precompressed 100%

zx-alphant-nt                                             1.66 GB raw
                                                     precompressed 72%, executable 27%

hp-openvms-2008                                           1.28 GB raw
                                                     precompressed 49%, text-like 48%

zx-kednos-vms                                             1.17 GB raw
                                                     precompressed 30%, unknown 64%

hp-alphaserver-2008                                       1.05 GB raw
                                                     precompressed 67%, text-like 17%, executable 13%

zx-sgi-freeware-old                                       0.94 GB raw
                                                     precompressed 98%

filibeto-aix-lib                                          0.84 GB raw
                                                     precompressed 100%

crashing-org                                              0.74 GB raw
                                                     precompressed 99%

decromancer-bits                                          0.67 GB raw
                                                     precompressed 54%, unknown 45%

zx-be-os                                                  0.54 GB raw
                                                     precompressed 79%, executable 9%, unknown 10%

damage-rt                                                 0.50 GB raw
                                                     precompressed 100%

abc-bladet                                                0.45 GB raw
                                                     precompressed 100%

biblionik-bull                                            0.36 GB raw
                                                     precompressed 100%

technologists-sauer                                       0.34 GB raw
                                                     precompressed 100%

AIX5-IA64                                                 0.33 GB raw
                                                     precompressed 49%, unknown 51%

giga-nl-walter                                            0.32 GB raw
                                                     precompressed 99%

infania-tl1                                               0.27 GB raw
                                                     precompressed 36%, text-like 63%

aixtools                                                  0.26 GB raw
                                                     unknown 100%

infania-tl2                                               0.25 GB raw
                                                     precompressed 39%, text-like 61%

sun3arc                                                   0.22 GB raw
                                                     precompressed 99%

circle4                                                   0.19 GB raw
                                                     precompressed 100%

square7-vintage                                           0.10 GB raw
                                                     precompressed 98%

rs6000-microcode                                          0.08 GB raw
                                                     executable 98%

technologists-dellunix                                    0.08 GB raw
                                                     precompressed 94%

adoxa-dos                                                 0.08 GB raw
                                                     precompressed 70%, unknown 29%

penguinppc                                                0.08 GB raw
                                                     precompressed 92%

debian-powerpc-boot                                       0.07 GB raw
                                                     precompressed 35%, executable 55%

bretjohnson                                               0.07 GB raw
                                                     precompressed 100%

infania-os-history                                        0.07 GB raw
                                                     precompressed 95%

aix-orphans                                               0.06 GB raw
                                                     precompressed 91%

aix-qemu-git                                              0.06 GB raw
                                                     precompressed 49%, unknown 50%

parisc-firmware                                           0.04 GB raw
                                                     unknown 94%

techsysadm                                                0.04 GB raw
                                                     precompressed 19%, text-like 81%

dialectronics                                             0.03 GB raw
                                                     precompressed 74%, unknown 20%

typewritten                                               0.03 GB raw
                                                     text-like 100%

apollo-clavius                                            0.02 GB raw
                                                     precompressed 98%

cryp-to-cwg                                               0.02 GB raw
                                                     precompressed 99%

devicetree-openfirmware                                   0.02 GB raw
                                                     text-like 95%

sco-devspecs                                              0.02 GB raw
                                                     precompressed 52%, text-like 48%

csiph-gallery                                             0.01 GB raw
                                                     precompressed 100%

wotug-inmos                                               0.01 GB raw
                                                     precompressed 99%

aixpdslib                                                 0.01 GB raw
                                                     precompressed 20%, text-like 79%

ibiblio-ppc-ports                                         0.01 GB raw
                                                     precompressed 100%

funet-aix                                                 0.01 GB raw
                                                     precompressed 96%

linuxfoundation-refspecs                                  0.01 GB raw
                                                     precompressed 43%, text-like 57%

ibm-openxl-docs                                           0.01 GB raw
                                                     unknown 95%

iffly-wiki                                                0.01 GB raw
                                                     text-like 100%

hp-labs-linux-salvage                                     0.00 GB raw
                                                     precompressed 12%, unknown 86%

ultimate-fastpath                                         0.00 GB raw
                                                     precompressed 33%, text-like 19%, executable 44%

misterhayden                                              0.00 GB raw
                                                     text-like 97%

perzl-wiki                                                0.00 GB raw
                                                     unknown 95%

sco-gabi                                                  0.00 GB raw
                                                     text-like 98%

tvsat-cpc710                                              0.00 GB raw
                                                     precompressed 100%

infania-unixos2                                           0.00 GB raw
                                                     precompressed 58%, text-like 42%

csri-toronto                                              0.00 GB raw
                                                     precompressed 100%

crashing-org-www                                          0.00 GB raw
                                                     text-like 100%

====================================================================================================
SHARED BYTES THAT CROSS A CLUSTER BOUNDARY -- waste this grouping does not capture
====================================================================================================
    13.46 GB  fsck-vendors                 vtda
     6.27 GB  bitsavers                    fsck-vendors
     3.27 GB  ardent-tool                  bitsavers
     1.17 GB  bitsavers                    oldskool
     1.16 GB  bitsavers                    somuchstuff-pdp8
     0.77 GB  bitsavers                    vtda
     0.68 GB  fsck-vendors                 ps-2.kev009.com
     0.64 GB  bitsavers                    fsck-aix-apps
     0.59 GB  oldskool                     ps-2.kev009.com
     0.45 GB  ibm-aix                      ps-2.kev009.com
     0.45 GB  ardent-tool                  oldskool
     0.44 GB  bitsavers                    ps-2.kev009.com
     0.41 GB  ps-2.kev009.com              vtda
     0.38 GB  bitsavers                    transputer-classiccmp
     0.32 GB  fsck-aix-apps                ps-2.kev009.com
     0.32 GB  ibm-aix                      vtda
     0.29 GB  ia-bullfreeware              ibm-aix
     0.27 GB  gsi-collection               ps-2.kev009.com
     0.27 GB  bullfreeware                 ibm-aix
     0.25 GB  filibeto-aix-lib             ps-2.kev009.com
     0.25 GB  bull-rpms                    ibm-aix
     0.22 GB  ia-bull-aix433-2013          ia-bull-toolbox-43
     0.21 GB  fsck-vendors                 tuhs

  total crossing a boundary: 35.39 GB
```

## Method

```python
# For each of the 98 archives, read .mirror-index.csv and accumulate:
#   bytes per compressibility class, bytes per extension,
#   and  hash-prefix -> [archive index]  for every file over 4 KB.
# Then, for every hash held by more than one archive, add its size to each pair's counter.
# Clusters: greedily merge the pairs that share the most, floor 0.4 GB, cap 500 GB per unit.
# `unique_bytes()` reports what a cluster holds after identical files inside it collapse to one.
```

The 4 KB floor is deliberate: files below it dominate the COUNT (1.76 million files) and are
irrelevant to the BYTES, and carrying them would have tripled the memory for nothing.

The clusters this script proposed are not quite the nineteen that were built. It optimises for
shared bytes; the final grouping optimises for **what a project needs together** and for **what
changes together**, because a multi-volume RAR cannot be appended to and the unit is therefore the
unit of rebuilding. Where the two disagreed, retrieval won -- `fsck-aix-media` sits with AIX rather
than with its host `fsck.technology`, so that an AIX-under-QEMU project does not have to fetch
404 GB of other vendors to reach 87 GB of install media.
