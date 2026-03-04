"""tw_prophet_web.py

TW_Prophet を社内向け Web アプリ(API + 簡易UI)として動かすためのエントリ。

狙い
 - File-Server (推奨: Windows) に常駐させ、社員がブラウザで閲覧できるようにする。
 - 既存の学習/予測ロジック(ModelHandler)とDB取得(AccessHandler)は極力そのまま利用。
 - Tkinter(GUI)依存を切り離して、サーバー上でGUI無しで動作。

起動例:
  (conda env)
  python run_web.py

環境変数(任意)
  - TW_PROPHET_DATA_DIR                : JSON(models/excluded/email/weekly list) を置く基準ディレクトリ
  - TW_PROPHET_MODELS_DIR              : 学習済みモデル(pkl)の保存先ディレクトリ
  - PORT                               : 待受ポート(既定 8000)

  - TW_PROPHET_ALLOW_WEB_TRAIN         : Webから学習を許可(1=許可, 既定0)

  - TW_PROPHET_NOTIFY_AUTO             : 在庫減少通知(部品のみ)の自動チェック(1=ON, 0=OFF, 既定1)
  - TW_PROPHET_NOTIFY_INTERVAL_MIN     : 自動チェックの間隔(分, 既定360=6時間)
"""

from __future__ import annotations

import io
import json
import os
import threading
import time
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

import matplotlib.pyplot as plt

# 既存ロジック
from model_handler import ModelHandler
from email_notifier import EmailNotifier
from access_handler import AccessHandler


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("TW_PROPHET_DATA_DIR", BASE_DIR)
MODELS_DIR = os.getenv("TW_PROPHET_MODELS_DIR", os.path.join(DATA_DIR, "models"))

EXCLUDED_JSON = os.path.join(DATA_DIR, "excluded_products.json")
WEEKLY_JSON = os.path.join(DATA_DIR, "weekly_data_list.json")
EMAIL_JSON = os.path.join(DATA_DIR, "email_list.json")

# 在庫減少通知(部品のみ)の 永続ファイル
NOTIFY_SETTINGS_JSON = os.path.join(DATA_DIR, "notify_settings.json")
NOTIFY_STATE_JSON = os.path.join(DATA_DIR, "notify_state.json")

ALLOW_WEB_TRAIN = os.getenv("TW_PROPHET_ALLOW_WEB_TRAIN", "0").strip() == "1"

# 通知の自動チェック
NOTIFY_AUTO = os.getenv("TW_PROPHET_NOTIFY_AUTO", "1").strip() == "1"
NOTIFY_INTERVAL_MIN = int(os.getenv("TW_PROPHET_NOTIFY_INTERVAL_MIN", "360"))  # 6時間


