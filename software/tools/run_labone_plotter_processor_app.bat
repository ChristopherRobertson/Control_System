@echo off
setlocal
cd /d "%~dp0\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tools\labone_plotter_processor_app.py" --gui
) else (
    python "tools\labone_plotter_processor_app.py" --gui
)
