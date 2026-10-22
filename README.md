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

The interface uses PySide6 and Qt 6 with a polished dark layout, sidebar navigation, inventory cards, a searchable profile table, subtle fade transitions, and local export dialogs.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6%20%2F%20Qt%206-41CD52?style=flat-square&logo=qt&logoColor=white)
![Privacy](https://img.shields.io/badge/Privacy-Local--only-16A34A?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-8B5CF6?style=flat-square)

### Features

- **Overview dashboard** — counts detected Discord clients, browser profiles, and storage-folder presence.
- **Discord client detection** — checks the standard user-data paths for Stable, PTB, and Canary.
- **Browser profile inventory** — lists supported Chrome, Edge, Brave, Vivaldi, Firefox, and Opera profile folders in standard locations.
- **Search and filter** — find entries by type, application, profile label, or home-relative path.
- **CSV export** — create a spreadsheet-friendly metadata report.
- **JSON export** — save the full metadata report, including its limitations.
- **Subtle UI animation** — Qt property animations provide short, reduced-complexity page transitions.
- **Lightweight inventory** — the scanning module uses only the Python standard library.
- **Clear separation** — the desktop interface never invokes `spoofer.py`.

### What the scan can tell you

The scan tells you whether standard folders exist. It does **not** establish that a user is currently signed in, identify an account username, validate a session, or prove that a session is active.

## Installation

### Requirements

- Windows 10 or 11 (the inventory module also supports common macOS and Linux profile paths)
- Python 3.10 or newer
- PySide6, installed from the version range in `requirements.txt`

### Setup

1. Download or clone this repository.
2. Open a terminal in the project folder.
3. Create and activate a virtual environment (recommended):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the desktop dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Launch the desktop app:

   ```powershell
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
| `app.py` | PySide6 desktop UI: dashboard, searchable inventory, animations, exports |
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
python -m py_compile app.py session_inventory.py tests/test_session_inventory.py
```

These tests use temporary directories and do not open real user credential stores or send network requests.

To run the Qt UI, use a desktop session with PySide6 installed. The scan checks folder metadata only.

## Experimental badge script

The separate `spoofer.py` script submits fabricated activity telemetry to undocumented Discord endpoints. It is not part of the desktop inventory workflow. Its behavior has not been verified against Discord's live badge-processing system, and an accepted HTTP request does not prove badge progress changed.

Automated or fabricated telemetry may violate Discord's Terms of Service and can put an account at risk. No badge progress or account outcome is promised.

## Attribution and license

This repository retains the original MIT license and its required copyright notice. The legacy `spoofer.py` component originated from the MIT-licensed [revere-group/discord-badge-spoofer](https://github.com/revere-group/discord-badge-spoofer) project; see `LICENSE` for the retained notice. The IVX desktop interface and metadata-only inventory are maintained separately.

This project is not affiliated with or endorsed by Discord.
