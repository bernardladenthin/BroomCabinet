# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What the collection is made of, and whether `b2-pack.py`'s grouping still fits it.

WHY THIS IS A TOOL AND NOT A SCRIPT THAT RAN ONCE. The nineteen units in `b2-pack.py` rest on three
measurements: how compressible each archive is, how many bytes two archives hold identically, and
what shape each archive has. Those numbers were taken on 2026-09-26 and written into
`measurements/collection-composition-2026-09-26.md`. They will drift -- a re-fetch grows an archive,
a new mirror arrives, a duplicate is removed -- and a grouping justified by a number nobody can
retake is a grouping nobody can argue with. So the measurement is a command.

IT READS THE INDEXES AND NOTHING ELSE. 98 files of `path,size,mtime_ns,sha256`, 247 MB, already on
disk. No mirrored file is opened, nothing is hashed, nothing is written into the collection.

WHAT IT FOUND THE FIRST TIME, so a later run can be compared against it:

  * 66.6 % of 3.98 TB is already entropy-coded and 0.5 % is text. `pdf` alone is 1.21 TB of scanned
    paper. A large dictionary has almost nothing to work on, which is why `b2-pack.py` defaults to
    `-m1` and stores the two units that are pure RPM and pure scans.
  * 171.37 GB are byte-identical files held more than once, and 111.46 GB of that is inside the
    Bull group: `bull-rpms` is contained 100 % in `bullfreeware` AND 100 % in `ia-bullfreeware`.
    One unit, sorted so the copies are adjacent, turns 185 GB into about 70.
  * About 31 GB of shared bytes cross a unit boundary, the largest 13.46 GB between `fsck-vendors`
    and `vtda`. Capturing those would mean forcing 639 GB into one unit, which is the wrong trade
    when a unit is the thing that gets repacked.

AND ONE MISTAKE WORTH KEEPING. The first version of this measurement had no class for `pdf`, so
1.21 TB -- the largest single kind of content in the collection -- fell into "other" and the
composition table was useless for the one question it was built to answer. `ps`, `bff`, `tap`,
`udf`, `mdf`, `tardist`, `pkg` and `sd` had the same problem. An extension the classifier does not
know is not an error; it is a silent wrong answer.

    python b2-cluster.py                         composition, duplicates, and the grouping check
    python b2-cluster.py --pairs 40               the forty archive pairs that share the most
    python b2-cluster.py --extensions             bytes per extension, per archive
    python b2-cluster.py --propose                re-derive clusters from shared bytes alone
