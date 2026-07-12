REM SPDX-FileCopyrightText: 2020 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
rem Thin launcher, e.g. "run.bat resize --execute" or "run.bat clean".
python "%~dp0pyimageresizer.py" %*
