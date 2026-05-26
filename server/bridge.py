#!/usr/bin/env python3
"""
HeartView Bridge Server v3.0
Pi 역할: 노이즈 필터링 (spike_reject + IQR) → 백엔드 전달
이상감지는 백엔드가 전담. Pi는 낙상/수동 알림만 직접 전송.
"""

import os, time, threading
import requests
from flask import Flask, request, jsonify, send_from_directory

# ── 환경변수 로드 ──────────────────────────────────────────────
def load_env(path):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

env_vars = load_env(os.path.expanduser('~/Capstone-HW/config.env'))

BACKEND_URL     = env_vars.get('BACKEND_URL', 'https://api.chewbit.dev/api/vitals')
ALERT_URL       = env_vars.get('ALERT_URL',   'https://api.chewbit.dev/api/emergency-event')
SERIAL_NUM      = env_vars.get('HR_SERIAL',   'HR-01')
RECV_PORT       = int(env_vars.get('RECV_PORT', 8888))
FALL_SERIAL_NUM = 'FALL-01'

# ── 필터 설정 (노이즈 제거용만) ────────────────────────────────
MAX_HR_SPIKE  = 25   # bpm — single-frame spike rejection threshold
MAX_HR_SLEW   = 12   # bpm — max change per reading (slew rate limiter)
MAX_BR_SPIKE  = 8    # breaths/min
MIN_BR        = 8    # physiological minimum (below = sensor noise)
FALL_COOLDOWN = 180  # fall alert cooldown (seconds)
WARMUP        = 10   # ignore first N readings (sensor stabilization)

# ── 상태 변수 ──────────────────────────────────────────────────
last_hr      = None
last_br      = None
last_present = True
warmup_count = 0

fall_detected      = False
last_fall_ts       = 0
last_alert_sent_ts = 0

lock = threading.Lock()

# ── 필터 함수 ──────────────────────────────────────────────────
def spike_reject(new_val, last_val, max_spike):
    """단발 스파이크 제거 — 튀면 이전 값 유지"""
    if last_val is None:
        return new_val
    return last_val if abs(new_val - last_val) > max_spike else new_val

def slew_limit(new_val, last_val, max_delta):
    """슬루레이트 리미터 — 급격한 변화를 서서히 따라감"""
    if last_val is None:
        return new_val
    diff = new_val - last_val
    if abs(diff) > max_delta:
        return last_val + max_delta * (1 if diff > 0 else -1)
    return new_val


# ── 알림 전송 (낙상/수동만) ────────────────────────────────────
def send_alert(event_type, hr_val, br_val, serial_num=None):
    global last_alert_sent_ts
    now = time.time()
    if event_type != 'manual_alert' and now - last_alert_sent_ts < FALL_COOLDOWN:
        print(f"[ALERT] 쿨다운 중 ({int(FALL_COOLDOWN-(now-last_alert_sent_ts))}초 남음)")
        return
    last_alert_sent_ts = now
    payload = {
        "serialNum":  serial_num if serial_num else SERIAL_NUM,
        "eventType":  event_type,
        "heartRate":  hr_val,
        "breathRate": br_val,
        "timestamp":  int(now * 1000),
    }
    try:
        r = requests.post(ALERT_URL, json=payload, timeout=5)
        print(f"[ALERT] {event_type} 전송 → {r.status_code}")
    except Exception as e:
        print(f"[ALERT] 전송 실패: {e}")

# ── Flask ──────────────────────────────────────────────────────
app = Flask(__name__, static_folder=os.path.expanduser('~/Capstone-HW/server'))

@app.route('/')
def index():
    return send_from_directory(os.path.expanduser('~/Capstone-HW/server'), 'dashboard.html')

@app.route('/dashboard.html')
def dashboard():
    return send_from_directory(os.path.expanduser('~/Capstone-HW/server'), 'dashboard.html')

