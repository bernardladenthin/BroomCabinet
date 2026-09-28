# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Unpack a tar that is PACKAGING around a mirrored site, into an archive of its own.

    python extract-container-tar.py --tar "Q:\mirror\bitsavers\mirrors\x.tar" \
                                    --archive agilent-ftp-2009 --strip-root --dry-run
    ...and again without --dry-run to do it.

WHICH TARS THIS IS FOR, AND WHICH IT IS NOT. The collection holds 6 728 tar files, 460 GB, and
almost all of them are CONTENT: IBM's fix packages, install media, the original UNIX tapes in
tuhs. Unpacking those would destroy the artefact -- the tar IS the thing that was shipped.

This tool is for the other kind: six tars, 82.7 GB, each wrapping a crawl of a website or FTP
server, made by somebody else years ago as a convenience. There the tar is a box, not a document,
and while it stays closed the contents are invisible to every tool here -- containment.py cannot
deduplicate them, find-html-imposters.py cannot inspect them, and a search has to open a 36 GB
file to answer any question.

The test is not the file extension. It is: would the original site have served this tar? If the
answer is no, it is packaging.

    ALREADY UNPACKED, and what each one had to record. RENAMED.txt is not paperwork: without it
    an extracted tree is the right bytes under the wrong names with nothing saying so.

        next-68k-org          234 761 files   37.7 GB   253 951 renamed        -- links
        dec-ftp-2006           22 172         36.0 GB    10 131 renamed    16 links
        hp-alphaserver-2008    10 202          1.0 GB        79 renamed        --
        hp-openvms-2008        27 373          1.3 GB        57 renamed        --
        hp-labs-2007            9 171          4.0 GB        45 renamed        --
        agilent-ftp-2009          814          2.5 GB   NEITHER FILE

    agilent-ftp-2009 carries no RENAMED.txt and no SYMLINKS.txt because it needed neither -- they
    are written only when there is something to write. Absence there means nothing was changed,
    and this is the one case where an empty record and a missing record say the same thing.
    next-68k-org's 253 951 is not a defect either: one NeXT FTP mirror full of Apache sort links,
    and every mapping is on disk.

    A SEVENTH CANDIDATE, MEASURED AND NOT TAKEN. ia-bullfreeware/packages.tar, 85.04 GB, dry run
    of 2026-09-12: 13 075 entries, ZERO renames, zero links or devices, zero path escapes, zero
    collisions, longest path 146 characters -- the cleanest container measured here. Against
    bullfreeware/.sha256sum it holds 1 877 basenames the live crawl never got, mostly .src.rpm
    sources. LEFT PACKED: 85 GB of disk is the owner's decision, not this tool's. Full figures in
    mirror.py's ia-bullfreeware entry; the check does not need repeating.

WHY A SEPARATE TOP-LEVEL ARCHIVE rather than unpacking in place. Because
bitsavers/mirrors/<site>/ would be a mirror inside a mirror, which this collection excludes
elsewhere on principle -- os2site.com's /mirrors/ is off-limits for exactly that reason. As its
own archive each site gets a marker, a checksum index and a PROVENANCE of its own, and becomes
visible to every tool. Buried inside bitsavers it would inherit a provenance that describes an
rsync mirror, which it is not.

WHAT IT REFUSES TO DO
  * absolute paths and `..` components -- a tar can escape its own directory and this one may not
  * symlinks, hardlinks, devices, fifos -- Windows cannot create them without privilege, so they
    are SKIPPED AND LISTED rather than half-created
  * overwrite anything that already exists

EVERY RENAME IS RECORDED. NTFS cannot hold `?` `:` `*` `<` `>` `|` `"` in a name, and a mirror of
a 2006 FTP server is full of them -- ftp.digital.com alone carries 5 124 files named after Apache
sort links, `index.html?C=D;O=A`. They are mapped the way mirror.py maps them, and every mapping
is written to RENAMED.txt beside the tree. Without that list the extracted tree would be a quiet
forgery: right bytes, wrong names, and nothing saying so.

