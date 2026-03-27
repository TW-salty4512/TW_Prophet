"""
config.py  –  TW_Prophet 内部版 集中設定

優先順位:
  1. 環境変数 (本番・CI 向け)
  2. %ProgramData%\\TW_Prophet\\settings.json  (インストーラが書込む)
  3. スクリプト同階層の settings.json            (開発用ローカル上書き)
  4. ここに定義したデフォルト値

すべての絶対パス・UNCパス・IPアドレス・資格情報は
このファイルまたは settings.json 経由で解決し、
他のモジュールへのハードコードは禁止とする。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# ディレクトリ解決ヘルパー
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent

def _program_data_settings() -> Path:
    """%ProgramData%\\TW_Prophet\\settings.json"""
    return Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "TW_Prophet" / "settings.json"


def _load_settings() -> dict[str, Any]:
    """settings.json を優先順位に従って読み込む。"""
    candidates = [
        _HERE / "settings.json",           # 開発者ローカル上書き (git 追跡外)
        _program_data_settings(),           # インストーラが書込む本番設定
    ]
    for p in candidates:
        if p.exists():
            try:
                with p.open(encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


_SETTINGS: dict[str, Any] = _load_settings()


def _get(key: str, env_var: str, default: Any = None) -> Any:
    """環境変数 → settings.json → デフォルト の順で解決する。"""
    env_val = os.environ.get(env_var)
    if env_val is not None:
        return env_val
    return _SETTINGS.get(key, default)


# ---------------------------------------------------------------------------
# Web サーバー
# ---------------------------------------------------------------------------
PORT: int = int(_get("port", "PORT", 8000))

# ---------------------------------------------------------------------------
# データ / 設定ファイルの保存先
# ---------------------------------------------------------------------------
#   - ProgramData 以下をデフォルトにすることで、任意ユーザーで共有できる
_DEFAULT_DATA_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "TW_Prophet" / "data"

DATA_DIR   = Path(_get("data_dir",   "TW_PROPHET_DATA_DIR",   str(_DEFAULT_DATA_DIR)))
MODELS_DIR = Path(_get("models_dir", "TW_PROPHET_MODELS_DIR", str(DATA_DIR / "models")))
LOG_DIR    = Path(_get("log_dir",    "TW_PROPHET_LOG_DIR",    str(DATA_DIR / "logs")))
CONFIG_DIR = Path(_get("config_dir", "TW_PROPHET_CONFIG_DIR", str(DATA_DIR / "config")))

# ---------------------------------------------------------------------------
# ランタイム JSON（実体は DATA_DIR / CONFIG_DIR 以下）
# ---------------------------------------------------------------------------
EXCLUDED_JSON       = Path(_get("excluded_json",      "TW_EXCLUDED_JSON",
                                str(CONFIG_DIR / "excluded_products.json")))
WEEKLY_JSON         = Path(_get("weekly_json",         "TW_WEEKLY_JSON",
                                str(CONFIG_DIR / "weekly_data_list.json")))
EMAIL_JSON          = Path(_get("email_json",          "TW_EMAIL_JSON",
                                str(CONFIG_DIR / "email_list.json")))
NOTIFY_SETTINGS_JSON = Path(_get("notify_settings_json", "TW_NOTIFY_SETTINGS_JSON",
                                  str(CONFIG_DIR / "notify_settings.json")))
NOTIFY_STATE_JSON   = Path(_get("notify_state_json",  "TW_NOTIFY_STATE_JSON",
                                str(DATA_DIR / "notify_state.json")))

# ---------------------------------------------------------------------------
# MDB パス（社内ファイルサーバーまたはローカル）
# ---------------------------------------------------------------------------
_DEFAULT_MDB_BASE = _get("mdb_base_dir", "TW_MDB_BASE_DIR", r"\\File-server\データベース")

SHIPMENT_MDB      = Path(_get("shipment_mdb",     "TW_SHIPMENT_MDB",
                               str(Path(_DEFAULT_MDB_BASE) / "簡易受注管理.mdb")))
POST_SHIPMENT_MDB = Path(_get("post_shipment_mdb", "TW_POST_SHIPMENT_MDB",
                               str(Path(_DEFAULT_MDB_BASE) / "出荷管理.mdb")))
MANUFACTURE_MDB   = Path(_get("manufacture_mdb",  "TW_MANUFACTURE_MDB",
                               str(Path(_DEFAULT_MDB_BASE) / "製造管理.mdb")))

# ---------------------------------------------------------------------------
# MySQL 接続（社内製造管理 DB 連携。不要なら空欄のまま可）
# ---------------------------------------------------------------------------
def _load_mysql_conf() -> dict[str, Any]:
    """mysql_config.json (CONFIG_DIR) → 環境変数 → デフォルト の順で解決。"""
    conf: dict[str, Any] = {}

    # CONFIG_DIR の mysql_config.json を試みる
    json_path = CONFIG_DIR / "mysql_config.json"
    if json_path.exists():
        try:
            with json_path.open(encoding="utf-8") as f:
                conf = json.load(f)
        except Exception:
            pass

    # 環境変数で上書き
    conf["host"]        = os.environ.get("MYSQL_HOST",        conf.get("host",        "127.0.0.1"))
    conf["port"]        = int(os.environ.get("MYSQL_PORT",    str(conf.get("port",    3306))))
    conf["user"]        = os.environ.get("MYSQL_USER",        conf.get("user",        ""))
    conf["password"]    = os.environ.get("MYSQL_PASSWORD",    conf.get("password",    ""))
    conf["database"]    = os.environ.get("MYSQL_DATABASE",    conf.get("database",    ""))
    conf["table_stock"] = os.environ.get("MYSQL_TABLE_STOCK", conf.get("table_stock", "stock"))
    return conf


MYSQL: dict[str, Any] = _load_mysql_conf()

# ---------------------------------------------------------------------------
# Web 学習許可 / 通知設定
# ---------------------------------------------------------------------------
ALLOW_WEB_TRAIN     : bool = _get("allow_web_train",    "TW_PROPHET_ALLOW_WEB_TRAIN",    "0") == "1"
NOTIFY_AUTO         : bool = _get("notify_auto",        "TW_PROPHET_NOTIFY_AUTO",        "1") == "1"
NOTIFY_INTERVAL_MIN : int  = int(_get("notify_interval_min", "TW_PROPHET_NOTIFY_INTERVAL_MIN", "360"))

# ---------------------------------------------------------------------------
# モード切替：内部(mdb/mysql) or サンプル(csv)
# ---------------------------------------------------------------------------
# TW_DATA_MODE=sample  でサンプルCSVを使うモードになる
DATA_MODE: str = _get("data_mode", "TW_DATA_MODE", "internal").lower()

# サンプルCSV パス（sample モード専用）
SAMPLE_DATA_DIR    = Path(_get("sample_data_dir", "TW_SAMPLE_DATA_DIR",
                               str(_HERE / "examples" / "sample_data")))
SAMPLE_CONFIG_DIR  = Path(_get("sample_config_dir", "TW_SAMPLE_CONFIG_DIR",
                               str(_HERE / "examples" / "sample_config")))
SHIPMENTS_CSV      = Path(_get("shipments_csv",  "TW_SAMPLE_SHIPMENTS_CSV",
                               str(SAMPLE_DATA_DIR / "shipments.csv")))
INVENTORY_CSV      = Path(_get("inventory_csv",  "TW_SAMPLE_INVENTORY_CSV",
                               str(SAMPLE_DATA_DIR / "inventory.csv")))
PARTS_CSV          = Path(_get("parts_csv",      "TW_SAMPLE_PARTS_CSV",
                               str(SAMPLE_DATA_DIR / "parts.csv")))

# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    """必要なディレクトリを作成する（起動時に呼ぶ）。"""
    for d in [DATA_DIR, MODELS_DIR, LOG_DIR, CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def is_sample_mode() -> bool:
    return DATA_MODE == "sample"


# ---------------------------------------------------------------------------
# Web UI ナビリンク（社内ページへのリンクを設定から差し込む）
# 例: [{"label": "製造管理", "url": "http://intranet/mfg/"}, ...]
# ---------------------------------------------------------------------------
def _load_nav_links() -> list[dict[str, str]]:
    val = _SETTINGS.get("nav_links")
    if isinstance(val, list):
        return val
    return []

NAV_LINKS: list[dict[str, str]] = _load_nav_links()


def summary() -> dict[str, Any]:
    """設定内容の概要（デバッグ・ログ用。機密値は除外）。"""
    return {
        "data_mode":   DATA_MODE,
        "port":        PORT,
        "data_dir":    str(DATA_DIR),
        "models_dir":  str(MODELS_DIR),
        "log_dir":     str(LOG_DIR),
        "config_dir":  str(CONFIG_DIR),
        "shipment_mdb": str(SHIPMENT_MDB),
        "mysql_host":  MYSQL.get("host"),
        "mysql_db":    MYSQL.get("database"),
        "allow_web_train":  ALLOW_WEB_TRAIN,
        "notify_auto":      NOTIFY_AUTO,
    }
