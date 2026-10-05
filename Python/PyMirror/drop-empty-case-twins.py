# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Remove a 0-byte file that is only the other casing of a file holding the content.

    python drop-empty-case-twins.py                 what WOULD go, nothing touched
    python drop-empty-case-twins.py --archive ibm-aix
    python drop-empty-case-twins.py --out plan.txt  write the plan and read it
    python drop-empty-case-twins.py --apply         do it, after the plan has been read

WHAT THESE FILES ARE. A case-insensitive web or FTP server answers `.../iz42658.epkg.Z` and
`.../IZ42658.epkg.Z` as the same resource. This crawler followed both links, and one of the two
arrived EMPTY while the other brought the 348 631 bytes. Measured on 2026-10-05: 56 such files
across three archives, 0 bytes in total, and the direction is not fixed -- sometimes the
upper-case name is the empty one (`terminfo/A/TRANS.TBL` against `terminfo/a/TRANS.TBL`,
10 810 bytes), sometimes the lower-case one (`iz42658.epkg.Z` against `IZ42658.epkg.Z`). So the
test is EMPTINESS and never the casing.

WHY THEY MATTER AT ALL, since zero bytes cost nothing to store: Rar.exe cannot hold two paths
differing only in case. It keeps ONE of the pair, says nothing, and exits 0 -- measured with a
14-byte and a 22-byte file, through a directory argument, -r, an @list, -oni and both names
explicitly. Which one it keeps is not predictable, so for 56 pairs RAR might keep the EMPTY member
and the content would not reach cold storage. Removing the empty twin resolves the pair with
nothing lost.

IT IS 56 OF 3 973 COLLISION GROUPS. The remaining 3 700 hold genuinely different content -- two
valid JPEGs of 320x116 and 333x165, two working ELF binaries with different entry points -- and
this tool does not touch them. They are a separate decision.

WHAT IT CHECKS BEFORE REMOVING ANYTHING:

  THE FILE IS REALLY EMPTY ON DISK, read now and not taken from the index. An index can be stale;
  that is how this whole investigation started.

  THE PARTNER REALLY EXISTS AND IS REALLY NOT EMPTY, also read from disk. A pair where both are
  empty is left alone -- those two are byte-identical and RAR keeping either loses nothing.

  THE TWO DIFFER ONLY IN CASE. Belt and braces: the lower-cased paths must be equal and the paths
  themselves must not be.

WHAT IT WRITES, in this order, per archive:

  1. a copy of the archive's index and four manifests into --backup, verified by SHA-256
  2. the removal record, BEFORE the first deletion, so an interrupted run is still documented
  3. the files, deleted one at a time
  4. any directory that is now empty, innermost first -- a directory that held nothing but an
     empty twin is an artefact of the same wrong link
  5. the index and the four manifests, rewritten through common.write_index and
     common.write_manifests -- the readers' own counterparts, so no format is parsed or spelled
     out here. NOTHING IS RE-HASHED: removing a path does not change any other file's digest.

THE RECORD FOLLOWS FRAGMENT-COPIES-REMOVED.txt, which this collection already carries in four
archives for the same shape of mistake -- a file fetched twice under two spellings of one URL. One
convention, not two.

AFTERWARDS, IN THIS ORDER, AND THE ORDER IS NOT COSMETIC. The record this tool writes is a NEW
file in the archive, and it lands after the index was rewritten -- so it is on disk, counted by
the marker, and absent from the index and all four manifests. Measured on 2026-10-05: doing it the
other way round made all six archives report "crc32 covers 25820 of 25821 ... --index-force once
completes them", one file short in every manifest, for a tree that was correct.

    mirror.py --archive <name> --index          picks up the record, one file to hash
    restate-marker.py --archive <name> --apply  brings files and bytes into line

