# -*- mode: python ; coding: utf-8 -*-
#
# TW_Prophet_Web.exe ビルド用 PyInstaller スペック
#
# ビルド方法（project/ ディレクトリで実行）:
#   pyinstaller installer\run_web.spec
#
# 出力: installer\dist\TW_Prophet_Web.exe

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent  # project/

def _collect_extra_dlls():
    """Collect DLLs that PyInstaller misses from conda envs."""
    env = Path(sys.executable).parent
    candidates = []
    patterns = {
        env / 'DLLs': ['ffi*.dll', 'libffi*.dll', '_ctypes*.pyd', 'pyexpat*.pyd'],
        env / 'Library' / 'bin': ['ffi*.dll', 'libffi*.dll', 'libexpat*.dll', 'expat*.dll'],
        env: ['ffi*.dll'],
    }
    for search_dir, pats in patterns.items():
        if search_dir.exists():
            for pat in pats:
                for f in search_dir.glob(pat):
                    candidates.append((str(f), '.'))
    return candidates

# collect_data_files('xgboost') includes VERSION, py.typed, and xgboost.dll
xgboost_datas = collect_data_files('xgboost')

a = Analysis(
    [str(ROOT / 'run_web.py')],
    pathex=[str(ROOT)],
    binaries=_collect_extra_dlls(),
    datas=[
        (str(ROOT / 'examples'), 'examples'),
        (str(ROOT / 'public'),   'public'),
    ] + xgboost_datas,
    hiddenimports=[
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # FastAPI / Starlette
        'fastapi',
        'fastapi.routing',
        'starlette',
        'starlette.routing',
        'starlette.responses',
        'starlette.middleware',
        'starlette.middleware.cors',
        'anyio',
        'anyio._backends._asyncio',
        # data processing
        'pandas',
        'numpy',
        'xgboost',
        'sklearn',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        # DB
        'pyodbc',
        'sqlalchemy',
        'sqlalchemy.dialects.mysql',
        'mysql',
        'mysql.connector',
        'mysql.connector.plugins',
        'mysql.connector.plugins.mysql_native_password',
        # holiday
        'jpholiday',
        # app modules
        'config',
        'tw_prophet_web',
        'api',
        'api.service',
        'api.routes',
        'model',
        'model.calendar',
        'model.metrics',
        'model.transforms',
        'model.features',
        'model.trainer',
        'model.evaluator',
        'model.store',
        'model_handler',
        'access_handler',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
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
    name='TW_Prophet_Web',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / 'icon.ico') if (ROOT / 'icon.ico').exists() else None,
    version=None,
)
