-- Applied once by the migration role, before starting either API or worker.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'recallhq_reader') THEN
        CREATE ROLE recallhq_reader NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'recallhq_ingestor') THEN
        CREATE ROLE recallhq_ingestor NOLOGIN;
    END IF;
END $$;
GRANT recallhq_reader, recallhq_ingestor TO CURRENT_USER;
GRANT USAGE ON SCHEMA public TO recallhq_reader, recallhq_ingestor;

ALTER TABLE messages DROP CONSTRAINT messages_source_channel_id_source_message_id_key;
ALTER TABLE messages ADD CONSTRAINT messages_source_workspace_channel_ts_key
    UNIQUE (source, workspace_id, channel_id, source_message_id);
ALTER TABLE messages ADD COLUMN source_revision numeric NOT NULL DEFAULT 0;
ALTER TABLE chunks ADD COLUMN source text;
ALTER TABLE chunks ADD COLUMN workspace_id text;
UPDATE chunks SET source = 'synthetic', workspace_id = 'beacon';
ALTER TABLE chunks ALTER COLUMN source SET NOT NULL;
ALTER TABLE chunks ALTER COLUMN workspace_id SET NOT NULL;
CREATE INDEX messages_workspace_channel_date_idx ON messages (source, workspace_id, channel_id, created_at, id);
CREATE INDEX chunks_workspace_channel_date_idx ON chunks (source, workspace_id, channel_id, start_at);
CREATE INDEX chunks_message_ids_idx ON chunks USING gin (message_ids);

CREATE TABLE slack_installations (
    team_id text PRIMARY KEY,
    encrypted_installation text NOT NULL,
    bot_user_id text NOT NULL,
    installed_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL DEFAULT true
);
CREATE TABLE slack_oauth_states (
    digest text PRIMARY KEY,
    expires_at timestamptz NOT NULL
);
CREATE TABLE slack_channels (
    team_id text NOT NULL REFERENCES slack_installations(team_id),
    channel_id text NOT NULL,
    name text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    import_status text NOT NULL DEFAULT 'pending',
    history_cursor text NOT NULL DEFAULT '',
    import_boundary text NOT NULL,
    last_ingested_at timestamptz,
    last_reconciled_at timestamptz,
    last_error text,
    PRIMARY KEY (team_id, channel_id)
);
CREATE TABLE slack_tombstones (
    team_id text NOT NULL,
    channel_id text NOT NULL,
    message_ts text NOT NULL,
    revision numeric NOT NULL,
    PRIMARY KEY (team_id, channel_id, message_ts)
);
CREATE TABLE slack_jobs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id text NOT NULL,
    channel_id text,
    kind text NOT NULL,
    dedupe_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed', 'cancelled')),
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    lease_token text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX slack_jobs_ready_idx ON slack_jobs (available_at, id) WHERE status IN ('pending', 'processing');
CREATE INDEX slack_jobs_channel_idx ON slack_jobs (team_id, channel_id, status);
CREATE TABLE slack_api_limits (
    team_id text NOT NULL,
    method text NOT NULL,
    available_at timestamptz NOT NULL,
    PRIMARY KEY (team_id, method)
);
CREATE TABLE slack_usage (
    team_id text NOT NULL,
    subject text NOT NULL,
    period bigint NOT NULL,
    count integer NOT NULL DEFAULT 0,
    PRIMARY KEY (team_id, subject, period)
);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY messages_read ON messages FOR SELECT TO recallhq_reader USING (
    source = current_setting('app.source', true)
    AND workspace_id = current_setting('app.workspace', true)
    AND COALESCE(nullif(current_setting('app.channels', true), ''), '[]')::jsonb ? channel_id
);
CREATE POLICY chunks_read ON chunks FOR SELECT TO recallhq_reader USING (
    source = current_setting('app.source', true)
    AND workspace_id = current_setting('app.workspace', true)
    AND COALESCE(nullif(current_setting('app.channels', true), ''), '[]')::jsonb ? channel_id
);
CREATE POLICY messages_write ON messages TO recallhq_ingestor USING (
    source = current_setting('app.source', true) AND workspace_id = current_setting('app.workspace', true)
) WITH CHECK (
    source = current_setting('app.source', true) AND workspace_id = current_setting('app.workspace', true)
);
CREATE POLICY chunks_write ON chunks TO recallhq_ingestor USING (
    source = current_setting('app.source', true) AND workspace_id = current_setting('app.workspace', true)
) WITH CHECK (
    source = current_setting('app.source', true) AND workspace_id = current_setting('app.workspace', true)
);
GRANT SELECT ON messages, chunks TO recallhq_reader;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages, chunks, slack_installations,
    slack_oauth_states, slack_channels, slack_tombstones, slack_jobs, slack_api_limits, slack_usage TO recallhq_ingestor;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO recallhq_ingestor;
