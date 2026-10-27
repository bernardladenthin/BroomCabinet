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
REM Explorer starts a double-clicked batch file as  cmd.exe /c ""<full path>" "  and closes
REM the window when it ends: only then wait for a key. Started from a prompt, a script or an
REM agent (cmd /c run_UpdateGitRepos.bat ...), the launcher returns at once.
echo(%cmdcmdline%| findstr /i /l /c:"/c \"\"%~f0\" \"" >nul && pause
