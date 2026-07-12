# Ubuntu notes

Historical package list and tuning notes (originally for Ubuntu 14.04 — adapt
package names for newer releases).

## Base packages

```bash
sudo apt-get install \
  texlive-full filezilla gimp inkscape pidgin sumo git subversion mplayer \
  lame vlc maven2 netbeans keepassx vim gparted smartmontools \
  openjdk-7-jdk openjdk-7-source openjdk-7-doc dkms libgsoap4 unrar \
  ttf-mscorefonts-installer pepperflashplugin-nonfree git-svn doxygen mercurial
```

VirtualBox from an external source — add your user to the `vboxusers` group:

```bash
sudo adduser "$USER" vboxusers
```

## Tuning

Remove Thunderbird completely:

```bash
sudo apt-get remove --purge 'thunderbird*'
```

Lower swappiness (favour RAM over swap):

```bash
echo "vm.swappiness=5" | sudo tee -a /etc/sysctl.conf
```

Periodic SSD trim and sync via cron:

```bash
sudo crontab -l | { cat; echo "* * * * * fstrim -v /home/"; } | sudo crontab -
sudo crontab -l | { cat; echo "* * * * * sync"; } | sudo crontab -
```
