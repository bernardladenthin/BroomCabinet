#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Recover a dead host from the Internet Archive, into the same layout mirror.py produces.

WHEN THIS IS THE RIGHT TOOL
    When the origin is gone. mirror.py copies what a server still serves; this reads what the
    Internet Archive kept after it stopped. The two are not variants of one job:

      mirror.py       follows links from a live root, and can be re-run to catch up
      this            works a list obtained from an index, once, and can never be complete

    The result is a SALVAGE, not a mirror, and the marker it produces says so. A mirror can be
    checked against its source; this cannot, because the source is what went missing.

HOW IT FINDS THINGS
    The Wayback CDX API lists every capture of a host. Link-following is useless here -- the
    origin serves nothing to follow -- so the URL list comes from the index instead:

        http://web.archive.org/cdx/search/cdx?url=<domain>&matchType=domain
            &fl=original,timestamp,statuscode,mimetype,length&collapse=urlkey

USAGE
    python wayback-salvage.py --domain download.example.net --root /srv/mirror --archive example
    python wayback-salvage.py --domain ... --root ... --archive ... --dry-run

FIVE THINGS THAT WILL BITE, ALL MEASURED
    1. The `id_` modifier in the replay URL is MANDATORY. Without it the Wayback Machine injects
       its own toolbar into the response, and a binary comes back corrupted -- silently, with a
       200 and a plausible size.
    2. The CDX `length` column is the size of the compressed WARC record, not of the file. Never
       compare a download against it. The real figure is in the `x-archive-orig-content-length`
       response header, which is what this checks.
    3. A row indexed with statuscode 200 can still 404 on replay: the record exists in the index
       and the data node cannot serve it. One of four sampled files behaved that way. Expect a
       nonzero rate and log it rather than treating it as a bug here.
    4. `warc/revisit` rows are deduplication stubs with no payload of their own. They carry
       statuscode `-` and must be filtered out.
    5. Apache's autoindex sort links (`?C=S;O=A` and friends) are captured as separate URLs. They
       are the same page under a different query string -- noise, and they cannot be written to a
       filesystem under a sane name.

VERIFICATION
    Every file is checked against `x-archive-orig-content-length` when the header is present. For
    AIX installp images (`.I`) the first four bytes must be `09 00 6b ea`, the BFF "backup by
    name" magic -- which catches exactly the toolbar-injection failure above.