Restating first and indexing second leaves the marker wrong again, because indexing adds a file
the marker has already been told about.
"""
import argparse
import collections
import io
import os
import shutil
import sys
import time

from common import (BOOKKEEPING_FILES, INDEX_FILE, MIRROR_ROOT, SUMS_FILE, exists, long_path,
                    read_index, read_manifests, say, sha256_file, write_index, write_manifests)

RECORD_FILE = "EMPTY-CASE-TWINS-REMOVED.txt"

# THE SECOND MODE'S RECORD, kept apart from the first because the REASON differs and a reader a
# year from now has to be able to tell which claim was made. "It was empty" and "its bytes are
# still here under the other name" are not the same statement, and only the second is provable
# from a digest. The tool's name predates this mode; it covers both shapes of one problem.
SAME_RECORD_FILE = "IDENTICAL-CASE-TWINS-REMOVED.txt"

SAME_RECORD_HEADER = """# Files removed %s because the file beside them, under another casing of
# the same name, holds BYTE-FOR-BYTE THE SAME CONTENT. Both digests were read
# from disk at the moment of deletion, not taken from the index, and they were
# equal -- that equality is the whole justification.
#
# A case-insensitive server answers two spellings of one URL as one resource,
# and this crawler followed both, so the same bytes arrived twice. Rar.exe
# cannot store two paths differing only in case: it keeps one and does not say
# which, and the CRC32 of the one it dropped then no longer matches what our
# manifests record for that path. Measured on misc.rar: 275 such paths, 165
# with a CRC32 that disagreed, and `rar t` reported "Alles OK" over all of it.
#
# NOTHING BELOW WAS LOST. The left-hand name is gone; every byte it held is in
# the file named on the right, and the sha256 printed with it is the proof. The
# kept spelling is the one that sorts first, which is merge-case-dirs.py's rule
# -- with identical content there is nothing to choose between them, so the
# choice is made to be predictable rather than clever.
#
# removed  ->  the file that holds the same bytes
"""

RECORD_HEADER = """# Files removed %s because they were 0 bytes and the file beside them, under
# the other casing of the same name, holds the content. Emptiness was read from
# disk at the moment of deletion, not taken from the index.
#
# A case-insensitive server answers two spellings of one URL as one resource.
# This crawler followed both, and one of the two arrived empty. Rar.exe cannot
# store two paths differing only in case -- it keeps one without saying which --
# so an empty twin could have displaced the content on its way to cold storage.
# Nothing below was lost: the left-hand name is gone and held nothing, the bytes
# are in the file named on the right.
#
# removed (0 bytes)  ->  the file that holds the content
"""


def disk_size(path):
    """-> the size on disk, or None if it is not there. The production answer for `size_of`."""
    if not exists(path):
        return None
    return os.path.getsize(long_path(path))


def disk_digest(path):
    """-> sha256 of the file on disk, or None if it is not there. Production `digest_of`."""
    if not exists(path):
        return None
    return sha256_file(path)


def identical_twins_in(root, archive, digest_of=disk_digest):
    r"""-> [(drop_rel, keeper_rel, size)] where two spellings hold THE SAME BYTES.

    THE SECOND SHAPE OF ONE PROBLEM, and the safer of the two. The empty-twin case drops a 0-byte
    file whose partner has content, which loses an empty file. This one drops a file whose partner
    is byte-for-byte identical, which loses NOTHING AT ALL -- the bytes remain, under the other
    spelling, and their digest is the proof. Measured across the collection on 2026-10-05: 420
    extra members outside the three tars, and 168 of them are this case.

    THE DIGESTS COME FROM DISK, NOT FROM THE INDEX, for the reason the empty-twin function gives:
    an index can be stale, and on 2026-10-05 the CRC32 cross-check found two manifests describing
    a file that had been rewritten since they were built. The index only narrows the search.

    THE KEEPER IS THE SORTED-FIRST SPELLING, which is `merge-case-dirs.py`'s rule for exactly the
    same reason: with identical content there is nothing to choose between them, so the choice has
    to be one a later reader can predict and a second run would repeat. `Filink.zip` is kept and
    `filink.zip` dropped, because uppercase sorts first -- not because either is more correct.

    `digest_of` IS INJECTABLE for the same reason `size_of` is: `A.TBL` and `a.TBL` cannot both
    exist in an ordinary Windows directory, so a fixture that wrote both would end up with one
    file and this function would never see the condition it looks for.
    """
    folded = collections.defaultdict(list)
    for rel in read_index(os.path.join(root, archive, INDEX_FILE)):
        folded[rel.replace("\\", "/").lower()].append(rel.replace("\\", "/"))
    out = []
    for key in sorted(folded):
        group = sorted(folded[key])
        if len(group) < 2:
            continue
        seen = {}
        for rel in group:
            full = os.path.join(root, archive, *rel.split("/"))
            digest = digest_of(full)
            if digest is None:
                seen = {}
                break
            seen.setdefault(digest, []).append(rel)
        if not seen:
            continue
        for digest in sorted(seen):
            same = sorted(seen[digest])
            if len(same) < 2:
                continue                      # a lone spelling of these bytes: nothing to drop
            keeper = same[0]
            size = disk_size(os.path.join(root, archive, *keeper.split("/")))
            for rel in same[1:]:
                out.append((rel, keeper, size if size is not None else 0))
    return out


def twins_in(root, archive, size_of=disk_size):
    r"""-> [(empty_rel, keeper_rel, keeper_size)] for one archive, sizes read from DISK.

    THE INDEX ONLY NARROWS THE SEARCH. Every size that decides anything comes from the filesystem,
    because an index can be stale -- which is what the CRC32 cross-check found on 2026-10-05, two
    manifests describing a file that had been rewritten since they were built.

    `size_of` IS INJECTABLE AND THAT IS NOT A CONVENIENCE. The condition this function looks for
    CANNOT BE BUILT IN AN ORDINARY WINDOWS DIRECTORY: `A.TBL` and `a.TBL` resolve to one file
    there, so a fixture writing both ends up with one, and `getsize` returns the same number twice.
    The real collection holds them only because those directories carry the per-directory
    case-sensitivity flag. A test would otherwise have to run `fsutil file setCaseSensitiveInfo`
    and would then test Windows rather than this function.
    """
    folded = collections.defaultdict(list)
    for rel in read_index(os.path.join(root, archive, INDEX_FILE)):
        folded[rel.replace("\\", "/").lower()].append(rel.replace("\\", "/"))
    out = []
    for key in sorted(folded):
        group = sorted(folded[key])
        if len(group) < 2:
            continue
        sized = []
        for rel in group:
            size = size_of(os.path.join(root, archive, *rel.split("/")))
            if size is None:
                sized = []
                break
            sized.append((rel, size))
        if not sized:
            continue
        empty = [rel for rel, size in sized if size == 0]
        filled = [(rel, size) for rel, size in sized if size > 0]
        if not empty or not filled:
            continue
        keeper, keeper_size = max(filled, key=lambda pair: pair[1])
        for rel in empty:
            out.append((rel, keeper, keeper_size))
    return out


def save_bookkeeping(root, archive, backup, report=say):
    """Copy the archive's index and manifests into `backup`, verified. -> True, or False."""
    where = os.path.join(backup, archive)
    if not os.path.isdir(where):
        os.makedirs(where)
    for name in sorted(BOOKKEEPING_FILES):
        if name.endswith(".tmp"):
            continue
        source = os.path.join(root, archive, name)
        if not exists(source):
            continue
        target = os.path.join(where, name)
        shutil.copy2(long_path(source), long_path(target))
        if sha256_file(source) != sha256_file(target):
            report("     the copy of %s does not match -- STOPPING" % name)
            return False
    return True


