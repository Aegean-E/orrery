import unittest

from orrery.sim import Body, Vec2, World
from orrery.trails import TrailRecorder


class TrailRecorderTests(unittest.TestCase):
    def _world(self):
        return World((Body("Mover", 1.0, Vec2(), Vec2(1.0, 0.0), "m"),), 1.0)

    def test_limit_keeps_the_most_recent_positions(self):
        world = self._world()
        recorder = TrailRecorder(world, 3)
        recorder.advance(world, 1.0, 5)
        self.assertEqual([point.x for point in recorder.trails[0]], [3.0, 4.0, 5.0])

    def test_sampling_every_other_step(self):
        world = self._world()
        recorder = TrailRecorder(world, 10)
        recorder.advance(world, 1.0, 4, every=2)
        self.assertEqual([point.x for point in recorder.trails[0]], [0.0, 2.0, 4.0])

    def test_advance_to_uses_a_short_final_step(self):
        world = self._world()
        recorder = TrailRecorder(world, 10)
        recorder.advance_to(world, 2.5, 1.0)
        self.assertAlmostEqual(world.time, 2.5)
        self.assertEqual([point.x for point in recorder.trails[0]], [0.0, 1.0, 2.0, 2.5])

    def test_zero_limit_disables_history(self):
        world = self._world()
        recorder = TrailRecorder(world, 0)
        recorder.advance(world, 1.0, 2)
        self.assertEqual(list(recorder.trails[0]), [])

    def test_invalid_arguments_are_rejected(self):
        world = self._world()
        with self.assertRaises(ValueError):
            TrailRecorder(world, -1)
        recorder = TrailRecorder(world, 4)
        with self.assertRaises(ValueError):
            recorder.advance(world, 1.0, -1)
        with self.assertRaises(ValueError):
            recorder.advance(world, 1.0, 1, every=0)
        with self.assertRaises(ValueError):
            recorder.advance_to(world, 1.0, 1.0, every=0)


if __name__ == "__main__":
    unittest.main()
