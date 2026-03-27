"""
tw_prophet_web.py  –  TW_Prophet Web エントリーポイント

責務:
  - FastAPI アプリを生成してルーターをマウント
  - サービスインスタンスをルーターにバインド
  - python tw_prophet_web.py 直実行 or run_web.py から uvicorn で起動

環境変数 (config.py 参照):
  PORT, TW_DATA_MODE, TW_PROPHET_DATA_DIR, TW_PROPHET_MODELS_DIR, ...
"""
from __future__ import annotations

import os

from fastapi import FastAPI

import config

# サービス層とルーター
if config.is_sample_mode():
    # sample モード: CSV ベースのハンドラを使う公開版サービス
    from public.tw_prophet_web import app as _public_app  # type: ignore
    app = _public_app
else:
    # internal モード: MDB/MySQL ベース
    from api.service import TWProphetWebService
    from api.routes import router, bind_service

    svc = TWProphetWebService()
    bind_service(svc)

    app = FastAPI(title="TW_Prophet Web", version="0.3")
    app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "tw_prophet_web:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=False,
        log_level="info",
    )
