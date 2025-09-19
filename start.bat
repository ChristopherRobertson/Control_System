
@echo off
setlocal enableextensions enabledelayedexpansion

echo 🚀 Starting IR Spectroscopy Control Interface...

REM Set up cleanup flag
set "cleanup_done=false"

:main
REM Check if Python is available (try python, then py -3)
echo 🔧 Checking Python installation...
set "PYEXE="
python --version >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE (
    py -3 --version >nul 2>&1 && set "PYEXE=py -3"
)
if not defined PYEXE (
    echo ERROR: Python not found. Please install Python 3.8+ and add it to PATH.
    echo If Python is installed, ensure either 'python' or 'py' launcher is in PATH.
    echo Download from: https://www.python.org/downloads/
    pause
    goto :cleanup
)
for /f "tokens=*" %%v in ('%PYEXE% --version') do echo Using %%v

REM Ensure pip is available (fallback to ensurepip if needed)
%PYEXE% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip not found; attempting to bootstrap pip with ensurepip...
    %PYEXE% -m ensurepip --upgrade >nul 2>&1
    %PYEXE% -m pip --version >nul 2>&1
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

REM Ensure Zurich Instruments LabOne Data Server is reachable
echo 🔌 Checking LabOne Data Server...
set "CFG_PATH=%~dp0hardware_configuration.toml"
REM Parse LabOne settings from [zurich_hf2li] using Python (reliable TOML parser)
for /f "usebackq tokens=1,* delims==" %%A in (`%PYEXE% -c "import tomllib,sys; p=r'%CFG_PATH%'; d=tomllib.load(open(p,'rb')).get('zurich_hf2li',{}); g=lambda k,df:d.get(k,df); print('LABONE_HOST='+str(g('host','127.0.0.1'))); print('LABONE_PORT='+str(g('data_server_port',8005))); print('LABONE_WEB_PORT='+str(g('web_server_port',8006))); print('ZI_LABONE_ROOT='+str(g('labone_root','C:/Program Files/Zurich Instruments/LabOne'))); print('AUTO_START_LABONE='+str(g('auto_start_servers',True)).lower()); print('REQUIRE_WEB_SERVER='+str(g('require_web_server',True)).lower())"`) do set "%%A=%%B"
if not defined LABONE_HOST set "LABONE_HOST=127.0.0.1"
if not defined LABONE_PORT set "LABONE_PORT=8005"
if not defined LABONE_WEB_PORT set "LABONE_WEB_PORT=8006"
if not defined ZI_LABONE_ROOT set "ZI_LABONE_ROOT=C:/Program Files/Zurich Instruments/LabOne"
if not defined AUTO_START_LABONE set "AUTO_START_LABONE=true"
if not defined REQUIRE_WEB_SERVER set "REQUIRE_WEB_SERVER=true"
set "LABONE_DATA_PORT=%LABONE_PORT%"

REM Normalize LabOne root path for Windows (convert forward slashes, resolve to absolute path)
set "ZI_LABONE_ROOT=%ZI_LABONE_ROOT:/=\%"
for %%P in ("%ZI_LABONE_ROOT%") do set "ZI_LABONE_ROOT=%%~fP"
if not exist "%ZI_LABONE_ROOT%" (
    echo ERROR: LabOne installation directory not found at "%ZI_LABONE_ROOT%".
    echo Update [zurich_hf2li].labone_root in hardware_configuration.toml or install LabOne.
    goto :cleanup
)
echo Using LabOne root: %ZI_LABONE_ROOT%

