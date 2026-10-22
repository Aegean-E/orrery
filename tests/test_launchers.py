"""One-click launch files: present, CRLF-safe on Windows and Python 3.10-aware."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH = ROOT / "run.cmd"
SHELL = ROOT / "run.sh"


class LauncherTest(unittest.TestCase):

    def test_launchers_exist(self):
        for path in (BATCH, SHELL):
            self.assertTrue(path.is_file(), path.name)

    def test_batch_file_has_crlf_line_endings(self):
        data = BATCH.read_bytes()
        self.assertEqual(0, data.replace(b"\r\n", b"").count(b"\n"),
                         "run.cmd must use CRLF so cmd.exe parses it reliably")

    def test_launchers_check_python_310_and_start_the_module(self):
        batch = BATCH.read_text(encoding="utf-8")
        shell = SHELL.read_text(encoding="utf-8")
        for text in (batch, shell):
            self.assertIn("3.10", text)
            self.assertIn("-m orrery run", text)

    def test_batch_failure_stays_visible(self):
        self.assertIn("pause", BATCH.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
