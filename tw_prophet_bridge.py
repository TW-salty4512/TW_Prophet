"""tw_prophet_bridge.py

Simple CLI bridge for batch prediction in the public release.
"""

from __future__ import annotations

import argparse
import json

from model_handler import ModelHandler
from public.access_handler import AccessHandler
from public.config import WEEKLY_JSON, load_json_list


class TWProphetBridge:
    def __init__(self):
        self.model_handler = ModelHandler()
        self.access_handler = AccessHandler()
        self.shipment_data = self.access_handler.get_shipment_data()
        self.inventory_data = self.access_handler.get_inventory_data()
        self.weekly_set = set(load_json_list(WEEKLY_JSON))

    def get_barcode_list(self) -> dict:
        barcodes = sorted({str(x).strip() for x in self.shipment_data["barcode"].tolist() if str(x).strip()})
        return {"success": True, "barcodes": barcodes, "count": len(barcodes)}

    def predict_consumption(self, barcode: str, months: int = 6) -> dict:
        if barcode not in set(self.shipment_data["barcode"].astype(str).tolist()):
            return {"success": False, "error": f"barcode not found: {barcode}"}

        # 公開版ではローカルサンプルデータを利用し、社内パス依存を排除。
        if barcode in self.weekly_set:
            mode = "weekly"
            consumption = self.model_handler.predict_consumption_for_n_months_weekly(self.shipment_data, barcode, n=months)
        else:
            mode = "monthly"
            consumption = self.model_handler.predict_consumption_for_n_months_monthly(self.shipment_data, barcode, n=months)

        inv_row = self.inventory_data[self.inventory_data["barcode"].astype(str) == str(barcode)]
        current_inventory = float(inv_row.iloc[0]["inventory"]) if not inv_row.empty else 0.0
        stock_months_left = (current_inventory / consumption) if consumption > 0 else 9999.0
        return {
            "success": True,
            "barcode": barcode,
            "mode": mode,
            "months": int(months),
            "predicted_consumption": float(consumption),
            "current_inventory": float(current_inventory),
            "stock_months_left": float(stock_months_left),
        }

    def batch_predict(self, barcodes: list[str], months: int = 6) -> dict:
        results = {}
        errors = []
        for barcode in barcodes:
            res = self.predict_consumption(barcode, months=months)
            if res.get("success"):
                results[barcode] = res
            else:
                errors.append({"barcode": barcode, "error": res.get("error", "unknown error")})
        return {
            "success": True,
            "results": results,
            "errors": errors,
            "total": len(barcodes),
            "succeeded": len(results),
            "failed": len(errors),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="TW_Prophet public bridge")
    parser.add_argument("--barcode", "-b", type=str, help="barcode")
    parser.add_argument("--months", "-m", type=int, default=6, help="forecast months")
    parser.add_argument("--list", "-l", action="store_true", help="list barcodes")
    parser.add_argument("--batch", type=str, help="comma separated barcodes")
    args = parser.parse_args()

    bridge = TWProphetBridge()
    if args.list:
        out = bridge.get_barcode_list()
    elif args.batch:
        values = [x.strip() for x in args.batch.split(",") if x.strip()]
        out = bridge.batch_predict(values, months=args.months)
    elif args.barcode:
        out = bridge.predict_consumption(args.barcode.strip(), months=args.months)
    else:
        out = {"success": False, "error": "no argument provided"}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

