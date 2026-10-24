import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from orrery.cli import KeyboardReader, _compose_frame, _sparkline, _viewport, main
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
        for key in ("solar", "figure-eight", "binary", "trojans", "pythagorean", "lagrange",
                    "rutherford", "bohr", "black-hole"):
            self.assertIn(key, output)

    def test_list_json_is_a_machine_readable_catalogue(self):
        code, output = run_cli("list", "--json")
        self.assertEqual(code, 0)
        catalogue = json.loads(output)
        self.assertEqual([entry["key"] for entry in catalogue],
                         ["solar", "figure-eight", "binary", "trojans", "pythagorean", "lagrange",
                          "rutherford", "bohr", "black-hole"])
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

    def test_camera_pan_zoom_and_tracking(self):
        keys = iter(["f", "1", "w", "a", "s", "d", "[", "]", "0", "q"])

        def fake_poll(self):
            return next(keys, None)

        with mock.patch.object(KeyboardReader, "poll", fake_poll):
            with mock.patch("sys.stdout.isatty", return_value=True):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    code, output = run_cli("run", "solar", "--frames", "0",
                                           "--ascii", "--no-color")
                    self.assertEqual(code, 0)
                    self.assertIn("Stopped at t =", output)

    def test_scenario_switching_keys(self):
        keys = iter(["n", "p", "q"])

        def fake_poll(self):
            return next(keys, None)

        with mock.patch.object(KeyboardReader, "poll", fake_poll):
            with mock.patch("sys.stdout.isatty", return_value=True):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    code, output = run_cli("run", "solar", "--frames", "0",
                                           "--ascii", "--no-color")
                    self.assertEqual(code, 0)

    def test_cli_relativity_and_merge_flags(self):
        code, output = run_cli("snapshot", "solar", "--relativity", "--c-light", "100.0",
                               "--ascii", "--no-color", "--no-trail")
        self.assertEqual(code, 0)
        code, output = run_cli("snapshot", "solar", "--merge", "--merge-radius", "0.05",
                               "--ascii", "--no-color", "--no-trail")
        self.assertEqual(code, 0)

    def test_run_paused_single_step(self):
        keys = iter([" ", ".", ">", "q"])

        def fake_poll(self):
            return next(keys, None)

        with mock.patch.object(KeyboardReader, "poll", fake_poll):
            with mock.patch("sys.stdout.isatty", return_value=True):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    code, output = run_cli("run", "solar", "--frames", "0",
                                           "--ascii", "--no-color")
                    self.assertEqual(code, 0)
                    self.assertIn("Stopped at t =", output)

    def test_export_relativity_and_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "rel_merge.json"
            code, output = run_cli("export", "solar", "--out", str(target),
                                   "--until", "2", "--every", "1", "--format", "json",
                                   "--relativity", "--c-light", "120.0",
                                   "--merge", "--merge-radius", "0.05")
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertTrue(payload["scenario"]["export"]["relativity"])
            self.assertEqual(payload["scenario"]["export"]["c"], 120.0)
            self.assertEqual(payload["scenario"]["export"]["merge_radius"], 0.05)

    def test_keyboard_arrow_mapping(self):
        fake_msvcrt = mock.MagicMock()
        fake_msvcrt.kbhit.side_effect = [True, True, True, True, False]
        fake_msvcrt.getwch.side_effect = ["\xe0", "H", "\xe0", "M"]
        with mock.patch("sys.stdin.isatty", return_value=True):
            with mock.patch.dict("sys.modules", {"msvcrt": fake_msvcrt}):
                with mock.patch("os.name", "nt"):
                    reader = KeyboardReader(enabled=True)
                    self.assertEqual(reader.poll(), "w")
                    self.assertEqual(reader.poll(), "d")

    def test_compose_frame_fps_and_step_hint(self):
        scenario = SCENARIOS["solar"]
        world = World(scenario.bodies, scenario.g)
        recorder = mock.MagicMock()
        recorder.trails = [[] for _ in world.bodies]
        viewport = _viewport(scenario, 80, 24, 2.0)
        frame = _compose_frame(
            world, scenario, viewport, recorder, world.total_energy(),
            ascii_only=True, color=False, fps=24.0, controls_hint=True,
        )
        self.assertIn("fps = 24.0", frame)
        self.assertIn("[.] Step", frame)
        self.assertIn("[{}] Aspect", frame)
        self.assertIn("[b] Dots", frame)

    def test_cli_dot_option_snapshot(self):
        code, output = run_cli("snapshot", "solar", "--dot", "circle",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY |", output)

        code, output = run_cli("snapshot", "solar", "--dot", "ascii",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY |", output)

    def test_run_interactive_aspect_and_dot_cycling(self):
        keys = iter(["{", "}", "b", "0", "q"])

        def fake_poll(self):
            return next(keys, None)

        with mock.patch.object(KeyboardReader, "poll", fake_poll):
            with mock.patch("sys.stdout.isatty", return_value=True):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    code, output = run_cli("run", "solar", "--frames", "0",
                                           "--ascii", "--no-color")
                    self.assertEqual(code, 0)
                    self.assertIn("Stopped at t =", output)

    def test_cli_bounce_and_restitution_options(self):
        code, output = run_cli("snapshot", "solar", "--bounce", "--bounce-radius", "0.05",
                               "--restitution", "0.9", "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY |", output)

    def test_cli_coulomb_option(self):
        code, output = run_cli("snapshot", "rutherford", "--k-coulomb", "0.2",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY |", output)

    def test_cli_telemetry_hud_energy_decomposition(self):
        code, output = run_cli("snapshot", "solar", "--telemetry", "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("K:", output)
        self.assertIn("U:", output)
        self.assertIn("2K+U:", output)

    def test_web_forwards_initial_world_and_overrides(self):
        with mock.patch("orrery.web.run_server", return_value=0) as run:
            code, output = run_cli(
                "web", "binary", "--no-open", "--dt", "0.5", "--time-scale", "2.0",
                "--reverse", "--relativity", "--c-light", "10", "--k-coulomb", "0.3",
                "--merge", "--merge-radius", "0.02",
            )
        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["initial_scenario"], "binary")
        self.assertEqual(kwargs["scenario"].key, "binary")
        self.assertFalse(kwargs["auto_open"])
        options = kwargs["options"]
        self.assertEqual(options.dt, 0.5)
        self.assertEqual(options.time_scale, 2.0)
        self.assertTrue(options.reverse)
        self.assertTrue(options.relativity)
        self.assertEqual(options.c_light, 10.0)
        self.assertEqual(options.k_coulomb, 0.3)
        self.assertEqual(options.collision_mode, "merge")
        self.assertEqual(options.merge_radius, 0.02)
        self.assertIsNone(options.bounce_radius)
        self.assertIsNone(options.restitution)

    def test_web_accepts_a_custom_scenario_file(self):
        payload = {
            "key": "web-custom",
            "g": 1.0, "dt": 0.01, "span": 4.0, "extent": [2.0, 2.0],
            "bodies": [
                {"name": "A", "mass": 1.0, "position": [0.0, 0.0],
                 "velocity": [0.0, 0.0], "symbol": "A"},
                {"name": "B", "mass": 1.0, "position": [1.0, 0.0],
                 "velocity": [0.0, 1.0], "symbol": "B"},
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "world.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch("orrery.web.run_server", return_value=0) as run:
                code, output = run_cli("web", str(path), "--no-open")
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args.kwargs["scenario"].key, "web-custom")

    def test_cli_invalid_physics_args_rejected(self):
        code, output = run_cli("snapshot", "solar", "--restitution", "1.5")
        self.assertEqual(code, 2)
        self.assertIn("--restitution", output)

        code, output = run_cli("snapshot", "solar", "--bounce-radius", "-0.1")
        self.assertEqual(code, 2)
        self.assertIn("--bounce-radius", output)

        code, output = run_cli("snapshot", "solar", "--k-coulomb", "-1.0")
        self.assertEqual(code, 2)
        self.assertIn("--k-coulomb", output)

    def test_cli_export_metadata_includes_bounce_and_coulomb(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_file = Path(temp_dir) / "export.json"
            code, output = run_cli("export", "rutherford", "--out", str(out_file),
                                   "--format", "json", "--bounce", "--restitution", "0.85",
                                   "--k-coulomb", "0.25")
            self.assertEqual(code, 0)
            data = json.loads(out_file.read_text(encoding="utf-8"))
            export_meta = data["scenario"]["export"]
            self.assertEqual(export_meta["k_e"], 0.25)
            self.assertEqual(export_meta["bounce_radius"], 0.05)
            self.assertEqual(export_meta["restitution"], 0.85)

    def test_cli_time_options_dt_and_reverse(self):
        code, output = run_cli("snapshot", "solar", "--dt", "0.05", "--reverse",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY |", output)

    def test_cli_time_options_warp(self):
        code, output = run_cli("snapshot", "solar", "--warp", "2.5",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("ORRERY |", output)

    def test_cli_invalid_time_args(self):
        code, output = run_cli("snapshot", "solar", "--dt", "-0.1")
        self.assertEqual(code, 2)
        self.assertIn("--dt", output)

        code, output = run_cli("snapshot", "solar", "--time-scale", "0.0")
        self.assertEqual(code, 2)
        self.assertIn("--time-scale", output)

    def test_run_interactive_time_keys(self):
        # Keys: 'x' (faster), 'z' (slower), 'v' (reverse), 'q' (quit)
        keys = iter(["x", "z", "v", "q"])

        def fake_poll(self):
            return next(keys, None)

        with mock.patch.object(KeyboardReader, "poll", fake_poll):
            with mock.patch("sys.stdout.isatty", return_value=True):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    code, output = run_cli("run", "solar", "--frames", "0",
                                           "--ascii", "--no-color")
                    self.assertEqual(code, 0)
                    self.assertIn("Stopped at t =", output)

    def test_cli_web_subcommand_help(self):
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stdout(stdout):
                main(["web", "--help"])
        self.assertEqual(caught.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("--port", output)
        self.assertIn("--no-open", output)


if __name__ == "__main__":
    unittest.main()
