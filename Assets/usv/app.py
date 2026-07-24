'''
    Main application logic for the USV vision-based control system.
'''

import socket
import json
import threading
import time
import csv
import os
from collections import deque
from datetime import datetime

import cv2
import math
import numpy as np

from .runtime_env import configure_qt_fontdir

configure_qt_fontdir()

from .config import (
    CAMERA_STREAMS,
    ENABLE_KALMAN_FILTER,
    PORT_LEFT_RX,
    PORT_LEFT_TX,
    PORT_RIGHT_RX,
    PORT_RIGHT_TX,
    FORMATION_MODE_RX,
    SHOW_SIDE_WINDOWS,
    SHOW_WINDOW,
    UDP_IP,
    WINDOW_SIZE,
    LEADER_AUTO_TRAJECTORY_ENABLE,
    LEADER_AUTO_TRAJECTORY_TX_PORT,
    LEADER_TRAJECTORY_MODE,
    LEADER_TRAJECTORY_SPEED,
    LEADER_TRAJECTORY_SPEED_RAMP_ENABLE,
    LEADER_TRAJECTORY_ACCELERATION,
    LEADER_TRAJECTORY_INITIAL_SPEED,
    LEADER_TRAJECTORY_CIRCLE_RADIUS,
    LEADER_TRAJECTORY_TRIANGLE_SIDE,
    LEADER_TRAJECTORY_RECT_SIZE,
    LEADER_TRAJECTORY_LOOP,
    LEADER_TRAJECTORY_RESET_ON_APPLY,
    LEADER_INITIAL_CONTROL_MODE,
    LEADER_RX,
    LEADER_WAIT_FOR_FOLLOWER_CONNECTIONS,
    LEADER_CONNECTION_WAIT_TIMEOUT_SEC,
    LEADER_CONNECTION_POLL_INTERVAL_SEC,
    LEADER_STARTUP_CMD_RETRY_COUNT,
    LEADER_STARTUP_CMD_RETRY_INTERVAL_SEC,
    FOLLOWER_THROTTLE_SPEED_RAMP_ENABLE,
    FOLLOWER_THROTTLE_RAMP_UP_RATE,
    FOLLOWER_THROTTLE_RAMP_DOWN_RATE,
    SYNC_FOLLOWER_STARTUP_ENABLE,
    SYNC_FOLLOWER_STARTUP_REQUIRE_ALL_CAMERA_STREAMS,
    SYNC_FOLLOWER_STARTUP_REQUIRE_FOLLOWER_STATE,
    SYNC_FOLLOWER_STARTUP_REQUIRE_FRONT_VISUAL_LOCK,
    SYNC_FOLLOWER_STARTUP_REQUIRE_SIDE_VISUAL_LOCK,
    SYNC_FOLLOWER_STARTUP_SETTLE_SEC,
    SYNC_FOLLOWER_STARTUP_TIMEOUT_SEC,
    SYNC_FOLLOWER_STARTUP_PACKET_STALE_SEC,
    NEAR_MISS_DISTANCE_THRESHOLD_PX,
    PREDICTION_HORIZON_SEC,
    WAVE_CONTROL_ENABLE,
    WAVE_CONTROL_PORT,
    SUIMONO_WAVE_HEIGHT,
    SUIMONO_TURBULENCE,
    SUIMONO_LARGE_WAVE_HEIGHT,
    SUIMONO_LARGE_WAVE_SCALE,
    SUIMONO_WAVE_SCALE,
    SUIMONO_FLOW_SPEED,
    SUIMONO_CAMERA_TILT_STRENGTH,
    WAVE_APPLY_AFTER_STARTUP,
)
from .control import process_boat_vision_based
from .formation_geometry import build_ideal_formation_points
from .helpers import make_status_frame
from .state import (
    boat_comm_states,
    display_frames,
    formation_targets,
    frame_lock,
    runtime_settings,
    vision_lock,
    vision_states,
)
from .vision import cv_processing_thread, tcp_camera_receiver_thread


