# legacy/ ディレクトリ

廃止予定の Tkinter デスクトップ GUI コンポーネントを格納しています。

| ファイル | 説明 |
|---------|------|
| `app.py` | Tkinter デスクトップ GUI（1228行）。Web UI 移行後は不要。 |
| `ui_frontend.py` | app.py で使うカスタムウィジェット（ParallelogramButton等）。 |

## 廃止方針

- Web アプリケーション（`tw_prophet_web.py` + `api/`）への完全移行後に削除予定
- `setup_wizard.py` が初回設定 UI の役割を引き継ぐ
- 学習の実行は `daily_train_all.py` または Web UI の `/api/train` で行う

## 注意

- `app.py` はファイルサーバーへの接続・モデル学習・可視化を含む
- 移行前に必要な機能を Web UI 側へ移植してから削除すること
