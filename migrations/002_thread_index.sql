CREATE INDEX IF NOT EXISTS messages_thread_created_idx
    ON messages (thread_root_id, created_at, id)
    WHERE thread_root_id IS NOT NULL;
