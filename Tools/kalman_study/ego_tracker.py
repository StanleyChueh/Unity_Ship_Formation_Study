"""Candidate d03: d02 image-offset Kalman channel plus an ego-motion range channel.

The bbox-area channel of d02 extrapolates log area with a constant rate. During
a censored interval the follower's own speed keeps changing under closed-loop
control, so the true box shrinks/grows for reasons a model-free extrapolator
cannot see (d02 gap forecasts were worse than EMA in area). Here the area is
converted to range with the pinhole relation r = c / sqrt(area), and range is
propagated with a process model that uses OWN-SHIP speed as a known input:

    r' = w - kappa * v_follower,     w' = white acceleration noise

w is the unknown leader contribution to range rate (approximately kappa times
leader speed). It is estimated only from image measurements; no leader speed,
pose or identity enters this filter. kappa = back / range of the DESIGNED
formation slot; c comes from the controller's own visual calibration area at
that designed range. Inputs: selected bbox, detector confidence, own speed.
"""
from dataclasses import dataclass
import math
import numpy as np
from robust_tracker import RobustTracker, Tuning


@dataclass(frozen=True)
class EgoTuning:
    formation_range_m: float = 25.6      # designed slot range (spawn geometry)
    formation_back_m: float = 22.0       # designed along-track separation
    range_log_noise: float = 0.08        # 1-sigma of 0.5*log(area) jitter
    leader_accel_density: float = 1.5    # (m/s^2)^2/Hz on w
    initial_w_std: float = 3.0
    huber_sigma: float = 3.0
    min_range_m: float = 4.0
    max_range_m: float = 400.0


class EgoRangeTracker(RobustTracker):
    """Offset: inherited d02 Kalman channel. Area: range Kalman with own-speed input."""

    def __init__(self, kalman=True, tuning=None, ego=None, ego_tuning=None, reference_area=None):
        super().__init__(kalman=kalman, tuning=tuning)
        self.ego_tuning = ego_tuning or EgoTuning()
        self.ego = ego or (lambda: None)       # returns own speed (m/s) or None
        self.reference_area = reference_area   # returns calibrated area at design range or None
        self.c = None
        self.y = None   # [range, w]
        self.Py = None
        self.kappa = self.ego_tuning.formation_back_m/self.ego_tuning.formation_range_m

    def _speed(self):
        v = self.ego()
        return None if v is None or not math.isfinite(v) else abs(float(v))

    def initialize(self, offset, area, now=0.0):
        super().initialize(offset, area, now)
        ref = self._reference()
        self.anchored = ref is not None
        self.c = self.ego_tuning.formation_range_m*math.sqrt(ref if ref is not None else max(float(area), 1.0))
        r = self._range(area)
        v = self._speed() or 0.0
        self.y = np.array([r, self.kappa*v])
        sr = r*self.ego_tuning.range_log_noise
        self.Py = np.diag([sr**2, self.ego_tuning.initial_w_std**2])
        self._sync_area()

    def _reference(self):
        ref = self.reference_area() if self.reference_area else None
        return float(ref) if ref and ref > 1.0 else None

    def _anchor(self):
        """Adopt the controller's calibration area once locked, keeping the current area estimate."""
        if self.anchored:
            return
        ref = self._reference()
        if ref is None:
            return
        scale = self.ego_tuning.formation_range_m*math.sqrt(ref)/self.c
        self.c *= scale
        self.y = self.y*scale
        self.Py = self.Py*scale**2
        self.anchored = True

    def _range(self, area):
        r = self.c/math.sqrt(max(float(area), 1.0))
        return min(max(r, self.ego_tuning.min_range_m), self.ego_tuning.max_range_m)

    def predict_to(self, now, missing=False):
        if self.x is None:
            return
        dt = float(now)-self.time
        super().predict_to(now, missing)   # offset channel (and unused log-area block)
        if dt <= 1e-8 or self.y is None:
            return
        v = self._speed()
        if v is None:
            v = self.y[1]/self.kappa  # no ego telemetry: assume zero range rate
        F = np.array([[1.0, dt], [0.0, 1.0]])
        B = np.array([-self.kappa*dt, 0.0])
        q = self.ego_tuning.leader_accel_density
        Q = q*np.array([[dt**3/3, dt**2/2], [dt**2/2, dt]])
        self.y = F @ self.y + B*v
        self.Py = F @ self.Py @ F.T + Q
        self._clip_range()
        self._sync_area()

    def observe(self, offset, area, now, confidence=1.0):
        fresh = self.x is None
        super().observe(offset, area, now, confidence)  # offset Kalman update / initialization
        if fresh or self.y is None:
            return
        self._anchor()
        z = self._range(area)
        confidence = max(0.25, min(1.0, float(confidence)))
        if self.kalman:
            sr = self.y[0]*self.ego_tuning.range_log_noise
            # Reuse the adaptive log-area variance learned by the d02 channel:
            # 0.5*log(area) noise maps to relative range noise.
            sr = max(sr, self.y[0]*0.5*math.sqrt(self.noise_var[1]))
            R = sr**2/confidence**2
            residual = z-self.y[0]
            S = self.Py[0, 0]+R
            weight = min(1.0, self.ego_tuning.huber_sigma*math.sqrt(S)/max(abs(residual), 1e-12))
            R /= weight**2
            K = self.Py[:, 0]/(self.Py[0, 0]+R)
            self.y = self.y+K*residual
            A = np.eye(2)-np.outer(K, [1.0, 0.0])
            self.Py = A @ self.Py @ A.T + R*np.outer(K, K)
            self.Py = (self.Py+self.Py.T)/2
        else:
            self.y[0] = z
        self._clip_range()
        self._sync_area()

    def _clip_range(self):
        self.y[0] = min(max(self.y[0], self.ego_tuning.min_range_m), self.ego_tuning.max_range_m)

    def _sync_area(self):
        """Expose range as log area so the shared adapter/controller interface is unchanged."""
        r = self.y[0]
        v = self._speed()
        rate = self.y[1]-self.kappa*(v if v is not None else self.y[1]/self.kappa)
        self.x[1, 0] = math.log((self.c/r)**2)
        self.x[1, 1] = -2.0*rate/r   # d log(area)/dt
        self._bounds()

    def range_state(self):
        return None if self.y is None else (float(self.y[0]), float(self.y[1]))
