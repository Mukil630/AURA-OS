@echo off
title AURA OS // Autonomous Executive Operating Plane (JARVIS Prime)
color 0B
cls

echo =================================================================
echo   >> AURA OS v3.1 // Supreme Autonomous Partner for Mukil <<
echo   >> Dual-Modal: Text Input + Tony Stark Voice Arc Mic <<
echo   >> Sub-Second Groq Engine + 16 Superpowers + Self-Extending <<
echo =================================================================
echo.

cd /d "C:\Users\mukil\aura-os"

echo [*] Verifying Environment & Tool Integrity...
python test_suite.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Warning: Some tests did not pass. Starting anyway...
)

echo.
echo [*] Launching AURA OS Cloud Gateway on http://localhost:8000 ...
start "" "http://localhost:8000"

echo [*] Starting FastAPI + WebSocket Server Daemon...
python -m uvicorn aura.server:app --host 127.0.0.1 --port 8000 --reload
pause
