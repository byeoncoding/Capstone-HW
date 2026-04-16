#!/usr/bin/env bash
# iKong Heartrate Setup (Raspberry Pi/Linux)

echo "--- iKong Heartrate 시스템 가동 (Pi) ---"

# 1. 필수 패키지 설치 (requests 등 추가됨)
pip3 install esphome aioesphomeapi aiohttp certifi requests sseclient-py -q

# 2. config.env에서 정보 읽기 및 YAML 수정 (추가됨)
WIFI_SSID=$(grep WIFI_SSID config.env | cut -d'=' -f2 | tr -d '"')
WIFI_PASS=$(grep WIFI_PASSWORD config.env | cut -d'=' -f2 | tr -d '"')

python3 -c "import re; p='hardware/heartrate.yaml'; c=open(p).read(); c=re.sub(r'ssid: \".*\"', f'ssid: \"$WIFI_SSID\"', c); c=re.sub(r'password: \".*\"', f'password: \"$WIFI_PASS\"', c); open(p,'w').write(c)"

echo "[OK] 와이파이 설정 완료: $WIFI_SSID"

# 3. 브릿지 백그라운드 실행 (경로가 server/bridge.py 로 수정됨)
nohup python3 server/bridge.py > bridge.log 2>&1 &
echo "브릿지가 백그라운드에서 실행 중입니다. (PID: $!)"
echo "로그 확인: tail -f bridge.log"