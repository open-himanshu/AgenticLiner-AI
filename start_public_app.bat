@echo off
title AgenticLiner - Public Server Launcher
cd /d "%~dp0"
echo ===================================================
echo Starting AgenticLiner Public Server...
echo ===================================================
python -u start_live_server.py
pause
