@echo off
cd /d "%~dp0backend"
echo ==================================
echo  时光像素 - 后端服务 :8000
echo  按 Ctrl+C 停止
echo ==================================
..\venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
