# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Plan the WinRAR units that carry this collection to cold storage. Prints; does not run.

WHY A PLANNER AND NOT A SCRIPT. The collection is 3.98 TB in 98 archives and 1.76 million files.
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
    python b2-pack.py --only bull --verbose          one unit, with its file list
    python b2-pack.py --sizes                       what each unit weighs, from the indexes
    python b2-pack.py --execute --password-file P    actually pack (refuses without rar)
"""
import argparse
import collections
import io
import math
import os
import subprocess
import sys

from common import (INDEX_FILE, MIRROR_ROOT, find_tool, human, read_index, say,
                    split_archive)

# THE VOLUME SIZE IS THE OWNER'S, and it is validated against real discs rather than derived
# here. 24 200 000 000 bytes fits a BD-RE (24 220 008 448) with about 20 MB to spare and therefore
# also fits an M-Disc BD-R 25 GB (25 025 314 816). Using the larger BD-R figure instead would save
# only THREE discs out of 227 across all nineteen units, because rounding up to whole volumes per
# unit dominates -- so one number that fits both media is worth more than the 3.3 % of capacity it
# leaves unused.
VOLUME_BYTES = 24200000000
BD_RE_BYTES = 24220008448
M_DISC_BD_R_BYTES = 25025314816

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
                                              "into all nineteen archives; hence WORK_MUST_BE_FLAT.",
}

# WHERE THE WORK DIRECTORY MAY BE, and this is a measured constraint rather than a preference.
# RAR stores a file given by absolute path under its whole path minus the drive letter. The unit
# index is passed that way, so `<drive>:\some\deep\work` would appear inside every archive
# as `some/deep/work/<unit>.index.csv` -- and one under a profile would carry the account
# name into all nineteen. One component directly under a drive root keeps it to `work/<unit>...`.
WORK_MUST_BE_FLAT = 1
PERSONAL_IN_PATH = ("users", "documents", "desktop", "appdata", "home")

# Switches whose exact behaviour differs between WinRAR versions. Named here rather than assumed,
# because a wrong guess is only visible after hours of packing.
VERIFY_AGAINST_YOUR_RAR = {
    "nothing": "every switch this tool emits was put to a real WinRAR on 2026-09-26. What is "
               "listed above is measured, not assumed. The one thing no measurement can settle is "
               "whether a restore works twenty years from now, which is why the volumes are "
               "RAR5 rather than a newer format and the dictionary stays at 1 GB or less.",
}


class Options(object):
    r"""WinRAR settings, immutable. `with_()` returns a copy -- this is the whole builder.

    NOTHING IS DUPLICATED PER UNIT. `DEFAULTS` holds the settings that are right for two thirds of
    the collection, and a unit names only what differs. A table of nineteen full option sets would
    drift the moment one of them was edited; nineteen one-line overrides cannot.
    """

    FIELDS = ("archive_format", "method", "dictionary", "solid", "solid_per_volume",
              "volume_bytes", "recovery_record", "recovery_volumes_min",
              "recovery_volumes_fraction", "lock", "encrypt_headers", "extra")

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

    def recovery_volumes(self, volumes):
        """-> how many .rev files this unit gets, for a set of `volumes` volumes.

        A FIXED COUNT IS THE WRONG SHAPE and that is measured, not felt. Two .rev files protect
        `unix-history` (2 volumes) completely and `ibm-aix` (32 volumes) by 6 %. The units here
        span 2 to 32 volumes, so the redundancy has to scale with the set -- a fraction with a
        floor. The floor matters: one .rev can only ever answer one lost volume, and a single disc
        failure in a two-volume unit would otherwise be fatal.
        """
        if volumes is None or not self.volume_bytes:
            return 0
        return max(self.recovery_volumes_min,
                   int(math.ceil(volumes * self.recovery_volumes_fraction)))

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
                if self.solid_per_volume:
                    out.append("-sv")
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


# The settings that are right for most of 3.98 TB: fast, because two thirds of it cannot be
# compressed anyway, but NOT stored -- `-m0` would also switch off the duplicate collapse, and the
# duplicates are worth more than the compression.
DEFAULTS = Options(
    archive_format="5",
    method=1,
    dictionary="256m",
    solid=True,
    solid_per_volume=True,
    volume_bytes=VOLUME_BYTES,
    recovery_record="10",
    recovery_volumes_min=2,
    recovery_volumes_fraction=0.10,
    lock=True,
    encrypt_headers=True,
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
         "containers, the only large body in the collection where compression level pays. Alone "
         "because it is the unit most likely to be re-fetched, and nothing else should be "
         "repacked when it is.",
         DEFAULTS.with_(method=5, dictionary="1g")),

    Unit("aix-opensource", ["oss4aix.org"],
         "208 GB that is 100 % rpm. Stored rather than compressed: there is nothing to win and "
         "-m0 turns the longest packing job in the plan into a copy. "
         "`rwth-aachen-ftp` LEFT ON 2026-10-03 and the unit's own sentence is why: this one is "
         "all rpm, and that archive held none -- 41 % exe, 25 % zip, 17 % pdf -- so it was being "
         "stored under a rule written for somebody else's content. It shared 0.00 GB with this "
         "unit and 6.30 GB with ibm-pc-hardware, where it now is.",
         DEFAULTS.with_(method=0)),

    Unit("aix-media", ["fsck-aix-media", "fsck-aix-apps"],
         "87 GB of AIX install media and applications. Kept with AIX rather than with its host "
         "fsck.technology BECAUSE OF THE RETRIEVAL TEST: an AIX-under-QEMU project needs exactly "
         "this, and grouping by source would make it fetch 404 GB of other vendors to reach it."),

    Unit("bull", ["bull-rpms", "bull-srpms", "bullfreeware", "ia-bullfreeware",
                  "ia-bull-toolbox-43", "ia-bull-aix433-2013", "ia-bull-aix433-2005",
                  "biblionik-bull", "biblionik-goupil"],
         "185 GB raw holding 111.46 GB of byte-identical duplicates -- bull-rpms is contained "
         "100 % in bullfreeware AND 100 % in ia-bullfreeware. Sorted so the copies are adjacent, "
         "a solid block collapses them to about 70 GB. Bull closed in 2022, so this unit is "
         "finished forever and its size costs nothing in future rebuilds. "
         "`biblionik-goupil` joined on 2026-09-27: the other half of the same French host, "
         "37 files of bootable SMT Goupil G3 images. Not Bull machines, but one server, one "
         "operator and one risk -- an EOL CentOS 7 box serving HTTP only -- so they travel "
         "together.",
         DEFAULTS.with_(dictionary="512m")),

    Unit("ibm-docs", ["ibm-redbooks", "ibm-rs6000-support", "gsi-collection", "filibeto-aix-lib",
                      "cmu-shadow",
                      "damage-rt", "AIX5-IA64", "infania-tl1", "infania-tl2", "aixtools",
                      "circle4", "rs6000-microcode", "aix-orphans", "aix-qemu-git", "techsysadm",
                      "typewritten", "aixpdslib", "funet-aix", "ibm-openxl-docs", "iffly-wiki",
                      "misterhayden", "perzl-wiki", "tvsat-cpc710", "csri-toronto"],
         "About 50 GB in 23 archives: Redbooks, the RS/6000 support tree, two wikis, a blog, "
         "manuals and the QEMU recipes. One unit because you consult them together and never one "
         "alone, and because 23 separate uploads is the chaos this plan exists to avoid. The only "
         "text-rich unit in the collection, so it gets the best compression -- it is small enough "
         "for that to be free.",
         DEFAULTS.with_(method=5, dictionary="512m")),

    Unit("ibm-pc-hardware", ["ps-2.kev009.com", "ardent-tool", "mcamafia", "rwth-aachen-ftp"],
         "374 GB of PS/2 and RS/6000 hardware material -- pccbbs alone is 248 GB. They share "
         "5.81 GB of identical files and the same subject. `mcamafia` joined on 2026-09-26: "
         "170 MB of Peter Wendt's own PS/2 technical-reference scans, the same subject as "
         "ardent-tool and very likely overlapping it. It belongs beside the archive it may "
         "duplicate rather than in another unit, where the duplication would be paid for twice; "
         "`b2-cluster.py` reports how much is actually shared. "
         "`rwth-aachen-ftp` JOINED ON 2026-10-03, moved out of aix-opensource, and four separate "
         "readings agreed: it shared 0.00 GB with its old unit and 6.30 GB here -- 62 % of its "
         "own 10.16 GB, 8 490 files of it with ps-2.kev009.com alone; its content profile is "
         "41 % exe / 25 % zip / 17 % pdf against ps-2's 26 % iso / 26 % exe / 12 % pdf, while the "
         "unit it sat in is 100 % rpm and stored BECAUSE of that; and somebody after PS/2 "
         "material had to open two archives to get it. 59 % of that archive is contained in "
         "ps-2.kev009.com."),

    Unit("ibm-os2-other", ["fsck-ibm-other", "os2bbs", "zx-hobbes-os2", "infania-unixos2",
                           "dreamlandbbs-os2"],
         "144 GB of IBM's non-AIX world: OS/2, OS/400, and THREE OS/2 file collections. The "
         "1.83 GB of identical files is between os2bbs and zx-hobbes-os2; `dreamlandbbs-os2` "
         "grew from almost nothing to 18.85 GB on 2026-10-03 and shares only 0.07 GB with "
         "either, which was worth measuring rather than assuming -- two OS/2 shareware "
         "collections that barely overlap. It is here for the subject, not for the duplicates."),

    # ---------------------------------------------------------------- bitsavers, split by its own
    # top level. The cut follows the rsync tree, so a re-fetch touches a KNOWN subset of units --
    # splitting across upstream directory boundaries would make every delivery repack two.
    Unit("bitsavers-pdf", ["bitsavers/pdf"],
         "652 GB of scanned paper, 93 681 files. Stored: these are image streams inside an "
         "already-compressed container, and -m1 would spend hours to find nothing.",
         DEFAULTS.with_(method=0)),

    Unit("bitsavers-magazines", ["bitsavers/magazines"],
         "192 GB in 2 997 files -- the largest files in the collection. Grows a few scans at a "
         "time, which is exactly why it is not inside the 652 GB unit.",
         DEFAULTS.with_(method=0)),

    Unit("bitsavers-bits", ["bitsavers/bits"],
         "174 GB of software rather than paper, 58 257 files, and the part of bitsavers with real "
         "duplicate mass against the rest of the collection."),

    Unit("bitsavers-rest", ["bitsavers"],
         "179 GB: components, projects, test_equipment, communications and two dozen small "
         "branches. Expressed as `bitsavers` MINUS the three units above, so a new top-level "
         "directory upstream lands here instead of being silently dropped -- the partition test "
         "is what makes that safe.",
         exclude=["bitsavers/pdf", "bitsavers/magazines", "bitsavers/bits"]),

    # ---------------------------------------------------------------- large third-party bodies
    Unit("fsck-vendors", ["fsck-vendors"],
         "404 GB in 37 vendor trees from one host: SGI 105, Sun 82, DEC-Compaq 64, HP 33, "
         "NeXT 19. One fetch, one unit."),

    Unit("vtda", ["vtda"],
         "235 GB from five rsync modules. NOT merged with bitsavers although both are museum "
         "archives: they are the two upstreams that grow on their own, and merging would make "
         "every delivery repack 1 431 GB. They share 0.77 GB, so merging would save nothing."),

    Unit("oldskool", ["oldskool"],
         "149 GB, of which drivers/ is 125 GB. One host, one 40-hour fetch, one unit."),

    # ---------------------------------------------------------------- by platform
    Unit("sgi", ["irixnet-ftp", "zx-sgi-freeware-old", "sgidepot"],
         "61 GB of IRIX -- 55 GB until 2026-10-03, when zx-sgi-freeware-old went from 0.94 GB to "
         "6.68 GB: its hand-written marker had claimed complete while the operator's own sitemap "
         "named 4 404 more files. The fsck.technology SGI tree stays in `fsck-vendors`; see the note there "
         "-- 105 GB would have to move to join it, and one host per unit keeps re-fetches "
         "simple. `sgidepot` joined on 2026-09-26: 497 MB of Ian Mapleson's own writing, "
         "including his HTML re-typesetting of the Indigo2 Technical Report. Its European "
         "mirror has already lost its DNS record, which is the clearest statement of risk in "
         "this whole plan."),

    Unit("dec", ["dec-ftp-2006", "zx-gatekeeper-dec", "zx-ultrix-freeware", "zx-kednos-vms",
                 "hp-openvms-2008", "somuchstuff-pdp8", "decromancer-bits"],
         "70 GB of DEC across PDP, VAX, Ultrix and VMS, including the HP-era OpenVMS tree, which "
         "belongs to DEC's lineage rather than to HP's. 26 % uncompressed containers, so this one "
         "is worth more than the default effort.",
         DEFAULTS.with_(method=3)),

    Unit("next", ["next-68k-org", "nice-next"],
         "39 GB of NeXT in two archives that share 0.50 GB of identical files. next-68k-org was "
         "itself unpacked out of a tar inside fsck-vendors, so the two halves of the NeXT world "
         "would otherwise sit in different units."),

    Unit("unix-history", ["tuhs", "ibiblio-historic-linux", "crashing-org", "crashing-org-kernel",
                          "crashing-org-www", "penguinppc", "debian-powerpc-boot",
                          "ibiblio-ppc-ports", "devicetree-openfirmware",
                          "linuxfoundation-refspecs", "sco-devspecs", "sco-gabi",
                          "technologists-dellunix", "technologists-sauer", "cryp-to-cwg"],
         "30 GB: the Unix Heritage Society, historic Linux, Linux-on-PowerPC and the ABI "
         "specifications. Read together when tracing where something came from."),

    Unit("misc-platforms", ["develooper-hpux", "hp-labs-2007", "hp-alphaserver-2008",
                            "agilent-ftp-2009", "zx-alphant-nt", "parisc-firmware",
                            "apollo-clavius", "infania-solaris", "sun3arc",
                            "novasareforever-aviion", "ndwiki-norsk-data",
                            "transputer-classiccmp", "wotug-inmos", "zx-microway", "zx-be-os",
                            "mpoli-bbs", "square7-vintage", "giga-nl-walter", "abc-bladet",
                            "adoxa-dos", "bretjohnson", "dialectronics", "csiph-gallery",
                            "infania-os-history", "ultimate-fastpath", "hp-labs-linux-salvage",
                            "vgamuseum-doc", "obsolyte", "fjkraan", "chipdb", "iommu",
                            "retro-digitalvintage", "kib-x86docs",
                            "seds-frommert", "acpc-amstrad", "openpa"],
         "HP-UX, Alpha, PA-RISC, Apollo, Solaris, Data General, Norsk Data, transputers, BeOS and "
         "a dozen one-person sites. The deliberate remainder: each too small to upload on its own "
         "and belonging to no platform in particular. "
         "`vgamuseum-doc` joined on 2026-09-26 and is the exception that had to be argued: at "
         "3.44 GB it is not small, and it is coherent rather than leftover -- cross-vendor "
         "graphics-card documentation, from IBM GXT and the RS/6000 adapter books through DEC "
         "ZLXp, Sun TechSource and the INMOS databook to PC chipsets. It is here BECAUSE it "
         "belongs to no single platform, which is what this unit is for; putting it with IBM "
         "would have buried the DEC, Sun and SGI half of it under the wrong subject. "
         "`acpc-amstrad` joined on 2026-09-27: 34 files, 1.24 GB of Amstrad CPC peripheral "
         "documentation -- printer and 3-inch floppy drive manuals in four languages, ROM "
         "expansion data sheets, the CPC464 technical specification. One home computer, one "
         "small tree, no platform of its own here: exactly what this unit is for. "
         "`openpa` joined on 2026-09-28: Paul Weissmann's original PA-RISC and HP 9000 articles, "
         "under 50 MB. PA-RISC already reaches this unit through `parisc-firmware` and "
         "`develooper-hpux`, and none of the three is large enough to stand alone. It was added "
         "on the 27th and removed the same day when the fetch failed outright -- an archive "
         "holding nothing does not belong in a backup plan."),
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
        rel = os.path.relpath(dirpath, base).replace("\\", "/")
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
        argv = ([rar, "a"] + unit.options.switches(volumes)
                + [archive, "@" + list_path, index_path])
        steps.append({"unit": unit, "argv": argv, "cwd": root, "list_path": list_path,
                      "index_path": index_path, "archive": archive, "rows": rows,
                      "volumes": volumes, "recovery_volumes": unit.options.recovery_volumes(volumes),
                      "empty_dirs": dirs})
    index_archive = os.path.join(out, INDEX_DIR, "index.rar")
    steps.append({"unit": None, "argv": [rar, "a", "-ep"] + INDEX_OPTIONS.switches()
                  + [index_archive, "*" + INDEX_SUFFIX],
                  "cwd": os.path.join(out, INDEX_DIR), "list_path": None, "index_path": None,
                  "archive": index_archive, "rows": [],
                  # Every step carries the same keys, so a caller never has to ask which kind it
                  # is before reading one. The index archive has no volumes and no directories.
                  "volumes": None, "recovery_volumes": 0, "empty_dirs": []})
    return steps


def write_list(step, dry_run=True):
    """The `@list` file and the unit's index, both OUTSIDE the collection."""
    if dry_run:
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
        discs = step["volumes"] + step["recovery_volumes"]
        total_discs += discs
        say("", stream=stream)
        extra = ("  + %d empty dir(s)" % len(step["empty_dirs"])) if step["empty_dirs"] else ""
        say("=== %-22s %10s  %7d files%s  %3d vol + %d rev = %3d disc(s) ==="
            % (unit.name, human(size), len(step["rows"]), extra, step["volumes"],
               step["recovery_volumes"], discs), stream=stream)
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
    say("%d unit(s), %s, %d files, %d disc(s) at %s per volume"
        % (len(steps) - 1, human(total_bytes), total_files, total_discs, human(VOLUME_BYTES)),
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


def first_volume(archive):
    """-> the name RAR gives the first volume of a split set: `name.part01.rar`."""
    stem = archive[:-4] if archive.lower().endswith(".rar") else archive
    return stem + ".part01.rar"


def check_password(text):
    r"""-> a complaint, or None. Called before anything is packed.

    ONE PASSWORD FOR ALL NINETEEN UNITS, decided deliberately on 2026-09-26. The material is
    public: it was fetched from public servers, and any sharing would go to a handful of people and
    would cover the whole collection rather than one unit. Compartmenting buys nothing here, while
    nineteen secrets would be nineteen chances to lose one over the archive's intended lifetime.

    WHICH MAKES A LOST OR WRONG PASSWORD THE ONLY REAL RISK, and it is the one thing this function
    can act on. A truncated or mistyped password file does not fail -- it packs 3.98 TB that opens
    with a key nobody has, and the mistake surfaces years later. So the shape is checked here, and
    `rar t` is run against every unit as soon as it is written.
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
        encrypted = step["unit"] is None or step["unit"].options.encrypt_headers
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
        test = [rar, "t"] + (["-hp" + password] if encrypted else []) + [target]
        say("  testing %s" % " ".join(hide_password(test)))
        checked = subprocess.run(test, cwd=step["cwd"])
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
    ap.add_argument("--execute", action="store_true", help="actually pack (needs --password-file)")
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
    rar = "rar"
    if args.execute:
        if not args.password_file:
            say("--execute needs --password-file: the password is never a command-line argument")
            return 2
        rar = find_rar()
        if rar is None:
            say("REFUSING TO RUN: no rar executable found.")
            return 2

    units = UNITS
    if args.only:
        wanted = set(args.only)
        unknown = wanted - set(u.name for u in UNITS)
        if unknown:
            say("no such unit: %s" % ", ".join(sorted(unknown)))
            return 2
        units = tuple(u for u in UNITS if u.name in wanted)

    # An archive whose index is missing would plan as an EMPTY unit, because `common.read_index`
    # answers {} rather than raising -- right for a cache, wrong for a packing plan. Checked here,
    # before anything is read, so the refusal names the file instead of the archive being silently
    # small. See `archive_rows`.
    absent = [os.path.join(a, INDEX_FILE) for u in units for a in u.archives()
              if not os.path.isfile(os.path.join(args.root, a, INDEX_FILE))]
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

    if not args.execute:
        say("")
        say("NOTHING WAS RUN. Pass --execute with --password-file to pack.")
        say("")
        say("Measured against a real WinRAR on 2026-09-26:")
        for fact, note in sorted(MEASURED_ON_THIS_MACHINE.items()):
            say("  %-36s %s" % (fact, note))
        say("")
        say("Still to check against your own rar.txt:")
        for switch, note in sorted(VERIFY_AGAINST_YOUR_RAR.items()):
            say("  %-22s %s" % (switch, note))
        return 0

    with io.open(args.password_file, encoding="utf-8") as fh:
        # Only the line ending is stripped: check_password complains about stray whitespace
        # rather than removing something that may legitimately belong to the password.
        password = fh.readline().rstrip(chr(13) + chr(10))
    complaint = check_password(password)
    if complaint:
        say("REFUSING: %s." % complaint)
        return 2
    # A password file beside the volumes would be uploaded with them.
    for where, label in ((args.out, "--out"), (args.work, "--work")):
        if os.path.abspath(args.password_file).startswith(os.path.abspath(where) + os.sep):
            say("REFUSING: the password file is inside %s and would be uploaded with the archives."
                % label)
            return 2
    return execute(steps, rar, password)


if __name__ == "__main__":
    sys.exit(main())
