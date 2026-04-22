import base64
import json
import os
import tempfile

from agents.meta_agent import auth


def test_decode_access_token_rejects_unsigned_base64_token(monkeypatch):
    monkeypatch.setattr(auth, "SECRET_KEY", "test-secret")
    forged = json.dumps(
        {
            "email": "attacker@example.com",
            "plan": "owner",
            "is_owner": True,
            "is_admin": True,
        }
    ).encode("utf-8")
    # This format used to be accepted when auth tokens were plain base64 JSON.
    token = base64.b64encode(forged).decode("utf-8")
    assert auth.decode_access_token(token) is None


def test_make_token_and_decode_round_trip(monkeypatch):
    monkeypatch.setattr(auth, "SECRET_KEY", "test-secret")
    token = auth.make_token("user@example.com", "professional", False)
    payload = auth.decode_access_token(token)
    assert payload is not None
    assert payload["email"] == "user@example.com"
    assert payload["plan"] == "professional"
    assert payload["is_owner"] is False


def test_load_users_returns_mapping_for_legacy_callers(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        users_file = os.path.join(tmp, "users.jsonl")
        monkeypatch.setattr(auth, "USERS_FILE", auth.Path(users_file))
        auth.save_user(
            {
                "email": "mapped@example.com",
                "name": "mapped",
                "password_hash": auth.hash_password("secret123"),
                "plan": "free",
            }
        )
        loaded = auth.load_users()
        assert isinstance(loaded, dict)
        assert loaded["mapped@example.com"]["email"] == "mapped@example.com"
