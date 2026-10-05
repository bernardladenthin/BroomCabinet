#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""What every tool here needs, in one place, because the copies had drifted.

WHY THIS FILE EXISTS, measured 2026-09-22 across all 42 scripts:

    long_path   10 copies,  8 different bodies
    human       10 copies,  9 different bodies
    exists       4 copies,  3 different bodies
    user agent  18 copies,  3 different values
    own-files    8 copies,  NO TWO ALIKE -- 0 identical pairs out of 28
    the loader  14 copies,  8 names for one module, and 8 of the 14 restoring sys.argv

Eight bodies for one helper is not style, it is drift, and three of the eight shared one defect:
they built the absolute path with os.path.abspath(). abspath NORMALISES, and normalising STRIPS A
TRAILING DOT -- the very thing the \\?\ prefix exists to prevent. A filename may end in a dot or
a space; older systems produced them freely and a copy has no business renaming them. For every
such name that helper turned a name that exists into a name that does not, and a stat that fails
is a file an index silently omits and a count never reaches.

The own-files sets were worse, because they are not formatting but DECISIONS ABOUT WHAT COUNTS.
Eight tools each kept their own list of "this is ours, not content"; no two agreed, so two tools
walking the same tree returned different file counts, and this collection's whole currency is
numbers.

EVERYTHING HERE IS A FUNCTION WHERE IT PLAUSIBLY VARIES. The user agent is `user_agent()` rather
than a constant so that there is one place to change it and one thing to test, and so a caller
that needs to say something else says so at the call site instead of editing a module global.

MIRROR.PY IMPORTS THIS TOO, and it took one line elsewhere to make that safe. Fourteen tools
loaded mirror.py by path rather than importing it -- a hyphen in a filename, or a 7 000-line
module with its own argparse, is reason enough -- and for all but one of them `import common`
inside mirror.py simply works: Python puts the SCRIPT'S directory on sys.path, not the working
directory, so a tool started from anywhere finds its neighbour.

The exception was wedge_test.py, which runs mirror.py inside a fresh `python -c` subprocess.
There sys.path[0] is the working directory, so its two templates name the directory themselves.
That was the whole of the constraint that had kept mirror.py on its own copies of long_path,
human and sha256_file until 2026-09-22.

THOSE FOURTEEN LOADERS ARE NOW ONE, load_peer(), AND THE HONEST REASON IS NOT THAT ANY OF THEM
WAS WRONG. Measured before the change: one module went under eight different names, and eight of
the fourteen saved and restored sys.argv while six did not -- but mirror.py reads sys.argv nowhere
at import, so neither half was broken and the difference cost nothing on the day it was written.
It is a liability rather than a defect: the day that stops being true, or the day loading needs a
guard, there are fourteen places to find rather than one, and the six that never had the guard are
the six nobody will think to look at. The two `python -c` templates in wedge_test.py remain, in
another process, where this module is not yet on the path.

THE CONTRACT, because there are now forty-odd clients and one provider, and the same hand writes
both. Every rule here is checked by TestTheContract in common_test.py -- a promise nothing
enforces is a promise that has already been broken somewhere.

    WHAT IS EXPORTED     __all__ is the surface. Nothing public exists outside it, and no client
                         reaches past it. A name that starts with `_` is ours and may change.

    HOW FAILURE ARRIVES  Three ways, and which one is used is a decision about the caller, never
                         about convenience:
                           * None  -- "I have no answer", where having none is ordinary and the
                                      caller must not read it as "fine". magic_mismatch, http_date,
                                      extension_for, relative_to, parse_size.
                           * raise -- where continuing would produce a wrong RECORD rather than a
                                      wrong line of output. mediawiki_siteinfo refuses to guess a
                                      namespace list; load_peer refuses to return a None that would
                                      surface three frames away naming the wrong thing.
                           * empty -- where the thing is a CACHE and damage costs time, not
                                      correctness. read_index and read_marker return {} and the
                                      caller rebuilds.
                         Nothing here calls sys.exit(). Ending the process is the client's
                         decision, and a library that makes it cannot be tested or reused.

    PROGRESS AND NOISE   A function that discovers something a human would want to see takes a
                         `report` callback and calls it; it does not own the screen. Defaults
                         print, so a client that wants the usual behaviour writes nothing. The
                         parameter is `report` in every one of them, and never the name of
                         something this module also exports.

    ARGUMENTS            The container comes first: relative_to(root, path), local_path(root,
                         base, url), iter_tree(root, ...). What counts as ours is `own_files`, a
                         SET, in every walker -- a flag could not say which set, and the
                         difference between the narrow and the wide one is load-bearing.

    TABLES ARE READ-ONLY These tools load one another as modules inside ONE process. An exported
                         dict is shared mutable state: a client that "just adds an entry" changes
                         what every other client decides about a file, with nothing recording it.
                         MAGIC and EXTENSION_FOR_TYPE are MappingProxyType; sets are frozenset;
                         sequences are tuples.

    TESTABLE WITHOUT     Anything that would otherwise need a network, a console or a clock takes
    THE WORLD            it as an argument: `opener`, `stream`, `sleep`, `report`. Exercising a
                         helper against somebody's live server is not free -- it is their server --
                         and a helper that can only be exercised that way is one nobody exercises.

    python -m unittest common_test -v        the tests
    python common.py                         what this module offers
