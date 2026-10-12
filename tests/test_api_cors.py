import pytest
from fastapi.testclient import TestClient

from recallhq.api import app


@pytest.mark.parametrize("origin", [
    "https://recall.abhaykale.me",
    "https://recallhq-black.vercel.app",
    "http://localhost:3000",
])
def test_frontend_origins_can_read_and_send_commands(origin):
    with TestClient(app) as client:
        preflight = client.options("/commands", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin

        response = client.get("/messages?channel=unknown", headers={"Origin": origin})
        assert response.status_code == 404
        assert response.headers["access-control-allow-origin"] == origin


def test_unapproved_origin_is_rejected():
    with TestClient(app) as client:
        response = client.options("/commands", headers={
            "Origin": "https://recall.abhaykale.me.attacker.example",
            "Access-Control-Request-Method": "POST",
        })
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
