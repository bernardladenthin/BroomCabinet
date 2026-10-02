#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""robots.txt: reading what an operator asked for, and answering whether a path is allowed.

SPLIT OUT OF common.py ON 2026-09-23, unchanged. Two tools use it -- recheck-decisions.py to
ask whether a host that once refused still refuses, and its own test file.

IT IMPORTS NOTHING AT ALL, not even from the standard library. The whole section is string
handling over a small text format, and that is worth noticing: a file with no dependencies
cannot be broken by anything but itself.

WHAT IT IS FOR IS A DECISION, NOT A FETCH. robots.txt states what an operator is willing to
have crawled. This module reads that statement and reports it; whether to honour a refusal,
and what to record when one is found, belongs to the caller -- that judgement is not a library's
to make on somebody else's behalf.
"""

__all__ = ["OUR_AGENT_NAMES", "robots_groups", "robots_verdict", "sitemaps"]

# ---------------------------------------------------------------------------------- robots
#
# READING SOMEBODY ELSE'S REFUSAL IS THE ONE THING THIS COLLECTION CANNOT GET WRONG QUIETLY. A
# crawl that reads a refusal as permission is not a bug in a report; it is a thing done to another
# person's server. So the parsing is separate from the judgement: the first can be checked against
# real files, and the second against what those files were meant to say.


# The names this collection answers to. A robots.txt that mentions any of them is about us
# whatever else it says. Passed as a parameter so a caller asking on behalf of something else can
# say so, rather than reading this file's answer and believing it is their own.
OUR_AGENT_NAMES = ("claudebot", "anthropic-ai", "anthropic", "claude-web", "claude-searchbot")


def sitemaps(text):
    """-> the Sitemap: URLs a robots.txt declares, in order, without repeats.

    WHY A CRAWLER SHOULD WANT THIS. A sitemap is the OPERATOR'S OWN STATEMENT of what the site
    consists of, and that is a different kind of evidence from anything a crawl can produce. A
    crawl -- and measure-remote.py, which crawls -- discovers what is LINKED; a sitemap is what
    the person publishing it says is there. Comparing the two is how a mirror stops being "every
    file we could find" and becomes "every file the source lists".

    MEASURED 2026-10-02 ON openpa.net, which is why this function exists. Five days of crawling
    and harvesting had produced 679 files and no way to say whether that was all of them. The
    sitemap named 168 internal paths and the mirror held 168 of 168 -- the page side of the
    archive settled, for ONE REQUEST, by the operator rather than by our own link-following. A
    measurement run would have cost one HEAD per file and told us only what we already knew.

    SITEMAP IS NOT INSIDE A GROUP, and that is the one parsing subtlety. It is a file-level
    directive: it belongs to the host, not to the `User-agent` block it happens to sit under, and
    reading it as part of a group would attach somebody else's sitemap to somebody else's agent.
    robots_groups() therefore cannot answer this and the line is read on its own.

    AND ITS ABSENCE PROVES NOTHING. openpa.net declares no Sitemap: at all and serves
    /sitemap.xml perfectly well. So a caller that finds nothing here still has one cheap guess
    left; see find-sitemaps.py, which makes exactly that guess and no more.
    """
    out = []
    for raw_line in (text or "").splitlines():
        line = raw_line.split("#")[0].strip()
        # Case-insensitive on the KEY only -- a URL is case-sensitive after the host.
        if line[:8].lower() == "sitemap:":
            url = line[8:].strip()
            if url and url not in out:
                out.append(url)
    return out


def robots_groups(text):
    """-> [(agents, rules)] from a robots.txt, lower-cased, comments and blank lines gone.

    A GROUP IS THE THING, NOT THE FILE. One `Disallow` belongs to the `User-agent` lines directly
    above it, and a file may hold many groups. Reading the whole file as one blob reports another
    agent's rule as ours -- which is how a circulated blocklist of 188 named bots, none of them
    us, was nearly read as a blanket refusal of a host that permits everything.

    A new group starts at the first `User-agent` AFTER a rule, not at every `User-agent`: a run of
    agent lines with one Disallow beneath them is ONE group naming many agents, and splitting it
    would give each of them an empty rule set.

    Rules are kept verbatim, including the empty string. An empty `Disallow:` is the difference
    between a file that permits everything and a file whose author meant the opposite, and only
    the caller can weigh that.
    """
    groups, agents, rules = [], [], []
    for raw in (text or "").lower().splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        if line.startswith("user-agent:"):
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(line.split(":", 1)[1].strip())
        elif line.startswith("disallow:"):
            rules.append(line.split(":", 1)[1].strip())
    if agents or rules:
        groups.append((agents, rules))
    return groups


def robots_verdict(text, path, ours=OUR_AGENT_NAMES):
    """-> (verdict, reason) for fetching `path`. BLOCKED / NO-OP BLOCK / OPEN.

    THE THREE ANSWERS ARE NOT TWO. "BLOCKED" is a rule that reaches us. "OPEN" is a file with no
    such rule. "NO-OP BLOCK" is a file whose author plainly meant to refuse and whose syntax does
    not: a long list of AI agents with an EMPTY `Disallow:`, which by the letter of the standard
    permits everything. A machine may not read a typo as consent, and a caller that collapses
    this into OPEN has decided something it was not asked to decide.

    NO robots.txt AT ALL IS OPEN, and that is a statement about this file only. A host that serves
    none while the same organisation has refused elsewhere is not open, and nothing here knows
    that -- the caller does.

    ORDER MATTERS AMONG THE BLOCKS: being named beats a blanket rule, and a blanket rule beats a
    path match, because the reason a reader is given should be the most specific true one.
    """
    if text is None:
        return "OPEN", "no robots.txt"

    named = blanket = hit = noop = None
    for agents, rules in robots_groups(text):
        mentions_us = any(any(o in a for o in ours) for a in agents)
        effective = [r for r in rules if r]
        if mentions_us:
            if effective:
                named = "names us: %s -> Disallow: %s" % (
                    next(a for a in agents if any(o in a for o in ours))[:28], effective[0][:24])
            else:
                noop = ("names us in a group of %d agents, but its Disallow is EMPTY"
                        % len(agents))
        elif len(agents) >= 10 and not effective:
            # A long agent list with nothing disallowed is a broken block, not an open door.
            noop = noop or "%d agents listed with an EMPTY Disallow" % len(agents)
        if "*" in agents:
            if "/" in rules:
                blanket = "User-agent: * -> Disallow: /"
            else:
                for rule in effective:
                    if path.lower().startswith(rule.rstrip("*")):
                        hit = "User-agent: * -> Disallow: %s matches the path" % rule[:30]
                        break

    if named:
        return "BLOCKED", named
    if blanket:
        return "BLOCKED", blanket
    if hit:
        return "BLOCKED", hit
    if noop:
        return "NO-OP BLOCK", noop + " -- honour the intent, not the syntax"
    return "OPEN", "robots.txt carries no rule that reaches us"
