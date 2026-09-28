#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Break each rule of common.py's contract on purpose, and check the suite notices.

WHY THIS EXISTS. TestTheContract in common_test.py asserts things about the whole library
surface: that nothing public lives outside __all__, that no exported table can be rewritten by a
client, that no library function ends the process, that a progress callback is always called
`report`. Those tests pass today. Passing is not the question -- a conformance test that has
never failed is a comment with a runtime cost, and a rule nothing can break is a rule nobody is
keeping.

So each rule is broken here, deliberately, one at a time, and the suite is expected to say which
one. Anything reported as NICHTS BEMERKT is a rule that is currently decoration.

    python contract-mutations.py --apply

WHAT IT TOUCHES. common.py and containment.py, in place, one mutation at a time, restoring both
after every step and again in a `finally`. If it is killed between the two, the copies are beside
them as `.mutating` and the originals are one `copy` away. Nothing else in the tree is read or
written, and no network or mirror is touched.

WHY --apply. Python CI runs `python3 <file> --help` over every script in this directory. Without
an argument parser this file would MUTATE THE LIBRARY INSIDE CI; with one, --help prints and exits
and the mutations need saying out loud.

EVERY MUTATION MUST LEAVE VALID PYTHON. One that does not says nothing about the test it is aimed
at: the import fails first and the suite never reaches the rule. That case is reported as
MUTATION KAPUTT rather than as a gap -- the first version of this script did not distinguish the
two and reported a perfectly good rule as missing, which is exactly the kind of false answer the
whole collection is built to avoid.

AND EVERY MUTATION GETS ITS OWN BYTECODE CACHE. Python decides a cached .pyc is still good from
the source's (mtime, size) -- mtime to WHOLE SECONDS. Writing a mutation, running it and copying
the original back all happen inside one second here, and `shutil.copy` stamps the restored file
with now; a mutation whose replacement is the same LENGTH as what it replaced therefore leaves a
file that looks to Python exactly like the one already compiled, and the next subprocess silently
measures the PREVIOUS mutation. Measured on 2026-09-23 outside this script, on a one-character
edit (1 -> 2): stale bytecode was served for a source that was correct on disk, and the failure
it produced named a test that had nothing to do with the edit. Today's seven mutations all change
the length enough to escape it, so no answer printed here was ever wrong -- that is luck, not a
property. Each subprocess now compiles into a private directory under PYCACHE, where there is
nothing old to find.
"""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "common.py")
CLIENT = os.path.join(HERE, "containment.py")
HOLES_VS_SOURCE = os.path.join(HERE, "holes-vs-source.py")
# A SECOND LIBRARY MODULE, since the split on 2026-09-23. The contract rules apply to every
# module, so at least one mutation has to land outside common -- otherwise "the rules hold" is
# only ever demonstrated for one file. This is the module that caught it: the `say=` mutation
# pointed at mediawiki_images, which moved, and the run reported PATTERN NOT UNIQUE (0 hits)
# rather than quietly passing. A harness that says when its own aim is stale is the only kind
# worth having.
MEDIAWIKI = os.path.join(HERE, "mediawiki.py")
SUITE = "common_test.py"
# Where the children's bytecode goes instead of the tree's __pycache__. Under the system temp
# directory, made when a run starts and removed when it ends -- nothing is left in the repo.
PYCACHE = None
Q = '"""'

# Written out rather than escaped, because this file is itself full of source patterns and a
# literal backslash-r in one of them is a thing to misread.
NEWLINE = chr(10)
CRLF = chr(13) + chr(10)

# A mutation whose `old` is this APPENDS `new` instead of replacing anything. Used where the
# thing being broken has no stable anchor -- a client's import line gains and loses names as
# the library grows, and a mutation pinned to one spelling of it goes stale silently.
APPEND = object()

