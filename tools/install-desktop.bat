@echo off
cd /d "%~dp0.."
.venv\Scripts\python.exe tools\create-desktop-env.py
if errorlevel 1 exit /b 1
if exist requirements.desktop.lock.txt (
 .venv-desktop\Scripts\python.exe -m pip install -r requirements.desktop.lock.txt
) else (
 .venv-desktop\Scripts\python.exe -m pip install -r requirements.desktop.txt
)
if errorlevel 1 exit /b 1
.venv-desktop\Scripts\python.exe -m src.desktop --register
if errorlevel 1 exit /b 1
echo Desktop runtime installed.
