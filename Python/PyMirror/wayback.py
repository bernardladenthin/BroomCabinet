#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The Internet Archive's two addresses: the index that lists captures, and the one that replays.

SPLIT OUT OF common.py ON 2026-09-23, unchanged. Two tools use it -- wayback-salvage.py to
recover a dead host, suspect-reconsider.py to rank every capture of a file that came back short.

IT DEPENDS ON NOTHING BUT urllib. Not on common, not on the wiki modules; the whole section is
URL construction, and the one thing it has to get exactly right is what gets encoded and what
does not. A url goes into a query VALUE here, so its own `?`, `&` and `/` must not survive as
structure -- otherwise the Archive is asked a different question and answers it, correctly,
about something else.

The direction of dependency is one-way and stays that way: nothing in common imports this.
"""

import urllib.parse

__all__ = [
    "WAYBACK_CDX_BASE", "WAYBACK_CDX_FIELDS", "WAYBACK_REPLAY_BASE",
    "wayback_cdx_url", "wayback_match_type", "wayback_replay_url",
]

# -------------------------------------------------------------------------------- wayback
#
# THE URLS, NOT THE JUDGEMENT. Two tools here ask the Internet Archive different questions --
# "everything under this prefix, best capture each" and "every capture of exactly this file" --
# and they choose among the answers differently, for reasons written where each of them decides.
# What they were both writing out by hand is the ADDRESS, and an address written twice is an
# address that can be wrong in one place: a query that is not encoded asks about a different url
# and answers confidently about it.


# https, although one of the two callers asked over http until 2026-09-23 and the other did
# not. The Archive redirects the first to the second, so http cost a round trip per query and
# bought nothing; naming it once means the two cannot drift apart again.
WAYBACK_CDX_BASE = "https://web.archive.org/cdx/search/cdx"
WAYBACK_REPLAY_BASE = "https://web.archive.org/web/"

# The text form's columns, in order. The index returns them positionally, so a caller that asks
# for a different set has to read a different order -- which is why this is one string and not an
# assumption spread across a parser.
WAYBACK_CDX_FIELDS = "original,timestamp,statuscode,mimetype,length"


def wayback_match_type(source):
    """-> "prefix" or "domain", by what `source` is.

    A SOURCE WITH A PATH IS A PREFIX; A BARE HOSTNAME IS A DOMAIN, so that its subdomains come
    along. Asking for a bare host as a prefix finds only what was captured at exactly that host,
    and a site that moved between `www.` and no-`www.` over twenty years is then half missing --
    with nothing to show that it is.
    """
    return "prefix" if "/" in source.strip("/") else "domain"


def wayback_cdx_url(source, match=None, fields=WAYBACK_CDX_FIELDS, output=None, extra=""):
    """The index query for `source`. -> a url.

    ENCODED WITH safe="", AND THAT IS NOT A DETAIL. A url is going into a query VALUE here, so its
    own `?`, `&` and `/` must not survive as structure -- otherwise the Archive is asked a
    different question and answers it, correctly, about something else.

    `match` defaults to what wayback_match_type() says; `match=""` LEAVES IT OUT, which is not
    the same thing -- the index has its own default and a caller that was relying on it should go
    on relying on it rather than inherit a guess about what it is. `output="json"` asks for the
    JSON form,
    whose first row is a HEADER and whose columns are the `fields` in order; leaving it out gives
    the text form, one space-separated row per capture and no header. The two are parsed
    differently and neither is wrong, so the caller says which it wants.

    EVERY CAPTURE COMES BACK, not the best one. There is no "give me the largest" in this API, and
    choosing is the caller's -- the 2001 crawls carried a 1 MiB ceiling the 2000 crawls did not,
    so the newest capture of a big file is routinely the truncated one.
    """
    if match is None:
        match = wayback_match_type(source)
    return "%s?url=%s%s&fl=%s%s%s" % (
        WAYBACK_CDX_BASE,
        urllib.parse.quote(source, safe=""),
        "&matchType=" + match if match else "",
        fields,
        "&output=" + output if output else "",
        extra)


def wayback_replay_url(timestamp, url):
    """The stored bytes of one capture. -> a url.

    `id_` IS THE WHOLE POINT. Without it the Archive returns the page as it renders it, with its
    own banner and its rewritten links; with it, the bytes it stored. A copy made from the
    rendered form is a copy of the Archive, not of the site.

    A SCHEME IS ADDED WHEN THERE IS NONE, because one caller here carries urls as `host/path` --
    that is what its records hold -- and the replay address needs an absolute one. Written out by
    hand in that tool, the `http://` was easy to read as part of the format rather than as a
    repair; named here, it is neither hidden nor repeated.
    """
    if "//" not in url.split("?", 1)[0]:
        url = "http://" + url
    return "%s%sid_/%s" % (WAYBACK_REPLAY_BASE, timestamp, url)
