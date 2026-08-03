from unittest.mock import MagicMock, patch

import jwt
import pytest

from backend.app import supabase_auth


def test_verify_token_raises_when_not_configured():
    supabase_auth._jwk_client = None
    with pytest.raises(RuntimeError):
        supabase_auth.verify_token("some-token")


def test_configure_sets_jwk_client():
    supabase_auth.configure("https://example.supabase.co")
    assert supabase_auth.is_configured()
    supabase_auth._jwk_client = None  # reset for other tests


def test_configure_noop_when_url_empty():
    supabase_auth._jwk_client = None
    supabase_auth.configure("")
    assert not supabase_auth.is_configured()


def test_verify_token_decodes_valid_payload():
    fake_signing_key = MagicMock()
    fake_signing_key.key = "fake-key"

    with patch.object(jwt.PyJWKClient, "get_signing_key_from_jwt", return_value=fake_signing_key), \
         patch.object(jwt, "decode", return_value={"sub": "user-123", "email": "a@b.com"}) as mock_decode:
        supabase_auth.configure("https://example.supabase.co")
        result = supabase_auth.verify_token("fake.jwt.token")

    assert result == {"user_id": "user-123", "email": "a@b.com"}
    mock_decode.assert_called_once()
    supabase_auth._jwk_client = None
