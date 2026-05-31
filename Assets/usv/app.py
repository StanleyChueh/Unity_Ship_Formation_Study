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

from .config import (
    CAMERA_STREAMS,
    ENABLE_KALMAN_FILTER,
    PORT_LEFT_RX,
    PORT_LEFT_TX,
    PORT_RIGHT_RX,
    PORT_RIGHT_TX,
    SHOW_WINDOW,
    UDP_IP,
    WINDOW_SIZE,
    LEADER_AUTO_TRAJECTORY_ENABLE,
    LEADER_AUTO_TRAJECTORY_TX_PORT,
    LEADER_TRAJECTORY_MODE,
    LEADER_TRAJECTORY_SPEED,
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
    NEAR_MISS_DISTANCE_THRESHOLD_PX,
    PREDICTION_HORIZON_SEC,
)
from .control import process_boat_vision_based
from .helpers import apply_camera_shake, make_status_frame
from .state import display_frames, frame_lock, runtime_settings, vision_lock, vision_states
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
                            "mean_distance",
                            "min_distance",
                            "distance_error_mean",
                            "mean_formation_error",
                            "near_miss_count",
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
                            "min_distance",
                            "distance_error_mean",
                            "mean_formation_error",
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
        }

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
                            f"{stats['mean_distance']:.6f}",
                            f"{stats['min_distance']:.6f}",
                            f"{stats['distance_error_mean']:.6f}",
                            f"{stats['mean_formation_error']:.6f}",
                            stats["near_miss_count"],
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
                        "mean_distance",
                        "min_distance",
                            "distance_error_mean",
                        "mean_formation_error",
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
                            f"{stats['mean_distance']:.6f}",
                            f"{stats['min_distance']:.6f}",
                            f"{stats['distance_error_mean']:.6f}",
                                f"{stats['distance_error_mean']:.6f}",
                            f"{stats['distance_error_mean']:.6f}",
                            f"{stats['mean_formation_error']:.6f}",
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
                                f"{stats['min_distance']:.6f}",
                                f"{stats['mean_formation_error']:.6f}",
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
                    w.writerow(
                        [
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
                            f"{stats['min_distance']:.6f}",
                            f"{stats['mean_formation_error']:.6f}",
                            stats["near_miss_count"],
                            "0.0",
                        ]
                    )
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


def main():
    sock_left = _build_udp_socket(PORT_LEFT_RX)
    sock_right = _build_udp_socket(PORT_RIGHT_RX)

    print("=======================================")
    print("雙船 Fully Vision-Based 啟動")
    print("=======================================")

    # Retry startup leader command a few times to tolerate startup ordering (Unity Play mode timing).
    leader_cmd_retries_remaining = max(1, int(LEADER_STARTUP_CMD_RETRY_COUNT))
    leader_cmd_retry_interval = max(0.05, float(LEADER_STARTUP_CMD_RETRY_INTERVAL_SEC))
    next_leader_cmd_time = time.time()

    if SHOW_WINDOW:
        for _, config in CAMERA_STREAMS.items():
            cv2.namedWindow(config["window"], cv2.WINDOW_NORMAL)
            cv2.resizeWindow(config["window"], *WINDOW_SIZE)
        with frame_lock:
            for stream_name, config in CAMERA_STREAMS.items():
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

    last_print_time = time.time()
    last_loop_time = time.time()
    t_udp = 0.0
    t_ui_copy = 0.0
    t_imshow = 0.0
    t_waitkey = 0.0
    metrics_logger = RunMetricsLogger(report_interval_sec=5.0)

    try:
        while True:
            loop_start = time.time()

            if leader_cmd_retries_remaining > 0 and loop_start >= next_leader_cmd_time:
                attempt = (max(1, int(LEADER_STARTUP_CMD_RETRY_COUNT)) - leader_cmd_retries_remaining) + 1
                total_attempts = max(1, int(LEADER_STARTUP_CMD_RETRY_COUNT))
                try:
                    _send_leader_startup_commands()
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
                    for stream_name in CAMERA_STREAMS:
                        if display_frames[stream_name] is not None:
                            disp_frames[stream_name] = display_frames[stream_name].copy()
                            display_frames[stream_name] = None
            t_ui_copy = time.time() - t0

            if SHOW_WINDOW:
                t0 = time.time()
                current_loop_time = time.time()
                try:
                    with speed_lock:
                        left_spd_knots = boat_speeds.get("Left", 0.0)
                        right_spd_knots = boat_speeds.get("Right", 0.0)
                    avg_speed_mps = ((left_spd_knots + right_spd_knots) / 2.0) / 1.94384
                except Exception:
                    avg_speed_mps = 0.0

                for stream_name, frame in disp_frames.items():
                    shaken_frame = apply_camera_shake(frame, avg_speed_mps, current_loop_time)
                    kalman_enabled = bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))
                    cv2.putText(
                        shaken_frame,
                        f"Kalman: {'ON' if kalman_enabled else 'OFF'}  (press K)",
                        (16, shaken_frame.shape[0] - 16),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 0) if kalman_enabled else (0, 0, 255),
                        2,
                    )
                    cv2.imshow(CAMERA_STREAMS[stream_name]["window"], shaken_frame)
                t_imshow = time.time() - t0

                t0 = time.time()
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                if key in (ord("k"), ord("K")):
                    new_value = not bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))
                    runtime_settings["enable_kalman_filter"] = new_value
                    print(f"[Kalman] Filter toggled {'ON' if new_value else 'OFF'}")
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
                    print(" || ".join(print_parts))
                last_print_time = current_time

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
