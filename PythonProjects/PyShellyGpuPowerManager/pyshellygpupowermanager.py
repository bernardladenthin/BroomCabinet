#!/usr/bin/env python3
"""Dynamically throttle a local NVIDIA GPU's power limit to keep a minimum
power reserve on a circuit monitored by a Shelly smart-plug/EM device.

Polls the Shelly device's real-time power-meter reading over the local
network and adjusts the GPU's power limit (via nvidia-smi) so the circuit
never gets overdrawn, while always keeping --minimum-free-power headroom.

Requirements: NVIDIA GPU with nvidia-smi on PATH, a Shelly device with an EM
power meter reachable over the local network. No external Python packages -
uses urllib from the standard library instead of the third-party `requests`.

Defaults to computing and printing the new power limit only; pass --execute
to actually apply it via nvidia-smi.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime


def calculate_power_limit(total_act_power, current_power_limit, minimum, maximum, step_size, minimum_free_power):
    """Calculate the new GPU power limit, reserving minimum_free_power on the circuit.

    Parameters:
    - total_act_power (float): Current total active power from Shelly (W)
    - current_power_limit (int): Current GPU power limit (W)
    - minimum (int): Minimum GPU power limit (W)
    - maximum (int): Maximum GPU power limit (W)
    - step_size (int): Power step granularity (W)
    - minimum_free_power (int): Power to always reserve on the circuit (W)

    Returns:
    - int: Calculated GPU power limit (W)
    """
    power_useable = -total_act_power + current_power_limit
    adjusted_power_useable = power_useable - minimum_free_power

    if adjusted_power_useable < minimum:
        return minimum
    if adjusted_power_useable > maximum:
        return maximum

    return int((adjusted_power_useable // step_size) * step_size)


def get_current_power_limit(device_id):
    """Retrieve the current power limit (W) of the given NVIDIA GPU device, or None on error."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-i", device_id, "--query-gpu=power.limit", "--format=csv,noheader"],
            capture_output=True, text=True, check=True,
        )
        return int(float(result.stdout.strip().split()[0]))
    except Exception as e:
        print(f"Error fetching current power limit: {e}")
        return None


def get_device_status_local(shelly_ip, timeout):
    """Retrieve the current total active power (W) from a local Shelly device, or None on error."""
    url = f"http://{shelly_ip}/rpc/Shelly.GetStatus"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read())
            return data.get("em:0", {}).get("total_act_power", None)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"Error fetching device status: {e}")
        return None


def check_device_status(args):
    """Check device status and apply a new GPU power limit if needed (preview only unless --execute)."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{current_time}] Checking power status...")

    current_power_limit = get_current_power_limit(args.device_id)
    if current_power_limit is None:
        print("Unable to retrieve current GPU power limit.")
        return

    print(f"Current GPU Power Limit: {current_power_limit} W")

    total_act_power = get_device_status_local(args.shelly_ip, args.http_timeout)
    if total_act_power is None:
        print("Power data not available.")
        return

    print(f"Total Active Power: {total_act_power:.2f} W")

    new_power_limit = calculate_power_limit(
        total_act_power, current_power_limit,
        args.minimum, args.maximum, args.step_size, args.minimum_free_power,
    )

    print(f"Calculated New Power Limit: {new_power_limit} W")

    if new_power_limit == current_power_limit:
        print("No change required.")
    elif not args.execute:
        print(f"[dry-run] would apply new power limit: {new_power_limit} W")
    else:
        print(f"Applying new power limit: {new_power_limit} W")
        try:
            subprocess.run(["nvidia-smi", "-i", args.device_id, "-pl", str(new_power_limit)], check=True)
        except FileNotFoundError:
            print("ERROR: 'nvidia-smi' not found on PATH - is it installed?")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: nvidia-smi exited with status {e.returncode}")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shelly-ip", required=True, help="IP address of the Shelly device on the local network.")
    parser.add_argument("--device-id", default="1", help="NVIDIA GPU device ID (default: 1).")
    parser.add_argument("--minimum", type=int, default=200, help="Minimum GPU power limit, W (default: 200).")
    parser.add_argument("--maximum", type=int, default=370, help="Maximum GPU power limit, W (default: 370).")
    parser.add_argument("--step-size", type=int, default=10, help="Power adjustment granularity, W (default: 10).")
    parser.add_argument("--minimum-free-power", type=int, default=30, help="Power to always reserve on the circuit, W (default: 30).")
    parser.add_argument("--sleep-time", type=float, default=2, help="Seconds between checks when looping (default: 2).")
    parser.add_argument("--http-timeout", type=float, default=5, help="Shelly HTTP request timeout, seconds (default: 5).")
    parser.add_argument("--once", action="store_true", help="Check (and maybe adjust) once, then exit, instead of looping forever.")
    parser.add_argument("--execute", action="store_true", help="Actually apply the new power limit via nvidia-smi. Without this flag: compute and print it only (the default).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    try:
        if args.once:
            check_device_status(args)
        else:
            while True:
                check_device_status(args)
                time.sleep(args.sleep_time)
    except KeyboardInterrupt:
        print("\nStopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
