<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Matrix digital rain

A console "Matrix rain" effect: green glyphs fall down each column with a bright
head and a fading tail. Just for fun — nothing is installed or changed.

## Files

* [`matrix.ps1`](matrix.ps1) — the effect. Uses half-width katakana + digits +
  latin glyphs, adapts live to window resizing, and each column falls at its own
  speed. Quit with **Esc**, **Q** or **Ctrl+C**.
* [`run_Matrix.bat`](run_Matrix.bat) — double-click launcher. Runs the script
  with `-NoProfile -ExecutionPolicy Bypass` so it works even when the script
  execution policy would otherwise block it (the bypass applies to this one run
  only).

## Run

Double-click [`run_Matrix.bat`](run_Matrix.bat), or from a terminal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File matrix.ps1
```
