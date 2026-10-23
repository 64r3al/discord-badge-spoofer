"""Official OAuth2 identity verification for local IVX account labels.

Only the OAuth2 \`identify\` scope is requested. User access tokens, refresh tokens,
client secrets, and authorization codes are never persisted. Saved account records
contain display metadata and a user-defined safety label only.
"""
from __future__ import annotations

import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event
from typing import Any, Callable

API_BASE = "https://discord.com/api/v10"
AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = f"{API_BASE}/oauth2/token"
ME_URL = f"{API_BASE}/users/@me"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_AVATAR_BYTES = 2 * 1024 * 1024
USER_AGENT = "IVX-Discord-Lab/1.4 (OAuth2 identify only)"


class IdentityVerificationError(RuntimeError):
    """A safe, user-facing identity verification error."""


def identity_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "IVXDiscordLab"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return base / "IVXDiscordLab"


def identity_store_path() -> Path:
    return identity_data_dir() / "verified_accounts.json"


def avatar_cache_path(user_id: str) -> Path:
    if not user_id.isdigit():
        raise ValueError("Invalid Discord user ID.")
    return identity_data_dir() / "avatars" / f"{user_id}.png"


def load_verified_accounts(path: Path | None = None) -> list[dict[str, str]]:
    path = path or identity_store_path()
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_JSON_BYTES:
            return []
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []

    clean: list[dict[str, str]] = []
    seen: set[str] = set()
    allowed_labels = {"Unlabeled", "TEST ACCOUNT", "MAIN ACCOUNT — DO NOT USE"}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        user_id = str(entry.get("id", ""))
        username = entry.get("username")
        if not user_id.isdigit() or user_id in seen or not isinstance(username, str) or not username:
            continue
        global_name = entry.get("global_name", "")
        avatar = entry.get("avatar", "")
        label = entry.get("label", "Unlabeled")
        label = label if isinstance(label, str) and label in allowed_labels else "Unlabeled"
        clean.append({
            "id": user_id,
            "username": username[:128],
            "global_name": global_name[:128] if isinstance(global_name, str) else "",
            "avatar": avatar[:256] if isinstance(avatar, str) else "",
            "label": label,
        })
        seen.add(user_id)
    return clean


