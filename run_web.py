"""run_web.py

Launcher for TW_Prophet Web.

Usage:
  python run_web.py
"""

from __future__ import annotations

import os
import sys

import uvicorn


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))

    # pythonw.exe 実行時は stdout/stderr が None になるため、
    # uvicorn デフォルトの log_config 初期化エラーを回避する。
    use_gui_launcher = (getattr(sys, "stdout", None) is None) or (
        getattr(sys, "stderr", None) is None
    )
    uvicorn_kwargs = {}
    if use_gui_launcher:
        uvicorn_kwargs["log_config"] = None

    uvicorn.run(
        "tw_prophet_web:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        **uvicorn_kwargs,
    )