
@echo off
echo 🚀 Starting IR Spectroscopy Control Interface...

REM Function to handle cleanup on exit
set "cleanup=echo. & echo 🛑 Shutting down services... & taskkill /F /IM python.exe >nul 2>&1 & taskkill /F /IM node.exe >nul 2>&1"

REM Set trap to cleanup on script exit (limited in batch)
echo Press Ctrl+C to stop all services

REM Start Backend
echo 🔧 Starting FastAPI Backend...
cd backend
start "FastAPI Backend" /MIN cmd /c "uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start Frontend
echo 🎨 Starting React Frontend...
cd frontend
start "React Frontend" /MIN cmd /c "npm run dev -- --host 0.0.0.0 --port 5000"
cd ..

echo ✅ Services started successfully!
echo 📱 Frontend: http://0.0.0.0:5000
echo 🔌 Backend API: http://0.0.0.0:8000
echo 📚 API Docs: http://0.0.0.0:8000/docs
echo.
echo Services are running in minimized windows.
echo Close this window or press Ctrl+C to stop all services.

REM Keep the script running
pause >nul
