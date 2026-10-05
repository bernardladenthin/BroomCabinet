# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Put two directories that differ only in case into one, as Windows would have.

    python merge-case-dirs.py                     what WOULD move, nothing touched
    python merge-case-dirs.py --archive ibm-aix
    python merge-case-dirs.py --out plan.txt      write the plan and read it
    python merge-case-dirs.py --apply --backup D  do it, after the plan has been read

WHY. Rar.exe cannot store two paths differing only in upper/lower case: it keeps ONE, says
nothing, and exits 0 -- measured on 2026-10-05 with a 14-byte and a 22-byte file through a
directory argument, -r, an @list, -oni and both names explicitly. 7-Zip 24.09 refuses outright
("Duplicate filename on disk"). Extracting such a pair onto an ordinary Windows folder is worse
still: one file arrives, under the wrong name, with the wrong content, and RAR reports "Alles OK".

SO THE COLLECTION HAS TO BECOME SOMETHING WINDOWS CAN HOLD. The owner's framing on 2026-10-05:
the sources will have changed or be gone in five years -- that is why they were mirrored -- the
scripts here are not run daily, and the job now is to get the bytes into cold storage in a form
that opens anywhere. Where two directories differ only in case, their contents go into one
directory "as if it had arrived that way from the mirror".

THE RULE IS UNIFORM AND THAT IS THE OWNER'S CHOICE: the FIRST name in sorted order keeps its
name, every other member's contents move into it. Sorted, so a second run cannot pick a different
winner, and uniform, so nobody has to remember which archive got which treatment. The cost is that
it sometimes moves the many into the few -- ardent-tool's `PS55/docs` has 157 files and `PS55/Docs`
has 1, and `Docs` wins because `D` sorts before `d`.

IT ONLY TOUCHES GROUPS WITH NOTHING TO DECIDE. A group is merged only when no two files would
collide on a name after the move. Measured on 2026-10-05: 17 of 34 groups qualify, 14 of them as
top-level operations -- the other 3 are nested inside one of those and come along. The 17 that do
NOT qualify are blocked almost entirely by one auxiliary file, `TRANS.TBL`, an ISO-9660 table
describing the very directory it sits in, plus ibm-aix's `fixes/V4` against `fixes/v4` where 1 887
names clash. Those are a separate decision and this tool refuses them.

TWO FILES WITH THE SAME NAME AND THE SAME BYTES ARE NOT A CLASH. funet-aix's `RS6000` and
`rs6000` hold the same 20 files with the same digests; one copy survives the merge and the other
is dropped, which loses nothing and is recorded as such.

WHAT IT WRITES, in this order, per archive:

  1. a copy of the archive's index and manifests into --backup, verified by SHA-256
  2. the record, BEFORE the first move, so an interrupted run is still documented
  3. the files, one at a time, by os.replace within the same volume -- never a copy, so there is
     no moment where two copies could disagree, and the digest is checked afterwards anyway
  4. the emptied directories, innermost first, only where os.listdir says they are empty
  5. the index and four manifests, rewritten through common.write_index and
     common.write_manifests. NOTHING IS RE-HASHED: a moved file keeps every digest it had.

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

RECORD_FILE = "CASE-DIRS-MERGED.txt"

RECORD_HEADER = """# Directories merged %s because their names differed only in upper/lower
# case, which Windows cannot hold and WinRAR silently halves: given two such
# paths, rar stores one of them, says nothing about the other and exits 0.
#
# The contents were moved into the FIRST name in sorted order. Nothing was
# renamed and nothing was lost: every file kept its own name and its own
# digests, and a name that appeared on both sides with identical bytes kept one
# copy. The index and all four manifests were rewritten from the recorded
# digests, not by re-hashing.
#
# moved from  ->  into
"""


