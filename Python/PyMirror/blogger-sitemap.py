# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Mirror techsysadm.blogspot.com via its sitemap.

WHY NOT mirror.py's HTML_CRAWL. Blogger's front page is an infinite-scroll widget: the twenty most
recent posts are inlined and the rest arrive over XHR, so a link crawl that starts at / walks the
archive-by-month hubs into a combinatorial fan of `?updated-max=` permutations and still misses
posts. mirror.py reported 0 files and then MARKED THE ARCHIVE COMPLETE, which is the worse half of
that failure -- the marker is rewritten truthfully at the end of this run.

The sitemap is the enumeration Blogger actually publishes, and it is authoritative: /sitemap.xml
indexes /sitemap.xml?page=N, each listing post URLs. Post pages are fetched as served, plus the
static JS/CSS-free HTML; images are followed one level because the QEMU walkthroughs carry
screenshots of the SMS menus.

NOTHING RUNS ON IMPORT. This file used to be a script body at module level, so
`python blogger-sitemap.py --help` did not print help -- it mirrored the whole blog. CI runs
exactly that line over every .py here.

    python blogger-sitemap.py                       # read the sitemaps, then a plan
    python blogger-sitemap.py --apply               # fetch
"""
import argparse
import hashlib
import io
import os
import sys
import http.client
import urllib.error
import urllib.parse
import urllib.request

from common import (MIRROR_ROOT, UNSAFE, extension_for, file_extension, http_get,
                    image_sources, relative_to, sitemap_locations)

BASE = "https://techsysadm.blogspot.com/"
SUBDIR = "techsysadm"


# Content-Type -> extension for the URLs that carry none. Blogger's image URLs end in a sizing
# token (`...=w400-h216-rw`) with no extension at all, so the naive "no extension -> index.html"
# rule labelled 162 WebP images as HTML. Files that lie about what they are is precisely the defect
# audit.py exists to find; do not manufacture it here.


def local(url, dest_root, ctype=None):
    p = urllib.parse.urlparse(url)
    parts = [UNSAFE.sub("_", urllib.parse.unquote(x)) for x in p.path.split("/") if x]
    if not parts:
        parts = ["index.html"]
    # file_extension: splitext answers "." for a segment ending in a dot, which is truthy,
    # so such a name kept no extension at all. It has none -- that is the point.
    if not file_extension(parts[-1]):
        ext = extension_for(ctype)
        parts.append("image" + ext if ext else "index.html")
    return os.path.join(dest_root, p.netloc, *parts)


def post_urls(base, log):
    """Walk the sitemap index down to the post URLs. -> (posts, number of sitemap files)."""
    posts, maps, seen = [], [urllib.parse.urljoin(base, "sitemap.xml")], set()
    while maps:
        m = maps.pop()
        if m in seen:
            continue
        seen.add(m)
        try:
            body = http_get(m)[0].decode("utf-8", "replace")
        except Exception as exc:
            log("  sitemap FAIL %s :: %s" % (m, exc))
            continue
        for loc in sitemap_locations(body):
            (maps if "sitemap" in loc else posts).append(loc)
    return sorted(set(posts)), len(seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=MIRROR_ROOT,
                        metavar="PATH", help="the mirror root; the copy lands in %s under it"
                                             % SUBDIR)
    parser.add_argument("--base", default=BASE, metavar="URL", help="the blog to mirror")
    parser.add_argument("--apply", action="store_true",
                        help="fetch the posts. Without it only the sitemaps are read")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    dest_root = os.path.join(args.root, SUBDIR)
    posts, nmaps = post_urls(args.base, print)
    print("sitemap: %d posts across %d sitemap files -> %s\n" % (len(posts), nmaps, dest_root),
          flush=True)
    if not args.apply:
        for u in posts[:20]:
            print("    %s" % u)
        if len(posts) > 20:
            print("    ... and %d more" % (len(posts) - 20))
        print("\n  only the sitemaps were read. --apply fetches the posts and their images.")
        return 0

    sums, ok, failed, imgs = [], 0, 0, 0
    for i, u in enumerate(posts, 1):
        try:
            data, hdr = http_get(u)
            ctype = hdr.get("Content-Type", "")
        except Exception as exc:
            failed += 1
            print("  FAIL %-56s %s" % (u[-56:], exc), flush=True)
            continue
        dest = local(u, dest_root, ctype)
        if os.path.exists(dest):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with io.open(dest, "wb") as fh:
            fh.write(data)
        sums.append("%s  %s" % (hashlib.sha256(data).hexdigest(),
                                relative_to(dest_root, dest)))
        ok += 1
        # one level of images -- the SMS-menu screenshots are the point of the walkthroughs
        for src in image_sources(data.decode("utf-8", "replace")):
            if not src.startswith("http") or "blogger.com/img" in src:
                continue
            try:
                idata, ihdr = http_get(src)
                ictype = ihdr.get("Content-Type", "")
            # AN IMAGE THAT DID NOT ANSWER, AND NOTHING ELSE. It was `except Exception:
            # continue`, which cannot tell that from a typo in this file -- and a typo there
            # would skip EVERY image silently while the run still reported success. The same
            # shape inverted recheck-decisions.py entirely; found 2026-09-24.
            except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
                continue
            idest = local(src, dest_root, ictype)
            if os.path.exists(idest):
                continue
            os.makedirs(os.path.dirname(idest), exist_ok=True)
            with io.open(idest, "wb") as fh:
                fh.write(idata)
            sums.append("%s  %s" % (hashlib.sha256(idata).hexdigest(),
                                    relative_to(dest_root, idest)))
            imgs += 1
        if i % 20 == 0:
            print("  %d/%d  posts %d  images %d  failed %d"
                  % (i, len(posts), ok, imgs, failed), flush=True)

    with io.open(os.path.join(dest_root, "SHA256SUMS"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sorted(sums)) + "\n")
    print("\nfetched %d posts + %d images, failed %d" % (ok, imgs, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