"""

import concurrent.futures
import csv
import hashlib
import html
import io
import os
import re
import socket
import subprocess
import sys
import threading
import time
import types
import zlib
import urllib.error
import urllib.parse

__all__ = [
    "user_agent", "request_headers",
    "long_path", "exists", "isfile", "safe_name", "safe_tar_segment",
    "relative_to", "comparable_path",
    "sha256_file", "sha256_bytes", "iter_files",
    "is_all_zero", "ZERO_PROBE",
    "iter_archives", "COLLECTION_DIRS",
    "human", "parse_size", "plural", "say",
    "LISTING_FLOOR", "listing_step", "size_agrees",
    "read_manifest", "find_manifests", "NEVER_CONTENT_DIRS",
    "parse_listing", "parse_date", "date_text", "resolution_base",
    "ROW_RE", "LIGHTTPD_RE", "PRE_RE", "LINK_RE", "LINK_ODD_RE", "FRAME_RE",
    "BASE_RE", "DATE_FORMATS",
    "WINDOWS_RESERVED",
    # mediawiki_* and pmwiki_* moved to modules of their own on 2026-09-23. Not re-exported
    # here on purpose: a name available from two modules is a name whose home nobody can tell,
    # and the point of the split was to give each one exactly one.
    #
    # WINDOWS_RESERVED STAYED, although it sat inside the mediawiki section. What this
    # filesystem refuses to store is a fact about the machine, not about one wiki engine.
    # dokuwiki_*, robots_* and wayback_* moved to modules of their own on 2026-09-23, and none
    # is re-exported here: a name available from two modules is a name whose home nobody can
    # tell, and giving each one exactly one home was the point of the split.
    # pdf_* moved to pdf.py on 2026-09-23, the last of the six sections to go. MAGIC[".pdf"]
    # below goes on spelling `%PDF` for itself, deliberately: magic_mismatch() answers a
    # question about extensions and must not have to import a PDF reader to do it.
    "sums_line", "read_index", "write_index",
    "read_marker", "write_marker", "marker_text", "MARKER_COLUMN",
    "iter_tree", "scan_tree", "hash_tree", "HASH_BATCH",
    "http_open", "answered_as_a_directory", "http_get", "http_try", "head_size", "unverified_context",
    "site_prefixes", "content_root", "under_site", "reach", "scheme_drift",
    "quote_url", "Pacer", "Backoff", "Patience", "blocking_parent", "local_failure", "UNREACHED",
    "GONE_FILE", "GONE_STATUS", "read_gone", "record_gone",
    "REFUSED_FILE", "read_refused", "record_refused",
    "RENAMED_FILE", "record_renamed",
    "declared_length", "DECLARES_ITS_LENGTH",
    "ZIP_TAIL", "ZIP_EOCD", "ZIP_CD_ENTRY", "ZIP64_MARK", "ISO_PVD_AT",
    "load_peer", "load_mirror", "source_url", "HTTP_FACE", "find_tool", "split_archive",
    "is_transport", "host_of", "http_date", "atomic_write", "copy_new_file",
    "RETRY_STATUS", "EMPTY_SHA256",
    "image_sources", "sitemap_locations", "extension_for",
    "IMG_SRC", "SITEMAP_LOC", "EXTENSION_FOR_TYPE",
    "set_case_sensitive",
    "is_partial", "looks_like_html", "looks_like_markup", "magic_mismatch",
    "MARKUP_HEADS", "BINARY_MAGIC", "MARKUP_WINDOW",
    "PARTIAL_SUFFIXES", "CHECKED_EXT", "MAGIC", "HTML_HEADS", "INDEX_PAGE",
    "page_title", "TITLE_TAG", "HEADING_TAG", "INNER_TAG",
    "looks_like_an_error_page", "PAGE_COMPLAINTS", "STOCK", "WEAK",
    "STOCK_ERROR_TITLES", "stock_error_title", "normalise_title",
    "LEADING_STATUS", "TITLE_JUNK", "TITLE_PREFIX",
    "classify_page", "PAGE_KINDS", "ORDINARY_PAGE",
    "looks_like_a_placeholder_page", "PLACEHOLDER_TITLES", "STUB_BODIES",
    "STUB_BYTES", "STUB_WINDOW",
    "file_extension", "url_extension",
    "MIN_FREE_BYTES", "COLLISION_DROPPED", "BFF_MAGIC", "FETCH_FAILED", "failed_urls",
    "OWN_FILES", "is_own_file", "BOOKKEEPING_FILES", "is_bookkeeping_file",
    "COMPLETE_MARKER", "INDEX_FILE", "SUMS_FILE", "PROVENANCE_FILE", "CATALOGUE_FILE",
    "DIGESTS", "digests_of_file", "crc32_text", "MANIFEST_FILES",
    "SHA1_FILE", "MD5_FILE", "SFV_FILE", "write_manifests", "read_manifests", "manifest_coverage", "read_sfv", "read_sums", "sfv_line",
    "MIRROR_ROOT",
    "ROOT_MARKER", "ARCHIVE_MARKERS", "archive_root",
    "COLLECTION_INDEX", "COLLECTION_SUMS",
    "is_extension_only", "looks_like_a_page", "looks_like_a_document", "looks_like_a_copy_of_a_page",
    "BACKUP_TAIL",
    "PAGE_EXTENSIONS", "DOCUMENT_EXTENSIONS", "PROGRAM_PAGE_EXTENSIONS",
    "MARKUP_EXTENSIONS",
    "strip_fragment", "strip_cache_buster", "is_child_link", "same_path_plus_slash",
    "looks_like_a_loop", "local_path",
    "LONG_PREFIX", "UNSAFE", "HASH_CHUNK", "STATIC_IMAGE",
    "MAX_DEPTH_BELOW_BASE", "MAX_CONSECUTIVE_REPEATS",
]

LONG_PREFIX = "\\\\?\\"
HASH_CHUNK = 1 << 20        # read size while hashing; 1 MB measured no worse than larger

# Characters Windows forbids in a filename. Sources do not care, so every tool that turns a URL
# into a path needs the same substitution -- and needs it to be the SAME one, or two tools
# disagree about where the same remote file belongs locally.
#
# THE BACKSLASH IS IN THE CLASS, and it was missing until 2026-09-23. Not cosmetic: callers split
# a url on "/" and pass each SEGMENT through safe_name(), so a separator that survives the
# substitution turns one segment into several directories. With `%5C` unquoted first -- which
# local_path() and blogger-sitemap.py both do -- the url `http://h/..%5C..%5Cetc%5Cx` mapped to
# `root\..\..\etc\x`, which normalises to `..\etc\x`: OUTSIDE root. The `..` guard beside it
# drops `..` only as a whole segment, so an encoded backslash smuggled the separators past it.
#
# Measured before the change: not one path in the 98 archive indexes holds a backslash, so
# nothing stored was mapped this way and nothing is orphaned by fixing it.
#
# `/` is deliberately NOT here: every caller splits on it before asking, and substituting it
# would turn a path into a name.
UNSAFE = re.compile('[<>:"|?*\\\\\x00-\x1f]')

# Device names Windows will not let a file be called, whatever the extension. A wiki, a web
# server and a tarball are all entitled to hold one, and every tool that turns a foreign name
# into a local path needs the same list.
#
# IT SAT INSIDE THE mediawiki SECTION until 2026-09-23, and only mediawiki_filename used it, so
# the split would have carried it off -- taking a general fact about this filesystem into a
# module about one wiki engine. Its own comment above says who needs it, and that sentence is
# why it stayed. Moved here, beside UNSAFE, where the rest of "what Windows will not store"
# already lives.
WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {"COM%d" % i for i in range(1, 10)}
    | {"LPT%d" % i for i in range(1, 10)})

_AGENT = "mirror/1.0"


# ------------------------------------------------------------------------------- identity


def user_agent():
    """The one identity every request from this collection goes out under.

    NEUTRAL ON PURPOSE, AND THAT IS MEASURED. On ndwiki.org, 2026-09-17, one variable at a time:
    anything beginning `Mozilla/` was answered with a proof-of-work challenge and everything else
    was answered with the file. The conventional `Mozilla/5.0 (compatible; X)` wrapper is a claim
    this program cannot honestly make, and dropping it is both more truthful and what gets served.
    mediawiki-source.py's docstring carries the table.

    UNTIL 2026-09-22 THERE WERE THREE. Five tools named themselves `archive-mirror/1.0` or
    `archival-copy/1.0`, one of those carried a contact e-mail address, and thirteen more sent a
    Chrome string they were not. A collection that asks servers to be honest with it should not
    open every request with a claim it cannot make.

    A function rather than a constant so there is one thing to test and one place to change.
    """
    return _AGENT


def request_headers(extra=None):
    """Request headers carrying the identity, plus whatever the caller adds.

    `extra` wins on a conflict: a caller asking for a Range or an Accept knows something this
    function does not. It cannot silently drop the User-Agent, because a caller that wanted no
    identity would not be calling this.
    """
    out = {"User-Agent": user_agent()}
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------------- paths


def long_path(path):
    r"""Windows refuses paths over 260 characters unless they carry the \\?\ prefix.

    A tree mirrored one url segment per directory crosses that easily -- a package repository
    nests the package name and then the full file name under it -- and without the prefix the
    failure surfaces as a misleading "No such file or directory" partway through a run.

    NOT via os.path.abspath(). abspath normalises, normalising strips a trailing dot, and the
    prefix exists to stop exactly that -- see the module docstring. Make it absolute by hand if
    it is not already, switch the separators, prefix. No normalisation anywhere.

    Safe because the roots these tools work from are absolute and everything joined onto them
    comes from os.walk() or from a URL path, never with `..` components.
    """
    if os.name != "nt":
        return path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    path = path.replace("/", "\\")
    if path.startswith(LONG_PREFIX):
        return path
    return LONG_PREFIX + path


def exists(path):
    """Does this path exist, including names only the prefixed form can reach?

    The plain call is tried first because it is the common case and because on POSIX it is the
    only one that means anything. One of the copies this replaces asked os.path.exists() on a
    RELATIVE path with the prefix glued on, which can never match.
    """
    return os.path.exists(path) or os.path.exists(long_path(path))


def isfile(path):
    """exists(), restricted to regular files.

    A directory occupying a file's path is a real case here: a server may offer one name as both
    and a filesystem cannot, so `is there a file at this path` and `is there anything` are
    different questions with different answers.
    """
    return os.path.isfile(path) or os.path.isfile(long_path(path))


def safe_name(name):
    """A filename a source served, made storable on Windows, with nothing else changed.

    NOT a path: the separator is left alone, so this is applied per component. Nothing is
    stripped, lowercased or normalised -- those names belong to the source server.
    """
    return UNSAFE.sub("_", name)


def safe_tar_segment(seg):
    r"""safe_name(), plus the one character a tar can carry that a URL crawler never meant to.

    A tar is a Unix artefact and `\` is an ORDINARY CHARACTER in a Unix filename. NTFS treats it
    as a separator, so a member literally named `dir\index.html` -- one file, in `dir`'s parent --
    becomes the path `dir/index.html` on Windows and lands on top of the real file of that name.
    Two members, one destination, and the second write destroys the first with nothing to show for
    it but a file count one lower than the manifest.

    Not hypothetical: h18002.www1.hp.com_20080527.tar carries both
    `products/storageworks/n12003204gnsr/index.html` and
    `products/storageworks/n12003204gnsr\index.html`, and they are different files.

    UNSAFE DELIBERATELY OMITS THE BACKSLASH AND IS LEFT ALONE. Widening it would repath every
    existing mirror to fix a case the HTTP crawler has never produced. mediawiki_filename() adds
    the backslash too, for the same reason in the opposite direction: a wiki title may contain one
    and a page is not a path. THREE DELIBERATE ANSWERS TO ONE QUESTION, which is why the pattern
    is shared and the decision is not.
    """
    return safe_name(seg.replace("\\", "_"))

def relative_to(root, path):
    """`path` as a forward-slash path under `root`, or None when it is not under it.

    NOT os.path.relpath, which normalises and therefore strips a trailing dot -- the same defect
    long_path exists to avoid, one function along. Compared case-insensitively on Windows only,
    because that is where the filesystem is.

    WHICH CHARACTERS ARE SEPARATORS IS A PLATFORM QUESTION, AND IT WAS ANSWERED WINDOWS-ONLY.
    A backslash is an ORDINARY CHARACTER in a POSIX filename, and this folded it to a slash on
    every platform: a file legitimately called `weird\\name.txt` on a Linux box came back as
    `weird/name.txt`, which is not a file at all but a path into a directory that does not
    exist. The same mistake in the other direction was already written down one function along,
    in safe_tar_segment: `\\` is a separator on NTFS and content on Unix, and no single answer
    is right for both. Here the platform decides.

    THE LONG-PATH PREFIX IS TAKEN OFF BOTH SIDES FIRST, and leaving that out was a trap that
    fired.
    A caller who walks with long_path(root) gets long paths back from os.walk and then passes the
    PLAIN root here: the two spellings of one path do not match by prefix, so every file comes
    back None -- silently, and the caller writes absolute paths into a column it labelled
    "relative". Measured 2026-09-24 over 26 280 rows, every one of them wrong, and it looked
    like a broken exception list rather than a path spelling.
    """
    seps = "\\/" if os.name == "nt" else "/"
    r = root[len(LONG_PREFIX):] if root.startswith(LONG_PREFIX) else root
    p = path[len(LONG_PREFIX):] if path.startswith(LONG_PREFIX) else path
    r = r.rstrip(seps)
    if os.name == "nt":
        if not p.lower().startswith(r.lower()):
            return None
    elif not p.startswith(r):
        return None
    rest = p[len(r):].lstrip(seps)
    return rest.replace(os.sep, "/")


def comparable_path(path):
    """A relative path reduced to the ONE spelling two records can be compared in.

    Separators forward, a leading `./` dropped, case folded. Two lists of the same files -- a
    manifest and a register, a directory and an index -- are written by different hands and agree
    on the file while disagreeing on how to spell it, and a comparison that skips this reports
    every one of them as a difference.

    THE LEADING `./` IS REMOVED AS A PREFIX, NOT AS A SET OF CHARACTERS. This expression existed
    in five places as `path.lstrip("./")`, and str.lstrip takes a set: `.gitignore` came back as
    `gitignore`, `../x` as `x`, `...odd` as `odd`. Measured against the 34 entries in the register
    on 2026-09-22 not one was affected, which is the only reason this could be corrected rather
    than merely written down -- a dotfile at the top of an archive would have been compared under
    a name it does not have.

    Case is folded because the filesystem these records describe does not distinguish it, so
    treating two spellings as two files would invent a difference the disk does not have.
    """
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lower()

# --------------------------------------------------------------------------------- hashing


def sha256_bytes(data):
    """SHA-256 of something already in memory."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, chunk=HASH_CHUNK):
    """SHA-256 of one file, read in pieces so a 4 GB ISO does not become 4 GB of RAM."""
    h = hashlib.sha256()
    with open(long_path(path), "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# The four this collection records, and who asks for each. Order is the order they are written in,
# strongest first, so a file listing them reads as a descending statement of confidence.
#
#   sha256  ours. The one a verification decides on.
#   sha1    what BACKBLAZE B2 stores per file (X-Bz-Content-Sha1), so a copy in cold storage can be
#           checked against what B2 itself recorded without downloading it back.
#   md5     what the INTERNET ARCHIVE publishes, and the reason md5 is here at all. Measured
#           2026-10-02 on this collection's own IA-METADATA.json: md5 on 204 of 204 files, crc32
#           and sha1 on 203, and sha256 on NONE. An index of sha256 alone cannot be compared with
#           the Archive for any file at all -- and the Archive is the second opinion this
#           collection reaches for whenever an origin is gone.
#   crc32   what RAR and ZIP store per member, so a container can be checked against the index
#           without unpacking it, and what .sfv files in the wild carry -- including the two RHash
#           sets that came with ia-bullfreeware from before its upload.
#
# WEAK IS NOT THE SAME AS USELESS. md5 and sha1 are broken for COLLISION resistance and crc32 was
# never more than a transmission check. Nobody is forging a 2002 AIX package to match our index;
# what threatens a mirror is a truncated resume, a flipped bit, an error page saved as a .zip, and
# a 32-bit check catches every one of those. The strong answer is sha256 and stays sha256.
DIGESTS = ("sha256", "sha1", "md5", "crc32")


def crc32_text(value):
    """A CRC32 as the eight upper-case hex digits every .sfv in the wild uses."""
    return "%08X" % (value & 0xFFFFFFFF)


def digests_of_file(path, chunk=HASH_CHUNK, want=DIGESTS):
    """-> {name: hex text} for one file, computed in ONE READ.

    ONE READ IS THE WHOLE POINT. Four passes would be four reads, and this collection is 4.02 TB
    on a disk that delivers about 208 MB/s cold -- five and a half hours per pass. Measured
    2026-10-02 on a 470 MB file, CPU only, with the disk out of the picture:

        sha256 alone              1551 MB/s
        sha256+sha1+crc32          583 MB/s
        all four                   309 MB/s        <- md5 alone is 658, the expensive one
        the disk, cold             208 MB/s

    So all four together still outrun the disk and the run stays disk-bound: the three extra
    digests cost no wall clock, only the one pass that has to happen anyway. md5 halves the CPU
    headroom (2.8x over the disk down to 1.5x) and that is the only price.

    `want` EXISTS FOR THE CALLER THAT NEEDS ONE, not as an optimisation. Asking for a subset saves
    nothing worth measuring; it is here so a tool that means "the sha256 of this file" can say so.
    """
    hs = {name: hashlib.new(name) for name in want if name != "crc32"}
    crc = 0
    with open(long_path(path), "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            for h in hs.values():
                h.update(block)
            if "crc32" in want:
                crc = zlib.crc32(block, crc)
    out = {name: h.hexdigest() for name, h in hs.items()}
    if "crc32" in want:
        out["crc32"] = crc32_text(crc)
    return out


# How much of a file to read before deciding it is worth reading further. Almost every file in a
# collection fails at the first byte, so the probe is what makes the question affordable: a pass
# over 1.76 million files costs about 7 GB of reading instead of the tree's full 3.8 TB.
ZERO_PROBE = 4096


def is_all_zero(path, probe=ZERO_PROBE, chunk=HASH_CHUNK):
    """Is this file nothing but zero bytes? -> True, False, or None when it cannot be read.

    A TRANSFER THAT FAILED AND WAS KEPT AS CONTENT. Two ROM images in sun3arc are 33 615 and
    33 689 bytes of nothing while their neighbours in the same directory are 0.3 % zero and
    genuine. They have plausible sizes, they sit in an archive marked COMPLETE, and every count
    in the collection treats them as present. [found 2026-09-23]

    A ZERO-LENGTH FILE IS NOT THIS, and answers False. It has no content to be wrong about, and
    a source is entitled to serve one -- 20 archives here hold empty files on purpose. That is
    EMPTY_SHA256's question, not this one.

    NONE IS NOT FALSE. A file that cannot be opened has not been shown to be fine, and a caller
    that treats the two alike reports a tree as clean because part of it was unreadable -- the
    shape containment.py exists to refuse.

    CHEAP BY SHORTCUT: one probe block, and unless all of it is zero the answer is False without
    reading further. The confirming pass only runs for a candidate, and there are very few.
    """
    try:
        with open(long_path(path), "rb") as fh:
            head = fh.read(probe)
            if not head:
                return False                      # zero LENGTH is a different thing
            if head.strip(b"\x00"):
                return False                      # the common case, one block and done
            while True:
                b = fh.read(chunk)
                if not b:
                    return True
                if b.strip(b"\x00"):
                    return False
    except OSError:
        return None


# Top-level directories of a COLLECTION that are not archives. Measured 2026-09-23 over the
# whole tree: 99 directories, and exactly one -- `logs` -- carries no completion marker.
#
# NOT "a directory without a marker", which would be the tempting rule and is wrong: an archive
# part-way through its first fetch has no marker either, and skipping it would hide exactly the
# tree most worth looking at. A name is a decision; an absent marker is a state.
COLLECTION_DIRS = frozenset({"logs"})


def iter_archives(root, only=None):
    """Yield (archive name, archive root path) for each archive in a collection, sorted by name.

    THE OUTER LOOP THREE TOOLS WROTE SEPARATELY. corpus-coverage.py and page-extensions.py each
    carried it character for character -- sorted listdir, skip what is not a directory, skip
    `logs` -- before this existed, and a fourth would have written it again. What differs between
    those tools is what they do INSIDE an archive, which is theirs; finding the archives is not.

    The path is long_path()ed, because everything that walks it will need that and forgetting it
    is silent: os.walk simply returns nothing for a path Windows will not open.

    `only` limits the run to one archive by name and is not an error when it matches nothing --
    the caller sees an empty iteration and says what that means in its own words.
    """
    for name in sorted(os.listdir(root)):
        if only and name != only:
            continue
        if name in COLLECTION_DIRS or name in NEVER_CONTENT_DIRS:
            continue
        path = long_path(os.path.join(root, name))
        if not os.path.isdir(path):
            continue
        yield name, path


def iter_files(root, own_files=None):
    """Yield (relative path with forward slashes, full path) for every file under `root`.

    SKIPS OUR OWN FILES BY DEFAULT, and only at the top level, because that is where they live.
    A source archive is perfectly entitled to contain a file called PROVENANCE.md of its own one
    directory down, and that one is content.

    `own_files` is a SET rather than a flag, and is spelled the same here, in iter_tree() and in
    scan_tree(). The default is the WIDE bookkeeping set, where iter_tree's is the narrow one --
    a boolean could not have said which, and the difference between the two sets is the thing
    most worth being able to see at a call site. Pass frozenset() to walk everything.

    Sorted, so two runs over an unchanged tree produce the same order and a diff of two outputs
    means something.
    """
    if own_files is None:
        own_files = BOOKKEEPING_FILES
    root = root.rstrip("\\/")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        at_top = os.path.normcase(dirpath) == os.path.normcase(root)
        for name in sorted(filenames):
            if at_top and name in own_files:
                continue
            full = os.path.join(dirpath, name)
            rel = relative_to(root, full)
            if rel is not None:
                yield rel, full


# ------------------------------------------------------------------------------ own files


# WHAT THIS COLLECTION WROTE, as against what it copied. Nothing here came off a source server,
# so nothing here belongs in a checksum index, a file count or a size total.
#
# EIGHT TOOLS EACH KEPT THEIR OWN VERSION OF THIS LIST AND NO TWO AGREED -- 0 identical pairs out
# of 28, measured 2026-09-22. That is not untidiness: `find-html-imposters.py` read
# IA-METADATA.json as if it were content and `crawl-gap-audit.py` did not, so the two returned
# different answers about the same tree. The set below is their union, which is the safe
# direction: a file wrongly called ours is left out of an index, a file wrongly called content is
# hashed and then reported as changed every time the bookkeeping is rewritten.
# ONE NAME PER FILE, AND ONE SPELLING OF EACH NAME. These strings appeared as literals in 13 to
# 19 files apiece -- ".sha256sum" 70 times, "PROVENANCE.md" 122 -- and as named constants under
# four different names in four files. Two of those names COLLIDED: `INDEX_FILE` meant
# ".mirror-index.csv" in one file and "collection-index.csv" in another, and `SUMS_FILE` the
# same, so a reader who knew one meaning was wrong about the other tree.
COMPLETE_MARKER = ".mirror-complete"        # a run finished with nothing outstanding
INDEX_FILE = ".mirror-index.csv"            # per archive: path, size, mtime, sha256
SUMS_FILE = ".sha256sum"                    # the same digests in sha256sum(1) format
# THE THREE WEAKER MANIFESTS, written beside the sha256 one and never instead of it. Each exists
# because somebody ELSE speaks that algorithm and nobody speaks ours:
#
#   .sha1sum   Backblaze B2 records a SHA-1 per file (X-Bz-Content-Sha1)
#   .md5sum    the Internet Archive publishes md5 for every file and sha256 for none
#   .sfv       RAR and ZIP store a CRC32 per member, and .sfv is what carries one on disk
#
# THE NAMES ARE THE TOOLS' OWN, not ours. `sha1sum -c .sha1sum` and `md5sum -c .md5sum` work
# unchanged, and OpenHashTab, QuickSFV and TeraCopy read all three without being told anything.
# An archive that outlives these scripts is still verifiable with what a system already has, which
# is the whole point of writing a standard format rather than a fourth column.
SHA1_FILE = ".sha1sum"
MD5_FILE = ".md5sum"
SFV_FILE = ".sfv"                           # CRC32; there is no crc32sum(1), .sfv is the format
# algorithm -> the file that carries it. One table, so a caller cannot pair them by hand wrongly.
MANIFEST_FILES = types.MappingProxyType({
    "sha256": SUMS_FILE, "sha1": SHA1_FILE, "md5": MD5_FILE, "crc32": SFV_FILE,
})
# Per archive: the paths a URL-LIST fetch asked for and the server answered 404 or 410 to.
# Measured 2026-10-02: images/dcsscr4.gif had been asked for THREE TIMES across three sessions
# and answered the same way each time. A 404 creates no file, so the path stays "absent", and a
# list built by diffing names against the tree names it again every session. Worse than the waste
# -- the dead names sort to the FRONT of these lists (dcss*, sna*), so they are the first requests
# a session spends, at a host that grants a session only a few dozen.
GONE_FILE = ".mirror-gone"
# THE TWO STATUSES THAT MEAN "THIS SOURCE DOES NOT HAVE IT", and deliberately not mirror.py's
# PERMANENT, which also holds 401 and 403. Those two say we may not HAVE it, which is a different
# fact and one a configuration change can reverse; writing them into a gone-record would turn a
# permissions decision into a claim about existence.
GONE_STATUS = frozenset((404, 410))
# A SOURCE SAYING NO IS NOT A SOURCE SAYING GONE, and until 2026-10-04 the second kind of
# answer had nowhere to live. Six paths in this collection are permanently refused:
#
#   technologists-sauer  asgchs91.rm, songs/zekeswaltz.mp3, songs/zekeswaltz.html   403
#   typewritten          Manual/IBM/AIX/2.2.1/man2/sh .html                         403
#   fjkraan              comp/m10/guide                                             403
#   bretjohnson          forum                                                      500
#
# record_gone refuses all of them, correctly -- 403 and 500 say "we will not serve you
# this", which may stop being true tomorrow, and collapsing that into "gone" is the
# mistake read_gone's docstring exists to prevent. But a completeness check that reports
# them for ever is a check nobody can read, and converge.py spent one wasted round on each
# before its gain brake noticed.
#
# SO THEY GET THEIR OWN FILE rather than a widened GONE_STATUS. Widening would change the
# meaning of a record data has already been written against, and this register's rule for
# that is explicit.
REFUSED_FILE = ".mirror-refused"
# NAMES CHANGED TO BE STORABLE, AND WHAT THEY WERE. Four archives already carry one, written
# by extract-container-tar.py, and the format below is theirs rather than a new one: a header
# naming the reason and the source, then `<original>` and an indented `-> <on disk>` per pair.
# Readers exist; a second format would be a second opinion about what the tree holds.
RENAMED_FILE = "RENAMED.txt"
PROVENANCE_FILE = "PROVENANCE.md"           # where the archive came from, written by hand
CATALOGUE_FILE = "CATALOGUE.md"             # generated for the whole tree from the markers
# Placed at a tree's root by hand. It marks a directory as "this is the tree" for a bare run
# with no --root, and it is the one way to point a tool at a git working copy on purpose.
# Empty is fine; only its presence is read.
ROOT_MARKER = ".mirror-root"

# WHERE THE COLLECTION IS, in one place and nowhere else.
#
# This was `os.environ.get("MIRROR_ROOT", r"Q:\mirror")` written out in 27 files, plus a dozen
# more with the path as a bare literal. Forty places naming one drive is the same shape this
# library was created to end: ".sha256sum" appeared 70 times before it became a constant here.
#
# IT IS A PLAIN VARIABLE AND IT IS MEANT TO BE ASSIGNED. A tool builds its `--root` default from
# it when the parser is constructed, so anything that sets it first is obeyed:
#
#     import common
#     common.MIRROR_ROOT = r"D:\elsewhere"
#
# No environment variable, on purpose: a value that comes from outside the process is a value
# that differs between two terminals on the same machine, and a run whose root depended on which
# window it was started from is not a run anybody can reproduce from its own output.
MIRROR_ROOT = r"Q:\mirror"

# The pair a NON-mirror tree gets, which is why they are spelled out separately rather than
# derived: checksums.py indexes a directory that nobody mirrored, and those two files must not be
# confused with the per-archive ones above.
COLLECTION_INDEX = "collection-index.csv"
COLLECTION_SUMS = "collection.sha256sum"

# TWO SETS, AND THE DIFFERENCE IS NOT TIDINESS. Collapsing them into one looked obvious and
# would have been wrong, which is worth the six lines it takes to say why.
#
# OWN_FILES is what a COMPLETION MARKER'S COUNTS EXCLUDE, and it is frozen by data already on
# disk. RENAMED.txt and SYMLINKS.txt are just as much ours as the rest, and they are deliberately
# NOT in it: the extracted archives that carry them were counted WITH them, so widening this set
# would make four existing markers disagree with their own trees, for a reason nobody reading the
# diff could reconstruct. A definition that stored data was written against is not free to change.
OWN_FILES = frozenset({
    COMPLETE_MARKER,
    INDEX_FILE,
    SUMS_FILE,
    PROVENANCE_FILE,
    ".mirror-case-probe",       # written to test whether the volume folds case
    ".MIRROR-CASE-PROBE",       # the other spelling of the same probe
    ".inventory",               # a page list a source tool took as a note, not as content
    "IA-METADATA.json",         # an item's own record from its source, kept to re-check against
    # subset-refetch.py writes its leftovers INTO the archive they describe. This name is in the
    # NARROW set although the paragraph above forbids widening it, and the difference is a
    # measurement rather than a judgement. The rule there is that a definition stored data was
    # written against is not free to change: counted 2026-09-24, exactly one STILL-MISSING.txt
    # exists in the whole collection, written that day at 12:59, while the only marker in its
    # archive was written on 2026-09-11. No marker has ever been verified against a tree holding
    # this name, so excluding it restores agreement instead of breaking it -- the opposite of
    # RENAMED.txt. Leaving it out cost ardent-tool one file on its count and would cost one more
    # on every archive a subset run ever touches.
    "STILL-MISSING.txt",
    # fill-from-local.py writes this into the archive it filled: which files did NOT come from
    # the archive's own source, where each came from, its size and its SHA-256. Same shape as
    # PROVENANCE_FILE and EXTRACTED-FROM.md -- content ABOUT the archive, meant to be read.
    #
    # IN THE NARROW SET, and by the same measurement STILL-MISSING.txt above is: counted
    # 2026-09-27, exactly one FILLED-FROM.md exists in the whole collection, in vgamuseum-doc,
    # which has NO completion marker. Zero of the 107 markers on disk was written against a tree
    # holding this name, so excluding it cannot make one disagree with its own tree.
    "FILLED-FROM.md",
    # IN THE NARROW SET BY THE SAME MEASUREMENT AS THE TWO ABOVE, and it is the easiest case of
    # the three: the name is new as of 2026-10-02, so ZERO of the markers on disk was written
    # against a tree holding it, and excluding it cannot put a marker at odds with its own tree.
    GONE_FILE,
    # THE SIBLING OF GONE_FILE, new on 2026-10-04, so no marker on disk was written against a
    # tree holding it and excluding it cannot put one at odds with its own tree -- the same
    # measurement the three names above rest on.
    REFUSED_FILE,
    # THE SAME MEASUREMENT AS GONE_FILE ABOVE, and the same easy case: all three names are
    # new on 2026-10-02, so ZERO markers on disk were written against a tree holding them
    # and excluding them cannot put a marker at odds with its own tree. They must be in
    # the NARROW set: a manifest counted as content is hashed into the index and then
    # reported as changed every time the manifests are rewritten.
    SHA1_FILE,
    MD5_FILE,
    SFV_FILE,
})

# AND EVERY ONE OF THEM AGAIN WITH `.tmp`, because write_index writes `<name>.tmp` and then renames
# it -- and a run that dies between the two leaves the `.tmp` behind. On 2026-10-03 the
# collection-wide four-digest run died on exactly that step, with WinError 5, and left
# `ibm-redbooks/.mirror-index.csv.tmp` on disk. That file was in NEITHER set, so a marker and every
# auditor would have counted 331 KB of our own scratch as content in that archive.
#
# DERIVED RATHER THAN LISTED, so a manifest added later is covered by arriving. The suffix is NOT
# added to PARTIAL_SUFFIXES, which would have been the shorter change and the wrong one: a mirrored
# archive is free to contain a real file called something.tmp, and this collection exists to keep
# such files rather than to hide them. Only OUR OWN write targets are named here.  [2026-10-03]
# THE UNION IS TYPE-PRESERVING ON PURPOSE: `a | b` takes the type of the LEFT operand, so a
# frozenset stays frozen and -- if contract-mutations.py turns the literal above into a
# plain set -- the result stays MUTABLE and the guard still bites. Written as
# `frozenset(OWN_FILES | ...)` first, which re-froze the mutation and silently turned the
# rule "an exported set made mutable again" into decoration. The mutation report caught it
# the same minute, which is the whole reason that script exists.
OWN_FILES = OWN_FILES | frozenset(name + ".tmp" for name in OWN_FILES)

# BOOKKEEPING_FILES is what a tool may skip when it only wants CONTENT -- an auditor, a lister, a
# duplicate hunter. It is a superset, and being wider is the safe direction here: a file wrongly
# skipped is one an auditor does not report on, while a file wrongly read as content is hashed
# and then reported as changed every time the bookkeeping is rewritten.
#
# EIGHT TOOLS EACH KEPT THEIR OWN VERSION AND NO TWO AGREED -- 0 identical pairs out of 28,
# measured 2026-09-22. One read IA-METADATA.json as content and another did not, so the two
# returned different answers about the same tree.
BOOKKEEPING_FILES = frozenset(OWN_FILES | {
    CATALOGUE_FILE,             # generated for the whole tree from the markers
    ROOT_MARKER,                # marks a directory as a mirror root
    "RENAMED.txt",              # names changed to be storable, and what they were
    "SYMLINKS.txt",             # links the source had and a copy cannot
    "EXTRACTED-FROM.md",        # this tree was unpacked from that archive
    # WHICH FILES A FRAGMENT-COPY REMOVAL TOOK, and why each was the same document as its
    # neighbour. Added 2026-10-02, when the tool's own docstring was found to call it "the same
    # reasoning as RENAMED.txt beside an extracted tree" while the name was in NEITHER set -- so it
    # was being counted as content by every auditor. Four archives carry one: ardent-tool,
    # gsi-collection, ibm-aix and ps-2.kev009.com.
    #
    # THE WIDE SET ONLY, exactly like RENAMED.txt above it, and that choice is what makes this safe
    # to add today. iter_tree and therefore every marker skip the NARROW set; putting the name
    # there would move four markers by one file each, and the four were rewritten from the tree
    # hours ago and agree with it. Here it changes what an auditor reads and nothing a marker
    # claims.
    "FRAGMENT-COPIES-REMOVED.txt",
    # EMPTY-CASE-TWINS-REMOVED.txt -- the same shape of record for the same shape of mistake, and
    # it was missing from this set for about an hour on 2026-10-05, which `mirror.py --verify`
    # caught immediately: the file sat on disk, outside the index, and read as unindexed content.
    #
    # WHAT IT RECORDS. A case-insensitive server answers two spellings of one URL as one resource;
    # this crawler followed both and one arrived EMPTY. 56 such files across ibiblio-historic-linux,
    # ibm-aix and somuchstuff-pdp8. They had to go because Rar.exe stores only ONE of two paths
    # differing in case, without saying which -- so an empty twin could have displaced 348 631
    # bytes on the way to cold storage. Wide set only, exactly like the three names below it.
    "EMPTY-CASE-TWINS-REMOVED.txt",
    # CASE-DIRS-MERGED.txt -- two directories whose names differed only in case, put into one.
    # Windows cannot hold both and WinRAR silently halves them, so the collection has to become
    # something Windows can hold. 14 merges across 6 archives on 2026-10-05, 460 files moved, the
    # FIRST name in sorted order keeping its name every time -- which is why ardent-tool's 157-file
    # `PS55/docs` moved into its 1-file `PS55/Docs`. Wide set only, like the records above it.
    "CASE-DIRS-MERGED.txt",
    # HOW-THIS-ARRIVED.md -- the provenance note beside a marker whose own figures are true but
    # whose `duration` hides the work. dreamlandbbs-os2 has the first: its crawl took three
    # minutes because twelve hours of fetching across six rounds came first, and that history
    # belongs somewhere a reader of the marker will find it. Wide set only, like the two above,
    # so an auditor skips it while the marker still counts it -- which is the collection's
    # convention for an archive's hand-written notes.  [2026-10-03]
    "HOW-THIS-ARRIVED.md",
    # THE ROUNDS converge.py NEEDED, written into the archive it closed. Same shape and same
    # set as the two names above, and registered here because the test for the new tool
    # asserted it and failed -- which is the third time a record file has been introduced
    # without a home. The wide set only, so an auditor skips it while the marker counts it.
    "CONVERGED.md",
    "SHA256SUMS",               # written by the one-off fetchers, in sha256sum(1) form
})                              # STILL-MISSING.txt is inherited from OWN_FILES, see there


def record_renamed(archive_dir, original, stored, reason, source=None):
    """Append one name the tree could not hold and the name it was given. -> True if written.

    WHY A RENAME IS NOT A LOSS BUT AN UNRECORDED ONE IS. The bytes are kept either way; what goes
    without this file is the knowledge that the source called the file something else, and nobody
    can ask a question about a name they cannot see. extract-container-tar.py's own docstring puts
    it as "RENAMED.txt is not paperwork".

    ITS FORMAT IS extract-container-tar.py'S, not a new one. dec-ftp-2006 and three others already
    carry a RENAMED.txt in that shape and there are readers for it; inventing a second layout
    would be a second opinion about what the tree holds.

    THE CASE THIS WAS ADDED FOR, 2026-10-04. A source may serve BOTH `X` and `X/y` -- a listing
    page and the files it lists -- and a filesystem may hold only one of them. Until today
    whichever arrived first won, which is why ps-2.kev009.com has `Harris` as a directory and had
    `Intel` as a 4 901-byte page that made 20 datasheets unstorable. The owner's decision is that
    FILES WIN and the page is stored beside them as `<name>.html`. That is a rename, and this is
    where it is written down.
    """
    if not original or not stored or original == stored:
        return False
    path = os.path.join(archive_dir, RENAMED_FILE)
    fresh = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline=chr(10)) as fh:
        if fresh:
            fh.write("# Names changed because NTFS cannot hold them. Original -> on disk." + chr(10))
            fh.write("# Source: %s" % (source or "fetched by url") + chr(10) + chr(10))
        fh.write("%s%s  -> %s   (%s)%s" % (original, chr(10), stored, reason, chr(10)))
    return True


def read_refused(archive_dir):
    """-> {relative path: (date, status)} from the archive's REFUSED_FILE.

    THE SIBLING OF read_gone, and the difference is the whole point: that one holds answers that
    mean "this is not here", this one holds answers that mean "we will not give it to you". Both
    stop a path being asked for by default and neither hides it -- the date is in the file so a
    later run can decide the answer is stale.
    """
    out = {}
    path = os.path.join(archive_dir, REFUSED_FILE)
    if not exists(path):
        return out
    with io.open(long_path(path), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 2)
            if len(parts) != 3:
                continue
            when, status, rel = parts
            try:
                out[rel] = (when, int(status))
            except ValueError:
                continue
    return out


def record_refused(archive_dir, rel, status, when=None):
    """Append one path the source refuses, with the status it refused with. -> True if written.

    ANY STATUS THE SOURCE ACTUALLY GAVE, deliberately wider than GONE_STATUS: 403, 401, 500, 451 --
    whatever a server said about this path rather than about the connection. What does NOT belong
    is a timeout or a DNS failure: those are our side of the wire or a host having a bad minute,
    and develooper-hpux answered 503 on one probe and 404 on the next, which is why that line is
    drawn here rather than left to the caller.
    """
    status = int(status)
    if status in GONE_STATUS or not 400 <= status < 600:
        # 404 AND 410 BELONG IN THE OTHER FILE, and anything outside the 4xx/5xx range is not a
        # refusal at all. Refusing to write is better than keeping two records of one fact.
        return False
    if rel in read_refused(archive_dir):
        return False
    path = os.path.join(archive_dir, REFUSED_FILE)
    fresh = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as fh:
        if fresh:
            fh.write("# Paths this archive's source REFUSED, the status it used, and the date.\n"
                     "# Not 404 -- that is .mirror-gone. These are answers of the shape 403, 401\n"
                     "# or 500: the file may well exist and this source will not serve it here.\n"
                     "# Re-askable on purpose; the date is what makes the answer stale.\n")
        fh.write("%s %s %s\n" % (when or time.strftime("%Y-%m-%d"), status, rel))
    return True


def read_gone(archive_dir):
    """-> {relative path: the date it was last answered 404} from the archive's GONE_FILE.

    WHAT THIS IS FOR. A url list is built by diffing names a page mentions against names on disk.
    A file the server no longer has fails that diff for ever: nothing arrives, so nothing changes,
    so the next list names it again. Three sessions in a row asked openpa.net for
    images/dcsscr4.gif and got three 404s, and those requests came out of a budget that runs to a
    few dozen -- the dead names sort to the front, so they were spent first.

    IT IS A NOTE, NOT A VERDICT, and the date is there to keep it one. This collection already
    learned what a closed question costs: LOST and FROZEN exist to stop anyone looking again, and
    recheck-decisions.py exists because a host comes back and nothing on disk changes when it
    does. So the record says WHEN, a caller may ignore it, and nothing here deletes or hides a
    name -- it only stops it being asked for by default.

    ONLY 404 AND 410 BELONG IN IT. Not a timeout, which says nothing about the file; not 403 or
    401, which say we may not have it rather than that it is gone -- and those can be switched off
    by the day's configuration. Collapsing any of them into "gone" is the exact mistake http_try's
    docstring exists to prevent, one level further on.
    """
    out = {}
    path = os.path.join(archive_dir, GONE_FILE)
    if not exists(path):
        return out
    with io.open(long_path(path), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # `<date> <status> <path>`; the path may hold spaces, the first two fields may not.
            parts = line.split(" ", 2)
            if len(parts) == 3:
                out[parts[2]] = parts[0]
    return out


def record_gone(archive_dir, rel, status, when=None):
    """Append one path the server answered 404 or 410 to. -> True if it was written.

    Appends rather than rewrites: the file is a log of answers and the DATES are the part a
    re-check needs. A path already in it is not written twice -- three identical lines would say
    nothing a single line plus its date does not.
    """
    if int(status) not in GONE_STATUS:
        return False
    if rel in read_gone(archive_dir):
        return False
    path = os.path.join(archive_dir, GONE_FILE)
    fresh = not exists(path)
    with io.open(long_path(path), "a", encoding="utf-8", newline="\n") as fh:
        if fresh:
            fh.write("# Paths this archive's source answered 404 or 410 to, and the date it did.\n"
                     "# NOT a statement that the bytes are gone from the world -- only that this\n"
                     "# source does not serve them. Re-askable on purpose; see read_gone().\n")
        fh.write("%s %s %s\n" % (when or time.strftime("%Y-%m-%d"), int(status), rel))
    return True


# DOES AN ARCHIVE BEGIN HERE? Either file answers yes, and two clients were each assembling this
# pair by hand. A completed archive carries the first; one still being fetched, or one whose root
# had to be marked for a tool that walks upward, carries the second. Asking for only one of them
# finds an archive in the state the asker happened to have in mind.
ARCHIVE_MARKERS = (COMPLETE_MARKER, ROOT_MARKER)


def archive_root(path, levels=6):
    """Walk upward from `path` to the directory an archive starts at, or None.

    OFFERED BECAUSE TWO TOOLS CLIMBED THIS BY HAND and stopped at different depths. `levels` is a
    bound rather than a rule: without one, a path outside any archive walks to the drive root and
    reports the first thing it finds there, which is a confident answer to a question nobody asked.
    """
    here = path
    for _ in range(levels):
        if any(isfile(os.path.join(here, m)) for m in ARCHIVE_MARKERS):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent
    return None

def is_own_file(name):
    """Does a completion marker's file count EXCLUDE this basename?

    The narrow question, and the one that must not change: see OWN_FILES. Use it when a number is
    going to be compared against a number already written down.

    Exact match, not a pattern. A pattern here would eventually claim a source file: names
    containing '#' taught that lesson already, where a rule keyed on one character would have
    removed over a thousand real names to reclaim nothing.
    """
    return name in OWN_FILES


def is_bookkeeping_file(name):
    """Is this basename something this collection wrote rather than copied?

    The wide question. Use it when the job is to look at CONTENT and our own files are merely in
    the way -- an audit, a listing, a duplicate hunt. Never use it to produce a count that will be
    compared against a marker; that is is_own_file()'s question and the two deliberately differ.
    """
    return name in BOOKKEEPING_FILES


# ------------------------------------------------------------------------------ formatting


_UNITS = (("TB", 10 ** 12), ("GB", 10 ** 9), ("MB", 10 ** 6), ("kB", 10 ** 3))


def human(n):
    """Bytes as a short decimal string: 1 kB is 1000 B, not 1024.

    DECIMAL BECAUSE THE DOCUMENTS ARE DECIMAL. CATALOGUE.md, every PROVENANCE.md and every
    completion marker report sizes in powers of ten; the bodies replaced here were split between
    the two conventions, and several divided by 1024 while printing "GB". A reader comparing a
    tool's output against a PROVENANCE figure was comparing two different quantities.
    """
    for unit, div in _UNITS:
        if abs(n) >= div:
            return "%.2f %s" % (n / float(div), unit)
    return "%d B" % n


def parse_size(text):
    """Read back what human() writes, and what a directory listing writes. -> int or None.

    Accepts `1.2M`, `1.2 MB`, `604M`, `12K`, `919216`, `-` and the empty string. Listings are
    written by whoever wrote the server, so this is deliberately forgiving about spacing and
    about whether the B is there -- but not about the unit letter, because guessing there is how
    a size ends up wrong by a factor of 1024.

    THE LISTING CONVENTION IS BINARY and human()'s is decimal, which looks like an inconsistency
    and is not: this reads what someone else wrote, that writes what we say. Apache's `1.2M`
    means 1.2 * 1024^2. Getting this backwards is how `1677721` came to be compared against an
    exact byte count and reported as a difference that did not exist.

    TWO SPELLINGS OF ONE CONVENTION, because two servers write it differently: Apache prints
    `25K`, lighttpd prints `772.8 KiB`. Both mean 1024. A reader that knows only one of them
    returns None for the other, and a size of None is what makes an ETA meaningless.

    OverflowError IS CAUGHT, AND IT IS NOT HYPOTHETICAL. A size column of a few hundred digits
    makes float() return inf and int(inf) raise. This is called from parse_listing(), which the
    crawler's producer thread invokes outside any handler of its own -- so an unparseable number
    in somebody's listing took the whole run down instead of meaning "no size".

    THE RESULT IS AS EXACT AS THE TEXT WAS, WHICH IS USUALLY NOT VERY. `1.1M` comes back as
    1 153 433 and the file is not 1 153 433 bytes -- the server printed two significant digits
    and this expanded them. Comparing that to an exact byte count reports differences that do not
    exist, which is a DIFFERENT mistake from the 1024 one above and was made here on 2026-09-24:
    225 files were called "not the same file" on the strength of a rounded number. Ask
    size_agrees() instead of comparing with ==.
    """
    if text is None:
        return None
    s = text.strip()
    if not s or s == "-":
        return None
    if s[-2:].upper() == "IB":               # KiB, MiB, GiB, TiB
        s = s[:-2].strip()
    elif s[-1:].upper() == "B":              # KB, MB, or plain bytes
        s = s[:-1].strip()
    mult = 1
    if s and s[-1] in "kKmMgGtT":
        mult = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "t": 1024 ** 4}[s[-1].lower()]
        s = s[:-1].strip()
    try:
        return int(float(s) * mult)
    except (ValueError, OverflowError):
        return None


# The smallest size several servers will print. Below it they do not say "240", they say `1k`,
# so a listed 1024 beside a 240-byte file is agreement and not a defect. Measured on penguinppc,
# whose Apache prints `1k` for every one of its 240-byte .sig files.
LISTING_FLOOR = 1024


def size_agrees(listed, actual):
    """Is this exact byte count consistent with the size a listing printed? -> True/False/None.

    None means the listing made no usable statement, and it is a THIRD answer rather than a
    False because the two are acted on differently: a caller hunting truncated downloads must
    report a mismatch and must not report a column it could not read.

    WHY THIS IS NOT `listed == actual`. A listing prints about two significant digits, so `1.1M`
    expands to 1 153 433 for a file of any size in that neighbourhood. Measured over 912 pairs
    where a stored index sits next to the files it describes: 13.0% matched exactly, 81.8% landed
    within half of the last printed digit, and 4.5% did not agree at all -- and reading that last
    group is what this function exists for. Among them:

        mozilla-0.8.0.0.exe   listing 38 063 308   on disk 7 488
        aixtools.php.5.3.20.0.I   listing 44 040 192   on disk 113 595

    Those are not rounding. A file that stops at 7 488 bytes where the server promised 38 MB is a
    download that was cut off, and it is invisible to every check that compares the tree against
    its own recorded hash.

    THE FLOOR IS THE PART THAT LOOKS LIKE A BUG. Some servers never print below `1k`, so a
    240-byte signature is listed as 1024. Both sides under LISTING_FLOOR therefore means "no
    statement", not "wrong by 784 bytes" -- without it, 27 intact signature files on penguinppc
    were reported as damaged.

    THE TOLERANCE IS ONE WHOLE PRINTED DIGIT, not half of one, because servers disagree about
    rounding versus truncating and the cost is asymmetric: a false alarm sends somebody to read a
    file that is fine, while being generous only loses mismatches smaller than the column can
    express -- which no reader could have confirmed from the column anyway.
    """
    if listed is None or actual is None:
        return None
    if listed == actual:
        return True
    if listed <= LISTING_FLOOR and actual <= LISTING_FLOOR:
        return None
    return abs(actual - listed) <= listing_step(listed)


def listing_step(listed):
    """-> the granularity a listing printed at, inferred from the value it printed.

    The column keeps no record of its own precision, so this reads it back out of the number: a
    value that is an EXACT MULTIPLE of its unit came from a column with no decimal place (`1k`,
    `449k`, `42M`) and is only good to the whole unit; anything else carried a tenth (`3.3K`,
    `1.1M`) and is good to a tenth. A value under 1024 was printed in bytes and is exact, so the
    step is 0.

    READING IT OFF THE MAGNITUDE INSTEAD WAS WRONG, and the mirror said so: `1k` beside a
    1 135-byte ChangeLog was reported as a discrepancy because 1024 is under ten kilobytes and
    was therefore assumed to be `1.0K`. Ten of twelve "contradictions" in the first pass were
    that one mistake, on a server that truncates to whole k and never prints a decimal.
    """
    for unit in (1024 ** 4, 1024 ** 3, 1024 ** 2, 1024):
        if listed >= unit:
            return unit if listed % unit == 0 else unit // 10
    return 0




# ------------------------------------------------------------------------------------ urls
#
# ABSTRACT ON PURPOSE. Nothing here knows about a particular archive, a particular run or a
# particular collection. Each rule carries the reason it is the rule and, where one helps, the
# ONE URL at which the case was first met; what was lost that day, how many files and how many
# gigabytes, belongs beside the archive it happened to -- see mirror.py.
#
# EVERY BEHAVIOURAL CLAIM BELOW HAS A CASE IN common_test.py. The rules are executable there, so
# a change that contradicts one fails the suite rather than a crawl.

# Extensions a cache-buster may be stripped from. DELIBERATELY NARROW: see strip_cache_buster.
STATIC_IMAGE = (".gif", ".jpg", ".jpeg", ".png", ".bmp", ".svg", ".webp", ".ico", ".tif",
                ".tiff", ".xbm", ".pcx")

MAX_DEPTH_BELOW_BASE = 24
MAX_CONSECUTIVE_REPEATS = 2


# TWO ANSWERS TO "IS THIS A PAGE", AND THE LIBRARY OFFERS BOTH RATHER THAN CHOOSING.
#
# The name promises a DOCUMENT. Every one of these is a file whose content is markup, or a
# preprocessor that emits markup and nothing else.
#
# THE SET IS PART OF A DEFECT, NOT A DETAIL, and mirror.py's crawler paid for that twice before
# the decision moved here. It carried a pattern of its own, `\.s?html?$`, which knew .html, .htm
# and .shtml only:
#
#   sun3arc.org writes every one of its 134 pages as **.phtml**, so each was SAVED and never
#   WALKED -- 878 links and 318 <img src> lying on disk, none followed. The run reported COMPLETE
#   with zero failures, because the SEEDS had opened the directories and the listings covered the
#   linked files; only the 213 embedded images had no second route, and nothing counts what was
#   never looked at. Eighth defect of that shape. [2026-09-11]
#
#   `.php` cost the same lesson one extension further out. so-much-stuff.com is hand-written .php
#   pages linking into an Apache tree, and its ENTIRE front page is the single link
#   /pdp8/index.php -- without walking that, the archive is one file. It is also why that site has
#   no Wayback snapshots: crawlers do not descend through the indirection either. [2026-09-13]
#
# `.shtm`, `.xhtm`, `.phtm`, `.xht` and `.php3` are here as PRECAUTION. They hold zero files in
# this collection and cost nothing to carry. Measured over all 9 255 290 hrefs on 2026-09-23:
# `.xht` is not even LINKED; `.php3` is linked six times, all six at other hosts. They are
# carried so the next defect of that shape is not another spelling of markup -- an extension
# nobody could mistake for anything else is cheaper to carry than to find.
#
# `.php4` IS NOT PRECAUTION. It is here because leaving it out already cost somebody an archive.
# [2026-09-23]
#
# bitsavers' 2007 capture of www.hpl.hp.com saved the nine `.php4` pages that index.html links
# and did not follow the links OUT of them. Everything one level down is absent from the tar, and
# `hp-labs-linux-salvage` exists to hold the 22 of 24 the Internet Archive could still give back.
#
# WHAT MAKES THIS EXTENSION WORSE THAN THE OTHERS is how it hides. Of the 1 206 in-scope links
# pointing at a `.php4` page in this collection, 1 169 are THEMSELVES on a `.php4` page. A
# crawler that does not walk the extension enters through the one link from index.html and sees
# nothing after it -- the spelling conceals itself, and the run ends COMPLETE with no failures.
# 119 files in two archives today, neither of them HTML_CRAWL, so this changes no run now.
DOCUMENT_EXTENSIONS = (".html", ".htm", ".shtml", ".shtm", ".xhtml", ".xhtm",
                       ".phtml", ".phtm", ".xht", ".php", ".php3", ".php4")

# The name promises a PROGRAM that serves a page. Whether one is worth following is a judgement
# about the site, not about the file: a `.cgi` may be the only route into a tree, or it may be a
# form that answers the same page to every request.
#
# Measured 2026-09-23 over the whole collection: EIGHT files in four archives, against 288 636
# that the document set already covers. Small enough that neither answer is obviously right,
# large enough that it is not nothing.
PROGRAM_PAGE_EXTENSIONS = (".asp", ".aspx", ".jsp", ".cgi")

# Everything that serves a page, either way.
#
# NOT the same question as MARKUP_EXTENSIONS below: that one asks whether markup is EXPECTED in a
# file of this name, so it holds .css, .js and .xml, and a file of those kinds that contains HTML
# is not news. This asks whether there are links inside worth following.
PAGE_EXTENSIONS = DOCUMENT_EXTENSIONS + PROGRAM_PAGE_EXTENSIONS

# WHERE MARKUP IS NOT NEWS -- a page extension, or one of the text formats that is markup by
# definition. Two tools need the complement of this: find-html-imposters.py reads everything
# OUTSIDE it (markup under one of those names is a file wearing somebody else's extension) and
# its --pages half reads everything INSIDE it (a page whose own title announces a failure).
#
# DERIVED FROM PAGE_EXTENSIONS AND NOT TYPED OUT, and that is the whole reason it is here. This
# list lived in find-html-imposters.py until 2026-09-27 and had drifted in BOTH directions. The
# .css/.js/.xml direction is deliberate and is the note above. The other direction was not: the
# tool's copy was missing `.php4`, `.phtm`, `.shtm` and `.xhtm`, four spellings of "page" the
# library already knew about -- so an HTML file named `x.php4` was reported as an imposter, and a
# real error page under `.php4` was not scanned at all. Both wrong, in opposite directions, from
# one omission.
#
# `.php4` IN PARTICULAR is the extension whose absence has already cost this collection an
# archive -- see the note above DOCUMENT_EXTENSIONS. Deriving the set means no future copy of it
# can leave that out again.
MARKUP_EXTENSIONS = PAGE_EXTENSIONS + (
    # Markup or structured text by definition: a file of this kind CONTAINING markup is what it
    # is for, so it can never be an imposter.
    ".css", ".js", ".xml", ".xsl", ".xsd", ".svg", ".rss", ".atom", ".rdf",
)


def looks_like_a_document(name):
    """-> True if this name promises MARKUP: a file to open, follow, and expect HTML from.

    THE NARROWER OF THE TWO. Use it where following the wrong thing has a cost the caller bears
    on somebody else's behalf -- a crawler asking a stranger's server for a `.cgi` may be asking
    it to run a program, which is not the same favour as asking for a file.

    A superset of what mirror.py's crawler has followed since it was written, so nothing it walks
    today would stop being walked.
    """
    return name.lower().endswith(DOCUMENT_EXTENSIONS)


def is_extension_only(href):
    """-> True if the last segment is a bare extension with NO STEM: `.html`, `dir/.htm`.

    NOT A FILENAME, and six links in this collection are exactly this shape -- typewritten's
    `Manual/IBM/AIX/2.2.1/man1/.html` and `man5/.html`, seds-frommert's `spider/OS2/HPFS/.html`
    and two siblings. Every one answers 403, which is a server declining to discuss a path rather
    than saying it is absent, so record_gone cannot hold them and a completeness check reported
    them for ever.

    THE SAME REASONING AS remove-fragment-copies.py'S FIRST TEST, written out there as "the part
    before the first '#' is NOT empty -- `#System_FW` has no stem; it IS the name". Here the part
    before the extension is empty, so what is left is not a name with an extension but an
    extension with nothing in front of it. A page generator emitting `<a href=".html">` is the
    likely origin; the register's own pages show it next to thousands of ordinary links.

    DELIBERATELY NARROW. A dotfile IS a name -- `.htaccess`, `.bashrc`, `.mirror-gone` -- and the
    test is not "starts with a dot". It is "the whole last segment is a dot followed by a known
    page extension and nothing else", which no real file in 1.8 million was found to match.
    """
    last = (href or "").rstrip("/").rsplit("/", 1)[-1]
    if not last.startswith(".") or last.count(".") != 1:
        return False
    return ("x" + last).lower().endswith(PAGE_EXTENSIONS)


def looks_like_a_page(name):
    """-> True if this name serves a page at all, document or program.

    THE WIDER OF THE TWO, and the right default for a tool reading files ALREADY ON DISK: there
    the cost of opening one more is a moment, and the cost of skipping one is a branch of the
    tree nobody ever looks at again.

    BY NAME, NOT BY CONTENT -- looks_like_html() answers the same question from the first bytes,
    and is the one to use when the bytes are already in hand. This one decides whether to spend a
    request or an open() at all.

    A name with NO extension is not decided by either: it may be a directory, a script or a file
    somebody forgot to name, and only the caller knows which of those its tree contains.
    """
    return name.lower().endswith(PAGE_EXTENSIONS)


# What somebody appended to a page's name to keep an older copy of it, or what a server put
# there. Matched at the END, after the page name: `x.html.~1~`, `x.html~`, `index.html@S=A`.
#
# THE UNDERSCORE FORM IS THE SAME THING AND WAS MISSING. A fetcher that will not put `@` in a
# filename writes Apache's column links as `index.html_D=A` instead, and this collection holds
# both spellings: measured 2026-09-24, **63 456** of `next-68k-org`'s 78 720 `.orig` files are
# `index.html_{C,D,M,N,S}={A,D}` with an optional `;O=x`, in exactly 17 distinct forms and no
# others. Only 114 `.orig` files in the whole collection are a backup of something else.
#
# Kept narrow on purpose -- a single letter, `=`, a short value -- because `_` is an ordinary
# character in a filename and a loose rule here would excuse real names.
BACKUP_TAIL = re.compile(r"(\.~\d+~|~|@[^/]*|_[A-Za-z]=[A-Za-z0-9]+(;[A-Za-z]=[A-Za-z0-9]+)*)$")


def looks_like_a_copy_of_a_page(name):
    """-> True if this is a COPY of a page rather than a new spelling of markup.

    THE QUESTION A REPORT OF UNWALKED PAGES HAS TO ANSWER. `page-extensions.py` looks for stored
    files that hold links under a name nothing walks -- that is how sun3arc's 134 `.phtml` pages
    sat unread while the run reported COMPLETE. But most of what it finds is not that: a backup
    of a page holds the same links as the page beside it, so nothing was missed, and a listing
    saved under its own sort order is the same listing. Those rows drowned the real ones and kept
    the tool out of the gates.

    A SHAPE, NOT A LIST OF EXTENSIONS. The obvious fix was to name `.orig`, `.bak`, `.old`,
    `.new`, `.save`, `.~1~` and whatever turns up next, which is a list that is wrong the first
    time somebody writes `.html.keep`. What every one of them has in common is structural:
    **take the suffix off and a page name is left.** `fetch.html.new` -> `fetch.html`;
    `index.html@S=A` -> `index.html`; `b.html.~1~` -> `b.html`.

    A NAME THAT IS ITSELF WALKED IS NOT A COPY, and getting that backwards would have been the
    bad direction: `x.phtml` strips to `x`, but it never reaches the stripping because it is a
    page in its own right. Answering True for it would have excused the exact defect this whole
    tool exists to find.
    """
    if looks_like_a_page(name) or looks_like_a_document(name):
        return False
    # PEELED IN A LOOP, NOT IN TWO FIXED STEPS. `index.html_D=A.orig` needs the suffix off first
    # and the sort order second, and the first version did them in the other order and answered
    # False for all 63 456 of them. Each turn removes ONE thing -- a backup tail or one extension
    # -- and asks again, which is what "take the suffix off and a page name is left" actually
    # means when somebody took two suffixes off.
    stem = name
    for _ in range(4):
        shorter = BACKUP_TAIL.sub("", stem)
        if shorter == stem:
            shorter = stem.rpartition(".")[0]
        if not shorter or shorter == stem:
            return False
        stem = shorter
        if looks_like_a_page(stem) or looks_like_a_document(stem):
            return True
    return False


def strip_fragment(href):
    """`page.html#anchor` -> `page.html`.

    A fragment names a position INSIDE a document, never a document. A crawler that keeps it
    asks the source for the same bytes once per anchor and stores each answer under its own
    name, so one page becomes as many identical files as it has anchors.
    """
    return href.split("#", 1)[0]


def strip_cache_buster(href):
    """`photo.gif?v=3` -> `photo.gif`. FOR AN EMBEDDED IMAGE ONLY, and only for image names.

    is_child_link() rejects every href carrying a query, which is right for a LINK: on a
    generated index a query is a sort order, and following those walks one directory once per
    column. Applied to an <img src> the same rule throws the picture away, because a cache-buster
    is decoration on a name that is otherwise complete.

    THE EXTENSION TEST IS THE WHOLE SAFETY MARGIN. A query is not always decoration -- `img.php?
    id=5` and `thumb.cgi?f=x` name a DIFFERENT picture per query, and stripping there would fetch
    one file and call it every image on the page. So the query is dropped only when the part
    before it already ends in a static image extension, where it cannot be selecting anything.
    """
    if "?" not in href:
        return href
    head = href.split("?", 1)[0]
    return head if head.lower().endswith(STATIC_IMAGE) else href


def is_child_link(href, allow_up=False):
    """Might this href point into the tree being copied? The caller decides for certain.

    THE WEAKER OF TWO GUARDS, on purpose. What actually keeps a crawl inside a tree is testing
    the RESOLVED url against the base, after urljoin. This one only drops what cannot possibly be
    useful, and every attempt to make it stricter has cost more than it saved -- a rejection here
    is invisible, because the link simply never appears in any count.

    Dropped unconditionally:

      a query           on a generated index it is a sort order, not a file
      protocol-relative almost always a third party; urljoin would keep OUR scheme and produce a
                        plausible-looking off-site url
      data:, mailto:, javascript:, tel:, about:, file:
                        things that were never on any server

    THE COLON IS THE WHOLE DISTINCTION in that last group, and a prefix test that forgets it
    drops real subtrees: `datasheets/`, `telnet-howto.html`, `about.html`, `filesystem-howto.html`
    and `mailtool.txt` are ordinary names.

    AN ABSOLUTE PATH IS ALLOWED THROUGH. It looks like a generated index's "Parent Directory"
    link and usually is not: a hand-written page may address its whole tree from the root. One
    that resolves outside the base is dropped by the caller, so nothing is gained by refusing it
    here.

    `allow_up` DOES THE SAME FOR '..' AND FOR A FULLY-QUALIFIED URL, and a crawl of hand-written
    HTML needs both. Such a page may navigate up two levels and back down into a sibling --
    resolving well INSIDE the base -- and may link its own files with the host spelled out. On a
    GENERATED index neither is true, which is why it is a flag and not the default.
    """
    if not href or href.startswith(("?", "#")):
        return False
    if href[:11].lower().startswith(("data:", "mailto:", "javascript:", "tel:", "about:",
                                     "file:")):
        return False
    if href.startswith("//"):
        return False
    if "://" in href and not allow_up:
        return False
    if href.startswith("..") and not allow_up:
        return False
    if "?" in href:
        return False
    return True


def content_root(archive_dir, base):
    """-> the directory inside `archive_dir` that `base`'s paths are relative to.

    MOST ARCHIVES ANSWER WITH archive_dir ITSELF. Four do not: a wayback salvage and a multi-host
    fetch write `<host>/<path>`, so the tree carries a HOST DIRECTORY LEVEL that the registered
    base says nothing about.

        aixpdslib        aixpdslib.seas.ucla.edu/ + ftp.aixpdslib.seas.ucla.edu/
        bullfreeware     bullfreeware.com/ + gnome.bullfreeware.com/   (base says www.)
        ibm-openxl-docs  ibm.com/                                      (base says www.)
        techsysadm       techsysadm.blogspot.com/ + blogger.googleusercontent.com/

    WHAT IT COST, 2026-10-04. techsysadm's completeness check reported 402 paths outstanding. It
    mapped `https://techsysadm.blogspot.com/2025/09/x.html` to `<archive>/2025/09/x.html` while the
    file is at `<archive>/techsysadm.blogspot.com/2025/09/x.html`. 199 of those 203 pages were
    HELD. Four were genuinely absent, and a check wrong by a factor of fifty is a check that
    cannot be used to decide whether an archive may be frozen.

    EVIDENCE AND NOT CONFIGURATION, which is looks_like_mirror_root's reasoning in this file
    already: the directory either exists or it does not, and a register table would have to be
    maintained for every future salvage. BOTH SPELLINGS ARE TRIED because the salvage writes the
    host it actually fetched -- bullfreeware is registered on `www.bullfreeware.com` and the tree
    says `bullfreeware.com`.

    A DIRECTORY THAT MERELY SHARES THE NAME IS NOT A TRAP: the name has to be the base's own host,
    so an archive holding a `www.example.com/` subtree of somebody else's site is unaffected
    unless that is also its base.
    """
    host = urllib.parse.urlsplit(base).hostname if base else None
    if not host:
        return archive_dir
    bare = host[4:] if host.startswith("www.") else host
    for candidate in (host, bare, "www." + bare):
        if candidate and os.path.isdir(os.path.join(archive_dir, candidate)):
            return os.path.join(archive_dir, candidate)
    return archive_dir


def site_prefixes(base):
    """-> every spelling of `base` that means the same site, longest first.

    TWO TOOLS FOUND THE SAME BUG IN ONE DAY, which is why this is in the library and not in either
    of them. A page or a sitemap names its own files with a spelling the register did not use, a
    plain `startswith` reads that as a foreign host, and the result is a CLEAN ZERO -- the answer
    this collection distrusts most, because it looks like a finding.

      find-sitemaps.py, 2026-10-02   ardent-tool is registered as https://ardent-tool.com/ and its
                                     sitemap writes https://www.ardent-tool.com/ -- all 2430
                                     entries counted OUTSIDE THE BASE, the archive reported as
                                     MISSING 0. A clean bill of health from comparing a site with
                                     itself and finding no overlap.
      pages-to-urllist.py, same day  a page writing https where the base says http had its own
                                     files counted as somebody else's.

    THE APEX AND `www.` ARE DIFFERENT NAMES AND THE SAME SITE. recheck-decisions.py's docstring
    already says so for a different purpose -- `crynwr.com` resolves while `www.crynwr.com` does
    not -- so one spelling existing says nothing about the other. The scheme is folded for the
    neighbouring reason: a site that moved to https still carries http links, or the reverse.

    LONGEST FIRST, so a caller cutting a prefix off a url cuts at the DEEPEST spelling that
    matches. Against a base of `/` and a base of `/a/` for the same host, the shorter one would
    otherwise win and leave `a/` glued to the front of every relative path.

    WHAT IT DOES NOT DO is guess at other hosts. A mirror served under two unrelated names is a
    fact about that mirror, and belongs in the register where somebody wrote it down.
    """
    parts = urllib.parse.urlsplit(base)
    hosts = {parts.netloc}
    hosts.add(parts.netloc[4:] if parts.netloc.startswith("www.") else "www." + parts.netloc)
    out = {urllib.parse.urlunsplit((scheme, host, parts.path, "", ""))
           for scheme in ("http", "https") for host in hosts}
    return tuple(sorted(out, key=len, reverse=True))


def under_site(url, base):
    """-> the path of `url` below `base` when it is the same site, else None.

    The companion to site_prefixes: one call instead of a loop every caller writes again. None and
    the empty string are different answers -- `base` itself gives "", a foreign host gives None --
    so a caller can tell "the site's own root" from "not this site" without re-testing.
    """
    for prefix in site_prefixes(base):
        if url.startswith(prefix):
            return url[len(prefix):]
    return None


def same_path_plus_slash(url, final):
    """True when `final` is `url` with a trailing slash added -- IGNORING an http/https flip.

    This is the "that is a directory, not a file" test. A redirect onto the same path plus a
    slash is the server saying so, and the body that arrives after the client follows it is the
    directory's own index page, about to be written under the directory's name.

    THE SCHEME HAS TO BE IGNORED. A server whose ServerName carries no https answers an https
    request with an http Location, and a comparison of whole strings fails on that while looking
    exactly right. The cost is not the one page: a directory stored as a file then blocks
    everything beneath it on every later run.

    Host and path still have to match. A redirect to a DIFFERENT place is a different question
    and is none of this function's business.
    """
    a = urllib.parse.urlsplit(url)
    b = urllib.parse.urlsplit(final)
    return (a.netloc == b.netloc and b.path.endswith("/")
            and b.path.rstrip("/") == a.path.rstrip("/"))


def looks_like_a_loop(url, base_url):
    """-> a reason to refuse this url, or None. Catches a symlink cycle seen over HTTP.

    A directory holding a link back into itself is not a cycle over HTTP. It is an infinitely
    deep tree of urls that are every one of them NEW:

        tools/less/xemacs/
        tools/less/xemacs/xemacs/
        tools/less/xemacs/xemacs/xemacs/            ... and so on

    A `seen` set cannot help. It holds visited urls, and none of these is ever visited twice: the
    crawler is not going in circles, it is walking forward forever, fetching the same files again
    at each level. Nothing fails, nothing retries, and the only symptom is that the run does not
    end. (Met at ftp.funet.fi/pub/unix/tools/less/; what it cost is recorded there.)

    TWO RULES, because each catches what the other misses.

    A REPEATED SEGMENT is the signature and is nearly conclusive: `a/b/b/b/` means something
    points at its own parent. Two in a row is allowed, because `doc/doc/` and `bin/bin/` do
    occur; three is refused. This fires at depth 3 rather than at the cap, so almost nothing is
    fetched before the loop is recognised.

    A DEPTH CAP is the backstop for cycles that rule does not describe -- `a/b/a/b/a/b/`, or a
    chain of differently-named links that happens to close. It has to be generous, because real
    archives nest hard, and it is a refusal of last resort rather than a policy about depth.

    Both refusals are the caller's to log and count. A crawl that stops early without saying so
    is worse than one that does not stop.
    """
    if not url.startswith(base_url):
        return None
    rel = url[len(base_url):].strip("/")
    if not rel:
        return None
    parts = [p for p in rel.split("/") if p]
    run = 1
    for i in range(1, len(parts)):
        if parts[i] == parts[i - 1]:
            run += 1
            if run > MAX_CONSECUTIVE_REPEATS:
                return ("path segment %r repeats %d times in a row -- a link that points at its "
                        "own parent" % (parts[i], run))
        else:
            run = 1
    if len(parts) > MAX_DEPTH_BELOW_BASE:
        return ("%d path segments below the base URL, limit is %d -- refusing rather than "
                "descending into what is probably a cycle" % (len(parts), MAX_DEPTH_BELOW_BASE))
    return None


def local_path(root, base_url, url):
    """Map a url under base_url onto a path under root, one url segment per directory.

    The url is UNQUOTED first, so `%20` becomes a space and the stored name is what the source
    calls the file rather than what HTTP needed to say it. Empty, `.` and `..` segments are
    dropped: they cannot name a directory, and `..` is the one that would escape `root`.

    Each segment is passed through safe_name() and NOTHING ELSE. No case folding, no stripping of
    trailing dots or spaces, no normalisation -- those names belong to the source, and a name a
    filesystem finds awkward is long_path()'s problem, not this one's.
    """
    rel = urllib.parse.unquote(url[len(base_url):])
    parts = [safe_name(p) for p in rel.split("/") if p not in ("", ".", "..")]
    return os.path.join(root, *parts)




# ------------------------------------------------------------------------------------ text


def say(msg, log=None, stream=None):
    """Print a line that CANNOT KILL THE RUN, and record it verbatim if a log is open.

    THE SCREEN AND THE RECORD GET DIFFERENT TEXT, ON PURPOSE. A Windows console is cp1252, and a
    name this collection genuinely holds -- a Japanese driver index, measured on this machine --
    raises UnicodeEncodeError from a plain print() and takes the whole pass with it. Hours of
    hashing lost to a filename. So the screen gets whatever the console can encode, with the rest
    replaced; the log is opened as UTF-8 and gets the real characters, because that is the copy
    anyone will read afterwards.

    Four copies of this existed. Three did the logging and would have died on such a name; the
    fourth, in another file, did the encoding and could not log. The lesson did not travel between
    two files in the same directory, which is the whole argument for this one being here.

    `stream` and the log are both injectable so a test can read back what was written, on any
    platform, without owning the console.
    """
    out = stream if stream is not None else sys.stdout
    enc = getattr(out, "encoding", None) or "utf-8"
    out.write(msg.encode(enc, "replace").decode(enc, "replace") + "\n")
    try:
        out.flush()
    except ValueError:          # a stream a caller already closed is not worth a traceback here
        pass
    if log:
        log.write(msg + "\n")
        log.flush()

def plural(n, word, suffix="s"):
    """`3 files`, `1 file`. English only, and only regular plurals -- anything else is a caller's
    business, because a function that guessed would be wrong in a way nobody checks."""
    return "%d %s%s" % (n, word, "" if n == 1 else suffix)


# ------------------------------------------------------------------------------- manifests


# Directories that are never content, whichever tree they turn up in. Three tools each carried
# this one name; it is a fact about the tooling, not about any archive.
NEVER_CONTENT_DIRS = frozenset({"__pycache__"})


def find_manifests(target):
    """-> the manifest paths describing `target`, in a stable order.

    `target` may be a manifest itself, an archive, or a directory holding archives, and all three
    are asked the same way because a caller usually has a path from a command line and does not
    know which it is.

    WHAT IT DOES NOT DECIDE. It used to return a second value saying whether each manifest was a
    mirror's own index, which its one caller turned straight into "protected from deduplication".
    Where a manifest is is a FACT; what is protected is a DECISION, and a function that returns
    both invites the next caller to inherit a policy it never chose. The caller asks
    `os.path.basename(p) == INDEX_FILE` in one line and means it.

    Ordered: the top level first, in the order the three names are listed, then one level down
    alphabetically. Two runs over an unchanged tree therefore produce the same list, and a diff
    of two reports means something.
    """
    if isfile(target):
        return [target]
    if not os.path.isdir(target):
        return []
    found = [os.path.join(target, name)
             for name in (COLLECTION_INDEX, INDEX_FILE, SUMS_FILE)
             if isfile(os.path.join(target, name))]
    try:
        entries = sorted(os.listdir(target))
    except OSError:
        return found
    return found + [os.path.join(target, e, INDEX_FILE)
                    for e in entries if isfile(os.path.join(target, e, INDEX_FILE))]

def read_manifest(path):
    """-> [(relative path, size or None, sha256)] from a checksum index OR a sums file.

    TWO FORMATS, ONE READER, because the tools that consume them do not care which they were
    handed and the difference is one line of parsing.

    THE SUMS FORMAT IS `<64 hex> *<path>` -- ONE space and a star. sha256sum(1) writes a space and
    an asterisk in binary mode, two spaces in text mode, and both are accepted here because both
    occur in the wild. Splitting it wrong is not a parse error, it is a WRONG ANSWER: a reader
    that split on whitespace once reported "0 of 7 890 held" for a tree that held 7 871, because
    every path came back with a leading star and matched nothing.

    A SIZE THAT WILL NOT PARSE BECOMES None, NOT ZERO. Zero is a size -- an empty file is a real
    thing here -- and a caller that treats a missing figure as zero reports a tree as smaller than
    it is rather than as unmeasured.
    """
    rows = []
    if path.endswith((SUMS_FILE, COLLECTION_SUMS)) or path.endswith(".sha256sum"):
        with open(long_path(path), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if len(line) > 66 and line[64:66] in (" *", "  "):
                    rows.append((line[66:], None, line[:64].lower()))
        return rows
    with open(long_path(path), encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                size = int(r["size"])
            except (KeyError, TypeError, ValueError):
                size = None
            rows.append((r.get("path", ""), size, (r.get("sha256") or "").lower()))
    return rows


# ------------------------------------------------------------------------------------ http


def unverified_context():
    """An SSL context that does NOT authenticate the origin.

    For one case only: a host whose chain is incomplete -- the leaf validates but the issuer is
    not served -- so every stdlib client refuses it and there is no unencrypted way round.

    THIS IS A REAL LOSS, NOT A FORMALITY, and a caller that uses it owes the compensation: check
    that each response has the shape it should have, derive the file set from one listing rather
    than from guesses, and record a digest of everything retrieved. For credentials or executable
    content the trade is not available at all.
    """
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class Pacer:
    """Waits between two requests to the SAME host, and not between requests to different ones.

    WHY THIS IS IN THE LIBRARY. Measured 2026-09-25: **42 `time.sleep` calls across 18 tools**,
    and they are not the same thing written 42 times. Two shapes exist side by side --

        time.sleep(args.delay)                                  # most of them
        wait = delay - (time.monotonic() - last); sleep(wait)   # nginx-autoindex-gallery

    -- and only the second is what a delay MEANS. A Crawl-delay of 2 s is "do not hit me more
    often than every 2 s", not "spend 2 s idle after every request": a fetch that itself took
    1.9 s has already paid it. The blind form waits nearly twice as long as asked, which is not a
    politeness problem but a correctness one in the other direction -- a run that takes twice as
    long as the operator asked for is a run somebody cuts short.

    PER HOST, because that is who the promise is made to. A tool asking five hosts about 75 files
    and pacing globally sleeps five times longer than politeness requires, and the wait buys
    nobody anything -- each server sees one request every 3.5 s instead of every 0.7 s.

    THE CLOCK AND THE SLEEP ARE ARGUMENTS so that pacing can be tested without a test that waits.
    That is not a hypothetical nicety: putting a 0.7 s pause into one tool took its test file from
    0.003 s to 34 s, and a suite that slow stops being run.

    IT NEVER GOES BACKWARDS. `time.monotonic` is used rather than the wall clock because a clock
    that is corrected while a long fetch runs would produce a negative wait, and `time.sleep` of a
    negative number raises. A crawler that dies at 03:00 because the machine synchronised its
    clock is exactly the kind of failure nobody reproduces.

        pacer = Pacer(0.7)
        for url in urls:
            pacer.wait(host_of(url))
            ...

    A ROW THAT IS NEVER ASKED MUST NOT CALL wait(). Callers drop rows for reasons that never reach
    the network -- no address recorded, a host already known to be gone -- and pacing those turns
    a table of unaskable rows into minutes of waiting to be told nothing happened. That is the
    caller's `continue`, not a method here: an object cannot know that a request it was never
    told about did not happen.
    """

    def __init__(self, pause, clock=time.monotonic, sleep=time.sleep):
        self.pause = pause
        self._clock = clock
        self._sleep = sleep
        self._due = {}
        self._lock = threading.Lock()

    def wait(self, key):
        """Sleep as long as politeness to `key` requires. -> the seconds actually slept.

        A key nobody has asked before does not wait: the promise is about the INTERVAL between
        two requests, and there is no first interval. Returning the slept time rather than None
        is what lets a caller report its own pacing, and what lets a test check it without a
        clock.

        IT RESERVES ITS SLOT AND THEN SLEEPS OUTSIDE THE LOCK, which is what makes it usable by a
        threaded crawler. `mirror.py` has carried its own version for as long as it has existed,
        and that one holds the lock ACROSS the sleep -- correct there, because a run paces one
        archive and therefore one host, and wrong the moment two hosts are paced by one object:
        every worker would queue behind whoever is sleeping, however unrelated their host.
        Recording the next allowed time before releasing the lock gives concurrent callers for
        the SAME key a proper queue and callers for different keys no interference at all.
        """
        with self._lock:
            now = self._clock()
            due = self._due.get(key, now)
            wait = due - now if due > now else 0.0
            self._due[key] = max(now, due) + self.pause
        if wait > 0:
            self._sleep(wait)
            return wait
        return 0.0


class Backoff:
    """How long to wait before trying AGAIN -- and longer when the server said to slow down.

    THE OTHER THING A PAUSE CAN MEAN, and the reason `Pacer` is not enough. A rate is a promise
    about how often we speak to a host at all; a backoff is what happens after something went
    wrong, and the two are opposites in one respect that matters: a rate is the same every time,
    a backoff must GROW, because repeating a failed request at the original rate is how a
    struggling server gets pushed over.

    Written down side by side, this collection's four ladders were:

        2 ** attempt                                   mirror.py, twice (HTTP retry)
        min(60 * attempt, 300), and 900 for one case   mirror.py (rsync retry)
        30 * (attempt + 1) if 429/503 else 12          suspect-reconsider.py
        BACKOFF[attempt], a table                      wayback-salvage.py

    TWO OF THE FOUR GROW GEOMETRICALLY AND TWO ARITHMETICALLY, which is why `seconds()` has both a
    `factor` and a `step`. Offering only doubling would have meant rewriting two working ladders
    into a shape their authors did not choose, and changing what a crawler does to suit a class is
    the wrong way round.

    THE ONE DISTINCTION WORTH KEEPING is the one `suspect-reconsider.py` makes and the others do
    not: **429 and 503 are the server talking about us.** Every other error is a thing that
    happened; those two are a request, and the only cooperative reply is to wait longer than we
    otherwise would. That is why `throttled` is a parameter here and not a separate class -- it
    is the same ladder climbed in bigger steps.

    `seconds()` and `wait()` are separate because callers log the number before they spend it:
    "RETRY 2/5 in 120s after rc=23" is written by `mirror.py` and has to know the wait in
    advance. A single method that slept and returned would force every such caller to guess.

    NOTHING HERE IS RANDOMISED. Jitter is the right answer when many clients back off against one
    server at once; this is one machine talking to one host, and an unpredictable wait would make
    a log that nobody can compare against another run.

        backoff = Backoff(first=1.0, factor=2.0, cap=300)
        for attempt in range(attempts):
            ...
            if attempt < attempts - 1:
                log("retry in %ds" % backoff.seconds(attempt))
                backoff.wait(attempt, throttled=code in (429, 503))
    """

    def __init__(self, first=1.0, factor=2.0, step=0.0, cap=None, throttled_first=None,
                 throttled_factor=None, throttled_step=None, sleep=time.sleep):
        if first < 0:
            raise ValueError("first must not be negative")
        if factor < 1:
            raise ValueError("factor below 1 shrinks the wait, which is not a backoff")
        if step < 0:
            raise ValueError("step below 0 shrinks the wait, which is not a backoff")
        self.first = first
        self.factor = factor
        self.step = step
        self.cap = cap
        # A throttled ladder that was not asked for is the ordinary one, doubled at the bottom.
        # Saying so here rather than at each call site is the point of the class.
        self.throttled_first = first * 2 if throttled_first is None else throttled_first
        self.throttled_factor = factor if throttled_factor is None else throttled_factor
        self.throttled_step = step if throttled_step is None else throttled_step
        self._sleep = sleep

    def seconds(self, attempt, throttled=False):
        """The wait before retry number `attempt`, counting from 0. -> seconds, never negative.

        ATTEMPT 0 IS THE FIRST RETRY, not the first request. A caller that has just failed once
        passes 0, and gets `first`.

        `first * factor ** attempt + step * attempt`, AND BOTH TERMS ARE THERE BECAUSE BOTH SHAPES
        WERE. Two of this collection's four hand-written ladders grow geometrically (`2 ** attempt`
        twice in mirror.py) and two grow arithmetically (`30 * (attempt + 1)` in
        suspect-reconsider, `min(60 * attempt, 300)` for rsync). An abstraction that covered only
        the first would have meant rewriting two working ladders into a shape their authors did
        not choose -- changing a crawler's behaviour to suit a class is the wrong way round.
        """
        if attempt < 0:
            raise ValueError("attempt counts from 0")
        if throttled:
            first, factor, step = self.throttled_first, self.throttled_factor, self.throttled_step
        else:
            first, factor, step = self.first, self.factor, self.step
        wait = first * (factor ** attempt) + step * attempt
        if self.cap is not None:
            wait = min(wait, self.cap)
        return wait

    def wait(self, attempt, throttled=False):
        """Sleep `seconds(attempt, throttled)`. -> the seconds actually slept."""
        wait = self.seconds(attempt, throttled)
        if wait > 0:
            self._sleep(wait)
        return wait


# Errno values that mean the request NEVER LEFT THIS MACHINE. Both spellings of each, because the
# collection runs on Windows and its CI on Linux, and a list with only one of them is a check that
# passes in the place it was written and nowhere else.
#
#   11001 / -2 / -3   getaddrinfo failed -- no DNS answer, or none yet (EAI_NONAME, EAI_AGAIN)
#   10051 / 101       network unreachable -- no route from here at all
#   10065 / 113       host unreachable
#   10050 / 100       the network itself is down, which is what a dropped wifi looks like
#
# A REFUSED CONNECTION IS NOT HERE, on purpose. ECONNREFUSED means a machine answered the SYN with
# a reset: something is at that address and it declined. That is the host talking, and treating it
# as a local fault would excuse exactly the refusal this collection must notice.
UNREACHED = frozenset((11001, -2, -3, 10051, 101, 10065, 113, 10050, 100))


def blocking_parent(path):
    """-> the ancestor of `path` that is a FILE where a directory is needed, or None.

    A SOURCE MAY SERVE BOTH `X` AND `X/y`; A FILESYSTEM MAY NOT. ps-2.kev009.com serves
    `ohlandl/CPU/docs/AMD` as a page AND `ohlandl/CPU/docs/AMD/<datasheet>.pdf` beneath it. One of
    the two can be stored and the other cannot, and which one wins is simply whichever arrived
    first.

    WHY THIS IS A FUNCTION AND NOT AN EXCEPTION HANDLER. manifest-fetch.py used to find out by
    trying: os.makedirs raised WinError 183 ("cannot create a file when that file already
    exists"), the generic handler counted it as a FAILURE, and Patience counted 30 of those in a
    row as the host having gone quiet. The run abandoned ps-2.kev009.com with 2 124 fetchable
    files untouched -- and I spent an afternoon explaining to the owner that the host had blocked
    us, that a second address would be route-shopping, and that we should wait a day. He restarted
    his router for nothing. The host had answered 200 the whole time.

    MEASURED 2026-10-04: of 2 278 candidates, 154 were blocked and TWO files did all of it --
    `ohlandl/CPU/docs/AMD` blocking 149 and `ohlandl/615x/AOS_43/Docs` blocking 5.

    ASKED BEFORE THE REQUEST, so the source is not made to send bytes that cannot be written. The
    register already knows this shape: 2 416 files across the collection are logged
    "LOST (a file occupies a parent directory of this one)".
    """
    parts = [p for p in str(path).replace("/", os.sep).split(os.sep) if p]
    if not parts:
        return None
    walk = parts[0] + os.sep if parts[0].endswith(":") else parts[0]
    for seg in parts[1:-1]:
        walk = os.path.join(walk, seg)
        if isfile(walk):
            return walk
    return None


def local_failure(exc):
    """-> a short label when a failure happened on OUR side of the wire, else None.

    WHAT THIS IS FOR. `Patience` has to tell "the host stopped answering" from "we never asked it",
    and only the exception knows. Measured 2026-10-02: a run of openpa ended on two
    `[Errno 11001] getaddrinfo failed` and announced that the host had stopped talking and should
    be left alone for days. The owner's wifi had dropped; the host answered 200 within the minute.

    IT UNWRAPS, BECAUSE THE INTERESTING ERRNO IS NEVER ON TOP. urllib raises URLError whose
    `reason` is the socket error, so `exc.errno` on the URLError is None and a check that reads
    only the outer exception finds nothing and reports nothing -- the silent form of this mistake.

    AND A TIMEOUT IS NOT LOCAL. `socket.timeout` means the request went out and nothing came back,
    which is the host's silence and the one case that does justify waiting. The whole value of this
    function is that it says None for that.
    """
    seen = 0
    while exc is not None and seen < 5:          # a URLError wrapping an OSError wrapping... stop.
        if isinstance(exc, socket.gaierror):
            return "DNS lookup failed (%s)" % (exc.errno,)
        errno = getattr(exc, "errno", None)
        if errno in UNREACHED:
            return "%s (errno %s)" % (getattr(exc, "strerror", None) or "unreachable", errno)
        exc = getattr(exc, "reason", None)
        seen += 1
    return None


class Patience:
    """How many requests a run may waste on a host that has stopped answering, before it stops.

    `Pacer` decides how OFTEN to ask and `Backoff` how long to wait before asking AGAIN. Neither
    can decide to stop, and stopping is the thing this collection has had to learn twice by
    losing a host:

        dialectronics  2026-09-16  377 requests, then 28, then 2 -- each trip cost tolerance in
                                   the next window, and the third one bought the ban.
        openpa         2026-09-27  "six in a row on /doc/ pages, WinError 10060. Stopped at once
                                   instead of retried."

    Both times a PERSON noticed and stopped it. A url-list fetch has no person watching: it walks
    its list to the end because that is what a list is, and 31 urls at a 120 s timeout is an hour
    of knocking on a door that has already been shut.

    THE COUNT IS CONSECUTIVE, NEVER CUMULATIVE. A run over 2 000 files that collects nine
    scattered failures is a healthy run over a lumpy archive; nine in a row is a host that went
    away. Summing them would abandon the first and tolerate the second, which is backwards.

    AND A 404 RESETS IT, WHICH IS THE WHOLE POINT. An HTTP status -- any status, including 404 and
    410 -- is the server SPEAKING TO US. It costs it nothing, it says the connection is alive, and
    a manifest full of files the mirror never kept will legitimately produce a long run of them.
    Only silence counts here: a timeout, a refused connection, a reset. That distinction already
    exists in `http_try`, whose docstring says why the two kinds of "no" must not be collapsed;
    this is the same line drawn one level up, where it decides whether to carry on at all.

    AND THERE ARE THREE OUTCOMES, NOT TWO -- learned 2026-10-02, after this class had already been
    in use for three days. A 568-url run of openpa stopped itself correctly and then gave the wrong
    advice:

        FAIL systems/images/saicgalaxy1996.gif :: [Errno 11001] getaddrinfo failed
        STOPPED: ... it has stopped talking. Leave it alone for days.

    Errno 11001 is a DNS lookup that failed. The owner's WLAN had dropped. No request ever left
    this machine, the host was never asked anything, and it answered 200 in 0.2 s a minute later --
    so "leave it alone for days" would have cost days over a hiccup on our own side.

    SO: the server answered, the server did not answer, OR WE NEVER REACHED IT. The third says
    nothing whatever about the host, and `unreachable()` is how a caller says so. The run still
    stops -- carrying on with no network is pointless -- but what it writes down is different, and
    what it writes down is what somebody acts on tomorrow.

        patience = Patience(limit=5)
        for url in urls:
            ...
            if the_server_replied:
                patience.answered()
            elif local_failure(exc):
                patience.unreachable(local_failure(exc))
            else:
                patience.went_quiet(type(exc).__name__)
            if patience.spent:
                print(patience.reason); break
    """

    def __init__(self, limit=5):
        if limit < 1:
            raise ValueError("a limit below 1 would stop before the first request: %r" % limit)
        self.limit = limit
        self.quiet = 0
        self.worst = 0
        # How many of the CURRENT streak never reached the wire. Reset with the streak, because a
        # run that recovered and failed again later is a different event.
        self.local = 0

    def answered(self):
        """The server replied -- 200, 404, 500, anything. The run is talking to something."""
        self.quiet = 0
        self.local = 0

    def went_quiet(self, what="no answer"):
        """Nothing came back: a timeout, a refusal, a reset. -> True once the limit is reached."""
        self.quiet += 1
        self.worst = max(self.worst, self.quiet)
        self.last = what
        return self.spent

    def unreachable(self, what="no route to the host"):
        """We never got to the wire: DNS failed, no route, no network. -> True at the limit.

        Counted in the SAME streak, because the run must stop either way and two counters would
        let a flapping connection alternate between them forever without ever reaching a limit.
        What differs is the reason, not the arithmetic.
        """
        self.local += 1
        return self.went_quiet(what)

    @property
    def spent(self):
        return self.quiet >= self.limit

    @property
    def reason(self):
        """What to print when a run stops. Says the count, because that is the evidence.

        THREE WORDINGS, because the advice differs and the advice is the point. Blaming a host for
        our own dropped wifi sends somebody away for days; blaming our wifi for a host that has
        genuinely stopped sends them back to hammer it.
        """
        last = getattr(self, "last", "no answer")
        if self.local and self.local == self.quiet:
            return ("STOPPED: %d requests in a row never reached the wire (%s). THIS SAYS NOTHING "
                    "ABOUT THE HOST -- it was not asked, and nothing here is evidence about those "
                    "files. Check this machine's own network, then run again; there is no reason "
                    "to wait." % (self.quiet, last))
        if self.local:
            return ("STOPPED: %d requests in a row went unanswered (%s), and %d of them never "
                    "reached the wire. MIXED, so neither reading is safe: check this machine's "
                    "network first, and only treat the host as refusing if the rest still times "
                    "out once it is sound." % (self.quiet, last, self.local))
        return ("STOPPED: %d requests in a row went unanswered (%s). The host is not refusing "
                "individual files, it has stopped talking. Leave it alone for days."
                % (self.quiet, last))


# The formats in this collection that STATE THEIR OWN LENGTH, and what they are called when they
# do. Measured 2026-09-25: 66 439 ZIP-family files (357 GB), 2 042 `.iso` (521 GB) and 636 RIFF
# (2.9 GB) -- 69 117 files that can be checked for completeness from a few kilobytes each.
#
# `.iso` IS THE REASON THIS EXISTS AT ALL. `check_holes` exempts disc images, because unallocated
# sectors read as zeros and always will -- so 521 GB of this collection is invisible to the only
# check that reads files in full. ISO 9660 records its own volume size in the primary volume
# descriptor, which asks a completely different question and needs 2 KB to answer it.
DECLARES_ITS_LENGTH = types.MappingProxyType({
    ".avi": "RIFF", ".wav": "RIFF", ".webp": "RIFF", ".ani": "RIFF",
    ".zip": "ZIP", ".jar": "ZIP", ".xpi": "ZIP", ".apk": "ZIP",
    ".docx": "ZIP", ".odt": "ZIP", ".pptx": "ZIP", ".xlsx": "ZIP", ".epub": "ZIP",
    ".iso": "ISO 9660",
})

# How far back an End Of Central Directory record may sit. Its fixed part is 22 bytes and a zip
# comment may follow it, up to 65 535 -- so 64 KB + a little always reaches it if it is there.
ZIP_TAIL = 66 * 1024
ZIP_EOCD = bytes([0x50, 0x4B, 5, 6])
# The signature every central-directory entry begins with -- what proves an EOCD real.
ZIP_CD_ENTRY = bytes([0x50, 0x4B, 1, 2])
ZIP64_MARK = 0xFFFFFFFF

# ISO 9660 puts the primary volume descriptor at logical sector 16 of 2 048 bytes.
ISO_PVD_AT = 16 * 2048

# "I found the record and it does not tell me", which is NOT "the record is missing". A zip
# reader has to keep those apart: a missing End Of Central Directory is damage, and a ZIP64
# archive whose 32-bit fields are placeholders is a perfectly good file this code cannot measure.
# Collapsing them reported every ZIP64 archive in the collection as truncated, and the test for
# it caught that before the first full run. [2026-09-25]
_CANNOT_TELL = object()


def _riff_length(fh):
    fh.seek(0)
    head = fh.read(12)
    if len(head) < 12 or head[:4] != b"RIFF":
        return None
    # The field counts everything after itself, so the file is eight bytes longer.
    return int.from_bytes(head[4:8], "little") + 8


def _zip_length(fh, size):
    """The End Of Central Directory record, VALIDATED against the directory it points at.

    FOUR MATCHING BYTES ARE NOT A RECORD. The signature is four bytes and deflate output is
    effectively random, so it turns up inside compressed data. Measured 2026-09-25:
    `mpoli-bbs/.../SYNC.ZIP` is 5 697 bytes and contains one such accident at offset 4 093, whose
    fields decode to a central directory at 3 301 229 764 and a 50 372-byte comment. Believed, it
    makes that file "6.60 GB short" -- and three neighbours produced the identical figure, which
    is what a parser error looks like and damage does not.

    AND THE OBVIOUS GUARD WAS WRONG IN THE OTHER DIRECTION. Requiring the comment to reach exactly
    to the end of the file rejects a real record whenever anything follows it, and in this
    collection plenty does: BBS and FTP copies padded to a block boundary. Checked against
    Python's own `zipfile` over a sample of 25, that rule disagreed on **17** -- it would have
    reported well over a thousand intact archives as truncated.

    WHAT IS CHECKED INSTEAD is the thing the record is actually for: it says where the central
    directory starts and how long it is, so the directory must BE there. `prefix` is what sits in
    front of the archive -- a self-extracting stub, usually zero -- and is what makes the offsets
    line up. An empty archive has no directory to look at and is accepted on its own arithmetic.

    -> the length the record implies, which is where the archive ENDS. Anything after that is
    padding and makes the file longer, never shorter.
    """
    fh.seek(max(0, size - ZIP_TAIL))
    tail = fh.read(ZIP_TAIL)
    base = size - len(tail)
    at = len(tail)
    while True:
        at = tail.rfind(ZIP_EOCD, 0, at)
        if at < 0:
            return None
        if len(tail) - at < 22:
            continue
        rec = tail[at:at + 22]
        entries = int.from_bytes(rec[10:12], "little")
        cd_size = int.from_bytes(rec[12:16], "little")
        cd_at = int.from_bytes(rec[16:20], "little")
        comment = int.from_bytes(rec[20:22], "little")
        if cd_at == ZIP64_MARK or cd_size == ZIP64_MARK:
            # ZIP64 keeps the real figures elsewhere. 0xFFFFFFFF is "look there", not a length,
            # and it is not damage either -- which is why it is not None.
            return _CANNOT_TELL
        here = base + at
        prefix = here - cd_size - cd_at
        if prefix < 0 or here + 22 + comment > size:
            continue
        if entries:
            fh.seek(prefix + cd_at)
            if fh.read(4) != ZIP_CD_ENTRY:
                continue            # the directory is not where this record says it is
        return here + 22 + comment


def _iso_length(fh, size):
    if size < ISO_PVD_AT + 2048:
        return None
    fh.seek(ISO_PVD_AT)
    pvd = fh.read(2048)
    if len(pvd) < 132 or pvd[1:6] != b"CD001":
        # Plenty of `.iso` are UDF, HFS or a raw track with no ISO 9660 filesystem at all. A
        # missing PVD is not evidence of damage here, only of a format with no opinion.
        return None
    blocks = int.from_bytes(pvd[80:84], "little")
    block_size = int.from_bytes(pvd[128:130], "little")
    if not blocks or not block_size:
        return None
    return blocks * block_size


def declared_length(path):
    """What the file says its own length should be -> (expected, format), or None.

    THE SEVENTH KIND OF RECORD, and the only one that needs nothing but the file. The others in
    this collection ask a live host, an archive's packing list, a medium's block index, a second
    mirror's digest, or a stored directory listing -- every one of them can go away. A length a
    file states about itself travels with it and cannot go stale.

    IT WAS A HAND MEASUREMENT FIRST. An Ultima VI savegame states its object count in its first
    two bytes, so `size == 2 + 8 * count`; 68 of 69 agreed and the 69th was one byte short. That
    file is damaged, and NOTHING in this collection could see it: not empty, no signature MAGIC
    knows, far under --holes' 16 MB floor, and --verify hashes it to itself and is content. This
    is that check generalised to the formats that are actually here.

    -> None when the file makes no statement: an extension nobody listed, a `.iso` that is not
    ISO 9660, a ZIP64 archive whose 32-bit fields are placeholders. "No opinion" and "damaged"
    must not be the same answer, or the check invents findings out of formats it cannot read.

    -> (None, format) when a file of a format that MUST carry the record does not: a ZIP with no
    End Of Central Directory has been cut short, and that IS the finding.

    SHORT IS DAMAGE; LONG IS NOT. A file longer than it declares is ordinary -- a CD image padded
    to a track boundary, a self-extracting archive with a stub in front of the zip, a RIFF with
    trailing metadata. Only missing bytes are missing.
    """
    fmt = DECLARES_ITS_LENGTH.get(file_extension(path))
    if fmt is None:
        return None
    try:
        size = os.path.getsize(long_path(path))
        with open(long_path(path), "rb") as fh:
            if fmt == "RIFF":
                expected = _riff_length(fh)
            elif fmt == "ZIP":
                expected = _zip_length(fh, size)
            else:
                expected = _iso_length(fh, size)
    except OSError:
        return None
    if expected is _CANNOT_TELL:
        return None
    if expected is None:
        # A ZIP is the only one of the three that MUST carry its record, so for a zip a missing
        # one is the finding itself. The other two simply turn out not to be the format their
        # name suggested, which is --ruins' question and not this one.
        return (None, fmt) if fmt == "ZIP" else None
    return (expected, fmt)


def quote_url(url):
    """A URL harvested from a page, made safe to hand to urllib. -> the requestable form.

    A SERVER MAY LINK WHAT IT CANNOT BE ASKED FOR. One archive here serves files called
    `AS400 Processor Summary.html` with the space unescaped, and urllib refuses those outright
    with `InvalidURL: URL can't contain control characters`. Measured before this existed: 188
    failures in the first 221 files -- better than one in four, and every one of them counted as
    an ordinary fetch failure, which is to say invisible.

    ONLY THE REQUEST IS QUOTED. The unencoded URL stays canonical everywhere else, so the local
    filename, the seen-set and the collision key are unaffected by this. `safe="/%"` leaves an
    already-encoded %XX alone rather than turning it into %25XX, which would ask for a different
    file and get a 404 that looks like a missing one.

    THE FRAGMENT IS DROPPED, because it is never sent in a request and a URL that differs only
    there is the same request twice -- see strip_fragment(), which answers the same question for
    a link rather than for a request.
    """
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc,
        urllib.parse.quote(parts.path, safe="/%"),
        urllib.parse.quote(parts.query, safe="=&%"),
        ""))

def http_open(url, timeout=120, context=None, extra_headers=None, opener=None, method=None,
              quote=False):
    """One request, left OPEN. -> the response, for a caller that wants to stream it.

    A four-gigabyte ISO must not become four gigabytes of memory, and a probe that only needs to
    know whether a url answers should read one byte and stop. Both need the response itself.

    Carries the collection's identity without the caller having to remember to. `extra_headers`
    goes through request_headers(), so a Range or an Accept is possible and the User-Agent cannot
    be dropped by accident.

    `opener` exists so this can be tested without a network: it defaults to urllib's and is
    otherwise any callable with the same shape. A helper that can only be exercised against a
    live host is a helper nobody exercises -- and against somebody's private server, exercising
    it is not free.

    `quote=True` puts the url through quote_url() first, and A CALLER WHOSE URLS CAME OUT OF A
    PAGE WANTS IT. It is off by default because it drops the fragment, and a caller that built
    its own url should get back exactly what it asked for. The building block is exported too,
    for a caller that needs the safe form for something other than this request.
    """
    import urllib.request
    if quote:
        url = quote_url(url)
    kw = {}
    if method:
        kw["method"] = method
    req = urllib.request.Request(url, headers=request_headers(extra_headers), **kw)
    call = opener or urllib.request.urlopen
    open_kw = {"timeout": timeout}
    if context is not None:
        open_kw["context"] = context
    return call(req, **open_kw)


def http_get(url, timeout=120, context=None, extra_headers=None, opener=None):
    """One GET, read to the end. -> (bytes, headers).

    For anything that fits in memory. http_open() is the one to use when it might not.
    """
    with http_open(url, timeout, context, extra_headers, opener) as r:
        return r.read(), r.headers


def answered_as_a_directory(asked, final):
    """-> True if the server redirected a bare path to the same path WITH A TRAILING SLASH.

    THAT SLASH IS THE SERVER SAYING "THIS IS A DIRECTORY", and storing the body under the bare
    name writes a file where a directory has to go. The register already has the bill for it:
    four impostor files of 122 077 bytes, each byte-identical to the listing it impersonates, and
    2 416 files afterwards logged "LOST (a file occupies a parent directory of this path)".

    same_path_plus_slash() answers a stricter question -- same host AND same path -- and that is
    right for the crawler, which uses it to decide whether to walk further. It is NOT enough here:
    ps-2.kev009.com answers `/ohlandl/CPU/docs/Intel` with a redirect to
    `ardent-tool.com/CPU/docs/Intel/`. Different host, different path, and the trailing slash still
    means exactly what it means. On 2026-10-04 that wrote FOUR more impostors -- Intel, AMD, IBM,
    Cyrix -- which then made 692 datasheets unstorable.
    #
    THE HOST AND THE PATH ARE DELIBERATELY NOT COMPARED. A server is free to answer for another
    name, and whether the redirect stayed on the same machine says nothing about whether what
    came back is a directory. Only the slash does.
    """
    if not final or not asked:
        return False
    return final.endswith("/") and not asked.endswith("/")


def http_try(url, timeout=120, limit=None, method=None, **kw):
    """A request that NEVER RAISES. -> (status, body).

    `status` is an int when a server answered, and a STRING NAMING THE FAILURE when none did --
    "URLError", "TimeoutError", "RemoteDisconnected". `body` is bytes, empty on any failure.

    THE POINT IS THAT THE TWO KINDS OF "NO" LOOK DIFFERENT. A 404 is the server's settled answer
    and a caller may write it down as final; a socket timeout is our end of the wire and means
    try again another day. Collapsing both into one value is how a transient failure gets
    recorded as permanent -- and this collection keeps records of what is permanently gone, so
    that distinction is the whole value of the record.

    THREE TOOLS CARRIED THIS try/except SHAPE, character for character. Two of them now call
    this: recheck-decisions.get and reachability-probe.head. [moved here 2026-09-23]

    TWO KEEP THEIR OWN, AND BOTH ARE RIGHT TO.

      nginx-autoindex-gallery.get paces requests to a Crawl-delay that host asked for, and its
      docstring says why: a rate is a promise made to ONE operator, and a shared helper would
      let another caller inherit it without knowing, or drop it without noticing.

      subset-refetch.fetch needs the Last-Modified header, which this deliberately does not hand
      back. Widening the return value for one caller -- or threading a callback through it --
      would cost every other caller a value it has no use for. A shared function earns its place
      by answering ONE question; the moment it answers two, it stops being the obvious thing to
      reach for.

    `limit` caps how much of the body is read. A probe that wants a page's head has no use for a
    400 MB answer and no way to know one is coming.
    """
    try:
        with http_open(url, timeout=timeout, method=method, **kw) as r:
            return r.status, (r.read(limit) if limit else r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, b""            # the server DID answer, and the code is the answer
    except Exception as exc:            # noqa: BLE001
        return type(exc).__name__, b""


def head_size(url, timeout=30, opener=None):
    """Content-Length for a URL, without fetching it. -> int, 0 when the server does not say.

    ZERO MEANS "NOT STATED", and a caller must not read it as "empty". A server is entitled to
    answer a HEAD without a length, and treating that as a measurement is how an archive gets
    reported as smaller than it is.
    """
    with http_open(url, timeout, opener=opener, method="HEAD") as r:
        return int(r.headers.get("Content-Length") or 0)




# ------------------------------------------------------------------------- loading a peer


def load_peer(filename, name=None, directory=None):
    """Load a sibling script as a module, by path. -> the module.

    WHY BY PATH AND NOT BY IMPORT. Several tools here have a hyphen in their filename, which makes
    them unimportable; and the largest of them parses a command line, so importing it for one
    constant would be a poor trade even if the name allowed it. importlib lets a caller take the
    one function or the one table it needs.

    sys.argv IS REPLACED FOR THE DURATION. A module that inspects it at import would otherwise see
    the CALLER'S arguments, which are not its own. Restored in a finally, so a raising module does
    not leave the caller's argv behind it.

    `directory` defaults to the directory of THIS file, which is where the peers live. A caller in
    another directory therefore does not have to know where they are, and -- the reason this
    matters -- `python -c` leaves sys.path[0] as the working directory, so a caller cannot rely on
    that either.

    EIGHTEEN FILES EACH CARRIED THIS. Several forgot the argv guard, one forgot the finally, and
    they used five different module names for the same module -- one of which collided with a
    real module in the same directory.
    """
    import importlib.util
    directory = directory or os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        raise IOError("no %s beside %s" % (filename, os.path.basename(__file__)))
    spec = importlib.util.spec_from_file_location(
        name or "_peer_" + os.path.splitext(filename)[0].replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [filename]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = saved
    return module


def load_mirror(directory=None):
    """mirror.py as a module. -> the module.

    It holds the registers -- which archives, which exclusions, which are retired -- and those
    live in exactly one place on purpose. A tool that needs one reads it from here rather than
    keeping a copy that will disagree by next month.
    """
    return load_peer("mirror.py", "_mirror", directory)


# AN ARCHIVE TAKEN OVER rsync THAT SERVES THE SAME TREE OVER HTTP. `mirror.ARCHIVES` records the
# address a crawl USED, which for bitsavers is an rsync module -- and rsync is not a protocol the
# question-asking tools speak. That left 21 of holes-vs-source.py's 67 findings unaskable, every
# one of them bitsavers, which is a third of the whole question.
#
# The same paths are served over HTTPS, and that is not an assumption: the two damaged PDFs in
# that tool's `HOLES_AT_SOURCE` were fetched whole from
# `https://bitsavers.org/www.computer.museum.uq.edu.au/` on 2026-09-25 and matched byte for byte.
#
# A SEPARATE TABLE AND NOT A FIX TO THE REGISTER, because the register is a record of what was
# done and this is a convenience for asking questions afterwards. Editing the first to suit the
# second would make the crawl's own history less true.
#
# IT LIVED IN TWO FILES UNTIL 2026-09-27, spelled identically, and truncated-vs-source.py's copy
# said so in its own comment: "Same table, same reason and same evidence as holes-vs-source.py".
# A third tool that asks the same question, ask-the-source.py, did not have it at all -- see
# source_url() directly below for what that cost.
#
# MappingProxyType, like every other exported table here, and the contract test said so within a
# minute of this moving: these tools load one another as modules inside ONE process, so an
# exported dict is shared mutable state. A caller that wants a different table passes one to
# source_url() -- which is why the parameter exists.
HTTP_FACE = types.MappingProxyType({
    "bitsavers": "https://bitsavers.org/",
})


def source_url(archive, rel, register, http_face=None):
    """-> the address `rel` was fetched from, or None when it cannot be asked over HTTP.

    TWO REASONS FOR None, AND THEY ARE NOT THE SAME THING -- but both end in a row nobody can
    challenge, so a caller reports both rather than dropping either. An archive missing from the
    register has no recorded address at all; an rsync archive has one no HTTP tool can speak.

    THREE TOOLS ASKED THIS AND ONLY TWO AGREED, which is why it is here. holes-vs-source.py and
    truncated-vs-source.py held byte-identical copies including the HTTP_FACE fallback;
    ask-the-source.py held a third version WITHOUT it, and so answered None for every bitsavers
    path while the other two answered a working URL for the same input. Nothing was broken and
    nothing was reported -- the third tool simply asked less, and no test could see it because
    each copy was consistent with itself.

    `rel` IS RELATIVE TO THE ARCHIVE, not to the collection. ask-the-source.py had it the other
    way round and split the name off inside the function, which is the kind of difference that
    makes two copies of one rule look like two different rules.

    THE PER-SEGMENT quote() IS DELIBERATE and is the behaviour all three had: `rel` comes from a
    local tree, so its names are UNENCODED, and quoting each segment is what turns a stored
    `AS400 Processor Summary.pdf` into something urllib will accept. It is not quote_url(), which
    repairs a URL harvested from a page and must leave an existing %XX alone -- the opposite
    requirement, and a reason these two must not be folded together.
    """
    if http_face is None:
        http_face = HTTP_FACE
    prefix = register.get(archive)
    if not prefix or prefix.startswith("rsync://"):
        prefix = http_face.get(archive)
    if not prefix or "://" not in prefix or prefix.startswith("rsync://"):
        return None
    return prefix.rstrip("/") + "/" + "/".join(
        urllib.parse.quote(part) for part in rel.split("/"))


def split_archive(rel):
    """A COLLECTION-relative path -> (archive directory name, path within it).

    `bitsavers/pdf/x.zip` -> `("bitsavers", "pdf/x.zip")`, and `bitsavers` alone -> `("bitsavers",
    "")`, which addresses the archive root.

    SEVEN PLACES DID THIS BY HAND and not all of them the same way. ask-the-source.py wrote
    `(rel.split("/", 1) + [""])[:2]` in one spot and `rel.split("/")[0]` in two others;
    truncated-vs-source.py wrote `where, under = rel.split("/", 1)`, which RAISES ValueError on a
    path with no slash; audit.py has `rel.split("/")[0] if "/" in rel else "(root)"`. Three
    different answers to "what if there is no slash": a tail of "", an exception, and the string
    "(root)".

    THE EMPTY TAIL IS THE ANSWER HERE, because the caller that cares can test for it and the two
    that do not get something usable. An exception is the one answer that cannot be ignored
    safely -- a table of findings is not the place to discover that one row has no directory.

    NOT URL-AWARE and not a path function: this splits on `/` only, because these rows are written
    with `/` whatever the filesystem uses. relative_to() and local_path() handle real paths.
    """
    archive, _, tail = rel.partition("/")
    return archive, tail


def find_tool(candidates):
    """-> the first of these external programs that is actually there, or None.

    ONE HOME FOR A LOOP THAT HAD TWO, byte for byte: b2-pack.py's find_rar() and
    iso-second-opinion.py's find_seven_zip(). Each keeps its own candidate list, which is the
    part that genuinely differs; the rule for deciding "is it there" is not.

    RAN AND MISBEHAVED STILL MEANS IT IS THERE, and that is the subtle half. Called with no
    arguments, rar prints its banner and exits non-zero, and 7z does much the same -- a
    SubprocessError from the probe is evidence the program EXISTS, so it is returned rather than
    skipped. Only OSError means the name could not be executed at all. Getting this backwards
    makes a present tool look missing, and both callers refuse to run without one.

    stdin IS CLOSED FOR THE PROBE, which neither copy did and which cost 30 seconds to find. A
    candidate called with no arguments may WAIT FOR INPUT instead of printing help, and with
    stdin inherited it then blocks until the timeout -- measured at exactly 30.019 s for one
    candidate in the first run of this function's own tests. The program is there either way, so
    the answer was never wrong; it just took the full timeout to give, once per candidate, in a
    function both callers run before they do anything at all.
    """
    for candidate in candidates:
        try:
            subprocess.run([candidate], capture_output=True, timeout=30,
                           stdin=subprocess.DEVNULL)
            return candidate
        except OSError:
            continue
        except subprocess.SubprocessError:
            return candidate
    return None


# ---------------------------------------------------------------------------- transport


# Answers that are about US rather than about the thing asked for: a rate limit, a gateway
# hiccup, a server restarting. Retrying is the cooperative response; treating them as a verdict
# on the resource is how a busy minute becomes a permanent "gone" in a written record.
RETRY_STATUS = frozenset((408, 429, 500, 502, 503, 504))

# SHA-256 of nothing. Worth naming: a zero-length file is a real thing in these trees, and a
# digest compared against this is how a truncated download is told from an empty one.
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def is_transport(exc, retry_status=RETRY_STATUS):
    """Is this "ask again later", rather than the server answering about the thing asked for?

    THE DISTINCTION IS THE WHOLE POINT, because the two get written down differently. A 404 is an
    ANSWER: the server says it has no such thing, and that belongs in the record. A refused,
    reset or timed-out socket is not an answer at all -- nothing was said about the resource, and
    recording "gone" would be inventing a fact.

    A 429 or a 503 arrives through the same exception type as the 404 and belongs with the socket
    errors: it is the server talking about US.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in retry_status
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, OSError))


