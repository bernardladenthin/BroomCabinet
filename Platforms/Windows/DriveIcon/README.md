# Custom drive icon & label (autorun.inf)

Windows shows a custom **icon** and **label** for a drive when an `autorun.inf`
sits in the drive's root directory. Place the file (and the `.ico`) at the root
of the volume, e.g. `E:\autorun.inf`.

`autorun.inf`:

```ini
[autorun]
ICON=icon.ico
LABEL=My Drive
```

* `ICON` — path to the icon, **relative to the drive root**. It can point at a
  `.ico` file, or an icon inside a `.dll`/`.exe` by index, e.g.
  `ICON=icons.dll,0`. Keep the icon in a subfolder if you prefer, e.g.
  `ICON=AUTORUN\scratch.ico` with the file at `E:\AUTORUN\scratch.ico`.
* `LABEL` — display name for the drive (optional).

A ready-to-copy [`autorun.inf`](autorun.inf) sample is next to this README.

## Notes

* This only sets the **icon/label**. Program *AutoRun/AutoPlay* from
  `[autorun]\open=...` is disabled by Windows for fixed and USB drives (since the
  post-Conficker security update) — the icon and label still work.
* Windows caches drive icons; you may need to re-insert the drive or restart
  Explorer to see a change.
* On a fixed disk you may need to set the file `+s +h` (system + hidden) and
  refresh for Explorer to pick it up:

  ```bat
  attrib +s +h E:\autorun.inf
  ```
