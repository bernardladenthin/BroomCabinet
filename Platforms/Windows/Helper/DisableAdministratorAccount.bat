REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
:: Disable the built-in Administrator account. Run as Administrator.
net user administrator /active:no
pause
