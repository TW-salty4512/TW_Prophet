"""Public application entrypoint."""

from public.app import TWProphetPublicApp, TW_prophet, main

# ★変更点★ 社内GUI実装を公開版Web起動実装へ置換。
__all__ = ["TWProphetPublicApp", "TW_prophet", "main"]


if __name__ == "__main__":
    raise SystemExit(main())