REM Probe connectivity first
powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ Write-Host 'LabOne Data Server reachable.'; exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo LabOne Data Server not reachable at %LABONE_HOST%:%LABONE_PORT%. Attempting to start...
    REM Only try to start locally if host is localhost or ::1
    if /I "%AUTO_START_LABONE%"=="true" if /I "%LABONE_HOST%"=="127.0.0.1" (
        powershell -NoProfile -Command "$svc = Get-Service -ErrorAction SilentlyContinue 'ziDataServer'; if(-not $svc){ $svc = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like '*LabOne*Data*Server*' } | Select-Object -First 1 }; if($svc){ if($svc.Status -ne 'Running'){ Start-Service -InputObject $svc; Start-Sleep -Seconds 2 }; Write-Host 'Service:' $svc.Name 'status' $svc.Status } else { Write-Host 'Service not found' }"
        REM Re-test
        powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ Write-Host 'LabOne Data Server reachable.'; exit 0 } else { exit 1 }"
        if errorlevel 1 (
            echo Attempting to start user-mode Data Server executable...
            set "ZI_DS_EXE=%ZI_LABONE_ROOT%\DataServer\ziDataServer.exe"
            if not exist "!ZI_DS_EXE!" for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -Command "$exe = Get-ChildItem '%ZI_LABONE_ROOT%' -Recurse -Filter 'ziDataServer*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1; if($exe){ $exe.FullName }"`) do set "ZI_DS_EXE=%%P"
            if defined ZI_DS_EXE if exist "!ZI_DS_EXE!" (
                echo Starting LabOne Data Server using "!ZI_DS_EXE!"
                powershell -NoProfile -Command "Start-Process -FilePath \"!ZI_DS_EXE!\" -ArgumentList '--port %LABONE_PORT%' -WindowStyle Minimized; Start-Sleep -Seconds 2"
                powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ exit 0 } else { exit 1 }"
                if errorlevel 1 (
                    echo First attempt failed; retrying with -p argument...
                    powershell -NoProfile -Command "Get-Process -Name ziDataServer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"
                    powershell -NoProfile -Command "Start-Process -FilePath \"!ZI_DS_EXE!\" -ArgumentList '-p %LABONE_PORT%' -WindowStyle Minimized; Start-Sleep -Seconds 2"
                    powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ exit 0 } else { exit 1 }"
                    if errorlevel 1 (
                        echo ERROR: Could not start LabOne Data Server automatically. Exiting.
                        goto :cleanup
                    ) else (
                        echo LabOne Data Server started successfully on port %LABONE_PORT%.
                    )
                ) else (
                    echo LabOne Data Server started successfully on port %LABONE_PORT%.
                )
            ) else (
                echo ERROR: LabOne Data Server executable not found under "%ZI_LABONE_ROOT%". Exiting.
                goto :cleanup
            )
        )
    ) else (
        echo ERROR: Target host %LABONE_HOST% is remote and not reachable. Exiting.
        goto :cleanup
    )
)

if /I "%REQUIRE_WEB_SERVER%"=="true" (
  REM Ensure LabOne Web Server is reachable
  echo 🌐 Checking LabOne Web Server...
  powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_WEB_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ Write-Host 'LabOne Web Server reachable.'; exit 0 } else { exit 1 }"
  if errorlevel 1 (
      echo LabOne Web Server not reachable at %LABONE_HOST%:%LABONE_WEB_PORT%. Attempting to start...
      if /I "%AUTO_START_LABONE%"=="true" if /I "%LABONE_HOST%"=="127.0.0.1" (
          powershell -NoProfile -Command "$svc = Get-Service -ErrorAction SilentlyContinue 'ziWebServer'; if(-not $svc){ $svc = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like '*LabOne*Web*Server*' } | Select-Object -First 1 }; if($svc){ if($svc.Status -ne 'Running'){ Start-Service -InputObject $svc; Start-Sleep -Seconds 2 }; Write-Host 'Service:' $svc.Name 'status' $svc.Status } else { Write-Host 'Service not found' }"
          powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_WEB_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ Write-Host 'LabOne Web Server reachable.'; exit 0 } else { exit 1 }"
          if errorlevel 1 (
              echo Attempting to start user-mode Web Server executable...
              set "ZI_WS_EXE=%ZI_LABONE_ROOT%\WebServer\ziWebServer.exe"
              if not exist "!ZI_WS_EXE!" for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -Command "$exe = Get-ChildItem '%ZI_LABONE_ROOT%' -Recurse -Filter 'ziWebServer*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1; if($exe){ $exe.FullName }"`) do set "ZI_WS_EXE=%%P"
              if defined ZI_WS_EXE if exist "!ZI_WS_EXE!" (
                  echo Starting LabOne Web Server using "!ZI_WS_EXE!"
                  powershell -NoProfile -Command "Start-Process -FilePath \"!ZI_WS_EXE!\" -ArgumentList '--port %LABONE_WEB_PORT%' -WindowStyle Minimized; Start-Sleep -Seconds 2"
                  powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_WEB_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ exit 0 } else { exit 1 }"
                  if errorlevel 1 (
                      echo First attempt failed; retrying with -p argument...
                      powershell -NoProfile -Command "Get-Process -Name ziWebServer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"
                      powershell -NoProfile -Command "Start-Process -FilePath \"!ZI_WS_EXE!\" -ArgumentList '-p %LABONE_WEB_PORT%' -WindowStyle Minimized; Start-Sleep -Seconds 2"
                      powershell -NoProfile -Command "$h='%LABONE_HOST%'; $p=%LABONE_WEB_PORT%; try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect($h,$p); $ok=$c.Connected; $c.Close() } catch { $ok=$false }; if($ok){ exit 0 } else { exit 1 }"
                      if errorlevel 1 (
                          echo ERROR: Could not start LabOne Web Server automatically. Exiting.
                          goto :cleanup
                      ) else (
                          echo LabOne Web Server started successfully on port %LABONE_WEB_PORT%.
                      )
                  ) else (
                      echo LabOne Web Server started successfully on port %LABONE_WEB_PORT%.
                  )
              ) else (
                  echo ERROR: LabOne Web Server executable not found under "%ZI_LABONE_ROOT%". Exiting.
                  goto :cleanup
              )
          )
      ) else (
          echo ERROR: Target host %LABONE_HOST% is remote and not reachable for Web Server. Exiting.
          goto :cleanup
      )
  )
)

