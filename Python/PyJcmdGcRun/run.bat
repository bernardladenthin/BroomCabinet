REM SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
rem Thin launcher so this can be double-clicked / run from Explorer's address
rem bar without typing "python" - forwards all args straight through.
python "%~dp0pyjcmdgcrun.py" %*
