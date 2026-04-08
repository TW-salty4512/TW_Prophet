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

class WeeklyRequest(BaseModel):
    barcode: str
    weekly: bool

class EmailRequest(BaseModel):
    email: str

class SmtpConfigRequest(BaseModel):
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    from_addr: str = ""
    password: str | None = None

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
# 週次/月次設定
# ---------------------------------------------------------------------------

@router.get("/api/weekly")
def weekly() -> dict[str, Any]:
    return {"weekly": sorted(_s().get_weekly_set())}


@router.post("/api/weekly")
def update_weekly(req: WeeklyRequest) -> dict[str, Any]:
    try:
        _s().set_weekly(req.barcode.strip(), req.weekly)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# メールリスト
# ---------------------------------------------------------------------------

@router.get("/api/emails")
def emails() -> dict[str, Any]:
    return {"emails": _s().get_email_list()}


@router.post("/api/emails")
def add_email(req: EmailRequest) -> dict[str, Any]:
    try:
        _s().add_email(req.email.strip())
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/emails")
def remove_email(req: EmailRequest) -> dict[str, Any]:
    try:
        _s().remove_email(req.email.strip())
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# SMTP 設定
# ---------------------------------------------------------------------------

@router.get("/api/smtp_config")
def smtp_config() -> dict[str, Any]:
    try:
        return _s().get_smtp_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/smtp_config")
