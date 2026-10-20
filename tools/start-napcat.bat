@echo off
cd /d "%~dp0.."
if not exist .runtime\napcat\launcher-user.bat (
 echo NapCat is not staged. See docs\QQ_SETUP.md
 exit /b 1
)
if exist .venv\Scripts\python.exe .venv\Scripts\python.exe tools\harden-napcat.py
echo Use a separate bot QQ account. Do not log in the owner's account.
echo NapCat WebUI and login tokens must stay on this computer.
echo Run the official non-admin launcher. If it fails, consult NapCat's installation guide.
.venv\Scripts\python.exe tools\launch-napcat.py
