@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
 echo Run tools\install.bat first.
 exit /b 1
)
.venv\Scripts\python.exe -m src.main
