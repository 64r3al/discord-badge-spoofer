"""Read the public Discord detectable-game catalog for the Activity Lab picker.

This module fetches public game metadata only. It never authenticates, reads account data,
or submits activity events.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

CATALOG_URLS = (
    ("Discord CDN catalog", "https://cdn.discordapp.com/detectables/games.json"),
    ("Discord public games catalog", "https://discord.com/api/v10/games/detectable"),
    ("Discord detectable applications catalog", "https://discord.com/api/v10/applications/detectable"),
)
USER_AGENT = "IVX-Discord-Lab/1.3.1 (public game catalog)"
MAX_CATALOG_BYTES = 32 * 1024 * 1024

FALLBACK_GAMES: list[dict[str, str]] = [
    {"id": "fallback:counter-strike-2", "name": "Counter-Strike 2", "executable": "cs2.exe"},
    {"id": "fallback:fortnite", "name": "Fortnite", "executable": "FortniteClient-Win64-Shipping.exe"},
    {"id": "fallback:minecraft", "name": "Minecraft", "executable": "Minecraft.exe"},
    {"id": "fallback:roblox", "name": "Roblox", "executable": "RobloxPlayerBeta.exe"},
    {"id": "fallback:rocket-league", "name": "Rocket League", "executable": "RocketLeague.exe"},
    {"id": "fallback:stardew-valley", "name": "Stardew Valley", "executable": "Stardew Valley.exe"},
    {"id": "fallback:valorant", "name": "Valorant", "executable": "VALORANT-Win64-Shipping.exe"},
    {"id": "fallback:apex-legends", "name": "Apex Legends", "executable": "r5apex.exe"},
]


def default_cache_path() -> Path:
    """Return a per-user cache location, outside the project/repository folder."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        cache_home = os.environ.get("XDG_CACHE_HOME")
        base = Path(cache_home) if cache_home else Path.home() / ".cache"
    return base / "IVXDiscordLab" / "detectable_games_cache.json"


def _payload_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("games", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def normalize_game_catalog(payload: Any) -> list[dict[str, str]]:
    """Normalize a public catalog into unique Windows-friendly {id, name, executable} rows."""
    games: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in _payload_items(payload):
        if not isinstance(item, dict):
            continue
        name_value = item.get("name") or item.get("title")
        if not isinstance(name_value, str) or not name_value.strip():
            continue
        name = name_value.strip()

        raw_executables = item.get("executables", item.get("executable", []))
        if isinstance(raw_executables, (str, dict)):
            raw_executables = [raw_executables]
        if not isinstance(raw_executables, list):
            raw_executables = []

        executable = ""
        platform_tagged = any(
            isinstance(entry, dict) and entry.get("os")
            for entry in raw_executables
        )
        candidates: list[str] = []
        for entry in raw_executables:
            if isinstance(entry, str) and entry.strip():
                candidates.append(entry.strip())
            elif isinstance(entry, dict):
                exe_name = entry.get("name") or entry.get("path")
                if not isinstance(exe_name, str) or not exe_name.strip():
                    continue
                os_name = str(entry.get("os", "")).casefold()
                if os_name in ("win32", "windows", "win"):
                    candidates.insert(0, exe_name.strip())
                elif not os_name:
                    candidates.append(exe_name.strip())

        if candidates:
            executable = candidates[0]
        elif platform_tagged:
            # This entry explicitly lists executables but none target Windows.
            continue

        raw_id = item.get("id") or item.get("application_id")
        game_id = str(raw_id).strip() if raw_id is not None else ""
        identity = game_id or f"{name.casefold()}|{executable.casefold()}"
        if identity in seen:
            continue
        seen.add(identity)
        games.append({
            "id": game_id or f"catalog:{len(games)}:{name.casefold()}",
            "name": name,
            "executable": executable or "Executable not listed",
        })

    games.sort(key=lambda entry: (entry["name"].casefold(), entry["id"]))
    return games


def _read_cache(cache_file: Path) -> list[dict[str, str]]:
    try:
        raw = cache_file.read_bytes()
        if len(raw) > MAX_CATALOG_BYTES:
            return []
        return normalize_game_catalog(json.loads(raw.decode("utf-8-sig")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return []


def _write_cache(cache_file: Path, games: list[dict[str, str]]) -> None:
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(games, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # A read-only cache location should not prevent use of the live catalog.
        pass


def fetch_detectable_games(
    *,
    timeout: float = 8.0,
    cache_file: Path | None = None,
    opener: Callable[..., Any] | None = None,
) -> tuple[list[dict[str, str]], str, str]:
    """Fetch the first valid public catalog; fall back to cache, then built-in titles.

    Returns (games, source_label, diagnostic_message). Only public game metadata is fetched.
    """
    cache_file = cache_file or default_cache_path()
    open_url = opener or urllib.request.urlopen
    errors: list[str] = []

    for source_label, url in CATALOG_URLS:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with open_url(request, timeout=timeout) as response:
                raw = response.read(MAX_CATALOG_BYTES + 1)
            if len(raw) > MAX_CATALOG_BYTES:
                raise ValueError("catalog response exceeded the 32 MiB safety limit")
            payload = json.loads(raw.decode("utf-8-sig"))
            games = normalize_game_catalog(payload)
            if not games:
                raise ValueError("the endpoint returned no supported game entries")
            _write_cache(cache_file, games)
            return games, source_label, f"Loaded {len(games):,} games from the public catalog."
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{source_label}: {exc}")

    cached_games = _read_cache(cache_file)
    if cached_games:
        return cached_games, "Cached catalog", (
            f"Network catalog could not be refreshed; loaded {len(cached_games):,} cached games. "
            + " | ".join(errors)
        )

    fallback = [dict(game) for game in FALLBACK_GAMES]
    return fallback, "Built-in fallback", (
        "The public catalog could not be reached and no valid cache was found. "
        "Showing built-in examples instead. Check your connection and try Refresh. "
        + " | ".join(errors)
    )
