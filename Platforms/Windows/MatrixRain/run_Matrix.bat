@echo off
REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

REM Double-click launcher for the Matrix rain. Bypasses the script execution
REM policy for this one file only (nothing is installed or changed).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0matrix.ps1"
