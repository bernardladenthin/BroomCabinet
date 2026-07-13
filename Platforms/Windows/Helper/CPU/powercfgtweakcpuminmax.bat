REM SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
REM
REM SPDX-License-Identifier: Apache-2.0

:: example usage
:: @call powercfgtweakcpuminmax 0 0
::

@IF "%1"=="" (
    @set valuemin=0
) ELSE (
	@set valuemin=%1
)

@IF "%2"=="" (
    set valuemax=100
) ELSE (
	set valuemax=%2
)

@echo min: %valuemin%
@echo max: %valuemax%

:: http://stackoverflow.com/questions/1173291/using-powercfg-to-duplicate-the-currently-active-power-scheme
:: save it in a variable:
@for /f "tokens=2 delims=:(" %%x in ('powercfg -getactivescheme') do @set guid=%%x
:: remove whitespace
@set guid=%guid: =%

:: https://technet.microsoft.com/en-us/library/hh824902.aspx
:: <SCHEME_GUID> <SUB_GUID> <SETTING_GUID> <SETTING_INDEX>

@set SUBGUID=SUB_PROCESSOR
@set SETTINGGUID=PROCTHROTTLEMIN
@POWERCFG /SETACVALUEINDEX %guid% %SUBGUID% %SETTINGGUID% %valuemin%
@POWERCFG /SETDCVALUEINDEX %guid% %SUBGUID% %SETTINGGUID% %valuemin%

@set SUBGUID=SUB_PROCESSOR
@set SETTINGGUID=PROCTHROTTLEMAX
@POWERCFG /SETACVALUEINDEX %guid% %SUBGUID% %SETTINGGUID% %valuemax%
@POWERCFG /SETDCVALUEINDEX %guid% %SUBGUID% %SETTINGGUID% %valuemax%

:: force reload
@POWERCFG -setactive %guid%
