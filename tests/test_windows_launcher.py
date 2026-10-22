from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsLauncherContractTests(unittest.TestCase):
    def setUp(self):
        self.launcher = (ROOT / "START_IVX_DISCORD_LAB.bat").read_text(encoding="utf-8")

    def test_launcher_creates_environment_installs_requirements_and_runs_ui(self):
        self.assertIn('python.exe', self.launcher)
        self.assertIn(' -m venv ".venv"', self.launcher)
        self.assertIn(' -m pip install', self.launcher)
        self.assertIn('"app.py"', self.launcher)
        self.assertIn('"requirements.txt"', self.launcher)

    def test_launcher_does_not_start_the_legacy_spoofer(self):
        self.assertNotIn('"spoofer.py"', self.launcher)
        self.assertNotIn('python spoofer.py', self.launcher.lower())

    def test_launcher_includes_actionable_setup_errors(self):
        self.assertIn(':no_python', self.launcher)
        self.assertIn(':install_failed', self.launcher)
        self.assertIn('https://www.python.org/downloads/windows/', self.launcher)


if __name__ == "__main__":
    unittest.main()
