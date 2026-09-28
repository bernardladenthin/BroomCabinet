#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Copy a MediaWiki as raw wikitext -- current revisions only -- through its own API.

WHEN THIS IS THE RIGHT TOOL
    When the target is a MediaWiki and a crawler would be the wrong instrument, which is the same
    reasoning as pmwiki-source.py and dokuwiki-source.py beside this file.

    A crawl of a MediaWiki copies RENDERED HTML wrapped in skin, navigation, edit links, category
    footers and a "Retrieved from" line -- and it walks into every `action=history`,
    `action=edit`, `oldid=`, `diff=` and `printable=yes` variant of each page on the way. The
    result is many times larger than the wiki, structurally harder to read, and still not what
    the wiki actually stores.

    MediaWiki will simply hand over what it stores:

        api.php?action=query&list=allpages&apnamespace=N     the page list, 500 at a time
        api.php?action=query&prop=revisions&rvslots=main     the wikitext, FIFTY PAGES per request

    Measured on ndwiki.org: 2 675 pages across every namespace, enumerable in a handful of
    requests and retrievable in about fifty-five more. A crawl of the same wiki would be
    thousands of requests for a worse copy.

CURRENT REVISIONS ONLY, DELIBERATELY
    `Special:Export` is the better-known route and it is the wrong one here: it returns FULL
    PAGE HISTORY unless told otherwise, which for a wiki with 7 877 edits over 2 675 pages means
    fetching roughly three times the content that was asked for. `prop=revisions` without
    `rvlimit` returns exactly one revision -- the current one -- and says so in the reply, which
    is checked rather than assumed (see `--verify-current`).

    History is not lesser; it is a different archive, and taking it by accident is not the same
    as deciding to take it.

THE USER-AGENT MUST NOT BEGIN "Mozilla/"
    This is not a style preference. Measured on ndwiki.org 2026-09-17, one variable at a time:

        Mozilla/5.0 (Windows NT 10.0 ...) Chrome/120   -> proof-of-work challenge page
        Mozilla/5.0 (compatible; archive-mirror/1.0)   -> challenge
        Mozilla/5.0 (compatible; Googlebot/2.1; ...)   -> challenge
        archive-mirror/1.0 (compatible)                -> the actual file
        curl/8.5.0  /  Wget/1.21.4                     -> the actual file

    The strings above are what was sent that day and are left as they were sent; a measurement
    rewritten to match a later rename is no longer a measurement. What the table establishes is
    the SHAPE, not the name: anything beginning `Mozilla/` was challenged and everything else
    was served. `archive-mirror/1.0` was this collection's identifier at the time; on 2026-09-22
    every tool here was changed to the neutral `mirror/1.0`, which has the same shape as the two
    rows that worked.

    Anubis and its relatives exist to stop scrapers that IMPERSONATE BROWSERS. The conventional
    `Mozilla/5.0 (compatible; X)` prefix is a claim this program cannot honestly make, and
    dropping it is more truthful, not less -- it is also what gets served.

--images IS A MANIFEST FETCH, NOT A CRAWL
    `list=allimages` returns, for every uploaded file, its URL, byte size, MIME type and **the
    wiki's own SHA-1**. That is an inventory from the operator's database rather than a reading
    of what some page happens to link, and this collection treats the two as different kinds of
    evidence -- a listing entry is a statement, a page link is a claim.

    The SHA-1 is the part worth having. Every downloaded file is hashed and compared against the
    value the wiki reports, so the copy is checked against A DIFFERENT PARTY's number rather than
    against one this tool computed itself. `sfv-verify.py` exists for the same reason.

    Run it after the pages. The `File:` description pages say what each image IS -- provenance,
    licence, caption -- and having them first means the bytes arrive into a context that can
    already explain them.

USAGE
    python mediawiki-source.py --base https://www.ndwiki.org --root Q:\mirror \
        --archive ndwiki --dry-run
    python mediawiki-source.py --base https://www.ndwiki.org --root Q:\mirror \
        --archive ndwiki
    python mediawiki-source.py --base https://www.ndwiki.org --root Q:\mirror \
        --archive ndwiki --images
