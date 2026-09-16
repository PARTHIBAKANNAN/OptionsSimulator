"""Verifies Supabase Auth JWTs via symmetric secret or Supabase's public JWKS endpoint."""
import jwt

_jwk_client: jwt.PyJWKClient | None = None
_jwt_secret: str | None = None


def configure(supabase_url: str, jwt_secret: str = "") -> None:
    global _jwk_client, _jwt_secret
    _jwt_secret = jwt_secret.strip() or None
    if supabase_url:
        _jwk_client = jwt.PyJWKClient(
            f"{supabase_url}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=86400,
            timeout=10.0,
        )
    else:
        _jwk_client = None


def is_configured() -> bool:
    return _jwk_client is not None or _jwt_secret is not None


def verify_token(token: str) -> dict:
    if not is_configured():
        raise RuntimeError("Supabase auth not configured (SUPABASE_URL or SUPABASE_JWT_SECRET missing)")

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
        except jwt.InvalidTokenError:
            if not _jwk_client:
                raise

    # 2. Fall back to JWKS (ES256 / RS256)
    if _jwk_client:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return {"user_id": payload["sub"], "email": payload.get("email")}

    raise ValueError("Failed to verify token with configured auth methods")
