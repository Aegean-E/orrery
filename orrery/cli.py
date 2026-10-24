"""Command-line surface for Orrery."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap
import time
from typing import Sequence

from . import __version__
from .custom import ScenarioFileError, load_scenario_file
from .render import (
    ANSI,
    CELL_ASPECT,
    RESET,
    Viewport,
    render_scene,
    resolve_dot_char,
    strip_ansi,
)
from .scenarios import Scenario, get_scenario, scenario_keys
from .sim import Body, Orbit, Vec2, World, orbital_elements
from .trails import TrailRecorder

SNAPSHOT_STEP_LIMIT = 2_000_000
MAX_EXPORT_SAMPLES = 200_000
MIN_FPS = 0.1
MAX_FPS = 240.0


class CliError(Exception):
    """A failure with a cause and a concrete next action."""

    def __init__(self, message: str, why: str, fix: str, code: int = 1) -> None:
        super().__init__(message)
        self.why = why
        self.fix = fix
        self.code = code


class TriadParser(argparse.ArgumentParser):
    """Argparse that turns a usage error into the Error/Why/Fix triad."""

    def error(self, message: str) -> None:
        """Print usage and the Error/Why/Fix triad, then exit 2."""
        self.print_usage(sys.stderr)
        self.exit(2, f"Error: {message}\n"
                     "Why: the command needs a known subcommand and valid options.\n"
                     "Fix: run `python -m orrery --help`, then retry with one of its "
                     "listed commands.\n")


def _scenario(name: str) -> Scenario:
    try:
        return get_scenario(name)
    except KeyError:
        candidate = Path(name).expanduser()
        if candidate.is_file() or name.lower().endswith(".json"):
            try:
                return load_scenario_file(candidate)
            except ScenarioFileError as error:
                raise CliError(
                    f"could not load scenario '{name}': {error}",
                    error.why,
                    error.fix,
                ) from None
        available = ", ".join(scenario_keys())
        raise CliError(
            f"unknown scenario '{name}'.",
            "a scenario key selects one built-in initial state.",
            f"choose one of: {available}, or pass a .json scenario file.",
        ) from None


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario_file(args.path)
    except ScenarioFileError as error:
        raise CliError(f"invalid scenario: {error}", error.why, error.fix) from None
    print(f"OK: {scenario.key} ({scenario.title}) with {len(scenario.bodies)} bodies")
    return 0


def _color_enabled(args: argparse.Namespace) -> bool:
    if getattr(args, "no_color", False) or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _unicode_enabled(args: argparse.Namespace) -> bool:
    if getattr(args, "ascii", False):
        return False
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "\u00b7\u2500\u0394\u2801".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _scene_size(args: argparse.Namespace) -> tuple[int, int]:
    columns, lines = shutil.get_terminal_size(fallback=(88, 28))
    width = args.width if args.width is not None else max(40, min(110, columns - 2))
    height = args.height if args.height is not None else max(12, min(32, lines - 6))
    if not 20 <= width <= 240:
        raise CliError(
            f"--width {width} is outside the supported range.",
            "the renderer needs a rectangle wide enough to show an orbit.",
            "pass a width between 20 and 240 columns.",
            code=2,
        )
    if not 8 <= height <= 80:
        raise CliError(
            f"--height {height} is outside the supported range.",
            "the renderer needs a rectangle tall enough to show an orbit.",
            "pass a height between 8 and 80 rows.",
            code=2,
        )
    return width, height


def _trail_limit(args: argparse.Namespace, scenario: Scenario) -> int:
    if getattr(args, "no_trail", False):
        return 0
    limit = args.trail if args.trail is not None else scenario.trail_length
    if not 1 <= limit <= 200_000:
        raise CliError(
            f"--trail {limit} is outside the supported range.",
            "a trail is a bounded sample of past positions, not an unbounded history.",
            "pass a trail length between 1 and 200000, or use --no-trail.",
            code=2,
        )
    return limit


def _fit_span(scenario: Scenario, width: int, height: int,
              aspect: float = CELL_ASPECT, margin: float = 1.05) -> float:
    """Pick a vertical span large enough for the scenario's horizontal extent."""
    half_width, half_height = scenario.extent
    horizontal = 2.0 * aspect * (height - 1) * half_width * margin / (width - 1)
    vertical = 2.0 * half_height * margin
    return max(scenario.span, horizontal, vertical)


def _viewport(scenario: Scenario, width: int, height: int,
              aspect: float = CELL_ASPECT,
              center: Vec2 | None = None,
              span_factor: float = 1.0) -> Viewport:
    base_span = _fit_span(scenario, width, height, aspect)
    effective_span = base_span * span_factor
    eff_center = center if center is not None else Vec2()
    return Viewport(width, height, effective_span, center=eff_center, aspect=aspect)


def _aspect(args: argparse.Namespace) -> float:
    aspect = getattr(args, "aspect", CELL_ASPECT)
    if not math.isfinite(aspect) or not 0.25 <= aspect <= 4.0:
        raise CliError(
            f"--aspect {aspect:g} is outside the supported range.",
            "the aspect describes how many character columns make one row of world scale.",
            "pass a value between 0.25 and 4.0; the default is 2.0.",
            code=2,
        )
    return aspect


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width
    return text[:width - 3] + "..."


