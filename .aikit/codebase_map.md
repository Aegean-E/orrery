# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `18`
- **Total Classes**: `26`
- **Total Top-Level Functions**: `63`
- **Total Class Methods**: `149`
- **Total Source Lines**: `3574`

---

## 📦 Modules & Exported Symbols

### [`orrery/__init__.py`](orrery/__init__.py)
> *Orrery: a zero-dependency N-body sandbox for the terminal.*

**Size**: `3` lines (`88` bytes)

---

### [`orrery/__main__.py`](orrery/__main__.py)
> *``python -m orrery`` entry point.*

**Size**: `10` lines (`160` bytes)

---

### [`orrery/cli.py`](orrery/cli.py)
> *Command-line surface for Orrery.*

**Size**: `1124` lines (`47242` bytes)

**Classes:**
- `class CliError` - *A failure with a cause and a concrete next action.*
  - Method `.__init__(message, why, fix, code)`
- `class TriadParser` - *Argparse that turns a usage error into the Error/Why/Fix triad.*
  - Method `.error(message)` - *Print usage and the Error/Why/Fix triad, then exit 2.*
- `class KeyboardReader` - *Non-blocking single-key reader with automatic terminal restore.*
  - Method `.__init__(enabled)`
  - Method `.__enter__()`
  - Method `.__exit__(*args)`
  - Method `.poll()` - *Return the next pressed character if one is available, or None.*

**Functions:**
- `def _scenario(name)`
- `def _cmd_validate(args)`
- `def _color_enabled(args)`
- `def _unicode_enabled(args)`
- `def _scene_size(args)`
- `def _trail_limit(args, scenario)`
- `def _fit_span(scenario, width, height, aspect, margin)` - *Pick a vertical span large enough for the scenario's horizontal extent.*
- `def _viewport(scenario, width, height, aspect, center, span_factor)`
- `def _aspect(args)`
- `def _truncate(text, width)`
- `def _pack_tokens(tokens, width, separator)`
- `def _fmt_mass(value)`
- `def _orbit_text(orbit)`
- `def _primary_index(world)`
- `def _dominant_primary(world)`
- `def _body_payload(scenario, body, primary, index, primary_index, dominant)`
- `def _info_payload(scenario, world, primary_index)`
- `def _catalog_payload(scenario)`
- `def _cmd_list(args)`
- `def _cmd_info(args)`
- `def _sparkline(values, width, *, ascii_only)` - *Render a compact sparkline trend string for a series of numeric samples.*
- `def _compose_frame(world, scenario, viewport, recorder, initial_energy, *, ascii_only, color, braille, telemetry, energy_history, initial_momentum, controls_hint, paused, camera_label, fps, dot_char)`
- `def _simulate(scenario, target, trail_limit, *, relativity, c_override, merge_radius)`
- `def _cmd_snapshot(args)`
- `def _enable_windows_ansi()` - *Enable VT processing when possible; return whether ANSI control is safe.*
- `def _cmd_run(args)`
- `def _cmd_export(args)`
- `def _add_view_options(parser, *, trails)`
- `def _add_physics_options(parser)`
- `def build_parser()`
- `def main(argv)`

---

### [`orrery/custom.py`](orrery/custom.py)
> *Load user-authored scenarios from JSON files.*

**Size**: `226` lines (`9415` bytes)

**Classes:**
- `class ScenarioFileError` - *A custom scenario could not be loaded; the CLI turns this into Error/Why/Fix.*
  - Method `.__init__(message, why, fix)`

**Functions:**
- `def _fail(message, why, fix)`
- `def _number(value, field, *, positive)`
- `def _integer(value, field, *, minimum, maximum)`
- `def _string(value, field, *, maximum)`
- `def _vector(value, field)`
- `def _body(raw, index)`
- `def _units(raw)`
- `def _reject_constant(value)`
- `def load_scenario_file(path_like)` - *Read one custom scenario, validating size, shape, values and the resulting Scenario.*

---

### [`orrery/render.py`](orrery/render.py)
> *Turn a world into a rectangular block of terminal cells.*

**Size**: `271` lines (`9310` bytes)

**Classes:**
- `class Viewport` - *A rectangular map from world units to terminal cells.*
  - Method `.__post_init__()`
  - Property `.rows_per_unit`
  - Property `.cols_per_unit`
  - Method `.cell(point)` - *Return ``(column, row)`` for a world point, or ``None`` when off-screen.*
  - Method `.subcell(point)` - *Return ``(subcolumn, subrow)`` in the 2x4 Braille grid, or ``None``.*

