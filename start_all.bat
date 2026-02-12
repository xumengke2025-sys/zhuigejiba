@echo off
echo Starting Trace Project...

:: Start Backend (Install deps first)
start "Trace Backend" cmd /k "cd /d %~dp0backend && set PYTHONIOENCODING=utf-8 && echo Installing Python dependencies... && pip install -r requirements.txt && echo Starting Backend... && python run.py"

:: Start Frontend (Install deps first)
start "Trace Frontend" cmd /k "cd /d %~dp0frontend && echo Installing Node dependencies... && npm install && echo Starting Frontend... && npm run dev"

echo Services launching...
echo Backend will run at: http://127.0.0.1:5002
echo Frontend will run at: http://localhost:3002
