@echo off
chcp 65001 >nul
title JARVIS Master Cognitive Engine Console
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python interactive_jarvis_cli.py
pause