REM Suppress noisy pip output
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_DEFAULT_TIMEOUT=60"

REM Check and install Python dependencies
echo 🔧 Checking Python dependencies...
set "VENV_DIR=%BACKEND_DIR%\venv"
set "ACT=%VENV_DIR%\Scripts\activate.bat"
set "VENV_PY_EXE=%VENV_DIR%\Scripts\python.exe"

REM If venv folder missing OR activation missing, (re)create venv
if not exist "%ACT%" (
    if exist "%VENV_DIR%" (
        echo Found incomplete virtual environment. Removing and recreating...
        rmdir /s /q "%VENV_DIR%" >nul 2>&1
    )
    echo Creating Python virtual environment...
    %PYEXE% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo First attempt to create venv failed. Trying with Python launcher...
        py -3 -m venv "%VENV_DIR%"
    )
    if not exist "%ACT%" (
        echo ERROR: Failed to create virtual environment at "%VENV_DIR%".
        echo Trying global pip install instead...
        rem First try user-level install to avoid permission issues
        %PYEXE% -m pip install -q --no-input --disable-pip-version-check --user -r "%BACKEND_DIR%\requirements.txt" 1>nul
        if errorlevel 1 (
            echo Global user-level install failed. Attempting system-wide pip install...
            %PYEXE% -m pip install -q --no-input --disable-pip-version-check -r "%BACKEND_DIR%\requirements.txt" 1>nul
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
    %PYEXE% -m pip install -q --no-input --disable-pip-version-check --user -r "%BACKEND_DIR%\requirements.txt" 1>nul
    if errorlevel 1 (
        echo Global user-level install failed. Attempting system-wide pip install...
        %PYEXE% -m pip install -q --no-input --disable-pip-version-check -r "%BACKEND_DIR%\requirements.txt" 1>nul
        if errorlevel 1 (
            echo ERROR: Failed to install Python dependencies globally.
            echo Tip: Try running PowerShell as Administrator, or ensure internet access for pip.
            pause
            goto :cleanup
        )
    )
    goto :start_backend_global
)

REM Validate the virtual environment binary (guard against WSL/Linux venv copied to Windows)
"%VENV_PY_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo Detected broken or foreign virtual environment. Recreating venv...
    rmdir /s /q "%VENV_DIR%" >nul 2>&1
    %PYEXE% -m venv "%VENV_DIR%"
)

echo Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    echo Trying global installation...
    %PYEXE% -m pip install -q --no-input --disable-pip-version-check -r requirements.txt 1>nul
    if errorlevel 1 (
        echo ERROR: Failed to install Python dependencies globally.
        pause
        goto :cleanup
    )
    goto :start_backend_global
)

REM Use the venv's Python for pip to avoid the Windows launcher choosing global Python.
python -m pip install -q --no-input --disable-pip-version-check -r "%BACKEND_DIR%\requirements.txt" 1>nul
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
start "FastAPI Backend" cmd /k "cd /d "%BACKEND_DIR%" && %PYEXE% -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
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
