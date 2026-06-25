"""
Simple linear Kalman filter for 1D offset and area tracking with velocities.

State vector: [offset, offset_vel, area, area_vel]
Measurement vector: [offset, area]

This lightweight filter is intended to run per-camera stream in vision.
"""
import numpy as np

from .config import (
    KF_ADAPTIVE_MOTION_GAIN,
    KF_ADAPTIVE_RESIDUAL_GAIN,
    KF_CONF_R_MAX,
    KF_INITIAL_VEL_BLEND,
    KF_MAX_PROCESS_SCALE,
    KF_MEAS_AREA_VAR,
    KF_MEAS_OFFSET_VAR,
    KF_MIN_DET_CONF,
    KF_PROC_POS_VAR,
    KF_PROC_VEL_VAR,
)


class KalmanFilter:
    def __init__(self):
        # state x and covariance P will be lazily initialized on first measurement
        self.x = None
        self.P = None
        self.last_meas = None
        self.last_dt = None

        # process noise tuning
        self.proc_pos_var = float(KF_PROC_POS_VAR)
        self.proc_vel_var = float(KF_PROC_VEL_VAR)

        # measurement noise (offset, area)
        self.meas_offset_var = float(KF_MEAS_OFFSET_VAR)
        self.meas_area_var = float(KF_MEAS_AREA_VAR)

    def initialize(self, offset, area):
        self.x = np.array([offset, 0.0, area, 0.0], dtype=float)
        self.P = np.diag([0.05, 0.5, max(10.0, area * 0.3), 1.0])
        self.last_meas = np.array([offset, area], dtype=float)
        self.last_dt = None

    def _adaptive_measurement_scale(self, residual):
        """Scale measurement noise up for large innovations (soft outlier rejection)."""
        if residual is None or self.x is None:
            return 1.0
        offset_residual = abs(float(residual[0]))
        area_ref = max(1.0, abs(float(self.x[2])))
        area_residual = abs(float(residual[1])) / area_ref
        motion_term = (offset_residual / 0.10) + (area_residual / 0.30)
        scale = 1.0 + float(KF_ADAPTIVE_RESIDUAL_GAIN) * motion_term
        return min(float(KF_MAX_PROCESS_SCALE), max(1.0, scale))

    def _adaptive_process_scale(self, dt, residual=None):
        scale = 1.0

        if dt > 1e-3:
            scale += min(3.0, float(dt) / 0.10)

        if residual is not None:
            offset_residual = abs(float(residual[0]))
            area_residual = abs(float(residual[1])) / max(1.0, abs(float(self.x[2])) if self.x is not None else 1.0)
            motion_term = (offset_residual / 0.08) + (area_residual / 0.20)
            scale += float(KF_ADAPTIVE_MOTION_GAIN) * motion_term

        if self.last_meas is not None and dt > 1e-3:
            prev_offset, prev_area = self.last_meas
            cur_offset = float(self.x[0]) if self.x is not None else float(prev_offset)
            cur_area = float(self.x[2]) if self.x is not None else float(prev_area)
            d_offset = abs(cur_offset - float(prev_offset))
            d_area = abs(cur_area - float(prev_area)) / max(1.0, abs(float(prev_area)))
            scale += 0.75 * ((d_offset / 0.08) + (d_area / 0.20))

        return min(float(KF_MAX_PROCESS_SCALE), max(1.0, scale))

    def predict(self, dt):
        if self.x is None:
            return
        F = np.array(
            [
                [1.0, dt, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, dt],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )

        process_scale = self._adaptive_process_scale(dt)
        q = np.array([self.proc_pos_var, self.proc_vel_var, self.proc_pos_var, self.proc_vel_var])
        Q = np.diag(q) * process_scale * max(1.0, dt)

        self.x = F.dot(self.x)
        self.P = F.dot(self.P).dot(F.T) + Q

    def update(self, meas_offset, meas_area, det_conf=1.0):
        if self.x is None:
            self.initialize(meas_offset, meas_area)
            return

        # If we have a previous measurement, use the measured delta to nudge
        # the velocity state toward the observed motion before the correction.
        if self.last_meas is not None and self.last_dt is not None and self.last_dt > 1e-3:
            prev_offset, prev_area = self.last_meas
            meas_offset_vel = (float(meas_offset) - float(prev_offset)) / float(self.last_dt)
            meas_area_vel = (float(meas_area) - float(prev_area)) / float(self.last_dt)
            self.x[1] = (1.0 - float(KF_INITIAL_VEL_BLEND)) * self.x[1] + float(KF_INITIAL_VEL_BLEND) * meas_offset_vel
            self.x[3] = (1.0 - float(KF_INITIAL_VEL_BLEND)) * self.x[3] + float(KF_INITIAL_VEL_BLEND) * meas_area_vel

        # measurement matrix
        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]])
        z = np.array([meas_offset, meas_area], dtype=float)

        residual = z - H.dot(self.x)
        measurement_scale = self._adaptive_measurement_scale(residual)
        # Low YOLO confidence → inflate R so the filter trusts the detection less.
        # conf=1.0 → no change; conf=0.25 → up to KF_CONF_R_MAX × R.
        conf_r_scale = min(1.0 / max(float(det_conf), float(KF_MIN_DET_CONF)), float(KF_CONF_R_MAX))
        R = np.diag([self.meas_offset_var, self.meas_area_var]) * min(measurement_scale * conf_r_scale, float(KF_MAX_PROCESS_SCALE))

        S = H.dot(self.P).dot(H.T) + R
        K = self.P.dot(H.T).dot(np.linalg.inv(S))

        y = residual
        self.x = self.x + K.dot(y)
        I = np.eye(self.P.shape[0])
        self.P = (I - K.dot(H)).dot(self.P)
        self.last_meas = np.array([meas_offset, meas_area], dtype=float)

    def set_last_dt(self, dt):
        self.last_dt = max(0.0, float(dt))

    def state(self):
        if self.x is None:
            return None
        return float(self.x[0]), float(self.x[1]), float(self.x[2]), float(self.x[3])
