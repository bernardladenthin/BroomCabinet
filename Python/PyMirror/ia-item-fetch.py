# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fetch an Internet Archive item whole, from its own metadata rather than by crawling it.

    python ia-item-fetch.py --item bull-freeware-aix433-2013 --archive ia-bull-aix433-2013
    python ia-item-fetch.py --item bullfreeware --archive ia-bullfreeware --dry-run

WHY NOT mirror.py. An Archive item is not a directory listing and should not be walked like one.
`https://archive.org/metadata/<id>` returns the complete file list -- names, sizes and MD5s -- in
ONE request. That is exact where a crawl is inferential, it is cheap where a crawl is expensive,
and it is the interface the Archive publishes for the purpose. Walking the HTML would be choosing
the worse of two offered doors.

IT ALSO GIVES US SOMETHING THIS COLLECTION VALUES SEPARATELY: an independent record. The metadata
carries an MD5 for every file, written by the Archive when the item was created. Checking a
download against it is a check against somebody else's arithmetic, not against our own -- the same
role bitsavers' `.tar.txt` manifests play for the container tars. It is stored beside the tree as
`IA-METADATA.json` so the check survives this run.

WHAT IS SKIPPED. The Archive adds its own derivatives to every item -- `_meta.xml`, `_files.xml`,
`_meta.sqlite`, the BitTorrent file, thumbnails. Those describe the item rather than being it, and
they change when the Archive reprocesses. The metadata JSON is kept (it is the record above); the
rest is skipped, and every skip is listed so the count can be reconciled.

