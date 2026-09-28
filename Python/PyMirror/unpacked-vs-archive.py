#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""May this unpacked copy be deleted? Ask the archive it came from, by content.

THE SITUATION. A working directory fills with trees that were unpacked to look inside them,
each sitting beside the archive it came out of. Later the directory has to be cleared, and the
question for every such tree is the same: is all of this still inside that archive?

THE WRONG WAY TO ANSWER IT, and it is the tempting one: compare FILENAMES. On 2026-09-20 seven
unpacked trees -- two gdb releases and four PmWiki releases, 1 585 files -- were deleted on a
basename match alone. It happened to be right. It is not evidence: a basename match says the
archive contains *a* file of that name, not that it contains *these bytes*. A truncated
extraction, a file edited after unpacking, or two members with the same basename and different
content all pass a name check and all lose data.

So this reads the members OUT of the archive, hashes them, and compares SHA-256. A directory is
covered when every file in it has a member with identical content -- not merely a namesake.

WHAT IT REFUSES TO GUESS. An archive it cannot read is reported as UNREADABLE and the files it
might have covered stay uncovered. The old LZW `.Z` is the common case: Python has no
decompressor for it, and `tarfile` fails with a bare ReadError that looks exactly like a corrupt
file. GNU gzip does read LZW, so it is tried as an external fallback when present -- but if it
is missing the answer is "cannot tell", never "covered". Saying "covered" about an archive one
could not open is how a clean report comes to justify a deletion it never examined.

    python unpacked-vs-archive.py DIR
    python unpacked-vs-archive.py DIR --archives ARCHIVE_DIR
    python unpacked-vs-archive.py DIR --list-uncovered

Exit status is 1 when anything is uncovered or any archive was unreadable, so a deletion can be
gated on it.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import tarfile
import zipfile

from common import long_path, relative_to

TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz")
LZW_SUFFIXES = (".tar.z", ".z")
ZIP_SUFFIXES = (".zip",)


def sha_of_file(path):
    digest = hashlib.sha256()
    with open(long_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_of_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1 << 20), b""):
        digest.update(chunk)
    return digest.hexdigest()


def members_of_tar(fileobj=None, path=None):
    """-> {basename: {sha256, ...}} for a tar this build of Python can open."""
    out = {}
    with (tarfile.open(path) if fileobj is None else tarfile.open(fileobj=fileobj)) as archive:
        for member in archive:
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            out.setdefault(os.path.basename(member.name), set()).add(sha_of_stream(handle))
    return out


def members_of_zip(path):
    out = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as handle:
                out.setdefault(os.path.basename(info.filename), set()).add(sha_of_stream(handle))
    return out


def members_via_gzip(path):
    """-> members of an LZW .Z, through GNU gzip, or None when that is not available.

    Python cannot decompress LZW. gzip can, and it is the difference between answering this
    question for a 1990s archive and not answering it at all -- six of the seven archives in one
    directory on 2026-09-20 were .Z. It stays optional: no gzip means UNREADABLE, not "covered".
    """
    try:
        proc = subprocess.run(["gzip", "-dc", path], capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    import io
    try:
        return members_of_tar(fileobj=io.BytesIO(proc.stdout))
    except (tarfile.TarError, EOFError):
        return None


def read_archive(path):
    """-> ({basename: {sha256}}, None) or (None, reason)."""
    low = path.lower()
    try:
        if low.endswith(ZIP_SUFFIXES):
            return members_of_zip(path), None
        if low.endswith(TAR_SUFFIXES):
            return members_of_tar(path=path), None
        if low.endswith(LZW_SUFFIXES):
            got = members_via_gzip(path)
            if got is None:
                return None, "LZW .Z and GNU gzip did not read it"
            return got, None
    except (tarfile.TarError, zipfile.BadZipFile, EOFError, OSError) as exc:
        return None, exc.__class__.__name__
    return None, "not an archive this tool reads"


def collect_archives(directory):
    found = {}
    unreadable = {}
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        if not low.endswith(ZIP_SUFFIXES + TAR_SUFFIXES + LZW_SUFFIXES):
            continue
        members, why = read_archive(path)
        if members is None:
            unreadable[name] = why
        else:
            found[name] = members
    return found, unreadable


def main():
    parser = argparse.ArgumentParser(
        description="Is every file in a directory also, by content, inside an archive beside it?")
    parser.add_argument("directory", nargs="?",
                        help="the directory holding the unpacked copies")
    parser.add_argument("--archives", metavar="DIR",
                        help="where the archives are, if not in DIRECTORY itself")
    parser.add_argument("--list-uncovered", action="store_true",
                        help="print every uncovered file, not just the first few")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    if not args.directory:
        parser.print_help()
        return 0
    if not os.path.isdir(args.directory):
        print("not a directory: %s" % args.directory)
        return 2

    archive_dir = args.archives or args.directory
    archives, unreadable = collect_archives(archive_dir)

    pool = set()
    for members in archives.values():
        for digests in members.values():
            pool |= digests

    print("Archives in %s: %d readable, %d unreadable" % (archive_dir, len(archives),
                                                          len(unreadable)))
    for name, members in archives.items():
        print("   %-34s %5d members" % (name[:34], sum(len(v) for v in members.values())))
    for name, why in unreadable.items():
        print("   %-34s UNREADABLE -- %s" % (name[:34], why))
    if unreadable:
        print("   An unreadable archive covers nothing here. Its files stay uncovered.")
    print()

    # The loose files beside the archives count too. An extraction does not always land in a
    # subdirectory of its own -- `tar xf` in place leaves Makefile and the config files right
    # next to the tar, and checking only subdirectories would report that directory as clean
    # while saying nothing about most of what is in it.
    groups = []
    loose = [os.path.join(args.directory, n) for n in sorted(os.listdir(args.directory))
             if os.path.isfile(os.path.join(args.directory, n)) and n not in archives
             and n not in unreadable]
    if loose:
        groups.append(("(loose files beside the archives)", loose))
    for entry in sorted(os.listdir(args.directory)):
        sub = os.path.join(args.directory, entry)
        if os.path.isdir(sub):
            found = []
            for root, _dirs, names in os.walk(sub):
                for name in names:
                    found.append(os.path.join(root, name))
            groups.append((entry, found))

    total = uncovered_total = 0
    uncovered_all = []
    for entry, files in groups:
        uncovered = []
        for path in files:
            try:
                if sha_of_file(path) not in pool:
                    uncovered.append(path)
            except OSError as exc:
                uncovered.append("%s (%s)" % (path, exc.__class__.__name__))
        total += len(files)
        uncovered_total += len(uncovered)
        uncovered_all.extend(uncovered)
        verdict = "covered" if not uncovered else "%d NOT covered" % len(uncovered)
        print("   %-30s %5d files   %s" % (entry[:30], len(files), verdict))
        if uncovered and not args.list_uncovered:
            for path in uncovered[:4]:
                print("        %s" % relative_to(args.directory, path))
            if len(uncovered) > 4:
                print("        ... %d more" % (len(uncovered) - 4))

    if args.list_uncovered and uncovered_all:
        print("\n   every uncovered file:")
        for path in uncovered_all:
            print("      %s" % relative_to(args.directory, path))

    print("\n   %d files, %d not covered by content" % (total, uncovered_total))
    if uncovered_total == 0 and not unreadable and total:
        print("   Every file here is inside an archive beside it, byte for byte.")
    return 1 if (uncovered_total or unreadable) else 0


if __name__ == "__main__":
    sys.exit(main())
