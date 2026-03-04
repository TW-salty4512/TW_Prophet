"""daily_train_all.py

TW_Prophet のモデルを「毎日 21:00 に全製品(除外を除く)」で学習するためのバッチ。

狙い
 - Web版UIから学習ボタンを撤去し、学習頻度をユーザー操作に依存しない運用にする。
 - excluded_products.json / weekly_data_list.json を参照して、週次/月次を自動で振り分け。
 - 学習済みモデルの保存先は TW_PROPHET_MODELS_DIR（未指定なら DATA_DIR/models）。

実行例:
  python daily_train_all.py

環境変数(任意)
  - TW_PROPHET_DATA_DIR   : excluded_products.json / weekly_data_list.json を置くディレクトリ
  - TW_PROPHET_MODELS_DIR : 学習済みモデル(pkl)の保存先
  - TW_PROPHET_LOG_DIR    : ログ出力先ディレクトリ(未指定なら DATA_DIR/logs)

メモ
 - Windows タスクスケジューラで 21:00 実行にするのが推奨。
 - conda 環境で動かす場合は「conda環境のpython.exe」を直接指定するか、conda run を使う。
"""

from __future__ import annotations

import json
import os
from datetime import datetime


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_json_list(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _log_write(fp, msg: str) -> None:
    fp.write(f"[{_now_str()}] {msg}\n")
    fp.flush()


def main() -> int:
    # tw_prophet_web.py と同じディレクトリ仕様に寄せる
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.getenv("TW_PROPHET_DATA_DIR", base_dir)
    models_dir = os.getenv("TW_PROPHET_MODELS_DIR", os.path.join(data_dir, "models"))
    log_dir = os.getenv("TW_PROPHET_LOG_DIR", os.path.join(data_dir, "logs"))

    _ensure_dir(data_dir)
    _ensure_dir(models_dir)
    _ensure_dir(log_dir)

    excluded_json = os.path.join(data_dir, "excluded_products.json")
    weekly_json = os.path.join(data_dir, "weekly_data_list.json")

    # ログは日付単位でローテ（タスクスケジューラで結果を追えるように）
    log_path = os.path.join(log_dir, f"daily_train_{datetime.now().strftime('%Y%m%d')}.log")

    # 既存ロジックを利用
    try:
        from access_handler import AccessHandler
        from model_handler import ModelHandler
    except Exception as e:
        print(f"[FATAL] import 失敗: {e}")
        return 2

    with open(log_path, "a", encoding="utf-8") as fp:
        _log_write(fp, "==== daily_train_all START ====")
        _log_write(fp, f"DATA_DIR={data_dir}")
        _log_write(fp, f"MODELS_DIR={models_dir}")

        excluded = set(_load_json_list(excluded_json))
        weekly_set = set(_load_json_list(weekly_json))

        _log_write(fp, f"excluded count={len(excluded)}")
        _log_write(fp, f"weekly count={len(weekly_set)}")

        # DB取得
        try:
            ah = AccessHandler()
            shipment = ah.get_shipment_data()
            shipment = shipment[shipment["バーコード"].notnull()]
        except Exception as e:
            _log_write(fp, f"[FATAL] DB取得失敗: {e}")
            _log_write(fp, "==== daily_train_all END (FAILED) ====")
            return 1

        barcodes = [bc for bc in shipment["バーコード"].unique().tolist() if bc]
        barcodes = sorted(barcodes)
        target = [bc for bc in barcodes if bc not in excluded]

        _log_write(fp, f"all barcodes={len(barcodes)} / train targets(excluded removed)={len(target)}")

        mh = ModelHandler()
        mh.model_dir = models_dir
        _ensure_dir(mh.model_dir)

        ok = 0
        ng = 0
        failed: list[str] = []

        for i, bc in enumerate(target, start=1):
            mode = "weekly" if bc in weekly_set else "monthly"
            try:
                if mode == "weekly":
                    mh.train_product_model_weekly(shipment, bc)
                else:
                    mh.train_product_model_monthly(shipment, bc)

                ok += 1
                if i % 10 == 0:
                    _log_write(fp, f"progress {i}/{len(target)} ok={ok} ng={ng}")
            except Exception as e:
                ng += 1
                failed.append(bc)
                _log_write(fp, f"[WARN] train failed: {bc} ({mode}) -> {e}")

        _log_write(fp, f"DONE ok={ok} ng={ng}")
        if failed:
            _log_write(fp, "FAILED LIST: " + ", ".join(failed[:100]) + (" ..." if len(failed) > 100 else ""))

        _log_write(fp, "==== daily_train_all END ====")

    return 0 if ng == 0 else 0  # バッチ運用上は部分失敗でも 0 にして停止連鎖を避ける


if __name__ == "__main__":
    raise SystemExit(main())
