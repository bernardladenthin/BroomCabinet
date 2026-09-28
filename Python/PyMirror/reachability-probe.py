# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Before mirroring anything: can the crawler actually get INTO it, or only to its front door?

    python reachability-probe.py https://host/path/ https://other/path/

WHY THIS EXISTS, AND WHY IT SHOULD HAVE EXISTED SOONER. Twice in one day a fetch of this
collection reported a clean completion over an archive that was almost empty:

  gate.crashing.org   3 files kept where 30 seeded URLs answered 200. The landing page links none
                      of /doc/ppc/, and a seed was walked but never saved.
  os-history.de       184 files where 213 exist. Every branch's index.html 404s while the
                      DIRECTORY answers 200 with an Apache listing.
  unixos2.org         11 files where 32 exist. The pages declare <base href> pointing at the path
                      the site had on ITS ORIGINAL HOST.

Each was found afterwards, by noticing a number that looked too small. That is luck, not method.
A fetch that ends INCOMPLETE announces itself; one that ends COMPLETE over an empty tree does not.

WHAT IT ASKS. One request for the root, then:

  * how many links does the root carry, and how many of them stay under it?
  * does it declare <base href>, and does that base point somewhere this host serves?
  * do the linked subdirectories actually answer?
  * if the root offers almost nothing, is that because the site IS small, or because the tree
    hangs off paths nothing links -- which is what a seed is for?

It fetches the root and HEADs a sample of children. Nothing is mirrored.

WHAT IT CANNOT TELL YOU. That a site has no unlinked subtree. Nothing can: an unlinked tree is
undiscoverable by definition, which is why R14 exists and why a seed comes from reading the site,
not from crawling it.
"""
import argparse
import html as html_mod
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from common import BASE_RE, http_open, http_try

A_RE = re.compile(r'<a\s[^>]*href="([^"]+)"', re.I)
SKIP = ("#", "mailto:", "javascript:", "?")


def get(url, timeout=45):
    with http_open(url, timeout=timeout) as r:
        return r.status, r.read(400000), r.geturl()


def head(url, timeout=30):
    """-> the status alone. http_try never raises, so neither does this."""
    return http_try(url, timeout=timeout, method="HEAD")[0]


def probe(base, sample):
    print("=" * 96)
    print(base)
    try:
        status, body, final = get(base)
    except Exception as exc:                                   # noqa: BLE001
        print("  ROOT UNREACHABLE: %s" % exc)
        print("  -> a mirror run would end INCOMPLETE with one unreadable listing and zero files.")
        return
    text = body.decode("utf-8", "replace")
    print("  root: HTTP %s, %d bytes%s"
          % (status, len(body), "" if final == base else "  (redirected to %s)" % final))

    m = BASE_RE.search(text)
    if m:
        declared = urllib.parse.urljoin(final, m.group(1))
        inside = declared.startswith(base)
        print("  <base href=%r> -> %s   %s"
              % (m.group(1), declared,
                 "inside our root" if inside else "OUTSIDE OUR ROOT -- must be rebased"))
        if not inside:
            print("     mirror.py rebases this onto the mirror root since 2026-09-07. Without "
                  "that, every relative link resolves one level wrong.")
    else:
        print("  no <base href>")

    hrefs = []
    for h in A_RE.findall(text):
        h = html_mod.unescape(h)
        if h.startswith(SKIP) or h in ("../",):
            continue
        hrefs.append(h)
    children = []
    for h in hrefs:
        u = urllib.parse.urljoin(final, h)
        if u.startswith(base) and u != base and u not in children:
            children.append(u)
    dirs = [u for u in children if u.endswith("/")]
    files = [u for u in children if not u.endswith("/")]
    print("  %d links, %d stay under the root: %d look like directories, %d like files"
          % (len(hrefs), len(children), len(dirs), len(files)))

    if not children:
        print("  *** THE ROOT LEADS NOWHERE. Either the site is one page, or its tree hangs off")
        print("      paths nothing links -- in which case a crawl WILL report a clean completion")
        print("      over an empty archive, and a SEED is required. Read the site by hand.")
        return

    tried = (dirs + files)[:sample]
    print("  checking %d of them:" % len(tried))
    good = 0
    for u in tried:
        st = head(u)
        if st == 200:
            good += 1
        print("     %-70s %s" % (u[-70:], st))
    print("  %d of %d answered 200" % (good, len(tried)))
    if good == 0:
        print("  *** NOTHING BELOW THE ROOT ANSWERS. The links exist and the targets do not --")
        print("      the os-history.de pattern. Check whether the DIRECTORY answers where the")
        print("      index page does not.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--sample", type=int, default=8,
                    help="how many children to HEAD (default 8). This is a probe, not a crawl.")
    args = ap.parse_args()
    for u in args.urls:
        probe(u if u.endswith("/") else u + "/", args.sample)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
