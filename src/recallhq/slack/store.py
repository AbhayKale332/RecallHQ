"""Encrypted OAuth storage, durable jobs, and workspace-scoped database access."""

import hashlib
import json
import logging
import secrets
from contextlib import nullcontext
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb
from slack_sdk.oauth.installation_store import InstallationStore
from slack_sdk.oauth.installation_store.models.installation import Installation
from slack_sdk.oauth.state_store import OAuthStateStore

from recallhq.config import Settings
from recallhq.db import QueryContext, connect

LOG = logging.getLogger("recallhq.slack")


class RetryLater(Exception):
    def __init__(self, seconds: float, reason: str = "rate_limit"):
        self.seconds = max(1, seconds)
        self.reason = reason


def database(settings: Settings, team: str = ""):
    return connect(settings, QueryContext("slack", team, ()), write=True)


def encrypt(settings: Settings, value: dict) -> str:
    return Fernet(settings.slack_encryption_key.encode()).encrypt(
        json.dumps(value, default=lambda v: v.timestamp() if isinstance(v, datetime) else str(v)).encode()).decode()


def decrypt(settings: Settings, value: str) -> dict:
    return json.loads(Fernet(settings.slack_encryption_key.encode()).decrypt(value.encode()))


def enqueue(conn, team: str, kind: str, payload: dict, dedupe: str, channel: str | None = None):
    return conn.execute("""
        INSERT INTO slack_jobs (team_id, channel_id, kind, payload, dedupe_key)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (dedupe_key) DO NOTHING RETURNING id
    """, (team, channel, kind, Jsonb(payload), dedupe)).fetchone()


def disable(conn, team: str, channel: str | None = None):
    """Revoke access now; perform potentially large content purges in the worker."""
    if channel:
        conn.execute("UPDATE slack_channels SET active = false, import_status = 'disabled' WHERE team_id = %s AND channel_id = %s", (team, channel))
        conn.execute("UPDATE slack_jobs SET status = 'cancelled', payload = '{}'::jsonb WHERE team_id = %s AND channel_id = %s AND status IN ('pending', 'processing')", (team, channel))
    else:
        conn.execute("UPDATE slack_installations SET active = false, encrypted_installation = '' WHERE team_id = %s", (team,))
        conn.execute("UPDATE slack_channels SET active = false, import_status = 'disabled' WHERE team_id = %s", (team,))
        conn.execute("UPDATE slack_jobs SET status = 'cancelled', payload = '{}'::jsonb WHERE team_id = %s AND status IN ('pending', 'processing')", (team,))
    enqueue(conn, team, "purge", {}, f"purge:{team}:{channel}:{secrets.token_hex(12)}", channel)


def purge(conn, team: str, channel: str | None = None):
    # A delayed purge must never wipe a channel that was explicitly reinvited meanwhile.
    params = (team, channel) if channel else (team,)
    suffix = " AND channel_id = %s" if channel else ""
    rows = conn.execute("SELECT channel_id FROM slack_channels WHERE team_id = %s AND NOT active" + suffix + " FOR UPDATE", params).fetchall()
    for row in rows:
        args = (team, row["channel_id"])
        for table in ("chunks", "messages"):
            conn.execute(f"DELETE FROM {table} WHERE source = 'slack' AND workspace_id = %s AND channel_id = %s", args)
        conn.execute("DELETE FROM slack_tombstones WHERE team_id = %s AND channel_id = %s", args)
        conn.execute("DELETE FROM slack_seen_messages WHERE team_id = %s AND channel_id = %s", args)
        conn.execute("UPDATE slack_jobs SET payload = '{}'::jsonb WHERE team_id = %s AND channel_id = %s AND status IN ('done','cancelled','failed')", args)
    if not channel:
        conn.execute("UPDATE slack_jobs SET payload = '{}'::jsonb WHERE team_id = %s AND status IN ('done','cancelled','failed')", (team,))


