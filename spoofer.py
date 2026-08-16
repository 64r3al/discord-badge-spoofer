#!/usr/bin/env python3
"""
discord science spoofer - inflate the playtime and games-played badges.

revere group, 2026. mit licensed (see LICENSE).

posts running_game_heartbeat events to /api/v9/science, the same endpoint the
real client uses to credit playtime. duration_tracked_ms isn't validated so any
number goes straight through.

run:
    python spoofer.py

auth bits:
    auth_token       your account token, from ../spoof_config.json
    analytics_token  pulled off the gateway ready payload
    super_props      rebuilt on the fly
    heartbeat/launch random uuids we make up
    cookie           the one thing you paste by hand (cf_clearance), saved in
                     science_state.json. menu option 3 updates it.

this breaks discord tos. your account, your problem.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator, Sequence

import aiohttp

# paths
ROOT = Path(__file__).resolve().parent
GAMES_FILE = ROOT.parent / "data" / "games.json"     # full game list, downloaded if absent
STATE_FILE = ROOT / "science_state.json"             # token, cookie, cached auth

GATEWAY_URL = "wss://gateway.discord.gg/?v=9&encoding=json"
SCIENCE_URL = "https://discord.com/api/v9/science"
GAMES_CDN_URL = "https://cdn.discordapp.com/detectables/games.json"  # used if games.json isn't there

BATCH_SIZE = 50           # events per /science request
BATCH_DELAY = 0.3         # seconds between requests
AUTH_MAX_AGE = 12 * 3600  # refetch the analytics token once the cache is older than this

# client identity
CLIENT_VERSION = "1.0.9253"
CLIENT_BUILD_NUMBER = 594031
NATIVE_BUILD_NUMBER = 88414
OS_VERSION = "10.0.26200"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) discord/1.0.9253 Chrome/148.0.7778.280 "
    "Electron/42.7.1 Safari/537.36"
)


class Console:
    """colored console output."""

    RED = "\x1b[91m"
    ORANGE = "\x1b[38;5;208m"
    GREEN = "\x1b[92m"
    YELLOW = "\x1b[93m"
    WHITE = "\x1b[97m"
    GREY = "\x1b[90m"
    RESET = "\x1b[0m"
    RULE = "─" * 44

    def __init__(self) -> None:
        if sys.platform == "win32":
            self._enable_ansi()

    @staticmethod
    def _enable_ansi() -> None:
        # flip on virtual terminal processing so ansi colors render on windows
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # std_output_handle
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)

    def _stamp(self) -> str:
        return f"{self.GREY}{time.strftime('%H:%M:%S')}{self.RESET}"

    def _line(self, glyph: str, target: str, detail: str, color: str) -> None:
        print(f"  {self._stamp()} {glyph} {self.WHITE}{target}{self.RESET} "
              f"{self.GREY}·{self.RESET} {color}{detail}{self.RESET}")

    def ok(self, target: str, detail: str) -> None:
        self._line(f"{self.GREEN}✓{self.RESET}", target, detail, self.GREEN)

    def sent(self, target: str, detail: str) -> None:
        self._line(f"{self.GREY}·{self.RESET} {self.GREEN}sent{self.RESET}", target, detail, self.GREEN)

    def warn(self, target: str, detail: str) -> None:
        self._line(f"{self.YELLOW}!{self.RESET}", target, detail, self.YELLOW)

    def err(self, target: str, detail: str) -> None:
        self._line(f"{self.RED}✗{self.RESET}", target, detail, self.RED)

    def info(self, detail: str) -> None:
        print(f"  {self._stamp()} {self.GREY}·{self.RESET} {self.WHITE}{detail}{self.RESET}")

    def rule(self) -> None:
        print(f"  {self.GREY}{self.RULE}{self.RESET}")

    def banner(self) -> None:
        print()
        print(f"  {self.ORANGE}spoofer{self.RESET} {self.GREY}·{self.RESET} {self.WHITE}discord badges{self.RESET}")
        print(f"    {self.GREY}by revere group{self.RESET}")
        print()


@dataclass
class State:
    """saved auth. token + cookie are yours to supply, the rest is auto."""

    token: str = ""
    cookie: str = ""
    analytics_token: str = ""
    super_props: str = ""
    heartbeat_session: str = ""
    launch_signature: str = ""
    fetched_at: int = 0

    @classmethod
    def load(cls) -> "State":
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return cls(**{k: data.get(k, v) for k, v in cls().__dict__.items()})
        return cls()

    def save(self) -> None:
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @property
    def is_stale(self) -> bool:
        return not self.analytics_token or (time.time() - self.fetched_at) > AUTH_MAX_AGE

    @property
    def has_cookie(self) -> bool:
        return bool(self.cookie.strip())

    @property
    def has_token(self) -> bool:
        return bool(self.token.strip())


def build_super_props(launch_signature: str, heartbeat_session: str) -> str:
    props = {
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": CLIENT_VERSION,
        "os_version": OS_VERSION,
        "os_arch": "x64",
        "app_arch": "x64",
        "system_locale": "en-GB",
        "has_client_mods": False,
        "client_launch_id": str(uuid.uuid4()),
        "browser_user_agent": USER_AGENT,
        "browser_version": "42.7.1",
        "os_sdk_version": "26200",
        "client_build_number": CLIENT_BUILD_NUMBER,
        "native_build_number": NATIVE_BUILD_NUMBER,
        "client_event_source": None,
        "launch_signature": launch_signature,
        "client_heartbeat_session_id": heartbeat_session,
        "client_app_state": "focused",
    }
    raw = json.dumps(props, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


async def _read_analytics_token(auth_token: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(GATEWAY_URL, max_msg_size=0) as ws:
            await ws.receive_json()  # hello
            await ws.send_json({
                "op": 2,
                "d": {
                    "token": auth_token,
                    "capabilities": 30717,
                    "properties": {
                        "os": "Windows",
                        "browser": "Discord Client",
                        "release_channel": "stable",
                        "client_version": CLIENT_VERSION,
                        "os_version": OS_VERSION,
                        "system_locale": "en-GB",
                    },
                },
            })
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                if data.get("op") == 9:
                    raise RuntimeError("gateway rejected token (invalid session)")
                if data.get("t") == "READY":
                    token = data["d"].get("analytics_token")
                    if not token:
                        raise RuntimeError("READY payload had no analytics_token")
                    return token
    raise RuntimeError("gateway closed before READY")


def refresh_auth(state: State) -> None:
    """grab a fresh analytics token and rebuild the bundle. leaves token + cookie alone."""
    analytics_token = asyncio.run(_read_analytics_token(state.token))
    state.analytics_token = analytics_token
    state.heartbeat_session = str(uuid.uuid4())
    state.launch_signature = str(uuid.uuid4())
    state.super_props = build_super_props(state.launch_signature, state.heartbeat_session)
    state.fetched_at = int(time.time())
    state.save()


@dataclass(frozen=True)
class Game:
    id: str
    name: str
    exe: str


def _win_exe(game: dict) -> str:
    for entry in game.get("executables", []):
        if entry.get("os") == "win32" and entry.get("name"):
            return entry["name"]
    return "game.exe"


def _download_games() -> str:
    request = urllib.request.Request(GAMES_CDN_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    GAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    GAMES_FILE.write_text(raw, encoding="utf-8")
    return raw


def load_games() -> list[Game]:
    if GAMES_FILE.exists():
        raw = GAMES_FILE.read_text(encoding="utf-8")
    else:
        try:
            raw = _download_games()
        except Exception:
            return []
    data = json.loads(raw)
    games: list[Game] = []
    seen: set[str] = set()
    for entry in data:
        gid = str(entry.get("id", ""))
        if not gid.isdigit() or gid in seen:
            continue
        if not any(e.get("os") == "win32" and e.get("name") for e in entry.get("executables", [])):
            continue
        seen.add(gid)
        games.append(Game(gid, entry.get("name", "Unknown"), _win_exe(entry)))
    return games


class ScienceClient:
    """builds and posts launch_game and running_game_heartbeat events."""

    def __init__(self, state: State) -> None:
        self.state = state
        self._seq = 0

    def _next_seq(self) -> int:
        # real clients use a running counter across the whole session
        self._seq += 1
        return self._seq

    def build_launch(self, game: Game) -> dict:
        now = int(time.time() * 1000)
        return {
            "type": "launch_game",
            "properties": {
                "client_track_timestamp": now,
                "client_heartbeat_session_id": self.state.heartbeat_session,
                "event_sequence_number": self._next_seq(),
                "game": game.name,
                "game_id": game.id,
                "verified": True,
                "elevated": False,
                "is_launcher": False,
                "game_platform": "desktop",
                "detection_method": "verified_game",
                "is_overlay_enabled": False,
                "is_overlay_game_enabled": True,
                "is_overlay_game_source": "OOP_DEFAULT_DATABASE",
                "fullscreen_type": "UNKNOWN",
                "hardware_display_count": 1,
                "overlay_method": "Disabled",
                "activity_status_enabled": True,
                "activity_status_shared_guilds": [],
                "current_user_status": "online",
                "game_detection_enabled": True,
                "executable_path": game.exe,
                # voice/guild/perf left null - real for "not in voice" and we don't fake identifying data
                "voice_channel_id": None,
                "voice_channel_type": None,
                "voice_channel_bitrate": None,
                "voice_channel_guild_id": None,
                "hidden_by_distributor": False,
                "game_metadata": None,
                "client_performance_cpu": None,
                "client_performance_memory": None,
                "cpu_core_count": None,
                "accessibility_features": 0,
                "rendered_locale": "en-GB",
                "launch_signature": self.state.launch_signature,
                "client_rtc_state": None,
                "client_app_state": "focused",
                "client_send_timestamp": now,
            },
        }

    def build_heartbeat(self, game: Game, duration_ms: int, session_id: str,
                        initial: bool, final: bool, ts: int | None = None) -> dict:
        ts = int(time.time() * 1000) if ts is None else ts
        return {
            "type": "running_game_heartbeat",
            "properties": {
                "client_track_timestamp": ts,
                "client_heartbeat_session_id": self.state.heartbeat_session,
                "event_sequence_number": self._next_seq(),
                "game_id": game.id,
                "game_name": game.name,
                "game_metadata": None,
                "game_executable": game.exe,
                "game_detection_enabled": True,
                "initial_heartbeat": initial,
                "final_heartbeat": final,
                "game_session_id": session_id,
                "duration_tracked_ms": duration_ms,
                "rtc_connection_id": None,
                "media_session_id": None,
                "launch_signature": self.state.launch_signature,
                "client_app_state": "focused",
                "client_send_timestamp": ts,
            },
        }

    def build_session(self, game: Game, duration_ms: int) -> list[dict]:
        # real client flow: open heartbeat (0ms) -> launch_game -> close heartbeat (full duration).
        # both heartbeats share one game_session_id; timestamps span the duration when it's sane.
        sid = str(uuid.uuid4())
        now = int(time.time() * 1000)
        start = now - duration_ms
        if start < 0:                       # duration too large to backdate sensibly
            start = now
        return [
            self.build_heartbeat(game, 0, sid, initial=True, final=False, ts=start),
            self.build_launch(game),
            self.build_heartbeat(game, duration_ms, sid, initial=False, final=True, ts=now),
        ]

    def post(self, events: Sequence[dict]) -> int:
        """post a batch. returns the http status (204 = accepted)."""
        body = json.dumps({"token": self.state.analytics_token, "events": list(events)}).encode("utf-8")
        request = urllib.request.Request(SCIENCE_URL, data=body, method="POST", headers={
            "accept": "*/*",
            "accept-language": "en-GB",
            "authorization": self.state.token,
            "content-type": "application/json",
            "cookie": self.state.cookie,
            "origin": "https://discord.com",
            "referer": "https://discord.com/channels/@me",
            "user-agent": USER_AGENT,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-GB",
            "x-discord-timezone": "Europe/Oslo",
            "x-super-properties": self.state.super_props,
        })
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except Exception:
            return 0


def _chunked(items: Sequence[Game], size: int) -> Iterator[Sequence[Game]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


class Spoofer:
    """sends events in batches and logs progress."""

    def __init__(self, client: ScienceClient, console: Console) -> None:
        self.client = client
        self.console = console

    def run(self, games: Sequence[Game], build_events) -> int:
        # build_events(game) -> list of event dicts to send for that game
        total = len(games)
        sent_ok = 0
        for request_no, chunk in enumerate(_chunked(games, BATCH_SIZE), start=1):
            events = []
            for game in chunk:
                events.extend(build_events(game))
            status = self.client.post(events)
            if status == 204:
                sent_ok += len(chunk)
                self.console.sent(f"batch {request_no}", f"{sent_ok}/{total} games")
            elif status in (401, 403):
                self.console.err(f"batch {request_no}",
                                 f"[{status}] auth rejected · refresh (option 3) with a fresh cookie")
                return sent_ok
            else:
                self.console.warn(f"batch {request_no}", f"[{status}]")
            time.sleep(BATCH_DELAY)
        return sent_ok


class App:
    def __init__(self) -> None:
        self.console = Console()
        self.state = State.load()
        self.games: list[Game] = []

    # startup

    def start(self) -> None:
        self.console.banner()

        if not self.state.has_token:
            self._prompt_token()
        if not self.state.has_token:
            self.console.err("token", "required to run")
            return

        self.games = load_games()
        if not self.games:
            self.console.err("games", f"not found or empty: {GAMES_FILE}")
            return
        self.console.info(f"loaded {self.console.GREEN}{len(self.games)}{self.console.WHITE} games")

        # make sure the analytics token is fresh before the menu
        if self.state.is_stale:
            self._refresh(prompt_cookie=False)

        self.menu()

    # auth

    def _prompt_token(self) -> None:
        self.console.info("paste your discord account token")
        entered = input(f"  {self.console.GREY}token:{self.console.RESET} ").strip()
        if entered:
            self.state.token = entered
            self.state.save()
            self.console.ok("token", "saved")

    def _refresh(self, prompt_cookie: bool) -> None:
        if prompt_cookie:
            self.console.info("paste a fresh cookie header (enter to keep the current one)")
            entered = input(f"  {self.console.GREY}cookie:{self.console.RESET} ").strip()
            if entered:
                self.state.cookie = entered
                self.console.ok("cookie", "updated")
            else:
                self.console.info("cookie unchanged")

        self.console.info("fetching analytics token from gateway...")
        try:
            refresh_auth(self.state)
        except Exception as exc:
            self.console.err("gateway", str(exc))
            return
        self.console.ok("auth", "refreshed")

    def _require_ready(self) -> bool:
        if not self.state.has_cookie:
            self.console.err("cookie", "not set · use option 3 to add one")
            return False
        if self.state.is_stale:
            self._refresh(prompt_cookie=False)
        return bool(self.state.analytics_token)

    # modules

    def module_playtime(self) -> None:
        if not self._require_ready():
            return
        raw = input(f"  {self.console.GREY}hours per game:{self.console.RESET} ").strip()
        try:
            hours = float(raw)
        except ValueError:
            self.console.err("input", "invalid hours")
            return
        duration_ms = int(hours * 3600 * 1000)
        print()
        self.console.info(
            f"claiming {self.console.ORANGE}{hours:g}h{self.console.WHITE} on "
            f"{self.console.ORANGE}{len(self.games)}{self.console.WHITE} games "
            f"{self.console.GREY}·{self.console.WHITE} {len(self.games) * hours:,.0f}h total"
        )
        self.console.rule()
        client = ScienceClient(self.state)
        ok = Spoofer(client, self.console).run(
            self.games,
            lambda g: client.build_session(g, duration_ms),
        )
        print()
        self.console.ok("complete", f"{ok}/{len(self.games)} games · {ok * hours:,.0f}h claimed")

    def module_played_count(self) -> None:
        if not self._require_ready():
            return
        print()
        self.console.info(
            f"registering {self.console.ORANGE}{len(self.games)}{self.console.WHITE} games as played "
            f"{self.console.GREY}·{self.console.WHITE} 1m each"
        )
        self.console.rule()
        # launch_game drives the played count; the open/close heartbeats add the minute
        client = ScienceClient(self.state)
        ok = Spoofer(client, self.console).run(
            self.games,
            lambda g: client.build_session(g, 60 * 1000),
        )
        print()
        self.console.ok("complete", f"{ok}/{len(self.games)} games marked played")

    # menu

    def menu(self) -> None:
        C = self.console
        while True:
            cookie_state = f"{C.GREEN}set{C.RESET}" if self.state.has_cookie else f"{C.RED}unset{C.RESET}"
            C.rule()
            print(f"  {C.ORANGE}1{C.RESET} {C.WHITE}claim playtime (hours){C.RESET}")
            print(f"  {C.ORANGE}2{C.RESET} {C.WHITE}games played (count){C.RESET}")
            print(f"  {C.ORANGE}3{C.RESET} {C.WHITE}refresh auth{C.RESET} {C.GREY}· cookie {cookie_state}{C.RESET}")
            print(f"  {C.ORANGE}4{C.RESET} {C.WHITE}exit{C.RESET}")
            C.rule()
            choice = input(f"  {C.ORANGE}›{C.RESET} ").strip()

            if choice == "1":
                self.module_playtime()
            elif choice == "2":
                self.module_played_count()
            elif choice == "3":
                self._refresh(prompt_cookie=True)
            elif choice == "4":
                break


def main() -> None:
    try:
        App().start()
    except KeyboardInterrupt:
        print()
        Console().warn("exit", "interrupted")


if __name__ == "__main__":
    main()