def save_verified_accounts(
    accounts: list[dict[str, Any]],
    path: Path | None = None,
) -> None:
    """Persist an allowlisted subset of display metadata; auth fields are discarded."""
    path = path or identity_store_path()
    clean: list[dict[str, str]] = []
    seen: set[str] = set()
    allowed_labels = {"Unlabeled", "TEST ACCOUNT", "MAIN ACCOUNT — DO NOT USE"}
    for entry in accounts:
        user_id = str(entry.get("id", ""))
        username = entry.get("username")
        if not user_id.isdigit() or user_id in seen or not isinstance(username, str) or not username:
            continue
        global_name = entry.get("global_name", "")
        avatar = entry.get("avatar", "")
        label = entry.get("label", "Unlabeled")
        label = label if isinstance(label, str) and label in allowed_labels else "Unlabeled"
        clean.append({
            "id": user_id,
            "username": username[:128],
            "global_name": global_name[:128] if isinstance(global_name, str) else "",
            "avatar": avatar[:256] if isinstance(avatar, str) else "",
            "label": label,
        })
        seen.add(user_id)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def avatar_url(user_id: str, avatar_hash: str, discriminator: str = "0") -> str:
    if not user_id.isdigit():
        return ""
    if avatar_hash:
        extension = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{extension}?size=128"
    try:
        old_discriminator = int(discriminator)
    except (TypeError, ValueError):
        old_discriminator = 0
    default_index = old_discriminator % 5 if old_discriminator else (int(user_id) >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{default_index}.png"


def _read_json_response(
    opener: Callable[..., Any],
    request: urllib.request.Request,
    *,
    timeout: float = 12.0,
) -> dict[str, Any]:
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read(1024).decode("utf-8", "replace")
        except Exception:
            error_body = ""
        # Never include request headers or secrets in diagnostics.
        raise IdentityVerificationError(
            f"Discord returned HTTP {exc.code}. {error_body[:240]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IdentityVerificationError(f"Could not contact Discord: {exc}") from exc

    if len(raw) > MAX_JSON_BYTES:
        raise IdentityVerificationError("Discord returned a response that exceeded the size limit.")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityVerificationError("Discord returned an invalid JSON response.") from exc
    if not isinstance(payload, dict):
        raise IdentityVerificationError("Discord returned an unexpected response format.")
    return payload


def _fetch_avatar(
    url: str,
    *,
    opener: Callable[..., Any] | None = None,
    timeout: float = 8.0,
) -> bytes:
    if not url:
        return b""
    open_url = opener or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_url(request, timeout=timeout) as response:
            raw = response.read(MAX_AVATAR_BYTES + 1)
            content_type = str(response.headers.get("Content-Type", "")).lower()
        if len(raw) > MAX_AVATAR_BYTES or not content_type.startswith("image/"):
            return b""
        return raw
    except Exception:
        return b""


def exchange_code_for_identity(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Exchange an OAuth authorization code and fetch only the identify-scoped user."""
    open_url = opener or urllib.request.urlopen
    token_body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode("ascii")
    token_request = urllib.request.Request(
        TOKEN_URL,
        data=token_body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    token_result = _read_json_response(open_url, token_request)
    access_token = token_result.get("access_token")
    scopes = str(token_result.get("scope", ""))
    if not isinstance(access_token, str) or not access_token:
        raise IdentityVerificationError("Discord did not return an access token. Check your application settings.")
    if "identify" not in scopes.split():
        raise IdentityVerificationError("The authorization did not include the identify scope.")

    me_request = urllib.request.Request(
        ME_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    user = _read_json_response(open_url, me_request)
    user_id = str(user.get("id", ""))
    username = user.get("username")
    if not user_id.isdigit() or not isinstance(username, str) or not username:
        raise IdentityVerificationError("Discord returned a user profile without a valid ID or username.")

    avatar_hash = user.get("avatar")
    avatar_hash = avatar_hash if isinstance(avatar_hash, str) else ""
    discriminator = str(user.get("discriminator", "0"))
    return {
        "id": user_id,
        "username": username,
        "global_name": user.get("global_name") if isinstance(user.get("global_name"), str) else "",
        "avatar": avatar_hash,
        "avatar_url": avatar_url(user_id, avatar_hash, discriminator),
    }


def verify_discord_account(
    client_id: str,
    client_secret: str,
    *,
    timeout: float = 180.0,
    opener: Callable[..., Any] | None = None,
    browser_open: Callable[[str], bool] | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    """Run the official OAuth2 identify flow on a loopback-only callback server."""
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    if not client_id.isdigit():
        raise IdentityVerificationError("Enter the numeric Client ID from your Discord developer application.")
    if not client_secret:
        raise IdentityVerificationError("Enter your Discord developer application's Client Secret.")
    if timeout <= 0:
        raise IdentityVerificationError("Verification timeout must be positive.")

    expected_state = secrets.token_urlsafe(32)
    event = Event()
    callback: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            returned_state = query.get("state", [""])[0]
            issuer = query.get("iss", [""])[0]
            if returned_state != expected_state or issuer != "https://discord.com":
                callback["error"] = "The OAuth state or issuer check failed. Please restart verification."
            elif query.get("error"):
                callback["error"] = "Discord authorization was cancelled or denied."
            else:
                code = query.get("code", [""])[0]
                if not code:
                    callback["error"] = "Discord returned no authorization code."
                else:
                    callback["code"] = code
            event.set()

            page = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>IVX Discord Lab</title></head>"
                "<body style='font:16px Segoe UI,sans-serif;background:#0b0d14;color:#eef;padding:40px'>"
                "<h2>IVX Discord Lab</h2><p>Account verification response received.</p>"
                "<p>You can close this tab and return to IVX Discord Lab.</p></body></html>"
            )
            encoded = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except OSError:
                pass

    try:
        server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), CallbackHandler)
    except OSError as exc:
        raise IdentityVerificationError(
            f"Could not listen on {CALLBACK_HOST}:{CALLBACK_PORT}. "
            "Close another local process using port 8765, then retry."
        ) from exc
    server.timeout = 0.5

    query = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": expected_state,
        "prompt": "consent",
    })
    auth_url = f"{AUTHORIZE_URL}?{query}"
    open_browser = browser_open or webbrowser.open
    try:
        if not open_browser(auth_url):
            raise IdentityVerificationError("Could not open a browser. Set a default browser and retry.")
        deadline = time.monotonic() + timeout
        while (
            not event.is_set()
            and time.monotonic() < deadline
            and not (cancel_event is not None and cancel_event.is_set())
        ):
            server.handle_request()
        if cancel_event is not None and cancel_event.is_set():
            raise IdentityVerificationError("Account verification was cancelled.")
        if not event.is_set():
            raise IdentityVerificationError("Verification timed out. Retry and complete the Discord approval page.")
        if callback.get("error"):
            raise IdentityVerificationError(callback["error"])
        result = exchange_code_for_identity(
            client_id=client_id,
            client_secret=client_secret,
            code=callback["code"],
            opener=opener,
        )
        avatar = _fetch_avatar(result["avatar_url"], opener=opener)
        result["avatar_bytes"] = avatar
        return result
    finally:
        server.server_close()
