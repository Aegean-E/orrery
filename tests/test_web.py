import http.server
import json
import threading
import time
import unittest
import urllib.request

from orrery.web import OrreryHandler, _catalog_list, _scenario_to_dict, run_server


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

        def _hit():
            time.sleep(0.08)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health") as resp:
                    _ = resp.read()
            # hygiene: allow test probe failure during server startup
            except Exception:
                pass

        threading.Thread(target=_hit, daemon=True).start()
        exit_code = run_server(port=port, auto_open=False, once=True)
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
