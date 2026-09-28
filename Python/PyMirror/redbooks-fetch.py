# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fetch the IBM Redbooks PDF set from the ids in the site's own sitemap.

    python redbooks-fetch.py                       # everything
    python redbooks-fetch.py --dry-run             # list, fetch nothing
    python redbooks-fetch.py --filter aix --filter power   # only ids whose TITLE matches

WHY NOT A CRAWL. The PDFs are not in sitemap.xml and the abstract pages do not need visiting:
sitemap.xml yields 2 985 ids, and the PDF follows from the id --

    sg…    -> /redbooks/pdfs/<id>.pdf          1 624 Redbooks
    redp…  -> /redpapers/pdfs/<id>.pdf         1 049 Redpapers
    tips…  -> /technotes/<id>.pdf                272 Technotes
    …and if that 404s, /redpieces/pdfs/<id>.pdf -- the document is still in DRAFT

One request per document, two for the drafts. A 22-id sample resolved 22/22 against the first
three rules, which is exactly how the fourth was missed: the sample contained no draft. The first
three 404s of the real run were all redpieces. A rule confirmed by sampling is confirmed only for
what the sample happened to contain.

TERMS. `robots.txt` is three lines and is quoted here in full because it is short enough to be
checked rather than trusted:

    User-agent: *
    Disallow: /cgi-bin/
    Disallow: /api/
    Disallow: */api/*

Nothing touches the PDF tree. Read directly on 2026-09-07, not taken from a summary.

AND A CAVEAT THIS TOOL SHOULD CARRY. Redbooks are not endangered. IBM has served them for thirty
years and they are mirrored widely; this collection's rule is one server, one person, no
successor, and Redbooks meet none of it. The owner asked for them and 20 GB is cheap insurance --
but it is insurance, not rescue.

--filter is offered for the same reason: most of this set is z/OS, cloud and watsonx material with
no bearing on AIX. Filtering costs one HEAD-free pass over the sitemap titles and can halve the
take. It matches against the TITLE, not the id, because ids carry no meaning.
"""
import argparse
import io
import os
import http.client
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (MIRROR_ROOT, Pacer, host_of, http_get, http_open, page_title,
                    sitemap_locations)

SITEMAP = "https://www.redbooks.ibm.com/sitemap.xml"
BASE = "https://www.redbooks.ibm.com"
ID_RE = re.compile(r"/abstracts/([a-z]+\d+)\.html", re.I)


def pdf_urls(doc_id):
    """-> the URLs this id's PDF may live at, in order. Try each until one is not a 404.

    THERE IS A FOURTH PATH AND THE ID DOES NOT REVEAL IT. A document still in draft is a
    "redpiece" and lives at /redpieces/pdfs/<id>.pdf -- with the same sg… or redp… id it will
    carry once published. sg248608, sg248599 and sg248525 were the first three 404s of the run and
    all three are redpieces; their abstract pages link the redpieces path directly.

    Nothing in the id, the sitemap or the abstract URL distinguishes a draft from a published
    document, so the only honest rule is: ask the normal place, and on 404 ask the draft place.
    One extra request for the few that need it, none for the rest -- and without it every
    in-progress Redbook is silently absent while the run reports a tidy handful of 404s.
    """
    if doc_id.startswith("sg"):
        return ["%s/redbooks/pdfs/%s.pdf" % (BASE, doc_id),
                "%s/redpieces/pdfs/%s.pdf" % (BASE, doc_id)]
    if doc_id.startswith("redp"):
        return ["%s/redpapers/pdfs/%s.pdf" % (BASE, doc_id),
                "%s/redpieces/pdfs/%s.pdf" % (BASE, doc_id)]
    if doc_id.startswith("tips"):
        # ONE PATH ONLY, and some technotes have no PDF AT ALL. tips1365 is the example: its
        # abstract page answers 200 and links no PDF anywhere, and all four candidate paths 404.
        # A technote can be a web page and nothing else. NOT FOUND on a tips… id is therefore a
        # finding about the document, not a failure of this tool -- do not go looking for a fifth
        # path on its account.
        return ["%s/technotes/%s.pdf" % (BASE, doc_id)]
    return []


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", default="ibm-redbooks")
    ap.add_argument("--delay", type=float, default=0.5,
                    help="seconds between requests (default 0.5). robots.txt sets no "
                         "Crawl-delay, so this is courtesy rather than obligation.")
    ap.add_argument("--filter", action="append", default=[],
                    help="keep only documents whose title matches this (case-insensitive, "
                         "repeatable). Without it, everything is taken.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-free-gb", type=float, default=1.0)
    args = ap.parse_args()

    dest = os.path.join(os.path.abspath(args.root), args.archive)
    logdir = os.path.join(os.path.abspath(args.root), "logs")
    os.makedirs(logdir, exist_ok=True)
    logf = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def log(t):
        line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), t)
        logf.write(line + "\n")
        logf.flush()
        print(t, flush=True)

    # --delay IS A RATE: "not more often than every N seconds", not "idle N seconds after every
    # request". A 40 MB Redbook takes far longer than 0.5 s to arrive and has already paid the
    # courtesy several times over; `Pacer` counts that elapsed time, the old
    # `time.sleep(args.delay)` did not. One for the run -- the abstract pass and the PDF pass
    # speak to the same host, and two rates would be two promises to one server.
    pacer = Pacer(args.delay)

    log("START %s -> %s" % (SITEMAP, dest))
    body = http_get(SITEMAP)[0].decode("utf-8", "replace")
    locs = sitemap_locations(body)
    ids = []
    seen = set()
    for loc in locs:
        m = ID_RE.search(loc)
        if m and m.group(1).lower() not in seen:
            seen.add(m.group(1).lower())
            ids.append(m.group(1))
    log("sitemap: %d entries, %d distinct document ids" % (len(locs), len(ids)))

    if args.filter:
        # The title lives in the sitemap only as the abstract URL, so filtering needs the abstract
        # page. That is a request per document -- the exact cost this tool exists to avoid -- so it
        # is opt-in and reported, never silent.
        log("--filter given: fetching %d abstract pages to read their titles" % len(ids))
        keep = []
        pats = [f.lower() for f in args.filter]
        for i, doc_id in enumerate(ids, 1):
            abstract = "%s/abstracts/%s.html" % (BASE, doc_id)
            pacer.wait(host_of(abstract))
            try:
                page = http_open(abstract, timeout=45).read()
                title = page_title(page) or ""   # common.page_title() since 2026-09-27
            # AN ABSTRACT THAT DID NOT ANSWER, AND NOTHING ELSE. `title = ""` makes the
            # pattern filter below match nothing, so a broad catch here quietly selects no
            # documents at all and the run reports a clean pass over an empty selection.
            except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
                title = ""
            if any(p in title.lower() for p in pats):
                keep.append(doc_id)
            if i % 200 == 0:
                log("  %d/%d abstracts read, %d kept" % (i, len(ids), len(keep)))
        log("filter kept %d of %d" % (len(keep), len(ids)))
        ids = keep

    jobs = [(i, pdf_urls(i)) for i in ids]
    jobs = [(i, u) for i, u in jobs if u]
    log("%d documents to fetch" % len(jobs))
    if args.dry_run:
        for i, u in jobs[:15]:
            print("  %s" % u[0])
        print("  ... and %d more\n\nDry run -- nothing fetched." % max(0, len(jobs) - 15))
        return 0

    import shutil
    ok = skip = fail = 0
    total = 0
    t0 = time.time()
    redpieces = 0
    for n, (doc_id, urls) in enumerate(jobs, 1):
        sub = "redbooks" if doc_id.startswith("sg") else (
            "redpapers" if doc_id.startswith("redp") else "technotes")
        out = os.path.join(dest, sub, doc_id + ".pdf")
        if os.path.exists(out):
            skip += 1
            continue
        if shutil.disk_usage(os.path.abspath(args.root)).free < args.min_free_gb * 1e9:
            log("DISK FLOOR: under %.1f GB free -- stopping. Re-run when there is room."
                % args.min_free_gb)
            break
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = out + ".part"
        # ONCE PER DOCUMENT, AND ONLY FOR ONE THAT IS ACTUALLY FETCHED. The old sleep sat at the
        # foot of the loop, so it paced documents already on disk as well -- a re-run over a
        # finished archive spent the whole delay per file to discover it had nothing to do.
        pacer.wait(host_of(urls[0]))
        # Try each candidate path; a 404 on the first is the normal signal that this one is a
        # draft, not that it is missing.
        url = None
        last = None
        for cand in urls:
            try:
                with http_open(cand, timeout=30) as probe:
                    probe.read(1)
                url = cand
                break
            except urllib.error.HTTPError as e:
                last = e
                if e.code != 404:
                    break
            except Exception as e:
                last = e
                break
        if url is None:
            fail += 1
            log("NOT FOUND %s :: %s (tried %d paths)" % (doc_id, last, len(urls)))
            continue
        if "redpieces" in url:
            redpieces += 1
            out = os.path.join(dest, "redpieces", doc_id + ".pdf")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            tmp = out + ".part"
        try:
            with http_open(url) as r:
                claimed = int(r.headers.get("Content-Length") or 0)
                got = 0
                with io.open(tmp, "wb") as fh:
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        fh.write(c)
                        got += len(c)
            if claimed and got != claimed:
                # A short PDF is worse than none: it opens, it looks like a document, and the
                # missing pages are invisible. Keep it aside under a name nothing reads.
                os.replace(tmp, out + ".suspect")
                fail += 1
                log("SHORT %s: %d of %d bytes" % (doc_id, got, claimed))
                continue
            os.replace(tmp, out)
            ok += 1
            total += got
        except urllib.error.HTTPError as e:
            fail += 1
            log("HTTP %d %s" % (e.code, url))
            try:
                os.remove(tmp)
            except OSError:
                pass
        except Exception as e:
            fail += 1
            log("FAIL %s :: %s" % (doc_id, e))
            try:
                os.remove(tmp)
            except OSError:
                pass
        if n % 50 == 0:
            log("  %d/%d  ok %d  skip %d  fail %d  %.2f GB  (%.0f/min)"
                % (n, len(jobs), ok, skip, fail, total / 1e9, n / max(time.time() - t0, 1) * 60))

    log("DONE fetched %d (of which %d drafts from /redpieces/), already present %d, "
        "failed %d, %.2f GB in %.0f min"
        % (ok, redpieces, skip, fail, total / 1e9, (time.time() - t0) / 60))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
