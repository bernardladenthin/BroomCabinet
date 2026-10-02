# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Re-check the decisions mirror.py has written down permanently. Reads only; fetches nothing.

WHY DECISIONS NEED RE-CHECKING AND FILES DO NOT. `--verify` and verify-content.py test what is on
disk, and a file that verified once verifies forever. mirror.py's LOST, FROZEN and CANDIDATES
lists are a different kind of claim: each is a statement about the world OUTSIDE this collection,
made on one day, and the world moves. A host comes back. A robots.txt is rewritten. A candidate
quietly closes. Nothing on disk changes when any of that happens, so nothing on disk can detect it.

A wrong entry here is worse than a missing file, because of what the lists are FOR: LOST and
FROZEN exist to stop anyone looking again. A host wrongly in LOST is not an absence, it is a
closed question.

TWO MISTAKES THIS TOOL EXISTS TO CATCH, both of which this collection has actually made.

  1. THE APEX AND `www.` ARE DIFFERENT NAMES. `crynwr.com` answers on 45.79.140.191 while
     `www.crynwr.com` does not resolve at all. A host declared dead on the strength of one name
     may be alive under the other, and one probe cannot tell. Both are tried, always.

  2. A robots READING IS EVIDENCE ONLY FOR THE HOST IT WAS READ FROM. `update.uu.se` serves no
     robots.txt on its FTP vhost and names ClaudeBot explicitly on its web vhost -- same club,
     same people. A 404 on one vhost is not permission when the organisation has said no on
     another, so the recorded verdict wins over a fresh green light; this tool reports the
     difference and never resolves it.

INTENT IS NOT SYNTAX. 4corn.co.uk lists 45 AI agents and gives them an EMPTY `Disallow:`, which
by the letter of the standard permits everything. It is a mistake in their file, not an invitation,
and this collection honours what they meant. Such a group is reported as NO-OP BLOCK rather than
as open -- a machine may not read a typo as consent.

AN UNANSWERED QUESTION IS NOT A NO. A timeout, a 429 or a DNS failure from here is a statement
about this run, not about the host. Those come back as UNKNOWN and are never folded in with the
refusals.

    python recheck-decisions.py                 # everything, differences highlighted
    python recheck-decisions.py --only lost     # lost | frozen | candidates | bases
    python recheck-decisions.py --quiet         # print only what no longer matches the record
