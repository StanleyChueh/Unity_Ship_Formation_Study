import math
import unittest
import numpy as np
from fusion_tracker import FusionRangeTracker

C = 25.6*math.sqrt(1000.0)


def area_at(r):
    return (C/r)**2


class V:
    def __init__(self, v):
        self.v = v

    def __call__(self):
        return self.v


class FusionTrackerTest(unittest.TestCase):
    def make(self, own, lead):
        return FusionRangeTracker(ego=own, leader=lead, reference_area=lambda: 1000.0)

    def steady(self, t, own, lead, seconds, r, tracker, noise=0.0, rng=None):
        for _ in range(int(seconds*10)):
            t += 0.1
            r += tracker.kappa*(lead.v-own.v)*0.1
            a = area_at(r)*(math.exp(rng.normal(0, noise)) if rng is not None else 1.0)
            tracker.observe(0.0, a, t, 1.0)
        return t, r

    def test_predicts_closing_on_decelerating_leader_without_measurements(self):
        own, lead = V(18.0), V(18.0)
        tr = self.make(own, lead)
        tr.observe(0.0, 1000.0, 0.0, 1.0)
        t, r = self.steady(0.0, own, lead, 5.0, 25.6, tr)
        lead.v = 10.0   # leader slows while unseen; telemetry reports it
        for k in range(20):
            tr.predict_to(t+0.1*(k+1), missing=True)
        expected = r-tr.kappa*8.0*2.0
        self.assertAlmostEqual(tr.y[0], expected, delta=0.5)
        self.assertLess(tr.range_rate(), -6.0)

    def test_wave_noise_range_estimate_is_stable(self):
        rng = np.random.default_rng(1)
        own, lead = V(18.0), V(18.0)
        tr = self.make(own, lead)
        tr.observe(0.0, 1000.0, 0.0, 1.0)
        errors = []
        t, r = 0.0, 25.6
        for _ in range(200):
            t, r = self.steady(t, own, lead, 0.1, r, tr, noise=0.4, rng=rng)
            errors.append(tr.y[0]-r)
        self.assertLess(np.std(errors[50:]), 2.0)   # raw area noise 0.4 log -> ~5 m range noise

    def test_gate_rejects_wrong_target_then_reacquires_persistent_change(self):
        own, lead = V(18.0), V(18.0)
        tr = self.make(own, lead)
        tr.observe(0.0, 1000.0, 0.0, 1.0)
        t, r = self.steady(0.0, own, lead, 3.0, 25.6, tr)
        before = tr.y[0]
        t += 0.1
        tr.observe(0.6, area_at(8.0), t, 1.0)   # another boat, far off in offset and range
        self.assertEqual(tr.gate_rejections, 1)
        self.assertAlmostEqual(tr.y[0], before, delta=0.3)
        for _ in range(4):
            t += 0.1
            tr.observe(0.6, area_at(8.0), t, 1.0)
        self.assertAlmostEqual(tr.y[0], 8.0, delta=0.5)   # 5th disagreement: re-acquire

    def test_single_clock_and_psd(self):
        own, lead = V(15.0), V(17.0)
        tr = self.make(own, lead)
        tr.observe(0.0, 1000.0, 0.0, 1.0)
        t, _ = self.steady(0.0, own, lead, 4.0, 25.6, tr)
        tr.predict_to(t+1.0, missing=True)
        y, P = tr.y.copy(), tr.Py.copy()
        tr.predict_to(t+1.0, missing=True)
        self.assertTrue(np.array_equal(y, tr.y) and np.array_equal(P, tr.Py))
        self.assertGreaterEqual(np.linalg.eigvalsh(tr.Py).min(), -1e-9)


if __name__ == '__main__':
    unittest.main()
