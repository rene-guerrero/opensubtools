#!/usr/bin/env python3
"""
Generate Windows Registry file for context menu integration.
Run this script once to create the .reg file, then import it into Windows Registry.
"""
import sys
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.resolve()
GENERATE_SUB_BAT = SCRIPT_DIR / "generate_sub.bat"

# Windows registry file content
# Note: %1 is Windows shell command parameter for the selected file
registry_template = '''Windows Registry Editor Version 5.00

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mp4\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mp4\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mkv\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mkv\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.avi\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.avi\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mov\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mov\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.wmv\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.wmv\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.flv\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.flv\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.webm\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.webm\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.m4v\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.m4v\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mpg\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mpg\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mpeg\\shell\\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\\SystemFileAssociations\\.mpeg\\shell\\Generar Subtitulos\\command]
@="{bat_path} \\"%1\\""
'''

def main():
    """Generate and write the registry file."""
    # Format the batch file path with proper escaping
    bat_path = str(GENERATE_SUB_BAT).replace("\\", "\\\\")
    registry_content = registry_template.format(bat_path=bat_path)

    # Write with UTF-16LE encoding (required by Windows Registry Editor)
    output_file = SCRIPT_DIR / "video_context_menu.reg"
    with open(output_file, "w", encoding="utf-16-le") as f:
        f.write(registry_content)

    print(f"✅ Registry file generated: {output_file}")
    print(f"\n📋 INSTRUCTIONS:")
    print(f"1. Right-click the .reg file or")
    print(f"2. Double-click to import into registry or")
    print(f"3. Open Command Prompt and run:")
    print(f"   regedit /s \"{output_file}\"")
    print(f"\n4. Restart Windows Explorer (or log out and back in)")
    print(f"   Then right-click on a video file and select 'Generar Subtítulos'")
    print(f"\n📝 Registry path: {bat_path}")

if __name__ == "__main__":
    main()
