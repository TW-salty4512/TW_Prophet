"""
tw_prophet_bridge.py

PHP から呼び出して TW_Prophet の AI 需要予測を取得するブリッジスクリプト。

使い方:
    python tw_prophet_bridge.py --barcode <バーコード> --months <予測月数>
    python tw_prophet_bridge.py --list
    python tw_prophet_bridge.py --batch <barcode1,barcode2,...>

出力:
    JSON 形式で予測結果を標準出力に出力

設定:
    TW_PROPHET_PATH 環境変数でモジュールの場所を指定する。
    未設定の場合はこのスクリプトと同じディレクトリを使用する。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------
# パス解決（環境変数 > スクリプト同階層）
# ------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TW_PROPHET_PATH = os.environ.get("TW_PROPHET_PATH", _SCRIPT_DIR)

if TW_PROPHET_PATH not in sys.path:
    sys.path.insert(0, TW_PROPHET_PATH)

try:
    import config
    from model_handler import ModelHandler
    from access_handler import AccessHandler
except ImportError as e:
    print(
        json.dumps(
            {"success": False, "error": f"TW_Prophetモジュールのインポートに失敗しました: {e}",
             "error_type": "import_error"},
            ensure_ascii=False,
        )
    )
    sys.exit(1)


class TWProphetBridge:
    """TW_Prophet と PHP 間のブリッジクラス。"""

    def __init__(self) -> None:
        self.model_handler: ModelHandler | None = None
        self.access_handler: AccessHandler | None = None
        self.shipment_data = None
        self.inventory_data = None
        self._initialized = False
        self._weekly_list_path = config.WEEKLY_JSON

    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            self.model_handler = ModelHandler()
            self.access_handler = AccessHandler()
            self.shipment_data = self.access_handler.get_shipment_data()
            self.inventory_data = self.access_handler.get_inventory_data()
            self._initialized = True
            return True
        except Exception as e:
            print(
                json.dumps(
                    {"success": False, "error": f"初期化エラー: {e}",
                     "error_type": "initialization_error"},
                    ensure_ascii=False,
                )
            )
            return False

    def get_barcode_list(self) -> dict:
        if not self.initialize():
            return {"success": False, "error": "初期化に失敗しました"}
        try:
            barcodes = sorted(
                [bc for bc in self.shipment_data["バーコード"].dropna().unique()
                 if bc and str(bc).strip()]
            )
            return {"success": True, "barcodes": barcodes, "count": len(barcodes)}
        except Exception as e:
            return {"success": False, "error": str(e), "error_type": "barcode_list_error"}

    def predict_consumption(self, barcode: str, months: int = 6) -> dict:
        if not self.initialize():
            return {"success": False, "error": "初期化に失敗しました"}
        try:
            if barcode not in self.shipment_data["バーコード"].values:
                return {
                    "success": False,
                    "error": f"バーコード '{barcode}' の出荷データがありません",
                    "error_type": "barcode_not_found",
                }

            weekly_set: set[str] = set()
            p = self._weekly_list_path
            if p.exists():
                try:
                    with p.open(encoding="utf-8") as f:
                        weekly_set = set(json.load(f))
                except Exception:
                    pass

            is_weekly = barcode in weekly_set
            if is_weekly:
                consumption = self.model_handler.predict_consumption_for_n_months_weekly(
                    self.shipment_data, barcode, n=months
                )
            else:
                consumption = self.model_handler.predict_consumption_for_n_months_monthly(
                    self.shipment_data, barcode, n=months
                )

            inv_row = self.inventory_data[self.inventory_data["バーコード"] == barcode]
            current_inventory = float(inv_row.iloc[0]["在庫数"]) if not inv_row.empty else 0.0

            return {
                "success": True,
                "barcode": barcode,
                "mode": "weekly" if is_weekly else "monthly",
                "months": months,
                "predicted_consumption": float(consumption),
                "current_inventory": current_inventory,
                "stock_months_left": current_inventory / consumption if consumption > 0 else 9999,
            }
        except Exception as e:
            return {"success": False, "barcode": barcode, "error": str(e),
                    "error_type": "prediction_error"}

    def batch_predict(self, barcodes: list[str], months: int = 6) -> dict:
        if not self.initialize():
            return {"success": False, "error": "初期化に失敗しました"}
        results: dict = {}
        errors: list = []
        for barcode in barcodes:
            r = self.predict_consumption(barcode, months)
            if r.get("success"):
                results[barcode] = {
                    "predicted_consumption": r.get("predicted_consumption", 0),
                    "current_inventory": r.get("current_inventory", 0),
                    "stock_months_left": r.get("stock_months_left", 9999),
                    "mode": r.get("mode", "monthly"),
                }
            else:
                errors.append({"barcode": barcode, "error": r.get("error", "Unknown error")})
        return {
            "success": True, "results": results, "errors": errors,
            "total": len(barcodes), "succeeded": len(results), "failed": len(errors),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="TW_Prophet Bridge Script")
    parser.add_argument("--barcode", "-b", type=str, help="対象のバーコード")
    parser.add_argument("--months",  "-m", type=int, default=6, help="予測月数（既定: 6）")
    parser.add_argument("--list",    "-l", action="store_true", help="バーコード一覧を取得")
    parser.add_argument("--batch",          type=str, help="カンマ区切りのバーコードで一括予測")
    args = parser.parse_args()

    bridge = TWProphetBridge()

    if args.list:
        result = bridge.get_barcode_list()
    elif args.batch:
        barcodes = [bc.strip() for bc in args.batch.split(",") if bc.strip()]
        result = bridge.batch_predict(barcodes, args.months)
    elif args.barcode:
        result = bridge.predict_consumption(args.barcode, args.months)
    else:
        result = {
            "success": False,
            "error": "引数が指定されていません。--help で使い方を確認してください。",
            "error_type": "argument_error",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
