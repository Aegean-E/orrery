# orrery

An N-body gravitational sandbox that runs in your terminal. Six carefully chosen worlds, a
symplectic integrator, live energy diagnostics, orbit trails, CSV and JSON export, and no
dependencies outside the Python standard library.

```text
ORRERY · Figure-Eight Choreography
──────────────────────────────────────────────────────────────────────────




              ⣀⣀⣀⣀⣀⣀⣀⣀                              ⣀⣀⣀⣀⣀⣀⣀⣀
         ⢀⡤⠖⠋⠉⠁      ⠈⠉⠓⠲⢤⣀                    ⣀⡤⠖⠚⠉⠁      ⠈⠉⠙⠲⢤⡀
       ⢀⡴⠋                ⠈⠙⠦⣄              ⣠⠴⠋⠁                ⠙⢦⡀
      ⣰B                     ⠈⠙⢦⣀        ⣀⡴⠋⠁                     ⠙⣆
     ⢰⠃                         ⠈⠳⣄    ⣠C⠁                         ⠘⡆
     ⡞                            ⠈⠳⣄⣠⠞⠁                            ⢳
     ⢧                            ⢀⡴⠋⠙⢦⡀                            ⡼
     ⠸⡄                         ⢀⡴⠋    ⠙⢦⡀                         ⢠⠇
      ⠹⣄                     ⢀⣠⠞⠉        ⠉⠳⣄⡀                     ⣠⠏
       ⠈⠳⣄                ⢀⣠⠖⠋              ⠙⠲⣄⡀                ⣠⠞⠁
         ⠈⠓⠦⢄⣀⡀      ⢀⣀⡤⠴⠚⠉                    ⠉⠓⠦⢤⣀⡀      ⢀⣀⡠⠴A⠁
              ⠉⠉⠉⠉⠉⠉⠉⠉                              ⠉⠉⠉⠉⠉⠉⠉⠉




──────────────────────────────────────────────────────────────────────────
t = 6.20 t    bodies = 3    ΔE/E = -4.96e-08
A Alpha   B Beta   C Gamma
```

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10 or newer (standard library only; no runtime packages)
- **Canonical Regression Shield Gate**:
  ```bash
  python -m unittest discover -s tests -t .
  ```
- **Try it now** (from this folder):
  ```bash
  python -m orrery list
  python -m orrery snapshot solar --at 120
  python -m orrery run figure-eight
  python -m orrery info binary
  python -m orrery export trojans --out trojans.csv --until 365
  ```
- **Install the `orrery` command** (optional):
  ```bash
  python -m pip install .
  orrery --version
  orrery run solar
  ```

Press `Ctrl-C` to leave an animation. Unicode terminals use Braille subcell trails by default;
pass `--no-braille` for one-cell trail marks, or `--ascii` to force ASCII borders and dots.

### 🚀 One-Click Launch

- **Windows**: double-click `run.cmd` to open the solar-system animation. It keeps the window
  open when the run ends.
- **macOS**: double-click `run.command`; it opens Terminal, runs the same animation, and waits
  for Return so the final frame stays visible.
- **Linux**: run `./run.sh` (or `sh run.sh`) for the same animation.
- To start a different world, pass its key and any normal `run` options:
  ```text
  run.cmd figure-eight
  run.cmd trojans --fps 30
  ./run.command binary --frames 120
  ./run.sh binary --frames 120
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)

| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status orrery` |
| Phase 4: every gate | `python aikit.py check orrery` |
| Repair memory and map, then check | `python aikit.py fix orrery` |
| Resume an interrupted task | `python aikit.py resume orrery` |

## 🌍 The Built-in Worlds

