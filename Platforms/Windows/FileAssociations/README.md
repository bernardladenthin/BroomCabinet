# File associations

`.reg` files that restore the Windows **default** file-type associations. Import
one by double-clicking it (or `regedit /s file.reg`), then sign out / restart
Explorer. Use these to undo a hijacked association (e.g. after some program
grabbed `.bat`, `.txt`, `.zip`, …) and put the built-in Windows default back.

| Directory | Contents |
|-----------|----------|
| `Windows7-Defaults/` | One `.reg` per extension for the Windows 7 defaults (audio/video, images, archives, scripts, system types, …). Also works on later Windows for most types. |
| `Windows8-BatFile/` | `default_batch_win8.1.reg` — restores the `.bat` association on Windows 8.1. |

Origin: the Windows 7 set was created by Shawn Brink /
[sevenforums.com "Default File Type Associations - Restore"](http://www.sevenforums.com/tutorials/19449-default-file-type-associations-restore.html).

> ⚠️ A `.reg` import overwrites the current association for that type. Review the
> file first if you are unsure — each one is plain text (UTF-16).
