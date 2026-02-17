#!/usr/bin/env python3
"""
Windows Context Menu Registration Script

Generates a .reg file to add "Generate Subtitles" to the Windows context menu
for video files. This script detects the Python environment and package location
automatically.

Usage:
    python generate_context_menu.py

The script will:
1. Detect the Python interpreter and package location
2. Generate a video_context_menu.reg file
3. Provide instructions on how to apply the registry changes
"""

import os
import sys
import subprocess
from pathlib import Path


def find_python_executable(package_root: Path) -> Path:
    """Find the Python executable to use.
    
    Priority:
    1. Python from venv in project root
    2. Currently running Python (if it's from a venv)
    3. System Python
    """
    # Option 1: Check for venv in project root
    venv_paths = [
        package_root / "venv" / "Scripts" / "python.exe",
        package_root / ".venv" / "Scripts" / "python.exe",
        package_root / "env" / "Scripts" / "python.exe",
    ]
    
    for venv_python in venv_paths:
        if venv_python.exists():
            return venv_python
    
    # Option 2: Check if current Python is already from a venv
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.prefix != sys.base_prefix):
        # We're in a virtual environment
        current_venv_python = Path(sys.executable)
        if current_venv_python.exists():
            return current_venv_python
    
    # Option 3: Fallback to system Python
    return Path(sys.executable)


def find_package_root() -> Path:
    """Find the package root directory."""
    # This file should be in src/subtitles/scripts/ or similar
    current_file = Path(__file__).resolve()
    
    # Try to find src/subtitles/ as package root
    package_root = current_file.parent.parent
    if package_root.name == "subtitles" and package_root.parent.name == "src":
        return package_root.parent.parent
    
    # Fallback: assume we're in src/subtitles/scripts/
    src_root = current_file.parent.parent.parent
    if src_root.name == "src":
        return src_root
    
    # Last resort: use current directory
    return Path.cwd()


def get_video_formats() -> list[str]:
    """Get list of video formats from config or use defaults."""
    try:
        # Try to import config to get video formats
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from subtitles.utils.config import get_config
        config = get_config()
        # Remove leading dots if present
        formats = [f.lstrip('.') for f in config.video_formats]
        return formats
    except Exception:
        # Use default formats
        return [
            "mp4", "mkv", "avi", "mov", "wmv", 
            "flv", "webm", "m4v", "mpg", "mpeg"
        ]


def generate_registry_file(
    python_exe: Path,
    package_root: Path,
    video_formats: list[str],
    output_file: Path,
    menu_text: str = "Generate Subtitles"
) -> None:
    """Generate the Windows registry file."""
    
    # Build command - escape quotes properly for .reg format
    # In .reg files: \" represents a literal quote character
    python_path = str(python_exe).replace("\\", "\\\\")
    # Use /k to keep window open so user can see output/errors
    # Format: cmd /k ""python.exe" -m module "%1"""
    # "" at start and end protects spaces in paths
    command = f'cmd /k \\"\\"{python_path}\\" -m subtitles.cli.generate \\"%1\\"\\"\\"'
    
    reg_content = ['Windows Registry Editor Version 5.00', '']
    
    for ext in video_formats:
        # Registry key path (single backslashes for .reg format)
        key_path = f'SystemFileAssociations\\.{ext}\\shell\\{menu_text}'
        
        reg_content.extend([
            f'[HKEY_CLASSES_ROOT\\{key_path}]',
            f'@="{menu_text}"',
            '',
            f'[HKEY_CLASSES_ROOT\\{key_path}\\command]',
            f'@="{command}"',
            ''
        ])
    
    output_file.write_text('\n'.join(reg_content), encoding='utf-8')
    print(f"[OK] Registry file created: {output_file}")


def check_admin_rights() -> bool:
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def apply_registry_file(reg_file: Path) -> bool:
    """Attempt to apply the registry file."""
    try:
        result = subprocess.run(
            ['reg', 'import', str(reg_file)],
            capture_output=True,
            text=True,
            shell=True
        )
        if result.returncode == 0:
            print("[OK] Registry keys applied successfully!")
            return True
        else:
            print(f"[ERROR] Failed to apply registry: {result.stderr}")
            return False
    except Exception as e:
        print(f"[ERROR] Error applying registry: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Windows Context Menu Registration")
    print("=" * 60)
    print()
    
    # Find package root first (needed to find venv)
    package_root = find_package_root()
    print(f"Package root: {package_root}")
    
    # Find Python executable
    python_exe = find_python_executable(package_root)
    print(f"Python executable: {python_exe}")
    
    # Get video formats
    video_formats = get_video_formats()
    print(f"Video formats: {', '.join(video_formats)}")
    print()
    
    # Determine output path
    output_file = package_root / "video_context_menu.reg"
    
    # Generate the registry file
    generate_registry_file(
        python_exe=python_exe,
        package_root=package_root,
        video_formats=video_formats,
        output_file=output_file
    )
    
    print()
    print("=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print()
    print(f"1. The registry file has been created at:")
    print(f"   {output_file}")
    print()
    print("2. To add to context menu, you have two options:")
    print()
    print("   Option A - Double-click the .reg file:")
    print("   - Double-click 'video_context_menu.reg'")
    print("   - Click 'Yes' to confirm")
    print("   - Click 'OK' to dismiss success message")
    print()
    print("   Option B - Run this script with admin rights:")
    print("   - Right-click on this script or terminal")
    print("   - Select 'Run as administrator'")
    print("   - The script will attempt to apply automatically")
    print()
    
    # Check if we can apply automatically
    if check_admin_rights():
        print("3. Running as administrator - attempting to apply...")
        print()
        apply_registry_file(output_file)
    else:
        print("3. Not running as administrator.")
        print("   The .reg file was created but not applied.")
        print("   You'll need to double-click it manually or run as admin.")
    print()
    print("=" * 60)
    print("To remove the context menu:")
    print("=" * 60)
    print("1. Run regedit")
    print("2. Navigate to HKEY_CLASSES_ROOT\\SystemFileAssociations")
    print("3. Delete the 'Generate Subtitles' key for each video format")
    print("   OR create an 'uninstall' .reg file with different values")
    print()


if __name__ == '__main__':
    main()
