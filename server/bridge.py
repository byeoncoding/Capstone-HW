import os
import requests
import json
import sseclient
import time
from datetime import datetime
from collections import deque

# config.env 로드
env_vars = {}
if os.path.exists("config.env"):
    with open("config.env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
                except ValueError:
                    continue

HR_MDNS      = env_vars.get("HR_MDNS", "heartview-hr.local")
SENSOR_URL   = f"http://{HR_MDNS}/events"
BACKEND_URL  = env_vars.get("BACKEND_URL", "https://api.chewbit.dev/api/vitals")
SERIAL_NUM   = env_vars.get("HR_SERIAL", "HR-01")
SEND_INTERVAL = 3  # 초: 몇 초마다 백엔드에 전송할지

print(f"\n{'='*60}")
print(f" [BRIDGE] {SENSOR_URL} → {BACKEND_URL}")
print(f"{'='*60}\n")

# 2차 버퍼 (ESPHome 필터 이후 추가 안정화)
hr_buf  = deque(maxlen=10)
br_buf  = deque(maxlen=10)

current = {"heartRate": 0, "breathRate": 0, "isPresent": False}
last_sent = 0

def wait_for_sensor():
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 센서 연결 시도: {HR_MDNS}")
            res = requests.get(SENSOR_URL, stream=True, timeout=(10, 60))
            if res.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 연결 성공")
                return res
        except requests.exceptions.RequestException as e:
            print(f"[WARN] 연결 실패: {e} → 5초 후 재시도")
            time.sleep(5)

while True:
    try:
        response = wait_for_sensor()
        client = sseclient.SSEClient(response)

        for event in client.events():
            if event.event != 'state':
                continue

            raw = json.loads(event.data)
            data_id = raw.get('id', '')
            val = raw.get('value')

            if val is None or val in ("NaN", ""):
                continue

            try:
                if "heart_rate" in data_id:
                    hr = int(float(val))
                    if 40 <= hr <= 150:      # 정상 범위만 버퍼에 추가
                        hr_buf.append(hr)

                elif "breath_rate" in data_id:
                    br = int(float(val))
                    if 5 <= br <= 40:
                        br_buf.append(br)

                elif "presence" in data_id or "target" in data_id:
                    current["isPresent"] = val if isinstance(val, bool) \
                        else str(val).lower() in ['true', 'on', '1']

            except ValueError:
                continue

            # SEND_INTERVAL 초마다 평균값 전송
            now = time.time()
            if now - last_sent >= SEND_INTERVAL and hr_buf and br_buf:
                hr_avg = round(sum(hr_buf) / len(hr_buf))
                br_avg = round(sum(br_buf) / len(br_buf))

                payload = {
                    "serialNum":     SERIAL_NUM,
                    "heartRate":     hr_avg,
                    "breathRate":    br_avg,
                    "isFallDetected": False,
                    "isPresent":     current["isPresent"]
                }

                try:
                    res = requests.post(BACKEND_URL, json=payload, timeout=5)
                    ts = datetime.now().strftime('%H:%M:%S')
                    print(f"[{ts}] HR: {hr_avg:3d} | BR: {br_avg:3d} | "
                          f"Present: {current['isPresent']} → {res.status_code}")
                except Exception as e:
                    print(f"[ERROR] 백엔드 전송 실패: {e}")

                last_sent = now

    except requests.exceptions.ReadTimeout:
        time.sleep(2)
    except KeyboardInterrupt:
        print("\n[TERMINATED] Bridge 종료")
        break
    except Exception as e:
        print(f"[ERROR] {e} → 3초 후 재시도")
        time.sleep(3)