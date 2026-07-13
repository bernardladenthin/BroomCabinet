REM SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

netsh interface tcp show global
netsh interface tcp set global autotuninglevel=disabled
netsh interface tcp show global
pause
