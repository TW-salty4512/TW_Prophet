from __future__ import annotations

import os
import sys

import uvicorn


def main() -> int:
    port = int(os.getenv("PORT", "8000"))
    use_gui_launcher = (getattr(sys, "stdout", None) is None) or (getattr(sys, "stderr", None) is None)
    kwargs = {}
    if use_gui_launcher:
        kwargs["log_config"] = None

    # ★変更点★ 公開版Webエントリを使用。
    uvicorn.run(
        "public.tw_prophet_web:app",
        host=os.getenv("TW_WEB_HOST", "0.0.0.0"),
        port=port,
        reload=False,
        log_level="info",
        **kwargs,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

