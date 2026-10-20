@echo off
cd /d "%~dp0.."
.venv\Scripts\python.exe tools\create-voice-env.py
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\install-voice.py
if errorlevel 1 exit /b 1
echo Local whisper installed. First transcription downloads the selected model weights.
