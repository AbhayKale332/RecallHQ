"""Security and ingestion integration tests.

Set RECALLHQ_TEST_DATABASE_URL to a disposable PG16/pgvector administrator URL.
The suite creates and drops its own database; it never uses DATABASE_URL.
"""

import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlencode

import psycopg
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from psycopg import sql
from slack_bolt.request import BoltRequest
from slack_sdk.oauth.installation_store.models.installation import Installation

from recallhq import api
from recallhq.config import Settings
from recallhq.db import DEMO_CONTEXT, QueryContext, connect, migrate
from recallhq.retrieval import service
from recallhq.slack import app as slack_app
from recallhq.slack import commands, ingestion, store, worker
from recallhq.slack.manifest import manifest


@pytest.fixture(scope="module")
def pg_url():
    url = os.getenv("RECALLHQ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RECALLHQ_TEST_DATABASE_URL for disposable Postgres integration tests")
    name = "recallhq_test_" + os.urandom(6).hex()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    test_url = psycopg.conninfo.make_conninfo(url, dbname=name)
    migrate(Settings(_env_file=None, database_url=test_url, database_write_url=test_url, database_migration_url=test_url))
    yield test_url
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def settings(pg_url, monkeypatch):
    with psycopg.connect(pg_url) as conn:
        conn.execute("TRUNCATE messages, chunks, slack_installations, slack_channels, slack_jobs, slack_oauth_states, slack_tombstones, slack_seen_messages, slack_api_limits, slack_usage RESTART IDENTITY CASCADE")
    settings = Settings(_env_file=None, database_url=pg_url, database_write_url=pg_url, database_migration_url=pg_url,
                        openai_api_key="test-only", open_router="", slack_client_id="client", slack_client_secret="secret",
                        slack_signing_secret="signing", slack_encryption_key=Fernet.generate_key().decode(),
                        slack_public_url="https://example.slack-test.invalid", slack_history_interval_seconds=1)
    monkeypatch.setattr(service, "SETTINGS", settings)
    monkeypatch.setattr(api, "SETTINGS", settings)
    return settings


def seed(settings, team="T1", channel="C1", name="eng", active=True):
    install = Installation(team_id=team, user_id="INSTALLER", bot_token="test-bot", bot_user_id="BOT", bot_id="B1")
    store.PostgresInstallationStore(settings).save(install)
    with store.database(settings, team) as conn:
        conn.execute("INSERT INTO slack_channels (team_id, channel_id, name, active, import_boundary) VALUES (%s,%s,%s,%s,'1800000000.000000')", (team, channel, name, active))
    return install


def message(ts="1750000000.000001", text="We chose PostgreSQL for storage", **extra):
    return {"ts": ts, "text": text, "user": "U1", **extra}


def add(settings, msg=None, team="T1", channel="C1", **kwargs):
    with store.database(settings, team) as conn:
        return ingestion.upsert_message(conn, team, channel, msg or message(), **kwargs)


def rows(settings, team="T1", channel="C1"):
    with connect(settings, QueryContext("slack", team, (channel,))) as conn:
        return conn.execute("SELECT * FROM messages ORDER BY created_at").fetchall()


def fake_slack(monkeypatch, memberships=None):
    memberships = memberships or {"C1": ["U1"]}

    def call(settings, team, client, method, **params):
        if method == "conversations.members":
            return {"members": memberships.get(params["channel"], []), "response_metadata": {}}
        if method == "users.info":
            return {"user": {"is_admin": True, "tz": "Asia/Kolkata"}}
        if method == "chat.getPermalink":
            return {"permalink": "https://example.slack.com/archives/" + params["channel"] + "/p" + params["message_ts"].replace(".", "")}
        raise AssertionError(method)

    monkeypatch.setattr(commands, "slack_call", call)
    return call


def job_for(settings, text, team="T1", user="U1"):
    return {"team_id": team, "created_at": datetime.now(UTC),
            "payload": {"encrypted": store.encrypt(settings, {"user": user, "channel": "C1", "text": text, "response_url": "https://hooks.slack.com/commands/T1/test"})}}


