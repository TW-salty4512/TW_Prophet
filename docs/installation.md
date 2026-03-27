# TW_Prophet 導入手順

新規 Windows PC への導入手順を説明します。

---

## 前提条件

| 項目 | 要件 |
|------|------|
| OS | Windows 10/11 (64bit) |
| Python | 3.9 以上 |
| Access ドライバ | Microsoft Access Database Engine 2016（内部 MDB 接続に必要） |
| ネットワーク | ファイルサーバー UNC パスへのアクセス権 |

---

## 方法 A: インストーラを使う（推奨）

1. `TW_Prophet_Setup_x.x.x.exe` を管理者として実行
2. インストール先を選択（既定: `C:\Program Files\TW_Prophet`）
3. タスクスケジューラ登録オプションにチェック（推奨）
4. 完了後に「セットアップウィザードを起動」を選択
5. ウィザードで以下を設定:
   - 動作モード（internal / sample）
   - MDB ベースディレクトリ（UNC パス）
   - MySQL 接続（必要な場合）
   - Web ポート（既定: 8000）
   - 自動起動の有無

---

## 方法 B: 手動インストール

### 1. ファイル配置

```
適当なディレクトリ（例: C:\Apps\TW_Prophet\）
└── project/ の中身をすべてコピー
```

### 2. Python 仮想環境の作成

```powershell
cd C:\Apps\TW_Prophet
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Microsoft Access Driver のインストール

Access MDB を使う場合（internal モード）:
- [Microsoft Access Database Engine 2016](https://www.microsoft.com/en-us/download/details.aspx?id=54920) をダウンロード
- `AccessDatabaseEngine_X64.exe` を実行

### 4. 設定ファイルの作成

```powershell
# テンプレートをコピー
Copy-Item settings.example.json settings.json

# または %ProgramData%\TW_Prophet\settings.json に作成（推奨）
$settingsDir = "$env:PROGRAMDATA\TW_Prophet"
New-Item -ItemType Directory -Force -Path $settingsDir
Copy-Item settings.example.json "$settingsDir\settings.json"
```

`settings.json` を編集して実際の値を設定します:

```json
{
  "data_mode": "internal",
  "port": 8000,
  "mdb_base_dir": "\\\\File-server\\データベース",
  "data_dir": "C:\\ProgramData\\TW_Prophet\\data",
  "models_dir": "C:\\ProgramData\\TW_Prophet\\data\\models"
}
```

### 5. MySQL 接続設定（必要な場合）

```powershell
$configDir = "$env:PROGRAMDATA\TW_Prophet\data\config"
New-Item -ItemType Directory -Force -Path $configDir
Copy-Item mysql_config.example.json "$configDir\mysql_config.json"
```

`mysql_config.json` を編集:
```json
{
  "host": "192.168.x.x",
  "port": 3306,
  "user": "your_user",
  "password": "your_password",
  "database": "your_database"
}
```

### 6. 動作確認

```powershell
# sample モードで確認
$env:TW_DATA_MODE = "sample"
python run_web.py

# ブラウザで http://localhost:8000 を開く
```

### 7. Windows 自動起動の登録

```powershell
# 管理者権限で実行
.\scripts\register_startup.ps1 -InstallDir "C:\Apps\TW_Prophet" -Port 8000

# 手動で今すぐ起動
Start-ScheduledTask -TaskName "TW_Prophet_Web"
```

---

## 設定の優先順位

1. 環境変数（最高優先）
2. `%ProgramData%\TW_Prophet\settings.json`
3. インストールディレクトリの `settings.json`
4. `config.py` 内のデフォルト値

---

## トラブルシューティング

### Access ドライバが見つからない

```
pyodbc.Error: ('IM002', '[IM002] Data source name not found...')
```

→ Access Database Engine をインストールしてください。
  Office 32bit と Engine 64bit は共存できないため、バージョンを統一してください。

### ポートが使用中

```
OSError: [Errno 10048] error while binding
```

→ `settings.json` の `"port"` を変更するか、
  `netstat -ano | findstr :8000` で使用プロセスを確認してください。

### モデルが見つからない（バックテストエラー）

→ 最初に学習が必要です。`/api/train` でバーコードを指定して学習してください。
  または定期学習バッチ `daily_train_all.py` を実行してください。

### タスクスケジューラのエラー

→ イベントビューアー → Windows ログ → System または
  タスクスケジューラライブラリ → TW_Prophet_Web で確認してください。
