CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS messages (
    id text PRIMARY KEY,
    source text NOT NULL,
    platform_style text NOT NULL,
    workspace_id text NOT NULL,
    channel_id text NOT NULL,
    channel_name text NOT NULL,
    source_message_id text NOT NULL,
    thread_root_id text,
    author_id text NOT NULL,
    author_name text NOT NULL,
    text text NOT NULL,
    created_at timestamptz NOT NULL,
    permalink text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source, channel_id, source_message_id)
);

CREATE INDEX IF NOT EXISTS messages_channel_created_idx
    ON messages (channel_id, created_at);

CREATE TABLE IF NOT EXISTS chunks (
    id text PRIMARY KEY,
    kind text NOT NULL,
    chunker_version text NOT NULL,
    channel_id text NOT NULL,
    message_ids text[] NOT NULL,
    start_at timestamptz NOT NULL,
    end_at timestamptz NOT NULL,
    text text NOT NULL,
    embedding vector(1536),
    embedding_model text,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
