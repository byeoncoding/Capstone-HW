@echo off
cd /d "%~dp0"

setlocal enabledelayedexpansion
title HeartView Fall Sensor Auto-Config

echo ==========================================
echo HeartView Fall Sensor Setup (Windows)
echo ==========================================

if not exist config.env (
    echo [ERROR] config.env file not found!
    pause
    exit
)

for /f "tokens=1* delims==" %%a in (config.env) do (
    set key=%%a
    set val=%%b
    if "!key!"=="WIFI_SSID" set WIFI_SSID=!val!
    if "!key!"=="WIFI_PASSWORD" set WIFI_PASSWORD=!val!
)

if defined WIFI_SSID set WIFI_SSID=!WIFI_SSID:"=!
if defined WIFI_PASSWORD set WIFI_PASSWORD=!WIFI_PASSWORD:"=!

echo [INFO] WIFI_SSID: !WIFI_SSID!

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python
) else (
    set PY_CMD=py
)

echo [STEP 0] Installing requirements...
!PY_CMD! -m pip install esphome aiohttp requests sseclient-py -q

echo [STEP 1] Flashing ESPHome...
!PY_CMD! -m esphome -s WIFI_SSID "!WIFI_SSID!" -s WIFI_PASSWORD "!WIFI_PASSWORD!" run hardware/fall.yaml

echo [STEP 2] Running Bridge Server...
!PY_CMD! server/bridge_fall.py

pause