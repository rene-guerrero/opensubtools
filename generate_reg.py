#!/usr/bin/env python3
"""Generate Windows Registry file for context menu integration."""
import sys

# Registry content in UTF-16LE format (required by Windows)
reg_content = """Windows Registry Editor Version 5.00

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mp4\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mp4\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mkv\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mkv\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.avi\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.avi\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mov\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mov\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.wmv\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.wmv\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.flv\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.flv\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.webm\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.webm\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.m4v\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.m4v\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mpg\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mpg\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mpeg\shell\Generar Subtitulos]
@="Generar Subtitulos"

[HKEY_CLASSES_ROOT\SystemFileAssociations\.mpeg\shell\Generar Subtitulos\command]
@="D:\\Me\\for-pleasure\\subtitles\\generate_sub.bat \\"%1\\""
"""

# Write as UTF-16LE with BOM (required by Windows Registry Editor)
output_file = "video_context_menu.reg"
with open(output_file, "w", encoding="utf-16-le") as f:
    f.write('\ufeff')  # BOM for UTF-16LE
    f.write(reg_content)

print(f"✅ Created {output_file} with UTF-16LE encoding")
print(f"   Size: {len(reg_content)} characters")
print(f"\nTo apply:")
print(f"  1. Double-click {output_file} or")
print(f"  2. Right-click → Merge or")
print(f"  3. Run: regedit /s {output_file}")
