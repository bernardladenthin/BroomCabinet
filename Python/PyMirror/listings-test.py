#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""parse_listing against real directory listings, one per form the collection actually holds.

WHY REAL PAGES. Every matcher in parse_listing was added because a REAL page had a shape the
others missed, and each one cost a run to find: a lighttpd table that parsed to nothing and left
1 955 PDFs behind in an archive marked COMPLETE; a frameset whose 1.72 GB came back as zero files
with no error anywhere; a FancyIndexing listing in DD-Mon-YYYY where every file arrived with no
size and no date. An invented example cannot reproduce any of that, because the thing being
tested is what somebody else's server writes.

WHERE THEY COME FROM. 287 112 stored pages were read on 2026-09-23 and sorted by what decides
their parse -- which matcher wins, which generator names itself, whether a size, a date, frames
or images are present. That gave 21 distinct forms, and the SMALLEST example of each is in
testdata/listings/, trimmed to the generator's own output. Twenty-one files, 116 KB.

WHAT IS PINNED. The href and the size of every entry, exactly. The date only as present or
absent: parse_date returns a LOCAL timestamp, and pinning one would make this test fail by the
machine's time zone -- parse_listing_test.py's first draft did exactly that and was wrong by
eight hours.

WHAT CATCHES A BROKEN MATCHER IS THE SIZE, NOT THE COUNT. A table that stops being recognised
still yields its links through the bare scan -- the same number of entries, with every size and
date gone, and with them the ETA and the date every file is stamped with. Measured by disabling
ROW_RE on purpose: four forms fail, and each reports `62 sizes lost, 62 dates lost` rather than
`63 entries != 63`, which is what the first draft printed and what tells a reader nothing.

The matcher recorded beside each form is a FIXTURE-INTEGRITY check -- "is this file still the
shape its name claims" -- and deliberately not an observation of the parse. Disabling a matcher
does not change it, which is exactly why the entries are the test.

    python listings-test.py
    python listings-test.py --rebuild     # after a deliberate change: rewrite expected.json
"""

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (FRAME_RE, IMG_SRC, LIGHTTPD_RE, PRE_RE, ROW_RE,  # noqa: E402
                    parse_listing, plural)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "testdata", "listings")
EXPECTED = os.path.join(DATA, "expected.json")


def matcher_for(body):
    """-> which matcher CAN read this page, by the same order parse_listing tries them.

    A FIXTURE-INTEGRITY CHECK, NOT AN OBSERVATION OF THE PARSE. It re-derives the choice rather
    than watching parse_listing make it, so it answers "is this file still the form its name
    says" and nothing more. Disabling a matcher inside parse_listing does not change this answer
    -- which is why the entries below, not this, are what catches a broken parse.
    """
    for label, matcher in (("row", ROW_RE), ("lighttpd", LIGHTTPD_RE), ("pre", PRE_RE)):
        if matcher is not PRE_RE and "</td>" not in body:
            continue
        if matcher.findall(body):
            return label
    return "bare"


def read(name):
    with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return fh.read()


def actual(name):
    body = read(name)
    rows = parse_listing(body)
    return {
        "bytes": len(body),
        "matcher": matcher_for(body),
        "entries": [[h, s, d is not None] for h, s, d in rows],
    }


def fixtures():
    return sorted(f for f in os.listdir(DATA) if f.endswith(".html"))


def rebuild():
    """Rewrite expected.json from what the code does NOW. Only after a deliberate change."""
    with io.open(EXPECTED, encoding="utf-8") as fh:
        old = json.load(fh)
    new = {}
    for name in fixtures():
        got = actual(name)
        got["archive"] = old.get(name, {}).get("archive", "?")
        got["trimmed"] = old.get(name, {}).get("trimmed", False)
        new[name] = got
    with io.open(EXPECTED, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(new, indent=1, sort_keys=True) + "\n")
    changed = [n for n in new if old.get(n, {}).get("entries") != new[n]["entries"]]
    print("  rewrote %s" % os.path.relpath(EXPECTED, HERE))
    print("  %s changed: %s" % (plural(len(changed), "form"), ", ".join(changed) or "none"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rebuild", action="store_true",
                    help="rewrite expected.json from the current code. Say this out loud: it "
                         "makes every difference disappear, which is the opposite of a test")
    args = ap.parse_args()

    if not os.path.isdir(DATA):
        return "no fixtures at %s" % DATA
    with io.open(EXPECTED, encoding="utf-8") as fh:
        expected = json.load(fh)

    if args.rebuild:
        return rebuild()

    have, want = set(fixtures()), set(expected)
    fails = []
    for name in sorted(have - want):
        fails.append("%s is not in expected.json" % name)
    for name in sorted(want - have):
        fails.append("%s is in expected.json but has no file" % name)

    for name in sorted(have & want):
        got, exp = actual(name), expected[name]
        where = "%-22s (%s)" % (name[:-5], exp.get("archive", "?"))
        if got["matcher"] != exp["matcher"]:
            fails.append("%s: matcher %s, expected %s -- size and date columns are at risk"
                         % (name, got["matcher"], exp["matcher"]))
            print("  FAIL %s  matcher %s != %s" % (where, got["matcher"], exp["matcher"]))
            continue
        if got["entries"] != exp["entries"]:
            # SAY WHAT DIFFERS, not how many there are. A matcher that stops firing still yields
            # the same links through the bare scan -- the same COUNT, with the sizes and dates
            # gone -- and "63 entries != 63" tells a reader nothing about that.
            lost_size = (sum(1 for _h, s, _d in exp["entries"] if s is not None)
                         - sum(1 for _h, s, _d in got["entries"] if s is not None))
            lost_date = (sum(1 for _h, _s, d in exp["entries"] if d)
                         - sum(1 for _h, _s, d in got["entries"] if d))
            how = []
            if len(got["entries"]) != len(exp["entries"]):
                how.append("%+d entries" % (len(got["entries"]) - len(exp["entries"])))
            if lost_size:
                how.append("%d sizes lost" % lost_size)
            if lost_date:
                how.append("%d dates lost" % lost_date)
            what = ", ".join(how) or "same count, different content"
            fails.append("%s: %s" % (name, what))
            print("  FAIL %s  %s" % (where, what))
            for a, b in list(zip(got["entries"], exp["entries"]))[:2]:
                if a != b:
                    print("         got  %s" % (a,))
                    print("         want %s" % (b,))
            continue
        extra = []
        if any(s is not None for _h, s, _d in got["entries"]):
            extra.append("size")
        if any(d for _h, _s, d in got["entries"]):
            extra.append("date")
        if FRAME_RE.search(read(name)):
            extra.append("frames")
        if IMG_SRC.search(read(name)):
            extra.append("images")
        print("  ok   %s  %-9s %3d entries  %s"
              % (where, got["matcher"], len(got["entries"]), ", ".join(extra) or "-"))

    print()
    if fails:
        print("  %s:" % plural(len(fails), "failure"))
        for f in fails:
            print("     %s" % f)
        return 1
    print("  %s, every one read as it was when it was captured"
          % plural(len(have), "form"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
