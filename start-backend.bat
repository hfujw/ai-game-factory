@echo off
cd /d "%~dp0backend"
..\venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
