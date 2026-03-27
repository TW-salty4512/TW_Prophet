"""
tests/test_config.py  –  config.py の単体テスト

依存:
    pip install pytest
実行:
    cd project
    pytest tests/test_config.py -v
"""
import json
import os
import sys
from pathlib import Path
import tempfile

import pytest

# project/ をパスに追加（テスト実行を project/ 以外から行う場合）
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# config モジュールのリロードヘルパー
# ---------------------------------------------------------------------------

def _reload_config(env_overrides: dict | None = None, settings: dict | None = None):
    """環境変数 + 一時 settings.json でconfig をリロードして返す。"""
    import importlib

    env_backup = {}
    try:
        if env_overrides:
            for k, v in env_overrides.items():
                env_backup[k] = os.environ.get(k)
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = str(v)

        if "config" in sys.modules:
            del sys.modules["config"]

        if settings is not None:
            # 一時 settings.json を project/ 直下に作成
            cfg_path = Path(__file__).parent.parent / "settings.json"
            cfg_path.write_text(json.dumps(settings), encoding="utf-8")
            try:
                import config as c
                return c
            finally:
                cfg_path.unlink(missing_ok=True)
                if "config" in sys.modules:
                    del sys.modules["config"]
        else:
            import config as c
            return c
    finally:
        # 環境変数を元に戻す
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------

class TestDefaultValues:
    def test_default_port(self):
        c = _reload_config(env_overrides={"PORT": None})
        assert c.PORT == 8000

    def test_env_port_override(self):
        c = _reload_config(env_overrides={"PORT": "9999"})
        assert c.PORT == 9999

    def test_default_data_mode_internal(self):
        c = _reload_config(env_overrides={"TW_DATA_MODE": None})
        assert c.DATA_MODE == "internal"

    def test_data_mode_sample(self):
        c = _reload_config(env_overrides={"TW_DATA_MODE": "sample"})
        assert c.is_sample_mode() is True

    def test_data_mode_internal_not_sample(self):
        c = _reload_config(env_overrides={"TW_DATA_MODE": "internal"})
        assert c.is_sample_mode() is False


class TestSettingsJson:
    def test_settings_json_port(self):
        c = _reload_config(settings={"port": 7777})
        # 環境変数で上書きされていなければ settings.json の値が使われる
        # 環境変数 PORT が設定されていない前提
        saved_port = os.environ.get("PORT")
        if saved_port is None:
            assert c.PORT == 7777

    def test_settings_json_data_mode(self):
        saved = os.environ.get("TW_DATA_MODE")
        if saved is None:
            c = _reload_config(settings={"data_mode": "sample"})
            assert c.DATA_MODE == "sample"

    def test_settings_json_mdb_base(self):
        saved = os.environ.get("TW_MDB_BASE_DIR")
        if saved is None:
            c = _reload_config(settings={"mdb_base_dir": r"C:\TestDB"})
            assert "TestDB" in str(c.SHIPMENT_MDB)


class TestMdbPaths:
    def test_mdb_base_dir_used_for_defaults(self):
        c = _reload_config(
            env_overrides={
                "TW_MDB_BASE_DIR": r"\\srv\db",
                "TW_SHIPMENT_MDB": None,
                "TW_POST_SHIPMENT_MDB": None,
                "TW_MANUFACTURE_MDB": None,
            }
        )
        assert "srv" in str(c.SHIPMENT_MDB) or "db" in str(c.SHIPMENT_MDB)

    def test_individual_mdb_override(self):
        c = _reload_config(env_overrides={"TW_SHIPMENT_MDB": r"C:\custom\ship.mdb"})
        assert str(c.SHIPMENT_MDB) == r"C:\custom\ship.mdb"


class TestMysqlConf:
    def test_mysql_defaults_when_no_config(self):
        c = _reload_config(
            env_overrides={
                "MYSQL_HOST": None, "MYSQL_USER": None,
                "MYSQL_PASSWORD": None, "MYSQL_DATABASE": None,
            }
        )
        assert c.MYSQL["host"] == "127.0.0.1"
        assert c.MYSQL["port"] == 3306

    def test_mysql_env_override(self):
        c = _reload_config(env_overrides={"MYSQL_HOST": "10.0.0.5", "MYSQL_DATABASE": "mydb"})
        assert c.MYSQL["host"] == "10.0.0.5"
        assert c.MYSQL["database"] == "mydb"


class TestSummary:
    def test_summary_has_required_keys(self):
        import config as c
        s = c.summary()
        for key in ["data_mode", "port", "data_dir", "models_dir", "mysql_host"]:
            assert key in s

    def test_summary_no_password(self):
        import config as c
        s = c.summary()
        # パスワードが summary に含まれないことを確認
        assert "password" not in s
        assert "mysql_password" not in s
