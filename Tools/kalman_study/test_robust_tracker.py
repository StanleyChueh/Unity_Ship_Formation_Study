import math
import unittest
import numpy as np
from robust_tracker import RobustTracker


class TrackerTests(unittest.TestCase):
    def test_continuous_noise_is_invariant_to_step_partition(self):
        F, Q = RobustTracker.transition(0.8, 0.3)
        f, q = RobustTracker.transition(0.1, 0.3)
        p = np.zeros((2, 2)); transition = np.eye(2)
        for _ in range(8):
            p = f @ p @ f.T+q
            transition = f @ transition
        np.testing.assert_allclose(F, transition, atol=1e-12)
        np.testing.assert_allclose(Q, p, atol=1e-12)

    def test_reacquisition_does_not_predict_gap_twice(self):
        tracker = RobustTracker(); tracker.initialize(0, 1000, 0)
        tracker.x[0, 1] = 0.1
        tracker.predict_to(1)
        self.assertAlmostEqual(tracker.state()[0], 0.1)
        before = tracker.P.copy()
        tracker.predict_to(1)
        np.testing.assert_array_equal(before, tracker.P)
        tracker.observe(0.1, 1000, 1)
        self.assertAlmostEqual(tracker.state()[0], 0.1)

    def test_covariance_psd_outlier_and_positive_area(self):
        rng = np.random.default_rng(77); tracker = RobustTracker()
        for step in range(1000):
            t = step*0.1
            if step%100>75:
                tracker.predict_to(t, missing=True)
            else:
                tracker.observe(0.15*math.sin(t/8)+rng.normal(0, .02),
                                math.exp(7+.2*math.sin(t/10)+rng.normal(0, .15)),t,.7)
            self.assertTrue(np.isfinite(tracker.x).all())
            self.assertGreater(tracker.state()[2],0)
            self.assertGreaterEqual(np.linalg.eigvalsh(tracker.P).min(),-1e-12)
        for i in range(50): tracker.observe(0.1,1000,100+i*.1,.9)
        before=tracker.state()[0]
        tracker.observe(0.9,tracker.state()[2]*40,105,.9)
        self.assertLess(abs(tracker.state()[0]-before), .20)

    def test_missing_measurements_raise_uncertainty(self):
        tracker = RobustTracker()
        for i in range(40): tracker.observe(i*.001,1000,i*.1)
        before=tracker.offset_uncertainty()
        tracker.predict_to(5.9, missing=True)
        self.assertGreater(tracker.offset_uncertainty(),before)
        with self.assertRaises(ValueError): tracker.predict_to(1)

if __name__=='__main__':unittest.main()
