
@echo off
setlocal enableextensions enabledelayedexpansion

echo 🚀 Starting IR Spectroscopy Control Interface...

REM Set up cleanup flag
set "cleanup_done=false"

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

REM Ensure pip is available (fallback to ensurepip if needed)
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip not found; attempting to bootstrap pip with ensurepip...
    python -m ensurepip --upgrade >nul 2>&1
    python -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: pip is not available even after ensurepip. Please add pip to PATH or repair Python.
        pause
        goto :cleanup
    )
)

REM Configure MIRcat SDK directory dynamically to avoid hardcoded paths in code
set "_SDK_DIR=%~dp0docs\sdks\daylight_mircat"
if exist "%_SDK_DIR%\MIRcatSDK.dll" (
    set "MIRCAT_SDK_DIR=%_SDK_DIR%"
    set "PATH=%MIRCAT_SDK_DIR%;%PATH%"
    echo Using MIRcat SDK at: !MIRCAT_SDK_DIR!
) else (
    set "_SDK_DIR=%~dp0docs\docs\sdks\daylight_mircat"
    if exist "%_SDK_DIR%\MIRcatSDK.dll" (
        set "MIRCAT_SDK_DIR=%_SDK_DIR%"
        set "PATH=%MIRCAT_SDK_DIR%;%PATH%"
        echo Using MIRcat SDK at: !MIRCAT_SDK_DIR!
    )
)

set "BACKEND_DIR=%~dp0backend"
pushd "%BACKEND_DIR%"

REM Check and install Python dependencies
echo 🔧 Checking Python dependencies...
set "VENV_DIR=%BACKEND_DIR%\venv"
set "ACT=%VENV_DIR%\Scripts\activate.bat"

REM If venv folder missing OR activation missing, (re)create venv
if not exist "%ACT%" (
    if exist "%VENV_DIR%" (
        echo Found incomplete virtual environment. Removing and recreating...
        rmdir /s /q "%VENV_DIR%" >nul 2>&1
    )
    echo Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo First attempt to create venv failed. Trying with Python launcher...
        py -3 -m venv "%VENV_DIR%"
    )
    if not exist "%ACT%" (
        echo ERROR: Failed to create virtual environment at "%VENV_DIR%".
        echo Trying global pip install instead...
        rem First try user-level install to avoid permission issues
        python -m pip install --user -r "%BACKEND_DIR%\requirements.txt"
        if errorlevel 1 (
            echo Global user-level install failed. Attempting system-wide pip install...
            python -m pip install -r "%BACKEND_DIR%\requirements.txt"
            if errorlevel 1 (
                echo ERROR: Failed to install Python dependencies globally.
                echo Tip: Try running PowerShell as Administrator, or ensure internet access for pip.
                pause
                goto :cleanup
            )
        )
        goto :start_backend_global
    )
)

REM Check if activation script exists (diagnose path issues explicitly)
if exist "%ACT%" (
    echo Found virtual environment: "%ACT%"
) else (
    echo ERROR: Virtual environment activation script missing: "%ACT%"
    echo Trying global pip install instead...
    python -m pip install --user -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo Global user-level install failed. Attempting system-wide pip install...
        python -m pip install -r "%BACKEND_DIR%\requirements.txt"
        if errorlevel 1 (
            echo ERROR: Failed to install Python dependencies globally.
            echo Tip: Try running PowerShell as Administrator, or ensure internet access for pip.
            pause
            goto :cleanup
        )
    )
    goto :start_backend_global
)

echo Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    echo Trying global installation...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install Python dependencies globally.
        pause
        goto :cleanup
    )
    goto :start_backend_global
)

python -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies in virtual environment.
    pause
    goto :cleanup
)

echo 🔧 Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "cd /d "%BACKEND_DIR%" && call "%ACT%" && python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
cd /d "%~dp0"
goto :start_frontend

:start_backend_global
echo 🔧 Starting FastAPI Backend (global Python)...
start "FastAPI Backend" cmd /k "cd /d "%BACKEND_DIR%" && python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
popd

:start_frontend

REM Wait a moment for backend to start
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Check if pnpm is available
echo 🎨 Checking pnpm installation...
pnpm --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pnpm not found. Please install pnpm.
    echo Install with: npm install -g pnpm
    echo Or download from: https://pnpm.io/installation
    pause
    goto :cleanup
)

REM Check and install Node.js dependencies
echo 🎨 Checking Node.js dependencies...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo Installing Node.js dependencies with pnpm...
    pnpm install
    if errorlevel 1 (
        echo ERROR: Failed to install Node.js dependencies with pnpm.
        pause
        goto :cleanup
    )
) else (
    echo Node.js dependencies already installed.
)

echo 🎨 Starting React Frontend...
start "React Frontend" cmd /k "cd /d "%~dp0frontend" && pnpm run dev -- --host 0.0.0.0 --port 5000"
cd /d "%~dp0"

REM Open default browser to the UI after a short wait
echo Opening browser to UI at http://localhost:5000 ...
timeout /t 2 /nobreak >nul
start "" http://localhost:5000

echo.
echo ✅ Services started successfully!
echo 📱 Frontend: http://localhost:5000
echo 🔌 Backend API: http://localhost:8000
echo 📚 API Docs: http://localhost:8000/docs
echo.
echo Both services are running in separate windows.
echo Press any key in this window to stop all services.
echo (Avoid Ctrl+C to prevent terminal input glitches.)
echo.
pause >nul
goto :cleanup

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
