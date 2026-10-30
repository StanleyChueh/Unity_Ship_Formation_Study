"""Candidate d04: d03 ego-range Kalman with maneuver-adaptive innovation handling.

d03 development (C10 seed 1701) showed the range channel lagging a genuine
rapid closure by ~10x in area: Huber weighting treated every large residual of a
sustained approach as an outlier while the follower kept 0.8 throttle toward a
near-collision. Robust weighting should reject ISOLATED wrong/partial boxes, not
a persistent same-sign innovation sequence, which indicates a maneuver.

Rule (same idea as the d02 offset channel's Q boost, now also releasing Huber):
consecutive same-sign normalized innovations |v| > 1 form a run. From the second
such innovation on, the Huber weight is 1 and the leader-acceleration density is
boosted (x(1+8(run-1)), capped at x50). An isolated |v| > 3 is still downweighted.
"""
import math
import numpy as np
from ego_tracker import EgoRangeTracker


class ManeuverRangeTracker(EgoRangeTracker):
    max_boost = 50.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.range_run = 0

    def _boost(self):
        return min(self.max_boost, 1.0+8.0*max(0, abs(self.range_run)-1))

    def predict_to(self, now, missing=False):
        if self.x is None:
            return
        dt = float(now)-self.time
        base = self.ego_tuning
        if dt > 1e-8 and self.y is not None and self._boost() > 1.0:
            # Extra acceleration uncertainty while a maneuver is indicated.
            extra = base.leader_accel_density*(self._boost()-1.0)
            super().predict_to(now, missing)
            self.Py = self.Py+extra*np.array([[dt**3/3, dt**2/2], [dt**2/2, dt]])
            return
        super().predict_to(now, missing)

    def observe(self, offset, area, now, confidence=1.0):
        fresh = self.x is None
        if fresh or self.y is None or not self.kalman:
            return super().observe(offset, area, now, confidence)
        # Run the inherited offset update and propagation, but do our own range update.
        # RobustTracker.observe: shared clock/propagation and the offset channel.
        super(EgoRangeTracker, self).observe(offset, area, now, confidence)
        self._anchor()
        z = self._range(area)
        confidence = max(0.25, min(1.0, float(confidence)))
        sr = max(self.y[0]*self.ego_tuning.range_log_noise, self.y[0]*0.5*math.sqrt(self.noise_var[1]))
        R = sr**2/confidence**2
        residual = z-self.y[0]
        S = self.Py[0, 0]+R
        v = residual/math.sqrt(S)
        if abs(v) > 1.0:
            sign = 1 if v > 0 else -1
            self.range_run = self.range_run+sign if self.range_run*sign > 0 else sign
        else:
            self.range_run = 0
        if abs(self.range_run) < 2:
            weight = min(1.0, self.ego_tuning.huber_sigma*math.sqrt(S)/max(abs(residual), 1e-12))
            R /= weight**2
        K = self.Py[:, 0]/(self.Py[0, 0]+R)
        self.y = self.y+K*residual
        A = np.eye(2)-np.outer(K, [1.0, 0.0])
        self.Py = A @ self.Py @ A.T + R*np.outer(K, K)
        self.Py = (self.Py+self.Py.T)/2
        self._clip_range()
        self._sync_area()
