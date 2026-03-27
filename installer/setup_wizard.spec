# -*- mode: python ; coding: utf-8 -*-
#
# TW_Prophet_Setup_Wizard.exe ビルド用 PyInstaller スペック
#
# ビルド方法（project/ ディレクトリで実行）:
#   pyinstaller installer\setup_wizard.spec
#
# 出力: installer\dist\TW_Prophet_Setup_Wizard.exe

import glob
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # project/

# conda 環境では libffi (ffi-8.dll など) が Library\bin にある
# PyInstaller が自動収集しないため明示的にバンドルする
def _collect_ffi_dlls():
    env = Path(sys.executable).parent
    candidates = []
    for search_dir in [env / 'DLLs', env / 'Library' / 'bin', env]:
        if search_dir.exists():
            for pat in ['ffi*.dll', 'libffi*.dll', '_ctypes*.pyd']:
                for f in search_dir.glob(pat):
                    candidates.append((str(f), '.'))
    return candidates

a = Analysis(
    [str(ROOT / 'setup_wizard.py')],
    pathex=[str(ROOT)],
    binaries=_collect_ffi_dlls(),
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.ttk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas', 'numpy', 'xgboost', 'sklearn',
        'fastapi', 'uvicorn', 'sqlalchemy', 'pyodbc',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TW_Prophet_Setup_Wizard',
    debug=False,
    strip=False,
    upx=False,
    console=False,      # Tkinter GUI なのでコンソール不要
    icon=str(ROOT / 'icon.ico') if (ROOT / 'icon.ico').exists() else None,
    version=None,
)
