from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from model_handler import ModelHandler
from public.access_handler import AccessHandler
from public.config import EXCLUDED_JSON, MODELS_DIR, WEEKLY_JSON, ensure_dirs, load_json_list, save_json_list
from public.email_notifier import EmailNotifier


class BarcodeRequest(BaseModel):
    barcode: str


class ExclusionRequest(BaseModel):
    barcode: str
    excluded: bool


class PublicService:
    def __init__(self):
        ensure_dirs()
        self.access_handler = AccessHandler()
        self.model_handler = ModelHandler()
        self.model_handler.model_dir = str(MODELS_DIR)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.email_notifier = EmailNotifier()

        self.shipment_df: pd.DataFrame | None = None
        self.inventory_df: pd.DataFrame | None = None
        self.refresh_data()

    def refresh_data(self) -> None:
        # 実DB再取得ではなく、公開サンプルCSVを再読み込み。
        self.shipment_df = self.access_handler.get_shipment_data()
        self.inventory_df = self.access_handler.get_inventory_data()

    def get_weekly_set(self) -> set[str]:
        return set(load_json_list(WEEKLY_JSON))

    def get_excluded_set(self) -> set[str]:
        return set(load_json_list(EXCLUDED_JSON))

    def update_excluded(self, barcode: str, excluded: bool) -> list[str]:
        data = self.get_excluded_set()
        if excluded:
            data.add(barcode)
        else:
            data.discard(barcode)
        result = sorted(data)
        save_json_list(EXCLUDED_JSON, result)
        return result

    def get_barcodes(self, q: str = "") -> list[str]:
        if self.shipment_df is None:
            return []
        q_norm = q.strip().lower()
        excluded = self.get_excluded_set()
        values = sorted({str(x).strip() for x in self.shipment_df["barcode"].tolist() if str(x).strip()})
        values = [v for v in values if v not in excluded]
        if q_norm:
            values = [v for v in values if q_norm in v.lower()]
        return values

    def _is_weekly(self, barcode: str) -> bool:
        return barcode in self.get_weekly_set()

    def train(self, barcode: str) -> dict[str, Any]:
        if self.shipment_df is None:
            raise ValueError("shipment data is not loaded.")
        if barcode not in self.get_barcodes():
            raise ValueError(f"barcode not found: {barcode}")
        if self._is_weekly(barcode):
            self.model_handler.train_product_model_weekly(self.shipment_df, barcode)
            mode = "weekly"
        else:
            self.model_handler.train_product_model_monthly(self.shipment_df, barcode)
            mode = "monthly"
        return {"ok": True, "barcode": barcode, "mode": mode}

    def backtest_plot(self, barcode: str):
        if self.shipment_df is None:
            raise ValueError("shipment data is not loaded.")
        if self._is_weekly(barcode):
            return self.model_handler.backtest_weekly_1month(self.shipment_df, barcode), "weekly"
        return self.model_handler.backtest_monthly_1year(self.shipment_df, barcode), "monthly"

    def _get_product_inventory(self, barcode: str) -> float:
        if self.inventory_df is None or self.inventory_df.empty:
            return 0.0
        row = self.inventory_df[self.inventory_df["barcode"].astype(str) == str(barcode)]
        if row.empty:
            return 0.0
        return float(pd.to_numeric(row.iloc[0]["inventory"], errors="coerce") or 0.0)

    def predict_parts(self, barcode: str) -> dict[str, Any]:
        if self.shipment_df is None:
            raise ValueError("shipment data is not loaded.")

        is_weekly = self._is_weekly(barcode)
        product_inventory = self._get_product_inventory(barcode)
        parts_df = self.access_handler.get_parts_info(barcode)
        alerts = self.model_handler.predict_parts_depletion(
            product_barcode=barcode,
            product_inventory=product_inventory,
            shipment_data=self.shipment_df,
            df_parts=parts_df,
            is_monthly=not is_weekly,
        )

        if is_weekly:
            cons_6m = self.model_handler.predict_consumption_for_n_months_weekly(self.shipment_df, barcode, n=6)
            cons_1m = self.model_handler.predict_consumption_for_n_months_weekly(self.shipment_df, barcode, n=1)
            mode = "weekly"
        else:
            cons_6m = self.model_handler.predict_consumption_for_n_months_monthly(self.shipment_df, barcode, n=6)
            cons_1m = self.model_handler.predict_consumption_for_n_months_monthly(self.shipment_df, barcode, n=1)
            mode = "monthly"

        six_month_days = 180.0
        one_month_days = 30.0
        rows = []
        for _, row in parts_df.iterrows():
            part_name = str(row.get("part_name", ""))
            part_stock = float(pd.to_numeric(row.get("stock", 0.0), errors="coerce") or 0.0)
            total_stock = max(0.0, product_inventory + part_stock)
            days_6 = (total_stock / cons_6m) * six_month_days if cons_6m > 0 else None
            days_1 = (total_stock / cons_1m) * one_month_days if cons_1m > 0 else None
            rows.append(
                {
                    "part_name": part_name,
                    "part_stock": part_stock,
                    "days_left_6mo": None if days_6 is None else round(days_6, 1),
                    "days_left_1mo": None if days_1 is None else round(days_1, 1),
                }
            )

        return {
            "barcode": barcode,
            "mode": mode,
            "product_inventory": product_inventory,
            "parts": rows,
            "alerts": alerts,
        }

    def send_test_notification(self) -> dict[str, Any]:
        self.email_notifier.set_to_addrs(["example@example.com"])
        sent = self.email_notifier.send_notification(
            subject="[TW_Prophet Public] Notification Test",
            body=f"Notification check at {datetime.now().isoformat(timespec='seconds')}",
            html_mode=False,
        )
        return {"ok": bool(sent), "enabled": self.email_notifier.enabled}