class PostgresInstallationStore(InstallationStore):
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def logger(self):
        return LOG

    def save(self, installation: Installation):
        if not installation.team_id or installation.is_enterprise_install or not installation.bot_token:
            raise ValueError("RecallHQ requires a workspace-level bot installation.")
        with database(self.settings, installation.team_id) as conn:
            conn.execute("""
                INSERT INTO slack_installations (team_id, encrypted_installation, bot_user_id)
                VALUES (%s, %s, %s) ON CONFLICT (team_id) DO UPDATE SET
                  encrypted_installation = EXCLUDED.encrypted_installation,
                  bot_user_id = EXCLUDED.bot_user_id, active = true, installed_at = now()
            """, (installation.team_id, encrypt(self.settings, installation.to_dict()), installation.bot_user_id))
            enqueue(conn, installation.team_id, "discover", {}, f"discover:{installation.team_id}:{secrets.token_hex(12)}")

    def find_installation(self, *, enterprise_id=None, team_id=None, user_id=None, is_enterprise_install=False):
        if not team_id or is_enterprise_install:
            return None
        with database(self.settings, team_id) as conn:
            row = conn.execute("SELECT encrypted_installation FROM slack_installations WHERE team_id = %s AND active", (team_id,)).fetchone()
        return Installation(**decrypt(self.settings, row["encrypted_installation"])) if row else None

    def find_bot(self, *, enterprise_id=None, team_id=None, is_enterprise_install=False):
        installation = self.find_installation(team_id=team_id, is_enterprise_install=is_enterprise_install)
        return installation.to_bot() if installation else None

    def delete_bot(self, *, enterprise_id=None, team_id=None):
        self.delete_installation(team_id=team_id)

    def delete_installation(self, *, enterprise_id=None, team_id=None, user_id=None):
        if team_id:
            with database(self.settings, team_id) as conn:
                disable(conn, team_id)


class PostgresStateStore(OAuthStateStore):
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def logger(self):
        return LOG

    def issue(self, *args, **kwargs):
        state = secrets.token_urlsafe(32)
        digest = hashlib.sha256(state.encode()).hexdigest()
        with database(self.settings) as conn:
            conn.execute("DELETE FROM slack_oauth_states WHERE expires_at < now()")
            conn.execute("INSERT INTO slack_oauth_states VALUES (%s, now() + interval '10 minutes')", (digest,))
        return state

    def consume(self, state: str):
        if not state:
            return False
        with database(self.settings) as conn:
            return bool(conn.execute("DELETE FROM slack_oauth_states WHERE digest = %s AND expires_at > now() RETURNING digest",
                                     (hashlib.sha256(state.encode()).hexdigest(),)).fetchone())


def claim(settings: Settings, kinds: tuple[str, ...] | None = None):
    lease = secrets.token_hex(16)
    with database(settings) as conn:
        return conn.execute("""
            UPDATE slack_jobs SET status = 'processing', attempts = attempts + 1,
              lease_until = now() + interval '10 minutes', lease_token = %s
            WHERE id = (
                SELECT id FROM slack_jobs
                WHERE (status = 'pending' OR (status = 'processing' AND lease_until < now()))
                  AND available_at <= now()
                  AND (%s::text[] IS NULL OR kind = ANY(%s))
                ORDER BY CASE kind WHEN 'purge' THEN 0 WHEN 'event' THEN 1 WHEN 'command' THEN 2 ELSE 3 END, available_at, id
                LIMIT 1 FOR UPDATE SKIP LOCKED
            ) RETURNING *
        """, (lease, list(kinds) if kinds else None, list(kinds) if kinds else None)).fetchone()


