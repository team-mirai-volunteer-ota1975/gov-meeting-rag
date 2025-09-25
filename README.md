# GOV Meeting RAG

政府会議の議事録をベクトル検索で横断的に調べられる FastAPI ベースの RAG (Retrieval Augmented Generation) API と、関連する Docker 開発環境を提供します。`docker-compose up --build` を実行するだけで、アプリケーションと PostgreSQL が起動し、初期データも自動的に復元されます。

## ディレクトリ構成
```
GOV-MEETING-RAG/
├── app/                  # FastAPI アプリ (main.py, Dockerfile, requirements.txt)
├── init/                 # DB 初期化用スクリプト
├── public/               # フロントエンドの静的ファイル
├── docker-compose.yml    # 開発用 Docker Compose 設定
├── .env                  # 環境変数 (ローカル)
├── .env.example          # 環境変数のサンプル
├── requirements.txt      # ルートの Python 依存パッケージ
└── vercel.json           # Vercel デプロイ設定
```

## 必要要件
- Docker と Docker Compose がインストール済みであること
- OpenAI Embedding を使う場合は `OPENAI_API_KEY` を取得しておくこと

## 環境変数の設定
1. `.env.example` を `.env` にコピーします。
2. 以下の値を用途に合わせて更新します。
   - `DATABASE_URL`: アプリが利用する PostgreSQL 接続文字列。
   - `OPENAI_API_KEY`: OpenAI Embedding を使う場合に設定。
   - `LOG_LEVEL`: アプリケーションのログレベル (例: `INFO`).

Docker Compose で起動する場合、`app` サービスには `DATABASE_URL=postgres://myuser:mypass@db:5432/mydb` が自動付与されるため、`.env` 側の設定はテストや本番など別環境向けに利用できます。

## 起動手順 (Docker Compose)
1. 初回または依存関係を更新したい場合はビルド付きで起動します。
   ```bash
   docker-compose up --build
   ```
2. `init/restore.sh` が Google Drive からダンプをダウンロードし、PostgreSQL に初期データを取り込みます。
3. FastAPI アプリが `http://localhost:8000` で待ち受けます。

停止するには `Ctrl + C` を押し、不要なコンテナとボリュームを削除する場合は以下を実行します。
```bash
docker-compose down -v
```

## API エンドポイント
- `GET /healthz`: 接続確認用ヘルスチェック。
- `POST /search`: 質問に関連する議事録のチャンクをスコア付きで返却します。
- `POST /summary_search`: 要約済みチャンクを返却します。

### リクエスト例
```bash
curl -X POST "http://127.0.0.1:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "医療DX", "top_k": 5}'
```

## ローカル開発メモ
- `app/requirements.txt` はルートの `requirements.txt` を参照しているため、依存追加時はルートで `pip install <package> && pip freeze > requirements.txt` のように更新してください。
- `scripts/` ディレクトリのユーティリティは (存在する場合) ベクトル埋め込み計算に利用されます。OpenAI API を利用できない場合はローカル擬似埋め込みにフォールバックします。

## トラブルシューティング
- 初回起動時に DB 復元が失敗した場合は `docker-compose down -v` でボリュームを削除し、再度 `docker-compose up --build` を実行してください。
- `DATABASE_URL` が未設定の場合、API は起動時にエラーを返します。環境変数を確認してください。
- OpenAI API Key が無効な場合、埋め込み計算がローカルの擬似実装にフォールバックするため、検索精度が下がる可能性があります。
