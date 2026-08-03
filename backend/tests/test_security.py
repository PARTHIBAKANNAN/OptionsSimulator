from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app import security


def test_login_user_sets_session():
    request = SimpleNamespace(session={})
    security.login_user(request, {"user_id": "u1", "email": "a@b.com"})
    assert request.session["user"] == {"user_id": "u1", "email": "a@b.com"}


def test_logout_user_clears_session():
    request = SimpleNamespace(session={"user": {"user_id": "u1"}})
    security.logout_user(request)
    assert "user" not in request.session


def test_current_user_returns_none_when_absent():
    request = SimpleNamespace(session={})
    assert security.current_user(request) is None


def test_require_login_raises_401_when_absent():
    request = SimpleNamespace(session={})
    with pytest.raises(HTTPException) as exc_info:
        security.require_login(request)
    assert exc_info.value.status_code == 401


def test_require_login_returns_user_when_present():
    request = SimpleNamespace(session={"user": {"user_id": "u1"}})
    assert security.require_login(request) == {"user_id": "u1"}


def test_is_authenticated_ws():
    ws_authed = SimpleNamespace(session={"user": {"user_id": "u1"}})
    ws_anon = SimpleNamespace(session={})
    assert security.is_authenticated_ws(ws_authed) is True
    assert security.is_authenticated_ws(ws_anon) is False
