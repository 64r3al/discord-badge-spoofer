# Safe Local Session Inventory

This companion utility lists detected Discord Stable/PTB/Canary user-data folders and common browser profile folders. It is separate from `spoofer.py`; it does not modify or execute the activity code.

## Run

Requires Python 3.10 or newer.

```powershell
python session_inventory.py
```

Save a metadata-only report if useful:

```powershell
python session_inventory.py --json session_inventory_report.json
```

## What it reports

- Whether the standard user-data folder for Discord Stable, PTB, and Canary exists.
- Whether expected Local Storage folders are present.
- Detected browser profile folder names for common Chrome-based browsers, Firefox, and Opera.
- A report can be saved as JSON; it contains profile labels and relative paths, not credentials.

## What it deliberately does not do

It does not read, decrypt, extract, display, or export Discord tokens, browser cookies, browser login databases, Local Storage contents, or account usernames. Folder detection does not prove that a user is currently signed in or that a session is valid. To confirm the username for a Discord client, open that client and check its account/profile UI.

## Tests

From the repository root:

```powershell
python -m unittest discover -s tests -v
python -m py_compile session_inventory.py tests/test_session_inventory.py
```

The tests use temporary directories and do not access real browser or Discord profile data.
