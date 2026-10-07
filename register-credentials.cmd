@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m emart24 credentials
if errorlevel 1 pause