svc = PublicService()
app = FastAPI(title="TW_Prophet Public", version="public-1.0.0")


@app.get("/api/status")
def api_status():
    return {
        "ok": True,
        "shipments": 0 if svc.shipment_df is None else int(len(svc.shipment_df)),
        "inventory": 0 if svc.inventory_df is None else int(len(svc.inventory_df)),
        "models_dir": str(MODELS_DIR),
    }


@app.post("/api/refresh")
def api_refresh():
    try:
        svc.refresh_data()
        return JSONResponse({"ok": True})
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/barcodes")
def api_barcodes(q: str = ""):
    try:
        return {"ok": True, "barcodes": svc.get_barcodes(q=q)}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/excluded")
def api_excluded():
    return {"ok": True, "barcodes": sorted(svc.get_excluded_set())}


@app.post("/api/excluded")
def api_excluded_update(req: ExclusionRequest):
    try:
        barcodes = svc.update_excluded(barcode=req.barcode.strip(), excluded=bool(req.excluded))
        return {"ok": True, "barcodes": barcodes}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/train")
def api_train(req: BarcodeRequest):
    try:
        return svc.train(req.barcode.strip())
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.get("/api/backtest_plot")
def api_backtest_plot(barcode: str):
    try:
        fig, mode = svc.backtest_plot(barcode.strip())
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png", headers={"X-TW-Mode": mode})
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.get("/api/parts")
def api_parts(barcode: str):
    try:
        return svc.predict_parts(barcode.strip())
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.post("/api/notify_run")
def api_notify_run():
    try:
        return svc.send_test_notification()
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/", response_class=HTMLResponse)
def index():
    # 社内リンク/社内文言を除去した公開版UI。
    return HTMLResponse(
        """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TW_Prophet Public</title>
  <style>
    body { font-family: "Segoe UI", sans-serif; margin: 18px; background: #f4f6fb; color:#1b2130; }
    .wrap { display: grid; grid-template-columns: 280px 1fr; gap: 14px; }
    .card { background:#fff; border:1px solid #dce3ef; border-radius:12px; padding:12px; }
    .list { height: 420px; overflow:auto; border:1px solid #dce3ef; border-radius:8px; margin-top:8px; }
    .item { padding:8px 10px; border-bottom:1px solid #edf1f8; cursor:pointer; }
    .item:hover { background:#edf3ff; }
    .item.sel { background:#dbe7ff; }
    button { cursor:pointer; border:none; border-radius:8px; padding:8px 12px; background:#3658d6; color:#fff; }
    .muted { color:#5a6479; font-size: 13px; }
    img { width: 100%; min-height: 280px; object-fit: contain; border:1px solid #dce3ef; border-radius:10px; background:#fff; }
    table { width:100%; border-collapse: collapse; font-size:13px; }
    th, td { border-bottom:1px solid #edf1f8; padding:6px; text-align:left; }
    #msg { white-space: pre-wrap; margin-top:8px; color:#234; font-size:13px; }
  </style>
</head>
<body>
  <h2>TW_Prophet Public</h2>
  <p class="muted">Sample CSV data only. Internal DB / internal email list are not included.</p>
  <div class="wrap">
    <section class="card">
      <input id="q" placeholder="Search barcode" onkeydown="if(event.key==='Enter')loadBarcodes()" />
      <button onclick="loadBarcodes()">Search</button>
      <div id="list" class="list"></div>
    </section>
    <section class="card">
      <div>Selected: <b id="sel">---</b></div>
      <div style="margin-top:8px; display:flex; gap:8px;">
        <button onclick="trainOne()">Train</button>
        <button onclick="showPlot()">Backtest</button>
        <button onclick="showParts()">Parts Forecast</button>
        <button onclick="refreshData()">Reload CSV</button>
      </div>
      <div id="msg"></div>
      <div style="margin-top:10px;"><img id="plot" alt="plot" /></div>
      <div style="margin-top:12px;" id="parts"></div>
    </section>
  </div>
  <script>
    let selected = '';
    function msg(t){ document.getElementById('msg').textContent = t || ''; }
    function esc(s){ return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); }
    async function api(url, opts){
      const r = await fetch(url, opts);
      if(!r.ok){
        let d=''; try{ d=(await r.json()).detail; }catch(e){ d=await r.text(); }
        throw new Error(d || ('HTTP '+r.status));
      }
      return r;
    }
    async function loadBarcodes(){
      const q = document.getElementById('q').value || '';
      const r = await api('/api/barcodes?q=' + encodeURIComponent(q));
      const j = await r.json();
      const list = document.getElementById('list');
      list.innerHTML = '';
      for(const bc of (j.barcodes || [])){
        const div = document.createElement('div');
        div.className = 'item' + (bc === selected ? ' sel' : '');
        div.textContent = bc;
        div.onclick = () => {
          selected = bc;
          document.getElementById('sel').textContent = bc;
          loadBarcodes();
        };
        list.appendChild(div);
      }
    }
    async function trainOne(){
      if(!selected){ msg('Select barcode first.'); return; }
      msg('Training...');
      const r = await api('/api/train', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({barcode:selected})
      });
      const j = await r.json();
      msg('Trained: ' + j.barcode + ' (' + j.mode + ')');
    }
    async function showPlot(){
      if(!selected){ msg('Select barcode first.'); return; }
      msg('Rendering plot...');
      const r = await api('/api/backtest_plot?barcode=' + encodeURIComponent(selected));
      const blob = await r.blob();
      document.getElementById('plot').src = URL.createObjectURL(blob);
      msg('Backtest updated.');
    }
    async function showParts(){
      if(!selected){ msg('Select barcode first.'); return; }
      const r = await api('/api/parts?barcode=' + encodeURIComponent(selected));
      const j = await r.json();
      const rows = (j.parts || []).map(x =>
        `<tr><td>${esc(x.part_name)}</td><td>${x.part_stock}</td><td>${x.days_left_6mo ?? '-'}</td><td>${x.days_left_1mo ?? '-'}</td></tr>`
      ).join('');
      const alerts = (j.alerts || []).map(x => `<li>${esc(x)}</li>`).join('');
      document.getElementById('parts').innerHTML = `
        <div class="muted">Mode: ${esc(j.mode)} / Product inventory: ${j.product_inventory}</div>
        <table><thead><tr><th>Part</th><th>Stock</th><th>Days Left (6M)</th><th>Days Left (1M)</th></tr></thead><tbody>${rows}</tbody></table>
        <div style="margin-top:8px;"><b>Alerts</b><ul>${alerts || '<li>None</li>'}</ul></div>
      `;
      msg('Parts forecast updated.');
    }
    async function refreshData(){
      await api('/api/refresh', {method:'POST'});
      msg('Sample CSV reloaded.');
      await loadBarcodes();
    }
    loadBarcodes();
  </script>
</body>
</html>
        """
    )

