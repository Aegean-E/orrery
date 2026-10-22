# orrery

An N-body gravitational sandbox that runs in your terminal. Four carefully chosen worlds, a
symplectic integrator, live energy diagnostics, orbit trails, CSV export, and no dependencies
outside the Python standard library.

```text
ORRERY | Figure-Eight Choreography
--------------------------------------------------------------------------




              ........                              ........
         ......      ......                    ......      ......
       ...                ....              ....                ...
      .B                     ....        ....                     ..
     ..                         ...    .C.                         ..
     .                            ......                            .
     .                            ......                            .
     ..                         ...    ...                         ..
      ..                     ....        ....                     ..
       ...                ....              ....                ...
         ......      ......                    ......      ....A.
              ........                              ........




--------------------------------------------------------------------------
t = 6.20 t    bodies = 3    dE/E = -4.96e-08
A Alpha   B Beta   C Gamma
```

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10 or newer (standard library only; no third-party packages)
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

Press `Ctrl-C` to leave an animation. If your terminal cannot display Unicode, Orrery falls back
to ASCII borders and trail dots automatically; pass `--ascii` to force it.

### 🚀 One-Click Launch

- **Windows**: double-click `run.cmd` to open the solar-system animation. It keeps the window
  open when the run ends.
- **macOS / Linux**: run `./run.sh` (or `sh run.sh`) for the same animation.
- To start a different world, pass its key and any normal `run` options:
  ```text
  run.cmd figure-eight
  run.cmd trojans --fps 30
  ./run.sh binary --frames 120
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)

| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status orrery` |
| Phase 4: every gate | `python aikit.py check orrery` |
| Repair memory and map, then check | `python aikit.py fix orrery` |
| Resume an interrupted task | `python aikit.py resume orrery` |

## 🌍 The Four Worlds

| Key | Bodies | What it shows |
|---|---|---|
| `solar` | Sun, Mercury, Venus, Earth, Mars | Real eccentric orbits and Kepler's third law. |
| `figure-eight` | Three equal masses | The Chenciner-Montgomery choreography: all three chase one another around a single curve and return after ~6.33 time units. |
| `binary` | Two half-solar stars, one planet | A Jupiter-mass planet on a circumbinary orbit while its two suns wobble around their barycentre. |
| `trojans` | Sun, Jupiter, Achilles, Patroclus | The stable L4 and L5 Lagrange points, 60° ahead of and behind Jupiter. |

Aliases are forgiving: `inner`, `solar-system`, `figure8`, `circumbinary`, `trojan` and a few
more resolve to the right scenario.

## 🕹️ Commands

```text
python -m orrery list
python -m orrery info KEY [--json]
python -m orrery snapshot KEY [--at TIME] [--width N] [--height N] [--ascii] [--no-color] [--trail N | --no-trail]
python -m orrery run KEY [--frames N] [--fps N] [--width N] [--height N] [--ascii] [--no-color] [--trail N | --no-trail]
python -m orrery export KEY --out FILE [--until TIME] [--every TIME]
```

- `snapshot` integrates to `--at` and prints one frame. With no `--at` you get the initial state.
- `run` loops on a terminal; `--frames 0` loops forever, and a piped run defaults to one still.
- `info` prints initial distances, osculating orbital elements and energy. `--json` is stable and
  machine-readable. If no single body dominates (the figure-eight and binary worlds), the
  two-body orbit columns are deliberately blank rather than misleading.
- `export` writes `time,body,x,y,vx,vy,speed` rows in the scenario's native units. It samples a
  temporary file and atomically replaces the target when complete.

Every failure follows the same triad:

```text
Error: unknown scenario 'nibiru'.
Why: a scenario key selects one built-in initial state.
Fix: choose one of: solar, figure-eight, binary, trojans.
```

Exit codes are `0` success, `1` runtime failure, `2` bad usage.

## 🔭 How It Works

- **Units belong to the scenario.** Solar-system worlds use AU, days and solar masses, so
  `G = 4π² / (365.2568983)² ≈ 2.9591e-4 AU³ / (M☉·d²)`. The figure-eight uses its published
  natural units (`G = 1`, three unit masses) so the initial conditions are exact.
- **Kick-drift-kick leapfrog.** Each step updates velocities by half a kick, drifts positions by
  the full step, then applies the second half-kick using the new forces. The method is
  time-reversible and keeps orbital energy bounded instead of letting it drift secularly.
- **Barycentric initial states.** Every scenario starts with zero net momentum and its centre of
  mass at the origin, so the view does not wander off screen.
- **Trails are bounded.** A `TrailRecorder` keeps a deque of past positions per body and samples
  every few steps. Old points fall off the end; memory stays flat during a long run.
- **The viewport knows about character cells.** A terminal cell is roughly twice as tall as it is
  wide, so the viewport uses twice as many columns per world unit as rows. Circles stay round.
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
├── .gitattributes            <- launcher line-ending policy
├── .gitignore
├── README.md
├── pyproject.toml            <- package metadata and the `orrery` console script
├── run.cmd                   <- one-click Windows launcher (solar by default)
├── run.sh                    <- one-click macOS/Linux launcher
├── orrery/
│   ├── __init__.py
│   ├── __main__.py           <- `python -m orrery`
│   ├── cli.py                <- argparse surface, animation, CSV export
│   ├── render.py             <- viewport, ANSI painting, pure frame rendering
│   ├── scenarios.py          <- the four worlds and their units
│   ├── sim.py                <- vectors, bodies, leapfrog, diagnostics
│   └── trails.py             <- bounded, sampled position history
└── tests/
    ├── __init__.py
    ├── test_cli.py
    ├── test_launchers.py
    ├── test_render.py
    ├── test_scenarios.py
    ├── test_sim.py
    └── test_trails.py
```

## 🧪 Verification

The suite is 45 tests and completes in about 0.2 seconds:

```bash
python -m unittest discover -s tests -t .
```

It covers pairwise gravity, circular-orbit energy and radius, momentum and barycentre
conservation over 500 steps, the full figure-eight period, orbital-element recovery for Earth,
Trojan geometry, viewport aspect correction, ASCII and colour rendering, trail bounds and
sampling, every CLI command, CSV shape, and the `Error/Why/Fix` failure paths.

## 📚 Design Notes

The integrator, unit policy and rendering boundary are recorded in `.aikit/decisions.md`
(ADR-001 and ADR-002).
