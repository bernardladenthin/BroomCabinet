#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Recover a dead host from the Internet Archive, into the same layout mirror.py produces.

WHEN THIS IS THE RIGHT TOOL
    When the origin is gone. mirror.py copies what a server still serves; this reads what the
    Internet Archive kept after it stopped. The two are not variants of one job:

      mirror.py       follows links from a live root, and can be re-run to catch up
      this            works a list obtained from an index, once, and can never be complete

    The result is a SALVAGE, not a mirror, and the marker it produces says so. A mirror can be
    checked against its source; this cannot, because the source is what went missing.

HOW IT FINDS THINGS
    The Wayback CDX API lists every capture of a host. Link-following is useless here -- the
    origin serves nothing to follow -- so the URL list comes from the index instead:

        http://web.archive.org/cdx/search/cdx?url=<source>&matchType=<domain|prefix>
            &fl=original,timestamp,statuscode,mimetype,length&collapse=urlkey

    `--domain` may be given more than once, because a dead site is not always one hostname and a
    hostname is not always one site. The match type follows from the shape of what you pass:

        bullfreeware.com            no slash  -> matchType=domain, so subdomains come too
        zipworld.com.au/~dtucker    a slash   -> matchType=prefix, so ONLY that path

    That distinction is not cosmetic. `~dtucker` is one user directory on a general-purpose ISP;
    asking for the domain would enumerate the whole ISP.

    When a run ends up with more than one host, each gets its own top-level directory (port
    stripped, leading `www.` stripped, so `www.example.com` and `example.com` are one host and
    not two). With a single host the layout is unchanged: paths hang directly off the archive.

WHAT TO LEAVE BEHIND
    A salvage is not obliged to take everything the index lists, and on a package host most of the
    bytes are usually things you already hold or things the site derived from them.

        --exclude REGEX      drop URLs matching it. Repeatable.
        --skip-listed FILE   drop URLs whose FILENAME appears in FILE, one per line.

    Use `--skip-listed` against a manifest of what is already mirrored elsewhere. It compares bare
    filenames, which is deliberately loose: the same package under two paths is the same package,
    and re-fetching 59 GB of RPMs from the Internet Archive to place a second copy beside the
    first is a week of someone else's bandwidth for nothing.

    **Record every exclusion in the marker as a CONDITION, never as a fact.** "The RPMs live in
    bull-rpms/" can be checked and revived; "we did not need the RPMs" cannot, and an exclusion
    written that way is never revisited. This project has lost four years to that shape once.

USAGE
    python wayback-salvage.py --domain download.example.net --root /srv/mirror --archive example
    python wayback-salvage.py --domain ... --root ... --archive ... --dry-run
    python wayback-salvage.py --domain a.example.com --domain b.example.com/pub \
        --exclude '/RPMS_ZIPS/' --skip-listed held.txt --root /srv/mirror --archive example

