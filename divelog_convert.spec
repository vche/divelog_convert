# -*- mode: python ; coding: utf-8 -*-
# Reference: https://pyinstaller.org/en/stable/spec-files.html#using-spec-files

# Addd the current project src so that we can get the app version
import os
import sys
sys.path.append(f"{os.getcwd()}/src")
import divelog_convert

block_cipher = None


a = Analysis(
    ['src/divelog_convert/app.py'],
    pathex=[],
    binaries=[],
    datas=[('README.md', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='divelog_convert',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    # target_arch='universal2',
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='divelog_convert',
)
app = BUNDLE(
    coll,
    name='divelog_convert.app',
    icon=None,
    bundle_identifier=None,
    version=divelog_convert.__version__,
)
