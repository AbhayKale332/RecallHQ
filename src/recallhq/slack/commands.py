"""Permission-aware /recall commands and private Slack responses."""

import html
import logging
import re
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import HTTPException

from recallhq.db import QueryContext, connect
from recallhq.ingestion.pipeline import ENCODER
from recallhq.retrieval import service
from recallhq.slack.ingestion import client_for, slack_call, source_id
from recallhq.slack.store import (
    database,
    decrypt,
    disable,
    encrypt,
    start_import,
)

# HTTPX's INFO messages include the complete credential-bearing Slack response URL.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

HELP = """*RecallHQ commands*
`/recall ask <question> [in:#channel]` — cited answers
`/recall search <terms> [in:#channel]` — matching messages
`/recall catchup YYYY-MM-DD YYYY-MM-DD [in:#channel]` — recap up to 32 days
`/recall summarize <Slack-message-link>` — thread summary
`/recall decisions [in:#channel]` — decisions from the last seven days
`/recall status` — history import and indexing progress
`/recall sync #channel` — admin: retry history import
`/recall forget #channel` — admin: confirm removal of channel data
Replies are private. Searches include only ingested channels you currently belong to.
Invite RecallHQ into a channel to start live capture and automatic history import."""


def accessible_context(settings, team: str, user: str, client):
    with database(settings, team) as conn:
        installed = conn.execute("SELECT active FROM slack_installations WHERE team_id = %s", (team,)).fetchone()
        if not installed or not installed["active"]:
            raise ValueError("Workspace installation is no longer active.")
        channels = conn.execute("SELECT channel_id, name FROM slack_channels WHERE team_id = %s AND active ORDER BY channel_id", (team,)).fetchall()
    allowed = {}
    for channel in channels:
        cursor = ""
        while True:
            response = slack_call(settings, team, client, "conversations.members", channel=channel["channel_id"], limit=200, cursor=cursor)
            if user in response["members"]:
                allowed[channel["channel_id"]] = channel["name"]
                break
            cursor = response.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
    return QueryContext("slack", team, tuple(allowed), user), allowed


def resolve_channel(value: str, allowed: dict[str, str]):
    match = re.fullmatch(r"<#([A-Z0-9]+)(?:\|[^>]+)?>", value)
    channel = match[1] if match else value.removeprefix("#")
    if channel in allowed:
        return channel
    candidates = [cid for cid, name in allowed.items() if name == channel]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("That channel is not ingested or you are not a current member. Invite RecallHQ into it first.")


def parse_filter(text: str, context: QueryContext, allowed: dict):
    match = re.search(r"(?:^|\s)in:(<#[^>]+>|#[^\s]+)\s*$", text)
    if not match:
        return text.strip(), context
    channel = resolve_channel(match[1], allowed)
    return text[:match.start()].strip(), QueryContext("slack", context.workspace_id, (channel,), context.user_id)


def date_bounds(content: str, zone):
    parts = content.split()
    if len(parts) != 2:
        raise ValueError("Use /recall catchup YYYY-MM-DD YYYY-MM-DD [in:#channel].")
    try:
        start, end = (date.fromisoformat(value) for value in parts)
    except ValueError:
        raise ValueError("Use valid dates in YYYY-MM-DD format.") from None
    if end < start or (end - start).days > 31:
        raise ValueError("Choose an inclusive range of up to 32 days.")
    return datetime.combine(start, day_time.min, zone), datetime.combine(end + timedelta(days=1), day_time.min, zone)


def chronological(settings, context: QueryContext, after=None, before=None, root=None, limit=2000):
    evidence, cursor = [], None
    with connect(settings, context) as conn:
        while len(evidence) <= limit:
            filters = ["source = 'slack'", "workspace_id = %s", "channel_id = ANY(%s)"]
            params = [context.workspace_id, list(context.channel_ids)]
            if after:
                filters.append("created_at >= %s")
                params.append(after)
            if before:
                filters.append("created_at < %s")
                params.append(before)
            if root:
                filters.append("(id = %s OR thread_root_id = %s)")
                params.extend((root, root))
            if cursor:
                filters.append("(created_at, id) > (%s, %s)")
                params.extend(cursor)
            rows = conn.execute(f"SELECT {service.MESSAGE_FIELDS} FROM messages WHERE {' AND '.join(filters)} ORDER BY created_at, id LIMIT 200", params).fetchall()
            if not rows:
                break
            evidence.extend(rows)
            cursor = (rows[-1]["created_at"], rows[-1]["id"])
    return evidence[:limit], len(evidence) > limit


