from pathlib import Path
import unittest

from bootstrap import MINIMUM_PYTHON, _tail


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "bootstrap.py").read_text(encoding="utf-8")


class BootstrapContractTests(unittest.TestCase):
    def test_bootstrap_requires_supported_python(self):
        self.assertEqual(MINIMUM_PYTHON, (3, 10))
        self.assertIn("sys.version_info < MINIMUM_PYTHON", SOURCE)

    def test_bootstrap_creates_environment_and_installs_qt(self):
        self.assertIn('"venv"', SOURCE)
        self.assertIn('"pip", "install"', SOURCE)
        self.assertIn("PySide6.QtWidgets", SOURCE)
        self.assertIn("requirements.txt", SOURCE)

    def test_bootstrap_has_responsive_animated_splash(self):
        self.assertIn("threading.Thread", SOURCE)
        self.assertIn("create_polygon", SOURCE)
        self.assertIn("def animate()", SOURCE)
        self.assertIn("def poll_events()", SOURCE)

    def test_bootstrap_starts_only_the_desktop_ui(self):
        self.assertIn('str(APP_FILE)', SOURCE)
        self.assertIn("process.wait()", SOURCE)
        self.assertNotIn("spoofer.py", SOURCE)

    def test_tail_limits_diagnostic_output(self):
        self.assertEqual(_tail("abcdef", 3), "def")
        self.assertEqual(_tail("", 3), "(No additional diagnostic output.)")


if __name__ == "__main__":
    unittest.main()
