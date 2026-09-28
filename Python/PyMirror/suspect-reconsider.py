# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Reconsider every .suspect against ALL Internet Archive captures, not just the one that failed.

WHAT THIS EXISTS TO CORRECT. wayback-salvage.py sets a file aside as `<name>.suspect` when the
bytes it received are shorter than the capture claimed, and its own documentation called that
verdict final:

    suspect       short or wrong-magic file  do not retry, that is all there is

The reasoning behind it was sound and was actually measured: for `gcc-3.3.tar.gz` the CDX index
lists ONE capture, status 200, length 9 985 620 -- the stored WARC record is itself ~10 MB, the
Archive's crawler hit a per-file ceiling in 2009 and stopped, and no amount of re-fetching will
produce bytes the Archive never kept.

Every word of that is true, and it generalises to nothing. It was established on a URL WITH ONE
CAPTURE and then applied to URLs with several. Re-checking all of them found:

    rs6000-microcode  12 of 15 recovered from later captures, +30 MB
    gcc-3.3.0.0.exe   held  9 999 682 B; best capture 51 263 345 B
    samba-3.0.4.0.bff held    130 767 B; best capture 21 344 390 B

So the rule keeps its evidence and gains the qualifier it always needed:

    A .SUSPECT IS FINAL ONLY WHEN THE BEST CAPTURE IS SHORT.

One CDX query per file settles it. `--retry-suspect` in wayback-salvage.py does NOT settle it:
it re-requests the same URL, Wayback replays a capture of its own choosing, and the same short
bytes come back -- which is exactly the observation that got written down as proof of finality.
Asking the same question again is not a second opinion.

WHY THIS MATTERS MORE THAN THE FILES. The .suspect set IS this collection's record of permanent
loss; markers and PROVENANCE files cite it by count. A wrong "final" is not a missing file, it is
a decision that stops anyone from looking again -- and it propagates into the written record as a
fact.

CDX `length` IS THE COMPRESSED WARC RECORD SIZE, not the file size. For already-compressed content
(.gz, .zip, .exe) the two are close; for text it can be far smaller than the file. So `length` is
used only to RANK captures and to decide whether the best one is worth fetching -- never as the
expected size. The decision to install is made on the bytes that actually arrive.

URL RECONSTRUCTION is from the on-disk layout, which wayback-salvage.py writes as
<archive>/<host>/<path> when several hosts share an archive and <archive>/<path> when one does.
The host is read from the completion marker rather than hardcoded; getting it wrong produces "no
200 captures" for everything, and THAT FAILURE LOOKS EXACTLY LIKE "nothing to recover" -- which is
what a first attempt produced before the difference was noticed.

The `id_` replay modifier is mandatory: without it Wayback injects its toolbar into the response
and the bytes are silently corrupted.

TWO CAPTURES OF ONE PAGE NEVER COMPARE EQUAL, and the inequality says nothing about the content.
A CMS stamps every asset URL with a token that changes per deploy -- IBM's `?t<hex>`, Drupal's
`form_build_id` nonce, a cache version in every stylesheet href -- so a byte comparison answers a
question about the server's release schedule. Normalise the tokens away first, then compare what
is left. Three IBM APAR pages measured that way differed from the copies already held by 47
bytes, every one of them a version stamp or a nonce; compared without it they looked like three
documents this collection did not have.

    python suspect-reconsider.py                    # dry run: asks CDX, downloads nothing
    python suspect-reconsider.py --apply            # fetch and install where a better capture exists
    python suspect-reconsider.py --archive aixtools --apply
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (MIRROR_ROOT, ARCHIVE_MARKERS, BFF_MAGIC, Backoff, Pacer, http_open,
                    iter_archives, long_path, relative_to, split_archive)
from wayback import wayback_cdx_url, wayback_replay_url

ROOT = MIRROR_ROOT

# wayback-salvage.py's check, repeated here rather than imported: a hyphen in that file's name
# makes it unimportable, and a copied constant that drifts is better than a tool that cannot run.

# A capture must beat what we hold by more than this before it is worth a request. Small
# differences are usually the compressed-vs-actual gap described above, not a better file.
MARGIN = 1000

