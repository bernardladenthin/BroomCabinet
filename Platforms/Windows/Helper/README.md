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
| `RenameCameraPrefixes.bat` | Strip camera/messenger name prefixes (`IMG-`, `VID_`, `AUD-`, `PXL_`, …) and normalise `.jpeg` to `.jpg`. Previews by default — see below. |
| `ResetNetworkStack.bat` | Reset Winsock and flush the DNS cache. |
| `ShowNonPresentDevices.bat` | Reveal hidden/non-present devices in Device Manager. |
| `TurnOffFastStartup.bat` | Disable Fast Startup (hiberboot). |
| `TurnOnFastStartup.bat` | Enable Fast Startup (hiberboot). |
| `CPU/` | Processor min/max state power-plan tweaks — see [`CPU/README.md`](CPU/README.md). |

## RenameCameraPrefixes.bat

Cameras, phones and messengers prefix their file names (`IMG-20240101.jpg`,
`VID_20240103.mp4`, `AUD-20240105.opus`, `PXL_…`, `MVIMG_…`). The script removes
those prefixes and renames `.jpeg` to `.jpg`, so a mixed folder sorts purely by
its date part.

```bat
RenameCameraPrefixes.bat                 preview, current directory
RenameCameraPrefixes.bat /y              rename, current directory
RenameCameraPrefixes.bat D:\Photos       preview, D:\Photos
RenameCameraPrefixes.bat D:\Photos /y    rename, D:\Photos
```

**Preview is the default** — without `/y` nothing is renamed, it only prints what
*would* happen. The script processes every matching file in the working
directory, so a double-click in the wrong folder must not do damage.

Details worth knowing:

* Only a prefix at the very **start** of the name is removed. `Urlaub-IMG-2.jpg`
  stays untouched — a naive `ren` with string replacement would turn it into
  `Urlaub-2.jpg`.
* A rename that would overwrite an existing file is reported as `[skip]` and left
  alone (e.g. both `IMG-9999.jpg` and `9999.jpg` present).
* Non-recursive by design; it never descends into subdirectories.
* In preview mode a `.jpeg` file with a prefix shows up twice — once for the
  extension change, once for the prefix strip. Both steps chain correctly when
  actually applied (`IMG_1.jpeg` → `IMG_1.jpg` → `1.jpg`).
* Extend the prefix list by editing the `PREFIXES` variable at the top.
