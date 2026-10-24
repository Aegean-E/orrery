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

    def test_parabolic_orbit_has_no_finite_elements(self):
        mass = 1e-9
        mu = 1.0 + mass
        sun = Body("Sun", 1.0, Vec2(), Vec2(), "@")
        comet = Body("Comet", mass, Vec2(1.0, 0.0), Vec2(0.0, math.sqrt(2.0 * mu)), "C")
        orbit = orbital_elements(sun, comet, 1.0)
        self.assertIsNone(orbit.semi_major)
        self.assertIsNone(orbit.period)
        self.assertAlmostEqual(orbit.eccentricity, 1.0, places=9)

    def test_orbital_elements_describe_a_unit_circle(self):
        mass = 3.0e-6
        speed = math.sqrt(G_SOLAR * (1.0 + mass))
        sun = Body("Sun", 1.0, Vec2(), Vec2(), "@")
        planet = Body("Planet", mass, Vec2(1.0, 0.0), Vec2(0.0, speed), "P")
        orbit = orbital_elements(sun, planet, G_SOLAR)
        self.assertAlmostEqual(orbit.semi_major, 1.0, places=6)
        self.assertLess(orbit.eccentricity, 1e-6)
        self.assertAlmostEqual(orbit.period, YEAR_DAYS / math.sqrt(1.0 + mass), places=6)

    def test_relativity_post_newtonian_precession(self):
        # Primary of mass 1.0, test body with e = 0.5
        sun = Body("Sun", 1.0, Vec2(), Vec2())
        # Perihelion at r = 0.5, v = sqrt(G*M*(1+e)/r) = sqrt(1.5 / 0.5) = sqrt(3)
        v0 = math.sqrt(3.0)
        planet_newt = Body("P", 1e-6, Vec2(0.5, 0.0), Vec2(0.0, v0))
        planet_rel = Body("P", 1e-6, Vec2(0.5, 0.0), Vec2(0.0, v0))
        world_newt = World((sun, planet_newt), 1.0)
        # Moderate c to produce noticeable 1PN precession without instability
        world_rel = World((sun, planet_rel), 1.0, c=20.0)
        dt = 0.001
        # Advance 1 orbit (period ~ 2*pi * a^(3/2) = 2*pi ~ 6.28)
        period = 2.0 * math.pi
        world_newt.advance_to(period, dt)
        world_rel.advance_to(period, dt)
        # 1PN precession should cause relativistic orbit to have slight forward phase advance
        self.assertNotEqual(world_newt.bodies[1].pos.x, world_rel.bodies[1].pos.x)
        self.assertLess(abs(world_rel.energy_drift(world_rel.total_energy())), 1e-5)

    def test_resolve_collisions_inelastic_merger(self):
        b1 = Body("Heavy", 10.0, Vec2(0.0, 0.0), Vec2(0.0, 1.0), "H", "yellow")
        b2 = Body("Light", 2.0, Vec2(0.005, 0.0), Vec2(0.0, -5.0), "L", "cyan")
        b3 = Body("Distant", 1.0, Vec2(5.0, 0.0), Vec2(0.0, 0.0), "D", "white")
        world = World((b1, b2, b3), 1.0)
        p0 = world.momentum()
        cm0 = world.center_of_mass()
        events = world.resolve_collisions(merge_radius=0.01)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], ("Heavy", "Light", "Heavy"))
        self.assertEqual(len(world.bodies), 2)
        merged = world.bodies[0]
        self.assertEqual(merged.name, "Heavy")
        self.assertEqual(merged.symbol, "H")
        self.assertEqual(merged.mass, 12.0)
        # Exact linear momentum and CM conservation
        p1 = world.momentum()
        cm1 = world.center_of_mass()
        self.assertAlmostEqual(p0.distance_to(p1), 0.0, places=9)
        self.assertAlmostEqual(cm0.distance_to(cm1), 0.0, places=9)

    def test_advance_and_advance_to_with_merge_radius(self):
        b1 = Body("Heavy", 10.0, Vec2(0.0, 0.0), Vec2(0.0, 0.0))
        b2 = Body("Light", 1.0, Vec2(0.02, 0.0), Vec2(0.0, 0.0))
        world = World((b1, b2), 1e-6)
        events = world.advance(0.01, 1, merge_radius=0.05)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(world.bodies), 1)

        b3 = Body("A", 1.0, Vec2(0.0, 0.0), Vec2(0.0, 0.0))
        b4 = Body("B", 1.0, Vec2(0.03, 0.0), Vec2(0.0, 0.0))
        world2 = World((b3, b4), 1e-6)
        events2 = world2.advance_to(0.02, 0.01, merge_radius=0.05)
        self.assertEqual(len(events2), 1)
        self.assertEqual(len(world2.bodies), 1)

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
        with self.assertRaises(ValueError):
            World((body,), 1.0, c=0.0)
        with self.assertRaises(ValueError):
            World((body,), 1.0, c=-5.0)
        with self.assertRaises(ValueError):
            World((body,), 1.0, k_e=-1.0)

    def test_coulomb_repulsion_and_attraction(self):
        # Two like charges repel
        p1 = Body("P1", 1.0, Vec2(0.0, 0.0), Vec2(), charge=1.0)
        p2 = Body("P2", 1.0, Vec2(2.0, 0.0), Vec2(), charge=2.0)
        world_repel = World((p1, p2), 1e-9, k_e=4.0)
        acc_repel = world_repel.accelerations()
        # Coulomb force magnitude: k_e * q1 * q2 / r^2 = 4.0 * 2.0 / 4.0 = 2.0
        # p1 pushed left (negative x), p2 pushed right (positive x)
        self.assertAlmostEqual(acc_repel[0].x, -2.0, places=5)
        self.assertAlmostEqual(acc_repel[1].x, 2.0, places=5)

        # Opposite charges attract
        e2 = Body("E2", 1.0, Vec2(2.0, 0.0), Vec2(), charge=-2.0)
        world_attract = World((p1, e2), 1e-9, k_e=4.0)
        acc_attract = world_attract.accelerations()
        # p1 pulled right (positive x), e2 pulled left (negative x)
        self.assertAlmostEqual(acc_attract[0].x, 2.0, places=5)
        self.assertAlmostEqual(acc_attract[1].x, -2.0, places=5)

    def test_electrostatic_energy_and_potential(self):
        p1 = Body("P1", 1.0, Vec2(0.0, 0.0), Vec2(), charge=2.0)
        p2 = Body("P2", 1.0, Vec2(2.0, 0.0), Vec2(), charge=3.0)
        world = World((p1, p2), g=1.0, k_e=5.0)
        # U_g = - 1.0 * 1.0 * 1.0 / 2.0 = -0.5
        # U_e = 5.0 * 2.0 * 3.0 / 2.0 = 15.0
        # U_tot = -0.5 + 15.0 = 14.5
        self.assertAlmostEqual(world.electrostatic_energy(), 15.0, places=6)
        self.assertAlmostEqual(world.potential_energy(), 14.5, places=6)

    def test_relativistic_energy_and_schwarzschild_radius(self):
        b1 = Body("B1", 10.0, Vec2(0.0, 0.0), Vec2(3.0, 0.0))
        world = World((b1,), g=2.0, c=5.0)
        # r_s = 2 * G * M / c^2 = 2 * 2.0 * 10.0 / 25.0 = 1.6
        self.assertAlmostEqual(world.schwarzschild_radius(), 1.6, places=6)
        # beta = v / c = 3.0 / 5.0 = 0.6
        # gamma = 1 / sqrt(1 - 0.36) = 1 / 0.8 = 1.25
        # E_rel = gamma * m * c^2 = 1.25 * 10.0 * 25.0 = 312.5
        self.assertAlmostEqual(world.relativistic_energy(), 312.5, places=5)

    def test_elastic_bounce_collisions_conservation(self):
        b1 = Body("Left", 2.0, Vec2(-0.01, 0.0), Vec2(2.0, 0.0), "L")
        b2 = Body("Right", 2.0, Vec2(0.01, 0.0), Vec2(-2.0, 0.0), "R")
        world = World((b1, b2), g=1e-9)
        k0 = world.kinetic_energy()
        p0 = world.momentum()
        cm0 = world.center_of_mass()
        events = world.resolve_elastic_collisions(bounce_radius=0.05, restitution=1.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], ("Left", "Right"))
        # Equal masses head-on bounce: velocities swap
        self.assertAlmostEqual(world.bodies[0].vel.x, -2.0, places=5)
        self.assertAlmostEqual(world.bodies[1].vel.x, 2.0, places=5)
        # Exact kinetic energy and momentum conservation
        self.assertAlmostEqual(world.kinetic_energy(), k0, places=6)
        self.assertAlmostEqual(world.momentum().distance_to(p0), 0.0, places=6)
        self.assertAlmostEqual(world.center_of_mass().distance_to(cm0), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
