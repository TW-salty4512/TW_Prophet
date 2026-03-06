"""
tw_prophet_bridge.py

PHPから呼び出してTW_ProphetのAI需要予測を取得するブリッジスクリプト

使い方:
    python tw_prophet_bridge.py --barcode <バーコード> --months <予測月数>
    python tw_prophet_bridge.py --list  # バーコード一覧取得
    python tw_prophet_bridge.py --batch <barcode1,barcode2,...>  # バッチ予測

出力:
    JSON形式で予測結果を標準出力に出力

設置場所:
    \\file-server\データベース\TW_Prophet\tw_prophet_bridge.py
"""

import os
import sys
import json
import argparse

# TW_Prophetのパスを追加
TW_PROPHET_PATH = r"\\file-server\データベース\TW_Prophet"
if TW_PROPHET_PATH not in sys.path:
    sys.path.insert(0, TW_PROPHET_PATH)

# 標準エラー出力を抑制
import warnings
warnings.filterwarnings('ignore')

# TW_Prophetのモジュールをインポート
try:
    from model_handler import ModelHandler
    from access_handler import AccessHandler
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"TW_Prophetモジュールのインポートに失敗しました: {str(e)}",
        "error_type": "import_error"
    }), file=sys.stdout)
    sys.exit(1)


class TWProphetBridge:
    """TW_ProphetとPHP間のブリッジクラス"""
    
    def __init__(self):
        self.model_handler = None
        self.access_handler = None
        self.shipment_data = None
        self.inventory_data = None
        self._initialized = False
        
    def initialize(self) -> bool:
        """モジュールとデータを初期化"""
        if self._initialized:
            return True
            
        try:
            self.model_handler = ModelHandler()
            self.access_handler = AccessHandler()
            
            # データ読み込み
            self.shipment_data = self.access_handler.get_shipment_data()
            self.inventory_data = self.access_handler.get_inventory_data()
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(json.dumps({
                "success": False,
                "error": f"初期化エラー: {str(e)}",
                "error_type": "initialization_error"
            }), file=sys.stdout)
            return False
    
    def get_barcode_list(self) -> dict:
        """利用可能なバーコード一覧を取得"""
        if not self.initialize():
            return {"success": False, "error": "初期化に失敗しました"}
        
        try:
            barcodes = self.shipment_data['バーコード'].dropna().unique().tolist()
            barcodes = sorted([bc for bc in barcodes if bc and str(bc).strip()])
            
            return {
                "success": True,
                "barcodes": barcodes,
                "count": len(barcodes)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "barcode_list_error"
            }
    
    def predict_consumption(self, barcode: str, months: int = 6) -> dict:
        """指定バーコードの需要予測を取得"""
        if not self.initialize():
            return {"success": False, "error": "初期化に失敗しました"}
        
        try:
            # バーコードが存在するか確認
            if barcode not in self.shipment_data['バーコード'].values:
                return {
                    "success": False,
                    "error": f"バーコード '{barcode}' の出荷データがありません",
                    "error_type": "barcode_not_found"
                }
            
            # 週次リストを確認（weekly_data_list.json）
            weekly_list_path = os.path.join(TW_PROPHET_PATH, "weekly_data_list.json")
            weekly_set = set()
            if os.path.exists(weekly_list_path):
                try:
                    with open(weekly_list_path, "r", encoding="utf-8") as f:
                        weekly_set = set(json.load(f))
                except:
                    pass
            
            is_weekly = barcode in weekly_set
            
            # 予測を実行
            if is_weekly:
                consumption = self.model_handler.predict_consumption_for_n_months_weekly(
                    self.shipment_data, barcode, n=months
                )
            else:
                consumption = self.model_handler.predict_consumption_for_n_months_monthly(
                    self.shipment_data, barcode, n=months
                )
            
            # 現在の在庫を取得
            inv_row = self.inventory_data[self.inventory_data['バーコード'] == barcode]
            current_inventory = float(inv_row.iloc[0]['在庫数']) if not inv_row.empty else 0.0
            
            return {
                "success": True,
                "barcode": barcode,
                "mode": "weekly" if is_weekly else "monthly",
                "months": months,
                "predicted_consumption": float(consumption),
                "current_inventory": current_inventory,
                "stock_months_left": current_inventory / consumption if consumption > 0 else 9999
            }
            
        except Exception as e:
            return {
                "success": False,
                "barcode": barcode,
                "error": str(e),
                "error_type": "prediction_error"
            }
    
    def batch_predict(self, barcodes: list, months: int = 6) -> dict:
        """複数バーコードの一括予測"""
        if not self.initialize():
            return {"success": False, "error": "初期化に失敗しました"}
        
        results = {}
        errors = []
        
        for barcode in barcodes:
            result = self.predict_consumption(barcode, months)
            if result.get("success"):
                results[barcode] = {
                    "predicted_consumption": result.get("predicted_consumption", 0),
                    "current_inventory": result.get("current_inventory", 0),
                    "stock_months_left": result.get("stock_months_left", 9999),
                    "mode": result.get("mode", "monthly")
                }
            else:
                errors.append({
                    "barcode": barcode,
                    "error": result.get("error", "Unknown error")
                })
        
        return {
            "success": True,
            "results": results,
            "errors": errors,
            "total": len(barcodes),
            "succeeded": len(results),
            "failed": len(errors)
        }


def main():
    parser = argparse.ArgumentParser(description='TW_Prophet Bridge Script')
    parser.add_argument('--barcode', '-b', type=str, help='対象のバーコード')
    parser.add_argument('--months', '-m', type=int, default=6, help='予測月数（デフォルト: 6）')
    parser.add_argument('--list', '-l', action='store_true', help='バーコード一覧を取得')
    parser.add_argument('--batch', type=str, help='カンマ区切りのバーコードで一括予測')
    
    args = parser.parse_args()
    
    bridge = TWProphetBridge()
    
    if args.list:
        result = bridge.get_barcode_list()
    elif args.batch:
        barcodes = [bc.strip() for bc in args.batch.split(',') if bc.strip()]
        result = bridge.batch_predict(barcodes, args.months)
    elif args.barcode:
        result = bridge.predict_consumption(args.barcode, args.months)
    else:
        result = {
            "success": False,
            "error": "引数が指定されていません。--help で使い方を確認してください。",
            "error_type": "argument_error"
        }
    
    # JSON出力
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
