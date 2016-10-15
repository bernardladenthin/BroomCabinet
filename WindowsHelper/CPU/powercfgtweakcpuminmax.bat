::
:: Copyright 2016 Bernard Ladenthin bernard.ladenthin@gmail.com
::
:: Licensed under the Apache License, Version 2.0 (the "License");
:: you may not use this file except in compliance with the License.
:: You may obtain a copy of the License at
::
::    http://www.apache.org/licenses/LICENSE-2.0
::
:: Unless required by applicable law or agreed to in writing, software
:: distributed under the License is distributed on an "AS IS" BASIS,
:: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
:: See the License for the specific language governing permissions and
:: limitations under the License.
::
::

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
