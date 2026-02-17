# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# Add src to path
src_path = os.path.join(os.path.abspath('.'), 'src')
sys.path.insert(0, src_path)

# Find tkinterdnd2 location
import tkinterdnd2
tkdnd_path = os.path.dirname(tkinterdnd2.__file__)

a = Analysis(
    ['main.py'],
    pathex=[src_path],
    binaries=[],
    datas=[
        (tkdnd_path, 'tkinterdnd2'),
    ],
    hiddenimports=[
        'tkinterdnd2.TkinterDnD',
        'tkinterdnd2.TkinterDnD.DnDWrapper',
        'customtkinter',
        'PIL',
        'PIL._imagingtk',
        'PIL._tkinter_finder',
        'srt',
        'deep_translator',
        'bs4',
        'requests',
        'charset_normalizer',
        'idna',
        'urllib3',
        'certifi',
        'subtitles',
        'subtitles.gui',
        'subtitles.gui.tabs',
        'subtitles.gui.tabs.generate',
        'subtitles.gui.tabs.translate',
        'subtitles.gui.tabs.batch',
        'subtitles.gui.tabs.sync',
        'subtitles.core',
        'subtitles.core.translator',
        'subtitles.core.extractor',
        'subtitles.core.downloader',
        'subtitles.utils',
        'subtitles.utils.config',
        'subtitles.utils.logging_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SubtitleTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
