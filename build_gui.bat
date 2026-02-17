@echo off
REM Build script for Subtitle Tools GUI
REM Requirements: pip install pyinstaller

echo Building SubtitleTools.exe...

REM Install build dependencies
pip install pyinstaller customtkinter

REM Build the executable
pyinstaller --onefile --windowed --name SubtitleTools main.py

echo.
echo Build complete!
echo Executable location: dist\SubtitleTools.exe
pause
