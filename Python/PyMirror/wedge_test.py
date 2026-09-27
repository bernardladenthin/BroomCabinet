#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Does mirror() still terminate when the producer dies?  Red/green for one specific blocker.

THE BUG THIS EXISTS FOR
    Workers parked in an untimed q.get(), the only sentinels queued after the producer's loop,
    and non-daemon threads blocking threading._shutdown(). If the producer died anywhere in
    that loop -- a disk filling up, a Ctrl-C, a bug -- the run did not crash. It hung, forever,
    with nothing on screen. The reviewer reproduced it twice.

    A hang is not an exception, so it cannot be caught and asserted on. Each scenario therefore
    runs in its own process under a wall-clock limit: a hang shows up as a timeout.

WHY IT IS BUILT SO DEFENSIVELY
    A test for a hang reports success by *not* doing something, and that is the easiest kind of
    green to fake. This file was silently blind from 2026-08-22 until 2026-08-29 in two ways at
    once: its stub producer did not accept the exclude/seeds/html_crawl keywords the caller had
    since grown, and its fake `args` was missing three attributes mirror() had since started
    reading. Both made the producer die *before doing anything*, and a producer that dies
    instantly does terminate -- so every scenario passed, and none of them tested.

    Hence three guards, each aimed at one way of lying:

      CONTRACT      the signatures the stubs replace are checked against the real module, so a
                    rename fails the test instead of hollowing it out
      STUB-RAN      each stub announces itself, so "it terminated" cannot mean "it never began"
      CONTROL       one scenario MUST hang; if it does not, the harness cannot see hangs at all
                    and every green result below is worthless

USAGE
    python wedge_test.py            exit 0 = all scenarios behaved as expected

    Needs no network and no mirror: the URLs point at port 9 (discard), and everything is
    written into a temporary directory that is removed afterwards.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

MIRROR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirror.py")

# The parameters the stubs below stand in for. Prefixes, not full signatures: the real functions
# may grow optional keywords -- that is normal -- but if a *leading* parameter is renamed or
# reordered, a stub is no longer a substitute for the thing it replaces.
CONTRACT = {
    "worker": ["q", "root", "base_url", "stats", "log"],
    "producer": ["q", "base_url", "stats", "log"],
    "put_item": ["q", "item", "alive", "log"],
    "mirror": ["name", "base_url", "args"],
}

# A queue item is built by ITEM(i), which the driver defines -- see DRIVER below. Keeping the
# shape in one place matters because it is a THIRD way this test went quietly blind: the item
# grew from (url, depth) to (url, size, mtime), the stubs kept pushing the old pair, every
# worker died unpacking it, and the resulting wedge looked like the product's fault.
# Signatures are checked by CONTRACT above; a data shape has to be written down somewhere.
SCENARIOS = {
    # Positive control. A test that only ever reports "no hang" is worthless until it has been
    # shown to report one. Workers that never return block the producer's bounded put while
    # alive() keeps answering True, so this must time out.
    "CONTROL (must hang): worker blocks forever": """
        import time as _t
        def stuck(q, root, base_url, stats, log, **kw):
            _t.sleep(10000)
        m.worker = stuck
        def push(q, base_url, stats, log, case_sensitive=False, alive=None, **kw):
            print('STUB-RAN', flush=True)
            for i in range(500):
                m.put_item(q, ITEM, alive, log)
        m.producer = push
    """,
    "producer raises OSError": """
        def boom(*a, **kw):
            print('STUB-RAN', flush=True)
            raise OSError(28, 'No space left on device')
        m.producer = boom
    """,
    "producer raises KeyboardInterrupt": """
        def boom(*a, **kw):
            print('STUB-RAN', flush=True)
            raise KeyboardInterrupt()
        m.producer = boom
    """,
    # The interesting one: the queue is full when the producer dies, so the sentinels that
    # normally end the workers cannot be pushed. This is the shape the original hang had.
    "producer raises after filling the queue": """
        def boom(q, base_url, stats, log, case_sensitive=False, alive=None, **kw):
            print('STUB-RAN', flush=True)
            for i in range(500):                 # more than the queue bound
                q.put(ITEM(i))
            raise RuntimeError('died with a full queue')
        m.producer = boom
    """,
    # put_item(), not a bare q.put(): the real producer uses it precisely so that a full queue
    # with no living worker behind it ends the push instead of blocking on it forever.
    "all workers dead, producer still pushing": """
        def dead_worker(q, root, base_url, stats, log, **kw):
            raise RuntimeError('worker died immediately')
        m.worker = dead_worker
        def push(q, base_url, stats, log, case_sensitive=False, alive=None, **kw):
            print('STUB-RAN', flush=True)
            for i in range(500):
                m.put_item(q, ITEM(i), alive, log)
        m.producer = push
    """,
    # Regression for the defect this test turned up on 2026-08-29, while being repaired. The
    # worker's unpack sat OUTSIDE its own "a worker must never die" guard, so a single
    # malformed item took the thread with it -- and enough of them took every thread, after
    # which the producer blocked on a queue nobody would ever drain again. Real workers here:
    # the point is that they survive rubbish and the run still ends.
    "malformed queue items (workers must survive them)": """
        def push(q, base_url, stats, log, case_sensitive=False, alive=None, **kw):
            print('STUB-RAN', flush=True)
            for i in range(300):
                m.put_item(q, ('http://127.0.0.1:9/%d' % i,), alive, log)   # one field, not three
        m.producer = push
    """,
}