class RunMetricsLogger:
    def __init__(self, report_interval_sec=5.0):
        self.report_interval_sec = max(1.0, float(report_interval_sec))
        self.started_at = time.time()
        self.last_report_at = self.started_at
        self.kalman_last_state = None
        self.kalman_last_time = self.started_at
        self.kalman_on_time = 0.0
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "experiment_metrics")
        )
        self.snapshots_csv_path = os.path.join(self.output_dir, f"run_{self.run_id}_snapshots.csv")
        self.summary_csv_path = os.path.join(self.output_dir, "run_summaries.csv")
        self.by_side = {
            "Left": self._make_side_state(),
            "Right": self._make_side_state(),
        }
        # Global formation metrics accumulator (shared across both sides)
        self.formation_metrics = {
            "count": 0,
            "iou_sum": 0.0,
            "iou_sq_sum": 0.0,
            "area_err_sum": 0.0,
            "centroid_offset_sum": 0.0,
            "centroid_offset_sq_sum": 0.0,
            "per_boat_rms_sum": 0.0,
            "per_boat_rms_sq_sum": 0.0,
        }
        self.last_formation_metrics = {
            "formation_iou": 0.0,
            "formation_area_err": 0.0,
            "centroid_offset_m": 0.0,
            "per_boat_rms_m": 0.0,
        }
        self._ensure_output_files()

    @staticmethod
    def _make_side_state():
        return {
            "samples": 0,
            "detected": 0,
            "leader_detected": 0,
            "follower_detected": 0,
            "stale": 0,
            "steer_delta_sum": 0.0,
            "throttle_delta_sum": 0.0,
            "prev_steer": None,
            "prev_throttle": None,
            "pred_queue": deque(),
            "pred_err_sum": 0.0,
            "pred_err_count": 0,
            "pred_flip_count": 0,
            "prev_pred_offset": None,
            "prev_pred_time": None,
            "prev_pred_sign": 0,
            # Control smoothness / saturation
            "steer_saturated_count": 0,
            "throttle_saturated_count": 0,
            "steer_max": 0.0,
            "throttle_max": 0.0,
            "last_steer": 0.0,
            "last_throttle": 0.0,
            "steer_sum": 0.0,
            "throttle_sum": 0.0,
            "steer_cmd_min": float('inf'),
            "steer_cmd_max": float('-inf'),
            "steer_abs_sum": 0.0,
            "steer_sq_sum": 0.0,
            "throttle_cmd_min": float('inf'),
            "throttle_cmd_max": float('-inf'),
            "throttle_abs_sum": 0.0,
            "throttle_sq_sum": 0.0,
            # Measured speed logging (Unity sends speed in m/s via state.speed)
            "speed_sum": 0.0,
            "speed_count": 0,
            "speed_max": 0.0,
            # Leader speed (measured) accumulators
            "leader_speed_sum": 0.0,
            "leader_speed_count": 0,
            "leader_speed_max": 0.0,
            # Distance / formation tracking
            "distance_sum": 0.0,
            "distance_count": 0,
            "min_distance": float('inf'),
            "distance_error_sum": 0.0,
            "distance_error_count": 0,
            # Formation error tracking
            "formation_error_sum": 0.0,
            "formation_error_count": 0,
            # Near-miss tracking (distance below safety threshold)
            "near_miss_count": 0,
            "near_miss_threshold": float(NEAR_MISS_DISTANCE_THRESHOLD_PX),
            # most recent world coordinates reported from Unity (meters)
            "last_x": None,
            "last_z": None,
            "last_yaw": None,
            "last_leader_x": None,
            "last_leader_z": None,
            "last_leader_yaw": None,
            "last_leader_forward_x": None,
            "last_leader_forward_z": None,
            "last_pos_error_m": 0.0,
        }

    def _ensure_output_files(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            if not os.path.exists(self.snapshots_csv_path):
                with open(self.snapshots_csv_path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(
                        [
                            "run_id",
                            "elapsed_s",
                            "kalman_enabled",
                            "side",
                            "samples",
                            "leader_det_rate_pct",
                            "follower_det_rate_pct",
                            "det_rate_pct",
                            "stale_rate_pct",
                            "dsteer_mean_abs",
                            "dthr_mean_abs",
                            "pred_mae",
                            "pred_flips",
                            "steer_saturated_pct",
                            "throttle_saturated_pct",
                            "steer_max",
                            "throttle_max",
                            "steer_cmd_mean",
                            "steer_cmd_min",
                            "steer_cmd_max",
                            "steer_cmd_mean_abs",
                            "throttle_cmd_mean",
                            "throttle_cmd_min",
                            "throttle_cmd_max",
                            "throttle_cmd_mean_abs",
                            "speed_mps",
                            "leader_speed_mps",
                            "x_m",
                            "z_m",
                            "leader_x_m",
                            "leader_z_m",
                               "formation_size_mean_side_m",
                               "formation_size_mean_leader_to_followers_m",
                            "pos_error_m",
                            "mean_distance",
                            "min_distance",
                            "distance_error_mean",
                            "mean_formation_error",
                            "near_miss_count",
                            "formation_iou",
                            "formation_area_err",
                            "centroid_offset_m",
                            "per_boat_rms_m",
                            "fps",
                        ]
                    )
            if not os.path.exists(self.summary_csv_path):
                with open(self.summary_csv_path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(
                        [
                            "run_id",
                            "timestamp",
                            "elapsed_s",
                            "kalman_on_ratio",
                            "side",
                            "samples",
                            "leader_det_rate_pct",
                            "follower_det_rate_pct",
                            "det_rate_pct",
                            "stale_rate_pct",
                            "dsteer_mean_abs",
                            "dthr_mean_abs",
                            "pred_mae",
                            "pred_flips",
                            "steer_saturated_pct",
                            "throttle_saturated_pct",
                            "steer_max",
                            "throttle_max",
                            "mean_distance",
                            "mean_speed_mps",
                            "max_speed_mps",
                            "min_distance",
                            "distance_error_mean",
                            "mean_formation_error",
                            "mean_formation_iou",
                            "std_formation_iou",
                            "mean_per_boat_rms_m",
                            "std_per_boat_rms_m",
                            "mean_centroid_offset_m",
                            "std_centroid_offset_m",
                            "near_miss_count",
                            "fps",
                        ]
                    )
        except Exception as e:
            print(f"[Metrics] WARNING: failed to initialize output files: {e}")

    def update_kalman_state(self, kalman_enabled, now):
        kalman_enabled = bool(kalman_enabled)
        if self.kalman_last_state is None:
            self.kalman_last_state = kalman_enabled
            self.kalman_last_time = now
            return

        dt = max(0.0, now - self.kalman_last_time)
        if self.kalman_last_state:
            self.kalman_on_time += dt
        self.kalman_last_state = kalman_enabled
        self.kalman_last_time = now

    def update(self, side, res, now):
        if side not in self.by_side or not res:
            return

        s = self.by_side[side]
        s["samples"] += 1

        detected = bool(res.get("detected", False))
        side_detected = bool(res.get("side_detected", False))
        stale = bool(res.get("stale", False))
        if detected:
            s["detected"] += 1
            s["leader_detected"] += 1
        if side_detected:
            s["follower_detected"] += 1
        if stale:
            s["stale"] += 1

        steer = float(res.get("steer", 0.0))
        throttle = float(res.get("throttle", 0.0))

        # record last commanded values (for snapshot plotting)
        s["last_steer"] = steer
        s["last_throttle"] = throttle
        s["steer_sum"] += steer
        s["throttle_sum"] += throttle
        # accumulate min/max/abs/sq for command summaries
        s["steer_cmd_min"] = min(s.get("steer_cmd_min", float('inf')), steer)
        s["steer_cmd_max"] = max(s.get("steer_cmd_max", float('-inf')), steer)
        s["steer_abs_sum"] += abs(steer)
        s["steer_sq_sum"] += steer * steer
        s["throttle_cmd_min"] = min(s.get("throttle_cmd_min", float('inf')), throttle)
        s["throttle_cmd_max"] = max(s.get("throttle_cmd_max", float('-inf')), throttle)
        s["throttle_abs_sum"] += abs(throttle)
        s["throttle_sq_sum"] += throttle * throttle
        
        # Track control saturation
        steer_abs = abs(steer)
        throttle_abs = abs(throttle)
        if steer_abs > 0.95:
            s["steer_saturated_count"] += 1
        if throttle_abs > 0.95:
            s["throttle_saturated_count"] += 1
        s["steer_max"] = max(s["steer_max"], steer_abs)
        s["throttle_max"] = max(s["throttle_max"], throttle_abs)
        
        if s["prev_steer"] is not None:
            s["steer_delta_sum"] += abs(steer - s["prev_steer"])
        if s["prev_throttle"] is not None:
            s["throttle_delta_sum"] += abs(throttle - s["prev_throttle"])
        s["prev_steer"] = steer
        s["prev_throttle"] = throttle

        # Record measured speeds if provided in the result (Unity sends knots fields)
        try:
            # res usually contains speed_knots and leader_speed_knots (kts)
            speed_knots = float(res.get("speed_knots", 0.0))
            leader_speed_knots = float(res.get("leader_speed_knots", 0.0))
            speed_mps = speed_knots / 1.94384 if speed_knots else float(res.get("speed_mps", 0.0))
            leader_speed_mps = leader_speed_knots / 1.94384 if leader_speed_knots else float(res.get("leader_speed_mps", 0.0))
        except Exception:
            speed_mps = float(res.get("speed_mps", 0.0))
            leader_speed_mps = float(res.get("leader_speed_mps", 0.0))

        try:
            s["speed_sum"] += float(speed_mps)
            s["speed_count"] += 1
            s["speed_max"] = max(s.get("speed_max", 0.0), float(speed_mps))
        except Exception:
            pass

        try:
            s["leader_speed_sum"] = s.get("leader_speed_sum", 0.0) + float(leader_speed_mps)
            s["leader_speed_count"] = s.get("leader_speed_count", 0) + 1
            s["leader_speed_max"] = max(s.get("leader_speed_max", 0.0), float(leader_speed_mps))
        except Exception:
            pass

        # Record latest world coordinates if provided by Unity (meters)
        try:
            if "x" in res and "z" in res:
                s["last_x"] = float(res.get("x", 0.0))
                s["last_z"] = float(res.get("z", 0.0))
            if "yaw" in res:
                s["last_yaw"] = float(res.get("yaw", 0.0))
            if "leader_x" in res and "leader_z" in res:
                # keep a short history to estimate heading from motion if leader_yaw not provided
                try:
                    s["prev_leader_x"] = s.get("last_leader_x")
                    s["prev_leader_z"] = s.get("last_leader_z")
                    s["prev_leader_time"] = s.get("last_leader_time")
                except Exception:
                    pass
                s["last_leader_x"] = float(res.get("leader_x", 0.0))
                s["last_leader_z"] = float(res.get("leader_z", 0.0))
                s["last_leader_time"] = time.time()
            if "leader_yaw" in res:
                s["last_leader_yaw"] = float(res.get("leader_yaw", 0.0))
            if "leader_forward_x" in res and "leader_forward_z" in res:
                s["last_leader_forward_x"] = float(res.get("leader_forward_x", 0.0))
                s["last_leader_forward_z"] = float(res.get("leader_forward_z", 0.0))
        except Exception:
            pass

        # Try compute formation metrics when both follower positions and leader are available
        try:
            self._compute_and_accumulate_formation_metrics()
        except Exception:
            pass

        # Track distance and formation error if available
        if detected:
            distance = float(res.get("distance", 0.0))
            formation_error = float(res.get("formation_error", 0.0))
            target_distance = float(res.get("target_distance", 0.0))
            if distance > 0:
                s["distance_sum"] += distance
                s["distance_count"] += 1
                s["min_distance"] = min(s["min_distance"], distance)
                # Track near-miss events (distance below threshold)
                if distance < s["near_miss_threshold"]:
                    s["near_miss_count"] += 1
            if distance > 0 and target_distance > 0:
                s["distance_error_sum"] += abs(distance - target_distance)
                s["distance_error_count"] += 1
            if formation_error >= 0:
                s["formation_error_sum"] += formation_error
                s["formation_error_count"] += 1

        if detected:
            measured_offset = float(res.get("offset", 0.0))

            while s["pred_queue"] and s["pred_queue"][0][0] <= now:
                _, pred_offset = s["pred_queue"].popleft()
                s["pred_err_sum"] += abs(measured_offset - pred_offset)
                s["pred_err_count"] += 1

            pred_conf = float(res.get("pred_conf", 0.0))
            pred_offset = float(res.get("pred_offset", measured_offset))
            if pred_conf > 1e-6:
                s["pred_queue"].append((now + float(PREDICTION_HORIZON_SEC), pred_offset))

            prev_pred_offset = s["prev_pred_offset"]
            prev_pred_time = s["prev_pred_time"]
            if prev_pred_offset is not None and prev_pred_time is not None:
                dt = now - prev_pred_time
                if dt > 1e-3:
                    pred_vel = (pred_offset - prev_pred_offset) / dt
                    if abs(pred_vel) > 0.01:
                        sign = 1 if pred_vel > 0 else -1
                        if s["prev_pred_sign"] != 0 and sign != s["prev_pred_sign"]:
                            s["pred_flip_count"] += 1
                        s["prev_pred_sign"] = sign

            s["prev_pred_offset"] = pred_offset
            s["prev_pred_time"] = now

    def should_report(self, now):
        if (now - self.last_report_at) >= self.report_interval_sec:
            self.last_report_at = now
            return True
        return False

    def _fmt_side(self, side):
        s = self.by_side[side]
        stats = self._compute_side_stats(s)
        return (
            f"{side}: leader={stats['leader_det_rate_pct']:5.1f}% follower={stats['follower_det_rate_pct']:5.1f}% "
            f"stale={stats['stale_rate_pct']:5.1f}% "
            f"Δsteer={stats['dsteer_mean_abs']:5.3f} Δthr={stats['dthr_mean_abs']:5.3f} "
            f"predMAE={stats['pred_mae']:5.3f} flips={int(stats['pred_flips']):4d}"
        )

    def _compute_side_stats(self, s):
        samples = max(1, int(s["samples"]))
        leader_det_rate = (100.0 * s["leader_detected"]) / samples
        follower_det_rate = (100.0 * s["follower_detected"]) / samples
        det_rate = (100.0 * s["detected"]) / samples
        stale_rate = (100.0 * s["stale"]) / samples
        steer_smooth = s["steer_delta_sum"] / samples
        throttle_smooth = s["throttle_delta_sum"] / samples
        pred_mae = (s["pred_err_sum"] / s["pred_err_count"]) if s["pred_err_count"] > 0 else 0.0
        steer_sat_pct = (100.0 * s["steer_saturated_count"]) / samples
        throttle_sat_pct = (100.0 * s["throttle_saturated_count"]) / samples
        mean_distance = (s["distance_sum"] / s["distance_count"]) if s["distance_count"] > 0 else 0.0
        min_distance = s["min_distance"] if s["min_distance"] != float('inf') else 0.0
        mean_distance_error = (s["distance_error_sum"] / s["distance_error_count"]) if s["distance_error_count"] > 0 else 0.0
        mean_formation_error = (s["formation_error_sum"] / s["formation_error_count"]) if s["formation_error_count"] > 0 else 0.0
        steer_cmd_mean = (s.get("steer_sum", 0.0) / max(1, int(s.get("samples", 1))))
        throttle_cmd_mean = (s.get("throttle_sum", 0.0) / max(1, int(s.get("samples", 1))))
        steer_cmd_min = s.get("steer_cmd_min", float('inf'))
        steer_cmd_max = s.get("steer_cmd_max", float('-inf'))
        steer_cmd_mean_abs = (s.get("steer_abs_sum", 0.0) / max(1, int(s.get("samples", 1))))
        throttle_cmd_min = s.get("throttle_cmd_min", float('inf'))
        throttle_cmd_max = s.get("throttle_cmd_max", float('-inf'))
        throttle_cmd_mean_abs = (s.get("throttle_abs_sum", 0.0) / max(1, int(s.get("samples", 1))))
        # population std (guard against small numerical errors)
        try:
            steer_sq_mean = s.get("steer_sq_sum", 0.0) / max(1, int(s.get("samples", 1)))
            steer_cmd_std = max(0.0, (steer_sq_mean - (steer_cmd_mean ** 2)) ** 0.5)
        except Exception:
            steer_cmd_std = 0.0
        try:
            thr_sq_mean = s.get("throttle_sq_sum", 0.0) / max(1, int(s.get("samples", 1)))
            throttle_cmd_std = max(0.0, (thr_sq_mean - (throttle_cmd_mean ** 2)) ** 0.5)
        except Exception:
            throttle_cmd_std = 0.0
        # Measured speed stats (m/s)
        try:
            speed_mean = (s.get("speed_sum", 0.0) / max(1, int(s.get("speed_count", 0)))) if s.get("speed_count", 0) > 0 else 0.0
        except Exception:
            speed_mean = 0.0
        try:
            speed_max = s.get("speed_max", 0.0)
        except Exception:
            speed_max = 0.0
        try:
            leader_speed_mean = (s.get("leader_speed_sum", 0.0) / max(1, int(s.get("leader_speed_count", 0)))) if s.get("leader_speed_count", 0) > 0 else 0.0
        except Exception:
            leader_speed_mean = 0.0
        try:
            leader_speed_max = s.get("leader_speed_max", 0.0)
        except Exception:
            leader_speed_max = 0.0
        try:
            pos_error_m = float(s.get("last_pos_error_m", 0.0))
        except Exception:
            pos_error_m = 0.0
        
        return {
            "samples": int(s["samples"]),
            "leader_det_rate_pct": leader_det_rate,
            "follower_det_rate_pct": follower_det_rate,
            "det_rate_pct": det_rate,
            "stale_rate_pct": stale_rate,
            "dsteer_mean_abs": steer_smooth,
            "dthr_mean_abs": throttle_smooth,
            "pred_mae": pred_mae,
            "pred_flips": int(s["pred_flip_count"]),
            "steer_saturated_pct": steer_sat_pct,
            "throttle_saturated_pct": throttle_sat_pct,
            "steer_max": s["steer_max"],
            "throttle_max": s["throttle_max"],
            "mean_distance": mean_distance,
            "min_distance": min_distance,
            "distance_error_mean": mean_distance_error,
            "mean_formation_error": mean_formation_error,
            "steer_cmd_mean": steer_cmd_mean,
            "steer_cmd_min": (0.0 if steer_cmd_min == float('inf') else steer_cmd_min),
            "steer_cmd_max": (0.0 if steer_cmd_max == float('-inf') else steer_cmd_max),
            "steer_cmd_mean_abs": steer_cmd_mean_abs,
            "steer_cmd_std": steer_cmd_std,
            "throttle_cmd_mean": throttle_cmd_mean,
            "throttle_cmd_min": (0.0 if throttle_cmd_min == float('inf') else throttle_cmd_min),
            "throttle_cmd_max": (0.0 if throttle_cmd_max == float('-inf') else throttle_cmd_max),
            "throttle_cmd_mean_abs": throttle_cmd_mean_abs,
            "throttle_cmd_std": throttle_cmd_std,
            "near_miss_count": int(s["near_miss_count"]),
            "speed_mean": speed_mean,
            "speed_max": speed_max,
            "leader_speed_mean": leader_speed_mean,
            "leader_speed_max": leader_speed_max,
            "pos_error_m": pos_error_m,
            "x_m": float(s.get("last_x", 0.0)) if s.get("last_x") is not None else 0.0,
            "z_m": float(s.get("last_z", 0.0)) if s.get("last_z") is not None else 0.0,
            "leader_x_m": float(s.get("last_leader_x", 0.0)) if s.get("last_leader_x") is not None else 0.0,
            "leader_z_m": float(s.get("last_leader_z", 0.0)) if s.get("last_leader_z") is not None else 0.0,
        }

    # ---------- Geometry helpers for formation IoU / overlap calculations ----------
    @staticmethod
    def _tri_area(pts):
        # pts: list of (x,y) tuples (3 points)
        (x1, y1), (x2, y2), (x3, y3) = pts
        return abs((x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2)) * 0.5)

    @staticmethod
    def _poly_area(poly):
        if not poly:
            return 0.0
        area = 0.0
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) * 0.5

    @staticmethod
    def _inside(p, a, b):
        # is point p inside the half-plane defined by edge a->b (left side)
        (x, y) = p
        (x1, y1) = a
        (x2, y2) = b
        return ((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) >= -1e-9

    @staticmethod
    def _compute_line_intersection(a, b, p, q):
        # intersection between line ab and pq (segments assumed to intersect)
        x1, y1 = a
        x2, y2 = b
        x3, y3 = p
        x4, y4 = q
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-12:
            return None
        px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom
        py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom
        return (px, py)

    def _sutherland_hodgman(self, subject, clipper):
        # subject and clipper are lists of (x,y) points; returns intersection polygon
        output = subject[:]
        for i in range(len(clipper)):
            input_list = output
            output = []
            A = clipper[i]
            B = clipper[(i + 1) % len(clipper)]
            if not input_list:
                break
            S = input_list[-1]
            for E in input_list:
                if self._inside(E, A, B):
                    if not self._inside(S, A, B):
                        inter = self._compute_line_intersection(S, E, A, B)
                        if inter is not None:
                            output.append(inter)
                    output.append(E)
                elif self._inside(S, A, B):
                    inter = self._compute_line_intersection(S, E, A, B)
                    if inter is not None:
                        output.append(inter)
                S = E
        return output

    def _polygon_intersection_area(self, poly_a, poly_b):
        if not poly_a or not poly_b:
            return 0.0
        inter_poly = self._sutherland_hodgman(poly_a, poly_b)
        return self._poly_area(inter_poly)

    def _compute_and_accumulate_formation_metrics(self):
        # Need both follower positions and leader position
        left = self.by_side["Left"]
        right = self.by_side["Right"]
        if left.get("last_x") is None or right.get("last_x") is None:
            return
        # leader pos: prefer left's leader fields if available
        leader_x = left.get("last_leader_x") if left.get("last_leader_x") is not None else right.get("last_leader_x")
        leader_z = left.get("last_leader_z") if left.get("last_leader_z") is not None else right.get("last_leader_z")
        leader_yaw = left.get("last_leader_yaw") if left.get("last_leader_yaw") is not None else right.get("last_leader_yaw")
        leader_forward_x = left.get("last_leader_forward_x") if left.get("last_leader_forward_x") is not None else right.get("last_leader_forward_x")
        leader_forward_z = left.get("last_leader_forward_z") if left.get("last_leader_forward_z") is not None else right.get("last_leader_forward_z")
        if leader_x is None or leader_z is None:
            return

        # Actual triangle points (order: leader, left follower, right follower)
        A = (float(leader_x), float(leader_z))
        B = (float(left.get("last_x", 0.0)), float(left.get("last_z", 0.0)))
        C = (float(right.get("last_x", 0.0)), float(right.get("last_z", 0.0)))
        actual_area = self._tri_area([A, B, C])

        # Build the ideal follower formation behind the leader. Prefer the
        # leader's trajectory tangent when it is moving so the target matches
        # the path the leader is actually following.
        try:
            s = float(LEADER_TRAJECTORY_TRIANGLE_SIDE)
        except Exception:
            s = 1.0
        side_src = left if left.get("last_leader_x") is not None else right
        prev_x = side_src.get("prev_leader_x")
        prev_z = side_src.get("prev_leader_z")
        motion_dx = None if prev_x is None else float(leader_x) - float(prev_x)
        motion_dz = None if prev_z is None else float(leader_z) - float(prev_z)
        target_pts, _ = build_ideal_formation_points(
            leader_x=leader_x,
            leader_z=leader_z,
            side_length=s,
            leader_forward_x=leader_forward_x,
            leader_forward_z=leader_forward_z,
            motion_dx=motion_dx,
            motion_dz=motion_dz,
            leader_yaw_deg=leader_yaw,
        )
        target_area = self._tri_area(target_pts)

        # Compute intersection area and IoU
        inter_area = self._polygon_intersection_area([A, B, C], target_pts)
        union_area = actual_area + target_area - inter_area if (actual_area + target_area - inter_area) > 1e-12 else 0.0
        iou = (inter_area / union_area) if union_area > 1e-12 else 0.0

        # Centroid offset (distance between centroids)
        def centroid(poly):
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            return (sum(xs) / len(xs), sum(ys) / len(ys))
        c_actual = centroid([A, B, C])
        c_target = centroid(target_pts)
        centroid_offset = math.hypot(c_actual[0] - c_target[0], c_actual[1] - c_target[1])

        # Per-boat RMS error: match leader -> leader, then assign remaining two followers to nearest target vertices
        # Build mapping
        tgt_map = list(target_pts)
        actual_map = [A, B, C]
        # leader matches leader (index 0)
        d_leader = math.hypot(A[0] - target_pts[0][0], A[1] - target_pts[0][1])
        # assign followers to remaining two
        remaining_targets = [target_pts[1], target_pts[2]]
        dist_B_t0 = math.hypot(B[0] - remaining_targets[0][0], B[1] - remaining_targets[0][1])
        dist_B_t1 = math.hypot(B[0] - remaining_targets[1][0], B[1] - remaining_targets[1][1])
        if dist_B_t0 <= dist_B_t1:
            d_B = dist_B_t0
            d_C = math.hypot(C[0] - remaining_targets[1][0], C[1] - remaining_targets[1][1])
        else:
            d_B = dist_B_t1
            d_C = math.hypot(C[0] - remaining_targets[0][0], C[1] - remaining_targets[0][1])
        rms = math.sqrt((d_leader * d_leader + d_B * d_B + d_C * d_C) / 3.0)

        # store per-side last position error (meters) for snapshot rows
        try:
            self.by_side["Left"]["last_pos_error_m"] = float(d_B)
        except Exception:
            pass
        try:
            self.by_side["Right"]["last_pos_error_m"] = float(d_C)
        except Exception:
            pass

        # area error absolute
        area_err = abs(actual_area - target_area)

        # Formation size diagnostics: mean side length and mean leader->followers distance
        # sides: AB (leader-left), AC (leader-right), BC (left-right)
        side_AB = math.hypot(A[0] - B[0], A[1] - B[1])
        side_AC = math.hypot(A[0] - C[0], A[1] - C[1])
        side_BC = math.hypot(B[0] - C[0], B[1] - C[1])
        mean_side = (side_AB + side_AC + side_BC) / 3.0
        mean_leader_to_followers = 0.5 * (side_AB + side_AC)

        # store into last_formation_metrics for snapshots/checkpoints and terminal access
        self.last_formation_metrics["formation_size_mean_side_m"] = mean_side
        self.last_formation_metrics["formation_size_mean_leader_to_followers_m"] = mean_leader_to_followers

        # accumulate global formation metrics
        fm = self.formation_metrics
        fm["count"] += 1
        fm["iou_sum"] += iou
        fm["iou_sq_sum"] += iou * iou
        fm["area_err_sum"] += area_err
        fm["centroid_offset_sum"] += centroid_offset
        fm["centroid_offset_sq_sum"] += centroid_offset * centroid_offset
        fm["per_boat_rms_sum"] += rms
        fm["per_boat_rms_sq_sum"] += rms * rms

        # remember last metrics for snapshots
        self.last_formation_metrics["formation_iou"] = iou
        self.last_formation_metrics["formation_area_err"] = area_err
        self.last_formation_metrics["centroid_offset_m"] = centroid_offset
        self.last_formation_metrics["per_boat_rms_m"] = rms

        # store formation sizes as diagnostics
        self.last_formation_metrics["formation_size_mean_side_m"] = mean_side
        self.last_formation_metrics["formation_size_mean_leader_to_followers_m"] = mean_leader_to_followers

    def draw_topdown(self, window_name="Top-Down Formation", pixels_per_meter=3.0, visual_scale=1.0):
        """Draw a simple top-down view showing actual and target triangle formation.
        - pixels_per_meter: visual scaling for rendering
        - visual_scale: multiplier applied to target formation size (post-hoc only)
        """
        try:
            left = self.by_side["Left"]
            right = self.by_side["Right"]
            if left.get("last_x") is None or right.get("last_x") is None:
                return
            leader_x = left.get("last_leader_x") if left.get("last_leader_x") is not None else right.get("last_leader_x")
            leader_z = left.get("last_leader_z") if left.get("last_leader_z") is not None else right.get("last_leader_z")
            leader_yaw = left.get("last_leader_yaw") if left.get("last_leader_yaw") is not None else right.get("last_leader_yaw")
            leader_forward_x = left.get("last_leader_forward_x") if left.get("last_leader_forward_x") is not None else right.get("last_leader_forward_x")
            leader_forward_z = left.get("last_leader_forward_z") if left.get("last_leader_forward_z") is not None else right.get("last_leader_forward_z")
            if leader_x is None or leader_z is None:
                return

            A = (float(leader_x), float(leader_z))
            B = (float(left.get("last_x", 0.0)), float(left.get("last_z", 0.0)))
            C = (float(right.get("last_x", 0.0)), float(right.get("last_z", 0.0)))

            # Build the ideal follower formation behind the leader.
            try:
                base_side = float(LEADER_TRAJECTORY_TRIANGLE_SIDE)
            except Exception:
                base_side = 1.0
            s = base_side * float(visual_scale)
            side_src = left if left.get("last_leader_x") is not None else right
            prev_x = side_src.get("prev_leader_x")
            prev_z = side_src.get("prev_leader_z")
            motion_dx = None if prev_x is None else float(leader_x) - float(prev_x)
            motion_dz = None if prev_z is None else float(leader_z) - float(prev_z)
            target_pts, _ = build_ideal_formation_points(
                leader_x=leader_x,
                leader_z=leader_z,
                side_length=s,
                leader_forward_x=leader_forward_x,
                leader_forward_z=leader_forward_z,
                motion_dx=motion_dx,
                motion_dz=motion_dz,
                leader_yaw_deg=leader_yaw,
            )

            # render
            W = 480
            H = 480
            img = 255 * np.ones((H, W, 3), dtype=np.uint8)
            cx = W // 2
            cy = H // 2
            def to_px(p):
                dx = (p[0] - A[0]) * pixels_per_meter
                # Flip vertical axis so world +z (forward/up) maps to image upwards
                dy = -(p[1] - A[1]) * pixels_per_meter
                # x->right, z->up on image
                return int(cx + dx), int(cy + dy)

            # draw target polygon (blue)
            tgt_px = [to_px(p) for p in target_pts]
            cv2.polylines(img, [np.array(tgt_px, dtype=np.int32)], isClosed=True, color=(200, 200, 255), thickness=2)
            # draw actual polygon (green)
            actual_px = [to_px(A), to_px(B), to_px(C)]
            cv2.polylines(img, [np.array(actual_px, dtype=np.int32)], isClosed=True, color=(180, 255, 180), thickness=2)
            # draw points
            cv2.circle(img, to_px(A), 5, (0, 0, 200), -1)
            cv2.circle(img, to_px(B), 5, (0, 200, 0), -1)
            cv2.circle(img, to_px(C), 5, (0, 200, 0), -1)

            # annotate sizes
            mean_side = self.last_formation_metrics.get("formation_size_mean_side_m", None)
            if mean_side is not None:
                cv2.putText(img, f"mean_side: {mean_side:.2f} m", (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            mean_lead = self.last_formation_metrics.get("formation_size_mean_leader_to_followers_m", None)
            if mean_lead is not None:
                cv2.putText(img, f"lead->f: {mean_lead:.2f} m", (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            cv2.imshow(window_name, img)
        except Exception:
            return

    def build_report_lines(self, final=False):
        elapsed = max(1e-6, time.time() - self.started_at)
        header = "[Metrics-Final]" if final else "[Metrics]"
        return [
            f"{header} elapsed={elapsed:6.1f}s",
            f"{header} {self._fmt_side('Left')}",
            f"{header} {self._fmt_side('Right')}",
        ]

    def write_periodic_snapshot(self, now, kalman_enabled, fps=0.0):
        try:
            elapsed = max(0.0, now - self.started_at)
            with open(self.snapshots_csv_path, "a", newline="") as f:
                w = csv.writer(f)
                for side in ("Left", "Right"):
                    stats = self._compute_side_stats(self.by_side[side])
                    w.writerow(
                        [
                            self.run_id,
                            f"{elapsed:.3f}",
                            int(bool(kalman_enabled)),
                            side,
                            stats["samples"],
                            f"{stats['leader_det_rate_pct']:.6f}",
                            f"{stats['follower_det_rate_pct']:.6f}",
                            f"{stats['det_rate_pct']:.6f}",
                            f"{stats['stale_rate_pct']:.6f}",
                            f"{stats['dsteer_mean_abs']:.6f}",
                            f"{stats['dthr_mean_abs']:.6f}",
                            f"{stats['pred_mae']:.6f}",
                            stats["pred_flips"],
                            f"{stats['steer_saturated_pct']:.6f}",
                            f"{stats['throttle_saturated_pct']:.6f}",
                            f"{stats['steer_max']:.6f}",
                            f"{stats['throttle_max']:.6f}",
                            f"{stats['steer_cmd_mean']:.6f}",
                            f"{stats['steer_cmd_min']:.6f}",
                            f"{stats['steer_cmd_max']:.6f}",
                            f"{stats['steer_cmd_mean_abs']:.6f}",
                            f"{stats['throttle_cmd_mean']:.6f}",
                            f"{stats['throttle_cmd_min']:.6f}",
                            f"{stats['throttle_cmd_max']:.6f}",
                            f"{stats['throttle_cmd_mean_abs']:.6f}",
                            f"{stats['speed_mean']:.6f}",
                            f"{stats['leader_speed_mean']:.6f}",
                            f"{stats.get('x_m', 0.0):.6f}",
                            f"{stats.get('z_m', 0.0):.6f}",
                            f"{stats.get('leader_x_m', 0.0):.6f}",
                            f"{stats.get('leader_z_m', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('formation_size_mean_side_m', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('formation_size_mean_leader_to_followers_m', 0.0):.6f}",
                            f"{stats.get('pos_error_m', 0.0):.6f}",
                            f"{stats['mean_distance']:.6f}",
                            f"{stats['min_distance']:.6f}",
                            f"{stats['distance_error_mean']:.6f}",
                            f"{stats['mean_formation_error']:.6f}",
                            stats["near_miss_count"],
                            f"{self.last_formation_metrics.get('formation_iou', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('formation_area_err', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('centroid_offset_m', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('per_boat_rms_m', 0.0):.6f}",
                            f"{fps:.2f}",
                        ]
                    )
        except Exception as e:
            print(f"[Metrics] WARNING: failed to write periodic snapshot: {e}")

    def write_checkpoint(self, now, kalman_enabled, tag=None):
        """Write a standalone run snapshot + summary using current in-memory stats.
        This creates a new run_id (timestamped) so checkpoints can be compared
        as independent runs in post-processing.
        """
        try:
            # generate a standalone run id
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_run_id = f"{stamp}"

            # snapshot file for this checkpoint
            snapshot_path = os.path.join(self.output_dir, f"run_{new_run_id}_snapshots.csv")
            summary_path = self.summary_csv_path

            # write snapshot CSV (single entry per side)
            with open(snapshot_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "run_id",
                        "elapsed_s",
                        "kalman_enabled",
                        "side",
                        "samples",
                        "leader_det_rate_pct",
                        "follower_det_rate_pct",
                        "det_rate_pct",
                        "stale_rate_pct",
                        "dsteer_mean_abs",
                        "dthr_mean_abs",
                        "pred_mae",
                        "pred_flips",
                        "steer_saturated_pct",
                        "throttle_saturated_pct",
                        "steer_max",
                        "throttle_max",
                        "steer_cmd_mean",
                        "steer_cmd_min",
                        "steer_cmd_max",
                        "steer_cmd_mean_abs",
                        "throttle_cmd_mean",
                        "throttle_cmd_min",
                        "throttle_cmd_max",
                        "throttle_cmd_mean_abs",
                        "speed_mps",
                        "leader_speed_mps",
                        "x_m",
                        "z_m",
                        "leader_x_m",
                        "leader_z_m",
                        "formation_size_mean_side_m",
                        "formation_size_mean_leader_to_followers_m",
                        "pos_error_m",
                        "mean_distance",
                        "min_distance",
                        "distance_error_mean",
                        "mean_formation_error",
                        "formation_iou",
                        "formation_area_err",
                        "centroid_offset_m",
                        "per_boat_rms_m",
                        "near_miss_count",
                        "fps",
                    ]
                )
                elapsed = max(1e-6, now - self.started_at)
                for side in ("Left", "Right"):
                    stats = self._compute_side_stats(self.by_side[side])
                    w.writerow(
                        [
                            new_run_id,
                            f"{elapsed:.3f}",
                            int(bool(kalman_enabled)),
                            side,
                            stats["samples"],
                            f"{stats['leader_det_rate_pct']:.6f}",
                            f"{stats['follower_det_rate_pct']:.6f}",
                            f"{stats['det_rate_pct']:.6f}",
                            f"{stats['stale_rate_pct']:.6f}",
                            f"{stats['dsteer_mean_abs']:.6f}",
                            f"{stats['dthr_mean_abs']:.6f}",
                            f"{stats['pred_mae']:.6f}",
                            stats["pred_flips"],
                            f"{stats['steer_saturated_pct']:.6f}",
                            f"{stats['throttle_saturated_pct']:.6f}",
                            f"{stats['steer_max']:.6f}",
                            f"{stats['throttle_max']:.6f}",
                            f"{stats['steer_cmd_mean']:.6f}",
                            f"{stats['steer_cmd_min']:.6f}",
                            f"{stats['steer_cmd_max']:.6f}",
                            f"{stats['steer_cmd_mean_abs']:.6f}",
                            f"{stats['throttle_cmd_mean']:.6f}",
                            f"{stats['throttle_cmd_min']:.6f}",
                            f"{stats['throttle_cmd_max']:.6f}",
                            f"{stats['throttle_cmd_mean_abs']:.6f}",
                            f"{stats['speed_mean']:.6f}",
                            f"{stats['leader_speed_mean']:.6f}",
                            f"{stats.get('x_m', 0.0):.6f}",
                            f"{stats.get('x_m', 0.0):.6f}",
                            f"{stats.get('z_m', 0.0):.6f}",
                            f"{stats.get('leader_x_m', 0.0):.6f}",
                            f"{stats.get('leader_z_m', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('formation_size_mean_side_m', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('formation_size_mean_leader_to_followers_m', 0.0):.6f}",
                            f"{stats.get('pos_error_m', 0.0):.6f}",
                            f"{stats.get('pos_error_m', 0.0):.6f}",
                            f"{stats['mean_distance']:.6f}",
                            f"{stats['min_distance']:.6f}",
                            f"{stats['distance_error_mean']:.6f}",
                            f"{stats['mean_formation_error']:.6f}",
                            f"{self.last_formation_metrics.get('formation_iou', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('formation_area_err', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('centroid_offset_m', 0.0):.6f}",
                            f"{self.last_formation_metrics.get('per_boat_rms_m', 0.0):.6f}",
                            stats["near_miss_count"],
                            "0.0",
                        ]
                    )

            # append a summary row to the global summaries CSV so plotting tools can pick it up
            try:
                kalman_on_time = float(self.kalman_on_time)
                kalman_on_ratio = kalman_on_time / max(1e-6, elapsed)
                timestamp = datetime.now().isoformat(timespec="seconds")
                with open(summary_path, "a", newline="") as f:
                    w = csv.writer(f)
                    for side in ("Left", "Right"):
                        stats = self._compute_side_stats(self.by_side[side])
                        # compute aggregated formation metrics (mean ± std) from global accumulators
                        fm = self.formation_metrics
                        if fm.get("count", 0) > 0:
                            cnt = fm["count"]
                            mean_iou = fm["iou_sum"] / cnt
                            std_iou = max(0.0, (fm["iou_sq_sum"] / cnt - mean_iou * mean_iou)) ** 0.5
                            mean_rms = fm["per_boat_rms_sum"] / cnt
                            std_rms = max(0.0, (fm["per_boat_rms_sq_sum"] / cnt - mean_rms * mean_rms)) ** 0.5
                            mean_cent = fm["centroid_offset_sum"] / cnt
                            std_cent = max(0.0, (fm["centroid_offset_sq_sum"] / cnt - mean_cent * mean_cent)) ** 0.5
                        else:
                            mean_iou = std_iou = mean_rms = std_rms = mean_cent = std_cent = 0.0

                        w.writerow(
                            [
                                new_run_id,
                                timestamp,
                                f"{elapsed:.3f}",
                                f"{kalman_on_ratio:.6f}",
                                side,
                                stats["samples"],
                                f"{stats['det_rate_pct']:.6f}",
                                f"{stats['stale_rate_pct']:.6f}",
                                f"{stats['dsteer_mean_abs']:.6f}",
                                f"{stats['dthr_mean_abs']:.6f}",
                                f"{stats['pred_mae']:.6f}",
                                int(stats["pred_flips"]),
                                f"{stats['steer_saturated_pct']:.6f}",
                                f"{stats['throttle_saturated_pct']:.6f}",
                                f"{stats['steer_max']:.6f}",
                                f"{stats['throttle_max']:.6f}",
                                f"{stats['mean_distance']:.6f}",
                                f"{stats['speed_mean']:.6f}",
                                f"{stats['speed_max']:.6f}",
                                f"{stats['min_distance']:.6f}",
                                f"{stats['distance_error_mean']:.6f}",
                                f"{stats['mean_formation_error']:.6f}",
                                f"{mean_iou:.6f}",
                                f"{std_iou:.6f}",
                                f"{mean_rms:.6f}",
                                f"{std_rms:.6f}",
                                f"{mean_cent:.6f}",
                                f"{std_cent:.6f}",
                                stats["near_miss_count"],
                                "0.0",
                            ]
                        )
                print(f"[Metrics] Checkpoint saved snapshots: {snapshot_path}")
                print(f"[Metrics] Checkpoint appended summary: {summary_path} (run_id={new_run_id})")
            except Exception as e:
                print(f"[Metrics] WARNING: failed to write checkpoint summary: {e}")
        except Exception as e:
            print(f"[Metrics] WARNING: failed to create checkpoint: {e}")

    def write_final_summary(self, now):
        try:
            self.update_kalman_state(self.kalman_last_state, now)
            elapsed = max(1e-6, now - self.started_at)
            kalman_on_ratio = self.kalman_on_time / elapsed
            timestamp = datetime.now().isoformat(timespec="seconds")
            with open(self.summary_csv_path, "a", newline="") as f:
                w = csv.writer(f)
                for side in ("Left", "Right"):
                    stats = self._compute_side_stats(self.by_side[side])
                    # compute aggregated formation metrics (mean ± std)
                    fm = self.formation_metrics
                    if fm.get("count", 0) > 0:
                        cnt = fm["count"]
                        mean_iou = fm["iou_sum"] / cnt
                        std_iou = max(0.0, (fm["iou_sq_sum"] / cnt - mean_iou * mean_iou)) ** 0.5
                        mean_rms = fm["per_boat_rms_sum"] / cnt
                        std_rms = max(0.0, (fm["per_boat_rms_sq_sum"] / cnt - mean_rms * mean_rms)) ** 0.5
                        mean_cent = fm["centroid_offset_sum"] / cnt
                        std_cent = max(0.0, (fm["centroid_offset_sq_sum"] / cnt - mean_cent * mean_cent)) ** 0.5
                    else:
                        mean_iou = std_iou = mean_rms = std_rms = mean_cent = std_cent = 0.0

                    w.writerow([
                        self.run_id,
                        timestamp,
                        f"{elapsed:.3f}",
                        f"{kalman_on_ratio:.6f}",
                        side,
                        stats["samples"],
                        f"{stats['leader_det_rate_pct']:.6f}",
                        f"{stats['follower_det_rate_pct']:.6f}",
                        f"{stats['det_rate_pct']:.6f}",
                        f"{stats['stale_rate_pct']:.6f}",
                        f"{stats['dsteer_mean_abs']:.6f}",
                        f"{stats['dthr_mean_abs']:.6f}",
                        f"{stats['pred_mae']:.6f}",
                        stats["pred_flips"],
                        f"{stats['steer_saturated_pct']:.6f}",
                        f"{stats['throttle_saturated_pct']:.6f}",
                        f"{stats['steer_max']:.6f}",
                        f"{stats['throttle_max']:.6f}",
                        f"{stats['mean_distance']:.6f}",
                        f"{stats['speed_mean']:.6f}",
                        f"{stats['speed_max']:.6f}",
                        f"{stats['min_distance']:.6f}",
                        f"{stats['distance_error_mean']:.6f}",
                        f"{stats['mean_formation_error']:.6f}",
                        f"{mean_iou:.6f}",
                        f"{std_iou:.6f}",
                        f"{mean_rms:.6f}",
                        f"{std_rms:.6f}",
                        f"{mean_cent:.6f}",
                        f"{std_cent:.6f}",
                        stats["near_miss_count"],
                        "0.0",
                    ])
            print(f"[Metrics] Saved snapshots: {self.snapshots_csv_path}")
            print(f"[Metrics] Appended summary: {self.summary_csv_path}")
        except Exception as e:
            print(f"[Metrics] WARNING: failed to write final summary: {e}")


def _build_udp_socket(port_rx):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, port_rx))
    sock.setblocking(False)
    return sock


def _send_leader_startup_commands():
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mode_cmd = {"cmd": "set_control_mode", "mode": str(LEADER_INITIAL_CONTROL_MODE)}
    # Send to configured leader TX port plus a legacy default port to be robust
    targets = {LEADER_AUTO_TRAJECTORY_TX_PORT, int(LEADER_RX), 5065}
    for port in sorted(targets):
        try:
            send_sock.sendto(json.dumps(mode_cmd).encode("utf-8"), (UDP_IP, port))
            print(f"[LeaderCmd] Sent control mode '{LEADER_INITIAL_CONTROL_MODE}' to leader port {port}")
        except Exception:
            print(f"[LeaderCmd] Failed sending control mode to port {port}")

    # If trajectory is desired and auto-trajectory is enabled, send the trajectory params too.
    if str(LEADER_INITIAL_CONTROL_MODE).lower() == "trajectory" and LEADER_AUTO_TRAJECTORY_ENABLE:
        cmd = {
            "cmd": "set_trajectory",
            "mode": LEADER_TRAJECTORY_MODE,
            "speed": LEADER_TRAJECTORY_SPEED,
            "enable_speed_ramp": bool(LEADER_TRAJECTORY_SPEED_RAMP_ENABLE),
            "trajectory_acceleration": float(LEADER_TRAJECTORY_ACCELERATION),
            "trajectory_initial_speed": float(LEADER_TRAJECTORY_INITIAL_SPEED),
            "circle_radius": LEADER_TRAJECTORY_CIRCLE_RADIUS,
            "triangle_side_length": LEADER_TRAJECTORY_TRIANGLE_SIDE,
            "rectangle_size_x": LEADER_TRAJECTORY_RECT_SIZE[0],
            "rectangle_size_y": LEADER_TRAJECTORY_RECT_SIZE[1],
            "loop": bool(LEADER_TRAJECTORY_LOOP),
            "reset": bool(LEADER_TRAJECTORY_RESET_ON_APPLY),
        }
        for port in sorted(targets):
            try:
                send_sock.sendto(json.dumps(cmd).encode("utf-8"), (UDP_IP, port))
                print(f"[LeaderCmd] Sent trajectory command to leader port {port}")
            except Exception:
                print(f"[LeaderCmd] Failed sending trajectory command to port {port}")

    send_sock.close()

    # Write a small startup file so Unity can pick up mode/trajectory even if UDP is missed
    try:
        import os as _os
        path = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "leader_startup.json"))
        startup = {}
        startup["cmd"] = "set_control_mode"
        startup["mode"] = str(LEADER_INITIAL_CONTROL_MODE)
        if str(LEADER_INITIAL_CONTROL_MODE).lower() == "trajectory" and LEADER_AUTO_TRAJECTORY_ENABLE:
            startup = {
                "cmd": "set_trajectory",
                "mode": LEADER_TRAJECTORY_MODE,
                "speed": LEADER_TRAJECTORY_SPEED,
                "enable_speed_ramp": bool(LEADER_TRAJECTORY_SPEED_RAMP_ENABLE),
                "trajectory_acceleration": float(LEADER_TRAJECTORY_ACCELERATION),
                "trajectory_initial_speed": float(LEADER_TRAJECTORY_INITIAL_SPEED),
                "circle_radius": LEADER_TRAJECTORY_CIRCLE_RADIUS,
                "triangle_side_length": LEADER_TRAJECTORY_TRIANGLE_SIDE,
                "rectangle_size_x": LEADER_TRAJECTORY_RECT_SIZE[0],
                "rectangle_size_y": LEADER_TRAJECTORY_RECT_SIZE[1],
                "loop": bool(LEADER_TRAJECTORY_LOOP),
                "reset": bool(LEADER_TRAJECTORY_RESET_ON_APPLY),
            }
        try:
            with open(path, "w") as f:
                json.dump(startup, f)
            print(f"[LeaderCmd] Wrote startup file for Unity: {path}")
        except Exception as e:
            print(f"[LeaderCmd] Failed writing startup file: {e}")
    except Exception:
        pass


def _send_follower_startup_commands():
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd = {
        "cmd": "set_drive_tuning",
        "enable_throttle_ramp": bool(FOLLOWER_THROTTLE_SPEED_RAMP_ENABLE),
        "throttle_ramp_up_rate": float(FOLLOWER_THROTTLE_RAMP_UP_RATE),
        "throttle_ramp_down_rate": float(FOLLOWER_THROTTLE_RAMP_DOWN_RATE),
    }
    for port in (int(PORT_LEFT_TX), int(PORT_RIGHT_TX)):
        try:
            send_sock.sendto(json.dumps(cmd).encode("utf-8"), (UDP_IP, port))
            print(f"[FollowerCmd] Sent drive tuning to follower port {port}")
        except Exception:
            print(f"[FollowerCmd] Failed sending drive tuning to port {port}")
    send_sock.close()


def _send_wave_settings():
    """Send SUIMONO wave parameters to Unity's WaveController via UDP."""
    if not WAVE_CONTROL_ENABLE:
        return
    cmd = {
        "cmd": "set_wave",
        "wave_height": float(SUIMONO_WAVE_HEIGHT),
        "turbulence": float(SUIMONO_TURBULENCE),
        "large_wave_height": float(SUIMONO_LARGE_WAVE_HEIGHT),
        "large_wave_scale": float(SUIMONO_LARGE_WAVE_SCALE),
        "wave_scale": float(SUIMONO_WAVE_SCALE),
        "flow_speed": float(SUIMONO_FLOW_SPEED),
        "camera_tilt_strength": float(SUIMONO_CAMERA_TILT_STRENGTH),
    }
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        send_sock.sendto(json.dumps(cmd).encode("utf-8"), (UDP_IP, int(WAVE_CONTROL_PORT)))
        print(
            f"[WaveCtrl] Sent wave settings → port {WAVE_CONTROL_PORT}: "
            f"height={SUIMONO_WAVE_HEIGHT} turb={SUIMONO_TURBULENCE} "
            f"lgH={SUIMONO_LARGE_WAVE_HEIGHT} tilt={SUIMONO_CAMERA_TILT_STRENGTH}"
        )
    except Exception as e:
        print(f"[WaveCtrl] Failed to send wave settings: {e}")
    finally:
        send_sock.close()


def _wait_for_follower_connections(timeout_sec, poll_interval_sec):
    timeout_sec = max(0.0, float(timeout_sec))
    poll_interval_sec = max(0.05, float(poll_interval_sec))
    deadline = time.time() + timeout_sec
    required_streams = ["LeftFront", "RightFront"]

    while True:
        with vision_lock:
            connected_streams = {
                stream_name: bool(vision_states[stream_name].get("connected", False))
                for stream_name in required_streams
            }

        if all(connected_streams.values()):
            print("[LeaderCmd] Both follower camera links are connected.")
            return True

        if time.time() >= deadline:
            print(
                "[LeaderCmd] WARNING: follower camera links not fully connected before timeout; "
                "leader startup will proceed anyway."
            )
            return False

        missing = [stream_name for stream_name, is_connected in connected_streams.items() if not is_connected]
        print(f"[LeaderCmd] Waiting for follower camera links: {', '.join(missing)}")
        time.sleep(poll_interval_sec)


def _set_startup_sync_state(released, status, wait_reason=""):
    runtime_settings["startup_sync_released"] = bool(released)
    runtime_settings["startup_sync_status"] = str(status)
    runtime_settings["startup_sync_wait_reason"] = str(wait_reason)


def _evaluate_startup_sync(now):
    if not bool(runtime_settings.get("startup_sync_enabled", False)):
        runtime_settings["startup_leader_cmd_triggered"] = True  # arm leader immediately when sync disabled
        _set_startup_sync_state(True, "disabled", "")
        return True

    if runtime_settings.get("startup_sync_started_at") is None:
        runtime_settings["startup_sync_started_at"] = now

    if bool(runtime_settings.get("startup_sync_released", False)):
        return True

    # Hard deadline: fires if cameras never connect (broken setup).  This is
    # intentionally generous so it only triggers in truly broken scenarios.
    hard_deadline = runtime_settings.get("startup_sync_hard_deadline")
    if hard_deadline and now >= float(hard_deadline):
        runtime_settings["startup_leader_cmd_triggered"] = True
        _set_startup_sync_state(True, "hard_timeout", "startup hard deadline reached")
        print("[StartupSync] Hard deadline reached; releasing follower control gate.")
        return True

    missing = []

    # Only require camera streams that are actually used for control.
    # When side detection is disabled, requiring side-camera connections would
    # block startup if those streams are not active in the Unity scene.
    if bool(SYNC_FOLLOWER_STARTUP_REQUIRE_ALL_CAMERA_STREAMS):
        side_det = bool(runtime_settings.get("enable_side_detection", False))
        with vision_lock:
            disconnected = [
                s for s, cfg in CAMERA_STREAMS.items()
                if (cfg.get("role") == "front" or side_det)
                and not bool(vision_states[s].get("connected", False))
            ]
        if disconnected:
            # Keep resetting the per-camera timeout until cameras are up so the
            # 25-second post-connect window starts from Unity's actual start.
            runtime_settings["startup_sync_started_at"] = now
            missing.append(f"streams:{','.join(disconnected)}")

    # Per-camera-connect timeout: only fires after cameras have been connected.
    started_at = float(runtime_settings.get("startup_sync_started_at") or now)
    timeout_sec = max(0.0, float(SYNC_FOLLOWER_STARTUP_TIMEOUT_SEC))
    if timeout_sec > 0.0 and (now - started_at) >= timeout_sec:
        runtime_settings["startup_leader_cmd_triggered"] = True  # ensure leader starts on fallback
        _set_startup_sync_state(True, "timeout_release", "startup sync timeout reached")
        print("[StartupSync] Timeout reached; releasing follower control gate.")
        return True

    stale_limit = max(0.05, float(SYNC_FOLLOWER_STARTUP_PACKET_STALE_SEC))
    if bool(SYNC_FOLLOWER_STARTUP_REQUIRE_FOLLOWER_STATE):
        with vision_lock:
            follower_state_missing = []
            for side in ("Left", "Right"):
                comm = boat_comm_states.get(side, {})
                last_packet_time = float(comm.get("last_packet_time", 0.0))
                is_connected = bool(comm.get("connected", False))
                is_fresh = last_packet_time > 0.0 and (now - last_packet_time) <= stale_limit
                if not (is_connected and is_fresh):
                    follower_state_missing.append(side)
        if follower_state_missing:
            missing.append(f"state:{','.join(follower_state_missing)}")

    if bool(SYNC_FOLLOWER_STARTUP_REQUIRE_FRONT_VISUAL_LOCK):
        with vision_lock:
            front_missing = [
                side for side in ("Left", "Right")
                if not bool(formation_targets[side].get("front_visual_initialized", False))
            ]
        if front_missing:
            missing.append(f"front_lock:{','.join(front_missing)}")

    if bool(SYNC_FOLLOWER_STARTUP_REQUIRE_SIDE_VISUAL_LOCK):
        with vision_lock:
            side_missing = [
                side for side in ("Left", "Right")
                if not bool(formation_targets[side].get("side_visual_initialized", False))
            ]
        if side_missing:
            missing.append(f"side_lock:{','.join(side_missing)}")

    if missing:
        runtime_settings["startup_sync_ready_since"] = None
        _set_startup_sync_state(False, "waiting", " | ".join(missing))
        return False

    # All conditions are satisfied.  Signal the main loop to arm leader commands
    # NOW — before the settle delay — so the leader starts while followers are
    # still gated.  The settle window then gives the leader time to start moving
    # before followers are released, keeping relative positions consistent.
    if not runtime_settings.get("startup_leader_cmd_triggered", False):
        runtime_settings["startup_leader_cmd_triggered"] = True
        print("[StartupSync] Front visual lock acquired; signaling leader to start.")

    ready_since = runtime_settings.get("startup_sync_ready_since")
    if ready_since is None:
        runtime_settings["startup_sync_ready_since"] = now
        ready_since = now

    settle_sec = max(0.0, float(SYNC_FOLLOWER_STARTUP_SETTLE_SEC))
    remaining = settle_sec - (now - float(ready_since))
    if remaining > 0.0:
        _set_startup_sync_state(False, "settling", f"settling:{remaining:.2f}s")
        return False

    _set_startup_sync_state(True, "released", "startup sync released")
    print("[StartupSync] All follower startup checks passed; releasing synchronized follower control.")
    return True


def main():
    sock_left = _build_udp_socket(PORT_LEFT_RX)
    sock_right = _build_udp_socket(PORT_RIGHT_RX)
    sock_formation = _build_udp_socket(FORMATION_MODE_RX)

    print("=======================================")
    print("雙船 Fully Vision-Based 啟動")
    print("=======================================")

    # Remove any stale leader_startup.json left by a previous run.  Unity reads
    # this file in Start() and would start the leader immediately, bypassing the
    # visual-lock gate we use to make startup reproducible.
    try:
        import os as _os
        _stale = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "leader_startup.json"))
        if _os.path.exists(_stale):
            _os.remove(_stale)
            print("[LeaderCmd] Removed stale leader_startup.json from previous run.")
    except Exception:
        pass

    # Leader commands are now armed only after front visual lock is confirmed by
    # _evaluate_startup_sync, so the reference area is always locked while the
    # leader is stationary at spawn.  Do NOT send commands here at startup.
    leader_cmd_retries_remaining = 0
    leader_cmd_retry_interval = max(0.05, float(LEADER_STARTUP_CMD_RETRY_INTERVAL_SEC))
    next_leader_cmd_time = 0.0

    if SHOW_WINDOW:
        for _, config in CAMERA_STREAMS.items():
            if config.get("role") == "side" and not bool(SHOW_SIDE_WINDOWS):
                continue
            cv2.namedWindow(config["window"], cv2.WINDOW_NORMAL)
            cv2.resizeWindow(config["window"], *WINDOW_SIZE)
        with frame_lock:
            for stream_name, config in CAMERA_STREAMS.items():
                if config.get("role") == "side" and not bool(SHOW_SIDE_WINDOWS):
                    continue
                display_frames[stream_name] = make_status_frame(config["window"], "Waiting for TCP stream...")

    receiver_threads = []
    for stream_name, config in CAMERA_STREAMS.items():
        receiver_threads.append(
            threading.Thread(target=tcp_camera_receiver_thread, args=(config["port"], stream_name), daemon=True)
        )
    t_cv = threading.Thread(target=cv_processing_thread, daemon=True)

    for receiver_thread in receiver_threads:
        receiver_thread.start()
    t_cv.start()

    if LEADER_AUTO_TRAJECTORY_ENABLE and str(LEADER_INITIAL_CONTROL_MODE).lower() == "trajectory":
        if bool(LEADER_WAIT_FOR_FOLLOWER_CONNECTIONS):
            _wait_for_follower_connections(LEADER_CONNECTION_WAIT_TIMEOUT_SEC, LEADER_CONNECTION_POLL_INTERVAL_SEC)
        # Send wave settings now only when WAVE_APPLY_AFTER_STARTUP is False.
        # When True, wave/rain are held back until startup sync releases (leader retry
        # loop), so extreme wave heights cannot destabilize boats before visual lock.
        if not bool(WAVE_APPLY_AFTER_STARTUP):
            _send_wave_settings()

    runtime_settings["startup_sync_started_at"] = time.time()
    runtime_settings["startup_sync_ready_since"] = None
    runtime_settings["startup_sync_enabled"] = bool(SYNC_FOLLOWER_STARTUP_ENABLE)
    # Hard deadline: release followers unconditionally after this many seconds
    # from Python start.  This fires only if cameras never connect at all.
    runtime_settings["startup_sync_hard_deadline"] = (
        time.time()
        + float(LEADER_CONNECTION_WAIT_TIMEOUT_SEC)
        + float(SYNC_FOLLOWER_STARTUP_TIMEOUT_SEC)
        + 30.0
    )
    # Flag set by _evaluate_startup_sync when conditions are met; main loop
    # watches it to arm the leader command retries.
    runtime_settings["startup_leader_cmd_triggered"] = False
    runtime_settings["startup_leader_cmd_armed"] = False
    if bool(SYNC_FOLLOWER_STARTUP_ENABLE):
        _set_startup_sync_state(False, "waiting", "startup sync initializing")
    else:
        _set_startup_sync_state(True, "disabled", "")

    last_print_time = time.time()
    last_startup_sync_print_time = 0.0
    last_loop_time = time.time()
    t_udp = 0.0
    t_ui_copy = 0.0
    t_imshow = 0.0
    t_waitkey = 0.0
    metrics_logger = RunMetricsLogger(report_interval_sec=5.0)
    metrics_tracking_started = False  # becomes True when startup sync releases

    try:
        while True:
            loop_start = time.time()

            _evaluate_startup_sync(loop_start)

            # Formation mode can be changed at runtime via UDP
            try:
                while True:
                    data, _ = sock_formation.recvfrom(1024)
                    msg = json.loads(data.decode("utf-8"))

                    if msg.get("cmd") != "set_formation_mode":
                        continue

                    new_mode = str(msg.get("mode", "v")).strip().lower()
                    if new_mode not in ("v", "line"):
                        continue

                    prev_mode = str(runtime_settings.get("formation_mode", "v")).strip().lower()
                    if new_mode == prev_mode:
                        continue

                    runtime_settings["formation_mode"] = new_mode

                    # Right follower front target will change across formations,
                    # so force it to relock its front visual reference.
                    formation_targets["Right"]["front_visual_initialized"] = False
                    formation_targets["Right"]["desired_front_offset"] = 0.0
                    formation_targets["Right"]["desired_front_area"] = 0.0
                    formation_targets["Right"]["desired_front_target_kind"] = None

                    if new_mode == "line":
                        runtime_settings["right_line_transition_until"] = time.time() + float(
                            runtime_settings.get("right_line_transition_sec", 2.0)
                        )
                        runtime_settings["right_v_recovery_until"] = 0.0

                    elif new_mode == "v":
                        runtime_settings["right_v_recovery_until"] = time.time() + float(
                            runtime_settings.get("right_v_recovery_sec", 2.5)
                        )
                        runtime_settings["right_line_transition_until"] = 0.0

                    else:
                        runtime_settings["right_line_transition_until"] = 0.0
                        runtime_settings["right_v_recovery_until"] = 0.0

                    print(f"[FormationMode] Switched {prev_mode} -> {new_mode}, reset Right front reference")

            except BlockingIOError:
                pass
            except Exception as e:
                print(f"[FormationMode] Receive error: {e}")

            # Arm leader command retries the first time startup sync signals that
            # visual lock is ready.  This ensures the leader is stationary at spawn
            # when the front-camera reference area is locked, making desired_front_area
            # consistent across runs.
            if (
                runtime_settings.get("startup_leader_cmd_triggered", False)
                and not runtime_settings.get("startup_leader_cmd_armed", False)
            ):
                leader_cmd_retries_remaining = max(1, int(LEADER_STARTUP_CMD_RETRY_COUNT))
                next_leader_cmd_time = loop_start
                runtime_settings["startup_leader_cmd_armed"] = True

            if leader_cmd_retries_remaining > 0 and loop_start >= next_leader_cmd_time:
                attempt = (max(1, int(LEADER_STARTUP_CMD_RETRY_COUNT)) - leader_cmd_retries_remaining) + 1
                total_attempts = max(1, int(LEADER_STARTUP_CMD_RETRY_COUNT))
                try:
                    _send_leader_startup_commands()
                    _send_follower_startup_commands()
                    _send_wave_settings()
                    if total_attempts > 1:
                        print(f"[LeaderCmd] Startup command attempt {attempt}/{total_attempts}")
                except Exception as e:
                    print(f"[LeaderCmd] Failed startup command attempt {attempt}/{total_attempts}: {e}")

                leader_cmd_retries_remaining -= 1
                next_leader_cmd_time = loop_start + leader_cmd_retry_interval

            loop_duration = loop_start - last_loop_time
            if loop_duration > 0.1:
                print(f"[{loop_start:.2f}] WARNING: Main loop paused for {loop_duration:.3f} seconds!")
                print(
                    f"  --> Last iteration timing: UDP={t_udp:.4f}s, "
                    f"UI_Copy={t_ui_copy:.4f}s, Imshow={t_imshow:.4f}s, WaitKey={t_waitkey:.4f}s"
                )
            last_loop_time = loop_start

            t0 = time.time()
            res_left = process_boat_vision_based(sock_left, PORT_LEFT_TX, "Left")
            res_right = process_boat_vision_based(sock_right, PORT_RIGHT_TX, "Right")
            t_udp = time.time() - t0

            t0 = time.time()
            disp_frames = {}
            if SHOW_WINDOW:
                with frame_lock:
                    for stream_name, config in CAMERA_STREAMS.items():
                        if config.get("role") == "side" and not bool(SHOW_SIDE_WINDOWS):
                            display_frames[stream_name] = None
                            continue
                        if display_frames[stream_name] is not None:
                            disp_frames[stream_name] = display_frames[stream_name].copy()
                            display_frames[stream_name] = None
            t_ui_copy = time.time() - t0

            if SHOW_WINDOW:
                t0 = time.time()
                current_loop_time = time.time()
                for stream_name, frame in disp_frames.items():
                    kalman_enabled = bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))
                    cv2.putText(
                        frame,
                        f"Kalman: {'ON' if kalman_enabled else 'OFF'}  (press K)",
                        (16, frame.shape[0] - 16),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 0) if kalman_enabled else (0, 0, 255),
                        2,
                    )
                    side_detect_enabled = bool(runtime_settings.get("enable_side_detection", True))
                    cv2.putText(
                        frame,
                        f"SideDetect: {'ON' if side_detect_enabled else 'OFF'}  (press S)",
                        (16, frame.shape[0] - 36),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.50,
                        (0, 255, 0) if side_detect_enabled else (0, 0, 255),
                        2,
                    )
                    cv2.imshow(CAMERA_STREAMS[stream_name]["window"], frame)
                t_imshow = time.time() - t0

                # show a top-down formation view if desired
                try:
                    vis_scale = float(runtime_settings.get("formation_visual_scale", 1.0))
                except Exception:
                    vis_scale = 1.0
                try:
                    metrics_logger.draw_topdown("Top-Down Formation", pixels_per_meter=3.0, visual_scale=vis_scale)
                except Exception:
                    pass
                t0 = time.time()
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                if key in (ord("k"), ord("K")):
                    new_value = not bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))
                    runtime_settings["enable_kalman_filter"] = new_value
                    print(f"[Kalman] Filter toggled {'ON' if new_value else 'OFF'}")
                if key in (ord("s"), ord("S")):
                    new_value = not bool(runtime_settings.get("enable_side_detection", True))
                    runtime_settings["enable_side_detection"] = new_value
                    print(f"[SideDetect] Side-camera detection toggled {'ON' if new_value else 'OFF'}")
                if key in (ord("c"), ord("C")):
                    # Save an on-demand checkpoint (writes independent run_id summary + snapshot)
                    now_ck = time.time()
                    kalman_now = bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))
                    try:
                        metrics_logger.write_checkpoint(now_ck, kalman_now)
                    except Exception as e:
                        print(f"[Metrics] WARNING: failed to write checkpoint: {e}")
                t_waitkey = time.time() - t0
            else:
                t_imshow = 0.0
                t_waitkey = 0.0

            current_time = time.time()
            kalman_enabled_loop = bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))

            # Only record metrics once followers are actually released.  This
            # prevents the pre-tracking wait period from polluting the CSV with
            # flat/zero data and keeps elapsed_s anchored to tracking start.
            sync_released = bool(runtime_settings.get("startup_sync_released", False))
            if sync_released and not metrics_tracking_started:
                metrics_logger.started_at = current_time
                metrics_logger.last_report_at = current_time
                metrics_logger.kalman_last_time = current_time
                metrics_tracking_started = True
                print(f"[Metrics] Tracking started; elapsed_s will be relative to this moment.")

            if sync_released:
                metrics_logger.update_kalman_state(kalman_enabled_loop, current_time)
                metrics_logger.update("Left", res_left, current_time)
                metrics_logger.update("Right", res_right, current_time)

                if metrics_logger.should_report(current_time):
                    for line in metrics_logger.build_report_lines(final=False):
                        print(line)
                    # Compute FPS from loop timing
                    loop_dt = max(1e-6, current_time - last_loop_time)
                    fps = 1.0 / loop_dt if loop_dt > 0 else 0.0
                    metrics_logger.write_periodic_snapshot(current_time, kalman_enabled_loop, fps=fps)

            if current_time - last_print_time > 0.2:
                print_parts = []

                if res_left:
                    method_left = res_left["method"] or "   "
                    symbol_left = "~" if res_left["stale"] else ("*" if res_left["detected"] else ".")
                    side_symbol_left = "~" if res_left["side_stale"] else ("*" if res_left["side_detected"] else ".")
                    side_method_left = res_left["side_method"] or "   "
                    print_parts.append(
                        f"[L-{method_left}] {symbol_left} 舵:{res_left['steer']:5.2f} "
                        f"油:{res_left['throttle']:4.2f} S:{res_left['area']:>5.0f} "
                        f"SL[{side_method_left}]{side_symbol_left}:{res_left['side_offset']:>5.2f} "
                        f"P:{res_left['pred_offset']:>5.2f} "
                        f"B:{res_left['pair_catchup_boost']:>4.2f}"
                    )

                if res_right:
                    method_right = res_right["method"] or "   "
                    symbol_right = "~" if res_right["stale"] else ("*" if res_right["detected"] else ".")
                    side_symbol_right = "~" if res_right["side_stale"] else ("*" if res_right["side_detected"] else ".")
                    side_method_right = res_right["side_method"] or "   "
                    print_parts.append(
                        f"[R-{method_right}] {symbol_right} 舵:{res_right['steer']:5.2f} "
                        f"油:{res_right['throttle']:4.2f} S:{res_right['area']:>5.0f} "
                        f"SL[{side_method_right}]{side_symbol_right}:{res_right['side_offset']:>5.2f} "
                        f"P:{res_right['pred_offset']:>5.2f} "
                        f"B:{res_right['pair_catchup_boost']:>4.2f}"
                    )

                if print_parts:
                    # append current formation size (if available)
                    fsz = metrics_logger.last_formation_metrics.get("formation_size_mean_side_m")
                    if fsz is not None:
                        print_parts.append(f"FormSize(mean_side)={fsz:.2f}m")
                    print(" || ".join(print_parts))
                last_print_time = current_time

            startup_sync_status = str(runtime_settings.get("startup_sync_status", ""))
            if startup_sync_status in ("waiting", "settling") and (current_time - last_startup_sync_print_time) > 1.0:
                wait_reason = str(runtime_settings.get("startup_sync_wait_reason", ""))
                if wait_reason:
                    print(f"[StartupSync] {startup_sync_status}: {wait_reason}")
                last_startup_sync_print_time = current_time

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        metrics_logger.write_final_summary(time.time())
        for line in metrics_logger.build_report_lines(final=True):
            print(line)
        if SHOW_WINDOW:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
