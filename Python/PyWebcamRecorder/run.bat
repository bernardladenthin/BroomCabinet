REM SPDX-FileCopyrightText: 2020 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
rem Thin launcher, e.g. run.bat --url https://example.com/cam --interval 10
python "%~dp0pywebcamrecorder.py" %*
