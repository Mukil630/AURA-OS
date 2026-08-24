@echo off
title JARVIS Voice Gateway & Cloudflare Tunnel
echo =======================================================
echo   JARVIS - Mobile "Hey Google" to PC Control System
echo =======================================================
cd /d "C:\Users\mukil\jarvis-core"

echo [1/2] Launching JARVIS Voice API Server...
start "JARVIS Voice API" cmd /k "python -m uvicorn api.voice_webhook:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Launching Cloudflare HTTPS Tunnel...
echo.
echo =======================================================
echo   LOOK BELOW FOR YOUR LIVE PUBLIC HTTPS URL:
echo   Example: https://xxxx-xxxx.trycloudflare.com
echo =======================================================
echo.
tools\cloudflared.exe tunnel --url http://localhost:8000

pause