| Key | Bodies | What it shows |
|---|---|---|
| `solar` | Sun, Mercury, Venus, Earth, Mars | Real eccentric orbits and Kepler's third law. |
| `figure-eight` | Three equal masses | The Chenciner-Montgomery choreography: all three chase one another around a single curve and return after ~6.33 time units. |
| `binary` | Two half-solar stars, one planet | A Jupiter-mass planet on a circumbinary orbit while its two suns wobble around their barycentre. |
| `trojans` | Sun, Jupiter, Achilles, Patroclus | The stable L4 and L5 Lagrange points, 60° ahead of and behind Jupiter. |
| `pythagorean` | Three, Four, Five | The classic 3-4-5 three-body problem: the masses start at rest, have a close chaotic encounter, and two are slung outward. |
| `lagrange` | Three equal masses | The 1772 Euler-Lagrange pinwheel: three equal masses at the vertices of an equilateral triangle rotating rigidly. |
| `rutherford` | Gold nucleus, 3 Alpha particles | Rutherford alpha scattering: Coulomb electrostatic repulsion ($+79e$ vs $+2e$) producing hyperbolic deflections. |
| `bohr` | Proton, 2 Electrons | Semi-classical Bohr planetary atom: electrons in stable orbits bound by inverse-square Coulomb attraction. |
| `black-hole` | Singularity, 2 Relativistic probes | Relativistic black hole ($r_s = 0.20$): high-velocity probes ($>40\% c$) undergoing 1PN general relativistic rosette precession. |

Aliases are forgiving: `inner`, `inner-solar-system`, `solar-system`, `figure-8`, `figure8`,
`eight`, `three-body`, `circumbinary`, `trojan`, `jupiter-trojans`, `pythagoras`, `chaos`, `atom`,
`gold-foil`, `bh`, `singularity` and more resolve to the right scenario.

## 🕹️ Commands

```text
python -m orrery list [--json]
python -m orrery info KEY|FILE [--json]
python -m orrery validate FILE
python -m orrery snapshot KEY|FILE [--at TIME] [--force] [--dt DT] [--reverse] [--telemetry] [--relativity] [--c-light C] [--k-coulomb K] [--merge] [--merge-radius R] [--bounce] [--bounce-radius R] [--restitution E] [--dot STYLE] [--width N] [--height N] [--aspect R] [--ascii] [--no-braille] [--no-color] [--trail N | --no-trail]
python -m orrery run KEY|FILE [--frames N] [--fps 0.1-240] [--dt DT] [--time-scale SCALE] [--reverse] [--telemetry] [--no-controls] [--relativity] [--c-light C] [--k-coulomb K] [--merge] [--merge-radius R] [--bounce] [--bounce-radius R] [--restitution E] [--dot STYLE] [--width N] [--height N] [--aspect R] [--ascii] [--no-braille] [--no-color] [--trail N | --no-trail]
python -m orrery export KEY|FILE --out FILE [--format csv|json] [--until TIME] [--every TIME] [--dt DT] [--reverse] [--relativity] [--c-light C] [--k-coulomb K] [--merge] [--merge-radius R] [--bounce] [--bounce-radius R] [--restitution E]
python -m orrery web [KEY|FILE] [--port PORT] [--host HOST] [--no-open]
```

- `web` starts the zero-dependency browser-based studio at `http://127.0.0.1:8000/` and opens your default browser. Features interactive HTML5/Canvas 2D rendering, time settings (warp slider, reverse, dt), camera panning/zooming, body tracking, live telemetry charts, and custom JSON scenario drag-and-drop.
- `list --json` emits the scenario catalogue with units, extents and initial bodies.
- `snapshot` integrates to `--at` and prints one frame. With no `--at` you get the initial state.
  A snapshot above 2,000,000 integration steps is refused unless you pass `--force`. `--reverse` and `--dt` allow fine-grained backward and custom step snapshots.
- `run` loops on a terminal; `--frames 0` loops forever, and a piped run defaults to one still.
  Frame rates are limited to `0.1`–`240` fps so a typo cannot sleep for years. `--aspect` overrides
  the assumed 2:1 character-cell ratio when your font or terminal differs.
  Interactive keyboard controls on terminals: Space pauses/resumes, . steps one frame while paused, z/x decreases/increases time warp, v reverses time direction, f or 1-9 tracks bodies, WASD or arrow keys pan, [ or ] zoom, { or } calibrates aspect ratio, b cycles orbit dot styles (circle, bullet, ring, disc, dot, ascii, braille), 0 resets camera and time settings, n or p cycles scenarios, +/- adjusts speed, c clears trails, r resets simulation, t toggles live telemetry HUD (displaying energy drift sparkline, momentum drift, K, U, and Virial theorem 2K+U metric), and q quits.
