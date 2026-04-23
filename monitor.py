import requests
import json
import sseclient
import time
from datetime import datetime

SENSOR_URL = "http://capstone.local/events"

vitals = {"heartRate": 0, "breathRate": 0, "isPresent": False}

def dw(s):
    """한글/이모지는 터미널에서 2칸 차지 → 실제 표시 너비 계산"""
    w = 0
    for c in s:
        cp = ord(c)
        if (0xAC00 <= cp <= 0xD7AF or   # 한글 음절
            0x1100 <= cp <= 0x11FF or   # 한글 자모
            0x2E80 <= cp <= 0x9FFF or   # CJK
            0x1F300 <= cp <= 0x1FAFF):  # 이모지
            w += 2
        else:
            w += 1
    return w

def pad(s, width):
    """display width 기준으로 우측에 공백 채우기"""
    return s + ' ' * max(0, width - dw(s))

# 각 컬럼의 표시 너비
W1, W2, W3, W4 = 12, 12, 12, 8

def header():
    return (f"  {pad('시각', W1)}  {pad('심박수', W2)}"
            f"  {pad('호흡수', W3)}  {'재실여부'}")

def row(ts, hr, br, presence):
    return (f"  {pad(ts, W1)}  {pad(hr, W2)}"
            f"  {pad(br, W3)}  {pad(presence, W4)}")

print("=" * 56)
print("  iKong 실시간 생체신호 모니터")
print(f"  연결: {SENSOR_URL}")
print("=" * 56)
print(header())
print("-" * 56)

def wait_and_connect():
    while True:
        try:
            res = requests.get(SENSOR_URL, stream=True, timeout=5)
            if res.status_code == 200:
                return res
        except Exception:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 센서 연결 대기 중... 5초 후 재시도")
            time.sleep(5)

try:
    response = wait_and_connect()
    client = sseclient.SSEClient(response)

    for event in client.events():
        if event.event != 'state':
            continue

        data = json.loads(event.data)
        data_id = data.get('id', '')
        val = data.get('value', 0)

        if "heart_rate" in data_id:
            vitals["heartRate"] = float(val)
        elif "breath_rate" in data_id:
            vitals["breathRate"] = float(val)
        elif "presence" in data_id:
            vitals["isPresent"] = bool(val)

        if "heart_rate" in data_id:
            ts       = datetime.now().strftime('%H:%M:%S')
            hr       = f"{vitals['heartRate']:.0f} bpm"
            br       = f"{vitals['breathRate']:.0f} rpm"
            presence = "✅" if vitals["isPresent"] else "❌"
            print(row(ts, hr, br, presence))

except KeyboardInterrupt:
    print("\n" + "=" * 56)
    print("  모니터 종료")
    print("=" * 56)
except Exception as e:
    print(f"\n[오류] {e}")