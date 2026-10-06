# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Unpack a packed unit and hash every file against the collection's own SHA-256.

    python rar-verify-content.py --archive X:/tarTarget/misc2/misc/misc.rar --unit misc
    python rar-verify-content.py --archive ... --unit misc --scratch X:/verify --apply
    python rar-verify-content.py --archive ... --unit misc --apply --clean

THE THIRD AND STRONGEST CHECK, and the only one that believes nothing RAR says. There are already
two, and both are cheap:

    rar t                 decompresses every member and compares it with the CRC32 RAR recorded
                          while packing. Measured on misc: 7 minutes, 3.8 GB read. It proves the
                          archive decompresses to what RAR itself wrote -- and cannot notice that
                          RAR wrote the wrong bytes, because both sides of that comparison come
                          from the same read.
    the CRC32 cross-check compares the archive's stored CRC32s with the `.sfv` WE built days
                          earlier from the files on disk. Two independent readings, seconds to
                          run. This is what found 165 wrong files in the first misc.rar, over
                          which `rar t` had said "Alles OK" five times.

WHAT THIS ADDS. Both of the above compare numbers in headers. This one takes the BYTES back out of
the archive and hashes them, against a SHA-256 that was computed from the original file. It is the
same proof `tar-subtree.py` ends with, and it needs neither RAR's headers nor its own CRC pass to
be trusted.

AND IT ANSWERS THE -oi1 QUESTION DIRECTLY. A `-oi1` reference carries no CRC32 of its own -- RAR
writes zeros, measured 2026-10-06 -- so the header checks can only judge it through its target.
That reasoning is sound (the content is byte-identical by construction, and our manifests record
the same digest for both) but it is reasoning. Hashing the extracted file is not.

WHY IT IS NOT THE DEFAULT. It costs a full extraction: 144 GB of scratch space and one
decompression pass for misc, about 4 TB for the whole collection. The two header checks run after
every unit; this one is for a sample, or for a unit there is a reason to doubt.

IT NEVER TOUCHES THE COLLECTION AND IT DELETES NOTHING ANYWHERE. Q: is read for the `.sha256sum`
files and nothing else; every byte written goes under --scratch; and `--clean` PRINTS the command
to remove the extraction rather than running it. The owner's instruction on 2026-10-06 was to run
no delete operation on the packing drive, which is also the drive holding every packed volume.

`rar x` DOES NOT FINISH ON THIS HOST, WHICH IS WORTH KNOWING BEFORE SPENDING 15 MINUTES ON IT.
Measured 2026-10-06 against the real misc archive: exit 9 after 895 seconds, with FOUR warnings --
"Versuche den ungueltigen Datei- oder Verzeichnisnamen zu korrigieren" -- over paths holding `aux`
as a DIRECTORY COMPONENT (`.../swt/aux/spelling/new/abbreviations`, `.../swt/aux/spelling/build`,
`.../slackware-2.1/usr/lib/nn/aux`). RAR renamed them, so those four come out under names the
manifest does not use and read as missing AND surplus at once.

THE ARCHIVE IS CORRECT: RAR stored the real names, and 341 965 of 341 969 files extracted fine.

AND "WINDOWS CANNOT HOLD THE NAME" WOULD BE TOO STRONG, which is worth writing down because it
was the first explanation and the measurement refuses it. In one directory, here:

    relative  "aux"                 open: FileNotFoundError     mkdir: NotADirectoryError
    absolute  "<dir>/aux"           open: SUCCEEDS -- the file is really in the listing
    extended  "//?/<dir>/aux"       open: SUCCEEDS

`aux`, `prn` and `com1` are refused when the name is RELATIVE, because Windows resolves it to the
device; given a full path, `aux` is created as an ordinary file. So the host can hold these names
and RAR's own path handling is what gives up. An earlier test of this skipped itself for exactly
that reason -- it used absolute paths and found nothing blocked -- and the skip was right while
the conclusion drawn from the failure was not.

