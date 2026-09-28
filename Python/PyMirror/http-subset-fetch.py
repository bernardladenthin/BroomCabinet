# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Fetch the AIX releases from fsck.technology that this collection does not hold.

WHAT IS TAKEN AND WHY THIS IS A SUBSET. The tree offers 549 files not matching any filename we
hold, 59.27 GB measured by Content-Length. That figure is misleading and the reason is worth
stating: a filename diff counts AIX 5.2 and 5.3 media as new because fsck's disc images are named
differently from our ISOs, not because the release is missing. Compared by RELEASE instead:

    held here already : AIX 4.3.3 (2.0 GB), 5.2 + 5.3 (26 GB), 6.1, 7.1, 7.2, 7.3, and AIX 1.3
    absent entirely   : AIX 1.2.1, 2.1.1, 2.2.1, 3.2.0, 3.2.5, 4.1.3, 4.1.4, 4.1.5, 4.2.1, 4.3.2, 5.1

So the 39.7 GB of 4.3.3/5.2/5.3 discs are duplicates of releases already held and are left, and
the ~19.6 GB below are releases with no copy in this collection at all. AIX 1.3.0 is taken despite
our holding 36 MB of it, because fsck has 153 files against our diskette subset -- a more complete
copy of the same release is not a duplicate.

That the result lands within half a gigabyte of the round-2 report's independently derived
"19.05 GB not already held" is the reassurance that the cut is the right one.

NOTHING RUNS ON IMPORT. This file used to be a script body at module level, so
`python http-subset-fetch.py --help` did not print help -- it read mirror.py, resolved the URL
list and started fetching gigabytes. CI runs exactly that line over every .py here.

    python http-subset-fetch.py --list fsck-new.txt           # what it would take
    python http-subset-fetch.py --list fsck-new.txt --apply   # take it
"""
import argparse
import io
import os
import sys
import urllib.parse
import urllib.request

from common import MIRROR_ROOT, http_open, load_mirror

SUBDIR = "fsck-aix-media"
ARCHIVE = "fsck-vendors"
ORIGIN = "https://fsck.technology/software/"

WANT = (
    "PS2/IBM AIX 1.2.1 for PS2",
    "PS2/IBM AIX 1.3.0 for PS2",
    "IBM RT/IBM AIX 2.1.1 for IBM RT",
    "IBM RT/IBM AIX 2.2.1",
    "RS6000/IBM AIX 3.2.0",
    "RS6000/IBM AIX 3.2.5",
    "RS6000/IBM AIX 4.1.3",
    "RS6000/IBM AIX 4.1.5",
    "RS6000/IBM AIX 4.2.1",
    "RS6000/IBM AIX 4.3.2",
    "RS6000/IBM AIX 5.1",
    "Apple Network Server/IBM AIX 4.1.4",
)


def retired_urls(log):
    """THE HARD FORM OF A DELIBERATE REMOVAL.

    This tool skips files it already has, which means a file deleted on purpose is a file it
    downloads again. `NeXT/next.68k.org Archive/next.68k.org.tar` was removed on 2026-09-07 after
    being unpacked into the `next-68k-org` archive; without this, the next run fetches 37.86 GB of
    a tar whose contents are already held, indexed and verified. The list lives in mirror.py so
    every fetching tool reads the same one.

    THIS ONE DOES NOT FAIL OPEN. The tools that read RETIRED to decide whether to SKIP a file
    return {} when mirror.py cannot be read, because the cost of being wrong there is a download.
    Here the list is the only thing standing between a run and 37.86 GB it already holds, so an
    unreadable register stops the run instead of quietly starting it.
    """
    return load_mirror().retired_urls(ARCHIVE, ORIGIN)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=MIRROR_ROOT,
                        metavar="PATH", help="the mirror root; the copy lands in %s under it"
                                             % SUBDIR)
    parser.add_argument("--list", dest="list_file",
                        default=os.environ.get("URL_LIST"), metavar="FILE",
                        help="one absolute URL per line. THIS FILE IS NOT IN THIS REPOSITORY: it "
                             "is per-job scratch, a listing of the remote tree produced for one "
                             "fetch. $URL_LIST is read when the flag is absent")
    parser.add_argument("--apply", action="store_true",
                        help="fetch. Without it nothing leaves this machine")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    if not args.list_file:
        print("REFUSED: no URL list. Pass --list FILE or set $URL_LIST.")
        return 2
    if not os.path.isfile(args.list_file):
        print("REFUSED: no URL list at %s" % args.list_file)
        return 2
    with io.open(args.list_file, encoding="utf-8") as fh:
        urls = [u.strip() for u in fh if u.strip()]

    retired = retired_urls(print)
    before = len(urls)
    urls = [u for u in urls if u not in retired]
    if len(urls) != before:
        for url, why in retired.items():
            if url not in urls:
                print("RETIRED, not fetched: " + url, flush=True)
                print("    " + why, flush=True)

    todo = []
    for u in urls:
        tail = urllib.parse.unquote(u).split("AIX Install Media/", 1)[-1]
        if any(tail.startswith(w) for w in WANT):
            todo.append((u, tail))
    dest_root = os.path.join(args.root, SUBDIR)
    print("selected %d of %d files -> %s\n" % (len(todo), len(urls), dest_root), flush=True)

    if not args.apply:
        for _u, tail in sorted(todo, key=lambda t: t[1])[:20]:
            print("    %s" % tail)
        if len(todo) > 20:
            print("    ... and %d more" % (len(todo) - 20))
        print("\n  nothing left this machine. --apply fetches.")
        return 0

    ok = skipped = failed = total = 0
    for i, (url, tail) in enumerate(sorted(todo, key=lambda t: t[1]), 1):
        parts = [p for p in tail.split("/") if p not in ("", ".", "..")]
        dest = os.path.join(dest_root, *parts)
        if os.path.exists(dest):
            skipped += 1
            continue
        tmp = dest + ".part"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        claimed = n = 0
        try:
            with http_open(url, timeout=600) as r:
                claimed = int(r.headers.get("Content-Length") or 0)
                with io.open(tmp, "wb") as fh:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
                        n += len(chunk)
        except Exception as exc:
            failed += 1
            print("  FAIL %-60s %s" % (tail[:60], exc), flush=True)
            try:
                os.remove(tmp)
            except OSError:
                pass
            continue
        if claimed and n != claimed:
            print("  SHORT %-59s got %d of %d" % (tail[:59], n, claimed), flush=True)
            os.replace(tmp, dest + ".suspect")
            failed += 1
            continue
        os.replace(tmp, dest)
        ok += 1
        total += n
        if i % 10 == 0 or i == len(todo):
            print("  %d/%d  ok %d  failed %d  skipped %d  %.2f GB"
                  % (i, len(todo), ok, failed, skipped, total / 1e9), flush=True)

    print("\nfetched %d, failed %d, already present %d, %.2f GB"
          % (ok, failed, skipped, total / 1e9))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