# (what is being broken, which file, the exact text to replace, what to replace it with)
MUTATIONS = (
    ("a public name outside __all__", LIB,
     "def user_agent():",
     "def leaked_helper():\n    return 1\n\n\ndef user_agent():"),

    ("an exported table made writable again", LIB,
     "MAGIC = types.MappingProxyType({",
     "MAGIC = ({"),

    ("a progress callback called say= again", MEDIAWIKI,
     "def mediawiki_images(base, delay=0.0, report=None, **kw):",
     "def mediawiki_images(base, delay=0.0, say=None, **kw):"),

    ("a library function ending the process", LIB,
     "def host_of(url):",
     'def host_of(url):\n    if url == "impossible":\n        sys.exit(1)'),

    ("an export with no docstring", LIB,
     "def sha256_bytes(data):\n    " + Q + "SHA-256 of something already in memory." + Q + "\n",
     "def sha256_bytes(data):\n"),

    ("an exported set made mutable again", LIB,
     "OWN_FILES = frozenset({",
     "OWN_FILES = ({"),

    ("a client reaching past __all__", CLIENT,
     APPEND,
     "\n\nfrom common import _unreadable  # noqa: E402,F401  (mutation)\n"),

    # THE RULE THAT PROTECTS A CONSOLIDATION, and it was asserted but never demonstrated until
    # 2026-09-27 -- the day five hand-rolled copies of a title extractor, two of source_url() and
    # two of the external-tool probe were folded into the library. The whole value of that work is
    # that a copy cannot quietly come back, so the rule against it has to be shown to bite.
    #
    # A LOCAL DEFINITION OF AN IMPORTED NAME is the exact shape the drift took: each copy was
    # self-consistent, so nothing failed and nothing was reported -- ask-the-source.py simply
    # answered "unaskable" for every bitsavers path while two other tools answered a working URL
    # for the same input.
    ("a tool shadowing a name it imports from the library", HOLES_VS_SOURCE,
     APPEND,
     "\n\ndef source_url(archive, rel, register):  # mutation\n    return None\n"),
)

# EVERY LIBRARY MODULE GETS ONE, AND THE LIST IS NOT TYPED OUT HERE.
#
# Until 2026-09-24 the mutations above reached common.py and mediawiki.py and no other. Yet
# TestTheContract loops over all seven modules, so its rules were ASSERTED for dokuwiki, pdf,
# pmwiki, robots and wayback and DEMONSTRATED for two. A loop that has never been shown to bite
# in a module is, for that module, exactly the comment-with-a-runtime-cost this script exists to
# refuse -- and the whole argument of the file applies to itself.
#
# GENERATED RATHER THAN WRITTEN OUT, because the failure being guarded against is precisely a
# module nobody remembered. LIBRARIES is the same tuple the suite loops over, so an eighth module
# is covered the day it is created and not the day somebody notices. Five near-identical entries
# typed by hand would also have been five chances to mistype one.
#
# THE RULE CHOSEN NEEDS NO ANCHOR. It appends, so it cannot go stale when a function is renamed
# or moved -- which is not hypothetical: the `say=` mutation above was aimed at mediawiki_images,
# that function moved, and the run reported PATTERN NOT UNIQUE. That is the good failure, but an
# anchor nobody has to maintain is better still.
LIBRARIES = ("common", "dokuwiki", "mediawiki", "pdf", "pmwiki", "robots", "wayback")

MUTATIONS += tuple(
    ("a public name outside __all__ (%s)" % name, os.path.join(HERE, name + ".py"),
     APPEND,
     "\n\ndef leaked_helper_%s():  # mutation\n    return 1\n" % name)
    for name in LIBRARIES
    if name != "common"          # common's copy of this rule is broken by hand, above
)


def child(argv):
    """Run a subprocess that can only compile what is on disk RIGHT NOW.

    PYTHONPYCACHEPREFIX moves the whole bytecode cache into a directory of its own, so the child
    neither reads the tree's __pycache__ nor writes to it. A fresh directory per call is what
    makes every answer here about the mutation currently written, and not about whichever one
    happened to be compiled in the same second -- see the note in the module docstring.
    """
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = tempfile.mkdtemp(prefix="mut-", dir=PYCACHE)
    return subprocess.run(argv, cwd=HERE, env=env,
                          capture_output=True, text=True, errors="replace")


def failures():
    """-> the names of the tests that failed, for whatever common.py is on disk right now."""
    r = child([sys.executable, SUITE])
    return sorted({line.split(" ")[1] for line in (r.stderr + r.stdout).split("\n")
                   if line.startswith(("FAIL: ", "ERROR: "))})


def importable():
    """Does common.py still parse and import? A mutation that broke it proves nothing."""
    r = child([sys.executable, "-c", "import common"])
    return r.returncode == 0, (r.stderr or "").strip().split("\n")[-1]


