<div align="center">

<img src="frontend/public/logo.svg" width="72" alt="RecallHQ logo" />

# RecallHQ

**Ask your team chat. Get grounded, cited answers.**

Hybrid retrieval and grounded answers over a synthetic Slack/Discord-style workspace.

[![Live demo](https://img.shields.io/badge/demo-recallhq--black.vercel.app-E6176D?style=for-the-badge&logo=vercel&logoColor=white)](https://recallhq-black.vercel.app)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Postgres_+_pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)
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
| `/ask <question>` | Grounded answer with links to source messages |
| `/search <terms>` | Matching messages across channels |
| `/catchup YYYY-MM-DD YYYY-MM-DD [#channel]` | Date-bounded recap (up to 32 days) |

## Architecture

```mermaid
flowchart LR
    U([User]) --> FE["Next.js frontend<br/>(Vercel)"]
    FE -->|"/ask · /search · /catchup"| API["FastAPI<br/>(Azure VM · Caddy)"]
    API -->|embed + generate| OAI[(OpenAI)]
    API -->|read-only role, TLS| PG[("PostgreSQL 16<br/>pgvector + tsvector")]

    subgraph Offline ingest
        C[corpus.jsonl] --> CH[Message & thread<br/>chunking] --> EM[Embeddings] --> PG
    end
```

## Retrieval pipeline

```mermaid
flowchart TD
    Q[Query] --> F{"Filters<br/>date range · channel"}
    F --> S["Semantic search<br/>pgvector cosine · top 30"]
    F --> L["Lexical search<br/>tsvector ts_rank · top 30"]
    S --> R["Reciprocal rank fusion<br/>score += 1 / (rank + 10)"]
    L --> R
    R --> E[Top-k evidence messages]
    E --> G["LLM answer<br/>cites [message-id]"]
    G --> V{Citations valid?}
    V -->|yes| A[Answer + sources]
    V -->|no| N["I couldn't verify an answer"]
```

## `/ask` request flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Postgres
    participant AI as OpenAI
    FE->>API: POST /commands "/ask ..."
    API->>API: Rate-limit check (per IP + site-wide)
    API->>AI: Embed query
    API->>DB: Hybrid search (vector + full-text)
    DB-->>API: Ranked message IDs
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

Set `OPENAI_API_KEY` and `DATABASE_URL` in `.env` (local defaults match `compose.yaml`).
Ingest is re-runnable: unchanged chunks keep their embeddings.
Anonymous commands are limited to 3/min and 20/day per IP, plus 200/day site-wide.

For the frontend, see [frontend/README.md](frontend/README.md). It adapts the MIT-licensed
[Slack clone](https://github.com/sanidhyy/slack-clone) into a public, read-only Beacon workspace.

## Deployment

| Piece | Where |
| --- | --- |
| Frontend | Vercel project `recallhq` |
| API | `recallhq-api` container on the `recova-vm` Docker network; Caddy routes `/recallhq/api/*` |
| Database | Azure PostgreSQL Flexible Server `recallhq-pg-abhay` (PG 16, B1ms, 32 GB, `vector` allowlisted) in `recallhq-rg` |
| Security | DB firewall allows only the VM's IP; API uses a read-only role with verified TLS; secrets live in `runtime.env` on the VM, outside the repo |

## Layout

```
src/recallhq/   API, CLI, ingestion, retrieval
migrations/     Postgres schema (pgvector, full-text index)
scripts/        Corpus generation & validation
evals/          Evaluation queries and reference checks
frontend/       Next.js + Convex chat UI
```

## License

[MIT](LICENSE)
