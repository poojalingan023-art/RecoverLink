@echo off
setlocal
title RecoverLink - Hospital-to-Home Care Coordination
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python was not found on this computer.
  echo Install Python 3.11+ from python.org and make sure "Add Python to PATH" is selected.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Setting up RecoverLink for first use...
  python -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Package installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)

if not exist "instance\recoverlink.db" (
  echo Preparing the RecoverLink demo database...
  ".venv\Scripts\python.exe" seed.py
)

start "" "http://127.0.0.1:5000"
".venv\Scripts\python.exe" app.py
endlocal
