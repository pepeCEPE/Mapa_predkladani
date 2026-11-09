@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python neni nainstalovany. Stahnete ho z https://www.python.org/downloads/ a pri instalaci zaskrtnete "Add Python to PATH".
  pause
  exit /b 1
)
python start.py
pause
