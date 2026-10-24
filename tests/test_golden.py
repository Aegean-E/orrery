import contextlib
import io
from pathlib import Path
import unittest

from orrery.cli import main

GOLDEN = Path(__file__).resolve().parent / "golden"
KEYS = ("solar", "figure-eight", "binary", "trojans", "pythagorean", "lagrange")


class GoldenFrameTests(unittest.TestCase):
    def test_frames_are_stable(self):
        for key in KEYS:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = main([
                    "snapshot", key, "--width", "60", "--height", "16",
                    "--ascii", "--no-color", "--no-trail",
                ])
            expected = (GOLDEN / f"{key}.txt").read_text(encoding="utf-8")
            with self.subTest(scenario=key):
                self.assertEqual(code, 0)
                self.assertEqual(buffer.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
