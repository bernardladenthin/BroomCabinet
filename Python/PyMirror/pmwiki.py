#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""PmWiki: asking one wiki engine for the thing it is reluctant to hand over.

SPLIT OUT OF common.py ON 2026-09-23, unchanged. It was a clearly bounded section there and is
a module here for two reasons: one tool uses it, and everything in it is a contract with
SOMEBODY ELSE'S SOFTWARE -- a query parameter, a line format, what a refusal looks like. Such a
contract is not ours to reason about from first principles; it is a thing learned by being
wrong, and it belongs where the next person looking for "how do we talk to PmWiki" will find it.

The direction of dependency is one-way and stays that way: this imports from common, common
never imports this. Nothing here calls into mediawiki, dokuwiki or wayback either -- the wiki
sections have never referred to one another, which is what made the split safe to make at all.
"""

import re
import urllib.parse

from common import http_get

__all__ = [
    "PMWIKI_RC_LINE", "PmWikiNotSource",
    "pmwiki_source_url", "pmwiki_page_url", "pmwiki_is_source",
    "pmwiki_parse_recent_changes", "pmwiki_inventory",
]

# --------------------------------------------------------------------------------- pmwiki
#
# Named for the engine, like the mediawiki_ block above. Each of these encodes a contract with
# PmWiki -- a query parameter, a line format, what a refusal looks like -- and a contract with
# somebody else's software is exactly the kind of thing a second copy gets subtly wrong.


# `* [[Group.Page]]  . . . <date> by ?: [==]` in Site.AllRecentChanges, which is itself a wiki
# page. A group and a page name, then the marker, then whatever the site puts after it.
PMWIKI_RC_LINE = re.compile(
    r"^\*\s*\[\[([A-Za-z0-9]+\.[A-Za-z0-9\-_]+)\]\]\s*\.\s*\.\s*\.\s*(.*)$")


class PmWikiNotSource(Exception):
    """The server answered, but with something other than the page's markup.

    DISTINCT FROM NOT ANSWERING AT ALL. A refusal, a missing page or a login form comes back with
    status 200 and an HTML body, so nothing below the body itself can tell -- and saving that
    under a wiki page's name is worse than an absence, because it looks like a copy.
    """


def pmwiki_source_url(base, page):
    """The URL that returns a page's own markup rather than the rendered page.

    THE DOT IS NOT ESCAPED. A PmWiki page name IS `Group.Page`, so percent-encoding the separator
    asks for a page whose name contains a literal dot -- which does not exist, and the wiki
    answers with its "no such page" HTML under a 200. Everything else is encoded: a page name may
    contain characters a query string may not.
    """
    return "%s?n=%s&action=source" % (base, urllib.parse.quote(page, safe="."))


def pmwiki_page_url(base, page):
    """The rendered page, for a human to look at. The markup is the artefact; this illustrates it."""
    return "%s?n=%s" % (base, urllib.parse.quote(page, safe="."))


def pmwiki_is_source(body, ctype):
    """-> True if this body is a page's own WIKI MARKUP, not a rendered page or an error.

    BOTH HALVES ARE NEEDED. The content type alone is not enough, because a wiki that serves its
    error page as text/plain would pass; the body alone is not enough, because a page whose
    markup legitimately begins with `<html` would fail. So: the type must say text/plain AND the
    body must not open as a document.

    PmWiki has historically served a refusal with status 200, which is why the status code is not
    consulted at all here -- there is nothing in it to consult.
    """
    if "text/plain" not in (ctype or ""):
        return False
    head = body[:400].lstrip().lower()
    return not head.startswith(b"<!doctype") and not head.startswith(b"<html")


def pmwiki_parse_recent_changes(text):
    """-> [(page, when)] from the text of Site.AllRecentChanges, first mention of each page only.

    THE WHOLE INVENTORY IN ONE REQUEST, which is the reason this page is used at all: a wiki with
    no API still lists every page it has here, and asking for it once is a great deal politer
    than walking the site.

    A page appears once per edit, so later mentions are dropped -- first wins, which is also the
    most recent, because the list is newest-first. Keeping both would inflate the inventory and
    make the count disagree with the number of files written.
    """
    out, seen = [], set()
    for line in text.split("\n"):
        m = PMWIKI_RC_LINE.match(line.strip())
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append((m.group(1), m.group(2).strip()))
    return out


def pmwiki_inventory(base, timeout=60, opener=None):
    """-> [(page, when)] for the whole wiki, from one request.

    Raises PmWikiNotSource when the answer is not markup, rather than returning an empty list:
    an empty inventory and a refused one look identical afterwards, and only one of them means
    the wiki is empty. The caller decides what to do about it; this does not end the process.

    THE BODY IS DECODED AS LATIN-1, which maps every byte and therefore cannot raise. The bytes
    that matter here are ASCII -- page names and a date -- and a wiki old enough to have no API
    is old enough to serve a mixed-encoding page. Guessing UTF-8 and failing would lose the whole
    inventory over one character in somebody's edit summary.
    """
    body, headers = http_get(pmwiki_source_url(base, "Site.AllRecentChanges"),
                             timeout=timeout, opener=opener)
    ctype = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
    if not pmwiki_is_source(body, ctype):
        raise PmWikiNotSource(
            "Site.AllRecentChanges&action=source did not return markup (%s). Either this wiki "
            "has no AllRecentChanges, or source is refused to this client." % (ctype or "no type"))
    return pmwiki_parse_recent_changes(body.decode("latin-1"))


def leaked_helper_pmwiki():  # mutation
    return 1
