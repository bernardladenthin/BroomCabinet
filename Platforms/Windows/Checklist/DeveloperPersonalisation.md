<!--
SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Developer personalisation
## git
git config --global user.email "bernard.ladenthin@gmail.com"
git config --global user.name "Bernard Ladenthin"
git config --global user.signingkey BF148ED2

## Disable Windows Defender
regedit "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows Defender" -> "DWORD-Wert" "DisableAntiSpyware" Value 1.
