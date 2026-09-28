#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Prove the guards on a real directory, with a real junction, before trusting them with --apply.

A GUARD THAT HAS NEVER BEEN TRIED IS A COMMENT. So this builds a throwaway tree in the system
temp directory, puts a genuine junction in it with `mklink /J` (a symlink where that is the
native thing), and asks sweep.check() about each case. Two things are asserted for every refusal:
that it said no, AND THAT THE FILE BEHIND THE LINK IS STILL THERE afterwards -- a guard that
returns the right answer while something else has already deleted the file is not a guard.

`is_reparse_point` once answered True for anything it could not stat, so 634 files that were
simply gone were reported as sitting behind a junction. The decision was safe and the reason was
false, and the reason is what a person reads. There is a case for that here.

    python sweep_test.py
    python sweep_test.py --keep      # leave the tree behind to look at
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep  # noqa: E402


def make_link(link, target):
    """-> True when a real junction or symlink now exists at `link`."""
    if os.name == "nt":
        # Captured as BYTES on purpose. cmd answers in the console codepage, and decoding that
        # as cp1252 raised inside subprocess's reader thread -- a traceback printed above a run
        # in which every case had passed. Nothing here reads the message, only the exit code.
        result = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                                capture_output=True)
        return result.returncode == 0 and os.path.exists(link)
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except OSError:
        return False


def row_for(root, rel):
    """The inventory row a correct inventory.py would have written for this file."""
    info = os.lstat(sweep.long_path(os.path.join(root, rel.replace("/", os.sep))))
    return {"path": rel, "size": str(info.st_size), "mtime": "%.0f" % info.st_mtime,
            "sha256": sweep.sha256_of(os.path.join(root, rel.replace("/", os.sep))),
            "decision": "delete", "reason": "test", "group": "test"}


def build(base):
    """-> (root, outside) with the tree the cases below are asked about."""
    root = os.path.join(base, "work")
    outside = os.path.join(base, "outside")
    os.makedirs(os.path.join(root, "sub"))
    os.makedirs(outside)
    open(os.path.join(root, ".sweepable"), "w").close()
    for path, text in [
        (os.path.join(root, "plain.txt"), "plain\n"),
        (os.path.join(root, "sub", "nested.txt"), "nested\n"),
        (os.path.join(root, "changed.txt"), "before\n"),
        (os.path.join(root, "retouched.txt"), "same size\n"),
        (os.path.join(outside, "precious.txt"), "MUST SURVIVE\n"),
    ]:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return root, outside


def run_cases(root, outside, note):
    """-> (passed, failed). Each case is (label, expectation, rel, mutate)."""
    good = row_for(root, "plain.txt")
    nested = row_for(root, "sub/nested.txt")
    changed = row_for(root, "changed.txt")
    retouched = row_for(root, "retouched.txt")

    # The two mutations the size/mtime/hash guard exists for.
    with open(os.path.join(root, "changed.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("after, and longer\n")
    with open(os.path.join(root, "retouched.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("SAME SIZE\n")  # same length, different bytes -- only SHA-256 sees this
    os.utime(sweep.long_path(os.path.join(root, "retouched.txt")),
             (float(retouched["mtime"]), float(retouched["mtime"])))

    linked = make_link(os.path.join(root, "link"), outside)
    if not linked:
        note("  !! could not create a junction -- the two link cases DID NOT RUN")

    cases = [
        ("a plain file inside the root", True, good),
        ("a file in a subdirectory", True, nested),
        ("an absolute path", False, dict(good, path=os.path.join(root, "plain.txt"))),
        ("a drive-letter path", False, dict(good, path="C:/Windows/notepad.exe")),
        ("a path with ..", False, dict(good, path="../outside/precious.txt")),
        ("a path with .. in the middle", False, dict(good, path="sub/../../outside/precious.txt")),
        ("a leading separator", False, dict(good, path="/Windows/notepad.exe")),
        ("an empty path", False, dict(good, path="")),
        ("a file that is not there", False, dict(good, path="never-existed.txt")),
        ("size changed since the inventory", False, changed),
        ("content changed, size and mtime kept", False, retouched),
        ("a directory, not a file", False, dict(good, path="sub")),
    ]
    if linked:
        cases += [
            ("a file reached through a junction", False,
             dict(good, path="link/precious.txt")),
            ("the junction itself", False, dict(good, path="link")),
        ]

    passed = failed = 0
    for label, should_pass, row in cases:
        path, why = sweep.check(row["path"], row, root, True)
        ok = bool(path) == should_pass
        note("  %-4s %-44s %s" % ("ok" if ok else "FAIL", label,
                                  "allowed" if path else why))
        passed, failed = (passed + ok, failed + (not ok))

    # THE SECOND HALF OF THE LINK CASE, and the one that actually matters.
    survived = os.path.isfile(os.path.join(outside, "precious.txt"))
    note("  %-4s %-44s %s" % ("ok" if survived else "FAIL",
                              "the file outside is still there",
                              "untouched" if survived else "GONE -- STOP"))
    passed, failed = (passed + survived, failed + (not survived))

    # A missing file must be refused as missing, never as a link.
    _path, why = sweep.check("never-existed.txt", dict(good, path="never-existed.txt"), root, True)
    correct = why == "already gone"
    note("  %-4s %-44s %s" % ("ok" if correct else "FAIL",
                              "a missing file is called missing", why))
    return passed + correct, failed + (not correct)


def check_marker(base, note):
    """Guard 1: a root without the marker is refused, and the message says how to fix it."""
    passed = failed = 0
    bare = os.path.join(base, "unmarked")
    os.makedirs(bare, exist_ok=True)
    for label, path, should_work in [
        ("a root without the marker is refused", bare, False),
        ("a root with the marker is accepted", os.path.join(base, "work"), True),
        ("a root that does not exist is refused", os.path.join(base, "nowhere"), False),
        ("no root at all is refused", "", False),
    ]:
        root, problem = sweep.resolve_root(path)
        ok = bool(root) == should_work
        note("  %-4s %-44s %s" % ("ok" if ok else "FAIL", label,
                                  "accepted" if root else problem.splitlines()[0]))
        passed, failed = (passed + ok, failed + (not ok))
    return passed, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", action="store_true",
                        help="leave the throwaway tree behind instead of deleting it")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    base = tempfile.mkdtemp(prefix="pysweeper-test-")
    print("building a real tree in %s\n" % base)
    passed = failed = 0
    try:
        root, outside = build(base)
        print("the root marker:")
        got, lost = check_marker(base, print)
        passed, failed = passed + got, failed + lost
        print("\nthe path and content guards:")
        got, lost = run_cases(root, outside, print)
        passed, failed = passed + got, failed + lost
    finally:
        if args.keep:
            print("\n  --keep: %s left behind" % base)
        else:
            # A junction must be unlinked, not walked: rmtree through one deletes the target.
            link = os.path.join(base, "work", "link")
            if os.path.isdir(link):
                try:
                    os.rmdir(link)
                except OSError:
                    pass
            for _attempt in range(3):
                shutil.rmtree(base, ignore_errors=True)
                if not os.path.exists(base):
                    break
                time.sleep(0.2)

    print("\n%d passed, %d failed" % (passed, failed))
    if failed:
        print("DO NOT RUN sweep.py --apply until these pass.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