SIX THINGS THAT WILL BITE, ALL MEASURED
    1. The `id_` modifier in the replay URL is MANDATORY. Without it the Wayback Machine injects
       its own toolbar into the response, and a binary comes back corrupted -- silently, with a
       200 and a plausible size.
    2. The CDX `length` column is the size of the compressed WARC record, not of the file. Never
       compare a download against it. The real figure is in the `x-archive-orig-content-length`
       response header, which is what this checks.
    3. A row indexed with statuscode 200 can still 404 on replay: the record exists in the index
       and the data node cannot serve it. One of four sampled files behaved that way. Expect a
       nonzero rate and log it rather than treating it as a bug here. THAT FAILURE IS RETRYABLE
       AND A SHORT TRANSFER IS NOT -- a distinction worth acting on, because at the moment they
       happen the two look equally final. A 404 on replay is the archive failing to serve a record
       it holds; every such file in the aixtools salvage came back whole on a later attempt, one
       of them a day later. A transfer that stops at the same byte count every time is the archive
       serving all it ever captured, and no number of retries will add to it. Only the size
       comparison in (2) tells them apart; the HTTP status does not.
    4. `warc/revisit` rows are deduplication stubs with no payload of their own. They carry
       statuscode `-` and must be filtered out.
    5. Apache's autoindex sort links (`?C=S;O=A` and friends) are captured as separate URLs. They
       are the same page under a different query string -- noise, and they cannot be written to a
       filesystem under a sane name.
    6. THE ARCHIVE WILL REFUSE THE CONNECTION IF YOU ASK TOO FAST, and that failure looks exactly
       like a missing file if you only count failures. Measured 2026-08-30, two salvages started
       against archive.org at the same time, 1.0 s and 1.5 s apart respectively: 116 of 242 URLs
       in one run and 118 in the first hour of the other came back `ECONNREFUSED`, none of them
       404, none short. Nothing was wrong with those records. The aggregate rate was wrong.

       So this tool now retries transport failures with a growing pause, and SLOWS ITSELF DOWN for
       the rest of the run once it has been refused -- the archive's answer to "too fast" is
       silence, and the only cooperative reply is to ask less often. A run reports `throttled`
       separately from `unfetchable` for the same reason the size check exists: three failures
       that look identical at the moment they happen mean three different things.

           throttled     we asked too fast          retry, and slow down
           unfetchable   404 on replay              retry later, probably fine
           suspect       short or wrong-magic file  retrying THIS capture is pointless -- but
                                                    see suspect-reconsider.py for the others

       WHY A SHORT TRANSFER IS FINAL, established 2026-08-31 rather than assumed. On the
       bullfreeware salvage, 27 source tarballs arrived short and almost all of them stopped at
       exactly 9 999 66x bytes -- a suspiciously round boundary that looks like a cap on the
       replay path, i.e. something a Range request might walk around. It is not. The CDX index
       for `gcc-3.3.tar.gz` lists ONE capture, status 200, `length` 9 985 620: the stored WARC
       RECORD is itself ~10 MB. The Archive's crawler hit a per-file ceiling in 2009 and stopped,
       and `x-archive-orig-content-length: 31113822` is the ORIGIN's header from that day,
       recorded faithfully -- a statement about what the origin was serving, never a promise
       about what the Archive kept.

       That is the whole reason the size check in (2) works, and it also explains the eleven
       aixtools Python filesets that stopped at varying sizes: different crawl eras, different
       ceilings. Check the CDX `length` column before concluding a short file is retryable; when
       it is close to what arrived, the record is complete and the file is not.

       AND THAT IS WHERE THIS REASONING WAS OVERSTATED, corrected 2026-09-13. Everything above is
       true of `gcc-3.3.tar.gz`, and the sentence that mattered is the one about its index: it
       lists ONE capture. The conclusion was then applied to URLs that have SEVERAL, where it does
       not hold. Re-checking every .suspect against every capture of its URL recovered:

           rs6000-microcode  12 of 15 from later captures, +30 MB
           gcc-3.3.0.0.exe   held  9 999 682 B; best capture 51 263 345 B
           samba-3.0.4.0.bff held    130 767 B; best capture 21 344 390 B

       So the rule keeps its evidence and gains its qualifier:

           A .SUSPECT IS FINAL ONLY WHEN THE BEST CAPTURE IS SHORT.

       `--retry-suspect` below does NOT establish that. It re-requests the same URL and lets
       Wayback choose the capture, so the same short bytes come back -- which is precisely the
       observation that was written down as proof of finality. Asking the same question again is
       not a second opinion. Use suspect-reconsider.py, which ranks all captures first.

       Note that "too fast" arrives in two forms and one of them is easy to misfile. A refused
       socket is obviously about us. An HTTP 503 or 429 is ALSO about us, but it arrives as an
       HTTPError -- the same exception type as a 404, which is about the record. Classifying by
       exception type instead of by status code sorted 503s in with the 404s, and the second
       bullfreeware run lost 17 catalogue pages that way before it was noticed. See RETRY_STATUS.

VERIFICATION
    Every file is checked against `x-archive-orig-content-length` when the header is present. For
    AIX installp images (`.I`) the first four bytes must be `09 00 6b ea`, the BFF "backup by
    name" magic -- which catches exactly the toolbar-injection failure above.