def reach(host, ports=(80, 443), timeout=15, resolve=None, connect=None):
    """Where does a connection to `host` actually stop? -> {"ip", "dns", "ports": {port: err}}

    `dns` is None when the name resolved and the error text when it did not. Each entry in `ports`
    is None when the TCP handshake completed and the error text when it did not. Nothing above the
    handshake is attempted: this answers "is anything listening", and HTTP is http_try's job.

    WHY THE LAYERS HAVE TO BE SEPARATE, measured on dreamlandbbs.com, 2026-09-27 to 2026-10-02.
    Every request to that host timed out at 21.2 s, three times across five days, and all three
    times it was written into the register as a rate-limit penalty -- "the host said so within a
    minute", "the timer is stable, so the rule behind it is untouched", "leave it alone for days".
    One call of this function says what it actually was:

        DNS: www.dreamlandbbs.com -> 62.163.18.65
        TCP 80:  timed out after 15.0s
        TCP 443: open in 0.0s

    Port 80 shut, 443 open. The host had moved to HTTPS and the archive's base said `http://`, so
    every request went to a closed port and hung -- which is indistinguishable from a block IF the
    only instrument is an HTTP request. The misreading was not careless; it was unequipped.

    AND IT KILLS A TEMPTING WRONG ANSWER. Changing the User-Agent was proposed twice during those
    five days. A header cannot matter when the handshake never completes, and this is the function
    that shows that rather than asserting it.

    `resolve` and `connect` ARE PARAMETERS SO THIS CAN BE TESTED, which a network probe otherwise
    cannot be. They default to the real socket calls; a test passes fakes and pins the readings
    that produced a wrong diagnosis in the first place.
    """
    resolve = resolve or socket.gethostbyname
    out = {"ip": None, "dns": None, "ports": {}}
    try:
        out["ip"] = resolve(host)
    except Exception as exc:                                   # noqa: BLE001
        out["dns"] = str(exc) or type(exc).__name__
        return out

    def _connect(h, port, t):
        sock = socket.socket()
        sock.settimeout(t)
        try:
            sock.connect((h, port))
        finally:
            sock.close()

    connect = connect or _connect
    for port in ports:
        try:
            connect(host, port, timeout)
            out["ports"][port] = None
        except Exception as exc:                               # noqa: BLE001
            out["ports"][port] = str(exc) or type(exc).__name__
    return out