def _pack_tokens(tokens: list[str], width: int, separator: str = "   ") -> list[str]:
    lines: list[str] = []
    current = ""
    for token in tokens:
        if len(strip_ansi(token)) > width:
            token = _truncate(strip_ansi(token), width)
        candidate = token if not current else f"{current}{separator}{token}"
        if not current or len(strip_ansi(candidate)) <= width:
            current = candidate
        else:
            lines.append(current)
            current = token
    if current:
        lines.append(current)
    return lines


def _fmt_mass(value: float) -> str:
    return f"{value:.3f}" if value >= 0.01 else f"{value:.2e}"


def _orbit_text(orbit: Orbit) -> tuple[str, str, str]:
    semi_major = f"{orbit.semi_major:.4f}" if orbit.semi_major is not None else "-"
    eccentricity = f"{orbit.eccentricity:.3f}" if orbit.eccentricity is not None else "-"
    period = f"{orbit.period:,.2f}" if orbit.period is not None else "-"
    return semi_major, eccentricity, period


def _primary_index(world: World) -> int:
    return max(range(len(world.bodies)), key=lambda index: world.bodies[index].mass)


def _dominant_primary(world: World) -> bool:
    masses = sorted((body.mass for body in world.bodies), reverse=True)
    if len(masses) < 2:
        return True
    return masses[0] >= 10.0 * masses[1]


def _body_payload(scenario: Scenario, body: Body, primary: Body, index: int,
                  primary_index: int, dominant: bool) -> dict[str, object]:
    meaningful = index != primary_index and dominant
    orbit = orbital_elements(primary, body, scenario.g) if meaningful else Orbit(None, None, None)
    distance = 0.0 if index == primary_index else body.pos.distance_to(primary.pos)
    return {
        "name": body.name,
        "mass": body.mass,
        "position": {"x": body.pos.x, "y": body.pos.y},
        "velocity": {"x": body.vel.x, "y": body.vel.y},
        "speed": body.vel.norm() * scenario.speed_scale,
        "distance_from_primary": distance,
        "semi_major_axis": orbit.semi_major,
        "eccentricity": orbit.eccentricity,
        "period": orbit.period,
    }


def _info_payload(scenario: Scenario, world: World, primary_index: int) -> dict[str, object]:
    primary = world.bodies[primary_index]
    dominant = _dominant_primary(world)
    return {
        "key": scenario.key,
        "title": scenario.title,
        "description": scenario.description,
        "units": {
            "time": scenario.time_unit,
            "distance": scenario.distance_unit,
            "mass": scenario.mass_unit,
            "speed": scenario.speed_unit,
        },
        "g": scenario.g,
        "dt": scenario.dt,
        "span": scenario.span,
        "dominant_primary": dominant,
        "bodies": [
            _body_payload(scenario, body, primary, index, primary_index, dominant)
            for index, body in enumerate(world.bodies)
        ],
        "energy": world.total_energy(),
        "angular_momentum": world.angular_momentum(),
    }


def _catalog_payload(scenario: Scenario) -> dict[str, object]:
    payload: dict[str, object] = {
        "key": scenario.key,
        "title": scenario.title,
        "description": scenario.description,
        "bodies": [
            {
                "name": body.name,
                "mass": body.mass,
                "symbol": body.symbol,
                "color": body.color,
            }
            for body in scenario.bodies
        ],
        "g": scenario.g,
        "dt": scenario.dt,
        "span": scenario.span,
        "extent": list(scenario.extent),
        "units": {
            "time": scenario.time_unit,
            "distance": scenario.distance_unit,
            "mass": scenario.mass_unit,
            "speed": scenario.speed_unit,
            "speed_scale": scenario.speed_scale,
        },
        "steps_per_frame": scenario.steps_per_frame,
        "trail_length": scenario.trail_length,
        "record_every": scenario.record_every,
        "default_frames": scenario.default_frames,
        "export_until": scenario.export_until,
    }
    if scenario.c is not None:
        payload["c"] = scenario.c
    return payload


