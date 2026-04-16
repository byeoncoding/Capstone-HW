import requests
import json
import sseclient
import time
from datetime import datetime

# [수정됨] 슬래시 오류 수정 및 mDNS(capstone.local) 적용
# 내일 IP 주소를 몰라도 자동으로 센서를 찾아냅니다!
SENSOR_URL = "http://capstone.local/events" 
BACKEND_URL = "https://api.chewbit.dev/api/vitals"

print(f"\n{'='*60}")
print(f" [SYSTEM] IoT Data Bridge Pipeline Initialized")
print(f" [SOURCE] {SENSOR_URL}")
print(f" [TARGET] {BACKEND_URL}")
print(f"{'='*60}\n")

current_vitals = {"heartRate": 0, "breathRate": 0, "isPresent": False}

try:
    response = requests.get(SENSOR_URL, stream=True)
    client = sseclient.SSEClient(response)
    
    for event in client.events():
        if event.event == 'state':
            raw_data = json.loads(event.data)
            data_id = raw_data.get('id', '')
            
            if "heart_rate" in data_id:
                current_vitals["heartRate"] = int(raw_data.get("value", 0))
            elif "breath_rate" in data_id:
                current_vitals["breathRate"] = int(raw_data.get("value", 0))
            elif "presence" in data_id:
                current_vitals["isPresent"] = bool(raw_data.get("value", False))

            if "heart_rate" in data_id:
                payload = {
                    "serialNum": "RPI-TEST-01",
                    "heartRate": current_vitals["heartRate"],
                    "breathRate": current_vitals["breathRate"],
                    "isFallDetected": False,
                    "isPresent": current_vitals["isPresent"]
                }
                
                start_time = time.time() # 응답 속도 체크용
                try:
                    res = requests.post(BACKEND_URL, json=payload, timeout=5)
                    elapsed = (time.time() - start_time) * 1000 # ms 단위
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    
                    if res.status_code in [200, 201]:
                       
                        print(f"[{timestamp}] PUSH >> Serial: {payload['serialNum']} | HR: {payload['heartRate']} bpm | BR: {payload['breathRate']} rpm | Presence: {payload['isPresent']}")
                        print(f"            STATUS: {res.status_code} OK | Latency: {elapsed:.2f}ms | Connection: Persistent")
                        print(f"{'-'*60}")
                    else:
                        print(f"[{timestamp}] ⚠️ UPLINK_FAILURE | Status: {res.status_code} | Msg: {res.text}")
                        
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ NETWORK_EXCEPTION: {e}")

except KeyboardInterrupt:
    print(f"\n{'='*60}")
    print(f" [TERMINATED] Data Pipeline Bridge Shutting Down Safely...")
    print(f"{'='*60}")
except Exception as e:
    print(f"\n [CRITICAL_ERROR] {e}")