def test_manifest_has_minimal_bot_scopes_and_one_command():
    result = manifest("https://host.example/recallhq/api/")
    assert result["features"]["slash_commands"][0]["command"] == "/recall"
    assert result["oauth_config"]["redirect_urls"] == ["https://host.example/recallhq/api/slack/oauth_redirect"]
    assert "im:history" not in result["oauth_config"]["scopes"]["bot"]
    with pytest.raises(ValueError):
        manifest("http://localhost:8001")


def test_migrations_are_recorded_once(settings):
    migrate(settings)
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 5


def test_encrypted_installations_and_single_use_oauth_state(settings):
    seed(settings)
    installation_store = store.PostgresInstallationStore(settings)
    assert installation_store.find_bot(team_id="T1").bot_token == "test-bot"
    with store.database(settings) as conn:
        ciphertext = conn.execute("SELECT encrypted_installation FROM slack_installations").fetchone()["encrypted_installation"]
        assert "test-bot" not in ciphertext
    states = store.PostgresStateStore(settings)
    state = states.issue()
    assert states.consume(state)
    assert not states.consume(state)
    expired = states.issue()
    with store.database(settings) as conn:
        conn.execute("UPDATE slack_oauth_states SET expires_at = now() - interval '1 second'")
    assert not states.consume(expired)


def test_oauth_callback_and_reinstall(settings, monkeypatch):
    bolt = slack_app.build_app(settings)
    monkeypatch.setattr(slack_app, "configured_app", lambda: bolt)
    install = Installation(team_id="T1", user_id="U1", bot_token="test-token", bot_user_id="BOT")
    monkeypatch.setattr(bolt.oauth_flow, "run_installation", lambda code: install)
    with TestClient(api.app) as client:
        page = client.get("/slack/install")
        assert page.status_code == 200
        state = store.PostgresStateStore(settings).issue()
        # Bolt binds state to the browser cookie as well as the database state store.
        client.cookies.set("slack-app-oauth-state", state)
        result = client.get("/slack/oauth_redirect", params={"state": state, "code": "mock-code"})
        assert result.status_code == 200
        assert store.PostgresInstallationStore(settings).find_bot(team_id="T1").bot_token == "test-token"
        assert client.get("/slack/oauth_redirect", params={"state": state, "code": "mock-code"}).status_code != 200
        assert client.get("/slack/oauth_redirect", params={"error": "access_denied"}).status_code == 200
    install.bot_token = "reinstalled-token"
    store.PostgresInstallationStore(settings).save(install)
    assert store.PostgresInstallationStore(settings).find_bot(team_id="T1").bot_token == "reinstalled-token"


