#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Microsoft To Do as folders of Markdown, with every attachment beside it.

    1. dump      paste export-indexeddb.js into the browser console on to-do.live.com;
                 it saves MicrosoftTODO-export-<date>.json
    2. links     python pymstodoexport.py links  D:\data\todo\export.json D:\data\todo
    3. download  open each link in a browser signed in to the same account (outlook.live.com)
                 and run download-attachment.js there, or press the download button by hand
    4. collect   python pymstodoexport.py collect D:\data\todo\export.json D:\data\todo
    5. markdown  python pymstodoexport.py markdown D:\data\todo\export.json D:\data\todo

COMMANDS
    links EXPORT OUT        the Outlook deep link of every attachment not yet in OUT, one JSON
                            object per line: index, url, display_name, target
        --all               every attachment, also those already collected
    collect EXPORT OUT      move downloaded attachments from the download folder into OUT and
                            check each one: complete file of the recorded type, plausible size
        --downloads DIR     where the browser saves files (default: ~/Downloads)
        INDEX[=NAME] ...    only these attachments (indexes from `links`); NAME is the file in
                            the download folder when the browser renamed it, e.g. "a (1).png"
    markdown EXPORT OUT     write <list>/<list>.md for every list and README.md, then check them
                            against the export: titles, note texts, links, attachments
        --check             write nothing, only report what the Markdown would be missing

A file that fails its check stays where it is. Nothing is ever overwritten by `collect`.

EXIT STATUS: 0 all good, 1 something was refused or is missing (listed on stdout), 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import mstodo


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    def paths(p):
        p.add_argument("export", help="the JSON written by export-indexeddb.js")
        p.add_argument("out", help="the output directory")

    p = sub.add_parser("links", help="list the attachments still to download")
    paths(p)
    p.add_argument("--all", action="store_true", help="also those already collected")
    p = sub.add_parser("collect", help="move downloaded attachments into place, checked")
    paths(p)
    p.add_argument("--downloads", default=os.path.join(os.path.expanduser("~"), "Downloads"))
    p.add_argument("only", nargs="*", metavar="INDEX[=NAME]")
    p = sub.add_parser("markdown", help="write and check the Markdown")
    paths(p)
    p.add_argument("--check", action="store_true", help="write nothing")
    return ap


def cmd_links(d: dict, out: str, every: bool) -> int:
    for i, a in enumerate(mstodo.attachments(d)):
        if a["type"] != "file" or (not every and mstodo.present(out, a) is not None):
            continue
        print(json.dumps({"index": i, "url": a["url"], "display_name": a["display_name"],
                          "target": a["rel_path"]}, ensure_ascii=False))
    return 0


def cmd_collect(d: dict, out: str, downloads: str, only: list[str]) -> int:
    att = mstodo.attachments(d)
    if only:
        todo = []
        for arg in only:
            idx, _, name = arg.partition("=")
            if not idx.isdigit() or not 0 <= int(idx) < len(att):
                print("no attachment with index %r" % idx)
                return 2
            todo.append((int(idx), name))
    else:
        todo = [(i, "") for i, a in enumerate(att) if a["type"] == "file" and mstodo.present(out, a) is None]
    failed = moved = 0
    for i, name in todo:
        a = att[i]
        src = os.path.join(downloads, name or a["display_name"])
        dst = mstodo.native(out, a["rel_path"])
        if a["type"] != "file":
            print("[%d] not an Exchange file, nothing to download: %s" % (i, a["display_name"]))
            failed += 1
        elif os.path.exists(dst):
            print("[%d] already in place: %s" % (i, a["rel_path"]))
        elif not os.path.isfile(src):
            print("[%d] not in the download folder: %s" % (i, name or a["display_name"]))
            failed += 1
        else:
            ok, why = mstodo.check_file(src, a)
            if not ok:
                print("[%d] REFUSED (%s): %s" % (i, why, src))
                failed += 1
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            moved += 1
            print("[%d] %s, %d of %s bytes recorded -> %s" % (i, why, os.path.getsize(dst), a["size"], a["rel_path"]))
    missing = sum(1 for a in att if a["type"] == "file" and mstodo.present(out, a) is None)
    print("moved %d, refused or not found %d, still missing %d" % (moved, failed, missing))
    return 1 if failed else 0


def cmd_markdown(d: dict, export: str, out: str, check: bool) -> int:
    files, problems = mstodo.render(d, out, os.path.basename(export))
    if not check:
        mstodo.write(out, files)
    print("%s %d files for %d lists and %d tasks" % (
        "checked" if check else "wrote", len(files), len(d["lists"]), len(d["tasks"])))
    print("problems: %d" % len(problems))
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    d = mstodo.load(args.export)
    if args.command == "links":
        return cmd_links(d, args.out, args.all)
    if args.command == "collect":
        return cmd_collect(d, args.out, args.downloads, args.only)
    return cmd_markdown(d, args.export, args.out, args.check)


if __name__ == "__main__":
    sys.exit(main())