"""
import argparse
import collections
import os
import sys

from common import INDEX_FILE, MIRROR_ROOT, human, read_index, say

# Entropy-coded already. Recompression gains ~0 %; only collapsing DUPLICATES helps here.
#
# `pdf` is in this list because this collection's PDFs are overwhelmingly SCANNED PAPER -- image
# streams inside an already-compressed container. A born-digital text PDF would compress; 944 GB of
# bitsavers scans will not, and treating them as compressible misplans the whole build.
PRECOMPRESSED = set("""gz z bz bz2 xz lz lzma lzo zst zip rar 7z arj lha lzh zoo arc cab
jpg jpeg jfif png gif webp mp3 mp4 m4a m4v avi mkv mov wmv flac ogg oga opus ape
tgz taz tbz tbz2 txz tlz tz tardist rpm deb pkg sd apk jar war ear dmg sit sitx sea
docx xlsx pptx odt ods odp epub mobi cbz cbr pdf woff woff2 xpi crx whl egg gem""".split())

# Uncompressed containers: the real prize. A tar or a bff is a header plus raw member bytes.
RAWCONTAINER = set("tar cpio tap bff installp ar a shar pax dump".split())

# Filesystem images: a mixed bag BY DEFINITION -- an ISO of RPMs gains nothing, an ISO of
# uncompressed install filesets gains a lot. Its own class because it cannot be predicted from the
# extension, so it must not be averaged into either neighbour.
DISKIMAGE = set("iso img dd raw mdf nrg udf vmdk vdi qcow qcow2 dsk ima adf st fdi d64 toast".split())

TEXTLIKE = set("""txt text md markdown html htm xhtml shtml phtml xml json yaml yml csv tsv
c h cc cpp cxx hpp hh s asm inc py pl pm sh bash csh ksh awk sed tcl rb java cs js css
conf cfg ini inf reg bat cmd mk am ac in m4 spec diff patch po log list idx nfo
me ms man 1 2 3 4 5 6 7 8 9 tex sty bib sql sgml dtd xsl lsm uu uue hex srec map lst sym
ps eps rtf boo brd sch""".split())

EXECUTABLE = set("exe dll ocx sys drv so dylib o obj lib com elf rom prom bin".split())

CLASSES = ("precompressed", "raw-container", "disk-image", "text-like", "executable", "unknown")

# Files below this are most of the COUNT and none of the BYTES. Carrying them through the duplicate
# map tripled its memory and changed no figure that matters.
DUPLICATE_FLOOR = 4096


def extension(path):
    base = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in base:
        return ""
    ext = base.rsplit(".", 1)[1].lower()
    return ext if len(ext) <= 12 and ext.isalnum() else ""


def klass(ext):
    for names, label in ((PRECOMPRESSED, "precompressed"), (RAWCONTAINER, "raw-container"),
                         (DISKIMAGE, "disk-image"), (TEXTLIKE, "text-like"),
                         (EXECUTABLE, "executable")):
        if ext in names:
            return label
    return "unknown"


def survey(root, archives, report=None):
    """-> (per-archive stats, hash -> [archive index], hash -> size). Reads indexes only."""
    stats = {}
    owners = {}
    sizes = {}
    for i, name in enumerate(archives):
        rec = {"files": 0, "bytes": 0,
               "klass": collections.Counter(), "ext": collections.Counter()}
        for path, (size, _mtime, digest) in read_index(
                os.path.join(root, name, INDEX_FILE)).items():
            ext = extension(path.replace("\\", "/"))
            rec["files"] += 1
            rec["bytes"] += size
            rec["klass"][klass(ext)] += size
            rec["ext"][ext or "(none)"] += size
            digest = (digest or "").strip()
            if len(digest) == 64 and size > DUPLICATE_FLOOR:
                key = bytes.fromhex(digest[:32])
                if key in owners:
                    if i not in owners[key]:
                        owners[key].append(i)
                else:
                    owners[key] = [i]
                    sizes[key] = size
        stats[name] = rec
        if report:
            report("  %2d/%d %-28s %s" % (i + 1, len(archives), name, human(rec["bytes"])))
    return stats, owners, sizes


def pair_totals(owners, sizes):
    """-> Counter[(i, j)] = bytes the two archives hold identically."""
    pairs = collections.Counter()
    for key, who in owners.items():
        if len(who) < 2:
            continue
        size = sizes[key]
        for a in range(len(who)):
            for b in range(a + 1, len(who)):
                pairs[(who[a], who[b])] += size
    return pairs


def duplicate_total(owners, sizes):
    """-> bytes that would disappear if every identical file were held once."""
    return sum(sizes[k] * (len(v) - 1) for k, v in owners.items() if len(v) > 1)


def propose(archives, stats, pairs, floor=0.4e9, cap=500e9):
    """-> [[archive]] merged greedily on shared bytes. Advisory, not the plan.

    THIS IS NOT WHERE `b2-pack.py`'s UNITS COME FROM, and the difference is the point. This
    optimises for shared bytes; the real grouping optimises for what a project needs together and
    what changes together, because a multi-volume RAR cannot be appended to. Where the two
    disagreed, retrieval won. Run it to see what pure byte-arithmetic would say, then read the
    reasons in `b2-pack.UNITS` for why it does not say that.
    """
    where = dict((n, {n}) for n in archives)
    for (a, b), shared in pairs.most_common():
        if shared < floor:
            break
        na, nb = archives[a], archives[b]
        if where[na] is where[nb]:
            continue
        merged = where[na] | where[nb]
        if sum(stats[m]["bytes"] for m in merged) > cap:
            continue
        for m in merged:
            where[m] = merged
    groups, seen = [], []
    for n in archives:
        if where[n] not in seen:
            seen.append(where[n])
            groups.append(sorted(where[n]))
    return groups


def crossing(owners, sizes, archives, unit_of):
    """-> (bytes that stay inside a unit, bytes that cross, Counter of crossing pairs).

    The clustering objective, stated as two numbers. Duplication inside a unit is a saving because
    a solid block collapses it; duplication across units is paid for twice.
    """
    inside = crossed = 0
    pairs = collections.Counter()
    for key, who in owners.items():
        if len(who) < 2:
            continue
        size = sizes[key]
        units = set(unit_of.get(archives[w]) for w in who)
        if len(units) == 1:
            inside += size * (len(who) - 1)
        else:
            crossed += size * (len(who) - 1)
            for a in range(len(who)):
                for b in range(a + 1, len(who)):
                    if unit_of.get(archives[who[a]]) != unit_of.get(archives[who[b]]):
                        pairs[(archives[who[a]], archives[who[b]])] += size
    return inside, crossed, pairs


def units_from_packer():
    """-> {archive: unit name} read from `b2-pack.py`, or None if it is not importable.

    IMPORTED RATHER THAN RESTATED. A second copy of the nineteen units here would be a second
    thing to keep in step, and this file exists to check the first one -- a check against its own
    copy of the answer checks nothing.
    """
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "b2-pack.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("b2_pack", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict((a, u.name) for u in module.UNITS for a in u.archives())


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=MIRROR_ROOT, help="the collection (default %(default)s)")
    ap.add_argument("--pairs", type=int, default=20, help="how many sharing pairs to print")
    ap.add_argument("--extensions", action="store_true", help="bytes per extension, per archive")
    ap.add_argument("--propose", action="store_true",
                    help="re-derive clusters from shared bytes alone, ignoring the real grouping")
    ap.add_argument("--quiet", action="store_true", help="no progress while it reads")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        say("no collection at %s" % args.root)
        return 2
    archives = sorted(n for n in os.listdir(args.root)
                      if os.path.isfile(os.path.join(args.root, n, INDEX_FILE)))
    if not archives:
        say("no archive under %s carries a %s" % (args.root, INDEX_FILE))
        return 2

    reporter = None if args.quiet else (lambda m: say(m, stream=sys.stderr))
    stats, owners, sizes = survey(args.root, archives, report=reporter)
    total = sum(r["bytes"] for r in stats.values())
    classes = collections.Counter()
    exts = collections.Counter()
    for rec in stats.values():
        classes.update(rec["klass"])
        exts.update(rec["ext"])

    say("%d archives, %s, %d files"
        % (len(archives), human(total), sum(r["files"] for r in stats.values())))
    say("")
    say("WHAT IT IS MADE OF -- the number that decides the compression settings")
    for cls in CLASSES:
        say("  %-16s %12s   %5.1f %%" % (cls, human(classes[cls]),
                                         100.0 * classes[cls] / max(1, total)))
    say("")
    say("  biggest extensions:")
    for ext, b in exts.most_common(12):
        say("    %-10s %12s  [%s]" % (ext, human(b), klass("" if ext == "(none)" else ext)))

    dup = duplicate_total(owners, sizes)
    say("")
    say("IDENTICAL FILES HELD MORE THAN ONCE: %s  (%.1f %% of the collection)"
        % (human(dup), 100.0 * dup / max(1, total)))

    pairs = pair_totals(owners, sizes)
    if args.pairs:
        say("")
        say("  the pairs that share the most:")
        for (a, b), shared in pairs.most_common(args.pairs):
            na, nb = archives[a], archives[b]
            say("    %12s   %-28s %-28s (%.0f%% / %.0f%%)"
                % (human(shared), na, nb,
                   100.0 * shared / max(1, stats[na]["bytes"]),
                   100.0 * shared / max(1, stats[nb]["bytes"])))

    unit_of = units_from_packer()
    if unit_of is None:
        say("")
        say("b2-pack.py is not here, so the grouping cannot be checked.")
    else:
        missing = [a for a in archives if a not in unit_of]
        inside, crossed, crossers = crossing(owners, sizes, archives, unit_of)
        say("")
        say("THE GROUPING IN b2-pack.py, CHECKED AGAINST THIS MEASUREMENT")
        say("  archives no unit claims:      %d%s"
            % (len(missing), ("  -- " + ", ".join(missing[:8])) if missing else ""))
        say("  duplicate bytes INSIDE a unit: %12s   <- a solid block collapses these"
            % human(inside))
        say("  duplicate bytes ACROSS units:  %12s   <- paid for twice" % human(crossed))
        if inside + crossed:
            say("  captured: %.1f %%" % (100.0 * inside / (inside + crossed)))
        for (na, nb), shared in crossers.most_common(10):
            say("    %12s   %-28s %s" % (human(shared), na, nb))

    if args.extensions:
        say("")
        say("EXTENSIONS PER ARCHIVE")
        for name in sorted(stats, key=lambda n: -stats[n]["bytes"]):
            top = ", ".join("%s %s" % (e, human(b))
                            for e, b in stats[name]["ext"].most_common(6))
            say("  %-28s %s" % (name, top))

    if args.propose:
        say("")
        say("WHAT SHARED BYTES ALONE WOULD PROPOSE -- advisory; see propose()'s own note")
        for members in sorted(propose(archives, stats, pairs),
                              key=lambda g: -sum(stats[m]["bytes"] for m in g)):
            raw = sum(stats[m]["bytes"] for m in members)
            say("  %12s  %s" % (human(raw), " + ".join(members)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
