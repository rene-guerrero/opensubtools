@echo off
REM Build script for Subtitle Tools GUI
REM Requirements: pip install pyinstaller

echo Building SubtitleTools.exe...

REM Install build dependencies
pip install pyinstaller customtkinter

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Build using spec file (includes tkinterdnd2 libraries)
pyinstaller SubtitleTools.spec --clean

echo.
echo Build complete!
echo Executable location: dist\SubtitleTools.exe
pause
