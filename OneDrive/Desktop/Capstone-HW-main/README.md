# Capstone-HW
캡스톤디자인 하드웨어

# 🏥 iKong: 실시간 생체 신호 모니터링 시스템

**iKong**은 mmwave센서를 활용하여 사용자의 심박수(BPM)와 호흡수(RPM)를 실시간으로 모니터링하고 시각화하는 프로젝트입니다.

## 🛠️ 주요 구성
- **MCU:** Seeed Studio XIAO ESP32-C6
- **OS/Gateway:** Raspberry Pi 5
- **Dashboard:** Flask 기반 웹 실시간 모니터링 화면

## 📂 파일 설명
- `hardware/ikong_log.yaml`: 센서의 와이파이 접속 및 데이터 정의가 담긴 ESPHome 설정 파일
- `server/app.py`: 실시간 데이터를 시각화하고 웹으로 띄워주는 파이썬 서버 코드

## 🚀 실행 방법
1. `hardware` 폴더의 설정을 이용해 센서에 펌웨어를 업로드합니다.
2. 라즈베리 파이에서 `python app.py`를 실행합니다.
3. 5인치 LCD 브라우저에서 실시간 대시보드를 확인합니다.

## 📷Seeed Studio MR60BHA2
https://www.mouser.kr/new/seeed-studio/seeed-studio-mr60bha2-sensor-kit/
센서 내부
<img width="1000" height="337" alt="image" src="https://github.com/user-attachments/assets/747325c8-c5a2-4273-8aea-2eb7a05ff7a8" />
