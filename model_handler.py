"""
model_handler.py  –  TW_Prophet 予測エンジン（ModelHandler）

依存サブモジュール（model/ パッケージ）:
  model/calendar.py   – 祝日・営業日カレンダー
  model/metrics.py    – smape / calc_metrics
  model/transforms.py – log1p変換・外れ値クリップ・safe_array
  model/features.py   – 特徴量エンジニアリング
  model/trainer.py    – XGBoost 学習・ハイパーパラメータ探索
  model/evaluator.py  – WalkForwardResult
  model/store.py      – モデル保存/読み込み

このファイルは後方互換を維持するファサードです。
メソッド内部は上記モジュールの関数に段階的に委譲しています。
"""
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.base import clone
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBRegressor

import matplotlib as mpl

# ---- model/ サブモジュールをインポート ----
from model.metrics import smape as _smape_impl, calc_metrics as _calc_metrics_impl
from model.transforms import (
    clip_upper_outliers as _clip_upper_outliers_impl,
    should_use_log_transform as _should_use_log_transform_impl,
    transform_target as _transform_target_impl,
    inverse_target as _inverse_target_impl,
    safe_array as _safe_array_impl,
)
from model.calendar import (
    is_holiday as _is_holiday_impl,
    holiday_count_for_week as _holiday_week_impl,
    holiday_count_for_month as _holiday_month_impl,
)
from model.trainer import (
    default_xgb as _default_xgb_impl,
    fit_estimator as _fit_estimator_impl,
    search_best_xgb as _search_best_xgb_impl,
)
from model.store import save_model as _save_model_impl, load_model as _load_model_impl

mpl.rc("font", family="MS Gothic")
warnings.filterwarnings("ignore")


# モジュールレベルで後方互換エイリアスとして公開
def smape(y_true, y_pred):
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true_arr) + np.abs(y_pred_arr)
    mask = denom != 0
    if not np.any(mask):
        return 0.0
    return float(100.0 * np.mean(2.0 * np.abs(y_pred_arr[mask] - y_true_arr[mask]) / denom[mask]))


