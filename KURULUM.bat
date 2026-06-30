@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Universal Color AI - Kurulum

set "PYTHON_CMD=py"
where py >nul 2>&1 || set "PYTHON_CMD=python"
where %PYTHON_CMD% >nul 2>&1 || goto python_error

if not exist ".venv\Scripts\python.exe" (
    echo [KURULUM] Sanal ortam oluşturuluyor...
    %PYTHON_CMD% -m venv .venv || goto error
)

echo [KURULUM] Gerekli paketler kuruluyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto error

if not exist "config.json" copy /Y "config.example.json" "config.json" >nul

echo.
echo [OK] Kurulum tamamlandı.
exit /b 0

:python_error
echo.
echo [HATA] Python bulunamadı. Python 3.10 veya üzerini kurup PATH seçeneğini açın.
goto error

:error
echo.
echo [HATA] Kurulum tamamlanamadı.
pause
exit /b 1
