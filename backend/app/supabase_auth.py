"""Verifies Supabase Auth JWTs via symmetric secret, public JWKS endpoint, or Supabase user API."""
import json
import urllib.request
import urllib.error
import jwt

_jwk_client: jwt.PyJWKClient | None = None
_jwt_secret: str | None = None
_supabase_url: str | None = None


def configure(supabase_url: str, jwt_secret: str = "") -> None:
    global _jwk_client, _jwt_secret, _supabase_url
    _supabase_url = supabase_url.strip().rstrip("/") or None
    _jwt_secret = jwt_secret.strip() or None
    if _supabase_url:
        _jwk_client = jwt.PyJWKClient(
            f"{_supabase_url}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=86400,
            timeout=10.0,
        )
    else:
        _jwk_client = None


def is_configured() -> bool:
    return _jwk_client is not None or _jwt_secret is not None or _supabase_url is not None


def verify_token(token: str) -> dict:
    if not is_configured():
        raise RuntimeError("Supabase auth not configured (SUPABASE_URL or SUPABASE_JWT_SECRET missing)")

    last_error: Exception | None = None

    # 1. If JWT secret is provided, try verifying with HS256 first (instant local decode, 0ms latency)
    if _jwt_secret:
        try:
            payload = jwt.decode(
                token,
                _jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            return {"user_id": payload["sub"], "email": payload.get("email")}
        except jwt.InvalidTokenError as e:
            last_error = e

    # 2. Fall back to JWKS (ES256 / RS256)
    if _jwk_client:
        try:
            signing_key = _jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
            return {"user_id": payload["sub"], "email": payload.get("email")}
        except Exception as e:
            last_error = e

    # 3. Direct REST verification fallback against Supabase /auth/v1/user
    if _supabase_url:
        try:
            req = urllib.request.Request(
                f"{_supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "OptionsSimulator-Auth/1.0",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    user_id = data.get("id") or data.get("sub")
                    if user_id:
                        return {"user_id": user_id, "email": data.get("email")}
        except urllib.error.HTTPError as e:
            raise ValueError(f"Supabase auth rejected token: HTTP {e.code}") from e
        except Exception as e:
            last_error = e

    raise ValueError(f"Failed to verify token with configured auth methods: {last_error}")

