@echo off
:: Reset the Winsock catalog and flush the DNS resolver cache.
:: Run as Administrator. A reboot is recommended after the winsock reset.
netsh winsock reset
ipconfig /flushdns
pause
