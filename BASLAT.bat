@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Universal Color AI

if not exist ".venv\Scripts\python.exe" (
    call KURULUM.bat || goto error
)

".venv\Scripts\python.exe" -c "import cv2, numpy" >nul 2>&1
if errorlevel 1 (
    call KURULUM.bat || goto error
)

if not exist "config.json" copy /Y "config.example.json" "config.json" >nul

".venv\Scripts\python.exe" launcher.py run
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo [HATA] Uygulama başlatılamadı.
echo Kamera sorunu için KAMERA_TARA.bat dosyasını çalıştırın.
pause
exit /b 1
