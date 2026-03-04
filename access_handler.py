"""
#################################################
2025/02
-TW_Prophet-
access_handler.py
#################################################
"""
import os
import json
import pyodbc
import pymysql
import pandas as pd
from typing import Optional, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

class AccessHandler:
    def __init__(
        self,
        mysql_config: Optional[Dict[str,Any]] = None,
    ):

        # ===== MDB 接続設定 =====

        # 簡易受注管理.mdb （出荷明細テーブルはこちら）
        self.shipment_db_path = r"\\File-server\データベース\簡易受注管理.mdb"
        self.shipment_conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            rf"DBQ={self.shipment_db_path};"
        )

        # 出荷管理.mdb
        self.post_shipment_db_path = r"\\File-server\データベース\出荷管理.mdb"
        self.post_shipment_conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            rf"DBQ={self.post_shipment_db_path};"
        )

        # 製品管理.mdb
        self.manufacture_db_path = r"\\File-server\データベース\製造管理.mdb"
        self.manufacture_conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            rf"DBQ={self.manufacture_db_path};"
        )

        self.mysql_conf = self._load_mysql_conf()
        self.mysql_engine: Engine | None = self._build_mysql_engine(self.mysql_conf)

        # MySQL 側ストックテーブル名（既定: "stock"）
        self.mysql_stock_table = self.mysql_conf.get("table_stock", "stock")
        
    def _load_mysql_conf(self) -> dict:
        conf = {}
        conf_path = os.path.join(os.getcwd(), "mysql_config.json")
        if os.path.exists(conf_path):
            try:
                with open(conf_path, "r", encoding="utf-8") as f:
                    conf = json.load(f)
            except Exception as e:
                raise ValueError(f"MySQL設定ファイル(mysql_config.json)読込に失敗しました: {e}")

        # 環境変数で上書き可能
        conf.setdefault("host", os.environ.get("MYSQL_HOST", "127.0.0.1"))
        conf.setdefault("port", int(os.environ.get("MYSQL_PORT", "3306")))
        conf.setdefault("user", os.environ.get("MYSQL_USER", "root"))
        conf.setdefault("password", os.environ.get("MYSQL_PASSWORD", ""))
        conf.setdefault("database", os.environ.get("MYSQL_DATABASE", ""))
        conf.setdefault("table_stock", os.environ.get("MYSQL_TABLE_STOCK", conf.get("table_stock", "stock")))
        return conf
    
    def _build_mysql_engine(self, conf: dict) -> Engine | None:
        try:
            if not conf.get("database"):
                # データベース名未設定の場合は None を返し、後段で検知
                return None
            # mysql-connector-python を使用
            url = (
                f"mysql+mysqlconnector://{conf['user']}:{conf['password']}"
                f"@{conf['host']}:{conf['port']}/{conf['database']}?charset=utf8mb4"
            )
            return create_engine(url, pool_pre_ping=True, pool_recycle=3600)
        except Exception as e:
            raise ValueError(f"MySQLエンジン生成に失敗しました: {e}")

    def get_shipment_data(self):
        """
        簡易受注管理.mdb の 出荷明細テーブル から
        [出荷完了日, バーコード, 数量] を取得
        """
        try:
            query = "SELECT 出荷完了日, バーコード, 数量, 顧客ID FROM 出荷明細テーブル"
            conn = pyodbc.connect(self.shipment_conn_str)
            data = pd.read_sql_query(query, conn)
            conn.close()

            # 日付型へ変換
            data['出荷完了日'] = pd.to_datetime(data['出荷完了日'], errors='coerce')
            data = data[data['数量'] > 0]
            return data
        except Exception as e:
            raise ValueError(f"出荷データの取得中にエラーが発生しました: {e}")

    def get_inventory_data(self):
        """
        出荷管理.mdb の「出荷後在庫数確認クエリ」より
          - 出荷型式 を バーコード として
          - 在庫数 を 在庫数 として
        取得し、 簡易受注管理.mdb で使用中のバーコードだけ抽出。
        """
        try:
            # まず 簡易受注管理.mdb からバーコード一覧を取得
            shipment_data = self.get_shipment_data()
            barcodes_in_shipment = shipment_data['バーコード'].unique()

            # 出荷管理.mdb の「出荷後在庫数確認クエリ」から在庫データ取得
            query = """
                SELECT
                    出荷後在庫数確認クエリ.出荷型式 AS バーコード,
                    出荷後在庫数確認クエリ.在庫数
                FROM 出荷後在庫数確認クエリ
            """
            conn = pyodbc.connect(self.post_shipment_conn_str)
            df = pd.read_sql_query(query, conn)
            conn.close()

            # shipment_data のバーコードと一致するものだけを抽出
            df_filtered = df[df["バーコード"].isin(barcodes_in_shipment)].copy()

            # 必要に応じて 0以下の在庫を除外したい場合は下記をコメントアウト解除
            # df_filtered = df_filtered[df_filtered["在庫数"] > 0]

            return df_filtered

        except Exception as e:
            raise ValueError(f"在庫データの取得中にエラーが発生しました: {e}")
        
    def get_parts_info(self, product_barcode):
        """
        製造管理.mdb から以下の流れで部品情報を取得:
          1) '製造品型名テーブル' の '販売商品名' = product_barcode の行を探し、
             '製造品ID' を取り出す
          2) '製造品構成クエリ' の中から上記 '製造品ID' と一致する行を抽出し、
             '製品名' と '在庫数' を取得
        戻り値: pd.DataFrame(columns=['部品名','在庫数']) という形にする

        KB-IOPAD4: 特別扱い。stock テーブルから item_id in ("CMB-KBIOPAD4_C","KB-IOPAD4-CASE") の在庫を拾う。
        戻り値: pd.DataFrame(columns=["部品名","在庫数"])
        """
        try:
            # 特別対応
            if product_barcode == "KB-IOPAD4":
                return self._get_parts_info_for_kb_iopad4_mysql()
            else:
                return self._get_parts_info_standard(product_barcode)
        except Exception as e:
            raise ValueError(f"製造管理.mdb の部品情報取得中にエラーが発生しました: {e}")

    def _get_parts_info_for_kb_iopad4_mysql(self):
        """
        KB-IOPAD4製品だけは **MySQL の stock テーブル**から以下を取得:
          item_id in ('CMB-KBIOPAD4_C','KB-IOPAD4-CASE')
          → item_id AS 部品名, stock_quantity AS 在庫数
        """
        if self.mysql_engine is None:
            raise ValueError(
                "MySQL 接続情報が不足しています。mysql_config.json を用意するか、"
                "環境変数 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE を設定してください。"
            )
        # テーブル名は設定ファイルの "table_stock"（既定: stock）
        table = self.mysql_stock_table

        # 安全のため、絞り込み ID をリストで管理
        target_items = ("CMB-KBIOPAD4_C", "KB-IOPAD4-CASE")

        # SQL（ANSI準拠。識別子はバッククォートで保護）
        query = f"""
            SELECT
                `item_id`   AS 部品名,
                `stock_quantity` AS 在庫数
            FROM `{table}`
            WHERE `item_id` IN (%s, %s)
        """
        try:
            df = pd.read_sql_query(query, self.mysql_engine, params=target_items)
        except Exception as e:
            raise ValueError(f"MySQL からの部品情報取得に失敗しました: {e}")

        if df.empty:
            # 空でも columns を保証
            return pd.DataFrame(columns=["部品名","在庫数"])
        return df

    def _get_parts_info_standard(self, product_barcode):
        """
        通常パターン:
          1) 製造品型名テーブル: 販売商品名 = product_barcode で検索 → 製造品ID
          2) 製造品構成クエリ   : 上記 製造品ID = ? → (製品名, 在庫数)
        """
        conn = pyodbc.connect(self.manufacture_conn_str)
        # 1) 製造品型名テーブル から 製造品ID を取得
        query_id = """
            SELECT 製造品ID
            FROM 製造品型名テーブル
            WHERE 販売商品名 = ?
        """
        df_id = pd.read_sql_query(query_id, conn, params=[product_barcode])
        if df_id.empty:
            conn.close()
            return pd.DataFrame(columns=['部品名','在庫数'])

        # numpy.int64 → Python int へキャストしてエラー回避
        manufacture_id = int(df_id.iloc[0]['製造品ID'])

        # 2) 製造品構成クエリ で部品取得
        query_parts = """
            SELECT 製造品構成クエリ.製品名, 製造品構成クエリ.在庫数
            FROM 製造品構成クエリ
            WHERE 製造品ID = ?
        """
        df_parts = pd.read_sql_query(query_parts, conn, params=[manufacture_id])
        conn.close()

        if df_parts.empty:
            return pd.DataFrame(columns=['部品名','在庫数'])

        df_parts = df_parts.rename(columns={
            '製品名': '部品名',
            '在庫数': '在庫数'
        })
        return df_parts
    
    def _validate_mysql_config(self) -> Dict[str, Any]:
        """
        MySQL 接続に必要なキーが揃っているか軽くチェックし、接続 dict を返す。
        """
        cfg = dict(self.mysql_config) if self.mysql_config else {}
        required = ["host", "user", "password", "database"]
        missing = [k for k in required if not cfg.get(k)]
        if missing:
            # host/user/password/database のいずれかが欠けている
            raise ValueError(
                "MySQL の接続設定が不足しています。環境変数または引数で設定してください。"
                f" 不足キー: {', '.join(missing)}  "
                "例) 環境変数 MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB"
            )

        # 既定値補完
        if not cfg.get("port"):
            cfg["port"] = 3306
        if not cfg.get("charset"):
            cfg["charset"] = "utf8mb4"
        if "cursorclass" not in cfg:
            cfg["cursorclass"] = pymysql.cursors.DictCursor
        return cfg