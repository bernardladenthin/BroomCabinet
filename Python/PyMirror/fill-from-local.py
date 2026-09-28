#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fill the gaps a fetch gave up on, from a copy of the same tree ALREADY IN THE COLLECTION.

    python fill-from-local.py --archive vgamuseum-doc \
        --from iommu/datasheets/mirrors/www.vgamuseum.info      # dry run, the default
    python fill-from-local.py --archive vgamuseum-doc --from ... --apply

WHEN THIS IS THE RIGHT TOOL
    When the origin still answers but cannot deliver, and somebody else's mirror of it is already
    on this disk. That is not a rare accident: a collection that takes both an archive and a
    mirror OF that archive ends up holding two copies of some files, and only one of them may be
    whole.

    The case it was written for: `vgamuseum-doc` is fetched from www.vgamuseum.info, which
    truncates large transfers -- `short read 36337467 of 103094544`, three attempts, every time.
    Twenty files were given up on. All twenty sit complete in
    `iommu/datasheets/mirrors/www.vgamuseum.info/`, which this collection fetched in full, the two
    large ZIPs at exactly the byte counts the origin itself advertises.

    It is NOT for filling one archive from an unrelated one, and it cannot tell you whether two
    trees are copies of each other. That judgement is the caller's, and `--from` is where it is
    recorded.

WHAT IT WILL NOT DO
    It never overwrites and it never deletes. common.copy_new_file() links the finished copy onto
    its name, so a file that is already there survives even if this tool is wrong about it, and
    even if something else creates it in the same instant.

    It fills ONLY what the fetch's own error log says it gave up on. Copying "everything the
    source has and the target lacks" would quietly undo every exclusion in mirror.EXCLUDE and
    every judgement behind them.

    It does not update `.mirror-index.csv` or `.sha256sum`. Those are mirror.py's, and a tool that
    wrote half of somebody else's bookkeeping would be worse than one that writes none. Re-run
    `mirror.py --root ... --archive ... --index` afterwards; this prints the line.

RUN IT WHEN NO FETCH IS IN FLIGHT, OR EXPECT TO RE-RUN THE FETCH
    Filling is safe at any time -- copy_new_file() cannot lose a file whoever else is writing --
    but a fetch ALREADY RUNNING counts its failures as they happen and does not look again. On
    2026-09-27 the two vgamuseum ZIPs were filled at 12:24 while the fetch that had given up on
    them at 11:03 was still walking listings; it finished afterwards and reported
    `INCOMPLETE: 2 failures` over a tree that was by then complete. Nothing was wrong with the
    archive and nothing was wrong with the fetch: each was right about a different moment.

    So the marker comes from a fetch that ran AFTER the fill. Re-running costs a listing walk and
    fetches nothing.

WHAT IT LEAVES BEHIND
    `FILLED-FROM.md` in the archive, listing every file, where it came from, its size and its
    SHA-256. A file whose provenance differs from the rest of the archive must say so in the
    archive, not in a log somebody has to still have.
