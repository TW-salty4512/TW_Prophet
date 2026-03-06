"""Public web wrapper."""

from public.tw_prophet_web import app

# ★変更点★ 公開版FastAPIアプリをエクスポート。
__all__ = ["app"]

