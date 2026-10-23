import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from discord_identity import (
    ME_URL,
    REDIRECT_URI,
    TOKEN_URL,
    avatar_cache_path,
    avatar_url,
    exchange_code_for_identity,
    identity_data_dir,
    load_verified_accounts,
    save_verified_accounts,
)


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class DiscordIdentityTests(unittest.TestCase):
    def test_custom_and_default_avatar_urls(self):
        self.assertEqual(
            avatar_url("123456789012345678", "a_hash"),
            "https://cdn.discordapp.com/avatars/123456789012345678/a_hash.gif?size=128",
        )
        self.assertTrue(
            avatar_url("123456789012345678", "").startswith(
                "https://cdn.discordapp.com/embed/avatars/"
            )
        )
        self.assertEqual(avatar_url("bad-id", "hash"), "")

    def test_exchange_requests_identify_only_and_returns_no_auth_values(self):
        requests = []

        def opener(request, timeout):
            requests.append(request)
            if request.full_url == TOKEN_URL:
                return FakeResponse(json.dumps({
                    "access_token": "temporary-oauth-access-token",
                    "refresh_token": "temporary-refresh-token",
                    "scope": "identify",
                }).encode())
            if request.full_url == ME_URL:
                self.assertEqual(request.get_header("Authorization"), "Bearer temporary-oauth-access-token")
                return FakeResponse(json.dumps({
                    "id": "123456789012345678",
                    "username": "qa_account",
                    "global_name": "QA Account",
                    "avatar": "avatar_hash",
                    "discriminator": "0",
                }).encode())
            self.fail(f"Unexpected request URL: {request.full_url}")

        with patch("discord_identity.urllib.request.urlopen", side_effect=AssertionError("unexpected global opener")):
            profile = exchange_code_for_identity(
                client_id="123456789012345678",
                client_secret="app-client-secret",
                code="short-lived-auth-code",
                opener=opener,
            )

        self.assertEqual(profile["username"], "qa_account")
        self.assertEqual(profile["global_name"], "QA Account")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].full_url, TOKEN_URL)
        self.assertEqual(requests[0].get_method(), "POST")
        body = requests[0].data.decode("ascii")
        self.assertIn("client_secret=app-client-secret", body)
        self.assertIn("redirect_uri=" + __import__("urllib.parse").parse.quote(REDIRECT_URI, safe=""), body)
        self.assertEqual(requests[1].full_url, ME_URL)
        self.assertEqual(requests[1].get_header("Authorization"), "Bearer temporary-oauth-access-token")
        self.assertFalse({"access_token", "refresh_token", "client_secret", "code"} & profile.keys())

    def test_exchange_rejects_missing_identify_scope(self):
        def opener(request, timeout):
            return FakeResponse(json.dumps({
                "access_token": "temporary-token",
                "scope": "guilds",
            }).encode())

        from discord_identity import IdentityVerificationError
        with self.assertRaises(IdentityVerificationError):
            exchange_code_for_identity(
                client_id="123456789012345678",
                client_secret="app-client-secret",
                code="one-time-code",
                opener=opener,
            )

    def test_saved_identity_store_is_allowlisted_and_round_trips_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "verified_accounts.json"
            save_verified_accounts([{
                "id": "123456789012345678",
                "username": "qa_account",
                "global_name": "QA Account",
                "avatar": "avatar_hash",
                "label": "TEST ACCOUNT",
                "access_token": "must-not-persist",
                "refresh_token": "must-not-persist",
                "client_secret": "must-not-persist",
                "cookie": "must-not-persist",
                "token": "must-not-persist",
            }], store)

            raw = store.read_text(encoding="utf-8")
            self.assertNotIn("must-not-persist", raw)
            self.assertNotIn("access_token", raw)
            self.assertNotIn("client_secret", raw)
            loaded = load_verified_accounts(store)
            self.assertEqual(loaded, [{
                "id": "123456789012345678",
                "username": "qa_account",
                "global_name": "QA Account",
                "avatar": "avatar_hash",
                "label": "TEST ACCOUNT",
            }])

    def test_saved_identity_store_rejects_invalid_ids_and_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "verified_accounts.json"
            save_verified_accounts([
                {"id": "not-an-id", "username": "bad"},
                {"id": "987654321098765432", "username": "okay", "label": ["bad"]},
            ], store)
            self.assertEqual(load_verified_accounts(store), [{
                "id": "987654321098765432",
                "username": "okay",
                "global_name": "",
                "avatar": "",
                "label": "Unlabeled",
            }])

    def test_avatar_cache_is_outside_project_and_requires_numeric_id(self):
        self.assertTrue(str(identity_data_dir()).endswith("IVXDiscordLab"))
        self.assertTrue(str(avatar_cache_path("123456789012345678")).endswith("123456789012345678.png"))
        with self.assertRaises(ValueError):
            avatar_cache_path("../unsafe")


if __name__ == "__main__":
    unittest.main()