def scheme_drift(result, ports=(80, 443)):
    """-> the scheme a host now wants, when exactly one of its two ports answers, else None.

    "https" when 80 is shut and 443 answers, "http" for the reverse. None when both answer, when
    neither does, or when DNS failed -- because then the ports say nothing about a scheme and a
    guess would be the same kind of invention this exists to replace.

    THE DISTINCTION IT MAKES IS BETWEEN A STALE RECORD AND A REFUSAL. A base URL was correct on the
    day it was written; a site that later closes port 80 has not refused anybody. Reading the
    second as the first costs days of waiting for a block that was never there -- it cost five.
    """
    if result.get("dns") is not None:
        return None
    plain, secure = ports
    got = result.get("ports", {})
    if plain not in got or secure not in got:
        return None
    if got[plain] is not None and got[secure] is None:
        return "https"
    if got[secure] is not None and got[plain] is None:
        return "http"
    return None


def host_of(url):
    """-> the hostname, with any port, credentials and a leading `www.` removed.

    `www.example.com`, `example.com` and `example.com:80` are one site under three spellings, and
    an index that was built over years holds all three. Folding them keeps a copy from growing
    phantom directories that differ only in how some crawler happened to write the host down.
    """
    host = urllib.parse.urlsplit(url).netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def http_date(text):
    """An HTTP date -> a POSIX timestamp, or None when it cannot be read.

    None rather than a guess or `now`: a wrong mtime is indistinguishable from a right one
    afterwards, and the date a source published something is often the only date worth having.
    """
    if not text:
        return None
    try:
        import email.utils
        return email.utils.parsedate_to_datetime(text).timestamp()
    # WHAT parsedate_to_datetime ACTUALLY RAISES on junk, measured rather than assumed: every
    # one of '', 'nonsense', 'Mon, 99 Xyz 9999', None and '2026-13-45' gives ValueError. A
    # broad catch here would also swallow a typo in this function and answer "no date" for
    # every header in the collection -- silently, since None is a legitimate answer.
    except (TypeError, ValueError):
        return None



