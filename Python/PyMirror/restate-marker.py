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
import os
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
RESTATED = "RESTATED"


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
    prose = _prose(old, new, reason)
    if apply_it:
        write_marker(path, fields, prose)
        report("  %-22s written" % "")
    else:
        report("")
        report(marker_text(fields, prose))
    return (old, new)


def _prose(old, new, reason):
    """The words under the header. They must say that a crawl did not write this."""
    return ("This mirror is complete. `--fresh` refuses to run while this file exists;\n"
            "delete it by hand if you really mean to fetch the whole archive again.\n"
            "`--verify` compares the tree against the two figures above.\n"
            "\n"
            "%s: the two figures above were moved after the crawl that wrote this file,\n"
            "from %d files and %d bytes, by a deliberate repair:\n"
            "%s\n"
            "`completed` above is still the crawl's date, not the repair's."
            % (RESTATED, old[0], old[1], reason))


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
