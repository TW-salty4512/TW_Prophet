"""
access_handler.py  –  TW_Prophet データ取得層（内部版）

MDB パスおよび MySQL 接続情報は config.py 経由で解決する。
直書き禁止。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import pandas as pd
import pyodbc
from sqlalchemy import create_engine

# Access ODBC は接続数が少ないため、プールせず毎回確実にクローズする
pyodbc.pooling = False
from sqlalchemy.engine import Engine

import config


def _mdb_conn_str(path: str) -> str:
    return (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={path};"
    )


class AccessHandler:
    """Access MDB / MySQL からデータを取得する。

    MDB パスは config.SHIPMENT_MDB / POST_SHIPMENT_MDB / MANUFACTURE_MDB。
    MySQL 接続情報は config.MYSQL。
    いずれも環境変数または %ProgramData%\\TW_Prophet\\settings.json で上書き可能。
    """

    def __init__(self) -> None:
        self.shipment_db_path      = str(config.SHIPMENT_MDB)
        self.post_shipment_db_path = str(config.POST_SHIPMENT_MDB)
        self.manufacture_db_path   = str(config.MANUFACTURE_MDB)

        self.shipment_conn_str      = _mdb_conn_str(self.shipment_db_path)
        self.post_shipment_conn_str = _mdb_conn_str(self.post_shipment_db_path)
        self.manufacture_conn_str   = _mdb_conn_str(self.manufacture_db_path)

        self.mysql_conf             = config.MYSQL
        self.mysql_engine: Engine | None = self._build_mysql_engine(self.mysql_conf)
        self.mysql_stock_table      = self.mysql_conf.get("table_stock", "stock")

    # ------------------------------------------------------------------
    # MySQL エンジン生成
    # ------------------------------------------------------------------
    def _build_mysql_engine(self, conf: dict[str, Any]) -> Engine | None:
        if not conf.get("database"):
            return None
        try:
            url = (
                f"mysql+mysqlconnector://{conf['user']}:{conf['password']}"
                f"@{conf['host']}:{conf['port']}/{conf['database']}?charset=utf8mb4"
            )
            return create_engine(url, pool_pre_ping=True, pool_recycle=3600)
        except Exception as e:
            raise ValueError(f"MySQLエンジン生成に失敗しました: {e}") from e

    # ------------------------------------------------------------------
    # 出荷明細
    # ------------------------------------------------------------------
    def get_shipment_data(self) -> pd.DataFrame:
        """簡易受注管理.mdb の出荷明細テーブルから [出荷完了日, バーコード, 数量, 顧客ID] を取得。"""
        try:
            query = "SELECT 出荷完了日, バーコード, 数量, 顧客ID FROM 出荷明細テーブル"
            conn = pyodbc.connect(self.shipment_conn_str)
            try:
                data = pd.read_sql_query(query, conn)
            finally:
                conn.close()
            data["出荷完了日"] = pd.to_datetime(data["出荷完了日"], errors="coerce")
            data = data[data["数量"] > 0]
            return data
        except Exception as e:
            raise ValueError(f"出荷データの取得中にエラーが発生しました: {e}") from e

    # ------------------------------------------------------------------
    # 在庫
    # ------------------------------------------------------------------
    def get_inventory_data(self) -> pd.DataFrame:
        """出荷管理.mdb の在庫クエリからバーコード別在庫数を取得。"""
        try:
            shipment_data = self.get_shipment_data()
            barcodes_in_shipment = shipment_data["バーコード"].unique()

            query = """
                SELECT
                    出荷後在庫数確認クエリ.出荷型式 AS バーコード,
                    出荷後在庫数確認クエリ.在庫数
                FROM 出荷後在庫数確認クエリ
            """
            conn = pyodbc.connect(self.post_shipment_conn_str)
            try:
                df = pd.read_sql_query(query, conn)
            finally:
                conn.close()

            return df[df["バーコード"].isin(barcodes_in_shipment)].copy()
        except Exception as e:
            raise ValueError(f"在庫データの取得中にエラーが発生しました: {e}") from e

    # ------------------------------------------------------------------
    # 部品情報
    # ------------------------------------------------------------------
    def get_parts_info(self, product_barcode: str) -> pd.DataFrame:
        """製造管理.mdb またはMySQL から部品情報を取得。"""
        try:
            mysql_barcodes = set(self.mysql_conf.get("mysql_barcodes", []))
            if product_barcode in mysql_barcodes:
                return self._get_parts_info_mysql(product_barcode)
            return self._get_parts_info_standard(product_barcode)
        except Exception as e:
            raise ValueError(f"部品情報取得中にエラーが発生しました: {e}") from e

    def _get_parts_info_mysql(self, product_barcode: str) -> pd.DataFrame:
        """MySQL の stock テーブルから部品在庫を取得する汎用メソッド。

        対象 item_id は config.MYSQL["mysql_barcodes_item_ids"] に設定する。
        例: {"KB-IOPAD4": ["CMB-KBIOPAD4_C", "KB-IOPAD4-CASE"]}
        """
        if self.mysql_engine is None:
            raise ValueError(
                "MySQL 接続情報が不足しています。"
                "settings.json または環境変数 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE を設定してください。"
            )
        table = self.mysql_stock_table
        item_ids_map: dict[str, list[str]] = self.mysql_conf.get("mysql_barcodes_item_ids", {})
        target_items = tuple(item_ids_map.get(product_barcode, []))

        if not target_items:
            return pd.DataFrame(columns=["部品名", "在庫数"])

        placeholders = ", ".join(["%s"] * len(target_items))
        query = f"""
            SELECT `item_id` AS 部品名, `stock_quantity` AS 在庫数
            FROM `{table}`
            WHERE `item_id` IN ({placeholders})
        """
        try:
            df = pd.read_sql_query(query, self.mysql_engine, params=target_items)
        except Exception as e:
            raise ValueError(f"MySQL からの部品情報取得に失敗しました: {e}") from e

        if df.empty:
            return pd.DataFrame(columns=["部品名", "在庫数"])
        return df

    def _get_parts_info_standard(self, product_barcode: str) -> pd.DataFrame:
        """通常パターン: 製造管理.mdb から製造品ID → 部品一覧を取得。"""
        conn = pyodbc.connect(self.manufacture_conn_str)
        try:
            query_id = "SELECT 製造品ID FROM 製造品型名テーブル WHERE 販売商品名 = ?"
            df_id = pd.read_sql_query(query_id, conn, params=[product_barcode])
            if df_id.empty:
                return pd.DataFrame(columns=["部品名", "在庫数"])

            manufacture_id = int(df_id.iloc[0]["製造品ID"])
            query_parts = """
                SELECT 製造品構成クエリ.製品名, 製造品構成クエリ.在庫数
                FROM 製造品構成クエリ
                WHERE 製造品ID = ?
            """
            df_parts = pd.read_sql_query(query_parts, conn, params=[manufacture_id])
        finally:
            conn.close()

        if df_parts.empty:
            return pd.DataFrame(columns=["部品名", "在庫数"])
        return df_parts.rename(columns={"製品名": "部品名"})
