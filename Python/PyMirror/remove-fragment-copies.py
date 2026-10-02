# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Remove files saved under a URL FRAGMENT, where the real document is already beside them.

    python remove-fragment-copies.py                 # verify and show the plan, delete nothing
    python remove-fragment-copies.py --delete        # after reading the plan
    python remove-fragment-copies.py --archive ardent-tool

WHERE THESE CAME FROM. A `#anchor` names a position INSIDE a document, never a document. Before
2026-09-03 this crawler took the whole href as a filename, so a page linking

    Lacuna.html#DirectConnection
    Lacuna.html#ECP_support

made the source send the same 56 018 bytes three times and stored them three times, under three
names. strip_fragment() has prevented new ones since; what is on disk is residue, and every copy
cost somebody else a full transfer.

WHY A PATTERN IS THE WRONG TOOL, and this is the whole reason this file exists rather than one
`del *#*`: 771 files in this collection have a `#` in their REAL name -- bitsavers 572, vtda 37,
next-68k-org 70, ardent-tool 80 among them, including pages MAD-PageGen generates as `#Planar`
and `#System_FW`. Deleting by pattern would take 5.75 GB of content with it.

So a file is removable only when ALL of this holds, re-checked at the moment of deletion:

    the part before the first '#' is NOT empty        `#System_FW` has no stem; it IS the name
    that stem exists AND IS A FILE                    a directory of the same name proves nothing
    both read back with the SAME SHA-256              size and mtime are not evidence

Anything else stays, and says which test it failed.

WHAT IT DOES NOT TOUCH. `.suspect`, `.superseded` and `.part` are not duplicates and are not
rubbish: a .suspect is a TRUNCATED DOWNLOAD, and mirror.py names those "PERMANENTLY LOST" and
says the count is whatever the tree returns -- deleting them would delete the record itself.