def copy_new_file(src, dest, chunk=HASH_CHUNK):
    """Copy `src` to `dest` WITHOUT EVER OVERWRITING `dest`. -> bytes copied, or None.

    None means dest was already there and nothing was written. It is not an error: the callers
    are gap-fillers, and "already have it" is the ordinary case.

    THE GUARD IS os.link() AND NOT A CHECK, because a check is a promise about a moment and this
    writes into a tree other programs write into. Measured on both filesystems here, NTFS and the
    collection's own drive: linking onto a name that exists raises FileExistsError, atomically, so
    the kernel makes the decision rather than a branch that ran earlier. os.replace() -- which
    mirror.py's rename_with_retry() correctly uses for its own `.part` files -- would silently
    destroy whatever was there, and this function exists precisely where that must not happen.

    THE COPY GOES BESIDE THE TARGET FIRST, under a name carrying this process's pid. A plain
    `<dest>.part` is the name mirror.py gives its downloads in flight, and two writers agreeing on
    a temporary name is how one of them loses a file. The suffix still ends in `.part`, so
    is_partial() keeps recognising it and no audit counts it as content.

    THE SOURCE'S mtime IS CARRIED OVER, best effort. In a collection where a stored file's
    timestamp is usually the origin's own Last-Modified, dropping it would make the filled copy
    look newer than the thing it is a copy of.

    IT DOES NOT VERIFY. A caller that knows what the bytes should be compares them itself --
    sha256_file() is right there -- and one that does not should not be pretending. What this
    guarantees is narrower and worth having alone: dest appears whole or not at all, and never
    replaces anything.
    """
    if exists(dest):
        return None
    parent = os.path.dirname(dest)
    if parent and not os.path.isdir(long_path(parent)):
        os.makedirs(long_path(parent), exist_ok=True)
    tmp = "%s.%d.part" % (dest, os.getpid())
    written = 0
    with io.open(long_path(src), "rb") as rd, io.open(long_path(tmp), "wb") as wr:
        while True:
            block = rd.read(chunk)
            if not block:
                break
            wr.write(block)
            written += len(block)
    try:
        os.utime(long_path(tmp), (time.time(), os.path.getmtime(long_path(src))))
    except OSError:
        pass
    try:
        os.link(long_path(tmp), long_path(dest))
    except FileExistsError:
        os.remove(long_path(tmp))
        return None
    os.remove(long_path(tmp))
    return written


def atomic_write(dest, data, mtime=None, suffix=".part"):
    """Write `data` to `dest` so that `dest` never exists half-written.

    A HALF-WRITTEN FILE THAT LOOKS COMPLETE IS THE FAILURE TO AVOID. Every tool here skips what it
    already has, so a truncated file is not retried -- it is inherited, indexed, and hashed into
    the record as though it were the thing itself. Writing beside the target and renaming makes
    the file appear whole or not at all.

    `mtime` may be a timestamp or an HTTP date string; None leaves the clock alone. Setting it is
    best-effort: a filesystem that refuses is not a reason to discard bytes that arrived intact.
    """
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(long_path(parent), exist_ok=True)
    tmp = dest + suffix
    with open(long_path(tmp), "wb") as fh:
        fh.write(data)
    os.replace(long_path(tmp), long_path(dest))
    if mtime is not None:
        ts = http_date(mtime) if isinstance(mtime, str) else mtime
        if ts:
            try:
                os.utime(long_path(dest), (ts, ts))
            except OSError:
                pass
    return dest



# ----------------------------------------------------------------------------- extraction


# EVERY SPELLING OF AN ATTRIBUTE VALUE, because pages in these trees are hand-written as often as
# generated: double quotes, single quotes, and none at all. A pattern that only matches the first
# is not stricter, it is blind -- one tool carried `<img[^>]+src="([^"]+)"` and silently found no
# image on any page that used the other two forms.
IMG_SRC = re.compile(r"""<img\s[^>]*?src\s*=\s*(?:"([^"]+)"|'([^']+)'|([^"'\s>]+))""", re.I)

# A sitemap names what a site is willing to say it has. For a store whose front page is an
# infinite scroll or a search box, that is the only complete enumeration on offer.
SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>")

# Content-Type -> extension, for URLs that carry none. NOT a general mime table: only types this
# collection has actually met, because guessing an extension is how a file comes to lie about
# what it is -- the exact defect the auditors exist to find.
#
# A URL may end in a sizing token with no extension at all. The naive "no extension means HTML"
# rule once labelled 162 WebP images as HTML on a single site.
EXTENSION_FOR_TYPE = types.MappingProxyType({
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
    "image/x-icon": ".ico",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/gzip": ".gz",
    "text/plain": ".txt",
    "text/html": ".html",
})


def image_sources(html):
    """-> [src] for every <img> on a page, in document order, duplicates kept.

    Duplicates are kept because the caller decides: a page that embeds one picture twice is a
    fact about the page, and de-duplicating here would hide it from anything that counts.
    """
    return [a or b or c for a, b, c in IMG_SRC.findall(html)]


def sitemap_locations(xml):
    """-> [url] for every <loc> in a sitemap or a sitemap index.

    The two are the same shape; a caller tells them apart by what the urls point at, which is
    its business and not this function's.
    """
    return SITEMAP_LOC.findall(xml)


def extension_for(content_type):
    """-> `.ext` for a Content-Type, or None when this collection has no opinion.

    None, not a guess. A name that claims an extension the bytes do not match is worse than a
    name with none: the first is believed, the second is looked at.
    """
    if not content_type:
        return None
    return EXTENSION_FOR_TYPE.get(content_type.split(";")[0].strip().lower())


# ---------------------------------------------------------------------------- filesystem


