REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
rem Thin launcher, e.g. "run.bat --shelly-ip 192.168.1.50 --once --dry-run".
python "%~dp0pyshellygpupowermanager.py" %*
