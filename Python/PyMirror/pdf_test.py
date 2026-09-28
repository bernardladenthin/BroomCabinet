#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""pdf.py: reading a document's title out of bytes, on PDFs built for the purpose.

MOVED OUT OF common_test.py ON 2026-09-23 with the module it tests, unchanged -- the largest of
the six, 52 tests. The three module-level helpers came with it: `BS`, `pdf_octal` and
`build_pdf` had no other caller, and a helper that stays behind is a helper the next reader
cannot find.

THE PDFs HERE ARE BUILT BYTE BY BYTE, not read from disk. Every rule in pdf.py was learned from
a real document that broke the previous one, and each of those is reproduced here as the
smallest file that still shows the problem: an octal escape Distiller writes as UTF-16, a
trailer that names /Info twice, an outline title where the document title should be. A fixture
of a whole real PDF would test the same rule while making it impossible to see which byte
mattered.
"""

import os
import sys
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402   # one test checks pdf bytes against common's magic table
import pdf  # noqa: E402

BS = chr(92).encode()      # one backslash, spelled so no quoting layer can eat it


def pdf_octal(raw):
    """`raw` bytes as a run of PDF octal escapes, the way Distiller writes UTF-16."""
    return b"".join(BS + ("%03o" % b).encode() for b in raw)


def build_pdf(title=None, extra_objects=b"", content=b"", with_trailer=True, xmp=None):
    """A small but genuine PDF. Built here rather than copied from the collection.

    A fixture taken from the mirror would make these tests depend on a file nobody may modify and
    on bytes nobody chose; this one says exactly what it contains.
    """
    parts = [b"%PDF-1.4\n",
             b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
             b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
             b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"]
    if content:
        stream = zlib.compress(content)
        parts.append(b"4 0 obj << /Length " + str(len(stream)).encode()
                     + b" /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream endobj\n")
    parts.append(extra_objects)
    if title is not None:
        parts.append(b"8 0 obj << /Title (" + title + b") /Author (IBM Corporation) >> endobj\n")
    if xmp:
        parts.append(b"<x:xmpmeta><dc:title>" + xmp + b"</dc:title></x:xmpmeta>\n")
    parts.append(b"trailer << /Root 1 0 R" + (b" /Info 8 0 R" if with_trailer else b"") + b" >>\n")
    parts.append(b"%%EOF\n")
    return b"".join(parts)


class TestPdfString(unittest.TestCase):
    """A PDF literal string, escapes resolved. This runs over every document that is filed."""

    def test_plain(self):
        self.assertEqual(pdf.pdf_string(b"Hello"), "Hello")

    def test_escaped_parentheses_and_backslash(self):
        self.assertEqual(pdf.pdf_string(b"a " + BS + b"( b " + BS + b") c"), "a ( b ) c")
        self.assertEqual(pdf.pdf_string(b"C:" + BS + BS + b"tmp"), "C:" + chr(92) + "tmp")

    def test_octal(self):
        self.assertEqual(pdf.pdf_string(BS + b"101" + BS + b"102"), "AB")

    def test_a_short_octal_escape(self):
        self.assertEqual(pdf.pdf_string(BS + b"7" + b"x"), "\x07x")

    def test_UTF16_BE_WITH_A_BYTE_ORDER_MARK(self):
        # How Distiller writes a title. Without resolving the octals first and honouring the mark
        # afterwards it reads as line noise.
        self.assertEqual(pdf.pdf_string(pdf_octal(b"\xfe\xff" + "Contents".encode("utf-16-be"))),
                         "Contents")

    def test_UTF16_LE_too(self):
        self.assertEqual(pdf.pdf_string(pdf_octal(b"\xff\xfe" + "Ok".encode("utf-16-le"))), "Ok")

    def test_OCTAL_HAS_NO_8_AND_NO_9(self):
        # A test for "is this a digit" accepts both, and int("8", 8) raises -- so one such escape
        # anywhere in a document's metadata killed the whole identification run. The specification
        # says a backslash before an unrecognised character is dropped and the character kept.
        self.assertEqual(pdf.pdf_string(BS + b"8x"), "8x")
        self.assertEqual(pdf.pdf_string(BS + b"9y"), "9y")

    def test_ONE_PASS_NOT_TWO(self):
        # Resolving `\\` first and octals second decodes an escaped backslash followed by three
        # ordinary digits as a single character. A single pass has already consumed the backslash.
        self.assertEqual(pdf.pdf_string(BS + BS + b"101"), chr(92) + "101")

    def test_the_simple_escapes(self):
        self.assertEqual(pdf.pdf_string(BS + b"n" + BS + b"t"), "\n\t")

    def test_a_line_continuation_disappears(self):
        self.assertEqual(pdf.pdf_string(b"one" + BS + b"\ntwo"), "onetwo")

    def test_a_trailing_backslash_escapes_nothing(self):
        self.assertEqual(pdf.pdf_string(b"abc" + BS), "abc")

    def test_an_unknown_escape_keeps_its_character(self):
        self.assertEqual(pdf.pdf_string(BS + b"q"), "q")

    def test_empty(self):
        self.assertEqual(pdf.pdf_string(b""), "")


class TestPdfShowRegex(unittest.TestCase):
    """The alternation order, which is the whole correctness of the string finder."""

    def test_AN_ESCAPED_PAREN_AT_THE_END_IS_NOT_LOST(self):
        # `[^()]` matches a lone backslash. In the middle of a string the engine backtracks and
        # recovers; at the END it does not, because the shorter match succeeds and the parenthesis
        # it failed to consume serves as the closing one. Every edition notice here ends this way.
        line = b"(Second Edition " + BS + b"(September 1996" + BS + b"))"
        self.assertEqual(pdf.PDF_SHOW.findall(line),
                         [b"Second Edition " + BS + b"(September 1996" + BS + b")"])

    def test_and_pdf_string_then_reads_it_whole(self):
        line = b"(Second Edition " + BS + b"(September 1996" + BS + b"))"
        raw = pdf.PDF_SHOW.findall(line)[0]
        self.assertEqual(pdf.pdf_string(raw), "Second Edition (September 1996)")

    def test_an_escaped_open_paren_alone_still_works(self):
        self.assertEqual(pdf.PDF_SHOW.findall(b"(a " + BS + b"( b)"), [b"a " + BS + b"( b"])

    def test_two_strings_stay_two(self):
        self.assertEqual(pdf.PDF_SHOW.findall(b"(first) Tj (second)"), [b"first", b"second"])

    def test_an_empty_string_is_found(self):
        self.assertEqual(pdf.PDF_SHOW.findall(b"()"), [b""])


class TestPdfObject(unittest.TestCase):
    def test_it_finds_the_body(self):
        data = b"%PDF\n8 0 obj << /Title (x) >> endobj\n"
        self.assertIn(b"/Title (x)", pdf.pdf_object(data, 8))

    def test_OBJECT_8_IS_NOT_OBJECT_18(self):
        # They end in the same digits, and a naive search finds the wrong one silently, with a
        # perfectly plausible dictionary inside it.
        data = b"%PDF\n18 0 obj << /Title (wrong) >> endobj\n8 0 obj << /Title (right) >> endobj\n"
        self.assertIn(b"right", pdf.pdf_object(data, 8))
        self.assertIn(b"wrong", pdf.pdf_object(data, 18))

    def test_a_missing_object_is_None(self):
        self.assertIsNone(pdf.pdf_object(b"%PDF\n", 9))

    def test_the_generation_matters(self):
        data = b"%PDF\n8 1 obj << /a (b) >> endobj\n"
        self.assertIsNone(pdf.pdf_object(data, 8, 0))
        self.assertIsNotNone(pdf.pdf_object(data, 8, 1))


class TestPdfInfo(unittest.TestCase):
    """From the /Info dictionary, which is what it always claimed."""

    def test_it_reads_the_info_dictionary(self):
        got = pdf.pdf_info(build_pdf(title=b"Real Title"))
        self.assertEqual(got["Title"], "Real Title")
        self.assertEqual(got["Author"], "IBM Corporation")

    def test_A_BOOKMARK_IS_NOT_THE_DOCUMENT_TITLE(self):
        # It used to search the whole file and take the first /Title, which in a document with
        # bookmarks is a bookmark, because the outline objects come first. Reporting that
        # confidently is the exact failure this tool exists to avoid.
        outline = b"6 0 obj << /Title (1.1 Microprocessor Overview) >> endobj\n"
        got = pdf.pdf_info(build_pdf(title=b"Contents", extra_objects=outline))
        self.assertEqual(got["Title"], "Contents")

    def test_a_utf16_title_is_decoded(self):
        raw = pdf_octal(b"\xfe\xff" + "Contents".encode("utf-16-be"))
        self.assertEqual(pdf.pdf_info(build_pdf(title=raw))["Title"], "Contents")

    def test_an_empty_value_is_dropped(self):
        self.assertNotIn("Title", pdf.pdf_info(build_pdf(title=b"   ")))

    def test_THE_LAST_TRAILER_WINS(self):
        # A file revised in place has several. An earlier one names the metadata as it was before
        # the revision, which is a true fact about a file nobody has.
        data = (b"%PDF-1.4\n7 0 obj << /Title (old) >> endobj\n"
                b"trailer << /Info 7 0 R >>\n"
                b"8 0 obj << /Title (new) >> endobj\n"
                b"trailer << /Info 8 0 R >>\n%%EOF\n")
        self.assertEqual(pdf.pdf_info(data)["Title"], "new")

    def test_NO_TRAILER_FALLS_BACK_AND_SAYS_SO(self):
        # A damaged file should still give up what it has -- but the reader has to be able to
        # tell which kind of answer they are looking at.
        data = build_pdf(title=b"Something", with_trailer=False)
        got = pdf.pdf_info(data)
        self.assertEqual(got.get("Title?"), "Something")
        self.assertNotIn("Title", got)

    def test_an_info_reference_pointing_nowhere_also_falls_back(self):
        data = b"%PDF-1.4\n9 0 obj << /Title (found anyway) >> endobj\ntrailer << /Info 8 0 R >>\n"
        self.assertEqual(pdf.pdf_info(data).get("Title?"), "found anyway")


class TestPdfPageCount(unittest.TestCase):
    def test_it_counts_pages(self):
        self.assertEqual(pdf.pdf_page_count(build_pdf()), 1)

    def test_TYPE_PAGES_IS_NOT_A_PAGE(self):
        # /Type /Pages is the tree node. Counting it would report one page too many in every file.
        self.assertEqual(pdf.pdf_page_count(b"/Type /Pages /Count 40"), None)

    def test_NONE_IS_NOT_ZERO(self):
        # In an object-stream PDF the page objects cannot be seen from the raw bytes at all, and
        # a printed 0 reads as a fact rather than as a failure to look.
        self.assertIsNone(pdf.pdf_page_count(b"%PDF-1.5\nnothing countable here\n"))


class TestPdfXmpTitle(unittest.TestCase):
    def test_it_strips_the_tags(self):
        data = build_pdf(xmp=b"<rdf:Alt><rdf:li>AIX Version 7.1</rdf:li></rdf:Alt>")
        self.assertEqual(pdf.pdf_xmp_title(data), "AIX Version 7.1")

    def test_no_packet_is_None(self):
        self.assertIsNone(pdf.pdf_xmp_title(build_pdf()))

    def test_an_empty_title_is_None_not_an_empty_string(self):
        self.assertIsNone(pdf.pdf_xmp_title(build_pdf(xmp=b"   ")))


class TestPdfOutline(unittest.TestCase):
    def test_it_lists_the_bookmarks_in_order(self):
        objs = (b"6 0 obj << /Title (1.1 Overview) >> endobj\n"
                b"7 0 obj << /Title (Chapter 2 Installing) >> endobj\n")
        self.assertEqual(pdf.pdf_outline(build_pdf(extra_objects=objs)),
                         ["1.1 Overview", "Chapter 2 Installing"])

    def test_A_BOOKMARK_IS_AN_ORDINARY_PDF_STRING(self):
        # Resolving only the parenthesis escapes printed a UTF-16 title as `\376\377\000C...` --
        # line noise, in a report whose entire purpose is to be read by a person naming a file.
        raw = pdf_octal(b"\xfe\xff" + "Contents".encode("utf-16-be"))
        objs = b"6 0 obj << /Title (" + raw + b") >> endobj\n"
        self.assertEqual(pdf.pdf_outline(build_pdf(extra_objects=objs)), ["Contents"])

    def test_duplicates_are_dropped(self):
        objs = (b"6 0 obj << /Title (Same) >> endobj\n7 0 obj << /Title (Same) >> endobj\n")
        self.assertEqual(pdf.pdf_outline(build_pdf(extra_objects=objs)), ["Same"])

    def test_the_limit_is_honoured(self):
        objs = b"".join(b"%d 0 obj << /Title (T%d) >> endobj\n" % (i, i) for i in range(10, 20))
        self.assertEqual(len(pdf.pdf_outline(build_pdf(extra_objects=objs), limit=3)), 3)

    def test_no_outline_is_an_empty_list(self):
        self.assertEqual(pdf.pdf_outline(build_pdf()), [])


class TestPdfDrawnText(unittest.TestCase):
    def test_it_reads_a_flate_stream(self):
        data = build_pdf(content=b"BT (Hello there) Tj ET")
        self.assertEqual(pdf.pdf_drawn_text(data), "Hello there")

    def test_whitespace_is_collapsed(self):
        data = build_pdf(content=b"BT (a) Tj ET\nBT (   b\n\nc ) Tj ET")
        self.assertEqual(pdf.pdf_drawn_text(data), "a b c")

    def test_AN_OCTAL_BECOMES_A_SPACE_HERE(self):
        # Not an inconsistency with pdf_string: in a stream drawn with a subset font in a custom
        # encoding the byte between the parentheses is a GLYPH INDEX, not a character, and
        # decoding it produces confident nonsense. A space says "unreadable", which is the truth.
        data = build_pdf(content=b"BT (" + BS + b"061" + BS + b"062 drawn) Tj ET")
        self.assertEqual(pdf.pdf_drawn_text(data), "drawn")

    def test_an_escaped_paren_at_the_end_survives(self):
        data = build_pdf(content=b"BT (Second Edition " + BS + b"(September 1996" + BS + b")) Tj ET")
        self.assertEqual(pdf.pdf_drawn_text(data), "Second Edition (September 1996)")

    def test_a_stream_that_is_not_flate_is_skipped_not_fatal(self):
        data = b"%PDF-1.4\n5 0 obj << >>\nstream\nnot compressed at all\nendstream endobj\n"
        self.assertEqual(pdf.pdf_drawn_text(data), "")

    def test_nothing_extractable_is_an_empty_string(self):
        # A real answer: a scan, or subset fonts. Four AIX manuals here are exactly that.
        self.assertEqual(pdf.pdf_drawn_text(build_pdf()), "")

    def test_the_limit_is_honoured(self):
        data = build_pdf(content=b"BT (" + b"x" * 500 + b") Tj ET")
        self.assertEqual(len(pdf.pdf_drawn_text(data, limit=100)), 100)


class TestIsPdf(unittest.TestCase):
    def test_the_header_not_the_extension(self):
        self.assertTrue(pdf.is_pdf(b"%PDF-1.4\n..."))
        self.assertFalse(pdf.is_pdf(b"<!DOCTYPE html>"))
        self.assertFalse(pdf.is_pdf(b""))

    def test_it_agrees_with_magic_mismatch(self):
        self.assertIsNone(common.magic_mismatch("a.pdf", b"%PDF-1.4"))
        self.assertIsNotNone(common.magic_mismatch("a.pdf", b"<html>"))


class TestTheConstantsNoTestTouched(unittest.TestCase):
    """Ten exports no test mentioned, measured 2026-09-24. None has a caller outside pdf.py.

    WHAT IS WORTH ASSERTING ABOUT A PATTERN is not the pattern -- a copy of the source line
    fails only when somebody edits it on purpose. It is the RELATIONSHIP to the function that
    reads it: this one finds the thing that one extracts, and the two are still looking at the
    same feature of the format. Every rule in here was learned from a real document, and every
    one of these is the shape of that lesson.
    """

    def test_PDF_MAGIC_is_the_same_four_bytes_common_keeps(self):
        """Spelled twice on purpose -- and that is exactly why it needs checking once.

        common.MAGIC[".pdf"] is what magic_mismatch() consults, and it must not have to import
        a PDF reader to answer a question about extensions. Two copies of four bytes is cheaper
        than that dependency; two copies that DISAGREE would be a file this collection calls
        broken under one check and fine under the other.
        """
        self.assertEqual(pdf.PDF_MAGIC, common.MAGIC[".pdf"][0])
        self.assertTrue(pdf.is_pdf(pdf.PDF_MAGIC + b"-1.4"))

    def test_PDF_STREAM_finds_what_pdf_drawn_text_reads(self):
        doc = b"1 0 obj\nstream\nBT (hello) Tj ET\nendstream\nendobj"
        found = pdf.PDF_STREAM.findall(doc)
        self.assertEqual(len(found), 1)
        self.assertIn(b"hello", found[0])

    def test_and_it_stops_at_the_first_endstream(self):
        # Greedy matching would swallow two objects into one and report the second's text as
        # part of the first.
        doc = b"stream\nA\nendstream\nstream\nB\nendstream"
        self.assertEqual(len(pdf.PDF_STREAM.findall(doc)), 2)

    def test_PDF_UNESCAPE_undoes_what_a_pdf_string_escapes(self):
        self.assertEqual(pdf.PDF_UNESCAPE.sub(rb"\1", rb"a\(b\)c\\d"), rb"a(b)c\d")

    def test_and_it_leaves_an_unrelated_backslash_alone(self):
        # Only the three characters a PDF string escapes. `\n` is handled elsewhere, and
        # stripping it here would join two lines into one word.
        self.assertEqual(pdf.PDF_UNESCAPE.sub(rb"\1", rb"a\nb"), rb"a\nb")

    def test_PDF_OCTAL_matches_the_escapes_Distiller_writes(self):
        for raw in (rb"\101", rb"\12", rb"\7"):
            self.assertEqual(pdf.PDF_OCTAL.findall(raw), [raw])

    def test_AND_STOPS_AT_THREE_DIGITS(self):
        # `\1012` is octal 101 followed by the character "2". Taking four would shift every
        # byte after it, which is how a title turns into mojibake rather than into an error.
        self.assertEqual(pdf.PDF_OCTAL.findall(rb"\1012"), [rb"\101"])

    def test_and_8_and_9_are_not_octal(self):
        # str.isdigit() accepts them and octal does not; pdf_string crashed on `\8` for that
        # reason before the rule was written down.
        self.assertEqual(pdf.PDF_OCTAL.findall(rb"\8"), [])

    def test_PDF_TRAILER_INFO_reads_the_reference_pdf_info_resolves(self):
        self.assertEqual(pdf.PDF_TRAILER_INFO.findall(b"trailer\n<< /Info 12 0 R /Root 1 0 R >>"),
                         [(b"12", b"0")])

    def test_AND_pdf_info_TAKES_THE_LAST_ONE(self):
        """An incrementally updated PDF carries several trailers. The last one wins, and reading
        the first returns the title the document had before it was revised."""
        self.assertEqual(pdf.PDF_TRAILER_INFO.findall(b"/Info 1 0 R ... /Info 99 0 R")[-1],
                         (b"99", b"0"))

    def test_PDF_INFO_KEYS_is_what_pdf_info_looks_for(self):
        self.assertIn("Title", pdf.PDF_INFO_KEYS)
        # Order matters: Title before Subject before the tool names. A document with both must
        # answer with its title, not with the name of the program that made it.
        self.assertLess(pdf.PDF_INFO_KEYS.index("Title"), pdf.PDF_INFO_KEYS.index("Producer"))

    def test_PDF_XMP_TITLE_finds_a_title_in_the_metadata_packet(self):
        self.assertTrue(pdf.PDF_XMP_TITLE.search(b"<dc:title><rdf:Alt><li>X</li></rdf:Alt></dc:title>"))

    def test_AND_IT_IS_BOUNDED(self):
        """The 400-character ceiling is the point: an unbounded `.*?` across a 40 MB file is a
        scan of the whole document for every candidate, and a malformed packet with no closing
        tag would never stop."""
        self.assertIsNone(pdf.PDF_XMP_TITLE.search(b"<dc:title>" + b"x" * 500 + b"</dc:title>"))

    def test_PDF_XML_TAGS_leaves_the_text_between_them(self):
        got = pdf.PDF_XML_TAGS.sub(b" ", b"<rdf:Alt><li>Real Title</li></rdf:Alt>")
        self.assertEqual(b" ".join(got.split()), b"Real Title")

    def test_PDF_OUTLINE_TITLE_reads_a_bookmark(self):
        self.assertEqual(pdf.PDF_OUTLINE_TITLE.findall(b"/Title (Chapter One) /Parent"),
                         [b"Chapter One"])

    def test_AND_IT_REFUSES_THE_VERY_SHORT_AND_THE_VERY_LONG(self):
        # 2 to 120 characters. A one-character bookmark is a page number; a 400-character one is
        # a paragraph somebody pasted, and neither is a document title.
        self.assertEqual(pdf.PDF_OUTLINE_TITLE.findall(b"/Title (X)"), [])
        self.assertEqual(pdf.PDF_OUTLINE_TITLE.findall(b"/Title (" + b"x" * 200 + b")"), [])

    def test_and_an_escaped_bracket_does_not_end_it(self):
        self.assertEqual(pdf.PDF_OUTLINE_TITLE.findall(rb"/Title (A \(B\) C)"), [rb"A \(B\) C"])

    def test_PDF_PAGE_TYPE_counts_pages_and_not_the_page_tree(self):
        """`/Type /Pages` is the NODE that holds them. Counting it would add one per tree level
        to every document, which is why the pattern refuses a following `s`."""
        doc = b"/Type /Page /Contents ... /Type /Pages /Kids ... /Type /Page\n"
        self.assertEqual(len(pdf.PDF_PAGE_TYPE.findall(doc)), 2)
        self.assertEqual(pdf.pdf_page_count(doc), 2)

    def test_and_whitespace_between_the_two_names_is_allowed(self):
        self.assertEqual(len(pdf.PDF_PAGE_TYPE.findall(b"/Type/Page ")), 1)
        self.assertEqual(len(pdf.PDF_PAGE_TYPE.findall(b"/Type   /Page ")), 1)

if __name__ == "__main__":
    unittest.main()
