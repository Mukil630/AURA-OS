@echo off
chcp 65001 >nul
title JARVIS Telegram Mobile Gateway Daemon
echo ========================================================
echo   ⚡ STARTING JARVIS TELEGRAM GATEWAY DAEMON
echo   Phase 12 Governed + 3-Voice Personas + Reminders
echo ========================================================
echo.

cd /d C:\Users\mukil\mukil-master-agent
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONPATH=C:\Users\mukil\mukil-master-agent;%PYTHONPATH%
python app\connectors\telegram\daemon.py

pause