def write_record(root, archive, pairs, same_content=False, digests=None):
    """Append the removal record BEFORE anything is deleted."""
    name = SAME_RECORD_FILE if same_content else RECORD_FILE
    header = SAME_RECORD_HEADER if same_content else RECORD_HEADER
    path = os.path.join(root, archive, name)
    new = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write(header % time.strftime("%Y-%m-%d"))
        fh.write("\n")
        for dropped, keeper, size in pairs:
            fh.write("%s\n  -> %s   (%d bytes)\n" % (dropped, keeper, size))
            # THE DIGEST IS THE CLAIM, so it is written down beside the pair it justifies. A
            # record saying "these were identical" without the number is an assertion; with it,
            # a later reader can check the surviving file and see for himself.
            if same_content and digests and dropped in digests:
                fh.write("     sha256 %s\n" % digests[dropped])
    return path


def prune_empty_dirs(root, archive, rel, report=say):
    """Remove directories that are now empty, innermost first. -> how many went."""
    gone = 0
    parts = rel.split("/")[:-1]
    while parts:
        here = os.path.join(root, archive, *parts)
        try:
            if os.listdir(long_path(here)):
                break
            os.rmdir(long_path(here))
        except OSError as problem:
            report("     could not remove %s: %s" % ("/".join(parts), problem))
            break
        gone += 1
        parts = parts[:-1]
    return gone


