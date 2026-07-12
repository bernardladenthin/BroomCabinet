# Webcam capture

Captures a still image from a USB webcam with [`fswebcam`](https://github.com/fsphil/fswebcam)
and stores it, sorted into per-day / per-hour folders:

```
/home/pi/cam/<YYYYMMDD>/<HH>/<YYYYMMDDHHMMSS>.jpg
```

Run every minute via cron it produces a simple timelapse archive.

## Prerequisites

```bash
sudo apt-get install fswebcam
```

## Script

[`picturecron.sh`](picturecron.sh) builds the dated path, creates it, and takes
the picture:

```sh
fswebcam -r 1280x720 --jpeg 100 -D 3 -S 13 "$imgFile"
```

* `-r 1280x720` — resolution
* `--jpeg 100` — JPEG quality
* `-D 3` — delay 3 s before capturing (lets the sensor settle)
* `-S 13` — skip the first 13 frames (auto-exposure warm-up)

Adjust `path` inside the script to change where images are stored.

## Add to cron

Take a picture every minute:

```bash
crontab -l | { cat; echo "* * * * * bash /home/pi/picturecron.sh"; } | crontab -
```

Copy `picturecron.sh` to `/home/pi/` first (or adjust the path in the cron line).
