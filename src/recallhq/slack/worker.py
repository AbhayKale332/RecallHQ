"""Run durable Slack work separately from HTTP acknowledgement."""

import logging
import re
import signal
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread

from recallhq.config import Settings
from recallhq.retrieval import service
from recallhq.slack.commands import deliver, respond
from recallhq.slack.ingestion import (
    complete_import,
    discover,
    embed_channel,
    history_page,
    process_event,
    replies_page,
)
from recallhq.slack.store import (
    RetryLater,
    claim,
    database,
    decrypt,
    finish,
    purge,
    start_import,
)

LOG = logging.getLogger("recallhq.slack.worker")


def process(settings, job):
    kind = job["kind"]
    if kind == "purge":
        with database(settings, job["team_id"]) as conn:
            purge(conn, job["team_id"], job["channel_id"])
    elif kind == "event":
        process_event(settings, job)
    elif kind == "discover":
        discover(settings, job)
    elif kind == "history":
        if history_page(settings, job):
            return settings.slack_history_interval_seconds
    elif kind == "replies":
        if replies_page(settings, job):
            return settings.slack_history_interval_seconds
    elif kind == "command":
        deliver(settings, job)
    elif kind == "embed":
        if embed_channel(settings, job["team_id"], job["channel_id"]):
            return 1
    elif kind != "noop":
        raise ValueError("Unknown job kind")
    return None


def maintenance(settings):
    with database(settings) as conn:
        completing = conn.execute("SELECT team_id, channel_id FROM slack_channels WHERE active AND import_status = 'threads'").fetchall()
        reconciling = conn.execute("SELECT team_id, channel_id FROM slack_channels WHERE active AND import_status = 'complete' AND last_reconciled_at < now() - %s * interval '1 second'", (settings.slack_reconcile_interval_seconds,)).fetchall()
        conn.execute("UPDATE slack_jobs SET payload = '{}'::jsonb WHERE status IN ('done','cancelled')")
        conn.execute("DELETE FROM slack_jobs WHERE status IN ('done','cancelled') AND created_at < now() - interval '7 days'")
        conn.execute("DELETE FROM slack_usage WHERE subject = 'workspace' AND period < extract(epoch FROM now())::bigint / 86400 - 2")
        conn.execute("DELETE FROM slack_usage WHERE subject <> 'workspace' AND period < extract(epoch FROM now())::bigint / 60 - 2")
        conn.execute("""INSERT INTO slack_jobs (team_id, channel_id, kind, dedupe_key, payload)
                        SELECT c.team_id, c.channel_id, 'embed', 'embed:' || c.team_id || ':' || c.channel_id, '{}'::jsonb
                        FROM slack_channels c JOIN slack_installations i USING(team_id) WHERE c.active AND i.active
                        ON CONFLICT (dedupe_key) DO UPDATE SET status = 'pending', attempts = 0, available_at = now()
                        WHERE slack_jobs.status = 'done'""")
    for channel in completing:
        complete_import(settings, channel["team_id"], channel["channel_id"])
    for channel in reconciling:
        with database(settings, channel["team_id"]) as conn:
            start_import(conn, channel["team_id"], channel["channel_id"])


def work_once(settings, kinds=None):
    job = claim(settings, kinds)
    if not job:
        return False
    heartbeat_stop = Event()

    def heartbeat():
        while not heartbeat_stop.wait(60):
            try:
                with database(settings) as conn:
                    conn.execute("UPDATE slack_jobs SET lease_until = now() + interval '10 minutes' WHERE id = %s AND lease_token = %s AND status = 'processing'", (job["id"], job["lease_token"]))
            except Exception:  # noqa: BLE001 - heartbeat errors must not drop the active job
                LOG.warning("Lease renewal failed for job %s", job["id"])

    renewal = Thread(target=heartbeat, daemon=True)
    renewal.start()
    try:
        delay = process(settings, job)
        finish(settings, job, delay=delay, continuing=delay is not None)
        LOG.info("Slack job %s (%s) processed", job["id"], job["kind"])
    except RetryLater as exc:
        finish(settings, job, delay=exc.seconds, error=exc.reason, continuing=True)
    except Exception as exc:  # noqa: BLE001 - durable worker boundary; persist only sanitized errors
        category = type(exc).__name__
        if isinstance(exc, ValueError) and re.fullmatch(r"Slack API: [a-z_]{1,60}", str(exc)):
            category = str(exc)
        finish(settings, job, delay=min(300, 2 ** min(job["attempts"], 8)), error=category)
        LOG.warning("Slack job %s (%s) failed: %s", job["id"], job["kind"], category)
        if job["kind"] == "command" and job["attempts"] >= settings.slack_job_max_attempts:
            try:
                payload = decrypt(settings, job["payload"]["encrypted"])
                respond(payload["response_url"], {"text": "RecallHQ couldn't complete this request after retrying. Please try again later."})
            except Exception:  # noqa: BLE001 - failed notification must not stop ingestion
                LOG.warning("Could not notify requester for failed job %s", job["id"])
    finally:
        heartbeat_stop.set()
        renewal.join(timeout=3)
    return True


def run():
    settings = Settings()
    if not settings.slack_encryption_key:
        raise ValueError("Set SLACK_ENCRYPTION_KEY before starting the worker.")
    service.SETTINGS = settings
    logging.basicConfig(level=logging.INFO)
    stopping = Event()

    def stop(*_):
        stopping.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    # Completed imports get a fresh reconciliation after an outage; in-flight imports resume their cursors.
    with database(settings) as conn:
        completed = conn.execute("SELECT team_id, channel_id FROM slack_channels WHERE active AND import_status = 'complete'").fetchall()
    for channel in completed:
        with database(settings, channel["team_id"]) as conn:
            start_import(conn, channel["team_id"], channel["channel_id"])
    def loop(kinds, maintain=False):
        last_maintenance = 0
        while not stopping.is_set():
            try:
                if not work_once(settings, kinds):
                    stopping.wait(1)
                if maintain and time.monotonic() - last_maintenance >= 10:
                    maintenance(settings)
                    last_maintenance = time.monotonic()
            except Exception as exc:  # noqa: BLE001 - reconnect after database failures
                LOG.error("Worker database/maintenance failure (%s)", type(exc).__name__)
                stopping.wait(2)

    # Queries and model calls cannot hold up live ingestion or source deletions.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="recallhq") as pool:
        pool.submit(loop, ("command",))
        pool.submit(loop, ("embed",))
        loop(("event", "purge", "noop", "discover", "history", "replies"), maintain=True)


if __name__ == "__main__":
    run()
