#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Find duplicates across any number of trees, and files that lie about what they are.

REPORTS ONLY. This script deletes nothing and changes nothing. It prints candidates and a human
decides -- deliberately, because the one thing worse than a redundant copy is a mirror with a
hole in it.

DUPLICATES ARE READ OUT OF MANIFESTS, NOT OFF THE DISK
    Give it the checksum files that `mirror.py --index` and `checksums.py` have already written,
    and it compares whole collections without reading a byte of content. Two consequences worth
    stating plainly:

      * It is exact. The previous version walked the trees and matched on name and size, because
        hashing hundreds of gigabytes to find a handful of matches was not worth the disk pass.
        That found 5 duplicates where the manifests find 163: anything renamed on its way in was
        invisible to it, and a same-name-same-size pair that differed was a false positive.
      * It is cheap enough for terabytes. The work is proportional to the NUMBER of files, not to
        their size.

    The price is that a manifest is a cache -- it was true when it was written. Refresh first if
    it matters, and never delete on this report alone. dedupe-docs.py re-reads both sides in full
    before it removes anything, and that separation is the point.

THE RULE THIS ENCODES
    A mirror is a faithful copy of someone else's tree. Its internal redundancy belongs to the
    source, not to us. oss4aix serves 97 % of `RPMS/` again under `everything/` and 99 % of
    `latest/` and `compatible/` -- of 208 GB only about 85 GB is distinct. Removing that would
    save 100 GB and destroy what the mirror is for: answering *what did this archive serve, and
    under which path*, byte for byte.

    So duplicates are classified by WHERE they sit, and only one class is ever a candidate:

      PROTECTED   every copy lives in a protected tree -- the same one, or two different ones.
                  Never a deletion candidate, not even across mirrors: if two archives both
                  carry a file, both are entitled to their copy.
      CANDIDATE   at least one copy in a protected tree, at least one outside it. The outside
                  copy is the redundant one; the protected tree is the authoritative location.
      LOOSE       no copy in any protected tree. An ordinary duplicate between working
                  directories -- a judgement call, not a rule.

    A tree is protected when its manifest is a mirror's (`.mirror-index.csv`). That needs no
    configuration and cannot be forgotten on the day it matters. `--protect` and `--unprotect`
    override it by label.

USAGE
    python audit.py --index /srv/mirror --index /srv/collection/collection-index.csv
    python audit.py --index ... --csv report.csv        the full list, not just the head
    python audit.py --ruins --root /srv/collection      magic bytes vs extension (reads a little)
    python audit.py --empty --root /srv/collection      files that are ALL zeros (reads a little)
    python audit.py --holes --root /srv/collection      whole-megabyte runs of zeros (reads all)

    EXIT CODE. Non-zero when any of the three reported something. The counts were computed and
    thrown away until 2026-09-24: a run that listed 81 certain losses exited 0, which made every
    one of these checks unusable as a gate. What --ruins skips as a source convention and what
    --empty lists without judging are NOT findings and do not count.

    THE THREE ASK DIFFERENT QUESTIONS and none of them covers another. --ruins opens only files
    whose extension has a known signature, so it cannot see a zero-filled .txt. --holes reads
    every file in full and starts at 16 MB, so a 33 KB file of nothing is beneath it twice over.
    --empty was added on 2026-09-23 after two 33 KB ROM images in sun3arc turned out to be
    entirely zero -- found by --ruins, and only because a file of nothing also fails .gz magic.

    `--index` takes a manifest file or a directory. A directory is searched at its own level and
    one level down, so pointing it at a mirror root loads every archive in it at once -- which is
    the common case, and naming twelve paths by hand is how one of them silently gets left out.
