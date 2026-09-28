# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Mirror csiph.com's photo gallery, and settle whether it duplicates ps-2.kev009.com.

WHY ONLY THE GALLERY. csiph.com is not a file archive -- it is Kevin Bowling's public NNTP server
for comp.sys.ibm.ps2.hardware. Of the three things it serves over HTTP, the daily INN statistics
reports have no archival value and the Usenet corpus is not reachable over HTTP at all. The
gallery is 43 files, 11 166 403 bytes, exhaustively enumerated.

THE QUESTION THIS ALSO ANSWERS. 25 of the 43 sit under Users/kev009/ in AIX/, RS6000/, benchnet/
and housenet/ subfolders. That is the same kev009 whose site is already mirrored here as a 332 GB
archive, so these may be duplicates. That was called "a provenance inference, not a measurement" --
at 10.65 MB it can simply be measured, so it is: every file is hashed and the digests compared
against ps-2.kev009.com's own manifest.

POLITENESS. robots.txt asks for Crawl-delay: 2 and that is honoured -- 2.5 s between requests, one
connection. It disallows only /search.

NOTHING RUNS ON IMPORT. This file used to be a script body at module level, so
`python nginx-autoindex-gallery.py --help` did not print help -- it walked and fetched the whole
gallery. CI runs exactly that line over every .py here, at no crawl delay anyone agreed to.

    python nginx-autoindex-gallery.py               # enumerate only
    python nginx-autoindex-gallery.py --apply       # fetch, then compare against kev009
"""
import argparse
import csv
import hashlib
import html
import io
import os
import re
import sys
import urllib.parse

from common import MIRROR_ROOT, INDEX_FILE, UNSAFE, Pacer, host_of, http_get

BASE = "https://csiph.com/gallery/albums/"
SUBDIR = "csiph-gallery"
KEV_SUBDIR = "ps-2.kev009.com"
DELAY = 2.5

A = re.compile(r'<a href="([^"]+)"', re.I)

# THE RATE STAYS HERE. THE ARITHMETIC OF HONOURING IT DOES NOT.
#
# robots.txt on this host asks for a Crawl-delay, and that promise is made to ONE operator: it
# must not live in a shared helper where another caller would inherit it without knowing, or drop
# it without noticing. `DELAY` is therefore still this file's own number, and that part of the
# old comment here was right.
#
# What was wrong was keeping a private copy of the WAITING. Measured 2026-09-25: 41 `time.sleep`
# calls across 17 tools, in three different meanings of "delay", and this file held the only
# correct one -- every other tool slept the full delay after each request instead of counting the
# request against it. A mechanism that only one of seventeen callers got right is a mechanism that
# belongs in the library. `common.Pacer` is that arithmetic and nothing else; the rate is still
# ours.
_pacer = [None]


def get(url, delay):
    """One request, not before `delay` seconds have passed since the last one to that host."""
    if _pacer[0] is None or _pacer[0].pause != delay:
        _pacer[0] = Pacer(delay)
    _pacer[0].wait(host_of(url))
    data, _hdr = http_get(url)
    return data


def walk(url, base, delay, seen):
    """Recursive nginx-autoindex walk -> [file urls]."""
    if url in seen:
        return []
    seen.add(url)
    out = []
    body = get(url, delay).decode("utf-8", "replace")
    for href in A.findall(body):
        href = html.unescape(href)
        if href.startswith(("http", "/", "..", "?", "#")):
            continue
        full = urllib.parse.urljoin(url, href)
        if not full.startswith(base):
            continue
        if href.endswith("/"):
            out += walk(full, base, delay, seen)
        else:
            out.append(full)
    return out


def compare_with_kev(sums, kev_root):
    """The duplicate question, measured rather than inferred."""
    idx = os.path.join(kev_root, INDEX_FILE)
    print("\nkev009 manifest present:", os.path.exists(idx))
    if not os.path.exists(idx):
        return
    kev_h, kev_size = set(), {}
    with io.open(idx, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("sha256") or "").strip().lower()
            if d:
                kev_h.add(d)
            try:
                kev_size.setdefault(int(row["size"]), []).append(row["path"])
            except (KeyError, ValueError):
                pass
    print("  %d digests, %d distinct sizes" % (len(kev_h), len(kev_size)))
    dup = [(p, h) for h, p, _n in sums if h in kev_h]
    same_size = [(p, n) for h, p, n in sums if n in kev_size and h not in kev_h]
    print("\n  IDENTICAL (same sha256) : %d of %d" % (len(dup), len(sums)))
    for p, _h in dup[:20]:
        print("      ", p)
    print("  same size, different bytes: %d" % len(same_size))
    for p, n in same_size[:10]:
        print("      %-58s %d B  <-> %s" % (p[:58], n, kev_size[n][0][:40]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=MIRROR_ROOT,
                        metavar="PATH",
                        help="the mirror root; the copy lands in %s under it, and %s under it is "
                             "the archive compared against" % (SUBDIR, KEV_SUBDIR))
    parser.add_argument("--base", default=BASE, metavar="URL", help="the gallery to walk")
    parser.add_argument("--delay", type=float, default=DELAY, metavar="S",
                        help="seconds between requests; robots.txt asks for 2 (default %.1f)"
                             % DELAY)
    parser.add_argument("--apply", action="store_true",
                        help="fetch the files. Without it only the listings are walked")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    dest = os.path.join(args.root, SUBDIR)
    files = walk(args.base, args.base, args.delay, set())
    print("enumerated %d files -> %s\n" % (len(files), dest), flush=True)
    if not args.apply:
        for u in sorted(files)[:20]:
            print("    %s" % urllib.parse.unquote(u[len(args.base):]))
        if len(files) > 20:
            print("    ... and %d more" % (len(files) - 20))
        print("\n  only the listings were read. --apply fetches the files.")
        return 0

    sums, total = [], 0
    for i, u in enumerate(sorted(files), 1):
        rel = urllib.parse.unquote(u[len(args.base):])
        parts = [UNSAFE.sub("_", p) for p in rel.split("/") if p]
        path = os.path.join(dest, "albums", *parts)
        if os.path.exists(path):
            continue
        data = get(u, args.delay)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "wb") as fh:
            fh.write(data)
        sums.append((hashlib.sha256(data).hexdigest(), "albums/" + "/".join(parts), len(data)))
        total += len(data)
        if i % 10 == 0:
            print("  %d/%d  %.2f MB" % (i, len(files), total / 1e6), flush=True)

    with io.open(os.path.join(dest, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join("%s  %s" % (h, p)
                           for h, p, _n in sorted(sums, key=lambda t: t[1])) + "\n")
    print("\nfetched %d files, %d bytes" % (len(sums), total))

    compare_with_kev(sums, os.path.join(args.root, KEV_SUBDIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
