#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""magic_mismatch and looks_like_an_error_page against real file heads, one per way a file can
lie about what it is.

WHY REAL BYTES. Two of these seven were found on 2026-09-24 by a check that had just been
widened, and neither could have been invented: `ZK-1933.gif` is a GIF missing exactly its first
byte, and `becvic.jpg` has its four-byte JPEG header overwritten with `yOya` while `JFIF` is
still legible two bytes later. Both are invisible to every other check here -- the length is
right, the hash matches what was recorded, and nothing in the file is zero.

THE THIRD ONE IS WHY THIS FILE EXISTS. `looks_like_html()` skipped a byte-order mark and leading
whitespace and not a leading COMMENT, so the most common error page in this collection --
`<!-- Copyright (C) Bull SAS - 2019 -->` before the doctype -- was reported as "does not begin
with the .jpg signature" rather than "HTML under a .jpg name". The vague answer sends a reader to
open the file; the precise one is finished. A fixture for that cannot be written from
imagination, because what is under test is where somebody else's CMS put its copyright line.

Each fixture is 512 BYTES, because magic_mismatch reads a head and never more -- except one that
is a whole 150-byte file, and is here for exactly that reason.

THE SECOND VERDICT, ADDED 2026-09-27, and the four fixtures it came with. `looks_like_an_error_page`
answers a different question -- not "is this file's NAME a lie" but "does this page ADMIT to being
a failure" -- and it was written because six of the eight `.cgi` files at spider.seds.org are
error pages served with HTTP 200 under the extension they are entitled to. Every check here was
right to stay silent about them.

AND THE FIXTURES PIN ITS LIMIT, which is the more useful half of what they say. The commonest
error page in this collection is titled `Bull Freeware`; the GeoCities one is `Yahoo! GeoCities`
and the Wayback one `Internet Archive Wayback Machine`. All three are a site's own template served
where a file was expected, and NONE of them admits anything -- so the title-only rule answers None
for all three, correctly and uselessly. They are caught by the other verdict in this same file,
because their NAMES are wrong. A page with a right name that fails SILENTLY is caught by neither,
and that is written down here rather than discovered twice.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "testdata", "heads")


def load():
    with io.open(os.path.join(DATA, "expected.json"), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    cases = load()
    bad = 0
    print()
    for case in cases:
        path = os.path.join(DATA, case["file"])
        with io.open(path, "rb") as fh:
            head = fh.read()

        # THE NAME THE FILE HAD IN THE COLLECTION, not the fixture's name. The verdict depends on
        # the extension, so testing the fixture's own name would test nothing that matters.
        name = os.path.basename(case["from"])
        got = common.magic_mismatch(name, head)
        want = case["verdict"]

        problems = []
        if got != want:
            problems.append("verdict %r, expected %r" % (got, want))

        # THE SECOND QUESTION, asked of every fixture and not only of the four that answer yes.
        # A rule is described as much by what it stays quiet about as by what it reports, and
        # `Bull Freeware` -- the commonest error page here -- is one of the quiet ones.
        complaint = common.looks_like_an_error_page(head)
        complaint = list(complaint) if complaint else None
        if complaint != case["error_page"]:
            problems.append("error page %r, expected %r" % (complaint, case["error_page"]))
        if len(head) != 512 and len(head) != case["full_size"]:
            problems.append("%d bytes, expected 512" % len(head))
        digest = common.sha256_bytes(head)
        if digest != case["head_sha256"]:
            problems.append("sha256 %s, recorded %s" % (digest[:12], case["head_sha256"][:12]))

        if problems:
            bad += 1
            print("  FAIL %-32s %s" % (case["file"], "; ".join(problems)))
        else:
            said = case["error_page"]
            print("  ok   %-32s %-46s %s%s"
                  % (case["file"], name[:46], got,
                     "" if not said else "  [%s %s: \"%s\"]" % (said[1], said[0], said[2])))

    print()
    # THE THREE THINGS THAT MUST NOT QUIETLY BECOME TRUE, checked here rather than left to the
    # reader: that the set is not empty, that the names are distinct, and that every fixture on
    # disk is accounted for. A test suite that silently runs zero cases is the failure mode this
    # collection has already met twice.
    on_disk = {n for n in os.listdir(DATA) if n.endswith(".head")}
    listed = {c["file"] for c in cases}
    if not cases:
        print("  FAIL no cases at all")
        bad += 1
    if len(listed) != len(cases):
        print("  FAIL a fixture is listed twice")
        bad += 1
    # AND THAT BOTH VERDICTS ARE ACTUALLY EXERCISED. A set where every error_page is None would
    # run the new check 17 times and demonstrate nothing -- the same failure as a suite that
    # silently runs zero cases, one level down.
    if not any(c["error_page"] for c in cases):
        print("  FAIL no fixture exercises looks_like_an_error_page")
        bad += 1
    if all(c["error_page"] for c in cases):
        print("  FAIL no fixture pins what it stays quiet about")
        bad += 1
    missing = on_disk - listed
    if missing:
        print("  FAIL on disk but not in expected.json: %s" % ", ".join(sorted(missing)))
        bad += 1
    absent = listed - on_disk
    if absent:
        print("  FAIL in expected.json but not on disk: %s" % ", ".join(sorted(absent)))
        bad += 1

    print("  %d head(s), %d of them error pages, %d failed"
          % (len(cases), sum(1 for c in cases if c["error_page"]), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
