<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Windows Helper scripts

Small Windows batch scripts. Most that change system state must be run **as
Administrator**. Quick-reference one-liners (pnputil, ffmpeg, robocopy, …) live
in the parent [`Windows/README.md`](../README.md); the CPU power-tuning guide is
in [`CPU/README.md`](CPU/README.md).

| Script | Purpose |
|--------|---------|
| `BackupMozilla.bat` | Archive the Firefox profile to the Desktop with WinRAR/rar. |
| `BackupPuttySessions.bat` | Export all stored PuTTY sessions to `putty.reg` on the Desktop. |
| `CleanIcons.bat` | Rebuild the Explorer icon cache (deletes `IconCache.db` and restarts Explorer). |
| `clearAllEvents.bat` | Clear every Windows event log via `wevtutil`. |
| `DisableAdministratorAccount.bat` | Disable the built-in Administrator account. |
| `DisableAutotuninglevel.bat` | Turn off TCP receive-window auto-tuning. |
| `EnableAdministratorAccount.bat` | Enable the built-in Administrator account. |
| `EnableHibernate.bat` | Re-enable hibernation (`powercfg -H on`). |
| `getUUID.bat` | Print the machine UUID (`wmic csproduct get UUID`). |
| `ListInstalledUpdates.bat` | Dump installed hotfixes/KBs to `updatelist.txt`. |
| `ResetNetworkStack.bat` | Reset Winsock and flush the DNS cache. |
| `ShowNonPresentDevices.bat` | Reveal hidden/non-present devices in Device Manager. |
| `TurnOffFastStartup.bat` | Disable Fast Startup (hiberboot). |
| `TurnOnFastStartup.bat` | Enable Fast Startup (hiberboot). |
| `CPU/` | Processor min/max state power-plan tweaks — see [`CPU/README.md`](CPU/README.md). |
