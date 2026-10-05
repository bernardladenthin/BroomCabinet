# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Give one of two files whose names differ only in case a name Windows can hold.

    python rename-case-files.py --archive ndwiki-norsk-data          what WOULD happen
    python rename-case-files.py --archive ndwiki-norsk-data --out plan.tsv
    python rename-case-files.py --archive ndwiki-norsk-data --backup DIR --apply

THE LAST SHAPE OF THE CASE PROBLEM, and the one neither of the other answers fits. A pair holding
the SAME bytes is dropped by `drop-empty-case-twins.py --same-content`, which loses nothing. A
branch where the spelling ENCODES something -- AIX locales, `netstation.msg.AR_AA` against
`Ar_AA` against `ar_AA`, `libC` against `libc` -- goes into a tar, because renaming would destroy
the identifying information. What is left is 163 groups scattered over about 123 directories with
one to three each, where a tar per directory would be absurd and the two files are genuinely
different. Measured 2026-10-06, after six tars and 149 verified removals: 178 collisions left, 15
of them identical, 163 of them this.

SIZE IS NOT A PROOF AND THIS TOOL NEVER TREATS IT AS ONE. Seven groups hold members of exactly
equal size and different content -- `README_IZ28002` against `README_iz28002`, both 244 bytes,
different bytes. A tool that compared sizes to decide "these are the same file" would have
destroyed seven files that look identical from the outside.

THE SECOND SPELLING IN SORTED ORDER GETS A TRAILING `_`, which is `rename-case-dirs.py`'s rule.
With two genuinely different files there is nothing in the content that says which name is more
correct, so the choice is made to be PREDICTABLE: a second run repeats it, and a reader can work
out what happened without this tool. `Wm.n` keeps its name and `wm.n` becomes `wm.n_`. The record
writes both names with their sizes, so the rename can be undone by hand if the other rule turns
out to be wanted.

WHY A TRAILING UNDERSCORE AND NOT ONE BEFORE THE EXTENSION. `wm_.n` is the tidier-looking idea
and it does not survive this collection: THERE IS NO SUCH THING AS "the last extension" here.
`lincks2.2.1db.tgz`, `libc_fix.tar`, `iz73980.epkg.Z`, `TipTop-Supplement-1.5.tar.gz` -- a rule
that inserts before the final dot has to decide whether `.tar.gz` is one extension or two, and
whether `2.2.1` is a version or three of them. It would answer differently for files sitting side
by side in one directory. At the END there is nothing to decide: it sorts next to its partner, it
survives every filesystem this collection will ever sit on, it cannot be mistaken for part of a
real extension, and it is visibly an addition. `wm.n_` reads as "wm.n, adjusted"; `wm_.n` reads as
a different file and `_wm.n` sorts somewhere else entirely.

