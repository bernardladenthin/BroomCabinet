# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Where does an answer of the shape "we will not give you this" live?

A SOURCE SAYING NO IS NOT A SOURCE SAYING GONE, and until 2026-10-04 the second kind of answer
had nowhere to go. Six paths in this collection are permanently refused:

    technologists-sauer  asgchs91.rm, songs/zekeswaltz.mp3, songs/zekeswaltz.html   403
    typewritten          Manual/IBM/AIX/2.2.1/man2/sh .html                         403
    fjkraan              comp/m10/guide                                             403
    bretjohnson          forum                                                      500

record_gone refuses every one of them, CORRECTLY: 403 and 500 say "we will not serve you this",
which may stop being true tomorrow, and collapsing that into "gone" is the mistake read_gone's own
docstring exists to prevent. But a completeness check that reports them on every run is a check
nobody can read, and converge.py spent one wasted round on each before its gain brake noticed.

SO THEY GET THEIR OWN FILE rather than a widened GONE_STATUS. Widening would change the meaning of
a record data has already been written against, and this register's rule for that is explicit.
The owner chose this over widening when both were put to him.

AND SIX OTHER PATHS NEEDED NO RECORD AT ALL. `<dir>/.html` is not a filename -- an extension with
nothing in front of it -- and is now dropped by the harvester. Measured before the rule was
written: of 1 814 446 indexed files, ZERO have a name of that shape.