**Functions:**
- `def resolve_dot_char(style, *, ascii_only, encoding)` - *Resolve a dot style name or single character to a printable glyph.*
- `def _line_cells(start, end)` - *Bresenham line in cell coordinates, including both endpoints.*
- `def _trail_color(color_key)`
- `def _paint_grid(grid, color)`
- `def _set_braille(bits, colors, subcell, color_key)`
- `def _render_braille(world, trails, viewport, color)`
- `def render_scene(world, trails, viewport, *, ascii_only, color, braille, dot_char)` - *Draw trails first, then bodies, on a fresh grid of exactly ``viewport.height`` lines.*
- `def strip_ansi(text)` - *Remove ANSI SGR sequences, for callers that need the visible width.*

---

### [`orrery/scenarios.py`](orrery/scenarios.py)
> *The built-in worlds.*

**Size**: `403` lines (`14243` bytes)

**Classes:**
- `class Scenario` - *A named initial state plus the knobs the player needs to present it.*
  - Method `.__post_init__()`

**Functions:**
- `def _rotate(vector, angle)`
- `def _center_and_zero_momentum(bodies)` - *Move the origin to the barycentre and remove any net drift.*
- `def _planet(name, mass, semi_major, eccentricity, angle_degrees, symbol, color)` - *A planet released at perihelion, with its orbit rotated around the Sun.*
- `def _solar()`
- `def _figure_eight()` - *Chenciner-Montgomery three-body choreography in natural units.*
- `def _binary()`
- `def _trojans()`
- `def _pythagorean()` - *The classic 3-4-5 three-body problem: rest, a close encounter, then ejection.*
- `def _lagrange()` - *Lagrange's 1772 equilateral pinwheel: three equal masses in a rigid rotating triangle.*
- `def scenario_keys()`
- `def get_scenario(name)` - *Resolve a key or a forgiving alias; raise KeyError when nothing matches.*

---

### [`orrery/sim.py`](orrery/sim.py)
> *Gravity, bodies and a symplectic leapfrog integrator.*

**Size**: `307` lines (`11778` bytes)

**Classes:**
- `class Vec2` - *A point or vector in the plane.*
  - Method `.__add__(other)`
  - Method `.__sub__(other)`
  - Method `.__mul__(scalar)`
  - Method `.__rmul__(scalar)`
  - Method `.__truediv__(scalar)`
  - Method `.__neg__()`
  - Method `.dot(other)`
  - Method `.norm_sq()`
  - Method `.norm()`
  - Method `.distance_to(other)`
- `class Body` - *An immutable snapshot of one gravitating body.*
- `class Orbit` - *Osculating elements of one body around a chosen primary, in world units.*
- `class World` - *A mutable simulation clock over a tuple of immutable bodies.*
  - Method `.__post_init__()`
  - Method `.accelerations()`
  - Method `.step(dt)` - *Advance one kick-drift-kick leapfrog step of length ``dt``.*
  - Method `.resolve_collisions(merge_radius)` - *Inelastically merge bodies closer than merge_radius, conserving momentum.*
  - Method `.advance(dt, steps, merge_radius)`
  - Method `.advance_to(target, dt, merge_radius)` - *Integrate to ``target``, ending with a shorter step when needed.*
  - Property `.total_mass`
  - Method `.momentum()`
  - Method `.center_of_mass()`
  - Method `.kinetic_energy()`
  - Method `.potential_energy()`
  - Method `.total_energy()`
  - Method `.angular_momentum()`
  - Method `.energy_drift(initial_energy)`

**Functions:**
- `def _accelerations(bodies, g, c)` - *Pairwise Newtonian acceleration on every body, with optional 1PN general relativity.*
- `def orbital_elements(primary, body, g)` - *Osculating semi-major axis, eccentricity and period of ``body`` around ``primary``.*

---

### [`orrery/trails.py`](orrery/trails.py)
> *Bounded, sampled position history for drawing orbit trails.*

**Size**: `88` lines (`3498` bytes)

