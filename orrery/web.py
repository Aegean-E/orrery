"""Zero-dependency HTTP server and embedded interactive Web-based UI for Orrery.

Provides a browser-based orbital laboratory alongside the terminal UI,
featuring HTML5 Canvas 2D simulation, time settings (warp, reverse, dt),
body tracking camera, scientific telemetry, and custom scenario support.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from http import HTTPStatus
import http.server
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser

from .custom import MAX_FILE_BYTES, load_scenario_file
from .scenarios import Scenario, get_scenario, scenario_keys
from .sim import World, orbital_elements

DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"
MAX_REQUEST_BYTES = MAX_FILE_BYTES


@dataclass(frozen=True, slots=True)
class WebOptions:
    """Physics and time overrides shared by the browser and the terminal.

    ``None`` means "keep the scenario's own value"; the browser then falls back
    to its built-in control defaults, so callers that do not pass options see
    exactly the previous behaviour.
    """

    dt: float | None = None
    time_scale: float = 1.0
    reverse: bool = False
    relativity: bool | None = None
    c_light: float | None = None
    k_coulomb: float | None = None
    collision_mode: str = "bounce"
    bounce_radius: float | None = 0.06
    restitution: float | None = 0.95
    merge_radius: float | None = 0.04

    def as_dict(self) -> dict[str, object]:
        """Return the JSON-safe view the browser consumes at startup."""
        return {
            "dt": self.dt,
            "time_scale": self.time_scale,
            "reverse": self.reverse,
            "relativity": self.relativity,
            "c_light": self.c_light,
            "k_coulomb": self.k_coulomb,
            "collision_mode": self.collision_mode,
            "bounce_radius": self.bounce_radius,
            "restitution": self.restitution,
            "merge_radius": self.merge_radius,
        }


@dataclass(slots=True)
class _WebState:
    """Per-server state: the chosen world, overrides and uploaded scenarios."""

    initial_key: str
    options: WebOptions
    registry: dict[str, Scenario] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


_DEFAULT_STATE = _WebState(initial_key="solar", options=WebOptions())


def _scenario_overrides(scenario: Scenario,
                        options: WebOptions) -> tuple[float, float | None, float]:
    """Resolve scenario defaults against CLI overrides exactly like the terminal."""
    dt = options.dt if options.dt is not None else scenario.dt
    if options.c_light is not None:
        c = options.c_light
    elif options.relativity is None:
        c = scenario.c
    else:
        c = scenario.c if options.relativity else None
    k_e = options.k_coulomb if options.k_coulomb is not None else scenario.k_e
    return dt, c, k_e


def _scenario_payload(scenario: Scenario, options: WebOptions) -> dict[str, object]:
    dt, c, k_e = _scenario_overrides(scenario, options)
    world = World(scenario.bodies, scenario.g, c=c, k_e=k_e)
    dominant_index = max(range(len(world.bodies)), key=lambda i: world.bodies[i].mass)
    primary = world.bodies[dominant_index]
    dominant = len(world.bodies) < 2 or (
        sorted((b.mass for b in world.bodies), reverse=True)[0]
        >= 10.0 * sorted((b.mass for b in world.bodies), reverse=True)[1]
    )
    bodies_payload = []
    for i, b in enumerate(world.bodies):
        meaningful = i != dominant_index and dominant
        orbit = orbital_elements(primary, b, scenario.g) if meaningful else None
        bodies_payload.append({
            "name": b.name,
            "mass": b.mass,
            "charge": b.charge,
            "x": b.pos.x,
            "y": b.pos.y,
            "vx": b.vel.x,
            "vy": b.vel.y,
            "symbol": b.symbol,
            "color": b.color,
            "semi_major": orbit.semi_major if orbit else None,
            "eccentricity": orbit.eccentricity if orbit else None,
            "period": orbit.period if orbit else None,
        })
    return {
        "key": scenario.key,
        "title": scenario.title,
        "description": scenario.description,
        "g": scenario.g,
        "dt": dt,
        "span": scenario.span,
        "extent": list(scenario.extent),
        "steps_per_frame": scenario.steps_per_frame,
        "trail_length": scenario.trail_length,
        "time_unit": scenario.time_unit,
        "distance_unit": scenario.distance_unit,
        "mass_unit": scenario.mass_unit,
        "speed_unit": scenario.speed_unit,
        "speed_scale": scenario.speed_scale,
        "c": c,
        "k_e": k_e,
        "schwarzschild_radius": world.schwarzschild_radius(),
        "total_energy": world.total_energy(),
        "kinetic_energy": world.kinetic_energy(),
        "potential_energy": world.potential_energy(),
        "angular_momentum": world.angular_momentum(),
        "bodies": bodies_payload,
    }


def _scenario_to_dict(scenario_key: str, options: WebOptions | None = None) -> dict[str, object]:
    """Describe one built-in scenario using the default web overrides."""
    return _scenario_payload(get_scenario(scenario_key), options or WebOptions())


def _json_safe(value: object) -> object:
    """Replace non-finite floats so the response stays valid strict JSON."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _catalog_list(state: _WebState | None = None) -> list[dict[str, object]]:
    scenarios: dict[str, Scenario] = {
        key: get_scenario(key) for key in scenario_keys()
    }
    if state is not None:
        with state.lock:
            scenarios.update(state.registry)
    return [
        {
            "key": s.key,
            "title": s.title,
            "description": s.description,
            "bodies": len(s.bodies),
            "span": f"{s.span:g} {s.distance_unit}",
            "c": s.c,
            "k_e": s.k_e,
        }
        for s in scenarios.values()
    ]