- `info` prints initial distances, osculating orbital elements and energy. `--json` is stable and
  machine-readable. If no single body dominates (the figure-eight and binary worlds), the
  two-body orbit columns are deliberately blank rather than misleading.
- `validate` checks a custom JSON scenario without rendering or advancing it.
- `export` writes CSV rows (`time,body,x,y,vx,vy,speed`) or a JSON document with scenario metadata,
  export settings and per-body samples, in the scenario's native units. Supports `--dt` and `--reverse`.
  It streams through a temporary file and atomically replaces the target when complete; the sample count is capped at 200,000.

Every failure follows the same triad:

```text
Error: unknown scenario 'nibiru'.
Why: a scenario key selects one built-in initial state.
Fix: choose one of: solar, figure-eight, binary, trojans, pythagorean, lagrange, rutherford, bohr, black-hole.
```

Exit codes are `0` success, `1` runtime failure, `2` bad usage.

## 🧩 Custom Scenarios

Any command that accepts a scenario key also accepts a `.json` file. Validate one first, then run
or export it:

```bash
python -m orrery validate examples/custom-two-body.json
python -m orrery run examples/custom-two-body.json
python -m orrery snapshot examples/custom-two-body.json --at 3.14
```

Required fields are `g`, `dt`, `span`, `extent` (`[half_x, half_y]`) and `bodies`. Optional fields
include `key`, `title`, `description`, `units`, `steps_per_frame`, `trail_length`,
`record_every`, `default_frames` and `export_until`; defaults keep a small file runnable. Each
body needs `name`, `mass`, `position` `[x, y]`, `velocity` `[x, y]` and a unique one-character
`symbol`; `color` defaults to white and must come from the built-in palette. The loader rejects
missing or malformed fields, duplicate names or symbols, unknown colours, control characters,
non-finite numbers, files over 1 MiB, more than 64 bodies, and bodies outside their declared
extent. It never executes code from the file.

## 🔭 How It Works

- **Units belong to the scenario.** Solar-system worlds use AU, days and solar masses, so
  `G = 4π² / (365.2568983)² ≈ 2.9591e-4 AU³ / (M☉·d²)`. The figure-eight uses its published
  natural units (`G = 1`, three unit masses) so the initial conditions are exact.
- **Kick-drift-kick leapfrog.** Each step updates velocities by half a kick, drifts positions by
  the full step, then applies the second half-kick using the new forces. The method is
  time-reversible and keeps orbital energy bounded instead of letting it drift secularly.
- **Barycentric initial states.** Every scenario starts with zero net momentum and its centre of
  mass at the origin, so the view does not wander off screen.
- **Trails are bounded and continuous.** A `TrailRecorder` keeps a deque of past positions per
  body, sampled densely (every step or two). Old points fall off the end, and consecutive samples
  are connected with line segments and painted in a dimmed version of each body's colour. On
  Unicode terminals the lines are drawn into a 2×4 Braille subcell grid, so a small orbit looks
  smooth instead of blocky; `--no-braille` keeps one-cell marks and `--ascii` returns to plain dots.
- **The viewport knows about character cells.** A terminal cell is roughly twice as tall as it is
  wide, so the viewport uses twice as many columns per world unit as rows by default; `--aspect`
  changes that ratio for unusual fonts. Circles stay round. Each scenario declares its half-extents;
  the vertical span expands when the terminal is too narrow to fit them, and the title, statistics
  and legend wrap to the scene width.
- **Rendering is pure.** `render_scene` returns exactly `height` lines of `width` visible cells.
  ANSI colours, the caret-hiding animation loop and terminal-size detection live in the CLI, not
  in the drawing code.
