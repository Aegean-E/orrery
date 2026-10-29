# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `20`
- **Total Classes**: `31`
- **Total Top-Level Functions**: `76`
- **Total Class Methods**: `214`
- **Total Source Lines**: `6122`

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

**Size**: `1373` lines (`59422` bytes)

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
- `def _compose_frame(world, scenario, viewport, recorder, initial_energy, *, ascii_only, color, braille, telemetry, energy_history, initial_momentum, controls_hint, paused, camera_label, fps, dot_char, time_warp)`
- `def _validate_physics_args(args)`
- `def _simulate(scenario, target, trail_limit, *, relativity, c_override, k_coulomb_override, merge_radius, bounce_radius, restitution, dt_override)`
- `def _cmd_snapshot(args)`
- `def _enable_windows_ansi()` - *Enable VT processing when possible; return whether ANSI control is safe.*
- `def _cmd_run(args)`
- `def _cmd_export(args)`
- `def _add_view_options(parser, *, trails)`
- `def _add_physics_options(parser)`
- `def _add_time_options(parser, *, warp)`
- `def _cmd_web(args)`
- `def build_parser()`
- `def main(argv)`

---

### [`orrery/custom.py`](orrery/custom.py)
> *Load user-authored scenarios from JSON files.*

**Size**: `231` lines (`9640` bytes)

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

**Size**: `533` lines (`18771` bytes)

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
- `def _rutherford()` - *Rutherford alpha particle scattering against a heavy gold nucleus (+79e).*
- `def _bohr()` - *Semi-classical Bohr atom: electrons in circular orbits around a central proton.*
- `def _black_hole()` - *Relativistic black hole with high-velocity probes exhibiting 1PN orbital precession.*
- `def scenario_keys()`
- `def get_scenario(name)` - *Resolve a key or a forgiving alias; raise KeyError when nothing matches.*

---

### [`orrery/sim.py`](orrery/sim.py)
> *Gravity, bodies and a symplectic leapfrog integrator.*

**Size**: `426` lines (`17511` bytes)

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
- `class Body` - *An immutable snapshot of one gravitating/charged body.*
- `class Orbit` - *Osculating elements of one body around a chosen primary, in world units.*
- `class World` - *A mutable simulation clock over a tuple of immutable bodies.*
  - Method `.__post_init__()`
  - Method `.accelerations()`
  - Method `.step(dt)` - *Advance one kick-drift-kick leapfrog step of length ``dt``.*
  - Method `.resolve_collisions(merge_radius)` - *Inelastically merge bodies closer than merge_radius, conserving momentum.*
  - Method `.resolve_elastic_collisions(bounce_radius, restitution)` - *Elastically bounce bodies closer than bounce_radius, conserving momentum.*
  - Method `.advance(dt, steps, merge_radius, bounce_radius, restitution)`
  - Method `.advance_to(target, dt, merge_radius, bounce_radius, restitution)` - *Integrate to ``target``, ending with a shorter step when needed.*
  - Property `.total_mass`
  - Method `.momentum()`
  - Method `.center_of_mass()`
  - Method `.kinetic_energy()`
  - Method `.potential_energy()`
  - Method `.electrostatic_energy()`
  - Method `.relativistic_energy()` - *Total relativistic energy E = sum(gamma * m * c^2), or None if c is not set.*
  - Method `.schwarzschild_radius()` - *Schwarzschild radius r_s = 2 * G * M / c^2 of the system's total mass.*
  - Method `.total_energy()`
  - Method `.angular_momentum()`
  - Method `.energy_drift(initial_energy)`

**Functions:**
- `def _accelerations(bodies, g, c, k_e)` - *Pairwise Newtonian/Coulomb acceleration on every body, with optional 1PN general relativity.*
- `def orbital_elements(primary, body, g, k_e)` - *Osculating semi-major axis, eccentricity and period of ``body`` around ``primary``.*

