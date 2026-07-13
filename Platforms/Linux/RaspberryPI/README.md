<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Raspberry Pi

Projects and notes for the Raspberry Pi.

| Item | Contents |
|------|----------|
| [`GPIOCounter/`](GPIOCounter/) | Count GPIO pulses and graph them daily. |
| [`Webcam/`](Webcam/) | Capture images from a USB webcam via `fswebcam` on a cron schedule. |

## Useful links

* **Connect to Wi-Fi from the command line** (`wpa_supplicant`, headless `/boot`
  setup, NetworkManager on newer Raspberry Pi OS) — official Raspberry Pi guide:
  [Setting up a wireless LAN via the command line](https://www.raspberrypi.com/documentation/computers/configuration.html).
  Remember to set `country=` or the radio stays rfkill-blocked.
