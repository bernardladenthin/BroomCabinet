# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fetch what an archive's OWN manifest names and the crawl could not reach.

WHY A CRAWLER IS NOT ENOUGH, and this is the case that shows it plainly. On
gatekeeper.dec.com, `.../SRC/research-reports/SRC-021-html/` does not serve a directory listing --
it serves the research paper. A crawler can therefore see only what that PAGE links: not
`evolve.css`, not `evolve.html`, not the backup files ending in `~`, not the contents of a
subdirectory confusingly named `icons.gif/`. Those files exist, answer 200, and are invisible to
any amount of crawling, because there is no listing anywhere that names them.

The archive's own `Index-byname` names all of them. So the manifest, not the crawl, is the
authority for this archive -- the same relationship as bitsavers' .tar.txt and bullfreeware's
.sfv, and the reason this collection keeps those files rather than treating them as clutter.

    python manifest-fetch.py --archive zx-gatekeeper-dec \
        --manifest Index-byname --prefix /pub/ --base http://ftp.zx.net.nz/pub/archive/gatekeeper.dec.com/

Skips anything already on disk, so it is safe to re-run and cheap when there is nothing to do.
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

from common import (COMPLETE_MARKER, MIRROR_ROOT, Pacer, exists, host_of, http_get,
                    read_marker, scan_tree)
from common import write_marker as common_write_marker

# `<date> <time> <size><unit> <absolute path>` -- gatekeeper's Index-byname shape. The size is
# rounded to a unit and is deliberately not parsed: this tool needs names, not figures.
LINE = re.compile(r"^\s*\S+\s+\S+\s+[\d.]+[kKmMgGbB]?\s+(/\S.*)$")


