@echo off
setlocal enabledelayedexpansion
title iKong Heartrate Auto-Config (Windows)

echo ==========================================
echo   iKong 심박 센서 자동화 시스템 (Windows)
echo ==========================================

:: 1. config.env에서 정보 추출
if not exist config.env (
    echo [ERROR] config.env 파일이 없습니다!
    pause
    exit
)

for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="WIFI_SSID" set WIFI_SSID=%%b
    if "%%a"=="WIFI_PASSWORD" set WIFI_PASSWORD=%%b
)

:: 따옴표 제거
set WIFI_SSID=%WIFI_SSID:"=%
set WIFI_PASSWORD=%WIFI_PASSWORD:"=%

echo [INFO] 설정된 와이파이: %WIFI_SSID%

:: 2. 필수 패키지 설치 (추가됨)
echo [STEP 0] 필수 패키지를 확인합니다...
pip install esphome aioesphomeapi aiohttp certifi requests sseclient-py -q

:: 3. YAML 파일 와이파이 자동 치환
echo [STEP 1] hardware/heartrate.yaml 업데이트 중...
python -c "import sys; import re; p = 'hardware/heartrate.yaml'; c = open(p, 'r', encoding='utf-8').read(); c = re.sub(r'ssid: \".*\"', 'ssid: \"%WIFI_SSID%\"', c); c = re.sub(r'password: \".*\"', 'password: \"%WIFI_PASSWORD%\"', c); open(p, 'w', encoding='utf-8').write(c)"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 파일 수정 중 오류가 발생했습니다.
    pause
    exit
)
echo [OK] 와이파이 정보 자동 업데이트 완료!

:: 4. ESPHome 업로드
echo [STEP 2] 센서 펌웨어 업로드 시작...
py -m esphome run hardware/heartrate.yaml

:: 5. 브릿지 실행 (경로 확인)
echo [STEP 3] 백엔드 브릿지 가동...
python server/bridge.py

pause