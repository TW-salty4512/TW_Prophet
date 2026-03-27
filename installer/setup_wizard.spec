# -*- mode: python ; coding: utf-8 -*-
#
# TW_Prophet_Setup_Wizard.exe ビルド用 PyInstaller スペック
#
# ビルド方法（project/ ディレクトリで実行）:
#   pyinstaller installer\setup_wizard.spec
#
# 出力: installer\dist\TW_Prophet_Setup_Wizard.exe

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # project/

# conda 環境では libffi・_tkinter・tcl/tk DLL が Library\bin や DLLs にある。
# PyInstaller が自動収集しないため明示的にバンドルする。
def _collect_conda_dlls():
    env = Path(sys.executable).parent
    bins = []
    for search_dir in [env / 'DLLs', env / 'Library' / 'bin', env]:
        if not search_dir.exists():
            continue
        for pat in [
            'ffi*.dll', 'libffi*.dll', '_ctypes*.pyd',   # ctypes
            '_tkinter*.pyd', 'tcl8*.dll', 'tk8*.dll',    # tkinter
            'tcl86*.dll', 'tk86*.dll',
        ]:
            for f in search_dir.glob(pat):
                bins.append((str(f), '.'))
    return bins

def _collect_tcl_data():
    """tcl8.6 / tk8.6 ライブラリデータを datas に追加する。"""
    env = Path(sys.executable).parent
    datas = []
    lib_dir = env / 'Library' / 'lib'
    if not lib_dir.exists():
        lib_dir = env / 'lib'
    for name in ('tcl8.6', 'tk8.6'):
        d = lib_dir / name
        if d.exists():
            datas.append((str(d), name))
    return datas

a = Analysis(
    [str(ROOT / 'setup_wizard.py')],
    pathex=[str(ROOT)],
    binaries=_collect_conda_dlls(),
    datas=_collect_tcl_data(),
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.ttk',
        '_tkinter',
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
    console=False,
    icon=str(ROOT / 'icon.ico') if (ROOT / 'icon.ico').exists() else None,
    version=None,
)
