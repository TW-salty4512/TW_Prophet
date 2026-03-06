"""Public web launcher."""

from public.run_web import main

# ★変更点★ 公開版Webランチャーへ委譲。
__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())

