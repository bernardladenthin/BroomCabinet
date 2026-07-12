@echo off
rem Thin launcher, e.g. "run.bat --shelly-ip 192.168.1.50 --once --dry-run".
python "%~dp0pyshellygpupowermanager.py" %*
