CREATE TABLE slack_seen_messages (
    team_id text NOT NULL,
    channel_id text NOT NULL,
    boundary text NOT NULL,
    message_ts text NOT NULL,
    PRIMARY KEY (team_id, channel_id, boundary, message_ts)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON slack_seen_messages TO recallhq_ingestor;
