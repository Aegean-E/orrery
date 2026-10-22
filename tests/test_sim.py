import math
import unittest

from orrery.scenarios import G_SOLAR, YEAR_DAYS, get_scenario
from orrery.sim import Body, Vec2, World, orbital_elements


class Vec2Tests(unittest.TestCase):
    def test_arithmetic(self):
        first = Vec2(3.0, -2.0)
        second = Vec2(-1.0, 4.0)
        self.assertEqual(first + second, Vec2(2.0, 2.0))
        self.assertEqual(first - second, Vec2(4.0, -6.0))
        self.assertEqual(first * 2.0, Vec2(6.0, -4.0))
        self.assertEqual(2.0 * first, Vec2(6.0, -4.0))
        self.assertEqual(-first, Vec2(-3.0, 2.0))
        self.assertEqual(first.dot(second), -11.0)
        self.assertAlmostEqual(Vec2(3.0, 4.0).norm(), 5.0)
        self.assertAlmostEqual(Vec2(3.0, 4.0).norm_sq(), 25.0)
        self.assertAlmostEqual(Vec2(1.0, 1.0).distance_to(Vec2(4.0, 5.0)), 5.0)


class WorldTests(unittest.TestCase):
    def test_pairwise_acceleration_points_towards_the_other_body(self):
        first = Body("A", 2.0, Vec2(0.0, 0.0), Vec2(), "a")
        second = Body("B", 3.0, Vec2(2.0, 0.0), Vec2(), "b")
        accelerations = World((first, second), 1.0).accelerations()
        self.assertAlmostEqual(accelerations[0].x, 3.0 / 4.0)
        self.assertAlmostEqual(accelerations[0].y, 0.0)
        self.assertAlmostEqual(accelerations[1].x, -2.0 / 4.0)
        self.assertAlmostEqual(accelerations[1].y, 0.0)

    def test_coincident_bodies_do_not_divide_by_zero(self):
        first = Body("A", 1.0, Vec2(2.0, 3.0), Vec2(), "a")
        second = Body("B", 1.0, Vec2(2.0, 3.0), Vec2(), "b")
        accelerations = World((first, second), 1.0).accelerations()
        self.assertEqual(accelerations[0], Vec2())
        self.assertEqual(accelerations[1], Vec2())

    def test_circular_orbit_keeps_its_radius_and_energy(self):
        planet_mass = 3.0e-6
        speed = math.sqrt(G_SOLAR * (1.0 + planet_mass))
        sun = Body("Sun", 1.0, Vec2(), Vec2(), "@")
        planet = Body("Planet", planet_mass, Vec2(1.0, 0.0), Vec2(0.0, speed), "P")
        world = World((sun, planet), G_SOLAR)
        initial_energy = world.total_energy()
        world.advance(0.5, 731)
        self.assertAlmostEqual(world.bodies[1].pos.norm(), 1.0, delta=5e-3)
        self.assertLess(abs(world.energy_drift(initial_energy)), 1e-5)

    def test_momentum_and_barycentre_are_conserved(self):
        first = Body("A", 1.0, Vec2(-1.0, 0.0), Vec2(0.0, -1.0), "a")
        second = Body("B", 1.0, Vec2(1.0, 0.0), Vec2(0.0, 1.0), "b")
        world = World((first, second), 1.0)
        initial_momentum = world.momentum()
        initial_center = world.center_of_mass()
        world.advance(0.001, 500)
        self.assertLess(world.momentum().distance_to(initial_momentum), 1e-12)
        self.assertLess(world.center_of_mass().distance_to(initial_center), 1e-12)

    def test_figure_eight_returns_after_one_period(self):
        scenario = get_scenario("figure-eight")
        world = World(scenario.bodies, scenario.g)
        starts = [body.pos for body in world.bodies]
        initial_energy = world.total_energy()
        world.advance(scenario.dt, round(6.32591398 / scenario.dt))
        self.assertLess(abs(world.energy_drift(initial_energy)), 1e-6)
        for body, start in zip(world.bodies, starts):
            self.assertLess(body.pos.distance_to(start), 2e-2,
                            f"{body.name} did not come back: {body.pos} vs {start}")

    def test_orbital_elements_describe_a_unit_circle(self):
        mass = 3.0e-6
        speed = math.sqrt(G_SOLAR * (1.0 + mass))
        sun = Body("Sun", 1.0, Vec2(), Vec2(), "@")
        planet = Body("Planet", mass, Vec2(1.0, 0.0), Vec2(0.0, speed), "P")
        orbit = orbital_elements(sun, planet, G_SOLAR)
        self.assertAlmostEqual(orbit.semi_major, 1.0, places=6)
        self.assertLess(orbit.eccentricity, 1e-6)
        self.assertAlmostEqual(orbit.period, YEAR_DAYS / math.sqrt(1.0 + mass), places=6)

    def test_invalid_inputs_are_rejected(self):
        body = Body("A", 1.0, Vec2(), Vec2(), "a")
        world = World((body,), 1.0)
        with self.assertRaises(ValueError):
            world.step(0.0)
        with self.assertRaises(ValueError):
            world.advance(0.1, -1)
        with self.assertRaises(ValueError):
            world.advance_to(-1.0, 0.1)
        with self.assertRaises(ValueError):
            World((Body("A", 0.0, Vec2(), Vec2()),), 1.0)
        with self.assertRaises(ValueError):
            World((Body("A", 1.0, Vec2(), Vec2()),
                   Body("A", 1.0, Vec2(1.0, 0.0), Vec2())), 1.0)


if __name__ == "__main__":
    unittest.main()