"""
import argparse
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (MIRROR_ROOT, copy_new_file, exists, failed_urls, human, load_mirror,
                    local_path, long_path, say, sha256_file)

# Where mirror.py writes what it gave up on. One file per archive, under the collection's logs.
ERRORS = os.path.join("logs", "errors-%s.txt")

# What this tool leaves in the archive. The name is common.OWN_FILES' -- content ABOUT the
# archive, like PROVENANCE.md, so a completion marker's counts exclude it and no audit reads it
# as something the source served. Named here as well because this is the tool that writes it.
FILLED_FROM = "FILLED-FROM.md"


def trees_line_up(archive_dir, source, sample=40):
    """-> (how many of the sampled paths the source also has, how many were tried).

    THE GUARD THAT HAD TO EXIST, because without it this tool gives a WRONG ANSWER THAT LOOKS
    LIKE A FINDING. `--from` must name the directory corresponding to the archive's BASE URL, and
    the first real run was pointed at `iommu/.../www.vgamuseum.info` while vgamuseum-doc is
    mounted at `https://www.vgamuseum.info/images/doc/`. Every file came back "not in the copy
    either" -- which reads as "the copy does not have them" and was false: they were two
    directories deeper.

    ANY OVERLAP AT ALL SETTLES IT. The two trees are not expected to agree -- the point is that
    one has what the other lacks -- so this asks only whether they are rooted the same way. Zero
    of forty shared paths is not a gap, it is a wrong `--from`.
    """
    tried = matched = 0
    for dirpath, _dirs, files in os.walk(long_path(archive_dir)):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = full[len(long_path(archive_dir)):].lstrip(os.sep)
            if rel.startswith(".") or rel == FILLED_FROM:
                continue
            tried += 1
            if exists(os.path.join(source, rel)):
                matched += 1
            if tried >= sample:
                return matched, tried
    return matched, tried


def gaps(root, archive, base_url, source):
    """-> (rel, url, target path, source path, why-not) for every url the fetch gave up on.

    `why-not` is None when the file can be filled. Every url is reported either way: a run that
    silently dropped the ones it could not help with would make "nothing to do" and "I could not
    tell" the same output.
    """
    text = ""
    path = os.path.join(root, ERRORS % archive)
    if exists(path):
        with io.open(long_path(path), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    base = os.path.join(root, archive)
    out = []
    for url in failed_urls(text):
        if not url.startswith(base_url):
            out.append((url, url, None, None, "not under this archive's base url"))
            continue
        rel = url[len(base_url):]
        target = local_path(base, base_url, url)
        src = local_path(source, base_url, url)
        if exists(target):
            why = "already here"
        elif not exists(src):
            why = "not in the copy either"
        else:
            why = None
        out.append((rel, url, target, src, why))
    return out


def record(archive_dir, source, filled, log=None):
    """Append what was filled to FILLED-FROM.md, creating it with a header the first time."""
    path = os.path.join(archive_dir, FILLED_FROM)
    first = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as fh:
        if first:
            # NO LICENCE HEADER, and the privacy ratchet is why this is spelled out. The first
            # version wrote one, which put the author's address into a file this tool GENERATES,
            # and privacy-test.py reported it -- correctly -- as the account name outside a
            # licence header. Checked afterwards: no PROVENANCE.md in the collection carries one
            # either, and none has a `.license` companion. The mirror is not a REUSE tree; the
            # repository that produces it is.
            fh.write("# Files in this archive that did NOT come from its own source\n\n"
                     "Each was given up on by `mirror.py` -- the origin answered but could not "
                     "deliver it -- and copied from another copy of the same tree already in "
                     "this collection, by `fill-from-local.py`. The SHA-256 is of the file as it "
                     "now stands here.\n")
        fh.write("\n## %s, from `%s`\n\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), source))
        for rel, size, digest in filled:
            fh.write("- `%s` — %s, `%s`\n" % (rel, human(size), digest))
    say("  wrote %s" % path, log)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--from", dest="source", required=True,
                    help="a copy of the SAME tree, absolute or relative to --root")
    ap.add_argument("--apply", action="store_true",
                    help="actually copy. Without it nothing is written and the plan is printed.")
    ap.add_argument("--log", default=None)
    args = ap.parse_args(argv)

    log = None
    if args.log:
        log = io.open(args.log, "a", encoding="utf-8")

    mirror = load_mirror(os.path.dirname(os.path.abspath(__file__)))
    register = dict(mirror.ARCHIVES)
    if args.archive not in register:
        say("no archive called %s in mirror.ARCHIVES" % args.archive, log)
        return 2
    base_url = register[args.archive]
    source = args.source if os.path.isabs(args.source) else os.path.join(args.root, args.source)
    if not os.path.isdir(long_path(source)):
        say("--from is not a directory: %s" % source, log)
        return 2

    archive_dir = os.path.join(args.root, args.archive)

    matched, tried = trees_line_up(archive_dir, source)
    if tried and not matched:
        say("REFUSING: none of %d paths sampled from %s exists under\n"
            "    %s\n\n"
            "--from must name the directory that corresponds to this archive's BASE URL,\n"
            "    %s\n"
            "and the two trees are rooted differently. Without this check every file would be\n"
            "reported as \"not in the copy either\", which reads as a finding and is not."
            % (tried, args.archive, source, base_url), log)
        return 2
    say("%s and the copy share %d of %d sampled paths" % (args.archive, matched, tried), log)

    rows = gaps(args.root, args.archive, base_url, source)
    if not rows:
        say("%s: the error log names nothing that was given up on" % args.archive, log)
        return 0

    can = [r for r in rows if r[4] is None]
    say("%s: %d url(s) given up on, %d fillable from %s"
        % (args.archive, len(rows), len(can), source), log)
    for rel, _url, _target, _src, why in rows:
        if why:
            say("  skip  %-58s %s" % (rel[:58], why), log)

    if not can:
        return 0
    if not args.apply:
        for rel, _url, _target, src, _why in can:
            say("  WOULD FILL %-52s %10s" % (rel[:52], human(os.path.getsize(long_path(src)))),
                log)
        say("\nnothing written. Add --apply to do it.", log)
        return 0

    filled = []
    failed = []
    for rel, _url, target, src, _why in can:
        written = copy_new_file(src, target)
        if written is None:
            # Something created it between the scan and now -- which is the guard working, not a
            # problem. The file that is there wins; this tool never replaces one.
            say("  kept   %-58s (appeared while we worked)" % rel[:58], log)
            continue
        digest = sha256_file(target)
        want = sha256_file(src)
        if digest != want:
            failed.append(rel)
            say("  BAD    %-58s copy does not match the source" % rel[:58], log)
            continue
        filled.append((rel, written, digest))
        say("  filled %-58s %10s" % (rel[:58], human(written)), log)

    if filled:
        record(archive_dir, os.path.relpath(source, args.root), filled, log)
    say("\n%d filled, %d unusable, %d skipped"
        % (len(filled), len(failed), len(rows) - len(can)), log)
    say("THE INDEX IS NOW STALE. Rebuild it with:\n"
        "    python mirror.py --root %s --archive %s --index" % (args.root, args.archive), log)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
