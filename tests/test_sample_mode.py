"""
tests/test_sample_mode.py  –  sample モード（CSV ベース）の統合テスト

依存:
    pip install pytest
実行:
    cd project
    TW_DATA_MODE=sample pytest tests/test_sample_mode.py -v
    または:
    pytest tests/test_sample_mode.py -v
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# サンプルデータのパス（テスト専用に examples/ を使う）
# ---------------------------------------------------------------------------
EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "sample_data"
SAMPLE_SHIP  = EXAMPLES_DIR / "shipments.csv"
SAMPLE_INV   = EXAMPLES_DIR / "inventory.csv"
SAMPLE_PARTS = EXAMPLES_DIR / "parts.csv"

skip_if_no_samples = pytest.mark.skipif(
    not SAMPLE_SHIP.exists(),
    reason="examples/sample_data/ が存在しません"
)


# ---------------------------------------------------------------------------
# サンプル CSV 読み込みテスト
# ---------------------------------------------------------------------------

@skip_if_no_samples
class TestSampleCsv:
    def test_shipments_csv_loads(self):
        df = pd.read_csv(SAMPLE_SHIP)
        assert len(df) > 0, "shipments.csv が空です"

    def test_shipments_required_columns(self):
        df = pd.read_csv(SAMPLE_SHIP)
        # ModelHandler が扱える列名が含まれているか（日英どちらでも可）
        date_like  = any(c.lower() in ("ds", "date", "出荷完了日") for c in df.columns)
        bcode_like = any(c.lower() in ("barcode", "バーコード") for c in df.columns)
        qty_like   = any(c.lower() in ("quantity", "qty", "数量") for c in df.columns)
        assert date_like,  f"日付列が見つかりません: {list(df.columns)}"
        assert bcode_like, f"バーコード列が見つかりません: {list(df.columns)}"
        assert qty_like,   f"数量列が見つかりません: {list(df.columns)}"

    def test_inventory_csv_loads(self):
        df = pd.read_csv(SAMPLE_INV)
        assert len(df) > 0

    def test_parts_csv_loads(self):
        df = pd.read_csv(SAMPLE_PARTS)
        assert len(df) > 0


# ---------------------------------------------------------------------------
# public/access_handler.py（サンプルCSV ベース）のテスト
# ---------------------------------------------------------------------------

class TestPublicAccessHandler:
    def setup_method(self):
        # sample モード用の環境変数を設定
        os.environ["TW_DATA_MODE"] = "sample"
        # public/ の config パスを向ける
        os.environ["TW_PUBLIC_DATA_DIR"]   = str(EXAMPLES_DIR)
        os.environ["TW_PUBLIC_CONFIG_DIR"] = str(Path(__file__).parent.parent / "examples" / "sample_config")

    @skip_if_no_samples
    def test_get_shipment_data(self):
        # public 版 AccessHandler をインポート
        sys.path.insert(0, str(Path(__file__).parent.parent / "public"))
        try:
            import importlib
            import public.access_handler as pah
            importlib.reload(pah)
            handler = pah.SampleDataHandler()
            df = handler.get_shipment_data()
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
        finally:
            sys.path.pop(0)

    @skip_if_no_samples
    def test_get_inventory_data(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "public"))
        try:
            import importlib
            import public.access_handler as pah
            importlib.reload(pah)
            handler = pah.SampleDataHandler()
            df = handler.get_inventory_data()
            assert isinstance(df, pd.DataFrame)
        finally:
            sys.path.pop(0)


# ---------------------------------------------------------------------------
# ModelHandler の最小動作テスト（サンプルデータで訓練→予測）
# ---------------------------------------------------------------------------

@skip_if_no_samples
class TestModelHandlerSample:
    def test_train_and_predict_monthly(self):
        """サンプルデータで月次モデルを訓練し、予測が正の数値を返すことを確認。"""
        import tempfile
        from model_handler import ModelHandler

        df = pd.read_csv(SAMPLE_SHIP)
        # 列名正規化
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if cl in ("ds", "date", "出荷完了日"):
                col_map[c] = "出荷完了日"
            elif cl in ("barcode", "バーコード"):
                col_map[c] = "バーコード"
            elif cl in ("quantity", "qty", "数量"):
                col_map[c] = "数量"
        df = df.rename(columns=col_map)
        df["出荷完了日"] = pd.to_datetime(df["出荷完了日"], errors="coerce")
        df = df[df["数量"] > 0].dropna(subset=["出荷完了日"])

        barcodes = df["バーコード"].unique().tolist()
        if not barcodes:
            pytest.skip("サンプルデータにバーコードがありません")

        barcode = barcodes[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            mh = ModelHandler()
            mh.model_dir = tmpdir

            # データ数が少ない場合はスキップ
            rows = df[df["バーコード"] == barcode]
            if len(rows) < 12:
                pytest.skip(f"バーコード {barcode} のデータ数が不足しています ({len(rows)}件)")

            mh.train_product_model_monthly(df, barcode)
            result = mh.predict_consumption_for_n_months_monthly(df, barcode, n=3)
            assert isinstance(result, float), f"予測結果が float でありません: {result}"
            assert result >= 0, f"予測値が負の数です: {result}"
