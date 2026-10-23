import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from app import APP_VERSION, MainWindow, discord_process_status


class DesktopAppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_window_builds_all_pages(self):
        window = MainWindow(auto_fetch_catalog=False)
        self.assertEqual(window.pages.count(), 7)
        self.assertEqual(window.windowTitle(), f"IVX Discord Lab · {APP_VERSION}")
        self.assertGreater(window.minimumWidth(), 0)
        window.close()

    def test_account_profiles_page_uses_official_identity_flow(self):
        window = MainWindow(auto_fetch_catalog=False)
        self.assertEqual(window.identity_verify_button.property("test_id"), "identityVerifyButton")
        self.assertEqual(window.identity_client_secret_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertIn("127.0.0.1:8765/callback", window.identity_redirect_label.text())
        self.assertIn("No Discord session tokens or cookies", " ".join(
            label.text() for label in window.findChildren(QLabel)
        ))
        self.assertEqual(window.identity_accounts_table.rowCount(), len(window.verified_accounts))
        window.close()

    def test_saved_identity_labels_appear_in_picker_without_auth_data(self):
        window = MainWindow(auto_fetch_catalog=False)
        window.verified_accounts = [{
            "id": "123456789012345678",
            "username": "qa_account",
            "global_name": "QA Test",
            "avatar": "",
            "label": "TEST ACCOUNT",
        }]
        window._render_verified_accounts()
        self.assertEqual(window.identity_accounts_table.rowCount(), 1)
        self.assertIn("qa_account", window.identity_accounts_table.cellWidget(1, 1).findChildren(QLabel)[1].text())
        index = window.activity_profile_combo.findData("123456789012345678")
        self.assertGreaterEqual(index, 0)
        self.assertIn("TEST ACCOUNT", window.activity_profile_combo.itemText(index))
        window.close()

    def test_game_badge_guide_has_safe_actions(self):
        window = MainWindow(auto_fetch_catalog=False)
        self.assertTrue(window.badge_check_button.isEnabled())
        self.assertEqual(window.badge_check_button.property("test_id"), "badgeCheckButton")
        self.assertIn("official badge guide", window.badge_guide_button.text().lower())
        label_text = " ".join(label.text() for label in window.findChildren(QLabel))
        self.assertIn("Use data to personalize my Discord experience", label_text)
        self.assertIn("no fake activity", label_text.casefold())
        window.close()

    def test_readiness_check_waits_for_initial_scan(self):
        window = MainWindow(auto_fetch_catalog=False)
        window.scan_completed = False
        with patch("app.QMessageBox.information") as information:
            window.run_badge_readiness_check()
        information.assert_called_once()
        self.assertIn("has not completed successfully", information.call_args.args[2])
        window.close()

    def test_windows_process_check_detects_discord_stable_and_ptb(self):
        output = (
            '"Discord.exe","1234","Console","1","60,000 K"\r\n'
            '"DiscordPTB.exe","5678","Console","1","60,000 K"\r\n'
            '"chrome.exe","9012","Console","1","120,000 K"\r\n'
        )
        with patch("app.sys.platform", "win32"), patch("app.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=output)
            self.assertEqual(discord_process_status(), (True, "discord.exe, discordptb.exe"))
            run.assert_called_once()

    def test_windows_process_check_reports_no_discord_process(self):
        with patch("app.sys.platform", "win32"), patch("app.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout='"chrome.exe","9012","Console","1","120,000 K"\r\n')
            self.assertEqual(discord_process_status(), (False, ""))
            run.assert_called_once()

    def test_activity_lab_configures_game_hours_and_controls(self):
        window = MainWindow(auto_fetch_catalog=False)
        self.assertEqual(window.activity_game_list.count(), 8)
        self.assertEqual(window.activity_hours_spin.value(), 2)
        self.assertFalse(window.activity_start_button.isEnabled())
        window.activity_game_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.qt_app.processEvents()
        self.assertTrue(window.activity_start_button.isEnabled())
        self.assertIn("1 game selected · 2 simulated hours", window.activity_total_label.text())
        window.activity_start_button.click()
        self.qt_app.processEvents()
        self.assertTrue(window.activity_timer.isActive())
        self.assertIn("No Discord request will be made.", window.activity_log.toPlainText())
        window.activity_pause_button.click()
        self.assertTrue(window.activity_paused)
        self.assertFalse(window.activity_timer.isActive())
        window.activity_pause_button.click()
        self.assertTrue(window.activity_timer.isActive())
        window.activity_stop_button.click()
        self.assertFalse(window.activity_timer.isActive())
        self.assertIn("No activity or credentials sent to Discord", window.activity_log.toPlainText())
        window.close()

    def test_catalog_result_populates_searchable_picker(self):
        window = MainWindow(auto_fetch_catalog=False)
        sample = [
            {
                "id": "catalog-1",
                "name": "Planet Builder",
                "executable": "planetbuilder.exe",
            },
            {
                "id": "catalog-2",
                "name": "Zeta Racing",
                "executable": "zeta.exe",
            },
        ]
        window._apply_activity_catalog(sample, "Test catalog", "Loaded 2 games.")
        self.assertEqual(window.activity_game_list.count(), 2)
        self.assertIn("Test catalog", window.activity_catalog_status.text())
        window.activity_game_search.setText("planetbuilder.exe")
        self.qt_app.processEvents()
        self.assertEqual(window.activity_game_list.count(), 1)
        self.assertIn("Planet Builder", window.activity_game_list.item(0).text())
        window.activity_game_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.qt_app.processEvents()
        self.assertEqual(len(window._selected_activity_games()), 1)
        self.assertIn("1 game selected", window.activity_total_label.text())
        window.close()

    def test_animated_navigation_has_independent_overlays(self):
        window = MainWindow(auto_fetch_catalog=False)
        self.assertIsNotNone(window.nav_indicator)
        self.assertIsNotNone(window.page_sweep)
        window.navigate(2)
        self.qt_app.processEvents()
        self.assertIsNotNone(window.nav_indicator_animation)
        self.assertIsNotNone(window.page_sweep_animation)
        self.assertIsNone(window.pages.widget(2).graphicsEffect())
        window.close()

    def test_metric_card_counts_up_smoothly(self):
        window = MainWindow(auto_fetch_catalog=False)
        metric = window.metric_browsers
        metric.animate_value(4, suffix=" profiles")
        self.assertIsNotNone(metric._count_animation)
        metric._count_animation.setCurrentTime(metric._count_animation.duration())
        self.qt_app.processEvents()
        self.assertEqual(metric.value_label.text(), "4 profiles")
        window.close()

    def test_scan_and_catalog_loading_indicators_update(self):
        window = MainWindow(auto_fetch_catalog=False)
        window._animate_scan_spinner()
        self.assertTrue(window.scan_button.text().endswith("Scanning profiles…"))
        window._animate_catalog_loading()
        self.assertIn("Fetching public game catalog", window.activity_catalog_status.text())
        window.close()

    def test_navigation_switches_pages(self):
        window = MainWindow(auto_fetch_catalog=False)
        window.navigate(1)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 1)
        window.navigate(2)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 2)
        self.assertEqual(window.page_title.text(), "Account profiles")
        window.navigate(3)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 3)
        self.assertEqual(window.page_title.text(), "Game badges")
        window.navigate(4)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 4)
        self.assertEqual(window.page_title.text(), "Activity Lab")
        window.navigate(5)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 5)
        self.assertEqual(window.page_title.text(), "Export reports")
        for page_index in range(window.pages.count()):
            self.assertIsNone(window.pages.widget(page_index).graphicsEffect())
        window.close()


if __name__ == "__main__":
    unittest.main()
