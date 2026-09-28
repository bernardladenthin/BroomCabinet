# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Ask each source how long a truncated file is supposed to be -- one HEAD request each.

WHY THE LENGTH IS THE RIGHT QUESTION HERE, WHEN IT WAS THE WRONG ONE NEXT DOOR. `holes-vs-source`
could learn nothing from a HEAD: all three files it settled were preallocated at full length and
never filled, so the source answers with exactly the length held here and the two cases --
"the source is broken too" and "the source has the intact file" -- are indistinguishable. Only
the bytes separate them.

A TRUNCATED FILE IS THE OPPOSITE. It stopped early, so it is SHORTER than the original, and one
HEAD request settles it outright. If the source is bigger, the missing part is still there and
the file is **re-fetchable** -- which is the best outcome this collection can produce and the
reason `--declared` was written.

WHAT COUNTS AS TRUNCATED. `common.declared_length` asks the file what length it claims: a RIFF
size field, an ISO 9660 volume size, a zip's End Of Central Directory. Two answers bring a file
here -- it is shorter than it declares, or it is a zip with no central directory at all, which is
what a transfer that stopped mid-stream leaves behind. A file LONGER than it declares is ordinary
padding and is not truncation.

IT CHANGES NOTHING. It reads the collection, asks for sizes, and prints. Re-fetching is
`subset-refetch.py`'s job and a decision somebody makes after reading this.

    python truncated-vs-source.py --dry-run        # what it found and whom it would ask
    python truncated-vs-source.py --under bitsavers
"""
import argparse
import os
import sys
from urllib.parse import urlsplit

import mirror
from common import (MIRROR_ROOT, DECLARES_ITS_LENGTH, Pacer, declared_length, file_extension,
                    head_size, human, iter_files, long_path, say, source_url,
                    split_archive)

TIMEOUT = 60
PER_HOST_PAUSE = 1.0

# HTTP_FACE and source_url() are common.py's since 2026-09-27. The comment that stood here said
# "Same table, same reason and same evidence as holes-vs-source.py" -- a duplicate that announced
# itself as one, which is a better argument for moving it than any measurement.

BIGGER = "THE SOURCE HAS MORE -- re-fetchable"
SAME = "the source is the same length -- it is broken there too"
SMALLER = "the source is SHORTER than our copy"
NO_SIZE = "the server would not say how long it is"
GONE = "nobody answered"
UNASKABLE = "no source URL recorded"
ORDER = (BIGGER, SMALLER, NO_SIZE, GONE, SAME, UNASKABLE)


def truncated(base, archive=None, report=None):
    """-> [(archive, rel, size, expected_or_None, fmt)] for every file short of its own claim.

    `archive` IS A PARAMETER RATHER THAN SOMETHING TO PEEL OFF THE PATH, because peeling was
    wrong and quietly so. Walking one archive gives paths already relative to it, and taking the
    first segment off those threw away a real directory: `Incoming/sf4.0.zip` became
    `sf4.0.zip`, every request 404ed, and the report said "nobody answered -- 8". Eight of eight
    failing is not eight dead sources, it is one bug, and it read like a finding. [2026-09-25]
    """
    out = []
    # `iter_files` yields (relative path, full path) and skips this collection's own bookkeeping
    # files, which is what we want here: a truncated `.mirror-index.csv` is a different problem
    # with a different tool.
    root = os.path.join(base, archive) if archive else base
    for rel, path in iter_files(root):
        if file_extension(rel) not in DECLARES_ITS_LENGTH:
            continue
        said = declared_length(path)
        if said is None:
            continue
        expected, fmt = said
        try:
            size = os.path.getsize(long_path(path))
        except OSError:
            continue
        if expected is None or size < expected:
            rel = rel.replace(os.sep, "/")
            if archive:
                where, under = archive, rel
            else:
                where, under = split_archive(rel)
                if not under:
                    continue        # a loose file in the collection root belongs to no archive
            out.append((where, under, size, expected, fmt))
            if report:
                report("  %s  %s/%s" % (fmt, where, under))
    return out


def judge(ours, theirs):
    if theirs is None:
        return NO_SIZE
    if theirs > ours:
        return BIGGER
    if theirs < ours:
        return SMALLER
    return SAME


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=MIRROR_ROOT,
                    help="the collection (default %(default)s)")
    ap.add_argument("--under", help="only this archive")
    ap.add_argument("--dry-run", action="store_true", help="find them, ask nobody")
    ap.add_argument("--quiet", action="store_true", help="no progress while it looks")
    args = ap.parse_args(argv)

    where = os.path.join(args.root, args.under) if args.under else args.root
    if not os.path.isdir(long_path(where)):
        say("no directory at %s" % where)
        return 2

    say("=== looking for files shorter than they say they are ===")
    rows = truncated(args.root, args.under, report=None if args.quiet else say)
    if not rows:
        say("  none found")
        return 0
    say("  %s\n" % plural_files(len(rows)))

    if args.dry_run:
        register = dict(mirror.ARCHIVES)
        for archive, rel, size, expected, fmt in rows:
            url = source_url(archive, rel, register)
            say("    %-9s %10s  %s" % (fmt, human(size), rel[:64]))
            say("        %s" % (url or "(no source URL recorded)"))
        return 0

    register = dict(mirror.ARCHIVES)
    pacer = Pacer(PER_HOST_PAUSE)
    counts = {}
    for archive, rel, size, expected, fmt in rows:
        url = source_url(archive, rel, register)
        if url is None:
            counts.setdefault(UNASKABLE, []).append((archive, rel, size, None, fmt))
            continue
        pacer.wait(urlsplit(url).netloc)
        try:
            theirs = head_size(url, timeout=TIMEOUT)
        except Exception:                                       # noqa: BLE001
            theirs = None
            verdict = GONE
        else:
            verdict = judge(size, theirs)
        counts.setdefault(verdict, []).append((archive, rel, size, theirs, fmt))

    for verdict in ORDER:
        items = counts.get(verdict)
        if not items:
            continue
        say("\n  %s -- %d" % (verdict, len(items)))
        if verdict is not SAME:
            for archive, rel, size, theirs, fmt in sorted(items):
                extra = "" if theirs is None else "  source %s (+%s)" % (
                    human(theirs), human(theirs - size))
                say("    %-9s %10s  %s/%s%s" % (fmt, human(size), archive, rel[:50], extra))

    total = sum(len(v) for v in counts.values())
    say("\n  %d file(s) asked about, %d accounted for" % (len(rows), total))
    if total != len(rows):
        say("  THE SUMMARY DOES NOT ADD UP -- a verdict is missing from ORDER")
        return 2
    return 1 if counts.get(BIGGER) else 0


def plural_files(n):
    return "%d file%s" % (n, "" if n == 1 else "s")


if __name__ == "__main__":
    sys.exit(main())
