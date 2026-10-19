@echo off
REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

REM Double-click launcher for Update-GitRepos.ps1. Bypasses the script execution
REM policy for this one file only (nothing is installed or changed).
REM Unless -Root is given it processes the folder that contains this BroomCabinet
REM clone (i.e. all sibling repositories); arguments are passed through,
REM e.g.  run_UpdateGitRepos.bat -WhatIf   or   run_UpdateGitRepos.bat -Root D:\src
echo.%* | findstr /i /c:"-Root" >nul
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update-GitRepos.ps1" -Root "%~dp0..\..\..\.." %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update-GitRepos.ps1" %*
)
pause
