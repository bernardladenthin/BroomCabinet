# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Give one of two directories that differ only in case a name Windows can keep apart.

    python rename-case-dirs.py --archive ibiblio-historic-linux    what WOULD happen
    python rename-case-dirs.py --pair fixes/V4=fixes/v4            one pair, named by hand
    python rename-case-dirs.py --out plan.txt                      write the plan and read it
    python rename-case-dirs.py --apply --backup D                  do it

WHY. Rar.exe stores only ONE of two paths differing in upper/lower case: it says nothing and
exits 0. Extracting such a pair onto an ordinary Windows folder yields one file, under the wrong
name, with the wrong content, while RAR reports "Alles OK". So the collection has to become
something Windows can hold.

RENAMING, NOT MERGING, AND THE OWNER CHOSE IT FOR THE REDHAT TREES. `merge-case-dirs.py` puts two
such directories into one, which is right where the contents belong together. It cannot be used
where a file inside would then collide -- and in `ibiblio-historic-linux` that is every group,
blocked by `TRANS.TBL`, the ISO-9660 table that describes the very directory it sits in. Renaming
leaves both directories and both tables alone: `X` becomes `X_`, `X_` and `x` coexist, and nothing
inside either one is touched. Measured on 2026-10-05: 16 groups, 65 file paths, 0 bytes of content
changed, and 0 colliding directories left in that archive. Merging the same 16 would have moved
about 700 files and rewritten 16 TRANS.TBL files.

THE SUFFIX IS `_` AND IT IS A MARK, NOT A NAME. The owner's words: "das man weiß, diese sind
abgeleitet". A trailing underscore is legal on NTFS, survives every archiver, and reads as
mechanical. The original name is in CASE-DIRS-RENAMED.txt.

THE RULE IS NARROW ON PURPOSE. A candidate is proposed only where exactly one member's last
component starts with an upper-case letter -- true for all 16 ibiblio groups and NOT generally
true: ibm-aix has `IJ36417`/`ij36417`, where both would qualify, and `generalIfix`/`generalifix`,
where neither does. Those are refused and must be named with --pair, which is why --pair exists.

IT ALSO FINISHES A MOVE SOMEBODY ELSE STARTED. The owner moved `fixes/V4` into `fixes/v4` by hand
on 2026-10-05; the tree was then right and the index still named the old paths. Given
`--pair fixes/V4=fixes/v4` with the source already gone, this tool verifies every affected file is
at the target WITH THE DIGEST THE INDEX RECORDED and then rewrites the records. It never assumes a
move happened -- it reads the bytes.

WHAT IT WRITES, in this order, per archive:

  1. a copy of the index and manifests into --backup, verified by SHA-256
  2. the record, BEFORE the first rename
  3. the rename itself -- one os.replace per directory, whatever it holds
  4. the index and four manifests, rewritten through common.write_index and
     common.write_manifests. NOTHING IS RE-HASHED where the digest was already recorded.

AFTERWARDS, IN THIS ORDER: `mirror.py --archive <name> --index` and only then
`restate-marker.py --archive <name> --apply`. The record is a new file the rewritten index does
not know about; restating first leaves every manifest one file short, which is exactly what
happened on 2026-10-05 before this was written down.
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

RECORD_FILE = "CASE-DIRS-RENAMED.txt"
MARK = "_"

RECORD_HEADER = """# Directories renamed %s because their names differed from another
# directory's only in upper/lower case, which Windows cannot keep apart and
# WinRAR silently halves: given two such paths, rar stores one of them, says
# nothing about the other and exits 0.
#
# A trailing underscore marks the renamed one as derived. Nothing inside either
# directory was touched -- no file was moved, merged or rewritten, and every
# digest is the digest it already had. The index and all four manifests were
# rewritten from those digests, not by re-hashing.
#
# renamed from  ->  to
"""


