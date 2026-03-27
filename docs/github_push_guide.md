# GitHub プッシュガイド（git 履歴の機密削除を含む）

## 現状

- リモート: `origin = https://github.com/TW-salty4512/TW_Prophet.git`
- 最新コミット: `3c837c6` (refactor: security cleanup...)
- 過去の履歴には **mysql_config.json・email_list.json・UNC パス** が含まれている

---

## STEP 1: 履歴から機密情報を削除する（必須・GitHub 公開前に実行）

### 方法 A: `git-filter-repo` を使う（推奨）

```powershell
# 1. git-filter-repo をインストール
pip install git-filter-repo

# 2. project/ に移動
cd C:\Users\tsalt\Dev\TW_Prophet\project

# 3. 機密ファイルを全履歴から削除
git filter-repo --path mysql_config.json --invert-paths
git filter-repo --path email_list.json --invert-paths
git filter-repo --path excluded_products.json --invert-paths
git filter-repo --path notify_settings.json --invert-paths
git filter-repo --path weekly_data_list.json --invert-paths
git filter-repo --path Prophet_backup.yml --invert-paths

# 4. リモートを再設定（filter-repo は remote を削除するため）
git remote add origin https://github.com/TW-salty4512/TW_Prophet.git
```

### 方法 B: BFG Repo Cleaner を使う

```powershell
# Java が必要
# https://rtyley.github.io/bfg-repo-cleaner/ からダウンロード

java -jar bfg.jar --delete-files "{mysql_config.json,email_list.json,excluded_products.json,notify_settings.json,weekly_data_list.json,Prophet_backup.yml}"

git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 注意事項

- **破壊的操作です**: 実行前に `project/` を別の場所にバックアップしてください
- チームメンバーがいる場合は全員に告知してからリポジトリをリセットしてもらう
- 実行後は古いクローンはすべて無効になります（`git pull` では対応不可）

---

## STEP 2: GitHub にプッシュ（履歴クリーン後）

```powershell
cd C:\Users\tsalt\Dev\TW_Prophet\project

# GitHub でリポジトリが空であることを確認してから:
git push -u origin main
```

### GitHub でリポジトリが空でない場合

```powershell
# 強制プッシュ（履歴を上書きする - リモートに他の人の変更がある場合は注意）
git push --force-with-lease origin main
```

---

## STEP 3: GitHub でのセキュリティ設定

1. **Secret scanning を有効化**: Settings → Code security → Secret scanning → Enable
2. **Branch protection**: Settings → Branches → Add rule → `main`
   - Require pull request reviews before merging
   - Require status checks (テストが通った時のみマージ可)

---

## STEP 4: 資格情報のローテーション（推奨）

履歴に入っていたパスワードは、削除後もキャッシュされている可能性があります:

- [ ] MySQL `prophet` ユーザーのパスワードを変更
- [ ] `mysql_config.json` の新しいパスワードを `%ProgramData%\TW_Prophet\data\config\mysql_config.json` に設定
- [ ] VBA フォームの MySQL 接続文字列も更新

---

## 現在の状態サマリー

```
ブランチ: main
リモート: https://github.com/TW-salty4512/TW_Prophet.git
最新コミット: 3c837c6 (refactor: security cleanup...)
未プッシュコミット数: 16 (git log --oneline で確認)
```

履歴クリーン完了後、`git push -u origin main` でプッシュできます。
