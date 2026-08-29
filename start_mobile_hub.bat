@echo off
title AURA-OS Mobile Hub & Chatbot Gateway
color 0b
echo ======================================================================
echo           🌌 AURA-OS -- JARVIS MOBILE HUB & CHATBOT GATEWAY
echo ======================================================================
echo.
echo Starting FastAPI Multi-Modal Server on http://localhost:8000 ...
echo Opening JARVIS Mobile Hub in default browser...
echo.

start "" "http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
