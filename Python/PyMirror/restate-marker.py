# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Bring a completion marker's counts up to date after a DELIBERATE change to the tree.

WHY THIS HAD TO EXIST. A marker is written by one thing only: the end of a full crawl. So after
a targeted repair the tree is right and the marker is wrong, `--verify` reports a MISMATCH that
nobody caused, and the only ways out were to re-crawl a finished archive or to edit the marker by
hand. The first costs hours and a host's patience; the second leaves a completion claim with no
record of who moved it or why.

Measured on 2026-09-24, the day this was needed: removing 33 stored directory pages and fetching
the 520 files they were blocking moved `gsi-collection` by +487 files and +1.94 GB and
`ardent-tool` by +93 files. Both markers went stale the moment the repair worked.

WHAT IT REFUSES. It will not run without `--reason`, and the reason is written INTO the marker
rather than into a log, because the marker is what somebody reads in a year. It will not invent a
marker that does not exist -- an archive with no completion marker was never complete, and
saying it is now is not this tool's decision. It keeps every field the old marker carried,
including `source` and `permanent-404`, and only ever moves `files` and `bytes`.

WHAT IT DOES NOT CLAIM. `completed` keeps the ORIGINAL crawl's timestamp. The archive was
completed then; it was repaired today, and those are different facts. Overwriting the first with
the second would quietly turn a two-week-old mirror into a fresh one.

    python restate-marker.py --root Q:\mirror --archive gsi-collection \
        --reason "33 blocked directory pages removed, 519 files fetched"      # dry run
    python restate-marker.py ... --apply
