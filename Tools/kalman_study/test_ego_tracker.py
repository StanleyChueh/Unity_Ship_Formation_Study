import math
import unittest
import numpy as np
from ego_tracker import EgoRangeTracker

C = 25.6*math.sqrt(1000.0)   # reference area 1000 px at the 25.6 m design range


def area_at(r):
    return (C/r)**2


class Speed:
    def __init__(self, v):
        self.v = v

    def __call__(self):
        return self.v


class EgoRangeTrackerTest(unittest.TestCase):
    def make(self, speed):
        return EgoRangeTracker(ego=speed, reference_area=lambda: 1000.0)

    def run_steady(self, tracker, speed, leader_speed, seconds, r0=25.6, start=0.0):
        """Leader and follower in line; range changes by kappa*(vL - vF)."""
        r = r0
        t = start
        for _ in range(int(seconds*10)):
            t += 0.1
            r += tracker.kappa*(leader_speed-speed.v)*0.1
            tracker.observe(0.0, area_at(r), t, 1.0)
        return r, t

    def test_steady_formation_coast_holds_range(self):
        speed = Speed(18.0)
        tracker = self.make(speed)
        tracker.observe(0.0, 1000.0, 0.0, 1.0)
        r, t = self.run_steady(tracker, speed, 18.0, 10.0)
        for k in range(20):
            tracker.predict_to(t+0.1*(k+1), missing=True)
        self.assertAlmostEqual(tracker.range_state()[0], r, delta=0.5)

    def test_own_slowdown_during_coast_shrinks_predicted_area(self):
        speed = Speed(18.0)
        tracker = self.make(speed)
        tracker.observe(0.0, 1000.0, 0.0, 1.0)
        r, t = self.run_steady(tracker, speed, 18.0, 10.0)
        before = tracker.state()[2]
        speed.v = 14.0   # follower decelerates while the leader is unseen
        for k in range(20):
            tracker.predict_to(t+0.1*(k+1), missing=True)
        expected = r+tracker.kappa*4.0*2.0
        self.assertAlmostEqual(tracker.range_state()[0], expected, delta=0.8)
        self.assertLess(tracker.state()[2], before*0.85)
        self.assertLess(tracker.state()[3], 0.0)   # area velocity reported as shrinking

    def test_learns_receding_leader_rate(self):
        speed = Speed(15.0)
        tracker = self.make(speed)
        tracker.observe(0.0, 1000.0, 0.0, 1.0)
        self.run_steady(tracker, speed, 18.0, 12.0)
        self.assertAlmostEqual(tracker.range_state()[1], tracker.kappa*18.0, delta=0.6)

    def test_single_propagation_clock_at_reacquisition(self):
        speed = Speed(18.0)
        tracker = self.make(speed)
        tracker.observe(0.0, 1000.0, 0.0, 1.0)
        r, t = self.run_steady(tracker, speed, 18.0, 5.0)
        for k in range(20):
            tracker.predict_to(t+0.1*(k+1), missing=True)
        coasted = tracker.range_state()[0]
        P = tracker.Py.copy()
        tracker.predict_to(t+2.0)   # same timestamp: no repeated propagation
        self.assertEqual(tracker.range_state()[0], coasted)
        self.assertTrue(np.array_equal(P, tracker.Py))

    def test_covariance_psd_and_area_positive(self):
        rng = np.random.default_rng(3)
        speed = Speed(16.0)
        tracker = self.make(speed)
        tracker.observe(0.0, 1000.0, 0.0, 1.0)
        t = 0.0
        for k in range(400):
            t += 0.1
            speed.v = 16+3*math.sin(k/30)
            if k % 50 < 40:
                tracker.observe(rng.normal(0, .02), area_at(25.6)*math.exp(rng.normal(0, .15)), t, rng.uniform(.3, 1))
            else:
                tracker.predict_to(t, missing=True)
            self.assertGreater(tracker.state()[2], 0)
            self.assertGreaterEqual(np.linalg.eigvalsh(tracker.Py).min(), -1e-9)

    def test_no_reference_uses_first_area(self):
        tracker = EgoRangeTracker(ego=Speed(0.0), reference_area=lambda: None)
        tracker.observe(0.0, 800.0, 0.0, 1.0)
        self.assertAlmostEqual(tracker.range_state()[0], 25.6, places=6)
        self.assertAlmostEqual(tracker.state()[2], 800.0, places=3)


    def test_reanchors_when_calibration_locks(self):
        ref = [None]
        tracker = EgoRangeTracker(ego=Speed(0.0), reference_area=lambda: ref[0])
        tracker.observe(0.0, 700.0, 0.0, 1.0)
        ref[0] = 1000.0
        tracker.observe(0.0, 1000.0, 0.1, 1.0)
        self.assertAlmostEqual(tracker.c, C, places=6)
        for k in range(30):
            tracker.observe(0.0, 1000.0, 0.2+0.1*k, 1.0)
        self.assertAlmostEqual(tracker.range_state()[0], 25.6, delta=0.3)


if __name__ == '__main__':
    unittest.main()
