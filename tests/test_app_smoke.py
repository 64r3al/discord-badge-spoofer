import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app import APP_VERSION, MainWindow, discord_process_status


class DesktopAppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_window_builds_all_pages(self):
        window = MainWindow()
        self.assertEqual(window.pages.count(), 6)
        self.assertEqual(window.windowTitle(), f"IVX Discord Lab · {APP_VERSION}")
        self.assertGreater(window.minimumWidth(), 0)
        window.close()

    def test_game_badge_guide_has_safe_actions(self):
        window = MainWindow()
        self.assertTrue(window.badge_check_button.isEnabled())
        self.assertEqual(window.badge_check_button.property("test_id"), "badgeCheckButton")
        self.assertIn("official badge guide", window.badge_guide_button.text().lower())
        label_text = " ".join(label.text() for label in window.findChildren(QLabel))
        self.assertIn("Use data to personalize my Discord experience", label_text)
        self.assertIn("no fake activity", label_text.casefold())
        window.close()

    def test_readiness_check_waits_for_initial_scan(self):
        window = MainWindow()
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
        window = MainWindow()
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

    def test_navigation_switches_pages(self):
        window = MainWindow()
        window.navigate(1)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 1)
        window.navigate(2)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 2)
        self.assertEqual(window.page_title.text(), "Game badges")
        window.navigate(3)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 3)
        self.assertEqual(window.page_title.text(), "Activity Lab")
        window.navigate(4)
        self.qt_app.processEvents()
        self.assertEqual(window.pages.currentIndex(), 4)
        self.assertEqual(window.page_title.text(), "Export reports")
        for page_index in range(window.pages.count()):
            self.assertIsNone(window.pages.widget(page_index).graphicsEffect())
        window.close()


if __name__ == "__main__":
    unittest.main()
