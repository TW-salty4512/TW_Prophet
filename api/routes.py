"""
api/routes.py  –  FastAPI ルーター定義

サービスインスタンス (svc) は tw_prophet_web.py で生成し、
このモジュールが公開する `router` にバインドして使う。
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

import config
from api.service import TWProphetWebService

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic リクエストモデル
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# サービス参照（アプリ起動後に tw_prophet_web.py が差し込む）
# ---------------------------------------------------------------------------
_svc: TWProphetWebService | None = None

def bind_service(svc: TWProphetWebService) -> None:
    global _svc
    _svc = svc

def _s() -> TWProphetWebService:
    if _svc is None:
        raise RuntimeError("Service not initialized")
    return _svc


# ---------------------------------------------------------------------------
# ヘルスチェック / DB 操作
# ---------------------------------------------------------------------------

@router.get("/api/status")
def status() -> dict[str, Any]:
    return {"ok": True}


@router.post("/api/refresh")
def refresh() -> dict[str, Any]:
    try:
        _s().refresh_db()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# バーコード一覧
# ---------------------------------------------------------------------------

@router.get("/api/barcodes")
def barcodes(search: str = "") -> dict[str, Any]:
    try:
        return {"barcodes": _s().list_barcodes(search=search)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 学習
# ---------------------------------------------------------------------------

@router.post("/api/train")
def train(req: BarcodeRequest) -> dict[str, Any]:
    import traceback
    if not config.ALLOW_WEB_TRAIN:
        raise HTTPException(status_code=403, detail="Webからの学習は無効です。")
    try:
        return _s().train_one(req.barcode.strip())
    except Exception as e:
        logger.error("[train] %s: %s\n%s", req.barcode, e, traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/train_all")
def train_all() -> dict[str, Any]:
    if not config.ALLOW_WEB_TRAIN:
        raise HTTPException(status_code=403, detail="Webからの学習は無効です。")
    try:
        return _s().train_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/train_status")
def train_status() -> dict[str, Any]:
    try:
        return _s().get_train_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# プロット
# ---------------------------------------------------------------------------

@router.get("/api/backtest_plot")
def backtest_plot(barcode: str) -> StreamingResponse:
    barcode = barcode.strip()
    try:
        buf: BytesIO = _s().backtest_png(barcode)
    except Exception as e:
        logger.warning("[backtest_plot] %s: %s", barcode, e)
        raise HTTPException(status_code=400, detail=str(e))
    return StreamingResponse(buf, media_type="image/png")


# ---------------------------------------------------------------------------
# 部品予測
# ---------------------------------------------------------------------------

@router.get("/api/parts")
def parts(barcode: str) -> JSONResponse:
    barcode = barcode.strip()
    try:
        return JSONResponse(_s().parts_prediction(barcode))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 除外リスト
# ---------------------------------------------------------------------------

@router.get("/api/excluded")
def excluded() -> dict[str, Any]:
    return {"excluded": sorted(_s().get_excluded_set())}


@router.post("/api/excluded")
def update_excluded(req: ExclusionRequest) -> dict[str, Any]:
    try:
        _s().set_excluded(req.barcode.strip(), req.excluded)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 通知設定
# ---------------------------------------------------------------------------

@router.get("/api/notify_settings")
def notify_settings() -> dict[str, Any]:
    try:
        return _s().get_notify_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/notify_settings")
def update_notify_settings(req: NotifySettingsRequest) -> dict[str, Any]:
    try:
        return _s().update_notify_settings(req.enabled, req.reminder_days)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/notify_run")
def notify_run(req: NotifyRunRequest) -> dict[str, Any]:
    try:
        return _s().run_parts_notification(force=bool(req.force))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Web UI（HTML）
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def index() -> str:
    # ナビリンクを config から生成（社内リンクのハードコードを排除）
    nav_link_html = ""
    for link in config.NAV_LINKS:
        label = str(link.get("label", ""))
        url   = str(link.get("url", "#"))
        nav_link_html += (
            f'<a href="{url}" target="_blank" rel="noopener">{label}</a>\n'
        )

    return _HTML_TEMPLATE.replace("<!-- NAV_LINKS -->", nav_link_html)


# ---------------------------------------------------------------------------
# HTML テンプレート（インライン）
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TW_Prophet Web</title>
  <style>
    html,body{height:100%;}
    body{
      font-family:system-ui,-apple-system,Segoe UI,Roboto,'Helvetica Neue',Arial;
      margin:0; background:#221B44; color:#80FFEA;
      display:flex; flex-direction:column; min-height:100vh;
    }
    header{
      padding:12px 16px;
      border-bottom:1px solid rgba(255,255,255,0.06);
      display:flex; gap:10px; align-items:center; flex:0 0 auto;
    }
    .versionBadge{
      padding:2px 8px; border-radius:999px;
      border:1px solid rgba(233,255,248,0.45);
      background:#243554; color:#E9FFF8;
      font-size:12px; font-weight:700; letter-spacing:.04em; white-space:nowrap;
    }
    .navlinks{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
    .navlinks a,.navlinks a:visited{
      color:#E9FFF8;text-decoration:none;padding:6px 10px;
      border-radius:999px;border:1px solid rgba(233,255,248,0.45);
      background:#243554;font-size:13px;font-weight:600;
      transition:background-color .15s,color .15s,border-color .15s;
    }
    .navlinks a:hover{color:#FFF;background:#2F4B73;border-color:rgba(255,255,255,0.7);}
    /* tabs */
    .tabBar{
      display:flex;gap:4px;padding:8px 12px 0;flex:0 0 auto;
    }
    .tabBtn{
      padding:8px 20px;border-radius:12px 12px 0 0;
      border:1px solid rgba(255,255,255,0.12);border-bottom:none;
      background:#2A2040;color:#B0A0E0;cursor:pointer;font-size:14px;font-weight:600;
      transition:background .15s,color .15s;
    }
    .tabBtn.active{background:#2E2E3E;color:#80FFEA;}
    .tabPane{display:none;flex:1 1 auto;min-height:0;flex-direction:column;}
    .tabPane.active{display:flex;}
    /* prediction layout */
    .wrap{
      flex:1 1 auto;min-height:0;display:grid;
      grid-template-columns:300px 1fr 360px;grid-template-rows:1fr;
      gap:12px;padding:12px;box-sizing:border-box;align-items:stretch;
    }
    /* train layout */
    .trainWrap{
      flex:1 1 auto;min-height:0;display:grid;
      grid-template-columns:300px 1fr;grid-template-rows:1fr;
      gap:12px;padding:12px;box-sizing:border-box;align-items:stretch;
    }
    .card{
      background:#2E2E3E;border:1px solid rgba(255,255,255,0.05);
      border-radius:12px;padding:12px;display:flex;flex-direction:column;
      min-height:0;box-sizing:border-box;
    }
    input,button{font-size:14px;}
    input{
      width:100%;padding:8px 10px;border-radius:10px;
      border:1px solid rgba(255,255,255,0.07);
      background:#1E1E2F;color:#80FFEA;box-sizing:border-box;
    }
    input[type="number"]{width:110px;}
    input[type="checkbox"]{width:auto;}
    button{
      padding:10px 12px;border-radius:12px;
      border:1px solid rgba(255,255,255,0.07);
      background:#1565C0;color:white;cursor:pointer;
    }
    button.secondary{background:#388E3C;}
    button.danger{background:#C62828;}
    button.warn{background:#E65100;}
    button:disabled{opacity:.45;cursor:not-allowed;}
    button.sm{padding:5px 10px;font-size:12px;border-radius:8px;}
    .list{
      flex:1 1 auto;min-height:0;overflow:auto;
      border-radius:12px;border:1px solid rgba(255,255,255,0.06);background:#1E1E2F;
    }
    .item{padding:10px;border-bottom:1px solid rgba(255,255,255,0.04);cursor:pointer;display:flex;align-items:center;gap:8px;}
    .item:hover{background:#3A3A4E;}
    .item.sel{background:#3A3A4E;outline:1px solid rgba(128,255,234,0.2);}
    .itemLabel{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .muted{color:#E5CAFF;opacity:.9;}
    .pill{display:inline-block;padding:2px 8px;border-radius:999px;background:#3A0CA3;color:white;font-size:12px;}
    .pill.green{background:#1B5E20;}
    .pill.orange{background:#E65100;}
    img{border-radius:12px;border:1px solid rgba(255,255,255,0.06);background:#111;}
    .plotFrame{flex:1 1 auto;min-height:0;display:flex;align-items:stretch;}
    #plot{width:100%;height:100%;object-fit:contain;display:block;}
    #msg{margin-top:10px;white-space:pre-wrap;max-height:120px;overflow:auto;}
    .rightScroll{flex:1 1 auto;min-height:0;overflow:auto;}
    table{width:100%;border-collapse:collapse;font-size:13px;}
    th,td{border-bottom:1px solid rgba(255,255,255,0.06);padding:6px;text-align:left;}
    .inline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
    /* progress bar */
    .progOuter{
      background:#1E1E2F;border-radius:8px;height:18px;overflow:hidden;
      border:1px solid rgba(255,255,255,0.07);margin:8px 0;
    }
    .progInner{
      height:100%;background:#1565C0;transition:width .4s ease;
      border-radius:8px;min-width:2px;
    }
    .progInner.done{background:#388E3C;}
    .statusDot{
      display:inline-block;width:10px;height:10px;border-radius:50%;
      background:#555;margin-right:6px;vertical-align:middle;
    }
    .statusDot.running{background:#F59E0B;animation:pulse 1s infinite;}
    .statusDot.done{background:#22C55E;}
    .statusDot.idle{background:#555;}
    @keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}
    .failList{
      background:#1E1E2F;border-radius:8px;padding:8px;
      font-size:12px;max-height:120px;overflow:auto;
      border:1px solid rgba(255,100,100,0.2);color:#FF8A80;
    }
    .infoRow{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;}
    .infoItem{display:flex;flex-direction:column;gap:2px;}
    .infoLabel{color:#B0A0E0;font-size:11px;text-transform:uppercase;letter-spacing:.05em;}
  </style>
</head>
<body>
  <header>
    <div style="font-weight:700;">TW_Prophet Web</div>
    <div class="muted">File-Server常駐版</div>
    <div class="versionBadge">Ver 3.3.0</div>
    <div class="navlinks">
<!-- NAV_LINKS -->
    </div>
    <div style="margin-left:auto;display:flex;gap:8px;align-items:center;">
      <button class="secondary" onclick="refreshDb()">DB再取得</button>
      <button class="danger" onclick="runNotify()">通知チェック</button>
    </div>
  </header>

  <!-- タブバー -->
  <div class="tabBar">
    <button class="tabBtn active" id="tab-predict" onclick="switchTab('predict')">予測</button>
    <button class="tabBtn"        id="tab-train"   onclick="switchTab('train')">学習管理</button>
  </div>

  <!-- 予測タブ -->
  <div class="tabPane active" id="pane-predict">
    <div class="wrap">
      <section class="card">
        <div class="muted" style="margin-bottom:8px;">製品リスト（検索可）</div>
        <input id="q" placeholder="例: PRODUCT-A" onkeydown="if(event.key==='Enter') loadBarcodes()" />
        <div style="height:8px"></div>
        <button onclick="loadBarcodes()">検索 / 更新</button>
        <div style="height:10px"></div>
        <div id="list" class="list"></div>
      </section>

      <section class="card">
        <div style="display:flex;align-items:center;gap:10px;">
          <div>選択: <span id="sel" class="pill">---</span></div>
          <div style="margin-left:auto;display:flex;gap:8px;">
            <button id="btnTrain" class="secondary" onclick="trainSelected()" disabled>学習</button>
            <button id="btnPredict" onclick="predictOne()" disabled>更新</button>
          </div>
        </div>
        <div style="height:12px"></div>
        <div class="plotFrame">
          <img id="plot" alt="backtest plot" />
        </div>
        <div id="msg" class="muted"></div>
      </section>

      <section class="card">
        <div class="muted">部品在庫予測</div>
        <div style="height:10px"></div>
        <div style="padding:10px;border:1px solid rgba(255,255,255,0.06);border-radius:12px;background:#1E1E2F;">
          <div class="muted" style="margin-bottom:6px;">通知設定（部品のみ）</div>
          <div class="inline">
            <label class="muted" style="display:flex;align-items:center;gap:6px;">
              <input id="notifyEnabled" type="checkbox" />通知ON
            </label>
            <span class="muted">リマインド(日)</span>
            <input id="reminderDays" type="number" min="1" />
            <button class="secondary" onclick="saveNotifySettings()">保存</button>
          </div>
          <div id="notifyMsg" class="muted" style="margin-top:6px;"></div>
        </div>
        <div style="height:10px"></div>
        <div id="mode" class="muted"></div>
        <div class="rightScroll">
          <div style="height:10px"></div>
          <div id="alerts" style="white-space:pre-wrap;"></div>
          <div style="height:10px"></div>
          <table>
            <thead><tr><th>部品名</th><th>在庫</th><th>半年残日数</th><th>1ヶ月残日数</th></tr></thead>
            <tbody id="parts"></tbody>
          </table>
        </div>
      </section>
    </div>
  </div>

  <!-- 学習管理タブ -->
  <div class="tabPane" id="pane-train">
    <div class="trainWrap">
      <!-- 左: 製品リスト + 個別学習 -->
      <section class="card">
        <div class="muted" style="margin-bottom:8px;">製品リスト（個別学習）</div>
        <input id="tq" placeholder="例: PRODUCT-A" onkeydown="if(event.key==='Enter') loadTrainList()" />
        <div style="height:8px"></div>
        <button onclick="loadTrainList()">検索 / 更新</button>
        <div style="height:10px"></div>
        <div id="trainList" class="list"></div>
      </section>

      <!-- 右: 一括学習・進捗・自動再学習 -->
      <section class="card" style="overflow:auto;">
        <!-- 一括学習 -->
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <span class="statusDot idle" id="trainDot"></span>
          <span id="trainStatusLabel" class="muted">待機中</span>
          <div style="margin-left:auto;display:flex;gap:8px;">
            <button id="btnTrainAll" class="warn" onclick="startTrainAll()">全バーコードを今すぐ学習</button>
          </div>
        </div>

        <!-- プログレスバー -->
        <div class="progOuter" id="progOuter" style="display:none;">
          <div class="progInner" id="progInner" style="width:0%"></div>
        </div>
        <div id="progText" class="muted" style="font-size:12px;"></div>

        <!-- 失敗リスト -->
        <div id="failArea" style="display:none;margin-top:8px;">
          <div class="muted" style="font-size:12px;margin-bottom:4px;">失敗した学習:</div>
          <div id="failList" class="failList"></div>
        </div>

        <!-- 自動再学習情報 -->
        <div style="margin-top:16px;padding:12px;border:1px solid rgba(255,255,255,0.07);border-radius:12px;background:#1E1E2F;">
          <div class="muted" style="margin-bottom:10px;font-weight:600;">月次自動再学習</div>
          <div class="infoRow">
            <div class="infoItem">
              <span class="infoLabel">最終実行</span>
              <span id="lastRetrainAt" class="muted">---</span>
            </div>
            <div class="infoItem">
              <span class="infoLabel">次回予定</span>
              <span id="nextRetrainAt" class="muted">---</span>
            </div>
            <div class="infoItem">
              <span class="infoLabel">自動再学習</span>
              <span id="autoRetrainBadge" class="pill">---</span>
            </div>
          </div>
          <div style="margin-top:10px;" class="muted" id="autoRetrainNote" style="font-size:12px;"></div>
        </div>

        <!-- 完了メッセージ -->
        <div id="trainMsg" class="muted" style="margin-top:12px;white-space:pre-wrap;"></div>
      </section>
    </div>
  </div>

  <script>
    /* -------- 共通ユーティリティ -------- */
    let selected = '';
    let plotReqToken = 0;
    let partsReqToken = 0;
    let trainPolling = null;

    function setMsg(t){ document.getElementById('msg').textContent = t||''; }
    function setNotifyMsg(t){ document.getElementById('notifyMsg').textContent = t||''; }
    function setTrainMsg(t){ document.getElementById('trainMsg').textContent = t||''; }

    async function api(url, opts){
      const r = await fetch(url, opts);
      if(!r.ok){
        let d='';
        try{ d=(await r.json()).detail; }catch(e){ d=await r.text(); }
        throw new Error(d||('HTTP '+r.status));
      }
      return r;
    }

    function switchTab(name){
      document.querySelectorAll('.tabBtn').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tabPane').forEach(p=>p.classList.remove('active'));
      document.getElementById('tab-'+name).classList.add('active');
      document.getElementById('pane-'+name).classList.add('active');
      if(name==='train') { loadTrainList().catch(()=>{}); refreshTrainStatus(); }
    }

    /* -------- 予測タブ -------- */
    async function loadNotifySettings(){
      try{
        const r=await api('/api/notify_settings');
        const j=await r.json();
        document.getElementById('notifyEnabled').checked=!!j.enabled;
        document.getElementById('reminderDays').value=(j.reminder_days??90);
        setNotifyMsg('現在: '+(j.enabled?'ON':'OFF')+' / リマインド '+(j.reminder_days??90)+' 日');
      }catch(e){ setNotifyMsg('通知設定の取得に失敗: '+e.message); }
    }

    async function saveNotifySettings(){
      const enabled=document.getElementById('notifyEnabled').checked;
      const reminder=parseInt(document.getElementById('reminderDays').value||'90',10);
      setNotifyMsg('保存中...');
      try{
        const r=await api('/api/notify_settings',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({enabled,reminder_days:reminder})
        });
        const j=await r.json();
        setNotifyMsg('保存しました: '+(j.enabled?'ON':'OFF')+' / リマインド '+j.reminder_days+' 日');
      }catch(e){ setNotifyMsg('保存失敗: '+e.message); }
    }

    async function runNotify(){
      setNotifyMsg('通知チェック中...');
      try{
        const r=await api('/api/notify_run',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({force:false})
        });
        const j=await r.json();
        if(j&&j.ok){
          setNotifyMsg(j.pending>0?'通知を送信しました（件数: '+j.pending+'）':'通知対象なし');
        }else{
          setNotifyMsg('通知エラー: '+(j.error||'unknown'));
        }
      }catch(e){ setNotifyMsg('通知失敗: '+e.message); }
    }

    async function loadPlot(barcode, announce){
      if(!barcode) return;
      const myToken=++plotReqToken;
      const img=document.getElementById('plot');
      if(img.dataset&&img.dataset.objurl){ try{URL.revokeObjectURL(img.dataset.objurl);}catch(e){} img.dataset.objurl=''; }
      img.src='';
      if(announce) setMsg('プロット生成中.');
      try{
        const r=await api('/api/backtest_plot?barcode='+encodeURIComponent(barcode)+'&_='+Date.now());
        const blob=await r.blob();
        if(myToken!==plotReqToken||selected!==barcode) return;
        const url=URL.createObjectURL(blob);
        if(img.dataset) img.dataset.objurl=url;
        img.src=url;
        if(announce) setMsg('');
      }catch(e){
        if(myToken!==plotReqToken) return;
        if(announce) setMsg('プロット表示失敗: '+e.message+'\n※未学習の可能性があります');
      }
    }

    async function loadParts(barcode, announce){
      if(!barcode) return;
      const myToken=++partsReqToken;
      if(announce){
        document.getElementById('mode').textContent='部品在庫予測: 計算中...';
        document.getElementById('alerts').textContent='';
        document.getElementById('parts').innerHTML='';
      }
      try{
        const r=await api('/api/parts?barcode='+encodeURIComponent(barcode));
        const j=await r.json();
        if(myToken!==partsReqToken||selected!==barcode) return;
        document.getElementById('mode').textContent='モデル: '+(j.mode||'-')+' / 製品在庫: '+(j.product_inventory??'-');
        const alerts=(j.alerts||[]).join('\n');
        document.getElementById('alerts').textContent=alerts?('\n'+alerts):'（アラートなし）';
        const tbody=document.getElementById('parts');
        tbody.innerHTML='';
        (j.parts||[]).forEach(p=>{
          const tr=document.createElement('tr');
          const d6=(p.days_6mo===null||p.days_6mo===undefined)?'予測低下注意':(p.days_6mo.toFixed(1)+'日');
          const d1=(p.days_1mo===null||p.days_1mo===undefined)?'予測低下注意':(p.days_1mo.toFixed(1)+'日');
          tr.innerHTML='<td>'+(p.part_name||'')+'</td><td>'+(p.part_inventory??'')+'</td><td>'+d6+'</td><td>'+d1+'</td>';
          tbody.appendChild(tr);
        });
      }catch(e){
        if(myToken!==partsReqToken) return;
        document.getElementById('mode').textContent='部品在庫予測: 取得失敗';
        document.getElementById('alerts').textContent=(e&&e.message)?e.message:'取得に失敗しました';
        document.getElementById('parts').innerHTML='';
      }
    }

    function selectBarcode(bc){
      selected=bc;
      document.getElementById('sel').textContent=bc;
      document.getElementById('btnPredict').disabled=!bc;
      document.getElementById('btnTrain').disabled=!bc;
      setMsg('');
      document.getElementById('plot').src='';
      document.getElementById('parts').innerHTML='';
      document.getElementById('alerts').textContent='';
      document.getElementById('mode').textContent='';
      loadPlot(bc,true).catch(e=>setMsg('プロット表示失敗: '+e.message));
      loadParts(bc,true).catch(()=>{});
    }

    async function loadBarcodes(){
      const q=document.getElementById('q').value||'';
      setMsg('リスト取得中.');
      const r=await api('/api/barcodes?search='+encodeURIComponent(q));
      const j=await r.json();
      const list=document.getElementById('list');
      list.innerHTML='';
      j.barcodes.forEach(bc=>{
        const div=document.createElement('div');
        div.className='item'+(bc===selected?' sel':'');
        div.innerHTML='<span class="itemLabel">'+bc+'</span>';
        div.onclick=()=>{
          Array.from(list.children).forEach(x=>x.classList.remove('sel'));
          div.classList.add('sel');
          selectBarcode(bc);
        };
        list.appendChild(div);
      });
      setMsg('件数: '+j.barcodes.length);
    }

    async function refreshDb(){
      setMsg('DB再取得中.');
      await api('/api/refresh',{method:'POST'});
      await loadBarcodes();
      setMsg('DB再取得完了');
    }

    async function predictOne(){
      if(!selected) return;
      setMsg('更新中.');
      await Promise.allSettled([loadPlot(selected,false),loadParts(selected,true)]);
      setMsg('更新完了');
    }

    async function trainSelected(){
      if(!selected) return;
      const btn=document.getElementById('btnTrain');
      btn.disabled=true;
      setMsg('学習中: '+selected+' ...');
      try{
        const r=await api('/api/train',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({barcode:selected})
        });
        const j=await r.json();
        setMsg('学習完了: '+selected+' ('+j.mode+')');
        loadPlot(selected,false).catch(()=>{});
      }catch(e){
        setMsg('学習失敗: '+e.message);
      }finally{
        btn.disabled=false;
      }
    }

    /* -------- 学習管理タブ -------- */
    async function loadTrainList(){
      const q=document.getElementById('tq').value||'';
      const r=await api('/api/barcodes?search='+encodeURIComponent(q));
      const j=await r.json();
      const list=document.getElementById('trainList');
      list.innerHTML='';
      j.barcodes.forEach(bc=>{
        const div=document.createElement('div');
        div.className='item';
        div.innerHTML='<span class="itemLabel">'+bc+'</span>'
          +'<button class="sm secondary" onclick="trainOne(event,\''+bc.replace(/'/g,"\\'")+'\')" >学習</button>';
        list.appendChild(div);
      });
    }

    async function trainOne(evt, bc){
      const btn=evt.currentTarget||evt.target;
      btn.disabled=true;
      btn.textContent='学習中';
      try{
        const r=await api('/api/train',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({barcode:bc})
        });
        const j=await r.json();
        btn.textContent='完了';
        btn.style.background='#1B5E20';
      }catch(e){
        btn.textContent='失敗';
        btn.style.background='#B71C1C';
        btn.title=e.message;
      }
    }

    async function startTrainAll(){
      const btn=document.getElementById('btnTrainAll');
      btn.disabled=true;
      setTrainMsg('');
      try{
        const r=await api('/api/train_all',{method:'POST'});
        const j=await r.json();
        if(j.ok&&j.started){
          startTrainPolling();
        }else{
          setTrainMsg('開始できませんでした: '+(j.reason||'unknown'));
          btn.disabled=false;
        }
      }catch(e){
        setTrainMsg('エラー: '+e.message);
        btn.disabled=false;
      }
    }

    function startTrainPolling(){
      if(trainPolling) clearInterval(trainPolling);
      trainPolling=setInterval(refreshTrainStatus, 2000);
    }

    async function refreshTrainStatus(){
      try{
        const r=await api('/api/train_status');
        const j=await r.json();
        applyTrainStatus(j);
      }catch(e){}
    }

    function applyTrainStatus(j){
      const dot=document.getElementById('trainDot');
      const label=document.getElementById('trainStatusLabel');
      const outer=document.getElementById('progOuter');
      const inner=document.getElementById('progInner');
      const progText=document.getElementById('progText');
      const btn=document.getElementById('btnTrainAll');
      const failArea=document.getElementById('failArea');
      const failList=document.getElementById('failList');

      if(j.running){
        dot.className='statusDot running';
        label.textContent='学習中...';
        outer.style.display='';
        const pct=j.total>0?Math.round(j.done/j.total*100):0;
        inner.style.width=pct+'%';
        inner.className='progInner';
        progText.textContent=pct+'%  ('+j.done+'/'+j.total+'件)'+(j.current?' 現在: '+j.current:'');
        btn.disabled=true;
      }else{
        if(trainPolling){ clearInterval(trainPolling); trainPolling=null; }
        btn.disabled=false;
        if(j.finished_at){
          dot.className='statusDot done';
          const fails=(j.failed||[]).length;
          label.textContent='完了 — '+(j.total)+'件学習, 失敗'+fails+'件';
          outer.style.display='';
          inner.style.width='100%';
          inner.className='progInner done';
          progText.textContent='完了: '+j.finished_at;
        }else{
          dot.className='statusDot idle';
          label.textContent='待機中';
          outer.style.display='none';
          progText.textContent='';
        }
      }

      // 失敗一覧
      const fails=j.failed||[];
      if(fails.length>0){
        failArea.style.display='';
        failList.innerHTML=fails.map(f=>'<div>'+f.barcode+': '+f.error+'</div>').join('');
      }else{
        failArea.style.display='none';
      }

      // 月次再学習情報
      document.getElementById('lastRetrainAt').textContent=j.last_retrain_at||'（未実行）';
      document.getElementById('nextRetrainAt').textContent=j.next_retrain_at||'（全学習実行後に設定）';
      const badge=document.getElementById('autoRetrainBadge');
      if(j.auto_retrain_monthly){
        badge.textContent='有効';badge.className='pill green';
        document.getElementById('autoRetrainNote').textContent='最初の全学習実行後、30日ごとに自動再学習します。';
      }else{
        badge.textContent='無効';badge.className='pill';
        document.getElementById('autoRetrainNote').textContent='自動再学習はOFFです（settings.jsonで変更可）。';
      }
    }

    /* -------- 初期化 -------- */
    loadBarcodes().catch(e=>setMsg('初期ロード失敗: '+e.message));
    loadNotifySettings().catch(()=>{});
    refreshTrainStatus().catch(()=>{});
  </script>
</body>
</html>"""
