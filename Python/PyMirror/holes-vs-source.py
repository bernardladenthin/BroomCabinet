# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Ask each source whether the holes `--holes` found are in ITS copy too -- a few blocks at a time.

WHY THIS, AND WHY NOT THE OBVIOUS TWO ANSWERS. The first full `--holes` run found 67 files with
whole empty blocks inside them, 62 of them distinct. Three were settled by fetching them whole
and comparing: all three byte for byte identical to what the source serves, so our copies are
faithful and the damage is somebody else's. That is 130 MB for three files, and the other 59
include a 4 GB install image -- fetching them all is not a plan.

The other obvious answer was to widen `audit.check_holes`' `exempt` set: `.udf`, `.usb` and `.efs`
were flagged at 100 %, `.toast` at 57.6 %, and unallocated sectors in a disc image read as zeros
and always will. But `.toast` at 57.6 % means fourteen of thirty-three came back CLEAN -- so the
format does not always have holes, and exempting it would make a truncated `.toast` invisible
forever. Trading a class of real findings for a quiet report is the wrong way round.

WHAT THIS DOES INSTEAD, and it is the same trivial check made cheap: **ask for the holes, not for
the file.** An HTTP Range request for the 1 MiB block at offset N costs a megabyte. If the source
serves zeros at the same offsets, our copy is faithful there and the emptiness is the source's --
whatever the extension is, with no argument about formats and no list to maintain. Three blocks
per file settles it at 62 x 3 MB instead of tens of gigabytes.

WHY THREE BLOCKS AND NOT ONE. One block agreeing could be luck: a disc image has zeros nearly
everywhere, so hitting one is not evidence about the file. The first, middle and last empty block
are spread across the whole file, and all three agreeing is a statement about the shape of the
damage rather than about one offset. It is still a SAMPLE, and the report says so -- a file whose
three blocks agree is recorded as "consistent with the source", not as proven identical. The three
that were fetched whole keep their stronger record in `HOLES_AT_SOURCE`.

WHAT A DISAGREEMENT MEANS, and it is the outcome worth having: the source has content where we
have nothing. That file is a **re-fetchable loss** -- the best kind of finding this collection can
produce, and the one nothing else has ever been able to see.

IT CHANGES NOTHING. It reads the collection, asks for ranges, and prints.

    python holes-vs-source.py --dry-run          # what it would ask, and of whom
    python holes-vs-source.py --under bitsavers  # one archive
