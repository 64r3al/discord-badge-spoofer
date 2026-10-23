from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsLauncherContractTests(unittest.TestCase):
    def setUp(self):
        self.launcher = (ROOT / "START_IVX_DISCORD_LAB.bat").read_text(encoding="utf-8")

    def test_launcher_starts_the_animated_bootstrapper(self):
        self.assertIn('"bootstrap.py"', self.launcher)
        self.assertIn('py -3 "bootstrap.py"', self.launcher)
        self.assertIn('python "bootstrap.py"', self.launcher)
        self.assertIn('"app.py"', self.launcher)
        self.assertIn('"requirements.txt"', self.launcher)
        self.assertIn(':capture_exit', self.launcher)

    def test_launcher_does_not_start_the_legacy_spoofer(self):
        self.assertNotIn('"spoofer.py"', self.launcher)
        self.assertNotIn('python spoofer.py', self.launcher.lower())

    def test_launcher_includes_actionable_setup_errors(self):
        self.assertIn(':no_python', self.launcher)
        self.assertIn(':missing_bootstrap', self.launcher)
        self.assertIn('https://www.python.org/downloads/windows/', self.launcher)
        self.assertIn(':find_python', self.launcher)


if __name__ == "__main__":
    unittest.main()
