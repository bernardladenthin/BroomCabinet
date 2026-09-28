#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""MediaWiki: asking a wiki's own API for what it holds, instead of crawling what it renders.

SPLIT OUT OF common.py ON 2026-09-23, unchanged. One tool uses it, mediawiki-source.py.

WHY AN API AND NOT A CRAWL. A wiki renders every page from markup it will hand over on request,
and the rendered form is the lossy one. Crawling it collects the illustration and leaves the
artefact behind -- so this asks for titles, images and site info the way the software offers
them, and a refusal to answer is a distinct thing from an answer of nothing.

It takes four things from common: http_open and sha256_bytes to fetch and identify, UNSAFE and
WINDOWS_RESERVED to turn a wiki title into a filename this filesystem will accept. Those last
two stayed in common deliberately -- what Windows will not store is a fact about the machine,
not about MediaWiki, and a module for one wiki engine is the wrong place to keep it.

Nothing here refers to the pmwiki or dokuwiki modules, and they do not refer to this.
"""

import json
import time
import urllib.parse

from common import UNSAFE, WINDOWS_RESERVED, Pacer, host_of, http_open, sha256_bytes

__all__ = [
    "mediawiki_api", "mediawiki_siteinfo", "mediawiki_titles", "mediawiki_images",
    "mediawiki_filename", "MediaWikiUnanswered", "MEDIAWIKI_PAGE_LIMIT",
]

# ------------------------------------------------------------------------------- mediawiki
#
# NAMED FOR THE SYSTEM THEY SPEAK TO, not hidden from the library because of it. These are not
# abstract -- each one encodes a contract with somebody else's software: a continuation marker,
# a namespace numbering, a rate limit. But that is exactly why they must be in one place and
# under test: a contract with a foreign system is the kind of thing a second copy gets subtly
# wrong, and the wrongness shows up as a short answer rather than as an error.
#
# The prefix is the honest label. `mediawiki_titles` says in its name which wiki API it assumes,
# so a reader never has to wonder whether it is general.


MEDIAWIKI_PAGE_LIMIT = "500"     # the API's own maximum for an anonymous client

class MediaWikiUnanswered(Exception):
    """A request that was never answered.

    RAISED RATHER THAN RETURNED AS EMPTINESS. A failed request and an empty answer are different
    facts, and this collection has already acted on the confusion once: a query that answered 503
    was recorded as "no captures", and the absence was believed.
    """


def mediawiki_api(base, params, delay=0.0, tries=4, timeout=90, opener=None, sleep=None):
    """One API call as JSON. -> (data, "") or (None, reason) -- NEVER a bare None.

    The reason is carried back so a caller can say WHY nothing came, in the place where it would
    otherwise print a count. `sleep` is injectable so the backoff can be tested without spending
    the wall-clock it describes.
    """
    sleep = sleep or time.sleep
    url = base.rstrip("/") + "/api.php?" + urllib.parse.urlencode(
        list(params) + [("format", "json"), ("formatversion", "2")])
    why = "?"
    for attempt in range(tries):
        try:
            with http_open(url, timeout=timeout, opener=opener) as r:
                return json.load(r), ""
        except urllib.error.HTTPError as exc:
            why = "HTTP %s" % exc.code
            # A rate limit is an instruction, not a failure: waiting longer is the correct
            # response to it, and hammering is how a polite client gets blocked outright.
            sleep(max(delay, 10) * (attempt + 1) if exc.code in (429, 503) else delay)
        except Exception as exc:                                # noqa: BLE001
            why = type(exc).__name__
            sleep(max(delay, 5) * (attempt + 1))
    return None, why


def mediawiki_siteinfo(base, delay=0.0, **kw):
    """-> ({namespace id: name}, general, statistics).

    NEGATIVE NAMESPACES ARE DROPPED: they are virtual (Special, Media) and hold nothing that can
    be fetched as a page.

    Raises MediaWikiUnanswered when siteinfo does not answer, because the alternative is guessing
    the namespace list -- and a guessed list produces a copy that is missing whole sections while
    reporting success.
    """
    d, why = mediawiki_api(base, [("action", "query"), ("meta", "siteinfo"),
                                  ("siprop", "namespaces|general|statistics")], delay, **kw)
    if d is None:
        raise MediaWikiUnanswered(why)
    query = d["query"]
    ns = {int(k): (v.get("name") or "Main")
          for k, v in query["namespaces"].items() if int(k) >= 0}
    return ns, query.get("general", {}), query.get("statistics", {})


def mediawiki_titles(base, ns_map, delay=0.0, only_ns=None, report=None, **kw):
    """Every page title, namespace by namespace. -> ([(ns, title)], complete).

    COMPLETE IS NOT A COURTESY. A namespace that stops answering halfway leaves a list which is
    indistinguishable, by inspection, from a namespace that really holds that many pages -- and
    the difference is whether the copy is missing something. The caller is told, and may not
    write a completion marker over a False.

    `report(namespace, name, pages_or_None, reason_or_None)` is called once per namespace: with a
    count when it answered, with None and a reason when it did not.
    """
    report = report or (lambda *a: None)
    # `delay` IS A RATE -- do not ask this wiki more often than every `delay` seconds -- and an
    # API page that took a second to arrive has already paid most of it. `common.Pacer` counts
    # that elapsed time; the `time.sleep(delay)` this replaces did not, so a large wiki was
    # walked at roughly half the rate the caller asked for. It also waits between NAMESPACES,
    # which the old sleep did not: it sat after the continuation test and was skipped on the
    # last page of each. Made here rather than taken as an argument because the signature is
    # this module's contract; `sleep` is borrowed from `kw` so pacing can be tested without
    # spending it, exactly as the retry ladder's own sleep is.
    pacer = Pacer(delay, sleep=kw.get("sleep") or time.sleep)
    titles, complete = [], True
    for ns in sorted(ns_map):
        if only_ns is not None and ns not in only_ns:
            continue
        cont, got = None, 0
        while True:
            p = [("action", "query"), ("list", "allpages"),
                 ("apnamespace", str(ns)), ("aplimit", MEDIAWIKI_PAGE_LIMIT)]
            if cont:
                p.append(("apcontinue", cont))
            pacer.wait(host_of(base))
            d, why = mediawiki_api(base, p, delay, **kw)
            if d is None:
                complete = False
                report(ns, ns_map[ns], None, why)
                break
            batch = d.get("query", {}).get("allpages", [])
            titles += [(ns, x["title"]) for x in batch]
            got += len(batch)
            cont = d.get("continue", {}).get("apcontinue")
            if not cont:
                break
        if got:
            report(ns, ns_map[ns], got, None)
    return titles, complete


def mediawiki_images(base, delay=0.0, report=None, **kw):
    """The wiki's own inventory of uploaded files. -> ([entries], complete).

    From `allimages` rather than from crawling the pages that embed them: a file nothing links to
    is still a file the wiki holds, and a crawl cannot see it at all.

    `report(count_so_far, reason_or_None)` is called after each page of the inventory.
    """
    report = report or (lambda *a: None)
    # The same rate, for the same reason, as in mediawiki_titles: see the note there. One Pacer
    # per call, so two calls in one run meet at an unpaced request -- which is one request, not
    # a pass, and cheaper than putting a pacer on a signature this module has promised.
    pacer = Pacer(delay, sleep=kw.get("sleep") or time.sleep)
    out, cont = [], None
    while True:
        p = [("action", "query"), ("list", "allimages"), ("ailimit", MEDIAWIKI_PAGE_LIMIT),
             ("aiprop", "url|size|sha1|mime|timestamp")]
        if cont:
            p.append(("aicontinue", cont))
        pacer.wait(host_of(base))
        d, why = mediawiki_api(base, p, delay, **kw)
        if d is None:
            report(len(out), why)
            return out, False
        out += d.get("query", {}).get("allimages", [])
        cont = d.get("continue", {}).get("aicontinue")
        report(len(out), None)
        if not cont:
            return out, True


def mediawiki_filename(title, ext=".wiki", limit=180):
    """Map a wiki title onto a filename on this filesystem. -> (name, changed).

    `changed` is what a rename record is written from, so it must be true for every substitution
    a reader would otherwise be unable to undo.

    THE SLASH IS REPLACED BEFORE THE COMPARISON, AND SO IS NOT REPORTED AS A CHANGE. A title is
    allowed to contain one and it is not a path separator to the wiki; here it must become one
    character or a page turns into a directory. Nothing is lost by the omission -- the manifest
    carries the real title for every page, not only for the renamed ones -- but the rename list
    is, for those titles, shorter than its own heading claims.

    The tail is trimmed because Windows drops a trailing dot or space while OPENING a file, so a
    name ending in one silently becomes a different name.

    THE CAP AND THE CUT ARE BOTH IN BYTES. They were not: the check measured encoded bytes and
    the truncation counted characters, so a title of 120 Norwegian characters was 240 bytes,
    exceeded the cap, and was then "truncated" to 150 characters -- which is to say not at all.
    The cap simply did not apply to the one alphabet the wiki it was written for is in. Measured
    against that wiki's 2 675 titles on 2026-09-22 the longest is 96 bytes, so nothing on disk
    changes; the defect was latent, not active, which is the only reason this could be corrected
    rather than merely recorded.
    """
    n = title.replace("/", "_")
    fixed = UNSAFE.sub("_", n.replace("\\", "_"))
    if fixed.rstrip(". ") != fixed:
        fixed = fixed.rstrip(". ") + "_"
    if fixed.split(".")[0].upper() in WINDOWS_RESERVED:
        fixed = "_" + fixed
    encoded = fixed.encode("utf-8")
    if len(encoded) > limit:
        # The digest is what keeps two long titles that share a prefix from becoming one file,
        # which would overwrite one page with another and say nothing. "ignore" drops a character
        # the cut landed inside: half of one is not a character.
        fixed = encoded[:limit - 30].decode("utf-8", "ignore")             + "~" + sha256_bytes(title.encode("utf-8"))[:12]
    return fixed + ext, fixed != n
