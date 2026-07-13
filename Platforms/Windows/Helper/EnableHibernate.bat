REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
:: Enable hibernation (adds the hibernate power option back).
:: Afterwards you may want to disable "Allow hybrid sleep" in the advanced
:: power options if you only want plain hibernate.
powercfg -H on
pause
