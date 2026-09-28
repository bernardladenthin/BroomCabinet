#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""PDF: getting a title, an outline and a page count out of a file, without a PDF library.

SPLIT OUT OF common.py ON 2026-09-23, unchanged. The largest of the sections that moved --
21 definitions, 19 of them exported -- and one tool uses it, pdf-identify.py.

IT DEPENDS ON NOTHING BUT re AND zlib. No part of common, no other module; the whole section is
byte-level reading of one file format. That is worth stating, because it is also the reason the
section could grow as large as it did without anybody noticing: nothing outside it ever had to
change when it did.

WHAT IT IS AND IS NOT. This does not render, lay out or fully parse a PDF. It reads the few
structures that answer "what document is this" -- the trailer's /Info, the XMP packet, the
outline, the page tree -- and it is deliberately tolerant: a file that answers none of them is
a file with no title, not an error. Every rule in here was learned from a document that broke
the previous one, and the docstrings name them.

THE SIGNATURE IS SPELLED TWICE, once here as PDF_MAGIC and once in common.MAGIC[".pdf"], and
that is on purpose: common's table is what magic_mismatch() consults and it must not depend on
this module. Four bytes duplicated in two places, each with its own reason to exist, is cheaper
than a library that imports a file-format reader to answer a question about extensions.
"""

import re
import zlib

__all__ = [
    "PDF_MAGIC", "PDF_STREAM", "PDF_SHOW", "PDF_UNESCAPE", "PDF_OCTAL",
    "PDF_TRAILER_INFO", "PDF_INFO_KEYS", "PDF_XMP_TITLE", "PDF_XML_TAGS",
    "PDF_OUTLINE_TITLE", "PDF_PAGE_TYPE",
    "is_pdf", "pdf_string", "pdf_drawn_text", "pdf_info", "pdf_xmp_title",
    "pdf_page_count", "pdf_outline", "pdf_object",
]

# ------------------------------------------------------------------------------------ pdf
#
# NO PDF LIBRARY, DELIBERATELY. These run from a standard library and answer a question -- what
# is this document -- rather than render a page. Crude, and enough to read a title page when the
# fonts are ordinary.
#
# What is NOT here: order numbers, edition notices, spine copy. Those are IBM's publishing
# conventions, not PDF's, and they apply to text however it was obtained. They stay with the tool
# whose subject they are.


PDF_MAGIC = b"%PDF"

# A content stream. Non-greedy, because a PDF holds many and the last `endstream` is far away.
PDF_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.S)

# A literal string, i.e. an operand of a text-showing operator.
#
# THE ESCAPE ALTERNATIVE COMES FIRST, AND THAT IS THE WHOLE CORRECTNESS OF IT. Written the
# other way round the character class matches a LONE BACKSLASH, because a backslash is not a
# parenthesis. In the middle of a string the engine backtracks and recovers; at the END it
# does not, because the shorter match SUCCEEDS -- the parenthesis it failed to consume then
# serves as the closing one. So an edition notice came back one character short with a stray
# backslash, and every edition notice in this collection ends `(Month Year)`.  [2026-09-22]
PDF_SHOW = re.compile(rb"\(((?:\\.|[^()])*)\)")

PDF_UNESCAPE = re.compile(rb"\\([()\\])")
PDF_OCTAL = re.compile(rb"\\[0-7]{1,3}")

# The same alternation order as PDF_SHOW, for the same reason: a title ending in an escaped
# parenthesis would otherwise lose its last character.
PDF_OUTLINE_TITLE = re.compile(rb"/Title\s*\(((?:\\.|[^()]){2,120})\)")

# `/Type /Page` but not `/Type /Pages`, which is the tree node rather than a leaf.
PDF_PAGE_TYPE = re.compile(rb"/Type\s*/Page[^s]")

PDF_XMP_TITLE = re.compile(rb"<dc:title>.{0,400}?</dc:title>", re.S)
PDF_XML_TAGS = re.compile(rb"<[^>]+>")

PDF_INFO_KEYS = ("Title", "Subject", "Author", "Creator", "Producer")

# `/Info 8 0 R` in the trailer. A file revised in place has several trailers, and the LAST
# one is the current document -- an earlier one names the metadata as it was before the
# revision, which is a true fact about a file nobody has.
PDF_TRAILER_INFO = re.compile(rb"/Info\s+(\d+)\s+(\d+)\s+R")

_PDF_OCTAL_DIGITS = b"01234567"
_PDF_SIMPLE_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}


def pdf_string(raw):
    r"""-> a readable string from a PDF literal string, escapes resolved.

    THE OCTAL ESCAPES ARE NOT DECORATION. An /Info value written by Distiller is often UTF-16BE
    with a byte-order mark, which arrives as `\376\377\000A\000c\000r...` and reads as line noise
    unless the octals are resolved first and the mark is honoured afterwards.

    OCTAL HAS NO 8 AND NO 9. A test for "is this a digit" accepts both, and `int("8", 8)` raises
    -- so one `\8` anywhere in a document's metadata killed the whole identification run with a
    ValueError three frames away from anything that named a file. The PDF specification says a
    backslash before an unrecognised character is dropped and the character kept, so `\8` is the
    digit 8, and that is what happens here.

    ONE PASS, NOT TWO. Resolving `\\` first and octals second decodes `\\101` -- an escaped
    backslash followed by three ordinary digits -- as the letter A. A single pass cannot make
    that mistake, because it has already consumed the backslash it escaped.
    """
    out = bytearray()
    i, n = 0, len(raw)
    while i < n:
        char = raw[i:i + 1]
        if char != b"\\":
            out += char
            i += 1
            continue
        i += 1
        if i >= n:
            break                                   # a trailing backslash escapes nothing
        nxt = raw[i:i + 1]
        if nxt in _PDF_OCTAL_DIGITS:
            digits = b""
            while i < n and len(digits) < 3 and raw[i:i + 1] in _PDF_OCTAL_DIGITS:
                digits += raw[i:i + 1]
                i += 1
            out.append(int(digits, 8) & 0xFF)
            continue
        if nxt in _PDF_SIMPLE_ESCAPES:
            out += _PDF_SIMPLE_ESCAPES[nxt]
        elif nxt == b"\n":
            pass                                    # a line continuation inside a long string
        elif nxt == b"\r":
            if raw[i + 1:i + 2] == b"\n":
                i += 1
        else:
            out += nxt                              # \( \) \\ and anything else: the character
        i += 1

    if out[:2] == b"\xfe\xff":
        return bytes(out[2:]).decode("utf-16-be", "replace")
    if out[:2] == b"\xff\xfe":
        return bytes(out[2:]).decode("utf-16-le", "replace")
    return bytes(out).decode("latin-1")


def pdf_drawn_text(data, limit=6000):
    """-> the strings the text operators draw, in stream order, up to `limit` characters.

    THE OCTALS BECOME SPACES HERE, and are decoded in pdf_string(). That is not an inconsistency:
    in a content stream drawn with a subset font in a custom encoding, the byte between the
    parentheses is a GLYPH INDEX and not a character, so decoding it produces confident nonsense.
    A space says "something was drawn here that this cannot read", which is the truth.

    The result is whitespace-collapsed and trimmed, because it is read by a person deciding
    what to call a file.

    Nothing extractable is a real answer, not a failure: it means a scan, or subset fonts. Four
    AIX manuals in this collection are exactly that, and were identified from their XMP packet.
    """
    out, total = [], 0
    for match in PDF_STREAM.finditer(data):
        try:
            body = zlib.decompress(match.group(1))
        except zlib.error:
            continue                                # not FlateDecode, or damaged: skip, not fail
        for raw in PDF_SHOW.findall(body):
            if not raw.strip():
                continue
            text = PDF_UNESCAPE.sub(rb"\1", raw)
            text = PDF_OCTAL.sub(b" ", text)
            out.append(text.decode("latin-1"))
            total += len(text)
        if total > limit:
            break
    # Trimmed BEFORE the limit is applied, not after: cutting first can leave a trailing
    # space that the caller then prints at the end of a line.
    return re.sub(r"\s+", " ", " ".join(out)).strip()[:limit]


def pdf_object(data, number, generation=0):
    """-> the body of `<number> <generation> obj ... endobj`, or None.

    The leading boundary is explicit because object 8 and object 18 end in the same digits, and a
    naive search for `8 0 obj` finds the wrong one -- silently, and with a perfectly plausible
    dictionary inside it.
    """
    pattern = (rb"(?:^|[^0-9])" + str(number).encode() + rb"\s+" + str(generation).encode()
               + rb"\s+obj\b(.*?)endobj")
    match = re.search(pattern, data, re.S)
    return match.group(1) if match else None


def pdf_info(data):
    """-> {key: value} from the /Info dictionary, empty values dropped.

    FROM THE /Info DICTIONARY, WHICH IS WHAT THIS ALWAYS CLAIMED. It used to search the whole
    file for `/Title (...)` and take the first hit -- which in a document with bookmarks is a
    BOOKMARK, because the outline objects come first. A sample built for this reported
    `1.1 PowerPC 601 Microprocessor Overview` as the document title while /Info said `Contents`.
    Both are facts about the file; only one of them answers the question, and reporting the wrong
    one confidently is the exact failure this whole tool exists to avoid.

    IF THE TRAILER CANNOT BE FOLLOWED, the old file-wide search is used and the keys are marked
    with a trailing `?`. A damaged or unusual file should still give up what it has -- but the
    reader has to be able to tell which kind of answer they are looking at.

    IBM's SCRIPT/VS writes the publication identifier into /Title rather than a title: three
    documents here say `Contents` and a fourth says `A`. So this reports what is there and judges
    nothing; the caller weighs it against the other answers.
    """
    refs = PDF_TRAILER_INFO.findall(data)
    region, suffix = None, ""
    if refs:
        number, generation = refs[-1]
        region = pdf_object(data, int(number), int(generation))
    if region is None:
        region, suffix = data, "?"

    out = {}
    for key in PDF_INFO_KEYS:
        match = re.search(rb"/" + key.encode() + rb"\s*\(((?:\\.|[^\\()])*)\)", region)
        if match:
            value = pdf_string(match.group(1))
            if value.strip():
                out[key + suffix] = value
    return out


def pdf_xmp_title(data):
    """-> the <dc:title> from the XMP packet, tags stripped, or None.

    Often the only usable title. Four AIX manuals here extract no text at all and carry a /Title
    of `Contents`, and their XMP says `AIX Version 7.1: Assembler Language Reference`.
    """
    match = PDF_XMP_TITLE.search(data)
    if not match:
        return None
    joined = b" ".join(PDF_XML_TAGS.sub(b" ", match.group(0)).split())
    return joined.decode("latin-1") if joined.strip() else None


def pdf_page_count(data):
    """-> the number of pages, or None when that cannot be counted from the raw bytes.

    NONE IS NOT ZERO, AND THE DIFFERENCE IS THE POINT. In a linearised or object-stream PDF the
    page objects live inside a compressed object stream where this cannot see them, and a zero
    printed as a page count reads as a fact rather than as a failure to look.
    """
    count = len(PDF_PAGE_TYPE.findall(data))
    return count or None


def pdf_outline(data, limit=12):
    """-> the first bookmark titles, in order, duplicates dropped.

    OFTEN PLAIN TEXT WHERE THE PAGE CONTENT IS NOT. The 601 User's Manual has no readable text
    and no usable title, and its bookmark tree opens `1.1 PowerPC 601 Microprocessor Overview`,
    which settles what it is.
    """
    seen = []
    for raw in PDF_OUTLINE_TITLE.findall(data):
        # THROUGH pdf_string, NOT A HALF-DECODE. A bookmark is an ordinary PDF literal string and
        # may be UTF-16 with a byte-order mark like any other; resolving only the parenthesis
        # escapes printed one as `\376\377\000\103\000\157...` -- line noise, in a report whose
        # entire purpose is to be readable by a person deciding what to call a file.
        title = pdf_string(raw).strip()
        if title and title not in seen:
            seen.append(title)
        if len(seen) >= limit:
            break
    return seen


def is_pdf(data):
    """-> True if these bytes open a PDF. The header, not the extension."""
    return data[:len(PDF_MAGIC)] == PDF_MAGIC
