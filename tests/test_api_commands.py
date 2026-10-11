from datetime import timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from recallhq import api


def test_catchup_uses_corpus_timezone_and_enforces_anonymous_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "QUOTA_DB", tmp_path / "quotas.sqlite3")
    calls = []
    monkeypatch.setattr(api, "retrieve", lambda *args: calls.append(args) or [])
    monkeypatch.setattr(api, "answer", lambda question, evidence: {"answer": "No evidence", "sources": []})
    request = Request({"type": "http", "method": "POST", "path": "/commands", "headers": [], "client": ("192.0.2.1", 1234)})
    payload = api.CommandInput(input="/catchup 2026-09-14 2026-09-18 #eng")

    for _ in range(3):
        assert api.command(payload, request)["kind"] == "answer"
    assert calls[0][1].utcoffset() == timedelta(hours=5, minutes=30)
    assert calls[0][3] == "eng"
    with pytest.raises(HTTPException) as error:
        api.command(payload, request)
    assert error.value.status_code == 429


def _hits(n):
    from datetime import datetime
    return [{"id": f"h{i}", "channel": "eng", "author_name": "A", "created_at": datetime(2026, 9, 1), "text": f"msg {i}"} for i in range(n)]


def test_rerank_orders_top_k_by_score_and_keeps_tail(monkeypatch):
    import io, json
    monkeypatch.setattr(api.SETTINGS, "open_router", "key")
    monkeypatch.setattr(api.SETTINGS, "rerank_top_k", 3)
    body = {"model": "m", "answers": {f"m{i}": {"type": "score", "score": s} for i, s in enumerate([0.5, 2.9, 1.0])}}
    monkeypatch.setattr(api.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(body).encode()))
    assert [h["id"] for h in api.rerank("q", _hits(5))] == ["h1", "h2", "h0", "h3", "h4"]


def test_rerank_falls_back_to_rrf_order_on_error(monkeypatch):
    monkeypatch.setattr(api.SETTINGS, "open_router", "key")
    def fail(*a, **k):
        raise TimeoutError("slow")
    monkeypatch.setattr(api.urllib.request, "urlopen", fail)
    hits = _hits(4)
    assert api.rerank("q", hits) == hits


def test_rerank_uses_fallback_model_when_jev_fails(monkeypatch):
    import io, json
    monkeypatch.setattr(api.SETTINGS, "open_router", "key")
    monkeypatch.setattr(api.SETTINGS, "rerank_top_k", 3)
    models = []
    def urlopen(request, timeout):
        model = json.loads(request.data)["model"]
        models.append(model)
        if model == api.SETTINGS.rerank_model:
            raise TimeoutError("jev down")
        body = {"model": model, "answers": {f"m{i}": {"type": "score", "score": s} for i, s in enumerate([0.0, 1.0, 3.0])}}
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(api.urllib.request, "urlopen", urlopen)
    assert [h["id"] for h in api.rerank("q", _hits(3))] == ["h2", "h1", "h0"]
    assert models == [api.SETTINGS.rerank_model, api.SETTINGS.rerank_fallback_model]