def write_marker(base_dir, archive, base_url, source, named, gone, failed):
    """Mark an archive that exists ONLY as a URL-list fetch. Refuses to replace another's.

    WHY THIS IS NOT mirror.py's JOB HERE. An archive it never crawled has no marker, and
    everything downstream keys off that file: catalogue.py takes its counts from it, and without
    one the archive reads `None files, 0.0 GB` -- on disk and invisible to every report. That is
    the same hole ia-item-fetch.py closed for the Internet Archive items, for the same reason,
    and the marker is written with the same library function so the two cannot drift in format.

    IT REFUSES TO OVERWRITE SOMEBODY ELSE'S. A manifest fetch is often a TOP-UP of an archive
    mirror.py crawled, and that marker is mirror.py's record of its own run -- replacing it would
    throw away the crawl's failure count and duration and put this tool's name on another's work.

    ITS OWN, THOUGH, IT REPLACES, and the first version got that wrong: it refused every existing
    marker, so a second run over the same archive -- four more files added to a list-fetched
    tree -- left the counts describing the tree as it was before. A marker that is stale is worse
    than one that is missing, because --verify then reports a mismatch that is nobody's fault.
    OURS IS RECOGNISED BY A FIELD ONLY THIS TOOL WRITES, `named-by-the-list`. Not by the prose,
    which a person may edit, and not by a timestamp, which says nothing about who.

    COUNTED WITH THE SAME FUNCTION THAT LATER CHECKS IT, for the reason ia-item-fetch.py records:
    a second counter with its own idea of what an own file is makes a marker that is wrong from
    the moment it is written.
    """
    path = os.path.join(base_dir, COMPLETE_MARKER)
    if exists(path) and "named-by-the-list" not in read_marker(path):
        print("  MARKER LEFT ALONE: %s already exists and this tool did not write it. It belongs "
              "to whatever did -- for a crawled archive that is mirror.py, and its run is not "
              "this one." % path)
        return
    n, b = scan_tree(base_dir)
    common_write_marker(
        path,
        {"archive": archive,
         "source": base_url,
         "completed": time.strftime("%Y-%m-%d %H:%M:%S"),
         "files": n,
         "bytes": b,
         "named-by-the-list": named,
         "gone-from-the-source": gone,
         "failed": failed},
        "Fetched with manifest-fetch.py from a URL LIST, NOT crawled. The source serves no "
        "directory listing this tool could follow -- so completeness here means `everything the "
        "list named`, and the list is only as complete as whatever produced it. That is a weaker "
        "claim than a crawl's and is why it is spelled out.\n"
        "\n"
        "`--verify` compares the tree against the two figures above. See PROVENANCE.md beside "
        "this file for where the list came from and what it could not name.")
    print("  wrote %s: %d files, %d bytes" % (COMPLETE_MARKER, n, b))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--manifest",
                    help="file inside the archive that lists its contents, in the "
                         "`<date> <time> <size> <path>` form gatekeeper.dec.com publishes")
    ap.add_argument("--url-list", metavar="PATH",
                    help="instead of --manifest: a file of absolute URLs, one per line. For a "
                         "store that cannot be enumerated at all -- novasareforever.org answers "
                         "403 to every directory under /user/archive/, and its filenames exist "
                         "only as hrefs on the catalogue pages")
    ap.add_argument("--base", required=True, help="URL the manifest's paths are relative to")
    ap.add_argument("--prefix", default="/",
                    help="only take manifest paths starting with this (default: everything)")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--marker", action="store_true",
                    help="write .mirror-complete afterwards. For an archive that exists "
                         "ONLY as a URL-list fetch: without a marker catalogue.py reports "
                         "it as `None files, 0.0 GB` -- present on disk, invisible to every "
                         "report. Off by default because a top-up of a CRAWLED archive must "
                         "leave mirror.py's own marker alone, and this refuses to overwrite "
                         "one that is already there.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base_dir = os.path.join(args.root, args.archive)
    if not args.manifest and not args.url_list:
        sys.exit("give either --manifest or --url-list")
    if args.manifest and args.url_list:
        sys.exit("--manifest and --url-list are alternatives, not both")

    base_url = args.base.rstrip("/") + "/"
    named = []

    if args.url_list:
        # Paths are derived from the URL's tail after --base, so the local tree mirrors the
        # server's layout rather than flattening it.
        for line in io.open(args.url_list, encoding="utf-8", errors="replace"):
            u = line.strip()
            if not u or u.startswith("#"):
                continue
            if not u.startswith(base_url):
                print("  OUTSIDE THE BASE, skipped: %s" % u[:78])
                continue
            rel = urllib.parse.unquote(u[len(base_url):])
            if rel.startswith(args.prefix.lstrip("/")) or args.prefix == "/":
                named.append(rel)
    else:
        man = os.path.join(base_dir, args.manifest)
        if not exists(man):
            sys.exit("no manifest at %s" % man)
        for line in io.open(man, encoding="utf-8", errors="replace"):
            m = LINE.match(line)
            if m and m.group(1).startswith(args.prefix):
                named.append(m.group(1).lstrip("/"))

    todo = [r for r in named
            if not exists(os.path.join(base_dir, r.replace("/", os.sep)))]
    print("  %s: the %s names %d paths under %s, %d are missing"
          % (args.archive, "URL list" if args.url_list else "manifest",
             len(named), args.prefix, len(todo)), flush=True)

    if args.dry_run:
        for r in todo[:20]:
            print("     %s" % r)
        if len(todo) > 20:
            print("     ... and %d more" % (len(todo) - 20))
        return 0

    # ONE PACER FOR THE RUN, made here and not in the loop: the pause is about the INTERVAL
    # between two requests, and a pacer created per file has no previous request to measure from
    # and would never wait. It also changes what `--delay` means, for the better -- "not more
    # often than every N seconds" rather than "idle N seconds after every request", so a fetch
    # that took longer than the delay has already paid it instead of paying it twice.
    pacer = Pacer(args.delay)

    ok = gone = failed = 0
    total = 0
    for rel in todo:
        url = base_url + "/".join(urllib.parse.quote(p) for p in rel.split("/"))
        out = os.path.join(base_dir, rel.replace("/", os.sep))
        # WAITED ONCE BEFORE THE REQUEST rather than in each of the three branches below. Every
        # one of them -- fetched, 404, failed -- had its own sleep, because every one of them
        # cost the server a request; asking before covers all three and cannot be forgotten in a
        # fourth.
        pacer.wait(host_of(url))
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            body, _headers = http_get(url, timeout=120)
        except urllib.error.HTTPError as e:
            # A manifest describes the ORIGINAL. A 404 here means the file did not survive the
            # mirroring, which is a fact about the copy and not a failure of this run.
            gone += 1
            print("  GONE HTTP %s  %s" % (e.code, rel), flush=True)
            continue
        except Exception as exc:                               # noqa: BLE001
            failed += 1
            print("  FAIL   %s :: %s" % (rel, str(exc)[:60]), flush=True)
            continue
        with io.open(out, "wb") as fh:
            fh.write(body)
        ok += 1
        total += len(body)
        if ok % 25 == 0:
            print("  %d/%d, %.1f MB" % (ok, len(todo), total / 1e6), flush=True)

    print("  DONE fetched %d, gone from the source %d, failed %d, %.1f MB"
          % (ok, gone, failed, total / 1e6))

    if args.marker:
        write_marker(base_dir, args.archive, base_url, args.url_list or args.manifest,
                     len(named), gone, failed)
    elif ok:
        print("  Next: mirror.py --archive %s --index, then bring the marker up to date."
              % args.archive)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
