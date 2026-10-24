import unittest

from orrery.render import (
    TRAIL_DOT_STYLES,
    Viewport,
    render_scene,
    resolve_dot_char,
    strip_ansi,
)
from orrery.sim import Body, Vec2, World


class ViewportTests(unittest.TestCase):
    def test_centre_and_edges_map_to_expected_cells(self):
        viewport = Viewport(41, 21, 2.0)
        self.assertEqual(viewport.cell(Vec2(0.0, 0.0)), (20, 10))
        self.assertEqual(viewport.cell(Vec2(-1.0, 0.0)), (0, 10))
        self.assertEqual(viewport.cell(Vec2(1.0, 0.0)), (40, 10))
        self.assertEqual(viewport.cell(Vec2(0.0, 1.0)), (20, 0))
        self.assertEqual(viewport.cell(Vec2(0.0, -1.0)), (20, 20))

    def test_horizontal_cells_are_twice_as_dense(self):
        viewport = Viewport(81, 25, 2.4)
        self.assertAlmostEqual(viewport.cols_per_unit, 2.0 * viewport.rows_per_unit)

    def test_custom_aspect_changes_column_density(self):
        viewport = Viewport(41, 21, 2.0, aspect=1.0)
        self.assertAlmostEqual(viewport.cols_per_unit, viewport.rows_per_unit)

    def test_off_screen_points_are_none(self):
        viewport = Viewport(41, 21, 2.0)
        self.assertIsNone(viewport.cell(Vec2(1.2, 0.0)))
        self.assertIsNone(viewport.cell(Vec2(0.0, 1.2)))

    def test_invalid_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            Viewport(4, 21, 2.0)
        with self.assertRaises(ValueError):
            Viewport(41, 2, 2.0)
        with self.assertRaises(ValueError):
            Viewport(41, 21, 0.0)
        with self.assertRaises(ValueError):
            Viewport(41, 21, 2.0, aspect=0.0)


class RenderSceneTests(unittest.TestCase):
    def setUp(self):
        self.sun = Body("Sun", 1.0, Vec2(0.0, 0.0), Vec2(), "@", "yellow")
        self.planet = Body("Planet", 1e-3, Vec2(0.5, 0.0), Vec2(), "P", "blue")
        self.world = World((self.sun, self.planet), 1.0)
        self.trails = [[Vec2(-0.5, 0.0)], [Vec2(0.5, 0.0)]]
        self.viewport = Viewport(41, 21, 2.0)

    def test_lines_have_the_exact_viewport_size(self):
        lines = render_scene(self.world, self.trails, self.viewport)
        self.assertEqual(len(lines), 21)
        self.assertTrue(all(len(line) == 41 for line in lines))

    def test_bodies_overwrite_trails(self):
        lines = render_scene(self.world, self.trails, self.viewport)
        self.assertEqual(lines[10][20], "@")
        self.assertEqual(lines[10][30], "P")
        self.assertEqual(lines[10][10], "·")

    def test_ascii_mode_is_plain_ascii(self):
        lines = render_scene(self.world, self.trails, self.viewport, ascii_only=True)
        self.assertEqual(lines[10][10], ".")
        self.assertTrue(all(ord(char) < 128 for line in lines for char in line))

    def test_colour_adds_ansi_but_keeps_the_same_cells(self):
        plain = render_scene(self.world, self.trails, self.viewport)
        coloured = render_scene(self.world, self.trails, self.viewport, color=True)
        self.assertTrue(any("\x1b[" in line for line in coloured))
        self.assertIn("\x1b[2;33m", "".join(coloured))
        self.assertEqual([strip_ansi(line) for line in coloured], plain)

    def test_trail_samples_are_connected_with_line_cells(self):
        world = World((Body("Probe", 1.0, Vec2(0.0, 0.9), Vec2(), "P"),), 1.0)
        trails = [[Vec2(-0.5, 0.0), Vec2(0.5, 0.0)]]
        lines = render_scene(world, trails, self.viewport, ascii_only=True)
        self.assertTrue(all(lines[10][column] == "." for column in range(10, 31)))

    def test_braille_trails_use_subcell_glyphs(self):
        world = World((Body("Probe", 1.0, Vec2(0.0, 0.9), Vec2(), "P"),), 1.0)
        trails = [[Vec2(-0.5, 0.0), Vec2(0.5, 0.0)]]
        lines = render_scene(world, trails, self.viewport, braille=True)
        flat = "".join(lines)
        self.assertTrue(any(0x2800 <= ord(char) <= 0x28FF for char in flat))
        self.assertEqual(len(lines), 21)
        self.assertTrue(all(len(line) == 41 for line in lines))

    def test_trail_count_must_match_bodies(self):
        with self.assertRaises(ValueError):
            render_scene(self.world, self.trails[:1], self.viewport)

    def test_render_scene_with_custom_dot_char(self):
        world = World((Body("Probe", 1.0, Vec2(0.0, 0.9), Vec2(), "P"),), 1.0)
        trails = [[Vec2(-0.5, 0.0), Vec2(0.5, 0.0)]]
        lines_circle = render_scene(world, trails, self.viewport, dot_char="○")
        self.assertEqual(lines_circle[10][10], "○")
        lines_bullet = render_scene(world, trails, self.viewport, dot_char="•")
        self.assertEqual(lines_bullet[10][10], "•")

    def test_resolve_dot_char_styles_and_fallbacks(self):
        self.assertIn("circle", TRAIL_DOT_STYLES)
        self.assertIn("bullet", TRAIL_DOT_STYLES)
        self.assertEqual(resolve_dot_char("circle", encoding="utf-8"), "○")
        self.assertEqual(resolve_dot_char("bullet", encoding="utf-8"), "•")
        self.assertEqual(resolve_dot_char("ring", encoding="utf-8"), "◦")
        self.assertEqual(resolve_dot_char("disc", encoding="utf-8"), "●")
        self.assertEqual(resolve_dot_char("dot", encoding="utf-8"), "·")
        self.assertEqual(resolve_dot_char("ascii", encoding="utf-8"), ".")
        self.assertEqual(resolve_dot_char("circle", ascii_only=True), "o")
        self.assertEqual(resolve_dot_char("circle", encoding="ascii"), "o")
        self.assertEqual(resolve_dot_char("bullet", encoding="cp1254"), "•")
        self.assertEqual(resolve_dot_char("x", encoding="utf-8"), "x")
        self.assertEqual(resolve_dot_char(None), "·")
        self.assertEqual(resolve_dot_char(None, ascii_only=True), ".")


if __name__ == "__main__":
    unittest.main()
