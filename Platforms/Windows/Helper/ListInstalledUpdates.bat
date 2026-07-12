@echo off
:: List all installed Windows updates (hotfixes / KBs) into updatelist.txt
wmic qfe list > updatelist.txt
echo Written to updatelist.txt
pause
