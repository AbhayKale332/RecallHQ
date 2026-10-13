<div align="center">

<img src="frontend/public/logo.svg" width="72" alt="RecallHQ logo" />

# RecallHQ

**Ask your team chat. Get grounded, cited answers.**

Hybrid retrieval and grounded answers over Slack conversations, with a public synthetic demo.

RecallHQ also runs as a multi-workspace **Slack bot**. Invite it into a channel to
import available history and capture new messages, then use `/recall ask`,
`/recall search`, or `/recall catchup` for private, cited results. Workspace and
channel access are enforced independently of the public demo.

See [Slack setup, commands, testing, and deployment](docs/slack-bot.md). Generate
an app manifest with `uv run python -m recallhq.cli slack-manifest --base-url <HTTPS-API-URL>`.

[![Docs and demo](https://img.shields.io/badge/recall.abhaykale.me-E6176D?style=for-the-badge&logo=vercel&logoColor=white)](https://recall.abhaykale.me)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Postgres_+_pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-6566F1?style=flat-square&logo=openrouter&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

</div>

---

## Commands

| Command | What it does |
| --- | --- |
| `/recall ask <question> [in:#channel]` | Private, grounded answer with links to Slack messages |
| `/recall search <terms> [in:#channel]` | Matching messages in channels you belong to |
| `/recall catchup YYYY-MM-DD YYYY-MM-DD [in:#channel]` | Date-bounded recap (up to 32 days) |
| `/recall summarize <message-link>` | Indexed thread summary |
| `/recall decisions [in:#channel]` | Decisions from the last seven days |
| `/recall status` | Channel imports and embedding backlog |
| `/recall sync #channel` | Admin: retry history import |
| `/recall forget #channel` | Admin: confirm disabling ingestion and purging channel data |

Use `/recall help` for syntax. The anonymous Beacon demo supports `/ask`,
`/search`, and `/catchup` over synthetic messages.

## Architecture

```mermaid
flowchart TB
    MEMBERS([Workspace members]) --> SLACK["Slack workspaces<br/>Invited public/private channels"]
    VISITORS([Public visitors])
    VERCEL["Next.js docs, demo and playground<br/>Vercel mirror: recall.abhaykale.me"]

    subgraph VM["Existing Azure VM: recova-vm"]
        CADDY["Caddy HTTPS proxy"]
        SITE["Next.js docs, demo and playground<br/>/recallhq"]
        API["FastAPI + Slack Bolt<br/>OAuth, signature checks, durable ingress<br/>Synthetic demo API"]
        WORKER["Slack worker<br/>Ingestion, commands and embedding lanes<br/>Retries, leases and reconciliation"]
        RAG["Shared retrieval service<br/>Hybrid search, reranking, cited answers"]
    end

    subgraph PG["Existing Azure PostgreSQL 16: recallhq-pg-abhay — verified TLS"]
        INSTALLS[("Encrypted OAuth installations<br/>Channel settings and quotas")]
        QUEUE[("Durable Slack job queue")]
        CONTENT[("Messages and chunks<br/>pgvector + tsvector<br/>Source/workspace/channel RLS")]
    end

    OAI["OpenAI<br/>Embeddings and answer generation"]
    ORT["OpenRouter Decisions API<br/>Reranking"]

    VISITORS --> CADDY
    VISITORS --> VERCEL
    VERCEL -->|Public demo requests| CADDY
    CADDY -->|/recallhq| SITE
    SITE -->|Install and demo API requests| CADDY
    SLACK -->|OAuth, signed events and /recall| CADDY
    CADDY -->|/recallhq/api| API
    API -->|Store installation| INSTALLS
    API -->|Persist before acknowledgement| QUEUE
    QUEUE -->|Claim leased jobs| WORKER
    WORKER -->|Read installation and channel settings| INSTALLS
    WORKER <-->|History and live membership checks| SLACK
    WORKER -->|Scoped writes: messages, edits and deletes| CONTENT
    WORKER -->|Embed chunks| OAI
    WORKER -->|Authorized workspace and channels| RAG
    API -->|Synthetic Beacon scope only| RAG
    RAG <-->|Scoped read-only queries| CONTENT
    RAG <-->|Embed query and generate answer| OAI
    RAG <-->|Score relevance| ORT
    RAG -->|Answer and evidence| WORKER
    WORKER -->|Revalidate sources and membership; private reply| SLACK
```

The API acknowledges verified Slack requests after persisting their jobs. The
worker imports available channel history, captures live changes, and performs
model work separately. Slack queries enforce current membership before retrieval
and delivery; the public site queries only the synthetic Beacon corpus. Runtime
database logins have separate read/write roles, and installations retain their
own encrypted bot tokens.

## Retrieval pipeline

```mermaid
flowchart TD
    Q[Query] --> F{"Filters<br/>date range · channel"}
    F --> S["Semantic search<br/>pgvector cosine · top 30"]
    F --> L["Lexical search<br/>tsvector ts_rank · top 30"]
    S --> R["Reciprocal rank fusion<br/>score += 1 / (rank + 10)"]
    L --> R
    R --> RR["Rerank top 10 · Jev 1.13<br/>(OpenRouter Decisions API)"]
    RR -.->|fails| RL["Fallback · GPT-6 Luna Decisions"]
    RL -.->|fails| E
    RR --> E[Top 12 evidence messages]
    RL --> E
    E --> G["LLM answer<br/>cites [message-id]"]
    G --> V{Citations valid?}
    V -->|yes| A[Answer + sources]
    V -->|no| N["I couldn't verify an answer"]
```

### Reranking

`/ask` and `/search` rerank the top 10 RRF hits with the OpenRouter **Decisions API**.
One request scores every candidate against a 4-level relevance rubric (unrelated → directly answers);
hits are sorted by that score, with ties kept in RRF order. `/catchup` is not reranked.

1. **Jev 1.13** (`typesafe/jev-1.13-20260917`) is tried first.
2. If it errors or times out, **GPT-6 Luna Decisions** (`openai/gpt-6-luna-decisions-20261006`) scores the same request.
3. If both fail, or `OPEN_ROUTER` is unset, results keep plain RRF order.

| Setting | Default |
| --- | --- |
| `OPEN_ROUTER` | OpenRouter API key (reranking is off when empty) |
| `RERANK_MODEL` | `typesafe/jev-1.13-20260917` |
| `RERANK_FALLBACK_MODEL` | `openai/gpt-6-luna-decisions-20261006` |
| `RERANK_TOP_K` | `10` |

Still planned for evaluation: a local cross-encoder (`BAAI/bge-reranker-v2-m3`) on the same candidates.

## `/ask` request flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Postgres
    participant AI as OpenAI
    participant ORT as OpenRouter
    FE->>API: POST /commands "/ask ..."
    API->>API: Rate-limit check (per IP + site-wide)
    API->>AI: Embed query
    API->>DB: Hybrid search (vector + full-text)
    DB-->>API: Ranked message IDs
    API->>ORT: Rerank top 10 with Jev
    alt Jev fails
        API->>ORT: Retry with GPT-6 Luna Decisions
    end
    ORT-->>API: Relevance scores
    API->>AI: Generate answer from evidence
    AI-->>API: Answer with [source IDs]
    API-->>FE: Answer + verified sources
```

## Quickstart

```bash
uv sync --locked
docker compose up -d
uv run python -m recallhq.cli migrate
uv run python -m recallhq.cli ingest data/synthetic/corpus.jsonl
uv run uvicorn recallhq.api:app --reload
uv run pytest -q
```

Set `OPENAI_API_KEY`, `DATABASE_URL` and optionally `OPEN_ROUTER` in `.env` (local defaults match `compose.yaml`).
Ingest is re-runnable: unchanged chunks keep their embeddings.
Anonymous commands are limited to 3/min and 20/day per IP, plus 200/day site-wide.

For the frontend, see [frontend/README.md](frontend/README.md). It adapts the MIT-licensed
[Slack clone](https://github.com/sanidhyy/slack-clone) into a public, read-only Beacon workspace.

## Deployment

| Piece | Where |
| --- | --- |
| Frontend and docs | Azure VM at [/recallhq](https://recova.indiasouthcentral.cloudapp.azure.com/recallhq); Vercel project `recallhq` remains available |
| API and Slack worker | `recallhq-slack-api` and `recallhq-slack-worker` on `recova-vm`; Caddy routes `/recallhq/api/*` |
| Database | Azure PostgreSQL Flexible Server `recallhq-pg-abhay` (PG 16, B1ms, 32 GB, `vector` allowlisted) in `recallhq-rg` |
| Security | DB firewall allows only the VM's IP; verified TLS, separate read/write logins, and workspace/channel RLS; secrets live in `slack-runtime.env` on the VM, outside the repo |

See the [Azure deployment runbook](deploy/azure/README.md) for releases, checks,
and Slack endpoint cutover. The docs site includes installation, command
reference, permissions, a synthetic demo, and an anonymous playground.

## Layout

```
src/recallhq/   API, CLI, ingestion, retrieval
src/recallhq/slack/ OAuth, signed ingress, incremental ingestion, commands, worker
migrations/     Postgres schema (pgvector, full-text index)
scripts/        Corpus generation & validation
evals/          Evaluation queries and reference checks
frontend/       Next.js + Convex chat UI
```

## License

[MIT](LICENSE)
