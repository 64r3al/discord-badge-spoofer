import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app import APP_VERSION, MainWindow


class DesktopAppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_window_builds_all_pages(self):
        window = MainWindow()
        self.assertEqual(window.pages.count(), 5)
        self.assertEqual(window.windowTitle(), f"IVX Discord Lab · {APP_VERSION}")
        self.assertGreater(window.minimumWidth(), 0)
        window.close()

    def test_game_badge_guide_has_safe_actions(self):
        window = MainWindow()
        self.assertTrue(window.badge_check_button.isEnabled())
        self.assertEqual(window.badge_check_button.property("test_id"), "badgeCheckButton")
        self.assertIn("official badge guide", window.badge_guide_button.text().lower())
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
        self.assertEqual(window.page_title.text(), "Export reports")
        window.close()


if __name__ == "__main__":
    unittest.main()