def signed(body, secret="signing", timestamp=None, content_type="application/json"):
    ts = str(timestamp or int(time.time()))
    signature = hmac.new(secret.encode(), f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
    return BoltRequest(body=body, headers={"x-slack-request-timestamp": ts, "x-slack-signature": "v0=" + signature, "content-type": content_type})


def test_signed_ingress_deduplicates_before_ack(settings):
    seed(settings)
    bolt = slack_app.build_app(settings)
    body = json.dumps({"type": "event_callback", "team_id": "T1", "event_id": "Ev1", "event": {"type": "message", "channel": "C1", **message()}})
    start = time.monotonic()
    assert bolt.dispatch(signed(body)).status == 200
    assert time.monotonic() - start < 3
    assert bolt.dispatch(signed(body)).status == 200
    assert bolt.dispatch(signed(body, "wrong")).status == 401
    assert bolt.dispatch(signed(body, timestamp=int(time.time()) - 600)).status == 401
    with store.database(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM slack_jobs WHERE dedupe_key = 'event:Ev1'").fetchone()["n"] == 1
    challenge = json.dumps({"type": "url_verification", "challenge": "check"})
    assert json.loads(bolt.dispatch(signed(challenge)).body)["challenge"] == "check"


def test_command_ingress_encrypts_urls_and_applies_quotas(settings):
    seed(settings)
    body = {"command": "/recall", "team_id": "T1", "user_id": "U1", "channel_id": "C1", "response_url": "https://hooks.slack.com/commands/T1/secret", "text": "ask storage?", "trigger_id": "trigger"}
    assert slack_app.ingress(settings, body).status == 200
    assert slack_app.ingress(settings, body).status == 200
    with store.database(settings) as conn:
        job = conn.execute("SELECT payload FROM slack_jobs WHERE kind = 'command'").fetchone()
        assert "hooks.slack.com" not in json.dumps(job)
        assert store.decrypt(settings, job["payload"]["encrypted"])["text"] == "ask storage?"
    settings.slack_user_commands_per_minute = 1
    result = slack_app.ingress(settings, {**body, "trigger_id": "another"})
    assert "limit" in result.body


def test_rls_excludes_other_workspaces_channels_and_unscoped_reads(settings):
    seed(settings, "T1", "C1")
    seed(settings, "T1", "C2", "secret")
    seed(settings, "T2", "C1")
    add(settings)
    add(settings, message(text="private"), channel="C2")
    add(settings, message(text="other workspace"), team="T2")
    assert len(rows(settings)) == 1
    assert rows(settings)[0]["text"] == "We chose PostgreSQL for storage"
    with connect(settings, DEMO_CONTEXT) as conn:
        assert conn.execute("SELECT * FROM messages").fetchall() == []
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("SET ROLE recallhq_reader")
        assert conn.execute("SELECT * FROM messages").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM messages")


def test_public_endpoints_cannot_serve_slack_messages(settings):
    seed(settings, "T1", "eng")
    add(settings, channel="eng")
    mid = ingestion.source_id("T1", "eng", message()["ts"])
    with TestClient(api.app) as client:
        assert client.get("/channels").json() == []
        assert client.get("/messages?channel=eng").json()["items"] == []
        assert client.get("/messages/" + mid).status_code == 404
        assert client.get("/threads/" + mid).status_code == 404
        assert client.get("/messages", params={"channel": "eng", "before": mid}).status_code == 400


def test_edits_retries_deletion_tombstones_and_empty_edits(settings):
    seed(settings)
    assert add(settings)
    assert not add(settings)
    changed = {**message(), "text": "We switched to SQLite", "edited": {"ts": "1750000100.000001"}}
    assert add(settings, changed)
    assert not add(settings, message())
    assert rows(settings)[0]["text"] == "We switched to SQLite"
    assert add(settings, {**changed, "text": "", "edited": {"ts": "1750000200.000001"}}, allow_empty=True)
    with store.database(settings, "T1") as conn:
        assert conn.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"] == 0
        ingestion.delete_message(conn, "T1", "C1", message()["ts"], "1750000300.000001")
    assert not add(settings, changed)
    assert rows(settings) == []


def test_thread_updates_deleted_roots_and_long_messages(settings):
    seed(settings)
    root = message()
    reply = message("1750000001.000001", "Approved", thread_ts=root["ts"])
    add(settings, reply)  # Reply can arrive before its parent.
    add(settings, {**root, "reply_count": 1})
    with store.database(settings, "T1") as conn:
        assert conn.execute("SELECT count(*) AS n FROM chunks WHERE kind = 'thread'").fetchone()["n"] == 1
        ingestion.delete_message(conn, "T1", "C1", root["ts"], "1750000300.000001")
        assert conn.execute("SELECT count(*) AS n FROM chunks WHERE kind = 'thread'").fetchone()["n"] == 0
    assert len(rows(settings)) == 1
    long = message("1750000002.000001", "word " * 9000)
    add(settings, long)
    assert rows(settings)[-1]["text"] == long["text"]
    with store.database(settings, "T1") as conn:
        chunks = conn.execute("SELECT text FROM chunks").fetchall()
        assert all(len(ingestion.ENCODER.encode(c["text"])) <= 600 for c in chunks)


def test_embedded_text_compare_and_swap(settings, monkeypatch):
    seed(settings)
    add(settings)

    def create(**kwargs):
        add(settings, {**message(), "text": "new content", "edited": {"ts": "1750000100.000001"}})
        return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.1] * 1536)])

    monkeypatch.setattr(ingestion, "OpenAI", lambda **kwargs: SimpleNamespace(embeddings=SimpleNamespace(create=create)))
    ingestion.embed_channel(settings, "T1", "C1")
    with store.database(settings, "T1") as conn:
        assert conn.execute("SELECT embedding FROM chunks").fetchone()["embedding"] is None