def recap(question: str, evidence: list[dict]):
    if not evidence:
        return service.answer(question, [])
    # Bound cost and job duration. Explicitly label any coverage limit to the requester.
    batches, batch, size, truncated = [], [], 0, False
    for row in evidence:
        length = len(ENCODER.encode(row["text"])) + 100
        if size + length > 6000 and batch:
            batches.append(batch)
            batch, size = [], 0
        if len(batches) >= 8:
            truncated = True
            break
        if length > 6000:
            row = {**row, "text": ENCODER.decode(ENCODER.encode(row["text"])[:5800])}
            truncated = True
        batch.append(row)
        size += min(length, 6000)
    if batch:
        batches.append(batch)
    if len(batches) == 1:
        result = service.answer(question, batches[0])
    else:
        summaries = [service.answer(question, rows) for rows in batches]
        sources = {row["id"]: row for summary in summaries for row in summary["sources"]}
        result = service.answer(question, list(sources.values()), condensed_context="\n\n".join(s["answer"] for s in summaries))
    if truncated:
        result["answer"] += "\nCoverage is partial: this recap reached its message/context budget. Use a smaller date range or a channel filter."
    originals = {row["id"]: row for row in evidence}
    result["sources"] = [originals[row["id"]] for row in result["sources"]]
    return result


def thread_from_link(settings, context: QueryContext, value: str):
    value = value.strip().removeprefix("<").removesuffix(">")
    value = value.split("|", 1)[0]
    url = urlsplit(value)
    match = re.fullmatch(r"/archives/([A-Z0-9]+)/p(\d{10,})(?:/)?", url.path)
    if url.scheme != "https" or not url.hostname or not url.hostname.endswith(".slack.com") or not match:
        raise ValueError("Provide a Slack message link, such as https://workspace.slack.com/archives/C…/p… .")
    channel, digits = match[1], match[2]
    if channel not in context.channel_ids:
        raise ValueError("You do not have access to that ingested channel.")
    mid = source_id(context.workspace_id, channel, digits[:-6] + "." + digits[-6:])
    with connect(settings, context) as conn:
        row = conn.execute("SELECT id, thread_root_id FROM messages WHERE id = %s", (mid,)).fetchone()
    if not row:
        raise ValueError("That message has not been imported, or it was deleted. Check /recall status.")
    return row["thread_root_id"] or row["id"]


def verify_admin(settings, team, user, client):
    info = slack_call(settings, team, client, "users.info", user=user)["user"]
    if info.get("deleted") or not (info.get("is_admin") or info.get("is_owner")):
        raise ValueError("This command requires a workspace admin or owner.")


def still_available(settings, context, evidence):
    if not evidence:
        return True
    with connect(settings, context) as conn:
        rows = conn.execute(f"SELECT {service.MESSAGE_FIELDS} FROM messages WHERE id = ANY(%s)", ([r["id"] for r in evidence],)).fetchall()
    current = {r["id"]: r for r in rows}
    return all(r["id"] in current and current[r["id"]]["text"] == r["text"]
               and current[r["id"]]["source_revision"] == r["source_revision"] for r in evidence)


def render_answer(settings, team, client, result):
    text = html.escape(result["answer"], quote=False)
    for row in result["sources"]:
        link = row.get("permalink")
        if not link:
            link = slack_call(settings, team, client, "chat.getPermalink", channel=row["channel"], message_ts=row["id"].rsplit(":", 1)[-1])["permalink"]
            with database(settings, team) as conn:
                conn.execute("UPDATE messages SET permalink = %s WHERE id = %s", (link, row["id"]))
        safe = urlsplit(link)
        if safe.scheme != "https" or not safe.hostname or not safe.hostname.endswith(".slack.com"):
            raise ValueError("Slack returned an invalid message permalink.")
        text = text.replace("[" + row["id"] + "]", f"<{link}|source>")
    return text


