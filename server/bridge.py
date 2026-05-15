import os
import requests
import time
import statistics
from collections import deque
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

env_vars = {}
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.env")
if not os.path.exists(env_file):
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

BACKEND_URL = env_vars.get("BACKEND_URL", "https://api.chewbit.dev/api/vitals")
SERIAL_NUM  = env_vars.get("HR_SERIAL", "HR-01")
RECV_PORT   = int(env_vars.get("RECV_PORT", 8888))

app = Flask(__name__)

current  = {"heartRate": 0, "breathRate": 0, "isPresent": False}
hr_buf   = deque(maxlen=10)
br_buf   = deque(maxlen=10)
last_hr  = None
last_br  = None
MAX_HR_DELTA = 8
MAX_BR_DELTA = 3

def iqr_mean(buf):
    if len(buf) < 4:
        return statistics.median(buf)
    s  = sorted(buf)
    n  = len(s)
    q1 = s[n // 4]
    q3 = s[(n * 3) // 4]
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    clean = [v for v in s if lo <= v <= hi]
    return statistics.mean(clean) if clean else statistics.median(s)

def clamp_delta(new_val, last_val, max_delta):
    if last_val is None:
        return new_val
    delta = new_val - last_val
    if abs(delta) > max_delta:
        return last_val + max_delta * (1 if delta > 0 else -1)
    return new_val

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=800, initial-scale=1.0">
<title>HeartView Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; cursor:none !important; }
  body {
    font-family:'Segoe UI','Noto Sans KR',sans-serif;
    background:#0b1208;
    color:#d8edca;
    width:100vw; height:100vh; overflow:hidden;
    display:flex; flex-direction:column; gap:8px; padding:8px;
  }

  .main-row { display:flex; gap:8px; flex:1; min-height:0; }
  .left-col  { display:flex; flex-direction:column; gap:8px; flex:1; min-width:0; }

  /* ── 날씨 ── */
  .weather-card {
    background:linear-gradient(135deg,#111a08,#1a280c);
    border-radius:14px; padding:10px 14px; flex:1; min-height:0;
    display:flex; flex-direction:column; justify-content:space-around;
    border:1px solid #4a7a28; overflow:hidden;
  }
  .weather-location { font-size:2.4vw; color:#8EC96D; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .weather-main     { display:flex; align-items:center; gap:8px; }
  .weather-icon     { font-size:7vw; line-height:1; }
  .weather-temp     { font-size:9vw; font-weight:700; color:#f0fff0; letter-spacing:-1px; line-height:1; }
  .weather-desc     { font-size:2.6vw; color:#b0d888; }
  .weather-detail   { display:flex; gap:10px; font-size:2.2vw; color:#8EC96D; flex-wrap:wrap; }

  /* ── 날짜/시계 ── */
  .datetime-card {
    background:#111808;
    border-radius:14px; padding:10px 14px; flex:1; min-height:0;
    border:1px solid #3a5a1a;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:6px; overflow:hidden;
  }
  .dt-date { font-size:3.8vw; font-weight:600; color:#c8e8a8; text-align:center; }
  .dt-time { font-size:5.5vw; font-weight:700; color:#8EC96D; text-align:center; letter-spacing:1px; white-space:nowrap; }

  /* ── 응급 버튼 (빨간색 유지) ── */
  .alert-btn {
    background:linear-gradient(160deg,#8b0000,#e74c3c,#8b0000);
    border:none; border-radius:16px; color:#fff;
    flex: 0 0 50%; min-height:0;
    cursor:none !important;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:8px;
    -webkit-tap-highlight-color:transparent; touch-action:manipulation;
    box-shadow:0 0 30px rgba(231,76,60,0.5);
    transition:filter 0.1s; overflow:hidden; padding:10px;
  }
  .alert-btn:active { filter:brightness(0.75); }
  .alert-btn.sent {
    background:linear-gradient(160deg,#0a4a20,#27ae60,#0a4a20);
    box-shadow:0 0 30px rgba(39,174,96,0.5);
  }
  .alert-icon   { font-size:9vw; line-height:1; }
  .alert-label  { font-size:6vw; font-weight:900; line-height:1.25; text-align:center; }
  .alert-status { font-size:2vw; color:rgba(255,255,255,0.75); text-align:center; }

  /* ── 바이탈 ── */
  .vital-row { display:flex; gap:8px; height:72px; flex-shrink:0; }
  .vital-card {
    flex:1; background:#111808; border-radius:12px;
    display:flex; align-items:center; justify-content:center;
    gap:10px; border:1px solid #3a5a1a;
  }
  .vital-icon  { font-size:24px; }
  .vital-label { font-size:9px; color:#5a8a30; text-transform:uppercase; letter-spacing:1px; }
  .vital-value { font-size:28px; font-weight:700; color:#d8edca; line-height:1; }
  .vital-unit  { font-size:10px; color:#7aaa45; margin-top:1px; }
</style>
</head>
<body>

<div class="main-row">
  <div class="left-col">
    <div class="weather-card">
      <div class="weather-location" id="wLocation">📍 전주</div>
      <div class="weather-main">
        <div class="weather-icon" id="wIcon">⏳</div>
        <div>
          <div class="weather-temp" id="wTemp">--°</div>
          <div class="weather-desc" id="wDesc">불러오는 중</div>
        </div>
      </div>
      <div class="weather-detail">
        <span id="wHumid">💧 --%</span>
        <span id="wWind">💨 -- km/h</span>
        <span id="wFeels">체감 --°</span>
      </div>
    </div>

    <div class="datetime-card">
      <div class="dt-date" id="dtDate"></div>
      <div class="dt-time" id="dtTime"></div>
    </div>
  </div>

  <button class="alert-btn" id="alertBtn" onclick="sendAlert()">
    <div class="alert-icon">🆘</div>
    <div class="alert-label" id="alertLabel">응급 알림<br>보내기</div>
    <div class="alert-status" id="alertStatus">누르면 즉시 전송</div>
  </button>
</div>

<div class="vital-row">
  <div class="vital-card">
    <div class="vital-icon">❤️</div>
    <div>
      <div class="vital-label">Heart Rate</div>
      <div class="vital-value" id="hrVal">--</div>
      <div class="vital-unit">bpm</div>
    </div>
  </div>
  <div class="vital-card">
    <div class="vital-icon">🫁</div>
    <div>
      <div class="vital-label">Breath Rate</div>
      <div class="vital-value" id="brVal">--</div>
      <div class="vital-unit">회/분</div>
    </div>
  </div>
  <div class="vital-card">
    <div class="vital-icon">🧍</div>
    <div>
      <div class="vital-label">재실여부</div>
      <div class="vital-value" id="presVal" style="font-size:20px">--</div>
    </div>
  </div>
</div>

<script>
const WMO = {
  0:['☀️','맑음'],1:['🌤️','대체로 맑음'],2:['⛅','구름 조금'],3:['☁️','흐림'],
  45:['🌫️','안개'],48:['🌫️','안개'],
  51:['🌦️','이슬비'],53:['🌦️','이슬비'],55:['🌧️','이슬비'],
  61:['🌧️','비'],63:['🌧️','비'],65:['🌧️','강한 비'],
  71:['🌨️','눈'],73:['🌨️','눈'],75:['❄️','강한 눈'],77:['🌨️','눈발'],
  80:['🌦️','소나기'],81:['🌦️','소나기'],82:['⛈️','강한 소나기'],
  95:['⛈️','뇌우'],96:['⛈️','뇌우'],99:['⛈️','뇌우'],
};

function fetchWeather(lat,lon){
  fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=auto`)
    .then(r=>r.json()).then(d=>{
      const c=d.current,[icon,desc]=WMO[c.weather_code]||['🌡️','알 수 없음'];
      document.getElementById('wIcon').textContent =icon;
      document.getElementById('wTemp').textContent =Math.round(c.temperature_2m)+'°';
      document.getElementById('wDesc').textContent =desc;
      document.getElementById('wHumid').textContent='💧 '+c.relative_humidity_2m+'%';
      document.getElementById('wWind').textContent ='💨 '+Math.round(c.wind_speed_10m)+' km/h';
      document.getElementById('wFeels').textContent='체감 '+Math.round(c.apparent_temperature)+'°';
    }).catch(()=>{document.getElementById('wDesc').textContent='날씨 로드 실패';});
}

// 전주 좌표 고정
fetchWeather(35.8242, 127.1480);
setInterval(()=>fetchWeather(35.8242, 127.1480), 600000);

function updateDateTime(){
  const now=new Date();
  const y=now.getFullYear(),mo=now.getMonth()+1,d=now.getDate();
  const h=now.getHours(),mi=String(now.getMinutes()).padStart(2,'0');
  const ampm=h<12?'오전':'오후',h12=h%12||12;
  document.getElementById('dtDate').textContent=y+'년 '+mo+'월 '+d+'일';
  document.getElementById('dtTime').textContent=ampm+' '+h12+'시 '+mi+'분';
}

function pollVitals(){
  fetch('/state').then(r=>r.json()).then(d=>{
    document.getElementById('hrVal').textContent =d.isPresent?(d.heartRate||'--'):'--';
    document.getElementById('brVal').textContent =d.isPresent?(d.breathRate||'--'):'--';
    document.getElementById('presVal').textContent=d.isPresent?'🟢 감지':'⚫ 없음';
  }).catch(()=>{});
}

function sendAlert(){
  const btn=document.getElementById('alertBtn'),
        status=document.getElementById('alertStatus'),
        label=document.getElementById('alertLabel');
  btn.disabled=true; status.textContent='전송 중...';
  fetch('/manual-alert',{method:'POST'}).then(r=>r.json()).then(()=>{
    btn.classList.add('sent'); label.innerHTML='전송<br>완료';
    status.textContent='보호자에게 알림이 전송되었습니다';
    setTimeout(()=>{
      btn.classList.remove('sent'); label.innerHTML='응급 알림<br>보내기';
      status.textContent='누르면 즉시 전송'; btn.disabled=false;
    },4000);
  }).catch(()=>{ status.textContent='전송 실패 — 다시 시도'; btn.disabled=false; });
}

updateDateTime();
setInterval(updateDateTime,1000);
pollVitals();
setInterval(pollVitals,3000);
</script>
</body>
</html>"""


@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/data', methods=['POST'])
def receive_data():
    global current, last_hr, last_br
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no data"}), 400
    hr       = int(data.get('hr',  0))
    br       = int(data.get('br', 0))
    presence = bool(data.get('present', False))
    if not presence:
        hr_buf.clear(); br_buf.clear()
        last_hr = None; last_br = None
        current.update({"heartRate":0,"breathRate":0,"isPresent":False})
        return jsonify({"ok": True})
    if hr > 0: hr_buf.append(hr)
    if br > 0: br_buf.append(br)
    current['isPresent'] = presence
    if not hr_buf or not br_buf:
        return jsonify({"ok": True})
    hr_final = round(clamp_delta(iqr_mean(hr_buf), last_hr, MAX_HR_DELTA))
    br_final = round(clamp_delta(iqr_mean(br_buf), last_br, MAX_BR_DELTA))
    last_hr  = hr_final
    last_br  = br_final
    current['heartRate']  = hr_final
    current['breathRate'] = br_final
    payload = {"serialNum":SERIAL_NUM,"heartRate":hr_final,"breathRate":br_final,"isFallDetected":False,"isPresent":presence}
    try:
        res = requests.post(BACKEND_URL, json=payload, timeout=5)
        ts  = datetime.now().strftime('%H:%M:%S')
        if res.status_code in [200,201]:
            print(f"[{ts}] PUSH >> HR: {hr_final:3d} | BR: {br_final:3d} | Presence: {presence}")
        else:
            print(f"[{ts}]  FAIL {res.status_code} | {res.text[:80]}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}]  NETWORK_ERR: {e}")
    return jsonify({"ok": True})

@app.route('/state')
def state():
    return jsonify(current)

@app.route('/manual-alert', methods=['POST'])
def manual_alert():
    alert_url = BACKEND_URL.rsplit('/vitals',1)[0]+'/alert'
    payload   = {"serialNum":SERIAL_NUM,"type":"manual","timestamp":datetime.now().isoformat()}
    try:
        res = requests.post(alert_url, json=payload, timeout=5)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ALERT >> {res.status_code}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f" [SYSTEM] HeartView Bridge (Flask)")
    print(f" [SERIAL] {SERIAL_NUM}")
    print(f" [TARGET] {BACKEND_URL}")
    print(f" [PORT]   {RECV_PORT}")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=RECV_PORT, debug=False)