class ModelHandler:
    def __init__(self):
        self.model_dir = "./models"
        os.makedirs(self.model_dir, exist_ok=True)

        self.WEEKLY_FREQ = "W-SUN"
        self.MONTHLY_FREQ = "M"

        self.WEEKLY_LAGS = [1, 2, 3, 4, 6, 8, 12, 26, 52]
        self.WEEKLY_ROLLING = [(4, "mean"), (4, "std"), (8, "mean"), (8, "std")]
        self.WEEKLY_BASE_COLS = [
            "week",
            "year",
            "week_sin",
            "week_cos",
            "holiday_days",
            "work_days",
            "is_may",
            "is_june",
            "is_nov",
            "is_dec",
        ]

        self.MONTHLY_LAGS = [1, 2, 3, 6, 12]
        self.MONTHLY_ROLLING = [(3, "mean"), (3, "std")]
        self.MONTHLY_BASE_COLS = [
            "year",
            "month",
            "month_sin",
            "month_cos",
            "holiday_days",
            "work_days",
            "is_may",
            "is_june",
            "is_nov",
            "is_dec",
        ]
        self.MONTHLY_LEGACY_FEATURE_COLS = [  # 旧学習済みモデル互換用（年/月/sin/cos + lag + rolling）
            "year",
            "month",
            "month_sin",
            "month_cos",
            "is_may",
            "is_june",
            "is_nov",
            "is_dec",
            "lag_1",
            "lag_2",
            "lag_3",
            "lag_6",
            "lag_12",
            "rolling_mean_3",
            "rolling_std_3",
        ]

        self.CUSTOMER_FEATURE_COLS = [
            "cust_unique",
            "cust_top_share",
            "cust_unique_roll",
            "cust_top_share_roll",
        ]
        self.enable_customer_features = os.getenv("TW_PROPHET_ENABLE_CUSTOMER_FEATURES", "0").strip() == "1"

        self.OUTLIER_IQR_MULTIPLIER = 1.5

        self._shipment_fallback = {
            "date": "蜃ｺ闕ｷ螳御ｺ・律",
            "barcode": "繝舌・繧ｳ繝ｼ繝・",
            "qty": "謨ｰ驥・",
        }
        self._inventory_fallback = {
            "barcode": "繝舌・繧ｳ繝ｼ繝・",
            "stock": "蝨ｨ蠎ｫ謨ｰ",
        }
        self._parts_fallback = {
            "name": "驛ｨ蜩∝錐",
            "stock": "蝨ｨ蠎ｫ謨ｰ",
        }

    # ======================================================
    # Utility
    # ======================================================
    def _pick_column(
        self,
        columns: List[Any],
        keywords: List[str],
        fallback_index: Optional[int] = None,
        fallback_name: Optional[str] = None,
    ) -> Optional[Any]:
        col_list = list(columns)
        lower_map = [str(c).lower() for c in col_list]
        for kw in keywords:
            kw_lower = kw.lower()
            for idx, c in enumerate(lower_map):
                if kw_lower in c:
                    return col_list[idx]
        if fallback_name is not None and fallback_name in col_list:
            return fallback_name
        if fallback_index is not None and 0 <= fallback_index < len(col_list):
            return col_list[fallback_index]
        return None

    def _resolve_shipment_columns(self, shipment_data: pd.DataFrame) -> Tuple[Any, Any, Any, Optional[Any]]:
        cols = list(shipment_data.columns)
        if not cols:
            raise ValueError("shipment_data has no columns.")

        date_col = self._pick_column(
            cols,
            keywords=["date", "ds", "日付", "出荷日"],
            fallback_index=0,
            fallback_name=self._shipment_fallback["date"],
        )
        barcode_col = self._pick_column(
            cols,
            keywords=["barcode", "バーコード", "code"],
            fallback_index=1,
            fallback_name=self._shipment_fallback["barcode"],
        )
        qty_col = self._pick_column(
            cols,
            keywords=["quantity", "qty", "数量", "出荷数"],
            fallback_index=2,
            fallback_name=self._shipment_fallback["qty"],
        )
        customer_col = self._pick_column(
            cols,
            keywords=["customer", "顧客", "client"],
            fallback_index=3,
            fallback_name=None,
        )
        if customer_col in (date_col, barcode_col, qty_col):
            customer_col = None
        return date_col, barcode_col, qty_col, customer_col

    def _resolve_inventory_columns(self, inventory_data: pd.DataFrame) -> Tuple[Any, Any]:
        cols = list(inventory_data.columns)
        if not cols:
            raise ValueError("inventory_data has no columns.")
        barcode_col = self._pick_column(
            cols,
            keywords=["barcode", "バーコード", "code"],
            fallback_index=0,
            fallback_name=self._inventory_fallback["barcode"],
        )
        stock_col = self._pick_column(
            cols,
            keywords=["stock", "inventory", "在庫"],
            fallback_index=1,
            fallback_name=self._inventory_fallback["stock"],
        )
        return barcode_col, stock_col

    def _resolve_parts_columns(self, parts_data: pd.DataFrame) -> Tuple[Any, Any]:
        cols = list(parts_data.columns)
        if not cols:
            raise ValueError("parts_data has no columns.")
        part_name_col = self._pick_column(
            cols,
            keywords=["part", "name", "部品"],
            fallback_index=0,
            fallback_name=self._parts_fallback["name"],
        )
        part_stock_col = self._pick_column(
            cols,
            keywords=["stock", "inventory", "在庫"],
            fallback_index=1,
            fallback_name=self._parts_fallback["stock"],
        )
        return part_name_col, part_stock_col

    def _to_float(self, value: Any, default: float = 0.0) -> float:
        try:
            x = float(value)
        except Exception:
            return default
        if not np.isfinite(x):
            return default
        return x

    def _weekly_feature_cols(self, use_customer: bool = False) -> List[str]:
        cols = (
            list(self.WEEKLY_BASE_COLS)
            + [f"lag_{l}" for l in self.WEEKLY_LAGS]
            + [f"rolling_{stat}_{w}" for (w, stat) in self.WEEKLY_ROLLING]
        )
        if use_customer:
            cols += list(self.CUSTOMER_FEATURE_COLS)
        return cols

    def _monthly_feature_cols(self, use_customer: bool = False) -> List[str]:
        cols = (
            list(self.MONTHLY_BASE_COLS)
            + [f"lag_{l}" for l in self.MONTHLY_LAGS]
            + [f"rolling_{stat}_{w}" for (w, stat) in self.MONTHLY_ROLLING]
        )
        if use_customer:
            cols += list(self.CUSTOMER_FEATURE_COLS)
        return cols

    def _choose_default_feature_cols(self, mode: str, model: Optional[Any]) -> List[str]:
        # 既存モデル(feature数)互換: 月次旧15特徴量モデルも扱えるように候補を切替
        if mode == "weekly":
            candidates = [
                self._weekly_feature_cols(use_customer=False),
                self._weekly_feature_cols(use_customer=True),
            ]
        else:
            candidates = [
                self._monthly_feature_cols(use_customer=False),
                list(self.MONTHLY_LEGACY_FEATURE_COLS),
                self._monthly_feature_cols(use_customer=True),
            ]

        n_features = getattr(model, "n_features_in_", None)
        if n_features is not None:
            for cand in candidates:
                if len(cand) == int(n_features):
                    return list(cand)
        return list(candidates[0])

    def _safe_array(self, X: Any) -> np.ndarray:
        return _safe_array_impl(X)

    def _clip_upper_outliers(self, y: pd.Series) -> pd.Series:
        return _clip_upper_outliers_impl(y, iqr_multiplier=self.OUTLIER_IQR_MULTIPLIER)

    def _should_use_log_transform(self, y_raw: np.ndarray) -> bool:
        return _should_use_log_transform_impl(y_raw)

    def _transform_target(self, y_raw: np.ndarray, use_log1p: bool) -> np.ndarray:
        return _transform_target_impl(y_raw, use_log1p)

    def _inverse_target(self, y_model: np.ndarray, use_log1p: bool) -> np.ndarray:
        return _inverse_target_impl(y_model, use_log1p)

    def _safe_predict(self, model: Any, X: Any, use_log1p: bool = False) -> np.ndarray:
        X_safe = self._safe_array(X)
        y_model = np.asarray(model.predict(X_safe), dtype=float).reshape(-1)
        return self._inverse_target(y_model, use_log1p=use_log1p)

    def _calc_metrics(self, y_true: Any, y_pred: Any) -> Dict[str, float]:
        return _calc_metrics_impl(y_true, y_pred)

    def _model_path(self, barcode: str, model_type: str) -> str:
        return os.path.join(self.model_dir, f"{model_type}_{barcode}.pkl")

    def _unwrap_model_payload(self, loaded: Any, mode: str) -> Tuple[Optional[Any], Dict[str, Any]]:
        if loaded is None:
            return None, {}
        if isinstance(loaded, dict) and "model" in loaded:
            model = loaded.get("model")
            meta = loaded.get("meta", {})
            if not isinstance(meta, dict):
                meta = {}
        else:
            model = loaded
            meta = {}

        if model is None:
            return None, {}

        if "feature_cols" not in meta:
            meta["feature_cols"] = self._choose_default_feature_cols(mode=mode, model=model)
        if "use_log1p" not in meta:
            meta["use_log1p"] = False
        return model, meta

    def _default_xgb_for_mode(self, mode: str, **params) -> XGBRegressor:
        return _default_xgb_impl(mode, **params)

    def _fit_estimator(self, estimator: Any, X: np.ndarray, y: np.ndarray) -> Any:
        return _fit_estimator_impl(estimator, X, y)

    def _xgb_param_dist(self, mode: str) -> Dict[str, List[Any]]:
        # 後方互換のために残す（内部では trainer.py の実装を使用）
        from model.trainer import _param_dist
        return _param_dist(mode)

    def _search_best_xgb(self, mode: str, X: np.ndarray, y: np.ndarray) -> Tuple[XGBRegressor, Dict[str, Any]]:
        return _search_best_xgb_impl(mode, X, y)

    # ======================================================
    # Data Prep
    # ======================================================
    def _filter_product_rows(self, shipment_data: pd.DataFrame, barcode: str) -> pd.DataFrame:
        date_col, barcode_col, qty_col, customer_col = self._resolve_shipment_columns(shipment_data)
        df = shipment_data.copy()
        df = df[df[barcode_col].astype(str) == str(barcode)].copy()
        if df.empty:
            raise ValueError(f"shipment data not found for barcode: {barcode}")

        df["ds"] = pd.to_datetime(df[date_col], errors="coerce")
        df["y"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0.0)
        df = df.dropna(subset=["ds"]).copy()
        df["y"] = df["y"].clip(lower=0.0)
        if df.empty:
            raise ValueError(f"valid dated shipment data not found for barcode: {barcode}")

        if customer_col is not None and customer_col in df.columns:
            df["customer_id"] = df[customer_col].astype(str)
            df.loc[df["customer_id"].isin(["", "nan", "None", "NaN"]), "customer_id"] = np.nan
        else:
            df["customer_id"] = np.nan
        return df[["ds", "y", "customer_id"]].copy()

    def _build_customer_period_features(
        self,
        product_df: pd.DataFrame,
        freq: str,
        rolling_window: int,
    ) -> pd.DataFrame:
        tmp = product_df.dropna(subset=["customer_id"]).copy()
        if tmp.empty:
            return pd.DataFrame(columns=["ds"] + self.CUSTOMER_FEATURE_COLS)

        period_grouper = pd.Grouper(key="ds", freq=freq)
        unique_count = tmp.groupby(period_grouper)["customer_id"].nunique()
        vol_total = tmp.groupby(period_grouper)["y"].sum()
        by_customer = tmp.groupby([period_grouper, "customer_id"])["y"].sum()
        top_customer = by_customer.groupby(level=0).max()
        top_share = (top_customer / vol_total.replace(0, np.nan)).fillna(0.0)

        cust_df = pd.DataFrame(
            {
                "ds": unique_count.index,
                "cust_unique": unique_count.astype(float).values,
                "cust_top_share": top_share.reindex(unique_count.index, fill_value=0.0).astype(float).values,
            }
        )
        cust_df = cust_df.set_index("ds").asfreq(freq, fill_value=0.0).reset_index()
        cust_df["cust_unique_roll"] = cust_df["cust_unique"].rolling(rolling_window, min_periods=1).mean()
        cust_df["cust_top_share_roll"] = cust_df["cust_top_share"].rolling(rolling_window, min_periods=1).mean()
        return cust_df

    def _prepare_periodic_series(
        self,
        shipment_data: pd.DataFrame,
        barcode: str,
        freq: str,
        include_customer: bool = False,
    ) -> pd.DataFrame:
        product_df = self._filter_product_rows(shipment_data, barcode)
        periodic = (
            product_df.set_index("ds")["y"]
            .resample(freq)
            .sum()
            .asfreq(freq, fill_value=0.0)
            .reset_index()
        )
        periodic.columns = ["ds", "y"]

        if include_customer:
            roll = 4 if freq == self.WEEKLY_FREQ else 3
            cust = self._build_customer_period_features(product_df, freq=freq, rolling_window=roll)
            if not cust.empty:
                periodic = periodic.merge(cust, on="ds", how="left")
            for c in self.CUSTOMER_FEATURE_COLS:
                if c not in periodic.columns:
                    periodic[c] = 0.0
                periodic[c] = pd.to_numeric(periodic[c], errors="coerce").fillna(0.0)

        periodic["y"] = pd.to_numeric(periodic["y"], errors="coerce").fillna(0.0).clip(lower=0.0)
        periodic = periodic.sort_values("ds").reset_index(drop=True)
        return periodic

    def _add_calendar_features_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["week"] = d["ds"].dt.isocalendar().week.astype(int)
        d["year"] = d["ds"].dt.year.astype(int)
        d["week_sin"] = np.sin(2.0 * np.pi * d["week"] / 52.0)
        d["week_cos"] = np.cos(2.0 * np.pi * d["week"] / 52.0)

        holiday_days = []
        for end_day in d["ds"]:
            week_start = end_day - pd.Timedelta(days=6)
            holiday_days.append(self._calc_holiday_count_for_week(week_start))
        d["holiday_days"] = np.asarray(holiday_days, dtype=int)
        d["work_days"] = 7 - d["holiday_days"]

        m = d["ds"].dt.month
        d["is_may"] = (m == 5).astype(int)
        d["is_june"] = (m == 6).astype(int)
        d["is_nov"] = (m == 11).astype(int)
        d["is_dec"] = (m == 12).astype(int)
        return d

    def _add_calendar_features_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["year"] = d["ds"].dt.year.astype(int)
        d["month"] = d["ds"].dt.month.astype(int)
        d["month_sin"] = np.sin(2.0 * np.pi * d["month"] / 12.0)
        d["month_cos"] = np.cos(2.0 * np.pi * d["month"] / 12.0)

        d["is_may"] = (d["month"] == 5).astype(int)
        d["is_june"] = (d["month"] == 6).astype(int)
        d["is_nov"] = (d["month"] == 11).astype(int)
        d["is_dec"] = (d["month"] == 12).astype(int)

        # 月次にも営業日寄与を追加（休日数/稼働日数）
        holiday_days = [self._calc_holiday_count_for_month(pd.Timestamp(x)) for x in d["ds"]]
        d["holiday_days"] = np.asarray(holiday_days, dtype=int)
        d["work_days"] = np.maximum(d["ds"].dt.days_in_month - d["holiday_days"], 0).astype(int)
        return d

    def _build_weekly_features(self, df_in: pd.DataFrame) -> pd.DataFrame:
        d = df_in.copy()
        d = self._add_calendar_features_weekly(d)

        for lag in self.WEEKLY_LAGS:
            d[f"lag_{lag}"] = d["y"].shift(lag, fill_value=0.0)

        for (window, stat) in self.WEEKLY_ROLLING:
            if stat == "mean":
                d[f"rolling_mean_{window}"] = d["y"].rolling(window, min_periods=1).mean().fillna(0.0)
            else:
                d[f"rolling_std_{window}"] = d["y"].rolling(window, min_periods=1).std(ddof=0).fillna(0.0)

        for c in self.CUSTOMER_FEATURE_COLS:
            if c not in d.columns:
                d[c] = 0.0
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)

        full_cols = self._weekly_feature_cols(use_customer=True)
        for c in full_cols:
            if c not in d.columns:
                d[c] = 0.0

        return d[["ds", "y"] + full_cols].copy()

    def _build_monthly_features(self, df_in: pd.DataFrame) -> pd.DataFrame:
        d = df_in.copy()
        d = self._add_calendar_features_monthly(d)

        for lag in self.MONTHLY_LAGS:
            d[f"lag_{lag}"] = d["y"].shift(lag, fill_value=0.0)

        for (window, stat) in self.MONTHLY_ROLLING:
            if stat == "mean":
                d[f"rolling_mean_{window}"] = d["y"].rolling(window, min_periods=1).mean().fillna(0.0)
            else:
                d[f"rolling_std_{window}"] = d["y"].rolling(window, min_periods=1).std(ddof=0).fillna(0.0)

        for c in self.CUSTOMER_FEATURE_COLS:
            if c not in d.columns:
                d[c] = 0.0
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)

        full_cols = self._monthly_feature_cols(use_customer=True)
        for c in full_cols:
            if c not in d.columns:
                d[c] = 0.0

        # month_colsの年(year)を常に含む（typo対策）
        if "year" not in d.columns:
            d["year"] = d["ds"].dt.year.astype(int)

        return d[["ds", "y"] + full_cols].copy()

    # ======================================================
    # Train (Weekly / Monthly)
    # ======================================================
    def train_product_model_weekly(self, shipment_data: pd.DataFrame, barcode: str):
        weekly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.WEEKLY_FREQ,
            include_customer=self.enable_customer_features,
        )
        weekly["y"] = self._clip_upper_outliers(weekly["y"])
        feat = self._build_weekly_features(weekly)

        feature_cols = self._weekly_feature_cols(use_customer=self.enable_customer_features)
        X = self._safe_array(feat[feature_cols].values)
        y_raw = pd.to_numeric(feat["y"], errors="coerce").fillna(0.0).clip(lower=0.0).values

        use_log1p = self._should_use_log_transform(y_raw)
        y_train = self._transform_target(y_raw, use_log1p=use_log1p)

        if len(X) < 20:
            model = Ridge()
            self._fit_estimator(model, X, y_train)
            meta = {
                "mode": "weekly",
                "feature_cols": feature_cols,
                "use_log1p": use_log1p,
                "freq": self.WEEKLY_FREQ,
                "with_customer_features": self.enable_customer_features,
            }
            self._save_model(barcode, model, "weekly", meta=meta)
            return

        model, best_params = self._search_best_xgb("weekly", X, y_train)
        split = max(8, int(len(X) * 0.2))
        split = min(split, len(X))
        hold_pred = self._safe_predict(model, X[-split:], use_log1p=use_log1p)
        hold_true = y_raw[-split:]
        m = self._calc_metrics(hold_true, hold_pred)

        print(f"[Weekly XGB] {barcode} best_params= {best_params}")
        print(f"{barcode} RMSE={m['rmse']:.3f} MAE={m['mae']:.3f} sMAPE={m['smape']:.3f}")

        meta = {
            "mode": "weekly",
            "feature_cols": feature_cols,
            "use_log1p": use_log1p,
            "freq": self.WEEKLY_FREQ,
            "with_customer_features": self.enable_customer_features,
        }
        self._save_model(barcode, model, "weekly", meta=meta)

    def train_product_model_monthly(self, shipment_data: pd.DataFrame, barcode: str):
        # 欠損月をasfreq(M)で0埋めし、月次でも一貫した時系列整形を実施
        monthly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.MONTHLY_FREQ,
            include_customer=self.enable_customer_features,
        )
        monthly["y"] = self._clip_upper_outliers(monthly["y"])
        feat = self._build_monthly_features(monthly)

        feature_cols = self._monthly_feature_cols(use_customer=self.enable_customer_features)
        X = self._safe_array(feat[feature_cols].values)
        y_raw = pd.to_numeric(feat["y"], errors="coerce").fillna(0.0).clip(lower=0.0).values

        use_log1p = self._should_use_log_transform(y_raw)
        y_train = self._transform_target(y_raw, use_log1p=use_log1p)

        if len(X) < 12:
            model = Ridge()
            self._fit_estimator(model, X, y_train)
            meta = {
                "mode": "monthly",
                "feature_cols": feature_cols,
                "use_log1p": use_log1p,
                "freq": self.MONTHLY_FREQ,
                "with_customer_features": self.enable_customer_features,
            }
            self._save_model(barcode, model, "monthly", meta=meta)
            return

        model, best_params = self._search_best_xgb("monthly", X, y_train)
        split = max(6, int(len(X) * 0.2))
        split = min(split, len(X))
        hold_pred = self._safe_predict(model, X[-split:], use_log1p=use_log1p)
        hold_true = y_raw[-split:]
        m = self._calc_metrics(hold_true, hold_pred)

        print(f"[Monthly XGB] {barcode} best_params= {best_params}")
        print(f"{barcode} RMSE={m['rmse']:.3f} MAE={m['mae']:.3f} sMAPE={m['smape']:.3f}")

        meta = {
            "mode": "monthly",
            "feature_cols": feature_cols,
            "use_log1p": use_log1p,
            "freq": self.MONTHLY_FREQ,
            "with_customer_features": self.enable_customer_features,
        }
        self._save_model(barcode, model, "monthly", meta=meta)

    # ======================================================
    # Walk-Forward Evaluation
    # ======================================================
    def _fit_model_from_dataframe(
        self,
        mode: str,
        train_df: pd.DataFrame,
        model_payload: Optional[Any] = None,
    ) -> Tuple[Any, List[str], bool]:
        if mode == "weekly":
            feat_df = self._build_weekly_features(train_df)
            default_cols = self._weekly_feature_cols(
                use_customer=bool(self.enable_customer_features and all(c in train_df.columns for c in self.CUSTOMER_FEATURE_COLS))
            )
        else:
            feat_df = self._build_monthly_features(train_df)
            default_cols = self._monthly_feature_cols(
                use_customer=bool(self.enable_customer_features and all(c in train_df.columns for c in self.CUSTOMER_FEATURE_COLS))
            )

        model_template = None
        meta = {}
        if model_payload is not None:
            model_template, meta = self._unwrap_model_payload(model_payload, mode=mode)

        if "feature_cols" in meta:
            feature_cols = list(meta["feature_cols"])
        elif model_template is not None:
            feature_cols = self._choose_default_feature_cols(mode=mode, model=model_template)
        else:
            feature_cols = list(default_cols)

        for c in feature_cols:
            if c not in feat_df.columns:
                feat_df[c] = 0.0

        X = self._safe_array(feat_df[feature_cols].values)
        y_raw = pd.to_numeric(feat_df["y"], errors="coerce").fillna(0.0).clip(lower=0.0).values
        use_log1p = bool(meta.get("use_log1p", self._should_use_log_transform(y_raw)))
        y_train = self._transform_target(y_raw, use_log1p=use_log1p)

        if model_template is not None:
            try:
                estimator = clone(model_template)
            except Exception:
                estimator = Ridge() if len(X) < 10 else self._default_xgb_for_mode(mode)
        else:
            estimator = Ridge() if len(X) < 10 else self._default_xgb_for_mode(mode)

        estimator = self._fit_estimator(estimator, X, y_train)
        return estimator, feature_cols, use_log1p

    def _build_features_by_mode(self, mode: str, df: pd.DataFrame) -> pd.DataFrame:
        if mode == "weekly":
            return self._build_weekly_features(df)
        return self._build_monthly_features(df)

    def _walk_forward_evaluate(
        self,
        periodic_df: pd.DataFrame,
        mode: str,
        test_periods: int,
        model_payload: Optional[Any] = None,
    ) -> Dict[str, Any]:
        freq = self.WEEKLY_FREQ if mode == "weekly" else self.MONTHLY_FREQ
        min_train = 16 if mode == "weekly" else 12
        min_eval = 8 if mode == "weekly" else 6

        d = periodic_df.copy()
        d["ds"] = pd.to_datetime(d["ds"])
        d["y"] = pd.to_numeric(d["y"], errors="coerce").fillna(0.0).clip(lower=0.0)
        d = d.set_index("ds").asfreq(freq, fill_value=0.0).reset_index()

        for c in self.CUSTOMER_FEATURE_COLS:
            if c in d.columns:
                d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)

        if len(d) < (min_train + 2):
            raise ValueError(f"not enough {mode} data for walk-forward evaluation.")

        max_test = len(d) - min_train
        if max_test <= 0:
            raise ValueError(f"not enough {mode} data after minimum train split.")

        test_periods = int(test_periods)
        if max_test >= min_eval and test_periods < min_eval:
            test_periods = min_eval
        test_periods = min(test_periods, max_test)
        if test_periods <= 0:
            raise ValueError(f"invalid test periods for {mode} walk-forward.")

        train_df = d.iloc[:-test_periods].copy()
        test_df = d.iloc[-test_periods:].copy()

        model, feature_cols, use_log1p = self._fit_model_from_dataframe(
            mode=mode,
            train_df=train_df,
            model_payload=model_payload,
        )

        actual = []
        pred = []
        dates = []
        history = train_df.copy()

        for _, row in test_df.iterrows():
            ds = pd.to_datetime(row["ds"])
            y_true = self._to_float(row["y"], default=0.0)

            future_row = {"ds": ds, "y": self._to_float(history["y"].iloc[-1], default=0.0)}
            for c in self.CUSTOMER_FEATURE_COLS:
                if c in history.columns:
                    future_row[c] = self._to_float(history[c].iloc[-1], default=0.0)

            tmp = pd.concat([history, pd.DataFrame([future_row])], ignore_index=True)
            feat_tmp = self._build_features_by_mode(mode, tmp)
            for c in feature_cols:
                if c not in feat_tmp.columns:
                    feat_tmp[c] = 0.0

            X_test = self._safe_array(feat_tmp.iloc[[-1]][feature_cols].values)
            y_pred = float(self._safe_predict(model, X_test, use_log1p=use_log1p)[0])

            actual.append(max(0.0, y_true))
            pred.append(max(0.0, y_pred))
            dates.append(ds)

            next_hist = {"ds": ds, "y": y_true}
            for c in self.CUSTOMER_FEATURE_COLS:
                if c in history.columns:
                    if c in test_df.columns:
                        next_hist[c] = self._to_float(row[c], default=self._to_float(history[c].iloc[-1], 0.0))
                    else:
                        next_hist[c] = self._to_float(history[c].iloc[-1], default=0.0)
            history = pd.concat([history, pd.DataFrame([next_hist])], ignore_index=True)

        metrics = self._calc_metrics(actual, pred)
        return {
            "mode": mode,
            "dates": dates,
            "actual": actual,
            "pred": pred,
            "rmse": metrics["rmse"],
            "mae": metrics["mae"],
            "smape": metrics["smape"],
            "train_size": len(train_df),
            "test_size": len(test_df),
            "use_log1p": bool(use_log1p),
            "feature_cols": list(feature_cols),
        }

    def evaluate_weekly_walk_forward(
        self,
        shipment_data: pd.DataFrame,
        barcode: str,
        test_weeks: int = 12,
        model_payload: Optional[Any] = None,
    ) -> Dict[str, Any]:
        # 週次の評価指標をRMSE/MAE/sMAPEで統一しwalk-forward実装を公開
        weekly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.WEEKLY_FREQ,
            include_customer=self.enable_customer_features,
        )
        payload = model_payload if model_payload is not None else self._load_model(barcode, "weekly")
        return self._walk_forward_evaluate(
            periodic_df=weekly,
            mode="weekly",
            test_periods=test_weeks,
            model_payload=payload,
        )

    def evaluate_monthly_walk_forward(
        self,
        shipment_data: pd.DataFrame,
        barcode: str,
        test_months: int = 12,
        model_payload: Optional[Any] = None,
    ) -> Dict[str, Any]:
        # 月次の評価指標をRMSE/MAE/sMAPEで統一しwalk-forward実装を公開
        monthly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.MONTHLY_FREQ,
            include_customer=self.enable_customer_features,
        )
        payload = model_payload if model_payload is not None else self._load_model(barcode, "monthly")
        return self._walk_forward_evaluate(
            periodic_df=monthly,
            mode="monthly",
            test_periods=test_months,
            model_payload=payload,
        )

    def _plot_backtest_result(self, result: Dict[str, Any], title_prefix: str) -> Figure:
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(result["dates"], result["actual"], label="Actual", color="tab:green")
        ax.plot(result["dates"], result["pred"], label="Forecast", color="tab:red", linestyle="--")
        ax.set_title(
            f"{title_prefix} RMSE={result['rmse']:.2f} "
            f"MAE={result['mae']:.2f} sMAPE={result['smape']:.1f}%"
        )
        ax.legend()
        return fig

    def backtest_weekly_1month(self, shipment_data, barcode):
        model_payload = self._load_model(barcode, model_type="weekly")
        if model_payload is None:
            raise ValueError(f"weekly model not found. train first => {barcode}")
        result = self.evaluate_weekly_walk_forward(
            shipment_data=shipment_data,
            barcode=barcode,
            test_weeks=12,
            model_payload=model_payload,
        )
        return self._plot_backtest_result(result, "Weekly Backtest (WF)")

    def backtest_monthly_1year(self, shipment_data, barcode):
        model_payload = self._load_model(barcode, model_type="monthly")
        if model_payload is None:
            raise ValueError(f"monthly model not found. train first => {barcode}")
        result = self.evaluate_monthly_walk_forward(
            shipment_data=shipment_data,
            barcode=barcode,
            test_months=12,
            model_payload=model_payload,
        )
        return self._plot_backtest_result(result, "Monthly Backtest (WF)")

    # ======================================================
    # Iterative Forecast
    # ======================================================
    def _next_period(self, last_ds: pd.Timestamp, mode: str) -> pd.Timestamp:
        if mode == "weekly":
            return pd.to_datetime(last_ds) + pd.Timedelta(days=7)
        # pd.offsets.MonthEnd typo回避 + months引数不整合回避
        return pd.to_datetime(last_ds) + pd.offsets.MonthEnd(1)

    def _predict_future_periods(
        self,
        history_df: pd.DataFrame,
        model: Any,
        mode: str,
        n_periods: int,
        feature_cols: List[str],
        use_log1p: bool,
    ) -> Tuple[float, List[float]]:
        if history_df.empty or n_periods <= 0:
            return 0.0, []

        freq = self.WEEKLY_FREQ if mode == "weekly" else self.MONTHLY_FREQ
        current = history_df.copy()
        current["ds"] = pd.to_datetime(current["ds"])
        current["y"] = pd.to_numeric(current["y"], errors="coerce").fillna(0.0).clip(lower=0.0)
        current = current.set_index("ds").asfreq(freq, fill_value=0.0).reset_index()

        for c in self.CUSTOMER_FEATURE_COLS:
            if c in current.columns:
                current[c] = pd.to_numeric(current[c], errors="coerce").fillna(0.0)

        total = 0.0
        preds = []

        for _ in range(int(n_periods)):
            next_ds = self._next_period(current["ds"].iloc[-1], mode=mode)
            next_row = {"ds": next_ds, "y": self._to_float(current["y"].iloc[-1], default=0.0)}
            for c in self.CUSTOMER_FEATURE_COLS:
                if c in current.columns:
                    next_row[c] = self._to_float(current[c].tail(4).mean(), default=0.0)

            tmp = pd.concat([current, pd.DataFrame([next_row])], ignore_index=True)
            feat_tmp = self._build_features_by_mode(mode, tmp)
            for c in feature_cols:
                if c not in feat_tmp.columns:
                    feat_tmp[c] = 0.0

            X_test = self._safe_array(feat_tmp.iloc[[-1]][feature_cols].values)
            y_hat = float(self._safe_predict(model, X_test, use_log1p=use_log1p)[0])
            y_hat = max(0.0, y_hat)

            total += y_hat
            preds.append(y_hat)

            next_row["y"] = y_hat
            current = pd.concat([current, pd.DataFrame([next_row])], ignore_index=True)
        return total, preds

    def _is_simple(self, model):
        return getattr(model, "n_features_in_", 0) == 1

    def _predict_by_simple_index_model(self, model: Any, start_index: int, n_periods: int) -> float:
        total = 0.0
        for step in range(int(n_periods)):
            X_test = np.array([[start_index + step]], dtype=float)
            y_hat = self._to_float(model.predict(X_test)[0], default=0.0)
            total += max(0.0, y_hat)
        return total

    # ======================================================
    # Public Forecast APIs (Existing I/F)
    # ======================================================
    def predict_consumption_for_n_months_weekly(self, shipment_data, barcode, n=6):
        loaded = self._load_model(barcode, model_type="weekly")
        if loaded is None:
            print(f"[WARN] weekly model not found -> {barcode}")
            return 0.0

        model, meta = self._unwrap_model_payload(loaded, mode="weekly")
        if model is None:
            return 0.0

        feature_cols = list(meta.get("feature_cols", self._choose_default_feature_cols("weekly", model)))
        use_customer = any(c in feature_cols for c in self.CUSTOMER_FEATURE_COLS)
        use_log1p = bool(meta.get("use_log1p", False))

        weekly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.WEEKLY_FREQ,
            include_customer=use_customer,
        )

        if self._is_simple(model):
            return self._predict_by_simple_index_model(model, start_index=len(weekly), n_periods=int(n) * 4)

        hist = weekly.iloc[-max(16, max(self.WEEKLY_LAGS) + 1) :].copy().reset_index(drop=True)
        total, _ = self._predict_future_periods(
            history_df=hist,
            model=model,
            mode="weekly",
            n_periods=int(n) * 4,
            feature_cols=feature_cols,
            use_log1p=use_log1p,
        )
        return total

    def predict_consumption_for_n_months_monthly(self, shipment_data: pd.DataFrame, barcode: str, n: int = 6) -> float:
        loaded = self._load_model(barcode, "monthly")
        if loaded is None:
            print(f"[WARN] monthly model not found -> {barcode}")
            return 0.0

        model, meta = self._unwrap_model_payload(loaded, mode="monthly")
        if model is None:
            return 0.0

        feature_cols = list(meta.get("feature_cols", self._choose_default_feature_cols("monthly", model)))
        use_customer = any(c in feature_cols for c in self.CUSTOMER_FEATURE_COLS)
        use_log1p = bool(meta.get("use_log1p", False))

        monthly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.MONTHLY_FREQ,
            include_customer=use_customer,
        )

        if self._is_simple(model):
            return self._predict_by_simple_index_model(model, start_index=len(monthly), n_periods=int(n))

        hist = monthly.iloc[-max(12, max(self.MONTHLY_LAGS) + 1) :].copy().reset_index(drop=True)
        total, _ = self._predict_future_periods(
            history_df=hist,
            model=model,
            mode="monthly",
            n_periods=int(n),
            feature_cols=feature_cols,
            use_log1p=use_log1p,
        )
        return total

    def _predict_next_weeks_weekly(self, shipment_data, barcode, n_weeks=4):
        loaded = self._load_model(barcode, model_type="weekly")
        if loaded is None:
            return 0.0
        model, meta = self._unwrap_model_payload(loaded, mode="weekly")
        if model is None:
            return 0.0

        feature_cols = list(meta.get("feature_cols", self._choose_default_feature_cols("weekly", model)))
        use_customer = any(c in feature_cols for c in self.CUSTOMER_FEATURE_COLS)
        use_log1p = bool(meta.get("use_log1p", False))

        weekly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.WEEKLY_FREQ,
            include_customer=use_customer,
        )
        if self._is_simple(model):
            return self._predict_by_simple_index_model(model, start_index=len(weekly), n_periods=int(n_weeks))

        total, _ = self._predict_future_periods(
            history_df=weekly,
            model=model,
            mode="weekly",
            n_periods=int(n_weeks),
            feature_cols=feature_cols,
            use_log1p=use_log1p,
        )
        return total

    def _predict_next_weeks_weekly_inner(self, hist_df: pd.DataFrame, model, n_weeks: int) -> float:
        if hist_df.empty:
            return 0.0
        feature_cols = self._choose_default_feature_cols("weekly", model)
        total, _ = self._predict_future_periods(
            history_df=hist_df,
            model=model,
            mode="weekly",
            n_periods=int(n_weeks),
            feature_cols=feature_cols,
            use_log1p=False,
        )
        return total

    def _predict_next_months_monthly(self, shipment_data, barcode, n_months=1):
        # 旧実装の「1ステップ予測 × n倍」を修正し、月次を反復予測に統一
        loaded = self._load_model(barcode, model_type="monthly")
        if loaded is None:
            return 0.0
        model, meta = self._unwrap_model_payload(loaded, mode="monthly")
        if model is None:
            return 0.0

        feature_cols = list(meta.get("feature_cols", self._choose_default_feature_cols("monthly", model)))
        use_customer = any(c in feature_cols for c in self.CUSTOMER_FEATURE_COLS)
        use_log1p = bool(meta.get("use_log1p", False))

        monthly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.MONTHLY_FREQ,
            include_customer=use_customer,
        )
        if self._is_simple(model):
            return self._predict_by_simple_index_model(model, start_index=len(monthly), n_periods=int(n_months))

        total, _ = self._predict_future_periods(
            history_df=monthly,
            model=model,
            mode="monthly",
            n_periods=int(n_months),
            feature_cols=feature_cols,
            use_log1p=use_log1p,
        )
        return total

    def predict_inventory_weekly(self, shipment_data, inventory_data, barcode, return_fig=False):
        loaded = self._load_model(barcode, model_type="weekly")
        if loaded is None:
            raise ValueError(f"weekly model not found. train first => {barcode}")

        model, meta = self._unwrap_model_payload(loaded, mode="weekly")
        if model is None:
            raise ValueError(f"weekly model is invalid => {barcode}")

        feature_cols = list(meta.get("feature_cols", self._choose_default_feature_cols("weekly", model)))
        use_customer = any(c in feature_cols for c in self.CUSTOMER_FEATURE_COLS)
        use_log1p = bool(meta.get("use_log1p", False))

        weekly = self._prepare_periodic_series(
            shipment_data=shipment_data,
            barcode=barcode,
            freq=self.WEEKLY_FREQ,
            include_customer=use_customer,
        )
        feat = self._build_weekly_features(weekly)
        for c in feature_cols:
            if c not in feat.columns:
                feat[c] = 0.0
        X_all = self._safe_array(feat[feature_cols].values)
        y_all = pd.to_numeric(feat["y"], errors="coerce").fillna(0.0).clip(lower=0.0).values

        if self._is_simple(model):
            y_pred = np.asarray(
                [max(0.0, self._to_float(model.predict(np.array([[i]], dtype=float))[0], default=0.0)) for i in range(len(y_all))]
            )
        else:
            y_pred = self._safe_predict(model, X_all, use_log1p=use_log1p)

        m = self._calc_metrics(y_all, y_pred)

        fig = None
        if return_fig:
            fig = Figure(figsize=(5, 3), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(feat["ds"], y_all, label="Actual", color="tab:blue")
            ax.plot(feat["ds"], y_pred, label="Forecast", color="tab:red", linestyle="--")
            ax.set_title(
                f"Weekly Full Backtest RMSE={m['rmse']:.2f} "
                f"MAE={m['mae']:.2f} sMAPE={m['smape']:.1f}%"
            )
            ax.legend()
        return fig

    def _get_product_inventory(self, inventory_data: pd.DataFrame, barcode: str) -> Optional[float]:
        barcode_col, stock_col = self._resolve_inventory_columns(inventory_data)
        row = inventory_data[inventory_data[barcode_col].astype(str) == str(barcode)]
        if row.empty:
            return None
        inv = self._to_float(row.iloc[0][stock_col], default=0.0)
        return inv

    def predict_months_left_weekly(self, shipment_data, inventory_data, barcode):
        model_payload = self._load_model(barcode, model_type="weekly")
        if model_payload is None:
            return None, None

        current_inv = self._get_product_inventory(inventory_data, barcode)
        if current_inv is None:
            return None, None
        if current_inv <= 0:
            return 0.0, 0.0

        c_1month = self._predict_next_weeks_weekly(shipment_data, barcode, n_weeks=4)
        if c_1month <= 0:
            return 9999, 9999

        days_left = (current_inv / c_1month) * 30.0
        months_left = days_left / 30.0
        return months_left, days_left

    def predict_months_left_monthly(self, shipment_data, inventory_data, barcode):
        model_payload = self._load_model(barcode, model_type="monthly")
        if model_payload is None:
            return None, None

        current_inv = self._get_product_inventory(inventory_data, barcode)
        if current_inv is None:
            return None, None
        if current_inv <= 0:
            return 0.0, 0.0

        c_1month = self._predict_next_months_monthly(shipment_data, barcode, n_months=1)
        if c_1month <= 0:
            return 9999, 9999

        days_left = (current_inv / c_1month) * 30.0
        months_left = days_left / 30.0
        return months_left, days_left

    # ======================================================
    # Parts depletion
    # ======================================================
    def _compute_remaining_days(self, leftover, consumption, period_days):
        if consumption > 0:
            return leftover / consumption * period_days
        return None

    def predict_parts_depletion(
        self,
        product_barcode,
        product_inventory,
        shipment_data,
        df_parts,
        is_monthly=False,
    ):
        if is_monthly:
            cons_6m = self.predict_consumption_for_n_months_monthly(shipment_data, product_barcode, n=6)
            cons_1m = self.predict_consumption_for_n_months_monthly(shipment_data, product_barcode, n=1)
        else:
            cons_6m = self.predict_consumption_for_n_months_weekly(shipment_data, product_barcode, n=6)
            cons_1m = self.predict_consumption_for_n_months_weekly(shipment_data, product_barcode, n=1)

        six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
        one_month_days = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days

        part_name_col, part_stock_col = self._resolve_parts_columns(df_parts)

        results = []
        base_inv = self._to_float(product_inventory, default=0.0)
        for _, row in df_parts.iterrows():
            part_name = row.get(part_name_col, "")
            part_inv = self._to_float(row.get(part_stock_col, 0), default=0.0)
            leftover = base_inv + part_inv

            days_6 = self._compute_remaining_days(leftover, cons_6m, six_months_days)
            days_1 = self._compute_remaining_days(leftover, cons_1m, one_month_days)

            if days_6 is None:
                results.append(
                    f"[WARN] {product_barcode}: 6month consumption unavailable. part '{part_name}' depletion cannot be estimated."
                )
            if days_1 is None:
                results.append(
                    f"[WARN] {product_barcode}: 1month consumption unavailable. part '{part_name}' depletion cannot be estimated."
                )
            if days_6 is not None and days_6 <= 180:
                results.append(f"[ALERT 6M] part '{part_name}' depleted in {days_6:.0f} days => product {product_barcode}")
            if days_1 is not None and days_1 <= 30:
                results.append(f"[ALERT 1M] part '{part_name}' depleted in {days_1:.0f} days => product {product_barcode}")
        return results

    # ======================================================
    # Holiday / Working-day helpers
    # ======================================================
    def _calc_holiday_count_for_week(self, week_start):
        return _holiday_week_impl(week_start)

    def _calc_holiday_count_for_month(self, month_end):
        return _holiday_month_impl(month_end)

    def _is_holiday(self, day):
        return _is_holiday_impl(day)

    # ======================================================
    # Save / Load
    # NOTE: model/store.py に同等のスタンドアロン実装あり。
    #       段階的な分割計画: model/ パッケージへ移行予定。
    # ======================================================
    def _save_model(self, barcode: str, model, model_type: str = "weekly", meta: Optional[Dict[str, Any]] = None):
        _save_model_impl(self.model_dir, barcode, model, model_type=model_type, meta=meta)

    def _load_model(self, barcode: str, model_type: str = "weekly"):
        return _load_model_impl(self.model_dir, barcode, model_type=model_type)
