"""Candidate d04 estimator: vision + own-speed + leader-speed-telemetry range Kalman filter.

e01 failure taxonomy (FINAL_REPORT.md): catastrophic runs were longitudinal —
followers fell behind when the leader accelerated, or overshot to 9-17 m when it
decelerated in huge waves (box area jitters +-50 %), then lost the leader out of
frame or reacquired another object. Range is therefore estimated with a process
model driven by KNOWN inputs, corrected by vision:

    r' = kappa * (v_leader - v_own) + b,     b' = white noise (geometry/heading bias)

v_own is ego telemetry; v_leader is the leader-speed telemetry the controller
already receives in every arm (communicated scalar, no pose/ID/future path).
Measurement: pinhole range c/sqrt(area) as in d03. Innovation gating: a detection
whose normalized innovation exceeds `gate_sigma` in offset or range is treated as
a wrong/partial target and not fused; after `max_rejects` consecutive rejections
the track is re-initialized on the new measurement (prevents permanent lockout).
"""
from dataclasses import dataclass
import math
import numpy as np
from robust_tracker import RobustTracker
from ego_tracker import EgoRangeTracker


@dataclass(frozen=True)
class FusionTuning:
    range_model_density: float = 0.5   # m^2/s^3 on r (unmodelled relative motion)
    bias_density: float = 0.2           # (m/s)^2/s on b
    initial_bias_std: float = 1.0
    gate_sigma: float = 4.0
    max_rejects: int = 5
    gate_after_s: float = 1.0


class FusionRangeTracker(EgoRangeTracker):
    def __init__(self, *args, leader=None, fusion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.leader = leader or (lambda: None)
        self.fusion = fusion or FusionTuning()
        self.rejects = 0
        self.gate_rejections = 0
        self.created = None

    def _leader_speed(self):
        v = self.leader()
        return None if v is None or not math.isfinite(v) else abs(float(v))

    def range_rate(self):
        vF, vL = self._speed(), self._leader_speed()
        rel = 0.0 if vF is None or vL is None else self.kappa*(vL-vF)
        return float(rel+self.y[1])

    def initialize(self, offset, area, now=0.0):
        super().initialize(offset, area, now)
        self.y[1] = 0.0
        self.Py = np.diag([self.Py[0, 0], self.fusion.initial_bias_std**2])
        self.created = float(now)
        self.rejects = 0
        self._sync_area()

    def predict_to(self, now, missing=False):
        if self.x is None:
            return
        dt = float(now)-self.time
        RobustTracker.predict_to(self, now, missing)   # offset channel + the single clock
        if dt <= 1e-8 or self.y is None:
            return
        F = np.array([[1.0, dt], [0.0, 1.0]])
        vF, vL = self._speed(), self._leader_speed()
        rel = 0.0 if vF is None or vL is None else self.kappa*(vL-vF)
        self.y = F @ self.y + np.array([rel*dt, 0.0])
        Q = np.diag([self.fusion.range_model_density*dt, self.fusion.bias_density*dt])
        self.Py = F @ self.Py @ F.T + Q
        self._clip_range()
        self._sync_area()

    def _sync_area(self):
        r = self.y[0]
        self.x[1, 0] = math.log((self.c/r)**2)
        self.x[1, 1] = -2.0*self.range_rate()/r
        self._bounds()

    def _range_R(self, confidence):
        sr = max(self.y[0]*self.ego_tuning.range_log_noise, self.y[0]*0.5*math.sqrt(self.noise_var[1]))
        return sr**2/max(0.25, min(1.0, float(confidence)))**2

    def observe(self, offset, area, now, confidence=1.0):
        if self.x is None or self.y is None or not self.kalman:
            return super().observe(offset, area, now, confidence)
        self.predict_to(now, missing=(float(now)-self.last_seen) > 0.25)
        self._anchor()
        z = self._range(area)
        R = self._range_R(confidence)
        nu_r = (z-self.y[0])/math.sqrt(self.Py[0, 0]+R)
        R_off = max(self.tuning.offset_noise**2, self.noise_var[0])/max(0.25, min(1.0, float(confidence)))**2
        nu_o = (float(offset)-self.x[0, 0])/math.sqrt(self.P[0, 0, 0]+R_off)
        established = self.created is not None and float(now)-self.created > self.fusion.gate_after_s
        if established and max(abs(nu_r), abs(nu_o)) > self.fusion.gate_sigma:
            self.rejects += 1
            self.gate_rejections += 1
            if self.rejects < self.fusion.max_rejects:
                return   # treated as missing: no fusion, lifetime not extended
            bias = self.y[1]
            self.initialize(offset, area, now)   # persistent disagreement: re-acquire
            self.y[1] = bias
            return
        self.rejects = 0
        RobustTracker.observe(self, offset, area, now, confidence)   # offset channel, last_seen
        R = self._range_R(confidence)
        residual = z-self.y[0]
        S = self.Py[0, 0]+R
        weight = min(1.0, self.ego_tuning.huber_sigma*math.sqrt(S)/max(abs(residual), 1e-12))
        R /= weight**2
        K = self.Py[:, 0]/(self.Py[0, 0]+R)
        self.y = self.y+K*residual
        A = np.eye(2)-np.outer(K, [1.0, 0.0])
        self.Py = A @ self.Py @ A.T + R*np.outer(K, K)
        self.Py = (self.Py+self.Py.T)/2
        self._clip_range()
        self._sync_area()
