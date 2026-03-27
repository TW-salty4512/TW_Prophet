# マイグレーションノート

## v3.1 → v3.2（本リファクタリング）

### 概要

- `project/` を単一の正本リポジトリとして昇格
- `master/` / `TW_Prophet_public/` の廃止
- 機密情報のコードからの完全排除
- Windows インストーラ / セットアップウィザードの追加

---

### 変更点一覧

#### 新規ファイル

| ファイル | 説明 |
|---------|------|
| `config.py` | 集中設定モジュール |
| `api/service.py` | TWProphetWebService（tw_prophet_web.py から分割） |
| `api/routes.py` | FastAPI ルーター + HTML（tw_prophet_web.py から分割） |
| `model/store.py` | モデル保存/読み込み（model_handler.py から抽出） |
| `setup_wizard.py` | 初回設定 Tkinter ウィザード |
| `scripts/register_startup.ps1` | タスクスケジューラ登録 |
| `scripts/unregister_startup.ps1` | タスクスケジューラ解除 |
| `scripts/start_service.bat` | 手動起動バッチ |
| `installer/tw_prophet.iss` | Inno Setup インストーラ定義 |
| `settings.example.json` | 設定テンプレート |
| `mysql_config.example.json` | MySQL 設定テンプレート |
| `tests/test_config.py` | config.py のユニットテスト |
| `tests/test_sample_mode.py` | sample モード統合テスト |
| `tests/test_model_store.py` | model/store.py のユニットテスト |
| `docs/installation.md` | 導入手順 |
| `docs/security_remediation.md` | セキュリティ是正ガイド |

#### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `access_handler.py` | UNC パスのハードコードを `config.py` 経由に変更。MySQL 特別処理を `mysql_barcodes` 設定で汎用化 |
| `tw_prophet_bridge.py` | `TW_PROPHET_PATH` ハードコードを `TW_PROPHET_PATH` 環境変数に変更 |
| `tw_prophet_web.py` | 1272 行 → 約 30 行のスリムなエントリーポイントに変更（ロジックは `api/` へ移動） |
| `.env.example` | 内部版の全環境変数を網羅した形に更新 |
| `.gitignore` | ランタイム JSON と `settings.json` を追跡対象外に追加 |
| `README.md` | 新構成・導入手順を反映 |

---

### 既存環境からのアップグレード手順

1. `project/` の内容を新しいコードで上書き

2. `settings.json` を作成（既存の環境変数や `.local.bat` の設定値を移行）:
   ```powershell
   Copy-Item settings.example.json "$env:PROGRAMDATA\TW_Prophet\settings.json"
   # 値を編集
   notepad "$env:PROGRAMDATA\TW_Prophet\settings.json"
   ```

3. MySQL 設定を移行（`mysql_config.json` から）:
   ```powershell
   $dest = "$env:PROGRAMDATA\TW_Prophet\data\config"
   New-Item -ItemType Directory -Force -Path $dest
   Copy-Item mysql_config.json "$dest\mysql_config.json"
   ```

4. ランタイム JSON を移行:
   ```powershell
   $dest = "$env:PROGRAMDATA\TW_Prophet\data\config"
   foreach ($f in "excluded_products.json","weekly_data_list.json","notify_settings.json","email_list.json") {
     if (Test-Path $f) { Copy-Item $f "$dest\$f" }
   }
   ```

5. 動作確認:
   ```powershell
   python run_web.py
   # http://localhost:8000 でアクセス確認
   ```

6. 自動起動タスクを再登録（既存タスクがある場合）:
   ```powershell
   .\scripts\unregister_startup.ps1   # 古いタスクを削除
   .\scripts\register_startup.ps1     # 新しいタスクを登録
   ```

---

### 後方互換性について

- `ModelHandler` クラスは `model_handler.py` に引き続き存在します（API 変更なし）
- `AccessHandler` クラスは `access_handler.py` に存在します（コンストラクタ引数変更）
  - **旧**: `AccessHandler(mysql_config={...})` 引数で MySQL 設定を渡していた場合
  - **新**: `config.MYSQL` から自動ロード（`settings.json` または環境変数で設定）
- PHP ブリッジ（`tw_prophet_bridge.py`）は API 変更なし。`TW_PROPHET_PATH` 環境変数の設定が必要

---

### 未完了事項（次のステップ）

- [ ] `model_handler.py` の完全分割（`features.py`, `trainer.py`, `predictor.py`, `evaluator.py`）
  - 現状: `model/__init__.py` と `model/store.py` のみ分割済み
  - 注意: テストを先に充実させてから実施すること
- [ ] `app.py`（Tkinter デスクトップ GUI）の扱い: 廃止または setup_wizard.py に統合
- [ ] Git 履歴からの機密削除（`docs/security_remediation.md` 参照）
- [ ] `Prophet_backup.yml` を再現可能な `environment.yml` に置き換え
- [ ] E2E テストの追加（FastAPI TestClient を使った API テスト）
- [ ] `master/` と `TW_Prophet_public/` ディレクトリの削除またはアーカイブ
