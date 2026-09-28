# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Does the widened parse_listing() find the new links WITHOUT losing the old ones?

The risk in this change is not that it finds too little -- it is that appending images or
single-quoted links disturbs the three column matchers, whose output feeds the ETA and the file
dates. So every case below checks BOTH directions.

WHAT IS UNDER TEST MOVED ON 2026-09-23 AND THESE CASES DID NOT. parse_listing lived in
mirror.py, and this file loaded that 6 700-line module by path to reach it -- which was also how
subset-refetch.py reached it, while measure-remote.py had written its own. It is in common.py
now, and this file imports it like any other caller. The cases stay here, in the file whose whole
subject they are; copying them into common_test.py would put the same evidence in two places.

    python parse_listing_test.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class Checker(object):
    def __init__(self):
        self.fails = []

    def __call__(self, label, got, want):
        ok = got == want
        print("  %-58s %s" % (label, "ok" if ok else "FAIL"))
        if not ok:
            print("      expected: %r" % (want,))
            print("      got     : %r" % (got,))
            self.fails.append(label)


def run(m, check):
    # --- an Apache index: columns must still be read, and no image is present ----------------
    #
    # The rows are written the way Apache actually emits them, one <tr> each. An earlier version
    # of this test jammed a bare "Parent" anchor directly against the first <tr>; ROW_RE then
    # matched ACROSS the two and reported the parent link carrying the file's size. That was the
    # test lying, not the parser -- but it is exactly how a fabricated fixture manufactures a
    # false alarm, so the fixture is now shaped like the real thing.
    apache = ('<tr><td><a href="../">Parent Directory</a></td>'
              '<td align="right">  - </td><td align="right">  - </td></tr>'
              '<tr><td><a href="doc.pdf">doc.pdf</a></td>'
              '<td align="right">2002-04-10 17:08  </td><td align="right">1.2M</td></tr>')
    r = m.parse_listing(apache)
    check("Apache index: file with size and date",
          [(h, s, bool(d)) for h, s, d in r], [("doc.pdf", int(1.2 * 1024 ** 2), True)])

    # --- the same page, with images=True: an icon must NOT displace the columns --------------
    apache_img = apache + '<img src="icons/folder.gif">'
    r = m.parse_listing(apache_img, images=True)
    check("index + <img>: columns stay, image is appended",
          [h for h, _s, _d in r], ["doc.pdf", "icons/folder.gif"])
    check("index + <img>: the real file's size is unchanged",
          r[0][1], int(1.2 * 1024 ** 2))

    # --- a hand-written page: single quotes, no quotes, and an embedded photograph -----------
    hand = ("<a href=\"a.html\">a</a>"
            "<a href='b.html'>b</a>"
            "<a href=c.html>c</a>"
            "<a name='x' href='d.html'>d</a>"
            "<img src='penarch.jpg'>"
            '<img src="board.gif" alt="board">')
    r = m.parse_listing(hand, images=True)
    check("hand-written: all four link forms plus two images",
          sorted(h for h, _s, _d in r),
          sorted(["a.html", "b.html", "c.html", "d.html", "penarch.jpg", "board.gif"]))

    # --- images=False must behave exactly as before ------------------------------------------
    r = m.parse_listing(hand, images=False)
    check("images=False: no image, links still complete",
          sorted(h for h, _s, _d in r), sorted(["a.html", "b.html", "c.html", "d.html"]))

    # --- no duplicates when a page links AND embeds the same file ----------------------------
    dup = "<a href=\"p.jpg\">p</a><img src=\"p.jpg\">"
    r = m.parse_listing(dup, images=True)
    check("same file linked and embedded: only once", [h for h, _s, _d in r], ["p.jpg"])

    # --- external and data: URIs must stay out -----------------------------------------------
    ext = ("<img src=\"https://cdn.example.com/x.gif\">"
           "<img src=\"data:image/gif;base64,R0lGOD\">"
           "<img src=\"local.gif\">")
    r = m.parse_listing(ext, images=True)
    check("foreign hosts and data: URIs stay out", [h for h, _s, _d in r], ["local.gif"])

    # --- the lighttpd shape that once cost whole subtrees ------------------------------------
    lig = ('<tr><td class="n"><a href="sub/">sub/</a></td>'
           '<td class="m">2010-01-02 03:04</td><td class="s">4.0K</td></tr>')
    r = m.parse_listing(lig)
    check("lighttpd column order still recognised", [h for h, _s, _d in r], ["sub/"])

    # --- href that is NOT the first attribute, double-quoted ---------------------------------
    #
    # `<a class="..." href="...">` is what every template engine emits. LINK_RE wants href FIRST
    # and LINK_ODD_RE excluded double quotes until 2026-09-11, so between them they saw 3 of the
    # 87 links on www.novasareforever.org/archives/ -- and that run reported COMPLETE WITH ZERO
    # FILES.
    cms = ('<a class="btn x" href="/archives/software/dg.aviion">AViiON</a>'
           '<a href="plain.html">plain</a>'
           "<a id='q' href='single.html'>single</a>"
           '<a data-x=1 href=bare.html>bare</a>')
    check("href not the first attribute, all four forms",
          sorted(h for h, _s, _d in m.parse_listing(cms, allow_up=True)),
          sorted(["/archives/software/dg.aviion", "plain.html", "single.html", "bare.html"]))

    # --- a FRAMESET root, which names its children with <frame src> and nothing else ---------
    #
    # transputer.classiccmp.org's front page is 387 bytes of exactly this. Before FRAME_RE the
    # parser returned nothing, the crawler walked nowhere, and the run reported COMPLETE with
    # ZERO FILES over a 1.72 GB archive -- with zero failures, so no counter could have caught it.
    frameset = ('<html><head><title>Ram\'s Transputer Home Page</title></head>'
                '<frameset cols="26%,74%">'
                '<frame src="topic.html" name="topics">'
                '<frame src="main_page.html" name="stage">'
                '<noframes><body></body></noframes></frameset></html>')
    check("frameset root: both children found",
          [h for h, _s, _d in m.parse_listing(frameset)], ["topic.html", "main_page.html"])

    # An <iframe>, and one pointing off-site which must still be refused.
    iframe = ('<iframe src="inner.html"></iframe>'
              '<iframe src="https://example.com/x.html"></iframe>')
    check("iframe: own yes, foreign no",
          [h for h, _s, _d in m.parse_listing(iframe)], ["inner.html"])

    # is_child_link, strip_cache_buster and same_path_plus_slash WERE CHECKED HERE UNTIL
    # 2026-09-22. They moved to common.py and their cases moved to common_test.py, which covers
    # them more widely than this did -- 9, 7 and 7 methods against the 13, 7 and 6 cases that
    # stood here, plus a sweep over every extension in STATIC_IMAGE.
    #
    # The cases that remain in this file are the ones that go THROUGH parse_listing(), because
    # those test the parser's use of those rules rather than the rules themselves. That is the
    # line: a rule belongs to the library and its test to common_test.py; what the parser does
    # with the result belongs here.

    # A SORTABLE TABLE HEADER IS A LINK TOO. Apache's HTMLTable autoindex and LiteSpeed's write
    # <th><a href="?C=N;O=D">Name</a></th> -- href as the FIRST attribute. The old `.*?` in ROW_RE
    # started a match there and ran to the first </a></td> in the document, that is into the FIRST
    # DATA ROW, which was thereby swallowed. ftp.irixnet.org lost its alphabetically first
    # directory that way, and the run reported COMPLETE.
    hdr = (
        '<table><thead class="t-header"><tr>'
        '<th class="c"><a class="name" href="?ND" onclick="return false">Name</a></th>'
        '<th class="c"><a href="?MA" onclick="return false">Last Modified</a></th>'
        '<th class="c"><a href="?SA" onclick="return false">Size</a></th></tr></thead>'
        '<tr><td data-sort="*first"><a href="/first/"><img class="icon" src="/i.svg">first</a>'
        '</td><td data-sort="1">2021-07-10 23:03</td><td data-sort="-1">-</td></tr>'
        '<tr><td data-sort="*second"><a href="/second/">second</a></td>'
        '<td>2025-11-29 07:29</td><td>-</td></tr></table>')
    check("table header: the first data row survives",
          sorted(h for h, _s, _m in m.parse_listing(hdr)), ["/first/", "/second/"])

    # And the same in Apache's own spelling.
    apache_table = (
        '<table><tr><th><a href="?C=N;O=D">Name</a></th>'
        '<th><a href="?C=M;O=A">Last modified</a></th>'
        '<th><a href="?C=S;O=A">Size</a></th></tr>'
        '<tr><td><a href="aaa/">aaa/</a></td><td>2019-01-01 10:00</td><td>-</td></tr>'
        '<tr><td><a href="bbb.txt">bbb.txt</a></td><td>2019-01-02 11:00</td><td>4.0K</td></tr>'
        '</table>')
    check("Apache HTMLTable: the first data row survives",
          sorted(h for h, _s, _m in m.parse_listing(apache_table)), ["aaa/", "bbb.txt"])

    # RESOLVE HTML ENTITIES BEFORE ANY CHECK. A site in this collection disguises its contact
    # address as numeric character references -- a twenty-year-old spam defence, and the reason
    # the address here is an invented one: writing the real one out in clear would undo exactly
    # what its operator went to the trouble of doing. The fixture proves the decoding, and any
    # address does that equally well.
    #
    # Unresolved, the scheme check sees no
    # `mailto:`, and strip_fragment cuts at the '#' of `&#109;` so that a bare `&` is left.
    # is_child_link('&') is True, so the crawler requested <base>/& and counted the 404.
    ent = ("<a href=\"&#109;&#097;&#105;&#108;&#116;&#111;&#058;someone@example.invalid\">Mail</a>"
           "<a href=\"echt.pdf\">real</a>"
           "<a href=\"a&amp;b.txt\">ampersand in the filename</a>")
    check("entities: disguised mailto out, &amp; in the name resolved",
          [h for h, _s, _m in m.parse_listing(ent)], ["echt.pdf", "a&b.txt"])

    # And through the parser: the image must arrive as a child, the link beside it unchanged.
    body = '<html><p><img src="Lacuna.gif?v=3" width="550"></p><a href="x.txt">x</a></html>'
    check("cache-buster: through parse_listing(images=True)",
          sorted(h for h, _s, _m in m.parse_listing(body, allow_up=True, images=True)),
          ["Lacuna.gif", "x.txt"])
    check("cache-buster: stays out without images",
          [h for h, _s, _m in m.parse_listing(body, allow_up=True)], ["x.txt"])

    # ROW_RE WAS QUADRATIC AND BROUGHT A RUN TO A STANDSTILL -- not to a crash. The tempered dot
    # was `*?` with no bound, and on a page with many anchors and NO table it ran to end of file
    # for every anchor; `</title>` does not stop it, the letter after `</t` is wrong. Measured on
    # mirrors.develooper.com/hpux/id-20100310.html: 5.4 MB, 22 165 <a href>, zero </td>. The crawl
    # sat at 99 % of one core, reported `fail 0` and gained three files in ninety minutes, while
    # the host answered in 1.3 s.
    #
    # This test is a TIME BOUND, and for a stall that is the only form that works: a hang is not
    # an exception one can catch and inspect.
    stat_page = ("<html><head><title>ITRC Forum statistics</title></head><body>\n<pre>\n"
                 + "".join('  %5d <a href="http://x/p?u=BR%06d&amp;f=1">BR%06d</a>  Name  0 0 -\n'
                           % (i, i, i) for i in range(4000))
                 + "</pre></body></html>\n")
    t0 = time.time()
    hits = m.parse_listing(stat_page, allow_up=True)
    dt = time.time() - t0
    check("stall: 4 000 anchors without a table in under 2 s (was: minutes)", dt < 2.0, True)
    print("     measured: %.4f s, %d children" % (dt, len(hits)))

    # The guard alone is not enough: ONE table cell anywhere and it no longer applies. Then the
    # {0,400} bound carries it.
    one_cell = stat_page.replace("</pre>", "<table><tr><td>x</td></tr></table></pre>")
    t0 = time.time()
    m.parse_listing(one_cell, allow_up=True)
    dt = time.time() - t0
    check("stall: the same page with ONE cell, under 2 s", dt < 2.0, True)
    print("     measured: %.4f s" % dt)

    # And the other direction, which must not be lost along the way: what ROW_RE MUST find, it
    # still finds. That is exactly the case it was rebuilt for after the irixnet defect -- a
    # sortable header row, and the first data row must not be swallowed.
    sortable = ('<table><tr><th><a href="?C=N;O=D">Name</a></th><th>Last modified</th>'
                '<th>Size</th></tr>\n'
                '<tr><td><a href="nekoware/">nekoware/</a></td><td>2024-01-15 10:22</td>'
                '<td>-</td></tr>\n'
                '<tr><td><a href="big.tar.gz">big.tar.gz</a></td><td>2009-03-02 08:00</td>'
                '<td>604M</td></tr>\n</table>')
    check("ROW_RE after the bound: sortable header, both rows",
          [h for h, _s, _m in m.parse_listing(sortable)], ["nekoware/", "big.tar.gz"])

    # WHAT THE BOUND COSTS, measured rather than estimated. The first draft of this test expected
    # a link text over 400 characters to lose the FILE. It does not: if ROW_RE drops out, the bare
    # link scan takes over and the href arrives anyway -- without size and without date. The price
    # is METADATA, not content, and that is a different price. A filename reaches 255 bytes on no
    # filesystem mirrored here, let alone 400.
    long_row = ('<table><tr><td><a href="f.bin">%s</a></td><td>2024-01-01 00:00</td>'
                '<td>12K</td></tr></table>')
    check("bound: 399 characters -- file WITH size and date",
          m.parse_listing(long_row % ("x" * 399)), [("f.bin", 12288, 1704063600.0)])
    check("bound: 401 characters -- file present, columns gone",
          [(h, s, t) for h, s, t in m.parse_listing(long_row % ("x" * 401))],
          [("f.bin", None, None)])

    # A PARTIAL MATCH MUST NOT DISPLACE THE FULL SCAN. Until 2026-09-17 the rule read
    # `if out: return out` -- any non-empty result from a column matcher won. On
    # adoxa.altervista.org the front page is a hand-written <table> whose third column carries a
    # VERSION NUMBER, and ROW_RE cannot tell a version from a size: "1.71" matches `[0-9.]+`,
    # "19.00a3" does not. ROW_RE returned 17 rows, the link scan would have returned 61, and the
    # run fetched 30 of 207 files -- with `0 failures, 0 unreadable listings`.
    versions = ('<table>\n'
                '<tr><th>Program</th><th>Description</th><th>Version</th></tr>\n'
                + "".join('<tr><td><a href="p%d/index.html">P%d</a></td><td>desc</td>'
                          '<td align="center">%s</td></tr>\n'
                          % (i, i, "1.71" if i % 2 else "19.00a3") for i in range(20))
                + '</table>')
    got = [h for h, _s, _m in m.parse_listing(versions)]
    check("partial match: hand-written table -> ALL 20 links, not the 10 with a numeric column",
          len(got), 20)
    print("     ROW_RE alone would find: %d" % len(m.ROW_RE.findall(versions)))

    # And the other direction, which must not be lost: a REAL autoindex is still read by the
    # column matcher, WITH size and date. There the two counts lie close together -- every row is
    # a link -- while the project table above sat at 0.28.
    auto = ('<table><tr><th><a href="?C=N;O=D">Name</a></th><th>Last modified</th>'
            '<th>Size</th></tr>\n'
            '<tr><td><a href="nekoware/">nekoware/</a></td><td>2024-01-15 10:22</td>'
            '<td>-</td></tr>\n'
            '<tr><td><a href="big.tar.gz">big.tar.gz</a></td><td>2009-03-02 08:00</td>'
            '<td>604M</td></tr>\n</table>')
    # The link and the SIZE are checked, the date is not: parse_date returns a local timestamp,
    # and a hard-coded value makes the test depend on the machine's time zone. The first draft did
    # exactly that and failed by eight hours.
    check("partial match: a real autoindex keeps its sizes",
          [(h, s) for h, s, _t in m.parse_listing(auto)],
          [("nekoware/", None), ("big.tar.gz", 633339904)])
    check("partial match: a real autoindex keeps a date too",
          all(t is not None for _h, _s, t in m.parse_listing(auto)), True)

    # APACHE'S SECOND DATE FORMAT. FancyIndexing writes DD-Mon-YYYY, not ISO, and PRE_RE demanded
    # ISO until 2026-09-17. On such a listing parse_listing fell back to the bare link scan: the
    # files arrived, but WITHOUT size and WITHOUT date -- that is, with the day they were copied
    # instead of the day they were published. Found on ftp.oldskool.org/pub/, where both styles
    # sit side by side: IBM_PC_BBS/ is HTMLTable, ftp.bocaresearch.com/ is FancyIndexing with
    # timestamps from 2004, which are exactly what is valuable about it.
    fancy = ('<pre><a href="../">Parent Directory</a>\n'
             '<a href="pdf/">pdf/</a>                     25-Mar-2011 00:05         -\n'
             '<a href="9331.zip">9331.zip</a>             26-Mar-2004 05:00    919216\n'
             '</pre>')
    r = [(h, s) for h, s, _t in m.parse_listing(fancy)]
    check("Apache FancyIndexing DD-Mon-YYYY: the size is read",
          [x for x in r if x[0] == "9331.zip"], [("9331.zip", 919216)])
    check("Apache FancyIndexing DD-Mon-YYYY: the date is read",
          all(t is not None for h, _s, t in m.parse_listing(fancy) if h == "9331.zip"), True)

    iso = ('<pre><a href="../">Parent Directory</a>\n'
           '<a href="big.tar.gz">big.tar.gz</a>          2009-03-02 08:00       604M\n'
           '</pre>')
    check("Apache FancyIndexing ISO is unchanged",
          [(h, s) for h, s, _t in m.parse_listing(iso)], [("big.tar.gz", 633339904)])


def main():
    check = Checker()
    # `run` takes the module holding parse_listing, which is the library now. It is passed in
    # rather than reached for directly so the cases below read as they always did.
    run(common, check)

    print()
    if check.fails:
        print("  %d test(s) failed: %s" % (len(check.fails), ", ".join(check.fails)))
        return 1
    print("  all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