AND IT LEAVES THE ARCHIVE CONSISTENT. Removing files makes every marker that counts them wrong,
so `files` and `bytes` are rewritten from the tree afterwards and a line recording the removal is
appended. Only those two lines change; the rest of a marker is somebody's written reasoning and
is not this tool's to touch. The checksum index still needs `mirror.py --archive X --index`,
which is printed at the end -- it carries hashes over and costs seconds.
"""

import argparse
import datetime
import hashlib
import io
import os
import re
import shutil
import sys


from common import (MIRROR_ROOT, COMPLETE_MARKER, OWN_FILES, is_partial, isfile, long_path,
                    relative_to)


def today():
    """-> the date this run happened, as the marker and the record both have to say."""
    return datetime.date.today().isoformat()



def sha(path):
    h = hashlib.sha256()
    try:
        fh = io.open(path, "rb")
    except OSError:
        try:
            fh = io.open(long_path(path), "rb")
        except OSError:
            return None
    with fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def size_of(p):
    try:
        return os.path.getsize(p)
    except OSError:
        try:
            return os.path.getsize(long_path(p))
        except OSError:
            return 0


def classify(dirpath, name):
    """-> (verdict, stem_path). verdict 'remove' only when the duplicate is proven."""
    head = name.split("#")[0]
    if not head:
        return "name begins with '#' -- it IS the name", None
    stem = os.path.join(dirpath, head)
    if not isfile(stem):
        return "no file of that name beside it", None
    a, b = sha(os.path.join(dirpath, name)), sha(stem)
    if a is None or b is None:
        return "unreadable", None
    if a != b:
        return "SAME NAME, DIFFERENT BYTES -- look at it", stem
    return "remove", stem


def measure(base):
    n = b = 0
    for dp, _d, fs in os.walk(base):
        top = os.path.normcase(dp) == os.path.normcase(base)
        for f in fs:
            if is_partial(f) or (top and f in OWN_FILES):
                continue
            n += 1
            b += size_of(os.path.join(dp, f))
    return n, b


def write_record(base, pairs):
    """Leave a list of what was removed and what it duplicated, inside the archive.

    NOT A BACKUP, AND DELIBERATELY NOT ONE. Copying 1.87 GB somewhere would protect bytes that
    are not at risk: every file removed here is byte-identical to one that stays, and that is
    proved by SHA-256 immediately before the deletion. What a copy could not preserve, and what
    actually disappears, is the NAMES -- the record that `Lacuna.html` was once also fetched as
    `Lacuna.html#DirectConnection` and `#ECP_support`, and that the source sent those bytes three
    times because of it.

    Same reasoning as RENAMED.txt beside an extracted tree: without the list, the tree is simply
    smaller than it was and nothing says why.
    """
    p = os.path.join(base, "FRAGMENT-COPIES-REMOVED.txt")
    with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
        # THE DATE IS TODAY'S, NOT THE DAY THIS TOOL WAS WRITTEN. It read "2026-09-13" here and in
        # the marker line below -- the day of authorship -- so a removal performed on 2026-10-02
        # was recorded as having happened three weeks earlier, in an archive's own marker. The
        # marker is what somebody reads in a year, and `completed` beside it is deliberately left
        # alone precisely so the two dates mean different things; a wrong second date is therefore
        # worse than none at all.
        fh.write("# Files removed %s because they were the same document as the file\n" % today()
                 + "# beside them, saved a second time under a URL fragment. Verified by SHA-256\n"
                 "# at the moment of deletion, not by size.\n"
                 "#\n"
                 "# A '#anchor' names a position INSIDE a document, never a document. This\n"
                 "# crawler treated the whole href as a filename until strip_fragment() was\n"
                 "# added on 2026-09-03, so the source was asked for the same bytes once per\n"
                 "# anchor. Nothing below was lost: the left-hand name is gone, the document it\n"
                 "# held is the file named on the right.\n"
                 "#\n"
                 "# removed  ->  the copy that remains\n\n")
        for gone, kept in sorted(pairs):
            fh.write("%s\n  -> %s\n" % (gone, kept))
    return len(pairs)


def fix_marker(base, removed, freed):
    """Rewrite only the `files` and `bytes` lines, and append what happened. Nothing else."""
    p = os.path.join(base, COMPLETE_MARKER)
    # isfile, not os.path.isfile: the marker of a deeply nested archive would otherwise read as
    # absent and this would answer "no marker" for one that is there.
    #
    # AND THE OPENS BELOW TAKE long_path FOR THE SAME REASON. Changing only the test made this
    # WORSE than leaving both alone: the guard would pass on a path os.path cannot open, and a
    # function that used to decline gracefully would raise instead. A path check and the open
    # that follows it have to mean the same path.
    if not isfile(p):
        return "no marker"
    n, b = measure(base)
    with io.open(long_path(p), encoding="utf-8", errors="replace") as fh:
        s = fh.read()
    s2, nf = re.subn(r"^files\s+\d+\s*$", "files         %d" % n, s, count=1, flags=re.M)
    s2, nb = re.subn(r"^bytes\s+\d+\s*$", "bytes         %d" % b, s2, count=1, flags=re.M)
    if not (nf and nb):
        return "MARKER NOT UNDERSTOOD -- left alone, run --verify"
    s2 = s2.rstrip("\n") + (
        "\n\nREMOVED %s: %d files saved under a URL fragment, %d bytes. Each was the same\n"
        "document as the file beside it -- verified by SHA-256 at the moment of deletion, not by\n"
        "size -- and existed only because this crawler treated `page.html#anchor` as a filename\n"
        "until strip_fragment() was added on 2026-09-03. Every one cost the source a full\n"
        "transfer. The figures above were rewritten from the tree.\n" % (today(), removed, freed))
    with io.open(long_path(p), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s2)
    return "marker: files %d, bytes %d" % (n, b)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append", default=[], help="limit to this one; repeatable")
    ap.add_argument("--backup", metavar="DIR", help="copy each file here before removing it")
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()

    names = args.archive or sorted(
        d for d in os.listdir(args.root)
        if os.path.isdir(os.path.join(args.root, d)) and d != "logs")

    plan = {}
    kept = {}
    for a in names:
        base = os.path.join(args.root, a)
        for dp, _d, fs in os.walk(base):
            for f in fs:
                if "#" not in f or is_partial(f):
                    continue
                verdict, _stem = classify(dp, f)
                if verdict == "remove":
                    plan.setdefault(a, []).append(os.path.join(dp, f))
                else:
                    kept.setdefault(verdict, []).append(os.path.join(dp, f))

    total = sum(len(v) for v in plan.values())
    freed = {a: sum(size_of(p) for p in v) for a, v in plan.items()}
    print("  %s\n" % ("DELETING" if args.delete else "CHECKING ONLY -- nothing is touched"))
    print("  removable, proven byte-identical to the document beside them:")
    for a in sorted(plan, key=lambda x: -freed[x]):
        print("     %-26s %6d files  %9.1f MB" % (a, len(plan[a]), freed[a] / 1e6))
    print("     %-26s %6d files  %9.1f MB" % ("TOTAL", total, sum(freed.values()) / 1e6))

    print("\n  kept, and why:")
    for why, v in sorted(kept.items(), key=lambda x: -len(x[1])):
        print("     %-46s %6d" % (why, len(v)))
        if "DIFFERENT BYTES" in why:
            for p in v[:6]:
                print("          %s" % p[-92:])

    if not args.delete:
        print("\n  Run again with --delete to remove them.")
        return 0
    if not total:
        print("\n  nothing to do")
        return 0

    if args.backup:
        os.makedirs(args.backup, exist_ok=True)

    gone = 0
    for a in sorted(plan):
        base = os.path.join(args.root, a)
        n_a = 0
        pairs = []
        for p in plan[a]:
            # RE-CHECKED HERE. The plan was built minutes ago; this is the moment that matters.
            verdict, stem = classify(os.path.dirname(p), os.path.basename(p))
            if verdict != "remove":
                print("     SKIPPED (%s) %s" % (verdict, p[-70:]))
                continue
            if args.backup:
                flat = relative_to(args.root, p).replace("/", "__").replace("#", "_HASH_")
                shutil.copy2(p, os.path.join(args.backup, flat[-180:]))
            rel_gone = relative_to(base, p)
            rel_kept = relative_to(base, stem)
            try:
                os.remove(p)
            except OSError:
                os.remove(long_path(p))
            pairs.append((rel_gone, rel_kept))
            n_a += 1
        gone += n_a
        rec = write_record(base, pairs) if pairs else 0
        print("  %-26s removed %6d   record %d   %s"
              % (a, n_a, rec, fix_marker(base, n_a, freed[a])))

    print("\n  %d files removed, %.2f GB freed" % (gone, sum(freed.values()) / 1e9))
    print("\n  NEXT, to leave every archive consistent:")
    for a in sorted(plan):
        print("     python mirror.py --root %s --archive %s --index" % (args.root, a))
    print("     python mirror.py --root %s --verify" % args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
