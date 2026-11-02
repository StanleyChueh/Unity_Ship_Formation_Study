"""Vision-only range Kalman filter: leader speed is ESTIMATED, never received.

Same structure and innovation gating as FusionRangeTracker, but with the leader
speed moved from a known input into the filter state:

    r' = w - kappa * v_own,     w' = white noise,     w = kappa * v_leader

so the leader's speed is inferred purely from how the box size changes over time
(plus the follower's own speed, which is what makes the two motions separable).
Measurement: pinhole range c/sqrt(area). The `leader` argument is deliberately
discarded, so no leader telemetry can reach this filter.

OwnSpeedModel replaces the own-speed SENSOR for the strict arm: it integrates the
commanded throttle through the known plant (first-order lag), so the only inputs
left are the camera and the follower's own commands.
"""
import numpy as np
from robust_tracker import RobustTracker
from fusion_tracker import FusionRangeTracker


class VisionRangeTracker(FusionRangeTracker):
    def __init__(self, *args, leader=None, **kwargs):
        super().__init__(*args, leader=None, **kwargs)

    def _own(self):
        return self._speed() or 0.0

    def range_rate(self):
        return float(self.y[1]-self.kappa*self._own())

    def leader_speed(self):
        return max(0.0, float(self.y[1])/self.kappa)

    def initialize(self, offset, area, now=0.0):
        super().initialize(offset, area, now)
        self.y[1] = self.kappa*self._own()
        self.Py[1, 1] = self.ego_tuning.initial_w_std**2
        self._sync_area()

    def predict_to(self, now, missing=False):
        if self.x is None:
            return
        dt = float(now)-self.time
        RobustTracker.predict_to(self, now, missing)   # offset channel + the single clock
        if dt <= 1e-8 or self.y is None:
            return
        F = np.array([[1.0, dt], [0.0, 1.0]])
        q = self.ego_tuning.leader_accel_density
        Q = q*np.array([[dt**3/3, dt**2/2], [dt**2/2, dt]])+np.diag([self.fusion.range_model_density*dt, 0.0])
        self.y = F @ self.y+np.array([-self.kappa*self._own()*dt, 0.0])
        self.Py = F @ self.Py @ F.T+Q
        self._clip_range()
        self._sync_area()


class OwnSpeedModel:
    """Own speed from commanded throttle: v' = (u/ff - v)/tau, no sensor."""

    def __init__(self, ff=0.043, tau=0.5):
        self.ff, self.tau = float(ff), float(tau)
        self.v, self.t = 0.0, None

    def step(self, throttle, now):
        if self.t is not None and now > self.t:
            a = min(1.0, (now-self.t)/self.tau)
            self.v += a*(float(throttle)/self.ff-self.v)
        self.t = float(now)
        return self.v