def test_jobs_reclaim_expired_leases_and_reject_stale_completion(settings):
    seed(settings)
    with store.database(settings) as conn:
        store.enqueue(conn, "T1", "event", {}, "one", "C1")
    first = store.claim(settings, ("event",))
    assert store.claim(settings, ("event",)) is None
    with store.database(settings) as conn:
        conn.execute("UPDATE slack_jobs SET lease_until = now() - interval '1 second' WHERE id = %s", (first["id"],))
    second = store.claim(settings, ("event",))
    assert first["lease_token"] != second["lease_token"]
    store.finish(settings, first)
    with store.database(settings) as conn:
        assert conn.execute("SELECT status FROM slack_jobs WHERE id = %s", (first["id"],)).fetchone()["status"] == "processing"
    store.finish(settings, second)
    with store.database(settings) as conn:
        assert conn.execute("SELECT payload FROM slack_jobs WHERE id = %s", (first["id"],)).fetchone()["payload"] == {}


def test_rate_limit_and_quota_reservations_are_durable(settings):
    store.reserve_api(settings, "T1", "conversations.history", 60)
    with pytest.raises(store.RetryLater):
        store.reserve_api(settings, "T1", "conversations.history", 60)
    store.reserve_api(settings, "T2", "conversations.history", 60)
    settings.slack_workspace_commands_per_day = 1
    store.command_quota(settings, "T1", "U1")
    with pytest.raises(ValueError):
        store.command_quota(settings, "T1", "U2")
    with store.database(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM slack_usage WHERE subject = 'user:U2'").fetchone()["n"] == 0


def test_import_paginates_threads_and_reconciles_missing_sources(settings, monkeypatch):
    seed(settings)
    add(settings, message("1740000000.000001", "Deleted during outage"))
    calls = []

    def call(settings, team, client, method, **params):
        calls.append((method, params))
        if method == "conversations.history" and not params["cursor"]:
            return {"messages": [message(reply_count=1)], "response_metadata": {"next_cursor": "page2"}}
        if method == "conversations.history":
            return {"messages": [], "response_metadata": {}}
        if method == "conversations.replies":
            return {"messages": [message(reply_count=1), message("1750000001.000001", "thread reply", thread_ts=message()["ts"])], "response_metadata": {}}
        raise AssertionError(method)

    monkeypatch.setattr(ingestion, "slack_call", call)
    job = {"team_id": "T1", "channel_id": "C1", "payload": {"boundary": "1800000000.000000"}}
    assert ingestion.history_page(settings, job)
    assert not ingestion.history_page(settings, job)
    reply_job = store.claim(settings, ("replies",))
    assert not ingestion.replies_page(settings, reply_job)
    store.finish(settings, reply_job)
    ingestion.complete_import(settings, "T1", "C1")
    assert len(rows(settings)) == 2
    with store.database(settings) as conn:
        assert conn.execute("SELECT import_status FROM slack_channels").fetchone()["import_status"] == "complete"
    assert calls[1][1]["cursor"] == "page2"


def test_failed_import_does_not_delete_unseen_sources(settings):
    seed(settings)
    add(settings)
    with store.database(settings) as conn:
        conn.execute("UPDATE slack_channels SET import_status = 'threads'")
        store.enqueue(conn, "T1", "replies", {}, "failed-reply", "C1")
        conn.execute("UPDATE slack_jobs SET status = 'failed' WHERE kind = 'replies'")
    ingestion.complete_import(settings, "T1", "C1")
    assert len(rows(settings)) == 1


def test_uninstall_revokes_access_immediately_and_purges(settings):
    seed(settings)
    add(settings)
    slack_app.ingress(settings, {"type": "event_callback", "team_id": "T1", "event_id": "uninstall", "event": {"type": "app_uninstalled"}})
    assert store.PostgresInstallationStore(settings).find_bot(team_id="T1") is None
    assert rows(settings) == []  # RLS revocation applies before the asynchronous purge.
    with store.database(settings, "T1") as conn:
        assert conn.execute("SELECT count(*) AS n FROM messages").fetchone()["n"] == 1
    assert not add(settings, message("1750000001.000001", "late event"))
    job = store.claim(settings, ("purge",))
    worker.process(settings, job)
    store.finish(settings, job)
    assert rows(settings) == []
    with store.database(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM chunks WHERE workspace_id = 'T1'").fetchone()["n"] == 0


def test_membership_filters_queries_and_paginates(settings, monkeypatch):
    seed(settings)
    seed(settings, "T1", "C2", "secret")
    fake_slack(monkeypatch, {"C1": ["U1"], "C2": ["U2"]})
    context, allowed = commands.accessible_context(settings, "T1", "U1", object())
    assert context.channel_ids == ("C1",)
    assert allowed == {"C1": "eng"}
    content, filtered = commands.parse_filter("why? in:<#C1|eng>", context, allowed)
    assert content == "why?" and filtered.channel_ids == ("C1",)
    with pytest.raises(ValueError):
        commands.parse_filter("why? in:<#C2|secret>", context, allowed)
    calls = []

    def paginated(settings, team, client, method, **params):
        calls.append(params["cursor"])
        return {"members": ["U1"] if params["cursor"] else ["OTHER"], "response_metadata": {"next_cursor": "next" if not params["cursor"] else ""}}

    monkeypatch.setattr(commands, "slack_call", paginated)
    commands.accessible_context(settings, "T1", "U1", object())
    assert calls == ["", "next", "", "next"]


def test_citation_allowlist_rejects_unknown_slack_ids(monkeypatch):
    row = {"id": "slack:T1:C1:1750000000.000001", "channel": "C1", "author_name": "U1", "created_at": datetime.now(UTC), "text": "decision"}
    text = "Decision [slack:T1:C1:1750000000.000001]"
    monkeypatch.setattr(service, "OpenAI", lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text=text))))
    assert service.answer("q", [row])["sources"] == [row]
    text = "Decision [slack:T2:C1:1750000000.000001]"
    assert service.answer("q", [row])["sources"] == []


