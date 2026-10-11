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
