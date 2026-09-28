# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Fetch the files that a case-INSENSITIVE local directory made mirror.py drop.

THE DEFECT THIS REPAIRS. HTTP paths are case-sensitive; NTFS by default is not. When a source
directory holds both `2153CDK.EXE` and `2153cdk.exe`, mirror.py's claim map -- which lowercases --
sees one key. On a case-sensitive target it fetches both and logs `COLLISION`. On a case-
insensitive one it CANNOT, so it keeps the first, drops the second, and logs `COLLISION DROPPED`.
That is the correct behaviour: a deterministic, logged loss beats whichever download finished last.

But it is still a loss, and it is only correct as a fallback. The remedy is to set the NTFS
per-directory case-sensitivity flag and fetch what was dropped.

WHY THE FLAG CANNOT SIMPLY BE SET AT THE ROOT. It is inherited by directories created AFTERWARDS,
never applied retroactively to existing ones. `ps-2.kev009.com/pccbbs/aptiva/` was created without
it in August; enabling the flag on the archive root today does nothing for that directory. So this
script sets it on each affected directory individually, which is also far fewer fsutil calls than
walking the whole tree.

WHY NOT JUST RE-RUN mirror.py. It would work -- with the flag set and every present file skipped,
a normal run fetches exactly the missing ones. It would also re-enumerate thousands of directory
listings against a machine this collection has agreed to be careful with (rule R9/R11: one
person's server). 153 targeted requests is the polite form of the same repair.

MEASURED FIRST, on 2026-09-08, before any of this was written: six pairs sampled from
ps-2.kev009.com and fetched under both spellings. Three were byte-identical -- the same file
listed twice -- and three were genuinely different, including `epr2f.inf` at 1 155 162 against
1 397 388 bytes. So the drops are real content, not an artefact of a case-folding origin. Had all
six matched, the right answer would have been to record that and fetch nothing.

    python case-collision-recover.py --archive ps-2.kev009.com --dry-run
    python case-collision-recover.py --archive ps-2.kev009.com
"""
import argparse
import hashlib
import io
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import MIRROR_ROOT, COLLISION_DROPPED, Pacer, exists, host_of, http_open, say, set_case_sensitive

PAT = COLLISION_DROPPED


def fetch(url, out):
    with http_open(url, timeout=120) as r:
        body = r.read()
    tmp = out + ".part"
    with io.open(tmp, "wb") as fh:
        fh.write(body)
    if exists(out):
        os.remove(tmp)
        raise IOError("target already exists -- refusing to overwrite %s" % out)
    os.rename(tmp, out)
    return len(body), hashlib.sha256(body).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--log", default=None, help="default: <root>/logs/<archive>-case-recover.log")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests. Default 1.0 -- this is someone's server.")
    args = ap.parse_args()

    src_log = os.path.join(args.root, "logs", "%s.log" % args.archive)
    if not os.path.isfile(src_log):
        sys.exit("no crawl log at %s" % src_log)

    pairs = set()
    for line in io.open(src_log, encoding="utf-8", errors="replace"):
        m = PAT.search(line)
        if m:
            pairs.add((m.group(1), m.group(2)))
    if not pairs:
        say("  no COLLISION DROPPED lines in %s -- nothing to recover" % src_log)
        return 0

    base_url = "/".join(sorted(pairs)[0][0].split("/")[:3]) + "/"
    base = os.path.join(args.root, args.archive)

    # Only the pairs where the dropped file is STILL absent and the kept one IS present. A run
    # after the flag was set may already have healed some of these, and a log line is not evidence
    # about today -- only the tree is.
    todo = []
    healed = 0
    for dropped, kept in sorted(pairs):
        if not dropped.startswith(base_url) or not kept.startswith(base_url):
            continue
        pd = os.path.join(base, urllib.parse.unquote(dropped[len(base_url):])
                          .replace("/", os.sep))
        pk = os.path.join(base, urllib.parse.unquote(kept[len(base_url):]).replace("/", os.sep))
        if exists(pd):
            healed += 1
            continue
        if not exists(pk):
            # Neither spelling present: not a case problem, and not this script's business.
            continue
        todo.append((dropped, pd))

    say("  %s: %d dropped pairs, %d already healed, %d to fetch"
        % (args.archive, len(pairs), healed, len(todo)))
    dirs = sorted({os.path.dirname(p) for _u, p in todo})
    say("  %d directories affected" % len(dirs))

    if args.dry_run:
        for d in dirs:
            say("     would enable case-sensitivity: %s" % d)
        for u, _p in todo[:10]:
            say("     would fetch: %s" % u)
        if len(todo) > 10:
            say("     ... and %d more" % (len(todo) - 10))
        return 0

    logpath = args.log or os.path.join(args.root, "logs",
                                       "%s-case-recover.log" % args.archive)
    log = io.open(logpath, "a", encoding="utf-8")
    say("=== %s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), args.archive), log)

    # THE FLAG MUST BE SET BEFORE A SINGLE FETCH. Writing first would land the dropped file on top
    # of the kept one and destroy the very file we were trying to keep company.
    bad_dirs = set()
    for d in dirs:
        r = set_case_sensitive(d)
        if r is not True:
            bad_dirs.add(d)
            say("  CASE-FLAG FAILED %s -- %s" % (d, r), log)
        else:
            say("  case-sensitive enabled: %s" % d, log)
    if bad_dirs:
        say("  %d directories could not be made case-sensitive; their files are SKIPPED."
            % len(bad_dirs), log)

    # ONE PACER FOR THE WHOLE RUN, because the promise `--delay` makes is about the INTERVAL
    # between two requests: a pacer made inside the loop would be new every time and never wait.
    # The meaning of the number changes slightly with it -- `--delay 1` now means "not more often
    # than once a second", so the time the fetch itself took counts towards the pause, where
    # time.sleep(args.delay) idled a full second ON TOP of it.
    pacer = Pacer(args.delay)

    ok = skipped = failed = 0
    total = 0
    for url, out in todo:
        if os.path.dirname(out) in bad_dirs:
            # NOT PACED: nothing is asked for this file, so there is nobody to be polite to.
            skipped += 1
            continue
        pacer.wait(host_of(url))
        try:
            n, h = fetch(url, out)
        except Exception as exc:                                   # noqa: BLE001
            failed += 1
            say("  FAIL %s :: %s" % (url, exc), log)
            continue
        ok += 1
        total += n
        say("  ok %8d B  %s  %s" % (n, h[:16], url[len(base_url):]), log)

    say("  DONE fetched %d, skipped %d, failed %d, %.1f MB"
        % (ok, skipped, failed, total / 1e6), log)
    if ok:
        say("", log)
        say("  NOW RUN: python mirror.py --archive %s --index" % args.archive, log)
        say("  and update files/bytes in .mirror-complete -- neither knows about these files yet,"
            % (), log)
        say("  so `--verify` will report the archive as DIFFERS until both are brought forward.",
            log)
    log.close()
    return 1 if (failed or skipped) else 0


if __name__ == "__main__":
    sys.exit(main())
