"""
api/service.py  –  TWProphetWebService

データ取得・学習・予測・通知の実行ロジックをまとめたサービス層。
FastAPI ルーターおよびスタートアップ処理から利用する。
"""
from __future__ import annotations

import io
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import config
from model_handler import ModelHandler
from email_notifier import EmailNotifier
from access_handler import AccessHandler

# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _load_json_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_json_list(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(sorted(set(values)), f, ensure_ascii=False, indent=2)


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json_dict(path: Path, d: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# サービスクラス
# ---------------------------------------------------------------------------

class TWProphetWebService:
    """学習・予測・通知の統合サービス。"""

    def __init__(self) -> None:
        config.ensure_dirs()

        self.access_handler = AccessHandler()
        self.model_handler  = ModelHandler()
        self.model_handler.model_dir = str(config.MODELS_DIR)
        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

        self.email_notifier = EmailNotifier()
        self._lock        = threading.RLock()
        self._db_lock     = threading.RLock()
        self._notify_lock = threading.Lock()
        self._train_lock  = threading.Lock()
        self._status_lock = threading.Lock()

        self._shipment_df:  pd.DataFrame | None = None
        self._inventory_df: pd.DataFrame | None = None

        self._train_status: dict[str, Any] = {
            "running": False, "total": 0, "done": 0,
            "failed": [], "started_at": None, "finished_at": None, "current": None,
        }

        with self._lock:
            self._ensure_notify_settings_file()

        if config.NOTIFY_AUTO:
            t = threading.Thread(target=self._notify_loop, daemon=True)
            t.start()

        if config.AUTO_RETRAIN_MONTHLY:
            t2 = threading.Thread(target=self._monthly_retrain_loop, daemon=True)
            t2.start()

    # ------------------------------------------------------------------
    # 永続リスト（除外/週次/メール）
    # ------------------------------------------------------------------
    def get_excluded_set(self) -> set[str]:
        with self._lock:
            return set(_load_json_list(config.EXCLUDED_JSON))

    def set_excluded(self, barcode: str, excluded: bool) -> None:
        with self._lock:
            current = set(_load_json_list(config.EXCLUDED_JSON))
            if excluded:
                current.add(barcode)
            else:
                current.discard(barcode)
            _save_json_list(config.EXCLUDED_JSON, sorted(current))

    def get_weekly_set(self) -> set[str]:
        with self._lock:
            return set(_load_json_list(config.WEEKLY_JSON))

    def set_weekly(self, barcode: str, weekly: bool) -> None:
        with self._lock:
            current = set(_load_json_list(config.WEEKLY_JSON))
            if weekly:
                current.add(barcode)
            else:
                current.discard(barcode)
            _save_json_list(config.WEEKLY_JSON, sorted(current))

    def get_email_list(self) -> list[str]:
        with self._lock:
            return _load_json_list(config.EMAIL_JSON)

    def add_email(self, email: str) -> None:
        with self._lock:
            current = _load_json_list(config.EMAIL_JSON)
            if email not in current:
                current.append(email)
                _save_json_list(config.EMAIL_JSON, current)

    def remove_email(self, email: str) -> None:
        with self._lock:
            current = _load_json_list(config.EMAIL_JSON)
            current = [e for e in current if e != email]
            _save_json_list(config.EMAIL_JSON, current)

    # ------------------------------------------------------------------
    # 通知設定
    # ------------------------------------------------------------------
    def _ensure_notify_settings_file(self) -> None:
        """notify_settings.json を初期化（呼び出し側でロック取得済みを前提）。"""
        d = _load_json_dict(config.NOTIFY_SETTINGS_JSON)
        if not d:
            d = {"enabled": True, "reminder_days": 90, "updated_at": _now_iso()}
            _save_json_dict(config.NOTIFY_SETTINGS_JSON, d)
            return
        changed = False
        if "enabled" not in d:
            d["enabled"] = True
            changed = True
        if "reminder_days" not in d:
            d["reminder_days"] = 90
            changed = True
        if changed:
            d["updated_at"] = _now_iso()
            _save_json_dict(config.NOTIFY_SETTINGS_JSON, d)

    def get_notify_settings(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_notify_settings_file()
            d = _load_json_dict(config.NOTIFY_SETTINGS_JSON)
            return {
                "enabled": bool(d.get("enabled", True)),
                "reminder_days": int(d.get("reminder_days", 90)),
                "updated_at": d.get("updated_at", ""),
            }

    def update_notify_settings(self, enabled: bool | None, reminder_days: int | None) -> dict[str, Any]:
        with self._lock:
            self._ensure_notify_settings_file()
            d = _load_json_dict(config.NOTIFY_SETTINGS_JSON)
            if enabled is not None:
                d["enabled"] = bool(enabled)
            if reminder_days is not None:
                rd = max(1, min(3650, int(reminder_days)))
                d["reminder_days"] = rd
            d["updated_at"] = _now_iso()
            _save_json_dict(config.NOTIFY_SETTINGS_JSON, d)
            return {
                "enabled": bool(d.get("enabled", True)),
                "reminder_days": int(d.get("reminder_days", 90)),
                "updated_at": d.get("updated_at", ""),
            }

    def _load_notify_state(self) -> dict[str, Any]:
        d = _load_json_dict(config.NOTIFY_STATE_JSON)
        if not d:
            d = {"version": 1, "items": {}, "updated_at": _now_iso()}
        if "items" not in d or not isinstance(d["items"], dict):
            d["items"] = {}
        return d

    def _save_notify_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now_iso()
        _save_json_dict(config.NOTIFY_STATE_JSON, state)

    # ------------------------------------------------------------------
    # DB ロード（キャッシュ付き）
    # ------------------------------------------------------------------
    def refresh_db(self) -> None:
        with self._db_lock:
            shipment = self.access_handler.get_shipment_data()
            shipment = shipment[shipment["バーコード"].notnull()]
            inv = self.access_handler.get_inventory_data()
            inv = inv[inv["バーコード"].notnull()]
            self._shipment_df  = shipment
            self._inventory_df = inv

    def _ensure_db(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with self._db_lock:
            if self._shipment_df is None or self._inventory_df is None:
                self.refresh_db()
            assert self._shipment_df is not None
            assert self._inventory_df is not None
            return self._shipment_df, self._inventory_df

    # ------------------------------------------------------------------
    # 主要機能
    # ------------------------------------------------------------------
    def list_barcodes(self, search: str = "") -> list[str]:
        shipment, _ = self._ensure_db()
        excluded = self.get_excluded_set()
        barcodes = [bc for bc in shipment["バーコード"].unique().tolist()
                    if bc and bc not in excluded]
        if search:
            s = search.strip().lower()
            barcodes = [bc for bc in barcodes if s in str(bc).lower()]
        return sorted(barcodes)

    def train_one(self, barcode: str) -> dict[str, Any]:
        shipment, _ = self._ensure_db()
        if barcode in self.get_excluded_set():
            raise ValueError(f"{barcode} は除外対象です")
        if barcode in self.get_weekly_set():
            self.model_handler.train_product_model_weekly(shipment, barcode)
            return {"barcode": barcode, "mode": "weekly"}
        else:
            self.model_handler.train_product_model_monthly(shipment, barcode)
            return {"barcode": barcode, "mode": "monthly"}

    def backtest_figure(self, barcode: str):
        shipment, _ = self._ensure_db()
        if barcode in self.get_weekly_set():
            return self.model_handler.backtest_weekly_1month(shipment, barcode)
        else:
            return self.model_handler.backtest_monthly_1year(shipment, barcode)

    def backtest_png(self, barcode: str) -> bytes:
        """バックテストプロットを PNG バイト列で返す。"""
        fig = self.backtest_figure(barcode)
        buf = io.BytesIO()
        try:
            fig.set_size_inches(12, 6, forward=True)
        except Exception:
            pass
        try:
            fig.savefig(buf, format="png", dpi=180, bbox_inches="tight", pad_inches=0.05)
        finally:
            try:
                plt.close(fig)
            except Exception:
                pass
        buf.seek(0)
        return buf

    def parts_prediction(self, barcode: str) -> dict[str, Any]:
        shipment, inventory = self._ensure_db()
        is_weekly = barcode in self.get_weekly_set()

        product_inv_row = inventory[inventory["バーコード"] == barcode]
        product_inventory = float(product_inv_row.iloc[0]["在庫数"]) if not product_inv_row.empty else 0.0

        with self._db_lock:
            df_parts = self.access_handler.get_parts_info(barcode)

        if df_parts is None or df_parts.empty:
            return {
                "barcode": barcode, "product_inventory": product_inventory,
                "parts": [], "alerts": [], "note": "部品情報がありません",
            }

        six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
        one_month_days  = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days

        if is_weekly:
            c_6mo = float(self.model_handler.predict_consumption_for_n_months_weekly(shipment, barcode, n=6))
            c_1mo = float(self.model_handler.predict_consumption_for_n_months_weekly(shipment, barcode, n=1))
        else:
            c_6mo = float(self.model_handler.predict_consumption_for_n_months_monthly(shipment, barcode, n=6))
            c_1mo = float(self.model_handler.predict_consumption_for_n_months_monthly(shipment, barcode, n=1))

        alerts = self.model_handler.predict_parts_depletion(
            product_barcode=barcode,
            product_inventory=product_inventory,
            shipment_data=shipment,
            df_parts=df_parts,
            is_monthly=(not is_weekly),
        )

        parts = []
        for _, row in df_parts.iterrows():
            part_name = str(row.get("部品名", ""))
            part_inv  = float(row.get("在庫数", 0))
            days_6mo  = (product_inventory + part_inv) / c_6mo * six_months_days if c_6mo > 0 else None
            days_1mo  = (product_inventory + part_inv) / c_1mo * one_month_days  if c_1mo > 0 else None
            parts.append({
                "part_name": part_name, "part_inventory": part_inv,
                "days_6mo": days_6mo,   "days_1mo": days_1mo,
            })

        return {
            "barcode": barcode, "mode": "weekly" if is_weekly else "monthly",
            "product_inventory": product_inventory, "parts": parts, "alerts": alerts,
        }

    # ------------------------------------------------------------------
    # 在庫減少通知（部品のみ）
    # ------------------------------------------------------------------
    def _notify_loop(self) -> None:
        time.sleep(5)
        while True:
            try:
                self.run_parts_notification(force=False)
            except Exception as e:
                print(f"[WARN] notify loop failed: {e}")
            time.sleep(max(1, config.NOTIFY_INTERVAL_MIN) * 60)

    def run_parts_notification(self, force: bool = False) -> dict[str, Any]:
        if not self._notify_lock.acquire(blocking=False):
            return {"ok": True, "skipped": True, "reason": "notify already running"}
        try:
            return self._run_parts_notification_impl(force=force)
        finally:
            self._notify_lock.release()

    def _run_parts_notification_impl(self, force: bool = False) -> dict[str, Any]:
        settings = self.get_notify_settings()
        if (not force) and (not settings.get("enabled", True)):
            return {"ok": True, "skipped": True, "reason": "notify disabled"}

        reminder_days = int(settings.get("reminder_days", 90))
        now = datetime.now()

        self.refresh_db()
        shipment, inventory = self._ensure_db()

        excluded   = self.get_excluded_set()
        weekly_set = self.get_weekly_set()
        barcodes   = sorted([bc for bc in shipment["バーコード"].unique().tolist()
                              if bc and bc not in excluded])

        to_addrs = self.get_email_list()
        if not to_addrs:
            return {"ok": False, "error": "email_list.json が空です（送信先がありません）"}

        with self._lock:
            state = self._load_notify_state()
            items: dict[str, Any] = state.get("items", {})
            if not isinstance(items, dict):
                items = {}
                state["items"] = items

        pending: list[dict[str, Any]] = []

        for bc in barcodes:
            is_weekly = bc in weekly_set
            product_inv_row = inventory[inventory["バーコード"] == bc]
            product_inv = float(product_inv_row.iloc[0]["在庫数"]) if not product_inv_row.empty else 0.0

            with self._db_lock:
                df_parts = self.access_handler.get_parts_info(bc)
            if df_parts is None or df_parts.empty:
                continue

            six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
            one_month_days  = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days

            try:
                if is_weekly:
                    c_6mo = float(self.model_handler.predict_consumption_for_n_months_weekly(shipment, bc, n=6))
                    c_1mo = float(self.model_handler.predict_consumption_for_n_months_weekly(shipment, bc, n=1))
                else:
                    c_6mo = float(self.model_handler.predict_consumption_for_n_months_monthly(shipment, bc, n=6))
                    c_1mo = float(self.model_handler.predict_consumption_for_n_months_monthly(shipment, bc, n=1))
            except Exception:
                continue

            for _, row in df_parts.iterrows():
                part_name   = str(row.get("部品名", "")).strip()
                part_inv    = float(row.get("在庫数", 0) or 0)
                days_6mo    = (product_inv + part_inv) / c_6mo * six_months_days if c_6mo > 0 else None
                days_1mo    = (product_inv + part_inv) / c_1mo * one_month_days  if c_1mo > 0 else None

                alert_kind = None
                if days_1mo is not None and days_1mo <= 30:
                    alert_kind = "1か月前"
                elif days_6mo is not None and days_6mo <= 180:
                    alert_kind = "半年前"

                key = f"{bc}||{part_name}"
                if alert_kind is None:
                    items.pop(key, None)
                    continue

                total_supply = float(product_inv + part_inv)
                rec = items.get(key)
                if rec is None:
                    rec = {
                        "barcode": bc, "part_name": part_name,
                        "baseline_supply": total_supply, "last_notified_supply": total_supply,
                        "last_notified_at": None, "reset_pending": False,
                        "ever_notified": False, "alert_active_since": _now_iso(),
                    }
                    items[key] = rec

                last_notified_supply = float(rec.get("last_notified_supply", total_supply))
                if total_supply > last_notified_supply + 1e-9:
                    rec.update({
                        "baseline_supply": total_supply, "last_notified_supply": total_supply,
                        "last_notified_at": None, "reset_pending": True,
                    })
                    continue

                last_notified_at = _parse_iso(rec.get("last_notified_at"))
                ever_notified    = bool(rec.get("ever_notified", False))
                reset_pending    = bool(rec.get("reset_pending", False))
                baseline_supply  = float(rec.get("baseline_supply", total_supply))
                remind_due       = last_notified_at is not None and (now - last_notified_at).days >= reminder_days

                send_due = (not ever_notified) and (rec.get("last_notified_at") is None)
                if ever_notified and not remind_due:
                    send_due = False
                if reset_pending:
                    send_due = total_supply < baseline_supply - 1e-9
                if remind_due:
                    send_due = True

                if not send_due:
                    continue

                pending.append({
                    "barcode": bc, "part_name": part_name,
                    "product_inventory": product_inv, "part_inventory": part_inv,
                    "total_supply": total_supply,
                    "days_6mo": days_6mo, "days_1mo": days_1mo,
                    "alert_kind": alert_kind, "mode": "weekly" if is_weekly else "monthly",
                    "key": key,
                })

        with self._lock:
            state["items"] = items
            self._save_notify_state(state)

        if not pending:
            return {"ok": True, "sent": 0, "pending": 0}

        rows = []
        for x in pending:
            d6 = "-" if x["days_6mo"] is None else f"{x['days_6mo']:.1f}日"
            d1 = "-" if x["days_1mo"] is None else f"{x['days_1mo']:.1f}日"
            rows.append(
                "<tr>"
                f"<td>{x['barcode']}</td><td>{x['part_name']}</td>"
                f"<td style='text-align:right;'>{x['total_supply']:.1f}</td>"
                f"<td style='text-align:right;'>{x['product_inventory']:.1f}</td>"
                f"<td style='text-align:right;'>{x['part_inventory']:.1f}</td>"
                f"<td>{d6}</td><td>{d1}</td>"
                f"<td>{x['alert_kind']}</td><td>{x['mode']}</td>"
                "</tr>"
            )

        html_body = f"""<html><head><meta charset='utf-8'></head><body>
<h2>【TW_Prophet】部品在庫減少通知</h2>
<p>- リマインド: {reminder_days}日ごと</p>
<table border='1' cellspacing='0' cellpadding='4' style='border-collapse:collapse;'>
<tr><th>製品バーコード</th><th>部品名</th><th>総在庫</th><th>製品在庫</th>
    <th>部品在庫</th><th>半年残日数</th><th>1ヶ月残日数</th><th>種別</th><th>モデル</th></tr>
{''.join(rows)}
</table>
<p style="color:#666;">generated at {_now_iso()}</p>
</body></html>""".strip()

        try:
            self.email_notifier.set_to_addrs(to_addrs)
            self.email_notifier.send_notification("【在庫警告】部品在庫減少通知（TW_Prophet）",
                                                   html_body, html_mode=True)
        except Exception as e:
            return {"ok": False, "error": f"メール送信に失敗: {e}", "pending": len(pending)}

        with self._lock:
            state2 = self._load_notify_state()
            items2 = state2.get("items", {})
            now_iso = _now_iso()
            for x in pending:
                rec2 = items2.get(x["key"])
                if not rec2:
                    continue
                rec2.update({
                    "last_notified_at": now_iso, "last_notified_supply": float(x["total_supply"]),
                    "baseline_supply": float(x["total_supply"]), "reset_pending": False,
                    "ever_notified": True, "last_alert_kind": x["alert_kind"],
                })
            state2["items"] = items2
            self._save_notify_state(state2)

        return {"ok": True, "sent": 1, "pending": len(pending), "items": pending[:50]}

    # ------------------------------------------------------------------
    # 一括学習
    # ------------------------------------------------------------------
    def train_all(self) -> dict[str, Any]:
        """全バーコードを順番に学習する（バックグラウンド実行）。"""
        if not self._train_lock.acquire(blocking=False):
            return {"ok": False, "reason": "already_running"}

        def _run() -> None:
            try:
                barcodes = self.list_barcodes()
                total = len(barcodes)
                failed: list[dict[str, str]] = []
                with self._status_lock:
                    self._train_status.update({
                        "running": True, "total": total, "done": 0,
                        "failed": [], "started_at": _now_iso(),
                        "finished_at": None, "current": None,
                    })
                for bc in barcodes:
                    with self._status_lock:
                        self._train_status["current"] = bc
                    try:
                        self.train_one(bc)
                    except Exception as e:
                        failed.append({"barcode": bc, "error": str(e)})
                    with self._status_lock:
                        self._train_status["done"] += 1
                        self._train_status["failed"] = failed

                now_iso = _now_iso()
                with self._status_lock:
                    self._train_status.update({
                        "running": False, "finished_at": now_iso, "current": None,
                    })
                self._save_retrain_state(now_iso)
            finally:
                self._train_lock.release()

        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True, "started": True}

    def get_train_status(self) -> dict[str, Any]:
        with self._status_lock:
            status = dict(self._train_status)
            status["failed"] = list(status.get("failed", []))
        retrain = self._load_retrain_state()
        status["last_retrain_at"] = retrain.get("last_retrain_at")
        status["next_retrain_at"] = retrain.get("next_retrain_at")
        status["auto_retrain_monthly"] = config.AUTO_RETRAIN_MONTHLY
        return status

    # ------------------------------------------------------------------
    # 月次自動再学習
    # ------------------------------------------------------------------
    def _load_retrain_state(self) -> dict[str, Any]:
        return _load_json_dict(config.RETRAIN_STATE_JSON)

    def _save_retrain_state(self, last_retrain_at: str) -> None:
        next_dt = datetime.fromisoformat(last_retrain_at) + timedelta(days=30)
        _save_json_dict(config.RETRAIN_STATE_JSON, {
            "last_retrain_at": last_retrain_at,
            "next_retrain_at": next_dt.isoformat(timespec="seconds"),
        })

    def _monthly_retrain_loop(self) -> None:
        time.sleep(60)  # 起動直後は待機
        while True:
            try:
                state = self._load_retrain_state()
                next_str = state.get("next_retrain_at")
                if next_str:
                    next_dt = _parse_iso(next_str)
                    if next_dt and datetime.now() >= next_dt:
                        self.train_all()
            except Exception as e:
                print(f"[WARN] monthly retrain check failed: {e}")
            time.sleep(3600)  # 1時間ごとにチェック