def test_commands_cover_help_search_ask_recaps_status_and_admin_actions(settings, monkeypatch):
    seed(settings)
    add(settings)
    fake_slack(monkeypatch)
    evidence = [{**rows(settings)[0], "channel": "C1"}]
    monkeypatch.setattr(service, "retrieve", lambda query, **kwargs: evidence)
    monkeypatch.setattr(service, "answer", lambda question, evidence, **kwargs: {"answer": f"Postgres [{evidence[0]['id']}]" if evidence else "No evidence", "sources": evidence})
    for text in ("help", "ask storage?", "search PostgreSQL", "catchup 2025-06-15 2025-06-16", "decisions", "status", "summarize https://example.slack.com/archives/C1/p1750000000000001", "sync <#C1|eng>"):
        body, _, _, _ = commands.execute(settings, job_for(settings, text))
        assert body["text"]
    body, _, _, _ = commands.execute(settings, job_for(settings, "forget <#C1|eng>"))
    value = body["blocks"][1]["elements"][0]["value"]
    with pytest.raises(ValueError):
        commands.execute(settings, job_for(settings, "forget-confirm " + value, user="OTHER"))
    result, _, _, _ = commands.execute(settings, job_for(settings, "forget-confirm " + value))
    assert "disabled" in result["text"]
    with store.database(settings) as conn:
        assert not conn.execute("SELECT active FROM slack_channels").fetchone()["active"]


def test_invalid_dates_thread_links_and_response_urls():
    from zoneinfo import ZoneInfo
    start, end = commands.date_bounds("2026-09-14 2026-09-18", ZoneInfo("Asia/Kolkata"))
    assert start.utcoffset() == timedelta(hours=5, minutes=30)
    assert (end - start).days == 5
    for content in ("2026-02-30 2026-03-01", "2026-03-02 2026-03-01", "2026-01-01 2026-03-01"):
        with pytest.raises(ValueError):
            commands.date_bounds(content, UTC)
    for url in ("https://evil.example/commands/a", "http://hooks.slack.com/commands/a", "https://hooks.slack.com.evil.example/commands/a"):
        with pytest.raises(ValueError):
            commands.respond(url, {"text": "private"})


