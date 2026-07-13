REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
:: Enable the built-in Administrator account. Run as Administrator.
:: Disable it again with DisableAdministratorAccount.bat when you are done.
net user administrator /active:yes
pause
