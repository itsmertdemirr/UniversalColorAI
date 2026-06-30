@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Universal Color AI - Kamera Taraması

if not exist ".venv\Scripts\python.exe" (
    call KURULUM.bat || exit /b 1
)

if not exist "config.json" copy /Y "config.example.json" "config.json" >nul

".venv\Scripts\python.exe" launcher.py cameras --scan-limit 10
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
