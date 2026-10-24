import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from orrery.cli import KeyboardReader, _sparkline, _viewport, main
from orrery.scenarios import SCENARIOS
from orrery.sim import World


def run_cli(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, output.getvalue()


class ListAndInfoTests(unittest.TestCase):
    def test_list_shows_every_scenario(self):
        code, output = run_cli("list")
        self.assertEqual(code, 0)
        for key in ("solar", "figure-eight", "binary", "trojans", "pythagorean", "lagrange"):
            self.assertIn(key, output)

    def test_list_json_is_a_machine_readable_catalogue(self):
        code, output = run_cli("list", "--json")
        self.assertEqual(code, 0)
        catalogue = json.loads(output)
        self.assertEqual([entry["key"] for entry in catalogue],
                         ["solar", "figure-eight", "binary", "trojans", "pythagorean", "lagrange"])
        self.assertEqual(catalogue[0]["units"]["distance"], "AU")
        self.assertEqual(catalogue[0]["extent"], [1.75, 1.7])

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
        self.assertIn("Error:", stderr.getvalue())
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

    def test_narrow_snapshot_never_exceeds_width(self):
        code, output = run_cli("snapshot", "trojans", "--width", "20", "--height", "8",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        lines = output.rstrip("\n").splitlines()
        self.assertTrue(lines)
        for line in lines:
            self.assertLessEqual(len(line), 20, line)

    def test_braille_is_default_and_can_be_disabled(self):
        code, output = run_cli("snapshot", "solar", "--at", "30", "--width", "40",
                               "--height", "12", "--no-color")
        self.assertEqual(code, 0)
        self.assertTrue(any(0x2800 <= ord(char) <= 0x28FF for char in output))
        code, output = run_cli("snapshot", "solar", "--at", "30", "--width", "40",
                               "--height", "12", "--no-color", "--no-braille")
        self.assertEqual(code, 0)
        self.assertFalse(any(0x2800 <= ord(char) <= 0x28FF for char in output))

    def test_aspect_can_be_overridden_and_is_validated(self):
        code, _ = run_cli("snapshot", "solar", "--aspect", "0.5", "--width", "40",
                          "--height", "12", "--ascii", "--no-color")
        self.assertEqual(code, 0)
        code, output = run_cli("snapshot", "solar", "--aspect", "0.01", "--width", "40",
                               "--height", "12", "--ascii", "--no-color")
        self.assertEqual(code, 2)
        self.assertIn("--aspect 0.01", output)

    def test_all_scenarios_are_visible_at_minimum_size(self):
        for scenario in SCENARIOS.values():
            world = World(scenario.bodies, scenario.g)
            viewport = _viewport(scenario, 20, 8)
            with self.subTest(scenario=scenario.key):
                self.assertTrue(
                    all(viewport.cell(body.pos) is not None for body in world.bodies)
                )

    def test_snapshot_step_budget_can_be_overridden(self):
        with mock.patch("orrery.cli.SNAPSHOT_STEP_LIMIT", 10):
            code, output = run_cli("snapshot", "solar", "--at", "100",
                                   "--width", "40", "--height", "12", "--ascii")
            self.assertEqual(code, 2)
            self.assertIn("--force", output)
            code, output = run_cli("snapshot", "solar", "--at", "100", "--force",
                                   "--width", "40", "--height", "12", "--ascii")
            self.assertEqual(code, 0)
            self.assertIn("t = 100.00 d", output)

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

    def test_frame_rate_range_is_enforced(self):
        for fps in ("0.01", "500"):
            code, output = run_cli("run", "solar", "--frames", "1", "--fps", fps,
                                   "--width", "40", "--height", "12", "--ascii")
            self.assertEqual(code, 2, fps)
            self.assertIn("outside the supported range", output)

    def test_piped_run_defaults_to_one_frame(self):
        code, output = run_cli("run", "solar", "--width", "40", "--height", "12",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertEqual(output.count("ORRERY | Inner Solar System"), 1)


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

    def test_overflowing_export_window_is_a_friendly_error(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "overflow.csv"
            code, output = run_cli("export", "solar", "--out", str(target),
                                   "--until", "1", "--every", "5e-324")
            self.assertEqual(code, 2)
            self.assertIn("export window is too large", output)
            self.assertIn("Error:", output)
            self.assertNotIn("Traceback", output)

    def test_export_json_contains_metadata_and_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "solar.json"
            code, output = run_cli("export", "solar", "--out", str(target),
                                   "--until", "1", "--every", "2", "--format", "json")
            self.assertEqual(code, 0)
            self.assertIn("(json)", output)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["scenario"]["key"], "solar")
            self.assertEqual(payload["scenario"]["units"]["distance"], "AU")
            self.assertEqual(payload["scenario"]["export"]["samples"], 2)
            self.assertEqual(len(payload["samples"]), 2)
            self.assertEqual([sample["time"] for sample in payload["samples"]], [0.0, 1.0])
            self.assertEqual(payload["samples"][0]["bodies"][0]["name"], "Sun")
            self.assertEqual(len(payload["samples"][0]["bodies"]), 5)

    def test_export_always_includes_the_final_state(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "final.csv"
            code, output = run_cli("export", "solar", "--out", str(target),
                                   "--until", "1", "--every", "2")
            self.assertEqual(code, 0)
            self.assertIn("2 samples", output)
            with target.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(len(rows), 1 + 2 * 5)
            self.assertEqual(sorted({row[0] for row in rows[1:]}), ["0", "1"])


class InteractiveAndTelemetryTests(unittest.TestCase):
    def test_sparkline_rendering(self):
        self.assertEqual(_sparkline([], 10), "")
        flat = _sparkline([1.0, 1.0, 1.0], 5, ascii_only=True)
        self.assertEqual(len(flat), 3)
        spark = _sparkline([-1.0, 0.0, 1.0], 10, ascii_only=True)
        self.assertEqual(len(spark), 3)
        self.assertEqual(spark[0], ".")
        self.assertEqual(spark[-1], "#")

    def test_keyboard_reader_disabled(self):
        reader = KeyboardReader(enabled=False)
        with reader as kb:
            self.assertIsNone(kb.poll())

    def test_snapshot_telemetry_output(self):
        code, output = run_cli("snapshot", "solar", "--telemetry", "--ascii", "--no-color", "--no-trail")
        self.assertEqual(code, 0)
        self.assertIn("trend: [", output)
        self.assertIn("min:", output)
        self.assertIn("max:", output)

    def test_run_telemetry_and_no_controls(self):
        code, output = run_cli("run", "solar", "--frames", "1", "--telemetry",
                               "--no-controls", "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("trend: [", output)

    def test_run_interactive_keyboard_events(self):
        keys = iter([" ", "+", "-", "c", "t", "q"])

        def fake_poll(self):
            return next(keys, None)

        with mock.patch.object(KeyboardReader, "poll", fake_poll):
            with mock.patch("sys.stdout.isatty", return_value=True):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    code, output = run_cli("run", "solar", "--frames", "0",
                                           "--ascii", "--no-color")
                    self.assertEqual(code, 0)
                    self.assertIn("Stopped at t =", output)


if __name__ == "__main__":
    unittest.main()