def _cmd_list(args: argparse.Namespace) -> int:
    keys = scenario_keys()
    if args.json:
        print(json.dumps([_catalog_payload(get_scenario(key)) for key in keys],
                         indent=2, allow_nan=False))
        return 0
    width = max(len(key) for key in keys)
    print(f"{'key':<{width}}  {'bodies':>6}  {'span':>10}  title")
    for key in keys:
        scenario = get_scenario(key)
        span = f"{scenario.span:g} {scenario.distance_unit}"
        print(f"{key:<{width}}  {len(scenario.bodies):>6}  {span:>10}  {scenario.title}")
    print()
    print("Try: python -m orrery snapshot solar")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    scenario = _scenario(args.key)
    world = World(scenario.bodies, scenario.g)
    primary_index = _primary_index(world)
    if args.json:
        print(json.dumps(_info_payload(scenario, world, primary_index),
                         indent=2, allow_nan=False))
        return 0

    width = min(96, max(60, shutil.get_terminal_size((96, 24)).columns))
    print(f"ORRERY - {scenario.title}")
    print(textwrap.fill(scenario.description, width=width))
    print()
    print(f"G = {scenario.g:.6g} {scenario.distance_unit}^3 / "
          f"({scenario.mass_unit} * {scenario.time_unit}^2)"
          "    integrator = kick-drift-kick leapfrog")
    print(f"dt = {scenario.dt:g} {scenario.time_unit}"
          f"    span = {scenario.span:g} {scenario.distance_unit}"
          f"    bodies = {len(world.bodies)}")
    print()
    print(f"{'body':<10} {'mass':>11} {'r':>9} {'a':>9} {'ecc':>7} "
          f"{'period':>11} {'speed':>11}")
    print(f"{'':<10} {f'({scenario.mass_unit})':>11} {f'({scenario.distance_unit})':>9} "
          f"{f'({scenario.distance_unit})':>9} {'':>7} {f'({scenario.time_unit})':>11} "
          f"{f'({scenario.speed_unit})':>11}")
    primary = world.bodies[primary_index]
    dominant = _dominant_primary(world)
    for index, body in enumerate(world.bodies):
        if index == primary_index:
            distance, semi_major, eccentricity, period = "-", "-", "-", "-"
        else:
            distance = f"{body.pos.distance_to(primary.pos):.4f}"
            if dominant:
                semi_major, eccentricity, period = _orbit_text(
                    orbital_elements(primary, body, scenario.g)
                )
            else:
                semi_major, eccentricity, period = "-", "-", "-"
        speed = body.vel.norm() * scenario.speed_scale
        print(f"{body.name[:10]:<10} {_fmt_mass(body.mass):>11} {distance:>9} "
              f"{semi_major:>9} {eccentricity:>7} {period:>11} {speed:>11.2f}")
    print()
    print(f"initial energy   = {world.total_energy():+.6e}")
    print(f"angular momentum = {world.angular_momentum():+.6e}")
    if not dominant:
        print()
        print("Orbit columns are blank: no single body dominates, so two-body "
              "elements around one body would mislead.")
    return 0


_SPARK_UNICODE = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")
_SPARK_ASCII = (".", "-", "=", "#")


