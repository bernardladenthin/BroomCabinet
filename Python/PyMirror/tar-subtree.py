# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Pack one subtree into a tar on another drive and prove the tar holds all of it.

    python tar-subtree.py --name v3                     what WOULD happen
    python tar-subtree.py --name v3 --apply              create the tar, then check it
    python tar-subtree.py --name v3 --check-only         re-check a tar that already exists
    python tar-subtree.py --name v3 --name v4 --apply

WHY A TAR AT ALL. `rar a` is handed two paths that differ only in case, stores ONE of them, and
exits 0. Measured on misc.rar: 275 paths present only in the other spelling and 165 files whose
CRC32 therefore does not match what the .sfv says for that path -- with `rar t` reporting "Alles
OK" over the lot. tar keeps both members, so a subtree that goes into a RAR as ONE tar file
cannot lose a case twin. GNU tar 1.35 was measured doing exactly that; 7-Zip refuses the input
outright ("Duplicate filename on disk") for every output format, so it is not an option here.

IT NEVER WRITES TO THE MIRROR AND NEVER DELETES ANYTHING. tar reads; every byte produced lands
under --target-root. Removing the packed subtree afterwards is the owner's decision and his hand
-- this tool does not do it, does not offer to, and says so when it is done.

THE FOUR MANIFESTS TRAVEL INSIDE THE TAR. They sit in the subtree on the mirror, so packing the
subtree picks them up with no special case -- and a tar whose members can be re-verified years
later from a file inside itself is the whole point. PyFixity leaves them out of their own line
counts, so the member total is files + 4, which is checked rather than assumed.

WHAT PROVES THE TAR IS COMPLETE, in the order the checks run and in rising strength:

  1. member list        every path from the manifest present, at the right size, and nothing in
                        the tar that the manifest does not name. Case-SENSITIVE comparison --
                        folding case here is exactly the bug this tool exists to prevent, and it
                        would report a tar missing 4000 files as complete.
  2. tar -d             compares the archive against the live tree: content, not just names.
                        A single flipped bit at unchanged size was measured being caught.
  3. digests            every member streamed out of the tar and hashed, compared against the
                        .sha256sum that is itself inside the tar. This is the real proof: it
                        needs neither the mirror nor this tool to be repeatable.

Check 2 needs the mirror still present and check 3 does not, which is why 3 is the one that
matters after the subtree is gone.

