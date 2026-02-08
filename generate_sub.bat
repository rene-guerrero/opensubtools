@echo off
REM Enhanced batch script for subtitle generation with better path handling
setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=!SCRIPT_DIR!venv\Scripts\python.exe"
set "GENERATE_PY=!SCRIPT_DIR!generate_sub.py"

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

REM Get the video file path - preserve everything including special characters
set "VIDEO_PATH=%~1"

REM Debug output
echo Debug: Script directory: !SCRIPT_DIR!
echo Debug: Video path received: "!VIDEO_PATH!"
echo Debug: Video path length: %VIDEO_PATH%

REM Run the generate_sub.py script with the FULL path including quotes
REM Use %VIDEO_PATH% (with delayed expansion) to preserve special characters
"!PYTHON_EXE!" "!GENERATE_PY!" "!VIDEO_PATH!"

echo.
echo Presione una tecla para continuar . . .
pause

