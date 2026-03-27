"""run_web.py

Launcher for TW_Prophet Web.

Usage:
  python   run_web.py          # 通常起動（コンソール表示あり）
  pythonw  run_web.py          # 隠し起動（タスクスケジューラから呼び出す）
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _setup_file_logging(log_path: Path) -> None:
    """stdout/stderr が使えない環境（pythonw / SYSTEM タスク）でログをファイルへ書く。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )
    # uvicorn が print() を使う箇所をファイルへリダイレクト
    sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    # pythonw.exe 実行時は stdout/stderr が None（コンソールなし）
    no_console = (getattr(sys, "stdout", None) is None) or (
        getattr(sys, "stderr", None) is None
    )

    if no_console:
        # ログを ProgramData\TW_Prophet\logs\service.log へ
        _prog_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
        _log_file  = _prog_data / "TW_Prophet" / "logs" / "service.log"
        _setup_file_logging(_log_file)

    # PyInstaller バンドル時は文字列参照が動作しないためオブジェクトを直接渡す
    from tw_prophet_web import app  # noqa: E402

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        log_config=None if no_console else None,
    )
