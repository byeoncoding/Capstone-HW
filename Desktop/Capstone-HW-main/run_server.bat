@echo off
cd /d "%~dp0"
title heartrate Sensor - Server Logs

echo ==========================================
echo Starting heartrate Detection Bridge Server...
echo ==========================================

python server/bridge_.py

pause