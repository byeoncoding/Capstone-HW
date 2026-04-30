from flask import Flask, render_template_string
import random

app = Flask(__name__)

@app.route('/')
def index():
    bpm = random.randint(65, 85)
    rpm = random.randint(15, 22)
    
    html_content = f'''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="1">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ 
                background-color: #000; color: #fff; font-family: sans-serif; 
                display: flex; justify-content: center; align-items: center; 
                height: 100vh; width: 100vw; overflow: hidden;
            }}
            .container {{ text-align: center; transform: scale(0.95); }}
            h1 {{ color: #00ff88; font-size: 2rem; margin-bottom: 25px; font-weight: bold; }}
            .card-wrapper {{ display: flex; justify-content: center; gap: 20px; margin-bottom: 30px; }}
            .card {{ 
                border: 1px solid #333; border-radius: 18px; padding: 15px; 
                width: 250px; background: #111; box-shadow: 0 10px 30px rgba(0,0,0,0.8);
            }}
            .label {{ font-size: 1.1rem; color: #888; margin-bottom: 8px; }}
            .data {{ font-size: 4rem; font-weight: 900; display: flex; align-items: center; justify-content: center; gap: 12px; }}
            .unit {{ font-size: 0.8rem; color: #444; }}
            .status-btn {{
                background-color: #00c853; color: #fff; border-radius: 50px;
                padding: 10px 50px; font-size: 1.4rem; font-weight: bold;
            }}
            @keyframes heartbeat {{
                0% {{ transform: scale(1); }}
                15% {{ transform: scale(1.2); }}
                30% {{ transform: scale(1); }}
                100% {{ transform: scale(1); }}
            }}
            .heart {{ animation: heartbeat 1.2s infinite; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 iKong Live Monitoring</h1>
            <div class="card-wrapper">
                <div class="card">
                    <div class="label">심박수 (BPM)</div>
                    <div class="data"><span class="heart">💓</span>{bpm}<span class="unit">BPM</span></div>
                </div>
                <div class="card">
                    <div class="label">호흡수 (RPM)</div>
                    <div class="data">🫁 {rpm}<span class="unit">RPM</span></div>
                </div>
            </div>
            <div class="status-btn">상태: 정상</div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html_content)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
