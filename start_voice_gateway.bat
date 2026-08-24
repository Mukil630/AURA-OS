@echo off
title JARVIS Voice & Gemini Agent Gateway
echo ===================================================
echo   JARVIS - Voice & Google Assistant/Gemini Gateway
echo ===================================================
cd /d "C:\Users\mukil\jarvis-core"
python -m uvicorn api.voice_webhook:app --host 0.0.0.0 --port 8000 --reload
pause