NO NETWORK AND NO COLLECTION.
"""
import ast
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402


class ARefusalIsNotAGoneFile(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="refused-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_an_empty_archive_reads_as_nothing_refused(self):
        """Callers ask about archives that have never met a refusal, which is most of them."""
        self.assertEqual(common.read_refused(self.d), {})

    def test_a_403_is_recorded_with_its_status_and_date(self):
        self.assertTrue(common.record_refused(self.d, "songs/zekeswaltz.mp3", 403,
                                              when="2026-10-04"))
        self.assertEqual(common.read_refused(self.d),
                         {"songs/zekeswaltz.mp3": ("2026-10-04", 403)})

    def test_a_500_is_recorded_too(self):
        """bretjohnson.us/forum answers 500. A server error on a CMS route is as permanent in
        practice as a 403, and the status is kept so a reader can tell them apart."""
        common.record_refused(self.d, "forum", 500, when="2026-10-04")
        self.assertEqual(common.read_refused(self.d)["forum"][1], 500)

    def test_A_404_IS_REFUSED_BECAUSE_IT_BELONGS_IN_THE_OTHER_FILE(self):
        """Two records of one fact is worse than one record in the wrong place."""
        for code in sorted(common.GONE_STATUS):
            self.assertFalse(common.record_refused(self.d, "x", code), code)
        self.assertEqual(common.read_refused(self.d), {})

    def test_AND_SO_IS_ANYTHING_THAT_IS_NOT_A_STATUS_AT_ALL(self):
        """A timeout or a DNS failure is OUR side of the wire, or a host having a bad minute.
        develooper-hpux answered 503 on one probe and 404 on the next, which is exactly why this
        line is drawn in the library and not left to each caller."""
        for code in (0, 200, 301, 399, 600, 999):
            self.assertFalse(common.record_refused(self.d, "y", code), code)
        self.assertEqual(common.read_refused(self.d), {})

    def test_the_same_path_is_not_written_twice(self):
        """Three identical lines say nothing a single line plus its date does not -- record_gone's
        reasoning, and the file is a log of answers rather than a set."""
        self.assertTrue(common.record_refused(self.d, "forum", 500))
        self.assertFalse(common.record_refused(self.d, "forum", 500))
        self.assertEqual(len(common.read_refused(self.d)), 1)

    def test_the_file_explains_itself_to_a_human(self):
        """Somebody meeting this file in a year has only its own text to go on."""
        common.record_refused(self.d, "forum", 500)
        with io.open(os.path.join(self.d, common.REFUSED_FILE), encoding="utf-8") as fh:
            head = fh.read()
        self.assertIn("REFUSED", head)
        self.assertIn(".mirror-gone", head)
        self.assertIn("Re-askable", head)

    def test_a_damaged_line_is_skipped_and_not_fatal(self):
        """Same precondition read_gone and read_index answer: damage costs information, never
        correctness."""
        path = os.path.join(self.d, common.REFUSED_FILE)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# a comment\n\nnonsense\n2026-10-04 notanumber x\n2026-10-04 403 good\n")
        self.assertEqual(common.read_refused(self.d), {"good": ("2026-10-04", 403)})

    def test_it_is_bookkeeping_and_not_content(self):
        """In the NARROW set, like GONE_FILE: a record counted as content is hashed into the index
        and then reported as changed every time it is appended to."""
        self.assertIn(common.REFUSED_FILE, common.OWN_FILES)
        self.assertIn(common.REFUSED_FILE, common.BOOKKEEPING_FILES)
        self.assertIn(common.REFUSED_FILE + ".tmp", common.OWN_FILES)


class AnExtensionWithNothingInFrontOfItIsNotAName(unittest.TestCase):
    """is_extension_only, which removed six of the eleven stuck paths without a record.

    typewritten's `Manual/IBM/AIX/2.2.1/man1/.html` and `man5/.html`, seds-frommert's
    `spider/OS2/HPFS/.html` and two siblings. Every one answers 403, so record_gone cannot hold
    them and the completeness check reported them for ever.

    THE SAME REASONING AS remove-fragment-copies.py'S FIRST TEST -- "the part before the first '#'
    is NOT empty: `#System_FW` has no stem; it IS the name". Here the part before the extension is
    empty, so what is left is an extension with nothing in front of it.
    """

    def test_the_six_real_cases(self):
        for href in (".html", "man1/.html", "man5/.html", "spider/OS2/HPFS/.html",
                     "spider/LG/.html", "spider/dss/.html"):
            self.assertTrue(common.is_extension_only(href), href)

    def test_A_DOTFILE_IS_A_NAME(self):
        """The test is not "starts with a dot". `.htaccess` is a file and so is `.mirror-gone`."""
        for href in (".htaccess", ".bashrc", common.GONE_FILE, ".gitignore", common.SUMS_FILE):
            self.assertFalse(common.is_extension_only(href), href)

    def test_an_ordinary_name_is_untouched(self):
        for href in ("index.html", "a/b.html", "x.htm", "dir/page.shtml"):
            self.assertFalse(common.is_extension_only(href), href)

    def test_a_STEM_OF_ONLY_A_SPACE_STILL_COUNTS_AS_A_STEM(self):
        """typewritten's sixth path is `man2/sh .html` -- `sh ` with a trailing space. It has a
        stem, so this rule leaves it alone and it went into .mirror-refused instead. Pinned
        because the tempting fix is to trim the name, and a name belongs to its source."""
        self.assertFalse(common.is_extension_only("man2/sh .html"))
        self.assertFalse(common.is_extension_only("x/ .html"))

    def test_a_non_page_extension_is_not_matched(self):
        """The rule is about links a harvester would chase. `.pdf` with no stem is odd but it is
        not what was measured, and widening a rule past its evidence is how the next false
        positive arrives."""
        self.assertFalse(common.is_extension_only("x/.pdf"))
        self.assertFalse(common.is_extension_only("x/.zip"))

    def test_an_empty_href_is_not_matched(self):
        for href in ("", "/", None):
            self.assertFalse(common.is_extension_only(href), repr(href))

    def test_NO_HELD_FILE_IN_THE_COLLECTION_MATCHES_IT(self):
        """The measurement the rule rests on, re-stated here so the claim is not only a comment:
        1 814 446 indexed files, zero of this shape. This case uses the shipped indexes when they
        are there and skips when they are not, so it is evidence on this machine and never a
        failure on somebody else's."""
        root = common.MIRROR_ROOT
        if not os.path.isdir(root):
            self.skipTest("the collection is not on this machine")
        checked = 0
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not os.path.isdir(d) or name == "logs":
                continue
            rows = common.read_index(os.path.join(d, common.INDEX_FILE))
            checked += len(rows)
            for rel in rows:
                self.assertFalse(common.is_extension_only(rel), name + "/" + rel)
        self.assertGreater(checked, 1000000, "the indexes look unexpectedly small")