`tar -d` EXITS 1 FOR "THERE ARE DIFFERENCES" AND THAT INCLUDES A CHANGED MTIME, so its output is
read rather than its status. Measured: unchanged tree -> exit 0 and no output; one bit flipped ->
exit 1 and "Contents differ"; truncated archive -> `tar -t` exits 2 with "Unexpected EOF". A
status-only test would call a tree with one re-dated file broken and a tar with a wrong byte fine.
"""
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import time

from common import MD5_FILE, MIRROR_ROOT, SFV_FILE, SHA1_FILE, SUMS_FILE, human, say

# THE SUBTREES THAT NEED THIS LIVE UNDER ONE ARCHIVE, and the drive is named in common.py alone.
# A second spelling of the collection's path is a second thing to change when it moves, and the
# library's own test refuses it.
SOURCE_ROOT = os.path.join(MIRROR_ROOT, "ibm-aix", "fixes")
TARGET_ROOT = os.path.join("X:" + os.sep, "tarTarget")
# The four, through the library's names rather than spelled out: a tool that writes ".sha256sum"
# by hand is one the next rename leaves behind.
MANIFESTS = (SUMS_FILE, SHA1_FILE, MD5_FILE, SFV_FILE)
BLOCK = 10240          # tar's own block size; a short final read means a truncated archive

# THE FULL PATH TO GNU TAR, AND NOT THE NAME. Windows resolves a bare `tar.exe` through System32
# BEFORE the PATH, so a subprocess gets `bsdtar 3.8.8` -- which has no `-d` at all and answers
# with its four-line usage text and exit 1. Measured: check 2 therefore ran not once, parsed that
# usage text for "Contents differ", found none, and reported the tar verified. A check that cannot
# fail is worse than no check, so the binary is named outright and its version is asserted below.
def find_gnu_tar():
    r"""-> a path to GNU tar, or None.

    NOT A BARE `tar`. Windows resolves `tar.exe` through System32 FIRST, and that is bsdtar, which
    has no `-d` -- so the comparison check would silently never run. Measured 2026-10-06: it
    reported success having compared nothing. The Git for Windows install is an MSYS GNU build and
    is named explicitly for that reason.

    ON POSIX `tar` IS GNU TAR and there is no System32 to get in the way, so the PATH is the right
    answer there. This was a hardcoded Windows path until 2026-10-10, which made all 51 tests in
    this file error out on a Linux runner with a FileNotFoundError naming `C:\Program Files`.

    `check_tar_binary()` still asserts "GNU tar" in `--version` whichever one is found, because
    the point was never where the binary lives but what it is.
    """
    candidates = [os.path.join("C:" + os.sep, "Program Files", "Git", "usr", "bin", "tar.exe"),
                  os.path.join(os.sep + "usr", "bin", "tar"),
                  os.path.join(os.sep + "bin", "tar")]
    for path in candidates:
        if os.path.isfile(path):
            return path
    found = shutil.which("gtar") or (shutil.which("tar") if os.name != "nt" else None)
    return found


GNU_TAR = find_gnu_tar()


def posix(path):
    r"""-> the path as GNU tar wants it: /x/tarTarget/v3/v3.tar

    GNU tar READS `X:\...` AS host:path AND TRIES TO RESOLVE A HOST CALLED "X". Measured, twice:
    `tar -cf C:\...\v9.tar` answers "Cannot connect to C: resolve failed" and exits 128, and
    `--force-local` fixes creation but then mangles the same path inside `-d` and exits 2. This
    binary is an MSYS build, so the drive-letter form it understands is the POSIX one -- with
    which creation, listing and `-d` all behave, and `-d` reports "Contents differ" for a single
    flipped bit at unchanged size.
    """
    path = os.path.abspath(path).replace(os.sep, "/")
    if len(path) > 1 and path[1] == ":":
        path = "/" + path[0].lower() + path[2:]
    return path


def manifest_rows(path):
    r"""-> {relative path: sha256} from a sha256sum(1) file.

    The paths inside are relative to the subtree and the tar stores them under `<name>/`, so the
    caller prefixes. Splitting on the FIRST space only: a path may contain spaces, a digest may
    not, and a plain split() would quietly drop everything after the first one in `IBM C Set.bff`.
    """
    out = {}
    with io.open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith(";"):
                continue
            digest, rest = line.split(" ", 1)
            out[rest.lstrip("*")] = digest
    return out


def tar_members(path):
    r"""-> {member path: size} for every regular file in the tar.

    THROUGH tarfile RATHER THAN PARSING `tar -tvf` TEXT. The listing's columns are localised --
    this machine's tar prints German month names -- and a size column that moves when a name is
    long is a parser waiting to be wrong about which file is short. tarfile reads the headers.
    """
    out = {}
    with tarfile.open(path, "r|") as archive:          # streaming: never holds the whole index
        for member in archive:
            if member.isfile():
                out[member.name] = member.size
    return out


def compare(expected, present, prefix):
    r"""-> (missing, extra, wrong size) between manifest and tar, CASE-SENSITIVELY.

    The dictionaries are keyed by exact bytes and compared with set operations, so `A.TBL` and
    `a.TBL` are two keys throughout. An earlier cross-check of a RAR normalised case "to be
    forgiving" and reported an archive missing 4542 files as complete.

    `expected` MAPS A RELATIVE PATH TO A SIZE, AND None MEANS "size not known here". The manifest
    carries digests and no sizes, so the sizes come from the live tree -- and once the tree is
    gone there are none to compare against, which is a missing comparison and not a failure. An
    earlier version of this function was handed the DIGEST dictionary by mistake and dutifully
    reported every single file as the wrong size, because a hex string is not a byte count.
    """
    want = dict((prefix + "/" + rel, size) for rel, size in expected.items())
    missing = sorted(set(want) - set(present))
    extra = sorted(set(present) - set(want))
    wrong = sorted(name for name in set(want) & set(present)
                   if want[name] is not None and want[name] != present[name])
    return missing, extra, wrong


def run(args, cwd=None):
    """-> (exit status, combined output). stderr folded in because tar reports on both."""
    done = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return done.returncode, done.stdout.decode("utf-8", "replace")


def check_tar_binary(tar=GNU_TAR, report=say):
    r"""-> True when this really is GNU tar and `-d` exists.

    ASSERTED, NOT ASSUMED, because the failure it guards against is silent: bsdtar prints a usage
    text and exits non-zero, and a caller that only looked for "Contents differ" in that text saw
    a clean comparison. The version line is read once and said out loud, so a run's own output
    records which binary produced its verdict.
    """
    if not os.path.exists(tar):
        report("  no GNU tar at %s" % tar)
        return False
    status, output = run([tar, "--version"])
    first = output.splitlines()[0] if output.splitlines() else ""
    if status != 0 or "GNU tar" not in first:
        report("  %s is not GNU tar: %s" % (tar, first[:60]))
        return False
    report("  %s" % first)
    return True


def check_digests(tar_path, want, prefix, report=say):
    r"""-> (checked, [(member, why)]) hashing every member as it streams past.

    ONE PASS, NO EXTRACTION. A `tar -xOf` per member would re-read the archive once per file --
    64146 passes over 92 GB. Streaming hashes each member where it lies, so the cost is one pass
    over the bytes. Nothing is written to disk, which also means this check can run against a tar
    on a drive with no room to extract into.
    """
    bad = []
    checked = 0
    started = time.time()
    seen_bytes = 0
    with tarfile.open(tar_path, "r|") as archive:
        for member in archive:
            if not member.isfile():
                continue
            if not member.name.startswith(prefix + "/"):
                continue
            rel = member.name[len(prefix) + 1:]
            if rel not in want:
                continue                               # named by compare(), not again here
            stream = archive.extractfile(member)
            digest = hashlib.sha256()
            while True:
                chunk = stream.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
            checked += 1
            seen_bytes += member.size
            if digest.hexdigest() != want[rel]:
                bad.append((member.name, "sha256 differs"))
            if checked % 10000 == 0:
                rate = seen_bytes / max(1e-6, time.time() - started)
                report("         %d members, %s, %.0f MB/s"
                       % (checked, human(seen_bytes), rate / 1e6))
    return checked, bad


def pack(name, source_root, target_root, apply_it, check_only, report=say):
    """-> 0 when the tar is proved complete, 1 when it is not, 2 on a setup problem."""
    source = os.path.join(source_root, name)
    target_dir = os.path.join(target_root, name)
    tar_path = os.path.join(target_dir, name + ".tar")

    if not os.path.isdir(source):
        report("  not a directory: %s" % source)
        return 2
    if not os.path.isdir(target_dir):
        report("  target missing: %s" % target_dir)
        return 2
    sums = os.path.join(source, SUMS_FILE)
    if not os.path.exists(sums):
        report("  no %s in %s -- run pyfixity there first" % (SUMS_FILE, source))
        return 2

    want = manifest_rows(sums)
    # Sizes for check 1 come from the TREE, because the manifest carries digests and no sizes.
    # None where the file cannot be sized: that is one comparison this run cannot make, and it
    # must not silently become "the size is wrong".
    sizes = {}
    want_bytes = 0
    for rel in want:
        try:
            sizes[rel] = os.path.getsize(os.path.join(source, rel))
            want_bytes += sizes[rel]
        except OSError:
            sizes[rel] = None
    report("  %-10s %7d files in the manifest, %s" % (name, len(want), human(want_bytes)))
    report("     source %s" % source)
    report("     tar    %s" % tar_path)

    exists = os.path.exists(tar_path)
    if check_only and not exists:
        report("     there is no tar to check")
        return 2
    if not apply_it and not check_only:
        report("     WOULD create the tar (%s there now)" % ("one is" if exists else "none is"))
        return 0
    if apply_it and exists:
        report("     A TAR IS ALREADY THERE -- refusing to overwrite it. Use --check-only, or "
               "move it aside by hand.")
        return 2

    if apply_it:
        report("     packing...")
        started = time.time()
        # -C the PARENT so members are stored as `<name>/...` and the tar unpacks into a folder
        # of its own rather than scattering into the current directory.
        status, output = run([GNU_TAR, "-cf", posix(tar_path), "-C", posix(source_root), name])
        took = time.time() - started
        if status != 0:
            report("     tar exited %d" % status)
            for line in output.splitlines()[:10]:
                report("       %s" % line)
            return 1
        size = os.path.getsize(tar_path)
        report("     %s in %.0fs (%.0f MB/s)" % (human(size), took, size / max(1e-6, took) / 1e6))
        if size % BLOCK:
            report("     NOTE: not a multiple of tar's %d-byte block" % BLOCK)

    report("     1/3 member list...")
    present = tar_members(tar_path)
    missing, extra, wrong = compare(sizes, present, name)
    report("         %d members in the tar, %d expected from the manifest"
           % (len(present), len(want)))
    if missing or extra or wrong:
        # The four manifests are in the tar and name only content, so they are expected extras.
        only_manifests = (not missing and not wrong
                          and all(os.path.basename(e) in MANIFESTS for e in extra))
        if only_manifests:
            report("         the %d extra members are the four manifests themselves -- they do "
                   "not list themselves, which is correct" % len(extra))
        else:
            report("         MISSING %d   UNEXPECTED %d   WRONG SIZE %d"
                   % (len(missing), len(extra), len(wrong)))
            for kind, rows in (("missing", missing), ("unexpected", extra), ("wrong size", wrong)):
                for row in rows[:5]:
                    report("           %-11s %s" % (kind, row))
            return 1
    else:
        report("         every expected path present at the right size")

    report("     2/3 tar -d against the live tree...")
    status, output = run([GNU_TAR, "-df", posix(tar_path), "-C", posix(source_root)])
    lines = [line for line in output.splitlines() if line.strip()]
    content = [line for line in lines if "Contents differ" in line or "Size differs" in line]
    dated = [line for line in lines if "Mod time differs" in line]
    # EVERY LINE IS ACCOUNTED FOR OR THE CHECK FAILS. The lines tar actually printed when this
    # was broken were its own usage text, and a classifier that counted only the two shapes it
    # knew reported "0 about content" over them and passed. Anything tar says that this tool does
    # not recognise is a reason to stop, not to ignore.
    unknown = [line for line in lines if line not in content and line not in dated]
    report("         tar exited %d, %d line(s): %d content, %d mtime only, %d unrecognised"
           % (status, len(lines), len(content), len(dated), len(unknown)))
    for line in content[:5] + unknown[:5]:
        report("           %s" % line)
    if content or unknown:
        return 1

    report("     3/3 sha256 of every member, out of the tar...")
    checked, bad = check_digests(tar_path, want, name, report)
    report("         %d of %d members hashed, %d wrong" % (checked, len(want), len(bad)))
    for member, why in bad[:5]:
        report("           %s: %s" % (member, why))
    if bad or checked != len(want):
        return 1

    report("     PROVED: %d members, every sha256 matching the manifest inside the tar."
           % checked)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", action="append", default=[], required=True,
                    help="subtree under the source root; repeatable")
    ap.add_argument("--source-root", default=SOURCE_ROOT, help="default %s" % SOURCE_ROOT)
    ap.add_argument("--target-root", default=TARGET_ROOT, help="default %s" % TARGET_ROOT)
    ap.add_argument("--apply", action="store_true",
                    help="create the tar. Without it, nothing is written")
    ap.add_argument("--check-only", action="store_true", help="check a tar that is already there")
    args = ap.parse_args(argv)

    if args.apply and args.check_only:
        say("--apply and --check-only are opposites")
        return 2
    if not check_tar_binary():
        return 2

    worst = 0
    for name in args.name:
        code = pack(name, args.source_root, args.target_root, args.apply, args.check_only)
        worst = max(worst, code)
        say("")
    if not args.apply and not args.check_only:
        say("NOTHING WAS WRITTEN. Pass --apply.")
    elif worst == 0:
        say("The subtree on the mirror is UNTOUCHED. Removing it is yours to do, not this tool's.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