def finish(settings: Settings, job: dict, *, delay: float | None = None, error: str | None = None, continuing=False):
    status = "done" if delay is None else "pending"
    if error and job["attempts"] >= settings.slack_job_max_attempts:
        status = "failed"
    with database(settings, job["team_id"]) as conn:
        conn.execute("""
            UPDATE slack_jobs SET status = %s, last_error = %s, lease_until = NULL, lease_token = NULL,
              available_at = now() + %s * interval '1 second',
              attempts = CASE WHEN %s THEN 0 ELSE attempts END,
              payload = CASE WHEN %s = 'done' THEN '{}'::jsonb ELSE payload END
            WHERE id = %s AND status = 'processing' AND lease_token = %s
        """, (status, error, delay or 0, continuing, status, job["id"], job["lease_token"]))
        if error and job.get("channel_id"):
            conn.execute("UPDATE slack_channels SET last_error = %s WHERE team_id = %s AND channel_id = %s",
                         (error, job["team_id"], job["channel_id"]))


def reserve_api(settings: Settings, team: str, method: str, interval: float):
    with database(settings) as conn:
        conn.execute("INSERT INTO slack_api_limits VALUES (%s, %s, now()) ON CONFLICT DO NOTHING", (team, method))
        row = conn.execute("SELECT available_at FROM slack_api_limits WHERE team_id = %s AND method = %s FOR UPDATE", (team, method)).fetchone()
        delay = (row["available_at"] - datetime.now(UTC)).total_seconds()
        if delay > 0:
            raise RetryLater(delay)
        conn.execute("UPDATE slack_api_limits SET available_at = now() + %s * interval '1 second' WHERE team_id = %s AND method = %s", (interval, team, method))


def postpone_api(settings: Settings, team: str, method: str, seconds: float):
    with database(settings) as conn:
        conn.execute("""INSERT INTO slack_api_limits VALUES (%s, %s, now() + %s * interval '1 second')
                        ON CONFLICT (team_id, method) DO UPDATE SET available_at = GREATEST(slack_api_limits.available_at, EXCLUDED.available_at)""",
                     (team, method, seconds))


def command_quota(settings: Settings, team: str, user: str, connection=None):
    now = int(datetime.now(UTC).timestamp())
    buckets = (("user:" + user, now // 60, settings.slack_user_commands_per_minute),
               ("workspace", now // 86400, settings.slack_workspace_commands_per_day))
    with (database(settings) if connection is None else nullcontext(connection)) as conn:
        # Stable order serializes both quota counters; the whole reservation rolls back on failure.
        for subject, period, limit in buckets:
            conn.execute("INSERT INTO slack_usage VALUES (%s, %s, %s, 0) ON CONFLICT DO NOTHING", (team, subject, period))
            row = conn.execute("SELECT count FROM slack_usage WHERE team_id = %s AND subject = %s AND period = %s FOR UPDATE", (team, subject, period)).fetchone()
            if row["count"] >= limit:
                raise ValueError("RecallHQ command limit reached. Please try again later.")
            conn.execute("UPDATE slack_usage SET count = count + 1 WHERE team_id = %s AND subject = %s AND period = %s", (team, subject, period))


def start_import(conn, team: str, channel: str):
    import time
    boundary = f"{time.time():.6f}"
    row = conn.execute("SELECT channel_id FROM slack_channels WHERE team_id = %s AND channel_id = %s AND active FOR UPDATE", (team, channel)).fetchone()
    if not row:
        return
    conn.execute("UPDATE slack_jobs SET status = 'cancelled', payload = '{}'::jsonb WHERE team_id = %s AND channel_id = %s AND kind IN ('history', 'replies') AND status IN ('pending','processing','failed')", (team, channel))
    conn.execute("UPDATE slack_jobs SET status = 'pending', attempts = 0, available_at = now(), last_error = NULL WHERE team_id = %s AND channel_id = %s AND kind = 'embed' AND status = 'failed'", (team, channel))
    conn.execute("UPDATE slack_channels SET import_boundary = %s, history_cursor = '', import_status = 'pending', last_error = NULL WHERE team_id = %s AND channel_id = %s", (boundary, team, channel))
    enqueue(conn, team, "history", {"boundary": boundary}, f"history:{team}:{channel}:{boundary}", channel)