def forget(root, archive, removed, report=say):
    r"""Drop `removed` from the index and the four manifests. -> True, or False.

    THROUGH THE LIBRARY'S OWN WRITERS and never by editing the files as text. There are four
    formats here and one of them, `.sfv`, puts the columns the other way round from sha256sum(1) --
    a hazard this library documents in `sfv_line`. `write_index` derives `.sha256sum` from the CSV
    so the two cannot disagree, and `write_manifests` writes the other three from one mapping.

    NOTHING IS RE-HASHED. Removing a path changes no other file's digest, so the digests already
    recorded are carried straight across. Re-indexing would have read 56.7 GB to learn what is
    already known.
    """
    gone = set(removed)
    index_path = os.path.join(root, archive, INDEX_FILE)
    rows = read_index(index_path)
    kept = dict((rel, got) for rel, got in rows.items() if rel.replace("\\", "/") not in gone)
    if len(rows) - len(kept) != len(gone):
        report("     the index lost %d entr(ies) and %d were named -- STOPPING"
               % (len(rows) - len(kept), len(gone)))
        return False
    write_index(index_path, os.path.join(root, archive, SUMS_FILE), kept)
    digests = read_manifests(os.path.join(root, archive))
    write_manifests(os.path.join(root, archive),
                    dict((rel, got) for rel, got in digests.items()
                         if rel.replace("\\", "/") not in gone))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append", default=[], help="only this one; repeatable")
    ap.add_argument("--out", metavar="PATH", help="write the full plan here")
    ap.add_argument("--backup", metavar="DIR",
                    help="where the index and manifests are copied before any change. Required "
                         "with --apply: these five files per archive are the only record of what "
                         "the tree looked like, and they are rewritten by this tool")
    ap.add_argument("--same-content", action="store_true",
                    help="the OTHER shape: drop a twin whose partner holds byte-for-byte the "
                         "same content, proved by reading both digests from disk. Loses nothing "
                         "at all, which the empty-twin default cannot claim")
    ap.add_argument("--apply", action="store_true",
                    help="actually remove. Without it NOTHING is written")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        say("not a directory: %s" % args.root)
        return 2
    names = args.archive or sorted(
        n for n in os.listdir(args.root)
        if os.path.isfile(os.path.join(args.root, n, INDEX_FILE)))

    kind = "identical twin" if args.same_content else "empty twin"
    found = []
    lines = []
    for archive in names:
        pairs = (identical_twins_in(args.root, archive) if args.same_content
                 else twins_in(args.root, archive))
        if not pairs:
            continue
        found.append((archive, pairs))
        say("  %-26s %3d %s(s)" % (archive, len(pairs), kind))
        for dropped, keeper, size in pairs:
            lines.append("%s\t%s\t%s\t%d" % (archive, dropped, keeper, size))

    total = sum(len(pairs) for _name, pairs in found)
    twice = sum(size for _name, pairs in found for _d, _k, size in pairs)
    say("")
    say("%d %s(s) across %d archive(s), %s"
        % (total, kind, len(found),
           "%d bytes that exist twice" % twice if args.same_content else "0 bytes"))
    if args.out:
        folder = os.path.dirname(os.path.abspath(args.out))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            # THE COLUMN IS NAMED FOR WHAT IT HOLDS. "empty" over a file that holds 20829 bytes
            # is a plan that reads as a different claim than the one being made.
            fh.write("archive\t%s\tkeeper\tkeeper_size\n"
                     % ("dropped" if args.same_content else "empty"))
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        say("plan written: %s" % args.out)

    if not args.apply:
        say("")
        say("NOTHING WAS REMOVED. Read the plan, then pass --apply with --backup.")
        return 0
    if not args.backup:
        say("REFUSING: --apply needs --backup.")
        return 2

    done = 0
    for archive, pairs in found:
        say("  %s" % archive)
        if not save_bookkeeping(args.root, archive, args.backup):
            return 2
        say("     bookkeeping copied to %s" % os.path.join(args.backup, archive))
        # THE DIGESTS ARE RE-READ HERE, not reused from the planning pass, and they go into the
        # record before anything is removed. The plan may be minutes or hours old; the only
        # digest that justifies a deletion is the one the file has at the moment it happens.
        fresh = {}
        if args.same_content:
            for dropped, keeper, _size in pairs:
                for rel in (dropped, keeper):
                    full = os.path.join(args.root, archive, *rel.split("/"))
                    fresh[rel] = disk_digest(full)
        say("     record: %s" % write_record(args.root, archive, pairs,
                                             same_content=args.same_content, digests=fresh))
        removed = []
        for dropped, keeper, _size in pairs:
            full = os.path.join(args.root, archive, *dropped.split("/"))
            keeper_full = os.path.join(args.root, archive, *keeper.split("/"))
            if not exists(full):
                say("     already gone: %s" % dropped)
                continue
            if args.same_content:
                # THE WHOLE JUSTIFICATION, CHECKED AGAIN AT THE LAST MOMENT. If the two are not
                # still byte-identical, this deletion would lose something, and the right answer
                # is to stop rather than to leave one file of a pair deleted and wonder later.
                if fresh.get(dropped) is None or fresh.get(keeper) is None:
                    say("     one of the pair is gone -- STOPPING at %s" % dropped)
                    return 2
                if fresh[dropped] != fresh[keeper]:
                    say("     NOT IDENTICAL ANY MORE -- STOPPING at %s" % dropped)
                    say("       %s  %s" % (fresh[dropped][:16], dropped))
                    say("       %s  %s" % (fresh[keeper][:16], keeper))
                    return 2
            else:
                if os.path.getsize(long_path(full)) != 0:
                    say("     NOT EMPTY ANY MORE, left alone: %s" % dropped)
                    continue
                if not exists(keeper_full) or os.path.getsize(long_path(keeper_full)) == 0:
                    say("     the keeper %s is gone or empty -- STOPPING" % keeper)
                    return 2
            os.remove(long_path(full))
            removed.append(dropped)
            done += 1
            pruned = prune_empty_dirs(args.root, archive, dropped)
            if pruned:
                say("     %s -- and %d empty director(ies) above it" % (dropped, pruned))
        if removed and not forget(args.root, archive, removed):
            return 2
        say("     %d removed, index and four manifests rewritten" % len(removed))
        # BOTH STEPS AND IN THIS ORDER -- see the module docstring. The record written above is a
        # new file the rewritten index does not know about.
        say("     NEXT: mirror.py --archive %s --index" % archive)
        say("     THEN: restate-marker.py --archive %s --apply --reason ..." % archive)
    say("")
    say("%d file(s) removed. Nothing was re-hashed: a removed path changes no other digest."
        % done)
    say("Run --index on every archive above BEFORE restate-marker.py, or each manifest will be "
        "one file short -- the record this tool wrote is not in the index it rewrote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
