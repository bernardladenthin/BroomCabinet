# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Re-ask the live hosts whether they still serve `ZERO_AT_SOURCE`'s files as zeros.

WHY THIS EXISTS. `ZERO_AT_SOURCE` holds 75 files that this collection keeps as nothing but zeros,
and says of every one of them: WE ASKED THE HOST AND IT SERVED ZEROS. That is the only thing
standing between those files and being reported as losses. Its own comment in `audit.py` puts it
plainly -- a record nobody sees is a record nobody can challenge when the source changes -- and
until this existed, nobody could see it: the table was taken with a throwaway script that was
never filed, so the 75 rows were a claim with no way left to test it.

WHAT A RE-ASK CAN FIND, and both outcomes matter:

  * THE SOURCE FIXED IT. Somebody re-uploaded the file, and what we hold really is a loss now --
    a re-fetchable one, which is the best kind of finding this collection can produce.
  * THE SOURCE IS GONE. The row cannot be challenged any more, and it stops being a measurement
    and becomes a memory. That is worth knowing BEFORE somebody leans on it. As of 2026-09-24
    two of the four hosts named in `robots_verdict_test.py` had already stopped answering, which
    is how quickly this happens.

IT NEEDS A URL, AND THE TABLE HOLDS COLLECTION PATHS. The addresses come from `mirror.ARCHIVES`,
which pairs each archive's directory name with the URL it was taken from. The register is read
rather than guessed: two archives of the same host can sit under different names, and inventing an
address is how a tool ends up asking the wrong server and believing the answer. A row whose
archive is not in the register, or is held over rsync, is reported as UNASKABLE rather than
skipped silently -- an unaskable row is exactly the kind that quietly rots.

WHY NOT THE COMPLETION MARKER, which also carries a `source` -- and it does, in 98 of 98 archives.
Measured 2026-09-25: the marker's `source` is PROSE, not an address. It reads
`https://github.com/ -- 3 repos + 1 gist`, or `Q:\mirror\bitsavers\...\ftp.agilent.com_...tar`, or
`http://aixpdslib.seas.ucla.edu/ (VIA web.archive.org -- origin dead)`. 26 of the 94 archives
present in both say something the register does not, and in every one of those 26 the extra words
are provenance a human wrote. That is the right thing for a marker to hold and the wrong thing to
concatenate a path onto.

The marker is still worth reading, and this tool's caller should: it is the only place that says
an archive was taken VIA THE WAYBACK MACHINE, which would mean a row's "the source serves zeros"
was measured against a copy rather than an origin. Checked for the five archives that appear in
`ZERO_AT_SOURCE` -- fsck-vendors, infania-tl2, oldskool, ps-2.kev009.com, sun3arc -- and all five
are direct captures. None of the 75 rows rests on a Wayback copy.

IT CHANGES NOTHING, AND IT DOES NOT READ THE COLLECTION EITHER. The recorded lengths are in the
table; the bytes are at the other end of a URL. Editing `ZERO_AT_SOURCE` is a decision with a
reason attached, and a reason is not something a script can write.

WHAT THE FIRST RUN FOUND, 2026-09-24. All 75 rows turned out to be askable -- none UNASKABLE.
`sun3arc` and `infania-tl2` were re-asked (4 files) and all four are still served as zeros at the
recorded length. The `infania-tl2` pair matters more than its size: those two AIX figures were
originally measured against `ps-2.kev009.com`, and `infania.net` is a host that had never been
asked about them. A third independent witness to the same two files.

    python ask-the-source.py                      # every row that can be asked
    python ask-the-source.py --under fsck-vendors  # one archive
