REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

@echo off
Setx DEVMGR_SHOW_NONPRESENT_DEVICES 1
Set DEVMGR_SHOW_NONPRESENT_DEVICES=1
Devmgmt.msc
