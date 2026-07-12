# Windows

Helper scripts, checklists and quick-reference commands for Windows.

## Subdirectories

| Directory | Contents |
|-----------|----------|
| [`Helper/`](Helper/) | Batch scripts for common maintenance tasks (network reset, admin account, hibernate, icon cache, CPU power tuning, …). See [`Helper/README.md`](Helper/README.md). |
| [`Checklist/`](Checklist/) | Step-by-step setup checklists for fresh Windows installs (developer machine, crypto node, 64K cluster install, …). |
| [`FileAssociations/`](FileAssociations/) | `.reg` files that restore the Windows default file-type associations. See [`FileAssociations/README.md`](FileAssociations/README.md). |
| [`Registry/`](Registry/) | Standalone registry tweaks (hide last user name, spooler despooling, "Open with LibreOffice", …). See [`Registry/README.md`](Registry/README.md). |
| [`ScheduledTasks/`](ScheduledTasks/) | Task Scheduler recipes (e.g. flush the disk write cache every 15 min with `sync.exe`). See [`ScheduledTasks/README.md`](ScheduledTasks/README.md). |
| [`DriveIcon/`](DriveIcon/) | Set a custom drive icon/label with `autorun.inf`. See [`DriveIcon/README.md`](DriveIcon/README.md). |

## Useful commands

Not standalone scripts — copy, adapt the placeholder, and run manually.

### System file integrity check

```bat
sfc /scannow
```

The detailed log is written to `%WinDir%\Logs\CBS\CBS.log`. If SFC cannot repair
in normal mode, run it again in Safe Mode. Reference:
<https://support.microsoft.com/kb/929833>

### Reboot straight into the advanced boot / Safe Mode menu

```bat
shutdown.exe /r /o /f /t 00
```

### Delete a file with a reserved or too-long name

Use the DOS 8.3 short name when the normal name cannot be addressed:

```bat
dir /x
del KURZNA~1.XYZ /F
```

### Paths longer than 260 characters (MAX_PATH)

Legacy Win32 tools (Explorer, `del`, `copy`) fail on a total path over ~260
characters ("the file name is too long"). Ways around it:

* Prefix the path with `\\?\` to opt out of the `MAX_PATH` limit:

  ```bat
  del "\\?\C:\very\long\path\...\file.txt"
  ```

* `robocopy` handles long paths natively — mirror an **empty** folder over the
  offending directory to wipe it, then remove it:

  ```bat
  robocopy C:\empty C:\very\long\path /MIR
  rmdir /s /q C:\very\long\path
  ```

* Enable Win32 long-path support system-wide (Windows 10 1607+):
  `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1`.
* Or use a tool that isn't `MAX_PATH`-bound, e.g. 7-Zip.

[`MaxPathOverflowDemo.zip`](MaxPathOverflowDemo.zip) reproduces the problem: it
contains a nested folder/file whose total path exceeds 260 characters. Extract
it and try to delete the result with Explorer or `del` to see the failure, then
practice the workarounds above.

### Redirect a batch run's output and errors to files

```bat
test.bat > output.msg 2> output.err
```

### List / remove third-party driver packages

```bat
pnputil.exe /e > c:\drivers.txt
pnputil.exe /d oemNN.inf
```

`/e` exports every third-party driver package; replace `oemNN.inf` with the
actual package name from the export to delete one.

### Show non-present ("ghost") devices in Device Manager

Set the flag and open Device Manager, then enable *View → Show hidden devices*.
Also available as [`Helper/ShowNonPresentDevices.bat`](Helper/ShowNonPresentDevices.bat).

```bat
set DEVMGR_SHOW_NONPRESENT_DEVICES=1
devmgmt.msc
```

### List shared folders / directories

Open the Shared Folders MMC snap-in to see every shared directory, the open
sessions and open files:

```bat
fsmgmt.msc
```

### GPU device / hardware ID

```bat
wmic PATH Win32_VideoController GET Description,PNPDeviceID
```

### Check whether ECC memory error-correction is active

```bat
wmic memphysical get memoryerrorcorrection
```

| Value | Meaning |
|-------|---------|
| 0 | Reserved |
| 1 | Other |
| 2 | Unknown |
| 3 | None |
| 4 | Parity |
| 5 | Single-bit ECC |
| 6 | Multi-bit ECC |
| 7 | CRC |

To see ECC errors that have actually been *logged* (WHEA-Logger events 18/19 in
the System log), see [`Topics/ECC/README.md`](../../Topics/ECC/README.md).

### Mirror a folder with robocopy

```bat
set src=D:\Source
set dst=E:\Destination
robocopy "%src%" "%dst%" /MIR
```

Quiet, multi-threaded variant (see the [robocopy examples wiki](http://social.technet.microsoft.com/wiki/contents/articles/1073.robocopy-and-a-few-examples.aspx)):

```bat
robocopy "%src%" "%dst%" /MIR /MT32 /NFL /NDL /NJH /NJS
```

`/NFL` no file list · `/NDL` no directory list · `/NJH` no job header · `/NJS` no job summary.

### Create a symbolic link (from PowerShell)

```powershell
cmd /c mklink link.exe target.exe
```

### Find which process has files open on a drive

With Sysinternals [`handle.exe`](https://learn.microsoft.com/sysinternals/downloads/handle):

```bat
handle.exe | findstr /i u:\
```

### Disable Chrome's built-in PDF viewer

Open this settings page and turn on "Download PDFs":

```
chrome://settings/content/pdfDocuments?search=pdf
```

### Persistent PowerShell command history

1. Start PowerShell as Administrator and allow local scripts:

   ```powershell
   Set-ExecutionPolicy RemoteSigned
   ```

2. Create `C:\Users\<username>\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`
   with:

   ```powershell
   $HistoryFilePath = Join-Path ([Environment]::GetFolderPath('UserProfile')) .ps_history
   Register-EngineEvent PowerShell.Exiting -Action { Get-History | Export-Clixml $HistoryFilePath } | Out-Null
   if (Test-Path $HistoryFilePath) { Import-Clixml $HistoryFilePath | Add-History }
   ```

PowerShell then keeps a `.ps_history` file in the user profile across sessions.

### Roaming "Open with" file-extension defaults (registry)

```
HKEY_CURRENT_USER\Software\Microsoft\Windows\Roaming\OpenWith\FileExt
```

### Fix: svchost / wuauserv 100 % CPU on Windows 7 (Windows Update)

Install Microsoft update KB3050265: <https://support.microsoft.com/kb/3050265>

### Losslessly re-encode a DVD VOB sequence to MP4

```
ffmpeg -i "concat:VTS_02_1.VOB|VTS_02_2.VOB|VTS_02_3.VOB|VTS_02_4.VOB|VTS_02_5.VOB" -c:v libx264 -preset slow -crf 20 -c:a aac -b:a 160k -vf format=yuv420p -movflags +faststart video-out.mp4
```

Replace the `VTS_02_*.VOB` file list with your own DVD title's VOB files.

### Legacy — Windows 8 classic Start behaviour

On early Windows 8, setting `RPEnabled` from `1` to `0` under
`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer`
restored the old Start menu / disabled the ribbon. Kept for reference only.

## References

### SMB2 client redirector caches

The SMB2 client keeps three metadata caches (directory, file-info,
file-not-found) that can make a network share show stale contents. Tunable via
the registry (`...\Services\LanmanWorkstation\Parameters`) or
`Set-SmbClientConfiguration`. Microsoft documentation:
[SMB2 Client Redirector Caches Explained](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-7/ff686200(v=ws.10)).
