#!/usr/bin/env python3
"""Trigger jcmd GC.run against every locally running JVM.

Replaces two hardcoded assumptions from the original script:
  - It used Windows' `wmic` to list javaw.exe PIDs; wmic is deprecated and
    removed from current Windows builds. `jcmd -l` lists every local JVM
    (pid + main class/jar) and ships with the JDK itself on every platform,
    so no OS-specific process listing is needed at all.
  - It shelled out to a hardcoded `C:\\Program Files\\Java\\jdk-9.0.1\\bin\\jcmd.exe`.
    The jcmd executable is now resolved via --jcmd-path or PATH.

Defaults to a dry-run preview; pass --execute to actually run GC.run.
"""

import argparse
import shutil
import subprocess
import sys


def discover_jvms(jcmd_path):
    """Return a list of (pid, description) tuples for every local JVM, via `jcmd -l`."""
    result = subprocess.run([jcmd_path, "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    jvms = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, description = line.partition(" ")
        if not pid_str.isdigit():
            continue
        jvms.append((int(pid_str), description))
    return jvms


def run_gc(jcmd_path, pid):
    subprocess.run([jcmd_path, str(pid), "GC.run"], check=False)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jcmd-path",
        default=shutil.which("jcmd") or "jcmd",
        help="Path to the jcmd executable (default: resolved from PATH).",
    )
    parser.add_argument(
        "--name-filter",
        default=None,
        help="Only target JVMs whose jcmd description contains this substring "
        "(e.g. 'javaw' to match only Windows GUI Java apps). Default: match every JVM.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run GC.run. Without this flag: list matching JVMs without acting (the default).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    jvms = discover_jvms(args.jcmd_path)
    if args.name_filter:
        jvms = [(pid, desc) for pid, desc in jvms if args.name_filter in desc]

    # jcmd -l also lists its own short-lived process; exclude our own invocation just in case.
    jvms = [(pid, desc) for pid, desc in jvms if "sun.tools.jcmd.JCmd" not in desc]

    if not jvms:
        print("No matching JVMs found.")
        return 0

    for pid, description in jvms:
        if args.execute:
            print(f"Running GC.run on pid {pid} ({description})")
            run_gc(args.jcmd_path, pid)
        else:
            print(f"[dry-run] would run GC.run on pid {pid} ({description})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