def _load_json_list(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_json_list(path: str, values: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)


def _load_json_dict(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json_dict(path: str, d: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


class BarcodeRequest(BaseModel):
    barcode: str


class ExclusionRequest(BaseModel):
    barcode: str
    excluded: bool


class NotifySettingsRequest(BaseModel):
    enabled: bool | None = None
    reminder_days: int | None = None


class NotifyRunRequest(BaseModel):
    force: bool = False


class TWProphetWebService:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(MODELS_DIR, exist_ok=True)

        # AccessHandler の引数はプロジェクト差があるため、柔軟に生成
        try:
            self.access_handler = AccessHandler()
        except TypeError:
            self.access_handler = AccessHandler()

        self.model_handler = ModelHandler()
        self.model_handler.model_dir = MODELS_DIR
        os.makedirs(self.model_handler.model_dir, exist_ok=True)

        self.email_notifier = EmailNotifier()
        self._lock = threading.RLock()
        self._db_lock = threading.RLock()
        self._notify_lock = threading.Lock()

        # キャッシュ(必要なら拡張)
        self._shipment_df: pd.DataFrame | None = None
        self._inventory_df: pd.DataFrame | None = None

        # 通知設定の初期化（なければ作成）
        with self._lock:
            self._ensure_notify_settings_file()

        # 自動通知チェックを起動（メール設定が未完でも落ちないように例外は握り潰す）
        if NOTIFY_AUTO:
            t = threading.Thread(target=self._notify_loop, daemon=True)
            t.start()

    # -----------------
    # 永続リスト
    # -----------------
    def get_excluded_set(self) -> set[str]:
        with self._lock:
            return set(_load_json_list(EXCLUDED_JSON))

    def set_excluded(self, barcode: str, excluded: bool) -> None:
        with self._lock:
            current = set(_load_json_list(EXCLUDED_JSON))
            if excluded:
                current.add(barcode)
            else:
                current.discard(barcode)
            _save_json_list(EXCLUDED_JSON, sorted(current))

    def get_weekly_set(self) -> set[str]:
        with self._lock:
            return set(_load_json_list(WEEKLY_JSON))

    def get_email_list(self) -> list[str]:
        with self._lock:
            return _load_json_list(EMAIL_JSON)

    # -----------------
    # 通知設定 / 状態
    # -----------------
    def _ensure_notify_settings_file(self) -> None:
        """notify_settings.json を初期化する（なければ作成）。

        - 以前はこの関数内でも self._lock を取得していました。
          しかし get_notify_settings()/update_notify_settings() 側でも self._lock を取得していたため、
          threading.Lock の場合は「同一スレッドで二重ロック」になりデッドロックして UI/API が固まります。
        - この関数は「呼び出し側でロック済み」を前提にし、ここではロックを取得しません。
        """
        d = _load_json_dict(NOTIFY_SETTINGS_JSON)
        if not d:
            d = {
                "enabled": True,
                "reminder_days": 90,  # 3か月
                "updated_at": _now_iso(),
            }
            _save_json_dict(NOTIFY_SETTINGS_JSON, d)
            return

        # 欠けているキーだけ補完
        changed = False
        if "enabled" not in d:
            d["enabled"] = True
            changed = True
        if "reminder_days" not in d:
            d["reminder_days"] = 90
            changed = True

        if changed:
            d["updated_at"] = _now_iso()
            _save_json_dict(NOTIFY_SETTINGS_JSON, d)

    def get_notify_settings(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_notify_settings_file()
            d = _load_json_dict(NOTIFY_SETTINGS_JSON)
            return {
                "enabled": bool(d.get("enabled", True)),
                "reminder_days": int(d.get("reminder_days", 90)),
                "updated_at": d.get("updated_at", ""),
            }

    def update_notify_settings(self, enabled: bool | None, reminder_days: int | None) -> dict[str, Any]:
        with self._lock:
            self._ensure_notify_settings_file()
            d = _load_json_dict(NOTIFY_SETTINGS_JSON)

            # UIから安全に更新
            if enabled is not None:
                d["enabled"] = bool(enabled)

            if reminder_days is not None:
                rd = int(reminder_days)
                if rd < 1:
                    rd = 1
                if rd > 3650:
                    rd = 3650  # 10年上限（事故防止）
                d["reminder_days"] = rd

            d["updated_at"] = _now_iso()
            _save_json_dict(NOTIFY_SETTINGS_JSON, d)
            return {
                "enabled": bool(d.get("enabled", True)),
                "reminder_days": int(d.get("reminder_days", 90)),
                "updated_at": d.get("updated_at", ""),
            }

    def _load_notify_state(self) -> dict[str, Any]:
        d = _load_json_dict(NOTIFY_STATE_JSON)
        if not d:
            d = {"version": 1, "items": {}, "updated_at": _now_iso()}
        if "items" not in d or not isinstance(d["items"], dict):
            d["items"] = {}
        return d

    def _save_notify_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now_iso()
        _save_json_dict(NOTIFY_STATE_JSON, state)

    # -----------------
    # DBロード
    # -----------------
    def refresh_db(self) -> None:
        # AccessHandler の実装に依存
        # DB競合防止: Access/MySQL への同時アクセスを防止
        with self._db_lock:
            shipment = self.access_handler.get_shipment_data()
            shipment = shipment[shipment["バーコード"].notnull()]
            inv = self.access_handler.get_inventory_data()
            inv = inv[inv["バーコード"].notnull()]

            self._shipment_df = shipment
            self._inventory_df = inv

    def _ensure_db(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        # キャッシュ参照も DBロックで守る（refresh中に中途半端な状態を読まない）
        with self._db_lock:
            if self._shipment_df is None or self._inventory_df is None:
                self.refresh_db()
            assert self._shipment_df is not None
            assert self._inventory_df is not None
            return self._shipment_df, self._inventory_df

    # -----------------
    # 主要機能
    # -----------------
    def list_barcodes(self, search: str = "") -> list[str]:
        shipment, _ = self._ensure_db()
        excluded = self.get_excluded_set()
        barcodes = [bc for bc in shipment["バーコード"].unique().tolist() if bc and bc not in excluded]
        if search:
            s = search.strip().lower()
            barcodes = [bc for bc in barcodes if s in str(bc).lower()]
        return sorted(barcodes)

    def train_one(self, barcode: str) -> dict[str, Any]:
        shipment, _ = self._ensure_db()
        excluded = self.get_excluded_set()
        if barcode in excluded:
            raise ValueError(f"{barcode} は除外対象です")

        weekly_set = self.get_weekly_set()
        if barcode in weekly_set:
            self.model_handler.train_product_model_weekly(shipment, barcode)
            return {"barcode": barcode, "mode": "weekly"}
        else:
            self.model_handler.train_product_model_monthly(shipment, barcode)
            return {"barcode": barcode, "mode": "monthly"}

    def backtest_figure(self, barcode: str):
        shipment, _ = self._ensure_db()
        weekly_set = self.get_weekly_set()
        if barcode in weekly_set:
            return self.model_handler.backtest_weekly_1month(shipment, barcode)
        else:
            return self.model_handler.backtest_monthly_1year(shipment, barcode)

    def parts_prediction(self, barcode: str) -> dict[str, Any]:
        shipment, inventory = self._ensure_db()
        weekly_set = self.get_weekly_set()
        is_weekly = barcode in weekly_set

        product_inv_row = inventory[inventory["バーコード"] == barcode]
        product_inventory = float(product_inv_row.iloc[0]["在庫数"]) if not product_inv_row.empty else 0.0

        with self._db_lock:
            df_parts = self.access_handler.get_parts_info(barcode)

        if df_parts is None or df_parts.empty:
            return {
                "barcode": barcode,
                "product_inventory": product_inventory,
                "parts": [],
                "alerts": [],
                "note": "部品情報がありません",
            }

        six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
        one_month_days = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days

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
            part_inv = float(row.get("在庫数", 0))

            days_6mo = None
            if c_6mo > 0:
                days_6mo = (product_inventory + part_inv) / c_6mo * six_months_days
            days_1mo = None
            if c_1mo > 0:
                days_1mo = (product_inventory + part_inv) / c_1mo * one_month_days

            parts.append(
                {
                    "part_name": part_name,
                    "part_inventory": part_inv,
                    "days_6mo": days_6mo,
                    "days_1mo": days_1mo,
                }
            )

        return {
            "barcode": barcode,
            "mode": "weekly" if is_weekly else "monthly",
            "product_inventory": product_inventory,
            "parts": parts,
            "alerts": alerts,
        }

    # -----------------
    # 在庫減少通知（部品のみ）
    # -----------------
    def _notify_loop(self) -> None:
        """一定間隔で「部品在庫減少通知」をチェックする（常駐用）。"""
        time.sleep(5)
        while True:
            try:
                self.run_parts_notification(force=False)
            except Exception as e:
                # ここで落ちると以降の自動チェックが止まるので、握り潰してログだけ
                print(f"[WARN] notify loop failed: {e}")
            time.sleep(max(1, NOTIFY_INTERVAL_MIN) * 60)

    def run_parts_notification(self, force: bool = False) -> dict[str, Any]:
        """部品在庫減少通知を実行する（自動/手動の二重実行を抑止）"""
        # 自動ループと手動ボタンが同時に走ると二重送信のリスクがあるため、排他します
        if not self._notify_lock.acquire(blocking=False):
            return {"ok": True, "skipped": True, "reason": "notify already running"}
        try:
            return self._run_parts_notification_impl(force=force)
        finally:
            self._notify_lock.release()

    def _run_parts_notification_impl(self, force: bool = False) -> dict[str, Any]:
        """全製品（除外除く）を走査し、部品のアラートだけをメール通知する。"""
        settings = self.get_notify_settings()
        if (not force) and (not settings.get("enabled", True)):
            return {"ok": True, "skipped": True, "reason": "notify disabled"}

        reminder_days = int(settings.get("reminder_days", 90))
        now = datetime.now()

        # DBは都度更新（在庫の増減を拾う）
        self.refresh_db()
        shipment, inventory = self._ensure_db()

        excluded = self.get_excluded_set()
        weekly_set = self.get_weekly_set()

        barcodes = [bc for bc in shipment["バーコード"].unique().tolist() if bc and bc not in excluded]
        barcodes = sorted(barcodes)

        # 送信先（空なら送れない）
        to_addrs = self.get_email_list()
        if not to_addrs:
            return {"ok": False, "error": "email_list.json が空です（送信先がありません）"}

        # 状態ロード
        with self._lock:
            state = self._load_notify_state()
            items: dict[str, Any] = state.get("items", {})
            if not isinstance(items, dict):
                items = {}
                state["items"] = items

        pending: list[dict[str, Any]] = []  # 今回送る候補

        for bc in barcodes:
            is_weekly = bc in weekly_set

            product_inv_row = inventory[inventory["バーコード"] == bc]
            product_inv = float(product_inv_row.iloc[0]["在庫数"]) if not product_inv_row.empty else 0.0

            # DB競合防止: 部品情報取得は排他
            with self._db_lock:
                df_parts = self.access_handler.get_parts_info(bc)

            if df_parts is None or df_parts.empty:
                # 部品情報がない製品は通知対象外
                continue

            six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
            one_month_days = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days

            try:
                if is_weekly:
                    c_6mo = float(self.model_handler.predict_consumption_for_n_months_weekly(shipment, bc, n=6))
                    c_1mo = float(self.model_handler.predict_consumption_for_n_months_weekly(shipment, bc, n=1))
                else:
                    c_6mo = float(self.model_handler.predict_consumption_for_n_months_monthly(shipment, bc, n=6))
                    c_1mo = float(self.model_handler.predict_consumption_for_n_months_monthly(shipment, bc, n=1))
            except Exception:
                # モデル未学習などは通知しない
                continue

            for _, row in df_parts.iterrows():
                part_name = str(row.get("部品名", "")).strip()
                part_inv = float(row.get("在庫数", 0) or 0)

                # 残日数計算（モデルのconsが低い場合はNone）
                days_6mo = None
                if c_6mo > 0:
                    days_6mo = (product_inv + part_inv) / c_6mo * six_months_days
                days_1mo = None
                if c_1mo > 0:
                    days_1mo = (product_inv + part_inv) / c_1mo * one_month_days

                # アラート判定（部品のみ）
                alert_kind = None
                if days_1mo is not None and days_1mo <= 30:
                    alert_kind = "1か月前"
                elif days_6mo is not None and days_6mo <= 180:
                    alert_kind = "半年前"

                key = f"{bc}||{part_name}"

                # アラートがないなら状態を掃除（通知済みのロックも解除）
                if alert_kind is None:
                    if key in items:
                        del items[key]
                    continue

                total_supply = float(product_inv + part_inv)

                rec = items.get(key)
                if rec is None:
                    # 初回検知（=今回送ってOK）
                    rec = {
                        "barcode": bc,
                        "part_name": part_name,
                        "baseline_supply": total_supply,
                        "last_notified_supply": total_supply,
                        "last_notified_at": None,
                        "reset_pending": False,
                        "ever_notified": False,
                        "alert_active_since": _now_iso(),
                    }
                    items[key] = rec

                # 在庫増加があったら「増えた地点」を新しい基準にして、次の減少まで黙る
                last_notified_supply = float(rec.get("last_notified_supply", total_supply))
                if total_supply > last_notified_supply + 1e-9:
                    rec["baseline_supply"] = total_supply
                    rec["last_notified_supply"] = total_supply
                    rec["last_notified_at"] = None
                    rec["reset_pending"] = True
                    # 増えているので今回送らない（減少通知なので）
                    continue

                last_notified_at = _parse_iso(rec.get("last_notified_at"))
                ever_notified = bool(rec.get("ever_notified", False))
                reset_pending = bool(rec.get("reset_pending", False))
                baseline_supply = float(rec.get("baseline_supply", total_supply))

                # リマインド判定（在庫が増えなくても reminder_days ごとに送る）
                remind_due = False
                if last_notified_at is not None:
                    if (now - last_notified_at).days >= reminder_days:
                        remind_due = True

                send_due = False

                # 初回検知は即送る（まだ一度も成功送信していない場合）
                if (not ever_notified) and (rec.get("last_notified_at") is None):
                    send_due = True

                # 送信済みなら、在庫が増えるまで送らない（remind_due を除く）
                if ever_notified and (not remind_due):
                    send_due = False

                # 在庫が増えた後(reset_pending)は、基準より減ったタイミングで再通知を許可
                if reset_pending:
                    if total_supply < baseline_supply - 1e-9:
                        send_due = True
                    else:
                        send_due = False

                # リマインドは優先
                if remind_due:
                    send_due = True

                if not send_due:
                    continue

                pending.append(
                    {
                        "barcode": bc,
                        "part_name": part_name,
                        "product_inventory": product_inv,
                        "part_inventory": part_inv,
                        "total_supply": total_supply,
                        "days_6mo": days_6mo,
                        "days_1mo": days_1mo,
                        "alert_kind": alert_kind,
                        "mode": "weekly" if is_weekly else "monthly",
                        "key": key,
                    }
                )

        # 状態はまず保存（アラート解除/在庫増加の反映）
        with self._lock:
            state["items"] = items
            self._save_notify_state(state)

        if not pending:
            return {"ok": True, "sent": 0, "pending": 0}

        # メール整形（HTML）
        rows = []
        for x in pending:
            d6 = "-" if x["days_6mo"] is None else f"{x['days_6mo']:.1f}日"
            d1 = "-" if x["days_1mo"] is None else f"{x['days_1mo']:.1f}日"
            rows.append(
                "<tr>"
                f"<td>{x['barcode']}</td>"
                f"<td>{x['part_name']}</td>"
                f"<td style='text-align:right;'>{x['total_supply']:.1f}</td>"
                f"<td style='text-align:right;'>{x['product_inventory']:.1f}</td>"
                f"<td style='text-align:right;'>{x['part_inventory']:.1f}</td>"
                f"<td>{d6}</td>"
                f"<td>{d1}</td>"
                f"<td>{x['alert_kind']}</td>"
                f"<td>{x['mode']}</td>"
                "</tr>"
            )

        html_body = f"""
<html><head><meta charset='utf-8'></head><body>
<h2>【TW_Prophet】部品在庫減少通知</h2>
<p>
- 対象: <b>部品のみ</b>（組み立て品の通知はしません）<br/>
- 重複抑止: 送信後は<b>在庫が増えるまで</b>再送しません（ただしリマインド除く）<br/>
- リマインド: {reminder_days}日ごと
</p>
<table border='1' cellspacing='0' cellpadding='4' style='border-collapse:collapse;'>
<tr>
  <th>製品バーコード</th>
  <th>部品名</th>
  <th>総在庫(製品+部品)</th>
  <th>製品在庫</th>
  <th>部品在庫</th>
  <th>半年残日数</th>
  <th>1ヶ月残日数</th>
  <th>種別</th>
  <th>モデル</th>
</tr>
{''.join(rows)}
</table>
<p style="color:#666;">generated at {_now_iso()}</p>
</body></html>
""".strip()

        subject = "【在庫警告】部品在庫減少通知（TW_Prophet）"

        # 送信（成功時だけ「送信済み」に反映）
        try:
            self.email_notifier.set_to_addrs(to_addrs)
            self.email_notifier.send_notification(subject, html_body, html_mode=True)
        except Exception as e:
            return {"ok": False, "error": f"メール送信に失敗: {e}", "pending": len(pending)}

        # 送信成功 → stateに反映
        with self._lock:
            state2 = self._load_notify_state()
            items2 = state2.get("items", {})
            now_iso = _now_iso()
            for x in pending:
                rec2 = items2.get(x["key"])
                if not rec2:
                    continue
                rec2["last_notified_at"] = now_iso
                rec2["last_notified_supply"] = float(x["total_supply"])
                rec2["baseline_supply"] = float(x["total_supply"])
                rec2["reset_pending"] = False
                rec2["ever_notified"] = True
                rec2["last_alert_kind"] = x["alert_kind"]
                rec2["last_mode"] = x["mode"]
                rec2["last_days_6mo"] = x["days_6mo"]
                rec2["last_days_1mo"] = x["days_1mo"]
            state2["items"] = items2
            self._save_notify_state(state2)

        return {"ok": True, "sent": 1, "pending": len(pending), "items": pending[:50]}


svc = TWProphetWebService()
app = FastAPI(title="TW_Prophet Web", version="0.2")


@app.get("/api/status")
def status():
    return {"ok": True}


@app.post("/api/refresh")
def refresh():
    try:
        svc.refresh_db()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/barcodes")
def barcodes(search: str = ""):
    try:
        return {"barcodes": svc.list_barcodes(search=search)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/train")
def train(req: BarcodeRequest):
    if not ALLOW_WEB_TRAIN:
        raise HTTPException(
            status_code=403,
            detail="Webからの学習は無効です。",
        )
    try:
        result = svc.train_one(req.barcode.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/backtest_plot")
def backtest_plot(barcode: str):
    barcode = barcode.strip()
    try:
        fig = svc.backtest_figure(barcode)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    buf = io.BytesIO()
    try:
        try:
            fig.set_size_inches(12, 6, forward=True)
        except Exception:
            pass

        fig.savefig(buf, format="png", dpi=180, bbox_inches="tight", pad_inches=0.05)
    finally:
        try:
            plt.close(fig)
        except Exception:
            pass

    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/api/parts")
def parts(barcode: str):
    barcode = barcode.strip()
    try:
        return JSONResponse(svc.parts_prediction(barcode))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/excluded")
def excluded():
    return {"excluded": sorted(list(svc.get_excluded_set()))}


@app.post("/api/excluded")
def update_excluded(req: ExclusionRequest):
    try:
        svc.set_excluded(req.barcode.strip(), req.excluded)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 通知設定API
@app.get("/api/notify_settings")
def notify_settings():
    try:
        return svc.get_notify_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notify_settings")
def update_notify_settings(req: NotifySettingsRequest):
    try:
        return svc.update_notify_settings(req.enabled, req.reminder_days)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 手動通知（WebUIのボタン用）
@app.post("/api/notify_run")
def notify_run(req: NotifyRunRequest):
    try:
        return svc.run_parts_notification(force=bool(req.force))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def index():
    # 依存を増やさないため、テンプレートは使わずHTML直書き(最初の足場)
    # レイアウトを「ヘッダー＋残り全部」にして、プロットを最大まで伸ばす
    html = """<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>TW_Prophet Web</title>
  <style>
    /* 画面全体を使うための土台 */
    html, body{height:100%;}
    body{
      font-family:system-ui,-apple-system,Segoe UI,Roboto,'Helvetica Neue',Arial;
      margin:0; background:#221B44; color:#80FFEA;
      display:flex; flex-direction:column; min-height:100vh;
    }

    header{
      padding:12px 16px;
      border-bottom:1px solid rgba(255,255,255,15);
      display:flex; gap:10px; align-items:center;
      flex:0 0 auto;
    }

    /* 左上ナビリンク（製造管理/出荷明細） */
    .navlinks{
      display:flex;
      gap:8px;
      align-items:center;
      flex-wrap:wrap;
    }
    /* # リンク色の視認性を改善（通常/訪問済み/ホバー/フォーカス） */
    .navlinks a,
    .navlinks a:visited{
      color:#E9FFF8;
      text-decoration:none;
      padding:6px 10px;
      border-radius:999px;
      border:1px solid rgba(233,255,248,0.45);
      background:#243554;
      font-size:13px;
      font-weight:600;
      text-shadow:0 1px 0 rgba(0,0,0,0.25);
      transition:background-color .15s ease,color .15s ease,border-color .15s ease;
    }
    .navlinks a:hover{
      color:#FFFFFF;
      background:#2F4B73;
      border-color:rgba(255,255,255,0.70);
    }
    .navlinks a:focus-visible{
      outline:2px solid #FFFFFF;
      outline-offset:2px;
    }

    /* wrapを「残り全部」で埋める + gridの行を1frに固定 */
    .wrap{
      flex:1 1 auto;
      min-height:0;
      display:grid;
      grid-template-columns: 300px 1fr 360px;
      grid-template-rows: 1fr;
      gap:12px;
      padding:12px;
      box-sizing:border-box;
      align-items:stretch;
    }

    /* カードをflex化して、中身(リスト/プロット/表)を伸ばせるようにする */
    .card{
      background:#2E2E3E;
      border:1px solid rgba(255,255,255,12);
      border-radius:12px;
      padding:12px;
      display:flex;
      flex-direction:column;
      min-height:0;
      box-sizing:border-box;
    }

    input,button{font-size:14px;}
    input{
      width:100%; padding:8px 10px; border-radius:10px;
      border:1px solid rgba(255,255,255,18);
      background:#1E1E2F; color:#80FFEA;
      box-sizing:border-box;
    }
    input[type=\"number\"]{width:110px;}
    button{
      padding:10px 12px; border-radius:12px;
      border:1px solid rgba(255,255,255,18);
      background:#1565C0; color:white; cursor:pointer;
    }
    button.secondary{background:#388E3C;}
    button.danger{background:#C62828;}
    button:disabled{opacity:.5; cursor:not-allowed;}

    /* リストは親(card)の残り高さを全部使う */
    .list{
      flex:1 1 auto;
      min-height:0;
      overflow:auto;
      border-radius:12px;
      border:1px solid rgba(255,255,255,12);
      background:#1E1E2F;
    }
    .item{padding:10px; border-bottom:1px solid rgba(255,255,255,08); cursor:pointer;}
    .item:hover{background:#3A3A4E;}
    .item.sel{background:#3A3A4E; outline:1px solid rgba(128,255,234,35)}
    .muted{color:#E5CAFF; opacity:.9}
    .pill{display:inline-block; padding:2px 8px; border-radius:999px; background:#3A0CA3; color:white; font-size:12px;}

    img{border-radius:12px; border:1px solid rgba(255,255,255,12); background:#111;}

    /* プロット領域を最大化してimgをフィットさせる */
    .plotFrame{
      flex:1 1 auto;
      min-height:0;
      display:flex;
      align-items:stretch;
    }
    #plot{
      width:100%;
      height:100%;
      object-fit:contain;   /* 端まで伸ばすが、比率は維持（グラフが潰れない） */
      display:block;
    }
    #msg{
      margin-top:10px;
      white-space:pre-wrap;
      max-height:120px;     /* msgが伸びすぎてプロットを圧迫しない */
      overflow:auto;
    }

    /* 右パネルは中身が多いのでスクロール */
    .rightScroll{
      flex:1 1 auto;
      min-height:0;
      overflow:auto;
    }

    table{width:100%; border-collapse:collapse; font-size:13px;}
    th,td{border-bottom:1px solid rgba(255,255,255,12); padding:6px; text-align:left;}
    .inline{display:flex; gap:8px; align-items:center; flex-wrap:wrap;}
  </style>
</head>
<body>
  <header>
    <div style=\"font-weight:700;\">TW_Prophet Web</div>
    <div class=\"muted\">File-Server常駐版</div>

    <div class=\\"navlinks\\">
      <a href="http://192.168.0.69/manufacturing_control_test/" target=\\"_blank\\" rel=\\"noopener\\">製造管理</a>
      <a href="http://192.168.0.69/manufacturing_control_test/shipments/" target=\\"_blank\\" rel=\\"noopener\\">IO製品の出荷明細</a>
    </div>

    <div style=\"margin-left:auto; display:flex; gap:8px; align-items:center;\">
      <button class=\"secondary\" onclick=\"refreshDb()\">DB再取得</button>
      <button class=\"danger\" onclick=\"runNotify()\">通知チェック</button>
    </div>
  </header>

  <div class=\"wrap\">
    <section class=\"card\">
      <div class=\"muted\" style=\"margin-bottom:8px;\">製品リスト（検索可）</div>
      <input id=\"q\" placeholder=\"例: KB-IOPAD4\" onkeydown=\"if(event.key==='Enter') loadBarcodes()\" />
      <div style=\"height:8px\"></div>
      <button onclick=\"loadBarcodes()\">検索 / 更新</button>
      <div style=\"height:10px\"></div>
      <div id=\"list\" class=\"list\"></div>
    </section>

    <section class=\"card\">
      <div style=\"display:flex; align-items:center; gap:10px;\">
        <div>選択: <span id=\"sel\" class=\"pill\">---</span></div>
        <div style=\"margin-left:auto; display:flex; gap:8px;\">
          <!-- Web版UIから「学習」機能を削除（定期学習運用に寄せる） -->
          <button id=\"btnPredict\" onclick=\"predictOne()\" disabled>更新</button>
        </div>
      </div>
      <div style=\"height:12px\"></div>

      <!-- プロットを伸ばすためのフレーム -->
      <div class=\"plotFrame\">
        <img id=\"plot\" alt=\"backtest plot\" />
      </div>

      <div id=\"msg\" class=\"muted\"></div>
    </section>

    <section class=\"card\">
      <div class=\"muted\">部品在庫予測</div>

      <!-- 通知設定 -->
      <div style=\"height:10px\"></div>
      <div style=\"padding:10px; border:1px solid rgba(255,255,255,12); border-radius:12px; background:#1E1E2F;\">
        <div class=\"muted\" style=\"margin-bottom:6px;\">通知設定（部品のみ）</div>
        <div class=\"inline\">
          <label class=\"muted\" style=\"display:flex; align-items:center; gap:6px;\">
            <input id=\"notifyEnabled\" type=\"checkbox\" style=\"width:auto;\" />
            通知ON
          </label>
          <span class=\"muted\">リマインド(日)</span>
          <input id=\"reminderDays\" type=\"number\" min=\"1\" />
          <button class=\"secondary\" onclick=\"saveNotifySettings()\">保存</button>
        </div>
        <div id=\"notifyMsg\" class=\"muted\" style=\"margin-top:6px;\"></div>
      </div>

      <div style=\"height:10px\"></div>
      <div id=\"mode\" class=\"muted\"></div>

      <!-- 右パネルはスクロール領域にまとめる -->
      <div class=\"rightScroll\">
        <div style=\"height:10px\"></div>
        <div id=\"alerts\" style=\"white-space:pre-wrap;\"></div>
        <div style=\"height:10px\"></div>
        <table>
          <thead><tr><th>部品名</th><th>在庫</th><th>半年残日数</th><th>1ヶ月残日数</th></tr></thead>
          <tbody id=\"parts\"></tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    let selected = '';

    // クリック連打時でも「最後に選んだ製品」だけ描画するための世代管理
    let plotReqToken = 0;

    // 部品在庫予測も「最後に選んだ製品」だけ反映する
    let partsReqToken = 0;

    function setMsg(t){ document.getElementById('msg').textContent = t || ''; }
    function setNotifyMsg(t){ document.getElementById('notifyMsg').textContent = t || ''; }

    async function api(url, opts){
      const r = await fetch(url, opts);
      if(!r.ok){
        let d='';
        try{ d = (await r.json()).detail; }catch(e){ d = await r.text(); }
        throw new Error(d || ('HTTP ' + r.status));
      }
      return r;
    }

    // 通知設定のロード/保存
    async function loadNotifySettings(){
      try{
        const r = await api('/api/notify_settings');
        const j = await r.json();
        document.getElementById('notifyEnabled').checked = !!j.enabled;
        document.getElementById('reminderDays').value = (j.reminder_days ?? 90);
        setNotifyMsg('現在: ' + (j.enabled ? 'ON' : 'OFF') + ' / リマインド ' + (j.reminder_days ?? 90) + ' 日');
      }catch(e){
        setNotifyMsg('通知設定の取得に失敗: ' + e.message);
      }
    }

    async function saveNotifySettings(){
      const enabled = document.getElementById('notifyEnabled').checked;
      const reminder = parseInt(document.getElementById('reminderDays').value || '90', 10);
      setNotifyMsg('保存中...');
      try{
        const r = await api('/api/notify_settings', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({enabled: enabled, reminder_days: reminder})
        });
        const j = await r.json();
        setNotifyMsg('保存しました: ' + (j.enabled ? 'ON' : 'OFF') + ' / リマインド ' + j.reminder_days + ' 日');
      }catch(e){
        setNotifyMsg('保存失敗: ' + e.message);
      }
    }

    // 通知チェック（手動）
    async function runNotify(){
      setNotifyMsg('通知チェック中...');
      try{
        const r = await api('/api/notify_run', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({force:false})
        });
        const j = await r.json();
        if(j && j.ok){
          if(j.pending && j.pending > 0){
            setNotifyMsg('通知を送信しました（件数: ' + j.pending + '）');
          }else{
            setNotifyMsg('通知対象なし');
          }
        }else{
          setNotifyMsg('通知エラー: ' + (j.error || 'unknown'));
        }
      }catch(e){
        setNotifyMsg('通知失敗: ' + e.message);
      }
    }

    // プロットを fetch->blob で取得して表示（エラー文も msg に出せる）
    async function loadPlot(barcode, announce){
      if(!barcode) return;

      const myToken = ++plotReqToken;
      const img = document.getElementById('plot');

      // 古いobjectURLを破棄（メモリリーク対策）
      if(img.dataset && img.dataset.objurl){
        try{ URL.revokeObjectURL(img.dataset.objurl); }catch(e){}
        img.dataset.objurl = '';
      }

      img.src = '';

      if(announce){
        setMsg('プロット生成中.');
      }

      try{
        const r = await api('/api/backtest_plot?barcode=' + encodeURIComponent(barcode) + '&_=' + Date.now());
        const blob = await r.blob();

        // 途中で別の製品が選ばれたら捨てる
        if(myToken !== plotReqToken || selected !== barcode){
          return;
        }

        const url = URL.createObjectURL(blob);
        if(img.dataset){
          img.dataset.objurl = url;
        }
        img.src = url;

        if(announce){
          setMsg('');
        }
      }catch(e){
        if(myToken !== plotReqToken){
          return;
        }
        if(announce){
          setMsg('プロット表示失敗: ' + e.message + '\\n※未学習の可能性があります（定期学習の完了後に再表示してください）');
        }
      }
    }

    // 部品在庫予測を取得して右パネルへ表示（自動プレビュー）
    async function loadParts(barcode, announce){
      if(!barcode) return;

      const myToken = ++partsReqToken;

      if(announce){
        document.getElementById('mode').textContent = '部品在庫予測: 計算中...';
        document.getElementById('alerts').textContent = '';
        document.getElementById('parts').innerHTML = '';
      }

      try{
        const r = await api('/api/parts?barcode=' + encodeURIComponent(barcode));
        const j = await r.json();

        // 途中で別の製品が選ばれたら捨てる
        if(myToken !== partsReqToken || selected !== barcode){
          return;
        }

        document.getElementById('mode').textContent = 'モデル: ' + (j.mode || '-') + ' / 製品在庫: ' + (j.product_inventory ?? '-');

        const alerts = (j.alerts || []).join('\\n');
        document.getElementById('alerts').textContent = alerts ? ('\\n' + alerts) : '（アラートなし）';

        const tbody = document.getElementById('parts');
        tbody.innerHTML = '';
        (j.parts || []).forEach(p=>{
          const tr = document.createElement('tr');
          const d6 = (p.days_6mo===null || p.days_6mo===undefined) ? '予測低下注意' : (p.days_6mo.toFixed(1) + '日');
          const d1 = (p.days_1mo===null || p.days_1mo===undefined) ? '予測低下注意' : (p.days_1mo.toFixed(1) + '日');
          tr.innerHTML = '<td>' + (p.part_name||'') + '</td><td>' + (p.part_inventory??'') + '</td><td>' + d6 + '</td><td>' + d1 + '</td>';
          tbody.appendChild(tr);
        });

      }catch(e){
        if(myToken !== partsReqToken){
          return;
        }
        document.getElementById('mode').textContent = '部品在庫予測: 取得失敗';
        document.getElementById('alerts').textContent = (e && e.message) ? e.message : '取得に失敗しました';
        document.getElementById('parts').innerHTML = '';
      }
    }

    function selectBarcode(bc){
      selected = bc;
      document.getElementById('sel').textContent = bc;
      document.getElementById('btnPredict').disabled = !bc;

      setMsg('');
      document.getElementById('plot').src = '';
      document.getElementById('parts').innerHTML='';
      document.getElementById('alerts').textContent='';
      document.getElementById('mode').textContent='';

      // 選択した瞬間に、プロットと部品在庫予測を自動表示
      loadPlot(bc, true).catch(e => setMsg('プロット表示失敗: ' + e.message));
      loadParts(bc, true).catch(()=>{});
    }

    async function loadBarcodes(){
      const q = document.getElementById('q').value || '';
      setMsg('リスト取得中.');
      const r = await api('/api/barcodes?search=' + encodeURIComponent(q));
      const j = await r.json();
      const list = document.getElementById('list');
      list.innerHTML='';
      j.barcodes.forEach(bc=>{
        const div = document.createElement('div');
        div.className='item' + (bc===selected ? ' sel' : '');
        div.textContent = bc;
        div.onclick = ()=>{
          Array.from(list.children).forEach(x=>x.classList.remove('sel'));
          div.classList.add('sel');
          selectBarcode(bc);
        };
        list.appendChild(div);
      });
      setMsg('件数: ' + j.barcodes.length);
    }

    async function refreshDb(){
      setMsg('DB再取得中.');
      await api('/api/refresh', {method:'POST'});
      await loadBarcodes();
      setMsg('DB再取得完了');
    }

    async function predictOne(){
      if(!selected) return;
      //「更新」ボタンではプロット/部品を再取得するだけ
      setMsg('更新中.');

      const p1 = loadPlot(selected, false);
      const p2 = loadParts(selected, true);
      await Promise.allSettled([p1, p2]);

      setMsg('更新完了');
    }

    // 初期ロード
    loadBarcodes().catch(e=> setMsg('初期ロード失敗: ' + e.message));
    loadNotifySettings().catch(()=>{});
  </script>
</body>
</html>"""
    return html


if __name__ == "__main__":
    # ★変更点★ python tw_prophet_web.py 直実行でもWebサーバーを起動できるようにする
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "tw_prophet_web:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
