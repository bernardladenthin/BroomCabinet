# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Re-read every byte in the collection and check it against the recorded SHA-256.

    python verify-content.py                          # all archives, resumable
    python verify-content.py --archive tuhs --archive vtda
    python verify-content.py --resume                 # skip archives already passed

WHY THIS IS NOT `mirror.py --verify`. That compares the tree's FILE COUNT and BYTE TOTAL against
the marker, and says so itself: "Counts and bytes cannot see a file whose content changed while
its size stayed the same." Bit rot does exactly that -- a flipped bit on a platter leaves the size
untouched. Before 3.5 TB goes into long-term storage, the only honest check is to read it all back
and hash it. This tool does that, and nothing else.

WHAT IT CAN AND CANNOT TELL YOU. A MISMATCH means the bytes on disk are not the bytes that were
fetched. It does NOT say which side is wrong: a file can also mismatch because it was legitimately
replaced. It reports; it never repairs and never deletes. MISSING means the index names a file the
tree no longer has -- the failure `mirror.py --verify` was blind to for 21 trailing-dot files.

RESUMABILITY IS THE POINT. A 3.5 TB pass takes hours and will be interrupted. Each archive's
verdict is appended to the state file the moment it finishes, so `--resume` picks up at the next
unverified archive rather than starting over. State is written with flush+fsync -- a verdict that
exists only in a buffer is a verdict lost to the interruption it was meant to survive.

