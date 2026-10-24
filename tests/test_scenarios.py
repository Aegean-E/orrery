import math
import unittest

from orrery.scenarios import (
    SCENARIOS,
    YEAR_DAYS,
    get_scenario,
    scenario_keys,
)
from orrery.sim import World, orbital_elements


class ScenarioTests(unittest.TestCase):
    def test_exactly_six_distinct_scenarios(self):
        self.assertEqual(
            scenario_keys(),
            ("solar", "figure-eight", "binary", "trojans", "pythagorean", "lagrange"),
        )
        self.assertEqual(len(set(scenario_keys())), 6)

    def test_lagrange_pinwheel_is_equilateral(self):
        scenario = get_scenario("lagrange")
        world = World(scenario.bodies, scenario.g)
        s = math.sqrt(3.0)
        p1, p2, p3 = world.bodies[0].pos, world.bodies[1].pos, world.bodies[2].pos
        self.assertAlmostEqual(p1.distance_to(p2), s, places=5)
        self.assertAlmostEqual(p2.distance_to(p3), s, places=5)
        self.assertAlmostEqual(p3.distance_to(p1), s, places=5)

    def test_every_scenario_is_valid_and_centred(self):
        for scenario in SCENARIOS.values():
            with self.subTest(scenario=scenario.key):
                world = World(scenario.bodies, scenario.g)
                self.assertGreater(scenario.dt, 0.0)
                self.assertGreater(scenario.span, 0.0)
                self.assertGreater(scenario.steps_per_frame, 0)
                self.assertGreater(scenario.trail_length, 0)
                self.assertLess(world.center_of_mass().norm(), 1e-12)
                scale = max(1.0, world.total_mass * max(
                    body.vel.norm() for body in world.bodies
                ))
                self.assertLess(world.momentum().norm(), 1e-12 * scale)

    def test_solar_earth_has_its_real_orbit(self):
        scenario = get_scenario("solar")
        world = World(scenario.bodies, scenario.g)
        sun = world.bodies[0]
        earth = next(body for body in world.bodies if body.name == "Earth")
        orbit = orbital_elements(sun, earth, scenario.g)
        self.assertAlmostEqual(orbit.semi_major, 1.0, places=4)
        self.assertAlmostEqual(orbit.eccentricity, 0.016708, places=4)
        self.assertAlmostEqual(orbit.period, YEAR_DAYS, delta=2.0)

    def test_trojan_asteroids_straddle_jupiter(self):
        scenario = get_scenario("trojans")
        world = World(scenario.bodies, scenario.g)
        sun = world.bodies[0]
        jupiter = next(body for body in world.bodies if body.name == "Jupiter")
        jupiter_angle = math.degrees(math.atan2(jupiter.pos.y - sun.pos.y,
                                                jupiter.pos.x - sun.pos.x))
        relative_angles = []
        for name in ("Achilles", "Patroclus"):
            asteroid = next(body for body in world.bodies if body.name == name)
            self.assertAlmostEqual(asteroid.pos.distance_to(sun.pos),
                                   jupiter.pos.distance_to(sun.pos), delta=1e-6)
            relative = asteroid.pos - jupiter.pos
            angle = math.degrees(math.atan2(relative.y, relative.x))
            separation = abs(angle - jupiter_angle)
            relative_angles.append(min(separation, 360.0 - separation))
        self.assertAlmostEqual(relative_angles[0], 120.0, delta=1e-3)
        self.assertAlmostEqual(relative_angles[1], 120.0, delta=1e-3)

    def test_aliases_resolve(self):
        self.assertEqual(get_scenario("inner").key, "solar")
        for name in ("figure-8", "Figure 8", "Figure8"):
            self.assertEqual(get_scenario(name).key, "figure-eight")
        self.assertEqual(get_scenario("circumbinary").key, "binary")
        self.assertEqual(get_scenario("trojan").key, "trojans")

    def test_extents_cover_the_initial_bodies(self):
        for scenario in SCENARIOS.values():
            for body in scenario.bodies:
                with self.subTest(scenario=scenario.key, body=body.name):
                    self.assertLessEqual(abs(body.pos.x), scenario.extent[0])
                    self.assertLessEqual(abs(body.pos.y), scenario.extent[1])

    def test_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            get_scenario("nibiru")


if __name__ == "__main__":
    unittest.main()
