"""
tests/test_model_store.py  –  model/store.py の単体テスト
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModelStore:
    def test_save_and_load_roundtrip(self):
        from model.store import save_model, load_model

        # ダミーモデルオブジェクト
        dummy_model = {"weights": [1, 2, 3]}
        meta = {"feature_cols": ["a", "b"], "use_log1p": False}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_model(tmpdir, "BARCODE-X", dummy_model, model_type="monthly", meta=meta)
            assert Path(path).exists()

            loaded = load_model(tmpdir, "BARCODE-X", model_type="monthly")
            assert loaded is not None
            assert loaded["model"] == dummy_model
            assert loaded["meta"]["use_log1p"] is False

    def test_load_nonexistent_returns_none(self):
        from model.store import load_model
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_model(tmpdir, "NO_SUCH_BARCODE")
            assert result is None

    def test_list_saved_barcodes(self):
        from model.store import save_model, list_saved_barcodes

        with tempfile.TemporaryDirectory() as tmpdir:
            save_model(tmpdir, "A-001", {}, model_type="monthly")
            save_model(tmpdir, "A-002", {}, model_type="weekly")
            save_model(tmpdir, "A-001", {}, model_type="weekly")

            all_barcodes = list_saved_barcodes(tmpdir)
            assert "A-001" in all_barcodes
            assert "A-002" in all_barcodes

            weekly_only = list_saved_barcodes(tmpdir, model_type="weekly")
            assert "A-001" in weekly_only
            assert "A-002" in weekly_only

            monthly_only = list_saved_barcodes(tmpdir, model_type="monthly")
            assert "A-001" in monthly_only
