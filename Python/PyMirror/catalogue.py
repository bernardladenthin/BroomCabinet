#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Generate a catalogue INSIDE the mirror tree, so the tree explains itself without this tool.

WHY THIS EXISTS. The status table and the reasoning behind every archive live in mirror.py, which
is version-controlled and small. That is right for maintenance -- a table edited in two places is
wrong in one of them, and it already was.

It is wrong for PRESERVATION. An archive that ends up on a shelf, or inside a 7z, or on someone
else's disk in ten years, does not have mirror.py beside it. It has a directory full of files and
whatever is written in that directory. If the only account of what the 2.9 TB IS lives in a git
repository somewhere else, the archive is not self-describing, and a preservation copy that cannot
explain itself has lost most of what makes it worth keeping.

So: GENERATED, not duplicated. Everything here is read out of the tree itself -- the completion
markers, the PROVENANCE files, the checksum indexes -- and written back as one readable document.
Re-run it whenever the tree changes; there is no second copy of any fact to drift.

    python catalogue.py --root Q:\\mirror

What it deliberately does NOT do: invent, summarise or judge. If an archive has no PROVENANCE.md,
the catalogue says so rather than filling the space with a guess, because the gap is the useful
information.
"""

import argparse
import csv
import io
import os
import re
import sys
import time

from common import (CATALOGUE_FILE, COMPLETE_MARKER, INDEX_FILE, PROVENANCE_FILE,
                    SUMS_FILE, human, read_marker, scan_tree)

OUT = CATALOGUE_FILE

# Files that are ours rather than content. Mirrors mirror.py's OWN_FILES, at the archive root only
# -- oss4aix.org ships 2 071 real SHA256SUMS files of its own, one per package directory.
# README.md removed 2026-09-07 -- see the note beside OWN_FILES in mirror.py. The two sets
# must agree, or the catalogue counts a file the index does not.
def first_paragraph(path):
    """-> the opening prose of a PROVENANCE.md, as one line.

    The first heading is the archive's own title and the first paragraph under it is what the
    author chose to say first, which is a better one-line summary than anything derived.
    """
    try:
        text = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    body = re.sub(r"^#[^\n]*\n", "", text.lstrip(), count=1).strip()
    para = body.split("\n\n", 1)[0]
    para = re.sub(r"\s+", " ", para).strip()
    para = re.sub(r"\*\*|`|\*", "", para)
    return para or None


def walk_counts(root):
    """-> (files, bytes, unreadable) BY THE LIBRARY'S DEFINITION, not by a second one.

    A file that cannot be stat'ed even through the extended-path prefix is NOT counted, because
    the marker this is compared against was not counted that way either -- and if this tool
    counted it the two would disagree by one file on an unchanged tree. That happened with `tuhs`,
    whose Documentation/TUHS/Old/mirroring.html is an rsync-created symlink with no resolvable
    target. Both answers were defensible, and that is precisely the danger: a catalogue that
    permanently reports a disagreement nobody can act on teaches its reader to ignore
    disagreements.  [2026-09-05]

    THIS USED TO SAY IT COUNTED "EXACTLY scan_tree's definition" AND IT DID NOT. Its own-file set
    and the library's differed by five names, and one of them -- IA-METADATA.json -- sits at the
    top of the four Internet Archive trees. Measured on 2026-09-23 against their markers:
    scan_tree agreed to the byte and this counted one file and 3 281 bytes more. The sentence was
    true of the intent and false of the code, which is the worst of the three possibilities.

    The unreadable count is still returned separately and printed on its own, so the fact is kept
    without being smuggled into a figure that means something else.
    """
    unreadable = []
    n, total = scan_tree(root, report=lambda rel, _exc: unreadable.append(rel))
    return n, total, len(unreadable)


def index_rows(path):
    try:
        with io.open(path, encoding="utf-8", errors="replace", newline="") as fh:
            return sum(1 for _ in csv.DictReader(fh))
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(
        description="Write a self-describing catalogue into the mirror tree.")
    ap.add_argument("--root", required=True, metavar="PATH",
                    help="the mirror tree. Required: this tool writes into it, and inheriting a "
                         "default would mean writing into whatever directory it happens to run in")
    ap.add_argument("--out", metavar="PATH",
                    help="where to write (default: %s in the root)" % OUT)
    ap.add_argument("--emit-held", action="store_true",
                    help="print the HELD block's NUMBERS in mirror.py's status-table format and "
                         "exit, with an empty note column. This is machine input for "
                         "refresh-table.py, which re-attaches the hand-written notes and rewrites "
                         "the block. DO NOT paste this output into mirror.py yourself -- the "
                         "notes are the half no tool can regenerate")
    ap.add_argument("--recount", action="store_true",
                    help="walk every archive to check its marker against the tree. Slow on "
                         "terabytes, and the point of it: a marker is a claim, the tree is the fact")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit("%s is not a directory" % root)
    out_path = args.out or os.path.join(root, OUT)

    names = sorted(d for d in os.listdir(root)
                   if os.path.isdir(os.path.join(root, d)) and d != "logs")

    rows = []
    for name in names:
        d = os.path.join(root, name)
        rec = read_marker(os.path.join(d, COMPLETE_MARKER))
        prov = os.path.join(d, PROVENANCE_FILE)
        rows.append({
            "name": name,
            "source": rec.get("source", ""),
            "completed": rec.get("completed", ""),
            "files": int(rec["files"]) if rec.get("files", "").isdigit() else None,
            "bytes": int(rec["bytes"]) if rec.get("bytes", "").isdigit() else None,
            "p404": rec.get("permanent-404", ""),
            "has_marker": bool(rec),
            "has_prov": os.path.exists(prov),
            "summary": first_paragraph(prov) if os.path.exists(prov) else None,
            "index": index_rows(os.path.join(d, INDEX_FILE)),
            "sums": os.path.exists(os.path.join(d, SUMS_FILE)),
            "actual": walk_counts(d) if args.recount else None,
        })

    if args.emit_held:
        # mirror.py's column layout: two leading spaces, 38-wide name, 7-wide count, 10-wide size.
        #
        # THE NOTE COLUMN IS DELIBERATELY EMPTY, and this output is NOT meant to be pasted.
        # `refresh-table.py` is the tool that rewrites the block: it reads this, re-attaches every
        # hand-written note by archive name, drops rows whose archive is gone, and names the rows
        # that still need a note.
        #
        # An earlier version of this function grew its own note-carrying. It worked, and it was
        # wrong: refresh-table.py APPENDS its notes to these lines, so two tools doing the same
        # job produced every note twice. Duplicated logic drifting apart is the exact failure this
        # collection keeps writing tools to prevent -- so the duplicate was removed rather than
        # reconciled, and the help text now points at the tool that owns the job.
        print("HELD                                    files      size   note")
        for r in sorted(rows, key=lambda x: -(x["bytes"] or 0)):
            size = r["bytes"]
            # UNKNOWN IS NOT ZERO. An archive with no marker has no recorded size, and rendering
            # that as "0.0000 GB" told the reader it was empty -- dialectronics holds 23 MB and
            # showed as zero, because it is deliberately markerless while incomplete. The file
            # count already used "-" for the same case; the size column now agrees with it.
            if size is None:
                txt = "-"
            else:
                txt = ("%.1f GB" % (size / 1e9)) if size >= 1e9 else                       ("%.3f GB" % (size / 1e9)) if size >= 1e6 else "%.4f GB" % (size / 1e9)
            print("  %-34s %8s %10s  " % (
                r["name"],
                "{:,}".format(r["files"]).replace(",", " ") if r["files"] is not None else "-",
                txt))
        sys.stderr.write("\nThis block has NO notes. Do not paste it into mirror.py by hand --\n"
                         "run refresh-table.py, which re-attaches every hand-written note.\n")
        return 0

    tf = sum(r["files"] or 0 for r in rows)
    tb = sum(r["bytes"] or 0 for r in rows)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    w = io.StringIO()
    w.write("# Mirrored archives — catalogue\n\n")
    w.write("Generated %s by `catalogue.py` from the markers, checksum indexes and PROVENANCE\n"
            "files in this tree. **Do not edit by hand** — re-run the tool instead; every fact\n"
            "here has exactly one source, which is the tree itself.\n\n" % stamp)
    w.write("**%d archives, %s files, %s.**\n\n" % (len(rows), "{:,}".format(tf).replace(",", " "),
                                                    human(tb)))
    w.write("Third-party material, copied verbatim. Nothing here was extracted, disassembled or\n"
            "derived; each archive carries whatever terms its source carries, and several are\n"
            "private preservation copies of material that may not be redistributed.\n\n")

    w.write("## What is here\n\n")
    w.write("| Archive | Files | Size | Completed | Provenance |\n")
    w.write("|---|---:|---:|---|---|\n")
    for r in sorted(rows, key=lambda x: -(x["bytes"] or 0)):
        w.write("| `%s` | %s | %s | %s | %s |\n" % (
            r["name"],
            "{:,}".format(r["files"]).replace(",", " ") if r["files"] is not None else "—",
            human(r["bytes"]) if r["bytes"] is not None else "—",
            r["completed"] or "—",
            "yes" if r["has_prov"] else "**MISSING**"))
    w.write("\n")

    w.write("## Each archive, in its own words\n\n")
    w.write("The line under each name is the opening of its `PROVENANCE.md`, which is where the\n"
            "full account lives — where it came from, why it was taken, what is deliberately\n"
            "absent, and what went wrong on the way.\n\n")
    for r in sorted(rows, key=lambda x: x["name"]):
        w.write("### `%s`\n\n" % r["name"])
        if r["source"]:
            w.write("*Source:* `%s`\n\n" % r["source"])
        if r["summary"]:
            w.write("%s\n\n" % r["summary"])
        else:
            w.write("**No `PROVENANCE.md`.** This archive predates the practice of recording one, "
                    "or was never given it. What is known about it is only what the marker and the "
                    "run log say — which is not enough for a reader who has nothing else.\n\n")

    w.write("## Verifying this tree\n\n")
    w.write("Every archive carries two checksum files, both listing every file it contains:\n\n")
    w.write("    .mirror-index.csv   path,size,mtime_ns,sha256  — the master\n")
    w.write("    .sha256sum          the same digests in the format `sha256sum -c` reads\n\n")
    w.write("To check one archive:\n\n")
    w.write("    cd <archive> && sha256sum -c .sha256sum\n\n")
    w.write("A size-and-count check against each marker is faster and much weaker — it cannot see\n"
            "a file whose content changed while its size stayed the same. For several of these\n"
            "sources this copy is now among the last in existence, so the digests are the point.\n\n")
    missing = [r["name"] for r in rows if not r["sums"]]
    if missing:
        w.write("**Without a checksum file: %s.**\n\n" % ", ".join("`%s`" % m for m in missing))

    w.write("## Reading the counts\n\n")
    w.write("A marker's `files` and `bytes` exclude four things, and each exclusion has a reason:\n\n")
    w.write("- `.mirror-complete`, `.mirror-index.csv`, `.sha256sum`, `PROVENANCE.md` at the\n"
            "  **archive root** — ours, not content. Only at the root: `oss4aix.org` ships 2 071\n"
            "  real `SHA256SUMS` files of its own, one per package directory.\n")
    w.write("- `.part` — a half-finished download.\n")
    w.write("- `.suspect` — arrived complete and failed verification: shorter than the source\n"
            "  claimed. Not a file, and counting it would put wrong bytes under a valid digest.\n")
    w.write("- `.superseded` — a `.suspect` that was later recovered whole from a better source,\n"
            "  with the short copy kept as evidence rather than deleted.\n\n")

    if args.recount:
        w.write("## Marker against tree\n\n")
        bad = [r for r in rows if r["actual"] and r["files"] is not None
               and (r["actual"][0] != r["files"] or r["actual"][1] != r["bytes"])]
        unread = [r for r in rows if r["actual"] and r["actual"][2]]
        if unread:
            w.write("**%d of these trees hold files that could not be read.** They are\n"
                    "counted by nobody -- not here and not by `mirror.py`, which skips them\n"
                    "the same way. Listed rather than folded into a figure that means\n"
                    "something else:\n\n" % len(unread))
            for r in unread:
                w.write("- `%s`: %d unreadable\n" % (r["name"], r["actual"][2]))
            w.write("\n")
        if not bad:
            w.write("Checked at generation time: every marker agrees with its tree.\n\n")
        else:
            w.write("**These markers disagree with their tree.** A disagreement is not damage by\n"
                    "itself, but it is always worth an explanation:\n\n")
            for r in bad:
                w.write("- `%s`: tree has %d files / %d bytes, marker says %d / %d\n"
                        % (r["name"], r["actual"][0], r["actual"][1], r["files"], r["bytes"]))
            w.write("\n")

    no_prov = [r["name"] for r in rows if not r["has_prov"]]
    if no_prov:
        w.write("## Undocumented\n\n")
        w.write("%d of %d archives have no `PROVENANCE.md`: %s.\n\n"
                % (len(no_prov), len(rows), ", ".join("`%s`" % n for n in no_prov)))
        w.write("Stated rather than quietly left blank, because a reader who finds an archive with\n"
                "no account of itself should know that the omission is known.\n\n")

    # newline="\n": CATALOGUE.md is written into the mirror tree and is meant to travel with it,
    # onto a shelf or someone else's disk. Windows line endings would be an accident of where the
    # tool happened to run, not a property of the document. The same omission in refresh-table.py
    # silently converted all 5 428 lines of mirror.py to CRLF on 2026-09-08.
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(w.getvalue())
    print("  wrote %s" % out_path)
    print("  %d archives, %s files, %s" % (len(rows),
                                           "{:,}".format(tf).replace(",", " "), human(tb)))
    if no_prov:
        print("  without PROVENANCE.md: %s" % ", ".join(no_prov))
    return 0


if __name__ == "__main__":
    sys.exit(main())
