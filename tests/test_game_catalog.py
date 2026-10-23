import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from game_catalog import CATALOG_URLS, FALLBACK_GAMES, fetch_detectable_games, normalize_game_catalog


class GameCatalogTests(unittest.TestCase):
    def test_normalizes_catalog_and_prefers_windows_executables(self):
        payload = [
            {
                "id": "20",
                "name": "Zeta Game",
                "executables": [
                    {"name": "zeta.exe", "os": "win32"},
                    {"name": "zeta.app", "os": "darwin"},
                ],
            },
            {
                "id": "10",
                "name": "Alpha Game",
                "executables": [],
            },
            {
                "id": "30",
                "name": "Linux Only",
                "executables": [{"name": "linux-game", "os": "linux"}],
            },
            {
                "id": "20",
                "name": "Duplicate Zeta",
                "executables": [{"name": "other.exe", "os": "win32"}],
            },
            None,
            {"name": ""},
        ]

        result = normalize_game_catalog(payload)

        self.assertEqual([game["name"] for game in result], ["Alpha Game", "Zeta Game"])
        zeta = next(game for game in result if game["name"] == "Zeta Game")
        self.assertEqual(zeta["executable"], "zeta.exe")
        alpha = next(game for game in result if game["name"] == "Alpha Game")
        self.assertEqual(alpha["executable"], "Executable not listed")

    def test_fetch_uses_public_endpoint_fallback_and_saves_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "catalog.json"
            calls = []

            def opener(request, timeout):
                calls.append((request.full_url, timeout, request.get_header("Authorization")))
                if len(calls) == 1:
                    raise URLError("CDN not reachable")
                body = json.dumps([
                    {
                        "id": "123",
                        "name": "Example Game",
                        "executables": [{"name": "example.exe", "os": "win32"}],
                    }
                ]).encode()
                return io.BytesIO(body)

            games, source, diagnostic = fetch_detectable_games(
                timeout=1.25,
                cache_file=cache,
                opener=opener,
            )

            self.assertEqual(games[0]["name"], "Example Game")
            self.assertEqual(source, CATALOG_URLS[1][0])
            self.assertIn("Loaded 1 games", diagnostic)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][0], CATALOG_URLS[0][1])
            self.assertEqual(calls[1][0], CATALOG_URLS[1][1])
            self.assertTrue(all(auth is None for _, _, auth in calls))
            self.assertTrue(cache.is_file())
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8"))[0]["id"], "123")

    def test_uses_cache_if_all_public_endpoints_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "catalog.json"
            cache.write_text(
                json.dumps([{"id": "cache-1", "name": "Cached Game", "executables": []}]),
                encoding="utf-8",
            )

            def offline_opener(request, timeout):
                raise URLError("offline")

            games, source, diagnostic = fetch_detectable_games(
                timeout=0.1,
                cache_file=cache,
                opener=offline_opener,
            )
            self.assertEqual(source, "Cached catalog")
            self.assertEqual(games[0]["name"], "Cached Game")
            self.assertIn("could not be refreshed", diagnostic)

    def test_uses_builtin_fallback_when_network_and_cache_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "missing" / "catalog.json"

            def offline_opener(request, timeout):
                raise URLError("offline")

            games, source, diagnostic = fetch_detectable_games(
                timeout=0.1,
                cache_file=cache,
                opener=offline_opener,
            )
            self.assertEqual(source, "Built-in fallback")
            self.assertEqual(len(games), len(FALLBACK_GAMES))
            self.assertIn("Check your connection", diagnostic)
            self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