def run():
    global PYCACHE
    PYCACHE = tempfile.mkdtemp(prefix="contract-mutations-")
    # DERIVED FROM THE MUTATIONS, not listed beside them. It was a hand-written dict of three
    # files, and the moment a mutation was added for a fourth module that module would have been
    # written to and NEVER RESTORED -- the one failure this script must not have, since it edits
    # the library in place. A second list of the same thing is a second list to forget.
    backups = {}
    for _label, target, _old, _new in MUTATIONS:
        backups.setdefault(target, target + ".mutating")
    # ONE AT A TIME, AND IT REFUSES RATHER THAN TRUSTS. This script edits the library in place,
    # so two of it at once is not a slow run but a corrupt one: on 2026-09-25 two gate runs
    # overlapped, one read `common.py` while the other had it mutated and reported the suite red,
    # and then the second removed the first's working copy and it died with FileNotFoundError.
    # Nothing was lost -- but only because the mutation happened to be restorable.
    #
    # A LEFTOVER IS AS SERIOUS AS A LIVE INSTANCE, which is why this does not try to tell them
    # apart. Either something is running now, or something died holding the original, and in both
    # cases the file on disk may not be the file somebody wrote. That is a person's decision, not
    # a flag to clear: `diff common.py common.py.mutating` says which it is in one line.
    busy = sorted(copy for copy in backups.values() if os.path.exists(copy))
    if busy:
        print("REFUSING TO RUN. A working copy already exists:")
        for copy in busy:
            print("    %s" % copy)
        print("\nEither another instance is running, or one died holding the original.")
        print("This script edits the library in place, so a second run would restore the wrong bytes.")
        print("Compare them -- `diff %s %s` -- and if the .mutating copy is the good one, put it"
              % (os.path.basename(busy[0])[:-len(".mutating")], os.path.basename(busy[0])))
        print("back by hand. Deleting it blind is how a mutation becomes permanent.")
        return 2

    for real, copy in backups.items():
        shutil.copy(real, copy)

    print("%-44s %s" % ("rule broken", "what the suite said"))
    print("-" * 100)
    gaps = 0
    try:
        before = failures()
        if before:
            sys.exit("the suite is ALREADY red (%s) -- fix that first, or this measures nothing."
                     % ", ".join(before[:3]))

        for label, target, old, new in MUTATIONS:
            # THE PATTERNS ARE WRITTEN WITH LF AND THE FILE MAY HOLD CRLF, so the newline is
            # normalised on both sides before matching and the file's own ending is restored on
            # the way out. Found on 2026-09-27: `an export with no docstring` reported
            # "PATTERN NOT UNIQUE (0 hits) -- the file moved on" while the function it names was
            # untouched. common.py is NOT TRACKED, so `core.autocrlf` never converts it, and an
            # edit written without newline="" had quietly turned the whole file into CRLF.
            #
            # A LATENT BUG, NOT A NEW ONE. Any fresh checkout on Windows with autocrlf=true hands
            # every tracked library file to this tool as CRLF, and all thirteen patterns would
            # have missed. It happened to work here only because these files were written by a
            # tool rather than checked out.
            src = io.open(backups[target], encoding="utf-8", newline="").read()
            ending = CRLF if CRLF in src else NEWLINE
            src = src.replace(CRLF, NEWLINE)
            if old is APPEND:
                io.open(target, "w", encoding="utf-8", newline="").write(
                    (src + new).replace(NEWLINE, ending))
            else:
                if src.count(old) != 1:
                    print("%-44s PATTERN NOT UNIQUE (%d hits) -- the file moved on"
                          % (label, src.count(old)))
                    gaps += 1
                    continue
                io.open(target, "w", encoding="utf-8", newline="").write(
                    src.replace(old, new, 1).replace(NEWLINE, ending))

            ok, why = importable()
            if not ok:
                print("%-44s MUTATION BROKEN (%s)" % (label, why[:46]))
                gaps += 1
            else:
                names = failures()
                if names:
                    print("%-44s %s" % (label, ", ".join(n[:50] for n in names[:2])))
                else:
                    print("%-44s NOTHING NOTICED  <-- this rule is decoration" % label)
                    gaps += 1

            for real, copy in backups.items():
                shutil.copy(copy, real)
    finally:
        for real, copy in backups.items():
            shutil.copy(copy, real)
            os.remove(copy)
        print()
        print("restored: %s" % ", ".join(sorted(os.path.basename(f) for f in backups)))

    # The last question -- is the tree really as it was -- is asked BEFORE the cache directory
    # goes, because asking it needs a subprocess too. Removing it in the `finally` above made
    # this line die with FileNotFoundError instead of answering.
    try:
        still = failures()
    finally:
        shutil.rmtree(PYCACHE, ignore_errors=True)
    if still:
        sys.exit("the suite is red AFTER restoring (%s) -- the tree is not as it was."
                 % ", ".join(still[:3]))
    print("%d mutation(s), %d unguarded" % (len(MUTATIONS), gaps))
    return 1 if gaps else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="actually mutate common.py and containment.py in place, one rule at a "
                         "time, restoring after each. Without this, nothing is touched.")
    args = ap.parse_args()
    if not args.apply:
        print(__doc__.strip())
        print("\nNothing was touched. Pass --apply to run the %d mutations." % len(MUTATIONS))
        return 0
    return run()


if __name__ == "__main__":
    sys.exit(main())
