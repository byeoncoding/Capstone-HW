@echo off
cd /d "%~dp0"
title Fall Sensor - Server Logs

echo ==========================================
echo Starting Fall Detection Bridge Server...
echo ==========================================

python server/bridge_fall.py

pause