"""
import argparse
import io
import os
import sys
from urllib.parse import urlsplit

import mirror
from common import (MIRROR_ROOT, Pacer, http_open, human, long_path, say, source_url)

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "measurements", "holes-run")

BLK = 1 << 20
SAMPLE = 3          # first, middle, last empty block -- see the module docstring
TIMEOUT = 120
PER_HOST_PAUSE = 1.0

SAME = "the source has the same holes"
CONTENT = "THE SOURCE HAS CONTENT WHERE WE HAVE NOTHING -- re-fetchable"
NO_RANGE = "the server ignored the range request"
REFUSED = "the server answered, but not with the file"
GONE = "nobody answered"
UNASKABLE = "no source URL recorded"
ORDER = (CONTENT, NO_RANGE, REFUSED, GONE, SAME, UNASKABLE)


def findings(logs=LOGS):
    """-> [(archive, relative path)] read out of the run's own logs.

    THE LOGS ARE THE RECORD. Re-running `--holes` to find out what it found would be 2.39 TB and
    five and a half hours; `holes-record-test.py` already checks that these files say what the
    run reported.
    """
    import re
    row = re.compile(r"^\s+[\d.]+ MB\s+\d+/\s*\d+ blocks empty \([\d.]+ %\)\s+(.*)$")
    out = []
    for name in sorted(os.listdir(logs)):
        if not name.endswith(".log"):
            continue
        with io.open(os.path.join(logs, name), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = row.match(line.rstrip("\n"))
                if m:
                    out.append((name[:-4], m.group(1).replace("\\", "/")))
    return out


def empty_blocks(path, limit=SAMPLE):
    """-> ([block indices to sample], total blocks). Reads the local file once."""
    zero = bytes(BLK)
    empty, total = [], 0
    with io.open(long_path(path), "rb") as fh:
        while True:
            b = fh.read(BLK)
            if not b:
                break
            if b == zero[:len(b)]:
                empty.append(total)
            total += 1
    if len(empty) <= limit:
        return empty, total
    # First, middle and last: spread across the file, so three agreeing says something about the
    # shape of the damage rather than about one offset.
    return [empty[0], empty[len(empty) // 2], empty[-1]], total


# AN ARCHIVE TAKEN OVER RSYNC THAT ALSO SERVES THE SAME TREE OVER HTTP.
#
# `mirror.ARCHIVES` records the address a crawl USED, which for bitsavers is an rsync module --
# and rsync is not a protocol this tool speaks. That left 21 of the 67 findings unaskable, every
# one of them bitsavers, which is a third of the whole question.
#
# The same paths are served over HTTPS, and that is not an assumption: the two damaged PDFs in
# `HOLES_AT_SOURCE` were fetched whole from `https://bitsavers.org/www.computer.museum.uq.edu.au/`
# on 2026-09-25 and matched byte for byte. One entry, with the evidence, beats either guessing a
# scheme or leaving a third of the findings unanswered.
#
# A SEPARATE TABLE AND NOT A FIX TO THE REGISTER, because the register is a record of what was
# done and this is a convenience for asking questions afterwards. Editing the first to suit the
# second would make the crawl's own history less true.
#
# THE TABLE AND source_url() MOVED TO common.py ON 2026-09-27, with this reasoning and the
# bitsavers evidence. They were spelled out identically here and in truncated-vs-source.py, and a
# THIRD tool asking the same question -- ask-the-source.py -- had its own version without the
# fallback and so answered "unaskable" for every bitsavers path. Three copies, two of them
# agreeing, and no test able to see the third disagree.


def one_block(url, index, opener=None):
    """-> (verdict-ish string or None, bytes). Never raises.

    THROUGH `common.http_open`, NOT `urllib` DIRECTLY, and there are two reasons rather than one.
    The visible one is a contract this collection keeps and a test enforces: `urlopen` is called
    in exactly one file. The one that matters is what that contract buys -- `http_open` carries
    the collection's identity, and the first version of this tool built its own `Request` and
    therefore asked somebody's server for a megabyte with no User-Agent at all. Its docstring
    names this exact case: "so a Range or an Accept is possible and the User-Agent cannot be
    dropped by accident."

    A 206 is the only answer that means anything. A 200 means the server ignored the range and is
    sending the WHOLE file, which must not be read to the end -- some of these are gigabytes --
    so it is reported and the file left alone.
    """
    start = index * BLK
    header = {"Range": "bytes=%d-%d" % (start, start + BLK - 1)}
    try:
        with http_open(url, timeout=TIMEOUT, extra_headers=header, opener=opener) as resp:
            code = resp.getcode()
            if code == 200:
                return NO_RANGE, b""
            if code != 206:
                return REFUSED, b""
            return None, resp.read(BLK)
    except Exception as exc:                                    # noqa: BLE001
        return (REFUSED if isinstance(getattr(exc, "code", None), int) else GONE), b""


def judge(blob):
    """Is this block still nothing? -> True when it is."""
    return blob.strip(bytes(1)) == b""


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=MIRROR_ROOT,
                    help="the collection (default %(default)s)")
    ap.add_argument("--logs", default=LOGS, help="where the --holes run left its logs")
    ap.add_argument("--under", help="only findings in this archive")
    ap.add_argument("--sample", type=int, default=SAMPLE,
                    help="empty blocks to ask about per file (default %(default)s)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be asked, ask nothing")
    args = ap.parse_args(argv)

    rows = [(a, r) for a, r in findings(args.logs) if not args.under or a == args.under]
    if not rows:
        say("no findings recorded under %r" % (args.under or args.logs))
        return 2

    register = dict(mirror.ARCHIVES)
    say("=== %d finding(s), sampling %d empty block(s) each ===" % (len(rows), args.sample))

    pacer = Pacer(PER_HOST_PAUSE)
    counts = {}
    asked = 0
    for archive, rel in rows:
        url = source_url(archive, rel, register)
        path = os.path.join(args.root, archive, rel.replace("/", os.sep))
        if url is None:
            counts.setdefault(UNASKABLE, []).append((archive, rel, ""))
            continue
        if args.dry_run:
            say("    %-16s %s" % (archive, rel[:70]))
            say("        %s" % url[:110])
            continue

        picks, total = empty_blocks(path, args.sample)
        verdict, detail = SAME, "%d/%d blocks empty" % (len(picks), total)
        for index in picks:
            pacer.wait(urlsplit(url).netloc)
            asked += 1
            problem, blob = one_block(url, index)
            if problem:
                verdict, detail = problem, "at block %d" % index
                break
            if not judge(blob):
                verdict = CONTENT
                detail = "block %d of %d: %d B, begins %r" % (index, total, len(blob), blob[:8])
                break
        counts.setdefault(verdict, []).append((archive, rel, detail))
        if verdict in (CONTENT, NO_RANGE):
            say("  %-14s %s" % (verdict.split(" --")[0][:14], rel[:70]))

    if args.dry_run:
        return 0

    for verdict in ORDER:
        items = counts.get(verdict)
        if not items:
            continue
        say("\n  %s -- %d" % (verdict, len(items)))
        if verdict in (CONTENT, NO_RANGE, REFUSED, GONE):
            for archive, rel, detail in sorted(items):
                say("    %-16s %-60s %s" % (archive, rel[:60], detail))

    total = sum(len(v) for v in counts.values())
    say("\n  %d file(s), %d range request(s), %s asked for"
        % (total, asked, human(asked * BLK)))
    if total != len(rows):
        say("  THE SUMMARY DOES NOT ADD UP -- a verdict is missing from ORDER")
        return 2
    return 1 if counts.get(CONTENT) else 0


if __name__ == "__main__":
    sys.exit(main())