@app.route('/data', methods=['POST'])
def receive_data():
    global last_hr, last_br, last_present, fall_detected

    data = request.get_json(silent=True) or {}
    ts   = time.strftime('%H:%M:%S')

    raw_hr        = data.get('hr')
    raw_br        = data.get('br')
    present       = data.get('present', True)
    sensor_serial = data.get('serialNum', SERIAL_NUM)

    if raw_hr is None or raw_br is None:
        return jsonify({"status": "missing"}), 400

    with lock:
        global warmup_count

        # 1) 워밍업 — 첫 N개 버림
        warmup_count += 1
        if warmup_count <= WARMUP:
            return jsonify({"status": "warmup"}), 200

        # 2) spike_reject + 오프셋 보정
        hr_raw_f = float(raw_hr)
        br_raw_f = float(raw_br)
        hr_rejected = last_hr is not None and abs(hr_raw_f - last_hr) > MAX_HR_SPIKE
        br_rejected = last_br is not None and (abs(br_raw_f - last_br) > MAX_BR_SPIKE or br_raw_f < MIN_BR)

        hr_spiked = spike_reject(hr_raw_f, last_hr, MAX_HR_SPIKE)
        hr_final  = round(slew_limit(hr_spiked, last_hr, MAX_HR_SLEW))
        br_final  = max(MIN_BR, round(spike_reject(br_raw_f, last_br, MAX_BR_SPIKE)))

        # 3) 상태 업데이트
        last_hr      = hr_final
        last_br      = br_final
        last_present = present

        # 스파이크 제거된 경우 출력 생략
        if not hr_rejected and not br_rejected:
            print(f"[{ts}] HR:{hr_final}  BR:{br_final}  present:{present}")

    # 4) 백엔드 전달 (이상감지는 백엔드가 판단)
    payload = {
        "serialNum":      sensor_serial,
        "heartRate":      hr_final,
        "breathRate":     br_final,
        "isFallDetected": fall_detected,
        "isPresent":      present,
    }
    try:
        requests.post(BACKEND_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"[BACKEND] 전송 실패: {e}")

    return jsonify({"status": "ok", "hr": hr_final, "br": br_final})

@app.route('/fall', methods=['POST'])
def receive_fall():
    global fall_detected, last_fall_ts, last_alert_sent_ts

    data     = request.get_json(silent=True) or {}
    is_fall  = bool(data.get('fall',  False))
    is_human = bool(data.get('human', False))
    ts       = time.strftime('%H:%M:%S')

    print(f"[{ts}] FALL: fall={is_fall}, human={is_human}")

    with lock:
        if is_fall and not fall_detected:
            fall_detected      = True
            last_fall_ts       = time.time()
            last_alert_sent_ts = 0  # 쿨다운 무시
            send_alert('fall_detected', last_hr or 0, last_br or 0, serial_num=FALL_SERIAL_NUM)
        elif not is_fall and fall_detected:
            if time.time() - last_fall_ts > 10:
                fall_detected = False

    # 낙상 전용 페이로드 (HR/BR 없음 → 백엔드 오탐 방지)
    fall_payload = {
        "serialNum":      FALL_SERIAL_NUM,
        "isFallDetected": is_fall,
        "isPresent":      is_human,
    }
    try:
        requests.post(BACKEND_URL, json=fall_payload, timeout=5)
    except Exception as e:
        print(f"[FALL PUSH] 실패: {e}")

    return jsonify({"status": "ok"})

@app.route('/manual-alert', methods=['POST'])
def manual_alert():
    global last_alert_sent_ts
    last_alert_sent_ts = 0
    send_alert('manual_alert', last_hr or 0, last_br or 0, serial_num=SERIAL_NUM)
    return jsonify({"status": "sent"})

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "hr":      last_hr,
        "br":      last_br,
        "present": last_present,
        "fall":    fall_detected,
    })

# ── 시작 배너 ──────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 48)
    print("  HeartView Bridge  v3.0")
    print("  Role: Filter + Forward (anomaly -> backend)")
    print("=" * 48)
    print(f" [SERIAL]  HR-01       (HR/BR sensor)")
    print(f" [SERIAL]  {SERIAL_NUM}       (HR/BR sensor)")
    print(f" [SERIAL]  {FALL_SERIAL_NUM}   (fall sensor)")
    print(f" [BACKEND] {BACKEND_URL}")
    print(f" [PORT]    {RECV_PORT}")
    print("=" * 48)
    app.run(host='0.0.0.0', port=RECV_PORT, debug=False)
