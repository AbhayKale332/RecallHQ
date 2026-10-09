from pathlib import Path

import psycopg

from recallhq.config import Settings


MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def migrate(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    with psycopg.connect(settings.database_url) as conn:
        for path in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(path.read_text())
