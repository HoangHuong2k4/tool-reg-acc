@echo off
title Grok - Chuyen ma giua cac profile
where python >nul 2>nul
if errorlevel 1 goto try_py
python -u "%~dp0relay\server.py"
goto finished
:try_py
where py >nul 2>nul
if errorlevel 1 goto missing
py -3 -u "%~dp0relay\server.py"
goto finished
:missing
echo Can cai Python 3.10 tro len de chay bo chuyen tiep.
:finished
pause
