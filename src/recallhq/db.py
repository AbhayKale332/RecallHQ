import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from recallhq.config import Settings

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


@dataclass(frozen=True)
class QueryContext:
    source: str
    workspace_id: str
    channel_ids: tuple[str, ...]
    user_id: str = ""


DEMO_CONTEXT = QueryContext("synthetic", "beacon", ("eng", "product", "ops", "build-help", "random"))


@contextmanager
def connect(settings: Settings, context: QueryContext = DEMO_CONTEXT, *, write: bool = False):
    url = (settings.database_write_url or settings.database_url) if write else settings.database_url
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=2) as conn:
        conn.execute("SET ROLE recallhq_ingestor" if write else "SET ROLE recallhq_reader")
        # These connections are never pooled; keep context across the offline importer's commits.
        conn.execute("SELECT set_config('app.source', %s, false), set_config('app.workspace', %s, false), "
                     "set_config('app.channels', %s, false)",
                     (context.source, context.workspace_id, json.dumps(context.channel_ids)))
        yield conn


def migrate(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    with psycopg.connect(settings.database_migration_url or settings.database_write_url or settings.database_url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(724019)")
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if not conn.execute("SELECT 1 FROM schema_migrations WHERE name = %s", (path.name,)).fetchone():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
