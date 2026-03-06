from __future__ import annotations

import os

import uvicorn


class TWProphetPublicApp:
    def __init__(self):
        self.host = os.getenv("TW_WEB_HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))

    def run(self) -> None:
        # 公開版はデスクトップGUIではなくWeb API/UI起動に統一。
        uvicorn.run("public.tw_prophet_web:app", host=self.host, port=self.port, reload=False, log_level="info")


class TW_prophet(TWProphetPublicApp):
    pass


def main() -> int:
    TWProphetPublicApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

