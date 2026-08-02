@echo off
REM SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

setlocal disabledelayedexpansion

:: Strip camera / messenger file name prefixes (IMG-, IMG_, VID_, AUD-, PXL_, ...)
:: and normalise .jpeg to .jpg.
::
::   RenameCameraPrefixes.bat                 preview, current directory
::   RenameCameraPrefixes.bat /y              rename, current directory
::   RenameCameraPrefixes.bat D:\Photos       preview, D:\Photos
::   RenameCameraPrefixes.bat D:\Photos /y    rename, D:\Photos
::
:: Preview is the default on purpose: the script touches every matching file in
:: the working directory, so a double click in the wrong folder must not do any
:: damage. Only a prefix at the very start of the name is removed, and a rename
:: that would overwrite an existing file is reported and skipped.

set "PREFIXES=IMG- IMG_ VID- VID_ AUD- AUD_ PXL_ PANO_ MVIMG_ SVID_"

set "APPLY="
set "TARGET=."

:parseArgs
if "%~1"=="" goto parsed
if /i "%~1"=="/y" (set "APPLY=1") else (set "TARGET=%~1")
shift
goto parseArgs
:parsed

pushd "%TARGET%" 2>nul
if errorlevel 1 (
    echo Directory not found: %TARGET%
    exit /b 1
)

set /a renamed=0, skipped=0

echo Directory: %CD%
if not defined APPLY echo PREVIEW ONLY - pass /y to actually rename.
echo.

:: .jpeg first, so that a following prefix strip already works on the .jpg name
for %%f in (*.jpeg) do call :tryRename "%%~nxf" "%%~nf.jpg"

for %%p in (%PREFIXES%) do (
    for %%f in ("%%p*") do call :stripPrefix "%%~nxf" "%%p"
)

echo.
echo Renamed: %renamed%   Skipped: %skipped%
popd
exit /b 0

:: ---------------------------------------------------------------------------

:stripPrefix  <fileName> <prefix>
:: The file name is read with delayed expansion still off so that a "!" in the
:: name survives. ":*prefix=" cuts everything up to and including the first
:: match - since the wildcard anchored the match at position 0, that is exactly
:: the prefix and nothing else.
set "_src=%~1"
setlocal enabledelayedexpansion
set "_dst=!_src:*%~2=!"
endlocal & set "_dst=%_dst%"
if not defined _dst exit /b 0
call :tryRename "%_src%" "%_dst%"
exit /b 0

:tryRename  <from> <to>
if /i "%~1"=="%~2" exit /b 0
if exist "%~2" (
    echo   [skip]  "%~1" -^> "%~2"  target exists
    set /a skipped+=1
    exit /b 0
)
if not defined APPLY (
    echo   [would] "%~1" -^> "%~2"
    set /a renamed+=1
    exit /b 0
)
ren "%~1" "%~2" 2>nul
if errorlevel 1 (
    echo   [fail]  "%~1" -^> "%~2"
    set /a skipped+=1
    exit /b 0
)
echo   [ok]    "%~1" -^> "%~2"
set /a renamed+=1
exit /b 0
