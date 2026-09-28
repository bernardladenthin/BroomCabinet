# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Does --trust-index skip exactly the files it should?

The part that matters is the round trip: a path in .sha256sum -> the URL the crawler builds for
it -> local_path() -> back to the same string. A mismatch of one character makes the feature a
no-op that reports success, which is this collection's most expensive defect class.
"""
import os
import sys
import tempfile
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mirror as M


class _Log:
    def __init__(self):
        self.lines = []

    def line(self, text, error=False):
        self.lines.append(text)


fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- format handling
with tempfile.TemporaryDirectory() as td:
    log = _Log()
    check("no .sha256sum -> empty set, and it says so",
          M.load_trusted_index(td, log) == frozenset()
          and any("TRUST-INDEX UNAVAILABLE" in ln for ln in log.lines))

    with open(os.path.join(td, M.SUMS_FILE), "w", encoding="utf-8") as fh:
        fh.write("a" * 64 + " *dir/file one.txt\n")
        fh.write("b" * 64 + " *other.bin\n")
        fh.write("\n")
    got = M.load_trusted_index(td, _Log())
    check("reads `<hash> *<path>`, one space and a star",
          got == {os.path.join(td, "dir", "file one.txt"), os.path.join(td, "other.bin")},
          repr(sorted(got)))

    # The two-space split that once reported "0 of 7 890 held" must not be what this does.
    with open(os.path.join(td, M.SUMS_FILE), "w", encoding="utf-8") as fh:
        fh.write("c" * 64 + " *name with  two spaces.txt\n")
    got = M.load_trusted_index(td, _Log())
    check("a filename containing two spaces survives",
          got == {os.path.join(td, "name with  two spaces.txt")}, repr(sorted(got)))

    log = _Log()
    with open(os.path.join(td, M.SUMS_FILE), "w", encoding="utf-8") as fh:
        fh.write("d" * 64 + " *good.txt\n")
        fh.write("this line has no star\n")
    check("one malformed line refuses the WHOLE index, loudly",
          M.load_trusted_index(td, log) == frozenset()
          and any("TRUST-INDEX REFUSED" in ln for ln in log.lines))

# ---------------------------------------------------------------- the real round trip
ROOT = "Q:/mirror/oldskool"
BASE = "http://ftp.oldskool.org/pub/"
if not os.path.exists(os.path.join(ROOT, M.SUMS_FILE)):
    print("  SKIP  round trip: %s not present on this machine" % ROOT)
else:
    root = os.path.normpath(ROOT)
    trusted = M.load_trusted_index(root, _Log())
    check("oldskool index loads", len(trusted) > 26000, "%d paths" % len(trusted))

    rel = [ln.split(" *", 1)[1]
           for ln in open(os.path.join(root, M.SUMS_FILE), encoding="utf-8",
                          errors="replace").read().splitlines() if " *" in ln]
    # Every 97th entry, so the sample spans the whole tree rather than one directory.
    sample = rel[::97]
    bad_member, bad_exist = [], []
    for r in sample:
        url = BASE + urllib.parse.quote(r)
        dest = M.local_path(root, BASE, url)
        if dest not in trusted:
            bad_member.append((r, dest))
        elif not os.path.exists(M.long_path(dest)):
            bad_exist.append(dest)
    check("index -> URL -> local_path() lands back in the index (%d sampled)" % len(sample),
          not bad_member, repr(bad_member[:3]))
    check("every sampled path is really on disk", not bad_exist, repr(bad_exist[:3]))

    # And the other direction: a file NOT in the index must not be trusted.
    outsider = M.local_path(root, BASE, BASE + "drivers/IBM/nothing-is-here.bin")
    check("a path absent from the index is not trusted", outsider not in trusted)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("all tests passed")