"""
import argparse
import sys
from urllib.parse import urlsplit

import audit
import mirror
from common import Pacer, human, http_try, say, source_url, split_archive

# How long to wait for one file. Generous on purpose: the hosts in this table are small, old and
# slow, and a timeout recorded as "no answer" would be this tool inventing the very finding it
# exists to check for.
TIMEOUT = 90

# HOW LONG TO WAIT BETWEEN TWO REQUESTS TO THE SAME HOST. The throwaway script that first filled
# `ZERO_AT_SOURCE` paced itself at 0.7 s and this tool was written without it -- which does not
# show while re-asking two rows, and would have put 51 requests onto fsck.technology back to back
# the first time somebody ran it over the whole table.
#
# THE WAITING ITSELF IS `common.Pacer`, not a sleep written here. It was a sleep written here for
# about an hour, which is how this collection ended up with 42 of them across 18 tools in two
# incompatible meanings of the word "delay". One more would have been the 43rd.
PER_HOST_PAUSE = 0.7

# What a run reports per row. Kept as one table so the summary cannot drift from the lines above
# it -- the summary that did not add up cost an afternoon once.
SAME = "still zeros, same length"
CHANGED = "THE SOURCE NOW SERVES CONTENT"
LENGTH = "zeros, but a different length"
REFUSED = "the server answered, but not with the file"
GONE = "nobody answered"
UNASKABLE = "no source URL recorded"
ORDER = (CHANGED, LENGTH, REFUSED, GONE, SAME, UNASKABLE)

# REFUSED AND GONE ARE KEPT APART BECAUSE `http_try` KEEPS THEM APART, and its docstring says why
# in one line: a 404 is the server's settled answer and may be written down as final, a socket
# timeout is our end of the wire and means try again another day. Collapsing them is how a
# transient failure gets recorded as permanent -- in a collection whose whole job is to record
# what is permanently gone.
#
# THE DISCRIMINATOR IS `status`, NOT `body`. `http_try` returns bytes ALWAYS, empty on any
# failure, and an int status only when a server answered. Testing `isinstance(body, bytes)` --
# which is what this tool and the throwaway script that first filled ZERO_AT_SOURCE both did --
# is a branch that can never be taken, so "0 unreachable" came out of a line that could not have
# said anything else. The measurement itself survived it (an empty body is length 0, which fails
# the same-length test and lands in a different bucket), but a report that cannot say "gone" is
# not a report. [found 2026-09-24 while testing this file]


def prefixes():
    """The register, as {archive directory name: source URL}."""
    return dict(mirror.ARCHIVES)


# source_url() IS common.py's SINCE 2026-09-27, and this tool is the reason it had to be. It held
# a third version of the rule, without the HTTP_FACE fallback the other two askers had, so every
# bitsavers path came back "unaskable" here while holes-vs-source.py answered a working URL for
# the same input. That is a behaviour change in this tool's favour: bitsavers rows are now asked.
#
# The library's `rel` is RELATIVE TO THE ARCHIVE; this tool's rows carry the archive name in
# front, so splitting one off the other is the part that is genuinely this tool's and it has a
# name of its own below.


def address(rel, register):
    """-> the URL for a row of THIS tool's tables, or None when it cannot be asked over HTTP.

    The rows here are collection-relative -- `bitsavers/pdf/x.zip` -- while common.source_url()
    takes an archive and a path within it. That split is all this function is, and it is written
    down rather than done inline so the tool's own rule has a test separate from the library's.

    A ROW THAT IS ONLY AN ARCHIVE NAME asks for the archive root, which is what an empty tail
    means. Not expected in these tables; answering None instead would be a silent second reason
    for UNASKABLE.
    """
    return source_url(*split_archive(rel), register=register)


def ask(rows, register, report=None, pause=PER_HOST_PAUSE, pacer=None):
    """-> list of (verdict, rel, recorded size, detail). Asks one file at a time, on purpose.

    `pacer` is an argument so the waiting can be tested without a test that waits; left out, one
    is made with `pause`.
    """
    out = []
    pacer = pacer if pacer is not None else Pacer(pause)
    for i, (rel, size) in enumerate(rows, 1):
        if report and i % 10 == 0:
            report("  asked %d of %d" % (i, len(rows)))
        url = address(rel, register)
        if url is None:
            # NOT PACED. Nothing was asked, so there is nobody to be polite to, and sleeping here
            # would make a table full of unaskable rows take minutes to report that.
            out.append((UNASKABLE, rel, size, ""))
            continue
        pacer.wait(urlsplit(url).netloc)
        status, body = http_try(url, timeout=TIMEOUT)
        if not isinstance(status, int):
            out.append((GONE, rel, size, str(status)))
            continue
        if status != 200:
            out.append((REFUSED, rel, size, "HTTP %d" % status))
            continue
        blob = bytes(body)
        if blob.strip(bytes(1)) != b"":
            out.append((CHANGED, rel, size, "%d B, begins %r" % (len(blob), blob[:8])))
        elif len(blob) != size:
            out.append((LENGTH, rel, size, "%d B now" % len(blob)))
        else:
            out.append((SAME, rel, size, ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--under", help="only rows under this archive")
    ap.add_argument("--quiet", action="store_true", help="no progress while it runs")
    args = ap.parse_args(argv)

    known = sorted({split_archive(rel)[0] for rel, _s in audit.ZERO_AT_SOURCE})
    if args.under and args.under not in known:
        # A TYPO MUST NOT LOOK LIKE A CLEAN RUN. Filtering to nothing and reporting success is
        # how somebody checks an archive, sees no findings, and believes it -- having asked
        # about zero files. The archives that HAVE rows are named, because the whole point of
        # --under is that the caller does not know the table by heart.
        say("no rows recorded under %r" % args.under)
        say("the table covers: %s" % ", ".join(known))
        return 2

    rows = [(rel, size) for rel, size in audit.ZERO_AT_SOURCE
            if not args.under or split_archive(rel)[0] == args.under]
    if not rows:
        say("the table is empty -- nothing to ask about")
        return 2

    say("=== Asking the source about %d recorded file(s) ===" % len(rows))
    results = ask(rows, prefixes(), report=None if args.quiet else say)

    counts = {}
    for verdict, rel, size, detail in results:
        counts.setdefault(verdict, []).append((rel, size, detail))
    for verdict in ORDER:
        items = counts.get(verdict)
        if not items:
            continue
        say("\n  %s -- %d" % (verdict, len(items)))
        # The two that need acting on are printed in full; the rest are counted. A run that
        # prints 75 unchanged rows is a run nobody reads to the end.
        if verdict in (CHANGED, LENGTH, REFUSED, GONE):
            for rel, size, detail in sorted(items):
                say("    %9s  %s%s" % (human(size), rel, "   " + detail if detail else ""))

    total = sum(len(v) for v in counts.values())
    say("\n  %d row(s) asked about, %d accounted for" % (len(rows), total))
    if total != len(rows):
        say("  THE SUMMARY DOES NOT ADD UP -- a verdict is missing from ORDER")
        return 2
    return 1 if counts.get(CHANGED) or counts.get(LENGTH) or counts.get(REFUSED) else 0


if __name__ == "__main__":
    sys.exit(main())
