@echo off
:: Enable the built-in Administrator account. Run as Administrator.
:: Disable it again with DisableAdministratorAccount.bat when you are done.
net user administrator /active:yes
pause