DO NOT PIPE THIS THROUGH `tail` OR `head`. The shell reports the LAST command's exit status, so a
verifier that died looks exactly like one that passed -- this collection has already lost two hours
to that. `tail` also buffers, so a night run would write nothing until it ended. Use --log.
"""
import argparse
import hashlib
import io
import os
import sys
import time

from common import MIRROR_ROOT, SUMS_FILE, human, long_path, say

CHUNK = 4 << 20


def sha256(path):
    h = hashlib.sha256()
    n = 0
    with io.open(path, "rb") as fh:
        while True:
            c = fh.read(CHUNK)
            if not c:
                break
            h.update(c)
            n += len(c)
    return h.hexdigest(), n


def verify_archive(root, name, log, every):
    base = os.path.join(root, name)
    idx = os.path.join(base, SUMS_FILE)
    if not os.path.isfile(idx):
        say("  %-22s NO INDEX -- run mirror.py --index" % name, log)
        return None

    want = []
    with io.open(idx, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            h, rel = line[:64], line[66:].rstrip("\r\n")
            if len(h) == 64 and rel:
                want.append((h, rel))

    bad, missing, unreadable = [], [], []
    done = seen_bytes = 0
    t0 = time.time()
    for h, rel in want:
        full = long_path(os.path.join(base, rel.replace("/", os.sep)))
        try:
            got, n = sha256(full)
        except FileNotFoundError:
            missing.append(rel)
            continue
        except OSError as exc:
            unreadable.append("%s -- %s" % (rel, exc.__class__.__name__))
            continue
        done += 1
        seen_bytes += n
        if got != h:
            bad.append(rel)
            say("     MISMATCH %s" % rel, log)
        if every and done % every == 0:
            el = time.time() - t0
            say("     %d/%d  %s  %.0f MB/s" % (done, len(want), human(seen_bytes),
                                               seen_bytes / 1e6 / max(el, 1e-9)), log)

    el = time.time() - t0
    verdict = "OK" if not (bad or missing or unreadable) else "FAIL"
    say("  %-22s %-4s %6d files  %10s  %5.0f MB/s  %s"
        % (name, verdict, done, human(seen_bytes), seen_bytes / 1e6 / max(el, 1e-9),
           "" if verdict == "OK" else "%d mismatch, %d missing, %d unreadable"
           % (len(bad), len(missing), len(unreadable))), log)
    for rel in missing:
        say("     MISSING  %s" % rel, log)
    for u in unreadable:
        say("     UNREADABLE %s" % u, log)
    return {"archive": name, "verdict": verdict, "files": done, "bytes": seen_bytes,
            "mismatch": len(bad), "missing": len(missing), "unreadable": len(unreadable),
            "seconds": round(el, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append", default=[])
    ap.add_argument("--resume", action="store_true",
                    help="skip archives that already have a verdict in the state file")
    ap.add_argument("--state", default=None, help="default: <root>/logs/verify-content.state")
    ap.add_argument("--log", default=None)
    ap.add_argument("--every", type=int, default=200, help="progress line every N files; 0 = off")
    args = ap.parse_args()

    names = args.archive or sorted(
        d for d in os.listdir(args.root)
        if os.path.isfile(os.path.join(args.root, d, SUMS_FILE)))

    state_path = args.state or os.path.join(args.root, "logs", "verify-content.state")
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    already = {}
    if os.path.isfile(state_path):
        with io.open(state_path, encoding="utf-8") as fh:
            for line in fh:
                p = line.split("\t")
                if len(p) >= 3:
                    already[p[1]] = p[2]

    log = io.open(args.log, "a", encoding="utf-8") if args.log else None
    say("verify-content  %d archives under %s" % (len(names), args.root), log)
    if args.resume and already:
        say("  resuming: %d already verified" % sum(1 for n in names if n in already), log)

    t0 = time.time()
    results = []
    # Archives that could not be verified because they carry no .sha256sum. THESE MUST BE REPORTED
    # RATHER THAN SKIPPED. Until 2026-09-08 an archive with no index simply fell out of the loop,
    # and the run then printed "every byte matches its recorded checksum" and exited 0 -- over a
    # tree it had not read one byte of. `--archive ia-bull-aix433-2013` said exactly that about
    # 2.36 GB with no index at all. A verifier whose silence is indistinguishable from success is
    # worse than no verifier, because it is trusted.
    unindexed = []
    for name in names:
        if args.resume and already.get(name) == "OK":
            say("  %-22s skipped (already OK)" % name, log)
            continue
        r = verify_archive(args.root, name, log, args.every)
        if r is None:
            unindexed.append(name)
            say("  %-22s NO .sha256sum -- nothing verified" % name, log)
            continue
        results.append(r)
        # Append and fsync per archive: an interrupted run must keep every verdict it earned.
        with io.open(state_path, "a", encoding="utf-8") as fh:
            fh.write("%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\n"
                     % (time.strftime("%Y-%m-%dT%H:%M:%S"), r["archive"], r["verdict"],
                        r["files"], r["bytes"], r["mismatch"], r["missing"], r["unreadable"]))
            fh.flush()
            os.fsync(fh.fileno())

    el = time.time() - t0
    tb = sum(r["bytes"] for r in results)
    failed = [r for r in results if r["verdict"] != "OK"]
    say("\n" + "=" * 78, log)
    say("  %d archives, %d files, %s in %.1f h  (%.0f MB/s average)"
        % (len(results), sum(r["files"] for r in results), human(tb), el / 3600,
           tb / 1e6 / max(el, 1e-9)), log)
    if failed:
        say("  %d ARCHIVES FAILED:" % len(failed), log)
        for r in failed:
            say("    %-22s %d mismatch, %d missing, %d unreadable"
                % (r["archive"], r["mismatch"], r["missing"], r["unreadable"]), log)
    elif results:
        say("  every byte matches its recorded checksum", log)

    # Said separately from the verdict above, and never folded into it: these archives have NO
    # local integrity record, so nothing here is a statement about them either way.
    if unindexed:
        say("", log)
        say("  %d ARCHIVE(S) COULD NOT BE VERIFIED -- no .sha256sum:" % len(unindexed), log)
        for n in unindexed:
            say("    %s" % n, log)
        say("  Fetched-time checksums (e.g. the Internet Archive's MD5) are not a substitute:", log)
        say("  they prove what arrived, not what is on the disk today.", log)
    elif not results:
        say("  nothing to verify", log)

    say("  state: %s" % state_path, log)
    if log:
        log.close()
    # Unindexed archives are a failure of this run to do its job, not a clean result. Exiting 0
    # would let a nightly caller treat "I read nothing" as "everything is fine".
    sys.exit(1 if (failed or unindexed) else 0)


if __name__ == "__main__":
    main()
