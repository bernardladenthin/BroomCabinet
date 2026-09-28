# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fetch a KNOWN-MISSING list into an existing archive, under a hard request budget.

WHY THIS EXISTS AND WHY IT IS NOT A CRAWL. Some hosts limit a COUNT OF REQUESTS PER WINDOW rather
than a rate. `dialectronics` is the worked example: one connection failed, 1 s pacing failed, and
4 s pacing failed at the same place -- about 227 requests -- because slowing down does not avoid a
quota, it only postpones reaching it.

For an archive that is mostly complete, a re-run is then WORSE THAN USELESS. HTML_CRAWL makes
producer() re-fetch every page it already holds in order to read its links, so the window budget
is spent on RE-ENUMERATION FIRST and on missing files last. Measured 2026-09-16: 377 successful
requests, 108 failures, 259 files before and 259 after. The progress curve flattens by
construction -- 199 -> 235 -> 240 -> 255 -> 259 -> 259 -- and more sessions each buy a file or two.

So: spend every request on something that is actually missing.

THE LIST MUST BE EVIDENCE, NOT CLAIMS. Feed this the URLs a crawl RECORDED AS FAILED -- LISTFAIL,
FAIL, from its own error log. Do NOT feed it a list built by scraping links out of stored pages:
that was tried here, produced 158 candidates, and the two that were checked were both 404. A page
link is a claim that something exists; a failed request is a record that something was asked for
and not received. Only the second is worth a request from a budget this small.

STOPPING BEFORE THE PENALTY IS THE POINT. Tripping this host costs about two and a half hours of
total unreachability -- measured: the run ended 08:02, the root answered again at 10:31. So the
budget is a hard ceiling, and a short run of consecutive connect failures aborts immediately
rather than spending the remaining budget on a host that has already stopped listening. Leaving
requests unspent is cheap; the penalty is not.

    python subset-refetch.py --archive dialectronics --list missing.txt          # dry run
    python subset-refetch.py --archive dialectronics --list missing.txt --apply
