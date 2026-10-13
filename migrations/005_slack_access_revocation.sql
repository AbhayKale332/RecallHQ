-- Readers can check revocation without access to encrypted credentials or channel names.
GRANT SELECT (team_id, active) ON slack_installations TO recallhq_reader;
GRANT SELECT (team_id, channel_id, active) ON slack_channels TO recallhq_reader;
ALTER POLICY messages_read ON messages USING (
    source = current_setting('app.source', true)
    AND workspace_id = current_setting('app.workspace', true)
    AND COALESCE(nullif(current_setting('app.channels', true), ''), '[]')::jsonb ? channel_id
    AND (source <> 'slack' OR EXISTS (
        SELECT 1 FROM slack_channels c JOIN slack_installations i USING (team_id)
        WHERE c.team_id = messages.workspace_id AND c.channel_id = messages.channel_id AND c.active AND i.active
    ))
);
ALTER POLICY chunks_read ON chunks USING (
    source = current_setting('app.source', true)
    AND workspace_id = current_setting('app.workspace', true)
    AND COALESCE(nullif(current_setting('app.channels', true), ''), '[]')::jsonb ? channel_id
    AND (source <> 'slack' OR EXISTS (
        SELECT 1 FROM slack_channels c JOIN slack_installations i USING (team_id)
        WHERE c.team_id = chunks.workspace_id AND c.channel_id = chunks.channel_id AND c.active AND i.active
    ))
);
