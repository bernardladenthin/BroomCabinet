#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""DokuWiki: the third wiki engine, and the same shape as the other two.

SPLIT OUT OF common.py ON 2026-09-23, unchanged. One tool uses it, dokuwiki-source.py.

THE URLS IT ANSWERS, WHAT A PAGE ID LOOKS LIKE, AND WHAT COMES BACK WHEN A PAGE IS NOT ONE.
Each of these encodes a contract with somebody else's software -- a query parameter, an id
format, what a refusal looks like -- and a contract with software we did not write is exactly
the kind of thing a second copy gets subtly wrong.

It takes one thing from common, http_get, and nothing from the other wiki modules: mediawiki,
pmwiki and this have never referred to one another. That is what made the split safe to make.
"""

import html
import os
import re
import urllib.parse

from common import Pacer, host_of, http_get

__all__ = [
    "DOKUWIKI_ID_LINK", "DOKUWIKI_NS_LINK", "DOKUWIKI_NOT_A_PAGE",
    "dokuwiki_index_url", "dokuwiki_source_url", "dokuwiki_parse_index",
    "dokuwiki_local_path", "dokuwiki_page_ids",
]

# ------------------------------------------------------------------------------- dokuwiki
#
# The third wiki engine beside mediawiki_ and pmwiki_, and the same shape: the URLs it answers,
# what its index looks like, and where a page id belongs on a filesystem. Each is a contract with
# somebody else's software, which is why each is here once rather than in every tool that asks.


# Links in a DokuWiki index page: `doku.php?id=ns:page`, and also `?id=ns:page&do=...`.
DOKUWIKI_ID_LINK = re.compile(r'[?&]id=([^"&\']+)')

# A namespace node in the index tree: `?do=index&idx=aix`.
DOKUWIKI_NS_LINK = re.compile(r'[?&]idx=([^"&\']+)')

# Ids the index links that are not pages: an action, and DokuWiki's own control entries.
DOKUWIKI_NOT_A_PAGE = ("do=", "-")


def dokuwiki_index_url(base, namespace=""):
    """The page tree, or one namespace of it.

    `do=index` renders the tree with namespaces collapsed on some themes, and `idx` expands one.
    Walking them explicitly is the reason this exists: trusting a single index page is how a
    500-page wiki comes back as a two-page wiki.
    """
    if not namespace:
        return base + "?do=index"
    return base + "?do=index&idx=" + urllib.parse.quote(namespace)


def dokuwiki_source_url(base, page_id):
    """One page as the wikitext the wiki actually stores, rather than as a rendered skin."""
    return base + "?id=" + urllib.parse.quote(page_id) + "&do=export_raw"


def dokuwiki_parse_index(text):
    """-> (page ids, namespaces) from one index page. Both sets, both unescaped.

    HTML-UNESCAPE BEFORE MATCHING, AND THAT IS THE WHOLE FUNCTION. The index writes its links as
    `&amp;idx=aix`, so a pattern anchored on a literal `&` sees `;idx=` and matches nothing. The
    wiki then looks like a two-page wiki instead of a 500-page one, WITH NO ERROR ANYWHERE -- the
    run finishes, reports success, and the copy is missing almost everything. Measured the hard
    way on a real wiki.

    Percent-encoding is undone too, because a page id is what the wiki calls the page and that is
    what a local path has to be built from.
    """
    plain = html.unescape(text)
    ids = {urllib.parse.unquote(m) for m in DOKUWIKI_ID_LINK.findall(plain)}
    ids = {i for i in ids if not i.startswith(DOKUWIKI_NOT_A_PAGE)}
    spaces = {urllib.parse.unquote(m) for m in DOKUWIKI_NS_LINK.findall(plain)}
    # A NAMESPACE IS ALSO A PAGE when it has a start page, so every id's parent is a namespace
    # worth visiting. Leaving them out loses whole branches that the collapsed index never named.
    for i in ids:
        if ":" in i:
            spaces.add(i.rsplit(":", 1)[0])
    return ids, spaces


def dokuwiki_local_path(root, page_id):
    """-> where a page id belongs under `root`, or None if the id names nothing.

    A DokuWiki id uses `:` as its namespace separator, which is not a legal filename character on
    Windows, so it becomes a directory separator: `aix:boot` is `aix/boot.txt`.

    `.` AND `..` COMPONENTS ARE DROPPED RATHER THAN RESOLVED. An id is a remote name and a remote
    name that walks upward out of the root is either a mistake or an attack; either way nothing
    below this should have to think about it. An id that is left with no components at all
    returns None, because there is no file it could mean.
    """
    parts = [p for p in page_id.split(":") if p not in ("", ".", "..")]
    if not parts:
        return None
    parts[-1] += ".txt"
    return os.path.join(root, *parts)


def dokuwiki_page_ids(base, delay=0.0, report=None, timeout=90, opener=None, pacer=None):
    """-> every page id the wiki lists, sorted, by walking the index namespace by namespace.

    ONE REQUEST PER NAMESPACE AND NO CRAWLING. A DokuWiki addresses pages as query strings, which
    are reachable only from its own sidebar; a crawler entering at the front page finds the
    namespace index and very often stops there. Measured: the Internet Archive holds 5 476 URLs
    from one such wiki and exactly ONE of them is a content page.

    A namespace that will not answer is REPORTED AND SKIPPED, not fatal: one branch of a wiki
    being unreachable is not a reason to lose the rest of it. The caller is told through `report`
    and can decide what an incomplete index means for what it is doing.

    `delay` IS A RATE, not an idle time. A caller already holding a `common.Pacer` for this host
    passes it as `pacer` so the index walk and whatever it does next share ONE rate against the
    one server; left out, one is made from `delay`.
    """
    report = report or (lambda *a: None)
    # PACED HERE AND NOT AFTER THE REQUEST, which is where the time.sleep(delay) this replaces
    # sat. Asking first covers the namespace that fails too -- that branch `continue`d past the
    # sleep although it had just cost the server a request -- and the time the request itself
    # took now counts towards the pause instead of being added to it.
    pacer = pacer if pacer is not None else Pacer(delay)
    host = host_of(base)
    seen, todo, ids = set(), [""], set()
    while todo:
        namespace = todo.pop()
        if namespace in seen:
            # NOT PACED: nothing is asked for a namespace already walked.
            continue
        seen.add(namespace)
        pacer.wait(host)
        try:
            body, _headers = http_get(dokuwiki_index_url(base, namespace),
                                      timeout=timeout, opener=opener)
        except Exception as exc:                                # noqa: BLE001
            report(namespace, None, len(todo), exc)
            continue
        found, spaces = dokuwiki_parse_index(body.decode("utf-8", "replace"))
        ids |= found
        todo += [s for s in spaces if s not in seen]
        report(namespace, len(ids), len(todo), None)
    return sorted(ids)
