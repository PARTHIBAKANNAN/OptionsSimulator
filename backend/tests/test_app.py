from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_ok():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["mode"] == "replay"  # DATA_ENGINE_ENABLED=false in this repo's .env


def test_snapshot_requires_login():
    with TestClient(app) as client:
        resp = client.get("/api/snapshot")
        assert resp.status_code == 401


def test_paper_positions_requires_login():
    with TestClient(app) as client:
        resp = client.get("/api/paper/positions")
        assert resp.status_code == 401


def test_me_requires_login():
    with TestClient(app) as client:
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


def test_login_flow_sets_session_cookie_and_unlocks_gated_routes():
    with patch("backend.app.main.supabase_auth.verify_token",
               return_value={"user_id": "u1", "email": "a@b.com"}):
        with TestClient(app) as client:
            login_resp = client.post("/api/auth/login", json={"access_token": "fake-token"})
            assert login_resp.status_code == 200
            assert login_resp.json() == {"user_id": "u1", "email": "a@b.com"}

            me_resp = client.get("/api/auth/me")
            assert me_resp.status_code == 200
            assert me_resp.json()["user_id"] == "u1"

            positions_resp = client.get("/api/paper/positions")
            assert positions_resp.status_code == 200
            assert isinstance(positions_resp.json(), list)

            logout_resp = client.post("/api/auth/logout")
            assert logout_resp.status_code == 200

            me_after_logout = client.get("/api/auth/me")
            assert me_after_logout.status_code == 401


def test_login_rejects_invalid_token():
    with patch("backend.app.main.supabase_auth.verify_token", side_effect=Exception("bad token")):
        with TestClient(app) as client:
            resp = client.post("/api/auth/login", json={"access_token": "garbage"})
            assert resp.status_code == 401


def test_login_requires_access_token_field():
    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400


def test_backtest_report_requires_login():
    with TestClient(app) as client:
        resp = client.get("/api/backtest/report")
        assert resp.status_code == 401


def test_ws_stream_rejects_unauthenticated():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/stream") as ws:
            # Server accepts then immediately closes with 4401 since there's no session cookie.
            data = ws.receive()
            assert data.get("type") == "websocket.close"
            assert data.get("code") == 4401
