@echo off
taskkill /FI "WINDOWTITLE eq RecoverLink - Hospital-to-Home Care Coordination*" /T /F >nul 2>nul
echo RecoverLink has been stopped.
pause