IT NEVER TOUCHES A PAIR WHOSE MEMBERS HOLD THE SAME BYTES. Those belong to the other tool, which
can drop one and prove nothing was lost; renaming them would preserve a duplicate forever. The
digests are read from disk and a group with one digest is skipped and said out loud.
"""
import argparse
import collections
import io
import os
import shutil
import sys
import time

from common import (INDEX_FILE, MIRROR_ROOT, SUMS_FILE, exists, human,
                    long_path, read_index, read_manifests, say, sha256_file, write_index,
                    write_manifests)

RECORD_FILE = "CASE-FILES-RENAMED.txt"

RECORD_HEADER = """# Files renamed %s because their names differed from another file
# in the same directory ONLY in case, and the two hold DIFFERENT content.
#
# Windows cannot keep both spellings in one directory unless that directory
# carries the per-directory case-sensitivity flag, and Rar.exe stores only ONE
# of two such paths without saying which. Measured on misc.rar: 275 paths
# present only in the other spelling, 165 with a CRC32 that then disagreed with
# our own manifests, and `rar t` reported "Alles OK" over all of it.
#
# NOTHING WAS MERGED AND NOTHING WAS DROPPED. Both files are still here; the one
# on the left now ends in `_`. Its sha256 is unchanged -- a rename does not touch
# a byte -- and the index and all four manifests name the new spelling.
#
# The kept name is the one that sorts FIRST, which is the rule
# CASE-DIRS-RENAMED.txt records for directories. With two genuinely different
# files nothing in the content says which name is the more correct one, so the
# choice is made to be predictable rather than clever.
#
# renamed  ->  its new name   (size, and the partner it collided with)
"""


def spelled_exactly(root, archive, rel):
    r"""-> True when `rel` exists with EXACTLY this spelling.

    NOT `os.path.exists`, WHICH ANSWERS A DIFFERENT QUESTION. On a directory without the
    case-sensitivity flag it resolves `fixes/V4` to `fixes/v4` and reports True for a name that is
    not there -- which is how an earlier measurement of this collection came out right only by
    accident. The parent is listed and the name compared byte for byte.
    """
    full = os.path.join(root, archive, *rel.split("/"))
    parent = os.path.dirname(full)
    name = os.path.basename(full)
    try:
        return name in os.listdir(long_path(parent))
    except OSError:
        return False


def disk_digest(path):
    """-> sha256 from disk, or None when it is not there."""
    if not exists(path):
        return None
    return sha256_file(path)


def candidates(root, archive, digest_of=disk_digest, report=say, under=()):
    r"""-> [(old_rel, new_rel, size, partner_rel)] for every group that needs a rename.

    THE INDEX NARROWS, THE DISK DECIDES. Every digest that decides anything is read from the
    filesystem, because an index can be stale -- the CRC32 cross-check of 2026-10-05 found two
    manifests describing a file that had been rewritten since they were built.

    A GROUP WHOSE MEMBERS SHARE A DIGEST IS SKIPPED, because dropping one of those loses nothing
    and `drop-empty-case-twins.py --same-content` is the tool for it. Renaming them would keep a
    byte-identical duplicate in the collection for ever under a name nobody chose.

    THE TARGET NAME IS CHECKED CASE-SENSITIVELY. `wm.n_` may already exist -- as itself, or as
    `WM.N_` -- and either would turn a rename into an overwrite.
    """
    # `under` NARROWS TO A BRANCH, AND CASE-SENSITIVELY. One archive's collisions sit in several
    # branches that want different answers -- ibiblio's `ftp-archives` is nine renames the owner
    # asked for while its `distributions` is eighty-three he has not decided on -- so a run has to
    # be able to name the branch. The prefixes are compared exactly, because a tool about case is
    # the last place to fold it.
    prefixes = tuple(p.strip("/") for p in under if p.strip("/"))
    folded = collections.defaultdict(list)
    for rel in read_index(os.path.join(root, archive, INDEX_FILE)):
        flat = rel.replace("\\", "/")
        if prefixes and not any(flat == p or flat.startswith(p + "/") for p in prefixes):
            continue
        folded[flat.lower()].append(flat)

    out = []
    for key in sorted(folded):
        group = sorted(folded[key])
        if len(group) < 2:
            continue
        digests = {}
        missing = False
        for rel in group:
            got = digest_of(os.path.join(root, archive, *rel.split("/")))
            if got is None:
                missing = True
                break
            digests[rel] = got
        if missing:
            report("  skipped (a member is not on disk): %s" % group[0])
            continue
        if len(set(digests.values())) == 1:
            report("  skipped (identical content, belongs to the other tool): %s" % group[0])
            continue

        keeper = group[0]
        for rel in group[1:]:
            new = rel + "_"
            # The partner this one collided with, for the record: the keeper, unless THIS member
            # is identical to a later one, which the digest check above has already excluded.
            if spelled_exactly(root, archive, new):
                report("  REFUSING %s: %s is already there" % (rel, new))
                return None
            if new.lower() in folded:
                report("  REFUSING %s: %s collides with an indexed path" % (rel, new))
                return None
            size = os.path.getsize(long_path(os.path.join(root, archive, *rel.split("/"))))
            out.append((rel, new, size, keeper))
    return out


def save_bookkeeping(root, archive, backup, report=say):
    r"""Copy the index and four manifests aside before anything is renamed.

    THESE FIVE FILES ARE THE ONLY RECORD OF WHAT THE TREE LOOKED LIKE, and this tool rewrites
    them. Without a copy, a rename that went wrong halfway would leave no way to see what the
    paths had been.
    """
    where = os.path.join(backup, archive)
    if not os.path.isdir(where):
        os.makedirs(where)
    for name in (INDEX_FILE, SUMS_FILE, ".sha1sum", ".md5sum", ".sfv"):
        src = os.path.join(root, archive, name)
        if exists(src):
            try:
                shutil.copy2(long_path(src), long_path(os.path.join(where, name)))
            except OSError as problem:
                report("  cannot copy %s: %s" % (name, problem))
                return False
    return True


def write_record(root, archive, pairs):
    """Append the record BEFORE anything is renamed."""
    path = os.path.join(root, archive, RECORD_FILE)
    new = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as handle:
        if new:
            handle.write(RECORD_HEADER % time.strftime("%Y-%m-%d"))
        handle.write("\n")
        for old, fresh, size, partner in pairs:
            handle.write("%s\n  -> %s   (%d bytes, collided with %s)\n"
                         % (old, fresh, size, partner))
    return path


def remap(root, archive, pairs, report=say):
    r"""Rewrite the index and four manifests for the renamed paths.

    THROUGH THE LIBRARY'S OWN WRITERS and never by editing the files as text. There are four
    formats and `.sfv` puts the columns the other way round from sha256sum(1) -- a hazard the
    library keeps inside `sfv_line`. `write_index` derives `.sha256sum` from the CSV, so those two
    cannot disagree with each other.

    NOTHING IS RE-HASHED. A rename does not change a byte, so every digest carries over.
    """
    index_path = os.path.join(root, archive, INDEX_FILE)
    rows = read_index(index_path)
    digests = read_manifests(os.path.join(root, archive))
    moved = dict((old, fresh) for old, fresh, _size, _partner in pairs)
    out_rows, out_digests = {}, {}
    for rel, got in rows.items():
        flat = rel.replace("\\", "/")
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
    ap.add_argument("--under", action="append", default=[], metavar="PREFIX",
                    help="only paths in this branch, relative to the archive root; repeatable. "
                         "Compared case-SENSITIVELY. Without it, the whole archive is considered")
    ap.add_argument("--out", metavar="PATH", help="write the full plan here")
    ap.add_argument("--backup", metavar="DIR",
                    help="where the index and manifests are copied before any change. Required "
                         "with --apply: those five files per archive are the only record of what "
                         "the paths were, and this tool rewrites them")
    ap.add_argument("--apply", action="store_true",
                    help="actually rename. Without it NOTHING is written")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        say("not a directory: %s" % args.root)
        return 2
    names = args.archive or sorted(
        n for n in os.listdir(args.root)
        if os.path.isfile(os.path.join(args.root, n, INDEX_FILE)))

    found = []
    lines = []
    for archive in names:
        pairs = candidates(args.root, archive, under=args.under)
        if pairs is None:
            return 2
        if not pairs:
            continue
        found.append((archive, pairs))
        say("  %-26s %3d rename(s)" % (archive, len(pairs)))
        for old, fresh, size, partner in pairs:
            lines.append("%s\t%s\t%s\t%d\t%s" % (archive, old, fresh, size, partner))

    total = sum(len(pairs) for _name, pairs in found)
    say("")
    say("%d rename(s) across %d archive(s), %s affected"
        % (total, len(found),
           human(sum(size for _n, pairs in found for _o, _f, size, _p in pairs))))
    if args.out:
        folder = os.path.dirname(os.path.abspath(args.out))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("archive\told\tnew\tsize\tpartner\n")
            handle.write("\n".join(lines) + ("\n" if lines else ""))
        say("plan written: %s" % args.out)

    if not args.apply:
        say("")
        say("NOTHING WAS RENAMED. Read the plan, then pass --apply with --backup.")
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
        say("     record: %s" % write_record(args.root, archive, pairs))
        for old, fresh, _size, _partner in pairs:
            src = os.path.join(args.root, archive, *old.split("/"))
            dst = os.path.join(args.root, archive, *fresh.split("/"))
            if not spelled_exactly(args.root, archive, old):
                say("     not there under that spelling any more: %s" % old)
                return 2
            if spelled_exactly(args.root, archive, fresh):
                say("     the new name appeared since the plan: %s -- STOPPING" % fresh)
                return 2
            os.rename(long_path(src), long_path(dst))
            done += 1
        if not remap(args.root, archive, pairs):
            return 2
        say("     %d renamed, index and four manifests rewritten" % len(pairs))
        # BOTH STEPS AND IN THIS ORDER. The record written above is a NEW file in the archive and
        # is not in the index this tool just rewrote, so indexing has to come before the marker
        # is restated -- the other way round leaves every manifest one file short and says so.
        say("     NEXT: mirror.py --archive %s --index" % archive)
        say("     THEN: restate-marker.py --archive %s --apply --reason ..." % archive)

    say("")
    say("%d file(s) renamed. Nothing was re-hashed: a rename changes no digest." % done)
    say("Run --index on every archive above BEFORE restate-marker.py, or each manifest will be "
        "one file short -- the record this tool wrote is not in the index it rewrote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