DRIVER = """
import importlib.util, os, sys, time, types
spec = importlib.util.spec_from_file_location('mirror', r'{mirror}')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# No network, and not merely "no network worth mentioning". These scenarios are about queue
# and thread mechanics, but with a real download() the outcome depended on how the host
# answers port 9 -- and on Windows that is not a refusal. The connect SUCCEEDS into a black
# hole, so workers stalled in urlopen, the producer blocked behind them on the bounded queue,
# and a test about sentinel delivery was quietly measuring TCP behaviour instead. It reported
# a hang in mirror.py that was not there.  [2026-08-29]
#
# The small delay is deliberate: it is what keeps the queue full while the producer pushes,
# which is the precondition the "full queue" scenario is named after.
def _download(url, path, stats, log, mtime=None):
    time.sleep(float(os.environ.get('WEDGE_DELAY', '0.05')))
    return 'fail'
m.download = _download

m.ATTEMPTS = 1                  # measure wedging, not retry backoff
m.ROOT = r'{root}'              # normally set by main(); this bypasses main()
m.LOGDIR = r'{root}' + '\\\\logs'

# One queue item in the shape the worker unpacks -- the single place that knows it.
def ITEM(i):
    return ('http://127.0.0.1:9/%d' % i, 1, None)

{patch}

# Every attribute mirror() reads. Missing one raises AttributeError *inside* mirror, which
# terminates the run and would read as a pass -- see the module docstring.
args = types.SimpleNamespace(workers=8, queue=128, interval=3600, fresh=True,
                             case_sensitive=False, archive=None, seed=None,
                             no_index=True, hash_workers=2)
try:
    m.mirror('wedgetest', 'http://127.0.0.1:9/', args)
except BaseException as exc:
    print('raised: %s: %s' % (type(exc).__name__, exc))
print('REACHED-END')
"""

CONTRACT_CHECK = """
import importlib.util, inspect, json, sys
spec = importlib.util.spec_from_file_location('mirror', r'{mirror}')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
bad = []
for name, expect in json.loads(r'''{contract}''').items():
    fn = getattr(m, name, None)
    if fn is None:
        bad.append('%s is gone' % name); continue
    got = list(inspect.signature(fn).parameters)
    if got[:len(expect)] != expect:
        bad.append('%s(%s...) -- expected (%s...)' % (name, ', '.join(got[:len(expect)]),
                                                      ', '.join(expect)))
print('CONTRACT-FAIL: ' + '; '.join(bad) if bad else 'CONTRACT-OK')
"""

LIMIT = 45


def run(code, limit):
    """-> (stdout, elapsed, returncode) or (partial stdout, elapsed, None) on timeout."""
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           timeout=limit)
        return p.stdout + p.stderr, time.time() - t0, p.returncode
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or b""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return out, time.time() - t0, None


def main():
    import json
    # An argument parser for a test that takes no arguments, so that `--help` answers instead of
    # running. The repository's Python CI smoke-tests every script with `--help`; without this the
    # suite would execute on every push, and its positive control deliberately hangs for 45 s.
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], epilog=(
        "Takes no options. Exit 0 = every scenario behaved as expected, including the control "
        "that must hang. Needs no network and no mirror."))
    ap.add_argument("--limit", type=int, default=LIMIT, metavar="S",
                    help="seconds before a scenario counts as hung (default %d)" % LIMIT)
    args = ap.parse_args()
    globals()["LIMIT"] = args.limit

    if not os.path.isfile(MIRROR):
        sys.exit("mirror.py not found next to this test: %s" % MIRROR)

    print("mirror.py: %s\n" % MIRROR)

    out, _, _ = run(CONTRACT_CHECK.format(mirror=MIRROR, contract=json.dumps(CONTRACT)), 60)
    line = next((ln for ln in out.splitlines() if ln.startswith("CONTRACT-")), "CONTRACT-FAIL: no output")
    print("  %s" % line)
    if not line.startswith("CONTRACT-OK"):
        print("\n  The stubs no longer match the code they replace. Fix them before believing\n"
              "  anything below -- a stub with the wrong signature dies on call, and a producer\n"
              "  that dies instantly terminates, which is exactly what this test looks for.")
        return 1
    print()

    root = tempfile.mkdtemp(prefix="wedge-")
    bad = 0
    try:
        for label, patch in SCENARIOS.items():
            control = label.startswith("CONTROL")
            code = DRIVER.format(mirror=MIRROR, root=root, patch=textwrap.dedent(patch).strip())
            out, elapsed, rc = run(code, LIMIT)
            ran = "STUB-RAN" in out

            if rc is None:                                   # timed out == hung
                ok = control
                note = "expected -- the test can see a hang" if ok else "FAIL"
                print("  %-46s HANGS (>%ds)  %s" % (label, LIMIT, note))
            elif control:
                ok = False
                print("  %-46s finished %5.1fs  FAIL: should have hung" % (label, elapsed))
            elif not ran:
                ok = False
                print("  %-46s finished %5.1fs  FAIL: the stub never ran" % (label, elapsed))
            else:
                ok = True
                print("  %-46s finished %5.1fs rc=%s  ok" % (label, elapsed, rc))
            bad += 0 if ok else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    print("  %s" % ("all as expected" if not bad else "%d deviations" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