def candidates(root, archive, index=None):
    r"""-> [(old, new, reason_or_None)] for every colliding directory group.

    `reason` IS WHY IT CANNOT BE PROPOSED, and a group with one is still returned so a reader of
    the plan sees what was skipped rather than wondering. The rule: exactly one member's last
    component must start with an upper-case letter. In ibiblio-historic-linux that holds for all
    16; in ibm-aix `IJ36417`/`ij36417` has two and `generalIfix`/`generalifix` has none.
    """
    idx = index if index is not None else read_index(os.path.join(root, archive, INDEX_FILE))
    paths = [rel.replace("\\", "/") for rel in idx]
    folded = collections.defaultdict(set)
    for rel in paths:
        parts = rel.split("/")
        for cut in range(1, len(parts)):
            folded["/".join(x.lower() for x in parts[:cut])].add("/".join(parts[:cut]))
    out = []
    for key in sorted(folded):
        members = sorted(folded[key])
        if len(members) < 2:
            continue
        upper = [m for m in members if m.split("/")[-1][:1].isupper()]
        if len(upper) != 1:
            out.append((members[0], None,
                        "%d of %d member(s) start upper-case -- name it with --pair"
                        % (len(upper), len(members))))
            continue
        old = upper[0]
        new = old + MARK
        if new.lower() in folded or any(p.lower().startswith(new.lower() + "/") for p in paths):
            out.append((old, None, "%s is already taken" % new))
            continue
        out.append((old, new, None))
    return out


def spelled_exactly(root, archive, rel):
    r"""-> True when `rel` exists under EXACTLY that spelling, asked case-sensitively.

    `os.path.exists` IS THE WRONG QUESTION HERE. On an ordinary Windows directory `fixes/V4`
    resolves to `fixes/v4`, so `exists` answers True for a name that is not there -- and this
    whole tool is about telling those two apart. It only answered correctly for ibm-aix because
    `fixes` happens to carry the per-directory case-sensitivity flag, and a check that depends on
    a flag somebody else set is not a check.

    So the parent is LISTED and the name compared byte for byte. os.listdir returns the names the
    filesystem actually holds, whatever its matching rules are.
    """
    parts = rel.split("/")
    here = os.path.join(root, archive)
    for part in parts:
        try:
            entries = os.listdir(long_path(here))
        except OSError:
            return False
        if part not in entries:
            return False
        here = os.path.join(here, part)
    return True


def affected(root, archive, old, index=None):
    """-> the index paths under `old`, as they are spelled in the index."""
    idx = index if index is not None else read_index(os.path.join(root, archive, INDEX_FILE))
    return sorted(rel for rel in idx if rel.replace("\\", "/").startswith(old + "/"))


def already_done(root, archive, old, new, index=None, report=say):
    r"""-> True when `old` is gone and every file is at `new` WITH THE RECORDED DIGEST.

    READ, NOT ASSUMED. The owner moved fixes/V4 into fixes/v4 by hand and the four files matched
    their recorded SHA-256 exactly -- but a tool that takes "the source is gone" as proof of a
    clean move would also accept a source that was deleted. So every affected file is hashed at
    the target and compared with what the index says, and one mismatch is a refusal.
    """
    idx = index if index is not None else read_index(os.path.join(root, archive, INDEX_FILE))
    if spelled_exactly(root, archive, old):
        return False
    for rel in affected(root, archive, old, idx):
        flat = rel.replace("\\", "/")
        target = new + flat[len(old):]
        full = os.path.join(root, archive, *target.split("/"))
        if not exists(full):
            report("     %s is not at %s -- REFUSING" % (flat, target))
            return None
        if sha256_file(full) != idx[rel][2]:
            report("     %s does not match the digest the index recorded -- REFUSING" % target)
            return None
    return True


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


def write_record(root, archive, pairs):
    """Append the record BEFORE anything is renamed."""
    path = os.path.join(root, archive, RECORD_FILE)
    new_file = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as fh:
        if new_file:
            fh.write(RECORD_HEADER % time.strftime("%Y-%m-%d"))
        fh.write("\n")
        for old, new, count in pairs:
            fh.write("%s\n  -> %s   (%d file(s) below it)\n" % (old, new, count))
    return path


