@echo off
cd /d "%~dp0"

setlocal enabledelayedexpansion
title iKong Heartrate Sensor Auto-Config

echo ==========================================
echo iKong Heartrate Sensor Setup (Windows)
echo ==========================================

if not exist config.env (
    echo [ERROR] config.env file not found!
    pause
    exit
)

for /f "tokens=1* delims==" %%a in (config.env) do (
    if "%%a"=="WIFI_SSID" set WIFI_SSID=%%b
    if "%%a"=="WIFI_PASSWORD" set WIFI_PASSWORD=%%b
)

set WIFI_SSID=%WIFI_SSID:"=%
set WIFI_PASSWORD=%WIFI_PASSWORD:"=%

echo [INFO] WIFI_SSID: %WIFI_SSID%

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python
) else (
    set PY_CMD=py
)

echo [STEP 0] Installing requirements...
%PY_CMD% -m pip install esphome aiohttp requests sseclient-py -q

echo [STEP 1] Updating hardware/heartrate.yaml...
echo import os, re > update_hr_yaml.py
echo s = os.environ.get('WIFI_SSID', '') >> update_hr_yaml.py
echo p = os.environ.get('WIFI_PASSWORD', '') >> update_hr_yaml.py
echo f = 'hardware/heartrate.yaml' >> update_hr_yaml.py
echo c = open(f, 'r', encoding='utf-8').read() >> update_hr_yaml.py
echo q = chr(34) >> update_hr_yaml.py
echo c = re.sub(r'ssid: ' + q + '.*' + q, f'ssid: {q}{s}{q}', c) >> update_hr_yaml.py
echo c = re.sub(r'password: ' + q + '.*' + q, f'password: {q}{p}{q}', c) >> update_hr_yaml.py
echo open(f, 'w', encoding='utf-8').write(c) >> update_hr_yaml.py

%PY_CMD% update_hr_yaml.py
del update_hr_yaml.py
echo [OK] YAML update complete!

echo [STEP 2] Flashing ESPHome...
%PY_CMD% -m esphome run hardware/heartrate.yaml

echo [STEP 3] Running Bridge Server...
%PY_CMD% server/bridge.py

pause