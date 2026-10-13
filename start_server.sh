#!/usr/bin/env bash
# AURA-OS Cloud Server Startup Script
# Telegram Bridge Daemon is managed cleanly via app.main lifespan with auto-shutdown

echo "========================================================"
echo "⚡ AURA-OS: Starting FastAPI Production Web Server..."
echo "========================================================"
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