"""
import argparse
import io
import os
import re
import sys

from common import (COMPLETE_MARKER, human, long_path, marker_text, read_marker, say, scan_tree,
                    write_marker)

# The word that says a marker was not written by a crawl. Restating twice does not stack two
# notes -- the prose is rebuilt each time, so the newest reason replaces the previous one.
#
# WHAT THAT COSTS, SAID PLAINLY: only ONE hop back is recorded. After a second restate the note
# names the count the second repair started from, and the crawl's original figure is gone from
# the file. That is acceptable while repairs are rare and each one is written up elsewhere; it
# would not be if this became routine, and the fix then is a list rather than a sentence.
#
# IT BECAME A LIST ON 2026-10-02, the day the paragraph above came true. ardent-tool was restated
# a SECOND time -- 25701 -> 25733, for 32 pages its own sitemap.xml names and no page links -- and
# the dry run showed the FIRST restatement gone from the preview: the +25 files from a removed
# directory page, and with them the crawl's own original figure of 25608. The paragraph above was
# right about the cost and right about the fix; the only thing left was to stop predicting it.
#
# EACH LINE IS ONE REPAIR, oldest first, so the chain back to what the crawl itself wrote stays
# unbroken however many follow. Earlier lines are carried across VERBATIM: they are somebody's
# record of what they did, and rewording them in passing would be the same loss as dropping them,
# made quieter. A marker written before this change has its one repair as a bare paragraph, and
# that paragraph is recovered as the first entry rather than discarded.
RESTATED = "RESTATED"
# What a repair line starts with. Read as well as written, so the list survives the next restate.
ENTRY = "  * "


def restate(root, archive, reason, apply_it=False, report=say):
    """Move one marker's counts onto the current tree. -> (old, new) as (files, bytes) pairs.

    -> None if there is no marker to restate, which is not an error here: an archive that was
    never marked complete has nothing for this tool to correct.
    """
    path = os.path.join(root, archive, COMPLETE_MARKER)
    if not os.path.exists(long_path(path)):
        report("  %-22s no completion marker -- nothing to restate" % archive)
        return None

    fields = read_marker(path)
    try:
        old = (int(fields["files"]), int(fields["bytes"]))
    except (KeyError, ValueError):
        report("  %-22s marker carries no usable counts -- left alone" % archive)
        return None

    new = scan_tree(os.path.join(root, archive))
    report("  %-22s %d -> %d files, %s -> %s"
           % (archive, old[0], new[0], human(old[1]), human(new[1])))
    if old == new:
        report("  %-22s already agrees with the tree" % "")
        return (old, new)

    fields["files"] = str(new[0])
    fields["bytes"] = str(new[1])
    # The marker as it stands. Its earlier repair lines are not in `fields` -- read_marker returns
    # the header -- so the file itself is the only place to carry them from.
    with io.open(long_path(path), encoding="utf-8", errors="replace") as fh:
        existing = fh.read()
    prose = _prose(old, new, reason, existing)
    if apply_it:
        write_marker(path, fields, prose)
        report("  %-22s written" % "")
    else:
        report("")
        report(marker_text(fields, prose))
    return (old, new)


FROM = re.compile(r"^from (\d+) files and (\d+) bytes", re.M)


def earlier_entries(text, reached=None):
    """-> the repair lines an existing marker already carries, verbatim and in order.

    Two shapes exist and both have to be read. A marker restated since 2026-10-02 carries one
    ENTRY line per repair. One restated before that carries a single paragraph instead, and the
    paragraph is recovered as the first entry -- dropping it is the loss this function was written
    to stop.

    `reached` IS WHAT THE OLD SHAPE CANNOT SAY FOR ITSELF, and leaving it out broke the promise
    this change was made to keep. The old paragraph records only the figures the repair moved
    AWAY from -- "from 25608 files" -- because the figures it moved TO were simply the header. By
    the time a second restate reads it the header has moved on, so the first entry would arrive
    with no destination and the chain would still have a hole in it where the crawl used to be.
    The caller knows the missing number: it is the count this restate is itself moving away from.
    """
    if RESTATED not in (text or ""):
        return []
    tail = text.split(RESTATED, 1)[1]
    lines = [ln[len(ENTRY):].rstrip() for ln in tail.splitlines() if ln.startswith(ENTRY)]
    if lines:
        return lines
    out = []
    for ln in tail.splitlines():
        if ln.startswith("`completed`"):
            break
        stripped = ln.strip()
        if (not stripped or stripped.startswith(":") or stripped.startswith("from ")
                or stripped.endswith("deliberate repair:")):
            continue
        out.append(stripped)
    joined = " ".join(out).strip()
    if not joined:
        return []
    was = FROM.search(tail)
    if was and reached:
        joined = ("%s -> %s files, %s -> %s bytes: %s"
                  % (was.group(1), reached[0], was.group(2), reached[1], joined))
    return [joined]


def _prose(old, new, reason, existing=""):
    """The words under the header. They must say that a crawl did not write this."""
    # `old` is both this repair's starting point and the previous one's destination.
    entries = earlier_entries(existing, reached=old)
    entries.append("%d -> %d files, %d -> %d bytes: %s" % (old[0], new[0], old[1], new[1], reason))
    return ("This mirror is complete. `--fresh` refuses to run while this file exists;\n"
            "delete it by hand if you really mean to fetch the whole archive again.\n"
            "`--verify` compares the tree against the two figures above.\n"
            "\n"
            "%s: the two figures above are NOT the crawl's. Every deliberate repair since,\n"
            "oldest first -- the first `->` on the list is where the crawl itself left off:\n"
            "%s\n"
            "`completed` above is still the crawl's date, not any repair's."
            % (RESTATED, "\n".join(ENTRY + e for e in entries)))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="directory holding one subdirectory per archive")
    ap.add_argument("--archive", action="append", required=True,
                    help="archive to restate; repeatable")
    ap.add_argument("--reason", required=True,
                    help="what changed the tree. Written into the marker, not into a log.")
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without it the new marker is printed and nothing moves.")
    args = ap.parse_args(argv)

    if not args.reason.strip():
        ap.error("--reason must say something")

    moved = 0
    for archive in args.archive:
        result = restate(args.root, archive, args.reason.strip(), args.apply)
        if result and result[0] != result[1]:
            moved += 1
    if not args.apply and moved:
        say("")
        say("  Dry run. Nothing was written. Add --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
