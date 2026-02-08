@echo off
REM Setup script to generate and register the context menu command
REM Run this as Administrator

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo Generador de Registro para Subtitulos
echo ========================================
echo.

REM Get full path to generate_sub.bat
set "SCRIPT_PATH=%cd%\generate_sub.bat"

REM Use Python to create the .reg file with proper UTF-16LE encoding
echo Generando archivo de registro...
python.exe create_registry.py

if %errorlevel% equ 0 (
    echo.
    echo Importando en el Registro de Windows...
    timeout /t 2 /nobreak

    REM Try to import the registry file
    reg import video_context_menu.reg 2>nul

    if %errorlevel% equ 0 (
        echo.
        echo ✅ Registro importado correctamente!
        echo.
        echo Pasos siguientes:
        echo   1. Reinicia el Explorador de Archivos (presiona Ctrl+Shift+Esc)
        echo   2. Haz clic derecho en un archivo de video
        echo   3. Debería aparecer "Generar Subtítulos"
        echo.
    ) else (
        echo.
        echo ❌ Error al importar con reg import
        echo.
        echo Intenta estos pasos:
        echo   1. Abre el archivo video_context_menu.reg con un editor de texto
        echo   2. Verifica que tenga sintaxis correcta
        echo   3. Haz doble clic en el archivo, o
        echo   4. Ejecuta: regedit /s video_context_menu.reg
        echo.
    )
) else (
    echo.
    echo ❌ Error al generar el archivo de registro
    echo Verifica que Python esté disponible en la PATH
    echo.
)

pause
