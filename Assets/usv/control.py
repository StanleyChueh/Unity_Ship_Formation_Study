'''
    Vision-based control logic for the USV, 
    processing camera data to compute throttle and steering commands.
'''

import json
import math
import time
import csv
import os
from datetime import datetime

from .config import *
from .helpers import blend_value, clamp, filter_steer_command, get_peer_boat_side
from .state import boat_comm_states, formation_targets, runtime_settings, vision_lock, vision_states


# Per-side startup lock expiry timestamps (epoch seconds).
_STARTUP_STEER_LOCK_UNTIL = {"Left": 0.0, "Right": 0.0}
# Per-side throttle memory for gentle smoothing, especially on the right follower.
_LAST_THROTTLE = {"Left": 0.0, "Right": 0.0}

# Persistence counter to avoid single-frame area spikes zeroing throttle
_AREA_OVER_MAX_COUNT = {"Left": 0, "Right": 0}

# Debug logging (Right follower)
_DEBUG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "experiment_metrics"))
_RIGHT_DEBUG_PATH = os.path.join(_DEBUG_DIR, "right_debug.csv")

def _log_right_debug(side, current_time, front_area, effective_area, predicted_area, pred_conf, front_stale, side_detected, side_pred_conf, edge_edge_factor, last_throttle, throttle):
    if side != "Right":
        return
    try:
        os.makedirs(_DEBUG_DIR, exist_ok=True)
        write_header = not os.path.exists(_RIGHT_DEBUG_PATH)
        with open(_RIGHT_DEBUG_PATH, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow([
                    "time", "elapsed_s", "front_area", "effective_area", "predicted_area", "pred_conf", "front_stale", "side_detected", "side_pred_conf", "edge_edge_factor", "last_throttle", "throttle"
                ])
            elapsed = float(current_time)
            w.writerow([
                datetime.now().isoformat(timespec="seconds"),
                f"{elapsed:.3f}",
                f"{float(front_area):.3f}",
                f"{float(effective_area):.3f}",
                f"{float(predicted_area):.3f}",
                f"{float(pred_conf):.3f}",
                int(bool(front_stale)),
                int(bool(side_detected)),
                f"{float(side_pred_conf):.3f}",
                f"{float(edge_edge_factor):.3f}",
                f"{float(last_throttle):.3f}",
                f"{float(throttle):.3f}",
            ])
    except Exception:
        pass


def _normalize_angle_deg(angle_deg):
    value = float(angle_deg)
    while value > 180.0:
        value -= 360.0
    while value < -180.0:
        value += 360.0
    return value


def _send_control_command(sock, tx_port, throttle, steer):
    msg = json.dumps({"throttle": float(throttle), "steer": float(steer)})
    sock.sendto(msg.encode("utf-8"), (UDP_IP, tx_port))


def compute_pair_catchup_boost(boat_side, own_detected, own_stale, own_method, own_area):
    if not own_detected or own_stale or own_method not in ("YOLO", "FUSED"):
        return 0.0, None, 0.0

    peer_side = get_peer_boat_side(boat_side)
    with vision_lock:
        peer_state = vision_states[FRONT_STREAM_BY_BOAT[peer_side]].copy()

    if (
        not peer_state.get("target_detected", False)
        or peer_state.get("target_stale", False)
        or peer_state.get("method") not in ("YOLO", "FUSED")
    ):
        return 0.0, None, 0.0

    peer_area = max(float(peer_state.get("target_area", 0.0)), 1.0)
    own_area = max(float(own_area), 1.0)
    dominant_area = max(peer_area, own_area, 1.0)
    area_gap_ratio = (peer_area - own_area) / dominant_area

    if area_gap_ratio <= FOLLOWER_PAIR_AREA_BALANCE_TOLERANCE_RATIO:
        return 0.0, peer_area, area_gap_ratio

    boost_ratio = clamp(
        (area_gap_ratio - FOLLOWER_PAIR_AREA_BALANCE_TOLERANCE_RATIO)
        / max(1e-5, (1.0 - FOLLOWER_PAIR_AREA_BALANCE_TOLERANCE_RATIO)),
        0.0,
        1.0,
    )
    boost = clamp(boost_ratio * FOLLOWER_PAIR_CATCHUP_GAIN, 0.0, FOLLOWER_PAIR_CATCHUP_MAX)
    return boost, peer_area, area_gap_ratio


def get_tracking_gains(method, is_stale):
    if method in ("YOLO", "FUSED"):
        steer_gain = YOLO_TRACK_STEER_GAIN
        throttle_gain = YOLO_TRACK_THROTTLE_GAIN
    elif method == "WAKE":
        steer_gain = WAKE_TRACK_STEER_GAIN
        throttle_gain = WAKE_TRACK_THROTTLE_GAIN
    elif method == "FOLLOWER":
        steer_gain = FOLLOWER_TRACK_STEER_GAIN
        throttle_gain = FOLLOWER_TRACK_THROTTLE_GAIN
    else:
        steer_gain = 1.0
        throttle_gain = 1.0

    if is_stale:
        steer_gain *= STALE_TRACK_STEER_GAIN
        throttle_gain *= STALE_TRACK_THROTTLE_GAIN

    return steer_gain, throttle_gain


def get_side_area_target_opt(side_visual_ref_ready, desired_side_area, side_target_kind):
    if side_visual_ref_ready and desired_side_area > 1.0:
        return desired_side_area
    if side_target_kind == "leader":
        return YOLO_AREA_OPT
    return FOLLOWER_AREA_OPT


def normalize_area_error(desired_area, measured_area):
    desired_area = max(float(desired_area), 1.0)
    return clamp((desired_area - float(measured_area)) / desired_area, -1.0, 1.0)


def shape_area_error(error_ratio):
    magnitude = abs(float(error_ratio))
    if magnitude <= VISION_AREA_ERROR_DEADZONE_RATIO:
        return 0.0

    shaped = (magnitude - VISION_AREA_ERROR_DEADZONE_RATIO) / max(1e-5, (1.0 - VISION_AREA_ERROR_DEADZONE_RATIO))
    return math.copysign(clamp(shaped, 0.0, 1.0), error_ratio)


def compute_centered_cruise_throttle(steer_error, area_error_ratio, predicted_area_ratio, area_velocity_ratio):
    if abs(steer_error) > VISION_FRONT_CRUISE_STEER_LIMIT:
        return 0.0
    if area_error_ratio < -VISION_FRONT_CRUISE_MAX_NEGATIVE_RATIO:
        return 0.0
    if area_error_ratio > VISION_FRONT_CRUISE_MAX_POSITIVE_RATIO:
        return 0.0

    predicted_gap = max(predicted_area_ratio, 0.0)
    shrinking = clamp(-area_velocity_ratio, 0.0, 1.0)
    growing = clamp(area_velocity_ratio, 0.0, 1.0)
    cruise_scale = clamp(0.55 + (predicted_gap * 0.75) + (shrinking * 0.45) - (growing * 0.85), 0.0, 1.0)
    return VISION_FRONT_CRUISE_THROTTLE * cruise_scale


def compute_turn_catchup_boost(steer, front_area_error_ratio, side_area_error_ratio):
    steer_mag = abs(float(steer))
    if steer_mag <= STEER_DEADZONE_H:
        return 0.0

    front_gap = max(float(front_area_error_ratio), 0.0)
    side_gap = max(float(side_area_error_ratio), 0.0)
    catchup_need = clamp((front_gap * 0.75) + (side_gap * 0.55), 0.0, 1.0)
    if catchup_need <= 1e-4:
        return 0.0

    turn_scale = clamp((steer_mag - 0.18) / 0.55, 0.0, 1.0)
    return clamp(catchup_need * turn_scale * VISION_TURN_CATCHUP_GAIN, 0.0, VISION_TURN_CATCHUP_MAX)


def compute_turn_predictive_assist(offset_velocity, area_velocity, prediction_confidence):
    confidence = clamp(
        (float(prediction_confidence) - PREDICTION_CONTROL_MIN_CONF) / max(1e-5, (1.0 - PREDICTION_CONTROL_MIN_CONF)),
        0.0,
        1.0,
    )
    if confidence <= 0.0:
        return 0.0, 0.0, 0.0

    offset_motion = clamp(abs(float(offset_velocity)) / 0.12, 0.0, 1.0)
    area_motion = clamp(abs(float(area_velocity)) / 0.12, 0.0, 1.0)
    motion = max(offset_motion, area_motion)
    if motion <= 0.0:
        return 0.0, 0.0, confidence

    steer_bias = clamp(
        float(offset_velocity) * VISION_TURN_PREDICTIVE_STEER_GAIN,
        -VISION_TURN_PREDICTIVE_STEER_MAX,
        VISION_TURN_PREDICTIVE_STEER_MAX,
    )
    throttle_bias = clamp(
        motion * confidence * VISION_TURN_PREDICTIVE_THROTTLE_GAIN,
        0.0,
        VISION_TURN_PREDICTIVE_THROTTLE_MAX,
    )
    return steer_bias, throttle_bias, confidence


def compute_visual_far_boost(area, predicted_area, area_velocity, target_opt, method):
    target_opt = max(float(target_opt), 1.0)
    size_gap = clamp((target_opt - float(area)) / target_opt, 0.0, 1.0)
    boost = VISUAL_FAR_BOOST_MAX * (size_gap ** VISUAL_FAR_BOOST_EXPONENT)

    predicted_gap = clamp((target_opt - float(predicted_area)) / target_opt, 0.0, 1.0)
    boost += VISUAL_FAR_BOOST_MAX * 0.5 * predicted_gap * PREDICTION_AREA_BLEND

    if area_velocity < 0.0:
        shrink_ratio = clamp((-float(area_velocity)) / target_opt, 0.0, 1.0)
        boost += VISUAL_SHRINK_BOOST_MAX * shrink_ratio

    if method == "WAKE":
        boost *= WAKE_TRACK_AREA_BIAS
    elif method == "FOLLOWER":
        boost *= FOLLOWER_TRACK_AREA_BIAS

    return clamp(boost, 0.0, FOLLOW_FAR_MAX_THROTTLE - FOLLOW_BASE_THROTTLE)


def compute_distance_from_area(front_area, desired_front_area, yolo_area_opt):
    """Estimate distance proxy from visual area (normalized).
    Lower area ≈ farther away; higher area ≈ closer.
    Returns a pseudo-distance metric (higher = farther).
    """
    if front_area <= 0 or yolo_area_opt <= 0:
        return 0.0
    # Simple inverse-area metric: distance ∝ 1 / area
    # Normalized by the optimal area to get pixel units
    distance = float(yolo_area_opt) / max(float(front_area), 1.0)
    return distance


def compute_formation_error(front_offset, desired_front_offset, front_area, desired_front_area):
    """Compute formation error as combined offset and area deviation.
    Offset error: horizontal centering deviation.
    Area error: distance/scale error.
    Returns a composite metric (lower = better formation).
    """
    offset_error = abs(float(front_offset) - float(desired_front_offset))
    area_error_ratio = abs(float(front_area) - float(desired_front_area)) / max(float(desired_front_area), 1.0)
    # Weighted combination (0.6 offset, 0.4 area)
    formation_error = (0.6 * offset_error) + (0.4 * area_error_ratio)
    return formation_error


def process_boat_vision_based(sock, tx_port, side):
    latest_data = None
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            latest_data = data
        except BlockingIOError:
            break

    if latest_data is None:
        return None

    state = json.loads(latest_data.decode("utf-8"))

    current_time = time.time()

    # One-time initialization of startup steer lock window.
    if STARTUP_STEER_LOCK_ENABLE and _STARTUP_STEER_LOCK_UNTIL.get(side, 0.0) <= 0.0:
        _STARTUP_STEER_LOCK_UNTIL[side] = current_time + max(0.0, float(STARTUP_STEER_LOCK_SEC))

    with vision_lock:
        prev_packet_time = float(boat_comm_states[side].get("last_packet_time", 0.0))
        prev_yaw_deg = float(boat_comm_states[side].get("yaw_deg", state.get("yaw", 0.0)))
        curr_yaw_deg = float(state.get("yaw", prev_yaw_deg))
        dt = current_time - prev_packet_time if prev_packet_time > 0.0 else 0.0
        if dt > 1e-3:
            yaw_delta = _normalize_angle_deg(curr_yaw_deg - prev_yaw_deg)
            yaw_rate_dps = yaw_delta / dt
        else:
            yaw_rate_dps = float(boat_comm_states[side].get("yaw_rate_dps", 0.0))

        boat_comm_states[side]["connected"] = True
        boat_comm_states[side]["last_packet_time"] = current_time
        boat_comm_states[side]["speed_mps"] = float(state.get("speed", 0.0))
        boat_comm_states[side]["leader_speed_mps"] = float(state.get("leader_speed", 0.0))
        boat_comm_states[side]["yaw_deg"] = curr_yaw_deg
        boat_comm_states[side]["yaw_rate_dps"] = yaw_rate_dps

    with vision_lock:
        front_state = vision_states[FRONT_STREAM_BY_BOAT[side]].copy()
        side_state = vision_states[SIDE_STREAM_BY_BOAT[side]].copy()

    front_detected = front_state["target_detected"]
    front_stale = front_state.get("target_stale", False)
    front_method = front_state["method"]
    front_offset = front_state["target_center_offset"]
    front_area = front_state["target_area"]
    last_known_offset = front_state.get("last_known_offset", 0.0)
    lost_search_dir = front_state.get("lost_search_dir", 1.0)
    front_predicted_offset = front_state.get("predicted_offset", front_offset)
    front_predicted_area = front_state.get("predicted_area", front_area)
    front_prediction_confidence = front_state.get("prediction_confidence", 0.0)
    front_track_area_velocity = front_state.get("track_area_velocity", 0.0)
    front_track_offset_velocity = front_state.get("track_offset_velocity", 0.0)

    side_detected = side_state["target_detected"]
    side_stale = side_state.get("target_stale", False)
    side_method = side_state["method"]
    side_target_kind = side_state.get("target_kind")
    side_offset = side_state["target_center_offset"]
    side_area = side_state["target_area"]
    side_leader_detected = bool(side_state.get("side_leader_detected", False))
    side_leader_offset = float(side_state.get("side_leader_center_offset", 0.0))
    side_follower_detected = bool(side_state.get("side_follower_detected", False))
    side_predicted_offset = side_state.get("predicted_offset", side_offset)
    side_predicted_area = side_state.get("predicted_area", side_area)
    side_prediction_confidence = side_state.get("prediction_confidence", 0.0)

    # Determine whether side tracking should be considered available.
    # Allow prediction-only side-follow if the bbox was recently lost but
    # the prediction confidence is sufficient (configurable in config.py).
    side_last_seen = float(side_state.get("last_detection_time", 0.0))
    side_time_since_seen = current_time - side_last_seen if side_last_seen > 0.0 else 1e6
    side_pred_ok = False
    if side_detected:
        side_pred_ok = True
    else:
        try:
            if SIDE_PREDICTION_FOLLOW_ENABLE and side_time_since_seen <= float(SIDE_PREDICTION_MAX_LOST_SEC) and float(side_prediction_confidence) >= float(SIDE_PREDICTION_MIN_CONF):
                # use predicted values from vision state when bbox is briefly lost
                side_effective_offset = side_state.get("predicted_offset", side_offset)
                side_effective_area = side_state.get("predicted_area", side_area)
                side_stale = True
                side_pred_ok = True
        except Exception:
            pass

    formation = formation_targets[side]
    front_visual_ref_ready = formation.get("front_visual_initialized", False)
    desired_front_offset = formation.get("desired_front_offset", 0.0)
    desired_front_area = formation.get("desired_front_area", 0.0)
    side_visual_ref_ready = formation.get("side_visual_initialized", False)
    desired_side_offset = formation.get("desired_side_offset", 0.0)
    desired_side_area = formation.get("desired_side_area", 0.0)
    desired_side_target_kind = formation.get("desired_side_target_kind")

    # If side-camera detection is globally disabled at runtime, ignore side detections
    # so the controller will rely only on the front camera for formation keeping.
    if not bool(runtime_settings.get("enable_side_detection", True)):
        side_detected = False
        side_pred_ok = False
        side_visual_ref_ready = False

    throttle = 1.0
    steer = 0.0
    throttle_ceiling = FOLLOW_MAX_THROTTLE
    side_steer_bias = 0.0
    side_throttle_bias = 0.0
    side_effective_offset = side_offset
    side_effective_area = side_area
    side_area_error_ratio = 0.0
    pair_catchup_boost = 0.0
    peer_front_area = None
    pair_area_gap_ratio = 0.0
    edge_offset = False
    edge_edge_factor = 0.0
    edge_throttle_floor = None
    side_reference_matches = True
    side_control_offset = side_offset
    steer_gain, throttle_gain = get_tracking_gains(front_method, front_stale)

    if side_pred_ok and side_visual_ref_ready:
        side_prediction_control_weight = clamp(
            (side_prediction_confidence - PREDICTION_CONTROL_MIN_CONF) / max(1e-5, (1.0 - PREDICTION_CONTROL_MIN_CONF)),
            0.0,
            1.0,
        )
        # Reduce blending when side detection method is only FOLLOWER (less reliable)
        try:
            if side_method == "FOLLOWER":
                side_prediction_control_weight *= float(SIDE_PREDICTION_METHOD_BLEND)
        except Exception:
            pass
        side_effective_offset = blend_value(
            side_offset,
            side_predicted_offset,
            clamp(side_prediction_control_weight * PREDICTION_OFFSET_BLEND, 0.0, 1.0),
        )
        side_effective_area = blend_value(
            side_area,
            side_predicted_area,
            clamp(side_prediction_control_weight * PREDICTION_AREA_BLEND, 0.0, 1.0),
        )

        side_control_offset = side_effective_offset
        if (
            str(SIDE_CAMERA_TARGET_MODE).strip().lower() == "dual"
            and side_leader_detected
            and side_follower_detected
        ):
            leader_edge_factor = clamp(
                (abs(side_leader_offset) - float(SIDE_DUAL_LEADER_EDGE_START))
                / max(1e-5, (1.0 - float(SIDE_DUAL_LEADER_EDGE_START))),
                0.0,
                1.0,
            )
            leader_blend = blend_value(
                float(SIDE_DUAL_LEADER_OFFSET_BLEND),
                float(SIDE_DUAL_LEADER_EDGE_BLEND),
                leader_edge_factor,
            )
            side_control_offset = blend_value(side_effective_offset, side_leader_offset, leader_blend)

        edge_offset_abs = abs(side_control_offset)
        edge_offset = edge_offset_abs >= float(SIDE_EDGE_IGNORE_OFFSET)
        if side == "Right":
            edge_edge_factor = clamp(
                (edge_offset_abs - float(RIGHT_SIDE_EDGE_RECOVERY_START))
                / max(1e-5, float(RIGHT_SIDE_EDGE_RECOVERY_END) - float(RIGHT_SIDE_EDGE_RECOVERY_START)),
                0.0,
                1.0,
            )
        right_edge_recovery_gain = 1.0
        if side == "Right" and edge_edge_factor > 0.0:
            # Use only the right boat's own motion state to recover more
            # aggressively when the leader stays near the side-camera border.
            comm = boat_comm_states.get(side, {})
            ego_yaw_rate = abs(float(comm.get("yaw_rate_dps", 0.0)))
            ego_speed = abs(float(comm.get("speed_mps", 0.0)))
            motion_factor = clamp((ego_yaw_rate / 35.0) + (ego_speed / 2.5), 0.0, 1.0)
            recovery_factor = clamp(edge_edge_factor * motion_factor, 0.0, 1.0)
            right_edge_recovery_gain = 1.0 + (float(RIGHT_SIDE_EDGE_RECOVERY_GAIN) - 1.0) * recovery_factor
            edge_throttle_floor = clamp(
                float(SEARCH_FORWARD_THROTTLE) * float(RIGHT_SIDE_EDGE_THROTTLE_FLOOR_SCALE) * (0.75 + 0.25 * recovery_factor),
                0.0,
                FOLLOW_MAX_THROTTLE * 0.78,
            )

        side_offset_error = side_control_offset - desired_side_offset
        if SIDE_STEER_ENABLED and abs(side_offset_error) > SIDE_STEER_DEADZONE_H:
            side_steer_bias = clamp(
                side_offset_error * SIDE_TRACK_STEER_KP * SIDE_TRACK_STEER_SIGN_BY_BOAT[side],
                -SIDE_TRACK_MAX_STEER_BIAS,
                SIDE_TRACK_MAX_STEER_BIAS,
            )

        if SIDE_STEER_ENABLED and side == "Right" and edge_edge_factor > 0.0:
            side_steer_bias = clamp(
                side_steer_bias * right_edge_recovery_gain,
                -SIDE_TRACK_MAX_STEER_BIAS,
                SIDE_TRACK_MAX_STEER_BIAS,
            )

        side_area_error_ratio = normalize_area_error(desired_side_area, side_effective_area)
        shaped_side_area_error = shape_area_error(side_area_error_ratio)
        side_throttle_bias = clamp(
            shaped_side_area_error * SIDE_TRACK_AREA_GAIN,
            -SIDE_TRACK_MAX_THROTTLE_BIAS,
            SIDE_TRACK_MAX_THROTTLE_BIAS,
        )

        side_reference_matches = (
            desired_side_target_kind is None
            or side_target_kind is None
            or desired_side_target_kind == side_target_kind
        )
        if not side_reference_matches:
            side_steer_bias *= float(SIDE_REFERENCE_MISMATCH_BIAS_SCALE)
            side_throttle_bias *= float(SIDE_REFERENCE_MISMATCH_BIAS_SCALE)
            side_area_error_ratio *= float(SIDE_REFERENCE_MISMATCH_BIAS_SCALE)

        if side_stale:
            side_steer_bias *= SIDE_STALE_BIAS_SCALE
            side_throttle_bias *= SIDE_STALE_BIAS_SCALE

    # KF approach ratio: set inside if front_detected, used at the EMA site below.
    _kf_approach_ratio = 0.0

    if front_detected:
        if front_method in ("YOLO", "FUSED"):
            if front_visual_ref_ready and desired_front_area > YOLO_AREA_MIN:
                target_opt = desired_front_area
                target_min = max(YOLO_AREA_MIN, desired_front_area * (1.0 - VISION_FRONT_AREA_TOLERANCE_RATIO))
                target_max = min(YOLO_AREA_MAX, desired_front_area * (1.0 + VISION_FRONT_AREA_TOLERANCE_RATIO))
            else:
                target_opt, target_min, target_max = YOLO_AREA_OPT, YOLO_AREA_MIN, YOLO_AREA_MAX
        else:
            target_opt, target_min, target_max = WAKE_AREA_OPT, WAKE_AREA_MIN, WAKE_AREA_MAX

        prediction_control_weight = clamp(
            (front_prediction_confidence - PREDICTION_CONTROL_MIN_CONF) / max(1e-5, (1.0 - PREDICTION_CONTROL_MIN_CONF)),
            0.0,
            1.0,
        )

        effective_offset = blend_value(
            front_offset,
            front_predicted_offset,
            clamp(prediction_control_weight * PREDICTION_OFFSET_BLEND, 0.0, 1.0),
        )
        effective_area = blend_value(
            front_area,
            front_predicted_area,
            clamp(prediction_control_weight * PREDICTION_AREA_BLEND, 0.0, 1.0),
        )
        # If the leader looks small in the frame, treat it as "far" and
        # prefer chasing (reduce formation urgency and boost chase terms).
        # When the formation reference is calibrated, derive the threshold dynamically
        # from the desired_front_area so it scales with the actual camera geometry.
        try:
            if front_visual_ref_ready and float(desired_front_area) > float(YOLO_AREA_MIN):
                _far_threshold = float(desired_front_area) * float(LEADER_FAR_AREA_SCALE)
            else:
                _far_threshold = float(LEADER_FAR_AREA_THRESHOLD)
            is_far = float(effective_area) < _far_threshold
        except Exception:
            is_far = False
        steer_error = effective_offset - desired_front_offset if front_visual_ref_ready else effective_offset
        predicted_area_ratio = normalize_area_error(target_opt, front_predicted_area)
        area_velocity_ratio = float(front_track_area_velocity) / max(float(target_opt), 1.0)

        active_kv_steer = float(RIGHT_KV_STEER) if side == "Right" else float(KV_STEER)
        if abs(steer_error) > STEER_DEADZONE_H:
            steer = clamp(steer_error * active_kv_steer * steer_gain, -1.0, 1.0)
        else:
            steer = 0.0

        try:
            if front_stale or (front_prediction_confidence < FRONT_PRIORITY_CONFIDENCE):
                side_steer_bias *= FRONT_PRIORITY_STALE_SCALE
                side_throttle_bias *= FRONT_PRIORITY_STALE_SCALE
        except Exception:
            pass

        steer = clamp(steer + side_steer_bias, -1.0, 1.0)

        predictive_steer_bias, predictive_throttle_boost, predictive_confidence = compute_turn_predictive_assist(
            front_track_offset_velocity,
            front_track_area_velocity,
            front_prediction_confidence,
        )
        if predictive_confidence > 0.0:
            steer = clamp(steer + predictive_steer_bias, -1.0, 1.0)

        turn_intensity = clamp(
            (abs(steer) - STEER_DEADZONE_H) / max(1e-5, (1.0 - STEER_DEADZONE_H)),
            0.0,
            1.0,
        )
        if turn_intensity > 0.0:
            if front_method in ("YOLO", "FUSED") and front_visual_ref_ready:
                target_opt *= 1.0 + (VISION_TURN_FORMATION_AREA_BOOST * turn_intensity)
                target_min *= 1.0 + (VISION_TURN_FORMATION_AREA_BOOST * turn_intensity)
                target_max *= 1.0 + (VISION_TURN_FORMATION_AREA_BOOST * turn_intensity)
                steer = clamp(
                    steer + math.copysign(VISION_TURN_FORMATION_STEER_BOOST * turn_intensity, steer),
                    -1.0,
                    1.0,
                )
                throttle_ceiling = max(throttle_ceiling, FOLLOW_FAR_MAX_THROTTLE * 0.92)
            elif front_method == "WAKE":
                steer = clamp(
                    steer + math.copysign(VISION_TURN_FORMATION_STEER_BOOST * 0.7 * turn_intensity, steer),
                    -1.0,
                    1.0,
                )
                throttle_ceiling = max(throttle_ceiling, VISION_FRONT_CRUISE_THROTTLE)

        if predictive_confidence > 0.0:
            throttle += predictive_throttle_boost
            throttle_ceiling = max(throttle_ceiling, VISION_TURN_PREDICTIVE_SPEED_CEILING)

        if steer != 0.0:
            with vision_lock:
                vision_states[FRONT_STREAM_BY_BOAT[side]]["lost_search_dir"] = 1.0 if steer > 0 else -1.0

        front_area_error_ratio = normalize_area_error(target_opt, effective_area)
        shaped_front_area_error = shape_area_error(front_area_error_ratio)

        # Require a small persistence for area-too-close before zeroing throttle.
        # Do not treat a small/negative area error as "too close" when the
        # leader is classified as far (prevents false zeroing when measured
        # area is noisy while the target is actually distant).
        if effective_area > target_max or (front_area_error_ratio <= 0.0 and not is_far):
            _AREA_OVER_MAX_COUNT[side] = _AREA_OVER_MAX_COUNT.get(side, 0) + 1
        else:
            _AREA_OVER_MAX_COUNT[side] = 0

        if _AREA_OVER_MAX_COUNT.get(side, 0) >= int(AREA_PERSISTENCE_FRAMES):
            # Log the zeroing event for diagnosis (Right follower logfile will capture it).
            _log_right_debug(
                side,
                current_time,
                front_area if 'front_area' in locals() else 0.0,
                effective_area if 'effective_area' in locals() else 0.0,
                front_predicted_area if 'front_predicted_area' in locals() else 0.0,
                front_prediction_confidence if 'front_prediction_confidence' in locals() else 0.0,
                front_stale if 'front_stale' in locals() else False,
                side_detected if 'side_detected' in locals() else False,
                side_prediction_confidence if 'side_prediction_confidence' in locals() else 0.0,
                edge_edge_factor if 'edge_edge_factor' in locals() else 0.0,
                _LAST_THROTTLE.get(side, 0.0),
                0.0,
            )
            throttle = 0.0
        else:
            if effective_area < target_min:
                throttle = FOLLOW_MAX_THROTTLE * throttle_gain
            else:
                throttle = clamp(shaped_front_area_error * VISION_FRONT_AREA_GAIN * throttle_gain, 0.0, FOLLOW_MAX_THROTTLE)
                if throttle > 0.0:
                    throttle = max(throttle, VISION_FRONT_AREA_MIN_THROTTLE)

        far_boost = compute_visual_far_boost(
            area=front_area,
            predicted_area=effective_area,
            area_velocity=front_track_area_velocity,
            target_opt=target_opt,
            method=front_method,
        )
        if far_boost > 0.0:
            if is_far:
                far_boost *= FAR_VISUAL_FAR_BOOST_MULTIPLIER
                throttle_ceiling = max(throttle_ceiling, FOLLOW_FAR_MAX_THROTTLE)
            throttle += far_boost

        cruise_throttle = compute_centered_cruise_throttle(
            steer_error=steer_error,
            area_error_ratio=front_area_error_ratio,
            predicted_area_ratio=predicted_area_ratio,
            area_velocity_ratio=area_velocity_ratio,
        )
        throttle = max(throttle, cruise_throttle)

        # Leader-speed feedforward: when at (or near) target distance, set a minimum
        # throttle proportional to the leader's current speed.  This prevents the
        # coast-to-near-zero → fall-behind → max-throttle-chase oscillation cycle by
        # providing a "soft landing" that keeps the follower matched to leader cruise speed.
        if front_visual_ref_ready and front_area_error_ratio > -float(VISION_AREA_ERROR_DEADZONE_RATIO):
            leader_ff = clamp(
                float(state.get("leader_speed", 0.0)) * float(LEADER_SPEED_THROTTLE_FF),
                0.0,
                float(FOLLOW_MAX_THROTTLE) * 0.95,
            )
            throttle = max(throttle, leader_ff)

        throttle += side_throttle_bias

        turn_catchup_boost = compute_turn_catchup_boost(
            steer=steer,
            front_area_error_ratio=front_area_error_ratio,
            side_area_error_ratio=side_area_error_ratio,
        )
        if turn_catchup_boost > 0.0:
            throttle += turn_catchup_boost
            throttle_ceiling = max(throttle_ceiling, VISION_TURN_SPEED_CEILING)

        if front_method == "WAKE":
            throttle = min(throttle, VISION_FRONT_CRUISE_THROTTLE)

        pair_catchup_boost, peer_front_area, pair_area_gap_ratio = compute_pair_catchup_boost(
            side,
            front_detected,
            front_stale,
            front_method,
            effective_area,
        )
        if pair_catchup_boost > 0.0:
            if is_far:
                pair_catchup_boost = clamp(
                    pair_catchup_boost * PAIR_CATCHUP_MULTIPLIER_WHEN_FAR,
                    0.0,
                    FOLLOWER_PAIR_CATCHUP_MAX,
                )
            throttle += pair_catchup_boost
            throttle_ceiling = max(throttle_ceiling, FOLLOW_FAR_MAX_THROTTLE)

        steer_mag = abs(steer)
        if steer_mag > VISION_TURN_SLOWDOWN_START:
            turn_excess = clamp(
                (steer_mag - VISION_TURN_SLOWDOWN_START) / max(1e-5, (1.0 - VISION_TURN_SLOWDOWN_START)),
                0.0,
                1.0,
            )
            slowdown_scale = 1.0 - ((1.0 - VISION_TURN_SLOWDOWN_MIN_SCALE) * turn_excess)
            throttle *= clamp(slowdown_scale, VISION_TURN_SLOWDOWN_MIN_SCALE, 1.0)

        if front_stale:
            steer *= STALE_TARGET_STEER_SCALE
            if throttle > 0.0:
                throttle = max(throttle * STALE_TARGET_THROTTLE_SCALE, SEARCH_FORWARD_THROTTLE)

        # KF approach-rate damper: when KF is ON and area is GROWING (follower closing
        # on the leader), subtract a D-term from throttle proportional to the approach
        # rate to prevent bang-bang overshoot.  _kf_approach_ratio is also used below
        # at the EMA site to boost alpha (faster decay) during approach.
        if ENABLE_KALMAN_FILTER and front_visual_ref_ready and float(front_track_area_velocity) > 0.0:
            _kf_approach_ratio = float(front_track_area_velocity) / max(float(target_opt), 1.0)
            kf_d = clamp(
                _kf_approach_ratio * float(KF_APPROACH_THROTTLE_D_GAIN),
                0.0,
                float(KF_APPROACH_THROTTLE_D_MAX),
            )
            throttle = max(0.0, throttle - kf_d)

    else:
        side_chase_available = SIDE_STEER_ENABLED and side_pred_ok and side_target_kind in ("leader", "follower")

        if side_chase_available:
            steer = clamp(side_steer_bias / max(FRONT_PRIORITY_NO_FRONT_STEER_SCALE, 1e-5), -SEARCH_MODE_STEER, SEARCH_MODE_STEER)

            if steer != 0.0:
                with vision_lock:
                    vision_states[FRONT_STREAM_BY_BOAT[side]]["lost_search_dir"] = 1.0 if steer > 0 else -1.0

            side_target_opt = get_side_area_target_opt(side_visual_ref_ready, desired_side_area, side_target_kind)
            side_follow_error_ratio = normalize_area_error(side_target_opt, side_effective_area)
            side_follow_shaped = shape_area_error(side_follow_error_ratio)
            if not side_reference_matches:
                side_follow_shaped *= float(SIDE_REFERENCE_MISMATCH_BIAS_SCALE)

            side_chase_throttle_gain = FOLLOWER_TRACK_THROTTLE_GAIN if side_method == "FOLLOWER" else YOLO_TRACK_THROTTLE_GAIN

            if side_follow_error_ratio <= 0.0:
                if edge_offset:
                    throttle = float(SEARCH_FORWARD_THROTTLE) * float(SIDE_EDGE_THROTTLE_SCALE)
                else:
                    throttle = 0.0
            else:
                base_throttle = (side_follow_shaped * SIDE_TRACK_AREA_GAIN * side_chase_throttle_gain) + (SEARCH_FORWARD_THROTTLE * 0.70)
                if edge_offset:
                    throttle = max(base_throttle, float(SEARCH_FORWARD_THROTTLE) * float(SIDE_EDGE_THROTTLE_SCALE))
                    throttle = clamp(throttle, 0.0, FOLLOW_MAX_THROTTLE * 0.78)
                else:
                    throttle = clamp(base_throttle, 0.0, FOLLOW_MAX_THROTTLE * 0.78)

            if side == "Right" and edge_edge_factor > 0.0:
                edge_boost = clamp(0.15 + 0.35 * edge_edge_factor, 0.0, 0.45)
                throttle = clamp(
                    blend_value(_LAST_THROTTLE[side], throttle + edge_boost, float(RIGHT_SIDE_THROTTLE_SMOOTH_ALPHA)),
                    0.0,
                    FOLLOW_MAX_THROTTLE * 0.82,
                )

            if side_stale:
                steer *= SIDE_STALE_BIAS_SCALE
                throttle *= SIDE_STALE_BIAS_SCALE

            if edge_throttle_floor is not None:
                throttle = max(throttle, edge_throttle_floor)
        elif DISABLE_SEARCH_MODE:
            throttle = 0.0
            steer = 0.0
        else:
            throttle = SEARCH_FORWARD_THROTTLE
            if abs(last_known_offset) > STEER_DEADZONE_H:
                steer = clamp(last_known_offset * KV_STEER * SEARCH_STEER_GAIN, -SEARCH_MODE_STEER, SEARCH_MODE_STEER)
            else:
                steer = lost_search_dir * SEARCH_MODE_STEER

    startup_sync_released = bool(runtime_settings.get("startup_sync_released", True))
    startup_sync_status = str(runtime_settings.get("startup_sync_status", "released"))
    if not startup_sync_released:
        throttle = 0.0
        steer = filter_steer_command(side, 0.0, time.time())
        _LAST_THROTTLE[side] = 0.0
        _log_right_debug(side, time.time(), front_area if 'front_area' in locals() else 0.0, 
                         front_predicted_area if 'front_predicted_area' in locals() else 0.0,
                         front_predicted_area if 'front_predicted_area' in locals() else 0.0,
                         front_prediction_confidence if 'front_prediction_confidence' in locals() else 0.0,
                         front_stale if 'front_stale' in locals() else False,
                         side_detected if 'side_detected' in locals() else False,
                         side_prediction_confidence if 'side_prediction_confidence' in locals() else 0.0,
                         edge_edge_factor if 'edge_edge_factor' in locals() else 0.0,
                         _LAST_THROTTLE.get(side, 0.0), 0.0)
        _send_control_command(sock, tx_port, 0.0, steer)

        speed_mps = state.get("speed", 0.0)
        leader_speed_mps = state.get("leader_speed", 0.0)
        distance = compute_distance_from_area(front_area, desired_front_area, YOLO_AREA_OPT) if front_detected else 0.0
        target_distance = compute_distance_from_area(desired_front_area, desired_front_area, YOLO_AREA_OPT) if (front_detected and front_visual_ref_ready) else 0.0
        formation_error = compute_formation_error(front_offset, desired_front_offset, front_area, desired_front_area) if (front_detected and front_visual_ref_ready) else 0.0

        return {
            "detected": front_detected,
            "stale": front_stale,
            "method": front_method,
            "side_detected": side_detected,
            "side_stale": side_stale,
            "side_method": side_method,
            "throttle": 0.0,
            "steer": steer,
            "area": front_area if front_detected else 0.0,
            "side_area": side_area if side_detected else 0.0,
            "offset": front_offset if front_detected else 0.0,
            "side_offset": side_effective_offset if side_detected else 0.0,
            "peer_area": peer_front_area if peer_front_area is not None else 0.0,
            "pair_area_gap_ratio": pair_area_gap_ratio,
            "pair_catchup_boost": 0.0,
            "pred_offset": front_predicted_offset if front_detected else 0.0,
            "pred_conf": front_prediction_confidence if front_detected else 0.0,
            "side_steer_bias": 0.0,
            "side_throttle_bias": 0.0,
            "speed_knots": speed_mps * 1.94384,
            "leader_speed_knots": leader_speed_mps * 1.94384,
            "distance": distance,
            "target_distance": target_distance,
            "formation_error": formation_error,
            "startup_sync_hold": True,
            "startup_sync_status": startup_sync_status,
            # pass through world coordinates (Unity provides these in the UDP state)
            "x": float(state.get("x", 0.0)),
            "z": float(state.get("z", 0.0)),
            "yaw": float(state.get("yaw", 0.0)),
            "leader_x": float(state.get("leader_x", 0.0)),
            "leader_z": float(state.get("leader_z", 0.0)),
            "leader_yaw": float(state.get("leader_yaw", 0.0)),
            "leader_forward_x": float(state.get("leader_forward_x", 0.0)),
            "leader_forward_z": float(state.get("leader_forward_z", 0.0)),
        }

    # Enforce a conservative minimum forward throttle when the front target
    # is detected but visually small (far). This avoids false full-stops
    # caused by noisy area/deadzone logic when the leader is actually distant.
    try:
        startup_ok = bool(runtime_settings.get("startup_sync_released", True))
    except Exception:
        startup_ok = True
    if front_detected and is_far and startup_ok and not front_stale:
        throttle = max(throttle, float(SEARCH_FORWARD_THROTTLE))

    throttle = clamp(throttle, 0.0, throttle_ceiling)

    formation_mode = str(runtime_settings.get("formation_mode", "v")).strip().lower()
    Line_transition_until = float(runtime_settings.get("right_line_transition_until", 0.0))
    Line_transition_scale = float(runtime_settings.get("right_line_throttle_scale", 0.75))
    v_recovery_until = float(runtime_settings.get("right_v_recovery_until", 0.0))
    v_recovery_boost = float(runtime_settings.get("right_v_recovery_boost", 0.12))

    if (
        side == "Right"
        and formation_mode == "line"
        and time.time() < Line_transition_until
    ):
        throttle *= Line_transition_scale

    if (
        side == "Right"
        and formation_mode == "v"
        and time.time() < v_recovery_until
        and front_visual_ref_ready
        and front_area_error_ratio > 0.0
    ):
        catchup_ratio = clamp(front_area_error_ratio, 0.0, 1.0)
        throttle += v_recovery_boost * catchup_ratio

    prev_throttle_ema = _LAST_THROTTLE.get(side, throttle)
    throttle_alpha = float(RIGHT_THROTTLE_SMOOTH_ALPHA) if side == "Right" else float(THROTTLE_SMOOTH_ALPHA)
    # KF alpha boost: when KF reports approach (area growing), anticipate the
    # setpoint drop and begin decaying the EMA faster before it actually lands.
    if _kf_approach_ratio > 0.0:
        alpha_boost = clamp(
            _kf_approach_ratio * float(KF_APPROACH_ALPHA_GAIN),
            0.0,
            float(KF_APPROACH_THROTTLE_ALPHA_MAX) - throttle_alpha,
        )
        throttle_alpha = throttle_alpha + alpha_boost
    # Asymmetric EMA: throttle can fall faster than it rises.
    # When the computed setpoint is below the current smoothed value the EMA
    # alpha is scaled up so the command follows the setpoint promptly.
    # This prevents EMA inertia from extending the overshoot window while
    # keeping the slow-rise (ramp-up) direction smooth.
    if throttle < prev_throttle_ema:
        throttle_alpha = min(
            float(THROTTLE_FAST_DECREASE_ALPHA_MAX),
            throttle_alpha * float(THROTTLE_DECREASE_ALPHA_SCALE),
        )
    throttle = blend_value(prev_throttle_ema, throttle, throttle_alpha)
    _LAST_THROTTLE[side] = throttle

    # Keep both followers heading straight during startup window.
    if STARTUP_STEER_LOCK_ENABLE:
        if current_time < _STARTUP_STEER_LOCK_UNTIL.get(side, 0.0):
            steer = 0.0

    steer = filter_steer_command(side, clamp(steer, -1.0, 1.0), time.time())

    _log_right_debug(side, time.time(), front_area if 'front_area' in locals() else 0.0, 
                     front_predicted_area if 'front_predicted_area' in locals() else 0.0,
                     front_predicted_area if 'front_predicted_area' in locals() else 0.0,
                     front_prediction_confidence if 'front_prediction_confidence' in locals() else 0.0,
                     front_stale if 'front_stale' in locals() else False,
                     side_detected if 'side_detected' in locals() else False,
                     side_prediction_confidence if 'side_prediction_confidence' in locals() else 0.0,
                     edge_edge_factor if 'edge_edge_factor' in locals() else 0.0,
                     _LAST_THROTTLE.get(side, 0.0), throttle)
    _send_control_command(sock, tx_port, throttle, steer)

    speed_mps = state.get("speed", 0.0)
    leader_speed_mps = state.get("leader_speed", 0.0)
    
    # Compute distance and formation error for evaluation
    distance = compute_distance_from_area(front_area, desired_front_area, YOLO_AREA_OPT) if front_detected else 0.0
    target_distance = compute_distance_from_area(desired_front_area, desired_front_area, YOLO_AREA_OPT) if (front_detected and front_visual_ref_ready) else 0.0
    formation_error = compute_formation_error(front_offset, desired_front_offset, front_area, desired_front_area) if (front_detected and front_visual_ref_ready) else 0.0
    
    return {
        "detected": front_detected,
        "stale": front_stale,
        "method": front_method,
        "side_detected": side_detected,
        "side_stale": side_stale,
        "side_method": side_method,
        "throttle": throttle,
        "steer": steer,
        "area": front_area if front_detected else 0.0,
        "side_area": side_area if side_detected else 0.0,
        "offset": front_offset if front_detected else 0.0,
        "side_offset": side_effective_offset if side_detected else 0.0,
        "peer_area": peer_front_area if peer_front_area is not None else 0.0,
        "pair_area_gap_ratio": pair_area_gap_ratio,
        "pair_catchup_boost": pair_catchup_boost,
        "pred_offset": front_predicted_offset if front_detected else 0.0,
        "pred_conf": front_prediction_confidence if front_detected else 0.0,
        "side_steer_bias": side_steer_bias,
        "side_throttle_bias": side_throttle_bias,
        "speed_knots": speed_mps * 1.94384,
        "leader_speed_knots": leader_speed_mps * 1.94384,
        "distance": distance,
        "target_distance": target_distance,
        "formation_error": formation_error,
        "startup_sync_hold": False,
        "startup_sync_status": startup_sync_status,
        # pass through world coordinates (Unity provides these in the UDP state)
        "x": float(state.get("x", 0.0)),
        "z": float(state.get("z", 0.0)),
        "yaw": float(state.get("yaw", 0.0)),
        "leader_x": float(state.get("leader_x", 0.0)),
        "leader_z": float(state.get("leader_z", 0.0)),
        "leader_yaw": float(state.get("leader_yaw", 0.0)),
        "leader_forward_x": float(state.get("leader_forward_x", 0.0)),
        "leader_forward_z": float(state.get("leader_forward_z", 0.0)),
    }
