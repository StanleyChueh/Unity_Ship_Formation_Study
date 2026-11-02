"""Unit tests for the vision-only range filter: run with `python3 test_vision_only.py`."""
import math
import unittest
import numpy as np
from vision_only_tracker import VisionRangeTracker, OwnSpeedModel

C = 25.6*math.sqrt(4000.0)


def area(r):
    return (C/r)**2


class Sim:
    def __init__(self, noise=0.0, seed=0):
        self.v = 18.0
        self.r = 25.6
        self.rng = np.random.default_rng(seed)
        self.noise = noise
        self.t = 0.0
        self.tracker = VisionRangeTracker(kalman=True, ego=lambda: self.v, reference_area=lambda: 4000.0)
        self.tracker.initialize(0.0, area(self.r), 0.0)

    def run(self, seconds, leader, measure=True):
        for _ in range(int(seconds*10)):
            self.t += 0.1
            self.r += 0.1*self.tracker.kappa*(leader(self.t)-self.v)
            # A follower that closes the range error, otherwise the test boat rams or loses the leader.
            self.v += 0.1*(0.8*(self.r-25.6)+leader(self.t)-self.v)/2.0
            if measure:
                a = area(self.r)*math.exp(2*self.noise*self.rng.standard_normal())
                self.tracker.observe(0.0, a, self.t)
            else:
                self.tracker.predict_to(self.t, missing=True)


class VisionOnly(unittest.TestCase):
    def test_estimates_leader_speed_from_images_only(self):
        s = Sim(noise=0.05)
        s.run(30, lambda t: 14.0)
        self.assertLess(abs(s.tracker.leader_speed()-14.0), 1.5)

    def test_tracks_speed_change(self):
        s = Sim(noise=0.05)
        s.run(20, lambda t: 18.0)
        s.run(20, lambda t: 10.0)
        self.assertLess(abs(s.tracker.leader_speed()-10.0), 1.5)

    def test_leader_input_is_discarded(self):
        t = VisionRangeTracker(kalman=True, leader=lambda: 999.0, ego=lambda: 18.0, reference_area=lambda: 4000.0)
        t.initialize(0.0, area(25.6), 0.0)
        self.assertLess(t.leader_speed(), 19.0)
        t.predict_to(1.0)
        self.assertLess(t.leader_speed(), 19.0)
        self.assertIsNone(t._leader_speed())

    def test_coasts_at_estimated_speed_through_dropout(self):
        s = Sim(noise=0.02)
        s.run(20, lambda t: 15.0)
        est = s.tracker.leader_speed()
        s.run(2, lambda t: 15.0, measure=False)
        self.assertAlmostEqual(s.tracker.leader_speed(), est, places=6)
        self.assertLess(abs(s.tracker.y[0]-s.r), 3.0)

    def test_gate_rejects_outlier_box(self):
        s = Sim(noise=0.02)
        s.run(10, lambda t: 18.0)
        before = s.tracker.y[0]
        s.tracker.observe(0.0, area(s.r)*40, s.t+0.1)
        self.assertLess(abs(s.tracker.y[0]-before), 2.0)
        self.assertEqual(s.tracker.gate_rejections, 1)

    def test_own_speed_model_settles_at_plant_gain(self):
        m = OwnSpeedModel()
        for k in range(100):
            m.step(18*0.043, k*0.1)
        self.assertAlmostEqual(m.v, 18.0, places=3)


if __name__ == '__main__':
    unittest.main()
