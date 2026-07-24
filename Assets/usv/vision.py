import socket
import struct
import time

import cv2
import numpy as np
from ultralytics import YOLO

from depth_Anything import DepthAnythingEstimator

try:
    import torch
except Exception:
    torch = None

from .config import *
from .helpers import (
    blend_value,
    clamp,
    draw_labeled_box,
    draw_prediction_arrow,
    get_model_class_name,
    get_yolo_box_color,
    make_status_frame,
    recv_exact,
)
from .state import (
    boat_comm_states,
    display_frames,
    formation_targets,
    frame_lock,
    latest_frames,
    runtime_settings,
    vision_lock,
    vision_states,
)
from .kalman import KalmanFilter


def build_track_candidate(bbox, area, center_offset, center, method, target_kind=None, det_conf=1.0):
    return {
        "bbox": bbox,
        "area": area,
        "center_offset": center_offset,
        "center": center,
        "method": method,
        "target_kind": target_kind,
        "det_conf": float(det_conf),
    }


def get_scaled_reference_area(area):
    scale = max(1e-3, float(FORMATION_SCALE_MULTIPLIER))
    return max(1.0, float(area) / (scale * scale))


def select_side_track_candidate(leader_target, follower_target, previous_target_kind=None):
    mode = str(SIDE_CAMERA_TARGET_MODE).strip().lower()

    if mode == "dual":
        return follower_target or leader_target
    if mode == "leader_only":
        return leader_target
    if mode == "follower_only":
        return follower_target
    if mode == "follower_preferred":
        return follower_target or leader_target
    if mode == "best_area":
        if leader_target is not None and follower_target is not None:
            leader_score = float(leader_target.get("area", 0.0))
            follower_score = float(follower_target.get("area", 0.0))
            if previous_target_kind == "leader":
                leader_score *= 1.05
            elif previous_target_kind == "follower":
                follower_score *= 1.05
            return leader_target if leader_score >= follower_score else follower_target
        return leader_target or follower_target

    return leader_target or follower_target


def fuse_track_sources(yolo_target, wake_target):
    if yolo_target is None and wake_target is None:
        return None
    if yolo_target is None:
        fused = wake_target.copy()
        fused["method"] = "WAKE"
        fused["wake_weight"] = 1.0
        return fused
    if wake_target is None:
        fused = yolo_target.copy()
        fused["method"] = "YOLO"
        fused["wake_weight"] = 0.0
        return fused

    offset_gap = abs(yolo_target["center_offset"] - wake_target["center_offset"])
    wake_agreement = clamp(1.0 - (offset_gap / max(FUSION_MAX_OFFSET_GAP, 1e-5)), 0.0, 1.0)

    yolo_weight = FUSION_YOLO_OFFSET_WEIGHT
    wake_weight = FUSION_WAKE_OFFSET_WEIGHT * wake_agreement

    if wake_weight < FUSION_MIN_WAKE_WEIGHT:
        fused = yolo_target.copy()
        fused["method"] = "YOLO"
        fused["wake_weight"] = 0.0
        return fused

    weight_sum = yolo_weight + wake_weight
    fused_offset = (
        yolo_target["center_offset"] * yolo_weight
        + wake_target["center_offset"] * wake_weight
    ) / max(weight_sum, 1e-5)

    yolo_center = yolo_target["center"]
    wake_center = wake_target["center"]
    fused_center_x = int(round(
        (yolo_center[0] * yolo_weight + wake_center[0] * wake_weight) / max(weight_sum, 1e-5)
    ))
    fused_center = (fused_center_x, yolo_center[1])

    fused = yolo_target.copy()
    fused["center_offset"] = fused_offset
    fused["center"] = fused_center
    fused["method"] = "FUSED"
    fused["wake_weight"] = wake_weight / max(weight_sum, 1e-5)
    return fused


def lock_visual_reference(boat_side, role, center_offset, area, target_kind=None):
    formation_ref = formation_targets[boat_side]
    if role == "front":
        init_key = "front_visual_initialized"
        offset_key = "desired_front_offset"
        area_key = "desired_front_area"
        kind_key = "desired_front_target_kind"
        target_offset = VISION_FRONT_TARGET_OFFSET
    else:
        init_key = "side_visual_initialized"
        offset_key = "desired_side_offset"
        area_key = "desired_side_area"
        kind_key = "desired_side_target_kind"
        target_offset = VISION_SIDE_TARGET_OFFSET

    if formation_ref.get(init_key, False):
        return

    formation_ref[offset_key] = target_offset
    formation_ref[area_key] = get_scaled_reference_area(area)
    formation_ref[kind_key] = target_kind
    formation_ref[init_key] = True
    print(
        f"[Formation-{boat_side}] Locked {role} camera ref: "
        f"offset={target_offset:.3f} target_area={formation_ref[area_key]:.0f} "
        f"(scale={float(FORMATION_SCALE_MULTIPLIER):.2f}, class={target_kind or role}) "
        f"(observed offset={center_offset:.3f})"
    )


