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