"""

import argparse
import io
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CDX = ("http://web.archive.org/cdx/search/cdx?url=%s&matchType=domain"
       "&fl=original,timestamp,statuscode,mimetype,length&collapse=urlkey")
REPLAY = "https://web.archive.org/web/%sid_/%s"

UA = "Mozilla/5.0 (compatible; archive-salvage/1.0)"
TIMEOUT = 120
CHUNK = 1 << 20

# Apache mod_autoindex column-sort links. Same page, different query string.
SORT_LINK = re.compile(r"\?C=[NMSD];O=[AD]$", re.I)

# AIX installp / BFF "backup by name" magic.
BFF_MAGIC = b"\x09\x00\x6b\xea"


def fetch(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def cdx_rows(domain):
    """-> [(original, timestamp, status, mimetype, length)] straight from the index."""
    with fetch(CDX % urllib.parse.quote(domain, safe="")) as r:
        body = r.read().decode("utf-8", "replace")
    rows = []
    for line in body.splitlines():
        parts = line.split(" ")
        if len(parts) >= 5:
            rows.append(tuple(parts[:5]))
    return rows


def wanted(rows):
    """-> [(original, timestamp)] worth fetching, plus a per-reason count of what was dropped.

    Kept deliberately generous: directory index pages are not decoration here. On a host that no
    longer exists they are the only surviving record of what each directory held, and of the
    sizes and dates the files had. Dropping them to save a few kilobytes would throw away the
    inventory and keep the inventoried.
    """
    keep, dropped = [], {}
    for original, ts, status, mime, _length in rows:
        why = None
        if status != "200":
            why = "status %s" % status
        elif mime == "warc/revisit":
            why = "revisit stub"
        elif SORT_LINK.search(original):
            why = "autoindex sort link"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
        else:
            keep.append((original, ts))
    return keep, dropped


def local_path(root, original):
    """Map an archived URL onto a path under `root`, host and port stripped."""
    u = urllib.parse.urlsplit(original)
    path = urllib.parse.unquote(u.path)
    if path.endswith("/") or not path:
        path += "index.html"
    parts = [p for p in path.split("/") if p not in ("", ".", "..")]
    return os.path.join(root, *parts)


def long_path(path):
    """Windows refuses paths over 260 characters without the \\\\?\\ prefix.

    Not via os.path.abspath(): normalising strips a trailing dot, which is one of the things the
    prefix exists to preserve.
    """
    if os.name != "nt":
        return path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    path = path.replace("/", "\\")
    return path if path.startswith("\\\\?\\") else "\\\\?\\" + path


def save(original, ts, dest, log):
    """-> (ok, bytes, note). Writes to a .part and renames, so a kill leaves no half file."""
    url = REPLAY % (ts, original)
    tmp = dest + ".part"
    os.makedirs(long_path(os.path.dirname(dest)), exist_ok=True)
    try:
        with fetch(url) as r:
            claimed = r.headers.get("x-archive-orig-content-length")
            n = 0
            head = b""
            with io.open(long_path(tmp), "wb") as fh:
                while True:
                    b = r.read(CHUNK)
                    if not b:
                        break
                    if not head:
                        head = b[:4]
                    fh.write(b)
                    n += len(b)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError) as exc:
        # A row indexed 200 that will not replay is the documented case, not a defect here.
        log("FAIL %s :: %s" % (original, exc))
        try:
            os.remove(long_path(tmp))
        except OSError:
            pass
        return False, 0, "unfetchable"

    note = ""
    if claimed is not None:
        try:
            if int(claimed) != n:
                note = "SIZE claimed %s got %d" % (claimed, n)
        except ValueError:
            pass
    if dest.lower().endswith(".i") and head != BFF_MAGIC:
        note = (note + "; " if note else "") + "NOT-BFF first4=%s" % head.hex()

    if note:
        log("SUSPECT %s :: %s" % (original, note))
        os.replace(long_path(tmp), long_path(dest + ".suspect"))
        return False, n, note
    os.replace(long_path(tmp), long_path(dest))
    return True, n, ""


def human(n):
    for unit in ("B", "K", "M", "G"):
        if abs(n) < 1024 or unit == "G":
            return "%.1f %s" % (n, unit)
        n /= 1024.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--domain", required=True, help="the dead host, e.g. download.example.net")
    ap.add_argument("--root", required=True, help="the mirror tree")
    ap.add_argument("--archive", required=True, help="subdirectory to write into")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched, fetch nothing")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1). The Internet Archive is not a "
                         "CDN; there is no hurry and this runs once")
    args = ap.parse_args()

    root = os.path.join(os.path.abspath(args.root), args.archive)
    logdir = os.path.join(os.path.abspath(args.root), "logs")
    os.makedirs(logdir, exist_ok=True)
    logfile = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def log(text):
        logfile.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        logfile.flush()

    print("Asking the CDX index about %s ..." % args.domain, flush=True)
    rows = cdx_rows(args.domain)
    keep, dropped = wanted(rows)
    print("  %d rows indexed, %d to fetch" % (len(rows), len(keep)))
    for why, n in sorted(dropped.items()):
        print("     dropped %-24s %d" % (why, n))
    if args.dry_run:
        for original, ts in keep[:20]:
            print("     %s  %s" % (ts, original))
        if len(keep) > 20:
            print("     ... and %d more" % (len(keep) - 20))
        print("\nDry run -- nothing fetched.")
        return 0

    log("SALVAGE START %s -> %s  (%d urls)" % (args.domain, root, len(keep)))
    ok = failed = skipped = 0
    total = 0
    t0 = time.time()
    for i, (original, ts) in enumerate(keep, 1):
        dest = local_path(root, original)
        if os.path.exists(long_path(dest)):
            skipped += 1
            continue
        good, n, _note = save(original, ts, dest, log)
        if good:
            ok += 1
            total += n
        else:
            failed += 1
        if i % 10 == 0 or i == len(keep):
            print("  %d/%d  ok %d  failed %d  skipped %d  %s"
                  % (i, len(keep), ok, failed, skipped, human(total)), flush=True)
        time.sleep(args.delay)

    el = time.time() - t0
    print("\n  fetched %d, failed %d, already present %d, %s in %dm%02ds"
          % (ok, failed, skipped, human(total), el // 60, el % 60))
    log("SALVAGE DONE ok=%d failed=%d skipped=%d bytes=%d" % (ok, failed, skipped, total))
    if failed:
        print("  %d could not be recovered -- see logs/%s.log. A row indexed 200 that will not"
              % (failed, args.archive))
        print("  replay is a known Internet Archive condition, not a defect in this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
