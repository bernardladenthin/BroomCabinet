<!--
SPDX-FileCopyrightText: 2020 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyWebcamRecorder

Periodically screenshots a single element on a webcam page and saves each frame
as a PNG — a simple way to build a time-lapse from an embedded webcam stream.

It opens the page in Chrome via Selenium, locates one DOM element (typically the
video player), and every `--interval` seconds saves a cropped screenshot of just
that element into `--output-dir`, named by timestamp (`<epoch-millis>.png`).

It was originally designed for [AngelCam](https://www.angelcam.com/) iframe
streams (`https://v.angelcam.com/iframe?v=...`), whose player element has the id
`player` — hence that default for `--element-id`. It works with any page that
exposes the target element by `id`.

## Install

```bash
pip install -r requirements.txt   # selenium + Pillow
```

Also requires **Google Chrome**. With Selenium ≥ 4.6 the matching `chromedriver`
is downloaded automatically (Selenium Manager) — no manual driver setup.

## Usage

```bash
# Capture the 'player' element every 10s into ./captures (runs until Ctrl+C)
python pywebcamrecorder.py --url "https://v.angelcam.com/iframe?v=XXXXXXXX&autoplay=1"

# Ten frames, 5s apart, headless, into a custom folder
python pywebcamrecorder.py --url "https://example.com/cam" --count 10 --interval 5 --headless --output-dir out
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--url` | *(required)* | Webcam page to open. |
| `--element-id` | `player` | DOM id to capture (angelcam iframes: `player`; skylinewebcams: `skylinewebcams`). |
| `--output-dir` | `captures` | Where PNGs are written (created if missing). |
| `--interval` | `10` | Seconds between screenshots. |
| `--count` | `0` | Number of frames, then stop; `0` = run forever. |
| `--window-width` / `--window-height` | `1600` / `800` | Browser size. |
| `--initial-sleep` | `5` | Wait after load before the first frame. |
| `--headless` | off | Run Chrome with no visible window. |
| `--chromedriver` | *(auto)* | Pin an explicit driver binary instead of Selenium Manager. |

On Windows, `run.bat` is a convenience launcher (`run.bat --url ... --count 10`).

## Notes

Only captures elements addressable by `id`. The cropping approach (full-viewport
screenshot → crop to the element box via Pillow) works even when the element
isn't the whole page. Respect the terms of service of whatever stream you point
it at.
