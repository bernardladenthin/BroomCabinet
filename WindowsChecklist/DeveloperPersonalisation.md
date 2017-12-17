# Developer personalisation
## git
git config --global user.email "bernard.ladenthin@gmail.com"
git config --global user.name "Bernard Ladenthin"
git config --global user.signingkey BF148ED2

## Disable Windows Defender
regedit "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows Defender" -> "DWORD-Wert" "DisableAntiSpyware" Value 1.
