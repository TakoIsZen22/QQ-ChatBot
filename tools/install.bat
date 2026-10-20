@echo off
cd /d "%~dp0.."
python -m venv .venv
if errorlevel 1 exit /b 1
if exist requirements.lock.txt (
 .venv\Scripts\python.exe -m pip install -r requirements.lock.txt
) else (
 .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt
echo Install complete. Run tools\start.bat
