import http.server
import json
import threading
import time
import unittest
import urllib.request

from orrery.scenarios import get_scenario
from orrery.web import (
    MAX_REQUEST_BYTES,
    OrreryHandler,
    WebOptions,
    _WebState,
    _catalog_list,
    _json_safe,
    _scenario_to_dict,
    run_server,
)


class WebApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OrreryHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_root_serves_html(self):
        with urllib.request.urlopen(f"{self.base_url}/") as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers.get("Content-Type"))
            html = response.read().decode("utf-8")
            self.assertIn("<canvas id=\"orrery-canvas\">", html)
            self.assertIn("ORRERY", html)

    def test_api_health(self):
        with urllib.request.urlopen(f"{self.base_url}/api/health") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("app"), "orrery")

    def test_api_scenarios_catalogue(self):
        with urllib.request.urlopen(f"{self.base_url}/api/scenarios") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(len(data), 9)
            keys = [item["key"] for item in data]
            self.assertIn("solar", keys)
            self.assertIn("rutherford", keys)
            self.assertIn("bohr", keys)
            self.assertIn("black-hole", keys)

    def test_api_scenario_detail(self):
        with urllib.request.urlopen(f"{self.base_url}/api/scenario/solar") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data["key"], "solar")
            self.assertEqual(len(data["bodies"]), 5)
            self.assertIn("dt", data)
            self.assertIn("span", data)

    def test_api_scenario_not_found(self):
        req = urllib.request.Request(f"{self.base_url}/api/scenario/unknown_world")
        try:
            urllib.request.urlopen(req)
            self.fail("Expected HTTP 404")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 404)
            data = json.loads(err.read().decode("utf-8"))
            self.assertIn("error", data)
            err.close()

    def test_api_validate_endpoint(self):
        # Valid custom payload
        valid_payload = json.dumps({
            "g": 1.0,
            "dt": 0.01,
            "span": 4.0,
            "extent": [2.0, 2.0],
            "bodies": [
                {"name": "A", "mass": 1.0, "position": [0.0, 0.0], "velocity": [0.0, 0.0], "symbol": "A"},
                {"name": "B", "mass": 1.0, "position": [1.0, 0.0], "velocity": [0.0, 1.0], "symbol": "B"}
            ]
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/validate",
            data=valid_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res.get("valid"))

    def test_internal_helpers(self):
        catalog = _catalog_list()
        self.assertEqual(len(catalog), 9)
        detail = _scenario_to_dict("bohr")
        self.assertEqual(detail["key"], "bohr")
        self.assertEqual(detail["k_e"], 0.01)

    def test_run_server_once(self):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OrreryHandler)
        port = server.server_port
        server.server_close()

        results = {}

        def _hit():
            time.sleep(0.08)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health") as resp:
                    results["status"] = resp.status
                    results["data"] = json.loads(resp.read().decode("utf-8"))
            # hygiene: allow test probe failure during server startup
            except Exception as err:
                results["error"] = str(err)

        th = threading.Thread(target=_hit, daemon=True)
        th.start()
        exit_code = run_server(port=port, auto_open=False, once=True)
        th.join(timeout=1.0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(results.get("status"), 200)
        self.assertEqual(results.get("data", {}).get("status"), "ok")


class WebConfigTests(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OrreryHandler)
        self.server.state = _WebState(
            initial_key="bohr",
            options=WebOptions(
                dt=0.25,
                time_scale=2.5,
                reverse=True,
                relativity=False,
                k_coulomb=0.5,
                collision_mode="merge",
                merge_radius=0.02,
            ),
        )
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _get_json(self, path):
        with urllib.request.urlopen(f"{self.base_url}{path}") as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _post_scenario(self, payload):
        request = urllib.request.Request(
            f"{self.base_url}/api/validate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = json.loads(err.read().decode("utf-8"))
            err.close()
            return err.code, body

    @staticmethod
    def _custom_payload(key="my-world", title="My World"):
        return {
            "key": key,
            "title": title,
            "g": 1.0,
            "dt": 0.01,
            "span": 4.0,
            "extent": [2.0, 2.0],
            "bodies": [
                {"name": "A", "mass": 1.0, "position": [0.0, 0.0],
                 "velocity": [0.0, 0.0], "symbol": "A"},
                {"name": "B", "mass": 1.0, "position": [1.0, 0.0],
                 "velocity": [0.0, 1.0], "symbol": "B"},
            ],
        }

    def test_config_reports_initial_world_and_options(self):
        status, data = self._get_json("/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(data["initial"], "bohr")
        self.assertEqual(data["options"]["dt"], 0.25)
        self.assertEqual(data["options"]["time_scale"], 2.5)
        self.assertTrue(data["options"]["reverse"])
        self.assertFalse(data["options"]["relativity"])
        self.assertEqual(data["options"]["k_coulomb"], 0.5)
        self.assertEqual(data["options"]["collision_mode"], "merge")

    def test_options_are_applied_to_scenario_detail(self):
        _, data = self._get_json("/api/scenario/bohr")
        self.assertEqual(data["dt"], 0.25)
        self.assertEqual(data["k_e"], 0.5)
        self.assertIsNone(data["c"])

    def test_relativity_override_sets_speed_of_light(self):
        self.server.state.options = WebOptions(relativity=False)
        _, data = self._get_json("/api/scenario/black-hole")
        self.assertIsNone(data["c"])

        self.server.state.options = WebOptions(relativity=True, c_light=5.0)
        _, data = self._get_json("/api/scenario/black-hole")
        self.assertEqual(data["c"], 5.0)

    def test_scenario_detail_uses_the_effective_coulomb_constant(self):
        self.server.state.options = WebOptions(k_coulomb=0.01)
        _, data = self._get_json("/api/scenario/bohr")
        electron = next(b for b in data["bodies"] if b["name"] == "Electron-1")
        self.assertAlmostEqual(electron["semi_major"], 0.792, delta=0.01)
        self.assertLess(electron["eccentricity"], 0.05)

        self.server.state.options = WebOptions(k_coulomb=0.5)
        _, data = self._get_json("/api/scenario/bohr")
        electron = next(b for b in data["bodies"] if b["name"] == "Electron-1")
        self.assertGreater(electron["eccentricity"], 0.5)

    def test_validated_custom_scenario_can_be_fetched(self):
        status, data = self._post_scenario(self._custom_payload())
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["key"], "my-world")

        status, detail = self._get_json(f"/api/scenario/{data['key']}")
        self.assertEqual(status, 200)
        self.assertEqual(detail["title"], "My World")
        self.assertEqual(len(detail["bodies"]), 2)

        _, catalog = self._get_json("/api/scenarios")
        self.assertIn("my-world", [item["key"] for item in catalog])

    def test_custom_scenario_cannot_shadow_a_builtin_key(self):
        status, data = self._post_scenario(self._custom_payload(key="solar"))
        self.assertEqual(status, 200)
        self.assertEqual(data["key"], "solar-2")
        _, detail = self._get_json("/api/scenario/solar-2")
        self.assertEqual(detail["title"], "My World")
        _, builtin = self._get_json("/api/scenario/solar")
        self.assertEqual(builtin["title"], get_scenario("solar").title)

    def test_json_safe_replaces_non_finite_floats(self):
        self.assertEqual(_json_safe({"a": float("inf"), "b": [float("nan"), 1.5]}),
                         {"a": None, "b": [None, 1.5]})
        self.assertEqual(_json_safe("text"), "text")

    def test_run_server_wires_initial_scenario_and_options(self):
        probe = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OrreryHandler)
        port = probe.server_port
        probe.server_close()

        results = {}

        def _hit():
            time.sleep(0.08)
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/config") as resp:
                    results["data"] = json.loads(resp.read().decode("utf-8"))
            # hygiene: allow test probe failure during server startup
            except Exception as err:
                results["error"] = str(err)

        th = threading.Thread(target=_hit, daemon=True)
        th.start()
        exit_code = run_server(port=port, auto_open=False, once=True,
                               scenario=get_scenario("binary"),
                               options=WebOptions(dt=0.25, reverse=True))
        th.join(timeout=1.0)
        self.assertEqual(exit_code, 0)
        data = results.get("data", {})
        self.assertEqual(data.get("initial"), "binary")
        self.assertEqual(data.get("options", {}).get("dt"), 0.25)
        self.assertTrue(data.get("options", {}).get("reverse"))

    def test_oversized_upload_is_refused(self):
        request = urllib.request.Request(
            f"{self.base_url}/api/validate",
            data=b"x" * (MAX_REQUEST_BYTES + 1),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request)
            self.fail("Expected HTTP 413")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 413)
            body = json.loads(err.read().decode("utf-8"))
            self.assertFalse(body["valid"])
            err.close()


if __name__ == "__main__":
    unittest.main()
