# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: Scenario-native units and kick-drift-kick leapfrog
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: Solar-system scenarios need real AU/day/solar-mass units, while the published
  figure-eight choreography is defined with G = 1 and unit masses. A visual sandbox also needs
  orbital energy to stay bounded over many frames without adaptive-step complexity.
- **Decision**: Every `Scenario` carries its own `g`, time step, view span and display units.
  `World.step` uses kick-drift-kick leapfrog: half velocity kick, full position drift, second
  half kick from the new forces. The time step is fixed per scenario.
- **Consequences**: Energy drift is bounded and measurable (the footer reports `ΔE/E`), and the
  figure-eight uses its exact published numbers. Close encounters and eccentric orbits must be
  given a small enough `dt` by the scenario author; there is no adaptive refinement.

### ADR-002: A pure renderer with a CLI-owned terminal loop
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: The frame builder must be testable without a TTY, yet the finished tool needs
  colour, cursor control and a graceful fallback for terminals without Unicode or ANSI.
- **Decision**: `render_scene` is a pure function returning exactly `height` lines of `width`
  visible cells. `Viewport` corrects for the roughly 2:1 height/width ratio of a character cell.
  `cli.py` owns colour detection, the Windows VT-mode opt-in, cursor hiding, clearing and the
  ASCII fallback; trailing `--ascii` and `--no-color` flags make output deterministic.
- **Consequences**: Frame tests compare plain strings, and snapshots and CSV export reuse the
  same simulation. The viewport is fixed for a run, so resizing the terminal mid-animation only
  takes effect on the next invocation.

### ADR-003: Fit the viewport locally and cap unbounded CLI work
- **Date**: 2026-10-23
- **Status**: Accepted
- **Context**: A fixed vertical span clipped wide scenarios on narrow terminals. Finite but
  extreme `--at`, `--fps` and export ratios could also run for hours or overflow a float.
- **Decision**: Each `Scenario` declares a half-extent. The CLI expands the vertical span to fit
  that extent at the 2:1 cell aspect, and wraps the title, statistics and legend to the viewport
  width. Snapshots above 2,000,000 steps require `--force`; exports are capped at 200,000 samples
  and always include `--until`; frame rates are limited to 0.1–240 fps. Windows VT mode is
  enabled before colour or cursor control and disabled on failure.
- **Consequences**: Narrow output stays within its width and no body is clipped, at the cost of a
  smaller drawing on very narrow terminals. Legitimate extreme runs remain available through
  `--force`, but accidental ones fail fast.

### ADR-004: Braille subcell trails on Unicode terminals
- **Date**: 2026-10-23
- **Status**: Accepted
- **Context**: One trail mark per terminal cell leaves small circular orbits visibly polygonal.
  Connecting samples at cell resolution removes gaps but cannot add resolution.
- **Decision**: When Unicode is available, render trails into a 2×4 Braille dot grid (eight subcells
  per cell), connect consecutive projected samples at subcell resolution, and overlay body symbols
  on top. `--no-braille` selects one-cell line marks; `--ascii` selects plain ASCII lines and is
  used by golden-frame tests.
- **Consequences**: Orbits become noticeably smoother at the same terminal size. The default output
  depends on a Braille-capable font; `--no-braille` and `--ascii` are explicit escape hatches.
### ADR-005: Non-blocking interactive keyboard control and live telemetry HUD
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Users running simulations in an interactive terminal could not pause, tweak speed,
  clear trails, reset or inspect real-time numerical conservation trends without stopping the
  process with Ctrl-C.
- **Decision**: Introduce a zero-dependency, cross-platform KeyboardReader using msvcrt on
  Windows and 	ermios/select on POSIX, active only when stdin.isatty() is True. Support Space
  (pause/resume), +/- (speed), c (clear trails), 
 (reset world), 	 (toggle telemetry
  sparkline trend), and q (clean quit). Add --telemetry to display a trend sparkline and
  angular-momentum drift. Fall back to ASCII sparkline glyphs when terminal encoding cannot encode
  Unicode blocks.
- **Consequences**: Orrery becomes an interactive, responsive terminal toy while preserving pure
  scripted and piped automation parity.

### ADR-006: Body tracking camera, 1PN relativistic precession, coalescence, and scenario switching
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Studying orbits from rotating non-inertial frames (e.g. geocentric epicycles) required
  centering the camera on moving bodies. Accretion physics required inelastic mergers, and Mercury's
  perihelion shift required general relativistic post-Newtonian corrections.
- **Decision**: Extend `Viewport` with dynamic center offset and span factor. In `_cmd_run`, add body
  tracking (`f`, digits `1-9`), WASD/arrow panning, zoom (`[`/`]`), reset (`0`), and scenario switching
  (`n`/`p`). Add pairwise 1PN post-Newtonian acceleration when `c` is specified (`--relativity`, `--c-light`),
  producing Einstein's 43 arcseconds/century perihelion shift. Implement inelastic coalescence
  (`--merge`, `--merge-radius`) strictly conserving linear momentum, mass, and center of mass,
  with automatic trail recorder buffer synchronization.
