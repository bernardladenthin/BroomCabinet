REM SPDX-FileCopyrightText: 2020 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
rem Thin launcher: forwards args, e.g. "run.bat sequence" or "run.bat encode".
python "%~dp0pyimagesequencer.py" %*
