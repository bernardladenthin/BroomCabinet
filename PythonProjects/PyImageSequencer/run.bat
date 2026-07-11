@echo off
rem Thin launcher: forwards args, e.g. "run.bat sequence" or "run.bat encode".
python "%~dp0pyimagesequencer.py" %*