---

### [`orrery/trails.py`](orrery/trails.py)
> *Bounded, sampled position history for drawing orbit trails.*

**Size**: `121` lines (`5231` bytes)

**Classes:**
- `class TrailRecorder` - *Keep one bounded deque of past positions per body, sampled every N steps.*
  - Method `.__init__(world, limit)`
  - Property `.trails`
  - Method `.sync(world)` - *Synchronize trail history buffers when the world body count changes.*
  - Method `.record(world)`
  - Method `.clear(world)` - *Clear historical trail samples, seeding with current positions if world is given.*
  - Method `.advance(world, dt, steps, every, merge_radius, bounce_radius, restitution)`
  - Method `.advance_to(world, target, dt, every, merge_radius, bounce_radius, restitution)`

---

### [`orrery/web.py`](orrery/web.py)
> *Zero-dependency HTTP server and embedded interactive Web-based UI for Orrery.*

**Size**: `1377` lines (`49214` bytes)

**Classes:**
- `class WebOptions` - *Physics and time overrides shared by the browser and the terminal.*
  - Method `.as_dict()` - *Return the JSON-safe view the browser consumes at startup.*
- `class _WebState` - *Per-server state: the chosen world, overrides and uploaded scenarios.*
- `class OrreryHandler` - *HTTP request handler serving the single-page application and JSON APIs.*
  - Method `.log_message(format, *args)` - *Suppress standard HTTP server access log to keep the terminal tidy.*
  - Method `._state()` - *Return the state attached by run_server, or safe defaults for bare handlers.*
  - Method `._resolve(key)`
  - Method `._send_json(status, data)`
  - Method `._send_html(content)`
  - Method `.do_GET()`
  - Method `.do_POST()`

**Functions:**
- `def _scenario_overrides(scenario, options)` - *Resolve scenario defaults against CLI overrides exactly like the terminal.*
- `def _scenario_payload(scenario, options)`
- `def _scenario_to_dict(scenario_key, options)` - *Describe one built-in scenario using the default web overrides.*
- `def _json_safe(value)` - *Replace non-finite floats so the response stays valid strict JSON.*
- `def _catalog_list(state)`
- `def _register_scenario(state, scenario)` - *Store an uploaded scenario under a key that cannot shadow a built-in one.*
- `def run_server(port, host, initial_scenario, auto_open, once, options, scenario)` - *Run the zero-dependency Orrery Web HTTP server.*

---

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

---

### [`tests/test_cli.py`](tests/test_cli.py)
**Size**: `565` lines (`26174` bytes)

**Classes:**
- `class ListAndInfoTests`
  - Method `.test_list_shows_every_scenario()`
  - Method `.test_list_json_is_a_machine_readable_catalogue()`
  - Method `.test_info_prints_a_table()`
  - Method `.test_info_json_contains_orbital_elements()`
  - Method `.test_equal_mass_system_does_not_invent_orbital_elements()`
  - Method `.test_info_json_uses_coulomb_for_charged_scenarios()`
  - Method `.test_info_json_marks_net_repulsion_as_unbound()`
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
  - Method `.test_cli_bounce_and_restitution_options()`
  - Method `.test_cli_coulomb_option()`
  - Method `.test_cli_telemetry_hud_energy_decomposition()`
  - Method `.test_web_forwards_initial_world_and_overrides()`
  - Method `.test_web_accepts_a_custom_scenario_file()`
  - Method `.test_cli_invalid_physics_args_rejected()`
  - Method `.test_cli_export_metadata_includes_bounce_and_coulomb()`
  - Method `.test_cli_time_options_dt_and_reverse()`
  - Method `.test_cli_time_options_warp()`
  - Method `.test_snapshot_rejects_time_scale()`
  - Method `.test_cli_invalid_time_args()`
  - Method `.test_run_interactive_time_keys()`
  - Method `.test_cli_web_subcommand_help()`

