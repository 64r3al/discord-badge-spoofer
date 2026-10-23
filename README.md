# IVX Discord Lab

<div align="center">

**A modern desktop companion for local Discord and browser profile inventory**

[Desktop UI](#desktop-app) · [Features](#features) · [Installation](#installation) · [Privacy](#privacy--security) · [Project structure](#project-structure)

</div>

---

## Overview

IVX Discord Lab is a Python project with a modern **PySide6 / Qt 6 desktop interface** for inspecting the presence of standard Discord client folders and supported browser profile directories. It exports a metadata-only inventory as CSV or JSON.

The repository also retains a separate legacy experimental script, `spoofer.py`, that constructs synthetic game-activity analytics events. That script is **not launched or controlled by the desktop interface**. Its operation against Discord's undocumented endpoints is unverified against the live service, may violate Discord's Terms of Service, and cannot guarantee Game Time or Game Variety badge progress.

> **Privacy by design:** the desktop app does not read, decrypt, display, or export Discord tokens, browser cookies, saved passwords, browser login databases, or local-storage contents. It does not send reports to webhooks or upload them to a server.

## Desktop app

The interface uses PySide6 and Qt 6 with a polished dark layout, sidebar navigation, inventory cards, a searchable profile table, clean page switching, animated first-run setup, and local export dialogs.

![Tests](https://github.com/64r3al/discord-badge-spoofer/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6%20%2F%20Qt%206-41CD52?style=flat-square&logo=qt&logoColor=white)
![Privacy](https://img.shields.io/badge/Privacy-Local--only-16A34A?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-8B5CF6?style=flat-square)

### Features

- **Overview dashboard** — counts detected Discord clients, browser profiles, and storage-folder presence.
- **Discord client detection** — checks the standard user-data paths for Stable, PTB, and Canary.
- **Browser profile inventory** — lists supported Chrome, Edge, Brave, Vivaldi, Firefox, and Opera profile folders in standard locations.
- **Search and filter** — find entries by type, application, profile label, or home-relative path.
- **Game badge guide** — current setup guidance for Game Time and Game Variety, plus a local check for Discord profile-folder presence and the running desktop process on Windows.
- **Activity Lab simulator** — fetch the public detectable-game catalog, search game names or executable hints, select titles, set simulated hours, and test start/pause/stop behavior with a timestamped local log. Catalog metadata is cached locally; if the network is unavailable, the picker falls back to the last cache or built-in example games. It never accepts credentials or sends activity to Discord.
- **CSV export** — create a spreadsheet-friendly metadata report.
- **JSON export** — save the full metadata report, including its limitations.
- **Animated startup splash** — a lightweight standard-library window shows a moving light sweep and setup progress while the local Python environment and Qt dependencies are prepared.
- **Clean page switching** — the desktop UI avoids stacked opacity effects that could leave ghosted or layered content behind the selected page.
- **Lightweight inventory** — the scanning module uses only the Python standard library.
- **Clear separation** — the desktop interface never invokes `spoofer.py`.

### Game Time and Game Variety

The **Game badges** page explains the official requirements and links to Discord's badge guide. Current official guidance says these badges count games detected by the Discord desktop app, require **Use data to personalize my Discord experience** to be enabled, and may take time to update. Console and mobile activity do not count toward these desktop badges, and some games may not be recognized.

The **Activity Lab** page fetches public Discord detectable-game metadata for the picker, including game names and executable hints, using the catalog sources documented in `game_catalog.py`. Fetching occurs in a background worker so the UI remains responsive. The catalog is cached under the user's application cache directory. When no endpoint is reachable and no valid cache exists, the eight built-in examples remain available. Game selection, planned hours, progress, pause/resume/stop controls, and event logs are still an **offline simulation**: the displayed hours are synthetic, the profile selector is display-only, and no authentication or Discord activity requests are made. The catalog describes games Discord may recognize; it does not guarantee detection or badge credit.

The local readiness check can report detected standard Discord profile folders and, on Windows, whether a Discord desktop process appears to be running. It cannot verify your privacy setting, inspect your Discord account, or confirm that Discord has credited badge progress. Only Discord can confirm that.

### What the scan can tell you

The scan tells you whether standard folders exist. It does **not** establish that a user is currently signed in, identify an account username, validate a session, or prove that a session is active.

## Installation

### Requirements

- Windows 10 or 11 (the inventory module also supports common macOS and Linux profile paths)
- Python 3.10 or newer
- PySide6, installed from the version range in `requirements.txt`

### One-click launch on Windows (recommended)

1. Download the repository using **Code → Download ZIP**, then extract the ZIP completely. Do not run the launcher from inside the ZIP preview or a temporary archive folder.
2. Open the extracted `discord-badge-spoofer` folder.
3. Double-click **`START_IVX_DISCORD_LAB.bat`**.

The launcher opens an animated setup splash and will:

- find Python 3.10 or newer;
- show progress while it creates or repairs the project-local `.venv` folder;
- install `requirements.txt` if the Qt desktop dependency is missing;
- show diagnostic details if setup fails;
- launch the IVX Discord Lab desktop UI and keep the launcher open until the UI closes.

The splash uses Python's standard library, so users do not need to install PySide6 before seeing setup progress. Application startup logs are saved locally under `%LOCALAPPDATA%\\IVXDiscordLab\\app.log` on Windows.

The launcher runs `app.py` only. It does **not** launch `spoofer.py`. Keep the launcher and the project files together in the extracted project folder.

### Manual setup

If you prefer to start it yourself, open a terminal in the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

### Command-line inventory (optional)

You can also run the inventory utility without opening the UI:

```powershell
python session_inventory.py
python session_inventory.py --csv ivx_profile_inventory.csv
python session_inventory.py --json ivx_profile_inventory.json
```

## Export formats

### CSV

The CSV contains rows for Discord client installations and browser profiles, including type, application, profile label, storage-folder presence, and a path relative to the home directory when possible.

### JSON

The JSON contains the inventory, a metadata-only warning, and a limitations list.

Both formats exclude tokens, cookies, saved passwords, browser database contents, and account usernames.

## Privacy & security

- Inventory is performed locally.
- The user chooses the export destination in a Save dialog.
- No webhook, telemetry upload, or background report upload is configured in the desktop app.
- Credential stores, browser login databases, cookie databases, and local-storage contents are not opened.
- The scan does not modify Discord installations or profile directories.
- Paths are home-relative where possible; exported files remain under the user's control.

Do not commit personal inventory reports or credential-bearing files to GitHub. Keep `science_state.json`, local caches, Python environments, and generated reports out of version control.

## Project structure

| File | Purpose |
|---|---|
| `app.py` | PySide6 desktop UI: dashboard, searchable inventory, Game Badges guide, searchable Activity Lab game picker, readiness check and exports |
| `game_catalog.py` | Public detectable-game metadata fetch, normalization, cache and fallback examples |
| `bootstrap.py` | Animated first-run setup splash, local environment preparation, dependency installation and app launch |
| `session_inventory.py` | Metadata-only local profile inventory |
| `tests/test_session_inventory.py` | Unit tests using temporary test directories |
| `spoofer.py` | Separate legacy experimental telemetry script; not integrated into the desktop UI |
| `SAFE_INVENTORY.md` | Command-line inventory notes |
| `ROADMAP.md` | Security-first development roadmap |
| `requirements.txt` | Desktop UI dependency |
| `LICENSE` | MIT license and retained upstream notice |

## Testing

Run the inventory tests from the repository root:

```powershell
python -m unittest discover -s tests -v
python -m py_compile app.py bootstrap.py game_catalog.py session_inventory.py tests/test_game_catalog.py tests/test_session_inventory.py tests/test_app_smoke.py tests/test_windows_launcher.py tests/test_bootstrap_contract.py
```

These tests use temporary directories and do not open real user credential stores or send network requests.

To run the Qt UI, use a desktop session with PySide6 installed. The scan checks folder metadata only.

## Experimental badge script

The separate `spoofer.py` script submits fabricated activity telemetry to undocumented Discord endpoints. It is not part of the desktop inventory workflow. Its behavior has not been verified against Discord's live badge-processing system, and an accepted HTTP request does not prove badge progress changed.

Automated or fabricated telemetry may violate Discord's Terms of Service and can put an account at risk. No badge progress or account outcome is promised.

## Attribution and license

This repository retains the original MIT license and its required copyright notice. The legacy `spoofer.py` component originated from the MIT-licensed [revere-group/discord-badge-spoofer](https://github.com/revere-group/discord-badge-spoofer) project; see `LICENSE` for the retained notice. The IVX desktop interface and metadata-only inventory are maintained separately.

This project is not affiliated with or endorsed by Discord.
