REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
taskkill /f /IM explorer.exe
CD /d %userprofile%\AppData\Local
DEL IconCache.db /a
Start explorer.exe