VERIFICATION IS AGAINST THE TAR, NOT AGAINST ITSELF. Every extracted file's size is compared with
the size the tar recorded for it. A count that matches proves only that the loop ran.
"""
import argparse
import io
import os
import shutil
import sys
import tarfile
import time


from common import MIRROR_ROOT, long_path, safe_tar_segment, sha256_file


# ---------------------------------------------------------------- the three container formats
#
# THE FILE IS STILL CALLED extract-container-tar.py because renaming it would break every
# invocation recorded in a PROVENANCE file, and those records are the point. It reads tar, zip and
# single-stream gzip. The alternative -- a second tool for zip -- would mean a second copy of
# safe_tar_segment, of the escape refusals, of the collision test and of RENAMED.txt, and two
# copies of a safety rule are one rule and one liability the day somebody fixes only one of them.

# `r:*` AND NOT `r:`. The mode was uncompressed-tar-only until 2026-09-13, which was true of
# every tar this tool had been pointed at and false of the next one: ia-bull-toolbox-43 holds
# toolbox.aix43.tar.gz and htmlfiles.tar.gz, and `r:` raises ReadError on both. `r:*` lets
# tarfile pick, and keeps a SEEKABLE file object -- `r|*`, the streaming form, would not, and the
# extraction loop needs to seek past member data it is not taking.
#
# The cost is that a compressed tar is decompressed twice, once for the table of contents and
# once to extract. For 529 MB that is seconds; for an 85 GB container it would not be, and the
# 85 GB one was uncompressed.
def container_kind(path):
    low = path.lower()
    if low.endswith(".zip"):
        return "zip"
    if low.endswith(".gz") and not low.endswith(".tar.gz"):
        return "gz"
    return "tar"


def read_toc(path, kind):
    """-> [(name, size, type, mtime, linkname)] in the tar vocabulary, whatever the format.

    ZIP directory entries end in '/' and carry no content; they are reported as DIRTYPE so the
    existing plan builder treats them the way it treats a tar's directories.

    A SINGLE-STREAM GZIP HAS NO MEMBER NAME AND NO STORED SIZE. The name is the container's own,
    minus `.gz` -- that is a convention, not metadata, and it is the only thing there is. The size
    is obtained by decompressing and counting, which means the data is read twice. Accepted here
    because these are containers sitting INSIDE an archive and are small; the trailer's ISIZE
    field would avoid it and is wrong above 4 GB, and a size that is right except when it matters
    is worse than a slow one.
    """
    if kind == "tar":
        with tarfile.open(path, "r:*") as tf:
            return [(m.name, m.size, m.type, m.mtime, m.linkname) for m in tf]
    if kind == "zip":
        import zipfile
        out = []
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                is_dir = i.is_dir()
                # ZIP stores local time as a 6-tuple with no zone. mktime reads it as local time,
                # which is what every other extractor does with it.
                try:
                    mtime = time.mktime(tuple(i.date_time) + (0, 0, -1))
                except (ValueError, OverflowError):
                    mtime = 0
                out.append((i.filename, 0 if is_dir else i.file_size,
                            tarfile.DIRTYPE if is_dir else tarfile.REGTYPE, mtime, ""))
        return out
    import gzip
    n = 0
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 << 20), b""):
            n += len(chunk)
    return [(os.path.basename(path)[:-3], n, tarfile.REGTYPE, os.path.getmtime(path), "")]


def open_members(path, kind):
    """-> iterator of (name, readable-stream-or-None). Mirrors `for m in tf` over any format."""
    if kind == "tar":
        with tarfile.open(path, "r:*") as tf:
            for m in tf:
                yield m.name, (tf.extractfile(m) if m.isfile() else None)
        return
    if kind == "zip":
        import zipfile
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                if i.is_dir():
                    yield i.filename, None
                else:
                    with z.open(i) as fh:
                        yield i.filename, fh
        return
    import gzip
    with gzip.open(path, "rb") as fh:
        yield os.path.basename(path)[:-3], fh


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tar", required=True)
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True, help="name of the new top-level archive")
    ap.add_argument("--strip-root", action="store_true",
                    help="drop the tar's own single top directory. Use it when that directory "
                         "merely repeats the archive name -- it usually does, and keeping it "
                         "would nest every path one level deeper for nothing.")
    ap.add_argument("--only", metavar="PREFIX",
                    help="extract ONLY members whose path, after --strip-root, starts with this. "
                         "For a rehearsal on a real but small part of a large tar: the whole "
                         "pipeline runs -- refusals, renames, collision check, size verification "
                         "against the tar -- on a few files instead of tens of thousands. A "
                         "PREFIX is used rather than a count because a rehearsal has to be "
                         "repeatable and has to name what it covered; 'the first 20 entries' is "
                         "neither. The result is a DELIBERATELY PARTIAL tree: this tool writes no "
                         "completion marker in any case, so nothing downstream can mistake it "
                         "for a finished archive, and --only additionally suppresses the tar "
                         "hash, which on an 85 GB container costs more than the rehearsal.")
    ap.add_argument("--in-place", action="store_true",
                    help="unpack BESIDE the container, inside the archive that already holds it, "
                         "instead of into a new top-level archive. For a container that is part "
                         "of what was published rather than a box around a site: an Internet "
                         "Archive item's _jp2.zip belongs to that item and moving it elsewhere "
                         "would break the relation. The archive-exists refusal does not apply, "
                         "so EVERY planned output path is checked individually instead, and a "
                         "single one already present aborts the run before anything is written.")
    ap.add_argument("--prefix", metavar="PATH",
                    help="put everything under this directory, created below the destination. "
                         "THE CASE THIS EXISTS FOR: ia-bullfreeware's packages.tar stores its "
                         "members as ./RPMS/..., while packages.sfv -- the uploader's own CRC32 "
                         "manifest, made from the directory the tar was created inside -- names "
                         "them packages/RPMS/... . Extracted bare, every one of the 11 884 "
                         "manifest lines misses, and a verification of a complete tree reports a "
                         "complete loss. Extracted under --prefix packages the manifest applies "
                         "as written, with no stripping, no rewriting and nothing to remember. "
                         "Applied AFTER --strip-root and after --only, which both speak the "
                         "container's own paths.")
    ap.add_argument("--min-free-gb", type=float, default=20.0,
                    help="refuse to start if less than this would remain free afterwards "
                         "(default 20). An 85 GB extraction that stops on a full volume leaves a "
                         "tree that is neither the old one nor the new one, and nothing on disk "
                         "says which.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.prefix:
        bad = [p for p in args.prefix.replace("\\", "/").split("/")
               if p in ("", ".", "..") or ":" in p]
        if bad or args.prefix.startswith(("/", "\\")):
            sys.exit("--prefix must be a plain relative path: %r" % args.prefix)

    kind = container_kind(args.tar)
    if args.in_place:
        dest = os.path.dirname(os.path.abspath(args.tar))
        if os.path.basename(os.path.dirname(dest + os.sep)) and args.archive:
            expect = os.path.join(os.path.abspath(args.root), args.archive)
            if os.path.normcase(dest) != os.path.normcase(expect):
                sys.exit("--in-place unpacks into the container's own directory, %s,\n"
                         "but --archive says %s. Name the archive the container is in."
                         % (dest, expect))
    else:
        dest = os.path.join(os.path.abspath(args.root), args.archive)
        if os.path.exists(long_path(dest)) and not args.dry_run:
            sys.exit("destination already exists: %s\nRefusing to write into it." % dest)

    print("  reading the table of contents (%s) ..." % kind, flush=True)
    t0 = time.time()
    members = read_toc(args.tar, kind)
    print("  %d entries in %.0f s" % (len(members), time.time() - t0), flush=True)

    roots = {m[0].split("/")[0] for m in members}
    strip = ""
    if args.strip_root:
        if len(roots) != 1:
            sys.exit("--strip-root asked for, but the tar has %d top-level entries: %s"
                     % (len(roots), sorted(roots)[:5]))
        strip = roots.pop() + "/"
        print("  stripping the tar's own root: %r" % strip)

    plan, renamed, skipped, refused = [], [], [], []
    filtered = 0
    root_entry = strip[:-1] if strip else None
    for name, size, typ, mtime, linkname in members:
        rel = name.rstrip("/")
        if root_entry is not None:
            # THE ROOT ENTRY IS USUALLY STORED WITHOUT A TRAILING SLASH, and matching only on the
            # `root/` prefix therefore misses it: every child is stripped correctly and the root
            # itself is recreated as an empty directory inside the archive, right beside the
            # contents it was supposed to be replaced by. Harmless -- and exactly the kind of
            # quiet wrongness a tree carries for years. Compare against the bare name first.
            if rel == root_entry:
                continue
            if not rel.startswith(strip):
                refused.append((name, "outside the root --strip-root was given for"))
                continue
            rel = rel[len(strip):]
        if not rel:
            continue
        # Filtered BEFORE the safety checks, so a rehearsal's counts describe the rehearsal. A
        # refusal or a collision elsewhere in the tar is a fact about the tar, not about what is
        # being written now, and mixing the two would make the rehearsal's report unreadable --
        # the dry run over the whole container is where those belong.
        if args.only and not rel.startswith(args.only):
            filtered += 1
            continue
        # AFTER the filter, so --only keeps speaking the container's own paths, and after the
        # escape checks have something to check: a prefix is validated once at startup and is not
        # a place an escape can enter.
        if args.prefix:
            rel = args.prefix.replace("\\", "/").strip("/") + "/" + rel
        parts = rel.split("/")
        if any(p in ("", ".", "..") for p in parts) or rel.startswith("/") or ":" in parts[0][1:2]:
            refused.append((name, "path escapes the archive"))
            continue
        if typ not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
            skipped.append((name, {tarfile.SYMTYPE: "symlink", tarfile.LNKTYPE: "hardlink",
                                   tarfile.CHRTYPE: "char device", tarfile.BLKTYPE: "block device",
                                   tarfile.FIFOTYPE: "fifo"}.get(typ, "type %r" % typ),
                            linkname))
            continue
        safe = [safe_tar_segment(p) for p in parts]
        if safe != parts:
            renamed.append(("/".join(parts), "/".join(safe)))
        plan.append((name, os.path.join(dest, *safe), size,
                     typ == tarfile.DIRTYPE, mtime))

    # TWO TAR ENTRIES MUST NOT LAND ON ONE PATH. Renaming is not injective: `?` `*` `:` all map to
    # the same replacement character, so `a?b` and `a*b` become one name and the second write
    # silently destroys the first. Nothing downstream would notice -- the file count would simply
    # be one lower than the manifest, in a tree where a lower count has half a dozen innocent
    # explanations. ftp.digital.com carries 5 124 Apache sort-link names of the form
    # `index.html?C=D;O=A`, which is where this stops being hypothetical.
    #
    # Case is a SEPARATE question and is only a warning. Q:\mirror has the NTFS per-directory
    # case-sensitivity flag set and new subdirectories inherit it, so `Foo` and `foo` coexist. If
    # that flag were ever missing they would not, so a case clash is worth naming even though it
    # is not an error here.
    seen_exact, seen_lower, collide, case_clash = {}, {}, [], []
    for entry in plan:
        name, out = entry[0], entry[1]
        if out in seen_exact:
            collide.append((seen_exact[out], name, out))
        else:
            seen_exact[out] = name
            low = out.lower()
            if low in seen_lower:
                case_clash.append((seen_lower[low], name))
            else:
                seen_lower[low] = name

    files = [p for p in plan if not p[3]]
    total = sum(p[2] for p in files)
    if args.only:
        print("\n  REHEARSAL: only members under %r -- %d of %d entries set aside"
              % (args.only, filtered, len(members)))
        if not plan:
            sys.exit("  nothing matches that prefix. Check it against the tar's own listing.")
    print("\n  %d files (%.2f GB), %d directories" % (len(files), total / 1e9, len(plan) - len(files)))
    print("  %d names had to be changed for NTFS" % len(renamed))
    print("  %d entries skipped (links/devices Windows cannot create)" % len(skipped))
    print("  %d entries REFUSED (path escape)" % len(refused))
    print("  %d COLLISIONS (two entries, one destination path)" % len(collide))
    print("  %d case-only clashes (fine while the case-sensitivity flag is set)" % len(case_clash))
    longest = max((len(p[1]) for p in plan), default=0)
    print("  longest destination path: %d characters" % longest)

    # SPACE, BEFORE ANYTHING IS WRITTEN. A run that fills the volume halfway through leaves a tree
    # that is neither the old one nor the new one, and no file on disk records which.
    try:
        free = shutil.disk_usage(os.path.dirname(os.path.abspath(dest))).free
        after = free - total
        print("  free now %.1f GB, after this extraction %.1f GB" % (free / 1e9, after / 1e9))
        if after < args.min_free_gb * 1e9 and not args.dry_run:
            sys.exit("\n  REFUSING: that would leave %.1f GB, below the %.1f GB floor. "
                     "Nothing written." % (after / 1e9, args.min_free_gb))
    except OSError as exc:                                      # noqa: BLE001
        print("  free space not readable (%s) -- not checked" % str(exc)[:40])
    for a, b, out in collide[:8]:
        print("     COLLISION %s\n           + %s\n          -> %s" % (a, b, out))
    for a, b in case_clash[:5]:
        print("     case clash %s  vs  %s" % (a, b))
    for n, why in refused[:5]:
        print("     REFUSED %s -- %s" % (n, why))
    for n, why, target in skipped[:5]:
        print("     skipped %s -- %s%s" % (n, why, (" -> " + target) if target else ""))
    for a, b in renamed[:5]:
        print("     rename  %s\n          -> %s" % (a, b))

    # IN-PLACE HAS NO ARCHIVE-LEVEL REFUSAL, so the per-file one has to be real. Checked over the
    # whole plan BEFORE a single byte is written: a run that stops halfway leaves a tree that is
    # neither the old one nor the new one, and nothing on disk says which.
    if args.in_place:
        present = [p[1] for p in plan
                   if not p[3] and (os.path.exists(p[1]) or os.path.exists(long_path(p[1])))]
        print("  %d of %d output paths already exist" % (len(present), len(files)))
        for p in present[:5]:
            print("     exists %s" % p)
        if present and not args.dry_run:
            sys.exit("\n  REFUSING: %d files would be overwritten. Nothing written."
                     % len(present))

    if args.dry_run:
        print("\n  Dry run -- nothing written.")
        return 0
    if refused:
        sys.exit("\n  REFUSING TO EXTRACT: %d entries would escape the archive." % len(refused))
    if collide:
        sys.exit("\n  REFUSING TO EXTRACT: %d pairs of entries would land on one path, and the "
                 "second\n  of each pair would silently overwrite the first. Fix the mapping "
                 "first." % len(collide))

    print("\n  extracting to %s ..." % dest, flush=True)
    t0 = time.time()
    n = 0
    # By name, not by scanning the plan per member. ftp.digital.com holds 22 182 entries and
    # h71000 27 372; a linear search inside the loop is 750 million string comparisons for a job
    # whose real cost should be the 36 GB of I/O.
    by_name = {p[0]: p for p in plan}
    for mname, src in open_members(args.tar, kind):
        hit = by_name.get(mname)
        if hit is None:
            continue
        _name, out, size, isdir, mtime = hit
        if isdir:
            os.makedirs(long_path(out), exist_ok=True)
            continue
        os.makedirs(long_path(os.path.dirname(out)), exist_ok=True)
        if src is None:
            continue
        with io.open(long_path(out), "wb") as fh:
            while True:
                b = src.read(8 << 20)
                if not b:
                    break
                fh.write(b)
        os.utime(long_path(out), (mtime, mtime))
        n += 1
        if n % 500 == 0:
            print("     %d/%d  (%.0f s)" % (n, len(files), time.time() - t0), flush=True)
    print("  %d files written in %.0f s" % (n, time.time() - t0))

    # --- verify every file against the size the TAR recorded, not against our own count -------
    print("\n  verifying against the tar's own table of contents ...", flush=True)
    bad, missing = [], []
    for _name, out, size, isdir, _mt in plan:
        if isdir:
            continue
        try:
            got = os.path.getsize(long_path(out))
        except OSError:
            missing.append(out)
            continue
        if got != size:
            bad.append((out, got, size))
    print("  %d files checked, %d wrong size, %d missing" % (len(files), len(bad), len(missing)))
    for o, g, w in bad[:5]:
        print("     SIZE %s: %d, tar says %d" % (o, g, w))
    for o in missing[:5]:
        print("     MISSING %s" % o)

    # A SKIPPED LINK MUST LEAVE A RECORD. Windows cannot create a symlink without privilege, so
    # these entries are not written -- but a symlink IS information: it says two names in the
    # source tree meant one thing. Dropped silently, the tree would claim those names never
    # existed. ftp.digital.com is the case that forced this: twelve links, `pub/Compaq.1`,
    # `pub/digital.6` and the like, ALL pointing at `pub/DEC`, and all stamped six years after the
    # capture -- somebody's later de-duplication, not part of the original FTP server. Without this
    # file that fact is unrecoverable from the extracted tree.
    if skipped:
        with io.open(os.path.join(dest, "SYMLINKS.txt"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# Entries in the tar that Windows cannot create, and what they pointed at.\n")
            fh.write("# NOT an error and NOT missing data: each target is elsewhere in this tree.\n")
            fh.write("# Source: %s\n\n" % os.path.basename(args.tar))
            for name, why, target in skipped:
                fh.write("%-60s %-10s %s\n" % (name, why, target or ""))
        print("  %d skipped entries recorded in SYMLINKS.txt" % len(skipped))

    if renamed:
        with io.open(os.path.join(dest, "RENAMED.txt"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# Names changed because NTFS cannot hold them. Original -> on disk.\n")
            fh.write("# Source: %s\n\n" % os.path.basename(args.tar))
            for a, b in renamed:
                fh.write("%s\n  -> %s\n" % (a, b))
        print("  %d renames recorded in RENAMED.txt" % len(renamed))

    if args.only:
        print("\n  Rehearsal finished. The source tar was NOT hashed -- that is 85 GB of reading "
              "for\n  a run that covers a few files, and the hash belongs to the real "
              "extraction.")
        print("  THIS TREE IS PARTIAL BY CONSTRUCTION. No marker was written, so nothing here "
              "claims\n  otherwise -- but delete it before the real run, or the destination check "
              "will refuse.")
        print("  The tar has NOT been touched.")
        return 1 if (bad or missing) else 0

    print("\n  hashing the source tar for the provenance record ...", flush=True)
    digest = sha256_file(args.tar, chunk=8 << 20)
    print("  %s" % digest)
    print("\n  NEXT: write PROVENANCE.md, then mirror.py --index, then verify-content.py.")
    print("  The tar has NOT been touched.")
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
