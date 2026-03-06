from __future__ import annotations

from public.run_web import main

# 公開版の明示的エントリポイントを追加。
if __name__ == "__main__":
    raise SystemExit(main())

