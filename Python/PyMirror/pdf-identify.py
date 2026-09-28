#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Say what a PDF actually is, when its filename does not.

WHY THIS EXISTS. Documents arrive as `601UM.pdf`, `p2715.pdf`, `a4a72.pdf` -- names that were
never meant to be read by anyone but the person who downloaded them. Filing such a file into a
curated directory means naming it, and naming it means identifying it. On 2026-09-20 this tool
identified seven documents that were then filed into an IBM documentation collection, and the
interesting part is that **no single field was enough for any of them**:

  * `/Title` said `Contents` for three of them and `A` for a fourth. IBM's SCRIPT/VS writes the
    publication identifier there, not a title.
  * The page text would not extract from the four AIX manuals at all: they are drawn with
    subset fonts in a custom encoding, so the bytes between the parentheses are glyph indices,
    not characters.
  * The XMP packet carried `<dc:title>AIX Version 7.1: Assembler Language Reference</dc:title>`
    for exactly those four.
  * The 601 User's Manual has no readable text and no usable title -- but its BOOKMARK TREE
    opens `1.1 PowerPC 601 Microprocessor Overview`, which settles it.
  * Two IBM operator guides gave up their machine, kind and order number only through the
    SPINE COPY: a note to the printer that the typesetter left in the file, reading "Anything
    over 220 pages will have spine copy 7015 Models R30, R40, and R50 CPU Enclosure SA23-2742-02
    Operator Guide".

So this prints all of them at once and lets the reader decide which one answered the question.

A KNOWN LIMIT, worth stating because it has bitten before. SCRIPT/VS lays some pages out in
EBCDIC; the text then decodes as mojibake in Latin-1 and as plain text in cp500. That is how a
Spanish AS/400 manual was identified. This tool does not try cp500 -- if the text looks like
noise and the creator is SCRIPT/VS, decode a stream by hand before concluding the file is a scan.

    python pdf-identify.py FILE [FILE ...]
    python pdf-identify.py --meta FILE          only /Info, XMP, page count, order numbers
    python pdf-identify.py --outline FILE       only the bookmark titles
    python pdf-identify.py --edition FILE       only the edition notice and its date
    python pdf-identify.py --text --chars 800 FILE
"""

import argparse
import hashlib
import re
import sys

from pdf import (is_pdf, pdf_drawn_text, pdf_info, pdf_outline, pdf_page_count,
                 pdf_xmp_title)

ORDER = re.compile(rb"\b(?:SC|SA|GC|GA|LCD|LK4T|REDP|SG24)[0-9]{0,2}-?\d{3,4}(?:-\d{2})?\b")
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December")
EDITION = re.compile(r"((?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|"
                     r"Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth)?\s*Edition[^.]{0,70})",
                     re.I)
EDITION_DATE = re.compile(r"\b(?:" + MONTHS + r")\s+(?:19|20)\d{2}\b")
# The phrase occurs twice: once as the section heading "Spine Copy", and once in the sentence
# that actually carries the title -- "Anything over 220 pages will have spine copy 7015 Models
# R30, R40, and R50 CPU Enclosure SA23-2742-02 Operator Guide". Prefer the second.
SPINE = re.compile(r"will have spine copy\s+(.{0,140})", re.I)
SPINE_ANY = re.compile(r"spine copy\s+(.{0,140})", re.I)


def document_fields(data):
    """Everything worth printing about one file: the PDF's own answers, plus IBM's.

    THE ORDER NUMBERS ARE NOT A PDF FIELD. They are matched over the raw bytes because they occur
    wherever the typesetter put them -- a cover, a footer, an XMP packet, a bookmark -- and a
    search restricted to the metadata dictionary finds none of them.
    """
    out = dict(pdf_info(data))
    title = pdf_xmp_title(data)
    if title:
        out["xmp:title"] = title
    numbers = sorted({n.decode() for n in ORDER.findall(data)})
    if numbers:
        out["order numbers"] = ", ".join(numbers[:8])
    pages = pdf_page_count(data)
    # None is not zero: in an object-stream PDF the page objects cannot be counted from the raw
    # bytes at all, and a printed 0 would read as a fact rather than as a failure to look.
    out["pages"] = str(pages) if pages is not None else "unknown (object streams)"
    return out


def edition(text):
    """-> (notices, dates, spine copy) out of already-extracted text."""
    notices = []
    for match in EDITION.finditer(text):
        notice = " ".join(match.group(1).split())
        if notice and notice not in notices:
            notices.append(notice)
    dates = []
    for match in EDITION_DATE.finditer(text):
        if match.group(0) not in dates:
            dates.append(match.group(0))
    spine = SPINE.search(text) or SPINE_ANY.search(text)
    return notices[:4], dates[:6], (" ".join(spine.group(1).split()) if spine else None)


def report(path, args):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        print("=== %s\n    UNREADABLE: %s" % (path, exc.__class__.__name__))
        return 1

    print("=== %s   [%s, %.1f MB]"
          % (path, hashlib.sha256(data).hexdigest()[:12], len(data) / 1e6))
    if not is_pdf(data):
        print("    NOT A PDF -- starts %r" % data[:16])
        return 1

    want_all = not (args.meta or args.outline or args.edition or args.text)

    if want_all or args.meta:
        info = document_fields(data)
        for key, value in info.items():
            print("    %-14s %s" % (key, " ".join(str(value).split())[:100]))
        if len(info) <= 1:
            print("    (no usable metadata)")

    text = ""
    if want_all or args.outline or args.edition or args.text:
        text = pdf_drawn_text(data, max(args.chars, 6000)
                              if (want_all or args.edition) else args.chars)

    if want_all or args.outline:
        titles = pdf_outline(data, args.outline_count)
        if titles:
            print("    bookmarks:")
            for title in titles:
                print("        %s" % title[:100])

    if want_all or args.edition:
        notices, dates, spine = edition(text)
        if spine:
            print("    spine copy:    %s" % spine)
        for notice in notices:
            print("    edition:       %s" % notice[:100])
        if dates:
            print("    dates in text: %s" % ", ".join(dates))

    if want_all or args.text:
        if text.strip():
            print("    text:          %s" % text[:args.chars])
        else:
            print("    text:          (nothing extractable -- a scan, or subset fonts with a"
                  " custom encoding)")
    print()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Identify a PDF from its metadata, bookmarks, edition notice and text.")
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="PDF files to identify")
    parser.add_argument("--meta", action="store_true",
                        help="only /Info, XMP title, page count and IBM order numbers")
    parser.add_argument("--outline", action="store_true",
                        help="only the bookmark titles")
    parser.add_argument("--edition", action="store_true",
                        help="only the edition notice, its date, and the printer's spine copy")
    parser.add_argument("--text", action="store_true",
                        help="only the drawn text")
    parser.add_argument("--chars", type=int, default=340, metavar="N",
                        help="how many characters of text to print (default 340)")
    parser.add_argument("--outline-count", type=int, default=14, metavar="N",
                        help="how many bookmark titles to print (default 14)")
    args = parser.parse_args()

    # A title page full of typographic quotes must not kill the tool on a cp1252 console.
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    if not args.files:
        parser.print_help()
        return 0
    return max(report(path, args) for path in args.files)


if __name__ == "__main__":
    sys.exit(main())
