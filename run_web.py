"""run_web.py

TW_Prophet Web を起動するためのランチャ。

起動:
  python run_web.py

※本番では uvicorn をサービス化(NSSM / タスクスケジューラ / systemd 等)して常駐させる。
"""

from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    # ポートを環境変数で切替できるように
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "tw_prophet_web:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
