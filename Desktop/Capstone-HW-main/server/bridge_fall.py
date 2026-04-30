import os
import requests
import json
import sseclient
import time
from datetime import datetime

# 1. config_fall.env 파일에서 설정 자동 읽기
env_vars = {}
env_file = "config_fall.env"
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

SENSOR_SERIAL = )
SENSOR_MDNS = ""
BACKEND_URL = ""
SENSOR_URL = f""

print(f"\n{'='*60}")
print(f" [SYSTEM] Fall Detection Bridge Initialized")
print(f" [SERIAL] {SENSOR_SERIAL}")
print(f" [SOURCE] {SENSOR_URL}")
print(f"{'='*60}\n")

current_state = {"isFallDetected": False, "isPresent": False}

def wait_for_sensor():
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to {SENSOR_MDNS}...")
            res = requests.get(SENSOR_URL, stream=True, timeout=(5, 60))
            if res.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Connected Successfully!")
                return res
        except requests.exceptions.RequestException:
            time.sleep(5)

while True:
    try:
        response = wait_for_sensor()
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            if event.event == 'state':
                raw_data = json.loads(event.data)
                data_id = raw_data.get('id', '')
                val = raw_data.get('value')
                
                if val is None or val == "NaN" or val == "":
                    continue

                is_updated = False
                
                # 낙상 감지 처리
                if "fall_detected" in data_id.lower():
                    new_val = val if isinstance(val, bool) else str(val).lower() in ['true', 'on', '1']
                    if current_state["isFallDetected"] != new_val:
                        current_state["isFallDetected"] = new_val
                        is_updated = True
                            
                # 재실 감지 처리
                elif "presence_detected" in data_id.lower() or "people_exist" in data_id.lower():
                    new_val = val if isinstance(val, bool) else str(val).lower() in ['true', 'on', '1']
                    if current_state["isPresent"] != new_val:
                        current_state["isPresent"] = new_val
                        is_updated = True

                # 백엔드 전송
                if is_updated:
                    payload = {
                        "serialNum": SENSOR_SERIAL,
                        "heartRate": 0,
                        "breathRate": 0,
                        "isFallDetected": current_state["isFallDetected"],
                        "isPresent": current_state["isPresent"]
                    }
                    
                    try:
                        requests.post(BACKEND_URL, json=payload, timeout=5)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] PUSH >> Fall: {payload['isFallDetected']} | Presence: {payload['isPresent']}")
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] NETWORK_EXCEPTION: {e}")

    except requests.exceptions.ReadTimeout:
        time.sleep(2)
    except KeyboardInterrupt:
        break 
    except Exception:
        time.sleep(3)