#!/usr/bin/env python3
"""Safely inventory Discord clients and browser profiles without reading secrets.

This utility reports profile directories and the presence of storage folders only.
It does not read/decrypt tokens, cookies, browser databases, or Local Storage files.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
from pathlib import Path
from typing import Mapping, Sequence

SENSITIVE_WARNING = (
    "Inventory only: this report contains detected profile names and folder-presence "
    "metadata. No tokens, cookies, browser databases, or storage contents were read."
)


def _home_path(home: Path, value: Path) -> str:
    """Render paths relative to home where possible, to avoid exposing the OS username."""
    try:
        return "~" + str(value.relative_to(home))
    except ValueError:
        return str(value)


def _discord_roots(home: Path, env: Mapping[str, str], system: str) -> list[tuple[str, Path]]:
    if system == "Windows":
        appdata = Path(env.get("APPDATA", str(home / "AppData" / "Roaming")))
    elif system == "Darwin":
        appdata = home / "Library" / "Application Support"
    else:
        appdata = home / ".config"
    return [
        ("Discord Stable", appdata / "discord"),
        ("Discord PTB", appdata / "discordptb"),
        ("Discord Canary", appdata / "discordcanary"),
    ]


def _browser_roots(home: Path, env: Mapping[str, str], system: str) -> list[tuple[str, Path, bool]]:
    """Return (browser label, root/profile path, root_is_direct_profile)."""
    if system == "Windows":
        local = Path(env.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        roaming = Path(env.get("APPDATA", str(home / "AppData" / "Roaming")))
        return [
            ("Google Chrome", local / "Google" / "Chrome" / "User Data", False),
            ("Microsoft Edge", local / "Microsoft" / "Edge" / "User Data", False),
            ("Brave", local / "BraveSoftware" / "Brave-Browser" / "User Data", False),
            ("Vivaldi", local / "Vivaldi" / "User Data", False),
            ("Opera", roaming / "Opera Software" / "Opera Stable", True),
            ("Firefox", roaming / "Mozilla" / "Firefox" / "Profiles", False),
        ]
    if system == "Darwin":
        app = home / "Library" / "Application Support"
        return [
            ("Google Chrome", app / "Google" / "Chrome" / "User Data", False),
            ("Microsoft Edge", app / "Microsoft Edge" / "User Data", False),
            ("Brave", app / "BraveSoftware" / "Brave-Browser" / "User Data", False),
            ("Vivaldi", app / "Vivaldi" / "User Data", False),
            ("Opera", app / "com.operasoftware.Opera", True),
            ("Firefox", home / "Library" / "Application Support" / "Firefox" / "Profiles", False),
        ]
    config = home / ".config"
    return [
        ("Google Chrome", config / "google-chrome", False),
        ("Google Chrome (Chromium)", config / "chromium", False),
        ("Microsoft Edge", config / "microsoft-edge", False),
        ("Brave", config / "BraveSoftware" / "Brave-Browser", False),
        ("Vivaldi", config / "vivaldi", False),
        ("Opera", config / "opera", True),
        ("Firefox", home / ".mozilla" / "firefox", False),
    ]


def _profile_dirs(root: Path, direct_profile: bool, browser_name: str) -> list[tuple[str, Path]]:
    if not root.is_dir():
        return []
    if direct_profile:
        return [(root.name or browser_name, root)]
    try:
        children = [p for p in root.iterdir() if p.is_dir()]
    except OSError:
        return []

    if browser_name == "Firefox":
        return sorted(
            [(p.name, p) for p in children if "." in p.name or p.name.lower() in {"profiles", "default"}],
            key=lambda item: item[0].casefold(),
        )
    allowed = {"default", "guest profile", "system profile"}
    selected = [p for p in children if p.name.casefold() in allowed or p.name.casefold().startswith("profile ")]
    return sorted([(p.name, p) for p in selected], key=lambda item: item[0].casefold())


def build_inventory(home: Path | None = None, env: Mapping[str, str] | None = None, system: str | None = None) -> dict:
    """Build metadata-only inventory; injectable paths make tests safe and deterministic."""
    home = Path(home or Path.home()).expanduser()
    env = env if env is not None else os.environ
    system = system or platform.system()

    discord_profiles = []
    for label, root in _discord_roots(home, env, system):
        exists = root.is_dir()
        local_storage = (root / "Local Storage").is_dir() or (root / "Local Storage" / "leveldb").is_dir()
        discord_profiles.append({
            "client": label,
            "user_data_found": exists,
            "local_storage_folder_found": local_storage,
            "path": _home_path(home, root),
        })

    browser_profiles = []
    for browser, root, direct in _browser_roots(home, env, system):
        for profile_name, profile_path in _profile_dirs(root, direct, browser):
            browser_profiles.append({
                "browser": browser,
                "profile": profile_name,
                "profile_folder_found": True,
                "local_storage_folder_found": (profile_path / "Local Storage").is_dir(),
                "path": _home_path(home, profile_path),
            })

    return {
        "report_type": "local-session-inventory",
        "warning": SENSITIVE_WARNING,
        "discord_clients": discord_profiles,
        "browser_profiles": browser_profiles,
        "limitations": [
            "This report cannot reveal account usernames or token values.",
            "No credential files, cookies, SQLite databases, LevelDB contents, or browser storage contents are opened.",
            "A detected folder does not prove that a session is currently valid or signed in.",
        ],
    }


def write_csv_report(report: dict, target: Path) -> None:
    """Write only profile metadata to CSV; never include tokens or cookies."""
    fieldnames = [
        "kind",
        "application",
        "profile",
        "profile_folder_found",
        "user_data_found",
        "local_storage_folder_found",
        "path",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in report["discord_clients"]:
            writer.writerow({
                "kind": "discord_client",
                "application": item["client"],
                "profile": "",
                "profile_folder_found": "",
                "user_data_found": item["user_data_found"],
                "local_storage_folder_found": item["local_storage_folder_found"],
                "path": item["path"],
            })
        for item in report["browser_profiles"]:
            writer.writerow({
                "kind": "browser_profile",
                "application": item["browser"],
                "profile": item["profile"],
                "profile_folder_found": item["profile_folder_found"],
                "user_data_found": "",
                "local_storage_folder_found": item["local_storage_folder_found"],
                "path": item["path"],
            })


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List Discord installations and browser profile folders without collecting credentials."
    )
    parser.add_argument("--json", dest="json_path", metavar="FILE", help="write the metadata-only inventory report to JSON FILE")
    parser.add_argument("--csv", dest="csv_path", metavar="FILE", help="write a metadata-only inventory table to CSV FILE")
    args = parser.parse_args(argv)

    report = build_inventory()
    print("\nSAFE LOCAL SESSION INVENTORY")
    print("============================")
    print(SENSITIVE_WARNING)
    print("\nDiscord clients:")
    for item in report["discord_clients"]:
        data = "found" if item["user_data_found"] else "not found"
        storage = "yes" if item["local_storage_folder_found"] else "no"
        print(f"  - {item['client']}: user data {data}; Local Storage folder: {storage}")
    print("\nBrowser profiles:")
    if report["browser_profiles"]:
        for item in report["browser_profiles"]:
            print(f"  - {item['browser']} / {item['profile']} (profile folder found)")
    else:
        print("  - No supported browser profiles detected in standard locations.")

    if args.json_path:
        target = Path(args.json_path).expanduser()
        try:
            target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"\nCould not write report: {exc}")
            return 1
        print(f"\nMetadata-only JSON report saved to: {target}")

    if args.csv_path:
        target = Path(args.csv_path).expanduser()
        try:
            write_csv_report(report, target)
        except OSError as exc:
            print(f"\nCould not write CSV report: {exc}")
            return 1
        print(f"\nMetadata-only CSV report saved to: {target}")

    print("\nNo token values or cookies were collected or exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
