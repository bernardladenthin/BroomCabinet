@echo off
:: Export all stored PuTTY sessions (and settings) to putty.reg on the Desktop.
:: See http://stackoverflow.com/questions/13023920/how-to-export-putty-sessions-list
:: Import the file on another machine by double-clicking it.
regedit /e "%userprofile%\Desktop\putty.reg" HKEY_CURRENT_USER\Software\SimonTatham
echo Exported to %userprofile%\Desktop\putty.reg
pause