RESUMABLE, because 85 GB over one connection will be interrupted. A file already present with the
right size is skipped; a partial download lands as `.part` and is only renamed once the length
matches.
"""
import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (MIRROR_ROOT, COMPLETE_MARKER, SUMS_FILE, Pacer, host_of, http_open, human,
                    iter_tree, load_mirror, long_path, scan_tree, sha256_file, sums_line)
# ALIASED, because this module defines a write_marker() of its own and a plain import would
# be shadowed by it -- which is exactly what happened until 2026-09-23: the local function
# called `write_marker(...)` meaning the library's, reached ITSELF, and every run that got as
# far as the marker recursed until memory gave out. mirror.py had it right all along.
from common import write_marker as common_write_marker

META = "https://archive.org/metadata/%s"
DL = "https://archive.org/download/%s/%s"

# Formats the Archive generates about an item rather than files the uploader gave it.
DERIVED = {"Metadata", "Archive BitTorrent", "Item Tile", "JSON", "Log",
           "Item Image", "Thumbnail", "Web ARChive GZ"}


def get_metadata(item):
    with http_open(META % item, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch(url, dest, expect, log):
    """-> (ok, bytes, md5). Resumable, because one file here is 85 GB.

    RESUME MATTERS MORE THAN ELEGANCE AT THIS SIZE. archive.org/details/bullfreeware is a single
    `packages.tar` of 85 045 MB. Without resume an interruption at 80 GB throws away 80 GB, and
    over a night on a domestic line an interruption is not a risk but a schedule.

    So a `.part` that already exists is continued with a Range request. The Archive honours ranges
    -- checked, it answers 206 with Content-Range -- and a server that ignores the header and
    replies 200 is detected and the file restarted rather than silently corrupted by appending a
    second copy of the beginning.

    THE MD5 IS THEN COMPUTED FROM THE FINISHED FILE ON DISK, not from the bytes that went past.
    Hashing only the resumed portion would produce a digest of nothing in particular; and reading
    85 GB back to check it against the Archive's own MD5 is exactly the check worth having.
    """
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    if have and expect and have >= expect:
        have = 0                      # nonsense left over; start again
    extra = None
    if have:
        # extra_headers goes through request_headers(), so the Range is added to the
        # identity rather than replacing it.
        extra = {"Range": "bytes=%d-" % have}
        log("  resuming %s at %s" % (os.path.basename(dest), human(have)))
    with http_open(url, timeout=300, extra_headers=extra) as r:
        if have and r.status != 206:
            # The server ignored the Range. Appending now would duplicate the head of the file.
            log("  server ignored Range (HTTP %s) -- restarting %s"
                % (r.status, os.path.basename(dest)))
            have = 0
        mode = "ab" if have else "wb"
        got = have
        with io.open(tmp, mode) as fh:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
    if expect and got != expect:
        os.replace(tmp, dest + ".suspect")
        log("SHORT %s: %d of %d bytes" % (os.path.basename(dest), got, expect))
        return False, got, None
    h = hashlib.md5()
    with io.open(tmp, "rb") as fh:
        while True:
            b = fh.read(8 << 20)
            if not b:
                break
            h.update(b)
    os.replace(tmp, dest)
    return True, got - have, h.hexdigest()


# Written by this tool and by mirror.py, not by the source. Kept out of the index for the same
# reason mirror.py keeps them out: they change when the bookkeeping changes, and a checksum that
# moves for reasons unrelated to the content is a checksum nobody will trust.


def write_sums(dest_dir, log):
    """Write `.sha256sum` over the finished tree, in the format mirror.py uses.

    NAMED write_sums AND NOT write_index, because common.write_index() is a different
    function -- it writes the CSV index AND derives the sums file from it. This writes only
    the sums file. Two functions with one name in one tree is how the marker bug above got in.

    WHY THIS EXISTS. Until 2026-09-08 this tool wrote no index at all, and the four Internet
    Archive archives -- 3.9 GB then, 89 GB once bullfreeware lands -- had NO LOCAL INTEGRITY
    RECORD. The Archive's MD5 was checked as each file arrived, which is worth having, but it is a
    statement about the download and not about the disk: it cannot detect a bad sector next year,
    a truncated resume, or a file deleted by hand.

    Worse, `verify-content.py` selects archives by the presence of `.sha256sum`, so these four
    were silently absent from every verification pass while the summary line said "every byte
    matches its recorded checksum". Both halves of that are fixed; this is the half that produces
    something to check.

    THE FORMAT IS NOT REIMPLEMENTED HERE. It was, until 2026-09-22, and that copy had drifted
    in four ways at once: it matched an own-file name AT ANY DEPTH rather than only at the top,
    it used os.path.relpath -- which strips a trailing dot, the very defect long_path exists to
    avoid -- it opened files without the long-path prefix, and it wrote the sums line without
    the escape rule. Not one of the four would have surfaced as an error. Each would have
    surfaced as a file that quietly failed to verify, years later, with no way left to tell
    whether the bytes or the record were wrong. It now calls the one implementation.

    THIS IS THE SMALLER OF THE TWO INDEXES mirror.py maintains. It writes `.sha256sum` AND
    `.mirror-index.csv`, and `--verify` reports "Index: none" when only the first exists. So for
    an archive that should be fully at home in the collection, follow a clean run with

        python mirror.py --archive <name> --index

    which is cheap here -- it carries over every hash already recorded below. What this function
    guarantees on its own is that the bytes are never unverifiable, not that every report knows
    about them.
    """
    rows = sorted((rel, sha256_file(full)) for rel, full in iter_tree(dest_dir))
    path = os.path.join(dest_dir, SUMS_FILE)
    with io.open(long_path(path), "w", encoding="utf-8", newline="") as fh:
        for rel, digest in rows:
            fh.write(sums_line(digest, rel))
    log("INDEX wrote %s with %d files" % (path, len(rows)))


def write_marker(dest_dir, item, log):
    """Write `.mirror-complete` in the format mirror.py uses.

    WHY AN IA ARCHIVE NEEDS ONE TOO. Everything downstream keys off this file: `catalogue.py`
    takes its file and byte counts from it, `mirror.py --verify` compares the tree against it, and
    `--fresh` refuses to run while it exists. Without it the four Internet Archive archives showed
    as "None files, 0.0 GB" in the catalogue -- present on disk, invisible to every report.

    The counts are recomputed from the tree rather than carried from the fetch loop, so the
    marker describes what is actually there, including anything a previous partial run left
    behind.

    COUNTED WITH THE SAME FUNCTION THAT LATER CHECKS IT. `mirror.py --verify` measures the tree
    with scan_tree and compares it against the two figures written here, so a second counter --
    which this had, with its own idea of what an own file is and no long-path prefix -- makes a
    marker that is wrong from the moment it is written and an archive that reports a mismatch
    forever, for a discrepancy that exists only between two pieces of our own code.

    AND WRITTEN BY THE SAME WRITER. The header format lived here as a format string and in
    mirror.py as a series of fh.write() calls; the two agreed on the columns and disagreed on the
    line ending, which is how 66 markers in this collection came to be CRLF and 31 LF. The words
    below are this tool's and stay here; the shape of the file is not this tool's business.
    """
    n, b = scan_tree(dest_dir)
    common_write_marker(
        os.path.join(dest_dir, COMPLETE_MARKER),
        {"archive": os.path.basename(dest_dir.rstrip(os.sep)),
         "source": "https://archive.org/details/%s" % item,
         "completed": time.strftime("%Y-%m-%d %H:%M:%S"),
         "files": n,
         "bytes": b},
        "Fetched with ia-item-fetch.py, NOT crawled. Completeness is measured against the item's\n"
        "own file list from https://archive.org/metadata/%s -- an exact manifest, not a guessed\n"
        "directory listing -- and every file's MD5 was compared with the Archive's as it landed.\n"
        "Archive-generated files (*_files.xml, *_meta.xml, *_meta.sqlite, *_archive.torrent) are\n"
        "deliberately not taken; the item record is kept as IA-METADATA.json.\n"
        "\n"
        "`--verify` compares the tree against the two figures above. See PROVENANCE.md beside\n"
        "this file for what the archive is and how it was checked." % item)
    log("MARKER wrote %s: %d files, %d bytes" % (COMPLETE_MARKER, n, b))


def _retired_for(archive):
    """-> f(member name) giving the reason it was removed, or None for everything.

    IMPORTED, NEVER COPIED. A second copy of this list is a list that disagrees with the first one
    the day somebody edits only one of them, and the whole value of RETIRED is that exactly one
    place answers "what did we remove, and why".

    Failing open -- {} on any error -- is the deliberate choice: the worst case is a re-download,
    which costs bandwidth. Failing closed would mean an unreadable mirror.py silently stops files
    from being fetched, and a mirror that is short for a reason nobody can see is the one outcome
    this collection spends all its effort avoiding.

    THE MATCHING IS mirror.py's OWN is_retired(), not a second dictionary built here. That
    copy spelled the comparison out by hand, which meant two implementations of "is this the
    same path" for one register, for the sake of a dictionary lookup over five entries.
    """
    try:
        mod = load_mirror()
    except Exception as exc:                                    # noqa: BLE001
        print("  WARNING: RETIRED not readable from mirror.py (%s) -- nothing is held back"
              % str(exc)[:60], flush=True)
        return lambda _name: None
    return lambda name: mod.is_retired(archive, name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--item", required=True, help="the archive.org identifier")
    ap.add_argument("--archive", required=True, help="directory name under --root")
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-free-gb", type=float, default=1.0)
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds between files. The Archive sets no Crawl-delay for /download/; "
                         "this is here for courtesy on a long run.")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    dest_dir = os.path.join(root, args.archive)
    logdir = os.path.join(root, "logs")
    os.makedirs(logdir, exist_ok=True)
    logf = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def log(t):
        logf.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), t))
        logf.flush()
        print(t, flush=True)

    log("START item=%s -> %s" % (args.item, dest_dir))
    meta = get_metadata(args.item)
    if not meta.get("files"):
        sys.exit("no such item, or it has no files: %s" % args.item)

    md = meta.get("metadata", {})
    log("  title    : %s" % md.get("title", ""))
    log("  uploader : %s   added %s" % (md.get("uploader", "?"), md.get("publicdate", "?")))
    log("  licence  : %s" % (md.get("licenseurl") or md.get("rights") or "(none stated)"))

    # THE HARD FORM OF A DELIBERATE REMOVAL, and this tool had no answer to it until 2026-09-12.
    # It skips what is already on disk, which means a file deleted ON PURPOSE is a file it fetches
    # again -- and an Internet Archive item is exactly where that bites, because the members are
    # large. ia-bullfreeware/packages.tar is 85.04 GB; unpack it, delete the container, and the
    # next refresh of this item quietly downloads all 85 GB back.
    #
    # mirror.py's RETIRED is the one list that answers "what did we remove, and why" for the whole
    # collection, so this reads THAT rather than growing a second one. http-subset-fetch.py has
    # done the same since 2026-09-07; the note there says the list lives in mirror.py "so every
    # fetching tool reads the same one", which was true of one tool out of five.
    retired = _retired_for(args.archive)
    want, skipped, held_back = [], [], []
    for f in meta["files"]:
        why = retired(f["name"])
        if why is not None:
            held_back.append((f["name"], why))
        elif f.get("format") in DERIVED:
            skipped.append((f["name"], f.get("format")))
        else:
            want.append(f)
    for n, why in held_back:
        log("  RETIRED, not fetched: %s" % n)
        log("      %s" % why)
    total = sum(int(f.get("size") or 0) for f in want)
    log("  %d files to take, %s; %d Archive-generated files skipped"
        % (len(want), human(total), len(skipped)))
    for n, fmt in skipped[:8]:
        log("     skip %-46s (%s)" % (n[:46], fmt))

    if args.dry_run:
        for f in sorted(want, key=lambda x: -int(x.get("size") or 0))[:12]:
            log("     %10s  %s" % (human(int(f.get("size") or 0)), f["name"][:70]))
        log("Dry run -- nothing fetched.")
        return 0

    os.makedirs(dest_dir, exist_ok=True)
    # The record this run can be checked against later, kept before a single byte is fetched.
    io.open(os.path.join(dest_dir, "IA-METADATA.json"), "w", encoding="utf-8").write(
        json.dumps(meta, indent=1, sort_keys=True))

    import shutil
    # ONE PACER FOR THE RUN, not one per file: a pacer with no previous request recorded never
    # waits, so one made inside the loop would pace nothing. It also fixes what `--delay` means
    # -- a RATE, "not more often than every N seconds against archive.org", so the minutes an
    # 85 GB member takes count towards the pause instead of the pause being added on top of them.
    pacer = Pacer(args.delay)

    ok = have = bad = 0
    done = 0
    t0 = time.time()
    for n, f in enumerate(sorted(want, key=lambda x: x["name"]), 1):
        name = f["name"]
        size = int(f.get("size") or 0)
        out = os.path.join(dest_dir, name.replace("/", os.sep))
        if os.path.exists(out) and (not size or os.path.getsize(out) == size):
            have += 1
            continue
        if shutil.disk_usage(root).free < args.min_free_gb * 1e9:
            log("DISK FLOOR: under %.1f GB free -- stopping." % args.min_free_gb)
            break
        url = DL % (args.item, urllib.parse.quote(name))
        # WAITED BEFORE THE REQUEST, not after it: the failure branch below `continue`s, so the
        # sleep at the end of the loop was skipped for exactly the files that had just made the
        # server work hardest. A file already on disk and a run stopped by the disk floor are
        # above this line and stay unpaced -- neither asks the Archive anything.
        pacer.wait(host_of(url))
        try:
            res = fetch(url, out, size, log)
        except Exception as exc:                               # noqa: BLE001
            bad += 1
            log("FAIL %s :: %s" % (name, exc))
            continue
        if res[0]:
            ok += 1
            done += res[1]
            if f.get("md5") and res[2] != f["md5"]:
                # The Archive's own MD5, written when the item was created. A mismatch here is
                # not our arithmetic disagreeing with itself.
                log("MD5 MISMATCH %s: got %s, metadata says %s" % (name, res[2], f["md5"]))
                bad += 1
        else:
            bad += 1
        if n % 25 == 0 or size > 1e9:
            log("  %d/%d  ok %d  present %d  bad %d  %s  (%.1f MB/s)"
                % (n, len(want), ok, have, bad, human(done),
                   done / 1e6 / max(time.time() - t0, 1e-9)))

    log("DONE fetched %d, already present %d, failed %d, %s in %.0f min"
        % (ok, have, bad, human(done), (time.time() - t0) / 60))

    if bad:
        # An index over a tree with known-bad files would record the damage as if it were the
        # truth, and a marker would claim the archive is complete. Fix the fetch first.
        log("NOT writing .sha256sum or .mirror-complete: %d file(s) failed or mismatched." % bad)
    else:
        write_sums(dest_dir, log)
        write_marker(dest_dir, args.item, log)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
