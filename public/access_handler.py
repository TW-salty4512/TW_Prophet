from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from public import config


class DataSourceError(ValueError):
    pass


@dataclass
class SampleDataHandler:
    shipments_csv: Path
    inventory_csv: Path
    parts_csv: Path

    def read_shipments(self) -> pd.DataFrame:
        if not self.shipments_csv.exists():
            raise DataSourceError(f"shipments CSV not found: {self.shipments_csv}")
        df = pd.read_csv(self.shipments_csv)
        required = {"shipment_date", "barcode", "quantity"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise DataSourceError(f"shipments CSV missing columns: {', '.join(missing)}")
        df = df.copy()
        df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="coerce")
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0).clip(lower=0.0)
        if "customer_id" not in df.columns:
            df["customer_id"] = ""
        return df.dropna(subset=["shipment_date"]).reset_index(drop=True)

    def read_inventory(self) -> pd.DataFrame:
        if not self.inventory_csv.exists():
            raise DataSourceError(f"inventory CSV not found: {self.inventory_csv}")
        df = pd.read_csv(self.inventory_csv)
        required = {"barcode", "inventory"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise DataSourceError(f"inventory CSV missing columns: {', '.join(missing)}")
        df = df.copy()
        df["inventory"] = pd.to_numeric(df["inventory"], errors="coerce").fillna(0.0).clip(lower=0.0)
        return df.reset_index(drop=True)

    def read_parts(self, product_barcode: str) -> pd.DataFrame:
        if not self.parts_csv.exists():
            raise DataSourceError(f"parts CSV not found: {self.parts_csv}")
        df = pd.read_csv(self.parts_csv)
        required = {"barcode", "part_name", "stock"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise DataSourceError(f"parts CSV missing columns: {', '.join(missing)}")
        df = df[df["barcode"].astype(str) == str(product_barcode)].copy()
        if df.empty:
            return pd.DataFrame(columns=["part_name", "stock"])
        df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0.0).clip(lower=0.0)
        return df[["part_name", "stock"]].reset_index(drop=True)


class AccessHandler:
    def __init__(
        self,
        data_dir: Optional[str | Path] = None,
        shipments_csv: Optional[str | Path] = None,
        inventory_csv: Optional[str | Path] = None,
        parts_csv: Optional[str | Path] = None,
    ):
        config.ensure_dirs()
        base_dir = Path(data_dir) if data_dir else config.DATA_DIR
        base_dir.mkdir(parents=True, exist_ok=True)

        # 公開版ではAccess/MySQL直結を廃止し、サンプルCSVをデータソースに固定。
        self.sample_handler = SampleDataHandler(
            shipments_csv=Path(shipments_csv) if shipments_csv else config.SHIPMENTS_CSV,
            inventory_csv=Path(inventory_csv) if inventory_csv else config.INVENTORY_CSV,
            parts_csv=Path(parts_csv) if parts_csv else config.PARTS_CSV,
        )

    def get_shipment_data(self) -> pd.DataFrame:
        return self.sample_handler.read_shipments()

    def get_inventory_data(self) -> pd.DataFrame:
        return self.sample_handler.read_inventory()

    def get_parts_info(self, product_barcode: str) -> pd.DataFrame:
        return self.sample_handler.read_parts(product_barcode)

