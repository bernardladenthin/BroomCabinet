import requests
import json
import os
import time
import subprocess
from datetime import datetime

"""
GPU Power Limit Manager with Shelly Device (LOCAL VERSION)

This script dynamically adjusts the NVIDIA GPU power limit based on real-time power consumption data 
from a Shelly device accessible via the local network.

It ensures a minimum power reserve (e.g. 10W) always stays in the grid, and avoids overdraw.

Requirements:
- Python 3.x
- NVIDIA GPU with `nvidia-smi`
- Shelly device with EM power meter
"""

def calculate_power_limit(total_act_power, current_power_limit, minimum, maximum, step_size, minimum_free_power):
    """
    Calculates the new GPU power limit based on current usage and reserves a minimum power in the grid.

    Parameters:
    - total_act_power (float): Current total active power from Shelly (W)
    - current_power_limit (int): Current GPU power limit (W)
    - minimum (int): Minimum GPU power limit (W)
    - maximum (int): Maximum GPU power limit (W)
    - step_size (int): Power step granularity (W)
    - minimum_free_power (int): Power to always reserve in the grid (W)

    Returns:
    - int: Calculated GPU power limit (W)
    """
    power_useable = -total_act_power + current_power_limit
    adjusted_power_useable = power_useable - minimum_free_power

    if adjusted_power_useable < minimum:
        return minimum
    if adjusted_power_useable > maximum:
        return maximum

    return (adjusted_power_useable // step_size) * step_size

def get_current_power_limit(device_id):
    """
    Retrieves the current power limit of a given NVIDIA GPU device.

    Parameters:
    - device_id (str): NVIDIA GPU ID

    Returns:
    - int: Current GPU power limit (W), or None if an error occurs.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "-i", device_id, "--query-gpu=power.limit", "--format=csv,noheader"],
            capture_output=True, text=True
        )
        return int(float(result.stdout.strip().split()[0]))
    except Exception as e:
        print(f"Error fetching current power limit: {e}")
        return None

def get_device_status_local(shelly_ip):
    """
    Retrieves the current total active power from a local Shelly device.

    Parameters:
    - shelly_ip (str): IP address of the Shelly device

    Returns:
    - float: Total active power (W), or None if unavailable.
    """
    url = f"http://{shelly_ip}/rpc/Shelly.GetStatus"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("em:0", {}).get("total_act_power", None)
        else:
            print(f"Failed to retrieve device status. HTTP Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching device status: {e}")
        return None

def check_device_status(shelly_ip, device_id, minimum, maximum, step_size, minimum_free_power):
    """
    Checks device status and updates GPU power limit if needed.

    Parameters:
    - shelly_ip (str): IP of the Shelly device
    - device_id (str): NVIDIA GPU device ID
    - minimum (int): Min power limit
    - maximum (int): Max power limit
    - step_size (int): Adjustment step
    - minimum_free_power (int): Grid reserve (W)
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{current_time}] Checking power status...")

    current_power_limit = get_current_power_limit(device_id)
    if current_power_limit is None:
        print("Unable to retrieve current GPU power limit.")
        return

    print(f"Current GPU Power Limit: {current_power_limit} W")

    total_act_power = get_device_status_local(shelly_ip)
    if total_act_power is None:
        print("Power data not available.")
        return

    print(f"Total Active Power: {total_act_power:.2f} W")

    new_power_limit = calculate_power_limit(
        total_act_power, current_power_limit,
        minimum, maximum, step_size, minimum_free_power
    )

    print(f"Calculated New Power Limit: {new_power_limit} W")

    if new_power_limit != current_power_limit:
        print(f"Applying new power limit: {new_power_limit} W")
        subprocess.run(["nvidia-smi", "-i", device_id, "-pl", str(new_power_limit)])
    else:
        print("No change required.")

# --- Configuration ---
shelly_ip = "192.168.2.226"  # IP of your Shelly device
device_id = "1"              # NVIDIA GPU ID
minimum = 200                # Minimum GPU power limit
maximum = 370                # Maximum GPU power limit
step_size = 10               # Power adjustment granularity
minimum_free_power = 30      # Keep at least 30W unused in the grid
sleep_time = 2               # Seconds between checks

# --- Loop ---
while True:
    check_device_status(shelly_ip, device_id, minimum, maximum, step_size, minimum_free_power)
    time.sleep(sleep_time)
