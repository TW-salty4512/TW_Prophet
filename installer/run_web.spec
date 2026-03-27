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

ROOT = Path(SPECPATH).parent  # project/

a = Analysis(
    [str(ROOT / 'run_web.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # サンプルデータ・静的ファイル
        (str(ROOT / 'examples'), 'examples'),
        (str(ROOT / 'public'),   'public'),
    ],
    hiddenimports=[
        # uvicorn 内部モジュール（文字列ではなくオブジェクト渡しでも必要）
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
        # データ処理
        'pandas',
        'numpy',
        'xgboost',
        'sklearn',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        # DB 接続（internal モード）
        'pyodbc',
        'sqlalchemy',
        'sqlalchemy.dialects.mysql',
        'mysql',
        'mysql.connector',
        'mysql.connector.plugins',
        'mysql.connector.plugins.mysql_native_password',
        # 祝日計算
        'jpholiday',
        # アプリ内モジュール
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
        # 不要な大型パッケージを除外してサイズ削減
        'tkinter',
        'matplotlib',
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
    upx=False,          # UPX はウイルス誤検知の原因になるため無効
    console=False,      # コンソールウィンドウを非表示
    icon=str(ROOT / 'icon.ico') if (ROOT / 'icon.ico').exists() else None,
    version=None,
)
