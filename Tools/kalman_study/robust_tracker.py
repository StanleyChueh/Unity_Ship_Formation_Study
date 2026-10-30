"""Adaptive log-area Kalman tracker. No simulator or target ground truth inputs.

Positions are normalized image offset and log(pixel area); velocity units are per
second. predict_to() owns the only propagation clock, including reacquisition.
This module is standalone so the frozen legacy study can continue unmodified.
"""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Tuning:
    offset_noise: float = 0.025
    log_area_noise: float = 0.16
    offset_accel_spectral_density: float = 0.0025
    log_area_accel_spectral_density: float = 0.01
    noise_memory_s: float = 2.0
    coast_velocity_half_life_s: float = 4.0
    max_offset_velocity: float = 0.60
    max_log_area_velocity: float = 0.80
    huber_sigma: float = 3.0
    max_gap_s: float = 3.0


class RobustTracker:
    """Two independent CV filters with robust, confidence-aware observations.

    An EMA comparator uses the same raw inputs, coordinate representation,
    derivative bounds, coast damping and lifetime, but no covariance/Kalman gain.
    """
    def __init__(self, kalman=True, tuning=None):
        self.kalman = kalman
        self.tuning = tuning or Tuning()
        self.x = None
        self.P = None
        self.time = None
        self.last_seen = None
        self.last_z = None
        self.noise_var = np.array([self.tuning.offset_noise**2, self.tuning.log_area_noise**2])
        self.innovation = np.zeros(2)
        self.innovation_run = np.zeros(2)
        self.accepted = True
        self.last_dt = 0.1

    def initialize(self, offset, area, now=0.0):
        self.x = np.array([[float(offset), 0.0], [math.log(max(float(area), 1.0)), 0.0]])
        self.P = np.array([np.diag([self.noise_var[i], 0.04]) for i in range(2)])
        self.time = float(now)
        self.last_seen = float(now)
        self.last_z = self.x[:, 0].copy()

    @staticmethod
    def transition(dt, density):
        F = np.array([[1.0, dt], [0.0, 1.0]])
        Q = density * np.array([[dt**3/3, dt**2/2], [dt**2/2, dt]])
        return F, Q

    def predict_to(self, now, missing=False):
        if self.x is None:
            return
        dt = float(now)-self.time
        if dt < -1e-8:
            raise ValueError('Tracker timestamps must be monotonic')
        if dt <= 1e-8:
            return
        self.last_dt = dt
        for i, q in enumerate([self.tuning.offset_accel_spectral_density, self.tuning.log_area_accel_spectral_density]):
            # Sustained same-sign residuals indicate a maneuver rather than
            # alternating wave/detection jitter. Increase process noise briefly.
            boost = 1.0 + min(15.0, max(0.0, abs(self.innovation_run[i])-2.0)*3.0)
            F, Q = self.transition(dt, q*boost)
            if missing:
                decay = math.exp(-math.log(2)*dt/self.tuning.coast_velocity_half_life_s)
                F[0, 1] = self.tuning.coast_velocity_half_life_s/math.log(2)*(1-decay)
                F[1, 1] = decay
                # Undamped Q is conservative for the damped coast model.
            self.x[i] = F @ self.x[i]
            self.P[i] = F @ self.P[i] @ F.T + Q
        self.time = float(now)
        self._bounds()

    def observe(self, offset, area, now, confidence=1.0):
        values = np.array([float(offset), math.log(max(float(area), 1.0))])
        if not np.all(np.isfinite(values)) or not math.isfinite(float(now)):
            raise ValueError('Nonfinite measurement')
        if self.x is None:
            self.initialize(offset, area, now)
            return
        since = max(1e-3, float(now)-self.last_seen)
        self.predict_to(now, missing=since > 0.25)
        residual = values-self.x[:, 0]
        confidence = max(0.25, min(1.0, float(confidence)))
        base = np.array([self.tuning.offset_noise**2, self.tuning.log_area_noise**2])
        if self.kalman:
            for i in range(2):
                R = max(base[i], self.noise_var[i]) / confidence**2
                S = self.P[i, 0, 0]+R
                # Huber innovation weighting: a single wrong/partial box has
                # limited influence; a sustained maneuver is allowed by Q boost.
                weight = min(1.0, self.tuning.huber_sigma*math.sqrt(S)/max(abs(residual[i]), 1e-12))
                R /= weight**2
                K = self.P[i, :, 0]/(self.P[i, 0, 0]+R)
                self.x[i] += K*residual[i]
                A = np.eye(2)-np.outer(K, [1.0, 0.0])
                self.P[i] = A @ self.P[i] @ A.T + R*np.outer(K, K)
                self.P[i] = (self.P[i]+self.P[i].T)/2
                sign = np.sign(residual[i])
                self.innovation_run[i] = (self.innovation_run[i]+sign if sign*self.innovation_run[i]>0 else sign)
                # Learn detector/wave variance only from alternating residuals;
                # do not explain a persistent target maneuver as sensor noise.
                if residual[i]*self.innovation[i] <= 0:
                    alpha = 1-math.exp(-min(since, 0.5)/self.tuning.noise_memory_s)
                    sample = min(residual[i]**2, base[i]*25)
                    self.noise_var[i] = (1-alpha)*self.noise_var[i]+alpha*sample
                else:
                    self.noise_var[i] = max(base[i], self.noise_var[i]*math.exp(-since/8))
        else:
            # Time-normalized common EMA, with a filtered finite-difference rate.
            alpha = 1-(1-np.array([0.35, 0.25]))**(min(since, 1.0)/0.1)
            # EMA smooths measurements, not innovation against its own forecast.
            old = getattr(self, '_ema', self.last_z).copy()
            ema = old + alpha*(values-old)
            rate = (ema-old)/since
            beta = 1-math.exp(-since/0.5)
            self.x[:, 1] = (1-beta)*self.x[:, 1]+beta*rate
            self.x[:, 0] = ema
            self._ema = ema.copy()
        self.innovation = residual.copy()
        self.last_seen = float(now)
        self.last_z = values.copy()
        self._bounds()

    def _bounds(self):
        self.x[0, 1] = np.clip(self.x[0, 1], -self.tuning.max_offset_velocity, self.tuning.max_offset_velocity)
        self.x[1, 1] = np.clip(self.x[1, 1], -self.tuning.max_log_area_velocity, self.tuning.max_log_area_velocity)
        self.x[1, 0] = np.clip(self.x[1, 0], 0, math.log(1e7))

    def state(self):
        if self.x is None:
            return None
        area = math.exp(self.x[1, 0])
        return float(self.x[0, 0]), float(self.x[0, 1]), area, float(area*self.x[1, 1])

    def offset_uncertainty(self):
        return float(math.sqrt(max(0, self.P[0, 0, 0]))) if self.P is not None else None

    def confidence(self, now):
        # Common lifetime/confidence policy isolates the estimator contrast.
        return max(0.0, 1.0-max(0, now-self.last_seen)/(self.tuning.max_gap_s+0.1))
