@echo off
title 🌌 AURA-OS -- MASTER AUTONOMOUS AGENT SYSTEM
color 0b
echo ==============================================================================
echo                🌌 AURA-OS -- AUTONOMOUS JARVIS MASTER OPERATING PLANE
echo ==============================================================================
echo.
echo [1/3] Initializing 24/7 Autonomous Proactive Heartbeat Daemon...
start /b python brain/autonomous_heartbeat_daemon.py
echo.
echo [2/3] Initializing Telegram 2-Way Gateway & Screenshot Dispatcher...
start /b python -m tools.telegram_bridge
echo.
echo [3/3] Launching FastAPI Multi-Modal Mobile Hub & Chatbot Gateway on :8000 ...
start "" "http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