- **Energy drift is visible.** The footer shows `ΔE/E` against the initial total energy. A value
  near `1e-8` after a full figure-eight period is the integrator doing its job.
- **No collisions or relativity.** Bodies pass through one another and gravity is Newtonian. This
  is a sandbox for orbital intuition, not a mission-design tool.

## 📦 What's Inside

```text
orrery/
├── .aikit/                   <- this project's memory: record, ledger, decisions
├── .github/
│   └── workflows/
│       └── ci.yml            <- Python 3.10/3.14 matrix on Linux, Windows and macOS
├── .gitattributes            <- launcher line-ending policy
├── .gitignore
├── LICENSE                   <- AGPL-3.0-or-later
├── README.md
├── examples/
│   └── custom-two-body.json  <- editable example scenario
├── pyproject.toml            <- package metadata and the `orrery` console script
├── run.cmd                   <- one-click Windows launcher (solar by default)
├── run.command               <- one-click macOS launcher, delegates to run.sh
├── run.sh                    <- one-click Linux/POSIX launcher
├── orrery/
│   ├── __init__.py
│   ├── __main__.py           <- `python -m orrery`
│   ├── cli.py                <- argparse surface, animation, CSV export
│   ├── custom.py             <- strict JSON scenario loader
│   ├── py.typed              <- inline type information for library users
│   ├── render.py             <- viewport, ANSI painting, pure frame rendering
│   ├── scenarios.py          <- the five worlds and their units
│   ├── sim.py                <- vectors, bodies, leapfrog, diagnostics
│   └── trails.py             <- bounded, sampled position history
└── tests/
    ├── __init__.py
    ├── golden/               <- deterministic ASCII frames per scenario
    ├── test_cli.py
    ├── test_custom.py
    ├── test_golden.py
    ├── test_invariants.py
    ├── test_launchers.py
    ├── test_render.py
    ├── test_scenarios.py
    ├── test_sim.py
    └── test_trails.py
```

## 🧪 Verification

The suite is 90 tests and completes in about 1.3 seconds:

```bash
python -m unittest discover -s tests -t .
```

It covers pairwise gravity, circular-orbit energy and radius, momentum and angular-momentum
conservation, binary and Lagrange-point stability, the full figure-eight period, orbital-element
recovery for Earth, parabolic orbits, Trojan geometry, viewport aspect correction and
narrow-terminal fitting and custom aspect ratios, golden frames for every scenario,
custom-scenario validation and failure paths, ASCII, colour and Braille rendering, trail bounds,
dense sampling and subcell line interpolation, every CLI command, CSV/JSON shape and final-state
sampling, the launcher files, and the `Error/Why/Fix` failure paths.

CI runs the suite on Python 3.10 and 3.14 across Ubuntu, Windows and macOS, installs the
package, runs Ruff, builds the wheel and sdist, and smoke-tests all three launchers. For local
development:

```bash
python -m pip install -e ".[dev]"
ruff check .
```

## 🧱 Library API

The simulation is importable without the terminal. `World` holds immutable body snapshots,
`advance`/`advance_to` mutate the world clock, and the diagnostics are plain methods:

```python
from orrery.scenarios import get_scenario
from orrery.sim import World

scenario = get_scenario("solar")
world = World(scenario.bodies, scenario.g)
initial_energy = world.total_energy()
world.advance_to(30.0, scenario.dt)

print(world.bodies[3].pos.norm())              # Earth's distance in AU
print(world.energy_drift(initial_energy))      # dimensionless drift
print(world.angular_momentum())
```

Custom files use `orrery.custom.load_scenario_file` and return the same `Scenario` type. Inline
types ship with the package (`py.typed`).

## 📚 Design Notes

The integrator, unit policy, rendering boundary, viewport fitting and work caps are recorded in
`.aikit/decisions.md` (ADR-001 through ADR-006).

## 📄 License

Orrery is licensed under the GNU Affero General Public License v3.0 or later. See `LICENSE`.
