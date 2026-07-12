# Data rescue

Recovering files from a failing or corrupted storage device — image it first,
then work on the *copy*, never the original.

## 1. Make a disk image (relayed dd_rescue)

Use [`PyDDRescueRelais`](../../Python/PyDDRescueRelais) to pull a raw image off
the failing device (retrying bad sectors), so all further work happens on the
image, not the dying hardware.

## 2. Repair a FAT32 image and copy the files off

Once you have a `.dd` image, attach it to a loop device, repair the FAT
filesystem, and rsync the files to safety.

### Attach the image to a loop device

```bash
# --partscan: scan partitions inside the image · --find: next free loop device · --show: print its name
losetup --partscan --find --show /media/targethdd/stickdd.dd
```

### Mount a partition

```bash
mount -o loop /dev/loop1p1 /media/stickmount
```

### Check & repair the FAT filesystem

```bash
# -w write now · -a auto-repair · -l lock · -v verbose · -t mark bad clusters
dosfsck -w -a -l -v -t /dev/loop1p1 > /media/targethdd/summary.txt
```

### Copy the files off with rsync

```bash
# -a archive · -u skip newer at dest · -v verbose · --delete · --ignore-errors (continue on errors)
rsync -auv --stats --delete --ignore-errors /media/stickmount/ /media/targethdd/stickcopy > /media/targethdd/rsyncsummary.txt 2>&1
```

### Detach the loop device when done

```bash
losetup -d /dev/loop1
```

## Verify a storage device (detect fake capacity / bad flash)

Cheap or counterfeit USB sticks and SD cards often report a larger size than
they physically have, silently corrupting anything written past the real
capacity. Write known random data across the whole device, read it back, and
compare checksums — if they differ, the device is faulty or lying about its size.

> ⚠️ This **destroys all data** on the device. Confirm the device node with
> `lsblk` first — writing to the wrong `/dev/sdX` wipes it.

```bash
DEV=/dev/sdX                                    # device under test — verify with lsblk!

# 1. Random reference file, at least as large as the device
dd if=/dev/urandom of=rnd_ref bs=1M count=16000 status=progress

# 2. Write it to the device (dd stops when the device is full)
dd if=rnd_ref of="$DEV" bs=1M status=progress

# 3. Trim the reference to the bytes that actually fit, read the same
#    amount back, and compare — the two checksums must be identical
SIZE=$(blockdev --getsize64 "$DEV")
head -c "$SIZE" rnd_ref > rnd_written
dd if="$DEV" of=rnd_read bs=1M count=$((SIZE / 1024 / 1024)) status=progress
md5sum rnd_written rnd_read

rm -f rnd_ref rnd_written rnd_read
```

Easier alternatives that do the same check for you: `f3write` / `f3read` (the
`f3` package), or `badblocks -w` (also destructive).
