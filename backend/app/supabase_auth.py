"""Verifies Supabase Auth JWTs via Supabase's public JWKS endpoint — no shared secret needed."""
import jwt

_jwk_client: jwt.PyJWKClient | None = None


def configure(supabase_url: str) -> None:
    global _jwk_client
    if supabase_url:
        _jwk_client = jwt.PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")


def is_configured() -> bool:
    return _jwk_client is not None


def verify_token(token: str) -> dict:
    if _jwk_client is None:
        raise RuntimeError("Supabase auth not configured (SUPABASE_URL missing)")
    signing_key = _jwk_client.get_signing_key_from_jwt(token)
    payload = jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated")
    return {"user_id": payload["sub"], "email": payload.get("email")}