def remap(root, archive, pairs, report=say):
    r"""Rewrite the index and four manifests for every path under a renamed directory.

    THROUGH THE LIBRARY'S OWN WRITERS and never by editing the files as text. There are four
    formats and `.sfv` puts the columns the other way round from sha256sum(1) -- a hazard this
    library keeps inside `sfv_line`. `write_index` derives `.sha256sum` from the CSV so the two
    cannot disagree.

    NOTHING IS RE-HASHED. A renamed directory changes no file's bytes.
    """
    index_path = os.path.join(root, archive, INDEX_FILE)
    rows = read_index(index_path)
    digests = read_manifests(os.path.join(root, archive))
    out_rows, out_digests = {}, {}
    for rel, got in rows.items():
        flat = rel.replace("\\", "/")
        where = flat
        for old, new, _count in pairs:
            if flat.startswith(old + "/"):
                where = new + flat[len(old):]
                break
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
    ap.add_argument("--pair", action="append", default=[], metavar="OLD=NEW",
                    help="rename this directory to that one, instead of the derived rule. "
                         "Needed where the rule cannot choose, and for finishing a move made by "
                         "hand. Requires exactly one --archive")
    ap.add_argument("--out", metavar="PATH", help="write the full plan here")
    ap.add_argument("--backup", metavar="DIR", help="required with --apply")
    ap.add_argument("--apply", action="store_true",
                    help="actually rename. Without it NOTHING is written")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        say("not a directory: %s" % args.root)
        return 2
    if args.pair and len(args.archive) != 1:
        say("--pair needs exactly one --archive")
        return 2
    names = args.archive or sorted(
        n for n in os.listdir(args.root)
        if os.path.isfile(os.path.join(args.root, n, INDEX_FILE)))

    work, lines, skipped = [], [], []
    for archive in names:
        idx = read_index(os.path.join(args.root, archive, INDEX_FILE))
        if args.pair:
            proposed = []
            for spec in args.pair:
                if "=" not in spec:
                    say("--pair wants OLD=NEW, got %s" % spec)
                    return 2
                old, new = spec.split("=", 1)
                proposed.append((old.strip("/"), new.strip("/"), None))
        else:
            proposed = candidates(args.root, archive, idx)
        good = []
        for old, new, reason in proposed:
            if reason:
                skipped.append((archive, old, reason))
                continue
            count = len(affected(args.root, archive, old, idx))
            if not count:
                skipped.append((archive, old, "the index names nothing under it"))
                continue
            good.append((old, new, count))
        if not good:
            continue
        work.append((archive, good))
        for old, new, count in good:
            say("  %-24s %-54s -> %s  (%d file(s))"
                % (archive, old[-52:], new.split("/")[-1], count))
            lines.append("%s\t%s\t%s\t%d" % (archive, old, new, count))

    total = sum(count for _a, good in work for _o, _n, count in good)
    say("")
    say("%d rename(s) across %d archive(s), %d file path(s) to rewrite; %d group(s) skipped"
        % (sum(len(good) for _a, good in work), len(work), total, len(skipped)))
    for archive, old, reason in skipped[:8]:
        say("  skipped  %-24s %-40s %s" % (archive, old[-38:], reason))
    if args.out:
        folder = os.path.dirname(os.path.abspath(args.out))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("archive\told\tnew\tfiles\n")
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        say("plan written: %s" % args.out)

    if not args.apply:
        say("")
        say("NOTHING WAS RENAMED. Read the plan, then pass --apply with --backup.")
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
        for old, new, count in good:
            source = os.path.join(args.root, archive, *old.split("/"))
            target = os.path.join(args.root, archive, *new.split("/"))
            settled = already_done(args.root, archive, old, new)
            if settled is None:
                return 2
            if settled:
                say("     %s is already at %s, every digest checked" % (old, new))
                done += count
                continue
            if not spelled_exactly(args.root, archive, old):
                say("     %s is gone and its files are not at %s -- STOPPING" % (old, new))
                return 2
            if spelled_exactly(args.root, archive, new):
                say("     %s already exists -- STOPPING" % new)
                return 2
            os.replace(long_path(source), long_path(target))
            say("     %s -> %s  (%d file(s))" % (old, new, count))
            done += count
        if not remap(args.root, archive, good):
            return 2
        say("     index and four manifests rewritten")
        say("     NEXT: mirror.py --archive %s --index" % archive)
        say("     THEN: restate-marker.py --archive %s --apply --reason ..." % archive)
    say("")
    say("%d file path(s) rewritten. Nothing was re-hashed: renaming a directory changes no "
        "file's bytes." % done)
    say("Run --index on every archive above BEFORE restate-marker.py, or each manifest will be "
        "one file short -- the record this tool wrote is not in the index it rewrote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
