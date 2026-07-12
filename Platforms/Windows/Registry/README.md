# Registry tweaks

Standalone `.reg` tweaks. Import by double-clicking (or `regedit /s file.reg`).
Review each file first — they are plain text.

| File | Effect |
|------|--------|
| `dontdisplaylastusername.reg` | Hide the last logged-on user name on the sign-in screen (`HKLM\...\Policies\System\dontdisplaylastusername = 1`). |
| `ForceCSREMFDespooling.reg` | Set `ForceCSREMFDespooling = 0` to fix print error `0x000006d1` ("cannot connect to printer") on Windows 8/8.1 — see below. |
| `OpenWithLibreOffice/` | Add a generic "Open with" command for unknown file types (two variants, see below). |

## ForceCSREMFDespooling — printer error 0x000006d1

On Windows 8/8.1 adding a shared printer can fail with
`0x000006d1`. Disabling server-side render/despooling fixes it.

* GUI (Pro/Enterprise): `gpedit.msc` → *Computer Configuration → Administrative
  Templates → Printers* → **Always render print jobs on the server** → *Disabled*.
* Registry (any edition): `ForceCSREMFDespooling.reg` sets
  `HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\ForceCSREMFDespooling = 0`.

## OpenWithLibreOffice

Registers `openas` for the `Unknown` file class so double-clicking an
unrecognised file offers to open it (used to route documents to LibreOffice).

* `shell_openas_command.reg` — minimal variant.
* `vista_shell_openas_command.reg` — Vista-era variant that also adds the
  `opendlg` command and the multi-select model.
