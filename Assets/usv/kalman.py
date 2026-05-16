"""
Simple linear Kalman filter for 1D offset and area tracking with velocities.

State vector: [offset, offset_vel, area, area_vel]
Measurement vector: [offset, area]

This lightweight filter is intended to run per-camera stream in vision.
"""
import math
import numpy as np


class KalmanFilter:
    def __init__(self):
        # state x and covariance P will be lazily initialized on first measurement
        self.x = None
        self.P = None

        # process noise tuning (can be adjusted from config later)
        self.proc_pos_var = 1e-3
        self.proc_vel_var = 1e-2

        # measurement noise (offset, area)
        self.meas_offset_var = 1e-2
        self.meas_area_var = 10.0

    def initialize(self, offset, area):
        self.x = np.array([offset, 0.0, area, 0.0], dtype=float)
        self.P = np.diag([0.05, 0.5, max(10.0, area * 0.3), 1.0])

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

        q = np.array([self.proc_pos_var, self.proc_vel_var, self.proc_pos_var, self.proc_vel_var])
        Q = np.diag(q) * max(1.0, dt)

        self.x = F.dot(self.x)
        self.P = F.dot(self.P).dot(F.T) + Q

    def update(self, meas_offset, meas_area):
        if self.x is None:
            self.initialize(meas_offset, meas_area)
            return

        # measurement matrix
        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]])
        z = np.array([meas_offset, meas_area], dtype=float)
        R = np.diag([self.meas_offset_var, self.meas_area_var])

        S = H.dot(self.P).dot(H.T) + R
        K = self.P.dot(H.T).dot(np.linalg.inv(S))

        y = z - H.dot(self.x)
        self.x = self.x + K.dot(y)
        I = np.eye(self.P.shape[0])
        self.P = (I - K.dot(H)).dot(self.P)

    def state(self):
        if self.x is None:
            return None
        return float(self.x[0]), float(self.x[1]), float(self.x[2]), float(self.x[3])
