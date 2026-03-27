# セキュリティ是正ガイド

このドキュメントは、過去のリポジトリに機密情報が混入していた事実と、
対処方法を記録するものです。

---

## 混入していた機密情報（過去のコミット）

以下の種別の情報が `project/` のコード・設定ファイルに直書きされていました:

| 種別 | 場所 | 現状 |
|------|------|------|
| 社内 MySQL ホスト/ポート | `mysql_config.json` | `.gitignore` 追跡除外済み |
| MySQL ユーザー名/パスワード | `mysql_config.json` | 同上 |
| ファイルサーバー UNC パス | `access_handler.py` | `config.py` 経由に変更済み |
| ファイルサーバー UNC パス | `tw_prophet_bridge.py` | 環境変数経由に変更済み |
| 社内 IP アドレス | `tw_prophet_web.py` (HTML) | `config.NAV_LINKS` に移動済み |
| 社内 IP アドレス | `access_vba/Form_未出荷フォーム.cls` | VBA ファイルは追跡対象外推奨 |
| メール送信先 | `email_list.json` | `.gitignore` 追跡除外済み |
| ユーザー固有 Python パス | `start_tw_prophet_web.local.bat` | `.gitignore` 追跡除外済み |
| conda prefix パス | `Prophet_backup.yml` | 追跡除外を推奨 |

---

## 現在の対策（本 PR で実施済み）

1. **`project/config.py` を新設** – すべてのパス/資格情報を集中管理。他のモジュールへのハードコードを排除。
2. **`access_handler.py` を書き換え** – UNC パスを `config.py` 経由に変更。
3. **`tw_prophet_bridge.py` を書き換え** – ハードコードパスを `TW_PROPHET_PATH` 環境変数に変更。
4. **`tw_prophet_web.py` の HTML** – 社内 IP リンクを `config.NAV_LINKS` に外出し。
5. **`.gitignore` を強化** – ランタイム JSON（`email_list.json`, `excluded_products.json`, `notify_settings.json`, `weekly_data_list.json`）および `settings.json` を追跡対象外に追加。
6. **テンプレートファイルを追加** – `.env.example`, `settings.example.json`, `mysql_config.example.json`

---

## 推奨される追加対処

### A. Git 履歴からの機密削除（重要）

現在のリポジトリ履歴に機密情報が残っている可能性があります。
履歴を公開する前に以下のいずれかを実施してください:

```bash
# 方法1: git-filter-repo（推奨）
# https://github.com/newren/git-filter-repo
pip install git-filter-repo

# mysql_config.json を履歴から削除
git filter-repo --path mysql_config.json --invert-paths

# 方法2: BFG Repo Cleaner（簡単）
# https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files mysql_config.json
git reflog expire --expire=now --all && git gc --prune=now --aggressive
```

> ⚠️ 履歴改変は **破壊的操作** です。必ずバックアップを取り、
> チームメンバーに共有してからリモートへ force push してください。

### B. 資格情報のローテーション

Git 履歴に一度でも公開された資格情報は、たとえ削除後も
キャッシュされている可能性があります。以下を実施してください:

- [ ] MySQL の `prophet` ユーザーのパスワードを変更
- [ ] MySQL ユーザー権限を最小限に絞る（SELECT のみなど）
- [ ] VBA フォームで使用している MySQL 接続の資格情報を変更

### C. Prophet_backup.yml の整理

```bash
# 個人パスを含む conda 環境ファイルを追跡対象外に
echo "Prophet_backup.yml" >> .gitignore

# 再現可能な environment.yml を作成
conda env export --from-history > environment.yml
```

### D. access_vba/ の取り扱い

VBA ファイルには MySQL 接続情報が含まれていた可能性があります。
このディレクトリは社内専用リポジトリで管理し、GitHub には公開しないことを推奨します。

---

## 今後のルール

1. **コードへの直書き禁止**: IP, パスワード, UNC パス, メールアドレスをコードに書かない
2. **設定は `config.py` 経由**: `_get()` ヘルパーを使って環境変数 → settings.json → デフォルトの優先順位を維持
3. **新規 JSON 追加時は `.gitignore` を更新**: ランタイム設定は必ず追跡対象外にする
4. **PR 前に `git diff` で確認**: 機密情報が含まれていないかレビューする
