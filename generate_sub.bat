@echo off
setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0
set PYTHON_EXE=!SCRIPT_DIR!venv\Scripts\python.exe
set GENERATE_PY=!SCRIPT_DIR!generate_sub.py

REM Check if Python executable exists
if not exist "!PYTHON_EXE!" (
    echo Error: Python no encontrado en !PYTHON_EXE!
    pause
    exit /b 1
)

REM Check if generate_sub.py exists
if not exist "!GENERATE_PY!" (
    echo Error: generate_sub.py no encontrado en !GENERATE_PY!
    pause
    exit /b 1
)

REM Run the generate_sub.py script with the video file path
REM %~1 removes quotes from the argument safely
"!PYTHON_EXE!" "!GENERATE_PY!" "%~1"
pause

