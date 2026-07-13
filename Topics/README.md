<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Topics

Cross-platform topics, clustered by subject. Each topic is a folder with its own
README; OS-specific details are kept as sections inside where relevant.
OS-specific helpers live in [`../Platforms/`](../Platforms/) instead.

| Directory | Contents |
|-----------|----------|
| [`DataRescue/`](DataRescue/) | Recover files from a failing/corrupted device — image it (PyDDRescueRelais), then repair a FAT32 image and copy files off. |
| [`ECC/`](ECC/) | Checking ECC memory and detecting logged ECC/WHEA errors (Windows + Linux). |
| [`FileEndings/`](FileEndings/) | File-name patterns (LaTeX build artifacts, OS junk files) for `.gitignore`/backup excludes, with `rm`/`find` cleanup commands. |
| [`GpsLogging/`](GpsLogging/) | PHP + MySQL endpoint for the Android GPSLogger app, with CSV/GPX/JSON export (sanitized example). |
| [`TodoTemplate/`](TodoTemplate/) | Plain-text to-do glyphs (☐ ☑ ☒) and an ASCII task-card template. |
| [`TrailingSpaces/`](TrailingSpaces/) | Groovy script to find file names with leading/trailing/double spaces. |
