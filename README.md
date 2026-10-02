<!--
SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# BroomCabinet

Some useful stuff and work in progress.

## Layout

| Directory | Contents |
|-----------|----------|
| [`Platforms/`](Platforms/) | OS-specific helpers, scripts and notes — [`Windows/`](Platforms/Windows/), [`Linux/`](Platforms/Linux/), [`macOS/`](Platforms/macOS/). |
| [`Topics/`](Topics/) | Cross-platform topics clustered by subject — ECC memory, file-ending lists, trailing-space checks. |
| [`Snippets/`](Snippets/) | Small reusable code snippets, organized by programming language. |
| [`Java/`](Java/) | Standalone Java/Maven projects (built by CI) plus Java reference notes. |
| [`Python/`](Python/) | Standalone Python projects (built by CI) — listed below. |

## Python projects

Each is self-contained and standard-library only unless its own README says otherwise.

| Project | What it does |
|---------|--------------|
| [`PyMirror/`](Python/PyMirror/README.md) | Mirrors whole HTTP archives and rsync modules, keeps a checksum index current as a side effect, and answers questions about what the copy actually holds. |
| [`PySweeper/`](Python/PySweeper/README.md) | Empties a working directory from a per-file inventory that records *why*, and refuses anything the inventory no longer describes. |
| [`PyB2Verify/`](Python/PyB2Verify/README.md) | Proves that local directories and their Backblaze B2 buckets hold the same bytes, and re-reads either side against its own checksums to catch silent damage. Read-only towards B2; needs `b2sdk` and `boto3`. |
| [`PyImageResizer/`](Python/PyImageResizer/README.md) | Image-processing toolkit with three subcommands; every one previews by default and needs `--execute` to touch a file. |
| [`PyWebcamRecorder/`](Python/PyWebcamRecorder/README.md) | Screenshots one element of a webcam page at intervals to build a time-lapse. |
| [`PyDDRescueRelais/`](Python/PyDDRescueRelais/) | Runs `ddrescue` against a drive that hangs almost immediately, power-cycling it through a USB relay between short attempts. |
| [`PyImageSequencer/`](Python/PyImageSequencer/) | Turns a directory tree of images into a sequentially numbered copy, and optionally encodes that sequence to video with ffmpeg. |
| [`PyJcmdGcRun/`](Python/PyJcmdGcRun/) | Triggers `jcmd GC.run` against every locally running JVM. |
| [`PyShellyGpuPowerManager/`](Python/PyShellyGpuPowerManager/) | Throttles an NVIDIA GPU's power limit from a Shelly plug's live meter reading, so the circuit keeps a set headroom and is never overdrawn. |
