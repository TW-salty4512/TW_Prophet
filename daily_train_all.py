"""Public batch-training entrypoint."""

from public.daily_train_all import main

# ★変更点★ 公開版サンプルデータ学習バッチへ委譲。
__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())

