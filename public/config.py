from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# 公開版の設定/データパスを集約し、社内固有パス依存を排除。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE_DATA_DIR = PROJECT_ROOT / "examples" / "sample_data"
DEFAULT_SAMPLE_CONFIG_DIR = PROJECT_ROOT / "examples" / "sample_config"

DATA_DIR = Path(os.getenv("TW_PUBLIC_DATA_DIR", str(DEFAULT_SAMPLE_DATA_DIR)))
CONFIG_DIR = Path(os.getenv("TW_PUBLIC_CONFIG_DIR", str(DEFAULT_SAMPLE_CONFIG_DIR)))
MODELS_DIR = Path(os.getenv("TW_PROPHET_MODELS_DIR", str(PROJECT_ROOT / "models")))
LOG_DIR = Path(os.getenv("TW_PROPHET_LOG_DIR", str(PROJECT_ROOT / "logs")))

EXCLUDED_JSON = Path(os.getenv("TW_EXCLUDED_JSON", str(CONFIG_DIR / "sample_excluded_products.json")))
WEEKLY_JSON = Path(os.getenv("TW_WEEKLY_JSON", str(CONFIG_DIR / "sample_weekly_data_list.json")))
NOTIFY_SETTINGS_JSON = Path(os.getenv("TW_NOTIFY_SETTINGS_JSON", str(CONFIG_DIR / "notify_settings.json")))

SHIPMENTS_CSV = Path(os.getenv("TW_SAMPLE_SHIPMENTS_CSV", str(DATA_DIR / "shipments.csv")))
INVENTORY_CSV = Path(os.getenv("TW_SAMPLE_INVENTORY_CSV", str(DATA_DIR / "inventory.csv")))
PARTS_CSV = Path(os.getenv("TW_SAMPLE_PARTS_CSV", str(DATA_DIR / "parts.csv")))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_json_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def save_json_list(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = sorted({str(x).strip() for x in values if str(x).strip()})
    with path.open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)


def load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_json_dict(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

