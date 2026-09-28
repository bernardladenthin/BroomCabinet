# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Mirror misterhayden.com/Stevens/ -- a flat Apache autoindex of AIX/RS-6000 procedure documents.

WHY NOT mirror.py. Two reasons, both about this host rather than about the tool. The site's TLS
chain is incomplete: the leaf validates but the issuer is not served, so every stdlib client refuses
it and mirror.py logged "1 unreadable listings" and stopped. And plain http redirects to https, so
there is no unencrypted way around it.

ABOUT THE DISABLED VERIFICATION. Turning verification off means the origin is not authenticated,
and that is a real loss, not a formality -- so it is compensated rather than waved away. Every
response is checked for the shape it should have (HTML that is really HTML, non-empty bodies), the
listing is fetched once and the file set derived from it, and the SHA-256 of everything retrieved is
written next to the files. If this were credentials or executable content the trade would be
unacceptable; for public read-only text about 25-year-old hardware, with the alternative being no
copy at all before the domain lapses on 2026-10-08, it is the better of two imperfect options.

NOTHING RUNS ON IMPORT, and that is not tidiness. This file used to be a script body at module
level with no main() and no argparse, so `python autoindex-tls-broken.py --help` did not print
help -- it fetched the whole site. CI runs exactly that line over every .py in this directory,
which would have turned one push into an unannounced crawl of somebody's private server.

    python autoindex-tls-broken.py                  # one request for the listing, then a plan
    python autoindex-tls-broken.py --apply          # fetch
"""
import argparse
import hashlib
import html
import io
import os
import re
import sys
import urllib.parse
import urllib.request

from common import MIRROR_ROOT, UNSAFE, http_get, unverified_context

BASE = "https://misterhayden.com/Stevens/"
SUBDIR = os.path.join("misterhayden", "Stevens")

A = re.compile(r'<a href="([^"?][^"]*)"', re.I)


def entries(text):
    """The file list, from ABSOLUTE hrefs.

    The autoindex writes `/Stevens/L3Guide.html`, not relative hrefs, so a filter that drops
    everything starting with `/` drops the entire file list -- which is what the first attempt
    did, reporting 0 entries against a 46 KB listing. Keep what is under /Stevens/, drop the
    parent link and the /_autoindex/ presentation assets.
    """
    names, seen = [], set()
    for href in A.findall(text):
        if href.startswith(("http", "..", "#")) or href in ("/", "/Stevens/"):
            continue
        if href.startswith("/_autoindex/") or href.endswith("/"):
            continue
        if not href.lower().startswith("/stevens/"):
            continue
        n = urllib.parse.unquote(href.split("/")[-1])
        if n in seen:
            continue
        seen.add(n)
        names.append((href, n))
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=MIRROR_ROOT,
                        metavar="PATH", help="the mirror root; the copy lands in %s under it"
                                             % SUBDIR)
    parser.add_argument("--base", default=BASE, metavar="URL", help="the autoindex to read")
    parser.add_argument("--apply", action="store_true",
                        help="fetch the files. Without it only the listing is read")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    dest = os.path.join(args.root, SUBDIR)
    ctx = unverified_context()
    body, _hdr = http_get(args.base, context=ctx)
    text = html.unescape(body.decode("utf-8", "replace"))
    if "<a href" not in text.lower():
        print("REFUSED: listing does not look like an autoindex; refusing to guess")
        return 2

    names = entries(text)
    print("listing: %d entries -> %s\n" % (len(names), dest), flush=True)
    if not args.apply:
        for _href, name in sorted(names, key=lambda t: t[1])[:20]:
            print("    %s" % name)
        if len(names) > 20:
            print("    ... and %d more" % (len(names) - 20))
        print("\n  one request was made, for the listing. --apply fetches the files.")
        return 0

    os.makedirs(dest, exist_ok=True)
    with io.open(os.path.join(dest, "_index.html"), "wb") as fh:
        fh.write(body)

    sums, ok, failed, total = [], 0, 0, 0
    for i, (href, name) in enumerate(sorted(names, key=lambda t: t[1]), 1):
        safe = UNSAFE.sub("_", name).rstrip(". ")
        path = os.path.join(dest, safe)
        if os.path.exists(path):
            continue
        try:
            data, _h = http_get(urllib.parse.urljoin(args.base, href), context=ctx)
        except Exception as exc:
            failed += 1
            print("  FAIL %-52s %s" % (name[:52], exc), flush=True)
            continue
        if not data:
            failed += 1
            print("  EMPTY %s" % name[:60], flush=True)
            continue
        with io.open(path, "wb") as fh:
            fh.write(data)
        sums.append("%s  %s" % (hashlib.sha256(data).hexdigest(), safe))
        ok += 1
        total += len(data)
        if i % 20 == 0:
            print("  %d/%d  ok %d  %.1f MB" % (i, len(names), ok, total / 1e6), flush=True)

    with io.open(os.path.join(dest, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sorted(sums)) + "\n")
    print("\nfetched %d, failed %d, %.2f MB" % (ok, failed, total / 1e6))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
