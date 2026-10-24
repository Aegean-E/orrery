"""Load user-authored scenarios from JSON files.

The loader is deliberately strict: a scenario file is data, never code. It bounds the file size,
body count and numeric ranges before constructing the same :class:`Scenario` the built-ins use,
so every CLI command works with custom worlds without a second execution path.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, NoReturn

from .render import ANSI
from .scenarios import Scenario
from .sim import Body, Vec2

MAX_FILE_BYTES = 1_048_576
MAX_BODIES = 64


class ScenarioFileError(Exception):
    """A custom scenario could not be loaded; the CLI turns this into Error/Why/Fix."""

    def __init__(self, message: str, why: str, fix: str) -> None:
        super().__init__(message)
        self.why = why
        self.fix = fix


def _fail(message: str, why: str | None = None, fix: str | None = None) -> NoReturn:
    raise ScenarioFileError(
        message,
        why or "a custom scenario must be a finite, self-contained JSON description.",
        fix or ("see the Custom Scenarios section in README.md, or start from "
                "examples/custom-two-body.json in the repository."),
    )


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field} must be a number.", f"{field} was missing or had the wrong type.")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        _fail(f"{field} is too large to represent as a float.")
    if not math.isfinite(result):
        _fail(f"{field} must be finite.", "NaN and infinity cannot be simulated.")
    if positive and result <= 0.0:
        _fail(f"{field} must be greater than zero.")
    return result


def _integer(value: Any, field: str, *, minimum: int = 1, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{field} must be an integer.", f"{field} was missing or had the wrong type.")
    if not minimum <= value <= maximum:
        _fail(f"{field} must be between {minimum} and {maximum}.")
    return value


def _string(value: Any, field: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string.", f"{field} was missing or empty.")
    if len(value) > maximum:
        _fail(f"{field} is longer than {maximum} characters.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _fail(
            f"{field} must not contain control characters.",
            "names, titles and units are rendered directly in the terminal.",
        )
    return value


def _vector(value: Any, field: str) -> Vec2:
    if not isinstance(value, list) or len(value) != 2:
        _fail(f"{field} must be a two-number array.", f"{field} should look like [x, y].")
    return Vec2(_number(value[0], f"{field}[0]"), _number(value[1], f"{field}[1]"))


def _body(raw: Any, index: int) -> Body:
    if not isinstance(raw, dict):
        _fail(f"bodies[{index}] must be an object.")
    name = _string(raw.get("name"), f"bodies[{index}].name", maximum=80)
    mass = _number(raw.get("mass"), f"bodies[{index}].mass", positive=True)
    position = _vector(raw.get("position"), f"bodies[{index}].position")
    velocity = _vector(raw.get("velocity"), f"bodies[{index}].velocity")
    symbol = _string(raw.get("symbol"), f"bodies[{index}].symbol", maximum=1)
    if (len(symbol) != 1 or not symbol.isascii() or not symbol.isprintable()
            or symbol.isspace()):
        _fail(
            f"bodies[{index}].symbol must be one printable, non-space ASCII character.",
            "the renderer places one character per body.",
            "use a single letter or digit such as E or 4.",
        )
    color = raw.get("color", "white")
    if not isinstance(color, str) or color not in ANSI:
        _fail(
            f"bodies[{index}].color is not a known colour.",
            "the palette is fixed so colour output stays portable.",
            f"use one of: {', '.join(sorted(ANSI))}.",
        )
    return Body(name=name, mass=mass, pos=position, vel=velocity,
                symbol=symbol, color=color)


def _units(raw: Any) -> tuple[str, str, str, str, float]:
    if raw is None:
        return "t", "u", "m", "u/t", 1.0
    if not isinstance(raw, dict):
        _fail("units must be an object.")
    return (
        _string(raw.get("time", "t"), "units.time", maximum=16),
        _string(raw.get("distance", "u"), "units.distance", maximum=16),
        _string(raw.get("mass", "m"), "units.mass", maximum=16),
        _string(raw.get("speed", "u/t"), "units.speed", maximum=16),
        _number(raw.get("speed_scale", 1.0), "units.speed_scale", positive=True),
    )


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"{value} is not allowed; use finite numbers only")


def load_scenario_file(path_like: str | Path) -> Scenario:
    """Read one custom scenario, validating size, shape, values and the resulting Scenario."""
    path = Path(path_like).expanduser()
    if not path.exists():
        _fail(f"{path} does not exist.", "custom scenarios are loaded from a JSON file.")
    if not path.is_file():
        _fail(f"{path} is not a file.", "pass the path to a JSON scenario file.")
    try:
        size = path.stat().st_size
    except OSError as error:
        _fail(f"could not inspect {path}: {error}", "the file metadata could not be read.")
    if size > MAX_FILE_BYTES:
        _fail(
            f"{path} is larger than {MAX_FILE_BYTES:,} bytes.",
            "a scenario description should contain only a small amount of data.",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"could not read {path}: {error}", "scenario files must be UTF-8 text.")
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except (json.JSONDecodeError, ValueError, RecursionError) as error:
        _fail(f"{path} is not valid JSON: {error}", "the file did not parse as JSON.")
    if not isinstance(data, dict):
        _fail("the top-level JSON value must be an object.")

    g = _number(data.get("g"), "g", positive=True)
    dt = _number(data.get("dt"), "dt", positive=True)
    span = _number(data.get("span"), "span", positive=True)
    extent_raw = data.get("extent")
    if not isinstance(extent_raw, list) or len(extent_raw) != 2:
        _fail("extent must be a two-number array.", "extent should look like [half_x, half_y].")
    extent = (
        _number(extent_raw[0], "extent[0]", positive=True),
        _number(extent_raw[1], "extent[1]", positive=True),
    )
    bodies_raw = data.get("bodies")
    if not isinstance(bodies_raw, list) or not 1 <= len(bodies_raw) <= MAX_BODIES:
        _fail(
            f"bodies must be an array with 1-{MAX_BODIES} entries.",
            "the O(N^2) gravity loop and the terminal need a bounded body count.",
        )
    bodies = tuple(_body(raw, index) for index, raw in enumerate(bodies_raw))
    names = [body.name for body in bodies]
    symbols = [body.symbol for body in bodies]
    if len(set(names)) != len(names):
        _fail("body names must be unique.")
    if len(set(symbols)) != len(symbols):
        _fail("body symbols must be unique.", "the legend and frame need one symbol per body.")

    key = _string(data.get("key", path.stem), "key", maximum=64)
    title = _string(data.get("title", key), "title", maximum=200)
    description = _string(
        data.get("description", f"Custom scenario loaded from {path.name}."),
        "description",
        maximum=2000,
    )
    time_unit, distance_unit, mass_unit, speed_unit, speed_scale = _units(data.get("units"))
    steps_per_frame = _integer(data.get("steps_per_frame", 1), "steps_per_frame",
                               maximum=100_000)
    trail_length = _integer(data.get("trail_length", 1000), "trail_length",
                            maximum=200_000)
    record_every = _integer(data.get("record_every", 1), "record_every",
                            maximum=100_000)
    default_frames = _integer(data.get("default_frames", 120), "default_frames",
                              maximum=1_000_000)
    export_until = _number(
        data.get("export_until", max(1.0, 100.0 * dt)),
        "export_until",
        positive=True,
    )
    c = _number(data["c"], "c", positive=True) if "c" in data and data["c"] is not None else None

    try:
        return Scenario(
            key=key,
            title=title,
            description=description,
            g=g,
            dt=dt,
            span=span,
            extent=extent,
            bodies=bodies,
            steps_per_frame=steps_per_frame,
            trail_length=trail_length,
            record_every=record_every,
            default_frames=default_frames,
            export_until=export_until,
            time_unit=time_unit,
            distance_unit=distance_unit,
            mass_unit=mass_unit,
            speed_unit=speed_unit,
            speed_scale=speed_scale,
            c=c,
        )
    except ValueError as error:
        _fail(
            f"the scenario is inconsistent: {error}",
            "one of the ranges, symbols or extents does not agree with the bodies.",
        )
