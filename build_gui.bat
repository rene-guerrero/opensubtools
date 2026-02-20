@echo off
REM Build script for OpenSubTools GUI
REM Requirements: pip install pyinstaller

echo Building OpenSubTools.exe...

REM Use venv Python if available
set PYTHON=
if exist venv\Scripts\python.exe (
    set PYTHON=venv\Scripts\
    echo Using venv Python
)

REM Install build dependencies
%PYTHON%pip.exe install pyinstaller

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Build using spec file (includes tkinterdnd2 libraries)
%PYTHON%pyinstaller SubtitleTools.spec --clean

echo.
echo Build complete!
echo Executable location: dist\OpenSubTools.exe
pause