"""

import argparse
import hashlib
import io
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (BFF_MAGIC, Pacer, host_of, http_open, human, is_transport,
                    long_path)
from common import MIN_FREE_BYTES as DEFAULT_MIN_FREE
from wayback import wayback_cdx_url, wayback_replay_url

# Refuse to fetch below this much free space, and the directory the check asks about. Both are
# module-level because save() runs per file and must not recompute either. SALVAGE_ROOT is filled
# in by main() before any worker starts; 1 GB is the owner's choice, set 2026-09-06 -- small,
# because the index this run writes afterwards is a few MB and nothing else on the volume needs
# headroom, and deliberate rather than a default nobody chose.
# The library's floor is where this starts; --min-free-gb moves it, which is why this stays
# a variable of this module rather than the constant itself.
MIN_FREE_BYTES = DEFAULT_MIN_FREE
SALVAGE_ROOT = "."
_floor_hit = False

# NO `collapse=urlkey`. It returns ONE capture per URL and keeps the FIRST in index order --
# usually the oldest -- so a URL whose early capture was truncated by a crawler ceiling looks
# like a file that cannot be had, when a later capture holds it whole.
#
# That cost this collection real material. 73 files were recorded as permanently lost, in
# markers, in PROVENANCE files and in mirror.py's status table, on the reasoning that their
# stored WARC records were themselves short. For 58 that was true. For 15 it was not:
# gcc-3.3.0.0.exe was held at 9 999 682 bytes with 52 966 597 available; samba-3.0.26.0.bff at
# 130 767 against 96 051 200; and all 15 rs6000-microcode truncations were EXACTLY 1 048 257
# bytes, a 1 MiB ceiling belonging to the 2000 crawls that the 2001 crawls did not have.
#
# So: ask for every capture and choose the largest 200 per URL. More rows over the wire, one
# query either way, and the difference between a file and no file.  [2026-09-05]
TIMEOUT = 120
CHUNK = 1 << 20

# How long to wait before each fresh attempt at one URL after the connection failed. Five tries
# over about five minutes: long enough to ride out a rate limiter, short enough that a genuinely
# unreachable host does not hold the run for an hour.
# A HAND-TUNED TABLE, and it stays one. `common.Backoff` covers ladders that grow geometrically
# or arithmetically; this grows by 4x, then 3x, 2x, 1.5x -- somebody chose those five numbers
# against this service's behaviour, and reshaping them to fit a class would be changing what the
# tool does in order to tidy how it is written. [reviewed 2026-09-25]
BACKOFF = (5, 20, 60, 120, 180)

# Everything here talks to one service; the pacer keys on it.
WAYBACK_HOST = "web.archive.org"
MAX_DELAY = 30.0  # ceiling for the adaptive inter-request pause

# Apache mod_autoindex column-sort links. Same page, different query string.
SORT_LINK = re.compile(r"\?C=[NMSD];O=[AD]$", re.I)

# What may stand in a filename built from a query string. Everything else becomes an underscore:
# Windows forbids \ / : * ? " < > | outright, and a query is arbitrary text from a stranger.
QUERY_UNSAFE = re.compile(r"[^A-Za-z0-9._=&+,()-]")

# The same problem in the PATH, which is easy to forget because a URL path usually looks like a
# filesystem path already. It is not one. Two shapes broke a run that had been going for hours:
#
#   /download/aix43/%2A                         ->  a literal '*' once unquoted
#   /web/20111101000000/http://www.example.com/ ->  a Wayback replay URL archived AS CONTENT,
#                                                   making 'http:' a directory name
#
# Only these characters are rewritten -- everything else a path may legitimately contain is left
# alone, because renaming more than necessary makes the copy diverge from the source for no gain.
PATH_UNSAFE = re.compile(r'[<>:"|?*\x00-\x1f]')

# An --exclude value that arrived as an absolute Windows path was rewritten by the shell rather
# than typed. Git Bash / MSYS2 rewrites any argument beginning with '/' on its way to a native
# executable, so `--exclude '/download/sources/'` reaches Python as
# 'C:/Program Files/Git/download/sources/'. It compiles, it matches nothing, and the run reports
# a clean bill of health while the exclusion silently does not exist -- which is how two
# exclusions on the bullfreeware salvage were inert for four restarts before anyone noticed the
# declined-reason table had no line for them.  [2026-08-31]
MANGLED = re.compile(r"^[A-Za-z]:[\\/]")

# AIX installp / BFF "backup by name" magic.


# HTTP statuses that mean "not now" rather than "not here". 503 is how archive.org says politely
# what ECONNREFUSED says rudely, and treating it as a verdict about the record loses files that
# are sitting right there. Measured 2026-08-31: a bullfreeware run at 3 s spacing, with zero
# refused connections, still collected 17 of these in 640 URLs -- every one of them a
# `affichage.php?id=NNNN` catalogue page, the exact content the salvage exists to rescue.


class Pace:
    """Request spacing that yields to the server instead of arguing with it.

    KEYED ON CONSECUTIVE REFUSALS, NOT ON THE TOTAL, and that distinction was learned the
    expensive way. The first version doubled the delay on every refusal and decayed it by 3% per
    success. Measured on the bullfreeware run: a 12% rate of isolated 503s -- every one of which
    succeeded on the first retry, i.e. ordinary archive.org background noise -- drove the spacing
    from 3 s to the 30 s ceiling and pinned it there, because recovering from ten doublings needed
    about seventy-six consecutive successes. Throughput fell eightfold in response to a server
    that was not actually refusing to serve us.

    A rate limiter says "stop" by refusing REPEATEDLY. One 503 between successes is weather. So an
    isolated refusal now costs 50% and is given back almost at once, while a genuine block still
    reaches the ceiling in six straight refusals.
    """

    def __init__(self, base):
        self.base = base
        self.delay = base
        self.refusals = 0
        self.streak = 0
        self.slowest = base
        # THE POLICY IS HERE; THE ARITHMETIC IS NOT. How fast to go is this tool's own judgement
        # -- grow on refusal, ease back on success -- and it does not belong in a shared helper.
        # HONOURING the current delay is a different thing, and the local `time.sleep(self.delay)`
        # got it wrong the way fifteen other tools did: it waited the full delay AFTER each
        # request instead of counting the request against it, so a 5 s pace with a 4 s response
        # ran at 9 s. `Pacer` is that arithmetic and nothing else. [2026-09-25]
        self._pacer = Pacer(base)

    def ok(self):
        self.streak = 0
        if self.delay > self.base:
            self.delay = max(self.base, self.delay * 0.85)

    def refused(self):
        self.refusals += 1
        self.streak += 1
        self.delay = min(MAX_DELAY, self.base * (1.5 ** min(self.streak, 10)))
        self.slowest = max(self.slowest, self.delay)
        return self.delay

    def sleep(self, key=WAYBACK_HOST):
        """Hold the current pace. -> the seconds actually slept."""
        self._pacer.pause = self.delay
        return self._pacer.wait(key)


def cdx_rows(source):
    """-> [(original, timestamp, status, mimetype, length)] straight from the index.

    A source with a path is asked for as a prefix; a bare hostname is asked for as a domain, so
    that its subdomains come along. See the module docstring for why that difference matters.
    """
    with http_open(wayback_cdx_url(source), timeout=TIMEOUT) as r:
        body = r.read().decode("utf-8", "replace")
    # Every capture comes back; keep the LARGEST successful one per URL. Ties and unparseable
    # lengths fall back to the last seen, which is the old behaviour for the rows that have no
    # better answer. A non-200 never displaces a 200.
    best = {}
    for line in body.splitlines():
        parts = line.split(" ")
        if len(parts) < 5:
            continue
        original, timestamp, status, mimetype, length = parts[:5]
        try:
            size = int(length)
        except ValueError:
            size = -1
        prev = best.get(original)
        if prev is None:
            best[original] = (size, (original, timestamp, status, mimetype, length))
            continue
        prev_size, prev_row = prev
        prev_ok, this_ok = prev_row[2] == "200", status == "200"
        if (this_ok and not prev_ok) or (this_ok == prev_ok and size > prev_size):
            best[original] = (size, (original, timestamp, status, mimetype, length))
    return [row for _size, row in best.values()]


def wanted(rows, excludes=(), skip_names=frozenset()):
    """-> [(original, timestamp)] worth fetching, plus a per-reason count of what was dropped.

    Kept deliberately generous about the site's own furniture: directory index pages are not
    decoration here. On a host that no longer exists they are the only surviving record of what
    each directory held, and of the sizes and dates the files had. Dropping them to save a few
    kilobytes would throw away the inventory and keep the inventoried.

    `excludes` and `skip_names` are the opposite judgement and are the caller's, not this
    function's: they exist so a salvage can decline bytes it already holds. Every drop is counted
    by reason so the run reports what it declined instead of quietly shrinking.
    """
    keep, dropped = [], {}
    for original, ts, status, mime, _length in rows:
        why = None
        if status != "200":
            why = "status %s" % status
        elif mime == "warc/revisit":
            why = "revisit stub"
        elif SORT_LINK.search(original):
            why = "autoindex sort link"
        else:
            for rx in excludes:
                if rx.search(original):
                    why = "excluded /%s/" % rx.pattern
                    break
            if not why and skip_names:
                name = urllib.parse.unquote(urllib.parse.urlsplit(original).path).rsplit("/", 1)[-1]
                if name in skip_names:
                    why = "already held elsewhere"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
        else:
            keep.append((original, ts))
    return keep, dropped


def salvage_path(root, original, host_dir=False):
    """Maps an ARCHIVED url onto a path. common.local_path() maps a live one under a base_url, with
    a different signature and a different idea of what the root means. [renamed 2026-09-24]

    Map an archived URL onto a path under `root`.

    With one host the host is stripped and paths hang directly off the archive, which is what a
    single-site salvage should look like. With several, the host becomes the first directory --
    otherwise two sites' `/index.html` are the same file and the second silently wins.

    THE QUERY STRING IS PART OF THE NAME, and leaving it out is not a simplification -- it is
    data loss that reports success. Measured on bullfreeware.com: of 17 022 URLs worth fetching,
    3 194 carry a query and dropping it collapses them onto 48 paths, so 3 181 files overwrite
    each other or are skipped as "already present". The casualties are the whole catalogue --
    1 189 `affichage.php?id=NNNN` package pages, 833 `search.php?package=NAME`, 905 `pkg?id=NNNN`
    -- while every RPM, having no query, arrives safely. The salvage would have kept the packages
    and thrown away the index of what the packages were.

    A database-backed site is normal for anything built after about 2000, and this tool met one
    for the first time on its second use. The first target was a plain Apache autoindex, where
    the only query strings were mod_autoindex's own sort links -- genuinely droppable, which is
    why they are dropped by name above rather than by the fact of having a query.
    """
    u = urllib.parse.urlsplit(original)
    path = urllib.parse.unquote(u.path)
    if path.endswith("/") or not path:
        path += "index.html"
    parts = [PATH_UNSAFE.sub("_", p) for p in path.split("/") if p not in ("", ".", "..")]
    if u.query:
        q = QUERY_UNSAFE.sub("_", urllib.parse.unquote(u.query))
        # Long or awkward queries keep a readable head and a digest, so two different queries can
        # never land on one name however they were truncated.
        if len(q) > 120:
            q = q[:104] + "-" + hashlib.sha256(u.query.encode("utf-8")).hexdigest()[:15]
        parts[-1] += "@" + q
    if host_dir:
        parts.insert(0, host_of(original))
    return os.path.join(root, *parts)


def save(original, ts, dest, log, pace):
    """-> (ok, bytes, note, kind). Writes to a .part and renames, so a kill leaves no half file.

    `kind` is "" on success, else one of throttled / unfetchable / suspect -- see the module
    docstring for why those three are not one number.
    """
    # STOP BEFORE THE VOLUME IS FULL. This tool had no floor at all until 2026-09-06, when it was
    # pointed at a 44 GB recovery with 29 GB free -- it would have written the disk to zero and
    # taken every other writer on the volume down with it.
    #
    # ASK A DIRECTORY THAT EXISTS. mirror.py's first attempt at this guard called disk_usage() on
    # dirname(dest) -- which the very next line CREATES -- so every file in a not-yet-existing
    # directory raised FileNotFoundError before a byte was requested, and a run died with 20 719
    # failures in seconds. SALVAGE_ROOT is set once in main() and is a directory by then.
    #
    # And the guard may never be the thing that fails a fetch: if the check itself throws, say so
    # once and carry on unguarded, because an unguarded run is recoverable and a dead one is not.
    global _floor_hit
    try:
        free = shutil.disk_usage(SALVAGE_ROOT).free
    except Exception as exc:  # noqa: BLE001 -- a broken guard must not break the run
        if not _floor_hit:
            _floor_hit = True
            log("DISK FLOOR DISABLED: cannot read free space (%s) -- fetching unguarded"
                     % exc.__class__.__name__)
        free = None
    if free is not None and free < MIN_FREE_BYTES:
        if not _floor_hit:
            _floor_hit = True
            log("DISK FLOOR: under %.1f GB free -- stopping here. Re-run when there is room; "
                     "everything already fetched is kept and skipped." % (MIN_FREE_BYTES / 1e9))
        return False, 0, "disk floor", "unfetchable"

    url = wayback_replay_url(ts, original)
    tmp = dest + ".part"

    # ONE NAME CANNOT BE BOTH A FILE AND A DIRECTORY, and a documentation site hands you exactly
    # that. IBM's Open XL docs live at .../openxl-c-and-cpp-aix (a page) and at
    # .../openxl-c-and-cpp-aix/17.1.1?topic=... (802 more pages under it). Whichever arrives first
    # wins the name: fetch the bare page first and every later URL dies with WinError 183, "cannot
    # create a file when that file already exists" -- 78 of the first 80, and the run looks like a
    # dead site rather than a naming collision.
    #
    # Apache calls the page-that-is-also-a-directory case an index, so resolve it that way: move
    # the file into the directory as index.html. Nothing is lost and the tree reads correctly.
    parent = os.path.dirname(dest)
    if os.path.isfile(long_path(parent)):
        keep = os.path.join(parent + ".tmpmove")
        try:
            os.replace(long_path(parent), long_path(keep))
            os.makedirs(long_path(parent), exist_ok=True)
            os.replace(long_path(keep), long_path(os.path.join(parent, "index.html")))
            log("PAGE-AND-DIRECTORY %s -- the page was moved to index.html so the "
                     "subtree below it can exist" % parent)
        except OSError as exc:
            log("PAGE-AND-DIRECTORY %s -- COULD NOT RESOLVE: %s" % (parent, exc))
    os.makedirs(long_path(os.path.dirname(dest)), exist_ok=True)

    last = None
    for attempt in range(len(BACKOFF) + 1):
        try:
            with http_open(url, timeout=TIMEOUT) as r:
                claimed = r.headers.get("x-archive-orig-content-length")
                n = 0
                head = b""
                with io.open(long_path(tmp), "wb") as fh:
                    while True:
                        b = r.read(CHUNK)
                        if not b:
                            break
                        if not head:
                            head = b[:4]
                        fh.write(b)
                        n += len(b)
            break
        except Exception as exc:  # noqa: BLE001 -- classified immediately below
            last = exc
            if not is_transport(exc) or attempt == len(BACKOFF):
                try:
                    os.remove(long_path(tmp))
                except OSError:
                    pass
                if is_transport(exc):
                    # Refused after every retry. The record is probably fine; we are not.
                    slowed = pace.refused()
                    log("THROTTLED %s :: %s (pacing now %.1fs)" % (original, exc, slowed))
                    return False, 0, "throttled", "throttled"
                # A row indexed 200 that will not replay is the documented case, not a defect
                # here -- and it is worth retrying on another day, unlike a short transfer.
                log("FAIL %s :: %s" % (original, exc))
                return False, 0, "unfetchable", "unfetchable"
            wait = BACKOFF[attempt]
            pace.refused()
            log("RETRY %s :: %s (attempt %d, waiting %ds)" % (original, exc, attempt + 1, wait))
            time.sleep(wait)
    else:  # pragma: no cover -- the loop always breaks or returns
        return False, 0, str(last), "unfetchable"

    pace.ok()

    note = ""
    if claimed is not None:
        try:
            if int(claimed) != n:
                note = "SIZE claimed %s got %d" % (claimed, n)
        except ValueError:
            pass
    if dest.lower().endswith(".i") and head != BFF_MAGIC:
        note = (note + "; " if note else "") + "NOT-BFF first4=%s" % head.hex()

    if note:
        log("SUSPECT %s :: %s" % (original, note))
        os.replace(long_path(tmp), long_path(dest + ".suspect"))
        return False, n, note, "suspect"
    os.replace(long_path(tmp), long_path(dest))
    return True, n, "", ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--domain", required=True, action="append", metavar="SOURCE",
                    help="the dead host, e.g. download.example.net. Repeatable. A value "
                         "containing a slash is asked for as a path prefix instead of a domain")
    ap.add_argument("--root", required=True, help="the mirror tree")
    ap.add_argument("--archive", required=True, help="subdirectory to write into")
    ap.add_argument("--exclude", action="append", default=[], metavar="REGEX",
                    help="drop URLs matching this regex. Repeatable")
    ap.add_argument("--host-dirs", choices=("auto", "always", "never"), default="auto",
                    help="give each host its own top-level directory. 'auto' (default) does so "
                         "only when a run covers more than one host -- which makes the LAYOUT "
                         "depend on the INVOCATION, so pass 'always' when an archive holds "
                         "several hosts but this particular run fetches only one of them")
    ap.add_argument("--skip-listed", metavar="FILE",
                    help="drop URLs whose filename appears in FILE, one per line -- a manifest "
                         "of what is already mirrored elsewhere")
    ap.add_argument("--retry-suspect", action="store_true",
                    help="re-fetch URLs whose previous attempt was set aside as *.suspect. Off by "
                         "default, and it is the WEAKER of the two ways to revisit one: this "
                         "re-requests the same URL and gets whichever capture Wayback picks, so "
                         "the same short bytes usually come back. suspect-reconsider.py ranks "
                         "ALL captures of the URL first and is what actually settles it")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched, fetch nothing")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1). The Internet Archive is not a "
                         "CDN; there is no hurry and this runs once")
    ap.add_argument("--min-free-gb", type=float, default=1.0,
                    help="stop fetching when the volume has less than this much free (default 1). "
                         "The run ends cleanly and is resumable; it does not fill the disk.")
    args = ap.parse_args()

    # A pattern that arrives looking like a Windows path was rewritten in transit, and the run
    # would otherwise proceed with an exclusion that silently matches nothing. See MANGLED.
    for p in args.exclude:
        if MANGLED.match(p):
            sys.exit(
                "--exclude %r looks like it was rewritten by the shell.\n"
                "  Git Bash / MSYS2 converts an argument that begins with '/' into a Windows path\n"
                "  before a native python.exe sees it: '/download/sources/' arrives as\n"
                "  'C:/Program Files/Git/download/sources/', which matches nothing and drops\n"
                "  nothing -- the run then looks healthy while the exclusion does not exist.\n"
                "  Drop the leading slash ('download/sources/'), or set MSYS_NO_PATHCONV=1."
                % p)

    try:
        excludes = [re.compile(p) for p in args.exclude]
    except re.error as exc:
        sys.exit("bad --exclude regex: %s" % exc)

    skip_names = set()
    if args.skip_listed:
        with io.open(args.skip_listed, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    skip_names.add(line.rsplit("/", 1)[-1])

    root = os.path.join(os.path.abspath(args.root), args.archive)
    logdir = os.path.join(os.path.abspath(args.root), "logs")
    os.makedirs(logdir, exist_ok=True)
    # The disk-floor check in save() asks about this directory. It must exist before any worker
    # runs, and --root is created by the caller or by the line above, so use the tree root rather
    # than the archive subdirectory, which may be new.
    global SALVAGE_ROOT, MIN_FREE_BYTES
    SALVAGE_ROOT = os.path.abspath(args.root)
    MIN_FREE_BYTES = int(args.min_free_gb * 10 ** 9)
    logfile = io.open(os.path.join(logdir, args.archive + ".log"), "a", encoding="utf-8")

    def log(text):
        logfile.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        logfile.flush()

    rows, seen_urls = [], set()
    for source in args.domain:
        print("Asking the CDX index about %s ..." % source, flush=True)
        got = cdx_rows(source)
        fresh = [r for r in got if r[0] not in seen_urls]
        for r in fresh:
            seen_urls.add(r[0])
        rows.extend(fresh)
        print("  %d rows, %d not already seen from an earlier source" % (len(got), len(fresh)))

    keep, dropped = wanted(rows, excludes, skip_names)
    hosts = sorted({host_of(o) for o, _ in keep})
    # 'auto' reads the layout off this run's own URL set, which is wrong whenever an archive holds
    # several hosts and a run fetches one of them: the same host then lands in a different place
    # depending on what else was asked for in the same command. Measured the hard way -- fetching
    # gnome.bullfreeware.com on its own wrote it into the archive ROOT beside bullfreeware.com/
    # instead of into gnome.bullfreeware.com/, because that run saw exactly one host.
    host_dir = {"always": True, "never": False}.get(args.host_dirs, len(hosts) > 1)
    print("\n  %d rows indexed, %d to fetch" % (len(rows), len(keep)))
    for why, n in sorted(dropped.items()):
        print("     dropped %-24s %d" % (why, n))
    print("     hosts %s%s" % (", ".join(hosts),
                               "  (each gets its own directory)" if host_dir else ""))
    if args.dry_run:
        for original, ts in keep[:20]:
            print("     %s  %s" % (ts, original))
        if len(keep) > 20:
            print("     ... and %d more" % (len(keep) - 20))
        print("\nDry run -- nothing fetched.")
        return 0

    log("SALVAGE START %s -> %s  (%d urls, %d declined)"
        % (", ".join(args.domain), root, len(keep), sum(dropped.values())))
    for why, n in sorted(dropped.items()):
        log("  declined %-26s %d" % (why, n))
    ok = skipped = 0
    kinds = {"throttled": 0, "unfetchable": 0, "suspect": 0, "broken": 0}
    total = 0
    pace = Pace(args.delay)
    t0 = time.time()
    for i, (original, ts) in enumerate(keep, 1):
        dest = salvage_path(root, original, host_dir)
        # A .suspect counts as ALREADY DONE. It is the recorded verdict of a completed transfer --
        # the archive served all it had and the size check caught the shortfall -- so a later run
        # that treats it as outstanding downloads the same short bytes again and writes the same
        # file. Measured: a resumed run spent 43 minutes re-fetching gcc, gimp and gtk+ tarballs
        # at ~10 MB each, produced not one new complete file, and looked busy the whole time.
        # --retry-suspect exists for the one case this gets wrong: a shortfall caused by OUR
        # connection dropping rather than by the record ending. The CDX `length` column tells the
        # two apart -- when it is close to what arrived, the record is complete and final.
        #
        # THAT IS TRUE OF THIS CAPTURE AND SAYS NOTHING ABOUT THE OTHERS. A URL can have many,
        # and the one this run happened to take need not be the longest. Skipping here is still
        # right -- re-walking a whole salvage to re-test 94 files is the wrong shape for it --
        # but "skipped" must not be read as "settled". suspect-reconsider.py settles it.
        if os.path.exists(long_path(dest)):
            skipped += 1
            continue
        if not args.retry_suspect and os.path.exists(long_path(dest + ".suspect")):
            skipped += 1
            continue
        # ONE BAD URL MUST NOT KILL THE RUN. A `%2A` in a path unquoted to a literal '*' and took
        # down a seven-hour salvage at URL 6390 of 7410, in os.makedirs, before it had reached the
        # subdomain that was the whole reason for the job. Everything already fetched survived --
        # the tree is the state -- but the remaining 1020 URLs simply did not happen, and the
        # run's own summary never printed, so it looked finished rather than dead.
        try:
            good, n, _note, kind = save(original, ts, dest, log, pace)
        except Exception as exc:  # noqa: BLE001 -- deliberately everything
            log("BROKEN %s :: %s" % (original, exc))
            good, n, kind = False, 0, "broken"
        if good:
            ok += 1
            total += n
        else:
            kinds[kind] = kinds.get(kind, 0) + 1
        if i % 10 == 0 or i == len(keep):
            print("  %d/%d  ok %d  throttled %d  unfetchable %d  suspect %d  broken %d"
                  "  skipped %d  %s (%.1fs)"
                  % (i, len(keep), ok, kinds["throttled"], kinds["unfetchable"],
                     kinds["suspect"], kinds["broken"], skipped, human(total), pace.delay),
                  flush=True)
        pace.sleep()

    el = time.time() - t0
    print("\n  fetched %d, already present %d, %s in %dm%02ds"
          % (ok, skipped, human(total), el // 60, el % 60))
    log("SALVAGE DONE ok=%d throttled=%d unfetchable=%d suspect=%d broken=%d skipped=%d bytes=%d"
        % (ok, kinds["throttled"], kinds["unfetchable"], kinds["suspect"], kinds["broken"],
           skipped, total))

    if kinds["broken"]:
        print("  %d could not be written to disk at all -- see BROKEN in logs/%s.log. That is a"
              % (kinds["broken"], args.archive))
        print("  defect in this tool, not in the archive: the URL maps to a path the filesystem")
        print("  refuses. Worth fixing; the run continued past it rather than dying.")

    if kinds["throttled"]:
        print("  %d THROTTLED -- the archive refused the connection even after %d retries."
              % (kinds["throttled"], len(BACKOFF)))
        print("  Those files are almost certainly fine. RUN THIS AGAIN with a larger --delay;")
        print("  what is already here is skipped, so a second pass costs only the remainder.")
        print("  Pacing reached %.1fs during the run (started at %.1fs)."
              % (pace.slowest, args.delay))
    if kinds["unfetchable"]:
        print("  %d could not be replayed -- see logs/%s.log. A row indexed 200 that will not"
              % (kinds["unfetchable"], args.archive))
        print("  replay is a known Internet Archive condition, not a defect in this run, and it")
        print("  is worth one more attempt on another day.")
    if kinds["suspect"]:
        print("  %d arrived short or with the wrong magic and are kept as *.suspect. These are"
              % kinds["suspect"])
        print("  the ones this capture cannot improve on. That is NOT the same as unrecoverable:")
        print("  run suspect-reconsider.py, which checks every capture of each URL. It has")
        print("  already turned 15 such files back into complete ones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
