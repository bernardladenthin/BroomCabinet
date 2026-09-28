#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Read every stored page in the collection and report what parse_listing makes of it.

WHY THIS EXISTS. Every claim in parse_listing is a claim about what somebody else's server
writes, and the collection holds 288 000 pages written by those servers. So the claims can be
checked against reality without asking a single host anything -- no requests, no rate limits, no
answer that changes between two runs.

WHAT IT WOULD HAVE CAUGHT. `ps-2.kev009.com` was fetched, marked COMPLETE and left missing
`basil.holloway/` and its 1 955 PDFs, because its lighttpd listings parsed to nothing and a
directory that parses to nothing is indistinguishable from an empty one. Nothing failed; nothing
was logged. This run would have printed that directory as a page with in-scope links that the
parser does not see -- which is the only shape that finding ever has.

READ ONLY. It opens files and parses them in memory. Nothing under --root is written, renamed or
removed, and no network is touched.

    python corpus-coverage.py --root Q:\mirror
    python corpus-coverage.py --root Q:\mirror --sample 60      # 60 pages per archive, minutes
    python corpus-coverage.py --root Q:\mirror --archive tuhs

EXIT CODE. Non-zero when a page holds links that pass is_child_link and parse_listing still
returns nothing. That is the one outcome worth acting on; everything else is reported and
returns 0, because a content page with no children of its own is not a defect.

THE REASONS ARE ASKED OF THE LIBRARY, NOT RE-IMPLEMENTED. A first draft of this decided for
itself why a link had been rejected, comparing lowercase prefixes -- and reported eight pages as
gaps whose links began `JavaScript:` with a capital J. The parser had been right and the check
was wrong, which is the exact failure mode this tool exists to avoid. So it asks is_child_link.
"""

import argparse
import io
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (MIRROR_ROOT, BOOKKEEPING_FILES, FRAME_RE, IMG_SRC, LIGHTTPD_RE,  # noqa: E402
                    LINK_ODD_RE, LINK_RE, PRE_RE, ROW_RE, is_child_link,
                    iter_archives, looks_like_a_page, parse_listing, plural, say,
                    strip_fragment)

MAX_BYTES = 2 << 20          # a page larger than this is not a listing; reading it all is waste


def which_matcher(body):
    """-> the name of the matcher whose result parse_listing would use."""
    for label, matcher in (("ROW_RE", ROW_RE), ("LIGHTTPD_RE", LIGHTTPD_RE), ("PRE_RE", PRE_RE)):
        if matcher is not PRE_RE and "</td>" not in body:
            continue
        if matcher.findall(body):
            return label
    return "bare link scan"


def hrefs_in(body):
    """Every href the bare scan would see, in the same spelling parse_listing gives them."""
    out = [h for h in LINK_RE.findall(body)]
    out += [a or b or c for a, b, c in LINK_ODD_RE.findall(body)]
    out += [a or b or c for a, b, c in FRAME_RE.findall(body)]
    return out


def why_nothing(body):
    """-> a short reason parse_listing found no children on this page.

    IN-SCOPE IS ASKED OF is_child_link, never decided here. The whole value of this tool is that
    it reports what the crawler would do, and a second opinion about that is worth nothing.
    """
    hrefs = hrefs_in(body)
    if not hrefs:
        return "no links at all" if "<a" not in body.lower() else "links carry no href"
    kept = [h for h in hrefs if strip_fragment(h) and is_child_link(strip_fragment(h))]
    if kept:
        return "GAP: %s in scope, none read" % plural(len(kept), "link")
    return "every link is out of scope"


def walk(root, only=None, sample=0):
    """Yield (archive, page path) for every stored page, archive by archive.

    The outer loop is common.iter_archives(): page-extensions.py carried the same one
    character for character until 2026-09-23. Which directories ARE archives is a fact
    about the collection; what to do inside one is this tool's business.
    """
    for name, archive in iter_archives(root, only):
        seen = 0
        for dirpath, _dirnames, files in os.walk(archive):
            for f in sorted(files):
                if f in BOOKKEEPING_FILES or not looks_like_a_page(f):
                    continue
                yield name, os.path.join(dirpath, f)
                seen += 1
                if sample and seen >= sample:
                    break
            if sample and seen >= sample:
                break


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=MIRROR_ROOT,
                    metavar="PATH", help="the mirror root (read only)")
    ap.add_argument("--archive", metavar="NAME", help="one archive instead of all of them")
    ap.add_argument("--sample", type=int, default=0, metavar="N",
                    help="stop after N pages per archive. 0, the default, reads every one")
    ap.add_argument("--show", type=int, default=12, metavar="N",
                    help="how many example paths to print per finding (default 12)")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        return "no such directory: %s" % args.root

    matchers, reasons = Counter(), Counter()
    gaps, columns = [], Counter()
    pages = unreadable = 0

    for archive, path in walk(args.root, args.archive, args.sample):
        try:
            if os.path.getsize(path) > MAX_BYTES:
                continue
            with io.open(path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            unreadable += 1
            continue
        pages += 1
        rows = parse_listing(body)
        if rows:
            matchers[which_matcher(body)] += 1
            columns["size" if any(s is not None for _h, s, _d in rows) else "no size"] += 1
            columns["date" if any(d is not None for _h, _s, d in rows) else "no date"] += 1
            if IMG_SRC.search(body):
                columns["embeds images"] += 1
            continue
        reason = why_nothing(body)
        reasons[reason.split(":")[0]] += 1
        if reason.startswith("GAP"):
            gaps.append((archive, path, reason))
        if pages % 20000 == 0:
            say("  ... %d pages" % pages)

    say("")
    say("  %s read from %s%s"
        % (plural(pages, "page"), args.root, ", %d unreadable" % unreadable if unreadable else ""))
    say("")
    say("  Which matcher answered:")
    for name, n in matchers.most_common():
        say("     %-18s %7d  %5.1f%%" % (name, n, 100.0 * n / max(pages, 1)))
    say("")
    say("  Columns recovered:")
    for name, n in columns.most_common():
        say("     %-18s %7d" % (name, n))
    say("")
    say("  Pages with no children, and why:")
    for name, n in reasons.most_common():
        say("     %-34s %7d  %5.1f%%" % (name, n, 100.0 * n / max(pages, 1)))

    if gaps:
        say("")
        say("  %s WHERE LINKS ARE IN SCOPE AND NONE WERE READ:" % plural(len(gaps), "PAGE").upper())
        say("  This is the shape a lost directory has. Nothing failed when it was fetched.")
        for archive, path, reason in gaps[:args.show]:
            say("     %-22s %-58s %s" % (archive, path[-58:], reason))
        if len(gaps) > args.show:
            say("     ... and %d more" % (len(gaps) - args.show))
        return 1

    say("")
    say("  No page holds an in-scope link the parser does not read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
