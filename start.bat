
@echo off
setlocal enableextensions enabledelayedexpansion

echo 🚀 Starting IR Spectroscopy Control Interface...

REM Set up cleanup function for Ctrl+C
set "cleanup_done=false"
if not defined parent (
    set parent=true
    REM Start a monitoring subprocess
    start /b "" "%~f0" monitor
)

REM Check if this is the monitor process
if "%1"=="monitor" goto :monitor

:main
echo 🔧 Starting FastAPI Backend...
cd /d "%~dp0backend"
start "FastAPI Backend" cmd /k "uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
cd /d "%~dp0"

REM Wait a moment for backend to start
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

echo 🎨 Starting React Frontend...
cd /d "%~dp0frontend"
start "React Frontend" cmd /k "npm run dev -- --host 0.0.0.0 --port 5000"
cd /d "%~dp0"

echo.
echo ✅ Services started successfully!
echo 📱 Frontend: http://localhost:5000
echo 🔌 Backend API: http://localhost:8000
echo 📚 API Docs: http://localhost:8000/docs
echo.
echo Both services are running in separate windows.
echo Press Ctrl+C or close this window to stop all services.
echo.

REM Wait for user to press Ctrl+C
:wait_loop
timeout /t 1 >nul 2>&1
if errorlevel 1 goto :cleanup
goto :wait_loop

:monitor
REM Monitor parent process and cleanup if it exits
:monitor_loop
tasklist /fi "PID eq %parent_pid%" >nul 2>&1
if errorlevel 1 (
    REM Parent process died, cleanup
    goto :cleanup
)
timeout /t 2 >nul 2>&1
goto :monitor_loop

:cleanup
if "%cleanup_done%"=="true" goto :end

echo.
echo 🛑 Shutting down services...

REM Kill FastAPI Backend (python/uvicorn processes)
for /f "tokens=2" %%i in ('tasklist /fi "WINDOWTITLE eq FastAPI Backend*" /fo csv ^| findstr /v "INFO"') do (
    taskkill /pid %%i /f >nul 2>&1
)

REM Kill React Frontend (node processes)  
for /f "tokens=2" %%i in ('tasklist /fi "WINDOWTITLE eq React Frontend*" /fo csv ^| findstr /v "INFO"') do (
    taskkill /pid %%i /f >nul 2>&1
)

REM Fallback: kill by process name
taskkill /f /im "uvicorn.exe" >nul 2>&1
taskkill /f /im "node.exe" >nul 2>&1
taskkill /f /im "python.exe" >nul 2>&1

set "cleanup_done=true"
echo Services stopped.

:end
timeout /t 2 >nul 2>&1
exit /b 0
