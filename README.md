# Bedrock RAG Chat

Amazon Bedrock Knowledge Bases を活用した RAG チャットアプリケーション。
S3 に格納したドキュメントを自然言語で検索・質問し、関連情報を基に回答を生成する。

---

## アーキテクチャ

構成図に差し替え予定。

```
Streamlit (Chat UI)
    │ HTTPS
    ▼
API Gateway (REST)
    │
    ▼
Lambda (Python 3.12)
    │ RetrieveAndGenerate API
    ▼
Bedrock Knowledge Bases
    ├── Embedding: Titan Text Embeddings V2
    ├── Vector Store: OpenSearch Serverless
    ├── 生成モデル: Claude Sonnet 4
    └── データソース: S3
```

### データフロー

1. Streamlit UI からチャットメッセージを送信
2. API Gateway → Lambda → Bedrock Knowledge Bases `RetrieveAndGenerate` API
3. クエリをベクトル化 → OpenSearch で類似検索 → Claude で回答生成
4. ソース情報付きでレスポンスを返却・表示

---

## 機能要件

- **チャット**: 自然言語で質問を入力し、ドキュメントに基づいた回答を得る
- **ソース表示**: 回答の根拠となったドキュメント（チャンク）を表示する
- **会話履歴**: セッション内の会話コンテキストを保持する

## 非機能要件

- 認証: なし（ローカル利用前提、将来的に Cognito 追加可能）
- レスポンス: 10秒以内の応答を目標
- コスト: 学習用途のため最小構成

---

## 技術スタック

| レイヤー         | 技術                            | 選定理由                                         |
| ---------------- | ------------------------------- | ------------------------------------------------ |
| フロントエンド   | Streamlit                       | Python のみで UI 構築可能。プロトタイプに最適    |
| API              | API Gateway (REST)              | Lambda との統合が容易                            |
| バックエンド     | Lambda (Python 3.12)            | サーバーレスでコスト最小化                       |
| RAG              | Bedrock Knowledge Bases         | チャンク分割・埋め込み・検索・生成を一括管理     |
| 埋め込みモデル   | Amazon Titan Text Embeddings V2 | Knowledge Bases とネイティブ統合                 |
| 生成モデル       | Claude Sonnet 4 (Bedrock)       | 高品質な日本語応答。コストと性能のバランスが良い |
| ベクトルストア   | OpenSearch Serverless           | Knowledge Bases 対応。サーバーレスで運用負荷なし |
| ドキュメント格納 | S3                              | Knowledge Bases のデータソースとして直接連携     |
| IaC              | AWS CDK (Python)                | Python で統一。CloudFormation より記述量が少ない |

---

## 対応ドキュメント形式

Bedrock Knowledge Bases がサポートする形式

- `.pdf` / `.txt` / `.md` / `.html`
- `.csv` / `.xls` / `.xlsx`
- `.doc` / `.docx`

---

## ディレクトリ構成

```
bedrock-rag-chat/
├── pyproject.toml              # uv 依存管理
├── cdk/                        # CDK インフラ定義
│   ├── app.py
│   ├── cdk.json
│   └── stacks/
│       ├── knowledge_base_stack.py   # S3 + OpenSearch + Knowledge Base
│       └── api_stack.py              # Lambda + API Gateway
├── lambda/                     # Lambda 関数
│   └── handler.py
├── frontend/                   # Streamlit アプリ
│   └── app.py
├── docs/                       # 検索対象ドキュメント（S3 アップロード用）
└── tests/
```

---

## 費用（月額・学習用途想定）

| サービス                    | 概算                                      |
| --------------------------- | ----------------------------------------- |
| OpenSearch Serverless       | ~$700（最小 2 OCU × $0.24/h × 24h × 30d） |
| Bedrock (Claude Sonnet 4) | ~$1-5（少量利用前提）                     |
| Bedrock (Titan Embeddings)  | ~$0.1                                     |
| Lambda / API Gateway / S3   | 無料枠内                                  |

> **注意**: OpenSearch Serverless は最低 2 OCU が必要で最大のコスト要因。
> 代替案として **Pinecone（無料枠あり、Bedrock KB 対応）** や **使用時のみ起動** を検討。

---

## セットアップ

### 前提

- AWS CLI が設定済み（`aws configure` でクレデンシャルが設定されていること）
- [uv](https://docs.astral.sh/uv/) がインストール済み
- Node.js がインストール済み（CDK CLI 用）
- Bedrock のモデルアクセスが有効化済み（Titan Text Embeddings V2, Claude Sonnet 4）

### 依存インストール

```bash
uv sync
npm install -g aws-cdk
```

### デプロイ

```bash
cd cdk

# 初回のみ
cdk bootstrap --profile <PROFILE> --region us-east-1

# インフラ（S3 + OpenSearch + Knowledge Base）
cdk deploy KnowledgeBaseStack --profile <PROFILE> --region us-east-1

# API（Lambda + API Gateway）
cdk deploy ApiStack --profile <PROFILE> --region us-east-1
```

### ドキュメントのアップロードと同期

```bash
# S3 にアップロード
aws s3 sync docs/ s3://bedrock-rag-docs-<ACCOUNT_ID>/ --profile <PROFILE> --region us-east-1

# データソース同期
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <KB_ID> \
  --data-source-id <DS_ID> \
  --profile <PROFILE> --region us-east-1
```

### ローカル起動

```bash
cp .env.example .env
# .env の API_URL を ApiStack のデプロイ出力で取得したエンドポイントに設定

uv run streamlit run frontend/app.py
```

ブラウザで `http://localhost:8501` が自動的に開く。

### リソース削除

```bash
cd cdk

# API スタック削除
cdk destroy ApiStack --profile <PROFILE> --region us-east-1

# Knowledge Base スタック削除
cdk destroy KnowledgeBaseStack --profile <PROFILE> --region us-east-1
```

> **削除順序**: ApiStack → KnowledgeBaseStack の順で削除する。

---

## 今後の追加機能

- **認証**: Cognito User Pool による認証・アクセス制御
- **会話の永続化**: DynamoDB または Bedrock Sessions による会話履歴の保存
- **ストリーミングレスポンス**: Lambda Response Streaming による逐次表示
- **フロントエンドの本番化**: Next.js / React、または Streamlit on ECS
- **CI/CD パイプライン**: CodePipeline / GitHub Actions によるデプロイ・データソース同期の自動化
