#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2020 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Periodically screenshot a single element on a webcam page (time-lapse capture).

Opens a page in Chrome via Selenium, locates one DOM element (e.g. the video
player), and saves a cropped PNG of just that element every --interval seconds.
Useful for building a time-lapse from an embedded webcam stream.

Everything that used to be hard-coded (output directory, page URL, element id,
window size, interval) is now a command-line argument, so nothing personal is
baked into the source.

Needs Chrome installed plus Selenium and Pillow (see requirements.txt). With
Selenium >= 4.6 the matching chromedriver is downloaded automatically by
Selenium Manager - no manual driver path required. Pass --chromedriver only if
you want to pin a specific driver binary.
"""

import argparse
import sys
import time
from io import BytesIO
from pathlib import Path


def take_element_screenshot(element, driver, filename):
    """Save a PNG of just `element` by cropping a full-viewport screenshot."""
    from PIL import Image

    location = element.location
    size = element.size
    png = driver.get_screenshot_as_png()  # screenshot of the whole viewport

    im = Image.open(BytesIO(png))  # open in memory via Pillow

    left = location["x"]
    top = location["y"]
    right = location["x"] + size["width"]
    bottom = location["y"] + size["height"]

    im = im.crop((left, top, right, bottom))  # crop to the element's box
    im.save(filename)


def build_driver(args):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    if args.headless:
        options.add_argument("--headless=new")

    # Selenium >= 4.6 resolves the driver via Selenium Manager when no Service
    # path is given; only build an explicit Service when the user pins one.
    service = Service(executable_path=args.chromedriver) if args.chromedriver else None
    return webdriver.Chrome(service=service, options=options)


def record(args):
    from selenium.webdriver.common.by import By

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    driver = build_driver(args)
    try:
        driver.get(args.url)
        driver.set_window_size(args.window_width, args.window_height)
        time.sleep(args.initial_sleep)  # let the stream start playing

        element = driver.find_element(By.ID, args.element_id)

        taken = 0
        while args.count == 0 or taken < args.count:
            millis = int(round(time.time() * 1000))
            filename = output_dir / f"{millis}.png"
            take_element_screenshot(element, driver, str(filename))
            taken += 1
            print(f"Saved {filename}")

            if args.count != 0 and taken >= args.count:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        driver.quit()

    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", required=True, help="Webcam page URL to open.")
    parser.add_argument(
        "--element-id",
        default="player",
        help="DOM id of the element to capture (default: 'player'; e.g. angelcam "
        "iframes use 'player', skylinewebcams uses 'skylinewebcams').",
    )
    parser.add_argument(
        "--output-dir",
        default="captures",
        help="Directory to write PNGs into, created if missing (default: 'captures').",
    )
    parser.add_argument(
        "--interval", type=float, default=10.0, help="Seconds between screenshots (default: 10)."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of screenshots to take, then stop; 0 means run forever (default: 0).",
    )
    parser.add_argument("--window-width", type=int, default=1600, help="Browser width (default: 1600).")
    parser.add_argument("--window-height", type=int, default=800, help="Browser height (default: 800).")
    parser.add_argument(
        "--initial-sleep",
        type=float,
        default=5.0,
        help="Seconds to wait after loading, before the first capture (default: 5).",
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run Chrome headless (no visible window)."
    )
    parser.add_argument(
        "--chromedriver",
        default=None,
        help="Explicit path to a chromedriver binary. Omit to let Selenium Manager auto-resolve it.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return record(args)


if __name__ == "__main__":
    sys.exit(main())
