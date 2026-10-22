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
