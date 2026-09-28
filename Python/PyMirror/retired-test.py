#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Can a container that was unpacked and deleted come back? Answered by tests, not by memory.

SIX ARCHIVES IN THIS COLLECTION WERE UNPACKED OUT OF A CONTAINER TAR and the tar was then
removed. The files are all still here, under their own names, in an archive of their own:

    agilent-ftp-2009      <- bitsavers/mirrors/ftp.agilent.com_CDs_20091212.tar
    dec-ftp-2006          <- bitsavers/mirrors/ftp.digital.com_20060831.tar
    hp-alphaserver-2008   <- bitsavers/mirrors/h18002.www1.hp.com_20080527.tar
    hp-labs-2007          <- bitsavers/mirrors/www.hpl.hp.com_20070827.tar
    hp-openvms-2008       <- bitsavers/mirrors/h71000.www7.hp.com_20080527.tar
    next-68k-org          <- fsck-vendors/NeXT/next.68k.org Archive/next.68k.org.tar

WHAT COMING BACK WOULD COST. The NeXT tar alone is 37.86 GB; the five bitsavers ones are a
further 39 GB. A refresh that fetched any of them would look like a perfectly clean run -- it is
exactly what a mirror tool is for -- and the collection would quietly hold both the container and
its contents, twice the bytes and two answers to "what did this archive serve".

THERE ARE TWO MECHANISMS AND THEY ARE NOT THE SAME ONE. That is the whole reason this file
exists:

  * `RETIRED` + `is_retired()`, consulted by `producer()` in mirror.py and by the URL-list tools
    (`ia-item-fetch.py`, `http-subset-fetch.py`, `sfv-verify.py`). This is what protects
    `fsck-vendors`, which is fetched from a list of URLs.
  * `--exclude` lines in `RSYNC[...]["filter"]`. bitsavers is fetched by rsync, which never asks
    Python anything. `RETIRED["bitsavers"]` is a RECORD of the decision; the exclude is what
    enforces it.

So the same decision is written twice, in two syntaxes, in two places. A tar retired but not
excluded comes straight back on the next rsync, with no error anywhere -- and the record would
say it had been removed on purpose. That is the drift these tests exist to refuse, and it is the
same shape as the two `LIBRARIES` tuples in contract-mutations.py and the hand-written backup
list beside its mutation table.

NOTHING HERE READS THE MIRROR except the last check, which says so and skips when the collection
is not mounted. Everything else is about the code and runs anywhere, CI included.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
mirror = common.load_peer("mirror.py", "_mirror_for_retired")

# The six, written out. Derived lists are better where a list can grow on its own; this one is a
# record of decisions somebody took, and a decision that quietly disappears from a derived list
# is the thing being guarded against.
UNPACKED = (
    ("bitsavers", "mirrors/ftp.agilent.com_CDs_20091212.tar", "agilent-ftp-2009"),
    ("bitsavers", "mirrors/ftp.digital.com_20060831.tar", "dec-ftp-2006"),
    ("bitsavers", "mirrors/h18002.www1.hp.com_20080527.tar", "hp-alphaserver-2008"),
    ("bitsavers", "mirrors/www.hpl.hp.com_20070827.tar", "hp-labs-2007"),
    ("bitsavers", "mirrors/h71000.www7.hp.com_20080527.tar", "hp-openvms-2008"),
    ("fsck-vendors", "NeXT/next.68k.org Archive/next.68k.org.tar", "next-68k-org"),
)

ROOT = common.MIRROR_ROOT

# When a decision was taken. Not a judgement about the prose around it.
DATE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}")


def excludes_of(archive):
    """-> the paths an rsync archive refuses, as RETIRED spells them: no leading slash."""
    spec = mirror.RSYNC.get(archive) or {}
    return {f[len("--exclude=/"):] for f in spec.get("filter", ())
            if f.startswith("--exclude=/")}


def check(label, ok, detail=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", label, ("  -- " + detail) if detail else ""))
    return 0 if ok else 1


def main():
    bad = 0
    print()

    # 1 -------------------------------------------------------------------------------------
    for archive, path, into in UNPACKED:
        why = mirror.is_retired(archive, path)
        bad += check("%s is retired in %s" % (os.path.basename(path)[:44], archive),
                     why is not None, "unpacked into %s" % into)

    # 2 -------------------------------------------------------------------------------------
    # The one that can go wrong silently. rsync never asks Python anything.
    for archive in sorted(mirror.RSYNC):
        retired = {p for p, _w in mirror.RETIRED.get(archive, ())}
        missing = sorted(retired - excludes_of(archive))
        bad += check("every RETIRED path in %s is also an rsync --exclude" % archive,
                     not missing, ", ".join(missing[:3]))

    # 3 -------------------------------------------------------------------------------------
    # A reason, not a label. A silenced path nobody can justify is one nobody can ever un-silence.
    #
    # WHAT A TEST CAN AND CANNOT JUDGE HERE, learnt by getting it wrong twice in a row. The
    # first version demanded 60 characters and failed `2.47 GB -> agilent-ftp-2009, 2026-09-07`,
    # a complete record in 39. The second demanded a literal `->` and failed "Unpacked into the
    # `next-68k-org` archive on 2026-09-07 -- 234 760 files, verified three ways", which says
    # where it went in better English than the arrow does.
    #
    # Whether prose is a good reason is not a thing a test decides. What it CAN decide is that a
    # decision is dated: 34 of 34 carry one, and an undated deletion is one nobody can place
    # against anything else in the record.
    for archive, rows in sorted(mirror.RETIRED.items()):
        undated = [p for p, why in rows if not DATE.search(why or "")]
        bad += check("every RETIRED entry in %s is dated" % archive,
                     not undated, ", ".join(undated[:3]))

    # 4 -------------------------------------------------------------------------------------
    # A guard that is never consulted reads exactly like a tree with nothing to guard.
    with io.open(os.path.join(HERE, "mirror.py"), encoding="utf-8") as fh:
        src = fh.read()
    bad += check("producer() consults is_retired() on the fetch path",
                 "is_retired(name_for_retired," in src)
    bad += check("and it is given the archive's own name",
                 "name_for_retired=name," in src)

    # 5 -------------------------------------------------------------------------------------
    # The only check that reads the collection: it catches a SEVENTH archive being unpacked and
    # its container not retired, which no amount of writing in this file can anticipate.
    if not os.path.isdir(ROOT):
        print("  skip the mirror is not mounted at %s -- checks 1-4 do not need it" % ROOT)
    else:
        known = {(a, p) for a, p, _i in UNPACKED}
        found, unlisted = 0, []
        for archive, apath in common.iter_archives(ROOT):
            prov = os.path.join(apath, "PROVENANCE.md")
            if not os.path.exists(common.long_path(prov)):
                continue
            with io.open(common.long_path(prov), encoding="utf-8", errors="replace") as fh:
                text = fh.read(4000)
            if "npacked" not in text:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line.lower().endswith(".tar"):
                    continue
                rel = common.relative_to(ROOT, line)
                if not rel or "/" not in rel:
                    continue
                container, inside = rel.split("/", 1)
                found += 1
                if (container, inside) not in known:
                    unlisted.append("%s <- %s/%s" % (archive, container, inside))
        bad += check("every unpacked archive's container is listed above",
                     not unlisted, ", ".join(unlisted[:2]))
        bad += check("and the list is not stale", found >= len(UNPACKED),
                     "found %d container references, listed %d" % (found, len(UNPACKED)))

    print()
    print("  %d check(s) failed" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