def groups_in(root, archive, index=None):
    r"""-> [(target, [other members], files_to_move, clashing names)] per colliding directory.

    NESTED GROUPS ARE LEFT TO THEIR PARENT. `aixpdslib/pub/URT` and `pub/URT/RISC` both collide;
    merging the first moves the second along with it, and acting on both would move the same files
    twice. So a group whose target sits under another group's target is dropped from the result.
    """
    idx = index if index is not None else read_index(os.path.join(root, archive, INDEX_FILE))
    paths = dict((rel.replace("\\", "/"), got) for rel, got in idx.items())
    folded = collections.defaultdict(set)
    for rel in paths:
        parts = rel.split("/")
        for cut in range(1, len(parts)):
            folded["/".join(x.lower() for x in parts[:cut])].add("/".join(parts[:cut]))
    found = []
    for key in sorted(folded):
        members = sorted(folded[key])
        if len(members) < 2:
            continue
        target, others = members[0], members[1:]
        # what each name under the group looks like, from every member
        tails = collections.defaultdict(list)
        for member in members:
            for rel, got in paths.items():
                if rel.startswith(member + "/"):
                    tails[rel[len(member) + 1:].lower()].append((member, rel, got[2]))
        # A CLASH IS BETWEEN MEMBERS, NEVER INSIDE ONE. The first version flagged any tail whose
        # rows disagreed, including two files sitting in the SAME member whose names differ only in
        # case -- and those already coexist, so moving them keeps each one's name and changes
        # nothing about them. It made the tool report 1 887 clashes for ibm-aix's fixes/V4 against
        # fixes/v4, where V4 held four files all under ml/ and the 1 887 names like
        # cics/cics.msg.ja_jp... were inside v4 itself. The group was refused for a reason that
        # had nothing to do with merging it, and the owner moved it by hand instead.
        #
        # WHAT IS A CLASH: two members contributing the same tail with different bytes. After the
        # move those two land in one directory under case-equal paths, which is exactly what rar
        # halves. Same tail and same bytes is the duplicate case -- one copy survives.
        clash = []
        for tail, rows in tails.items():
            by_member = {}
            for member, _rel, digest in rows:
                by_member.setdefault(member, set()).add(digest)
            if len(by_member) < 2:
                continue
            if len(set(d for digests in by_member.values() for d in digests)) > 1:
                clash.append(tail)
        clash = sorted(clash)
        moves = []
        for member in others:
            for rel in sorted(paths):
                if rel.startswith(member + "/"):
                    moves.append((rel, target + "/" + rel[len(member) + 1:]))
        found.append((target, others, moves, clash))
    tops = []
    for target, others, moves, clash in found:
        if any(target != t and target.startswith(t + "/") for t, _o, _m, _c in found):
            continue
        tops.append((target, others, moves, clash))
    return tops


def mergeable(root, archive, index=None):
    """-> only the groups with nothing to decide."""
    return [g for g in groups_in(root, archive, index) if not g[3]]


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


def write_record(root, archive, groups):
    """Append the record BEFORE anything moves."""
    path = os.path.join(root, archive, RECORD_FILE)
    new = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write(RECORD_HEADER % time.strftime("%Y-%m-%d"))
        fh.write("\n")
        for target, others, moves, _clash in groups:
            for other in others:
                fh.write("%s\n  -> %s   (%d file(s))\n" % (other, target, len(moves)))
    return path


def prune_empty_dirs(root, archive, rel, report=say):
    """Remove directories that are now empty, innermost first. -> how many went."""
    gone = 0
    parts = rel.split("/")
    while parts:
        here = os.path.join(root, archive, *parts)
        try:
            if not os.path.isdir(long_path(here)) or os.listdir(long_path(here)):
                break
            os.rmdir(long_path(here))
        except OSError as problem:
            report("     could not remove %s: %s" % ("/".join(parts), problem))
            break
        gone += 1
        parts = parts[:-1]
    return gone


