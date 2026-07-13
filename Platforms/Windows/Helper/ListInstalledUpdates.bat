REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
:: List all installed Windows updates (hotfixes / KBs) into updatelist.txt
wmic qfe list > updatelist.txt
echo Written to updatelist.txt
pause
