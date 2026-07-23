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

## Time-lapse camera capture (`motion` / MMAL)

When capturing a time-lapse with the [`motion`](https://motion-project.github.io/)
daemon and a Raspberry Pi camera (MMAL), fixing exposure and white balance keeps
consecutive frames consistent — otherwise auto-exposure makes the resulting video
flicker. Set the MMAL camera control parameters in `motion.conf`:

```conf
mmalcam_control_params -awb none -iso 100 --shutter 4500
```

* `-awb none` — disable auto white balance (locked colour temperature).
* `-iso 100` — fix the sensor sensitivity (low ISO = less noise).
* `--shutter 4500` — fix the exposure time in microseconds (4.5 ms).

The captured JPEG sequence can then be renumbered and encoded into a video with
[`Python/PyImageSequencer`](../../../Python/PyImageSequencer/).

## Useful links

* **Connect to Wi-Fi from the command line** (`wpa_supplicant`, headless `/boot`
  setup, NetworkManager on newer Raspberry Pi OS) — official Raspberry Pi guide:
  [Setting up a wireless LAN via the command line](https://www.raspberrypi.com/documentation/computers/configuration.html).
  Remember to set `country=` or the radio stays rfkill-blocked.
