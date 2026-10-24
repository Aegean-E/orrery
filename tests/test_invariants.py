import math
import unittest

from orrery.scenarios import SCENARIOS, YEAR_DAYS, get_scenario
from orrery.sim import World


class InvariantTests(unittest.TestCase):
    def test_angular_momentum_is_conserved_scenario_wide(self):
        for scenario in SCENARIOS.values():
            world = World(scenario.bodies, scenario.g)
            initial = world.angular_momentum()
            scale = math.fsum(
                body.mass * body.pos.norm() * body.vel.norm()
                for body in world.bodies
            )
            world.advance(scenario.dt, 500)
            with self.subTest(scenario=scenario.key):
                self.assertLess(
                    abs(world.angular_momentum() - initial),
                    1e-10 * max(scale, 1.0),
                )

    def test_binary_remains_bound_for_ninety_days(self):
        scenario = get_scenario("binary")
        world = World(scenario.bodies, scenario.g)
        initial_energy = world.total_energy()
        steps = math.ceil(90.0 / scenario.dt)
        world.advance(scenario.dt, steps)
        stars = [body for body in world.bodies if body.name in ("Aster", "Boreas")]
        planet = next(body for body in world.bodies if body.name == "Pale")
        self.assertAlmostEqual(stars[0].pos.distance_to(stars[1].pos), 0.2, delta=0.02)
        self.assertAlmostEqual(planet.pos.norm(), 1.3, delta=0.05)
        self.assertLess(abs(world.energy_drift(initial_energy)), 1e-8)
        self.assertTrue(all(math.isfinite(value) for body in world.bodies
                            for value in (body.pos.x, body.pos.y)))

    def test_trojans_hold_their_lagrange_angles_for_ten_years(self):
        scenario = get_scenario("trojans")
        world = World(scenario.bodies, scenario.g)
        world.advance(scenario.dt, math.ceil(10 * YEAR_DAYS / scenario.dt))
        sun, jupiter = world.bodies[0], world.bodies[1]
        jupiter_angle = math.degrees(math.atan2(jupiter.pos.y - sun.pos.y,
                                                jupiter.pos.x - sun.pos.x))
        for asteroid in world.bodies[2:]:
            angle = math.degrees(math.atan2(asteroid.pos.y - sun.pos.y,
                                            asteroid.pos.x - sun.pos.x))
            separation = abs(angle - jupiter_angle)
            separation = min(separation, 360.0 - separation)
            with self.subTest(body=asteroid.name):
                self.assertAlmostEqual(separation, 60.0, delta=0.1)
                self.assertAlmostEqual(asteroid.pos.distance_to(sun.pos), 5.2038,
                                       delta=1e-3)


if __name__ == "__main__":
    unittest.main()
