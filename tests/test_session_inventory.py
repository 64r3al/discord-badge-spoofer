import csv
import tempfile
import unittest
from pathlib import Path

from session_inventory import build_inventory, write_csv_report


class InventoryTests(unittest.TestCase):
    def test_detects_discord_channels_without_reading_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "user"
            roaming = home / "AppData" / "Roaming"
            (roaming / "discord" / "Local Storage" / "leveldb").mkdir(parents=True)
            (roaming / "discordptb").mkdir(parents=True)
            report = build_inventory(home=home, env={"APPDATA": str(roaming), "LOCALAPPDATA": str(home / "AppData" / "Local")}, system="Windows")
            clients = {row["client"]: row for row in report["discord_clients"]}
            self.assertTrue(clients["Discord Stable"]["user_data_found"])
            self.assertTrue(clients["Discord Stable"]["local_storage_folder_found"])
            self.assertTrue(clients["Discord PTB"]["user_data_found"])
            self.assertFalse(clients["Discord Canary"]["user_data_found"])
            self.assertIn("No credential files", " ".join(report["limitations"]))

    def test_detects_browser_profile_names_only(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "user"
            local = home / "AppData" / "Local"
            roaming = home / "AppData" / "Roaming"
            (local / "Google" / "Chrome" / "User Data" / "Default" / "Local Storage").mkdir(parents=True)
            (local / "Google" / "Chrome" / "User Data" / "Profile 2").mkdir(parents=True)
            report = build_inventory(home=home, env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local)}, system="Windows")
            chrome = [row for row in report["browser_profiles"] if row["browser"] == "Google Chrome"]
            self.assertEqual({row["profile"] for row in chrome}, {"Default", "Profile 2"})
            default = next(row for row in chrome if row["profile"] == "Default")
            self.assertTrue(default["local_storage_folder_found"])

    def test_csv_export_contains_profile_metadata_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "user"
            local = home / "AppData" / "Local"
            roaming = home / "AppData" / "Roaming"
            (local / "Google" / "Chrome" / "User Data" / "Default").mkdir(parents=True)
            report = build_inventory(
                home=home,
                env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local)},
                system="Windows",
            )
            output = root / "inventory.csv"
            write_csv_report(report, output)
            with output.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertIn("application", rows[0])
            self.assertIn("local_storage_folder_found", rows[0])
            self.assertNotIn("token", rows[0])
            self.assertNotIn("cookie", rows[0])
            self.assertTrue(any(row["application"] == "Google Chrome" for row in rows))

    def test_missing_roots_are_reported_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            report = build_inventory(home=Path(temp) / "empty", env={}, system="Windows")
            self.assertEqual(report["browser_profiles"], [])
            self.assertEqual(len(report["discord_clients"]), 3)
            self.assertTrue(all(not row["user_data_found"] for row in report["discord_clients"]))


if __name__ == "__main__":
    unittest.main()
