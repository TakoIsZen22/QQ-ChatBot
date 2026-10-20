@echo off
cd /d "%~dp0.."
.venv\Scripts\python.exe tools\manage.py health
