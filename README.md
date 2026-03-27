# TW_Prophet

AI 需要予測 & 部品在庫アラート Web サービス。

XGBoost ベースの時系列予測で製品の月次/週次需要を予測し、
部品在庫の枯渇タイミングをブラウザから確認できます。

---

## 目次

1. [機能概要](#機能概要)
2. [ディレクトリ構成](#ディレクトリ構成)
3. [動作モード](#動作モード)
4. [クイックスタート（サンプルモード）](#クイックスタート)
5. [社内導入（internal モード）](#社内導入)
6. [設定リファレンス](#設定リファレンス)
7. [Windows 自動起動](#windows-自動起動)
8. [インストーラビルド](#インストーラビルド)
9. [テスト実行](#テスト実行)
10. [開発・貢献](#開発貢献)

---

## 機能概要

- 出荷実績から製品ごとの月次/週次需要予測（XGBoost）
- 在庫残日数 / 残月数のリアルタイム計算
- 部品在庫枯渇アラート（メール通知）
- FastAPI + シングルページ Web UI
- Access MDB / MySQL / サンプル CSV を切り替え可能

---

## ディレクトリ構成

```
project/
├── config.py                  # 集中設定（全パス/資格情報はここ経由）
├── tw_prophet_web.py          # Web エントリーポイント
├── model_handler.py           # 予測ロジック（XGBoost）
├── access_handler.py          # MDB/MySQL データ取得（internal モード）
├── email_notifier.py          # メール通知
├── tw_prophet_bridge.py       # PHP ブリッジ
├── setup_wizard.py            # 初回設定ウィザード（Tkinter）
├── run_web.py                 # uvicorn 起動スクリプト
│
├── api/
│   ├── service.py             # TWProphetWebService（サービス層）
│   └── routes.py              # FastAPI ルーター + HTML
│
├── model/
│   ├── __init__.py
│   └── store.py               # モデル保存/読み込み
│
├── public/                    # sample モード / 公開版
│   ├── config.py
│   ├── access_handler.py      # CSV ベースハンドラ
│   └── tw_prophet_web.py      # 公開版 Web
│
├── examples/
│   ├── sample_data/           # サンプル CSV
│   └── sample_config/         # サンプル設定 JSON
│
├── scripts/
│   ├── register_startup.ps1   # タスクスケジューラ登録
│   ├── unregister_startup.ps1 # タスクスケジューラ解除
│   └── start_service.bat      # 手動起動バッチ
│
├── installer/
│   └── tw_prophet.iss         # Inno Setup インストーラ定義
│
├── tests/                     # pytest テスト
├── docs/                      # 運用ドキュメント
│
├── settings.example.json      # 設定テンプレート
├── .env.example               # 環境変数テンプレート
└── mysql_config.example.json  # MySQL 設定テンプレート
```

---

## 動作モード

| モード | データソース | 用途 |
|--------|-------------|------|
| `internal` | Access MDB + MySQL | 社内本番運用 |
| `sample` | examples/sample_data/ の CSV | デモ・開発・公開 |

`TW_DATA_MODE=sample` または `settings.json` の `"data_mode": "sample"` で切替。

---

## クイックスタート

サンプル CSV を使ったデモ起動:

```bash
# 1. 依存パッケージをインストール
pip install -r requirements.txt

# 2. sample モードで起動
TW_DATA_MODE=sample python tw_prophet_web.py

# 3. ブラウザで開く
# http://localhost:8000
```

---

## 社内導入

詳細は [docs/installation.md](docs/installation.md) を参照してください。

### 最小手順

```powershell
# 1. 仮想環境を作成
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. セットアップウィザードで設定
python setup_wizard.py

# 3. 起動確認
python run_web.py
```

設定は `%ProgramData%\TW_Prophet\settings.json` に保存されます。

---

## 設定リファレンス

主要な環境変数（`.env.example` 参照）:

| 変数 | 既定値 | 説明 |
|------|--------|------|
| `TW_DATA_MODE` | `internal` | `internal` / `sample` |
| `PORT` | `8000` | Web サーバーポート |
| `TW_MDB_BASE_DIR` | `\\File-server\データベース` | MDB の UNC ベースパス |
| `MYSQL_HOST` | `127.0.0.1` | MySQL ホスト |
| `MYSQL_DATABASE` | `` | MySQL データベース名 |
| `TW_PROPHET_ALLOW_WEB_TRAIN` | `0` | Web から学習を許可 |
| `TW_PROPHET_NOTIFY_AUTO` | `1` | 部品在庫自動通知 |

ナビリンクは `settings.json` の `nav_links` で設定:
```json
{
  "nav_links": [
    {"label": "製造管理", "url": "http://intranet/mfg/"},
    {"label": "出荷明細", "url": "http://intranet/shipments/"}
  ]
}
```

---

## Windows 自動起動

```powershell
# 管理者権限で実行
.\scripts\register_startup.ps1 -Port 8000

# 解除
.\scripts\unregister_startup.ps1
```

タスクスケジューラ（SYSTEM アカウント）で `At Startup` に登録します。
ログイン不要で PC 起動時に自動起動します。

---

## インストーラビルド

[Inno Setup 6](https://jrsoftware.org/isinfo.php) をインストール後:

1. `installer/tw_prophet.iss` を Inno Setup で開く
2. \[Build\] → \[Compile\]
3. `installer/Output/TW_Prophet_Setup_x.x.x.exe` が生成される

インストーラが行うこと:
- ファイルのコピー
- `%ProgramData%\TW_Prophet\` ディレクトリの作成
- `settings.example.json` から `settings.json` を自動生成
- タスクスケジューラへの自動起動登録（オプション）
- セットアップウィザードの起動（オプション）

---

## テスト実行

```bash
cd project
pip install pytest
pytest tests/ -v
```

サンプルモードのみテスト:
```bash
TW_DATA_MODE=sample pytest tests/test_sample_mode.py -v
```

---

## 開発・貢献

- `project/` が単一の正本です
- `master/` および `TW_Prophet_public/` は廃止予定です
- 機密情報（IP, パスワード, UNCパス）のコードへのハードコードは禁止です
- すべての設定は `config.py` 経由で解決してください

### セキュリティに関する注意

過去のコミット履歴に機密情報が含まれている可能性があります。
詳細は [docs/security_remediation.md](docs/security_remediation.md) を参照してください。
