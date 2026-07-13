REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
:: Reset the Winsock catalog and flush the DNS resolver cache.
:: Run as Administrator. A reboot is recommended after the winsock reset.
netsh winsock reset
ipconfig /flushdns
pause
