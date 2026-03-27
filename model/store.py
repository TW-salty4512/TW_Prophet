"""
model/store.py  –  モデルの保存/読み込みユーティリティ

ModelHandler の _save_model / _load_model と同等のスタンドアロン実装。
将来の完全分割に向けた第一歩として単独でも使えるようにしておく。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import joblib


def model_path(model_dir: str | Path, barcode: str, model_type: str) -> str:
    return os.path.join(str(model_dir), f"{model_type}_{barcode}.pkl")


def save_model(
    model_dir: str | Path,
    barcode: str,
    model: Any,
    model_type: str = "weekly",
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """モデルと meta 情報を pkl に保存する。保存パスを返す。"""
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    path = model_path(model_dir, barcode, model_type)
    payload = {"model": model, "meta": meta or {}}
    joblib.dump(payload, path)
    return path


def load_model(model_dir: str | Path, barcode: str, model_type: str = "weekly") -> Any | None:
    """pkl から payload を読み込む。存在しなければ None を返す。"""
    path = model_path(model_dir, barcode, model_type)
    if not os.path.exists(path):
        return None
    return joblib.load(path)


def list_saved_barcodes(model_dir: str | Path, model_type: str | None = None) -> list[str]:
    """model_dir 内の保存済みバーコード一覧を返す。"""
    d = Path(model_dir)
    if not d.exists():
        return []
    barcodes = []
    for f in d.glob("*.pkl"):
        stem = f.stem  # e.g. "monthly_PRODUCT-A"
        if model_type:
            prefix = f"{model_type}_"
            if stem.startswith(prefix):
                barcodes.append(stem[len(prefix):])
        else:
            parts = stem.split("_", 1)
            if len(parts) == 2:
                barcodes.append(parts[1])
    return sorted(set(barcodes))