def _sparkline(values: Sequence[float], width: int, *, ascii_only: bool = False) -> str:
    """Render a compact sparkline trend string for a series of numeric samples."""
    if not values:
        return ""
    recent = list(values[-width:])
    min_val = min(recent)
    max_val = max(recent)
    span = max_val - min_val
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    use_ascii = ascii_only
    if not use_ascii:
        try:
            "".join(_SPARK_UNICODE).encode(encoding)
        except (UnicodeEncodeError, LookupError):
            use_ascii = True
    glyphs = _SPARK_ASCII if use_ascii else _SPARK_UNICODE
    if span <= 1e-15:
        return glyphs[len(glyphs) // 2] * len(recent)
    chars = []
    for val in recent:
        index = int((val - min_val) / span * (len(glyphs) - 1))
        index = max(0, min(len(glyphs) - 1, index))
        chars.append(glyphs[index])
    return "".join(chars)


class KeyboardReader:
    """Non-blocking single-key reader with automatic terminal restore."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdin.isatty()
        self._old_settings = None

    def __enter__(self) -> KeyboardReader:
        if not self.enabled:
            return self
        if os.name != "nt":
            try:
                import termios
                import tty

                fd = sys.stdin.fileno()
                self._old_settings = termios.tcgetattr(fd)
                tty.setcbreak(fd)
            # hygiene: allow terminal setup is best-effort
            except Exception:
                self.enabled = False
        return self

    def __exit__(self, *args: object) -> None:
        if self._old_settings is not None and os.name != "nt":
            try:
                import termios

                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_settings)
            # hygiene: allow terminal teardown is best-effort
            except Exception:
                pass

    def poll(self) -> str | None:
        """Return the next pressed character if one is available, or None."""
        if not self.enabled:
            return None
        if os.name == "nt":
            try:
                import msvcrt

                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        if msvcrt.kbhit():
                            ch2 = msvcrt.getwch()
                            arrow_map = {"H": "w", "P": "s", "K": "a", "M": "d"}
                            return arrow_map.get(ch2, None)
                        return None
                    return ch
            # hygiene: allow non-blocking read is best-effort
            except Exception:
                return None
            return None
        try:
            import select

            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if rlist:
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    rlist2, _, _ = select.select([sys.stdin], [], [], 0)
                    if rlist2:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            ch3 = sys.stdin.read(1)
                            arrow_map = {"A": "w", "B": "s", "D": "a", "C": "d"}
                            return arrow_map.get(ch3, None)
                return ch
        # hygiene: allow non-blocking read is best-effort
        except Exception:
            return None
        return None


def _compose_frame(world: World, scenario: Scenario, viewport: Viewport,
                   recorder: TrailRecorder, initial_energy: float,
                   *, ascii_only: bool, color: bool, braille: bool = False,
                   telemetry: bool = False,
                   energy_history: Sequence[float] | None = None,
                   initial_momentum: float | None = None,
                   controls_hint: bool = False,
                   paused: bool = False,
                   camera_label: str | None = None,
                   fps: float | None = None,
                   dot_char: str | None = None) -> str:
    bar = "-" * viewport.width if ascii_only else "─" * viewport.width
    separator = " | " if ascii_only else " · "
    drift_label = "dE/E" if ascii_only else "ΔE/E"
    pause_tag = "[PAUSED] " if paused else ""
    title = _truncate(f"{pause_tag}ORRERY{separator}{scenario.title}", viewport.width)
    lines = [title, bar]
    lines.extend(render_scene(world, recorder.trails, viewport,
                              ascii_only=ascii_only, color=color, braille=braille,
                              dot_char=dot_char))
    lines.append(bar)
    current_drift = world.energy_drift(initial_energy)
    stats = [
        f"t = {world.time:,.2f} {scenario.time_unit}",
        f"bodies = {len(world.bodies)}",
        f"{drift_label} = {current_drift:+.2e}",
    ]
    if fps is not None:
        stats.append(f"fps = {fps:.1f}")
    if camera_label:
        stats.append(f"cam: {camera_label}")
    lines.extend(_pack_tokens(stats, viewport.width, separator="    "))
    if telemetry:
        history = list(energy_history) if energy_history else [current_drift]
        spark_width = max(6, min(20, viewport.width - 34))
        spark = _sparkline(history, spark_width, ascii_only=ascii_only)
        telemetry_tokens = [
            f"{drift_label} trend: [{spark}]",
            f"min: {min(history):+.2e}",
            f"max: {max(history):+.2e}",
        ]
        if initial_momentum is not None:
            dl = world.angular_momentum() - initial_momentum
            dl_label = "dLz" if ascii_only else "ΔLz"
            telemetry_tokens.append(f"{dl_label}: {dl:+.2e}")
        lines.extend(_pack_tokens(telemetry_tokens, viewport.width, separator="  "))
    legend = []
    for body in world.bodies:
        if color:
            legend.append(f"{ANSI.get(body.color, ANSI['white'])}{body.symbol}{RESET} {body.name}")
        else:
            legend.append(f"{body.symbol} {body.name}")
    lines.extend(_pack_tokens(legend, viewport.width))
    if controls_hint:
        hint_text = "[Space] Pause  [.] Step  [f] Track  [WASD] Pan  [[]] Zoom  [{}] Aspect  [b] Dots  [n/p] World  [C] Clear  [R] Reset  [T] Telemetry  [Q] Quit"
        if len(hint_text) <= viewport.width:
            lines.append(hint_text)
        else:
            lines.extend(_pack_tokens([
                "[Space] Pause", "[.] Step", "[f] Track", "[WASD] Pan", "[[]] Zoom",
                "[{}] Aspect", "[b] Dots", "[n/p] World", "[C] Clear", "[R] Reset",
                "[T] Telemetry", "[Q] Quit",
            ], viewport.width, separator="  "))
    return "\n".join(lines)


def _simulate(scenario: Scenario, target: float, trail_limit: int,
              *, relativity: bool = False, c_override: float | None = None,
              merge_radius: float = 0.0) -> tuple[World, TrailRecorder, float]:
    c_val = c_override if c_override is not None else (scenario.c if relativity else None)
    world = World(scenario.bodies, scenario.g, c=c_val)
    initial_energy = world.total_energy()
    recorder = TrailRecorder(world, trail_limit)
    recorder.advance_to(world, target, scenario.dt, scenario.record_every, merge_radius=merge_radius)
    return world, recorder, initial_energy


def _cmd_snapshot(args: argparse.Namespace) -> int:
    scenario = _scenario(args.key)
    if not math.isfinite(args.at) or args.at < 0.0:
        raise CliError(
            f"--at {args.at:g} is not a valid time.",
            "a snapshot needs a finite, non-negative simulation time.",
            "pass --at 0 for the initial state, or a positive number of "
            f"{scenario.time_unit}.",
            code=2,
        )
    estimated_steps = math.ceil(args.at / scenario.dt)
    if estimated_steps > SNAPSHOT_STEP_LIMIT and not getattr(args, "force", False):
        raise CliError(
            f"--at {args.at:g} needs about {estimated_steps:,} integration steps.",
            "a single snapshot should not run for hours without warning.",
            "lower --at, or pass --force to allow the full run.",
            code=2,
        )
    width, height = _scene_size(args)
    relativity = getattr(args, "relativity", False)
    c_override = getattr(args, "c_light", None)
    merge_radius = getattr(args, "merge_radius", 0.0) if getattr(args, "merge", False) else 0.0

    world, recorder, initial_energy = _simulate(
        scenario, args.at, _trail_limit(args, scenario),
        relativity=relativity, c_override=c_override, merge_radius=merge_radius,
    )
    viewport = _viewport(scenario, width, height, _aspect(args))
    color = _color_enabled(args)
    if color:
        color = _enable_windows_ansi()
    ascii_only = not _unicode_enabled(args)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    dot_arg = getattr(args, "dot", None)
    if dot_arg == "braille":
        braille = not ascii_only
        dot_char = None
    elif dot_arg is not None:
        braille = False
        dot_char = resolve_dot_char(dot_arg, ascii_only=ascii_only, encoding=encoding)
    else:
        braille = (not ascii_only) and not getattr(args, "no_braille", False)
        dot_char = None
    frame = _compose_frame(
        world, scenario, viewport, recorder, initial_energy,
        ascii_only=ascii_only, color=color, braille=braille,
        telemetry=getattr(args, "telemetry", False),
        energy_history=[world.energy_drift(initial_energy)],
        initial_momentum=world.angular_momentum(),
        dot_char=dot_char,
    )
    print(frame)
    return 0


def _enable_windows_ansi() -> bool:
    """Enable VT processing when possible; return whether ANSI control is safe."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
        return False
    # hygiene: allow VT-mode setup is best-effort; the ASCII renderer works without it
    except (AttributeError, OSError):
        return False


def _cmd_run(args: argparse.Namespace) -> int:
    scenario = _scenario(args.key)
    if not math.isfinite(args.fps) or not MIN_FPS <= args.fps <= MAX_FPS:
        raise CliError(
            f"--fps {args.fps:g} is outside the supported range.",
            f"the player sleeps between frames, so the rate must be between "
            f"{MIN_FPS:g} and {MAX_FPS:g}.",
            "pass a value such as --fps 24.",
            code=2,
        )
    interactive = sys.stdout.isatty()
    frames = args.frames if args.frames is not None else (0 if interactive else 1)
    if frames < 0:
        raise CliError(
            f"--frames {frames} is negative.",
            "a frame count cannot be less than zero; zero means loop forever.",
            "pass 0 to loop, or a positive frame count.",
            code=2,
        )
    width, height = _scene_size(args)
    color = _color_enabled(args)
    ascii_only = not _unicode_enabled(args)
    braille = (not ascii_only) and not getattr(args, "no_braille", False)
    vt_ready = _enable_windows_ansi() if interactive else True
    if not vt_ready:
        color = False
    screen_control = interactive and vt_ready
    aspect = _aspect(args)
    initial_aspect = aspect
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    dot_styles_cycle = ["braille", "circle", "bullet", "ring", "disc", "dot", "ascii"]
    dot_arg = getattr(args, "dot", None)
    if dot_arg is not None:
        dot_style = dot_arg
    elif braille:
        dot_style = "braille"
    else:
        dot_style = "ascii" if ascii_only else "dot"
    initial_dot_style = dot_style

    relativity = getattr(args, "relativity", False)
    c_override = getattr(args, "c_light", None)
    merge_radius = getattr(args, "merge_radius", 0.0) if getattr(args, "merge", False) else 0.0

    world, recorder, initial_energy = _simulate(
        scenario, 0.0, _trail_limit(args, scenario),
        relativity=relativity, c_override=c_override, merge_radius=merge_radius,
    )
    initial_momentum = world.angular_momentum()
    energy_history: list[float] = [world.energy_drift(initial_energy)]
    frame_index = 0
    stopped = False
    paused = False
    single_step = False
    fps = args.fps
    telemetry_enabled = getattr(args, "telemetry", False)
    controls_enabled = interactive and not getattr(args, "no_controls", False)
    show_hints = controls_enabled

    zoom_factor = 1.0
    pan_offset = Vec2()
    tracking_index: int | None = None

    catalog = scenario_keys()
    scenario_idx = catalog.index(scenario.key) if scenario.key in catalog else None

    if screen_control:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
    with KeyboardReader(enabled=controls_enabled) as keyboard:
        try:
            while frames == 0 or frame_index < frames:
                key = keyboard.poll()
                while key is not None:
                    if key in ("q", "Q", "\x03"):
                        stopped = True
                        break
                    if key == " ":
                        paused = not paused
                    elif key == ".":
                        single_step = True
                    elif key in ("+", "="):
                        fps = min(MAX_FPS, fps * 1.5)
                    elif key in ("-", "_"):
                        fps = max(MIN_FPS, fps / 1.5)
                    elif key in ("{", "<"):
                        aspect = max(0.5, round(aspect - 0.05, 2))
                    elif key in ("}", ">"):
                        aspect = min(5.0, round(aspect + 0.05, 2))
                    elif key in ("b", "B"):
                        idx = dot_styles_cycle.index(dot_style) if dot_style in dot_styles_cycle else 0
                        dot_style = dot_styles_cycle[(idx + 1) % len(dot_styles_cycle)]
                        if dot_style == "braille" and ascii_only:
                            dot_style = "circle"
                    elif key in ("c", "C"):
                        recorder.clear(world)
                    elif key in ("r", "R"):
                        world, recorder, initial_energy = _simulate(
                            scenario, 0.0, _trail_limit(args, scenario),
                            relativity=relativity, c_override=c_override, merge_radius=merge_radius,
                        )
                        initial_momentum = world.angular_momentum()
                        energy_history = [world.energy_drift(initial_energy)]
                        zoom_factor = 1.0
                        pan_offset = Vec2()
                        tracking_index = None
                    elif key in ("t", "T"):
                        telemetry_enabled = not telemetry_enabled
                    elif key in ("h", "?"):
                        show_hints = not show_hints
                    elif key in ("f", "F"):
                        if not world.bodies:
                            tracking_index = None
                        elif tracking_index is None:
                            tracking_index = 0
                        elif tracking_index + 1 < len(world.bodies):
                            tracking_index += 1
                        else:
                            tracking_index = None
                    elif key == "0":
                        tracking_index = None
                        pan_offset = Vec2()
                        zoom_factor = 1.0
                        aspect = initial_aspect
                        dot_style = initial_dot_style
                    elif key in "123456789":
                        digit = int(key) - 1
                        if digit < len(world.bodies):
                            tracking_index = digit
                    elif key in ("[", "i", "I"):
                        zoom_factor = max(0.02, zoom_factor / 1.25)
                    elif key in ("]", "o", "O"):
                        zoom_factor = min(50.0, zoom_factor * 1.25)
                    elif key in ("w", "W"):
                        span_now = _fit_span(scenario, width, height, aspect) * zoom_factor
                        pan_offset = Vec2(pan_offset.x, pan_offset.y + 0.1 * span_now)
                    elif key in ("s", "S"):
                        span_now = _fit_span(scenario, width, height, aspect) * zoom_factor
                        pan_offset = Vec2(pan_offset.x, pan_offset.y - 0.1 * span_now)
                    elif key in ("a", "A"):
                        span_now = _fit_span(scenario, width, height, aspect) * zoom_factor
                        pan_offset = Vec2(pan_offset.x - 0.1 * span_now, pan_offset.y)
                    elif key in ("d", "D"):
                        span_now = _fit_span(scenario, width, height, aspect) * zoom_factor
                        pan_offset = Vec2(pan_offset.x + 0.1 * span_now, pan_offset.y)
                    elif key in ("n", "N", "p", "P") and catalog:
                        if scenario_idx is None:
                            scenario_idx = 0
                        else:
                            step = 1 if key in ("n", "N") else -1
                            scenario_idx = (scenario_idx + step) % len(catalog)
                        scenario = get_scenario(catalog[scenario_idx])
                        world, recorder, initial_energy = _simulate(
                            scenario, 0.0, _trail_limit(args, scenario),
                            relativity=relativity, c_override=c_override, merge_radius=merge_radius,
                        )
                        initial_momentum = world.angular_momentum()
                        energy_history = [world.energy_drift(initial_energy)]
                        zoom_factor = 1.0
                        pan_offset = Vec2()
                        tracking_index = None
                    key = keyboard.poll()

                if stopped:
                    break

                if not paused or single_step:
                    recorder.advance(world, scenario.dt, scenario.steps_per_frame,
                                     scenario.record_every, merge_radius=merge_radius)
                    frame_index += 1
                    energy_history.append(world.energy_drift(initial_energy))
                    if len(energy_history) > 60:
                        energy_history.pop(0)
                    single_step = False

                if dot_style == "braille" and not ascii_only:
                    current_braille = True
                    dot_char = None
                else:
                    current_braille = False
                    dot_char = resolve_dot_char(dot_style, ascii_only=ascii_only, encoding=encoding)

                if tracking_index is not None and tracking_index < len(world.bodies):
                    center_pos = world.bodies[tracking_index].pos + pan_offset
                else:
                    center_pos = pan_offset
                    if tracking_index is not None and tracking_index >= len(world.bodies):
                        tracking_index = None

                viewport = _viewport(scenario, width, height, aspect, center=center_pos,
                                     span_factor=zoom_factor)

                cam_tokens = []
                if tracking_index is not None and tracking_index < len(world.bodies):
                    cam_tokens.append(f"[{world.bodies[tracking_index].name}]")
                if abs(zoom_factor - 1.0) > 0.05:
                    cam_tokens.append(f"{1.0 / zoom_factor:.1f}x")
                if pan_offset.norm() > 1e-4:
                    cam_tokens.append("panned")
                if abs(aspect - initial_aspect) > 0.01:
                    cam_tokens.append(f"asp={aspect:.2f}")
                if dot_style != initial_dot_style:
                    cam_tokens.append(f"dot={dot_style}")
                camera_label = " ".join(cam_tokens) if cam_tokens else None

                if screen_control:
                    sys.stdout.write("\x1b[H\x1b[2J")
                sys.stdout.write(_compose_frame(
                    world, scenario, viewport, recorder, initial_energy,
                    ascii_only=ascii_only, color=color, braille=current_braille,
                    telemetry=telemetry_enabled,
                    energy_history=energy_history,
                    initial_momentum=initial_momentum,
                    controls_hint=show_hints,
                    paused=paused,
                    camera_label=camera_label,
                    fps=fps,
                    dot_char=dot_char,
                ) + "\n")
                sys.stdout.flush()
                if frames == 0 or frame_index < frames:
                    sleep_time = 0.05 if paused else (1.0 / fps)
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            stopped = True
        finally:
            if screen_control:
                sys.stdout.write("\x1b[?25h\n")
                sys.stdout.flush()
    if stopped:
        print(f"Stopped at t = {world.time:,.2f} {scenario.time_unit}.")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    scenario = _scenario(args.key)
    out = Path(args.out).expanduser()
    if out.exists() and out.is_dir():
        raise CliError(
            f"{out} is a directory.",
            "the export writes a data file, not a folder.",
            "pass a file path such as --out orbit.csv or orbit.json.",
            code=2,
        )
    if not out.parent.exists():
        raise CliError(
            f"the folder for {out} does not exist.",
            "the export does not create parent directories.",
            f"create {out.parent} first, or pass a path in an existing folder.",
            code=2,
        )
    until = args.until if args.until is not None else scenario.export_until
    every = args.every if args.every is not None else scenario.dt * scenario.steps_per_frame
    if not math.isfinite(until) or until <= 0.0:
        raise CliError(
            f"--until {until:g} is not a valid time.",
            "an export needs a positive, finite window.",
            f"pass a value such as --until {scenario.export_until:g}.",
            code=2,
        )
    if not math.isfinite(every) or every <= 0.0:
        raise CliError(
            f"--every {every:g} is not a valid interval.",
            "the sampling interval must be positive so the file stays finite.",
            f"pass a value such as --every {scenario.dt * scenario.steps_per_frame:g}.",
            code=2,
        )
    ratio = until / every
    if not math.isfinite(ratio):
        raise CliError(
            "the export window is too large.",
            "dividing the window by the interval overflowed the sample count.",
            "increase --every or decrease --until.",
            code=2,
        )
    sample_count = int(math.floor(ratio + 1e-12)) + 1
    if sample_count > MAX_EXPORT_SAMPLES:
        raise CliError(
            f"the export would write {sample_count:,} samples.",
            "an unbounded sample count can fill the disk and stall the terminal.",
            "increase --every or decrease --until.",
            code=2,
        )
    targets = [index * every for index in range(sample_count)]
    if targets[-1] < until - 1e-12:
        targets.append(until)
    if len(targets) > MAX_EXPORT_SAMPLES:
        raise CliError(
            f"the export would write {len(targets):,} samples.",
            "an unbounded sample count can fill the disk and stall the terminal.",
            "increase --every or decrease --until.",
            code=2,
        )
    export_format = getattr(args, "format", "csv")
    relativity = getattr(args, "relativity", False)
    c_override = getattr(args, "c_light", None)
    c_val = c_override if c_override is not None else (scenario.c if relativity else None)
    merge_radius = getattr(args, "merge_radius", 0.0) if getattr(args, "merge", False) else 0.0

    metadata = _catalog_payload(scenario)
    metadata["export"] = {
        "until": until,
        "every": every,
        "samples": len(targets),
    }
    if relativity:
        metadata["export"]["relativity"] = True
        metadata["export"]["c"] = c_val
    if merge_radius > 0.0:
        metadata["export"]["merge_radius"] = merge_radius

    world = World(scenario.bodies, scenario.g, c=c_val)
    temporary: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=out.parent,
            prefix=f"{out.name}.", suffix=".tmp", delete=False,
        )
        temporary = Path(handle.name)
        with handle:
            if export_format == "csv":
                writer = csv.writer(handle)
                writer.writerow(["time", "body", "x", "y", "vx", "vy", "speed"])
                for target in targets:
                    world.advance_to(target, scenario.dt, merge_radius=merge_radius)
                    for body in world.bodies:
                        writer.writerow([
                            f"{world.time:.10g}",
                            body.name,
                            f"{body.pos.x:.12g}",
                            f"{body.pos.y:.12g}",
                            f"{body.vel.x:.12g}",
                            f"{body.vel.y:.12g}",
                            f"{body.vel.norm():.12g}",
                        ])
            else:
                handle.write('{\n  "scenario": ')
                json.dump(metadata, handle, allow_nan=False)
                handle.write(',\n  "samples": [')
                first = True
                for target in targets:
                    world.advance_to(target, scenario.dt, merge_radius=merge_radius)
                    sample = {
                        "time": world.time,
                        "bodies": [
                            {
                                "name": body.name,
                                "x": body.pos.x,
                                "y": body.pos.y,
                                "vx": body.vel.x,
                                "vy": body.vel.y,
                                "speed": body.vel.norm(),
                            }
                            for body in world.bodies
                        ],
                    }
                    if not first:
                        handle.write(",")
                    handle.write("\n    ")
                    json.dump(sample, handle, allow_nan=False)
                    first = False
                handle.write("\n  ]\n}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, out)
        temporary = None
    except OSError as error:
        raise CliError(
            f"could not write {out}: {error}",
            "the export writes a temporary file and then replaces the target.",
            "check the folder permissions and that no other program holds the file open.",
        ) from error
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)
    rows = len(targets) * len(world.bodies)
    print(f"wrote {rows:,} rows across {len(targets):,} samples to {out} "
          f"({export_format})")
    print(f"units: {scenario.distance_unit}, {scenario.time_unit}; "
          f"velocity in {scenario.distance_unit}/{scenario.time_unit}")
    return 0


