@echo off
cd /d "%~dp0.."
.venv\Scripts\python.exe tools\manage.py stop
if errorlevel 1 exit /b 1
call tools\start.bat
