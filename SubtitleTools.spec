# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# Add src to path
src_path = os.path.join(os.path.abspath('.'), 'src')
sys.path.insert(0, src_path)

# Find tkinterdnd2 location (native tkdnd libraries)
import tkinterdnd2
tkdnd_path = os.path.dirname(tkinterdnd2.__file__)

datas = [
    (tkdnd_path, 'tkinterdnd2'),
    ('src/subtitles/gui/icon.ico', 'subtitles/gui'),
    # Offline en->es model (CTranslate2 weights + SentencePiece tokenizer).
    # The stanza/ folder shipped with the Argos package is not needed.
    ('.work/argos/en_es/en_es/model', 'argos_model/model'),
    ('.work/argos/en_es/en_es/sentencepiece.model', 'argos_model'),
]

# Data files (babelfish language tables, guessit config, knowit data)
datas += collect_data_files('babelfish')
datas += collect_data_files('guessit')
datas += collect_data_files('knowit')

# ctranslate2 ships its native DLLs inside the package
binaries = collect_dynamic_libs('ctranslate2')

# Package metadata needed by stevedore to discover subliminal providers at runtime
datas += copy_metadata('subliminal')
datas += copy_metadata('stevedore')
datas += copy_metadata('dogpile.cache')
datas += copy_metadata('knowit')

hiddenimports = [
    # GUI
    'tkinterdnd2.TkinterDnD',
    'customtkinter',
    'darkdetect',
    'PIL',
    'PIL._imagingtk',
    'PIL._tkinter_finder',
    # Core deps
    'ffmpeg',
    'srt',
    'yaml',
    'deep_translator',
    'bs4',
    'requests',
    'charset_normalizer',
    'idna',
    'urllib3',
    'certifi',
    'defusedxml',
    'defusedxml.ElementTree',
    'platformdirs',
    'rarfile',
    # Offline translation (imported lazily inside offline._load)
    'ctranslate2',
    'sentencepiece',
    # Our package
    'subtitles',
]

# Subliminal + its plugin/runtime stack: providers and cache backends are
# loaded dynamically by name, so PyInstaller cannot detect them statically.
hiddenimports += collect_submodules('subliminal')
hiddenimports += collect_submodules('babelfish')
hiddenimports += collect_submodules('guessit')
hiddenimports += collect_submodules('rebulk')
hiddenimports += collect_submodules('knowit')
hiddenimports += collect_submodules('stevedore')
hiddenimports += collect_submodules('dogpile')
hiddenimports += collect_submodules('subtitles')

a = Analysis(
    ['main.py'],
    pathex=[src_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='OpenSubTools',
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
    icon='src/subtitles/gui/icon.ico',
)