def _add_view_options(parser: argparse.ArgumentParser, *, trails: bool = False) -> None:
    parser.add_argument("--width", type=int, default=None,
                        help="scene width in columns (default: fit the terminal)")
    parser.add_argument("--height", type=int, default=None,
                        help="scene height in rows (default: fit the terminal)")
    parser.add_argument("--ascii", action="store_true",
                        help="use ASCII borders and trail dots only")
    parser.add_argument("--no-color", action="store_true",
                        help="disable ANSI colour even on a terminal")
    parser.add_argument("--aspect", type=float, default=CELL_ASPECT,
                        help="terminal cell height/width ratio (default: 2.0)")
    parser.add_argument("--no-braille", action="store_true",
                        help="use one-cell trail marks instead of Braille subcells")
    if trails:
        parser.add_argument("--trail", type=int, default=None,
                            help="number of recorded positions per body")
        parser.add_argument("--no-trail", action="store_true",
                            help="hide orbit trails")
        parser.add_argument("--dot", default=None,
                            choices=("braille", "circle", "bullet", "ring", "disc", "dot", "ascii"),
                            help="orbit dot style: braille, circle, bullet, ring, disc, dot, ascii")


def _add_physics_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--relativity", action="store_true",
                        help="enable post-Newtonian 1PN general relativistic precession")
    parser.add_argument("--c-light", type=float, default=None,
                        help="speed of light override for 1PN relativity")
    parser.add_argument("--merge", action="store_true",
                        help="enable inelastic collision coalescence")
    parser.add_argument("--merge-radius", type=float, default=0.02,
                        help="collision distance threshold for coalescence (default: 0.02)")


