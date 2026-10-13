"""Bolt OAuth and signed, durable HTTP ingress. No LLM work runs before acknowledgement."""

import hashlib
import json
import logging
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request
from slack_bolt import App
from slack_bolt.adapter.starlette.handler import to_bolt_request, to_starlette_response
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_bolt.response import BoltResponse
from starlette.concurrency import run_in_threadpool

from recallhq.config import Settings
from recallhq.slack.manifest import SCOPES, manifest
from recallhq.slack.store import (
    PostgresInstallationStore,
    PostgresStateStore,
    command_quota,
    database,
    disable,
    encrypt,
    enqueue,
)

router = APIRouter(prefix="/slack")


class HideOAuthQuery(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            record.args = (client, method, path.split("?", 1)[0], version, status)
        return True


logging.getLogger("uvicorn.access").addFilter(HideOAuthQuery())


def ephemeral(text: str):
    return BoltResponse(status=200, body={"response_type": "ephemeral", "text": text})


def ingress(settings: Settings, body: dict):
    if body.get("type") == "url_verification":
        return BoltResponse(status=200, body={"challenge": body["challenge"]})
    team = body.get("team_id") or body.get("team", {}).get("id")
    if not team:
        return BoltResponse(status=400, body="Missing workspace")
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        event_id = body.get("event_id")
        if not event_id or not event.get("type"):
            return BoltResponse(status=400, body="Invalid event")
        channel = event.get("channel")
        if isinstance(channel, dict):
            channel = channel.get("id")
        with database(settings, team) as conn:
            conn.execute("SET LOCAL lock_timeout = '750ms'")
            conn.execute("SET LOCAL statement_timeout = '1500ms'")
            installed = conn.execute("SELECT active, bot_user_id FROM slack_installations WHERE team_id = %s FOR UPDATE", (team,)).fetchone()
            if not installed or not installed["active"]:
                return BoltResponse(status=200, body="")
            if conn.execute("SELECT 1 FROM slack_jobs WHERE dedupe_key = %s", ("event:" + event_id,)).fetchone():
                return BoltResponse(status=200, body="")
            kind = event["type"]
            if kind == "app_uninstalled" or (kind == "tokens_revoked" and event.get("tokens", {}).get("bot")):
                disable(conn, team)
            elif (kind == "member_left_channel" and event.get("user") == installed["bot_user_id"]) or kind in ("channel_deleted", "group_deleted", "channel_archive", "group_archive"):
                disable(conn, team, channel)
            elif kind in ("channel_rename", "group_rename"):
                conn.execute("UPDATE slack_channels SET name = %s WHERE team_id = %s AND channel_id = %s", (event["channel"]["name"], team, channel))
            else:
                enqueue(conn, team, "event", {"event": event}, "event:" + event_id, channel)
                return BoltResponse(status=200, body="")
            # Preserve deduplication for lifecycle events without retaining their payload.
            enqueue(conn, team, "noop", {}, "event:" + event_id, channel)
        return BoltResponse(status=200, body="")
    if body.get("command") != "/recall" and body.get("type") != "block_actions":
        return BoltResponse(status=400, body="Unsupported request")
    user = body.get("user_id") or body.get("user", {}).get("id")
    channel = body.get("channel_id") or body.get("channel", {}).get("id")
    response_url = body.get("response_url", "")
    text = body.get("text", "help").strip()
    if body.get("type") == "block_actions":
        actions = body.get("actions", [])
        if len(actions) != 1 or actions[0].get("action_id") != "recall_forget_confirm":
            return BoltResponse(status=400, body="Unsupported action")
        text = "forget-confirm " + actions[0].get("value", "")
    if not user or not response_url or len(text) > 4000:
        return ephemeral("Use /recall help for command syntax.")
    trigger = body.get("trigger_id") or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    dedupe = "command:" + trigger
    try:
        with database(settings, team) as conn:
            conn.execute("SET LOCAL lock_timeout = '750ms'")
            conn.execute("SET LOCAL statement_timeout = '1500ms'")
            installed = conn.execute("SELECT 1 FROM slack_installations WHERE team_id = %s AND active FOR SHARE", (team,)).fetchone()
            if not installed:
                return ephemeral("Install RecallHQ through /slack/install before running commands.")
            if conn.execute("SELECT 1 FROM slack_jobs WHERE dedupe_key = %s", (dedupe,)).fetchone():
                return BoltResponse(status=200, body="")
            command_quota(settings, team, user, conn)
            payload = {"user": user, "channel": channel, "text": text, "response_url": response_url}
            enqueue(conn, team, "command", {"encrypted": encrypt(settings, payload)}, dedupe, channel)
    except ValueError as exc:
        return ephemeral(str(exc))
    return ephemeral("RecallHQ is working on your request…")


def build_app(settings: Settings):
    manifest(settings.slack_public_url)  # Validate HTTPS before generating OAuth URLs.
    store = PostgresInstallationStore(settings)

    def durable_ingress(body):
        return ingress(settings, body)

    return App(signing_secret=settings.slack_signing_secret,
               token_verification_enabled=False, before_authorize=durable_ingress,
               oauth_settings=OAuthSettings(client_id=settings.slack_client_id, client_secret=settings.slack_client_secret,
                   scopes=SCOPES, installation_store=store, state_store=PostgresStateStore(settings),
                   redirect_uri=settings.slack_public_url.rstrip("/") + "/slack/oauth_redirect",
                   install_path="/slack/install", redirect_uri_path="/slack/oauth_redirect"))


@lru_cache(maxsize=1)
def configured_app():
    settings = Settings()
    if not settings.slack_enabled:
        raise HTTPException(503, "Slack is not configured. See docs/slack-bot.md.")
    return build_app(settings)


@router.get("/install")
async def install(request: Request):
    flow = configured_app().oauth_flow
    result = await run_in_threadpool(flow.handle_installation, to_bolt_request(request, b""))
    return to_starlette_response(result)


@router.get("/oauth_redirect")
async def oauth_redirect(request: Request):
    flow = configured_app().oauth_flow
    result = await run_in_threadpool(flow.handle_callback, to_bolt_request(request, b""))
    return to_starlette_response(result)


@router.post("/events")
async def events(request: Request):
    body = bytearray()
    async for part in request.stream():
        if len(body) + len(part) > 1_000_000:
            raise HTTPException(413, "Slack payload too large")
        body.extend(part)
    result = await run_in_threadpool(configured_app().dispatch, to_bolt_request(request, bytes(body)))
    return to_starlette_response(result)
