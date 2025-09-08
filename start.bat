
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
REM Check if Python is available
echo 🔧 Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ and add it to PATH.
    echo Download from: https://www.python.org/downloads/
    pause
    goto :cleanup
)

cd /d "%~dp0backend"

REM Check and install Python dependencies
echo 🔧 Checking Python dependencies...
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Trying global pip install instead...
        pip install -r requirements.txt
        if errorlevel 1 (
            echo ERROR: Failed to install Python dependencies globally.
            pause
            goto :cleanup
        )
        goto :start_backend_global
    )
)

REM Check if activation script exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment creation failed.
    echo Trying global pip install instead...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install Python dependencies globally.
        pause
        goto :cleanup
    )
    goto :start_backend_global
)

echo Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    echo Trying global installation...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install Python dependencies globally.
        pause
        goto :cleanup
    )
    goto :start_backend_global
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies in virtual environment.
    pause
    goto :cleanup
)

echo 🔧 Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "cd /d "%~dp0backend" && call venv\Scripts\activate.bat && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
cd /d "%~dp0"
goto :start_frontend

:start_backend_global
echo 🔧 Starting FastAPI Backend (global Python)...
start "FastAPI Backend" cmd /k "cd /d "%~dp0backend" && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
cd /d "%~dp0"

:start_frontend

REM Wait a moment for backend to start
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Check if Node.js/npm is available
echo 🎨 Checking Node.js installation...
npm --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm/Node.js not found. Please install Node.js and add it to PATH.
    echo Download from: https://nodejs.org/
    pause
    goto :cleanup
)

REM Check and install Node.js dependencies
echo 🎨 Checking Node.js dependencies...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo Installing Node.js dependencies...
    npm install
    if errorlevel 1 (
        echo ERROR: Failed to install Node.js dependencies.
        pause
        goto :cleanup
    )
) else (
    echo Node.js dependencies already installed.
)

echo 🎨 Starting React Frontend...
start "React Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 0.0.0.0 --port 5000"
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
