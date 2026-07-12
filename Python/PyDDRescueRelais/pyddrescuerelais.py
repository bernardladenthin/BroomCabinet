#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Run ddrescue against a drive that hangs almost immediately, power-cycling
it through a USB relay between short attempts.

Each cycle: start ddrescue, let it run for --rescue-run-seconds (short on
purpose - this is for drives that need a power kick almost every attempt,
not a normal full-length rescue run), interrupt it, power the relay off then
back on, then start the next cycle. ddrescue resumes from --logfile each
time, so interrupting it repeatedly is safe - it never loses prior progress.

--source/--dest/--logfile have NO defaults on purpose: this drives ddrescue
directly against raw block devices, and a wrong device here can irreversibly
destroy data. You must specify them explicitly every time.

Defaults to a dry-run preview and asks nothing else; pass --execute to
actually touch the relay and run ddrescue (which then also asks for an
interactive 'yes' confirmation, skippable with --yes).
"""

import argparse
import signal
import subprocess
import sys
import time

# Relay protocol bytes for this specific USB relay model - not user-configurable,
# these are fixed hardware constants, equivalent to the original relaisOn.sh /
# relaisOff.sh: `echo -e '\xA0\x01\x01\xA2' > /dev/ttyUSB0` and `...\x00\xA1...`.
_RELAY_ON_BYTES = bytes([0xA0, 0x01, 0x01, 0xA2])
_RELAY_OFF_BYTES = bytes([0xA0, 0x01, 0x00, 0xA1])


def set_relay(port, on, dry_run):
    data = _RELAY_ON_BYTES if on else _RELAY_OFF_BYTES
    state = "ON" if on else "OFF"
    if dry_run:
        print(f"[dry-run] would write {data!r} to {port} (relay {state})")
        return
    print(f"Relay {state}")
    try:
        with open(port, "wb") as f:
            f.write(data)
    except OSError as e:
        raise SystemExit(f"ERROR: could not write to relay port {port}: {e}")


def build_ddrescue_cmd(args):
    cmd = ["ddrescue", "-c", str(args.max_retries), "-n", "--force", "-d", args.source, args.dest, args.logfile]
    cmd.extend(args.extra_ddrescue_args)
    return cmd


def run_cycle(args, cycle_num):
    print(f"\n--- cycle {cycle_num} ---")

    if not args.execute:
        print(f"[dry-run] would run: {' '.join(build_ddrescue_cmd(args))}")
        print(f"[dry-run] would let it run {args.rescue_run_seconds}s, then send SIGINT")
        print(f"[dry-run] would wait {args.post_interrupt_seconds}s")
        set_relay(args.relay_port, on=False, dry_run=True)
        print(f"[dry-run] would wait {args.relay_off_seconds}s")
        set_relay(args.relay_port, on=True, dry_run=True)
        print(f"[dry-run] would wait {args.relay_on_seconds}s before the next cycle")
        return

    print(f"Starting ddrescue: {' '.join(build_ddrescue_cmd(args))}")
    try:
        process = subprocess.Popen(build_ddrescue_cmd(args))
    except FileNotFoundError:
        raise SystemExit("ERROR: 'ddrescue' not found on PATH - is it installed?")
    time.sleep(args.rescue_run_seconds)

    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=args.post_interrupt_seconds)
    except subprocess.TimeoutExpired:
        print(f"WARNING: ddrescue did not exit within {args.post_interrupt_seconds}s of SIGINT; continuing anyway.")

    set_relay(args.relay_port, on=False, dry_run=False)
    time.sleep(args.relay_off_seconds)

    set_relay(args.relay_port, on=True, dry_run=False)
    time.sleep(args.relay_on_seconds)


def confirm(args):
    if args.yes:
        return True
    print("WARNING: this drives ddrescue directly against raw block devices:")
    print(f"  source:  {args.source}")
    print(f"  dest:    {args.dest}")
    print(f"  logfile: {args.logfile}")
    print("Double-check these are correct BEFORE continuing - a wrong device can destroy data irreversibly.")
    answer = input("Type 'yes' to continue: ")
    return answer.strip().lower() == "yes"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Source block device to rescue from, e.g. /dev/sdc. No default.")
    parser.add_argument("--dest", required=True, help="Destination block device/image to rescue to. No default.")
    parser.add_argument("--logfile", required=True, help="ddrescue logfile/mapfile path (resumable progress state). No default.")
    parser.add_argument("--relay-port", default="/dev/ttyUSB0", help="Serial device for the USB relay (default: /dev/ttyUSB0).")
    parser.add_argument("-c", "--max-retries", type=int, default=1, help="ddrescue -c retry count (default: 1).")
    parser.add_argument("--rescue-run-seconds", type=float, default=2, help="How long each ddrescue attempt runs before being interrupted (default: 2).")
    parser.add_argument("--post-interrupt-seconds", type=float, default=3, help="Wait after interrupting ddrescue, before power-cycling the relay (default: 3).")
    parser.add_argument("--relay-off-seconds", type=float, default=1, help="How long to keep the relay off (default: 1).")
    parser.add_argument("--relay-on-seconds", type=float, default=3, help="Wait after turning the relay back on, before the next cycle (default: 3).")
    parser.add_argument("--passes", type=int, default=None, help="Stop after this many cycles (default: run forever, like the original).")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt (only relevant together with --execute).")
    parser.add_argument("--execute", action="store_true", help="Actually touch the relay and run ddrescue. Without this flag: dry-run preview only (the default), no prompt.")
    parser.add_argument("extra_ddrescue_args", nargs=argparse.REMAINDER, help="Extra args passed through to ddrescue verbatim (must come last).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.execute and not confirm(args):
        print("Aborted.")
        return 1

    cycle = 0
    try:
        while args.passes is None or cycle < args.passes:
            cycle += 1
            run_cycle(args, cycle)
    except KeyboardInterrupt:
        print("\nStopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
