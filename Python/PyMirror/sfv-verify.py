# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Check files against a .sfv manifest -- CRC32, the format RHash and the demoscene tools write.

WHY THIS EXISTS. An archive verified only against the checksum of the host that served it is
verified against one opinion. `ia-bullfreeware` arrived with per-file MD5 from the Internet
Archive's metadata API, which proves the transfer -- but the uploader ALSO shipped two .sfv files
made with RHash on 2022-02-28, before the upload, from the original bullfreeware.com tree:

    packages.tar.sfv     one line: the whole 85 GB tar,  CRC32 37CDDCAF
    packages.sfv         23 771 lines: every member file inside that tar

Those are a second, independent statement about the same bytes, from a different party at a
different time with a different algorithm. Agreement between them is the strongest evidence this
collection can obtain for a file whose origin is gone. It is the same shape as bitsavers' .tar.txt
listings, and the reason both are kept.

CRC32 IS WEAK, and that is fine here. It is a 32-bit check designed against transmission noise,
not against forgery, and this is not a security check -- nobody is attacking a 2022 AIX package
archive. What it catches is exactly what threatens a mirror: a truncated resume, a flipped bit, a
file that silently became an HTML error page. For that it is perfectly adequate, and it is what
the manifest actually offers.

    python sfv-verify.py packages.tar.sfv
    python sfv-verify.py --root Q:/mirror/ia-bullfreeware packages.sfv
"""
import argparse
import io
import os
import sys
import time
import zlib

from common import human, load_mirror, read_sfv

CHUNK = 1 << 22       # 4 MB; on an 85 GB file the read size matters more than for small ones


def crc32(path, progress=None):
    """-> (crc as 8 upper-case hex digits, bytes read). Streamed; never loads the file."""
    c = 0
    read = 0
    last = time.time()
    with io.open(path, "rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            c = zlib.crc32(b, c)
            read += len(b)
            if progress and time.time() - last > 10:
                progress(read)
                last = time.time()
    return "%08X" % (c & 0xFFFFFFFF), read


# parse_sfv LIVED HERE UNTIL 2026-10-02 and is now common.read_sfv, because this collection
# started WRITING .sfv files as well as reading other people's: mirror.py --index emits one per
# archive beside .sha1sum and .md5sum. A format whose reader sits in one file and whose writer sits
# in another is a format with two opinions, and the one that matters -- that a filename may contain
# spaces, so the split is from the RIGHT -- is exactly the kind that gets re-derived differently.
# `common.sfv_line` is the writer, `common.read_sfv` the reader, and a test round-trips the pair.


def retired_in(root):
    """-> f(manifest path) giving the reason it was removed ON PURPOSE, or None.

    A MANIFEST DESCRIBES WHAT THE ORIGIN HAD. Once anything is deliberately removed from a mirror
    -- a container unpacked and then deleted -- the manifest and the tree disagree for ever, and
    every future run reports that file MISSING. The word is the problem: it is the same word this
    tool uses for a truncated download and for bit rot, and a check that cries wolf on schedule is
    a check people learn to ignore. The alarm has to be explained BY THE TOOL, not by a paragraph
    somebody has to go and find.

    So the one list that already answers "what did we remove, and why" -- mirror.py's RETIRED --
    is read here too, and those entries are counted and printed apart from real losses. They do
    not affect the exit code, because nothing is wrong.

    Matched on the manifest's own spelling, relative to the archive directory: packages.sfv names
    `packages/SRPMS.tar.gz` and RETIRED["ia-bullfreeware"] names exactly that.

    FAILS OPEN. An unreadable mirror.py must never turn into silence about a file that really
    is gone.  [2026-09-13]

    THE MATCHING IS mirror.py's OWN is_retired(), not a second dictionary built here.
    """
    archive = os.path.basename(os.path.abspath(root).rstrip("\\/"))
    try:
        mod = load_mirror()
    # MIRROR.PY IS NOT BESIDE THIS SCRIPT, AND NOTHING ELSE. It was `except Exception`,
    # which also swallows an AttributeError -- so the day mirror.py stopped carrying
    # ARCHIVES, every tool reading it here would have quietly seen an empty register and
    # reported a clean pass over nothing. "The file is absent" is a fact; "the register
    # moved" is a defect, and only the first belongs here.
    except (OSError, ImportError):
        return lambda _name: None
    return lambda name: mod.is_retired(archive, name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sfv", help="the .sfv manifest")
    ap.add_argument("--root", default=None,
                    help="directory the names are relative to (default: the .sfv's own directory)")
    ap.add_argument("--quiet", action="store_true", help="only print failures and the summary")
    args = ap.parse_args()

    if not os.path.isfile(args.sfv):
        sys.exit("no such file: %s" % args.sfv)
    root = args.root or os.path.dirname(os.path.abspath(args.sfv))

    entries = read_sfv(args.sfv)
    if not entries:
        sys.exit("no usable lines in %s -- is it really an .sfv?" % args.sfv)
    print("  %s: %d entries, checking against %s" % (args.sfv, len(entries), root), flush=True)

    retired = retired_in(root)
    ok = bad = missing = 0
    gone_on_purpose = []
    t0 = time.time()
    for name, want in entries:
        p = os.path.join(root, name.replace("/", os.sep))
        if not (os.path.exists(p) or os.path.exists("\\\\?\\" + p)):
            why = retired(name)
            if why is not None:
                gone_on_purpose.append((name, why))
                print("  RETIRED  %s" % name, flush=True)
                continue
            missing += 1
            print("  MISSING  %s" % name, flush=True)
            continue

        def show(read, _n=name):
            el = time.time() - t0
            print("     %-28s %s  (%.0f MB/s)"
                  % (_n[:28], human(read), read / 1e6 / max(el, 1e-9)), flush=True)

        got, size = crc32(p, progress=None if args.quiet else show)
        if got == want:
            ok += 1
            if not args.quiet:
                print("  ok       %s  %s  %s" % (want, human(size), name), flush=True)
        else:
            bad += 1
            print("  MISMATCH %s: computed %s, manifest says %s" % (name, got, want), flush=True)

    el = time.time() - t0
    print()
    print("  %d ok, %d mismatched, %d missing%s, in %.1f min"
          % (ok, bad, missing,
             (", %d retired" % len(gone_on_purpose)) if gone_on_purpose else "", el / 60))
    for name, why in gone_on_purpose:
        print("  RETIRED, not missing: %s" % name)
        print("      %s" % why)
    if bad:
        print("  A MISMATCH IS NOT NOISE. CRC32 is weak against forgery and strong against"
              " damage;")
        print("  a disagreement here means the bytes on disk are not the bytes that were"
              " manifested.")
    elif not missing:
        print("  every file %smatches its manifest -- an INDEPENDENT confirmation, from the"
              " uploader" % ("still present " if gone_on_purpose else ""))
        print("  rather than from the host that served the download.")
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
