# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Rebuild mirror.py's HELD block from the tree, keeping every hand-written note.

WHY. The status table drifted twice in two days: after the fsck fetches it still listed OS400_i
and the AIX media remainder under DEFERRED although both were held, and it still had an IN FLIGHT
section for runs that had finished. Numbers in a hand-maintained table are wrong the moment
anything is added, and a stale table that looks authoritative is the failure mode this collection
keeps meeting.

WHAT THIS KEEPS AND WHAT IT REPLACES. The NOTE on each row is the part only a person can write --
"SALVAGED; both hosts are gone", "3 695 permanent 404s: a deleted NCD mirror whose catalogue
survives". Those are carried across verbatim, matched by archive name. The file count and the size
are read from the markers. A row whose archive no longer exists is dropped and reported; a new
archive gets an empty note, which is a visible gap rather than a silent one.

DO NOT RUN THIS WHILE A FETCH IS IN FLIGHT. It reads the tree and writes the result into the
master record, so a run started mid-fetch freezes a half-finished state as the authoritative
table. That is why writing now needs --apply: the default reports what would change and touches
nothing.

NOTHING RUNS ON IMPORT, and the paths are arguments. This file used to hold an absolute path into
the author's own source tree twice and `Q:\mirror` twice more, at module level with no main(), so
`python refresh-table.py --help` did not print help -- on this machine it REWROTE mirror.py, and
on the CI runner it died on the first path.

    python refresh-table.py                     # what would change
    python refresh-table.py --apply             # write it
