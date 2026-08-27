@echo off
title JARVIS Telegram Mobile Gateway Daemon
echo ========================================================
echo   ⚡ STARTING JARVIS TELEGRAM GATEWAY DAEMON
echo   Phase 12 Governed + 2-Way Voice + Safe Diagnostics
echo ========================================================
echo.

cd /d C:\Users\mukil\mukil-master-agent
set PYTHONPATH=C:\Users\mukil\mukil-master-agent;%PYTHONPATH%
python app\connectors\telegram\daemon.py

pause