def save_smtp_config(req: SmtpConfigRequest) -> dict[str, Any]:
    try:
        _s().save_smtp_config(
            smtp_server=req.smtp_server.strip(),
            smtp_port=req.smtp_port,
            username=req.username.strip(),
            from_addr=req.from_addr.strip(),
            password=req.password,
        )
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <style>
    /* ===== DARK (default) ===== */
    :root{
      --bg:#06060E; --card:#0C0C1A; --panel:#08080F;
      --yellow:#FCE300; --cyan:#00E5FF; --magenta:#FF003C; --orange:#FFA000;
      --text:#B8C4D0; --muted:#5A6A7A;
      --border-y:rgba(252,227,0,0.22); --border-c:rgba(0,229,255,0.22);
      --glow-y:rgba(252,227,0,0.12); --glow-c:rgba(0,229,255,0.12);
      --header-bg:#0A0A14; --scanline:rgba(0,0,0,0.04);
      --title-shadow:0 0 16px rgba(252,227,0,0.5),0 0 40px rgba(252,227,0,0.15);
      --input-text:var(--cyan);
    }
    /* ===== LIGHT ===== */
    body.light{
      --bg:#EEF0F5; --card:#FFFFFF; --panel:#F5F6FA;
      --yellow:#B08C00; --cyan:#006E8A; --magenta:#B8002A; --orange:#A06800;
      --text:#2A2E3A; --muted:#6A7080;
      --border-y:rgba(160,130,0,0.22); --border-c:rgba(0,100,140,0.22);
      --glow-y:rgba(160,130,0,0.06); --glow-c:rgba(0,100,140,0.06);
      --header-bg:#FAFAFD; --scanline:transparent;
      --title-shadow:none;
      --input-text:#2A2E3A;
    }
    body.light::after{background:none !important;}
    body.light header{border-bottom-color:rgba(0,0,0,0.08);box-shadow:0 1px 4px rgba(0,0,0,0.06);}
    body.light header>div:first-child{text-shadow:none;}
    body.light .versionBadge{text-shadow:none;}
    body.light .tabBar{background:var(--panel);border-bottom-color:rgba(0,0,0,0.08);}
    body.light .tabBtn{background:var(--panel);}
    body.light .tabBtn.active{background:var(--card);text-shadow:none;border-color:rgba(160,130,0,0.4);}
    body.light .card{box-shadow:0 1px 6px rgba(0,0,0,0.06);border-top-color:rgba(160,130,0,0.3);}
    body.light input{background:var(--panel);color:var(--text);border-color:rgba(0,0,0,0.1);border-left-color:rgba(0,100,140,0.3);}
    body.light input::placeholder{color:#A0A8B0;}
    body.light input:focus{box-shadow:0 0 6px rgba(0,100,140,0.12);}
    body.light button:hover:not(:disabled){text-shadow:none;}
    body.light .item:hover{background:#F0F1F5;}
    body.light .item.sel{background:#F8F4E0;}
    body.light ::-webkit-scrollbar-track{background:var(--panel);}
    body.light ::-webkit-scrollbar-thumb{background:rgba(0,0,0,0.15);}
    body.light .plotFrame{border-color:rgba(0,0,0,0.08);box-shadow:none;}
    html,body{height:100%;}
    body{
      font-family:'Rajdhani','Segoe UI',system-ui,sans-serif;
      margin:0; background:var(--bg); color:var(--text);
      display:flex; flex-direction:column; min-height:100vh;
    }
    /* scanline overlay */
    body::after{
      content:''; pointer-events:none; position:fixed; inset:0; z-index:9999;
      background:repeating-linear-gradient(0deg,transparent,transparent 2px,var(--scanline) 2px,var(--scanline) 4px);
    }
    ::selection{background:rgba(252,227,0,0.3);color:#fff;}
    ::-webkit-scrollbar{width:6px;height:6px;}
    ::-webkit-scrollbar-track{background:var(--bg);}
    ::-webkit-scrollbar-thumb{background:rgba(252,227,0,0.2);border:none;}
    ::-webkit-scrollbar-thumb:hover{background:rgba(252,227,0,0.4);}

    header{
      padding:10px 16px;
      border-bottom:1px solid var(--border-y);
      box-shadow:0 2px 30px var(--glow-y);
      display:flex; gap:10px; align-items:center; flex:0 0 auto;
      background:var(--header-bg);
    }
    header>div:first-child{
      font-size:17px; font-weight:700; color:var(--yellow);
      letter-spacing:.14em; text-transform:uppercase;
      text-shadow:var(--title-shadow);
    }
    .versionBadge{
      padding:2px 14px; border:1px solid var(--yellow);
      background:transparent; color:var(--yellow);
      font-size:11px; font-weight:700; letter-spacing:.1em; white-space:nowrap;
      font-family:'Share Tech Mono',monospace;
      clip-path:polygon(8px 0%,100% 0%,calc(100% - 8px) 100%,0% 100%);
      text-shadow:0 0 8px rgba(252,227,0,0.5);
    }
    .navlinks{display:flex;gap:6px;align-items:center;flex-wrap:wrap;}
    .navlinks a,.navlinks a:visited{
      color:var(--cyan);text-decoration:none;padding:4px 14px;
      border:1px solid var(--border-c); background:transparent;
      font-size:12px;font-weight:700;letter-spacing:.08em;
      clip-path:polygon(8px 0%,100% 0%,calc(100% - 8px) 100%,0% 100%);
      transition:all .15s;
    }
    .navlinks a:hover{color:var(--yellow);background:var(--glow-y);border-color:var(--yellow);}

    /* ---- tabs ---- */
    .tabBar{
      display:flex;gap:2px;padding:8px 12px 0;flex:0 0 auto;
      background:#08080F;border-bottom:1px solid var(--border-y);
    }
    .tabBtn{
      padding:8px 22px;border-radius:0;
      border:1px solid rgba(252,227,0,0.1);border-bottom:none;
      background:var(--card);color:#555;cursor:pointer;
      font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
      clip-path:polygon(10px 0%,100% 0%,100% 100%,0% 100%);
      transition:all .15s; font-family:inherit;
    }
    .tabBtn.active{
      background:#0F0F22;color:var(--yellow);
      border-color:rgba(252,227,0,0.5);
      text-shadow:0 0 12px rgba(252,227,0,0.5);
    }
    .tabBtn:hover:not(.active){color:#999;background:#0E0E1E;}
    .tabPane{display:none;flex:1 1 auto;min-height:0;flex-direction:column;}
    .tabPane.active{display:flex;}

    /* ---- layouts ---- */
    .wrap{
      flex:1 1 auto;min-height:0;display:grid;
      grid-template-columns:300px 1fr 360px;grid-template-rows:1fr;
      gap:10px;padding:10px;box-sizing:border-box;align-items:stretch;
    }
    .trainWrap{
      flex:1 1 auto;min-height:0;display:grid;
      grid-template-columns:300px 1fr;grid-template-rows:1fr;
      gap:10px;padding:10px;box-sizing:border-box;align-items:stretch;
    }

    /* ---- card ---- */
    .card{
      background:var(--card);
      border:1px solid var(--border-y);
      border-top:2px solid rgba(252,227,0,0.45);
      border-radius:0; padding:12px;
      display:flex;flex-direction:column;min-height:0;box-sizing:border-box;
      box-shadow:0 0 20px var(--glow-y),inset 0 1px 0 rgba(252,227,0,0.06);
    }

    /* ---- inputs ---- */
    input,button{font-size:13px;font-family:inherit;}
    input{
      width:100%;padding:8px 10px;border-radius:0;
      border:1px solid var(--border-c);
      border-left:2px solid rgba(0,229,255,0.45);
      background:var(--panel);color:var(--input-text,var(--cyan));box-sizing:border-box;
      letter-spacing:.04em;font-family:'Share Tech Mono',monospace;
    }
    input:focus{outline:none;border-color:var(--cyan);box-shadow:0 0 10px var(--glow-c);}
    input::placeholder{color:#3A4A5A;}
    input[type="number"]{width:110px;}
    input[type="checkbox"]{width:auto;}

    /* ---- buttons ---- */
    button{
      padding:9px 16px;border-radius:0;
      border:1px solid rgba(252,227,0,0.35);
      background:rgba(252,227,0,0.06);color:var(--yellow);cursor:pointer;
      font-weight:700;letter-spacing:.1em;text-transform:uppercase;
      clip-path:polygon(8px 0%,100% 0%,calc(100% - 8px) 100%,0% 100%);
      transition:all .15s;font-family:inherit;
    }
    button:hover:not(:disabled){
      background:rgba(252,227,0,0.16);
      box-shadow:0 0 16px rgba(252,227,0,0.25);
      text-shadow:0 0 8px rgba(252,227,0,0.5);
    }
    button.secondary{
      background:rgba(0,229,255,0.06);color:var(--cyan);
      border-color:rgba(0,229,255,0.35);
    }
    button.secondary:hover:not(:disabled){
      background:rgba(0,229,255,0.16);
      box-shadow:0 0 16px rgba(0,229,255,0.25);
      text-shadow:0 0 8px rgba(0,229,255,0.5);
    }
    button.danger{
      background:rgba(255,0,60,0.08);color:var(--magenta);
      border-color:rgba(255,0,60,0.4);
    }
    button.danger:hover:not(:disabled){
      background:rgba(255,0,60,0.18);
      box-shadow:0 0 16px rgba(255,0,60,0.3);
    }
    button.warn{background:rgba(255,160,0,0.08);color:var(--orange);border-color:rgba(255,160,0,0.35);}
    button.warn:hover:not(:disabled){background:rgba(255,160,0,0.18);}
    button:disabled{opacity:.25;cursor:not-allowed;}
    button.sm{padding:4px 10px;font-size:11px;clip-path:none;}

    /* ---- list ---- */
    .list{
      flex:1 1 auto;min-height:0;overflow:auto;
      border:1px solid var(--border-c);background:var(--panel);
    }
    .item{
      padding:9px 12px;border-bottom:1px solid rgba(255,255,255,0.02);
      cursor:pointer;display:flex;align-items:center;gap:8px;
      border-left:2px solid transparent;transition:all .1s;
      font-family:'Share Tech Mono',monospace;font-size:13px;
    }
    .item:hover{background:#0E0E1C;border-left-color:rgba(0,229,255,0.4);}
    .item.sel{background:#0F0F20;border-left-color:var(--yellow);color:var(--yellow);}
    .itemLabel{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

    /* ---- misc ---- */
    .muted{color:var(--muted);}
    .pill{
      display:inline-block;padding:2px 12px;
      border:1px solid rgba(252,227,0,0.35);
      background:transparent;color:var(--yellow);
      font-size:11px;font-weight:700;letter-spacing:.08em;
      font-family:'Share Tech Mono',monospace;
      clip-path:polygon(6px 0%,100% 0%,calc(100% - 6px) 100%,0% 100%);
    }
    .pill.green{border-color:rgba(0,229,255,0.4);color:var(--cyan);}
    .pill.orange{border-color:rgba(255,160,0,0.4);color:var(--orange);}
    img{background:var(--bg);display:block;}
    .plotFrame{
      flex:1 1 auto;min-height:0;display:flex;align-items:stretch;
      border:1px solid var(--border-y);
      box-shadow:inset 0 0 30px rgba(0,0,0,0.6);
    }
    #plot{width:100%;height:100%;object-fit:contain;display:block;}
    #msg{margin-top:8px;white-space:pre-wrap;max-height:120px;overflow:auto;font-size:12px;color:var(--muted);}
    .rightScroll{flex:1 1 auto;min-height:0;overflow:auto;}
    table{width:100%;border-collapse:collapse;font-size:12px;letter-spacing:.04em;}
    th{
      color:var(--yellow);font-weight:700;text-transform:uppercase;
      letter-spacing:.1em;font-size:10px;padding:8px 6px;
      border-bottom:1px solid rgba(252,227,0,0.25);text-align:left;
    }
    td{border-bottom:1px solid rgba(255,255,255,0.03);padding:7px 6px;text-align:left;}
    tr:hover td{background:rgba(252,227,0,0.02);}
    .inline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}

    /* ---- progress ---- */
    .progOuter{
      background:var(--panel);height:6px;overflow:hidden;
      border:none;border-bottom:1px solid var(--border-y);margin:8px 0;
    }
    .progInner{
      height:100%;background:var(--yellow);transition:width .4s ease;
      min-width:2px;box-shadow:0 0 10px rgba(252,227,0,0.7);
    }
    .progInner.done{background:var(--cyan);box-shadow:0 0 10px rgba(0,229,255,0.7);}
    .statusDot{
      display:inline-block;width:8px;height:8px;
      background:#2A2A3A;margin-right:6px;vertical-align:middle;
    }
    .statusDot.running{background:var(--yellow);animation:pulse 1s infinite;box-shadow:0 0 8px rgba(252,227,0,0.8);}
    .statusDot.done{background:var(--cyan);box-shadow:0 0 6px rgba(0,229,255,0.6);}
    .statusDot.idle{background:#2A2A3A;}
    @keyframes pulse{0%,100%{opacity:1;}50%{opacity:.25;}}
    .failList{
      background:var(--panel);padding:8px;
      font-size:12px;max-height:120px;overflow:auto;
      border:1px solid rgba(255,0,60,0.25);color:#FF5070;
    }
    .infoRow{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;}
    .infoItem{display:flex;flex-direction:column;gap:2px;}
    .infoLabel{color:var(--yellow);font-size:10px;text-transform:uppercase;letter-spacing:.12em;opacity:.7;}

    /* ---- details/summary cyberpunk ---- */
    details summary{color:var(--cyan);font-weight:700;}
    code{background:#12122A;padding:1px 6px;border:1px solid var(--border-c);color:var(--cyan);font-family:'Share Tech Mono',monospace;font-size:12px;}
    a{color:var(--cyan);}a:visited{color:var(--cyan);}a:hover{color:var(--yellow);}
  </style>
</head>
<body>
  <header>
    <div>TW_PROPHET</div>
    <div class="muted" style="font-family:'Share Tech Mono',monospace;font-size:11px;letter-spacing:.15em;">// DEMAND FORECAST SYSTEM</div>
    <div class="versionBadge">Ver 4.0.1</div>
    <div class="navlinks">
<!-- NAV_LINKS -->
    </div>
    <div style="margin-left:auto;display:flex;gap:8px;align-items:center;">
      <button class="secondary" onclick="refreshDb()">DB再取得</button>
      <button class="danger" onclick="runNotify()">通知チェック</button>
      <button id="themeToggle" class="sm" onclick="toggleTheme()" style="font-size:16px;padding:4px 10px;clip-path:none;border-color:var(--border-y);letter-spacing:0;">&#9789;</button>
    </div>
  </header>

  <!-- タブバー -->
  <div class="tabBar">
    <button class="tabBtn active" id="tab-predict" onclick="switchTab('predict')">予測</button>
    <button class="tabBtn"        id="tab-train"   onclick="switchTab('train')">学習管理</button>
    <button class="tabBtn"        id="tab-manage"  onclick="switchTab('manage')">製品管理</button>
    <button class="tabBtn"        id="tab-email"   onclick="switchTab('email')">メール管理</button>
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
        <div style="padding:10px;border:1px solid rgba(255,255,255,0.06);border-radius:0;background:var(--panel,#08080F);border:1px solid var(--border-y,rgba(252,227,0,0.15));">
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

  <!-- 製品管理タブ -->
  <div class="tabPane" id="pane-manage">
    <div style="flex:1 1 auto;min-height:0;display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px;box-sizing:border-box;align-items:stretch;">

      <!-- 除外管理 -->
      <section class="card">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
          <span style="font-weight:600;">表示・学習から除外する製品</span>
          <span id="excludedCount" class="pill" style="margin-left:auto;">0件</span>
        </div>
        <div class="muted" style="font-size:12px;margin-bottom:8px;">除外すると製品リストから非表示になり、学習対象からも外れます。</div>
        <div style="display:flex;gap:8px;margin-bottom:8px;">
          <input id="excludeSearch" placeholder="バーコードを検索" style="flex:1;" oninput="renderManageList()" />
        </div>
        <div id="manageList" class="list" style="flex:1 1 auto;"></div>
      </section>

      <!-- 週次/月次管理 -->
      <section class="card">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
          <span style="font-weight:600;">週次モデルで学習する製品</span>
          <span id="weeklyCount" class="pill green" style="margin-left:auto;">0件</span>
        </div>
        <div class="muted" style="font-size:12px;margin-bottom:8px;">チェックあり → 週次モデル（W-SUN）。チェックなし → 月次モデル（M）。</div>
        <div style="display:flex;gap:8px;margin-bottom:8px;">
          <input id="weeklySearch" placeholder="バーコードを検索" style="flex:1;" oninput="renderWeeklyList()" />
        </div>
        <div id="weeklyList" class="list" style="flex:1 1 auto;"></div>
      </section>
    </div>
  </div>

  <!-- メール管理タブ -->
  <div class="tabPane" id="pane-email">
    <div style="flex:1 1 auto;min-height:0;display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px;box-sizing:border-box;align-items:start;">

      <!-- 送信先リスト -->
      <section class="card">
        <div style="font-weight:600;margin-bottom:12px;">通知メール送信先リスト</div>
        <div class="muted" style="font-size:12px;margin-bottom:12px;">このリストに登録したアドレスに在庫減少通知メールが送信されます。</div>
        <div style="display:flex;gap:8px;margin-bottom:12px;">
          <input id="newEmail" placeholder="追加するメールアドレス" style="flex:1;" onkeydown="if(event.key==='Enter') addEmail()" />
          <button class="secondary" onclick="addEmail()">追加</button>
        </div>
        <div id="emailList" class="list" style="min-height:120px;"></div>
        <div id="emailMsg" class="muted" style="margin-top:8px;font-size:13px;"></div>
      </section>

      <!-- SMTP 設定 -->
      <section class="card">
        <div style="font-weight:600;margin-bottom:4px;">送信元メール設定（SMTP）</div>
        <div class="muted" style="font-size:12px;margin-bottom:14px;">メールの送信元アカウントを設定します。</div>

        <!-- Gmail案内 -->
        <details style="margin-bottom:14px;">
          <summary style="cursor:pointer;color:var(--cyan);font-size:13px;font-weight:600;">
            Gmail を使う場合 — アプリパスワードの取得手順
          </summary>
          <div style="margin-top:10px;padding:12px;background:var(--panel);border-radius:0;font-size:12px;line-height:1.8;color:var(--text);border:1px solid var(--border-c);">
            <b>前提:</b> Google アカウントで 2段階認証が有効になっていること<br>
            <br>
            <b>手順:</b><br>
            1. <a href="https://myaccount.google.com/security" target="_blank" rel="noopener">myaccount.google.com/security</a> を開く<br>
            2. 「2段階認証プロセス」をクリック<br>
            3. 下にスクロールして「アプリパスワード」をクリック<br>
            4. アプリ名に「TW_Prophet」など任意の名前を入力して「作成」<br>
            5. 表示された <b>16文字のパスワード</b>（スペース不要）を下の「パスワード」欄に貼り付ける<br>
            <br>
            <b>設定値:</b><br>
            SMTPサーバー: <code style="background:#2a2a3e;padding:1px 5px;border-radius:4px;">smtp.gmail.com</code><br>
            ポート: <code style="background:#2a2a3e;padding:1px 5px;border-radius:4px;">587</code><br>
            ユーザー名: <code style="background:#2a2a3e;padding:1px 5px;border-radius:4px;">your.address@gmail.com</code>
          </div>
        </details>

        <div style="display:flex;flex-direction:column;gap:10px;">
          <div>
            <div class="infoLabel" style="margin-bottom:4px;">SMTPサーバー</div>
            <input id="smtpServer" value="smtp.gmail.com" />
          </div>
          <div>
            <div class="infoLabel" style="margin-bottom:4px;">ポート</div>
            <input id="smtpPort" type="number" value="587" style="width:110px;" />
          </div>
          <div>
            <div class="infoLabel" style="margin-bottom:4px;">ユーザー名（メールアドレス）</div>
            <input id="smtpUser" placeholder="your.address@gmail.com" />
          </div>
          <div>
            <div class="infoLabel" style="margin-bottom:4px;">送信元表示アドレス（空欄=ユーザー名と同じ）</div>
            <input id="smtpFrom" placeholder="省略可" />
          </div>
          <div>
            <div class="infoLabel" style="margin-bottom:4px;">パスワード / アプリパスワード</div>
            <div style="display:flex;gap:8px;">
              <input id="smtpPass" type="password" placeholder="変更しない場合は空欄のまま" style="flex:1;" />
              <button class="sm secondary" onclick="togglePassVis()" id="btnPassVis">表示</button>
            </div>
            <div id="smtpPassStatus" class="muted" style="font-size:12px;margin-top:4px;"></div>
          </div>
          <div style="display:flex;gap:8px;margin-top:4px;">
            <button class="secondary" onclick="saveSmtpConfig()">保存</button>
            <button onclick="testSmtp()">テスト送信</button>
          </div>
        </div>
        <div id="smtpMsg" class="muted" style="margin-top:10px;font-size:13px;white-space:pre-wrap;"></div>
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
        <div style="margin-top:16px;padding:12px;border:1px solid rgba(255,255,255,0.07);border-radius:0;background:var(--panel,#08080F);border:1px solid var(--border-y,rgba(252,227,0,0.15));">
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

    /* ---- theme toggle ---- */
    function applyTheme(theme){
      document.body.classList.toggle('light', theme==='light');
      const btn=document.getElementById('themeToggle');
      if(btn) btn.innerHTML = theme==='light' ? '&#9728;' : '&#9789;';
      localStorage.setItem('tw_theme', theme);
    }
    function toggleTheme(){
      const cur = document.body.classList.contains('light') ? 'light' : 'dark';
      applyTheme(cur==='light' ? 'dark' : 'light');
    }
    (function(){
      const saved = localStorage.getItem('tw_theme');
      if(saved) applyTheme(saved);
    })();

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
      if(name==='train')  { loadTrainList().catch(()=>{}); refreshTrainStatus(); }
      if(name==='manage') { loadManageData().catch(()=>{}); }
      if(name==='email')  { loadEmails().catch(()=>{}); }
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

    /* -------- 製品管理タブ -------- */
    let _allBarcodes = [];   // 全バーコード（除外含む）
    let _excludedSet = new Set();
    let _weeklySet   = new Set();

    async function loadManageData(){
      // 全バーコード（除外済みも含む）、除外リスト、週次リストを同時取得
      const [rAll, rExc, rWkl] = await Promise.all([
        api('/api/barcodes?search=&include_excluded=1').catch(()=>api('/api/barcodes?search=')),
        api('/api/excluded'),
        api('/api/weekly'),
      ]);
      const jAll = await rAll.json();
      const jExc = await rExc.json();
      const jWkl = await rWkl.json();

      // 除外済み + アクティブ をマージして全バーコードリストを作る
      const active = new Set(jAll.barcodes || []);
      _excludedSet = new Set(jExc.excluded || []);
      _weeklySet   = new Set(jWkl.weekly   || []);
      _allBarcodes = Array.from(new Set([...active, ..._excludedSet])).sort();

      document.getElementById('excludedCount').textContent = _excludedSet.size + '件';
      document.getElementById('weeklyCount').textContent   = _weeklySet.size   + '件';
      renderManageList();
      renderWeeklyList();
    }

    function renderManageList(){
      const q = (document.getElementById('excludeSearch').value || '').toLowerCase();
      const list = document.getElementById('manageList');
      list.innerHTML = '';
      const items = _allBarcodes.filter(bc => !q || bc.toLowerCase().includes(q));
      items.forEach(bc => {
        const isExc = _excludedSet.has(bc);
        const div = document.createElement('div');
        div.className = 'item';
        div.style.opacity = isExc ? '0.5' : '1';
        div.innerHTML =
          '<span class="itemLabel" title="'+bc+'">' + bc + '</span>' +
          '<button class="sm ' + (isExc ? 'secondary' : 'danger') + '" ' +
            'onclick="toggleExclude(event,\''+bc.replace(/'/g,"\\'")+'\')">' +
            (isExc ? '解除' : '除外') + '</button>';
        list.appendChild(div);
      });
      if(!items.length) list.innerHTML = '<div style="padding:12px;color:#888;">該当なし</div>';
    }

    async function toggleExclude(evt, bc){
      const btn = evt.currentTarget || evt.target;
      btn.disabled = true;
      const nowExcluded = _excludedSet.has(bc);
      try{
        await api('/api/excluded',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({barcode: bc, excluded: !nowExcluded})
        });
        if(nowExcluded) _excludedSet.delete(bc);
        else            _excludedSet.add(bc);
        document.getElementById('excludedCount').textContent = _excludedSet.size + '件';
        renderManageList();
      }catch(e){
        alert('失敗: ' + e.message);
        btn.disabled = false;
      }
    }

    function renderWeeklyList(){
      const q = (document.getElementById('weeklySearch').value || '').toLowerCase();
      const list = document.getElementById('weeklyList');
      list.innerHTML = '';
      // アクティブなバーコード（除外除く）のみ表示
      const active = _allBarcodes.filter(bc => !_excludedSet.has(bc));
      const items  = active.filter(bc => !q || bc.toLowerCase().includes(q));
      items.forEach(bc => {
        const isWeekly = _weeklySet.has(bc);
        const div = document.createElement('div');
        div.className = 'item';
        const badge = isWeekly
          ? '<span class="pill green" style="font-size:11px;">週次</span>'
          : '<span class="pill"       style="font-size:11px;">月次</span>';
        div.innerHTML =
          badge +
          '<span class="itemLabel" title="'+bc+'" style="margin-left:6px;">'+bc+'</span>' +
          '<button class="sm secondary" onclick="toggleWeekly(event,\''+bc.replace(/'/g,"\\'")+'\')">' +
            (isWeekly ? '→月次に変更' : '→週次に変更') + '</button>';
        list.appendChild(div);
      });
      if(!items.length) list.innerHTML = '<div style="padding:12px;color:#888;">該当なし</div>';
    }

    async function toggleWeekly(evt, bc){
      const btn = evt.currentTarget || evt.target;
      btn.disabled = true;
      const nowWeekly = _weeklySet.has(bc);
      try{
        await api('/api/weekly',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({barcode: bc, weekly: !nowWeekly})
        });
        if(nowWeekly) _weeklySet.delete(bc);
        else          _weeklySet.add(bc);
        document.getElementById('weeklyCount').textContent = _weeklySet.size + '件';
        renderWeeklyList();
      }catch(e){
        alert('失敗: ' + e.message);
        btn.disabled = false;
      }
    }

    /* -------- メール管理タブ -------- */
    function setEmailMsg(t){ document.getElementById('emailMsg').textContent = t || ''; }

    async function loadEmails(){
      try{
        const r = await api('/api/emails');
        const j = await r.json();
        renderEmailList(j.emails || []);
      }catch(e){ setEmailMsg('取得失敗: ' + e.message); }
      loadSmtpConfig().catch(()=>{});
    }

    function renderEmailList(emails){
      const list = document.getElementById('emailList');
      list.innerHTML = '';
      if(!emails.length){
        list.innerHTML = '<div style="padding:12px;color:#888;">登録なし</div>';
        return;
      }
      emails.forEach(em => {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML =
          '<span class="itemLabel">'+em+'</span>' +
          '<button class="sm danger" onclick="removeEmail(event,\''+em.replace(/'/g,"\\'")+'\')">' +
          '削除</button>';
        list.appendChild(div);
      });
    }

    async function addEmail(){
      const input = document.getElementById('newEmail');
      const email = input.value.trim();
      if(!email){ setEmailMsg('メールアドレスを入力してください'); return; }
      setEmailMsg('追加中...');
      try{
        await api('/api/emails',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({email})
        });
        input.value = '';
        await loadEmails();
        setEmailMsg('追加しました: ' + email);
      }catch(e){ setEmailMsg('追加失敗: ' + e.message); }
    }

    async function removeEmail(evt, email){
      const btn = evt.currentTarget || evt.target;
      btn.disabled = true;
      setEmailMsg('削除中...');
      try{
        await api('/api/emails',{
          method:'DELETE', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({email})
        });
        await loadEmails();
        setEmailMsg('削除しました: ' + email);
      }catch(e){
        setEmailMsg('削除失敗: ' + e.message);
        btn.disabled = false;
      }
    }

    /* -------- SMTP設定 -------- */
    function setSmtpMsg(t){ document.getElementById('smtpMsg').textContent = t||''; }

    async function loadSmtpConfig(){
      try{
        const r = await api('/api/smtp_config');
        const j = await r.json();
        document.getElementById('smtpServer').value = j.smtp_server || 'smtp.gmail.com';
        document.getElementById('smtpPort').value   = j.smtp_port   || 587;
        document.getElementById('smtpUser').value   = j.username    || '';
        document.getElementById('smtpFrom').value   = j.from_addr   || '';
        document.getElementById('smtpPass').value   = '';
        document.getElementById('smtpPassStatus').textContent =
          j.password_set ? '✓ パスワード設定済み（変更する場合のみ入力）' : '未設定';
      }catch(e){ setSmtpMsg('SMTP設定の取得失敗: '+e.message); }
    }

    function togglePassVis(){
      const inp = document.getElementById('smtpPass');
      const btn = document.getElementById('btnPassVis');
      if(inp.type==='password'){ inp.type='text';  btn.textContent='隠す'; }
      else                     { inp.type='password'; btn.textContent='表示'; }
    }

    async function saveSmtpConfig(){
      setSmtpMsg('保存中...');
      const body = {
        smtp_server: document.getElementById('smtpServer').value.trim(),
        smtp_port:   parseInt(document.getElementById('smtpPort').value||'587',10),
        username:    document.getElementById('smtpUser').value.trim(),
        from_addr:   document.getElementById('smtpFrom').value.trim(),
        password:    document.getElementById('smtpPass').value || null,
      };
      try{
        await api('/api/smtp_config',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify(body)
        });
        setSmtpMsg('保存しました。');
        await loadSmtpConfig();
      }catch(e){ setSmtpMsg('保存失敗: '+e.message); }
    }

    async function testSmtp(){
      setSmtpMsg('テスト送信中...');
      try{
        const r = await api('/api/notify_run',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({force:true})
        });
        const j = await r.json();
        if(j.ok){
          setSmtpMsg('テスト送信が完了しました（通知対象がない場合はメールは届きません）。\n送信先: 送信先リストに登録されたアドレス');
        }else{
          setSmtpMsg('送信失敗: '+(j.error||'unknown'));
        }
      }catch(e){ setSmtpMsg('送信失敗: '+e.message); }
    }

    /* -------- 初期化 -------- */
    loadBarcodes().catch(e=>setMsg('初期ロード失敗: '+e.message));
    loadNotifySettings().catch(()=>{});
    refreshTrainStatus().catch(()=>{});
  </script>
</body>
</html>"""
