@echo off
title JARVIS Autonomous Telegram Voice Gateway
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ===================================================
echo Starting JARVIS 2-Way Voice Telegram Daemon...
echo ===================================================
python tools/telegram_bridge.py
pause
