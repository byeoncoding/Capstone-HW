@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
setlocal enabledelayedexpansion

title iKong Auto-Config

echo ==========================================
echo   iKong Sensor Auto-Setup (Windows)
echo ==========================================

:: ---------- [1] config.env check ----------
if not exist config.env (
    echo [ERROR] config.env not found in this folder!
    pause
    exit /b 1
)

set WIFI_SSID=
set WIFI_PASSWORD=

for /f "usebackq tokens=1* delims==" %%a in ("config.env") do (
    set "_key=%%a"
    set "_val=%%b"
    if "%%a"=="WIFI_SSID"     set WIFI_SSID=%%b
    if "%%a"=="WIFI_PASSWORD" set WIFI_PASSWORD=%%b
)

:: Remove surrounding quotes
set WIFI_SSID=%WIFI_SSID:"=%
set WIFI_PASSWORD=%WIFI_PASSWORD:"=%

if "%WIFI_SSID%"=="" (
    echo [ERROR] WIFI_SSID is empty in config.env. Please set it first.
    pause
    exit /b 1
)

echo [INFO] WiFi target: %WIFI_SSID%

:: ---------- [2] Find Python ----------
set PY_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python
    goto :FOUND_PY
)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=py
    goto :FOUND_PY
)
echo [ERROR] Python not found. Install from https://python.org
pause
exit /b 1

:FOUND_PY
echo [INFO] Python command: %PY_CMD%

:: ---------- [3] Install packages ----------
echo [STEP 0] Installing required packages...
%PY_CMD% -m pip install esphome aioesphomeapi aiohttp certifi requests sseclient-py -q
if %errorlevel% neq 0 (
    echo [WARN] Some packages may not have installed correctly. Continuing...
)

:: ---------- [4] Update heartrate.yaml WiFi ----------
echo [STEP 1] Updating hardware/heartrate.yaml ...

if not exist hardware\heartrate.yaml (
    echo [ERROR] hardware\heartrate.yaml not found!
    echo         Make sure the hardware folder exists and contains heartrate.yaml
    pause
    exit /b 1
)

:: Write a tiny python script to do the substitution safely
(
    echo import os, re
    echo s = os.environ.get^('WIFI_SSID', ''^)
    echo p = os.environ.get^('WIFI_PASSWORD', ''^)
    echo f = 'hardware/heartrate.yaml'
    echo c = open^(f, 'r', encoding='utf-8'^).read^(^)
    echo q = chr^(34^)
    echo c = re.sub^(r'ssid: ' + q + '.*?' + q, 'ssid: ' + q + s + q, c^)
    echo c = re.sub^(r'password: ' + q + '.*?' + q, 'password: ' + q + p + q, c^)
    echo open^(f, 'w', encoding='utf-8'^).write^(c^)
    echo print^('[OK] WiFi credentials updated in heartrate.yaml'^)
) > _update_yaml.py

%PY_CMD% _update_yaml.py
if %errorlevel% neq 0 (
    echo [ERROR] Failed to update heartrate.yaml
    del _update_yaml.py >nul 2>&1
    pause
    exit /b 1
)
del _update_yaml.py >nul 2>&1

:: ---------- [5] Flash ESPHome firmware ----------
echo [STEP 2] Flashing firmware to ESP32 (connect via USB first!)
echo          Press Ctrl+C to skip if already flashed.
echo.
%PY_CMD% -m esphome run hardware/heartrate.yaml
if %errorlevel% neq 0 (
    echo [WARN] ESPHome flash failed or was skipped.
    echo        If already flashed, ignore this warning.
)

:: ---------- [6] Start bridge ----------
echo [STEP 3] Starting sensor bridge ...
echo          (Ctrl+C to stop)
echo.
%PY_CMD% server/bridge.py

pause