- **Consequences**: Orrery functions as a multi-reference-frame observatory with relativistic and accretion
  capabilities while remaining completely zero-dependency and backward-compatible.

### ADR-007: Physics export parity, single-frame stepping, and multi-step collision resolution
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Exporting trajectories to CSV/JSON previously omitted 1PN relativistic precession and
  inelastic mergers. Long integration intervals in advance_to could miss collisions occurring between
  coarse sample times. When paused, users could not advance a single frame for precise inspection,
  nor view the effective FPS, and arrow keys on Windows/POSIX terminals were not mapped to camera panning.
- **Decision**: Add physics options (--relativity, --c-light, --merge, --merge-radius) to the export
  command and write simulation parameters into export metadata. Extend World.advance, World.advance_to,
  and TrailRecorder.advance_to with an optional merge_radius parameter resolving collisions at every
  sub-step. Add single-frame step (. or >) during interactive pause, display live fps in HUD stats,
  and parse Windows two-byte scan codes and POSIX ANSI sequences for arrow key camera panning.
- **Consequences**: Scientific data exports match visual simulation physics identically. Paused simulations
  can be inspected frame-by-frame with zero overshoot. Backward compatibility is fully preserved.

### ADR-008: Circular orbit dot styles and interactive aspect ratio calibration
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Orbit trails were previously rendered either as continuous Braille line strokes or as
  tiny middle dots (`·`) / periods (`.`), which did not present round, circular points. Furthermore,
  the fixed terminal cell aspect ratio of 2.0 vertically stretched circular orbits (such as Earth or
  Lagrange) into tall ellipses on modern terminal fonts with standard 1.2–1.4 line heights.
- **Decision**: Introduce selectable orbit dot styles (`circle` for `○`/`o`, `bullet` for `•`,
  `ring` for `◦`, `disc` for `●`, `dot` for `·`, and `ascii` for `.`), with automatic encoding
  fallback across UTF-8, CP1254, and ASCII. Add interactive key `b` in `run` mode to cycle dot styles
  live, and add `{` / `}` to interactively calibrate the cell aspect ratio in increments
  of 0.05, allowing users to make orbits almost exact geometric circles on any monitor and font.
- **Consequences**: Users can dial in perfect circular orbit geometry and select circular dot markers
  with immediate HUD feedback (`asp=X.XX`, `dot=...`). Backward compatibility is fully preserved.


### ADR-009: Elastic bounce collisions, Coulomb electrostatics, atomic scenarios, and relativistic energy metrics
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Inelastic coalescence was previously the only collision mode, destroying bodies on impact.
  Users requested elastic bounce dynamics, atomic and electrostatic simulations, relativistic energy
  decomposition, and atomic scenarios.
- **Decision**: Add pairwise elastic collisions with restitution (`--bounce`, `--bounce-radius`,
  `--restitution`), conserving linear momentum and barycentre through mass-weighted position push-out
  and impulse exchange. Add Coulomb electrostatic force alongside gravity ($F_e = k_e q_1 q_2 / r^2$),
  electrostatic potential energy, relativistic total energy $E = \sum \gamma m c^2$, Schwarzschild radius
  $r_s = 2GM/c^2$, and live telemetry HUD decomposition ($K$, $U$, Virial metric $2K+U$). Implement
  built-in atomic and relativistic scenarios: `rutherford` (alpha particle scattering against gold nucleus),
  `bohr` (semi-classical planetary atom), and `black-hole` (relativistic singularity with rosette precession).
- **Consequences**: Orrery models gravitational, relativistic, and subatomic electrostatic physics
  seamlessly in a single zero-dependency engine with full CLI and export parity.


### ADR-010: Simulation time settings and zero-dependency Web-based UI
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Users requested comprehensive temporal control (configurable dt, time warp scale,
  reverse integration direction) and a companion Web-based UI while preserving the terminal UI completely.
- **Decision**: Extend kick-drift-kick leapfrog with negative dt support (time-reversible symplectic
  symmetry), allowing backward integration to retrace orbits identically. Add CLI time options
  (`--dt`, `--time-scale` / `--warp`, `--reverse`) and interactive terminal keybindings (`x` for faster
  warp, `z` for slower warp, `v` to reverse direction). Implement a zero-dependency HTTP server in
  `orrery/web.py` using Python's standard `http.server`, serving an embedded HTML5 Canvas 2D orbital
  studio (`python -m orrery web`) with real-time physics, camera panning/zooming, body tracking,
  time controls, live telemetry, and custom scenario JSON drag-and-drop loading.
- **Consequences**: Users can explore simulations interactively both in the terminal and in any modern
  web browser without installing any external packages or npm dependencies.
