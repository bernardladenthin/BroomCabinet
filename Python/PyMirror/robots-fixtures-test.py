#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""robots_verdict against the real files, captured while the hosts still answer.

WHY THESE ARE STORED AND THE OTHERS ARE NOT. `robots_verdict_test.py` carries its cases as inline
strings, which was right when they were written and is not enough now: a robots.txt is the most
perishable evidence in this collection. It is a live statement, it can be rewritten tomorrow, and
several recorded decisions rest on one.

**Two of the four hosts named in that file already do not answer.** `update.uu.se` and
`hpux.connect.org.uk` both fail to connect as of 2026-09-24, so for those the inline text there is
the only record that survives. The two that do answer are captured here, with five more from hosts
this collection actively fetches from.

WHAT THIS PROVES THAT THE INLINE CASES CANNOT. The inline cases prove the FUNCTION reads a rule
correctly. These prove the DECISION still holds: `irixnet.org` still carries no rule that reaches
us, and `4corn.co.uk` still names us in a group of 45 with an empty Disallow. If either host
rewrites its file, this test fails and somebody has to look -- which is the whole point of
recording a decision about somebody else's wishes.

STORED WHOLE, not as a head. A robots.txt is a statement in its entirety and half of one says
something different from the whole. The largest is 4 909 bytes.
"""
import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from robots import robots_verdict  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "testdata", "robots")


def main():
    with io.open(os.path.join(DATA, "expected.json"), encoding="utf-8") as fh:
        cases = json.load(fh)
    bad = 0
    print()
    for case in cases:
        path = os.path.join(DATA, case["file"])
        with io.open(path, "rb") as fh:
            blob = fh.read()

        problems = []
        if len(blob) != case["bytes"]:
            problems.append("%d bytes, recorded %d" % (len(blob), case["bytes"]))
        digest = hashlib.sha256(blob).hexdigest()
        if digest != case["sha256"]:
            problems.append("sha256 %s, recorded %s" % (digest[:12], case["sha256"][:12]))

        got = robots_verdict(blob.decode("utf-8", "replace"), case["path"])
        want = tuple(case["verdict"])
        if tuple(got) != want:
            problems.append("verdict %r, recorded %r" % (got, want))

        if problems:
            bad += 1
            print("  FAIL %-24s %s" % (case["host"], "; ".join(problems)))
        else:
            print("  ok   %-24s %-26s %s" % (case["host"], case["path"][:26], got[0]))

    # THE TWO THAT ARE ALREADY GONE, named so the absence is a record rather than a gap. A
    # fixture directory that simply lacks them looks like nobody thought of them.
    print()
    print("  not captured, the hosts no longer answer (2026-09-24):")
    for host in ("update.uu.se", "hpux.connect.org.uk"):
        print("    %-24s only the inline case in robots_verdict_test.py survives" % host)

    on_disk = {n for n in os.listdir(DATA) if n.endswith(".txt")}
    listed = {c["file"] for c in cases}
    if on_disk != listed:
        print("  FAIL on disk but not listed: %s" % ", ".join(sorted(on_disk - listed) or ["-"]))
        print("  FAIL listed but not on disk: %s" % ", ".join(sorted(listed - on_disk) or ["-"]))
        bad += 1
    if not cases:
        print("  FAIL no cases at all")
        bad += 1

    print()
    print("  %d file(s), %d failed" % (len(cases), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