def set_case_sensitive(directory):
    """Make one NTFS directory case-sensitive. -> True, or a message saying why not.

    WHAT THIS IS FOR. A case-folding filesystem cannot hold `README` and `readme` at once, and a
    source that has both loses one silently -- the second write lands on the first. Windows can
    be told, per directory, to stop folding.

    fsutil REFUSES a directory that ALREADY holds names differing only in case, and that refusal
    is returned rather than swallowed: if it fires, the tree is not in the state the caller
    assumes, and carrying on would write the second name over the first all over again.

    THE DIRECTORY IS CHECKED FIRST, and that line is here because writing a test found the hole:
    `fsutil file setCaseSensitiveInfo` on a path that DOES NOT EXIST returns 0. It reports
    success for a directory it did not touch and could not have touched, so a caller that
    mistyped a path -- or ran before creating it -- was told the flag was set. Measured
    2026-09-22: rc 0, no output, the directory still absent afterwards.

    No elevation needed. On anything but Windows this is not an error, it is simply not a
    question -- the filesystem was never folding.
    """
    if os.name != "nt":
        return "not Windows"
    if not os.path.isdir(long_path(directory)):
        return "no such directory: %s" % directory
    import subprocess
    try:
        subprocess.run(["fsutil", "file", "setCaseSensitiveInfo", directory, "enable"],
                       check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or getattr(exc, "stdout", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("mbcs" if os.name == "nt" else "utf-8", "replace")
        return "fsutil failed: %s %s" % (exc, detail.strip())




# ------------------------------------------------------------------- what a file really is


# A running copy always has some of these, they are not content, and reporting them as damage
# buries the real findings.
PARTIAL_SUFFIXES = (".part", ".suspect", ".superseded")

# Extensions whose first bytes are worth checking. Deliberately the LARGE, opaque formats: those
# are the ones an error page can hide inside without anyone noticing the size.
CHECKED_EXT = frozenset({
    ".pdf", ".iso", ".img", ".rpm", ".tar", ".gz", ".zip", ".rar", ".z",
    ".squash", ".qcow2", ".ova", ".bff",
    # IMAGES, added 2026-09-24 after the cost and the yield were both measured rather than
    # guessed. The objection on record was that this "widens --ruins to millions of files":
    # counted out of the checksum indexes, the candidates are 114 210 against the 526 051 already
    # opened -- 22% more reading, not a different order of magnitude.
    #
    # WHICH ONES, decided by opening all of them. Of 279 mismatches across every image extension,
    # 122 were `.ico` and 47 `.bmp`, and almost none of those are damage: OS/2 keeps `BA`, `CI`
    # and `IC` icon formats under `.ico`, and `.bmp` is claimed by Ultima VI and by svgalib for
    # formats of their own. Two bytes of `BM` and four of `00 00 01 00` are not enough to say
    # what a file is. They are left out; .webp is left out because RIFF needs two checks at two
    # offsets and MAGIC holds one prefix per entry.
    ".jpg", ".jpeg", ".jpe", ".png", ".gif", ".tif", ".tiff",
    # A QNX package. 478 in this collection, 452 gzip and 26 all zeros, no third kind.
    ".qpk",
})

# Extension -> the byte sequences a file of that type may begin with. Several formats have more
# than one legal opening, and a check that knew only the common one would report the others as
# damage -- which is worse than not checking, because it teaches a reader to ignore the report.
# A READ-ONLY VIEW, not a dict. These tools load one another as modules inside one process, so
# an exported dict is shared mutable state: a client that "just adds one entry" changes what every
# other client in that process decides about a file, and nothing records that it happened.
# The first four bytes of an AIX fileset. Two tools each wrote this out: one refuses to
# install a salvaged `.i` that does not begin with it, the other the same for a `.suspect`
# it is about to replace. A magic number written twice is one that can be mistyped once.
BFF_MAGIC = b"\x09\x00\x6b\xea"

MAGIC = types.MappingProxyType({
    ".pdf": (b"%PDF",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06"),     # the second is an EMPTY archive, and legal
    ".rar": (b"Rar!",),
    ".gz": (b"\x1f\x8b",),
    ".z": (b"\x1f\x9d", b"\x1f\xa0"),           # LZW and LZH, both written by compress(1)
    ".rpm": (b"\xed\xab\xee\xdb",),
    ".squash": (b"hsqs", b"sqsh"),              # little- and big-endian
    ".qcow2": (b"QFI\xfb",),
    # AIX backup file format. `.bff` has been in CHECKED_EXT from the start and had NO
    # signature here, so magic_mismatch answered None for every one of them -- "no opinion",
    # which a caller must not read as "fine". An error page stored under a fileset name was
    # exactly as invisible as if the extension had never been checked.  [2026-09-23]
    ".bff": (BFF_MAGIC,),
    # IMAGES. What they are worth, measured on 2026-09-24 over the seven extensions kept: 108
    # mismatches, of which 41 are files of PURE ZEROS -- a picture of nothing is damage whatever
    # else is unclear -- and 28 are one landing page, `Copyright (C) Bull SAS - 2019`, standing
    # where bullfreeware's own images should be. That is the same page `--listed` found under an
    # `.exe` name and `--ruins` found under eight `.rpm` names on the same day.
    #
    # Two more were worth the whole exercise: `hp-openvms-2008/.../ZK-1933.gif` begins `F87ac`,
    # a GIF missing its first byte, and `os2bbs/bitmap/becvic.jpg` begins `yOya` where the four
    # JPEG bytes belong, with `JFIF` still legible two bytes later. Neither is visible to any
    # other check.
    ".jpg": (b"\xff\xd8\xff",),                 # JFIF and EXIF share these three
    ".jpeg": (b"\xff\xd8\xff",),
    ".jpe": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),            # eight bytes, four of them a corruption probe
    ".gif": (b"GIF87a", b"GIF89a"),             # the only two versions ever published
    ".tif": (b"II*\x00", b"MM\x00*"),           # little- and big-endian, "Intel" and "Motorola"
    ".tiff": (b"II*\x00", b"MM\x00*"),
    # A QNX PACKAGE IS A GZIP, and the collection said so rather than a specification. Of the
    # 478 `.qpk` files here -- all in `fsck-vendors/QNX/` -- 452 begin with the gzip signature
    # and 26 are entirely zeros. THERE IS NO THIRD KIND. Its sibling `.qpm` is the manifest
    # and is XML: 446 of 474 are text and the other 28 zeros, broken the same way.
    #
    # The 26 sat under "no statement possible" for as long as nothing here knew what a `.qpk`
    # was, beside 900 intact siblings in one directory. A 29 933-byte file of nothing is not a
    # package.  [2026-09-24]
    ".qpk": (b"\x1f\x8b",),
})

# How a text/html body starts, in the spellings that occur. Case matters here only because it is
# cheaper to list both than to lower-case every file's first bytes.
HTML_HEADS = (b"<!DOC", b"<!doc", b"<html", b"<HTML", b"<?xml")

# A generated directory listing SAVED AS A FILE. This happens when a listing links a subdirectory
# WITHOUT a trailing slash: a crawler cannot tell that from a file, downloads the index, and then
# nothing below that path can be written at all -- a filesystem cannot hold a file and a
# directory under one name.
#
# It says what it is in its own title, and no genuine document says that about itself.
INDEX_PAGE = re.compile(rb"<title>\s*Index of /|<h1>\s*Index of /", re.I)


# THE TWO PLACES A PAGE NAMES ITSELF. Separate patterns rather than one alternation, because the
# ORDER matters: a page with both gets its <title>, and <h1> is the fallback for the stock server
# pages that carry no title at all.
TITLE_TAG = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
HEADING_TAG = re.compile(rb"<h1[^>]*>(.*?)</h1>", re.I | re.S)

# Markup inside a heading, stripped so `<h1><b>NGC/IC Error!</b></h1>` reads as its text.
INNER_TAG = re.compile(rb"<[^>]+>")


def page_title(head):
    """-> what this page CALLS ITSELF -- its <title>, or its first <h1> when it has no title --
    with tags removed and whitespace collapsed, or None when it names itself nowhere.

    ONE HOME FOR A REGEX THAT HAD FIVE. find-html-imposters.py, recheck-decisions.py and
    redbooks-fetch.py each carried their own copy, and they had already drifted: one capped the
    match at 120 characters, one at 44, one not at all, and only one fell back to <h1>. Nothing
    was broken by the drift -- which is the point. Three spellings of one question is how the
    exclusion comparison came to exist in three places, with only one of them instrumented.
    NO LENGTH CAP HERE, deliberately: a caller that wants 44 characters can slice, and a cap
    baked into the regex is a cap the caller cannot see.

    BYTES OR STR, because the callers genuinely differ -- one reads files, one reads a decoded
    response body -- and making each convert first is how a sixth copy gets written. Bytes are
    decoded as UTF-8 with replacement: this is a label for a human to read, never content.

    A HEADING THAT IS ONLY MARKUP OR SPACE IS NOT A NAME. `<title></title>` occurs in this
    collection, and answering "" would make an empty string a value callers must test for
    separately from a missing one.

    AN EMPTY <title> FALLS THROUGH TO <h1>, which the first version of this function got wrong:
    it picked whichever tag MATCHED first and then emptied the result, so `<title></title>` ahead
    of a real <h1> answered None. Caught by the four-line hand check run before the tests were
    written. What is wanted is the first heading that HAS TEXT, not the first tag that exists.

    ENTITIES ARE DECODED, and this is not cosmetic. Measured 2026-09-27 over the 2 357 titles a
    collection-wide scan collected: 89 of them carry one -- `&quot;` 107 times, `&#58;` 18,
    `&amp;` 6, em and en dashes 11. `&#58;` IS A COLON, and stock_error_title() drops a site
    prefix by looking for one, so `NETFINITY 3500&#58; ERROR LED RESET` would have kept its
    prefix and been judged against the wrong string. A label a human reads is also a label a
    rule reads.
    """
    if isinstance(head, str):
        head = head.encode("utf-8", "replace")
    for pattern in (TITLE_TAG, HEADING_TAG):
        m = pattern.search(head)
        if not m:
            continue
        text = INNER_TAG.sub(b" ", m.group(1))
        text = " ".join(html.unescape(text.decode("utf-8", "replace")).split())
        if text:
            return text
    return None


# WHAT A PAGE CALLS ITSELF WHEN WHAT IT ANNOUNCES IS A FAILURE. Matched against the TITLE ONLY --
# see looks_like_an_error_page() for why that restriction is the whole idea -- and grouped so the
# answer says WHICH complaint, because "forbidden" and "not found" send a reader to different
# places.
#
# THE VOCABULARY IS NOT NEW; ITS PLACE IS. find-html-imposters.py has carried a six-class table
# since it was written and recheck-decisions.py a placeholder list, each for its own question.
# Nothing was missing -- nothing APPLIED IT to a file whose name was RIGHT.
#
# NO BARE STATUS NUMBERS, deliberately, and this is a documentation collection so the reason is
# concrete: `\b404\b` matches `HP 404 Calculator` and `\b500\b` matches `IBM System/36 5360`.
# Every real server title that carries a code carries the words too -- `404 Not Found`,
# `500 Internal Server Error` -- so the phrases catch them and the model numbers stay out.
#
# THE ORDER IS THE ANSWER, because the first match wins and the last entry matches nearly
# everything the others do. `500 Internal Server Error` contains the bare word "error", so with
# the generic class first it was reported as "error" and the specific reading was thrown away --
# caught by this table's own test, not by reading it. The catch-all goes LAST.
PAGE_COMPLAINTS = (
    ("not found", re.compile(r"\bnot\s+found\b|\bno\s+such\s+file\b|\bdoes\s+not\s+exist\b",
                             re.I)),
    ("forbidden", re.compile(r"\bforbidden\b|\baccess\s+denied\b|\bpermission\s+denied\b|"
                             r"\bunauthori[sz]ed\b", re.I)),
    ("unavailable", re.compile(r"\binternal\s+server\b|\bservice\s+unavailable\b|"
                               r"\bbad\s+gateway\b|\btemporarily\s+unavailable\b", re.I)),
    # Four languages, because two of the eight `.cgi` files at spider.seds.org say it in French.
    ("error", re.compile(r"\b(error|erreur|fehler|errore)\b", re.I)),
)



# HOW GOOD THE EVIDENCE IS, and this collection forced the distinction. Measured 2026-09-27 over
# every stored page in it -- 295 586 files, see measurements/error-pages-2026-09-27.md:
#
#     the loose vocabulary below            2 357 findings, of which ~2 275 are DOCUMENTS
#     the title IS a stock status phrase       82 findings, 5 distinct titles, all genuine
#
# The collection holds an IBM technical-support knowledge base, IBM PS/2 maintenance manuals, the
# Bison and Emacs manuals and an AIX message reference. Their pages are titled `Error Log`,
# `Numeric Error Codes`, `Appendix B. ODM Error Codes`, `Bison 1.25 - Error Recovery`. A rule that
# reports those is not a rule.
#
# TWO DISCRIMINATORS WERE TRIED FIRST AND BOTH ARE MEASURABLY WRONG, recorded so neither is
# reinvented:
#
#   title LENGTH   The real error pages have short titles (11-21 characters) and the HP Labs
#                  false ones long ones (54-79), which looked decisive on 13 examples. Over the
#                  whole collection the SHORTEST titles of all are `Error Log` at 9 characters --
#                  IBM PS/2 manual pages. Backwards.
#   file SIZE      An error page is a stub, so a body threshold should separate them. The
#                  SMALLEST findings in the collection are 284-byte PS/2 manual frames. Also
#                  backwards.
#
# What did work is neither: a stock error page's title IS the status phrase and nothing else,
# while a document's title is a sentence that contains one.
STOCK = "stock"
WEAK = "weak"

# The phrases a server uses when it is the SERVER talking. A title that reduces to exactly one of
# these is that page; a title that merely contains one is a document about it.
STOCK_ERROR_TITLES = frozenset((
    "not found", "file not found", "page not found", "object not found",
    "document not found", "document not found message", "no such file",
    "no such file or directory", "file or directory not found",
    "forbidden", "access denied", "permission denied", "unauthorized", "unauthorised",
    "internal server error", "service unavailable", "bad gateway", "bad request",
    "gateway timeout", "request timeout", "moved permanently", "temporarily unavailable",
    "error", "an error occurred", "error occurred",
))

# A leading status code, with or without the words a server puts in front of it: `404 `,
# `404 - `, `HTTP 500: `, `Error 403 `.
LEADING_STATUS = re.compile(r"^(?:http[ /]?)?(?:error[ :-]*)?(\d{3})\b[\s:.,-]*", re.I)

# Anything that is not a letter, a digit or a space. Titles arrive with `!`, `:`, quotes and
# non-breaking spaces; `NGC Error !` and `NGC Error!` must normalise alike.
TITLE_JUNK = re.compile(r"[^a-z0-9 ]+")

# A site's own name in front of its message: `IBM PartnerWorld for Developers : Document not
# found message`, `Hewlett-Packard: Page Not Found`, `Acme | Not Found`. Bounded to 40 characters
# so it cannot eat a whole sentence.
#
# A COLON OR A BAR NEEDS NO SPACE IN FRONT OF IT AND A DASH DOES, which is not fussiness: `Site:
# Message` is the commonest form there is, while a dash with no space around it is usually part of
# a NAME -- `Hewlett-Packard` would otherwise be split at its own hyphen and judged as
# `Packard: Page Not Found`. Found by a test using a real title; the first version required
# whitespace before every separator and matched neither of the two forms in the measured data.
TITLE_PREFIX = re.compile(r"^.{2,40}?\s*(?::|\|)\s+|^.{2,40}?\s+(?:--|-)\s+")


def normalise_title(title):
    """-> a title reduced for comparison: lower case, no leading status code, no punctuation."""
    t = LEADING_STATUS.sub("", title.strip().lower())
    return " ".join(TITLE_JUNK.sub(" ", t).split())


def stock_error_title(title):
    """-> the stock phrase this title IS, or None when it merely contains one.

    THE ONE RULE THAT SURVIVED MEASUREMENT. Over 2 357 loose findings in this collection it keeps
    82 and drops 2 275, and the 82 are five distinct titles -- `404 Not Found`, `File Not Found`,
    `404 - File or directory not found.`, `Document not found message` and IBM PartnerWorld's
    prefixed form of the last. Every one is a server talking.

    A SITE PREFIX MAY BE DROPPED, but only in front of a phrase of two words or more. Otherwise
    `ECA 024 - 113 error` reduces to the bare word "error" and is kept, and it is a BBS bulletin
    about error 113, not a server saying anything. Measured: that one exception is the difference
    between 84 findings and 82, and both of the two it removes are false.
    """
    n = normalise_title(title)
    if n in STOCK_ERROR_TITLES:
        return n
    n = normalise_title(TITLE_PREFIX.sub("", title, count=1))
    if n in STOCK_ERROR_TITLES and " " in n:
        return n
    return None


def looks_like_an_error_page(head):
    """-> (which complaint, how good the evidence is, the title), or None.

    THE MIDDLE FIELD IS STOCK OR WEAK AND A CALLER MUST LOOK AT IT. STOCK means the title IS a
    server's status phrase; WEAK means it merely contains an error word. Over this collection the
    difference is 82 findings against 2 357, and the 2 275 that separate them are documents -- see
    the note above STOCK. A sweep of the whole collection is only usable on STOCK; WEAK is for one
    archive at a time, where a person reads the handful that come back.

    THE POINT IS A WRONG PAGE UNDER A RIGHT NAME, which is the one case nothing here could see.
    magic_mismatch() finds HTML wearing another format's extension; find-html-imposters.py hunts
    the same thing across the collection. Both start from a name that is already suspect. This
    starts from the page.

    THE FILE THAT MADE IT NECESSARY: spider.seds.org/ngc/ holds eight `.cgi` files, fetched with
    HTTP 200, and SIX OF THEM ARE ERROR PAGES -- `NGC Error !`, `Erreur NGC !`, `NGC/IC Error!`,
    `Error in revngcic.cgi`, 150 to 1 303 bytes each. Nothing reported them and nothing was
    wrong: `.cgi` is in PROGRAM_PAGE_EXTENSIONS, so HTML under that name is exactly what is
    expected. The two real pages beside them are titled `Digital Sky Survey image`, and the title
    is the ONLY thing that separates the two groups.

    THE TITLE ONLY, AND NOT THE BODY. find-html-imposters.py matches its table against the whole
    head, which is right for its question -- it already knows the name is wrong, so any mention
    of an error is a clue. Here the name is right, so only what the page SAYS ABOUT ITSELF counts.
    Against a body, every page carrying the word "error" in a paragraph would be reported, and in
    a collection of hardware manuals that is thousands of them. It is the same argument
    INDEX_PAGE makes: no genuine document says that about itself in its title.

    IT IS A REPORT, NOT A VERDICT, so it returns the complaint AND the title rather than True.
    A caller printing "seds-frommert ngc/ngc.cgi  error  \"NGC Error !\"" has said everything a
    reader needs; a caller printing "suspicious" has sent somebody to open the file.

    THE SIX SEDS PAGES ARE WEAK, and that is the honest shape of this problem rather than a
    shortcoming to fix later. `NGC Error !` is a title an application invented, and nothing
    separates it from `Error Log` -- a real IBM PS/2 manual page, nine characters, 284 bytes --
    except knowing that spider.seds.org holds no error-code documentation and ps-2.kev009.com is
    made of it. That is knowledge about an archive, which is a caller's to have, not a library's.

    WHAT IT WILL STILL GET WRONG, said plainly because it is a documentation collection: a manual
    genuinely titled `Error Codes` or `POST Error Messages` is a true document and a false
    finding. Measured over every page in this collection before this was shipped -- see
    measurements/error-pages-2026-09-27.md for the count and for the titles. That is why this
    reports rather than acts, and why nothing deletes on its strength.

    AND WHAT IT WILL MISS, which is the larger half and was measured at the same time. The
    COMMONEST error page in this collection is titled `Bull Freeware`; the GeoCities one is
    `Yahoo! GeoCities` and the Wayback one `Internet Archive Wayback Machine`. Each is a site's
    own template served where a file was expected, and NONE of them admits to anything, so this
    answers None for all three -- correctly, by its own rule, and uselessly. They are caught
    instead by magic_mismatch(), because their NAMES are wrong.

    THE TWO HALVES ARE COMPLEMENTARY AND NEITHER COVERS THE GAP BETWEEN THEM:

        wrong name, any content          magic_mismatch() -- Bull, GeoCities, Wayback
        right name, admitted failure     this -- the six seds `.cgi` pages
        right name, SILENT wrong page    nothing here finds it

    The third row is written down rather than discovered twice. Fixtures for all three are in
    testdata/heads/, with real bytes.
    """
    if not looks_like_html(head):
        return None
    title = page_title(head)
    if not title:
        return None
    if stock_error_title(title):
        for kind, pattern in PAGE_COMPLAINTS:
            if pattern.search(title):
                return kind, STOCK, title
        return "error", STOCK, title
    for kind, pattern in PAGE_COMPLAINTS:
        if pattern.search(title):
            return kind, WEAK, title
    return None


# WHAT KIND OF WRONG PAGE THIS IS, judged from the WHOLE BODY rather than from the title.
#
# THE SECOND OF TWO TABLES AND THEY MUST STAY TWO. PAGE_COMPLAINTS above is asked of a file whose
# NAME IS RIGHT, so only what the page says about itself can count and a bare `404` is banned --
# `HP 404 Calculator` is a real title here. This one is asked of a file whose NAME IS ALREADY
# WRONG: a `.bin` holding markup is a defect whatever the markup says, and the label only decides
# how it is likely to be recovered. There the loose patterns cost nothing and catch more, so
# `\b404\b` and `\b5\d\d\b` are in. Folding the tables would either blind this one or make the
# other report thousands of manuals.
#
# A server that is unhappy has more than one way to say so, and each produces a file a fetcher
# accepts with status 200:
#
#     index       a directory listing saved where a file was expected -- which additionally
#                 blocks everything below that path, because a filesystem cannot hold a file and
#                 a directory under one name
#     soft-404    "404" or "not found" in a page served with status 200
#     forbidden   403 pages, "access denied", login walls
#     redirect    a refresh meta or a "moved" stub instead of the content
#     parking     the host is gone and a registrar or free-host placeholder answers
#     error       everything else that announces a failure
#
# THE ORDER IS DELIBERATE, first match wins, and `error` is last for the same reason it is last in
# PAGE_COMPLAINTS: it matches nearly everything the others do.
PAGE_KINDS = (
    ("index",     INDEX_PAGE),
    ("soft-404",  re.compile(rb"\b404\b|not\s+found|no\s+such\s+file|does\s+not\s+exist", re.I)),
    ("forbidden", re.compile(rb"\b403\b|forbidden|access\s+denied|permission\s+denied|"
                             rb"unauthori[sz]ed|sign\s*in|log\s*in\s+to", re.I)),
    ("redirect",  re.compile(rb"http-equiv\s*=\s*[\"']?refresh|\b30[12]\b|moved\s+(permanently|"
                             rb"temporarily)|document\s+has\s+moved", re.I)),
    ("parking",   re.compile(rb"domain\s+(is\s+)?for\s+sale|this\s+domain|parked|"
                             rb"under\s+construction|default\s+web\s+site|it\s+works!", re.I)),
    ("error",     re.compile(rb"\berror\b|\b5\d\d\b|internal\s+server|service\s+unavailable|"
                             rb"bad\s+gateway|temporarily\s+unavailable", re.I)),
)

# What a page is called when it is real markup with nothing wrong announced in it. Named rather
# than spelled inline, because it is the value a caller filters on.
ORDINARY_PAGE = "page"


def classify_page(blob):
    """-> which kind of wrong page these bytes are, or ORDINARY_PAGE when none of them.

    A HINT FOR TRIAGE, NOT A VERDICT. What makes a file wrong is that a `.bin` contains markup at
    all; which flavour it is only decides how it is likely to be recovered. Callers report it and
    nothing acts on it.

    ORDINARY_PAGE IS AN ANSWER, not a failure to answer -- real HTML with no failure markers,
    often perfectly legitimate, and reported separately by every caller so far.
    """
    for name, pattern in PAGE_KINDS:
        if pattern.search(blob):
            return name
    return ORDINARY_PAGE

# A 200 FROM ONE OF THESE IS A DOMAIN THAT WAS SOLD, not a site that came back. Matched against
# the TITLE. Seeing it is the difference between "spscicomp.org answers" and "spscicomp.org is
# for sale", and no status code can tell those apart.
#
# The hosting-provider names are there for the same reason: `www.spscicomp.org` answers 200 with
# the title "Welcome spscicomp.org - BlueHost.com" -- an account that exists with nothing on it,
# which is not the IBM HPC user group's proceedings coming back.
PLACEHOLDER_TITLES = (
    "domain is for sale", "buy this domain", "parked", "godaddy", "sedo",
    "hugedomains", "this domain", "afternic", "namecheap", "under construction",
    "default web site page", "welcome to nginx", "apache2 ubuntu default",
    "bluehost", "hostgator", "dreamhost", "siteground", "ionos", "future home of",
    "site not configured", "coming soon",
)

# Default server pages, matched against the BODY because they carry no title at all.
STUB_BODIES = (
    "it works!", "test page for the apache", "if you can read this page",
    "this is the default", "web server's default page",
)

# A 200 too small to be a page. `download.aixtools.net` answers with 44 bytes of Apache's stock
# "It works!" -- no title, so a title-only test calls it alive and puts a permanent `!!` on an
# archive whose own marker says the origin is gone.
STUB_BYTES = 200

# How far into a body a stub marker still counts. A real page that happens to quote one of those
# phrases further down is not a stub.
STUB_WINDOW = 600

# NOT IN EITHER TABLE, DELIBERATELY, AND THIS IS THE RULE MOST WORTH RE-READING: "Index of /".
# An Apache autoindex is the single most PROMISING thing a dead-looking host can answer -- it
# means there are files there to walk. Adding it as a placeholder marker would silence exactly
# the finding these tools exist to make. The first draft of STUB_BODIES had "<h1>index of" in it,
# three lines under the comment warning against that, so the rule is stated again here.


def looks_like_a_placeholder_page(body, title=None):
    """-> (why, the evidence) when this answer is not a site, or None when it may be one.

    `why` is "stub" for a server's own default page and "parked" for a title that sells or
    advertises the domain. The two are told apart because they mean different things: a stub is a
    machine with nothing on it, a parked domain is somebody else's machine.

    A STATUS CODE CANNOT ANSWER THIS. A lapsed domain is bought, parked, and answers 200 forever.
    The page has to be read, and this is the cheapest thing that separates a revived archive from
    a sales page.

    `title` is taken as given when passed -- the caller usually has it already -- and read with
    page_title() otherwise. Bytes or str, because one caller has a decoded response body.

    AN AUTOINDEX IS NEVER A PLACEHOLDER. See the note above the tables: it is the best possible
    answer here, and a rule that silenced it would defeat the tools that call this.
    """
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    if len(body) < STUB_BYTES:
        return "stub", "%d bytes, too small to be a page" % len(body)
    low = body.lower()[:STUB_WINDOW]
    for marker in STUB_BODIES:
        if marker in low:
            return "stub", marker
    if title is None:
        title = page_title(body) or ""
    low_title = title.lower()
    for marker in PLACEHOLDER_TITLES:
        if marker in low_title:
            return "parked", marker
    return None


# HOW LITTLE FREE SPACE IS TOO LITTLE TO GO ON FETCHING. A gigabyte, which is not a guess about
# disks but about what a partly-written file costs: the run stops with room to finish the one in
# flight and to write the index beside it. Two fetchers each decided this separately and agreed;
# they no longer have to.
MIN_FREE_BYTES = 1 * 10 ** 9

# The line a run writes when a name could not be stored because another differing only in case
# already held it. TWO TOOLS READ IT BACK -- one to re-fetch what was dropped, one to audit what
# was lost -- and a log line that is read is a format, not a message.
COLLISION_DROPPED = re.compile(
    r"COLLISION DROPPED \S+ <- (\S+) \(already claimed by (\S+)\)")

# THE LINE A FETCH WRITES WHEN IT GIVES UP ON A FILE, and a second tool reads it to decide what
# to do about the gap. A log line that is read is a FORMAT, not a message -- the same argument
# COLLISION_DROPPED above makes, and the same reason it lives here rather than in the reader.
#
#     2026-09-27 11:03:36 FAIL OSError: short read 40703264 of 116150679 https://host/path.zip
#     2026-09-14 05:21:47 FAIL HTTP 500 https://host/cgi/x.pl
#
# THE URL IS LAST AND THE REASON IS NOT PARSED. Measured over every errors-*.txt this collection
# has written -- 680 FAIL lines: the reason is free text and comes in at least six shapes,
# including an OSError whose message embeds two Windows long paths and a URLError whose message
# contains a NEWLINE. Three of the 680 lines therefore do not end in a URL at all. Reading from
# the LAST `://` to the end of the line, and only when there is one, is what survives that.
#
# A URL MAY CONTAIN A SPACE, which the first version of this pattern got wrong. It read
# `(\S+://\S+)$` and would have skipped, in silence, exactly the files this collection is most
# likely to lose: a server that LINKS an unescaped space -- see quote_url(), which exists because
# one archive here serves `AS400 Processor Summary.html` that way. Measured the day it was
# written: 0 of the FAIL lines carry a space, and 333 PERMFAIL lines do. The shape is real, it
# had simply not yet landed on a file that was given up on, and a gap-filler reading this would
# have passed over it without a word.
#
# THE LAST `://` WINS, because the reason may contain anything. Measured against the six shapes
# on disk: none of the reason texts contains `://` -- the PermissionError one embeds Windows
# paths, which do not -- so the last occurrence is the url the line is about.
# THE GROUP STARTS AT A WORD BOUNDARY, which the second version of this pattern also got
# wrong: `.*(\S+://...)` lets the greedy `.*` eat as far as `http` and leaves the group
# matching `s://host/path`. Caught immediately because the check ran against a real line.
FETCH_FAILED = re.compile(r"^\S+ \S+ FAIL (?:.*\s)?(\S+://.*\S)\s*$", re.M)


def failed_urls(text):
    """-> the urls a fetch gave up on, in order, without repeats.

    ORDER IS KEPT AND REPEATS ARE NOT, because an errors file accumulates across runs: the two
    vgamuseum ZIPs appear eight times between them, once per attempt over two days, and a caller
    filling gaps wants two pieces of work and not eight.

    A RETRY LINE IS NOT A FAILURE. `RETRY 2/3` says the fetch is still trying; only `FAIL` says it
    stopped. Matching both would report files that arrived on the third attempt as missing, and
    this collection's error files are full of those.
    """
    out = []
    seen = set()
    for m in FETCH_FAILED.finditer(text):
        url = m.group(1)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out

def file_extension(name):
    """-> the lowercase suffix of a STORED FILE NAME, or "" when it has none.

    NOT URL-AWARE, ON PURPOSE. `#` and `?` are ordinary characters in a file name, and this
    collection is full of them: `Forvus_Technical_Bulletin_#107.pdf`, `SS#7_Protocol_Set_ANSI_
    Reference_Manual_Nov1990.pdf`. A first version of page-extensions.py ran every stored name
    through urlsplit() first and answered "no extension" for 208 PDFs, because urlsplit read
    `#107.pdf` as a fragment. Ask url_extension() when the string really is a url.

    A NAME ENDING IN A DOT HAS NO EXTENSION, which os.path.splitext does not agree with: it
    answers "." for `TALK.`, and 25 stored names in this collection end that way. They are the
    same names long_path() exists for, because Windows strips a trailing dot while OPENING the
    file, and an extension of "." is a value no caller has a use for.

    A LEADING DOT IS A NAME, NOT A TYPE -- `.gitignore` is a file called that, not a file of type
    "gitignore". splitext already agrees, and it is said here because the opposite mistake was
    made elsewhere in this collection with lstrip(".").
    """
    ext = os.path.splitext(name)[1]
    return "" if ext == "." else ext.lower()


def url_extension(url):
    """-> file_extension of what a url ADDRESSES: query and fragment removed first.

    `a.html?v=2` and `a.html#top` both address a page called a.html. Keeping the query would make
    `.html?v=2` an extension of its own, which is how a census grows a row per sort order.

    A URL ENDING IN "/" HAS NO EXTENSION, even when its last segment is spelled `icons.gif/` --
    and one directory in this collection is. It addresses a DIRECTORY; mirror.py branches on that
    slash long before any extension is consulted, and answering `.gif` would file a directory
    among the images.
    """
    return file_extension(urllib.parse.urlsplit(url).path)


def is_partial(name):
    """Is this the name of a transfer that did not finish, rather than of content?"""
    return name.lower().endswith(PARTIAL_SUFFIXES)


def looks_like_html(head):
    """Do these first bytes begin an HTML or XML document?

    A leading byte-order mark or whitespace is skipped: a server that pads its error page does
    not thereby make it a PDF.

    AND SO IS A LEADING COMMENT, which was missing and mattered. The commonest error page in this
    collection opens `<!-- Copyright (C) Bull SAS - 2019 -->` and only then `<!DOCTYPE html>`, so
    every one of them was reported as "does not begin with the .jpg signature" instead of "HTML
    under a .jpg name" -- the vague answer that sends somebody to open the file, for the one page
    that had already been identified three times over on 2026-09-24: under `.exe` by --listed,
    under eight `.rpm` names and under 28 image names by --ruins.

    A COMMENT IS SKIPPED, NOT TREATED AS PROOF. `<!--` alone does not make a file HTML; what
    follows the comment still has to. An unterminated comment inside the bytes we were given is
    not an answer either, so it returns False rather than guessing -- this reads a fixed-size
    head, and "the document may continue" is not the same as "it does".
    """
    if not head:
        return False
    if head[:3] == b"\xef\xbb\xbf":
        head = head[3:]
    head = head.lstrip()
    for _ in range(8):                      # bounded: a page prefaced by a licence block
        if not head.startswith(b"<!--"):
            break
        end = head.find(b"-->", 4)
        if end < 0:
            return False
        head = head[end + 3:].lstrip()
    return head[:5].startswith(HTML_HEADS)


# Leading bytes that mean "this is markup", for HUNTING rather than for classifying. Checked after
# a BOM and whitespace are stripped and against LOWER-CASED bytes.
#
# DELIBERATELY WIDER THAN HTML_HEADS, and the two must not be folded. HTML_HEADS classifies a body
# whose type is already known, so it is narrow on purpose; this set accepts a page opening with a
# comment, a <meta> or a <title>, because a served error page often begins with one of those.
# Folding them would either blind the hunt or make magic_mismatch() report ordinary files as HTML.
MARKUP_HEADS = (b"<!doctype", b"<html", b"<head", b"<?xml", b"<!--", b"<meta", b"<title")

# A file that opens with one of these IS that format, whatever appears later in the buffer. This
# check must come FIRST, and it exists because of one false positive worth remembering:
# os2bbs/science/gmt4os2.zip, 17 957 583 bytes, is a real ZIP whose first member is an
# UNCOMPRESSED gmt4os2.html -- so `<HTML>` sits at byte 0x30, inside the local file header, and a
# scan of the first 512 bytes called an 18 MB archive an error page. Container formats carry other
# formats; that is what they are for.
#
# NOT DERIVED FROM MAGIC, on purpose. MAGIC maps an EXTENSION to what it must open with, and is
# used to catch a file that contradicts its own name. This is a flat set of "some known format
# starts here", and it holds openings MAGIC has no extension for -- MZ, ELF, XCOFF, several image
# formats -- because the question is only "is this binary", never "is this the right binary".
BINARY_MAGIC = (
    b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08",            # zip and friends
    b"MZ", b"%PDF", b"\x1f\x8b", b"\x1f\x9d", b"\x1f\xa0",  # exe, pdf, gzip, compress
    b"BZh", b"Rar!", b"7z\xbc\xaf\x27\x1c", b"\xfd7zXZ",    # bzip2, rar, 7z, xz
    b"\xed\xab\xee\xdb",                                    # rpm
    b"\x01\xdf", b"\x01\xf7", b"\x7fELF",                   # XCOFF32/64, ELF
    b"GIF8", b"\x89PNG", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*", b"BM",
    b"\xd0\xcf\x11\xe0", b"\x00\x00\x01\x00", b"OggS", b"RIFF", b"\x00\x01\x00\x00",
    b"SQLite format 3", b"!<arch>", b"\x1aVersion", b"<bff>", b"\x08\x02",
)

# How far into a file a stray `<html` still counts. Bounded so a text file that merely MENTIONS
# markup further down is not swept up.
MARKUP_WINDOW = 512


def looks_like_markup(head):
    """-> True if these bytes open an HTML/XML document, and are not a container that holds one.

    THE HUNTING QUESTION, where looks_like_html() is the classifying one. A caller using this is
    looking for a page that has no business being where it is, so it accepts an opening comment,
    a bare <meta> or <title>, and a `<html` a little further in. A caller using looks_like_html()
    already knows what the file is meant to be and wants a narrow answer.

    THE CONTAINER CHECK COMES FIRST AND IS NOT OPTIONAL -- see BINARY_MAGIC for the 18 MB ZIP that
    was reported as an error page because its first member was an uncompressed .html.
    """
    if not head:
        return False
    if head.startswith(BINARY_MAGIC):
        return False
    b = head.lstrip(b"\xef\xbb\xbf").lstrip()          # BOM, then whitespace
    if b[:64].lower().startswith(MARKUP_HEADS):
        return True
    return b"<html" in b[:MARKUP_WINDOW].lower()


def magic_mismatch(name, head):
    """-> a reason this file's bytes contradict its name, or None.

    THE POINT IS NOT TYPE-CHECKING, it is finding what a crawl stored under the wrong name. An
    error page, a login form or a saved directory listing arrives with status 200 and a matching
    Content-Length; every counter agrees, and only the first four bytes disagree.

    None is returned for an extension with no known opening, because "I have no opinion" and
    "this is fine" must not be the same answer.
    """
    ext = file_extension(name)
    if not head:
        return None
    if INDEX_PAGE.search(head):
        return "a generated directory listing saved as a file"
    expected = MAGIC.get(ext)
    if expected is None:
        return None
    if head.startswith(expected):
        return None
    if looks_like_html(head):
        return "HTML under a %s name" % ext
    # IS IT ANOTHER FORMAT THIS TABLE ALREADY KNOWS? Saying so costs one loop over nine entries
    # and changes what the reader has to do: "does not begin with the .jpg signature" sends
    # somebody to open the file, while "a .gif under a .jpg name" is finished. Measured
    # 2026-09-24: of 108 image mismatches 30 are exactly this, and of the 26 280 findings over
    # the whole collection 582 are a gzip stored under `.Z` and 84 a compress(1) under `.gz` --
    # old habits rather than damage, and each one was costing a reader a look.
    for other, sigs in MAGIC.items():
        if other != ext and head.startswith(sigs):
            return "a %s under a %s name" % (other, ext)
    return "does not begin with the %s signature" % ext



# ------------------------------------------------------------- the index and the marker
#
# THREE FILES DESCRIBE A FINISHED TREE, and every tool that writes or reads one must agree with
# every other about the bytes. They did not: the sums line was written out by hand in two places
# with two different rules, and the marker was parsed inline in two more. What follows is the
# single copy.


# Files handed to the thread pool at once, which is also how often the index is persisted.
# Submitting a whole tree -- 190 000 entries for the largest archive here -- would build the very
# in-memory list the bounded queue exists to avoid.
HASH_BATCH = 2000


def sfv_line(crc, rel):
    """One line of a .sfv: `<name> <CRC32>`, the COLUMNS THE OTHER WAY ROUND from sha256sum(1).

    That reversal is the whole hazard of this format. `sha256sum` writes `<hash> *<path>` and an
    .sfv writes `<path> <hash>`, so a reader that splits from the left gets the first word of a
    filename with a space in it. sfv-verify.py splits from the RIGHT for exactly this reason, and
    this writer is its counterpart: what we emit has to be what we already know how to read.

    No `;` comment line is written per file. RHash puts size and mtime there and sfv-verify.py
    deliberately does not parse them as authority -- writing our own would invite some later
    reader to.
    """
    return "%s %s\n" % (rel, crc)


def sums_line(digest, rel):
    """One line of sha256sum(1) output, in binary mode.

    `*` is the binary-mode marker, which is what this content is. GNU escapes a path containing a
    backslash or a newline by prefixing the whole line with one backslash; neither character can
    occur in a Windows filename, so this never fires here -- it is written down so that the format
    stays CORRECT rather than accidentally correct.
    """
    if "\\" in rel or "\n" in rel:
        return "\\%s *%s\n" % (digest, rel.replace("\\", "\\\\").replace("\n", "\\n"))
    return "%s *%s\n" % (digest, rel)


def iter_tree(root, own_files=None):
    """Yield (relative path, full path) for every file that counts as CONTENT.

    THE SINGLE DEFINITION OF WHAT IS IN A TREE. A counting pass and a hashing pass that each
    walked with their own copy of the rules would agree at first and diverge silently later, and
    the two figures they produce are exactly the ones a later check compares against.

    Distinct from iter_files(), and deliberately: that one skips the WIDE bookkeeping set and
    keeps partial transfers, because it describes a directory. This one skips the NARROW own-file
    set and drops partials, because it describes an archive's contents. Folding them together
    would put four hand-written notes into a count that must not contain them.

    A TRANSFER THAT DID NOT FINISH IS NOT CONTENT. `.part` is half a download -- one outage left
    11 of them holding 741 MB -- and `.suspect` is one that completed and then failed
    verification. Counting either inflates the figure a later check compares the tree against,
    and puts a truncated file into the index under a hash that is perfectly valid for the wrong
    bytes. `.superseded` was missed at first: `X.suspect.superseded` does not end in `.suspect`,
    so a two-suffix test let 15 of them back in and three archives were reported as changed for a
    reason that was pure bookkeeping. A file kept as evidence of a failure is not content.

    Relative paths use forward slashes on every platform, because they are written verbatim into
    a file that `sha256sum -c` has to be able to read on a Unix box.

    THE SUFFIX TEST HERE IS CASE-SENSITIVE AND is_partial() IS NOT, and that is deliberate in
    both. is_partial() answers a question about a name, for a report. This one decides what goes
    into A COUNT THAT MARKERS ON DISK WERE ALREADY WRITTEN AGAINST. A tree of software from the
    uppercase era can hold a genuine `SOMETHING.PART` -- a split archive volume, not a half
    download -- so folding case here would drop it from the count and every marker written before
    the change would report a mismatch for a change nobody made. A rule that decides what counts
    as content may be widened only DELIBERATELY, never as a side effect of sharing code.
    """
    if own_files is None:
        own_files = OWN_FILES
    root = root.rstrip("\\/")
    for dirpath, _dirnames, names in os.walk(root):
        top = os.path.normcase(dirpath) == os.path.normcase(root)
        for f in names:
            if f.endswith(PARTIAL_SUFFIXES):
                continue
            # Only at the top: an archive may legitimately contain a README.md of its own.
            if top and f in own_files:
                continue
            full = os.path.join(dirpath, f)
            rel = relative_to(root, full)
            if rel is not None:
                yield rel, full


def scan_tree(root, own_files=None, report=None):
    """-> (file count, total bytes) over what iter_tree() calls content.

    THROUGH long_path(), AND A FAILURE IS REPORTED RATHER THAN SWALLOWED. Without the prefix,
    getsize() fails on any name ending in a dot or a space -- `TALK.` raises "the system cannot
    find the file" for a file the walk has just handed us and which is plainly there. An earlier
    `except OSError: pass` therefore left 21 files out of every figure this function feeds, and a
    tree could lose files and still report unchanged forever.

    Swallowing was the worse half of that bug, not the missing prefix. A file that fails EVEN
    THROUGH the prefix is a different thing and does still happen -- an rsync-created symlink
    whose target does not resolve raises WinError 1920 -- and it must not stop the pass for the
    other 12 138 files. So: loud, not fatal, and never silent.
    """
    n = total = 0
    for rel, full in iter_tree(root, own_files):
        try:
            total += os.path.getsize(long_path(full))
        except OSError as exc:
            (report or _unreadable)(rel, exc)
            continue
        n += 1
    return n, total


def _unreadable(rel, exc):
    print("     UNREADABLE %s -- %s" % (rel, exc.__class__.__name__), flush=True)


def read_index(path):
    """Load an index: relative path -> (size, mtime_ns, sha256).

    A MISSING OR DAMAGED INDEX IS NOT AN ERROR AND IS NOT FATAL. The index is a cache of work
    already done, and every row is revalidated against the file's own size and mtime before it is
    reused -- so damage here costs time, never correctness. Returning {} and rehashing is the
    right answer; refusing to start is not.
    """
    out = {}
    try:
        with open(long_path(path), "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    out[row["path"]] = (int(row["size"]), int(row["mtime_ns"]), row["sha256"])
                except (KeyError, TypeError, ValueError):
                    continue
    except OSError:
        return {}
    return out


def write_manifests(archive_dir, digests, want=("sha1", "md5", "crc32")):
    """Write the weaker manifests beside the sha256 one, from one mapping, atomically.

    `digests` is {relative path: {algorithm: hex}} -- the shape digests_of_file returns, one entry
    per file. -> the paths written.

    ONE MAPPING, WRITTEN IN ONE CALL, and that is the only defence against the failure this
    collection has already had. Eight tools once each kept their own idea of which files were
    bookkeeping and no two agreed -- 0 identical pairs out of 28. Four manifests of the same tree,
    written from four places at four times, would go the same way, and a manifest that disagrees
    with its neighbours is worse than a missing one: it looks like evidence.

    SHA-256 IS NOT WRITTEN HERE, on purpose. `.sha256sum` is derived from the CSV index by
    write_index(), which is checkpointed DURING a long hash run so an interruption leaves a valid
    partial index. These three describe a finished pass and are written once at the end of it.
    Two writers, two lifetimes, and the one that must survive an interruption is the one that
    already does. A test asserts all four cover the same set of paths.

    A FILE WHOSE DIGEST IS MISSING IS SKIPPED RATHER THAN WRITTEN BLANK. A manifest line with an
    empty hash passes `-c` on nothing and reads as a check that was made.

    AND A MANIFEST WITH NO LINES AT ALL IS NOT WRITTEN, which the first trial on a real archive
    found the hard way. csri-toronto's index was already current, so nothing was re-hashed, so
    there was nothing to write -- and three EMPTY files appeared beside a populated .sha256sum.
    `md5sum -c` over zero lines reports success, which is the shape this collection distrusts most:
    a clean zero that looks like a verification. An absent file says "not done yet" and cannot be
    mistaken for anything else.
    """
    ordered = sorted(digests.items())
    written = []
    for algo in want:
        name = MANIFEST_FILES[algo]
        path = os.path.join(archive_dir, name)
        if not any(got.get(algo) for _rel, got in ordered):
            continue
        tmp = path + ".tmp"
        with open(long_path(tmp), "w", encoding="utf-8", newline="") as fh:
            for rel, got in ordered:
                value = got.get(algo)
                if not value:
                    continue
                fh.write(sfv_line(value, rel) if algo == "crc32" else sums_line(value, rel))
        os.replace(long_path(tmp), long_path(path))
        written.append(path)
    return written


def read_sums(path):
    """-> {relative path: digest} from a sha256sum(1)-format file. A missing file gives {}.

    The line is `<hex> *<path>` and a path may contain spaces, so the split is on the FIRST ` *`
    rather than on whitespace. That separator was written out by hand in four places before
    2026-10-02 -- mirror.py and three tests -- which is how one format comes to have four slightly
    different opinions about a filename that contains " *" itself.

    GNU's leading-backslash escape is not decoded; such a line is SKIPPED rather than guessed at.
    Neither a backslash nor a newline can occur in a Windows filename, so nothing here can produce
    one, and a file that carries one came from somewhere else and is better noticed than
    half-read.
    """
    out = {}
    if not exists(path):
        return out
    with io.open(long_path(path), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("\\"):
                continue
            digest, sep, rel = line.partition(" *")
            if sep and digest and rel:
                out[rel] = digest
    return out


def read_manifests(archive_dir, want=("sha1", "md5", "crc32")):
    """-> {rel: {algorithm: hex}} from whatever manifests the archive already carries.

    WHY A READ-BACK EXISTS AT ALL. An index run hashes only what changed -- that is what makes a
    re-run over a finished archive cost a stat of the tree instead of a read of it. The files it
    carries over therefore have no weaker digests in hand, and writing the manifests from the run's
    own results alone would shrink them to whatever happened to be re-hashed. The first incremental
    run after the one-time full pass would have thrown nearly all of it away.
    """
    out = {}
    for algo in want:
        path = os.path.join(archive_dir, MANIFEST_FILES[algo])
        pairs = (read_sfv(path) if algo == "crc32" else read_sums(path).items())
        for rel, value in pairs:
            out.setdefault(rel, {})[algo] = value
    return out


def manifest_coverage(archive_dir, want=DIGESTS):
    """-> {algorithm: how many files that archive's manifest covers}. 0 for one not written yet.

    A MANIFEST COVERING ONE FILE LOOKS EXACTLY LIKE A MANIFEST COVERING ALL OF THEM, and
    `md5sum -c` over it reports success. That is the whole reason this exists.

    FOUND ON 2026-10-03, AND NOT BY A TOOL. nice-next carried an index of 4 540 files and a
    .sha256sum of 4 540 -- and a .sha1sum, .md5sum and .sfv of ONE LINE EACH. A single README had
    been fetched the day before and an INCREMENTAL index run wrote the three weaker manifests from
    just that file: the read-back in read_manifests above cannot carry over digests that were never
    there, and those three manifests did not exist yet. build_index does print "N of M files carry
    the weaker digests" when it notices, and that line was printed, and nobody acted on it.

    WHAT HID IT AFTERWARDS was a check of my own that asked whether the four files EXIST. All 113
    archives answered yes, including this one. Existence is not coverage, and a count of lines
    would have said so in the same second.
    """
    cover = {}
    for algo in want:
        path = os.path.join(archive_dir, MANIFEST_FILES[algo])
        if algo == "crc32":
            cover[algo] = len(read_sfv(path))
        else:
            cover[algo] = len(read_sums(path))
    return cover


def read_sfv(path):
    """-> [(filename, CRC32 as upper-case hex)] from a .sfv. Unreadable lines are skipped.

    MOVED HERE FROM sfv-verify.py ON 2026-10-02, when this collection started WRITING .sfv files
    as well as reading somebody else's. A format with a reader in one file and a writer in another
    is a format with two opinions; `sfv_line` and this function are now the same pair.

    Lines beginning with `;` are comments -- RHash puts size and mtime there, which is useful to a
    human and is deliberately not read as authority. The data line is `<name> <8 hex digits>`, and
    THE NAME MAY CONTAIN SPACES, so the split is from the RIGHT.

    A MISSING FILE IS AN EMPTY LIST, and this was learned the moment it moved here. As
    sfv-verify.parse_sfv it was only ever called on a path a person had typed, so a missing file
    was their mistake and an exception was the right answer. read_manifests calls it on a name that
    does not exist yet -- the first index run of an archive has no .sfv -- and the end-to-end run
    died on FileNotFoundError. Lifting a function into a library gives it callers with different
    preconditions; read_sums and read_index already answered this way, and now so does this.
    """
    out = []
    if not exists(path):
        return out
    with io.open(long_path(path), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            parts = line.rsplit(None, 1)
            if len(parts) != 2 or len(parts[1]) != 8:
                continue
            try:
                int(parts[1], 16)
            except ValueError:
                continue
            out.append((parts[0].replace("\\", "/"), parts[1].upper()))
    return out


def write_index(index_path, sums_path, rows):
    """Write the CSV index, then DERIVE the sums file from it. Both atomically.

    Two files, one source of truth. Deriving the second from the first -- rather than writing both
    from the same loop -- is what keeps them from ever disagreeing.

    Temporary name and rename, because the alternative is that an interrupted run leaves behind a
    half-written manifest THAT STILL LOOKS LIKE A MANIFEST, and nothing downstream can tell.
    """
    ordered = sorted(rows.items())

    tmp = index_path + ".tmp"
    with open(long_path(tmp), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(("path", "size", "mtime_ns", "sha256"))
        for rel, (size, mtime_ns, digest) in ordered:
            w.writerow((rel, size, mtime_ns, digest))
    os.replace(long_path(tmp), long_path(index_path))

    tmp = sums_path + ".tmp"
    with open(long_path(tmp), "w", encoding="utf-8", newline="") as fh:
        for rel, (_size, _mtime, digest) in ordered:
            fh.write(sums_line(digest, rel))
    os.replace(long_path(tmp), long_path(sums_path))


# The column the header values line up in. A fixed number rather than one computed from the
# longest key, so that every marker in the collection looks the same whichever tool wrote it and
# a diff of two of them shows what changed rather than how they were aligned.
MARKER_COLUMN = 14


def marker_text(fields, prose=""):
    """-> the text of a completion marker: an aligned header, a blank line, then prose.

    THE BLANK LINE IS THE FORMAT, not decoration. read_marker() stops there, and everything after
    it is for a person. A marker written by hand once explained its archive in lines beginning
    "files" and "bytes"; a reader that did not stop parsed those and died on
    int("7826  ->  94899").

    A VALUE'S OWN WHITESPACE IS COLLAPSED. A newline inside a value would put a second line into
    the header, where it would be read as another key or -- if blank -- end the header early and
    silently truncate the record. Collapsing rather than refusing is deliberate: a completed fetch
    should not go unmarked because a source URL picked up a stray character.

    A KEY WITH WHITESPACE IN IT IS REFUSED, because there is no spelling of it the reader could
    get back. That is a mistake in the calling code, not in the data.
    """
    lines = []
    for key, value in fields.items():
        if key != "".join(key.split()):
            raise ValueError("marker key %r contains whitespace and could not be read back" % key)
        width = max(MARKER_COLUMN, len(key) + 1)
        lines.append("%-*s%s" % (width, key, " ".join(str(value).split())))
    text = "\n".join(lines) + "\n"
    if prose:
        text += "\n" + prose.rstrip("\n") + "\n"
    return text


def write_marker(path, fields, prose=""):
    """Write a completion marker. -> the text written.

    LF, ALWAYS. Two tools wrote this file and only one of them said so: 66 of the 97 markers in
    this collection are CRLF and 31 are LF, because one used a plain open() on Windows and the
    other named the line ending. The sums file beside it has always been LF, and a record is read
    on whatever machine someone has. Existing markers are not touched by this; only new ones.

    THROUGH long_path, because a mirror root can be deep and the failure without it is a
    misleading "no such file" for a directory the caller has just finished writing into.

    The text is returned so a caller can log or show exactly what it wrote, rather than
    reconstructing it and being slightly wrong.
    """
    text = marker_text(fields, prose)
    with io.open(long_path(path), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return text

def read_marker(path):
    """-> the machine-readable header of a completion marker, as {key: value}.

    ONLY THE LEADING HEADER IS DATA. Everything from the first blank line on is prose for a human,
    and reading the whole file is a trap that has already fired: a marker written by hand had an
    explanation whose lines began "files" and "bytes", the reader parsed those instead of the
    header, and the run died on int("7826  ->  94899").

    Values stay strings. A caller that wants a number asks for one and decides for itself what a
    missing key means -- which is not the same decision in a checker as in a report.

    A BYTE THAT IS NOT UTF-8 IS REPLACED, NOT RAISED. catalogue.py's own copy of this reader had
    that and the library did not, so the same marker could be read by one tool and kill another.
    A marker is a record about an archive; one bad byte in it must not stop a report that is
    otherwise entirely readable.
    """
    rec = {}
    try:
        fh = open(long_path(path), encoding="utf-8", errors="replace")
    except OSError:
        return rec
    with fh:
        for line in fh:
            if not line.strip():
                break
            parts = line.split(None, 1)
            if len(parts) == 2:
                rec[parts[0]] = parts[1].strip()
    return rec


def hash_tree(entries, rows, workers, interval, checkpoint, label="", batch_size=HASH_BATCH,
              report=None, digests=None):
    """Hash `entries` into `rows` in bounded batches, checkpointing as it goes.

    `entries` is [(rel, full, size, mtime_ns)]; `rows` is the index being assembled and IS MUTATED
    IN PLACE; `checkpoint` is called with no arguments to persist it.

    A PARTIAL INDEX IS A VALID INDEX. Everything already hashed is reused by the next run, so an
    interruption costs the current batch and nothing else -- which is only true because the
    checkpoint also runs in `finally`. Without that, the work between the last timed checkpoint
    and the interruption is simply lost.

    `digests`, when a caller passes a dict, is filled with {rel: {algorithm: hex}} FOR THE SAME
    READ -- all four of DIGESTS instead of sha256 alone. The three weaker ones exist for the
    parties that could give a second opinion and do not speak sha256: B2 records sha1, the
    Internet Archive publishes md5 and never sha256, RAR and ZIP store crc32. Measured
    2026-10-02: all four together run at 309 MB/s against a disk that gives 208, so they cost the
    one pass and no wall clock. Omit the argument and nothing changes -- the extra work is not
    done at all, which is what a caller that only wants to decide `--trust-index` should ask for.

    -> (files done, bytes done, [(rel, error)], elapsed seconds)
    """
    report = report or _progress
    done = done_bytes = 0
    total_bytes = sum(e[2] for e in entries)
    failed = []
    t0 = last_print = last_write = time.time()
    # One function either way, so the two paths cannot read a file differently.
    work = digests_of_file if digests is not None else sha256_file

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            for start in range(0, len(entries), batch_size):
                chunk = entries[start:start + batch_size]
                futures = [(item, ex.submit(work, item[1])) for item in chunk]
                for (rel, _full, size, mtime_ns), fut in futures:
                    try:
                        got = fut.result()
                    except OSError as exc:
                        failed.append((rel, str(exc)))
                        continue
                    if digests is None:
                        rows[rel] = (size, mtime_ns, got)
                    else:
                        # THE CSV KEEPS ITS FOUR COLUMNS. Widening it would break every reader of
                        # the 113 indexes already on disk, for three values no verification here
                        # decides on; the weaker digests go to their own standard-format manifests
                        # instead, which is also what makes them readable without these scripts.
                        rows[rel] = (size, mtime_ns, got["sha256"])
                        digests[rel] = got
                    done += 1
                    done_bytes += size

                now = time.time()
                if now - last_print >= interval:
                    report(label, done, len(entries), done_bytes, total_bytes, now - t0)
                    last_print = now
                if now - last_write >= 60.0:
                    checkpoint()
                    last_write = now
    finally:
        checkpoint()

    return done, done_bytes, failed, time.time() - t0


def _progress(label, done, total, done_bytes, total_bytes, elapsed):
    rate = done_bytes / max(elapsed, 1e-6)
    left = (total_bytes - done_bytes) / rate if rate else 0
    print("      %s%d/%d  %s of %s  %.0f MB/s  ~%dm left"
          % (label, done, total, human(done_bytes), human(total_bytes), rate / 1e6, left / 60),
          flush=True)



# ---------------------------------------------------------------------------- html listings
#
# READING A DIRECTORY LISTING IS THE ONE THING EVERY FETCHING TOOL HERE DOES, and until
# 2026-09-23 exactly one of them knew how. parse_listing lived in mirror.py; subset-refetch.py
# reached into that 6 700-line module by path to borrow it, and measure-remote.py had written its
# own -- which is how the measuring tool and the fetching tool came to disagree about how many
# files a site had.
#
# Every pattern below carries the run it cost to get right. They are not decoration: a matcher
# without its incident is a matcher somebody simplifies next year, and each of these was found
# by a mirror that reported SUCCESS while missing a branch.

# Apache's table-form autoindex, which is what both servers emit:
#   <a href="NAME">NAME</a></td><td align="right">DATE</td><td align="right"> 25K</td>
# The size column is rounded, so it is good enough for an ETA and useless for verification.
# `(?:(?!</t[dhr]|<tr).)*?` AND NOT `.*?`, and this cost an archive its first directory.
#
# A SORTABLE TABLE HEADER IS A LINK TOO. Apache's HTMLTable autoindex and LiteSpeed's both write
#     <th ...><a href="?C=N;O=D">Name</a></th>
# and `href` is the FIRST attribute there, so this pattern happily starts a match on it. The old
# `.*?` then ran forward -- across </th>, across the next header link, across </tr></thead> --
# until it found the first `</a></td>` in the document, which belongs to THE FIRST DATA ROW. That
# row was swallowed into the match, the captured href was the sort link, and is_child_link
# correctly threw the whole thing away.
#
# Measured on ftp.irixnet.org 2026-09-15: the first match began at `<a href="?MA">` in the header
# and spanned 393 characters, ending inside `nekoware`'s row. The run reported COMPLETE with 230
# files where 2 770 exist -- because `nekoware/`, the alphabetically first directory, was never
# seen. Zero failures, zero unreadable listings; the ninth defect of that exact shape.
#
# Forbidding the gap from crossing a cell or row boundary fixes it without loosening anything:
# a real row's <a>...</a> never contains </td>, </th>, <tr or </tr>.
ROW_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*>(?:(?!</t[dhr]|<tr).){0,400}?</a>\s*</td>\s*'
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'
    # T BELONGS HERE AND WAS MISSING UNTIL 2026-09-27. `parse_size` has understood T since it
    # was written; this matcher did not, so a row reading "1.0T" matched only the bare "1" and
    # the file was recorded as ONE BYTE. Not a parse failure -- a confident wrong number, which
    # is the worse kind. Found when a ratchet in common_test.py failed after measure-remote.py
    # stopped carrying its own parser and started using this one.
    r'<td[^>]*>\s*([0-9.]+\s*[KMGT]?|-)\s*</td>',
    re.I | re.S,
)


# THE `{0,400}` IS A STALL FIX, AND IT COST A RUN TO FIND. The tempered dot used to be `*?`,
# unbounded. That is quadratic on a page with many anchors and no table: for EVERY anchor the
# engine walks forward one character at a time, testing the negative lookahead at each, and it
# only stops at `</t[dhr]` or `<tr` -- neither of which exists on such a page. `</title>` does
# not qualify; the letter after `</t` is wrong.
#
# Measured on mirrors.develooper.com/hpux/id-20100310.html: 5 434 733 bytes, 22 165 <a href>,
# and ZERO <td>, </td>, <tr> or <table> -- the whole page is one <pre> of forum statistics.
# About 10^11 lookahead checks. Synthetic reproduction, doubling the page each row:
#
#     anchors      400     1600     6400    25600
#     old         0.25 s   3.84 s    ~1 min   ~16 min      factor 4.2 per doubling
#     new       0.0000 s 0.0000 s  0.0000 s  0.0010 s
#
# THE RUN DID NOT FAIL. It logged `fail 0`, `retry 0`, sat at 99% of one core, and gained three
# files in ninety minutes while the reporter kept printing. The host was answering in 1.3 s
# throughout. Every diagnosis that begins "we must be throttled" was wrong again; the CPU
# measurement is what settled it.
#
# 400 is the bound because the tempered part is the LINK TEXT of a directory listing, i.e. a
# filename -- and a filename cannot reach 255 bytes on any filesystem this collection mirrors
# from.
#
# AND THE COST IS SMALLER THAN IT LOOKS, measured rather than assumed. Over 400 characters this
# matcher drops out, but parse_listing then falls through to the bare link scan and the href
# still arrives -- without its size and date:
#
#     399 characters -> ('f.bin', 12288, 1704063600.0)
#     401 characters -> ('f.bin', None, None)
#
# So the bound costs METADATA, never a file. The first draft of the regression test asserted
# the opposite, that the file is lost, and the test failing is what established this.
#
# The bound alone is not enough. parse_listing ALSO refuses to run this matcher on a body with
# no `</td>` in it at all -- see there. The bound handles a page with one distant cell and
# thousands of anchors; the guard handles the page above, where the answer is simply "no".
#   [2026-09-16]
# lighttpd's table autoindex, which puts the columns the other way round -- name, SIZE, DATE:
#   <td class="link"><a href="NAME/">NAME/</a></td><td class="size">-</td>
#   <td class="date">2015-Jan-12 09:17</td>
#
# ROW_RE cannot read it, and the way it fails is what made this expensive. On such a page ROW_RE
# matches exactly one row: "Parent directory", whose *date* cell is "-" and therefore happens to
# satisfy ROW_RE's size pattern. One match is enough to claim the format, the row is then dropped
# as a parent link, and parse_listing returns an empty list without ever trying the fallback.
#
# A directory that parses to nothing is indistinguishable from an empty directory: no LISTFAIL,
# no warning, no counter. That is how `ps-2.kev009.com` was mirrored, marked COMPLETE, and left
# missing `basil.holloway/` with its 1955 PDFs. Found 2026-08-23.
LIGHTTPD_RE = re.compile(
    r'<td class="link"><a\s+href="([^"]+)"[^>]*>.*?</a></td>\s*'
    r'<td class="size">\s*([0-9.]+\s*[KMGT]?i?B?|-)\s*</td>\s*'
    r'<td class="date">\s*([^<]*?)\s*</td>',
    re.I | re.S,
)


# Apache's other autoindex style, a <pre> block rather than a table. IBM's Toolbox serves this
# one, and without a matcher for it every file comes back with an unknown size -- 21165 files
# reported as 0 bytes, which is not a small error to have in an ETA.
#   <a href="NAME">NAME</a>        2002-04-10 17:08  1.2M
PRE_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*>[^<]*</a>\s+'
    r'((?:\d{4}-\d{2}-\d{2}|\d{1,2}-[A-Za-z]{3}-\d{4})\s+\d{2}:\d{2})\s+'
    # T, for the reason given at ROW_RE: without it a terabyte reads as one byte.
    r'([0-9.]+\s*[KMGT]?|-)',
    re.I)


# BOTH APACHE DATE SHAPES, and the second was missing until 2026-09-17. FancyIndexing writes
#     <a href="9331.zip">9331.zip</a>          26-Mar-2004 05:00        919216
# in DD-Mon-YYYY, which is Apache's OLDER and still entirely ordinary default. The ISO-only
# pattern here did not match it, so parse_listing fell through to the bare link scan and every
# file in such a listing arrived with NO SIZE AND NO DATE -- fetchable, but stamped with the day
# it was copied instead of the day it was published, and with a useless ETA.
#
# parse_date already accepted "%d-%b-%Y %H:%M"; only this regex did not reach it. Found while
# surveying ftp.oldskool.org/pub/, where directories in the two styles sit side by side:
# IBM_PC_BBS/ is HTMLTable and ftp.bocaresearch.com/ is FancyIndexing.
LINK_RE = re.compile(r'<a\s+href="([^"]+)"', re.I)


# The same link, quoted the two other ways HTML allows, and with href not necessarily first.
# LINK_RE above is deliberately left alone: it also feeds the size/date matchers, whose column
# positions depend on its exact shape. This one is an ADDITION, used only for the bare scan.
#
# WIDENED AGAIN 2026-09-11 to accept DOUBLE-quoted hrefs that are not the first attribute --
# `<a class="..." href="...">`, which is what every template engine emits. The 2026-09-08 version
# excluded `"` on the reasoning that LINK_RE already covered it; LINK_RE covers it only when href
# comes FIRST, and nobody tested a tag with a preceding attribute.
#
# www.novasareforever.org/archives/ carries 87 hrefs of which THREE are href-first. The crawler
# saw those three, walked almost nothing, and reported COMPLETE WITH ZERO FILES -- no failures,
# no unreadable listings, nothing any counter could flag.
#
# The 2026-09-08 measurement could not have caught this: it ran over hand-written 1990s HTML,
# where href usually IS the first attribute. A measurement is only as wide as the sample under
# it, and that sample had no CMS in it.
#
# MEASURED ACROSS THE WHOLE COLLECTION 2026-09-08, and the honest answer is small: **50 files**.
# 48 in gsi-collection, 2 in dialectronics (which is incomplete for other reasons), 0 everywhere
# else.
#
# The raw counts invite a much bigger claim and it would be wrong. ardent-tool's stored pages hold
# 15 478 single-quoted or unquoted hrefs and **not one** names a file the mirror lacks -- every
# target was reached through a double-quoted link or a directory listing. One Blogspot page in
# techsysadm carries 251 `href='` against 4 `href="`, which looks catastrophic until you resolve
# them: they are absolute off-site URLs, never archive children, and that site is seeded from
# blogger-sitemap.py rather than crawled.
#
# So this closes a hole that had cost 50 files, which is the cheapest moment to close one. The
# lesson is the measurement, not the fix: a pattern count is not a loss count.
LINK_ODD_RE = re.compile(
    r"""<a\s[^>]*?href\s*=\s*(?:"([^"]+)"|'([^']+)'|([^"'\s>]+))""", re.I)


# <frame> and <iframe>. A FRAMESET ROOT NAMES ITS CHILDREN THIS WAY AND NO OTHER, so without this
# the crawler sees a page with no links and walks nowhere.
#
# transputer.classiccmp.org's front page is 387 bytes of frameset -- `<frame src="topic.html">`
# and `<frame src="main_page.html">` -- and the first run over it fetched ZERO files from a
# 1.72 GB archive, reported COMPLETE, and recorded zero failures and zero unreadable listings.
# Nothing in the program could have flagged that: nothing had failed.
#
# Followed for every archive, not only HTML_CRAWL. A frame is never decoration -- it is the only
# route to the page it names -- so unlike <img src> there is no case where following one is
# noise. On a generated directory index there are no frames at all.
FRAME_RE = re.compile(
    r"""<(?:i?frame)\s[^>]*?src\s*=\s*(?:"([^"]+)"|'([^']+)'|([^"'\s>]+))""", re.I)


# The two date formats the indexes use. An archive's file dates are part of what it is: without
# these every mirrored file claims to have been made on the day it was copied, and a 2005 RPM
# becomes indistinguishable from one built yesterday.
DATE_FORMATS = ("%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%b-%Y %H:%M:%S",
                "%Y-%b-%d %H:%M")   # lighttpd: 2009-Feb-06 10:16


def parse_date(text):
    """Listing date -> epoch seconds, or None. Minute precision, which is what the index gives.

    OverflowError IS CAUGHT ALONGSIDE ValueError, and it is not a theoretical case. time.mktime
    raises it for a date the platform's time_t cannot hold, and a listing of genuinely old files
    is exactly where such a date appears. Found on 2026-09-23 by parsing the collection's own
    stored pages: the crawler died on one, in the producer thread, which has no handler of its own.
    The same shape as parse_size's overflow, two functions apart.

    A date that cannot be represented is NOT a date of zero. None means "the index gave one and
    this cannot hold it", and the caller then stamps the file with nothing rather than with 1970.

    AND "THE PLATFORM CANNOT HOLD IT" WAS A WINDOWS SENTENCE, which this docstring stated as a
    general one until 2026-10-02. `01-Jan-1900 00:00` raises OverflowError on Windows and returns
    -2208988800.0 on Linux, so the answer depended on which machine asked -- and the CI caught it
    only because two tests had pinned the Windows reading. The same shape as the time-zone defect
    of the same week: a test encoding the behaviour of the machine it was written on.

    SO A PRE-EPOCH DATE IS NOW None EVERYWHERE, by an explicit test rather than by whichever error
    the platform happens to raise. That keeps the promise the paragraph above makes -- a date that
    cannot be stamped portably is not a date -- and it makes the two platforms agree.

    MEASURED BEFORE CHANGING IT, because this alters what a listing turns into: 1 802 057 rows
    across every index in the collection, and NOT ONE carries an mtime before 1970. The oldest is
    1977-06-08. Nothing held here depends on a negative timestamp, and on these sources a date
    before 1970 is a default or a corruption rather than a fact about a file.
    """
    text = (text or "").strip()
    if not text or text == "-":
        return None
    for fmt in DATE_FORMATS:
        try:
            when = time.mktime(time.strptime(text, fmt))
        except (ValueError, OverflowError):
            continue
        return None if when < 0 else when
    return None


def date_text(epoch):
    """The inverse of parse_date: epoch seconds -> the listing text it would have been read from.

    -> "" for None, which is what parse_date returns for a date it could not hold. A caller
    printing a column wants a blank there, not the word None or the year 1970.

    WHY THIS IS IN THE LIBRARY AND NOT IN A TEST. parse_date calls time.mktime, which reads a
    listing date IN THE TIME ZONE OF THE MACHINE PARSING IT. A listing says `2024-01-01 00:00`
    and carries no zone, so the epoch it becomes is not a property of the listing -- it is a
    property of the listing and the reader together. Anything that compares a parsed date against
    an expected one must therefore go back through the SAME localtime, or it is comparing a date
    with a time zone.

    MEASURED, TWICE, THE SECOND TIME IN PUBLIC. parse_listing_test.py pinned 1704063600.0 -- that
    sum in CET -- and the GitHub runner is UTC: it failed by one hour and took the whole Python CI
    job down on three consecutive merges to main, 2026-09-28 to 2026-10-02. common_test.py had
    already met the same thing ("wrong by eight hours"), fixed it with a local helper, and written
    the lesson into a docstring BESIDE ITS OWN FIX -- while the line it was describing, in the
    other file, stayed as it was. A lesson recorded next to code that already obeys it is not a
    check on the code that does not, and a helper in one test file is not available to the next.

    IT IS NOT A WORKAROUND FOR A TIME-ZONE BUG, which is worth saying plainly: the absolute
    instant a listing means cannot be recovered, because the server does not say which zone it
    printed. See the note on DATE_FORMATS. This function makes the round trip exact; it cannot
    make the original unambiguous.
    """
    if epoch is None:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))


BASE_RE = re.compile(r'<base\s[^>]*href="([^"]+)"', re.I)


def resolution_base(body, page_url, base_url):
    """-> the URL relative links on this page must be resolved against.

    Normally the page's own final URL. But a page may declare `<base href>`, and on a MIRRORED
    site that tag says where the site used to live, not where it lives now.

    unixos2.org is the case. Its pages carry `<base href="/mirrors/unixos2.org/">` -- the path it
    occupied on its ORIGINAL host -- while infania serves it at /sites/unixos2.org/ and has no
    /mirrors/ at all. Ignore the tag and `pages/packages/GnuAwk/`, written on `/pages/Downloads.html`
    to mean "from the site root", resolves to `/pages/pages/packages/GnuAwk/` and 404s. That is
    exactly what happened on 2026-09-07: 36 permanent 404s, all of them doubled path segments, and
    11 files fetched where the measurement said 18. The whole `packages/` branch -- GnuAwk, GnuPG,
    GnuMake, GnuBaSH, Autoconf, Pine, UnixOS2Base, UX2BS -- was missing, which is not the trimming
    of a site but its substance.

    So: honour `<base>` as the resolution target, and REBASE IT ONTO OUR ROOT when it points
    somewhere this host does not serve. A mirror's `<base>` says where the site used to live and
    the mirror root says where it lives now; mapping one onto the other is what mirroring is.

    THIS LOGIC WAS ALREADY IN measure-remote.py AND NOT HERE, which is the whole defect. The
    measuring tool learned it on 2026-09-06 and the fetching tool did not, so the measurement said
    18 files and the fetch produced 11 and nothing compared the two. A rule that lives in one of a
    pair of tools is a rule that will be contradicted by the other.  [2026-09-07]
    """
    m = BASE_RE.search(body)
    if not m:
        return page_url
    declared = urllib.parse.urljoin(page_url, m.group(1))
    return declared if declared.startswith(base_url) else base_url


# Extensions a cache-buster may be stripped from. DELIBERATELY NARROW: see strip_cache_buster.
def _bare_child_count(body, allow_up):
    """How many in-scope children a plain link scan would find on this page.

    Used only to sanity-check a column matcher's yield -- see the note at the acceptance test in
    parse_listing. Deliberately counts DISTINCT hrefs after the same is_child_link filter the
    real scan applies, so the two numbers are comparable; counting raw <a> tags instead would
    make every page with a navigation bar look like a partial match.
    """
    seen = set()
    for x in LINK_RE.findall(body):
        seen.add(x)
    for a, b, c in LINK_ODD_RE.findall(body):
        seen.add(a or b or c)
    n = 0
    for x in seen:
        h = strip_fragment(html.unescape(x))
        if h and is_child_link(h, allow_up):
            n += 1
    return n


def parse_listing(body, allow_up=False, images=False):
    """-> [(href, size_or_None, mtime_or_None)] for the children of one directory listing.

    Three matchers, tried in order of how much they tell us. The bare link scan is last because
    it yields neither size nor date, which silently turns the ETA into nonsense and stamps every
    file with the day it was copied -- so a new index style is worth a matcher rather than a shrug.

    `images=True` additionally yields every `<img src>` the page embeds, and is passed for the
    HTML_CRAWL archives only. THE ORDER MATTERS: images are appended after the links, never
    before, so that a page which is both a listing and illustrated still gets its size and date
    columns from the matcher that knows them.

    Embedded images are appended even when one of the three column matchers succeeded. That is
    deliberate and is the whole point -- a hand-written page can carry a table of files AND the
    photographs of the machine those files are for, and until 2026-09-08 the second kind was
    invisible to this crawler.
    """
    # (matcher, order of the two trailing groups). A matcher is accepted only if it yields at
    # least one *child* -- not merely at least one match. ROW_RE matching only the "Parent
    # directory" row of a lighttpd page used to count as success and suppressed the fallback,
    # which is how whole subtrees went missing without a single warning.
    def embedded(already):
        """-> the page's own <img src> targets, as (href, None, None). Empty unless images=True.

        `already` holds the hrefs the link matchers produced, so a file that is both linked and
        embedded -- a thumbnail wrapped in an <a> to its full size, the commonest shape in a
        gallery -- is yielded once. producer()'s `seen` set would swallow the repeat anyway; the
        cost of not deduping here is a wrong `found` counter, which is the number the ETA and the
        completion marker are built from.
        """
        if not images:
            return []
        seen, out = set(already), []
        for a, b, c in IMG_SRC.findall(body):
            h = strip_cache_buster(strip_fragment(html.unescape(a or b or c)))
            if not h or h in seen or not is_child_link(h, allow_up):
                continue
            seen.add(h)
            out.append((html.unescape(h), None, None))
        return out

    for matcher, size_first in ((ROW_RE, False), (LIGHTTPD_RE, True), (PRE_RE, False)):
        # A TABLE MATCHER CANNOT MATCH A DOCUMENT WITH NO TABLE CELL IN IT, and saying so costs
        # one linear scan instead of a quadratic search. Both patterns require `</td>`
        # literally; without one there is nothing to find and everything to waste. See ROW_RE.
        if matcher is not PRE_RE and "</td>" not in body:
            continue
        out = []
        for h, a, b in matcher.findall(body):
            if not is_child_link(h, allow_up):
                continue
            z, d = (a, b) if size_first else (b, a)
            h = strip_fragment(html.unescape(h))
            if not h:
                continue
            out.append((html.unescape(h), parse_size(z), parse_date(d)))
        # A COLUMN MATCHER MUST ACCOUNT FOR MOST OF THE PAGE, OR IT IS NOT READING THIS PAGE.
        # The rule here was `if out:` until 2026-09-17, which let a PARTIAL match win and suppress
        # the full link scan -- silently, with the run then reporting COMPLETE.
        #
        # adoxa.altervista.org is the measured case. Its front page is a hand-written <table> of
        # projects whose third column is a VERSION NUMBER, and ROW_RE cannot tell a version from
        # a size:
        #
        #     <td>ANSICON</td> <td>…</td> <td align="center">1.71</td>     matches [0-9.]+
        #     <td>7-Zip</td>   <td>…</td> <td align="center">19.00a3</td>  does not
        #
        # ROW_RE therefore returned 17 rows where a bare scan returns 61, and the crawl fetched
        # 30 files out of 207 while logging `0 failures, 0 unreadable listings`. Tenth defect of
        # that signature, and the worst shape of it so far: not a total failure that shows up as
        # an empty archive, but a PARTIAL success that looks finished.
        #
        # On a real generated index the two counts are essentially EQUAL -- every row is a link,
        # and what a bare scan adds (parent link, sort headers) is refused by is_child_link
        # anyway. So the floor is 80 %, and the first draft of it was wrong: half was chosen as
        # "generous", and a test written at exactly 10-of-20 passed through it. A column matcher
        # that sees half a page is no more reading that page than one that sees a quarter.
        #
        # ERRING TOWARDS THE BARE SCAN IS THE CHEAP DIRECTION. Rejecting a column matcher costs
        # the size and date columns; accepting a partial one costs FILES, and costs them silently.
        # adoxa sat at 0.28, a real autoindex sits at 1.0, and nothing legitimate is known to sit
        # between -- 0.8 is where to put the line when the two failure costs are that unequal.
        if out and len(out) * 5 >= _bare_child_count(body, allow_up) * 4:
            return out + embedded({h for h, _s, _d in out})

    # The bare scan. LINK_ODD_RE is folded in here and nowhere else: it carries no size or date,
    # so it belongs with the matcher that has none either.
    bare = list(LINK_RE.findall(body))
    for a, b, c in LINK_ODD_RE.findall(body):
        bare.append(a or b or c)
    # Frames are added to the BARE scan, which runs only when no column matcher produced a child
    # -- and a frameset page has no columns to match, so this is exactly where it belongs.
    for a, b, c in FRAME_RE.findall(body):
        bare.append(a or b or c)
    seen, out = set(), []
    for h in (strip_fragment(html.unescape(x)) for x in bare):
        if not h or h in seen or not is_child_link(h, allow_up):
            continue
        seen.add(h)
        out.append((html.unescape(h), None, None))
    return out + embedded(seen)


# ----------------------------------------------------------------------------------- main


def main():
    """No command line. Printing the summary is what makes `--help` exit 0 for the CI check."""
    print(__doc__.strip())
    print("\nexported:")
    for name in __all__:
        obj = globals()[name]
        doc = (obj.__doc__ or "").strip().splitlines()[0] if callable(obj) else repr(obj)[:70]
        print("  %-16s %s" % (name, doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
