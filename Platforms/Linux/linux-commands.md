<!--
SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Linux commands

A curated grab-bag of useful Linux/CLI one-liners, grouped by topic. Placeholders
like `<user>`, `<host>`, `<url>` should be replaced with your own values.

## Files, search & archives

```bash
# Create / extract a tar archive (-z = gzip, -c create, -x extract, -v verbose, -f file)
tar -zcvf archive.tar.gz /path/to/dir
tar -xvf archive.tar                     # add -z if it is gzipped

# Recursive, case-insensitive text search
grep -rin 'text' .

# Identify files by MIME type
find . -exec file -i {} \; > files.txt

# Test the integrity of zip files
unzip -t '*.zip'

# Delete all .svn (or other) directories recursively
find . -type d -name '.svn' -print0 | xargs -0 rm -rf

# Empty directories: list / delete
find /path -type d -empty
find /path -type d -empty -delete
```

## Text editing (vim hex mode)

```vim
:%!xxd        " switch the buffer to a hex dump
:%!xxd -r     " convert back from hex
```

## System & hardware info

```bash
cat /etc/*release*                       # distribution / version
fdisk -l /dev/sda                        # partitions on a disk
df -h                                    # mounted filesystems, usage
lspci -nnk | grep -i VGA -A2             # GPU + kernel driver in use
glxinfo | grep -i render                 # OpenGL renderer
ldd ./program                            # shared libraries a binary needs
smartctl -A /dev/sdb                     # disk SMART attributes (needs smartmontools)
```

## Time, locale, hostname

```bash
timedatectl set-timezone Europe/Berlin
timedatectl                              # current time settings
hostnamectl                              # hostname / machine info
localectl                                # locale / keymap
```

## Filesystems & mounting

```bash
# Mount a VirtualBox shared folder
mount -t vboxsf -o rw,uid=1000,gid=1000 shareme /home/<user>/shareme

# Permanent mount via /etc/fstab, then mount it
echo '/dev/sdb1  /hdd  ext4  defaults  0  0' | sudo tee -a /etc/fstab
sudo mkdir -p /hdd && sudo mount /hdd
```

## Networking

```bash
# Find hosts on the local network by MAC (needs arp-scan)
arp-scan 192.168.0.0/24

# Remove a single host key from known_hosts
ssh-keygen -R <host>

# Capture traffic to a host/port into a pcap
tcpdump -nnvvvS -s 0 -w capture.pcap "dst <host> and dst port <port>"

# Enable IPv4 forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Transparently redirect port 80 to a local proxy (e.g. squid on 3128)
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 3128
```

## Cron

```bash
# Edit / list the current user's crontab
crontab -e
crontab -l

# Trigger a URL on a schedule (e.g. a PHP cron endpoint); --spider = don't download the body
*/5 * * * * wget --quiet --spider --tries=1 "http://example.com/task.php"

# Dynamic DNS: push the current public IP to the provider (credentials as placeholders)
*/5 * * * * wget --quiet --tries=1 "https://<user>:<pass>@dynupdate.no-ip.com/nic/update?hostname=<host>&myip=$(curl -s https://icanhazip.com)"

# Run a command at boot
@reboot python3 /home/user/script.py &

# Flush filesystem write buffers to disk periodically
*/30 * * * * sync

# Scheduled daily reboot at 03:00 (delayed 10s)
0 3 * * * /sbin/reboot -d 10
```

## Multimedia

```bash
# Extract the audio track from a video
mplayer -novideo -ao "pcm:file=out.wav" input.avi

# Merge wavs, then encode to mp3
sox *.wav out.wav
lame -b 128 out.wav out.mp3
```

## Devices & permissions

```bash
# Serial device access: quick fix, then the permanent way
sudo chmod 666 /dev/ttyUSB0
sudo usermod -aG dialout <user>          # permanent (re-login required)

# Add a user to a group (e.g. VirtualBox)
sudo usermod -aG vboxusers <user>

# Unblock all radios (wifi / bluetooth)
rfkill unblock all
```

## Security & system

```bash
# Generate strong passwords (needs apg): L/C/N = letters, capitals, numbers
apg -M LCN -s -a 1 -m 63 -n 4

# Magic SysRq on/off
sysctl -w kernel.sysrq=1

# SELinux: find access-vector (AVC) denials
ausearch -m avc

# SELinux: restore the default security-context labels on a path
restorecon -Rv /path

# Ubuntu: recover an eCryptfs mount passphrase
ecryptfs-unwrap-passphrase
```

## Package maintenance (Debian / Ubuntu)

```bash
sudo apt-get autoremove                  # remove unused deps and old kernels
dpkg -l | grep linux-image               # list installed kernels
sudo dpkg -i package.deb                 # install a .deb
```

## Git

```bash
# Delete a remote branch
git push origin --delete <branch>

# Roll the remote branch back by one commit (force — destructive!)
git push -f origin HEAD~1:master

# Create and push a signed tag
git tag -s v1.0.0 -m 'signed release 1.0.0'
git push origin --tags

# Patch from uncommitted / staged changes, then apply elsewhere
git diff > my.patch                      # unstaged changes
git diff --cached > my.patch             # staged changes
git apply my.patch

# Export commits as patch files
git format-patch -1 HEAD                  # just the last commit
git format-patch -10 HEAD --stdout > last-10.patch

# Move work between machines via stash
git stash show -p > work.patch            # on the source machine
git apply work.patch                      # on the target machine

# Rebase your branch onto an upstream remote
git remote add upstream <url>
git fetch upstream
git rebase upstream/master
```

## X11 / desktop

```bash
xrdb -load ~/.Xresources                 # reload X resources
xev                                      # show X events (identify key codes, X11)
showkey -k                               # show key codes on the console/TTY (non-X11 equivalent of xev)
xbacklight -set 100                      # set screen brightness (%)
xinput list                              # list input devices
```
