# TW_Prophet (Public Edition)

TW_Prophet の公開版です。  
公開版には、時系列予測・在庫予測・部品枯渇予測ロジックを残し、社内機密（社名、実サーバー、実DB、実メール送信先、実運用データ）は含めていません。

## できること

- 出荷実績から製品ごとの需要予測（`model_handler.py`）
- 在庫と予測消費量を使った残日数算出
- 部品在庫の枯渇アラート算出
- FastAPI の簡易 Web UI で可視化

## 公開版で除外しているもの

- 実DB接続（Access / MySQL）
- 社内メール送信先リスト
- 社内URL / 社内IP / UNCパス
- 社内運用向け JSON / バッチ常駐前提設定

## ディレクトリ構成（主要）

- `public/` : 公開版アプリ実装
- `examples/sample_data/` : サンプル CSV（出荷・在庫・部品）
- `examples/sample_config/` : サンプル設定 JSON
- `model_handler.py` : 予測ロジック本体（再利用）
- `public_main.py` : 公開版起動エントリ

## 前提環境

- Python 3.9 以上
- Anaconda 環境を推奨

## セットアップ

```bash
pip install -r requirements.txt
```

必要に応じて `.env.example` を `.env` にコピーし、データパスなどを変更してください。

## 実行方法

### Web アプリ起動

```bash
python public_main.py
```

または

```bash
python run_web.py
```

ブラウザで `http://localhost:8000` を開きます。

### 全製品学習バッチ

```bash
python daily_train_all.py
```

## 自社データに差し替える箇所

1. `examples/sample_data/shipments.csv`  
   必須列: `shipment_date`, `barcode`, `quantity`（任意: `customer_id`）
2. `examples/sample_data/inventory.csv`  
   必須列: `barcode`, `inventory`
3. `examples/sample_data/parts.csv`  
   必須列: `barcode`, `part_name`, `stock`
4. `examples/sample_config/sample_excluded_products.json`
5. `examples/sample_config/sample_weekly_data_list.json`

環境変数でファイルパスを切り替える場合は `.env.example` の `TW_SAMPLE_*` / `TW_*_JSON` を利用します。

## メール通知について

- 公開版ではデフォルト無効（`TW_ENABLE_EMAIL=0`）。
- SMTP 設定を与えた場合のみ送信します。
- 実送信先リスト（`email_list.json`）は公開物に含めません。

## ライセンス

`LICENSE` は MIT テンプレートです。  
公開前に組織ポリシーに合わせて最終確認してください。

