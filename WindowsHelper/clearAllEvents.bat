@echo off
SETLOCAL EnableDelayedExpansion
for /F "tokens=*" %%1 in ('wevtutil.exe el') DO wevtutil.exe cl "%%1"