RECORD = "SUSPECT-RECONSIDERED.txt"

# Everything this tool talks to is one service. Pacing per host is what `Pacer` does; naming the
# key once says that out loud rather than leaving a bare string at two call sites.
INTERNET_ARCHIVE = "web.archive.org"

# THE THREE KINDS OF PAUSE, side by side, because this one file has all three.
#
# A RATE: do not query the CDX index, or fetch a replay, more often than this. `Pacer` counts the
# time the request itself took towards the wait -- `time.sleep(pause)` did not, so the old code
# waited `pause` PLUS however long the Archive took to answer, which on a slow day was double.
PACE = Pacer(0.0)            # the interval comes from --pause, set where it is known
REPLAY_PACE = Pacer(6.0)

# A LADDER: after a failed CDX query, wait longer before trying again -- and longer still when the
# Archive says 429 or 503, because those are the server talking about us. 12 s flat otherwise,
# 30/60/90 when throttled, which is exactly what this file did by hand.
CDX_RETRY = Backoff(first=12, factor=1, throttled_first=30, throttled_step=30)

# A COOLDOWN after a fetch that failed outright. See the call site: it is neither of the above.
FAILURE_COOLDOWN = 20


def source_hosts(text):
    """Hostnames the marker names as the origin, in the order it names them.

    web.archive.org is filtered out: it is how the files were reached, never what they are.
    """
    out = []
    for m in re.finditer(r"https?://([A-Za-z0-9.-]+)", text or ""):
        h = m.group(1).lower().rstrip(".")
        if h not in out and "archive.org" not in h:
            out.append(h)
    return out


def _bare(h):
    return h[4:] if h.startswith("www.") else h


def is_host_component(first, hosts):
    """Does the archive's layout start with a host directory?

    Compared with `www.` stripped from both sides, because a marker that says
    `http://www.bullfreeware.com/` produced a directory named `bullfreeware.com`.
    """
    if "." not in first:
        return False
    f = _bare(first.lower())
    return any(f == _bare(h) for h in hosts)


def cdx(url, tries=4):
    """All captures of `url`. Returns (rows, reason); rows is None when the query failed.

    None and [] are deliberately different: one is "the Archive did not answer", the other is
    "the Archive answered, and has nothing". Collapsing them reports a network problem as a
    permanent loss -- the precise mistake this tool exists to undo.

    THE REASON IS CARRIED OUT because the two failures that matter look identical from here. An
    HTTP 429 means we asked too fast and the answer is still available; anything else may mean
    the index genuinely has no record. This collection has already once printed "no capture" for
    twelve questions that were never answered, and acted on it.
    """
    # The JSON form, and only the three columns this ranks on. Its first row is a header,
    # which is why the caller below starts at rows[1:].
    q = wayback_cdx_url(url, match="", fields="timestamp,statuscode,length", output="json")
    reason = "unknown"
    for attempt in range(tries):
        try:
            with http_open(q, timeout=90) as r:
                return json.load(r), ""
        except urllib.error.HTTPError as exc:
            reason = "HTTP %s" % exc.code
            # 429/503 are about us, and backing off is the only cooperative reply. That
            # distinction is the whole reason `Backoff` takes a `throttled` flag: every other
            # error is a thing that happened, those two are a request.
            CDX_RETRY.wait(attempt, throttled=exc.code in (429, 503))
        except Exception as exc:
            reason = type(exc).__name__
            CDX_RETRY.wait(attempt)
    return None, reason


def fetch(ts, url, timeout=900):
    # `url` here is host/path with no scheme -- that is what the records hold -- and
    # wayback_replay_url adds one.
    with http_open(wayback_replay_url(ts, url), timeout=timeout) as r:
        return r.read()


def archives_with_suspects(root, only=None):
    out = {}
    # common.iter_archives() decides what an archive is, and long_path()s it. Measured
    # before the change: `logs/` holds 315 files and not one .suspect, so skipping it --
    # which this loop did not -- costs nothing here and keeps one answer in one place.
    for name, base in iter_archives(root, only):
        found = [(rt, f) for rt, _d, fs in os.walk(base) for f in fs if f.endswith(".suspect")]
        if found:
            out[name] = (base, sorted(found))
    return out