**Classes:**
- `class TrailRecorder` - *Keep one bounded deque of past positions per body, sampled every N steps.*
  - Method `.__init__(world, limit)`
  - Property `.trails`
  - Method `.sync(world)` - *Synchronize trail history buffers when the world body count changes.*
  - Method `.record(world)`
  - Method `.clear(world)` - *Clear historical trail samples, seeding with current positions if world is given.*
  - Method `.advance(world, dt, steps, every, merge_radius)`
  - Method `.advance_to(world, target, dt, every, merge_radius)`

---

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

---

### [`tests/test_cli.py`](tests/test_cli.py)
**Size**: `402` lines (`18623` bytes)

**Classes:**
- `class ListAndInfoTests`
  - Method `.test_list_shows_every_scenario()`
  - Method `.test_list_json_is_a_machine_readable_catalogue()`
  - Method `.test_info_prints_a_table()`
  - Method `.test_info_json_contains_orbital_elements()`
  - Method `.test_equal_mass_system_does_not_invent_orbital_elements()`
  - Method `.test_usage_error_has_the_same_triad()`
- `class SnapshotTests`
  - Method `.test_snapshot_at_zero_is_ascii_clean()`
  - Method `.test_snapshot_advances_time()`
  - Method `.test_negative_time_is_refused()`
  - Method `.test_narrow_snapshot_never_exceeds_width()`
  - Method `.test_braille_is_default_and_can_be_disabled()`
  - Method `.test_aspect_can_be_overridden_and_is_validated()`
  - Method `.test_all_scenarios_are_visible_at_minimum_size()`
  - Method `.test_snapshot_step_budget_can_be_overridden()`
  - Method `.test_bad_width_is_refused()`
  - Method `.test_unknown_scenario_is_a_friendly_error()`
- `class RunTests`
  - Method `.test_one_frame_renders_the_first_step()`
  - Method `.test_frame_rate_range_is_enforced()`
  - Method `.test_piped_run_defaults_to_one_frame()`
- `class ExportTests`
  - Method `.test_export_writes_sampled_csv_without_leftovers()`
  - Method `.test_missing_export_folder_is_refused()`
  - Method `.test_overflowing_export_window_is_a_friendly_error()`
  - Method `.test_export_json_contains_metadata_and_samples()`
  - Method `.test_export_always_includes_the_final_state()`
- `class InteractiveAndTelemetryTests`
  - Method `.test_sparkline_rendering()`
  - Method `.test_keyboard_reader_disabled()`
  - Method `.test_snapshot_telemetry_output()`
  - Method `.test_run_telemetry_and_no_controls()`
  - Method `.test_run_interactive_keyboard_events()`
  - Method `.test_camera_pan_zoom_and_tracking()`
  - Method `.test_scenario_switching_keys()`
  - Method `.test_cli_relativity_and_merge_flags()`
  - Method `.test_run_paused_single_step()`
  - Method `.test_export_relativity_and_merge()`
  - Method `.test_keyboard_arrow_mapping()`
  - Method `.test_compose_frame_fps_and_step_hint()`
  - Method `.test_cli_dot_option_snapshot()`
  - Method `.test_run_interactive_aspect_and_dot_cycling()`

**Functions:**
- `def run_cli(*argv)`

---

### [`tests/test_custom.py`](tests/test_custom.py)
**Size**: `141` lines (`5171` bytes)

**Classes:**
- `class CustomScenarioTests`
  - Method `.setUp()`
  - Method `._write(payload)`
  - Method `._run_validate(path)`
  - Method `.test_example_loads_with_units_and_defaults()`
  - Method `.test_validate_and_snapshot_accept_a_json_path()`
  - Method `.test_optional_fields_have_documented_defaults()`
  - Method `.test_missing_file_is_a_friendly_error()`
  - Method `.test_invalid_json_is_reported()`
  - Method `.test_non_finite_numbers_are_rejected()`
  - Method `.test_duplicate_symbols_are_rejected()`
  - Method `.test_body_outside_extent_is_rejected()`
  - Method `.test_control_text_and_unknown_colours_are_rejected()`
  - Method `.test_body_limit_is_enforced()`

**Functions:**
- `def run_cli(*argv)`

---

### [`tests/test_golden.py`](tests/test_golden.py)
**Size**: `28` lines (`881` bytes)

**Classes:**
- `class GoldenFrameTests`
  - Method `.test_frames_are_stable()`

---

### [`tests/test_invariants.py`](tests/test_invariants.py)
**Size**: `70` lines (`3311` bytes)