"""
import argparse
import io
import os
import re
import subprocess
import sys

from common import MIRROR_ROOT, COMPLETE_MARKER, iter_archives

HERE = os.path.dirname(os.path.abspath(__file__))
HELD_HEADER = "HELD                                    files      size   note"

# Spelled-out counts for the headline. Never a wrong word: an unknown count prints as digits.
WORDS = {30: "Thirty", 37: "Thirty-seven", 40: "Forty", 50: "Fifty", 60: "Sixty",
         70: "Seventy", 71: "Seventy-one", 80: "Eighty", 90: "Ninety", 100: "One hundred"}


def spell(n):
    """-> the count in words if we have one, else the digits."""
    return WORDS.get(n, str(n))


def read_notes(block):
    """Existing notes, including their continuation lines, keyed by archive name."""
    notes, current = {}, None
    for line in block.splitlines()[1:]:
        # The size is TWO tokens ("1241.5 GB"). A first attempt matched only one and carried
        # the unit into the note, giving every row "GB  GB  ...". Anchor on the unit explicitly.
        #
        # It can also be a bare "-". Added 2026-09-08, when catalogue.py stopped printing an
        # unknown size as "0.0000 GB" -- which had told the reader that dialectronics, holding
        # 23 MB with no marker, was empty. Four rows print "-" today: the two archives still
        # fetching, funet-unix, and dialectronics. WITHOUT THIS BRANCH their notes fail to match
        # and are silently dropped on the next rebuild, which is the precise damage this tool
        # exists to prevent.
        m = re.match(r"^  (\S+?)\s{2,}[\d ,-]+\s+(?:[\d.]+\s+GB|-)\s*(.*)$", line)
        if m:
            current = m.group(1)
            notes[current] = [m.group(2).rstrip()]
        elif current and line.startswith(" " * 50):
            notes[current].append(line.strip())
        elif not line.strip():
            current = None
    return notes


def unmarked_archives(root):
    """Archives on disk with files but no completion marker.

    THE HEADLINE IS A SUM OF MARKERS, AND AN ARCHIVE WITHOUT ONE CONTRIBUTES ZERO. That part is
    correct -- an interrupted fetch has no figure to contribute -- and until 2026-09-13 it was
    also SILENT, which is not. The headline read 1 537 271 files while the tree held 1 537 976,
    and the 705 were crashing-org-kernel (a run cut off on 2026-09-08 at 304 of 441+ files) and
    dialectronics (199 of 372+). Both carry a PROVENANCE.md and a .sha256sum and no
    .mirror-complete: visible to anyone reading the directory, invisible to every number this
    tool writes.

    A count that is short for a reason is fine. A count that is short WITHOUT SAYING SO is the
    exact failure this collection spends all its effort on.
    """
    out = []
    # WHICH DIRECTORIES ARE ARCHIVES is common.iter_archives()'s answer, not this tool's.
    # It also long_path()s the root, which this loop did not -- and a walk of a path
    # Windows will not open returns nothing rather than failing, so an archive could have
    # counted as empty here and nobody would have seen why.
    for name, path in iter_archives(root):
        if os.path.isfile(os.path.join(path, COMPLETE_MARKER)):
            continue
        n = sum(len(files) for _dp, _dn, files in os.walk(path))
        if n:
            out.append((name, n))
    return out


def build(text, fresh, notes):
    """-> (new HELD block, archive names seen, dropped names)."""
    out, seen = [fresh[0]], set()
    for line in fresh[1:]:
        m = re.match(r"^  (\S[^\s]*)\s", line)
        if not m:
            continue
        name = m.group(1)
        seen.add(name)
        parts = notes.get(name) or [""]
        out.append(line.rstrip() + ("  " + parts[0] if parts[0] else ""))
        for cont in parts[1:]:
            out.append(" " * 58 + cont)
    return out, seen, sorted(set(notes) - seen)


def headline(text, rows):
    """-> (text with the headline resummed, the new headline) or (text, None).

    THE HEADLINE, TOO -- because it says of itself that it is generated. mirror.py's third line
    carried "Thirty-seven archives, 826 162 files, 3 506 GB" followed by "THESE THREE NUMBERS ARE
    GENERATED, NOT TYPED". They were not: this tool anchored on the HELD header and rewrote only
    the block beneath it, so the headline was hand-maintained by a sentence insisting it was not.
    By 2026-09-10 the truth was 71 archives and 1 394 095 files, and the paragraph's own
    cautionary example described the state it was in while describing it as past.

    Rather than delete the numbers, make the claim true. They are summed from the same rows the
    block above is built from, so the headline and the table cannot drift again.
    """
    files = size = 0
    for line in rows[1:]:
        mm = re.match(r"^  \S+\s+([\d ]+|-)\s+([\d.]+)\s+GB", line)
        if mm:
            f = mm.group(1).replace(" ", "")
            if f.isdigit():
                files += int(f)
            size += float(mm.group(2))
    count = sum(1 for line in rows[1:] if re.match(r"^  \S", line))

    m_head = re.compile(r"^\S[^\n]*?, [\d ]+ files, [\d ]+ GB: ", re.M).search(text)
    if not (m_head and files):
        return text, None
    new = "%s archives, %s files, %s GB: " % (
        spell(count), "{:,}".format(files).replace(",", " "),
        "{:,}".format(int(round(size))).replace(",", " "))
    return text[:m_head.start()] + new + text[m_head.end():], new


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mirror", default=os.path.join(HERE, "mirror.py"), metavar="FILE",
                        help="the master record to rewrite (default: beside this file)")
    parser.add_argument("--catalogue", default=os.path.join(HERE, "catalogue.py"), metavar="FILE",
                        help="the tool that emits the fresh rows (default: beside this file)")
    parser.add_argument("--root", default=MIRROR_ROOT,
                        metavar="PATH", help="the mirror tree to read")
    parser.add_argument("--apply", action="store_true",
                        help="write mirror.py. Without it nothing is changed. DO NOT USE WHILE A "
                             "FETCH IS RUNNING -- see the module docstring")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    for label, path in (("--mirror", args.mirror), ("--catalogue", args.catalogue)):
        if not os.path.isfile(path):
            print("REFUSED: %s is not a file: %s" % (label, path))
            return 2
    if not os.path.isdir(args.root):
        print("REFUSED: --root is not a directory: %s" % args.root)
        return 2

    with io.open(args.mirror, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index(HELD_HEADER)
    end = text.index("\nDEFERRED", start)
    notes = read_notes(text[start:end])

    fresh = subprocess.run([sys.executable, args.catalogue, "--root", args.root, "--emit-held"],
                           capture_output=True, text=True, check=True).stdout.splitlines()
    rows, seen, gone = build(text, fresh, notes)

    text, new_head = headline(text, rows)
    if new_head:
        print("  headline: %s" % new_head.rstrip(": "))
        # start/end were computed against the ORIGINAL string; re-find the block after editing
        # above it, or the splice below lands at the wrong offset.
        start = text.index(HELD_HEADER)
        end = text.index("\nDEFERRED", start)
        unmarked = unmarked_archives(args.root)
        if unmarked:
            print("  NOT IN THAT HEADLINE -- %d archive(s) on disk with no completion marker, "
                  "%d files:" % (len(unmarked), sum(n for _d, n in unmarked)))
            for name, n in unmarked:
                print("     %-26s %7d files" % (name, n))
    else:
        print("  headline NOT updated (pattern not found) -- check mirror.py's third line by hand")

    print("  HELD rebuilt: %d rows" % (len(rows) - 1))
    print("  notes carried across: %d" % sum(1 for n in seen if notes.get(n) and notes[n][0]))
    if gone:
        print("  rows dropped (archive no longer present): %s" % ", ".join(gone))
    missing = [n for n in seen if not (notes.get(n) and notes[n][0])]
    if missing:
        print("  rows with NO note -- write one: %s" % ", ".join(sorted(missing)))

    if not args.apply:
        print("\n  %s was NOT written. --apply does it." % args.mirror)
        return 0

    # newline="\n" IS NOT OPTIONAL. Without it, Python's text mode translates every "\n" on
    # Windows, and this tool -- which rewrites ~150 lines of a 7 000-line file -- converted ALL OF
    # mirror.py from LF to CRLF. Caught 2026-09-08 by diffing against a backup: 10 856 changed
    # lines for a 70-row table refresh. The damage is invisible in an editor and total in a git
    # diff, which is the worst combination: every later change to this file would have been
    # unreviewable.
    with io.open(args.mirror, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text[:start] + "\n".join(rows) + "\n" + text[end:])
    print("\n  written to %s" % args.mirror)
    return 0


if __name__ == "__main__":
    sys.exit(main())
