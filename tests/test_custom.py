import contextlib
import copy
import io
import json
from pathlib import Path
import string
import tempfile
import unittest

from orrery.cli import main
from orrery.custom import load_scenario_file

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "custom-two-body.json"


def run_cli(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, output.getvalue()


class CustomScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def _write(self, payload):
        path = Path(self.temporary.name) / "scenario.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _run_validate(self, path):
        return run_cli("validate", str(path))

    def test_example_loads_with_units_and_defaults(self):
        scenario = load_scenario_file(EXAMPLE)
        self.assertEqual(scenario.key, "custom-two-body")
        self.assertEqual(len(scenario.bodies), 2)
        self.assertEqual(scenario.extent, (1.2, 1.2))
        self.assertEqual(scenario.time_unit, "t")
        self.assertEqual(scenario.speed_scale, 1.0)

    def test_validate_and_snapshot_accept_a_json_path(self):
        code, output = self._run_validate(EXAMPLE)
        self.assertEqual(code, 0)
        self.assertIn("OK: custom-two-body", output)
        code, output = run_cli("snapshot", str(EXAMPLE), "--width", "40", "--height", "12",
                               "--ascii", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("Custom Two-Body System", output)
        self.assertIn("S Sun   P Planet", output)

    def test_optional_fields_have_documented_defaults(self):
        payload = {
            "g": 1.0,
            "dt": 0.1,
            "span": 2.0,
            "extent": [1.0, 1.0],
            "bodies": [{
                "name": "Solo",
                "mass": 1.0,
                "position": [0.0, 0.0],
                "velocity": [0.0, 0.0],
                "symbol": "S",
            }],
        }
        scenario = load_scenario_file(self._write(payload))
        self.assertEqual(scenario.steps_per_frame, 1)
        self.assertEqual(scenario.trail_length, 1000)
        self.assertEqual(scenario.default_frames, 120)
        self.assertEqual(scenario.time_unit, "t")
        self.assertEqual(scenario.speed_scale, 1.0)

    def test_missing_file_is_a_friendly_error(self):
        code, output = self._run_validate(Path(self.temporary.name) / "missing.json")
        self.assertEqual(code, 1)
        self.assertIn("does not exist", output)
        self.assertIn("Error:", output)
        self.assertIn("Fix:", output)

    def test_invalid_json_is_reported(self):
        path = Path(self.temporary.name) / "broken.json"
        path.write_text("{", encoding="utf-8")
        code, output = self._run_validate(path)
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", output)

    def test_non_finite_numbers_are_rejected(self):
        payload = copy.deepcopy(self.base)
        payload["g"] = float("nan")
        code, output = self._run_validate(self._write(payload))
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", output)

    def test_duplicate_symbols_are_rejected(self):
        payload = copy.deepcopy(self.base)
        payload["bodies"][1]["symbol"] = "S"
        code, output = self._run_validate(self._write(payload))
        self.assertEqual(code, 1)
        self.assertIn("symbols must be unique", output)

    def test_body_outside_extent_is_rejected(self):
        payload = copy.deepcopy(self.base)
        payload["bodies"][1]["position"] = [9.0, 0.0]
        code, output = self._run_validate(self._write(payload))
        self.assertEqual(code, 1)
        self.assertIn("outside its extent", output)

    def test_control_text_and_unknown_colours_are_rejected(self):
        unsafe_title = copy.deepcopy(self.base)
        unsafe_title["title"] = "bad\x1b[31mtitle"
        unknown_colour = copy.deepcopy(self.base)
        unknown_colour["bodies"][0]["color"] = "ultraviolet"
        for label, payload in (("control", unsafe_title), ("colour", unknown_colour)):
            code, output = self._run_validate(self._write(payload))
            self.assertEqual(code, 1, label)
            self.assertIn("Error:", output, label)

    def test_body_limit_is_enforced(self):
        payload = copy.deepcopy(self.base)
        symbols = string.ascii_letters + string.digits + "!@#$%^&*()"
        payload["bodies"] = [
            {
                "name": f"Body {index}",
                "mass": 1.0,
                "position": [0.0, 0.0],
                "velocity": [0.0, 0.0],
                "symbol": symbols[index],
            }
            for index in range(65)
        ]
        code, output = self._run_validate(self._write(payload))
        self.assertEqual(code, 1)
        self.assertIn("1-64 entries", output)

    def test_custom_scenario_with_charge_and_coulomb(self):
        payload = copy.deepcopy(self.base)
        payload["k_e"] = 2.5
        payload["bodies"][0]["charge"] = 1.0
        payload["bodies"][1]["charge"] = -1.0
        scenario = load_scenario_file(self._write(payload))
        self.assertEqual(scenario.k_e, 2.5)
        self.assertEqual(scenario.bodies[0].charge, 1.0)
        self.assertEqual(scenario.bodies[1].charge, -1.0)


if __name__ == "__main__":
    unittest.main()
