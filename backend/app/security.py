"""
Session-cookie login gate. The browser verifies against Supabase Auth directly and gets a JWT,
then POSTs it once to /api/auth/login here — we verify it and mint a signed session cookie.
Everything after that (including the WebSocket, which can't carry a custom Authorization header)
just rides the cookie via `credentials: "include"`.
"""
from fastapi import HTTPException, Request, WebSocket


def login_user(request: Request, user: dict) -> None:
    request.session["user"] = user


def logout_user(request: Request) -> None:
    request.session.pop("user", None)


def current_user(request: Request) -> dict | None:
    return request.session.get("user")


def require_login(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def is_authenticated_ws(websocket: WebSocket) -> bool:
    return websocket.session.get("user") is not None