class AStorableNameIsNotAMissingFile(unittest.TestCase):
    """The existence check has to ask for the name the file was WRITTEN under.

    gsi-collection's source names a file `Aster*x_3.1.0.50_pcf_font_problem`. NTFS forbids `*`,
    so safe_name() stores it as `Aster_x_...` -- and the completeness check asked for the raw name,
    found nothing, and reported a held file as outstanding. Every file whose name had to be changed
    to be written was reported that way on every single run.

    AND manifest-fetch.py BUILT ITS OWN PATH, which is the worse half of the same defect: it died
    on that name with an unhandled OSError (Errno 22) after 3 788 of 3 789 candidates. Had the
    filesystem allowed the raw name anywhere, it would have stored the file where mirror.py never
    looks -- two tools disagreeing about where a document belongs.

    THE FIRST FIX WAS WRONG AND THE MEASUREMENT CAUGHT IT. Using common.local_path to re-derive
    the path threw away under_site's folding: that function cuts `base_url` off the url literally,
    and dreamlandbbs-os2's pages say http:// where the register says https://. Its figure went
    from 0 to 7 694, and six other archives broke with it. safe_name is applied to the ALREADY
    FOLDED relative path instead.
    """

    def test_safe_name_is_what_decides_where_a_file_lives(self):
        self.assertEqual(common.safe_name("Aster*x_3.1.0"), "Aster_x_3.1.0")
        for bad in "<>:\"|?*":
            self.assertNotIn(bad, common.safe_name("a" + bad + "b"))

    def test_the_harvester_tests_the_storable_name(self):
        with io.open(os.path.join(HERE, "pages-to-urllist.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("safe_name(q) for q in rel.split", src)

    def test_and_NOT_by_re_deriving_the_path_from_the_url(self):
        """local_path would undo under_site's folding. Pinned because it was the obvious fix and
        it broke seven archives' figures."""
        with io.open(os.path.join(HERE, "pages-to-urllist.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("local = local_path(", src)

    def test_the_fetcher_uses_the_library_and_not_its_own_join(self):
        """PARSED, NOT GREPPED. The first draft searched the text and failed on the COMMENT that
        quotes the old line -- the same mistake the os.path.relpath ratchet made two days ago, and
        for the same reason: prose about a defect is worth keeping and a text search cannot tell
        it from the defect.

        AND THE PARSE FOUND A SECOND LIVE ONE the text search had hidden: the `todo` list was also
        testing raw names, so every file stored under a made-storable name was judged missing and
        FETCHED AGAIN on every run."""
        with io.open(os.path.join(HERE, "manifest-fetch.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("out = local_path(base_dir, base_url, url)", src)
        bad = []
        for node in ast.walk(ast.parse(src, "manifest-fetch.py")):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "replace" and len(node.args) == 2):
                continue
            first, second = node.args
            if (isinstance(first, ast.Constant) and first.value == "/"
                    and isinstance(second, ast.Attribute) and second.attr == "sep"):
                bad.append(node.lineno)
        self.assertEqual(bad, [], "a path is still built by replacing / with os.sep instead of "
                                  "going through safe_name or local_path")

    def test_local_path_and_safe_name_agree_on_a_forbidden_character(self):
        """The two routes must land on the same name or the disagreement is back."""
        base = "https://example.org/"
        url = base + "d/Aster%2Ax_1.0"
        got = common.local_path(os.path.join("mirror", "an-archive"), base, url)
        self.assertTrue(got.endswith(os.path.join("d", "Aster_x_1.0")), got)


if __name__ == "__main__":
    unittest.main(verbosity=2)
