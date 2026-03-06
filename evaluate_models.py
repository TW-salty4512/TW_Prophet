"""
evaluate_models.py

Usage:
    python evaluate_models.py
    python evaluate_models.py --top-n 30 --selection random --train-missing
"""
import argparse
import os
from datetime import datetime

import numpy as np
import pandas as pd

from access_handler import AccessHandler
from model_handler import ModelHandler


def _load_weekly_set(base_dir: str) -> set:
    weekly_json = os.path.join(base_dir, "weekly_data_list.json")
    if not os.path.exists(weekly_json):
        return set()
    try:
        arr = pd.read_json(weekly_json, typ="series")
        return set(arr.astype(str).tolist())
    except Exception:
        return set()


def _select_barcodes(shipment: pd.DataFrame, barcode_col: str, qty_col: str, top_n: int, selection: str, seed: int):
    totals = (
        shipment[[barcode_col, qty_col]]
        .assign(**{barcode_col: shipment[barcode_col].astype(str)})
        .groupby(barcode_col, as_index=False)[qty_col]
        .sum()
        .sort_values(qty_col, ascending=False)
    )
    totals = totals[totals[barcode_col].notna() & (totals[barcode_col] != "")]
    if totals.empty:
        return []

    all_barcodes = totals[barcode_col].tolist()
    n = max(1, min(int(top_n), len(all_barcodes)))

    # ★ 点★ 改修前/改修後比較しやすいように選定方法をCLIで切替可能にした
    if selection == "random":
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(all_barcodes), size=n, replace=False)
        return [all_barcodes[i] for i in idx]
    return all_barcodes[:n]


def _format_float(x):
    if x is None:
        return ""
    try:
        return f"{float(x):.4f}"
    except Exception:
        return ""


def parse_args():
    p = argparse.ArgumentParser(description="Evaluate TW_Prophet weekly/monthly walk-forward metrics.")
    p.add_argument("--top-n", type=int, default=20, help="Number of barcodes to evaluate.")
    p.add_argument("--selection", choices=["top", "random"], default="top", help="Barcode selection strategy.")
    p.add_argument("--seed", type=int, default=42, help="Random seed for random selection.")
    p.add_argument("--weekly-test-weeks", type=int, default=12, help="Weekly walk-forward test window.")
    p.add_argument("--monthly-test-months", type=int, default=12, help="Monthly walk-forward test window.")
    p.add_argument("--train-missing", action="store_true", help="Train model first if pkl is missing.")
    p.add_argument("--output", default="", help="Output CSV path. default: ./evaluation_results_YYYYmmdd_HHMMSS.csv")
    return p.parse_args()


def main():
    args = parse_args()
    base_dir = os.getenv("TW_PROPHET_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    weekly_set = _load_weekly_set(base_dir)

    print("[INFO] Loading shipment data from Access...")
    ah = AccessHandler()
    mh = ModelHandler()
    shipment = ah.get_shipment_data()

    date_col, barcode_col, qty_col, _ = mh._resolve_shipment_columns(shipment)
    shipment = shipment[shipment[barcode_col].notnull()].copy()
    shipment[barcode_col] = shipment[barcode_col].astype(str)
    shipment[qty_col] = pd.to_numeric(shipment[qty_col], errors="coerce").fillna(0.0)

    barcodes = _select_barcodes(
        shipment=shipment,
        barcode_col=barcode_col,
        qty_col=qty_col,
        top_n=args.top_n,
        selection=args.selection,
        seed=args.seed,
    )
    if not barcodes:
        print("[ERROR] No barcode found.")
        return 1

    print(f"[INFO] evaluate target count = {len(barcodes)} (selection={args.selection})")

    rows = []
    for i, bc in enumerate(barcodes, start=1):
        mode = "weekly" if bc in weekly_set else "monthly"
        model_path = os.path.join(mh.model_dir, f"{mode}_{bc}.pkl")
        model_exists = os.path.exists(model_path)

        print(f"[{i:03d}/{len(barcodes):03d}] {bc} mode={mode} model_exists={model_exists}")
        try:
            if args.train_missing and (not model_exists):
                # ★ 点★ モデル未作成バーコードでも即時評価できるように任意学習を追加
                if mode == "weekly":
                    mh.train_product_model_weekly(shipment, bc)
                else:
                    mh.train_product_model_monthly(shipment, bc)

            if mode == "weekly":
                res = mh.evaluate_weekly_walk_forward(
                    shipment_data=shipment,
                    barcode=bc,
                    test_weeks=args.weekly_test_weeks,
                )
            else:
                res = mh.evaluate_monthly_walk_forward(
                    shipment_data=shipment,
                    barcode=bc,
                    test_months=args.monthly_test_months,
                )

            rows.append(
                {
                    "barcode": bc,
                    "mode": mode,
                    "train_size": int(res.get("train_size", 0)),
                    "test_size": int(res.get("test_size", 0)),
                    "rmse": float(res.get("rmse", np.nan)),
                    "mae": float(res.get("mae", np.nan)),
                    "smape": float(res.get("smape", np.nan)),
                    "use_log1p": bool(res.get("use_log1p", False)),
                    "model_exists_before_eval": bool(model_exists),
                    "error": "",
                }
            )
        except Exception as e:
            rows.append(
                {
                    "barcode": bc,
                    "mode": mode,
                    "train_size": 0,
                    "test_size": 0,
                    "rmse": np.nan,
                    "mae": np.nan,
                    "smape": np.nan,
                    "use_log1p": False,
                    "model_exists_before_eval": bool(model_exists),
                    "error": str(e),
                }
            )

    result_df = pd.DataFrame(rows)
    ok_df = result_df[result_df["error"] == ""].copy()
    ng_df = result_df[result_df["error"] != ""].copy()

    print("\n===== Evaluation Summary =====")
    print(f"total={len(result_df)} ok={len(ok_df)} ng={len(ng_df)}")
    if not ok_df.empty:
        summary = (
            ok_df.groupby("mode")[["rmse", "mae", "smape"]]
            .mean()
            .reset_index()
            .sort_values("mode")
        )
        print("\n[Mean metrics by mode]")
        for _, r in summary.iterrows():
            print(
                f"mode={r['mode']:<7} "
                f"RMSE={_format_float(r['rmse'])} "
                f"MAE={_format_float(r['mae'])} "
                f"sMAPE={_format_float(r['smape'])}"
            )

        print("\n[Top 10 best by sMAPE]")
        show_cols = ["barcode", "mode", "rmse", "mae", "smape", "test_size", "use_log1p"]
        top = ok_df.sort_values("smape", ascending=True).head(10)[show_cols]
        print(top.to_string(index=False))

    if not ng_df.empty:
        print("\n[Errors]")
        print(ng_df[["barcode", "mode", "error"]].to_string(index=False))

    if args.output:
        out_csv = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = os.path.join(base_dir, f"evaluation_results_{ts}.csv")

    result_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n[INFO] saved: {out_csv}")
    print("Run command: python evaluate_models.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