def configure_yolo_runtime(model):
    using_cuda = False
    half_enabled = False

    try:
        cv2.setUseOptimized(True)
        cv2.setNumThreads(VISION_CPU_THREADS)
    except Exception:
        pass

    if torch is None:
        return using_cuda, half_enabled

    try:
        torch.set_num_threads(VISION_CPU_THREADS)
    except Exception:
        pass

    try:
        torch.set_num_interop_threads(max(1, min(4, VISION_CPU_THREADS // 2)))
    except Exception:
        pass

    try:
        using_cuda = YOLO_DEVICE.startswith("cuda") and torch.cuda.is_available()
    except Exception:
        using_cuda = False

    if not using_cuda:
        return False, False

    try:
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
        model.to(YOLO_DEVICE)
    except Exception:
        pass

    if YOLO_ENABLE_TORCH_COMPILE:
        try:
            model.model = torch.compile(model.model, mode="reduce-overhead", fullgraph=False)
        except Exception:
            pass

    return True, True


def warmup_yolo_runtime(model, predict_kwargs):
    if not YOLO_ENABLE_WARMUP:
        return

    warmup_frame = np.zeros((YOLO_IMGSZ, YOLO_IMGSZ, 3), dtype=np.uint8)
    warmup_batch = [warmup_frame for _ in range(max(1, len(CAMERA_STREAMS)))]

    try:
        model.predict(warmup_batch, **predict_kwargs)
    except Exception as exc:
        print(f"[Vision] YOLO warmup skipped: {exc}")


def reset_vision_state(stream_name):
    with vision_lock:
        state = vision_states[stream_name]
        state["connected"] = False
        state["target_detected"] = False
        state["target_stale"] = False
        state["method"] = None
        state["target_bbox"] = None
        state["target_area"] = 0.0
        state["target_center_offset"] = 0.0
        state["target_depth"] = None
        state["target_depth_confidence"] = 0.0
        state["depth_status"] = "Depth disabled"
        state["depth_inference_ms"] = 0.0
        state["last_detection_time"] = 0.0
        state["last_known_offset"] = 0.0
        state["last_known_area"] = 0.0
        state["last_known_method"] = None
        state["track_prev_measurement_time"] = 0.0
        state["track_prev_center_offset"] = 0.0
        state["track_prev_center_y"] = 0.0
        state["track_prev_area"] = 0.0
        state["track_offset_velocity"] = 0.0
        state["track_vertical_velocity"] = 0.0
        state["track_area_velocity"] = 0.0
        state["predicted_offset"] = 0.0
        state["predicted_area"] = 0.0
        state["prediction_confidence"] = 0.0


def detect_stern_wake(frame, preferred_offset=None, reference_bbox=None):
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, WAKE_LOWER_WHITE, WAKE_UPPER_WHITE)

    sky_crop = int(height * WAKE_SKY_CROP_RATIO)
    boat_crop = int(height * WAKE_BOAT_CROP_RATIO)
    mask[:sky_crop, :] = 0
    mask[boat_crop:, :] = 0

    kernel_open = np.ones(WAKE_OPEN_KERNEL, np.uint8)
    kernel_close = np.ones(WAKE_CLOSE_KERNEL, np.uint8)
    kernel_dilate = np.ones(WAKE_DILATE_KERNEL, np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
    mask = cv2.dilate(mask, kernel_dilate, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_cnt = None
    best_area = 0.0
    best_score = -1.0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_WAKE_CONTOUR:
            continue

        x, y, w_box, h_box = cv2.boundingRect(cnt)
        if h_box < WAKE_MIN_BBOX_HEIGHT or w_box < WAKE_MIN_BBOX_WIDTH:
            continue

        aspect_ratio = h_box / max(float(w_box), 1.0)
        if aspect_ratio < WAKE_MIN_ASPECT_RATIO:
            continue

        fill_ratio = area / max(float(w_box * h_box), 1.0)
        if fill_ratio < WAKE_MIN_FILL_RATIO:
            continue

        center_y_norm = (y + (h_box * 0.5)) / max(float(height), 1.0)
        elongation_score = clamp(aspect_ratio / 2.2, 0.7, 1.7)
        height_score = clamp(h_box / max(height * 0.18, 1.0), 0.7, 1.6)
        mid_water_score = clamp(1.0 - abs(center_y_norm - 0.62) / 0.45, 0.55, 1.25)
        score = area * elongation_score * height_score * mid_water_score * clamp(fill_ratio / 0.30, 0.60, 1.35)

        moments = cv2.moments(cnt)
        if moments["m00"] == 0:
            continue

        cx = moments["m10"] / moments["m00"]
        center_offset = (cx - (width / 2.0)) / (width / 2.0)
        if abs(center_offset) > WAKE_MAX_CENTER_OFFSET:
            continue

        if preferred_offset is not None:
            offset_delta = abs(center_offset - preferred_offset)
            if offset_delta > WAKE_MAX_OFFSET_FROM_TRACK:
                continue
            score *= 1.0 - min(offset_delta, 1.0) * TRACK_REACQUIRE_BIAS
        else:
            score *= 1.0 - min(abs(center_offset), 1.0) * 0.18

        if reference_bbox is not None:
            ref_x1, ref_y1, ref_x2, ref_y2 = reference_bbox
            ref_center_x = (ref_x1 + ref_x2) * 0.5
            ref_offset = (ref_center_x - (width / 2.0)) / (width / 2.0)
            if abs(center_offset - ref_offset) > WAKE_MAX_OFFSET_FROM_YOLO:
                continue

            max_top_gap = max(16, int(height * WAKE_MAX_TOP_GAP_FROM_YOLO_RATIO))
            if y > (ref_y2 + max_top_gap):
                continue

            score *= clamp(
                1.0 - abs(center_offset - ref_offset) / max(WAKE_MAX_OFFSET_FROM_YOLO, 1e-5),
                0.35,
                1.10,
            )

        if score > best_score:
            best_score = score
            best_area = area
            best_cnt = cnt

    if best_cnt is None:
        return None

    moments = cv2.moments(best_cnt)
    if moments["m00"] == 0:
        return None

    cx = int(moments["m10"] / moments["m00"])
    cy = int(moments["m01"] / moments["m00"])
    x, y, w_box, h_box = cv2.boundingRect(best_cnt)
    center_offset = (cx - (width / 2.0)) / (width / 2.0)

    if (y + h_box) > height * (1.0 - WAKE_IGNORE_BOTTOM_RATIO):
        return None

    return {
        "bbox": (x, y, x + w_box, y + h_box),
        "area": best_area,
        "center_offset": center_offset,
        "center": (cx, cy),
        "mask": mask,
    }


def _compute_ego_offset_velocity(ego_yaw_rate_dps, ego_speed_mps, center_offset):
    if not PREDICTION_EGO_COMPENSATION_ENABLE:
        return 0.0

    yaw_term = float(ego_yaw_rate_dps) * float(PREDICTION_EGO_YAW_RATE_GAIN)
    speed_term = float(ego_speed_mps) * float(center_offset) * float(PREDICTION_EGO_SPEED_GAIN)
    return clamp(yaw_term + speed_term, -PREDICTION_EGO_MAX_OFFSET_VEL, PREDICTION_EGO_MAX_OFFSET_VEL)


def update_track_prediction(state, center_offset, center_y_norm, area, current_time, ego_speed_mps=0.0, ego_yaw_rate_dps=0.0, det_conf=1.0):
    kalman_enabled = bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))

    if not kalman_enabled:
        state["kf"] = None
        prev_time = state.get("track_prev_measurement_time", 0.0)
        prev_offset = state.get("track_prev_center_offset", center_offset)
        prev_area = state.get("track_prev_area", area)

        predicted_offset = center_offset
        predicted_area = area
        confidence = 0.0

        if prev_time > 0.0:
            dt = current_time - prev_time
            if 1e-3 < dt <= 1.0:
                d_offset = center_offset - prev_offset
                d_area = area - prev_area
                area_ref = max(area, prev_area, 1.0)
                area_ratio_step = abs(d_area) / area_ref

                if abs(d_offset) < PREDICTION_MIN_OFFSET_STEP:
                    d_offset = 0.0
                if area_ratio_step < PREDICTION_MIN_AREA_RATIO_STEP:
                    d_area = 0.0

                raw_offset_velocity = d_offset / dt
                raw_offset_velocity -= _compute_ego_offset_velocity(ego_yaw_rate_dps, ego_speed_mps, center_offset)
                raw_area_velocity = d_area / dt
                state["track_offset_velocity"] = blend_value(
                    state.get("track_offset_velocity", 0.0),
                    raw_offset_velocity,
                    PREDICTION_VELOCITY_ALPHA,
                )
                state["track_area_velocity"] = blend_value(
                    state.get("track_area_velocity", 0.0),
                    raw_area_velocity,
                    PREDICTION_VELOCITY_ALPHA,
                )

                predicted_offset = clamp(center_offset + state["track_offset_velocity"] * PREDICTION_HORIZON_SEC, -1.0, 1.0)
                max_area_delta = max(area, prev_area, 1.0) * PREDICTION_MAX_AREA_DELTA_RATIO
                predicted_area = max(0.0, area + clamp(state["track_area_velocity"] * PREDICTION_HORIZON_SEC, -max_area_delta, max_area_delta))
                cadence_score = clamp(1.0 - abs(dt - 0.1) / 0.4, 0.0, 1.0)
                motion_score = max(clamp(abs(d_offset) / 0.08, 0.0, 1.0), clamp(area_ratio_step / 0.30, 0.0, 1.0))
                confidence = cadence_score * motion_score

        state["track_prev_measurement_time"] = current_time
        state["track_prev_center_offset"] = center_offset
        state["track_prev_center_y"] = center_y_norm
        state["track_prev_area"] = area
        state["predicted_offset"] = predicted_offset
        state["predicted_area"] = predicted_area
        state["prediction_confidence"] = confidence
        return

    # Use a lightweight linear Kalman filter on [offset, offset_vel, area, area_vel]
    prev_time = state.get("track_prev_measurement_time", 0.0)

    kf = state.get("kf", None)
    if kf is None:
        # create and store one lazily
        try:
            state["kf"] = KalmanFilter()
            kf = state["kf"]
        except Exception:
            kf = None

    predicted_offset = center_offset
    predicted_area = area
    confidence = 0.0

    if prev_time > 0.0:
        dt = current_time - prev_time
        if 1e-3 < dt <= 1.0:
            prev_offset = state.get("track_prev_center_offset", center_offset)
            prev_area = state.get("track_prev_area", area)
            d_offset = center_offset - prev_offset
            d_area = area - prev_area
            area_ref = max(area, prev_area, 1.0)
            area_ratio_step = abs(d_area) / area_ref

            if abs(d_offset) < PREDICTION_MIN_OFFSET_STEP:
                d_offset = 0.0
            if area_ratio_step < PREDICTION_MIN_AREA_RATIO_STEP:
                d_area = 0.0

            offset_motion = clamp(abs(d_offset) / 0.08, 0.0, 1.0)
            area_motion = clamp(area_ratio_step / 0.30, 0.0, 1.0)
            motion_score = max(offset_motion, area_motion)

            cadence_score = clamp(1.0 - abs(dt - 0.1) / 0.4, 0.0, 1.0)

            if kf is not None:
                try:
                    if hasattr(kf, "set_last_dt"):
                        kf.set_last_dt(dt)
                    kf.predict(dt)
                    kf.update(center_offset, area, det_conf=det_conf)
                    sx = kf.state()
                    if sx is not None:
                        # Compute raw measured velocity for sign-consistency check
                        raw_meas_offset_velocity = (d_offset / dt) - _compute_ego_offset_velocity(ego_yaw_rate_dps, ego_speed_mps, center_offset)
                        kf_offset_vel = float(sx[1])
                        kf_area_vel = float(sx[3])

                        # Determine whether KF velocity sign matches measured velocity
                        vel_thresh = float(PREDICTION_SIGN_CONSISTENCY_VEL_THRESH)
                        sign_consistent = True
                        if abs(raw_meas_offset_velocity) > vel_thresh and abs(kf_offset_vel) > vel_thresh:
                            sign_consistent = (raw_meas_offset_velocity * kf_offset_vel) >= 0.0

                        # If sign inconsistent and confidence low, reject KF prediction
                        if not sign_consistent and (cadence_score * motion_score) < float(PREDICTION_SIGN_CONSISTENCY_CONF):
                            # reject KF contribution this frame
                            state["kf_rejected"] = True
                            predicted_offset = clamp(center_offset + state["track_offset_velocity"] * PREDICTION_HORIZON_SEC, -1.0, 1.0)
                            max_area_delta = max(area, prev_area, 1.0) * PREDICTION_MAX_AREA_DELTA_RATIO
                            predicted_area = max(0.0, area + clamp(state["track_area_velocity"] * PREDICTION_HORIZON_SEC, -max_area_delta, max_area_delta))
                        else:
                            state["kf_rejected"] = False
                            raw_kf_offset_velocity = kf_offset_vel - _compute_ego_offset_velocity(ego_yaw_rate_dps, ego_speed_mps, center_offset)
                            raw_kf_area_velocity = kf_area_vel
                            state["track_offset_velocity"] = blend_value(
                                state.get("track_offset_velocity", 0.0),
                                raw_kf_offset_velocity,
                                0.30,
                            )
                            state["track_area_velocity"] = blend_value(
                                state.get("track_area_velocity", 0.0),
                                raw_kf_area_velocity,
                                0.45,  # increased from 0.30: faster area-velocity tracking feeds D-term sooner
                            )
                            predicted_offset = clamp(
                                float(sx[0]) + (state["track_offset_velocity"] * PREDICTION_HORIZON_SEC),
                                -1.0,
                                1.0,
                            )
                            predicted_area = max(
                                0.0,
                                float(sx[2]) + (state["track_area_velocity"] * PREDICTION_HORIZON_SEC),
                            )
                except Exception:
                    predicted_offset = clamp(center_offset + state["track_offset_velocity"] * PREDICTION_HORIZON_SEC, -1.0, 1.0)
                    max_area_delta = max(area, prev_area, 1.0) * PREDICTION_MAX_AREA_DELTA_RATIO
                    predicted_area = max(0.0, area + clamp(state["track_area_velocity"] * PREDICTION_HORIZON_SEC, -max_area_delta, max_area_delta))

            if motion_score <= 1e-4:
                state["track_offset_velocity"] *= PREDICTION_IDLE_DECAY
                state["track_area_velocity"] *= PREDICTION_IDLE_DECAY
                confidence = cadence_score * 0.15
            else:
                confidence = cadence_score * motion_score
            # Keep a small confidence floor when Kalman is active so the smoother
            # actually contributes to control instead of being gated out.
            if kf is not None:
                confidence = max(confidence, 0.15)
        else:
            # stale timing: decay velocities and confidence
            state["track_offset_velocity"] *= PREDICTION_STALE_DECAY
            state["track_area_velocity"] *= PREDICTION_STALE_DECAY
            confidence = state.get("prediction_confidence", 0.0) * PREDICTION_STALE_DECAY
            if kf is not None:
                try:
                    dt = min(max(0.0, current_time - prev_time), 1.0)
                    if hasattr(kf, "set_last_dt"):
                        kf.set_last_dt(dt)
                    kf.predict(dt)
                    kf.update(center_offset, area, det_conf=det_conf)
                    sx = kf.state()
                    if sx is not None:
                        dt_meas = max(1e-3, current_time - prev_time)
                        d_offset = center_offset - prev_offset
                        # sign-consistency check (same logic as measurement-time branch)
                        raw_meas_offset_velocity = (d_offset / dt_meas) - _compute_ego_offset_velocity(ego_yaw_rate_dps, ego_speed_mps, center_offset)
                        kf_offset_vel = float(sx[1])
                        vel_thresh = float(PREDICTION_SIGN_CONSISTENCY_VEL_THRESH)
                        sign_consistent = True
                        if abs(raw_meas_offset_velocity) > vel_thresh and abs(kf_offset_vel) > vel_thresh:
                            sign_consistent = (raw_meas_offset_velocity * kf_offset_vel) >= 0.0

                        if not sign_consistent and (state.get("prediction_confidence", 0.0) * PREDICTION_STALE_DECAY) < float(PREDICTION_SIGN_CONSISTENCY_CONF):
                            state["kf_rejected"] = True
                            predicted_offset = clamp(center_offset + state["track_offset_velocity"] * PREDICTION_HORIZON_SEC, -1.0, 1.0)
                            predicted_area = max(0.0, area)
                        else:
                            state["kf_rejected"] = False
                            state["track_offset_velocity"] = blend_value(
                                state.get("track_offset_velocity", 0.0),
                                float(sx[1]) - _compute_ego_offset_velocity(ego_yaw_rate_dps, ego_speed_mps, center_offset),
                                0.30,
                            )
                            state["track_area_velocity"] = blend_value(
                                state.get("track_area_velocity", 0.0),
                                float(sx[3]),
                                0.30,
                            )
                            predicted_offset = clamp(
                                float(sx[0]) + (state["track_offset_velocity"] * PREDICTION_HORIZON_SEC),
                                -1.0,
                                1.0,
                            )
                            predicted_area = max(
                                0.0,
                                float(sx[2]) + (state["track_area_velocity"] * PREDICTION_HORIZON_SEC),
                            )
                except Exception:
                    pass

    # persist temporal info
    state["track_prev_measurement_time"] = current_time
    state["track_prev_center_offset"] = center_offset
    state["track_prev_center_y"] = center_y_norm
    state["track_prev_area"] = area
    state["predicted_offset"] = predicted_offset
    state["predicted_area"] = predicted_area
    state["prediction_confidence"] = confidence


def update_static_track(state, center_offset, center_y_norm, area, current_time):
    state["kf"] = None
    state["track_prev_measurement_time"] = current_time
    state["track_prev_center_offset"] = center_offset
    state["track_prev_center_y"] = center_y_norm
    state["track_prev_area"] = area
    state["track_offset_velocity"] = 0.0
    state["track_vertical_velocity"] = 0.0
    state["track_area_velocity"] = 0.0
    state["predicted_offset"] = center_offset
    state["predicted_area"] = area
    state["prediction_confidence"] = 0.0


def tcp_camera_receiver_thread(port, stream_name):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port))
    server.listen(1)

    label = CAMERA_STREAMS[stream_name]["window"]
    print(f"[TCP] Waiting for {label} on {HOST}:{port} ...")

    while True:
        conn = None
        try:
            conn, addr = server.accept()
            conn.settimeout(TCP_FRAME_TIMEOUT)
            print(f"[TCP] {label} connected by {addr}")

            with vision_lock:
                vision_states[stream_name]["connected"] = True

            while True:
                header = recv_exact(conn, 12)
                if header is None:
                    break

                width, height, data_len = struct.unpack("iii", header)
                if width <= 0 or height <= 0:
                    print(f"[TCP] {label} invalid frame size header: {(width, height, data_len)}")
                    break
                if data_len <= 0 or data_len > MAX_JPEG_BYTES:
                    print(f"[TCP] {label} invalid jpeg bytes: {data_len}")
                    break

                jpg_bytes = recv_exact(conn, data_len)
                if jpg_bytes is None:
                    break

                img_array = np.frombuffer(jpg_bytes, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is None:
                    print(f"[TCP] {label} decode failed for a frame.")
                    continue

                with frame_lock:
                    latest_frames[stream_name] = frame

        except Exception as exc:
            print(f"[TCP] {label} receiver error: {exc}")
        finally:
            reset_vision_state(stream_name)

            with frame_lock:
                latest_frames[stream_name] = None
                if SHOW_WINDOW:
                    display_frames[stream_name] = make_status_frame(label, "Waiting for TCP stream...")
                else:
                    display_frames[stream_name] = None

            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def cv_processing_thread():
    print("[Vision] Central processing thread started.")

    try:
        model = YOLO(YOLO_MODEL_PATH)
        print(f"[Vision] Model {YOLO_MODEL_PATH} loaded successfully.")
    except Exception as exc:
        print(f"[Vision] Failed to load YOLO model: {exc}")
        return

    yolo_uses_cuda, yolo_half_enabled = configure_yolo_runtime(model)
    print(f"[Vision] YOLO runtime on {YOLO_DEVICE} (half={yolo_half_enabled})." if yolo_uses_cuda else "[Vision] YOLO runtime on CPU/default device.")

    yolo_predict_kwargs = {
        "verbose": False,
        "conf": YOLO_CONFIDENCE,
        "classes": YOLO_CLASSES,
        "imgsz": YOLO_IMGSZ,
    }
    if yolo_uses_cuda:
        yolo_predict_kwargs["device"] = YOLO_DEVICE
        yolo_predict_kwargs["half"] = yolo_half_enabled

    warmup_yolo_runtime(model, yolo_predict_kwargs)

    depth_estimator = None
    if USE_DEPTH_ANYTHING_TEST:
        depth_estimator = DepthAnythingEstimator(model_id=DEPTH_ANYTHING_MODEL_ID, device=DEPTH_ANYTHING_DEVICE)
        if depth_estimator.available:
            print(f"[Vision] Depth Anything {DEPTH_ANYTHING_MODEL_ID} loaded successfully.")
        else:
            print(f"[Vision] Depth Anything disabled: {depth_estimator.error}")

    times_dict = {stream_name: time.time() for stream_name in CAMERA_STREAMS}
    display_times = {stream_name: 0.0 for stream_name in CAMERA_STREAMS}
    depth_cache = {
        "Left": {"result": None, "preview": None, "updated_at": 0.0},
        "Right": {"result": None, "preview": None, "updated_at": 0.0},
    }

    try:
        while True:
            active_yolo_stream_count = sum(
                1
                for cfg in CAMERA_STREAMS.values()
                if not (
                    cfg.get("role") == "side"
                    and not bool(runtime_settings.get("enable_side_detection", ENABLE_SIDE_DETECTION))
                )
            )
            pending_streams = []
            for stream_name, config in CAMERA_STREAMS.items():
                with frame_lock:
                    frame = latest_frames[stream_name]
                    latest_frames[stream_name] = None

                if frame is None:
                    continue

                current_time = time.time()
                height, width = frame.shape[:2]
                display_due = SHOW_WINDOW and (current_time - display_times[stream_name]) >= DISPLAY_UPDATE_INTERVAL_SEC
                display_frame = frame.copy() if display_due else None

                if config.get("role") == "side" and not bool(runtime_settings.get("enable_side_detection", ENABLE_SIDE_DETECTION)):
                    with vision_lock:
                        state = vision_states[stream_name]
                        state["connected"] = True
                        state["target_detected"] = False
                        state["target_stale"] = False
                        state["method"] = None
                    continue

                with vision_lock:
                    prev_state = vision_states[stream_name].copy()

                preferred_offset = prev_state.get("last_known_offset", 0.0)
                last_detection_time = prev_state.get("last_detection_time", 0.0)
                has_recent_track = (current_time - last_detection_time) <= (TRACK_HOLD_SEC + 0.8)

                pending_streams.append(
                    {
                        "stream_name": stream_name,
                        "config": config,
                        "boat_side": config["boat"],
                        "role": config["role"],
                        "frame": frame,
                        "height": height,
                        "width": width,
                        "display_frame": display_frame,
                        "display_due": display_due,
                        "prev_state": prev_state,
                        "preferred_offset": preferred_offset,
                        "has_recent_track": has_recent_track,
                    }
                )

            if YOLO_USE_BATCHING and len(pending_streams) < active_yolo_stream_count:
                time.sleep(YOLO_BATCH_WAIT_SEC)
                queued_streams = {item["stream_name"] for item in pending_streams}
                for stream_name, config in CAMERA_STREAMS.items():
                    if stream_name in queued_streams:
                        continue
                    with frame_lock:
                        frame = latest_frames[stream_name]
                        latest_frames[stream_name] = None
                    if frame is None:
                        continue

                    current_time = time.time()
                    height, width = frame.shape[:2]
                    display_due = SHOW_WINDOW and (current_time - display_times[stream_name]) >= DISPLAY_UPDATE_INTERVAL_SEC
                    display_frame = frame.copy() if display_due else None

                    if config.get("role") == "side" and not bool(runtime_settings.get("enable_side_detection", ENABLE_SIDE_DETECTION)):
                        with vision_lock:
                            state = vision_states[stream_name]
                            state["connected"] = True
                            state["target_detected"] = False
                            state["target_stale"] = False
                            state["method"] = None
                        continue

                    with vision_lock:
                        prev_state = vision_states[stream_name].copy()

                    preferred_offset = prev_state.get("last_known_offset", 0.0)
                    last_detection_time = prev_state.get("last_detection_time", 0.0)
                    has_recent_track = (current_time - last_detection_time) <= (TRACK_HOLD_SEC + 0.8)

                    pending_streams.append(
                        {
                            "stream_name": stream_name,
                            "config": config,
                            "boat_side": config["boat"],
                            "role": config["role"],
                            "frame": frame,
                            "height": height,
                            "width": width,
                            "display_frame": display_frame,
                            "display_due": display_due,
                            "prev_state": prev_state,
                            "preferred_offset": preferred_offset,
                            "has_recent_track": has_recent_track,
                        }
                    )

            inference_inputs = [item["frame"] for item in pending_streams]

            if not pending_streams:
                time.sleep(0.005)
                continue
            
            batch_results = model.predict(inference_inputs, **yolo_predict_kwargs) if YOLO_USE_BATCHING else [model.predict(frame, **yolo_predict_kwargs)[0] for frame in inference_inputs]

            for item, result in zip(pending_streams, batch_results):
                stream_name = item["stream_name"]
                boat_side = item["boat_side"]
                role = item["role"]
                frame = item["frame"]
                height = item["height"]
                width = item["width"]
                display_frame = item["display_frame"]
                display_due = item["display_due"]
                prev_state = item["prev_state"]
                preferred_offset = item["preferred_offset"]
                has_recent_track = item["has_recent_track"]

                best_box = None
                best_area = 0.0
                best_score = -1.0
                detection_method = None
                target_kind = None
                center_point = None
                center_offset = 0.0
                yolo_target = None
                side_leader_target = None
                follower_target = None
                wake_target = None
                fusion_wake_weight = 0.0
                yolo_display_detections = []
                wake_mask = None
                depth_result = None
                depth_preview = None
                best_follower_score = -1.0
                best_side_leader_score = -1.0

                if result is not None and result.boxes is not None:
                    formation_mode = str(runtime_settings.get("formation_mode", "v")).strip().lower()
                    desired_front_class = YOLO_CLASS_LEADER
                    desired_front_kind = "leader"

                if role == "front":
                    if boat_side == "Right" and formation_mode == "line":
                        desired_front_class = YOLO_CLASS_FOLLOWER
                        desired_front_kind = "follower"
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        area = (x2 - x1) * (y2 - y1)
                        if area < YOLO_MIN_BOX_AREA or y1 < height * IGNORE_TOP_RATIO or y2 > height * (1.0 - IGNORE_BOTTOM_RATIO):
                            continue

                        box_conf = float(box.conf[0])
                        yolo_display_detections.append(
                            {
                                "bbox": (x1, y1, x2, y2),
                                "area": area,
                                "cls_id": cls_id,
                                "cls_name": get_model_class_name(model, cls_id),
                                "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                            }
                        )

                        candidate_offset = (((x1 + x2) / 2.0) - (width / 2.0)) / (width / 2.0)

                        # Hard false-positive gates (wave glitter / spurious detections).
                        # Only active once a track is established so initial acquisition is unaffected.
                        if has_recent_track and TRACK_GATE_ENABLE:
                            if abs(candidate_offset - preferred_offset) > TRACK_GATE_MAX_OFFSET_DELTA:
                                continue
                            last_known_area_gate = prev_state.get("last_known_area", 0.0)
                            if last_known_area_gate > 0.0 and (
                                area > last_known_area_gate * TRACK_GATE_MAX_AREA_RATIO
                                or area < last_known_area_gate / TRACK_GATE_MAX_AREA_RATIO
                            ):
                                continue

                        if role == "front":
                            if cls_id != YOLO_CLASS_LEADER:
                                continue
                            score = area
                            if has_recent_track:
                                score *= 1.0 - min(abs(candidate_offset - preferred_offset), 1.0) * TRACK_REACQUIRE_BIAS
                            if score > best_score:
                                best_score = score
                                best_area = area
                                best_box = (x1, y1, x2, y2)
                                center_point = ((x1 + x2) // 2, (y1 + y2) // 2)
                                center_offset = candidate_offset
                                detection_method = "YOLO"
                                yolo_target = build_track_candidate(
                                    best_box,
                                    best_area,
                                    center_offset,
                                    center_point,
                                    "YOLO",
                                    target_kind=desired_front_kind,
                                    det_conf=box_conf,
                                )
                        else:
                            if cls_id == YOLO_CLASS_LEADER:
                                leader_score = area
                                if has_recent_track:
                                    leader_score *= 1.0 - min(abs(candidate_offset - preferred_offset), 1.0) * TRACK_REACQUIRE_BIAS
                                if leader_score > best_side_leader_score:
                                    best_side_leader_score = leader_score
                                    side_leader_target = build_track_candidate(
                                        (x1, y1, x2, y2),
                                        area,
                                        candidate_offset,
                                        ((x1 + x2) // 2, (y1 + y2) // 2),
                                        "YOLO",
                                        target_kind="leader",
                                        det_conf=box_conf,
                                    )
                            elif cls_id == YOLO_CLASS_FOLLOWER:
                                follower_score = area
                                if has_recent_track:
                                    follower_score *= 1.0 - min(abs(candidate_offset - preferred_offset), 1.0) * (TRACK_REACQUIRE_BIAS * 0.55)
                                if follower_score > best_follower_score:
                                    best_follower_score = follower_score
                                    follower_target = build_track_candidate(
                                        (x1, y1, x2, y2),
                                        area,
                                        candidate_offset,
                                        ((x1 + x2) // 2, (y1 + y2) // 2),
                                        "FOLLOWER",
                                        target_kind="follower",
                                        det_conf=box_conf,
                                    )

                # Class-agnostic fallback: if the front camera lost its leader-class
                # detection (e.g. YOLO mis-classified the leader as a follower under
                # wave noise), do a second pass accepting any class within a tight
                # position gate.  This recovers the track without accepting far-away
                # wave glitter (which was already rejected by the hard offset gate above).
                if (
                    role == "front"
                    and yolo_target is None
                    and has_recent_track
                    and TRACK_GATE_CLASS_AGNOSTIC_ENABLE
                    and result is not None
                    and result.boxes is not None
                ):
                    best_agnostic_score = -1.0
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        area_fb = (x2 - x1) * (y2 - y1)
                        if area_fb < YOLO_MIN_BOX_AREA or y1 < height * IGNORE_TOP_RATIO or y2 > height * (1.0 - IGNORE_BOTTOM_RATIO):
                            continue
                        fb_offset = (((x1 + x2) / 2.0) - (width / 2.0)) / (width / 2.0)
                        if abs(fb_offset - preferred_offset) > TRACK_GATE_CLASS_AGNOSTIC_OFFSET:
                            continue
                        fb_conf = float(box.conf[0])
                        fb_score = area_fb * fb_conf
                        if fb_score > best_agnostic_score:
                            best_agnostic_score = fb_score
                            yolo_target = build_track_candidate(
                                (x1, y1, x2, y2),
                                area_fb,
                                fb_offset,
                                ((x1 + x2) // 2, (y1 + y2) // 2),
                                "YOLO",
                                target_kind=desired_front_kind,
                                det_conf=fb_conf * 0.7,
                            )

                if role == "front":
                    wake_reference_bbox = yolo_target["bbox"] if yolo_target is not None else None
                    if ENABLE_WAKE_DETECTION:
                        wake_result = detect_stern_wake(frame, preferred_offset if has_recent_track else None, wake_reference_bbox)
                        if wake_result is not None:
                            wake_mask = wake_result["mask"]
                            wake_target = build_track_candidate(
                                wake_result["bbox"],
                                wake_result["area"],
                                wake_result["center_offset"],
                                wake_result["center"],
                                "WAKE",
                                target_kind="leader",
                            )
                        fused_target = fuse_track_sources(yolo_target, wake_target)
                    else:
                        fused_target = yolo_target.copy() if yolo_target is not None else None
                        if fused_target is not None:
                            fused_target["method"] = "YOLO"
                            fused_target["wake_weight"] = 0.0

                    if fused_target is not None:
                        best_box = fused_target["bbox"]
                        best_area = fused_target["area"]
                        center_offset = fused_target["center_offset"]
                        center_point = fused_target["center"]
                        detection_method = fused_target["method"]
                        target_kind = fused_target.get("target_kind", "leader")
                        fusion_wake_weight = fused_target.get("wake_weight", 0.0)
                        det_conf_meas = fused_target.get("det_conf", 1.0)
                    elif yolo_target is not None:
                        best_box = yolo_target["bbox"]
                        best_area = yolo_target["area"]
                        center_offset = yolo_target["center_offset"]
                        center_point = yolo_target["center"]
                        detection_method = yolo_target["method"]
                        target_kind = yolo_target.get("target_kind", "leader")
                        det_conf_meas = yolo_target.get("det_conf", 1.0)
                    else:
                        best_box = None
                        best_area = 0.0
                        center_offset = 0.0
                        center_point = None
                        detection_method = None
                        det_conf_meas = 1.0
                else:
                    selected_side_target = select_side_track_candidate(
                        side_leader_target,
                        follower_target,
                        prev_state.get("last_known_target_kind"),
                    )
                    if selected_side_target is not None:
                        best_box = selected_side_target["bbox"]
                        best_area = selected_side_target["area"]
                        center_offset = selected_side_target["center_offset"]
                        center_point = selected_side_target["center"]
                        detection_method = selected_side_target["method"]
                        target_kind = selected_side_target.get("target_kind")
                        det_conf_meas = selected_side_target.get("det_conf", 1.0)
                    else:
                        best_box = None
                        best_area = 0.0
                        center_offset = 0.0
                        center_point = None
                        detection_method = None
                        det_conf_meas = 1.0

                current_time = time.time()
                cache_entry = depth_cache[boat_side]
                depth_roi_box = None
                if role == "front" and yolo_target is not None:
                    depth_roi_box = yolo_target["bbox"]
                elif role == "front" and best_box is not None and not DEPTH_ONLY_ON_YOLO:
                    depth_roi_box = best_box

                should_run_depth = (
                    depth_estimator is not None
                    and role == "front"
                    and depth_roi_box is not None
                    and (current_time - cache_entry["updated_at"]) >= DEPTH_UPDATE_INTERVAL_SEC
                )

                if should_run_depth:
                    depth_result = depth_estimator.estimate(frame, depth_roi_box, input_max_size=DEPTH_INPUT_MAX_SIZE)
                    cache_entry["updated_at"] = current_time
                    cache_entry["result"] = depth_result
                    cache_entry["preview"] = depth_estimator.build_colormap(depth_result.get("depth_map_norm")) if depth_result.get("ok") else None

                if role == "front" and depth_roi_box is not None and (not DEPTH_ONLY_ON_YOLO or yolo_target is not None):
                    depth_result = cache_entry["result"]
                    depth_preview = cache_entry["preview"]
                else:
                    depth_result = None
                    depth_preview = None

                dt = current_time - times_dict[stream_name]
                times_dict[stream_name] = current_time
                fps = 1.0 / dt if dt > 0 else 0.0
                overlay_offset_velocity = 0.0
                overlay_vertical_velocity = 0.0
                overlay_prediction_conf = 0.0

                with vision_lock:
                    state = vision_states[stream_name]
                    state["fps"] = fps
                    overlay_depth_status = state.get("depth_status", "Depth disabled")
                    if role == "side":
                        state["side_leader_detected"] = side_leader_target is not None
                        state["side_leader_area"] = float(side_leader_target["area"]) if side_leader_target is not None else 0.0
                        state["side_leader_center_offset"] = float(side_leader_target["center_offset"]) if side_leader_target is not None else 0.0
                        state["side_follower_detected"] = follower_target is not None
                        state["side_follower_area"] = float(follower_target["area"]) if follower_target is not None else 0.0
                        state["side_follower_center_offset"] = float(follower_target["center_offset"]) if follower_target is not None else 0.0

                    if best_box is not None:
                        if role == "front" and detection_method in ("YOLO", "FUSED"):
                            lock_visual_reference(boat_side, "front", center_offset, best_area, target_kind=target_kind)
                        elif role == "side" and target_kind in ("leader", "follower"):
                            lock_visual_reference(boat_side, "side", center_offset, best_area, target_kind=target_kind)

                        previous_offset = state.get("last_known_offset", center_offset)
                        previous_area = state.get("last_known_area", best_area)
                        if state.get("last_detection_time", 0.0) > 0.0:
                            center_offset = blend_value(previous_offset, center_offset, TRACK_OFFSET_ALPHA)
                            best_area = blend_value(previous_area, best_area, TRACK_AREA_ALPHA)

                        center_y_norm = (center_point[1] / float(height)) if center_point is not None else 0.5
                        if role == "front":
                            comm = boat_comm_states.get(boat_side, {})
                            ego_speed_mps = float(comm.get("speed_mps", 0.0))
                            ego_yaw_rate_dps = float(comm.get("yaw_rate_dps", 0.0))
                            update_track_prediction(
                                state,
                                center_offset,
                                center_y_norm,
                                best_area,
                                current_time,
                                ego_speed_mps=ego_speed_mps,
                                ego_yaw_rate_dps=ego_yaw_rate_dps,
                                det_conf=det_conf_meas,
                            )
                        else:
                            if PREDICTION_ENABLE_SIDE_FOLLOWER:
                                comm = boat_comm_states.get(boat_side, {})
                                ego_speed_mps = float(comm.get("speed_mps", 0.0))
                                ego_yaw_rate_dps = float(comm.get("yaw_rate_dps", 0.0))
                                update_track_prediction(
                                    state,
                                    center_offset,
                                    center_y_norm,
                                    best_area,
                                    current_time,
                                    ego_speed_mps=ego_speed_mps,
                                    ego_yaw_rate_dps=ego_yaw_rate_dps,
                                    det_conf=det_conf_meas,
                                )
                            else:
                                # Side follower track: use direct measurement only (no velocity prediction)
                                update_static_track(state, center_offset, center_y_norm, best_area, current_time)

                        state["target_detected"] = True
                        state["target_stale"] = False
                        state["method"] = detection_method
                        state["target_bbox"] = best_box
                        state["target_area"] = best_area
                        state["target_center_offset"] = center_offset
                        state["target_kind"] = target_kind
                        if role == "front" and depth_result and depth_result.get("ok"):
                            depth_value = depth_result.get("relative_depth")
                            state["target_depth"] = depth_value
                            state["target_depth_confidence"] = depth_result.get("depth_confidence", 0.0)
                            state["depth_inference_ms"] = depth_result.get("inference_sec", 0.0) * 1000.0
                            state["depth_status"] = "Depth ROI invalid" if depth_value is None else f"Depth rel={depth_value:.3f}"
                        elif role == "front" and depth_result:
                            state["target_depth"] = None
                            state["target_depth_confidence"] = 0.0
                            state["depth_inference_ms"] = 0.0
                            state["depth_status"] = f"Depth unavailable: {depth_result.get('error', 'unknown error')}"
                        else:
                            state["target_depth"] = None
                            state["target_depth_confidence"] = 0.0
                            state["depth_inference_ms"] = 0.0
                            if role == "side":
                                state["depth_status"] = f"Side {target_kind or 'camera'} track"
                            elif depth_estimator is not None and yolo_target is None and DEPTH_ONLY_ON_YOLO:
                                state["depth_status"] = "Depth waiting for YOLO boat"
                            elif depth_estimator is not None:
                                state["depth_status"] = "Depth cached/idle"
                            else:
                                state["depth_status"] = "Depth disabled"
                        state["last_detection_time"] = current_time
                        state["last_known_offset"] = center_offset
                        state["last_known_area"] = best_area
                        state["last_known_method"] = detection_method
                        state["last_known_target_kind"] = target_kind
                        overlay_depth_status = state["depth_status"]
                        overlay_offset_velocity = state.get("track_offset_velocity", 0.0)
                        overlay_vertical_velocity = state.get("track_vertical_velocity", 0.0)
                        overlay_prediction_conf = state.get("prediction_confidence", 0.0)
                    else:
                        time_since_seen = current_time - state.get("last_detection_time", 0.0)
                        if state.get("last_known_method") is not None and time_since_seen <= TRACK_HOLD_SEC:
                            state["target_detected"] = True
                            state["target_stale"] = True
                            state["method"] = state["last_known_method"]
                            state["target_bbox"] = None
                            state["target_area"] = state.get("last_known_area", 0.0)
                            state["target_center_offset"] = state.get("last_known_offset", 0.0)
                            state["target_kind"] = state.get("last_known_target_kind")
                            state["prediction_confidence"] = state.get("prediction_confidence", 0.0) * PREDICTION_STALE_DECAY
                            overlay_depth_status = state.get("depth_status", "Depth idle")
                            overlay_offset_velocity = state.get("track_offset_velocity", 0.0)
                            overlay_vertical_velocity = state.get("track_vertical_velocity", 0.0)
                            overlay_prediction_conf = state.get("prediction_confidence", 0.0)
                        else:
                            state["target_detected"] = False
                            state["target_stale"] = False
                            state["method"] = None
                            state["target_bbox"] = None
                            state["target_area"] = 0.0
                            state["target_center_offset"] = 0.0
                            state["target_kind"] = None
                            state["target_depth"] = None
                            state["target_depth_confidence"] = 0.0
                            state["depth_inference_ms"] = 0.0
                            state["track_prev_measurement_time"] = 0.0
                            state["track_prev_center_offset"] = 0.0
                            state["track_prev_center_y"] = 0.0
                            state["track_prev_area"] = 0.0
                            state["track_offset_velocity"] = 0.0
                            state["track_vertical_velocity"] = 0.0
                            state["track_area_velocity"] = 0.0
                            state["predicted_offset"] = 0.0
                            state["predicted_area"] = 0.0
                            state["prediction_confidence"] = 0.0
                            state["kf"] = None
                            state["kf_rejected"] = False
                            if role == "side":
                                state["depth_status"] = "Side camera idle"
                            elif depth_estimator is not None and not depth_estimator.available:
                                state["depth_status"] = f"Depth unavailable: {depth_estimator.error}"
                            elif depth_estimator is not None:
                                state["depth_status"] = "Depth idle"
                            else:
                                state["depth_status"] = "Depth disabled"
                            overlay_depth_status = state["depth_status"]

                if SHOW_WINDOW and display_due and display_frame is not None:
                    for detection in yolo_display_detections:
                        det_box = detection["bbox"]
                        det_cls_id = detection["cls_id"]
                        det_color = get_yolo_box_color(det_cls_id)
                        det_label = f"YOLO({detection['cls_name']}): {detection['area']:.0f}"
                        det_thickness = 2

                        if best_box is not None and det_box == best_box:
                            det_label += " [target]"
                            det_thickness = 3

                        draw_labeled_box(
                            display_frame,
                            det_box,
                            det_label,
                            det_color,
                            center=detection["center"] if det_box == best_box else None,
                            thickness=det_thickness,
                        )

                    if wake_target is not None:
                        draw_labeled_box(
                            display_frame,
                            wake_target["bbox"],
                            f"WAKE Area: {wake_target['area']:.0f}",
                            (0, 255, 255),
                            center=wake_target["center"] if detection_method == "WAKE" else None,
                            thickness=2,
                        )

                    if best_box is not None and center_point is not None:
                        cv2.circle(display_frame, center_point, 6, (255, 255, 0), -1)
                        if detection_method == "FUSED":
                            cv2.putText(display_frame, f"FUSED wake={fusion_wake_weight:.2f}", (16, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
                        # Only draw arrow when prediction is enabled for this role
                        # and the Kalman prediction was not rejected for sign inconsistency.
                        if ((role == "front" and PREDICTION_ENABLE_LEADER_TRAJECTORY) or (role == "side" and PREDICTION_ENABLE_SIDE_FOLLOWER)) and not state.get("kf_rejected", False):
                            draw_prediction_arrow(
                                display_frame,
                                center_point,
                                overlay_offset_velocity,
                                overlay_vertical_velocity,
                                overlay_prediction_conf,
                            )
                    else:
                        time_since_seen = current_time - prev_state.get("last_detection_time", 0.0)
                        if prev_state.get("last_known_method") is not None and time_since_seen <= TRACK_HOLD_SEC:
                            hold_text = f"HOLD {prev_state['last_known_method']} {time_since_seen:.2f}s"
                            cv2.putText(display_frame, hold_text, (16, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

                    if wake_mask is not None:
                        mask_small = cv2.resize(wake_mask, (0, 0), fx=WAKE_MASK_PREVIEW_SCALE, fy=WAKE_MASK_PREVIEW_SCALE)
                        mask_color = cv2.cvtColor(mask_small, cv2.COLOR_GRAY2BGR)
                        mask_h, mask_w = mask_color.shape[:2]
                        display_frame[0:mask_h, 0:mask_w] = mask_color

                    if depth_preview is not None:
                        depth_small = cv2.resize(depth_preview, (0, 0), fx=DEPTH_OVERLAY_SCALE, fy=DEPTH_OVERLAY_SCALE)
                        depth_h, depth_w = depth_small.shape[:2]
                        depth_y = 0
                        depth_x = max(0, display_frame.shape[1] - depth_w)
                        display_frame[depth_y: depth_y + depth_h, depth_x: depth_x + depth_w] = depth_small

                    if SHOW_OVERLAY_TEXT:
                        text_x = int(display_frame.shape[1] * WAKE_MASK_PREVIEW_SCALE) + 10 if wake_mask is not None else 10
                        cv2.putText(display_frame, f"FPS: {fps:.1f}", (text_x, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
                        cv2.putText(display_frame, overlay_depth_status[:80], (text_x, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 220, 255), 1)
                        if detection_method is not None:
                            cv2.putText(display_frame, f"Track: {role.upper()} {detection_method}", (text_x, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
                    with frame_lock:
                        display_frames[stream_name] = display_frame
                    display_times[stream_name] = current_time

    except Exception as exc:
        print(f"[Vision] Error: {exc}")