"""
import argparse
import hashlib
import http.client
import urllib.error
import io
import os
import sys
import time

from common import Pacer, host_of, http_open, long_path, relative_to
from mediawiki import (MediaWikiUnanswered, mediawiki_api, mediawiki_filename,
                       mediawiki_images, mediawiki_siteinfo, mediawiki_titles)

# The API's own limit for an anonymous client. Asking for more is silently truncated, which would
# look like pages quietly going missing.
BATCH = 50

# Windows forbids characters the wiki allows. Every substitution is recorded in RENAMED.txt so
# the copy can still say what the page was really called -- see mediawiki_filename() for the one
# case it does not record, and why that loses nothing.



def show_site(base, delay):
    """Print who answered and what they hold. -> the namespace map.

    THE PRINTING IS THIS TOOL'S JOB, NOT THE LIBRARY'S. A helper that owns the screen cannot be
    called by anything that wants the answer without the noise, and cannot be tested without
    capturing stdout.
    """
    try:
        ns, general, stats = mediawiki_siteinfo(base, delay)
    except MediaWikiUnanswered as why:
        raise SystemExit("  siteinfo failed: %s -- refusing to guess the namespace list" % why)
    print("  %s -- %s" % (general.get("sitename", "?"), general.get("generator", "?")))
    if stats:
        print("     %d pages, %d articles, %d files, %d edits"
              % (stats.get("pages", 0), stats.get("articles", 0),
                 stats.get("images", 0), stats.get("edits", 0)))
    print("     rights: %s" % (general.get("rights") or "(none declared)"))
    return ns


def ns_progress(ns, name, got, why):
    if got is None:
        print("     ns %-3d %-18s UNANSWERED (%s) -- NOT an empty namespace" % (ns, name, why))
    else:
        print("     ns %-3d %-18s %5d pages" % (ns, name, got))


def image_progress(n, why):
    if why is None:
        print("     %d files so far" % n, flush=True)
    else:
        print("     UNANSWERED (%s) after %d files -- this is NOT the end of the list" % (why, n))

def fetch_images(base, root, delay, note):
    """Download every file the wiki lists, and check each against the wiki's OWN sha1."""
    imgs, complete = mediawiki_images(base, delay, report=image_progress)
    total = sum(i.get("size", 0) for i in imgs)
    print("\n  %d files, %.2f GB%s\n"
          % (len(imgs), total / 2**30, "" if complete else "   (LIST INCOMPLETE -- see above)"))

    dest_dir = os.path.join(root, "images")
    os.makedirs(long_path(dest_dir), exist_ok=True)
    rows = []
    ok = skipped = mismatch = failed = 0
    got = 0
    t0 = time.time()
    # One rate for the whole run. A wiki's files come from its own host, so there is one key.
    pacer = Pacer(delay)
    host = host_of(base)

    for n, im in enumerate(imgs, 1):
        name, _changed = mediawiki_filename(im["name"], ext="")
        dest = os.path.join(dest_dir, name)
        want_sha1 = (im.get("sha1") or "").lower()

        if os.path.exists(long_path(dest)) and os.path.getsize(long_path(dest)) == im.get("size"):
            # NOT PACED: nothing is asked for a file already on disk.
            skipped += 1
            continue
        # BEFORE the request, not after each branch. The four sleeps this replaces sat at the end
        # of the fail, mismatch and success paths -- so the loop paced everything EXCEPT the
        # requests that had just failed, which is exactly backwards: a failing server is the one
        # that needs the pause. `Pacer` also counts the fetch itself against the delay, where
        # `time.sleep(delay)` added it on top. [2026-09-25]
        pacer.wait(host)
        try:
            with http_open(im["url"], timeout=300) as r:
                data = r.read()
        except Exception as exc:                                # noqa: BLE001
            note("FILE FAIL %s :: %s" % (im["name"], type(exc).__name__))
            failed += 1
            continue

        have_sha1 = hashlib.sha1(data).hexdigest()
        if want_sha1 and have_sha1 != want_sha1:
            # TWO DIFFERENT FAULTS LOOK IDENTICAL HERE, and only a second fetch tells them apart:
            #
            #   the bytes arrived wrong          -> a retry gives a DIFFERENT hash
            #   the wiki's metadata is stale     -> a retry gives the SAME hash
            #
            # The second is not corruption at all. Measured on ndwiki.org 2026-09-17:
            # 3033-nd100-cpu-cx-card.jpg is recorded in the database as 1 848 878 B / ed677a59…,
            # and the server serves 3 528 916 B / d89c5aa2… twice over. The file was replaced and
            # the row was never updated. Refusing it as "corrupt" would be wrong, and accepting it
            # silently would throw away the only evidence that the operator's index is off.
            pacer.wait(host)
            try:
                with http_open(im["url"], timeout=300) as r2:
                    again = hashlib.sha1(r2.read()).hexdigest()
            # A RE-FETCH THAT FAILED, AND NOTHING ELSE. `again = None` makes the file read as
            # CHANGED, so a broad catch here turns any programming error into "the operator's
            # index is off" -- a wrong answer that looks exactly like the finding this code is
            # written to produce.
            except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
                again = None
            if again == have_sha1:
                note("SHA1 STALE-METADATA %s :: wiki says %s/%s B, server serves %s/%s B twice"
                     % (im["name"], want_sha1, im.get("size"), have_sha1, len(data)))
                print("  !! wiki's OWN sha1 is stale, not written: %s" % im["name"][:56])
            else:
                note("SHA1 MISMATCH %s :: wiki %s, got %s then %s (%d B)"
                     % (im["name"], want_sha1, have_sha1, again, len(data)))
                print("  !! SHA-1 mismatch (bytes unstable), NOT written: %s" % im["name"][:46])
            mismatch += 1
            continue

        with io.open(long_path(dest + ".part"), "wb") as fh:
            fh.write(data)
        os.replace(long_path(dest + ".part"), long_path(dest))
        rows.append((im["name"], len(data), have_sha1, im.get("mime", ""),
                     im.get("timestamp", ""), "images/" + name))
        ok += 1
        got += len(data)
        if ok % 25 == 0 or n == len(imgs):
            print("  %5d/%d  ok %d  skip %d  mismatch %d  failed %d   %.2f GB  %.0fs"
                  % (n, len(imgs), ok, skipped, mismatch, failed, got / 2**30, time.time() - t0),
                  flush=True)

    if rows:
        p = os.path.join(root, "MANIFEST-FILES.tsv")
        head = not os.path.exists(long_path(p))
        with io.open(long_path(p), "a", encoding="utf-8", newline="\n") as fh:
            if head:
                fh.write("name\tbytes\tsha1\tmime\tuploaded\tpath\n")
            for r in rows:
                fh.write("\t".join(str(x) for x in r) + "\n")

    note("FILES DONE ok=%d skipped=%d mismatch=%d failed=%d bytes=%d"
         % (ok, skipped, mismatch, failed, got))
    print("\n  %d fetched (%.2f GB), %d already held, %d SHA-1 mismatches, %d failed"
          % (ok, got / 2**30, skipped, mismatch, failed))
    print("  Every byte checked against the WIKI'S OWN sha1, not one computed here.")
    if not complete:
        print("  THE FILE LIST ITSELF WAS CUT SHORT by an unanswered query -- rerun before")
        print("  treating this archive as finished.")
    return 1 if (failed or mismatch or not complete) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True, help="wiki root, e.g. https://www.ndwiki.org")
    ap.add_argument("--root", required=True, help="the mirror tree")
    ap.add_argument("--archive", required=True, help="subdirectory to write into")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="seconds between requests (default 1.5). These are small servers")
    ap.add_argument("--namespaces", help="comma-separated namespace ids; default is all of them")
    ap.add_argument("--images", action="store_true",
                    help="fetch the uploaded FILES instead of the page text, from the wiki's own "
                         "allimages inventory, verifying each against the wiki's own SHA-1. Run "
                         "this after the pages -- the File: descriptions explain what arrives")
    ap.add_argument("--dry-run", action="store_true",
                    help="enumerate and stop. Writes nothing, fetches no page text")
    ap.add_argument("--verify-current", action="store_true", default=True,
                    help="abort if the API ever returns more than one revision for a page")
    args = ap.parse_args()

    only = None
    if args.namespaces:
        only = {int(x) for x in args.namespaces.split(",") if x.strip()}

    root = os.path.join(os.path.abspath(args.root), args.archive)
    logdir = os.path.join(os.path.abspath(args.root), "logs")
    os.makedirs(logdir, exist_ok=True)
    log = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def note(t):
        log.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), t))
        log.flush()

    if args.images:
        print("Asking %s for its own file inventory ...\n" % args.base, flush=True)
        show_site(args.base, args.delay)
        print()
        if args.dry_run:
            imgs, complete = mediawiki_images(args.base, args.delay, report=image_progress)
            tot = sum(i.get("size", 0) for i in imgs)
            print("\n  %d files, %.2f GB%s -- dry run, nothing written"
                  % (len(imgs), tot / 2**30, "" if complete else "  (LIST INCOMPLETE)"))
            return 0
        os.makedirs(long_path(root), exist_ok=True)
        note("FILES START %s -> %s" % (args.base, root))
        return fetch_images(args.base, root, args.delay, note)

    print("Asking %s for its own page list ...\n" % args.base, flush=True)
    ns_map = show_site(args.base, args.delay)
    print()
    titles, complete = mediawiki_titles(args.base, ns_map, args.delay, only,
                                        report=ns_progress)
    print("\n  %d pages in %d namespaces%s\n"
          % (len(titles), len({n for n, _ in titles}),
             "" if complete else "   -- THE LIST IS INCOMPLETE, do not treat this as the wiki"))

    if args.dry_run:
        for ns, t in titles[:30]:
            print("     %-4s %s" % (ns, t))
        if len(titles) > 30:
            print("     ... and %d more" % (len(titles) - 30))
        print("\n  dry run -- nothing written. %d text requests would follow (%d per batch)."
              % ((len(titles) + BATCH - 1) // BATCH, BATCH))
        return 0

    os.makedirs(long_path(root), exist_ok=True)
    note("WIKI START %s -> %s (%d pages, current revisions only)"
         % (args.base, root, len(titles)))

    rows, renamed = [], []
    ok = missing = failed = 0
    t0 = time.time()
    by_ns = {ns: name for ns, name in ns_map.items()}
    pacer = Pacer(args.delay)
    host = host_of(args.base)

    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        # Same change as the image loop: the two sleeps this replaces sat after the request, one
        # of them behind a `continue` that a failed batch reached and a successful one did not.
        pacer.wait(host)
        d, why = mediawiki_api(args.base, [("action", "query"), ("prop", "revisions"),
                                 ("rvslots", "main"),
                                 ("rvprop", "content|timestamp|ids"),
                                 ("titles", "|".join(t for _n, t in chunk))], args.delay)
        if d is None:
            note("BATCH FAIL %d-%d :: %s" % (i, i + len(chunk), why))
            failed += len(chunk)
            print("  %5d/%d  batch UNANSWERED (%s)" % (i + len(chunk), len(titles), why))
            continue

        for p in d.get("query", {}).get("pages", []):
            title = p.get("title", "?")
            if "revisions" not in p:
                note("NO REVISION %s" % title)
                missing += 1
                continue
            if args.verify_current and len(p["revisions"]) != 1:
                raise SystemExit(
                    "  %s returned %d revisions. This tool exists to take the CURRENT one only;\n"
                    "  refusing to write history that was not asked for."
                    % (title, len(p["revisions"])))
            rev = p["revisions"][0]
            text = rev["slots"]["main"].get("content", "")
            ns = p.get("ns", 0)
            name, changed = mediawiki_filename(title.split(":", 1)[-1] if ns else title)
            sub = by_ns.get(ns) or "Main"
            dest = os.path.join(root, sub, name)
            os.makedirs(long_path(os.path.dirname(dest)), exist_ok=True)
            data = text.encode("utf-8")
            with io.open(long_path(dest + ".part"), "wb") as fh:
                fh.write(data)
            os.replace(long_path(dest + ".part"), long_path(dest))
            if changed:
                renamed.append((title, relative_to(root, dest)))
            rows.append((title, ns, p.get("pageid", ""), rev.get("revid", ""),
                         rev.get("timestamp", ""), len(data),
                         hashlib.sha256(data).hexdigest(),
                         relative_to(root, dest)))
            ok += 1

        print("  %5d/%d  ok %d  no-revision %d  failed %d   %.0fs"
              % (min(i + BATCH, len(titles)), len(titles), ok, missing, failed, time.time() - t0),
              flush=True)

    with io.open(long_path(os.path.join(root, "MANIFEST.tsv")), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("title\tns\tpageid\trevid\ttimestamp\tbytes\tsha256\tpath\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")

    if renamed:
        with io.open(long_path(os.path.join(root, "RENAMED.txt")), "w",
                     encoding="utf-8", newline="\n") as fh:
            fh.write("Wiki titles that could not be filenames on this filesystem.\n"
                     "The real title is always in MANIFEST.tsv.\n\n")
            for t, p in renamed:
                fh.write("%s\t%s\n" % (t, p))

    total = sum(r[5] for r in rows)
    note("WIKI DONE ok=%d missing=%d failed=%d bytes=%d" % (ok, missing, failed, total))
    print("\n  %d pages, %.2f MB of wikitext, %d renamed" % (ok, total / 2**20, len(renamed)))
    if missing:
        print("  %d titles came back with no revision -- listed in the log" % missing)
    if failed:
        print("  %d pages in UNANSWERED batches. NOT losses; rerun to pick them up." % failed)
    print("  MANIFEST.tsv carries every title, revid, timestamp and SHA-256.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