def test_access_revocation_before_delivery_suppresses_answer(settings, monkeypatch):
    seed(settings)
    add(settings)
    context = QueryContext("slack", "T1", ("C1",), "U1")
    evidence = [{**rows(settings)[0], "channel": "C1"}]
    job = job_for(settings, "ask q")
    payload = store.decrypt(settings, job["payload"]["encrypted"])
    monkeypatch.setattr(commands, "execute", lambda *args: ({"text": "private decision"}, payload, context, evidence))
    monkeypatch.setattr(commands, "accessible_context", lambda *args: (QueryContext("slack", "T1", (), "U1"), {}))
    delivered = []
    monkeypatch.setattr(commands, "respond", lambda url, body: delivered.append(body))
    commands.deliver(settings, job)
    assert "private decision" not in delivered[0]["text"]
    assert "access changed" in delivered[0]["text"]


def test_form_command_signature_and_private_action_delivery(settings, monkeypatch):
    seed(settings)
    body = urlencode({"command": "/recall", "team_id": "T1", "user_id": "U1", "channel_id": "C1",
                      "text": "status", "response_url": "https://hooks.slack.com/commands/T1/test", "trigger_id": "form"})
    request = signed(body, content_type="application/x-www-form-urlencoded")
    assert slack_app.build_app(settings).dispatch(request).status == 200
    sent = []
    monkeypatch.setattr(commands.httpx, "post", lambda url, **kwargs: sent.append(kwargs) or SimpleNamespace(is_success=True))
    commands.respond("https://hooks.slack.com/actions/T1/test", {"text": "confirmed"})
    assert sent[0]["json"]["response_type"] == "ephemeral"
    assert not sent[0]["follow_redirects"]


def test_authorized_sources_only_reach_generation(settings, monkeypatch):
    seed(settings)
    seed(settings, "T1", "C2", "private")
    seed(settings, "T2", "C1")
    add(settings)
    add(settings, message(text="PostgreSQL private password"), channel="C2")
    add(settings, message(text="PostgreSQL other workspace secret"), team="T2")
    inputs = []
    allowed_id = ingestion.source_id("T1", "C1", message()["ts"])

    def create(**kwargs):
        inputs.append(kwargs["input"])
        return SimpleNamespace(output_text=f"PostgreSQL [{allowed_id}]")

    monkeypatch.setattr(service, "OpenAI", lambda **kwargs: SimpleNamespace(
        embeddings=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 1536)])),
        responses=SimpleNamespace(create=create)))
    evidence = service.retrieve("PostgreSQL", context=QueryContext("slack", "T1", ("C1",), "U1"))
    assert len(evidence) == 1 and evidence[0]["id"] == allowed_id
    service.answer("storage?", evidence)
    assert "private password" not in inputs[0] and "other workspace secret" not in inputs[0]


def test_source_edit_before_delivery_suppresses_stale_answer(settings, monkeypatch):
    seed(settings)
    add(settings)
    evidence = [{**rows(settings)[0], "channel": "C1"}]
    context = QueryContext("slack", "T1", ("C1",), "U1")
    assert commands.still_available(settings, context, evidence)
    add(settings, {**message(), "text": "Changed decision", "edited": {"ts": "1750000100.000001"}})
    assert not commands.still_available(settings, context, evidence)


def test_oauth_codes_are_hidden_from_access_logs():
    import logging
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "%s %s %s %s %s",
                               ("client", "GET", "/slack/oauth_redirect?code=secret&state=private", "1.1", 200), None)
    slack_app.HideOAuthQuery().filter(record)
    assert "secret" not in record.getMessage() and "private" not in record.getMessage()


def test_synthetic_import_retains_scope_across_commit(settings):
    from psycopg.rows import tuple_row

    from recallhq.ingestion.pipeline import build_chunks, import_rows
    row = {"channel": "eng", "local_id": "0001", "author": "priya", "text": "synthetic only",
           "created_at": "2026-09-01T09:00:00+05:30", "parent_id": None, "plants": [], "refs": []}
    story = {"channels": [{"id": "eng", "name": "eng", "platform_style": "slack"}],
             "personas": [{"id": "priya", "name": "Priya"}]}
    chunks, _ = build_chunks([row])
    with connect(settings, DEMO_CONTEXT, write=True) as conn:
        conn.row_factory = tuple_row
        import_rows(conn, [row], chunks, story)
        assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
    with connect(settings, DEMO_CONTEXT) as conn:
        assert conn.execute("SELECT source, workspace_id FROM chunks").fetchone() == {"source": "synthetic", "workspace_id": "beacon"}