def _register_scenario(state: _WebState, scenario: Scenario) -> Scenario:
    """Store an uploaded scenario under a key that cannot shadow a built-in one."""
    with state.lock:
        if state.registry.get(scenario.key) == scenario:
            return state.registry[scenario.key]
        unique_key = scenario.key
        if unique_key in scenario_keys() or unique_key in state.registry:
            suffix = 2
            while (f"{unique_key}-{suffix}" in scenario_keys()
                   or f"{unique_key}-{suffix}" in state.registry):
                suffix += 1
            unique_key = f"{unique_key}-{suffix}"
            scenario = replace(scenario, key=unique_key)
        state.registry[unique_key] = scenario
        return scenario


class OrreryHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler serving the single-page application and JSON APIs."""

    server_version = "OrreryWeb/1.0"

    def log_message(self, format: str, *args: object) -> None:
        """Suppress standard HTTP server access log to keep the terminal tidy."""
        _ = (format, args)
        return

    def _state(self) -> _WebState:
        """Return the state attached by run_server, or safe defaults for bare handlers."""
        state = getattr(self.server, "state", None)
        return state if isinstance(state, _WebState) else _DEFAULT_STATE

    def _resolve(self, key: str) -> Scenario:
        state = self._state()
        with state.lock:
            scenario = state.registry.get(key)
        return scenario if scenario is not None else get_scenario(key)

    def _send_json(self, status: int, data: object) -> None:
        payload = json.dumps(_json_safe(data), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, content: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path or path == "/index.html":
            self._send_html(HTML_PAGE)
            return
        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "app": "orrery"})
            return
        if path == "/api/scenarios":
            self._send_json(HTTPStatus.OK, _catalog_list(self._state()))
            return
        if path == "/api/config":
            state = self._state()
            self._send_json(HTTPStatus.OK, {
                "initial": state.initial_key,
                "options": state.options.as_dict(),
            })
            return
        if path.startswith("/api/scenario/"):
            requested = urllib.parse.unquote(path[len("/api/scenario/"):])
            try:
                scenario = self._resolve(requested)
                data = _scenario_payload(scenario, self._state().options)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND,
                                {"error": f"scenario '{requested}' not found"})
                return
            except (ValueError, OverflowError) as err:
                self._send_json(HTTPStatus.BAD_REQUEST,
                                {"error": f"scenario '{requested}' cannot be described: {err}"})
                return
            self._send_json(HTTPStatus.OK, data)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/validate":
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST,
                                {"valid": False, "error": "Content-Length must be an integer"})
                return
            if length <= 0:
                self._send_json(HTTPStatus.BAD_REQUEST,
                                {"valid": False, "error": "the request body is empty"})
                return
            if length > MAX_REQUEST_BYTES:
                self.close_connection = True
                if length <= MAX_REQUEST_BYTES + 65_536:
                    try:
                        self.rfile.read(length)
                    except OSError:
                        return
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                    "valid": False,
                    "error": f"scenario files are limited to {MAX_REQUEST_BYTES:,} bytes",
                })
                return
            try:
                body = self.rfile.read(length).decode("utf-8")
                if len(body.encode("utf-8")) > MAX_REQUEST_BYTES:
                    raise ValueError(f"scenario files are limited to {MAX_REQUEST_BYTES:,} bytes")
                with tempfile.TemporaryDirectory(prefix="orrery-web-") as folder:
                    temp_file = Path(folder) / "scenario.json"
                    temp_file.write_text(body, encoding="utf-8")
                    scenario = _register_scenario(self._state(), load_scenario_file(temp_file))
                self._send_json(HTTPStatus.OK, {
                    "valid": True,
                    "key": scenario.key,
                    "title": scenario.title,
                    "bodies": len(scenario.bodies),
                })
            except Exception as err:  # noqa: BLE001 - any loader failure is a client error
                self._send_json(HTTPStatus.BAD_REQUEST, {"valid": False, "error": str(err)})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})


def run_server(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST,
               initial_scenario: str = "solar", auto_open: bool = True,
               once: bool = False, options: WebOptions | None = None,
               scenario: Scenario | None = None) -> int:
    """Run the zero-dependency Orrery Web HTTP server.

    ``scenario`` carries an already-resolved world (built-in alias or custom
    file) and takes precedence over ``initial_scenario``; ``options`` applies
    the CLI physics/time overrides to both the initial world and every fetch.
    """
    if scenario is None:
        try:
            scenario = get_scenario(initial_scenario)
        except KeyError:
            sys.stderr.write(f"Error: unknown scenario '{initial_scenario}'.\n"
                             "Why: the web UI needs a built-in key or a .json scenario file.\n"
                             "Fix: run `python -m orrery list`, or pass a valid file path.\n")
            return 2
    state = _WebState(initial_key=scenario.key, options=options or WebOptions())
    if scenario.key in scenario_keys():
        state.initial_key = scenario.key
    else:
        state.initial_key = _register_scenario(state, scenario).key

    server_address = (host, port)
    server_cls = http.server.HTTPServer if once else http.server.ThreadingHTTPServer
    try:
        httpd = server_cls(server_address, OrreryHandler)
    except OSError as error:
        sys.stderr.write(f"Error: could not bind to {host}:{port}: {error}\n")
        return 1
    httpd.state = state  # type: ignore[attr-defined]

    actual_port = httpd.server_port
    url = f"http://{host}:{actual_port}/"
    sys.stdout.write(f"ORRERY Web UI active at {url}\n")
    sys.stdout.write(f"Initial world: {state.initial_key}  |  Press Ctrl+C to terminate\n")
    sys.stdout.flush()

    if auto_open and not once:
        def _open() -> None:
            time.sleep(0.3)
            try:
                # Launch browser in a background thread without blocking server loop
                open_browser = getattr(webbrowser, "open")
                open_browser(url)
            # hygiene: allow best-effort browser launch failure on headless environments
            except Exception:
                return
        threading.Thread(target=_open, daemon=True).start()

    try:
        if once:
            httpd.handle_request()
        else:
            httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nShutting down Orrery Web UI server...\n")
    finally:
        httpd.server_close()
    return 0


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ORRERY - Celestial N-Body Laboratory</title>
<style>
:root {
  --bg-dark: #0a0c16;
  --bg-card: #131728;
  --bg-panel: rgba(19, 23, 40, 0.88);
  --border: #232942;
  --accent-cyan: #00e5ff;
  --accent-gold: #ffd700;
  --accent-magenta: #e040fb;
  --accent-red: #ff3366;
  --accent-green: #00e676;
  --text-main: #f0f4fc;
  --text-muted: #8b9bb4;
  --font-mono: 'SF Mono', Consolas, 'Courier New', monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg-dark);
  color: var(--text-main);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  overflow: hidden;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 10;
  gap: 12px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 1.15rem;
  letter-spacing: 1.5px;
  color: var(--accent-cyan);
}
.brand span { font-size: 1.3rem; }
.header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
select, button, input {
  background: var(--bg-dark);
  color: var(--text-main);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.85rem;
  outline: none;
  cursor: pointer;
  transition: all 0.2s ease;
}
select:hover, button:hover, input:hover {
  border-color: var(--accent-cyan);
}
button.active, button.primary {
  background: var(--accent-cyan);
  color: #000;
  font-weight: 600;
  border-color: var(--accent-cyan);
}
button.danger {
  background: var(--accent-red);
  color: #fff;
  border-color: var(--accent-red);
}
main {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}
#canvas-container {
  flex: 1;
  position: relative;
  background: radial-gradient(circle at center, #11152a 0%, #060810 100%);
  cursor: grab;
}
#canvas-container:active { cursor: grabbing; }
canvas { width: 100%; height: 100%; display: block; }

/* Side Drawer HUD */
#hud-panel {
  width: 380px;
  background: var(--bg-panel);
  backdrop-filter: blur(12px);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  transition: transform 0.3s ease;
  z-index: 5;
}
#hud-panel.collapsed {
  transform: translateX(100%);
  position: absolute;
  right: 0;
  height: 100%;
}
.panel-section {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.panel-title {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-muted);
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.metric-box {
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  font-family: var(--font-mono);
}
.metric-label { font-size: 0.7rem; color: var(--text-muted); }
.metric-val { font-size: 0.95rem; font-weight: 600; margin-top: 2px; }
.control-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 0.85rem;
}
.control-row input[type="range"] {
  flex: 1;
  margin: 0 10px;
  accent-color: var(--accent-cyan);
}
.sparkline-canvas {
  width: 100%;
  height: 50px;
  background: rgba(0,0,0,0.4);
  border-radius: 4px;
  margin-top: 6px;
}

/* Floating Bottom Time Controls */
#time-bar {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-panel);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 30px;
  padding: 8px 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  z-index: 8;
}
.btn-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 1rem;
}
.time-display {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  padding: 0 8px;
  min-width: 120px;
  text-align: center;
}
.badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  font-family: var(--font-mono);
}
.badge-reverse { background: var(--accent-magenta); color: #fff; }
.badge-forward { background: var(--accent-cyan); color: #000; }
table.bodies-table {
  width: 100%;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  border-collapse: collapse;
  margin-top: 6px;
}
table.bodies-table th, table.bodies-table td {
  padding: 4px 6px;
  text-align: right;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
table.bodies-table th:first-child, table.bodies-table td:first-child { text-align: left; }
</style>
</head>
<body>

<header>
  <div class="brand">
    <span>🪐</span> ORRERY
  </div>
  <div class="header-controls">
    <label for="scenario-select" style="font-size:0.8rem; color:var(--text-muted)">WORLD:</label>
    <select id="scenario-select"></select>
    <button id="btn-toggle-hud" title="Toggle Telemetry Sidebar">📊 HUD</button>
    <button id="btn-upload" title="Load custom scenario JSON">📂 Upload</button>
    <input type="file" id="file-input" accept=".json" style="display:none">
  </div>
</header>

<main>
  <div id="canvas-container">
    <canvas id="orrery-canvas"></canvas>

    <div id="time-bar">
      <button class="btn-circle primary" id="btn-play" title="Play / Pause (Space)">⏸</button>
      <button class="btn-circle" id="btn-step-back" title="Step Back (-dt)">⮌</button>
      <button class="btn-circle" id="btn-step-fwd" title="Step Forward (+dt)">⮎</button>
      <button id="btn-reverse" class="badge badge-forward" title="Toggle Time Direction">FORWARD</button>
      <div class="time-display" id="time-readout">t = 0.00</div>
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="font-size:0.75rem; color:var(--text-muted)">WARP:</span>
        <button id="btn-warp-down" style="padding:2px 6px;">0.5x</button>
        <span id="warp-label" style="font-family:var(--font-mono); font-size:0.8rem; min-width:40px; text-align:center;">1.0x</span>
        <button id="btn-warp-up" style="padding:2px 6px;">2.0x</button>
      </div>
      <button class="btn-circle" id="btn-reset" title="Reset World (R)">↺</button>
    </div>
  </div>

  <div id="hud-panel">
    <div class="panel-section">
      <div class="panel-title">
        <span>WORLD DESCRIPTION</span>
        <span id="units-badge" class="badge" style="background:#222; color:#aaa"></span>
      </div>
      <div id="scenario-desc" style="font-size:0.82rem; line-height:1.4; color:var(--text-muted)"></div>
    </div>

    <div class="panel-section">
      <div class="panel-title">LIVE ENERGY & CONSERVATION</div>
      <div class="grid-2">
        <div class="metric-box">
          <div class="metric-label">ENERGY DRIFT (ΔE/E)</div>
          <div class="metric-val" id="val-drift">+0.00e+00</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">VIRIAL (2K + U)</div>
          <div class="metric-val" id="val-virial">+0.00e+00</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">KINETIC (K)</div>
          <div class="metric-val" id="val-ke">0.00</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">POTENTIAL (U)</div>
          <div class="metric-val" id="val-pe">0.00</div>
        </div>
      </div>
      <canvas id="energy-chart" class="sparkline-canvas"></canvas>
    </div>

    <div class="panel-section">
      <div class="panel-title">TIME & PHYSICS SETTINGS</div>
      <div class="control-row">
        <span>Time Step (dt):</span>
        <input type="range" id="slider-dt" min="0.0001" max="1.0" step="0.0005" value="0.01">
        <span id="label-dt" style="font-family:var(--font-mono); width:50px; text-align:right">0.01</span>
      </div>
      <div class="control-row">
        <span>1PN Relativity:</span>
        <input type="checkbox" id="check-relativity">
        <input type="range" id="slider-c" min="5" max="100" step="1" value="30">
        <span id="label-c" style="font-family:var(--font-mono); width:40px; text-align:right">c=30</span>
      </div>
      <div class="control-row">
        <span>Coulomb Force:</span>
        <input type="checkbox" id="check-coulomb">
        <input type="range" id="slider-ke" min="0" max="5" step="0.01" value="0.1">
        <span id="label-ke" style="font-family:var(--font-mono); width:40px; text-align:right">ke=0.1</span>
      </div>
      <div class="control-row">
        <span>Collision Mode:</span>
        <select id="select-collision" style="padding:3px 6px;">
          <option value="off">Off (Ghost)</option>
          <option value="bounce" selected>Elastic Bounce</option>
          <option value="merge">Inelastic Merge</option>
        </select>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-title">VISUAL TUNING</div>
      <div class="control-row">
        <span>Trail Length:</span>
        <input type="range" id="slider-trail" min="50" max="4000" step="50" value="800">
        <span id="label-trail" style="font-family:var(--font-mono)">800</span>
      </div>
      <div class="control-row">
        <span>Dot Style:</span>
        <select id="select-dot-style" style="padding:3px 6px;">
          <option value="circle">Circle (○)</option>
          <option value="bullet">Bullet (•)</option>
          <option value="ring">Ring (◦)</option>
          <option value="disc">Disc (●)</option>
          <option value="line" selected>Glowing Path</option>
        </select>
      </div>
      <div class="control-row">
        <span>Camera Lock:</span>
        <select id="select-tracking" style="padding:3px 6px; max-width:180px;">
          <option value="-1">Barycentre (Free)</option>
        </select>
      </div>
    </div>

    <div class="panel-section" style="flex:1;">
      <div class="panel-title">CELESTIAL BODIES</div>
      <table class="bodies-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Mass</th>
            <th>Speed</th>
            <th>Dist</th>
          </tr>
        </thead>
        <tbody id="bodies-tbody"></tbody>
      </table>
    </div>
  </div>
</main>

<script>
// Orrery Web Studio Client-Side Simulation & Rendering Engine
(function() {
  const canvas = document.getElementById('orrery-canvas');
  const ctx = canvas.getContext('2d');
  const energyCanvas = document.getElementById('energy-chart');
  const energyCtx = energyCanvas.getContext('2d');

  let state = {
    bodies: [],
    g: 1.0,
    c: null,
    k_e: 0.0,
    dt: 0.01,
    time: 0.0,
    span: 4.0,
    units: { time: "t", dist: "u", mass: "m" },
    trails: [],
    maxTrails: 800,
    paused: false,
    timeDirection: 1.0,
    timeWarp: 1.0,
    initialEnergy: 0.0,
    driftHistory: [],
    trackingIndex: -1,
    pan: { x: 0, y: 0 },
    zoom: 1.0,
    collisionMode: "bounce",
    bounceRadius: 0.06,
    restitution: 0.95,
    mergeRadius: 0.04,
    dotStyle: "line"
  };

  const COLOR_PALETTE = {
    yellow: '#ffd700',
    red: '#ff3366',
    blue: '#00e5ff',
    cyan: '#00ffff',
    magenta: '#e040fb',
    gold: '#ffb300',
    green: '#00e676',
    gray: '#a0aab8',
    white: '#f5f7fa'
  };

  function resize() {
    canvas.width = canvas.clientWidth * window.devicePixelRatio;
    canvas.height = canvas.clientHeight * window.devicePixelRatio;
    energyCanvas.width = energyCanvas.clientWidth * window.devicePixelRatio;
    energyCanvas.height = energyCanvas.clientHeight * window.devicePixelRatio;
  }

  // Clamp a slider by widening its range, so overrides outside the default
  // bounds are shown and used instead of being silently snapped.
  function setSliderValue(id, value) {
    const slider = document.getElementById(id);
    const number = Number(value);
    if (!Number.isFinite(number)) return;
    slider.min = Math.min(parseFloat(slider.min), number).toString();
    slider.max = Math.max(parseFloat(slider.max), number).toString();
    slider.value = number.toString();
    return number;
  }
  window.addEventListener('resize', resize);
  resize();

  // Load the server's initial world, option overrides and scenario catalogue
  let webConfig = { initial: 'solar', options: {} };
  Promise.all([
    fetch('/api/config').then(r => r.json()),
    fetch('/api/scenarios').then(r => r.json())
  ]).then(([config, list]) => {
    webConfig = config;
    const select = document.getElementById('scenario-select');
    select.innerHTML = '';
    list.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.key;
      opt.textContent = `${item.title} (${item.bodies} bodies)`;
      select.appendChild(opt);
    });
    const initial = config.initial || (list[0] && list[0].key) || 'solar';
    if (!Array.from(select.options).some(opt => opt.value === initial)) {
      const opt = document.createElement('option');
      opt.value = initial;
      opt.textContent = initial;
      select.appendChild(opt);
    }
    select.value = initial;
    loadScenario(initial);
  });

  document.getElementById('scenario-select').addEventListener('change', e => {
    loadScenario(e.target.value);
  });

  function loadScenario(key) {
    fetch(`/api/scenario/${encodeURIComponent(key)}`)
      .then(r => r.json())
      .then(data => {
        state.bodies = data.bodies.map(b => ({
          name: b.name,
          mass: b.mass,
          charge: b.charge || 0.0,
          x: b.x,
          y: b.y,
          vx: b.vx,
          vy: b.vy,
          symbol: b.symbol,
          color: COLOR_PALETTE[b.color] || '#ffffff'
        }));
        state.g = data.g;
        state.dt = data.dt;
        state.c = data.c;
        state.k_e = data.k_e || 0.0;
        state.span = data.span;
        state.time = 0.0;
        state.units = { time: data.time_unit, dist: data.distance_unit, mass: data.mass_unit };
        state.trails = state.bodies.map(() => []);
        state.pan = { x: 0, y: 0 };
        state.zoom = 1.0;
        state.trackingIndex = -1;
        state.initialEnergy = totalEnergy();
        state.driftHistory = [0.0];

        document.getElementById('scenario-desc').textContent = data.description;
        document.getElementById('units-badge').textContent = `${data.distance_unit}, ${data.time_unit}`;
        setSliderValue('slider-dt', data.dt);
        document.getElementById('label-dt').textContent = data.dt.toString();
        document.getElementById('check-relativity').checked = data.c !== null;
        if (data.c !== null) setSliderValue('slider-c', data.c);
        document.getElementById('check-coulomb').checked = data.k_e > 0.0;
        if (data.k_e) setSliderValue('slider-ke', data.k_e);
        document.getElementById('label-ke').textContent = 'ke=' + data.k_e;
        document.getElementById('label-c').textContent = 'c=' + (data.c !== null ? data.c : document.getElementById('slider-c').value);

        updateTrackingSelect();
        applyWebOptions();
      });
  }

  function applyWebOptions() {
    const op = webConfig.options || {};
    if (op.dt !== null && op.dt !== undefined) {
      state.dt = op.dt;
      setSliderValue('slider-dt', op.dt);
      document.getElementById('label-dt').textContent = op.dt.toString();
    }
    if (op.time_scale !== null && op.time_scale !== undefined) {
      state.timeWarp = op.time_scale;
      document.getElementById('warp-label').textContent = op.time_scale + 'x';
    }
    if (op.reverse) {
      state.timeDirection = -1.0;
      const btn = document.getElementById('btn-reverse');
      btn.textContent = 'REVERSE';
      btn.className = 'badge badge-reverse';
    }
    if (op.c_light !== null && op.c_light !== undefined) {
      setSliderValue('slider-c', op.c_light);
      document.getElementById('check-relativity').checked = true;
      document.getElementById('label-c').textContent = 'c=' + op.c_light;
    }
    if (op.k_coulomb !== null && op.k_coulomb !== undefined) {
      setSliderValue('slider-ke', op.k_coulomb);
      document.getElementById('check-coulomb').checked = true;
      document.getElementById('label-ke').textContent = 'ke=' + op.k_coulomb;
    }
    if (op.collision_mode) {
      state.collisionMode = op.collision_mode;
      document.getElementById('select-collision').value = op.collision_mode;
    }
    if (op.bounce_radius !== null && op.bounce_radius !== undefined) state.bounceRadius = op.bounce_radius;
    if (op.restitution !== null && op.restitution !== undefined) state.restitution = op.restitution;
    if (op.merge_radius !== null && op.merge_radius !== undefined) state.mergeRadius = op.merge_radius;
  }

  function updateTrackingSelect() {
    const sel = document.getElementById('select-tracking');
    sel.innerHTML = '<option value="-1">Barycentre (Free)</option>';
    state.bodies.forEach((b, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${b.name} (${b.symbol})`;
      sel.appendChild(opt);
    });
  }

  // Physics Integration: Symplectic Kick-Drift-Kick Leapfrog
  function accelerations(bodies) {
    const count = bodies.length;
    const ax = new Float64Array(count);
    const ay = new Float64Array(count);
    const g = state.g;
    const c = document.getElementById('check-relativity').checked ? parseFloat(document.getElementById('slider-c').value) : null;
    const k_e = document.getElementById('check-coulomb').checked ? parseFloat(document.getElementById('slider-ke').value) : 0.0;

    for (let i = 0; i < count - 1; i++) {
      const b1 = bodies[i];
      for (let j = i + 1; j < count; j++) {
        const b2 = bodies[j];
        const dx = b2.x - b1.x;
        const dy = b2.y - b1.y;
        const r2 = dx * dx + dy * dy;
        if (r2 <= 1e-12) continue;
        const r = Math.sqrt(r2);
        const inv_r3 = 1.0 / (r2 * r);
        let pull = g * inv_r3;
        if (c !== null && c > 0.0) {
          pull *= (1.0 + (3.0 * g * (b1.mass + b2.mass)) / (c * c * r));
        }
        ax[i] += pull * b2.mass * dx;
        ay[i] += pull * b2.mass * dy;
        ax[j] -= pull * b1.mass * dx;
        ay[j] -= pull * b1.mass * dy;

        if (k_e !== 0.0 && (b1.charge !== 0.0 || b2.charge !== 0.0)) {
          const coulomb = k_e * (b1.charge * b2.charge) * inv_r3;
          ax[i] -= (coulomb / b1.mass) * dx;
          ay[i] -= (coulomb / b1.mass) * dy;
          ax[j] += (coulomb / b2.mass) * dx;
          ay[j] += (coulomb / b2.mass) * dy;
        }
      }
    }
    return { ax, ay };
  }

  function resolveCollisions() {
    const mode = state.collisionMode;
    if (mode === "off" || state.bodies.length < 2) return;

    if (mode === "bounce") {
      const rad = state.bounceRadius;
      const rest = state.restitution;
      for (let i = 0; i < state.bodies.length - 1; i++) {
        const b1 = state.bodies[i];
        for (let j = i + 1; j < state.bodies.length; j++) {
          const b2 = state.bodies[j];
          const dx = b2.x - b1.x;
          const dy = b2.y - b1.y;
          const dist = Math.hypot(dx, dy);
          if (dist < rad && dist > 1e-9) {
            const nx = (b1.x - b2.x) / dist;
            const ny = (b1.y - b2.y) / dist;
            const dvx = b1.vx - b2.vx;
            const dvy = b1.vy - b2.vy;
            const vn = dvx * nx + dvy * ny;
            if (vn < 0.0) {
              const impulse = -(1.0 + rest) * vn / (1.0 / b1.mass + 1.0 / b2.mass);
              b1.vx += (impulse / b1.mass) * nx;
              b1.vy += (impulse / b1.mass) * ny;
              b2.vx -= (impulse / b2.mass) * nx;
              b2.vy -= (impulse / b2.mass) * ny;
              const overlap = rad - dist;
              const mTotal = b1.mass + b2.mass;
              b1.x += (overlap * (b2.mass / mTotal)) * nx;
              b1.y += (overlap * (b2.mass / mTotal)) * ny;
              b2.x -= (overlap * (b1.mass / mTotal)) * nx;
              b2.y -= (overlap * (b1.mass / mTotal)) * ny;
            }
          }
        }
      }
    } else if (mode === "merge") {
      const rad = state.mergeRadius;
      let i = 0;
      while (i < state.bodies.length) {
        let j = i + 1;
        let merged = false;
        while (j < state.bodies.length) {
          const b1 = state.bodies[i];
          const b2 = state.bodies[j];
          if (Math.hypot(b2.x - b1.x, b2.y - b1.y) <= rad) {
            const totM = b1.mass + b2.mass;
            b1.x = (b1.x * b1.mass + b2.x * b2.mass) / totM;
            b1.y = (b1.y * b1.mass + b2.y * b2.mass) / totM;
            b1.vx = (b1.vx * b1.mass + b2.vx * b2.mass) / totM;
            b1.vy = (b1.vy * b1.mass + b2.vy * b2.mass) / totM;
            b1.charge += b2.charge;
            b1.mass = totM;
            state.bodies.splice(j, 1);
            state.trails.splice(j, 1);
            merged = true;
          } else {
            j++;
          }
        }
        if (!merged) i++;
      }
    }
  }

  function step(dt) {
    const half = dt * 0.5;
    const start = accelerations(state.bodies);
    for (let i = 0; i < state.bodies.length; i++) {
      state.bodies[i].vx += start.ax[i] * half;
      state.bodies[i].vy += start.ay[i] * half;
      state.bodies[i].x += state.bodies[i].vx * dt;
      state.bodies[i].y += state.bodies[i].vy * dt;
    }
    const end = accelerations(state.bodies);
    for (let i = 0; i < state.bodies.length; i++) {
      state.bodies[i].vx += end.ax[i] * half;
      state.bodies[i].vy += end.ay[i] * half;
    }
    state.time += dt;
    resolveCollisions();
  }

  function kineticEnergy() {
    let ke = 0.0;
    for (const b of state.bodies) {
      ke += 0.5 * b.mass * (b.vx * b.vx + b.vy * b.vy);
    }
    return ke;
  }

  function potentialEnergy() {
    let pe = 0.0;
    const count = state.bodies.length;
    const k_e = document.getElementById('check-coulomb').checked ? parseFloat(document.getElementById('slider-ke').value) : 0.0;
    for (let i = 0; i < count - 1; i++) {
      const b1 = state.bodies[i];
      for (let j = i + 1; j < count; j++) {
        const b2 = state.bodies[j];
        const dist = Math.hypot(b2.x - b1.x, b2.y - b1.y);
        if (dist > 0.0) {
          pe -= state.g * b1.mass * b2.mass / dist;
          if (k_e !== 0.0 && (b1.charge !== 0.0 || b2.charge !== 0.0)) {
            pe += k_e * b1.charge * b2.charge / dist;
          }
        }
      }
    }
    return pe;
  }

  function totalEnergy() {
    return kineticEnergy() + potentialEnergy();
  }

  // Interactive Pan and Zoom
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  canvas.addEventListener('mousedown', e => {
    isDragging = true;
    dragStart = { x: e.clientX, y: e.clientY };
  });
  window.addEventListener('mouseup', () => isDragging = false);
  canvas.addEventListener('mousemove', e => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    dragStart = { x: e.clientX, y: e.clientY };
    const worldScale = (state.span * state.zoom) / Math.min(canvas.clientWidth, canvas.clientHeight);
    state.pan.x -= dx * worldScale;
    state.pan.y += dy * worldScale;
    state.trackingIndex = -1;
    document.getElementById('select-tracking').value = "-1";
  });
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.15 : 0.85;
    state.zoom = Math.max(0.02, Math.min(50.0, state.zoom * factor));
  });

  // UI Button Bindings
  document.getElementById('btn-play').addEventListener('click', () => {
    state.paused = !state.paused;
    document.getElementById('btn-play').textContent = state.paused ? '▶' : '⏸';
  });
  document.getElementById('btn-reverse').addEventListener('click', () => {
    state.timeDirection *= -1.0;
    const btn = document.getElementById('btn-reverse');
    btn.textContent = state.timeDirection > 0 ? 'FORWARD' : 'REVERSE';
    btn.className = state.timeDirection > 0 ? 'badge badge-forward' : 'badge badge-reverse';
  });
  document.getElementById('btn-step-fwd').addEventListener('click', () => step(state.dt));
  document.getElementById('btn-step-back').addEventListener('click', () => step(-state.dt));
  document.getElementById('btn-warp-up').addEventListener('click', () => {
    state.timeWarp = Math.min(50.0, +(state.timeWarp * 1.5).toFixed(2));
    document.getElementById('warp-label').textContent = state.timeWarp + 'x';
  });
  document.getElementById('btn-warp-down').addEventListener('click', () => {
    state.timeWarp = Math.max(0.05, +(state.timeWarp / 1.5).toFixed(2));
    document.getElementById('warp-label').textContent = state.timeWarp + 'x';
  });
  document.getElementById('btn-reset').addEventListener('click', () => {
    const sel = document.getElementById('scenario-select');
    loadScenario(sel.value);
  });
  document.getElementById('btn-toggle-hud').addEventListener('click', () => {
    document.getElementById('hud-panel').classList.toggle('collapsed');
  });
  document.getElementById('slider-dt').addEventListener('input', e => {
    state.dt = parseFloat(e.target.value);
    document.getElementById('label-dt').textContent = state.dt.toString();
  });
  document.getElementById('slider-c').addEventListener('input', e => {
    document.getElementById('label-c').textContent = 'c=' + e.target.value;
  });
  document.getElementById('slider-ke').addEventListener('input', e => {
    document.getElementById('label-ke').textContent = 'ke=' + e.target.value;
  });
  document.getElementById('slider-trail').addEventListener('input', e => {
    state.maxTrails = parseInt(e.target.value);
    document.getElementById('label-trail').textContent = state.maxTrails.toString();
  });
  document.getElementById('select-collision').addEventListener('change', e => {
    state.collisionMode = e.target.value;
  });
  document.getElementById('select-dot-style').addEventListener('change', e => {
    state.dotStyle = e.target.value;
  });
  document.getElementById('select-tracking').addEventListener('change', e => {
    state.trackingIndex = parseInt(e.target.value);
  });

  // Custom scenario upload
  document.getElementById('btn-upload').addEventListener('click', () => {
    document.getElementById('file-input').click();
  });
  document.getElementById('file-input').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const parsed = JSON.parse(ev.target.result);
        fetch('/api/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(parsed)
        })
        .then(r => r.json())
        .then(res => {
          if (res.valid) {
            const select = document.getElementById('scenario-select');
            if (!Array.from(select.options).some(opt => opt.value === res.key)) {
              const opt = document.createElement('option');
              opt.value = res.key;
              opt.textContent = `${res.title} (${res.bodies} bodies)`;
              select.appendChild(opt);
            }
            select.value = res.key;
            alert(`Loaded custom scenario: ${res.title}`);
            loadScenario(res.key);
          } else {
            alert(`Validation error: ${res.error}`);
          }
        });
      } catch (err) {
        alert('Invalid JSON file');
      }
    };
    reader.readAsText(file);
  });

  // Render & Animation Loop
  let frameCount = 0;
  function animate() {
    requestAnimationFrame(animate);

    if (!state.paused) {
      const stepsToRun = Math.max(1, Math.round(state.timeWarp));
      const subDt = (state.dt * state.timeDirection * state.timeWarp) / stepsToRun;
      for (let s = 0; s < stepsToRun; s++) {
        step(subDt);
      }
      for (let i = 0; i < state.bodies.length; i++) {
        if (!state.trails[i]) state.trails[i] = [];
        state.trails[i].push({ x: state.bodies[i].x, y: state.bodies[i].y });
        if (state.trails[i].length > state.maxTrails) {
          state.trails[i].shift();
        }
      }
    }

    // World to Screen Projection
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    let centerX = state.pan.x;
    let centerY = state.pan.y;
    if (state.trackingIndex >= 0 && state.trackingIndex < state.bodies.length) {
      centerX = state.bodies[state.trackingIndex].x + state.pan.x;
      centerY = state.bodies[state.trackingIndex].y + state.pan.y;
    }

    const viewSpan = state.span * state.zoom;
    const scale = Math.min(w, h) / viewSpan;
    const originX = w * 0.5;
    const originY = h * 0.5;

    function toScreen(x, y) {
      return {
        x: originX + (x - centerX) * scale,
        y: originY - (y - centerY) * scale
      };
    }

    // Draw Orbit Trails
    for (let i = 0; i < state.bodies.length; i++) {
      const trail = state.trails[i];
      if (!trail || trail.length < 2) continue;
      const bColor = state.bodies[i].color;

      if (state.dotStyle === "line") {
        ctx.beginPath();
        for (let t = 0; t < trail.length; t++) {
          const pt = toScreen(trail[t].x, trail[t].y);
          if (t === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.strokeStyle = bColor;
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.45;
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      } else {
        ctx.fillStyle = bColor;
        ctx.strokeStyle = bColor;
        for (let t = 0; t < trail.length; t += 2) {
          const pt = toScreen(trail[t].x, trail[t].y);
          const alpha = 0.2 + 0.8 * (t / trail.length);
          ctx.globalAlpha = alpha;
          if (state.dotStyle === "circle" || state.dotStyle === "ring") {
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 2.5, 0, Math.PI * 2);
            ctx.stroke();
          } else {
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 2.0, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        ctx.globalAlpha = 1.0;
      }
    }

    // Draw Celestial Bodies
    for (let i = 0; i < state.bodies.length; i++) {
      const b = state.bodies[i];
      const pt = toScreen(b.x, b.y);

      // Glow halo
      const grad = ctx.createRadialGradient(pt.x, pt.y, 1, pt.x, pt.y, 14);
      grad.addColorStop(0, b.color);
      grad.addColorStop(1, 'transparent');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 14, 0, Math.PI * 2);
      ctx.fill();

      // Body core
      ctx.fillStyle = b.color;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
      ctx.fill();

      // Name & Symbol
      ctx.font = '11px ' + getComputedStyle(document.body).fontFamily;
      ctx.fillStyle = '#ffffff';
      ctx.fillText(`${b.name} (${b.symbol})`, pt.x + 8, pt.y - 6);
    }

    // Update HUD Metrics every 4 frames
    frameCount++;
    if (frameCount % 4 === 0) {
      document.getElementById('time-readout').textContent = `t = ${state.time.toFixed(2)} ${state.units.time}`;
      const ke = kineticEnergy();
      const pe = potentialEnergy();
      const te = ke + pe;
      const drift = state.initialEnergy !== 0.0 ? (te - state.initialEnergy) / Math.abs(state.initialEnergy) : 0.0;
      state.driftHistory.push(drift);
      if (state.driftHistory.length > 80) state.driftHistory.shift();

      document.getElementById('val-drift').textContent = (drift >= 0 ? '+' : '') + drift.toExponential(2);
      document.getElementById('val-virial').textContent = (2.0 * ke + pe).toExponential(2);
      document.getElementById('val-ke').textContent = ke.toExponential(2);
      document.getElementById('val-pe').textContent = pe.toExponential(2);

      // Render Energy Drift Sparkline
      energyCtx.clearRect(0, 0, energyCanvas.width, energyCanvas.height);
      if (state.driftHistory.length > 1) {
        const ew = energyCanvas.width;
        const eh = energyCanvas.height;
        const minVal = Math.min(...state.driftHistory);
        const maxVal = Math.max(...state.driftHistory);
        const range = Math.max(1e-12, maxVal - minVal);
        energyCtx.beginPath();
        for (let h = 0; h < state.driftHistory.length; h++) {
          const hx = (h / (state.driftHistory.length - 1)) * ew;
          const hy = eh - ((state.driftHistory[h] - minVal) / range) * (eh - 8) - 4;
          if (h === 0) energyCtx.moveTo(hx, hy);
          else energyCtx.lineTo(hx, hy);
        }
        energyCtx.strokeStyle = '#00e5ff';
        energyCtx.lineWidth = 2.0;
        energyCtx.stroke();
      }

      // Update Bodies Table
      const tbody = document.getElementById('bodies-tbody');
      tbody.innerHTML = '';
      state.bodies.forEach(b => {
        const tr = document.createElement('tr');
        const spd = Math.hypot(b.vx, b.vy).toFixed(2);
        const dist = Math.hypot(b.x, b.y).toFixed(2);
        const nameCell = document.createElement('td');
        const marker = document.createElement('span');
        marker.style.color = b.color;
        marker.textContent = '● ';
        nameCell.appendChild(marker);
        nameCell.appendChild(document.createTextNode(b.name));
        const massCell = document.createElement('td');
        massCell.textContent = b.mass.toExponential(1);
        const speedCell = document.createElement('td');
        speedCell.textContent = spd;
        const distCell = document.createElement('td');
        distCell.textContent = dist;
        tr.append(nameCell, massCell, speedCell, distCell);
        tbody.appendChild(tr);
      });
    }
  }

  requestAnimationFrame(animate);
})();
</script>
</body>
</html>
"""
