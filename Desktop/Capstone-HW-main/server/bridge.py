import os
import requests
import json
import sseclient
import time
from datetime import datetime

# config.env 파일에서 환경 변수 로드
env_vars = {}
env_file = "config.env"
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

# 환경 변수 및 브릿지 설정 적용
HR_MDNS = env_vars.get("HR_MDNS", "heartview-hr.local")
SENSOR_URL = f"http://{HR_MDNS}/events"
BACKEND_URL = env_vars.get("BACKEND_URL", "https://api.chewbit.dev/api/vitals")
SERIAL_NUM = env_vars.get("HR_SERIAL", "HR-01")

print(f"\n{'='*60}")
print(f" [SYSTEM] HeartView HR Data Bridge Initialized")
print(f" [SERIAL] {SERIAL_NUM}")
print(f" [SOURCE] {SENSOR_URL}")
print(f" [TARGET] {BACKEND_URL}")
print(f"{'='*60}\n")

current_vitals = {"heartRate": 0, "breathRate": 0, "isPresent": False}

# 센서 연결 대기 및 재시도 함수
def wait_for_sensor():
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 센서({HR_MDNS}) 연결 시도 중...")
            res = requests.get(SENSOR_URL, stream=True, timeout=(5, 60))
            if res.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 센서 연결 성공! 데이터 수신을 시작합니다.")
                return res
        except requests.exceptions.RequestException:
            time.sleep(5)

# 데이터 수신 및 백엔드 전송 루프
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
                
                # 센서 데이터 파싱 및 상태 업데이트
                try:
                    if "heart_rate" in data_id:
                        new_hr = int(float(val))
                        if current_vitals["heartRate"] != new_hr:
                            current_vitals["heartRate"] = new_hr
                            is_updated = True
                    elif "breath_rate" in data_id:
                        new_br = int(float(val))
                        if current_vitals["breathRate"] != new_br:
                            current_vitals["breathRate"] = new_br
                            is_updated = True
                    elif "presence" in data_id or "target" in data_id:
                        new_presence = val if isinstance(val, bool) else str(val).lower() in ['true', 'on', '1']
                        if current_vitals["isPresent"] != new_presence:
                            current_vitals["isPresent"] = new_presence
                            is_updated = True
                except ValueError:
                    continue

                # 상태 변경 시 백엔드로 페이로드 전송
                if is_updated:
                    payload = {
                        "serialNum": SERIAL_NUM,
                        "heartRate": current_vitals["heartRate"],
                        "breathRate": current_vitals["breathRate"],
                        "isFallDetected": False,
                        "isPresent": current_vitals["isPresent"]
                    }
                    
                    try:
                        res = requests.post(BACKEND_URL, json=payload, timeout=5)
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        
                        if res.status_code in [200, 201]:
                            print(f"[{timestamp}] PUSH >> HR: {payload['heartRate']:3d} | BR: {payload['breathRate']:3d} | Presence: {payload['isPresent']}")
                        else:
                            print(f"[{timestamp}]  UPLINK_FAILURE | Status: {res.status_code} | Msg: {res.text}")
                            
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]  NETWORK_EXCEPTION (Backend): {e}")

    except requests.exceptions.ReadTimeout:
        time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n{'='*60}")
        print(f" [TERMINATED] Data Pipeline Bridge Shutting Down Safely...")
        print(f"{'='*60}")
        break 
    except Exception:
        time.sleep(3)