'''
    Vision-based control logic for the USV, 
    processing camera data to compute throttle and steering commands.
'''

import json
import math
import time

from .config import *
from .helpers import blend_value, clamp, filter_steer_command, get_peer_boat_side
from .state import boat_comm_states, formation_targets, vision_lock, vision_states


def _normalize_angle_deg(angle_deg):
    value = float(angle_deg)
    while value > 180.0:
        value -= 360.0
    while value < -180.0:
        value += 360.0
    return value


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
    side_offset = side_state["target_center_offset"]
    side_area = side_state["target_area"]
    side_predicted_offset = side_state.get("predicted_offset", side_offset)
    side_predicted_area = side_state.get("predicted_area", side_area)
    side_prediction_confidence = side_state.get("prediction_confidence", 0.0)

    formation = formation_targets[side]
    front_visual_ref_ready = formation.get("front_visual_initialized", False)
    desired_front_offset = formation.get("desired_front_offset", 0.0)
    desired_front_area = formation.get("desired_front_area", 0.0)
    side_visual_ref_ready = formation.get("side_visual_initialized", False)
    desired_side_offset = formation.get("desired_side_offset", 0.0)
    desired_side_area = formation.get("desired_side_area", 0.0)

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
    steer_gain, throttle_gain = get_tracking_gains(front_method, front_stale)

    if side_detected and side_visual_ref_ready:
        side_prediction_control_weight = clamp(
            (side_prediction_confidence - PREDICTION_CONTROL_MIN_CONF) / max(1e-5, (1.0 - PREDICTION_CONTROL_MIN_CONF)),
            0.0,
            1.0,
        )
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

        side_offset_error = side_effective_offset - desired_side_offset
        if abs(side_offset_error) > SIDE_STEER_DEADZONE_H:
            side_steer_bias = clamp(
                side_offset_error * SIDE_TRACK_STEER_KP * SIDE_TRACK_STEER_SIGN_BY_BOAT[side],
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

        if side_stale:
            side_steer_bias *= SIDE_STALE_BIAS_SCALE
            side_throttle_bias *= SIDE_STALE_BIAS_SCALE

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
        try:
            is_far = float(effective_area) < float(LEADER_FAR_AREA_THRESHOLD)
        except Exception:
            is_far = False
        steer_error = effective_offset - desired_front_offset if front_visual_ref_ready else effective_offset
        predicted_area_ratio = normalize_area_error(target_opt, front_predicted_area)
        area_velocity_ratio = float(front_track_area_velocity) / max(float(target_opt), 1.0)

        if abs(steer_error) > STEER_DEADZONE_H:
            steer = clamp(steer_error * KV_STEER * steer_gain, -1.0, 1.0)
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

        if effective_area > target_max or front_area_error_ratio <= 0.0:
            throttle = 0.0
        elif effective_area < target_min:
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

    else:
        side_chase_available = side_detected and (side_method == "FOLLOWER")

        if side_chase_available:
            steer = clamp(side_steer_bias / max(FRONT_PRIORITY_NO_FRONT_STEER_SCALE, 1e-5), -SEARCH_MODE_STEER, SEARCH_MODE_STEER)

            if steer != 0.0:
                with vision_lock:
                    vision_states[FRONT_STREAM_BY_BOAT[side]]["lost_search_dir"] = 1.0 if steer > 0 else -1.0

            side_target_opt = desired_side_area if (side_visual_ref_ready and desired_side_area > FOLLOWER_AREA_MIN) else FOLLOWER_AREA_OPT
            side_follow_error_ratio = normalize_area_error(side_target_opt, side_effective_area)
            side_follow_shaped = shape_area_error(side_follow_error_ratio)

            if side_follow_error_ratio <= 0.0:
                throttle = 0.0
            else:
                throttle = clamp(
                    (side_follow_shaped * SIDE_TRACK_AREA_GAIN * FOLLOWER_TRACK_THROTTLE_GAIN) + (SEARCH_FORWARD_THROTTLE * 0.70),
                    0.0,
                    FOLLOW_MAX_THROTTLE * 0.78,
                )

            if side_stale:
                steer *= SIDE_STALE_BIAS_SCALE
                throttle *= SIDE_STALE_BIAS_SCALE
        elif DISABLE_SEARCH_MODE:
            throttle = 0.0
            steer = 0.0
        else:
            throttle = SEARCH_FORWARD_THROTTLE
            if abs(last_known_offset) > STEER_DEADZONE_H:
                steer = clamp(last_known_offset * KV_STEER * SEARCH_STEER_GAIN, -SEARCH_MODE_STEER, SEARCH_MODE_STEER)
            else:
                steer = lost_search_dir * SEARCH_MODE_STEER

    throttle = clamp(throttle, 0.0, throttle_ceiling)
    steer = filter_steer_command(side, clamp(steer, -1.0, 1.0), time.time())

    msg = json.dumps({"throttle": throttle, "steer": steer})
    sock.sendto(msg.encode("utf-8"), (UDP_IP, tx_port))

    speed_mps = state.get("speed", 0.0)
    leader_speed_mps = state.get("leader_speed", 0.0)
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
    }