def remap(root, archive, moved, dropped, report=say):
    r"""Rewrite the index and the four manifests for `moved` and without `dropped`. -> True/False.

    THROUGH THE LIBRARY'S OWN WRITERS and never by editing the files as text. There are four
    formats and one of them, `.sfv`, puts the columns the other way round from sha256sum(1) -- a
    hazard this library documents in `sfv_line`. `write_index` derives `.sha256sum` from the CSV so
    the two cannot disagree.

    NOTHING IS RE-HASHED. A file that moved within one volume has the bytes it had, so its digests
    are carried across unchanged. Re-indexing instead would read every moved byte to learn what was
    already recorded.
    """
    index_path = os.path.join(root, archive, INDEX_FILE)
    rows = read_index(index_path)
    digests = read_manifests(os.path.join(root, archive))
    out_rows, out_digests = {}, {}
    for rel, got in rows.items():
        flat = rel.replace("\\", "/")
        if flat in dropped:
            continue
        where = moved.get(flat, flat)
        if where in out_rows:
            report("     %s would land on an existing row -- STOPPING" % where)
            return False
        out_rows[where] = got
        if flat in digests:
            out_digests[where] = digests[flat]
    write_index(index_path, os.path.join(root, archive, SUMS_FILE), out_rows)
    write_manifests(os.path.join(root, archive), out_digests)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append", default=[], help="only this one; repeatable")
    ap.add_argument("--out", metavar="PATH", help="write the full plan here")
    ap.add_argument("--backup", metavar="DIR",
                    help="where the index and manifests are copied before any change. Required "
                         "with --apply")
    ap.add_argument("--apply", action="store_true",
                    help="actually move. Without it NOTHING is written")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        say("not a directory: %s" % args.root)
        return 2
    names = args.archive or sorted(
        n for n in os.listdir(args.root)
        if os.path.isfile(os.path.join(args.root, n, INDEX_FILE)))

    work, lines, refused = [], [], 0
    for archive in names:
        every = groups_in(args.root, archive)
        good = [g for g in every if not g[3]]
        refused += len(every) - len(good)
        if not good:
            continue
        work.append((archive, good))
        for target, others, moves, _clash in good:
            say("  %-24s %-44s <- %s  (%d file(s))"
                % (archive, target[-42:], ", ".join(o.split("/")[-1] for o in others), len(moves)))
            for old, new in moves:
                lines.append("%s\t%s\t%s" % (archive, old, new))

    total = sum(len(m) for _a, good in work for _t, _o, m, _c in good)
    say("")
    say("%d merge(s) across %d archive(s), %d file(s) to move; %d group(s) refused for a real "
        "name clash" % (sum(len(good) for _a, good in work), len(work), total, refused))
    if args.out:
        folder = os.path.dirname(os.path.abspath(args.out))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("archive\told\tnew\n")
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        say("plan written: %s" % args.out)

    if not args.apply:
        say("")
        say("NOTHING WAS MOVED. Read the plan, then pass --apply with --backup.")
        return 0
    if not args.backup:
        say("REFUSING: --apply needs --backup.")
        return 2

    done = 0
    for archive, good in work:
        say("  %s" % archive)
        if not save_bookkeeping(args.root, archive, args.backup):
            return 2
        say("     bookkeeping copied")
        say("     record: %s" % write_record(args.root, archive, good))
        moved, dropped, emptied = {}, set(), []
        for target, others, moves, _clash in good:
            for old, new in moves:
                source = os.path.join(args.root, archive, *old.split("/"))
                dest = os.path.join(args.root, archive, *new.split("/"))
                if not exists(source):
                    say("     already gone: %s" % old)
                    continue
                if exists(dest):
                    # SAME NAME, SAME BYTES -- funet-aix's RS6000 and rs6000 hold the same 20
                    # files. One copy survives and the other is dropped, which loses nothing.
                    if sha256_file(source) != sha256_file(dest):
                        say("     %s and %s differ -- STOPPING" % (old, new))
                        return 2
                    os.remove(long_path(source))
                    dropped.add(old)
                    emptied.append(old)
                    continue
                parent = os.path.dirname(dest)
                if parent and not os.path.isdir(long_path(parent)):
                    os.makedirs(long_path(parent))
                was = sha256_file(source)
                os.replace(long_path(source), long_path(dest))
                if sha256_file(dest) != was:
                    say("     the digest of %s changed in the move -- STOPPING" % new)
                    return 2
                moved[old] = new
                emptied.append(old)
                done += 1
        for old in emptied:
            prune_empty_dirs(args.root, archive, os.path.dirname(old))
        if not remap(args.root, archive, moved, dropped):
            return 2
        say("     %d moved, %d duplicate(s) dropped, index and four manifests rewritten"
            % (len(moved), len(dropped)))
        # BOTH STEPS AND IN THIS ORDER. The record written above is a new file: it is on
        # disk, the marker counts it, and the index this tool just rewrote does not know it.
        # Restating before indexing leaves the marker wrong again.
        say("     NEXT: mirror.py --archive %s --index" % archive)
        say("     THEN: restate-marker.py --archive %s --apply --reason ..." % archive)
    say("")
    say("%d file(s) moved. Nothing was re-hashed: a moved file keeps every digest it had."
        % done)
    say("Run --index on every archive above BEFORE restate-marker.py, or each manifest will be "
        "one file short -- the record this tool wrote is not in the index it rewrote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