def execute(settings, job):
    payload = decrypt(settings, job["payload"]["encrypted"])
    team, user, text = job["team_id"], payload["user"], payload["text"]
    parts = text.split(maxsplit=1)
    name, content = (parts[0].lower() if parts else "help"), (parts[1] if len(parts) > 1 else "")
    client, _ = client_for(settings, team)
    if name == "help":
        return {"text": HELP}, payload, None, []
    if name not in ("ask", "search", "catchup", "summarize", "decisions", "status", "sync", "forget", "forget-confirm"):
        raise ValueError("Unknown command. Use /recall help.")
    context, allowed = accessible_context(settings, team, user, client)
    content, filtered = parse_filter(content, context, allowed)
    if name == "forget-confirm":
        confirm = decrypt(settings, content)
        if confirm.get("team") != team or confirm.get("user") != user or time.time() - confirm.get("created", 0) > 600:
            raise ValueError("This confirmation is invalid or expired. Run /recall forget again.")
        verify_admin(settings, team, user, client)
        channel = resolve_channel(confirm["channel"], allowed)
        with database(settings, team) as conn:
            disable(conn, team, channel)
        return {"text": "Channel ingestion is disabled and its stored data is queued for deletion."}, payload, None, []
    if name in ("sync", "forget"):
        verify_admin(settings, team, user, client)
        channel = resolve_channel(content, allowed)
        if name == "forget":
            value = encrypt(settings, {"team": team, "user": user, "channel": channel, "created": time.time()})
            return {"text": "Confirm channel removal", "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Delete RecallHQ’s stored messages and embeddings for <#{channel}>? Ingestion stays disabled until the bot is removed and reinvited."}},
                {"type": "actions", "elements": [{"type": "button", "action_id": "recall_forget_confirm", "text": {"type": "plain_text", "text": "Delete channel data"}, "style": "danger", "value": value}]}]}, payload, context, []
        with database(settings, team) as conn:
            start_import(conn, team, channel)
        return {"text": "History import has been queued. Use /recall status to check progress."}, payload, context, []
    if name == "status":
        with database(settings, team) as conn:
            rows = conn.execute("""SELECT c.channel_id, c.import_status, c.last_ingested_at, c.last_error,
                                  (SELECT count(*) FROM messages m WHERE m.workspace_id = c.team_id AND m.channel_id = c.channel_id AND m.source = 'slack') AS messages,
                                  (SELECT count(*) FROM chunks k WHERE k.workspace_id = c.team_id AND k.channel_id = c.channel_id AND k.source = 'slack' AND k.embedding IS NULL) AS pending_embeddings
                                  FROM slack_channels c WHERE c.team_id = %s AND c.active AND c.channel_id = ANY(%s) ORDER BY c.channel_id""", (team, list(context.channel_ids))).fetchall()
        lines = [f"<#{r['channel_id']}>: {r['messages']} messages; history {r['import_status']}; {r['pending_embeddings']} chunks awaiting embeddings" + (f"; last error: {r['last_error']}" if r["last_error"] else "") for r in rows]
        return {"text": "\n".join(lines) or "No ingested channels are available to you. Invite RecallHQ into a channel first."}, payload, context, []
    if not filtered.channel_ids:
        raise ValueError("No ingested channels are available to you. Invite RecallHQ into a channel first.")
    if name in ("ask", "search"):
        if not content or len(content) > 1200:
            raise ValueError(f"Use /recall {name} followed by 1–1200 characters.")
        evidence = service.rerank(content, service.retrieve(content, context=filtered))
        if name == "search":
            result = {"answer": "\n\n".join(f"[{r['id']}] {r['author_name']}: {r['text'][:350]}" for r in evidence) or "No matching messages found.", "sources": evidence}
        else:
            result = service.answer(content, evidence)
    else:
        info = slack_call(settings, team, client, "users.info", user=user)["user"]
        try:
            zone = ZoneInfo(info.get("tz") or "UTC")
        except ZoneInfoNotFoundError:
            zone = UTC
        if name == "summarize":
            root = thread_from_link(settings, filtered, content)
            evidence, partial = chronological(settings, filtered, root=root)
            question = "Summarize this thread, including decisions, disagreements, blockers, and next steps."
        else:
            if name == "catchup":
                after, before = date_bounds(content, zone)
                question = "Summarize updates, decisions, blockers, and next steps in this date range."
            else:
                if content:
                    raise ValueError("Use /recall decisions [in:#channel].")
                before = datetime.now(zone)
                after = before - timedelta(days=7)
                question = "List explicit decisions from the last seven days. Identify owners only when the messages state them."
            evidence, partial = chronological(settings, filtered, after, before)
        result = recap(question, evidence)
        if partial:
            result["answer"] += "\nCoverage is partial: more than 2,000 messages matched. Narrow the date range or channel."
    with database(settings, team) as conn:
        pending = conn.execute("SELECT 1 FROM slack_channels WHERE team_id = %s AND channel_id = ANY(%s) AND import_status <> 'complete' LIMIT 1", (team, list(filtered.channel_ids))).fetchone()
    if pending:
        result["answer"] += "\nHistory import is incomplete. This response uses currently indexed messages; check /recall status."
    return {"text": render_answer(settings, team, client, result)}, payload, filtered, result["sources"]


def respond(url: str, body: dict):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "hooks.slack.com" or parsed.port not in (None, 443) or parsed.username or parsed.password or not parsed.path.startswith(("/commands/", "/actions/")):
        raise ValueError("Invalid Slack response URL")
    # Do not follow redirects, expose response_url credentials, or create public messages.
    response = httpx.post(url, json={**body, "response_type": "ephemeral", "replace_original": False}, timeout=20, follow_redirects=False)
    if not response.is_success:
        raise ValueError("Slack response delivery failed")


def deliver(settings, job):
    payload = decrypt(settings, job["payload"]["encrypted"])
    if datetime.now(UTC) - job["created_at"] > timedelta(minutes=25):
        return
    try:
        body, payload, context, evidence = execute(settings, job)
        if context:
            client, _ = client_for(settings, job["team_id"])
            refreshed, _ = accessible_context(settings, job["team_id"], payload["user"], client)
            if not set(context.channel_ids).issubset(refreshed.channel_ids) or not still_available(settings, refreshed, evidence):
                body = {"text": "The evidence or your channel access changed while processing. Please run the command again."}
        # Block Kit and response URLs have practical size limits. Keep private output bounded.
        if "text" in body and len(body["text"]) > 12000:
            body["text"] = body["text"][:11900] + "\nResponse shortened. Narrow the question or date range."
        respond(payload["response_url"], body)
    except ValueError as exc:
        respond(payload["response_url"], {"text": html.escape(str(exc), quote=False)})
    except HTTPException:
        respond(payload["response_url"], {"text": "Search is temporarily unavailable. Please try again later."})
