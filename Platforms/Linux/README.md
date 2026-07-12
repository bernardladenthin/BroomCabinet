# Linux

Helper scripts and notes for Linux (and Raspberry Pi).

## Notes

- [`linux-commands.md`](linux-commands.md) — curated CLI one-liners grouped by
  topic (files/archives, networking, multimedia, git, package maintenance, …).

## Subdirectories

| Directory | Contents |
|-----------|----------|
| [`Helper/`](Helper/) | Shell helpers — e.g. `NTFSNamingCheck.sh` finds file names that are invalid on NTFS/Windows (trailing spaces, double spaces, names ending in a dot). |
| [`Ubuntu/`](Ubuntu/) | Package list and system-tuning notes. See [`Ubuntu/README.md`](Ubuntu/README.md). |
| [`RaspberryPI/`](RaspberryPI/) | Raspberry Pi projects and notes — [GPIO counter](RaspberryPI/GPIOCounter/README.md), [webcam capture](RaspberryPI/Webcam/README.md), and useful links. See [`RaspberryPI/README.md`](RaspberryPI/README.md). |

## Useful commands

### Find file names that break on NTFS / Windows

Run inside the directory you want to audit (see `Helper/NTFSNamingCheck.sh`):

```bash
find -iname "* .*"   # space before the extension
find -iname "*  *"   # double space
find -iname " *"     # leading space
find -iname "* "     # trailing space
find -iname "*."     # trailing dot
```