**Functions:**
- `def run_cli(*argv)`

---

### [`tests/test_custom.py`](tests/test_custom.py)
**Size**: `151` lines (`5614` bytes)

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
  - Method `.test_custom_scenario_with_charge_and_coulomb()`

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

**Size**: `66` lines (`2457` bytes)

**Classes:**
- `class LauncherTest`
  - Method `.test_launchers_exist()`
  - Method `.test_macos_command_launcher_delegates_to_the_shell_launcher()`
  - Method `.test_batch_file_has_crlf_line_endings()`
  - Method `.test_launchers_check_python_310_and_start_the_module()`
  - Method `.test_batch_checks_each_python_candidate()`
  - Method `.test_batch_failure_stays_visible()`
  - Method `.test_web_launchers_exist_and_start_the_web_command()`
  - Method `.test_web_command_launcher_delegates_to_the_shell_launcher()`
  - Method `.test_web_batch_file_has_crlf_line_endings()`

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
**Size**: `124` lines (`5615` bytes)

**Classes:**
- `class ScenarioTests`
  - Method `.test_distinct_scenarios()`
  - Method `.test_lagrange_pinwheel_is_equilateral()`
  - Method `.test_every_scenario_is_valid_and_centred()`
  - Method `.test_solar_earth_has_its_real_orbit()`
  - Method `.test_trojan_asteroids_straddle_jupiter()`
  - Method `.test_aliases_resolve()`
  - Method `.test_rutherford_scenario()`
  - Method `.test_bohr_scenario()`
  - Method `.test_black_hole_scenario()`
  - Method `.test_extents_cover_the_initial_bodies()`
  - Method `.test_unknown_key_raises()`

---

### [`tests/test_sim.py`](tests/test_sim.py)
**Size**: `280` lines (`13538` bytes)

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
  - Method `.test_orbital_elements_include_coulomb_attraction()`
  - Method `.test_orbital_elements_reject_net_repulsion()`
  - Method `.test_relativity_post_newtonian_precession()`
  - Method `.test_resolve_collisions_inelastic_merger()`
  - Method `.test_advance_and_advance_to_with_merge_radius()`
  - Method `.test_invalid_inputs_are_rejected()`
  - Method `.test_coulomb_repulsion_and_attraction()`
  - Method `.test_electrostatic_energy_and_potential()`
  - Method `.test_relativistic_energy_and_schwarzschild_radius()`
  - Method `.test_elastic_bounce_collisions_conservation()`
  - Method `.test_time_reversible_leapfrog()`
  - Method `.test_advance_and_advance_to_backward_in_time()`

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

### [`tests/test_web.py`](tests/test_web.py)
**Size**: `298` lines (`11569` bytes)

**Classes:**
- `class WebApiTests`
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_root_serves_html()`
  - Method `.test_api_health()`
  - Method `.test_api_scenarios_catalogue()`
  - Method `.test_api_scenario_detail()`
  - Method `.test_api_scenario_not_found()`
  - Method `.test_api_validate_endpoint()`
  - Method `.test_internal_helpers()`
  - Method `.test_run_server_once()`
- `class WebConfigTests`
  - Method `.setUp()`
  - Method `.tearDown()`
  - Method `._get_json(path)`
  - Method `._post_scenario(payload)`
  - Method `._custom_payload(key, title)`
  - Method `.test_config_reports_initial_world_and_options()`
  - Method `.test_options_are_applied_to_scenario_detail()`
  - Method `.test_relativity_override_sets_speed_of_light()`
  - Method `.test_validated_custom_scenario_can_be_fetched()`
  - Method `.test_custom_scenario_cannot_shadow_a_builtin_key()`
  - Method `.test_json_safe_replaces_non_finite_floats()`
  - Method `.test_run_server_wires_initial_scenario_and_options()`
  - Method `.test_oversized_upload_is_refused()`

---
