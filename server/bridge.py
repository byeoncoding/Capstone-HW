import os
import requests
import json
import sseclient
import time
import statistics
from datetime import datetime
from collections import deque

# config.env 로드
env_vars = {}
env_file = os.path.join(os.path.dirname(__file__), "..", "config.env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
                except ValueError:
                    continue

HR_MDNS        = env_vars.get("HR_MDNS", "heartview-hr.local")
SENSOR_URL     = f"http://{HR_MDNS}/events"
BACKEND_URL    = env_vars.get("BACKEND_URL", "https://api.chewbit.dev/api/vitals")
SERIAL_NUM     = env_vars.get("HR_SERIAL", "HR-01")
SEND_INTERVAL  = 3
ALERT_COOLDOWN = 300

print(f"\n{'='*60}")
print(f" [BRIDGE] HeartView HR Data Bridge")
print(f" [SOURCE] {SENSOR_URL}")
print(f" [TARGET] {BACKEND_URL}")
print(f"{'='*60}\n")

hr_buf          = deque(maxlen=10)
br_buf          = deque(maxlen=10)
hr_baseline_buf = deque(maxlen=100)
br_baseline_buf = deque(maxlen=100)
current         = {"heartRate": 0, "breathRate": 0, "isPresent": False}
alert_start     = {"hr": None, "br": None}
last_sent       = 0
last_alert_time = 0
presence_since  = None

def check_emergency(hr_avg, br_avg):
    global last_alert_time

    if len(hr_baseline_buf) < 20:
        hr_baseline_buf.append(hr_avg)
        br_baseline_buf.append(br_avg)
        return None

    hr_base = statistics.mean(hr_baseline_buf)
    br_base = statistics.mean(br_baseline_buf)
    hr_std  = max(statistics.stdev(hr_baseline_buf), 5)
    br_std  = max(statistics.stdev(br_baseline_buf), 3)

    hr_z = abs(hr_avg - hr_base) / hr_std
    br_z = abs(br_avg - br_base) / br_std

    now = time.time()
    alert_level = None

    if hr_z > 2.5:
        if alert_start["hr"] is None:
            alert_start["hr"] = now
        duration = now - alert_start["hr"]
        hr_list = list(hr_buf)
        is_rising = len(hr_list) >= 2 and hr_list[-1] > hr_list[0]
        if duration > 120 and is_rising:
            alert_level = "심각"
        elif duration > 60:
            alert_level = "주의"
    else:
        alert_start["hr"] = None

    if hr_z > 2.5 and br_z > 2.5:
        alert_level = "심각"

    if hr_avg < 40 or hr_avg > 160:
        alert_level = "심각"
    if br_avg < 6 or br_avg > 35:
        alert_level = "심각"

    if alert_level and (now - last_alert_time) > ALERT_COOLDOWN:
        last_alert_time = now
        return {
            "level": alert_level,
            "hr": hr_avg,
            "br": br_avg,
            "hr_base": round(hr_base),
            "hr_z": round(hr_z, 1)
        }

    if hr_z < 1.5:
        hr_baseline_buf.append(hr_avg)
        br_baseline_buf.append(br_avg)

    return None

def wait_for_sensor():
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 센서 연결 시도: {HR_MDNS}")
            res = requests.get(SENSOR_URL, stream=True, timeout=(10, 60))
            if res.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 센서 연결 성공!")
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
                    if 40 <= hr <= 160:
                        hr_buf.append(hr)

                elif "breath_rate" in data_id:
                    br = int(float(val))
                    if 5 <= br <= 40:
                        br_buf.append(br)

                elif "presence" in data_id or "target" in data_id:
                    new_presence = val if isinstance(val, bool) \
                        else str(val).lower() in ['true', 'on', '1']
                    if new_presence and not current["isPresent"]:
                        presence_since = time.time()
                    elif not new_presence:
                        presence_since = None
                    current["isPresent"] = new_presence

            except ValueError:
                continue

            now = time.time()
            if now - last_sent >= SEND_INTERVAL and hr_buf and br_buf:

                if presence_since and (now - presence_since) < 20:
                    last_sent = now
                    continue

                hr_avg = round(sum(hr_buf) / len(hr_buf))
                br_avg = round(sum(br_buf) / len(br_buf))

                payload = {
                    "serialNum":      SERIAL_NUM,
                    "heartRate":      hr_avg,
                    "breathRate":     br_avg,
                    "isFallDetected": False,
                    "isPresent":      current["isPresent"]
                }

                try:
                    res = requests.post(BACKEND_URL, json=payload, timeout=5)
                    ts = datetime.now().strftime('%H:%M:%S')
                    print(f"[{ts}] HR: {hr_avg:3d} | BR: {br_avg:3d} | "
                          f"Present: {current['isPresent']} → {res.status_code}")
                except Exception as e:
                    print(f"[ERROR] 백엔드 전송 실패: {e}")

                alert = check_emergency(hr_avg, br_avg)
                if alert:
                    ts = datetime.now().strftime('%H:%M:%S')
                    print(f"[{ts}] ⚠ ALERT {alert['level']} | "
                          f"HR: {alert['hr']} (기준: {alert['hr_base']}, "
                          f"편차: {alert['hr_z']}σ)")

                last_sent = now

    except requests.exceptions.ReadTimeout:
        time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n[TERMINATED] Bridge 종료")
        break
    except Exception as e:
        print(f"[ERROR] {e} → 3초 후 재시도")
        time.sleep(3)
