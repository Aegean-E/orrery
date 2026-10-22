import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from orrery.cli import main


def run_cli(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, output.getvalue()


class ListAndInfoTests(unittest.TestCase):
    def test_list_shows_every_scenario(self):
        code, output = run_cli("list")
        self.assertEqual(code, 0)
        for key in ("solar", "figure-eight", "binary", "trojans"):
            self.assertIn(key, output)

    def test_info_prints_a_table(self):
        code, output = run_cli("info", "solar")
        self.assertEqual(code, 0)
        self.assertIn("Inner Solar System", output)
        self.assertIn("Earth", output)
        self.assertIn("initial energy", output)

    def test_info_json_contains_orbital_elements(self):
        code, output = run_cli("info", "solar", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["key"], "solar")
        earth = next(body for body in payload["bodies"] if body["name"] == "Earth")
        self.assertAlmostEqual(earth["semi_major_axis"], 1.0, delta=0.01)
        self.assertAlmostEqual(earth["eccentricity"], 0.0167, delta=1e-3)
        self.assertAlmostEqual(earth["period"], 365.2569, delta=2.0)
        self.assertLess(payload["energy"], 0.0)
        self.assertTrue(payload["dominant_primary"])

    def test_equal_mass_system_does_not_invent_orbital_elements(self):
        code, output = run_cli("info", "figure-eight", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertFalse(payload["dominant_primary"])
        self.assertTrue(all(body["semi_major_axis"] is None for body in payload["bodies"]))

    def test_usage_error_has_the_same_triad(self):
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(stderr):
                main(["--not-a-command"])
        self.assertEqual(2, caught.exception.code)
        self.assertIn("Why:", stderr.getvalue())
        self.assertIn("Fix:", stderr.getvalue())


class SnapshotTests(unittest.TestCase):
    def test_snapshot_at_zero_is_ascii_clean(self):
        code, output = run_cli("snapshot", "solar", "--width", "40", "--height", "12",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY | Inner Solar System", output)
        self.assertIn("@ Sun", output)
        self.assertIn("t = 0.00 d", output)
        self.assertTrue(all(ord(char) < 128 for char in output))

    def test_snapshot_advances_time(self):
        code, output = run_cli("snapshot", "solar", "--at", "100",
                               "--width", "40", "--height", "12", "--ascii")
        self.assertEqual(code, 0)
        self.assertIn("t = 100.00 d", output)

    def test_negative_time_is_refused(self):
        code, output = run_cli("snapshot", "solar", "--at", "-1", "--width", "40",
                               "--height", "12")
        self.assertEqual(code, 2)
        self.assertIn("Error: --at -1", output)
        self.assertIn("Why:", output)
        self.assertIn("Fix:", output)

    def test_bad_width_is_refused(self):
        code, output = run_cli("snapshot", "solar", "--width", "5")
        self.assertEqual(code, 2)
        self.assertIn("--width 5", output)

    def test_unknown_scenario_is_a_friendly_error(self):
        code, output = run_cli("snapshot", "nibiru")
        self.assertEqual(code, 1)
        self.assertIn("Error: unknown scenario 'nibiru'.", output)
        self.assertIn("solar", output)
        self.assertIn("Fix:", output)


class RunTests(unittest.TestCase):
    def test_one_frame_renders_the_first_step(self):
        code, output = run_cli("run", "solar", "--frames", "1", "--width", "40",
                               "--height", "12", "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY | Inner Solar System", output)
        self.assertIn("t = 1.60 d", output)


class ExportTests(unittest.TestCase):
    def test_export_writes_sampled_csv_without_leftovers(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "solar.csv"
            code, output = run_cli("export", "solar", "--out", str(target),
                                   "--until", "10", "--every", "2")
            self.assertEqual(code, 0)
            self.assertIn("30 rows", output)
            with target.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], ["time", "body", "x", "y", "vx", "vy", "speed"])
            self.assertEqual(len(rows), 1 + 6 * 5)
            self.assertEqual(rows[1][1], "Sun")
            self.assertEqual(sorted({row[0] for row in rows[1:]}),
                             ["0", "10", "2", "4", "6", "8"])
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_missing_export_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "missing" / "solar.csv"
            code, output = run_cli("export", "solar", "--out", str(target))
            self.assertEqual(code, 2)
            self.assertIn("does not exist", output)


if __name__ == "__main__":
    unittest.main()