**Classes:**
- `class InvariantTests`
  - Method `.test_angular_momentum_is_conserved_scenario_wide()`
  - Method `.test_binary_remains_bound_for_ninety_days()`
  - Method `.test_trojans_hold_their_lagrange_angles_for_ten_years()`
  - Method `.test_lagrange_pinwheel_returns_after_one_period()`

---

### [`tests/test_launchers.py`](tests/test_launchers.py)
> *One-click launch files: present, CRLF-safe on Windows and Python 3.10-aware.*

**Size**: `45` lines (`1528` bytes)

**Classes:**
- `class LauncherTest`
  - Method `.test_launchers_exist()`
  - Method `.test_macos_command_launcher_delegates_to_the_shell_launcher()`
  - Method `.test_batch_file_has_crlf_line_endings()`
  - Method `.test_launchers_check_python_310_and_start_the_module()`
  - Method `.test_batch_checks_each_python_candidate()`
  - Method `.test_batch_failure_stays_visible()`

---

### [`tests/test_render.py`](tests/test_render.py)
**Size**: `122` lines (`5680` bytes)

**Classes:**
- `class ViewportTests`
  - Method `.test_centre_and_edges_map_to_expected_cells()`
  - Method `.test_horizontal_cells_are_twice_as_dense()`
  - Method `.test_custom_aspect_changes_column_density()`
  - Method `.test_off_screen_points_are_none()`
  - Method `.test_invalid_dimensions_are_rejected()`
- `class RenderSceneTests`
  - Method `.setUp()`
  - Method `.test_lines_have_the_exact_viewport_size()`
  - Method `.test_bodies_overwrite_trails()`
  - Method `.test_ascii_mode_is_plain_ascii()`
  - Method `.test_colour_adds_ansi_but_keeps_the_same_cells()`
  - Method `.test_trail_samples_are_connected_with_line_cells()`
  - Method `.test_braille_trails_use_subcell_glyphs()`
  - Method `.test_trail_count_must_match_bodies()`
  - Method `.test_render_scene_with_custom_dot_char()`
  - Method `.test_resolve_dot_char_styles_and_fallbacks()`

---

### [`tests/test_scenarios.py`](tests/test_scenarios.py)
**Size**: `93` lines (`4154` bytes)

**Classes:**
- `class ScenarioTests`
  - Method `.test_exactly_six_distinct_scenarios()`
  - Method `.test_lagrange_pinwheel_is_equilateral()`
  - Method `.test_every_scenario_is_valid_and_centred()`
  - Method `.test_solar_earth_has_its_real_orbit()`
  - Method `.test_trojan_asteroids_straddle_jupiter()`
  - Method `.test_aliases_resolve()`
  - Method `.test_extents_cover_the_initial_bodies()`
  - Method `.test_unknown_key_raises()`

---

### [`tests/test_sim.py`](tests/test_sim.py)
**Size**: `168` lines (`7993` bytes)

**Classes:**
- `class Vec2Tests`
  - Method `.test_arithmetic()`
- `class WorldTests`
  - Method `.test_pairwise_acceleration_points_towards_the_other_body()`
  - Method `.test_coincident_bodies_do_not_divide_by_zero()`
  - Method `.test_circular_orbit_keeps_its_radius_and_energy()`
  - Method `.test_momentum_and_barycentre_are_conserved()`
  - Method `.test_figure_eight_returns_after_one_period()`
  - Method `.test_parabolic_orbit_has_no_finite_elements()`
  - Method `.test_orbital_elements_describe_a_unit_circle()`
  - Method `.test_relativity_post_newtonian_precession()`
  - Method `.test_resolve_collisions_inelastic_merger()`
  - Method `.test_advance_and_advance_to_with_merge_radius()`
  - Method `.test_invalid_inputs_are_rejected()`

---

### [`tests/test_trails.py`](tests/test_trails.py)
**Size**: `73` lines (`2851` bytes)

**Classes:**
- `class TrailRecorderTests`
  - Method `._world()`
  - Method `.test_limit_keeps_the_most_recent_positions()`
  - Method `.test_sampling_every_other_step()`
  - Method `.test_advance_to_uses_a_short_final_step()`
  - Method `.test_advance_to_resolves_collisions()`
  - Method `.test_zero_limit_disables_history()`
  - Method `.test_clear_resets_trail_history()`
  - Method `.test_invalid_arguments_are_rejected()`

---