def build_parser() -> argparse.ArgumentParser:
    parser = TriadParser(
        prog="orrery",
        description="A zero-dependency N-body sandbox that draws orbits in your terminal.",
        epilog="Start with: python -m orrery list",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=TriadParser)

    listing = commands.add_parser("list", help="show the built-in scenarios")
    listing.add_argument("--json", action="store_true",
                         help="emit the catalogue as machine-readable JSON")
    listing.set_defaults(handler=_cmd_list)

    info = commands.add_parser("info", help="describe a scenario and its initial orbits")
    info.add_argument("key", help="scenario key, alias, or .json scenario file")
    info.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    info.set_defaults(handler=_cmd_info)

    validate = commands.add_parser("validate", help="validate a custom JSON scenario")
    validate.add_argument("path", help="path to a scenario .json file")
    validate.set_defaults(handler=_cmd_validate)

    snapshot = commands.add_parser("snapshot", help="draw one frame at a chosen time")
    snapshot.add_argument("key", help="scenario key, alias, or .json scenario file")
    snapshot.add_argument("--at", type=float, default=0.0,
                          help="simulation time to reach before drawing")
    snapshot.add_argument("--force", action="store_true",
                          help="allow a snapshot beyond the integration-step budget")
    snapshot.add_argument("--telemetry", action="store_true",
                          help="display live energy drift trend in footer")
    _add_view_options(snapshot, trails=True)
    _add_physics_options(snapshot)
    snapshot.set_defaults(handler=_cmd_snapshot)

    run = commands.add_parser("run", help="animate a scenario in the terminal")
    run.add_argument("key", help="scenario key, alias, or .json scenario file")
    run.add_argument("--frames", type=int, default=None,
                     help="number of frames; 0 loops forever "
                          "(default: forever on a terminal, one still when piped)")
    run.add_argument("--fps", type=float, default=24.0,
                     help=f"frames per second, {MIN_FPS:g}-{MAX_FPS:g} (default: 24)")
    run.add_argument("--telemetry", action="store_true",
                     help="display live energy drift sparkline and telemetry HUD")
    run.add_argument("--no-controls", action="store_true",
                     help="disable interactive keyboard controls")
    _add_view_options(run, trails=True)
    _add_physics_options(run)
    run.set_defaults(handler=_cmd_run)

    export = commands.add_parser("export", help="write sampled positions to CSV")
    export.add_argument("key", help="scenario key, alias, or .json scenario file")
    export.add_argument("--out", required=True, help="destination data file")
    export.add_argument("--format", choices=("csv", "json"), default="csv",
                        help="output format (default: csv)")
    export.add_argument("--until", type=float, default=None,
                        help="end of the export window; the final state is included")
    export.add_argument("--every", type=float, default=None,
                        help="sampling interval in simulation time")
    _add_physics_options(export)
    export.set_defaults(handler=_cmd_export)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        try:
            return int(args.handler(args))
        except CliError as error:
            print(f"Error: {error}")
            print(f"Why: {error.why}")
            print(f"Fix: {error.fix}")
            return error.code
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 0
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
