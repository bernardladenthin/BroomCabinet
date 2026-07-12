# macOS

Notes for macOS.

## Mount an APFS volume manually (read-only)

List APFS containers/volumes, unlock an encrypted volume, then mount it
read-only:

```bash
diskutil apfs list
diskutil apfs unlockVolume /dev/diskXsY
mount_apfs -o rdonly /dev/diskXsY /Volumes/MyMount1/
```

Replace `/dev/diskXsY` with the volume from `diskutil apfs list`, and make sure
the mount point (e.g. `/Volumes/MyMount1/`) exists first.