WHAT THAT LEAVES. The check is usable with those four paths as named exceptions, and a run on a
Linux filesystem would have none. Where neither suits, `rar p` streams a member to stdout and
writes nothing at all, so no filesystem naming rule applies -- measured: `rar p -inul <first
volume> <member>` returns the bytes and the sha256 matches, references included. Its cost is one
decompression from the start of that member's solid block per invocation, which makes it a tool
for a handful of files rather than for 341 969.
"""
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import time

from common import (BOOKKEEPING_FILES, MIRROR_ROOT, OWN_FILES, SUMS_FILE, exists, human,
                    long_path, relative_to, say)

GNU_RAR_NAMES = ("Rar.exe",)
RAR_DIRS = (os.path.join("C:" + os.sep, "Program Files", "WinRAR"),
            os.path.join("C:" + os.sep, "Program Files (x86)", "WinRAR"))


def find_rar():
    """-> the path to Rar.exe, or None. The GUI binary ignores a command line, so not WinRAR.exe."""
    for folder in RAR_DIRS:
        for name in GNU_RAR_NAMES:
            candidate = os.path.join(folder, name)
            if exists(candidate):
                return candidate
    return None


def expected_digests(unit, root, report=say):
    r"""-> {archive/path: sha256} from the `.sha256sum` files we wrote, for what the unit claims.

    THE SAME SHAPE AS b2-pack's crc32_expected AND FOR THE SAME REASON: the digests were computed
    days earlier, from the files on disk, by a different pass than the one that packed them. A
    comparison between two readings of one file is worth something; a comparison of a reading with
    itself is not.
    """
    want = {}
    for archive in unit.archives():
        path = os.path.join(root, archive, SUMS_FILE)
        if not exists(path):
            report("  no %s in %s" % (SUMS_FILE, archive))
            continue
        with io.open(long_path(path), encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.rstrip("\n")
                if not line.strip() or line.startswith(";"):
                    continue
                digest, rest = line.split(" ", 1)
                rel = rest.lstrip("*").replace("\\", "/")
                if unit.claims(archive, rel):
                    want["%s/%s" % (archive, rel)] = digest
    return want


def sha256_of(path, chunk=1 << 20):
    """-> the digest of a file on disk, read in chunks so a 20 GB member does not need 20 GB."""
    digest = hashlib.sha256()
    with io.open(long_path(path), "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def extract(rar, archive, into, report=say):
    r"""Unpack the whole set into `into`. -> True on success.

    `x` AND NOT `e`, so the stored paths are recreated: the comparison is by path, and a flattened
    extraction would collide `README` with `README` and verify neither.

    NO -mdx. The dictionary is 4g since 2026-10-06, which `rar t` and `rar x` accept without it --
    measured, where -md6g refused with exit 3. If a future unit goes above 4 GB this is where the
    refusal will appear, and it should: the switch exists to make that visible, not to paper over.
    """
    if not os.path.isdir(into):
        os.makedirs(into)
    started = time.time()
    done = subprocess.run([rar, "x", "-o+", "-idq", archive, into + os.sep],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = done.stdout.decode("utf-8", "replace")
    report("     rar x exited %d after %.0fs" % (done.returncode, time.time() - started))
    if done.returncode != 0:
        for line in [one for one in text.splitlines() if one.strip()][:8]:
            report("       %s" % line.strip()[:110])
        return False
    return True


def compare(root_dir, want, report=say):
    r"""-> (checked, [(path, why)], [our own records]) hashing everything under `root_dir`.

    THE WALK IS THE AUTHORITY FOR WHAT IS THERE and `want` for what should be, so the two
    directions are reported separately: a file present with the wrong bytes is a different fault
    from one that never arrived, and an extra file is a third. An earlier check in this project
    reported a count match and missed 4542 absent files because it only looked one way.

    PATHS ARE COMPARED CASE-SENSITIVELY. The whole reason this collection was rebuilt over two
    days is that `rar a` silently keeps one of two paths differing only in case; a verification
    that folded case would be blind to exactly the failure it exists to catch.
    """
    seen = {}
    for dirpath, _dirs, files in os.walk(root_dir):
        for name in files:
            full = os.path.join(dirpath, name)
            # common.relative_to AND NOT os.path.relpath, WHICH THIS PROJECT'S OWN TEST REFUSES:
            # relpath normalises the result and strips a trailing dot, and 33 files in this
            # collection end in one -- `TALK.` among them. Each would have come out under a name
            # the manifest does not use, and been reported as missing AND surplus at once. The
            # first draft of this tool had exactly that bug.
            rel = relative_to(root_dir, full)
            if rel is None:
                continue
            seen[rel] = full

    bad = []
    checked = 0
    started = time.time()
    seen_bytes = 0
    for rel in sorted(want):
        if rel not in seen:
            bad.append((rel, "not extracted"))
            continue
        got = sha256_of(seen[rel])
        checked += 1
        try:
            seen_bytes += os.path.getsize(long_path(seen[rel]))
        except OSError:
            pass
        if got != want[rel]:
            bad.append((rel, "sha256 differs"))
        if checked % 20000 == 0:
            rate = seen_bytes / max(1e-6, time.time() - started)
            report("         %d files, %s, %.0f MB/s" % (checked, human(seen_bytes), rate / 1e6))

    # OUR OWN BOOKKEEPING IS EXPECTED IN THE ARCHIVE AND IS IN NO .sha256sum, because a manifest
    # does not list itself. b2-pack's CRC32 check counts those separately and calls them "ours";
    # this one reported them as problems, so the end-to-end run in the scratchpad came back with
    # one fault for a four-file archive -- and on misc it would have been 367, enough to make
    # every real run read as a failure and the check as noise.
    #
    # BOTH SETS, because the two exist for different reasons: OWN_FILES is what a tree skips at
    # its top (the index, the four manifests), BOOKKEEPING_FILES the wider set of records that are
    # walked and therefore indexed. A file packed with a unit can be either.
    ours = []
    for rel in sorted(seen):
        if rel in want:
            continue
        base = rel.rsplit("/", 1)[-1]
        if base in OWN_FILES or base in BOOKKEEPING_FILES:
            ours.append(rel)
            continue
        bad.append((rel, "in the archive, in no .sha256sum"))
    return checked, bad, ours


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", required=True, help="the unit's first volume, or its base name")
    ap.add_argument("--unit", required=True, help="which unit of b2-pack.py this archive holds")
    ap.add_argument("--root", default=MIRROR_ROOT, help="the collection, read-only")
    ap.add_argument("--scratch", default=os.path.join("X:" + os.sep, "verify"),
                    help="where the archive is unpacked. Everything written goes here")
    ap.add_argument("--apply", action="store_true",
                    help="actually extract and hash. Without it only the plan is printed")
    ap.add_argument("--clean", action="store_true",
                    help="print the command that would remove the extraction. THIS TOOL DELETES "
                         "NOTHING: the owner's instruction on 2026-10-06 was to run no delete "
                         "operation on the packing drive at all")
    args = ap.parse_args(argv)

    rar = find_rar()
    if not rar:
        say("no Rar.exe in %s" % " or ".join(RAR_DIRS))
        return 2
    packer = load_packer()
    units = dict((u.name, u) for u in packer.UNITS)
    if args.unit not in units:
        say("unknown unit %r; known: %s" % (args.unit, ", ".join(sorted(units))))
        return 2
    unit = units[args.unit]

    first = packer.first_volume(args.archive) or args.archive
    if not exists(first):
        say("no archive at %s" % first)
        return 2

    want = expected_digests(unit, args.root)
    say("  %-12s %7d file(s) with a sha256 in our own manifests" % (args.unit, len(want)))
    say("     archive %s" % first)
    where = os.path.join(args.scratch, args.unit)
    say("     unpack  %s" % where)

    # SPACE IS CHECKED BEFORE THE EXTRACTION AND NOT DISCOVERED DURING IT. A run that fills the
    # drive at 90 % leaves a partial tree that looks like thousands of missing files, and the
    # report would be about the disk rather than the archive.
    try:
        free = shutil.disk_usage(args.scratch if os.path.isdir(args.scratch)
                                 else os.path.dirname(args.scratch) or ".").free
        say("     %s free where it unpacks -- the unit must fit UNPACKED, which is more than the"
            " archive" % human(free))
    except OSError:
        say("     cannot tell how much room is free where it unpacks")

    if not args.apply:
        say("")
        say("NOTHING WAS EXTRACTED. Pass --apply. It needs room for the whole unit unpacked.")
        return 0

    if os.path.isdir(where) and os.listdir(where):
        say("     %s is not empty -- refusing to mix two extractions" % where)
        return 2

    say("     extracting...")
    if not extract(rar, first, where):
        return 1
    say("     hashing every file against %s..." % SUMS_FILE)
    checked, bad, ours = compare(where, want)
    say("     %d of %d file(s) hashed, %d of our own record(s), %d problem(s)"
        % (checked, len(want), len(ours), len(bad)))
    kinds = {}
    for _rel, why in bad:
        kinds[why] = kinds.get(why, 0) + 1
    for why in sorted(kinds):
        say("         %-34s %d" % (why, kinds[why]))
    for rel, why in bad[:8]:
        say("           %-28s %s" % (why, rel))

    if bad:
        say("")
        say("THE CONTENT CHECK FAILED. The extraction is left at %s to be looked at." % where)
        return 1

    say("")
    say("PROVED: %d file(s) came out of the archive with the sha256 our manifests recorded."
        % checked)
    # THIS TOOL DELETES NOTHING, EVER, AND --clean ONLY PRINTS. The owner's instruction on
    # 2026-10-06 was explicit -- no delete operation on the packing drive -- and an extraction of
    # 136 GB is exactly the thing a tool should not remove on its own judgement. It is also the
    # drive that holds every packed volume, so a wrong path here costs the archive itself.
    size = sum(os.path.getsize(os.path.join(d, f))
               for d, _s, fs in os.walk(where) for f in fs)
    say("The extraction is at %s (%s) and THIS TOOL DOES NOT REMOVE IT." % (where, human(size)))
    if args.clean:
        say("To remove it yourself:  rmdir /s /q %s" % where)
    return 0


def load_packer():
    """-> b2-pack.py as a module, for its UNITS and first_volume().

    THROUGH common.load_peer AND NOT A COPY. The unit definitions decide which files this check
    expects; a second list of them here would agree on the day it was written and drift silently
    afterwards, and what it would drift about is what counts as missing.
    """
    import common
    return common.load_peer("b2-pack.py", "_b2pack", os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    sys.exit(main())