"""
import argparse
import io
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from common import (MIRROR_ROOT, Pacer, atomic_write, http_open, load_mirror, local_path,
                    long_path, parse_listing)


# Windows reports a refused/blackholed TCP connect as WinError 10060 after ~21 s. Several in a
# row is this host's penalty state, not bad luck with individual files.
PENALTY_MARKERS = ("10060", "timed out", "TimeoutError", "ConnectionResetError")

# The temporary name a half-written file carries. Named for this tool rather than the plain
# `.part` mirror.py uses, because both write into the same tree.
SUFFIX = ".part-subset"


def fetch(url, timeout=120):
    """-> (status, body, last_modified). status is an int, or a string naming the failure."""
    try:
        # quote=True BECAUSE THESE URLS CAME OUT OF A LISTING. urljoin() of an href that a
        # server wrote with an unescaped space produces a url urllib refuses outright, and the
        # refusal arrives here as an ordinary failure string -- a file silently not fetched.
        # mirror.py learned this at 188 failures in 221 files; this tool reads the same listings.
        with http_open(url, timeout=timeout, quote=True) as r:
            return r.status, r.read(), r.headers.get("Last-Modified")
    except urllib.error.HTTPError as exc:
        return exc.code, b"", None
    except Exception as exc:                                    # noqa: BLE001
        return "%s: %s" % (type(exc).__name__, str(exc)[:60]), b"", None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", required=True)
    ap.add_argument("--list", required=True, dest="list_file")
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--apply", action="store_true",
                    help="actually fetch. Without it nothing leaves this machine.")
    ap.add_argument("--budget", type=int, default=180,
                    help="hard ceiling on requests (default 180, against a measured ~227 limit)")
    ap.add_argument("--stop-after-failures", type=int, default=5,
                    help="abort after this many CONSECUTIVE connect failures (default 5)")
    ap.add_argument("--interval", type=float,
                    help="seconds between requests; defaults to the archive's MIN_INTERVAL")
    ap.add_argument("--follow-listings", action="store_true",
                    help="parse a fetched directory listing and queue its children, budget "
                         "permitting. Off by default: a listing costs one request and may add "
                         "dozens, which is how a targeted run turns back into a crawl.")
    args = ap.parse_args()

    mod = load_mirror()
    base = dict(mod.ARCHIVES).get(args.archive)
    if not base:
        print("no such archive in mirror.py: %s" % args.archive)
        return 2
    root = os.path.join(args.root, args.archive)
    if not os.path.isdir(root):
        print("no archive directory at %s" % root)
        return 2

    interval = args.interval if args.interval is not None else mod.MIN_INTERVAL.get(args.archive, 0)
    # ONE MINIMUM INTERVAL, honoured across every request this run makes. This was a private
    # `Pace` class until 2026-09-25 and is now `common.Pacer`, which fixes a defect the local copy
    # had: it measured with `time.time()`, the WALL clock. A clock corrected backwards mid-run --
    # an NTP step, a timezone service, a VM resuming -- made `gap` larger than the interval by the
    # size of the jump, and the tool would have slept it off in one go. `Pacer` uses
    # `time.monotonic()`, which cannot go backwards.
    #
    # One archive means one host, so the key is constant; `Pacer` paces per key and this run has
    # exactly one.
    pace = Pacer(float(interval or 0.0))

    with io.open(args.list_file, encoding="utf-8") as fh:
        queue = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    queue = [u for u in queue if u.startswith(base)]

    print("%s -- %d URL(s), budget %d, %.1fs apart%s"
          % (args.archive, len(queue), args.budget, interval,
             "" if args.apply else "   DRY RUN -- nothing leaves this machine"))

    spent = consec = 0
    got = skipped = permfail = failed = 0
    remaining, added = [], 0
    seen = set(queue)

    i = 0
    done = set()
    while i < len(queue):
        url = queue[i]
        i += 1
        # The input list can name the same URL twice -- two different listings both linked
        # `OpenFirmware/`, and the first version of this spent two requests on it. On a budget
        # measured against a ban threshold, a duplicate is not untidiness, it is a lost file.
        if url in done:
            continue
        done.add(url)
        is_dir = url.endswith("/")
        dest = local_path(root, base, url)
        if not is_dir and os.path.exists(long_path(dest)):
            skipped += 1
            continue
        if spent >= args.budget:
            remaining.append(url)
            continue
        if not args.apply:
            print("  would fetch  %s" % url[len(base):][:74])
            spent += 1
            continue

        pace.wait(base)
        status, body, lm = fetch(url)
        spent += 1

        if isinstance(status, str):
            failed += 1
            remaining.append(url)
            if any(m in status for m in PENALTY_MARKERS):
                consec += 1
                print("  FAIL   %-58s %s" % (url[len(base):][:58], status[:24]))
                if consec >= args.stop_after_failures:
                    print("\n  %d consecutive connect failures -- the host has stopped listening."
                          % consec)
                    print("  Stopping with %d of %d requests unspent. Leaving budget on the table"
                          % (args.budget - spent, args.budget))
                    print("  is cheap; the penalty that follows hammering it is not.")
                    break
            else:
                consec = 0
            continue
        consec = 0

        if status != 200:
            permfail += 1
            print("  HTTP %-3s %-56s (the page links it; the file is not there)"
                  % (status, url[len(base):][:56]))
            continue

        if is_dir:
            if args.follow_listings:
                # parse_listing takes TEXT. Handing it bytes raises "cannot use a string pattern
                # on a bytes-like object" only once it reaches the first matcher, i.e. after the
                # request has already been spent.
                for href, _size, _mtime in parse_listing(body.decode("utf-8", "replace")):
                    child = urllib.parse.urljoin(url, href)
                    if child.startswith(base) and child not in seen:
                        seen.add(child)
                        queue.append(child)
                        added += 1
                print("  LIST   %-58s %d child(ren) queued" % (url[len(base):][:58], added))
            else:
                # The listing itself is still worth keeping -- it is the record of what was there.
                atomic_write(os.path.join(root, *[p for p in
                                                  urllib.parse.unquote(url[len(base):]).split("/")
                                                  if p] + ["index.html"]),
                             body, mtime=lm, suffix=SUFFIX)
                print("  LIST   %-58s read, %d B (children NOT queued)"
                      % (url[len(base):][:58], len(body)))
            got += 1
            continue

        # SUFFIX names this tool, so a half-written file left by an interruption cannot be
        # mistaken for one of mirror.py's -- two tools writing `.part` into one tree would
        # each treat the other's leftovers as their own to finish.
        atomic_write(dest, body, mtime=lm, suffix=SUFFIX)
        got += 1
        print("  ok     %-58s %d B" % (url[len(base):][:58], len(body)))

    remaining.extend(queue[i:])

    print("\n  %d fetched, %d already held, %d permanently absent, %d failed"
          % (got, skipped, permfail, failed))
    print("  %d of %d requests spent%s" % (spent, args.budget,
                                           ", %d queued by listings" % added if added else ""))
    if remaining:
        out = os.path.join(root, "STILL-MISSING.txt")
        if args.apply:
            with io.open(long_path(out), "w", encoding="utf-8") as fh:
                fh.write("\n".join(remaining) + "\n")
            print("  %d still missing -- written to %s" % (len(remaining), out))
        else:
            print("  %d would remain" % len(remaining))
        print("  THESE ARE NOT LOSSES. They are unanswered requests; ask again in the next window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