"""

import argparse
import collections
import csv
import io
import os
import re
import sys
import urllib.parse

from common import (BOOKKEEPING_FILES, CHECKED_EXT, EMPTY_SHA256, INDEX_FILE, MAGIC,
                    NEVER_CONTENT_DIRS, ZERO_PROBE, file_extension, find_manifests, human,
                    is_all_zero, is_partial, long_path, looks_like_a_page, magic_mismatch,
                    declared_length, parse_listing, plural, read_manifest,
                    relative_to, say, sha256_file, size_agrees, split_archive)

# THE COST THESE CHECKS WERE WRITTEN FOR, kept here because it is this collection's, not the
# library's. On 2026-08-23 one outage left 11 half-finished downloads; fifteen saved HTTP error
# pages sat under .pdf names, indistinguishable from real documents in any listing or file count;
# and one autoindex page saved where a directory belonged blocked 49 files and 7.6 GB behind
# `rs6000/files` -- with no error, because a filesystem simply cannot hold a file and a directory
# under one name. The rules themselves are in common.py and are tested there.
# --------------------------------------------------------------------------------- manifests


def label_for(manifest, used):
    """A short, unique name for the tree a manifest describes."""
    d = os.path.dirname(os.path.abspath(manifest))
    label = os.path.basename(d) or d
    if label in used:
        parent = os.path.basename(os.path.dirname(d))
        label = "%s/%s" % (parent, label) if parent else d
    base, n = label, 2
    while label in used:
        label, n = "%s#%d" % (base, n), n + 1
    return label


# -------------------------------------------------------------------------------- duplicates


def load_sources(targets, protect, unprotect):
    """-> [(label, manifest, protected)], resolving directories and applying the overrides."""
    sources, used = [], set()
    for t in targets:
        found = find_manifests(t)
        if not found:
            say("  NO MANIFEST under %s -- skipped" % t)
            continue
        for manifest in found:
            label = label_for(manifest, used)
            used.add(label)
            # A MIRROR'S OWN INDEX IS PROTECTED BY DEFAULT, and that is this tool's policy rather
            # than a property of the manifest -- which is why find_manifests does not decide it.
            prot = os.path.basename(manifest) == INDEX_FILE
            if label in protect:
                prot = True
            if label in unprotect:
                prot = False
            sources.append((label, manifest, prot))
    return sources


def audit_duplicates(targets, protect, unprotect, csv_out, head, only_ext=(), min_bytes=0):
    """`only_ext` and `min_bytes` narrow WHICH FILES ARE CONSIDERED, not which are reported.

    A full run over this collection compares 750 000 mirror files against 4 300 collection files
    and prints thousands of groups, most of them small text and HTML that duplicates for good
    reasons. The question that actually gets asked is narrower -- "is any of my 83 GB of disc
    images already in a mirror" -- and it drowns in the rest.

    Filtering the INPUT rather than the output matters: a group is only interesting if every copy
    of it survives the filter, and filtering afterwards would show one .iso beside a .txt and call
    them a pair.  [2026-09-05]
    """
    sources = load_sources(targets, protect, unprotect)
    if not sources:
        say("No manifests found. --index takes a file or a directory.")
        return 1

    say("=== Sources ===")
    by_hash = collections.defaultdict(list)      # sha -> [(label, rel, size, protected)]
    total = 0
    for label, manifest, prot in sources:
        try:
            rows = read_manifest(manifest)
        except (OSError, csv.Error) as exc:
            say("  %-26s UNREADABLE (%s)" % (label, exc))
            continue
        kept = 0
        for rel, size, sha in rows:
            if not sha or sha == EMPTY_SHA256:
                continue
            if only_ext and file_extension(rel) not in only_ext:
                continue
            if size < min_bytes:
                continue
            by_hash[sha].append((label, rel, size, prot))
            kept += 1
        total += kept
        rows = range(kept)   # the count printed below is what was KEPT, not what was read
        say("  %-26s %8d files  %-11s %s"
              % (label, len(rows), "protected" if prot else "", manifest))
    say("  %d files from %d manifests\n" % (total, len(sources)))

    groups = {"CANDIDATE": [], "LOOSE": [], "PROTECTED": []}
    for sha, copies in by_hash.items():
        if len(copies) < 2:
            continue
        prot = any(c[3] for c in copies)
        unprot = any(not c[3] for c in copies)
        groups["CANDIDATE" if prot and unprot else "PROTECTED" if prot else "LOOSE"].append(
            (sha, copies))

    def biggest(copies):
        return max((c[2] or 0) for c in copies)

    def waste(entries):
        """Bytes held by every copy after the first. Unknown sizes count as zero."""
        return sum(biggest(copies) * (len(copies) - 1) for _, copies in entries)

    say("=== CANDIDATE: in a protected tree AND outside one ===")
    cand = sorted(groups["CANDIDATE"], key=lambda g: -biggest(g[1]))
    outer_bytes = sum(sum((c[2] or 0) for c in copies if not c[3]) for _, copies in cand)
    for sha, copies in cand[:head]:
        say("  %10s  %s" % (human(biggest(copies)), sha[:12]))
        for label, rel, _s, prot in sorted(copies, key=lambda c: (not c[3], c[0], c[1])):
            say("      %-11s %-24s %s" % ("protected" if prot else "outside", label, rel))
    if len(cand) > head:
        say("  ... and %s not shown" % plural(len(cand) - head, "group"))
    say("  %s; the copies outside hold %s and are expendable,"
          " the protected ones are not\n" % (plural(len(cand), "group"), human(outer_bytes)))

    say("=== LOOSE: outside every protected tree -- a judgement call ===")
    loose = sorted(groups["LOOSE"], key=lambda g: -waste([g]))
    for sha, copies in loose[:head]:
        say("  %10s  x%d  %s" % (human(biggest(copies)), len(copies), sha[:12]))
        for label, rel, _s, _p in sorted(copies):
            say("      %-24s %s" % (label, rel))
    if len(loose) > head:
        say("  ... and %s not shown" % plural(len(loose) - head, "group"))
    say("  %s, %s held twice\n" % (plural(len(loose), "group"), human(waste(loose))))

    say("=== PROTECTED: duplicates within or between protected trees ===")
    say("  %s, %s. Not deletable -- which is the purpose, not a limitation:"
          % (plural(len(groups["PROTECTED"]), "group"), human(waste(groups["PROTECTED"]))))
    say("  a mirror is a copy of somebody else's tree, and its internal redundancy belongs")
    say("  to the source. Two identical files at two paths are two answers.\n")

    if csv_out:
        with io.open(csv_out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(("class", "sha256", "size", "source", "protected", "path"))
            for cls in ("CANDIDATE", "LOOSE", "PROTECTED"):
                for sha, copies in groups[cls]:
                    for label, rel, size, prot in sorted(copies):
                        w.writerow((cls, sha, "" if size is None else size,
                                    label, "yes" if prot else "no", rel))
        say("  Full report: %s" % csv_out)
    return 0


# ------------------------------------------------------------------------ content-level checks


# How often a long walk says something inside one archive. 25 000 is about a line every few
# seconds on this collection's slowest volume, and ps-2.kev009.com alone holds 94 899 files --
# four lines rather than one, which is the difference between "it is working" and "it is stuck".
PROGRESS_EVERY = 25_000


def walk(root, report=None):
    """Every file under `root` as (size, path), announcing progress if asked.

    WHY A CHECK THAT SAYS NOTHING GETS KILLED. These checks hold everything until the last file
    has been read -- they have to, because a file's group is not known until it has been compared
    against the records -- so a run over the collection printed **zero bytes for 58 minutes** and
    there was no way to tell it from a hung one. Twice on 2026-09-24 it was killed at that point
    by the person who started it, and C4 (`--holes`, 3.8 TB read in full) has never been run at
    all, which is very likely the same reason.

    IT REPORTS ARCHIVES, NOT FILES. One line as each archive is reached and one every
    PROGRESS_EVERY files inside it: enough to see that something is happening and which part of
    1.76 M files it is in, without turning the output into a second problem.

    THE CALLBACK IS NAMED `report`, which is the library's contract and is enforced by a test,
    and it defaults to None so nothing prints unless a caller asks.
    """
    seen, n = None, 0
    for dirpath, dirnames, names in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in NEVER_CONTENT_DIRS]
        for name in names:
            p = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(long_path(p))
            except OSError:
                continue
            if report is not None:
                rel = relative_to(root, p) or ""
                archive, tail = split_archive(rel)
                top = archive if tail else "(root)"   # a loose file belongs to no archive
                if top != seen:
                    if seen is not None:
                        report("  ... %-28s %s" % (seen, plural(n, "file")))
                    seen, n = top, 0
                n += 1
                if n % PROGRESS_EVERY == 0:
                    report("  ... %-28s %s so far" % (top, plural(n, "file")))
            yield size, p
    if report is not None and seen is not None:
        report("  ... %-28s %s" % (seen, plural(n, "file")))


# The one reason in --ruins' output that is not magic_mismatch's own words. It is stated here
# rather than inline because the column that holds it is sized from the reasons, and a literal
# buried in a say() is a literal the sizing cannot see.
DIRECTORY_PAGE = "DIRECTORY PAGE saved as a file"

# Files this collection holds as a WEB PAGE under a binary name, because that is what the source
# serves under that name. Every one arrived with status 200 and a matching Content-Length, which
# is why no counter ever noticed: an error page is a perfectly ordinary HTTP success.
#
# ALL TWENTY-ONE WERE ASKED AGAIN, 2026-09-24, and not one of them can be repaired:
#
#     8   the server returned BYTE-IDENTICAL what we already hold. Their titles are worth
#         reading -- `Yahoo! GeoCities`, `Internet Archive Wayback Machine`, `IBM eServer -
#         UNIX Servers features and benefits`, three plain 404s. Some of these pages have been
#         standing in for their files for well over a decade.
#     4   dl.power-devops.com is alive, answers 200, and hands back the same Bull SAS landing
#         page. THE STATUS CODE WOULD HAVE CALLED ALL FOUR AVAILABLE; only the bytes disagree,
#         and a re-fetch would have replaced a broken file with the same broken file.
#     9   bullfreeware's two origin hosts do not answer at all. That tree was fetched via
#         web.archive.org and its own marker said so before anything was requested.
#
# SO OUR COPIES ARE FAITHFUL AND THE DAMAGE IS THE SOURCES'. They are recorded rather than
# deleted, for the same reason the zero-filled files are: a mirror answers "what did this archive
# serve, and under which path", and removing a truthful copy of a server's mistake makes that
# answer less true.
#
# RECORDED BY PATH AND SIZE, EXACTLY, so a NEW page appearing under a binary name is still a
# finding -- and so is any of these changing size, which would mean the source finally moved.
# Each row carries the sentence that justifies it; a silenced path with no reason is a path
# nobody can ever safely un-silence.
PAGE_AT_SOURCE = (
    ("ardent-tool/comms/rcm204a.tar.z",
     2376, "the source still serves an Internet Archive Wayback page here, byte for byte"),
    ("bull-srpms/openldap/openldap-2.4.35-1.src.rpm",
     7661, "the source answers 200 with the same Bull SAS landing page"),
    ("bull-srpms/protobuf/protobuf-2.4.1-1.src.rpm",
     7660, "the source answers 200 with the same Bull SAS landing page"),
    ("bull-srpms/redis/redis-2.6.16-1.src.rpm",
     7655, "the source answers 200 with the same Bull SAS landing page"),
    ("bull-srpms/snappy/snappy-1.1.0-1.src.rpm",
     7656, "the source answers 200 with the same Bull SAS landing page"),
    ("bullfreeware/bullfreeware.com/download/bin/1375/_openssl-1.0.0d-2.aix5.3.ppc.rpm",
     2831, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2229/gcc-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2230/gcc-c++-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2232/gcc-gfortran-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2233/libgcc-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2234/libgomp-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2235/libstdc++-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/2236/libstdc++-devel-4.8.4-1.aix7.1.ppc.rpm",
     2753, "the source host no longer answers; this tree came via web.archive.org"),
    ("bullfreeware/bullfreeware.com/download/bin/3660/python-tornado-4.4.2-1.aix6.1.ppc.rpm",
     78, "the source host no longer answers; this tree came via web.archive.org"),
    ("mpoli-bbs/hardware/DISPLAY/S3/964N3S3.ZIP",
     177, "the source still serves a 404 page here, byte for byte"),
    ("ps-2.kev009.com/basil.holloway/ALL PDF/SCSI-IG.pdf",
     45740, "the source still serves a Document Library page here, byte for byte"),
    ("ps-2.kev009.com/basil.holloway/ALL PDF/cs4231a.pdf",
     7461, "the source still serves a Yahoo! GeoCities page here, byte for byte"),
    ("ps-2.kev009.com/basil.holloway/ALL PDF/sa380544.pdf",
     51919, "the source still serves an IBM eServer marketing page here, byte for byte"),
    ("ps-2.kev009.com/basil.holloway/ALL PDF/sa380545.pdf",
     50603, "the source still serves an IBM eServer marketing page here, byte for byte"),
    ("ps-2.kev009.com/pccbbs/pc_servers/01r0763.rpm",
     233, "the source still serves a 404 page here, byte for byte"),
    ("transputer-classiccmp/documentation/sundance/pcil3_1.pdf",
     305, "the source still serves a 404 page here, byte for byte"),
)


def page_at_source(rel):
    """Is a web page what the SOURCE serves under this name? -> the recorded size, or None.

    Same right-anchored path match as zero_at_source(), for the same reason: --root may be the
    whole collection or one archive inside it, and a plain equality quietly stops matching the
    day somebody narrows the run.
    """
    rel = rel.replace(os.sep, "/")
    for known, size, _why in PAGE_AT_SOURCE:
        if known == rel or known.endswith("/" + rel):
            return size
    return None


def check_ruins(root, report=None):
    """A file that lies about what it is. Cheap: a few bytes read per file.

    Two kinds. A wrong magic number is the loud one and was worth fifteen findings on 2026-08-22:
    saved HTTP error pages under .pdf names, indistinguishable from real documents in any listing
    or file count. The quiet one is an autoindex page saved under a directory's name -- it blocks
    everything below that path and produces no error until something tries to write there.
    """
    say("=== Ruins: the contents contradict the extension ===")
    found = skipped = 0
    rows, at_source_pages = [], []
    for size, p in walk(root, report):
        name = os.path.basename(p)
        if is_partial(name):
            continue
        # A PATH THE SOURCE USES FOR SOMETHING ELSE. Counted and named rather than silently
        # dropped: see SOURCE_CONVENTIONS for what each one is and what it was worth.
        rel_early = relative_to(root, p)
        if rel_early is not None and source_convention(rel_early):
            skipped += 1
            continue
        # file_extension, not splitext: splitext answers "." for a name ending in a dot,
        # which is TRUTHY, so `TALK.` was never treated as an extension-less candidate.
        ext = file_extension(p)
        # A directory name rarely carries an extension, so only the extension-less candidates can
        # be an index page written where a directory belongs -- and a real page is small.
        if ext:
            if ext not in CHECKED_EXT:
                continue
        elif size >= 300_000:
            continue
        try:
            with open(long_path(p), "rb") as fh:
                head = fh.read(4096)
        except OSError:
            continue
        why = magic_mismatch(name, head)
        if not why:
            continue
        # A PAGE THE SOURCE ITSELF SERVES UNDER THIS NAME. Not a finding, because nothing can be
        # done about it: all 21 were asked again on 2026-09-24 and every one came back the same,
        # gone, or serving the identical page. Checked on SIZE as well as path, so the day a
        # source finally puts the real file back this stops matching and the row shows up again.
        rel_now = relative_to(root, p)
        if rel_now is not None and page_at_source(rel_now) == size:
            at_source_pages.append((size, rel_now))
            continue
        found += 1
        # WHICH directory the page describes is the part worth printing: it names the subtree
        # that cannot be written while this file sits there.
        if "directory listing" in why:
            m = re.search(rb"Index of (/[^<]*)", head)
            rows.append((DIRECTORY_PAGE, size, relative_to(root, p),
                         m.group(1).decode("utf-8", "replace").strip() if m else "?"))
        else:
            rows.append((why, size, relative_to(root, p), ""))

    # COLLECTED FIRST AND PRINTED AFTERWARDS, because the reason column has to be as wide as the
    # widest reason and nothing knows that until the last file has been read. It was a literal
    # 34, and TEN of the nineteen reasons magic_mismatch can produce are longer than that -- so
    # on more than half of them the size ran into the reason with no space between, and a parser
    # written against this output failed on exactly those lines. Any fixed number is correct
    # only until the next extension is added to MAGIC.
    width = max([len(r[0]) for r in rows] + [len(DIRECTORY_PAGE)])
    for why, size, rel, extra in rows:
        say("  %-*s %9d B  %s%s"
              % (width, why, size, rel, "   = index of %s" % extra if extra else ""))
    if at_source_pages:
        # PRINTED, NOT SWALLOWED. A record nobody sees is a record nobody can challenge when a
        # source changes, and these are the rows most likely to change: a dead host can come
        # back, and dl.power-devops.com is alive today and simply wrong.
        say("\n  and %s the SOURCE ITSELF serves as a web page under that name -- our copy is"
              % plural(len(at_source_pages), "file"))
        say("  faithful and a re-fetch cannot improve it (all asked again 2026-09-24):")
        for size, rel in sorted(at_source_pages, reverse=True):
            say("    %9d B  %s" % (size, rel))
        say("")
    say("  %d found%s\n"
          % (found, ", %s skipped as a source convention" % plural(skipped, "file")
             if skipped else ""))
    return found


# Paths where the SOURCE keeps something else under a name, and its own layout says so.
#
# EACH ONE IS A DECISION TO STOP LOOKING, so each carries the sentence that justifies it. A list
# of silenced paths with no reasons is a list nobody can ever safely shorten again.
SOURCE_CONVENTIONS = (
    ("oss4aix.org/rpmdb/db/",
     "oss4aix publishes a dependency database here: one short text file per package, named "
     "after that package's .rpm and holding `prov`/`req` lines. 23 190 of the 26 313 findings "
     "in the first full run were these -- 88 % -- and none of them is damage. [2026-09-23]"),
    ("somuchstuff-pdp8/trunk/pdp8/shadb/",
     "A SHADOW DATABASE, and the source documents it in its own Meta.txt: 'the meta data "
     "archive mimics the true name directory structure to quickly look up the meta data', and "
     "it keeps entries for files 'which do not (yet) exist'. So `src/dec/.../x.pdf` is a "
     "106-254 byte record -- .name, .description, .partnumber, .group -- and never a document. "
     "The tree root holds 22 250 more files named by sha256, each one line naming the path that "
     "hashes to it. 1 841 findings, none of them damage, and no PDF is missing because this "
     "layer was never meant to hold one. [2026-09-24]"),
    ("ibiblio-historic-linux/distributions/*/*/live/var/lib/rpm/",
     "The RPM DATABASE of an installed Red Hat tree, mirrored as it stood. `packages.rpm`, "
     "`nameindex.rpm`, `providesindex.rpm`, `requiredby.rpm` and the rest are Berkeley DB files "
     "(magic 0x00061561), not packages -- the same shape as oss4aix's rpmdb one directory up the "
     "stack. 37 findings across seven distributions, redhat-4.0 to 5.1. [2026-09-24]"),
)


def source_convention(rel):
    """Is this path one the source uses for something other than what its name suggests?

    ANCHORED AT THE ARCHIVE, not matched anywhere in the path. `rpmdb/db/` under some other
    archive is a different thing, and a rule that silenced it there would hide a real finding
    somewhere nobody was looking.

    `*` STANDS FOR ONE PATH SEGMENT and never for a separator, so a pattern still names the
    archive it applies to. It was added for a convention that repeats across seven sibling
    directories -- `distributions/redhat-4.0/`, `-4.1`, `-4.2`, `-5.0`, `-5.1` and two more --
    where seven near-identical entries would have been seven chances to mistype one and no
    clearer for the reader.
    """
    rel = rel.replace(os.sep, "/")
    for pattern, _why in SOURCE_CONVENTIONS:
        if "*" not in pattern:
            if rel.startswith(pattern):
                return True
        elif re.match("".join("[^/]*" if part == "*" else re.escape(part)
                              for part in re.split(r"(\*)", pattern)), rel):
            return True
    return False


# Files this collection holds as all zeros BECAUSE THE SOURCE SERVES THEM THAT WAY.
#
# MEASURED, NOT ASSUMED. [2026-09-24] Each of these was requested again from its live host: all
# twenty answered HTTP 200 with exactly the byte count we hold, and every byte of it zero. Our
# copy is faithful. Nothing was lost in transit, nothing is missing, and a re-fetch cannot
# improve any of them -- the emptiness is what the server has.
#
# THE FIRST DIAGNOSIS WAS WRONG AND THIS IS WHAT CORRECTED IT. The matching sizes looked like a
# transfer that had kept the length and lost the content, and the obvious next step was to fetch
# them again. The first re-fetch returned 276 906 fresh bytes of nothing, which is the only
# reason the other nineteen were probed rather than repaired.
#
# THEY ARE NOT DELETED. A mirror answers "what did this archive serve, and under which path",
# byte for byte; removing a faithful copy of an empty file would make that answer less true, not
# more. They are recorded here instead, EXACTLY -- by path, not by directory -- so that a new
# empty file appearing beside one of them is still a finding.
ZERO_AT_SOURCE = (
    ("oldskool/drivers/HardwareDoc/Harddisks/DawiSCSI93.pdf", 276906),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/aixwinlc.htm", 48348),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/db2univr.htm", 1945),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/dtharkop.htm", 2311),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/dynatexu.htm", 2894),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/hacmpapp.htm", 10934),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/hageomet.htm", 1771),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/mmediada.htm", 2429),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/opgl32ad.htm", 5765),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/pexgphii.htm", 6527),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/soft5082.htm", 9558),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/sysmgtwe.htm", 2647),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixins/inslppkg/vtypedic.htm", 2745),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixkybd/kybdtech/chapter1.htm", 2182),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixkybd/kybdtech/chinese2.htm", 1753),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixkybd/kybdtech/french4.htm", 155310),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixkybd/kybdtech/serbian2.htm", 126462),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixkybd/kybdtech/united.htm", 156032),
    ("sun3arc/ROMs/3_60/sun3_60_v1.5.gz", 33615),
    ("sun3arc/ROMs/3_60/sun3_60_v1.6.gz", 33689),
    # FOUR MORE, ADDED 2026-09-24 THE DAY MAGIC LEARNED WHAT AN IMAGE IS (A3). Until then a
    # zero-filled JPEG sat under "no statement possible", because cannot_be_empty() asks MAGIC
    # and MAGIC knew no image format. These four were the first findings the change produced.
    #
    # THEY ARE TWO FILES, HELD TWICE. `infania-tl2` and `ps-2.kev009.com` are independent mirrors
    # of the same IBM AIX documentation set, and both hold exactly these two figures as zeros, at
    # exactly these lengths. Two captures taken by different people at different times agreeing
    # byte for byte is a strong statement about the source on its own -- and then the source was
    # asked: ps-2 answers HTTP 200 with 10 655 and 65 664 bytes, every one of them zero.
    ("infania-tl2/techlib/manuals/adoclib/aixlnk25/x25usrgd/figures/a1190cf8.jpg", 10655),
    ("infania-tl2/techlib/manuals/adoclib/aixprggd/aixwnpgd/figures/aixwn59.jpg", 65664),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixlnk25/x25usrgd/figures/a1190cf8.jpg", 10655),
    ("ps-2.kev009.com/tl/techlib/manuals/adoclib/aixprggd/aixwnpgd/figures/aixwn59.jpg", 65664),
    # FIFTY-ONE MORE, ADDED 2026-09-24 (C3, group 3): THE WHOLE QNX 6 PACKAGE REPOSITORY.
    #
    # 23 `.qpk` and 28 `.qpm` in one directory of `fsck-vendors`, 1 350 597 bytes of nothing,
    # from 1 189 B to 462 KB each. The 23 `.qpk` had become CERTAIN LOSSES earlier the same day,
    # when `.qpk` was recognised as gzip and entered MAGIC. That was a correct change and it
    # produced a wrong verdict, which is exactly why a finding is not finished until the source
    # has been asked.
    #
    # ALL FIFTY-ONE WERE ASKED, not a sample. Three were checked by hand first and all three came
    # back as zeros; three is not a record when 51 files are about to stop being reported, so
    # fsck.technology was asked about every one. It answered HTTP 200 for all 51, at exactly the
    # length held here, every byte zero: 51 the same, 0 different, 0 unreachable. The packages
    # were uploaded empty; nothing was lost in transit and there is nothing here to re-fetch.
    #
    # WHY BOTH HALVES OF EACH PACKAGE. 23 packages have an empty `.qpk` AND an empty `.qpm`; 5
    # more have only an empty manifest. Recording the archives alone would leave the manifests to
    # resurface as findings the day `.qpm` gets a signature -- the mistake this table has already
    # made once.
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/firebird-0.7-public.qpm", 46347),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/gaim-0.59.8-x86-public.qpm", 6583),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-1.2-public.qpk", 31578),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-1.2-public.qpm", 5712),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-1.2-x86-public.qpk", 29933),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-1.2-x86-public.qpm", 4898),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-dev-1.2-public.qpk", 4205),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-dev-1.2-public.qpm", 5399),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-dev_x86-1.2-public.qpk", 17764),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-dev_x86-1.2-public.qpm", 5174),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-slib-1.2-public.qpk", 1438),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libbinio-slib-1.2-public.qpm", 4880),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libiconv-1.7-bld2-public.qpk", 6867),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libiconv-1.7-bld2-public.qpm", 5607),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libmad-0.15.0b-x86-public.qpk", 65056),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libmad-0.15.0b-x86-public.qpm", 4792),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libmad-dev-0.15.0b-public.qpk", 8862),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libmad-dev-0.15.0b-public.qpm", 5143),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libmad-slib-0.15.0b-public.qpk", 1434),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libmad-slib-0.15.0b-public.qpm", 4783),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-3.4-public.qpk", 43220),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-3.4-public.qpm", 3450),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-3.4-x86-public.qpk", 130162),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-3.4-x86-public.qpm", 3726),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-dev-3.4-public.qpk", 11280),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-dev-3.4-public.qpm", 3994),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-dev_x86-3.4-public.qpk", 473408),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-dev_x86-3.4-public.qpm", 4232),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-slib-3.4-public.qpk", 1216),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/libtiff-slib-3.4-public.qpm", 3561),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/lmarbles-1.0.6-public.qpm", 11222),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/lmarbles-1.0.6-x86-public.qpk", 33242),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/lmarbles-1.0.6-x86-public.qpm", 4624),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/lopan-0.9-armle-JF.qpk", 11120),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/lopan-0.9-armle-JF.qpm", 4503),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/snes9x-1.39-x86-JF.qpk", 226103),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/snes9x-1.39-x86-JF.qpm", 4902),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/spin-1.10-bld2-public.qpk", 1482),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/spin-1.10-bld2-public.qpm", 5063),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/spin-1.10-bld2-x86-public.qpk", 47197),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/spin-1.10-bld2-x86-public.qpm", 4279),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/sqlite-2.7.3-public.qpk", 1189),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/sqlite-2.7.3-public.qpm", 4254),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/tin-1.4.6-x86-public.qpm", 4174),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/tspc-0.9.6-public.qpm", 5686),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/tspc-0.9.6-x86-public.qpk", 18692),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/tspc-0.9.6-x86-public.qpm", 4365),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/unrar-3.23-public.qpk", 2547),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/unrar-3.23-public.qpm", 4524),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/uw-imap-2002b-public.qpk", 1817),
    ("fsck-vendors/QNX/QNX 6/QNX6/Repository/repository621a/uw-imap-2002b-public.qpm", 4908),
)


# Files this collection holds as all zeros BECAUSE THE CAPTURE THEY CAME OUT OF ALREADY HELD
# THEM THAT WAY. A SECOND TABLE, AND THE REASON IT IS NOT THE ONE ABOVE IS THE EVIDENCE.
#
# ZERO_AT_SOURCE means "we asked the live host and it served zeros". Not one of these was asked,
# because there is nothing left to ask: `h18002.www1.hp.com` does not resolve, and the tar this
# archive was unpacked from is no longer in the collection either. Putting them in that table
# would have made its opening sentence false for three quarters of its entries.
#
# WHAT WAS CHECKED INSTEAD, and it is first-hand rather than inherited [2026-09-24]. bitsavers
# publishes a `tar tvf` listing beside each of its container tars, and that listing is still
# here: `bitsavers/mirrors/h18002.www1.hp.com_20080527.tar.txt`, 10 201 file members, written by
# whoever packed the archive in 2008. Every one of these 79 files appears in it at EXACTLY the
# length we hold -- 79 of 79, none missing, none differing. So nothing was lost in the unpacking;
# the emptiness is in HP's capture of 27 May 2008.
#
# ALL 79 ARE HERE, NOT THE 61 THAT CURRENTLY COUNT. 57 `.htm` and 4 `.html` are what
# cannot_be_empty() calls certain damage today; the other 18 are .gif, .jpg, .js and .css, which
# it has no opinion about. Recording only the 61 would leave 13 images waiting to become false
# findings the moment MAGIC learns an image format -- which is an open decision, not a hypothesis.
ZERO_IN_CAPTURE = (
    ("hp-alphaserver-2008/alphaserver/archive/comp/mar94.html",
     13878),
    ("hp-alphaserver-2008/alphaserver/docs/cli_reference/WebHelp/8p_backplane_cli_connector.htm",
     3168),
    ("hp-alphaserver-2008/alphaserver/docs/cli_reference/WebHelp/environmentvariablestext.htm",
     6269),
    ("hp-alphaserver-2008/alphaserver/docs/cli_reference/WebHelp/whframes.js",
     2024),
    ("hp-alphaserver-2008/alphaserver/docs/cli_reference/WebHelp/whgdata/whlstt3.htm",
     12014),
    ("hp-alphaserver-2008/alphaserver/docs/cli_reference/WebHelp/whgdata/whnvt30.htm",
     2043),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/common_events/console_connection_(tower)_text.htm",
     7031),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/common_events/es47_tower_ams_console_connection.htm",
     1347),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/common_events/flashinclude01.js",
     2213),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/common_events/install_a_nat_box_text.htm",
     3750),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/connect_the_i_o_cables_(64p).htm",
     1301),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/es47_cabinet_consoles/gs1280_using_an_ams.htm",
     3079),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/es47_cabinet_graphic.htm",
     2498),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/es47_cabinet_placement_text.htm",
     2562),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/system_power-up/ocp_es47_tower_text.htm",
     6364),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/title_page.htm",
     3607),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/whgdata/whlstfl17.htm",
     2160),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/whgdata/whlstfl18.htm",
     2934),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/whgdata/whlsti0.htm",
     6948),
    ("hp-alphaserver-2008/alphaserver/docs/install/WebHelp/whgdata/whnvl31.htm",
     3211),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/8p_backplane_cli_connector.htm",
     2385),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/access_the_cli_from_a_remote_telnet_session.htm",
     2690),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/apw_discovery_phase.htm",
     4856),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/apw_resources_window_graphic.htm",
     2375),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/apwdisplayresourcesgraphic2.htm",
     2373),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/cablelegend.jpg",
     3429),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/flexibility_parent.htm",
     1408),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/how_we_show__clicks__on_screen_shots.htm",
     3222),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/memory_assignment_text.htm",
     5258),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/memory_striping_graphic1.htm",
     2357),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/power_on_hard_partitions.htm",
     2809),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/testtext.htm",
     2752),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/the_general_process.htm",
     3160),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/useful_srm_commands_graphic.htm",
     2374),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/what_are_partitions_parent.htm",
     1465),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/whgdata/whlstt6.htm",
     5962),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/whgdata/whlstt9.htm",
     4825),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/whgdata/whnvt31.htm",
     2020),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/whstart.js",
     9550),
    ("hp-alphaserver-2008/alphaserver/docs/partitions/WebHelp/whstub.js",
     3292),
    ("hp-alphaserver-2008/alphaserver/docs/siteprep/WebHelp/whgdata/whlstf8.htm",
     23529),
    ("hp-alphaserver-2008/alphaserver/docs/siteprep/WebHelp/whgdata/whlstfl19.htm",
     2246),
    ("hp-alphaserver-2008/alphaserver/docs/siteprep/WebHelp/whgdata/whlstfl8.htm",
     2837),
    ("hp-alphaserver-2008/alphaserver/docs/siteprep/WebHelp/whgdata/whnvl31.htm",
     2647),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/AMU_zoom_display_parent.htm",
     1389),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/AMUwhatstheregraphic1.htm",
     2676),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/APW_Display_Resources.htm",
     3483),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/Add_Standalone_Console_graphic.htm",
     2561),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/Connecting_to_hp_AlphaServer_ES47_ES80_GS1280_graphic.htm",
     5144),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/Copyright.htm",
     2851),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/Corporate_LAN_text.htm",
     3415),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/Create_Console_Log_File_parent.htm",
     1416),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/SPM_properties_display_graphic1.htm",
     2498),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/System_Control_Manager_(SCM)_Interface.htm",
     4559),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/apw_the_general_process.htm",
     4776),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/default_ns.css",
     2291),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/set_console_archive_graphic.htm",
     2527),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/whgdata/whlstfl20.htm",
     2762),
    ("hp-alphaserver-2008/alphaserver/docs/sm_tutorial/WebHelp/whgdata/whnvt32.htm",
     2059),
    ("hp-alphaserver-2008/alphaserver/docs/srm_reference/WebHelp/morecommand.htm",
     10536),
    ("hp-alphaserver-2008/alphaserver/docs/srm_reference/WebHelp/showdevice.htm",
     9184),
    ("hp-alphaserver-2008/alphaserver/docs/srm_reference/WebHelp/whgdata/whlstfl16.htm",
     2210),
    ("hp-alphaserver-2008/alphaserver/docs/srm_reference/WebHelp/whgdata/whnvt32.htm",
     2014),
    ("hp-alphaserver-2008/alphaserver/docs/userguide/WebHelp/usersguide.htm",
     4992),
    ("hp-alphaserver-2008/alphaserver/images/a200.jpg",
     3584),
    ("hp-alphaserver-2008/alphaserver/images/a600.jpg",
     4141),
    ("hp-alphaserver-2008/alphaserver/images/celera_logo2.gif",
     1017),
    ("hp-alphaserver-2008/alphaserver/images/deutsche.jpg",
     1267),
    ("hp-alphaserver-2008/alphaserver/images/ds25_100x100.jpg",
     1498),
    ("hp-alphaserver-2008/alphaserver/images/es40_oracle_feb01.gif",
     5481),
    ("hp-alphaserver-2008/alphaserver/images/malta_fp_logo.gif",
     2093),
    ("hp-alphaserver-2008/alphaserver/images/oct_03_perf1.gif",
     4611),
    ("hp-alphaserver-2008/alphaserver/images/oracle_logo2.gif",
     1052),
    ("hp-alphaserver-2008/alphaserver/images/psc1.jpg",
     2164),
    ("hp-alphaserver-2008/alphaserver/images/psc_tag.gif",
     1062),
    ("hp-alphaserver-2008/images/logo.gif",
     2721),
    ("hp-alphaserver-2008/products/servers/management/cim45-description.html",
     16148),
    ("hp-alphaserver-2008/products/servers/management/system-advisories.html",
     146),
    ("hp-alphaserver-2008/products/servers/proliantessentials/index.html",
     137),
)


def zero_in_capture(rel):
    """Was this file already zeros in the archive this tree was unpacked from? -> size or None.

    The same right-anchored path match as zero_at_source(), for the same reason: --root may be
    the collection or one archive inside it, and a plain equality would silently stop matching
    when somebody narrowed the run.
    """
    rel = rel.replace(os.sep, "/")
    for known, size in ZERO_IN_CAPTURE:
        if known == rel or known.endswith("/" + rel):
            return size
    return None


# Files this collection holds as all zeros BECAUSE THE MEDIUM THEY WERE EXTRACTED FROM HOLDS
# THOSE BLOCKS AS ZEROS. A THIRD TABLE, and again the reason is the evidence, not the files.
#
# The first table says "we asked the live host". The second says "the packing list of the archive
# agrees on the length". This one is stronger than both, and it is the only one that can be
# re-checked forever without a network: THE MEDIUM IS HERE. These 43 came off an OS/8 disk image
# that sits in the same directory as the files extracted from it, together with the extractor's
# own index. Three independent statements, and all three agree.
#
# WHAT WAS MEASURED [2026-09-24, C3 group 1]. `dec-s8-lftna-a-ua1.xml` names every file with the
# octal block range it occupies, e.g. `<file name='.../abs.ra' start=01032 end=01032>`. A block is
# 256 twelve-bit words = 384 bytes packed. For all 123 extracted files:
#
#   * every empty file's length is EXACTLY (end - start + 1) x 384 -- 43 of 43, no exception;
#   * the image's own bytes in that block range are zero -- 43 of 43;
#   * and the other way round, all 80 files WITH content have content in the image -- 80 of 80.
#
# Not one mixed case in either direction. The extraction is faithful; the disk was empty there.
#
# THE MAPPING WAS VERIFIED BEFORE IT WAS TRUSTED, because a block table that is off by a constant
# would produce exactly this clean a result. Block 01162 of the image decodes to `/` CR LF with
# the high bit set -- the RALF assembler's comment character, which is what `acos.ra` starts with.
# A second container of the same disk in another format (737 x 516 bytes) corroborates from
# outside the mapping entirely: 62.4 per cent zero bytes against the image's 62.1, longest zero
# run 17 673 B against 17 535 B. The disk is largely blank, and that is a fact about 1970s media.
#
# NONE OF THESE 43 IS REPORTED AS A LOSS TODAY -- 25 `.ra` and 18 `.bn`, and MAGIC knows neither.
# They are recorded anyway, for the same reason the images went into ZERO_AT_SOURCE before they
# were findings: the day `.bn` or `.ra` gets a signature, this table is what stops 43 false
# reports, and by then the evidence will be much harder to reconstruct than it was today.
ZERO_IN_THE_MEDIUM = (
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/lpsv.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/td8esy.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/rommsy.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/rf08ns.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/pt8e.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/csa.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/rk8ens.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/lspt.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/tm8e.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/vr12.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/lincsy.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/lqp.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dump.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/vt50.bn", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/csb.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/csc.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/csd.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/rlsy.bn", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/sqrt.ra", 3072),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/xfix.ra", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/abs.ra", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/realtm.ra", 5760),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/alog10.ra", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dim.ra", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/atan.ra", 1920),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/float.ra", 384),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/exp.ra", 1920),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/ifix.ra", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/sinh.ra", 1920),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/csin.ra", 1536),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/amod.ra", 1152),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dmod.ra", 1536),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dlog10.ra", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/tand.ra", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dexp3.ra", 1152),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dlog.ra", 3072),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/csqrt.ra", 1536),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/real.ra", 1152),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dmin1.ra", 768),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/amin.ra", 1152),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/exp3.ra", 1152),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/dsqrt.ra", 1152),
    ("somuchstuff-pdp8/trunk/pdp8/src/dec/dec-s8-lftna/dec-s8-lftna-a-ua1.0/cos.ra", 768),
)


def zero_in_the_medium(rel):
    """Is this file a faithful copy of a region the medium itself holds as zeros? -> size or None.

    The same right-anchored path match as zero_at_source() and zero_in_capture(), for the same
    reason: --root may be the collection or one archive inside it.
    """
    rel = rel.replace(os.sep, "/")
    for known, size in ZERO_IN_THE_MEDIUM:
        if known == rel or known.endswith("/" + rel):
            return size
    return None


# Files with WHOLE EMPTY BLOCKS INSIDE THEM that the source serves byte for byte the same way.
#
# WHY A FOURTH TABLE AND NOT `ZERO_AT_SOURCE`. That one is about files that are entirely zero and
# it matches on (path, size). These are not empty; they are 73 to 95 per cent empty, which is a
# different claim needing a different proof -- two files can share a length and differ in every
# block that matters. So the record here is the SHA-256 of the whole file, ours and the source's,
# and they are equal.
#
# HOW THEY WERE SETTLED [2026-09-25, the first full --holes run]. Asking for the length was not
# enough and very nearly ended the matter: all three sources answer HEAD with EXACTLY the length
# held here, and a source holding the intact file at the same length is precisely the case where
# a repair IS possible. Only the bytes tell the two apart, so all three were fetched whole
# (130 MB) and compared. Identical, every one. Our copies are faithful and there is nothing to
# re-fetch -- copying would change not one byte.
#
# THEY ARE REAL DAMAGE, and that is the point of recording rather than exempting them:
#
#   AlphaStations.avi   the RIFF header declares 0x012D4F18 + 8 = 19 746 592 bytes, which is
#                       EXACTLY the file size -- and 18 of its 19 blocks are nothing. Right size,
#                       right signature, right self-declared length, 94.7 % absent. No other
#                       check in this collection can see it; this is the shape --holes exists for.
#   both PDFs           open with a valid `%PDF-1.6` header and their last `%%EOF` sits at byte
#                       420 and 424 of 30 and 79 MB. Everything after the first-page cross
#                       reference is zeros.
#
# Recorded so they stop being reported and so the claim can be re-checked: if a source ever
# replaces one, its SHA-256 stops matching and `ask-the-source.py`'s successor has something to
# find. `holes-at-source-test.py` re-takes the local half of the measurement.
HOLES_AT_SOURCE = (
    ("zx-alphant-nt/Miscellany/AlphaStations.avi",
     19746592, "6919c492aef4c71320061e405f85fd8f0646ea468b3ee60a866865d93def5b94"),
    ("bitsavers/www.computer.museum.uq.edu.au/pdf/DEC-11-HDUMA-B-D DU11 Single Line Programmable Synchronous Interface Maintenance Manual.pdf",
     30391332, "2ec631c2dda268122cc75661758c9f3fb3c64972d2037594c2894e05efb16a83"),
    ("bitsavers/www.computer.museum.uq.edu.au/RSX/AA-L668A-TC RSX-11M & M-PLUS RMS-11 Macro Programmer's Guide.pdf",
     79691564, "a6ce632d23f0f1ca284974d1e48aab4e814cc2ee971127de31e180ad44be36c4"),
)


def holes_at_source(rel, digest):
    """Is this file one the source serves with exactly these holes? -> True/False.

    THE DIGEST IS PART OF THE KEY, unlike the other three tables. A path and a length cannot
    distinguish a file that is 94 per cent zeros from the intact file of the same length, and
    that distinction is the entire question here.
    """
    rel = rel.replace(os.sep, "/")
    for known, _size, sha in HOLES_AT_SOURCE:
        if (known == rel or known.endswith("/" + rel)) and sha == digest:
            return True
    return False


def zero_at_source(rel):
    """Is this one of the files the source itself serves as zeros? -> the recorded size, or None.

    MATCHED FROM THE RIGHT, ON A PATH BOUNDARY, because --root may be the whole collection or a
    single archive inside it. relative_to() answers against whatever root it was given, so the
    same file arrives here as `sun3arc/ROMs/3_60/x.gz` in one run and `ROMs/3_60/x.gz` in the
    next. Written as a plain equality this record matched only the first and went on reporting
    the second as a loss -- worse than having no record at all, because it looks like it works.

    The boundary is what keeps it honest: a file called `chinese2.htm` somewhere else entirely
    must not be matched by `.../kybdtech/chinese2.htm`.
    """
    rel = rel.replace(os.sep, "/")
    for known, size in ZERO_AT_SOURCE:
        if known == rel or known.endswith("/" + rel):
            return size
    return None


def cannot_be_empty(name):
    """Does this name, by itself, say that a file of nothing is damage?

    THE QUESTION A SIZE FLOOR CANNOT ANSWER. The first full run found 400 all-zero files. Sorted
    by extension rather than by size: 74 `.htm`, 4 `.html`, 2 `.gz` and 1 `.pdf` were certain
    losses -- a page or an archive of zeros was never content -- while 129 `.dat`, 28 `.qpm`,
    25 `.ra` and 23 `.qpk` were files a source is entitled to ship empty.

    A FLOOR WOULD HAVE BEEN WRONG IN BOTH DIRECTIONS. The certain ones run from 137 bytes to
    276 906; --holes' 16 MB floor sees none of them, and even 16 KB would report 36 while
    missing 45. Size says nothing here; the name does.

    PAST TENSE ABOVE, BECAUSE THIS FUNCTION'S ANSWER HAS SINCE MOVED, AND KNOWING WHICH WAY IS
    THE POINT [2026-09-24]. `.qpk` was recognised as gzip and entered MAGIC, so the 23 became
    certain losses -- and then fsck.technology was asked about all 51 QNX files and served every
    one of them as zeros at exactly our length. The verdict here got SHARPER and the finding
    disappeared, and both are right: what a name can promise and what a source actually shipped
    are different questions. This function answers only the first. ZERO_AT_SOURCE answers the
    second, which is why widening MAGIC must never be done without re-reading that table.

    It asks the library rather than keeping a list of its own: looks_like_a_page for markup,
    MAGIC for anything with a signature. Both are tested where they live.
    """
    return looks_like_a_page(name) or file_extension(name) in MAGIC


def check_empty(root, probe=ZERO_PROBE, report=None):
    """Files that are ENTIRELY zero bytes: a transfer that failed and was kept as content.

    WHY NEITHER OF THE OTHER TWO FINDS THESE. --ruins only opens files whose extension has a
    known signature, so a zero-filled .txt is invisible to it; the two zero-filled ROM images in
    sun3arc turned up there only by accident, because a file of nothing also fails the .gz magic.
    --holes reads every file IN FULL and starts at 16 MB, so 33 KB of nothing passes it twice
    over -- once for size, once because nobody waits out 3.8 TB to find a 33 KB file.

    CHEAP BECAUSE ALMOST EVERY FILE FAILS AT THE FIRST BYTE. Read one block; unless all of it is
    zero, stop. Only a candidate is read to the end, and there are very few. That is ~7 GB of
    reading across this collection instead of 3.8 TB, which is the difference between a check
    that gets run and one that does not.

    An EMPTY file (0 bytes) is not this: it has no content to be wrong about, and a source is
    entitled to serve one. Only a file with a plausible size and nothing in it is a ruin.
    """
    say("=== Empty: files holding nothing but zeros ===")
    certain, unclear, at_source, in_capture, in_medium, unreadable = [], [], [], [], [], 0
    for size, p in walk(root, report):
        if size == 0 or is_partial(os.path.basename(p)):
            continue
        answer = is_all_zero(p, probe=probe)
        if answer is None:
            # NOT counted as fine. A file that could not be opened has not been shown to be
            # anything, and a silent zero here is how a tree reads as clean because part of it
            # was unreadable -- the shape containment.py exists to refuse.
            unreadable += 1
            continue
        if answer:
            rel = relative_to(root, p)
            recorded = zero_at_source(rel) if rel else None
            captured = zero_in_capture(rel) if rel else None
            medium = zero_in_the_medium(rel) if rel else None
            if recorded == size:
                # Measured against the live host and found empty THERE. Our copy is faithful, so
                # this is not a finding -- but it is still printed, because a record nobody sees
                # is a record nobody can challenge when the source changes.
                at_source.append((size, rel))
            elif captured == size:
                # A SECOND KIND OF EVIDENCE, and kept apart from the first on purpose. Nobody
                # asked a host about these; what was checked is the packing list of the archive
                # they were unpacked from. That is weaker -- it proves the length, not the bytes
                # -- and a reader who cannot tell the kinds apart cannot judge any of them.
                in_capture.append((size, rel))
            elif medium == size:
                # THE THIRD KIND, and the strongest of the three: the medium these came off is
                # in this collection, and its own blocks are zero where they sit. Nothing has to
                # be taken on trust and nothing has to still be online to re-check it.
                in_medium.append((size, rel))
            elif cannot_be_empty(p):
                certain.append((size, rel))
            else:
                unclear.append((size, rel))

    say("  A FILE OF THIS KIND CANNOT BE EMPTY -- these are losses")
    for size, rel in sorted(certain, reverse=True):
        say("    %9d B  %s" % (size, rel))
    say("    %s\n" % plural(len(certain), "file"))

    say("  and %s whose kind says nothing either way, listed and not judged:"
          % plural(len(unclear), "file"))
    seen = {}
    for size, rel in unclear:
        seen.setdefault(file_extension(rel) or "(no extension)", []).append((size, rel))
    for ext, items in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        smallest, largest = min(i[0] for i in items), max(i[0] for i in items)
        say("    %-14s %4d   %d B .. %d B   e.g. %s"
              % (ext, len(items), smallest, largest, sorted(items)[0][1][:58]))
    if at_source:
        say("\n  and %s the SOURCE ITSELF serves as zeros -- our copy is faithful:"
              % plural(len(at_source), "file"))
        for size, rel in sorted(at_source, reverse=True):
            say("    %9d B  %s" % (size, rel))
    if in_capture:
        say("\n  and %s already empty in the archive this tree was unpacked from, at exactly"
              % plural(len(in_capture), "file"))
        say("  this length -- checked against that archive's own packing list, not against a")
        say("  live host, because there is no longer one to ask:")
        # Grouped by the FIRST PATH SEGMENT, which is the archive when --root is the collection
        # and a subdirectory when it is one archive. Naming the variable `by_archive` would have
        # been wrong half the time.
        by_top = {}
        for size, rel in in_capture:
            by_top.setdefault(split_archive(rel)[0], []).append((size, rel))
        for top, items in sorted(by_top.items()):
            say("    %-28s %4d, %d B .. %d B"
                  % (top, len(items), min(i[0] for i in items), max(i[0] for i in items)))
    if in_medium:
        say("\n  and %s that are faithful copies of blocks THE MEDIUM ITSELF holds as zeros,"
              % plural(len(in_medium), "file"))
        say("  checked against the image and against the extractor's own block index, both of")
        say("  which are in this collection and can be re-checked without a network:")
        by_top = {}
        for size, rel in in_medium:
            by_top.setdefault(split_archive(rel)[0], []).append((size, rel))
        for top, items in sorted(by_top.items()):
            say("    %-28s %4d, %d B .. %d B"
                  % (top, len(items), min(i[0] for i in items), max(i[0] for i in items)))
    if unreadable:
        say("\n  %s could not be read at all" % plural(unreadable, "file"))
    say("")
    return len(certain)


# The names a stored directory index is kept under. Deliberately short: parse_listing is
# forgiving enough to read an ordinary web page as a link list, and every page it reads that is
# not a listing is a chance to invent a finding out of somebody's table of version numbers.
#
# MEASURED BEFORE BEING TRUSTED, 2026-09-24, over the first 12 archives: of 722 files ending
# .html or .htm whose bytes match INDEX_PAGE, 722 are called index.html or index.htm and NONE
# carries another name. What that measurement does NOT cover is a listing stored under a name
# with no HTML extension -- and that is on purpose, because it is a different defect with its own
# check: `--ruins` reports it as "directory listing", and 33 such files were the whole of B1.
LISTING_NAMES = ("index.html", "index.htm")

# HOW FAR SHORT A FILE HAS TO FALL BEFORE IT IS CALLED A FINDING, on top of the printed-precision
# rule size_agrees() applies. Some servers' size column simply does not describe the files it
# lists, and that was settled by asking the server rather than by reasoning about it:
#
#     ps-2.kev009.com/.../aixcmds6/perftun.htm    its index says 89 088, we hold 86 697
#     re-fetched 2026-09-24, HTTP 200, 86 697 bytes -- the live server serves exactly our copy.
#     Two more checked the same way, same answer. Our copies are faithful; the column is not.
#
# Across that tree the disagreement runs both ways and reaches 2.7% on the files that survive
# size_agrees(). The smallest shortfall anywhere that is NOT of that kind is 19.5%, and the two
# genuine ones are 99.7% and 99.98%. So the gap between 2.7% and 19.5% is real and measured, and
# 10% sits in it with room on both sides.
#
# THIS IS A THRESHOLD, NOT A LAW. It is a property of the sources in this collection as measured
# on one day. A file 5% short of its listing is still printed -- in its own group, where somebody
# can look -- because being quiet about it would be the same mistake in the other direction.
LISTING_NOISE = 0.10


def check_listed(root, report=None):
    """Compare each file against the size the SOURCE'S OWN INDEX printed for it.

    THIS IS THE ONLY CHECK HERE THAT DOES NOT ASK THE TREE ABOUT ITSELF. A marker counts the
    tree, an index hashes the tree, `--verify` compares the tree with what was recorded from the
    tree -- so anything already wrong when the index was built stays invisible for ever. **A
    truncated download hashes to itself perfectly.** The stored directory listings are different:
    the server wrote them, they name a size per file, and the crawler fetched those files
    afterwards. It is the cheapest independent record in the collection and it is already on disk.

    WHAT IT FOUND ON THE DAY IT WAS WRITTEN, over four archives:

        bullfreeware…/contrib/mozilla-0.8.0.0.exe   listed 38 063 308   on disk 7 488

    which is not an executable at all but an HTML page carrying `Copyright (C) Bull SAS - 2019`:
    a server answering 200 with a landing page, stored under the name of the file that was asked
    for. `--ruins` is silent because `.exe` has no entry in MAGIC, `--empty` is silent because it
    is not zeros, and `--verify` is silent for the reason above.

    SMALLER AND LARGER ARE NOT THE SAME FINDING, and splitting them is what makes the output
    readable. A file SHORTER than the index promised is the loss shape -- a transfer that stopped.
    A file LONGER than it lost nothing, and the commonest reason in this collection is an SSI
    page: hp-labs-2007's listing gives the size of the .html on the server's disk while what was
    fetched is the assembled output, so 5 800 pages there are each about 15 kB larger. Only short
    ones can be findings, and only those short by more than LISTING_NOISE -- see there for why
    that threshold exists and what settled it.

    OVER THE WHOLE COLLECTION, 2026-09-24: 2 084 listings, 89 984 files compared, 88.0% agreeing.
    The first run counted 18 short. Asking the live server about three of them showed our copies
    were byte-for-byte what it still serves, so the count was wrong about them and the threshold
    now separates the two kinds.

    THE COMPARISON IS size_agrees(), NOT `==`. A listing prints about two significant digits, so
    `1.1M` expands to 1 153 433 for a file of any size nearby, and some servers never print below
    `1k` at all. Comparing with `==` reported 41 contradictions where there were 3; the library
    carries that rule and its measurements.
    """
    say("=== Listed: files that disagree with the size their source's index printed ===")
    short, slight, long_, agreed, no_statement = [], [], [], 0, 0
    pages = 0
    for _size, page in walk(root, report):
        if os.path.basename(page).lower() not in LISTING_NAMES:
            continue
        try:
            with io.open(long_path(page), encoding="utf-8", errors="replace") as fh:
                body = fh.read(400000)
        except OSError:
            continue
        here = os.path.dirname(page)
        used = False
        for href, listed, _mtime in parse_listing(body):
            if href.endswith("/") or href.startswith("/") or "?" in href \
                    or href.startswith("http") or ":" in href.split("/")[0]:
                continue                       # a directory, a parent link, or somewhere else
            if listed is None:
                # NOT "the column could not say". There was no column: this page is a page of
                # links, not a directory index, and parse_listing is forgiving enough to read
                # one as the other. Counting these would drown the summary in pages that have
                # nothing to do with the question.
                continue
            name = urllib.parse.unquote(href)
            if name in BOOKKEEPING_FILES or is_partial(name):
                continue
            child = os.path.join(here, name)
            try:
                actual = os.path.getsize(long_path(child))
            except OSError:
                # NOT a finding. A listing naming a file we do not hold is a gap in the crawl,
                # which is a different question and one --verify's counts already answer. This
                # check is only about files we DO hold being the wrong size.
                continue
            used = True
            verdict = size_agrees(listed, actual)
            if verdict is True:
                agreed += 1
            elif verdict is None:
                no_statement += 1
            elif actual < listed:
                row = (listed - actual, listed, actual, relative_to(root, child))
                (short if (listed - actual) > LISTING_NOISE * listed else slight).append(row)
            else:
                long_.append((actual - listed, listed, actual, relative_to(root, child)))
        if used:
            pages += 1

    say("  SHORTER THAN THE SOURCE SAID BY MORE THAN %d%% -- read these" % (LISTING_NOISE * 100))
    for gap, listed, actual, rel in sorted(short, reverse=True):
        say("    %-58s listed %11d  on disk %11d  short by %s (%.1f%%)"
              % (rel[:58], listed, actual, human(gap), 100.0 * gap / listed))
    say("    %s\n" % plural(len(short), "file"))

    if slight:
        say("  and %s short by less than that -- on the sources measured, the column simply"
              % plural(len(slight), "file"))
        say("  does not describe its own files, so these are listed and not judged:")
        for gap, listed, actual, rel in sorted(slight, reverse=True)[:20]:
            say("    %-58s listed %11d  on disk %11d  -%.1f%%"
                  % (rel[:58], listed, actual, 100.0 * gap / listed))
        if len(slight) > 20:
            say("    ... and %d more" % (len(slight) - 20))
        say("")

    if long_:
        say("  and %s LONGER than the index said, which loses nothing and is listed"
              % plural(len(long_), "file"))
        say("  rather than judged. The commonest cause here is measured, not guessed: an SSI")
        say("  page. hp-labs-2007's listing states the size of the .html ON THE SERVER'S DISK")
        say("  while what was fetched is the assembled output, so every page in that tree is")
        say("  about 15 kB larger -- the same header and footer, included server-side:")
        for gap, listed, actual, rel in sorted(long_, reverse=True)[:20]:
            say("    %-58s listed %11d  on disk %11d  +%s"
                  % (rel[:58], listed, actual, human(gap)))
        if len(long_) > 20:
            say("    ... and %d more" % (len(long_) - 20))

    # EVERY GROUP, OR THE LINE IS A LIE. Adding `slight` as a fourth outcome and forgetting it
    # here made the collection run report 89 972 files where it had compared 89 984 -- off by
    # exactly the size of the group that had just been introduced. A summary whose parts do not
    # add up to its own total is worse than no summary, and a test now sums them.
    total = agreed + no_statement + len(short) + len(slight) + len(long_)
    say("\n  read %s holding a size column, %s compared:"
          % (plural(pages, "listing"), plural(total, "file")))
    # ONE LINE PER OUTCOME, so the parts can be read off and added up. They were on three lines
    # with two numbers sharing the last one, which is how the total came to disagree with them
    # without anybody seeing it.
    say("    %6d agree with the listing" % agreed)
    say("    %6d the column could not say (it prints no size that small)" % no_statement)
    say("    %6d short by more than %d%% -- findings" % (len(short), LISTING_NOISE * 100))
    say("    %6d short by less -- listed, not judged" % len(slight))
    say("    %6d longer -- listed, not judged" % len(long_))
    say("")
    return len(short)



def check_declared(root, report=None):
    """Files that state their own length -- and do not have it.

    THE ONE CHECK THAT NEEDS NOTHING BUT THE FILE. Every other external record this collection
    uses can go away: a live host stops answering, a packing list is lost with its archive, a
    stored listing was never taken. A length a file states about itself travels with it.

    IT SEES WHAT NOTHING ELSE CAN. A download that simply stopped -- no zeros, just fewer bytes --
    is invisible to all four other checks. `--empty` sees a file that is not empty, `--ruins`
    reads a perfectly good header, `--holes` finds no empty block because nothing was written
    where the missing part would be, and `--verify` hashes the truncated file to itself and is
    satisfied. Only `--listed` could catch it, and only for the 88 per cent of files whose source
    published a size.

    AND IT IS THE ONLY CHECK THAT LOOKS AT DISC IMAGES AT ALL. `check_holes` exempts them, because
    unallocated sectors read as zeros and always will -- which leaves 2 042 `.iso` and 521 GB with
    nothing asking anything about them. ISO 9660 records its own volume size in 2 KB at sector 16.

    AN ISO FINDING IS WHERE A QUESTION STARTS, NOT WHERE IT ENDS, and the report says "losses"
    more firmly than the evidence supports for that format. The descriptor states a volume size
    and both endian copies agree -- a real signal -- but it cannot tell a truncated image from
    one whose descriptor simply describes more than the file holds. Measured 2026-09-25 by asking
    7-Zip about all 199 that this check flagged: **11 truncated** (their own directory needs more
    bytes than the file contains), **134 not damaged at all**, and 54 that 7-Zip cannot read
    either, where no verdict is possible. A zip finding here is solid -- that half agreed with
    Python's `zipfile` 300 times out of 300 -- and an ISO finding is a candidate.
    See `measurements/iso-second-opinion-2026-09-25.md`.

    SHORT IS DAMAGE; LONG IS NOT, and the asymmetry is the whole of the judgement. A file longer
    than it declares is ordinary: a CD image padded to a track boundary, a self-extracting archive
    with a stub before the zip, a RIFF with metadata after the chunks. Reporting those would bury
    the real findings under the normal ones, which is how a check stops being read.

    CHEAP. 12 bytes for a RIFF, 2 KB for an ISO, 66 KB from the end of a ZIP. 69 117 files in this
    collection state a length, 881 GB between them, and this reads a few hundred megabytes.
    """
    say("=== Declared: files that state their own length and do not have it ===")
    short, over, silent, unreadable = [], [], [], 0
    looked = 0
    for size, p in walk(root, report):
        try:
            said = declared_length(p)
        except OSError:
            unreadable += 1
            continue
        if said is None:
            continue
        looked += 1
        expected, fmt = said
        rel = relative_to(root, p) or p
        if expected is None:
            # A zip with no End Of Central Directory. The record is not optional.
            silent.append((size, fmt, rel))
        elif size < expected:
            short.append((expected - size, size, expected, fmt, rel))
        elif size > expected:
            over.append((size - expected, fmt, rel))

    say("  A FILE SHORTER THAN IT SAYS IT IS -- these are losses")
    for missing, size, expected, fmt, rel in sorted(short, reverse=True):
        say("    %12s missing  %s of %s  %-9s %s"
            % (human(missing), human(size), human(expected), fmt, rel))
    say("    %s\n" % plural(len(short), "file"))

    if silent:
        say("  and %s whose own record is GONE -- a zip must end with a central directory:"
            % plural(len(silent), "file"))
        for size, fmt, rel in sorted(silent, reverse=True):
            say("    %12s  %-9s %s" % (human(size), fmt, rel))
        say("")

    if over:
        # Counted, not listed. Padding is ordinary and a list of it is how a report stops being
        # read -- but a count that suddenly moves is worth seeing.
        by_fmt = {}
        for extra, fmt, _rel in over:
            got = by_fmt.setdefault(fmt, [0, 0])
            got[0] += 1
            got[1] = max(got[1], extra)
        say("  and %s longer than declared, which is ordinary (padding, a stub, trailing"
            % plural(len(over), "file"))
        say("  metadata) and is counted rather than listed:")
        for fmt, (n, biggest) in sorted(by_fmt.items()):
            say("    %-9s %5d, at most %s extra" % (fmt, n, human(biggest)))
        say("")

    say("  %s asked, %s could not be read\n"
        % (plural(looked, "file"), plural(unreadable, "file")))
    return len(short) + len(silent)


def check_holes(root, min_size, report=None):
    """Find downloads that stopped in the middle without saying so.

    A file can carry the right magic bytes, the right extension and a plausible size and still be
    unusable: an abandoned torrent preallocates the full length and fills pieces out of order, so
    what is missing reads back as zeros. A set of fix-pack archives was found this way -- 827 MB with
    0.8 % of its blocks empty looks perfectly healthy in any directory listing.

    Whole-megabyte runs of zeros are the signature. Real compressed data effectively never
    produces one; sparse disk images legitimately do, which is why they are exempt.
    """
    say("=== Holes: entirely empty blocks in the middle of a file ===")
    say("  (reads every file of %d MB or more in full -- this takes a while)" % (min_size // 1048576))
    blk = 1 << 20
    zero = bytes(blk)
    # Unallocated blocks in a disk image read as zeros and always will. A carved region such as an
    # AIX boot logical volume can be 37 % empty and perfectly intact.
    exempt = {".qcow2", ".img", ".iso", ".raw", ".bin"}
    found = read = 0
    unreadable = []
    at_source = []
    for size, p in walk(root, report):
        if size < min_size or file_extension(p) in exempt:
            continue
        n = empty = 0
        try:
            with open(long_path(p), "rb") as fh:
                while True:
                    b = fh.read(blk)
                    if not b:
                        break
                    n += 1
                    if b == zero[:len(b)]:
                        empty += 1
        except OSError as exc:
            # NOT A SILENT SKIP, and it was one. This check reads 33 734 files and 2.39 TB --
            # between four and eleven hours on this volume. A file that could not be opened has
            # not been shown to be anything, and swallowing it means the run ends with a count
            # that is silent about its own blind spot. check_empty has refused exactly this shape
            # since it was written; this one carried `except OSError: continue` for as long.
            #
            # It is not hypothetical over a pass this long: a lock, a bad sector, a path the
            # filesystem will not open twice. Recorded and reported, and it does NOT count as a
            # finding -- "I could not look" and "I looked and it was fine" stay apart.
            unreadable.append((relative_to(root, p) or p, type(exc).__name__))
            continue
        read += 1
        if not empty:
            continue
        rel = relative_to(root, p) or p
        # ONLY NOW IS THE FILE HASHED. Reading 2.39 TB twice to answer a question about three
        # files would be absurd; a file with no empty block is never a candidate, and the ones
        # that are number in the dozens.
        if holes_at_source(rel, sha256_file(p)):
            at_source.append((size, empty, n, rel))
            continue
        found += 1
        say("  %6.1f MB  %4d/%4d blocks empty (%.1f %%)  %s"
            % (size / 1048576, empty, n, 100 * empty / n, rel))
    say("  %d incomplete files, %s read in full" % (found, plural(read, "file")))
    if at_source:
        say("")
        say("  and %s the SOURCE SERVES WITH THE SAME HOLES, byte for byte -- our copy is"
            % plural(len(at_source), "file"))
        say("  faithful and there is nothing to re-fetch. Damaged, and not damaged by us:")
        for size, empty, n, rel in sorted(at_source, reverse=True):
            say("    %6.1f MB  %4d/%4d blocks empty (%.1f %%)  %s"
                % (size / 1048576, empty, n, 100 * empty / n, rel))
    if unreadable:
        say("")
        say("  AND %s COULD NOT BE READ AT ALL -- this check says nothing about them:"
            % plural(len(unreadable), "file").upper())
        for rel, why in unreadable[:20]:
            say("    %-12s %s" % (why, rel))
        if len(unreadable) > 20:
            say("    ... and %d more" % (len(unreadable) - 20))
    say("")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", action="append", metavar="PATH", default=[],
                    help="manifest file, or a directory to find manifests in. Repeatable. A "
                         "directory is searched at its own level and one level down, so a mirror "
                         "root loads every archive in it")
    ap.add_argument("--protect", action="append", metavar="LABEL", default=[],
                    help="treat this source as authoritative even though it is not a mirror")
    ap.add_argument("--unprotect", action="append", metavar="LABEL", default=[],
                    help="the reverse, for a mirror manifest to be treated as ordinary")
    ap.add_argument("--csv", metavar="PATH",
                    help="write every duplicate group here, not just the head of each list")
    ap.add_argument("--head", type=int, default=15,
                    help="groups printed per class (default 15); the counts are always complete")
    ap.add_argument("--ruins", action="store_true", help="magic bytes vs extension; needs --root")
    ap.add_argument("--holes", action="store_true", help="zero-block check; needs --root")
    ap.add_argument("--declared", action="store_true",
                    help="compare each file against the length IT states for itself -- RIFF, ZIP "
                         "and ISO 9660. Needs --root. The only check that needs nothing but the "
                         "file, and the only one that looks at disc images at all")
    ap.add_argument("--empty", action="store_true",
                    help="files of a plausible size holding nothing but zeros; needs --root. "
                         "Cheap: one block per file, and only a candidate is read further")
    ap.add_argument("--listed", action="store_true",
                    help="compare each file against the size its source's own stored directory "
                         "index printed; needs --root. The only check here that does not ask the "
                         "tree about itself. Cheap: reads listings, stats files")
    ap.add_argument("--root", metavar="PATH",
                    help="the tree for --ruins, --holes, --empty and --listed")
    ap.add_argument("--quiet", action="store_true",
                    help="no progress lines. They go to stderr and name each archive as it is "
                         "reached; without them a run over this collection prints nothing at all "
                         "for the best part of an hour, which is indistinguishable from a hang")
    ap.add_argument("--ext", action="append", metavar="EXT", default=[],
                    help="only consider files with this extension, e.g. --ext .iso. Repeatable. "
                         "Filters the INPUT to the duplicate scan, so a group is reported only "
                         "when every copy in it survives the filter")
    ap.add_argument("--min-mb", type=float, default=0.0, metavar="MB",
                    help="only consider files of at least this many MB in the duplicate scan")
    ap.add_argument("--min-size", type=int, default=16,
                    help="minimum size in MB for --holes (default 16)")
    args = ap.parse_args()

    say("This script deletes nothing. It only reports.\n")

    if args.ruins or args.holes or args.empty or args.listed or args.declared:
        if not args.root or not os.path.isdir(args.root):
            sys.exit("--ruins, --holes, --empty, --listed and --declared read files, so they "
                     "need --root pointing at a tree.")
        root = os.path.abspath(args.root)
        # THE COUNTS WERE THROWN AWAY UNTIL 2026-09-24, and every one of these checks returns
        # one. A run that reported 81 certain losses exited 0, so none of this could ever be a
        # gate -- the whole point of a check is that something downstream can act on its answer.
        # PROGRESS IS ON BY DEFAULT HERE and off in the functions, which is the right way round:
        # a library says nothing unless asked, and a person waiting an hour at a terminal wants
        # to know it is working. It goes to STDERR, so `audit.py --ruins > report.txt` still
        # produces a report with nothing in it but findings.
        reporter = None if args.quiet else (lambda m: say(m, stream=sys.stderr))
        findings = 0
        if args.ruins:
            findings += check_ruins(root, report=reporter)
        if args.empty:
            findings += check_empty(root, report=reporter)
        if args.listed:
            findings += check_listed(root, report=reporter)
        if args.declared:
            findings += check_declared(root, report=reporter)
        if args.holes:
            findings += check_holes(root, args.min_size * 1048576, report=reporter)
        return 1 if findings else 0

    if not args.index:
        sys.exit("Nothing to do. Give --index (a manifest, or a directory holding some), or "
                 "--ruins / --empty / --listed / --declared / --holes together with --root.")
    return audit_duplicates(args.index, set(args.protect), set(args.unprotect),
                            args.csv, args.head,
                            tuple(e.lower() if e.startswith(".") else "." + e.lower()
                                  for e in args.ext),
                            int(args.min_mb * 1048576))


if __name__ == "__main__":
    sys.exit(main())