"""
import argparse
import http.client
import io
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

from common import (MIRROR_ROOT, ARCHIVE_MARKERS, Pacer, host_of, http_open, http_try,
                    reach, scheme_drift,
                    load_mirror, looks_like_a_placeholder_page, page_title)
from robots import robots_verdict


# Tokens in a CANDIDATES note that record an OPERATOR'S REFUSAL -- a decision by a person, which
# a robots.txt cannot revoke. If one is present, a fresh "open" reading is a DIFFERENCE to be read
# by a human, never an opening.
REFUSAL_TOKENS = ("NAMES US", "BLANKET REFUSAL", "OPERATOR REFUSAL", "HONOURED INTENT",
                  "ROBOTS.TXT DISALLOWS", "ROBOTS DISALLOWS", "PERMISSION")

# Tokens that record a reason which is NOT a refusal and has nothing to do with robots.txt.
# Keeping these out of REFUSAL_TOKENS matters: the first run of this tool reported `adoxa-dos`
# and `pelikonepeijoonit.net` as "recorded as a refusal, robots.txt no longer says so" when
# neither was ever a robots question -- adoxa's downloads sit behind `dl.php?f=` and cannot be
# walked, and pelikonepeijoonit was serving malware. A tool that files every reason under
# "refusal" manufactures drift that is not there, which is worse than missing drift: it trains
# the reader to skim the exceptions.
OTHER_REASON_TOKENS = ("NOT CRAWLABLE", "COMPROMISED", "REDUNDANT", "ALREADY SAFE",
                       "TOO BIG", "NOT A NEW HOST", "CLOSED", "ALREADY GONE", "THE BYTES ARE")

# A LOST or FROZEN note that ALREADY DESCRIBES a host as answering-but-empty. The record for
# `support.bull.com` says "Now a Salesforce login shell"; for `linkitup.de` it says "parked".
# Both therefore answer, and both are exactly as lost as the record states. Without this the tool
# raises the same two `!!` on every run forever, and a permanent alarm is one a reader learns to
# skim -- which costs more than the alarm was ever worth.
#
# An answer that does NOT match the note still surfaces: these tokens suppress the flag only when
# the probe found the kind of emptiness the note describes.
EXPLAINED_TOKENS = ("PARKED", "LOGIN", "SALESFORCE", "PLACEHOLDER", "FOR SALE", "SHELL",
                    "STOCK", "ANSWERS 404", "IDENTICAL", "SQUATT")


HOSTISH = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}")


def hosts_in(key):
    """EVERY hostname a record key mentions, apex and www. form, deduplicated in order.

    ONE KEY CAN NAME SEVERAL HOSTS. LOST carries
    `www.rootvg.net / www.aixmind.com / ppckernel.org / mach-linux.org / gd.tuwien.ac.at`
    as a single entry -- five sites that died together. An earlier version of this took the text
    up to the first "/", probed `rootvg.net ` (with the trailing space) and left four hosts
    unasked while printing a line that looked like a complete answer.

    The apex and the www. form are BOTH returned because they are different names: `crynwr.com`
    resolves and `www.crynwr.com` does not, and a host written off on one of them may be alive
    under the other.
    """
    text = key.strip().lower()
    if "://" in text:
        text = text.replace("://", " ")
    out = []
    for m in HOSTISH.finditer(text):
        h = m.group(0).rstrip(".").split("@")[-1].split(":")[0]
        bare = h[4:] if h.startswith("www.") else h
        for name in (bare, "www." + bare):
            if name not in out:
                out.append(name)
    return out


def hosts_for_entry(key, root):
    """-> (hostnames, how). Resolves a record key to something probeable, or explains why not.

    FROZEN IS KEYED BY ARCHIVE NAME, NOT BY HOSTNAME -- `aixtools`, `bullfreeware`, `next-68k-org`.
    The first run of this tool found none of them probeable, checked nothing, and still printed
    "none answer under either name -- the record still holds". That sentence is indistinguishable
    from a real all-clear, which is the failure this collection keeps meeting: a checker that reads
    nothing and a checker that finds nothing print the identical line.

    So an archive name is resolved through the archive's own completion marker, which records the
    origin it was taken from, and anything still unresolved is counted as NOT CHECKED.
    """
    direct = hosts_in(key)
    if direct:
        return direct, ""
    base = os.path.join(root, key)
    if os.path.isdir(base):
        for cand in ARCHIVE_MARKERS:
            p = os.path.join(base, cand)
            if not os.path.exists(p):
                continue
            try:
                with io.open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                # Deliberately NOT a bare `except Exception`. A blanket catch here swallowed a
                # NameError (this file had no `import io`) and reported all nine FROZEN entries as
                # "no origin in a marker" -- a code defect wearing the costume of a finding.
                continue
            hosts = []
            # ftp:// too. `agilent-ftp-2009` and `dec-ftp-2006` were unpacked from bitsavers tars,
            # and their markers name the origin only as `ftp://ftp.agilent.com/pub/callpub/`.
            # Matching http(s) alone left the two oldest entries in FROZEN unchecked.
            for m in re.finditer(r"(?:https?|ftp)://([A-Za-z0-9.-]+)", text):
                h = m.group(1).lower().rstrip(".")
                if "archive.org" in h:
                    continue
                bare = h[4:] if h.startswith("www.") else h
                for name in (bare, "www." + bare):
                    if name not in hosts:
                        hosts.append(name)
            if hosts:
                return hosts, "via %s" % cand
    return [], "no hostname in the key and no origin in a marker"


# TITLE_RE lived here until 2026-09-27, one of five copies of the same regex across this
# directory. It is common.page_title() now -- and the copies had already drifted: this one
# never fell back to <h1>, which is the tag the stock server pages below actually use.
#
# THAT FALLBACK IS A BEHAVIOUR CHANGE HERE, and in the wanted direction: a host answering with an
# Apache autoindex used to be reported with no title at all, because an autoindex names itself in
# <h1> and nothing else. It now reads `Index of /pub`, which is the single most promising thing a
# host in LOST can say -- see the note under PARKED. Neither "Index of /" nor an autoindex body is
# a placeholder marker, so the richer title cannot make one look dead.

# PARKED, STUB_BODIES and the "too small to be a page" rule are common.py's since 2026-09-27,
# as PLACEHOLDER_TITLES, STUB_BODIES and looks_like_a_placeholder_page(). They went with their
# reasoning, including the one rule most worth re-reading: "Index of /" is NOT a placeholder
# marker. An autoindex is the single most promising thing a host in LOST can answer, and the
# first draft of STUB_BODIES had "<h1>index of" in it, three lines under the comment warning
# against exactly that.
#
# find-html-imposters.py's "parking" class asks a looser version of the same question over a
# whole body. Both now sit beside each other in the library instead of in two files that could
# learn different vocabularies.


def probe(host, timeout=20):
    """-> (state, alive). `alive` means a server is there AND the answer is not obviously empty.

    THE STATUS CODE IS NOT ENOUGH, twice over.

    A 5xx is not a return. HTTP 522 in particular is Cloudflare's own code for "I resolved, the
    origin did not answer" -- DNS and a CDN survive the machine behind them for years. Treating
    that as alive puts a permanent `!!` next to a host that is exactly as dead as the record says.

    A 200 is not a return either. A lapsed domain is bought, parked, and answers 200 forever, so
    the page TITLE is read and reported: it is the cheapest thing that separates a revived archive
    from a sales page, and no status code can do it.
    """
    try:
        socket.gethostbyname(host)
    # WHAT gethostbyname RAISES: gaierror, which is an OSError, and UnicodeError for a name
    # too long to encode. Measured. Anything else here is a defect in this file, and this
    # function has already been wrong about every host in the collection once today.
    except (OSError, UnicodeError):
        return "no DNS", False
    for scheme in ("https", "http"):
        try:
            with http_open("%s://%s/" % (scheme, host), timeout=timeout) as r:
                body = r.read(8192)
                text = body.decode("utf-8", "replace")
                title = (page_title(text) or "")[:44]
                # A STUB IS NOT A SITE, and a parked domain is not one either -- the library
                # tells them apart and says which. `download.aixtools.net` answers 200 with 44
                # bytes of Apache's stock "It works!" and no title at all, so a title-only test
                # calls it alive and puts a permanent `!!` on an archive whose own marker says
                # the origin is gone.
                why = looks_like_a_placeholder_page(text, title=title)
                stub = why is not None and why[0] == "stub"
                parked = why is not None
                return ("%s %d, %d B%s%s"
                        % (scheme, r.status, len(body),
                           "  \"%s\"" % title if title else "",
                           "  [STUB]" if stub else ("  [PARKED?]" if parked else "")), not parked)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return "%s HTTP %d (refusing, not gone)" % (scheme, exc.code), True
            if 500 <= exc.code < 600:
                # Includes Cloudflare's 52x family: the edge lives, the origin does not.
                return "%s HTTP %d (server/origin error, not a return)" % (scheme, exc.code), False
            return "%s HTTP %d" % (scheme, exc.code), False
        # A HOST THAT DOES NOT ANSWER IS NOT THE SAME AS A BUG IN THIS FILE, and for a while
        # this could not tell them apart. It was `except Exception: continue`, and the body
        # called `http_open` -- a name that was never imported. NameError is an Exception, so
        # every probe fell through both schemes and returned "DNS resolves, nothing answers" for
        # EVERY host, including ones this collection was fetching from the same day. The tool
        # whose job is to notice a dead archive coming back reported the whole world as dead,
        # with no error and no clue. Found by ruff on 2026-09-24, which until then ran only in CI.
        #
        # So the net is cast at network failures and nothing else. A programming error now takes
        # the run down, which is the correct outcome: a probe that cannot run is not a probe that
        # found nothing.
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
            continue
    return "DNS resolves, nothing answers", False


def get(url, timeout=25, limit=200000):
    """The library's http_try, with this tool's limits. Carried here as its own try/except
    until 2026-09-23, identically to two other tools."""
    return http_try(url, timeout=timeout, limit=limit)


def section_hosts(mod, key, quiet, pacer, root):
    """LOST and FROZEN: is anything here answering under a name nobody tried?"""
    entries = getattr(mod, key, {}) or {}
    resolved, unresolved, probes = [], [], 0
    for name in sorted(entries):
        hosts, how = hosts_for_entry(name, root)
        if hosts:
            resolved.append((name, hosts, how))
            probes += len(hosts)
        else:
            unresolved.append((name, how))

    print("=== %s -- %d entries, %d resolved to %d hostname(s)"
          % (key, len(entries), len(resolved), probes))
    if unresolved:
        print("  NOT CHECKED -- %d entr%s could not be resolved to a host:"
              % (len(unresolved), "y" if len(unresolved) == 1 else "ies"))
        for name, how in unresolved:
            print("     %-26s %s" % (name, how))

    surprises = []
    for name, hosts, how in resolved:
        # PACED PER HOST, WHICH IS WHY THE PAUSE MOVED IN HERE. One entry can name five hosts
        # that died together, and the old `time.sleep(pause)` at the foot of this loop probed
        # all five back to back and then waited -- a pause between strangers, and none between
        # the two requests one server actually gets. host_of wants a URL; the scheme is there
        # only so urlsplit sees a netloc, and folding `www.` is right because hosts_in() returns
        # both spellings of every name and they are, in practice, one machine.
        row = []
        for h in hosts:
            pacer.wait(host_of("http://" + h))
            row.append((h,) + probe(h))
        live = [r for r in row if r[2]]
        note = (entries.get(name) or "").upper()
        explained = [t for t in EXPLAINED_TOKENS if t in note]
        if live and explained:
            # The note already says this host answers with nothing. Report it, do not alarm on it.
            live, how = [], "answers, and the record says why: \"%s\"" % explained[0].lower()
        if live:
            surprises.append((name, live))
        if live or not quiet:
            print("  %s %-26s %s%s"
                  % ("!!" if live else "  ", name[:26],
                     "   |   ".join("%s: %s" % (h, s) for h, s, _a in row),
                     "   (%s)" % how if how else ""))

    if surprises:
        print("\n  %d of %d ANSWER under at least one name. The loss may hang on ONE name:"
              % (len(surprises), len(resolved)))
        for name, live in surprises:
            print("     %-26s %s" % (name, ", ".join("%s (%s)" % (h, s) for h, s, _a in live)))
        print("  Answering is not the same as holding the files. Check before editing the record.")
    elif resolved:
        print("\n  none of the %d checked answer under any name -- for those, the record holds."
              % len(resolved))
    else:
        print("\n  NOTHING WAS CHECKED. This is not an all-clear.")
    return len(surprises) + len(unresolved)


def section_candidates(mod, quiet, pacer):
    cands = getattr(mod, "CANDIDATES", []) or []
    print("=== CANDIDATES -- %d entries" % len(cands))
    print("  %-24s %-8s %-12s %s" % ("candidate", "base", "robots", "note"))
    drift = 0
    for entry in cands:
        name, url = entry[0], entry[1]
        note = entry[3] if len(entry) > 3 else ""
        if not url or "://" not in url:
            continue
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https"):
            if not quiet:
                print("  %-24s %-8s %-12s %s" % (name, parts.scheme, "-", "not fetched over HTTP"))
            continue

        # The page and its robots.txt are one visit to one server, so the rate is claimed once
        # for the pair -- as it was before, when a single sleep followed both.
        pacer.wait(host_of(url))
        code, _body = get(url)
        rcode, rbody = get("%s://%s/robots.txt" % (parts.scheme, parts.netloc))
        text = rbody.decode("utf-8", "replace") if rcode == 200 and rbody.strip() else None
        verdict, why = robots_verdict(text, parts.path)

        # Case-insensitive on purpose. The notes write the verdict both ways -- "BLOCKED:
        # robots.txt disallows /ftp/" -- and an exact-case test missed both entries that this
        # collection is actually waiting on an operator for.
        upper = note.upper()
        recorded_refusal = any(t in upper for t in REFUSAL_TOKENS)
        other_reason = any(t in upper for t in OTHER_REASON_TOKENS)
        changed = ""
        if recorded_refusal and verdict == "OPEN":
            # A robots verdict covers THE PATH IT WAS ASKED ABOUT. `hpux.connect.org.uk` is
            # recorded at its apex, where nothing is disallowed, while the block that matters sits
            # on /ftp/ -- the whole binary tree. Reporting that as "no longer refuses" would be
            # false, and would quietly reopen a host this collection has decided to ask first.
            if parts.path in ("", "/"):
                changed = ""
                why = ("record cites a robots block on a DEEPER path; this check only covers %s"
                       % (parts.path or "/"))
            else:
                changed = "!! recorded as a refusal, robots.txt no longer says so -- RECORD wins"
                drift += 1
        elif verdict == "BLOCKED" and not recorded_refusal and not other_reason:
            changed = "!! newly blocked since the entry was written"
            drift += 1
        elif (isinstance(code, str) or (isinstance(code, int) and code >= 400)) and not other_reason:
            changed = "!! base URL no longer answers (%s)" % code
            drift += 1
        elif other_reason and not quiet:
            why = "recorded for a reason unrelated to robots.txt; %s" % why

        if changed or not quiet:
            print("  %-24s %-8s %-12s %s" % (name, code, verdict, (changed or why)[:60]))

    print("\n  %d entr%s differ from the record." % (drift, "y" if drift == 1 else "ies"))
    if drift:
        print("  A DIFFERENCE IS NOT AN INSTRUCTION. A host that stopped refusing today may have")
        print("  lost its robots.txt in a server move; a refusal recorded from a human is not")
        print("  revoked by a file. Read the note before changing anything.")
    return drift


def section_bases(mod, quiet, pacer):
    """Does every archive's OWN base URL still work? -> the number that no longer does.

    THE GAP THIS CLOSES, and this file already argued for it in its own first paragraph: LOST,
    FROZEN and CANDIDATES are "a statement about the world OUTSIDE this collection, made on one
    day, and the world moves". A BASE URL is exactly the same kind of claim and was the one this
    tool did not check -- it did not mention ARCHIVES at all.

    MEASURED 2026-10-02, after five days of getting it wrong. dreamlandbbs.com closed port 80 and
    moved to HTTPS; the base said `http://`, so every request went to a shut door and timed out at
    21.2 s. That was recorded three times as a rate-limit penalty and the archive was left alone,
    while 5 648 files and 14.05 GB stayed reachable over `https`. 51 of the 104 archives are
    registered on `http://` and nothing was watching any of them.

    IT PROBES PORTS, NOT PAGES. One TCP handshake per port says whether anything is listening,
    which is what distinguishes a stale record from a refusal; `scheme_drift` names the first and
    stays silent about the second rather than guessing. A 404 on a path is a different question and
    belongs to the tool that fetches.
    """
    print("=== ARCHIVES: does each base still answer? ===")
    bad = 0
    for name, base in mod.ARCHIVES:
        if not base.startswith("http"):
            continue                      # rsync:// is not a scheme this probes
        # TWO DIFFERENT NAMES FOR TWO DIFFERENT JOBS, and the first run of this section got it
        # wrong. host_of() strips a leading `www.` because that is what FOLDING AN INDEX needs --
        # one site should not grow two directory trees. A connection needs the name as written:
        # `dreamlandbbs.com` does not resolve while `www.dreamlandbbs.com` does, which is the
        # apex-vs-www hazard this file's own docstring describes in the opposite direction
        # (`crynwr.com` answers, `www.crynwr.com` does not). Probing the folded name reported DNS
        # failures for hosts that were answering.
        #
        # The PACER still keys on the folded name, which is right: two spellings are one operator
        # and should share one rate.
        host = urllib.parse.urlsplit(base).hostname
        if not host:
            print("  %-24s no host in the base URL: %s" % (name, base))
            bad += 1
            continue
        pacer.wait(host_of(base))
        got = reach(host)
        drift = scheme_drift(got)
        want = "https" if base.startswith("https") else "http"
        if got["dns"] is not None:
            print("  %-24s DNS FAILS: %s" % (name, got["dns"]))
            bad += 1
        elif drift and drift != want:
            print("  %-24s SCHEME DRIFT: registered %s, but port %d is shut and %s answers"
                  % (name, want, 80 if want == "http" else 443, drift))
            bad += 1
        elif all(v is not None for v in got["ports"].values()):
            # BOTH PORTS SHUT IS NOT A DRIFT and must not be reported as one. It is the shape of a
            # host refusing this address -- openpa reads exactly this -- or of one that is gone.
            print("  %-24s NOTHING LISTENING on 80 or 443 (refusal, or the host is gone)" % name)
            bad += 1
        elif not quiet:
            print("  %-24s ok" % name)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["lost", "frozen", "candidates", "bases"])
    ap.add_argument("--quiet", action="store_true",
                    help="print only entries that no longer match the record")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between hosts (default 1)")
    ap.add_argument("--root", default=MIRROR_ROOT,
                    help="the mirror root. FROZEN is keyed by ARCHIVE NAME, so resolving those "
                         "entries to a host means reading each archive's own marker.")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print("--root %s is not a directory. FROZEN cannot be resolved without it."
              % args.root)
        return 2

    mod = load_mirror()
    total = 0
    # --pause IS A RATE PER HOST, AND THIS IS THE TOOL WHERE THAT CHANGES THE MOST. It walks
    # every dead host the record knows, so a single global sleep made each probe wait on the
    # previous one's server -- hundreds of hosts paced against strangers they have nothing to do
    # with, and still nothing promised to the one host asked twice in a row. One Pacer for the
    # whole run, keyed by host, so a name that appears under LOST and again under CANDIDATES is
    # one rate. Elapsed time counts: a probe that spent 20 s timing out has already waited.
    pacer = Pacer(args.pause)
    for want, key in (("lost", "LOST"), ("frozen", "FROZEN")):
        if args.only in (None, want):
            total += section_hosts(mod, key, args.quiet, pacer, args.root)
            print("")
    if args.only in (None, "candidates"):
        total += section_candidates(mod, args.quiet, pacer)
        print("")
    if args.only in (None, "bases"):
        total += section_bases(mod, args.quiet, pacer)
        print("")

    print("%d item(s) no longer match what mirror.py records." % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
