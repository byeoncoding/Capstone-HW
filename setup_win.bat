@echo off
:: 한글 깨짐 방지 (UTF-8 인코딩 강제 적용)
chcp 65001 >nul

:: 관리자 권한 실행 시 경로 꼬임 방지
cd /d "%~dp0"

setlocal enabledelayedexpansion
title iKong Heartrate Auto-Config (Windows)

echo ==========================================
echo   iKong 심박 센서 자동화 시스템 (Windows)
echo ==========================================

:: 1. config.env 파일 확인
if not exist config.env (
    echo [ERROR] config.env 파일이 같은 폴더에 없습니다!
    pause
    exit
)

for /f "tokens=1* delims==" %%a in (config.env) do (
    if "%%a"=="WIFI_SSID" set WIFI_SSID=%%b
    if "%%a"=="WIFI_PASSWORD" set WIFI_PASSWORD=%%b
)

:: 따옴표 제거 (이 값들이 환경변수로 파이썬에 전달됩니다)
set WIFI_SSID=%WIFI_SSID:"=%
set WIFI_PASSWORD=%WIFI_PASSWORD:"=%

echo [INFO] 설정된 와이파이: %WIFI_SSID%

:: 🔥 [해결책 1] 내 컴퓨터에 맞는 파이썬 명령어(python 또는 py) 자동 찾기
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python
) else (
    set PY_CMD=py
)

:: 2. 필수 패키지 설치
echo [STEP 0] 필수 패키지를 확인합니다...
%PY_CMD% -m pip install esphome aioesphomeapi aiohttp certifi requests sseclient-py -q

:: 3. YAML 파일 확인 및 자동 치환
echo [STEP 1] hardware/heartrate.yaml 업데이트 중...

if not exist hardware\heartrate.yaml (
    echo [ERROR] hardware 폴더 안에 heartrate.yaml 파일이 없습니다! 
    pause
    exit
)

:: 🔥 [해결책 2] 명령 프롬프트의 따옴표 꼬임을 막기 위해, 임시 파이썬 파일을 직접 만듭니다.
echo import os, re > update_yaml.py
echo s = os.environ.get('WIFI_SSID', '') >> update_yaml.py
echo p = os.environ.get('WIFI_PASSWORD', '') >> update_yaml.py
echo f = 'hardware/heartrate.yaml' >> update_yaml.py
echo c = open(f, 'r', encoding='utf-8').read() >> update_yaml.py
echo q = chr(34) >> update_yaml.py
echo c = re.sub(r'ssid: ' + q + '.*' + q, f'ssid: {q}{s}{q}', c) >> update_yaml.py
echo c = re.sub(r'password: ' + q + '.*' + q, f'password: {q}{p}{q}', c) >> update_yaml.py
echo open(f, 'w', encoding='utf-8').write(c) >> update_yaml.py

:: 방금 만든 파이썬 스크립트 실행
%PY_CMD% update_yaml.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 파이썬 스크립트 실행 중 알 수 없는 오류가 발생했습니다.
    pause
    exit
)

:: 쓴맛을 본 임시 파일은 깨끗하게 삭제합니다.
del update_yaml.py
echo [OK] 와이파이 정보 자동 업데이트 완료!

:: 4. ESPHome 업로드
echo [STEP 2] 센서 펌웨어 업로드 시작...
%PY_CMD% -m esphome run hardware/heartrate.yaml

:: 5. 브릿지 실행
echo [STEP 3] 백엔드 브릿지 가동...
%PY_CMD% server/bridge.py

pause