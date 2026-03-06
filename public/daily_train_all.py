from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from model_handler import ModelHandler
from public.access_handler import AccessHandler
from public.config import EXCLUDED_JSON, LOG_DIR, MODELS_DIR, WEEKLY_JSON, ensure_dirs, load_json_list


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_log(fp, message: str) -> None:
    fp.write(f"[{_now_str()}] {message}\n")
    fp.flush()


def main() -> int:
    ensure_dirs()
    log_path = LOG_DIR / f"daily_train_{datetime.now().strftime('%Y%m%d')}.log"

    excluded = set(load_json_list(EXCLUDED_JSON))
    weekly_set = set(load_json_list(WEEKLY_JSON))

    with log_path.open("a", encoding="utf-8") as fp:
        _write_log(fp, "==== public daily_train_all START ====")
        _write_log(fp, f"MODELS_DIR={MODELS_DIR}")

        ah = AccessHandler()
        shipment = ah.get_shipment_data()
        if shipment.empty:
            _write_log(fp, "[WARN] shipment data is empty.")
            _write_log(fp, "==== public daily_train_all END ====")
            return 0

        barcodes = sorted({str(x).strip() for x in shipment["barcode"].tolist() if str(x).strip()})
        targets = [bc for bc in barcodes if bc not in excluded]
        _write_log(fp, f"all={len(barcodes)} targets={len(targets)} excluded={len(excluded)}")

        mh = ModelHandler()
        mh.model_dir = str(MODELS_DIR)
        os.makedirs(mh.model_dir, exist_ok=True)

        ok = 0
        ng = 0
        for idx, barcode in enumerate(targets, start=1):
            mode = "weekly" if barcode in weekly_set else "monthly"
            try:
                # 公開版はサンプルCSVから学習し、社内DB依存を持たない。
                if mode == "weekly":
                    mh.train_product_model_weekly(shipment, barcode)
                else:
                    mh.train_product_model_monthly(shipment, barcode)
                ok += 1
            except Exception as ex:
                ng += 1
                _write_log(fp, f"[WARN] train failed barcode={barcode} mode={mode} error={ex}")
            if idx % 10 == 0 or idx == len(targets):
                _write_log(fp, f"progress {idx}/{len(targets)} ok={ok} ng={ng}")

        _write_log(fp, f"done ok={ok} ng={ng}")
        _write_log(fp, "==== public daily_train_all END ====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