def read_marker_text(base):
    for cand in ARCHIVE_MARKERS:
        p = os.path.join(base, cand)
        if os.path.exists(p):
            try:
                return io.open(long_path(p), encoding="utf-8", errors="replace").read()
            # A FILE THAT WILL NOT OPEN, and nothing else. It was `except Exception: pass`, which
            # also catches a NameError or a typo'd attribute and returns "" -- indistinguishable
            # from an archive that has no marker, and wrong about every archive at once. That
            # exact shape was found in recheck-decisions.py on 2026-09-24, where it had inverted
            # the tool's whole answer for weeks.
            except OSError:
                pass
    return ""


def install(dest, data, suspect_path):
    """Write `data` at `dest` atomically and retire the .suspect. Returns a note, or "" on success.

    The .suspect is RENAMED, never deleted: it is the evidence for a verdict this collection has
    written into its own record, and the replacement has not been verified by anything yet.
    """
    if dest.lower().endswith(".i") and data[:4] != BFF_MAGIC:
        return "wrong magic for a BFF fileset"
    if os.path.exists(long_path(dest)) and os.path.getsize(long_path(dest)) >= len(data):
        return "a file already sits at that name and is not shorter"
    tmp = dest + ".part-reconsider"
    with io.open(long_path(tmp), "wb") as fh:
        fh.write(data)
    os.replace(long_path(tmp), long_path(dest))
    os.replace(long_path(suspect_path), long_path(suspect_path + ".superseded"))
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--archive", help="only this archive")
    ap.add_argument("--apply", action="store_true",
                    help="fetch better captures and install them. Without it nothing is "
                         "downloaded and nothing on disk is touched.")
    ap.add_argument("--pause", type=float, default=3.0,
                    help="seconds between CDX queries (default 3)")
    args = ap.parse_args()

    found = archives_with_suspects(args.root, args.archive)
    if not found:
        print("no .suspect files under %s" % args.root)
        return 0

    total = sum(len(v[1]) for v in found.values())
    print("%d .suspect file(s) in %d archive(s)%s\n"
          % (total, len(found), "" if args.apply else "   DRY RUN -- nothing is downloaded"))

    grand = {"recovered": 0, "final": 0, "unknown": 0, "gained": 0}

    for name, (base, items) in found.items():
        hosts = source_hosts(read_marker_text(base))
        print("=== %s   %d .suspect   origin: %s"
              % (name, len(items), ", ".join(hosts) if hosts else "UNKNOWN"))
        if not hosts:
            print("    no origin host in the marker -- skipped rather than guessed\n")
            grand["unknown"] += len(items)
            continue

        lines = []
        for rt, fn in items:
            stem = fn[:-len(".suspect")]
            spath = os.path.join(rt, fn)
            have = os.path.getsize(long_path(spath))
            rel = relative_to(base, os.path.join(rt, stem))
            first = split_archive(rel)[0]
            if is_host_component(first, hosts):
                url = rel
            elif "." in first and len(hosts) > 1:
                print("    %-44s ambiguous host for %s -- skipped" % (stem[:44], first))
                grand["unknown"] += 1
                continue
            else:
                url = "%s/%s" % (hosts[0], rel)

            PACE.pause = args.pause
            PACE.wait(INTERNET_ARCHIVE)
            rows, why = cdx(url)
            if rows is None:
                print("    %-44s UNANSWERED (%s) -- not a verdict" % (stem[:44], why))
                lines.append("UNKNOWN  %s  CDX unanswered: %s" % (rel, why))
                grand["unknown"] += 1
                continue
            caps = [(int(r[2]), r[0]) for r in rows[1:] if r[1] == "200" and str(r[2]).isdigit()]
            if not caps:
                print("    %-44s no 200 capture (%s)" % (stem[:44], url[-42:]))
                lines.append("UNKNOWN  %s  no 200 capture" % rel)
                grand["unknown"] += 1
                continue

            best, ts = max(caps)

            # THE STRONGER REASON FIRST. With one capture there is nothing to rank and nothing
            # else to try -- that is the original gcc-3.3.tar.gz finding, correctly scoped, and it
            # settles the file outright. The size comparison below is the WEAKER argument, because
            # CDX `length` is a compressed record size: all eleven aixtools filesets report a
            # `length` well BELOW the bytes already held, which proves nothing about completeness
            # on its own. Reporting the strong reason where it applies keeps the record honest
            # about what each verdict actually rests on.
            if len(caps) == 1:
                print("    %-44s FINAL   the only capture there is (length %d, held %d)"
                      % (stem[:44], best, have))
                lines.append("FINAL    %s  sole capture  held=%d cdx_length=%d" % (rel, have, best))
                grand["final"] += 1
                continue
            if best <= have + MARGIN:
                print("    %-44s FINAL   best of %d captures is %d, held %d"
                      % (stem[:44], len(caps), best, have))
                lines.append("FINAL    %s  held=%d best=%d captures=%d" % (rel, have, best, len(caps)))
                grand["final"] += 1
                continue

            if not args.apply:
                print("    %-44s BETTER  %d -> %d B (%s, %d captures)"
                      % (stem[:44], have, best, ts, len(caps)))
                lines.append("BETTER   %s  held=%d best=%d ts=%s" % (rel, have, best, ts))
                continue

            try:
                data = fetch(ts, url)
            except Exception as exc:
                print("    %-44s fetch failed: %s" % (stem[:44], str(exc)[:38]))
                lines.append("UNKNOWN  %s  fetch failed" % rel)
                grand["unknown"] += 1
                # NEITHER A RATE NOR A LADDER, and left as it is for that reason. There is no
                # attempt counter here -- the item is abandoned, not retried -- and it is longer
                # than the ordinary pace on purpose: a replay that failed is a sign the service
                # is unhappy, and the next item should not follow immediately. Two of this
                # collection's 41 pauses are of this third kind (the other is move-mirror's
                # "let the drive drain"), they share no arithmetic, and a helper wrapping one
                # `sleep` would say less than this comment does.
                time.sleep(FAILURE_COOLDOWN)
                continue

            if len(data) <= have:
                print("    %-44s replay gave %d, no better than %d" % (stem[:44], len(data), have))
                lines.append("FINAL    %s  replay=%d held=%d" % (rel, len(data), have))
                grand["final"] += 1
            else:
                note = install(os.path.join(rt, stem), data, spath)
                if note:
                    print("    %-44s NOT installed: %s" % (stem[:44], note))
                    lines.append("UNKNOWN  %s  not installed: %s" % (rel, note))
                    grand["unknown"] += 1
                else:
                    print("    %-44s RECOVERED %d -> %d B (%s)"
                          % (stem[:44], have, len(data), ts))
                    lines.append("RECOVERED %s  %d -> %d  ts=%s" % (rel, have, len(data), ts))
                    grand["recovered"] += 1
                    grand["gained"] += len(data) - have
            REPLAY_PACE.wait(INTERNET_ARCHIVE)

        if lines and args.apply:
            with io.open(long_path(os.path.join(base, RECORD)), "w", encoding="utf-8") as fh:
                fh.write("Every .suspect in this archive, checked against EVERY Internet Archive\n"
                         "capture of its URL -- not only the one the salvage happened to take.\n"
                         "Written by suspect-reconsider.py.\n\n")
                fh.write("\n".join(lines) + "\n")
            print("    record written to %s" % RECORD)
        print("")

    print("recovered %d (+%.1f MB), confirmed final %d, undetermined %d"
          % (grand["recovered"], grand["gained"] / 1e6, grand["final"], grand["unknown"]))
    if grand["unknown"]:
        print("THE %d UNDETERMINED ARE NOT FINAL. An unanswered question is not a no; rerun\n"
              "them later with a longer --pause before any of them is written down as lost."
              % grand["unknown"])
    if not args.apply:
        print("dry run -- rerun with --apply to fetch the captures marked BETTER")
    return 0


if __name__ == "__main__":
    sys.exit(main())
