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
from .render import ANSI, RESET, Viewport, render_scene
from .scenarios import Scenario, get_scenario, scenario_keys
from .sim import Body, Orbit, World, orbital_elements
from .trails import TrailRecorder


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
        """Print usage and a triad, then exit 2 like any other usage failure."""
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n"
                     "Why: the command needs a known subcommand and valid options.\n"
                     "Fix: run `python -m orrery --help`, then retry with one of its "
                     "listed commands.\n")


def _scenario(name: str) -> Scenario:
    try:
        return get_scenario(name)
    except KeyError:
        available = ", ".join(scenario_keys())
        raise CliError(
            f"unknown scenario '{name}'.",
            "a scenario key selects one built-in initial state.",
            f"choose one of: {available}.",
        ) from None


def _color_enabled(args: argparse.Namespace) -> bool:
    if getattr(args, "no_color", False) or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _unicode_enabled(args: argparse.Namespace) -> bool:
    if getattr(args, "ascii", False):
        return False
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "·─".encode(encoding)
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


def _cmd_list(args: argparse.Namespace) -> int:
    keys = scenario_keys()
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


def _compose_frame(world: World, scenario: Scenario, viewport: Viewport,
                   recorder: TrailRecorder, initial_energy: float,
                   *, ascii_only: bool, color: bool) -> str:
    bar = "-" * viewport.width if ascii_only else "─" * viewport.width
    separator = " | " if ascii_only else " · "
    drift_label = "dE/E" if ascii_only else "ΔE/E"
    lines = [f"ORRERY{separator}{scenario.title}", bar]
    lines.extend(render_scene(world, recorder.trails, viewport,
                              ascii_only=ascii_only, color=color))
    lines.append(bar)
    lines.append(
        f"t = {world.time:,.2f} {scenario.time_unit}"
        f"    bodies = {len(world.bodies)}"
        f"    {drift_label} = {world.energy_drift(initial_energy):+.2e}"
    )
    legend = []
    for body in world.bodies:
        if color:
            legend.append(f"{ANSI.get(body.color, ANSI['white'])}{body.symbol}{RESET} {body.name}")
        else:
            legend.append(f"{body.symbol} {body.name}")
    lines.append("   ".join(legend))
    return "\n".join(lines)


def _simulate(scenario: Scenario, target: float, trail_limit: int
              ) -> tuple[World, TrailRecorder, float]:
    world = World(scenario.bodies, scenario.g)
    initial_energy = world.total_energy()
    recorder = TrailRecorder(world, trail_limit)
    recorder.advance_to(world, target, scenario.dt, scenario.record_every)
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
    width, height = _scene_size(args)
    world, recorder, initial_energy = _simulate(
        scenario, args.at, _trail_limit(args, scenario)
    )
    viewport = Viewport(width, height, scenario.span)
    frame = _compose_frame(world, scenario, viewport, recorder, initial_energy,
                           ascii_only=not _unicode_enabled(args),
                           color=_color_enabled(args))
    print(frame)
    return 0


def _enable_windows_ansi() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    # hygiene: allow VT-mode setup is best-effort; the ASCII renderer works without it
    except (AttributeError, OSError):
        pass


def _cmd_run(args: argparse.Namespace) -> int:
    scenario = _scenario(args.key)
    if not math.isfinite(args.fps) or args.fps <= 0.0:
        raise CliError(
            f"--fps {args.fps:g} is not a valid frame rate.",
            "the player sleeps between frames, so the rate must be positive.",
            "pass a finite value such as --fps 24.",
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
    if interactive:
        _enable_windows_ansi()
    world, recorder, initial_energy = _simulate(scenario, 0.0, _trail_limit(args, scenario))
    viewport = Viewport(width, height, scenario.span)
    frame_index = 0
    stopped = False
    if interactive:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
    try:
        while frames == 0 or frame_index < frames:
            recorder.advance(world, scenario.dt, scenario.steps_per_frame,
                             scenario.record_every)
            frame_index += 1
            if interactive:
                sys.stdout.write("\x1b[H\x1b[2J")
            sys.stdout.write(_compose_frame(
                world, scenario, viewport, recorder, initial_energy,
                ascii_only=ascii_only, color=color,
            ) + "\n")
            sys.stdout.flush()
            if frames == 0 or frame_index < frames:
                time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        stopped = True
    finally:
        if interactive:
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
            "the export writes a CSV file, not a folder.",
            "pass a file path such as --out orbit.csv.",
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
    sample_count = int(math.floor(until / every + 1e-12)) + 1
    if sample_count > 200_000:
        raise CliError(
            f"the export would write {sample_count:,} samples.",
            "an unbounded sample count can fill the disk and stall the terminal.",
            "increase --every or decrease --until.",
            code=2,
        )
    world = World(scenario.bodies, scenario.g)
    temporary: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=out.parent,
            prefix=f"{out.name}.", suffix=".tmp", delete=False,
        )
        temporary = Path(handle.name)
        with handle:
            writer = csv.writer(handle)
            writer.writerow(["time", "body", "x", "y", "vx", "vy", "speed"])
            for index in range(sample_count):
                target = index * every
                world.advance_to(target, scenario.dt)
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
    rows = sample_count * len(world.bodies)
    print(f"wrote {rows:,} rows across {sample_count:,} samples to {out}")
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
    if trails:
        parser.add_argument("--trail", type=int, default=None,
                            help="number of recorded positions per body")
        parser.add_argument("--no-trail", action="store_true",
                            help="hide orbit trails")


def build_parser() -> argparse.ArgumentParser:
    parser = TriadParser(
        prog="orrery",
        description="A zero-dependency N-body sandbox that draws orbits in your terminal.",
        epilog="Start with: python -m orrery list",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=TriadParser)

    listing = commands.add_parser("list", help="show the built-in scenarios")
    listing.set_defaults(handler=_cmd_list)

    info = commands.add_parser("info", help="describe a scenario and its initial orbits")
    info.add_argument("key", help="scenario key or alias")
    info.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    info.set_defaults(handler=_cmd_info)

    snapshot = commands.add_parser("snapshot", help="draw one frame at a chosen time")
    snapshot.add_argument("key", help="scenario key")
    snapshot.add_argument("--at", type=float, default=0.0,
                          help="simulation time to reach before drawing")
    _add_view_options(snapshot, trails=True)
    snapshot.set_defaults(handler=_cmd_snapshot)

    run = commands.add_parser("run", help="animate a scenario in the terminal")
    run.add_argument("key", help="scenario key")
    run.add_argument("--frames", type=int, default=None,
                     help="number of frames; 0 loops forever "
                          "(default: forever on a terminal, one still when piped)")
    run.add_argument("--fps", type=float, default=24.0,
                     help="frames per second (default: 24)")
    _add_view_options(run, trails=True)
    run.set_defaults(handler=_cmd_run)

    export = commands.add_parser("export", help="write sampled positions to CSV")
    export.add_argument("key", help="scenario key")
    export.add_argument("--out", required=True, help="destination CSV file")
    export.add_argument("--until", type=float, default=None,
                        help="end of the export window")
    export.add_argument("--every", type=float, default=None,
                        help="sampling interval in simulation time")
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
