import json
import os
import socket
import struct
import threading
import time
import math

import cv2
import numpy as np
from ultralytics import YOLO

from depth_Anything import DepthAnythingEstimator

try:
    import torch
except Exception:
    torch = None

# =========================================================
# 1) UDP 設定 (保留向船隻發送油門與打舵訊息)
# =========================================================
UDP_IP = "127.0.0.1"

# 左護法 (Follower_Left)
PORT_LEFT_RX = 5066
PORT_LEFT_TX = 5065

# 右護法 (Follower_Right)
PORT_RIGHT_RX = 5068
PORT_RIGHT_TX = 5067

sock_left = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_left.bind((UDP_IP, PORT_LEFT_RX))
sock_left.setblocking(False)

sock_right = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_right.bind((UDP_IP, PORT_RIGHT_RX))
sock_right.setblocking(False)

# =========================================================
# 2) 視覺處理 TCP 設定
# =========================================================
HOST = "0.0.0.0"
PORT_LEFT_FRONT_CAM = 9998
PORT_RIGHT_FRONT_CAM = 9999
PORT_LEFT_SIDE_CAM = 10000
PORT_RIGHT_SIDE_CAM = 10001

BOAT_SIDES = ("Left", "Right")
CAMERA_STREAMS = {
    "LeftFront": {
        "boat": "Left",
        "role": "front",
        "port": PORT_LEFT_FRONT_CAM,
        "window": "Left Front Camera",
        "search_dir": 1.0,
    },
    "LeftSide": {
        "boat": "Left",
        "role": "side",
        "port": PORT_LEFT_SIDE_CAM,
        "window": "Left Side Camera",
        "search_dir": 1.0,
    },
    "RightFront": {
        "boat": "Right",
        "role": "front",
        "port": PORT_RIGHT_FRONT_CAM,
        "window": "Right Front Camera",
        "search_dir": -1.0,
    },
    "RightSide": {
        "boat": "Right",
        "role": "side",
        "port": PORT_RIGHT_SIDE_CAM,
        "window": "Right Side Camera",
        "search_dir": -1.0,
    },
}
FRONT_STREAM_BY_BOAT = {"Left": "LeftFront", "Right": "RightFront"}
SIDE_STREAM_BY_BOAT = {"Left": "LeftSide", "Right": "RightSide"}

SHOW_WINDOW = True
SHOW_OVERLAY_TEXT = True
DISPLAY_UPDATE_INTERVAL_SEC = 0.0
YOLO_MODEL_PATH = "best_v2.pt"
USE_DEPTH_ANYTHING_TEST = False
DEPTH_ANYTHING_MODEL_ID = "LiheYoung/depth-anything-small-hf"
DEPTH_ANYTHING_DEVICE = "cuda"
DEPTH_OVERLAY_SCALE = 0.30
DEPTH_INPUT_MAX_SIZE = 256
DEPTH_UPDATE_INTERVAL_SEC = 0.30
DEPTH_ONLY_ON_YOLO = True
TCP_FRAME_TIMEOUT = 1.0
MAX_JPEG_BYTES = 8 * 1024 * 1024
WINDOW_SIZE = (640, 360)
YOLO_CLASS_LEADER = 0
YOLO_CLASS_FOLLOWER = 1
YOLO_CLASSES = [YOLO_CLASS_LEADER, YOLO_CLASS_FOLLOWER]
YOLO_CONFIDENCE = 0.12
YOLO_MIN_BOX_AREA = 300
YOLO_DEVICE = "cuda:0"
YOLO_USE_BATCHING = True
YOLO_IMGSZ = 640
YOLO_BATCH_WAIT_SEC = 0.008
YOLO_ENABLE_WARMUP = True
YOLO_ENABLE_TORCH_COMPILE = False
VISION_CPU_THREADS = max(1, min(8, (os.cpu_count() or 4)))
IGNORE_TOP_RATIO = 0.25
IGNORE_BOTTOM_RATIO = 0.18

WAKE_LOWER_WHITE = np.array([0, 0, 220], dtype=np.uint8)
WAKE_UPPER_WHITE = np.array([180, 55, 255], dtype=np.uint8)
WAKE_SKY_CROP_RATIO = 0.50
WAKE_BOAT_CROP_RATIO = 0.90
WAKE_MASK_PREVIEW_SCALE = 0.30
WAKE_IGNORE_BOTTOM_RATIO = 0.12
WAKE_MIN_BBOX_HEIGHT = 14
WAKE_MIN_BBOX_WIDTH = 8
WAKE_MIN_ASPECT_RATIO = 1.25
WAKE_MIN_FILL_RATIO = 0.16
WAKE_MAX_CENTER_OFFSET = 0.42
WAKE_MAX_OFFSET_FROM_TRACK = 0.18
WAKE_MAX_OFFSET_FROM_YOLO = 0.12
WAKE_MAX_TOP_GAP_FROM_YOLO_RATIO = 0.14
WAKE_OPEN_KERNEL = (3, 3)
WAKE_CLOSE_KERNEL = (21, 5)
WAKE_DILATE_KERNEL = (5, 3)

TRACK_HOLD_SEC = 0.60
TRACK_REACQUIRE_BIAS = 0.35
TRACK_OFFSET_ALPHA = 0.35
TRACK_AREA_ALPHA = 0.25
STALE_TARGET_THROTTLE_SCALE = 0.65
STALE_TARGET_STEER_SCALE = 0.85
SEARCH_FORWARD_THROTTLE = 0.24
SEARCH_STEER_GAIN = 0.85
DISABLE_SEARCH_MODE = True
VISUAL_FAR_BOOST_MAX = 0.16
VISUAL_SHRINK_BOOST_MAX = 0.08
VISUAL_FAR_BOOST_EXPONENT = 1.35
FOLLOW_FAR_MAX_THROTTLE = 0.9 #0.82
PREDICTION_HORIZON_SEC = 0.40
PREDICTION_OFFSET_BLEND = 0.55
PREDICTION_AREA_BLEND = 0.35
PREDICTION_VELOCITY_ALPHA = 0.35
PREDICTION_STALE_DECAY = 0.88
PREDICTION_MAX_OFFSET_DELTA = 0.35
PREDICTION_MAX_AREA_DELTA_RATIO = 0.45
PREDICTION_IDLE_DECAY = 0.60
PREDICTION_MIN_OFFSET_STEP = 0.012
PREDICTION_MIN_VERTICAL_STEP = 0.010
PREDICTION_MIN_AREA_RATIO_STEP = 0.045
PREDICTION_CONTROL_MIN_CONF = 0.32

SIDE_TRACK_STEER_KP = 0.95
SIDE_TRACK_MAX_STEER_BIAS = 0.22
SIDE_TRACK_MAX_THROTTLE_BIAS = 0.14
SIDE_TRACK_AREA_GAIN = 0.18
SIDE_STEER_DEADZONE_H = 0.03
SIDE_STALE_BIAS_SCALE = 0.72
YOLO_TRACK_STEER_GAIN = 1.06
YOLO_TRACK_THROTTLE_GAIN = 1.08
WAKE_TRACK_STEER_GAIN = 0.90
WAKE_TRACK_THROTTLE_GAIN = 0.82
WAKE_TRACK_AREA_BIAS = 0.88
FOLLOWER_TRACK_STEER_GAIN = 0.82
FOLLOWER_TRACK_THROTTLE_GAIN = 0.90
FOLLOWER_TRACK_AREA_BIAS = 0.84
FOLLOWER_MOTION_MIN_CONF = 0.10
FOLLOWER_MOTION_STEER_GAIN = 0.42
FOLLOWER_MOTION_MAX_STEER = 0.24
FOLLOWER_AREA_CATCHUP_MAX = 0.04
STALE_TRACK_STEER_GAIN = 0.80
STALE_TRACK_THROTTLE_GAIN = 0.80
VISION_FRONT_TARGET_OFFSET = 0.0
VISION_SIDE_TARGET_OFFSET = 0.0
VISION_AREA_ERROR_DEADZONE_RATIO = 0.06
VISION_FRONT_AREA_TOLERANCE_RATIO = 0.10
VISION_SIDE_AREA_TOLERANCE_RATIO = 0.12
VISION_FRONT_AREA_GAIN = 0.72
VISION_FRONT_AREA_MIN_THROTTLE = 0.08
VISION_FRONT_CRUISE_THROTTLE = 0.18
VISION_FRONT_CRUISE_STEER_LIMIT = 0.055
VISION_FRONT_CRUISE_MAX_POSITIVE_RATIO = 0.20
VISION_FRONT_CRUISE_MAX_NEGATIVE_RATIO = 0.06
VISION_TURN_CATCHUP_GAIN = 0.16
VISION_TURN_CATCHUP_MAX = 0.18
VISION_TURN_SPEED_CEILING = 0.82
VISION_TURN_SLOWDOWN_START = 0.55
VISION_TURN_SLOWDOWN_MIN_SCALE = 0.78
VISION_TURN_FORMATION_AREA_BOOST = 0.18
VISION_TURN_FORMATION_STEER_BOOST = 0.16
VISION_TURN_FORMATION_THROTTLE_SCALE = 0.88

# =========================================================
# 3) 純視覺 PID 控制參數設定
# =========================================================
KV_STEER = 1.35
STEER_DEADZONE_H = 0.035
SEARCH_MODE_STEER = 0.5
KV_THROTTLE_P = 0.00018
FOLLOW_BASE_THROTTLE = 0.40
FOLLOW_MAX_THROTTLE = 0.62

# YOLO 距離設定
YOLO_AREA_OPT = 250000
YOLO_AREA_MIN = 200
YOLO_AREA_MAX = 350000
FOLLOWER_AREA_OPT = 150000
FOLLOWER_AREA_MIN = 200
FOLLOWER_AREA_MAX = 260000

# WAKE(尾流) 傳統視覺距離設定
WAKE_AREA_OPT = 2000
WAKE_AREA_MIN = 650
WAKE_AREA_MAX = 5000
MIN_WAKE_CONTOUR = 220
FUSION_YOLO_OFFSET_WEIGHT = 0.78
FUSION_WAKE_OFFSET_WEIGHT = 0.26
FUSION_MAX_OFFSET_GAP = 0.45
FUSION_MIN_WAKE_WEIGHT = 0.08
PREDICTION_ARROW_MIN_CONF = 0.12
PREDICTION_ARROW_PIXELS = 90
PREDICTION_ARROW_MIN_PIXELS = 18
SIDE_TRACK_STEER_SIGN_BY_BOAT = {"Left": 1.0, "Right": 1.0}

# =========================================================
# 4) 共享狀態區
# =========================================================
vision_lock = threading.Lock()


def make_track_state(default_search_dir):
    return {
        "connected": False,
        "target_detected": False,
        "target_stale": False,
        "method": None,
        "target_bbox": None,
        "target_area": 0.0,
        "target_center_offset": 0.0,
        "target_depth": None,
        "target_depth_confidence": 0.0,
        "depth_status": "Depth disabled",
        "depth_inference_ms": 0.0,
        "fps": 0.0,
        "lost_search_dir": default_search_dir,
        "last_detection_time": 0.0,
        "last_known_offset": 0.0,
        "last_known_area": 0.0,
        "last_known_method": None,
        "track_prev_measurement_time": 0.0,
        "track_prev_center_offset": 0.0,
        "track_prev_center_y": 0.0,
        "track_prev_area": 0.0,
        "track_offset_velocity": 0.0,
        "track_vertical_velocity": 0.0,
        "track_area_velocity": 0.0,
        "predicted_offset": 0.0,
        "predicted_area": 0.0,
        "prediction_confidence": 0.0,
    }


vision_states = {
    stream_name: make_track_state(config["search_dir"])
    for stream_name, config in CAMERA_STREAMS.items()
}

frame_lock = threading.Lock()
latest_frames = {stream_name: None for stream_name in CAMERA_STREAMS}
display_frames = {stream_name: None for stream_name in CAMERA_STREAMS}

# =========================================================
# 🌟 加入這行：用來把 UDP 的船速傳給 OpenCV
boat_speeds = {"Left": 0.0, "Right": 0.0}
# =========================================================

# =========================================================
# 🌟 新增：效能監控變數 (單位：毫秒 ms)
perf_metrics = {
    "Left": {"net_ms": 0.0, "ai_ms": 0.0, "cv_ms": 0.0, "ctrl_ms": 0.0},
    "Right": {"net_ms": 0.0, "ai_ms": 0.0, "cv_ms": 0.0, "ctrl_ms": 0.0}
}
# =========================================================

formation_targets = {
    "Left": {
        "front_visual_initialized": False,
        "desired_front_offset": 0.0,
        "desired_front_area": 0.0,
        "side_visual_initialized": False,
        "desired_side_offset": 0.0,
        "desired_side_area": 0.0,
    },
    "Right": {
        "front_visual_initialized": False,
        "desired_front_offset": 0.0,
        "desired_front_area": 0.0,
        "side_visual_initialized": False,
        "desired_side_offset": 0.0,
        "desired_side_area": 0.0,
    },
}


# =========================================================
# 工具函式
# =========================================================
def recv_exact(conn, size):
    data = b""
    while len(data) < size:
        try:
            packet = conn.recv(size - len(data))
        except socket.timeout:
            return None
        if not packet:
            return None
        data += packet
    return data


def make_status_frame(label, message):
    width, height = WINDOW_SIZE
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(frame, label, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(frame, message, (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 255), 2)
    cv2.putText(
        frame,
        "Check Unity camera sender / port / console",
        (20, 155),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (180, 180, 180),
        2,
    )
    return frame


def clamp(value, low, high):
    return max(min(value, high), low)


def blend_value(previous, current, alpha):
    return previous + (current - previous) * alpha


def get_tracking_gains(method, is_stale):
    if method == "YOLO":
        steer_gain = YOLO_TRACK_STEER_GAIN
        throttle_gain = YOLO_TRACK_THROTTLE_GAIN
    elif method == "FUSED":
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


def update_track_prediction(state, center_offset, center_y_norm, area, current_time):
    prev_time = state.get("track_prev_measurement_time", 0.0)
    prev_offset = state.get("track_prev_center_offset", center_offset)
    prev_center_y = state.get("track_prev_center_y", center_y_norm)
    prev_area = state.get("track_prev_area", area)

    predicted_offset = center_offset
    predicted_area = area
    confidence = 0.0

    if prev_time > 0.0:
        dt = current_time - prev_time
        if 1e-3 < dt <= 1.0:
            d_offset = center_offset - prev_offset
            d_vertical = center_y_norm - prev_center_y
            d_area = area - prev_area
            area_ref = max(area, prev_area, 1.0)
            area_ratio_step = abs(d_area) / area_ref

            if abs(d_offset) < PREDICTION_MIN_OFFSET_STEP:
                d_offset = 0.0
            if abs(d_vertical) < PREDICTION_MIN_VERTICAL_STEP:
                d_vertical = 0.0
            if area_ratio_step < PREDICTION_MIN_AREA_RATIO_STEP:
                d_area = 0.0

            raw_offset_velocity = d_offset / dt
            raw_vertical_velocity = d_vertical / dt
            raw_area_velocity = d_area / dt

            offset_motion = clamp(abs(d_offset) / 0.08, 0.0, 1.0)
            vertical_motion = clamp(abs(d_vertical) / 0.08, 0.0, 1.0)
            area_motion = clamp(area_ratio_step / 0.30, 0.0, 1.0)
            motion_score = max(offset_motion, vertical_motion, area_motion)

            if motion_score <= 1e-4:
                state["track_offset_velocity"] *= PREDICTION_IDLE_DECAY
                state["track_vertical_velocity"] *= PREDICTION_IDLE_DECAY
                state["track_area_velocity"] *= PREDICTION_IDLE_DECAY
                predicted_offset = center_offset
                predicted_area = area
                confidence = 0.0
            else:
                state["track_offset_velocity"] = blend_value(
                    state.get("track_offset_velocity", 0.0),
                    raw_offset_velocity,
                    PREDICTION_VELOCITY_ALPHA,
                )
                state["track_vertical_velocity"] = blend_value(
                    state.get("track_vertical_velocity", 0.0),
                    raw_vertical_velocity,
                    PREDICTION_VELOCITY_ALPHA,
                )
                state["track_area_velocity"] = blend_value(
                    state.get("track_area_velocity", 0.0),
                    raw_area_velocity,
                    PREDICTION_VELOCITY_ALPHA,
                )

                predicted_offset_delta = clamp(
                    state["track_offset_velocity"] * PREDICTION_HORIZON_SEC,
                    -PREDICTION_MAX_OFFSET_DELTA,
                    PREDICTION_MAX_OFFSET_DELTA,
                )
                predicted_offset = clamp(center_offset + predicted_offset_delta, -1.0, 1.0)

                max_area_delta = max(area, prev_area, 1.0) * PREDICTION_MAX_AREA_DELTA_RATIO
                predicted_area_delta = clamp(
                    state["track_area_velocity"] * PREDICTION_HORIZON_SEC,
                    -max_area_delta,
                    max_area_delta,
                )
                predicted_area = max(0.0, area + predicted_area_delta)
                cadence_score = clamp(1.0 - abs(dt - 0.1) / 0.4, 0.0, 1.0)
                confidence = cadence_score * motion_score
        else:
            state["track_offset_velocity"] *= PREDICTION_STALE_DECAY
            state["track_vertical_velocity"] *= PREDICTION_STALE_DECAY
            state["track_area_velocity"] *= PREDICTION_STALE_DECAY
            confidence = state.get("prediction_confidence", 0.0) * PREDICTION_STALE_DECAY

    state["track_prev_measurement_time"] = current_time
    state["track_prev_center_offset"] = center_offset
    state["track_prev_center_y"] = center_y_norm
    state["track_prev_area"] = area
    state["predicted_offset"] = predicted_offset
    state["predicted_area"] = predicted_area
    state["prediction_confidence"] = confidence


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


def build_track_candidate(bbox, area, center_offset, center, method):
    return {
        "bbox": bbox,
        "area": area,
        "center_offset": center_offset,
        "center": center,
        "method": method,
    }


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

    # Keep the vertical anchor near the leader bbox when available.
    fused_center = (fused_center_x, yolo_center[1])

    fused = yolo_target.copy()
    fused["center_offset"] = fused_offset
    fused["center"] = fused_center
    fused["method"] = "FUSED"
    fused["wake_weight"] = wake_weight / max(weight_sum, 1e-5)
    return fused


def draw_prediction_arrow(frame, center_point, offset_velocity, vertical_velocity, confidence):
    if frame is None or center_point is None:
        return

    if confidence < PREDICTION_ARROW_MIN_CONF:
        return

    height, width = frame.shape[:2]
    vx = float(offset_velocity) * (width * 0.5)
    vy = float(vertical_velocity) * height
    magnitude = math.hypot(vx, vy)
    if magnitude < PREDICTION_ARROW_MIN_PIXELS:
        return

    scale = PREDICTION_ARROW_PIXELS * clamp(confidence, 0.35, 1.0) / magnitude
    end_x = int(round(center_point[0] + vx * scale))
    end_y = int(round(center_point[1] + vy * scale))
    end_x = int(clamp(end_x, 0, width - 1))
    end_y = int(clamp(end_y, 0, height - 1))

    if end_x == center_point[0] and end_y == center_point[1]:
        return

    cv2.arrowedLine(
        frame,
        center_point,
        (end_x, end_y),
        (0, 165, 255),
        2,
        tipLength=0.25,
    )
    cv2.putText(
        frame,
        f"traj {confidence:.2f}",
        (center_point[0] + 8, max(center_point[1] - 10, 18)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 165, 255),
        1,
    )


def lock_visual_reference(boat_side, role, center_offset, area):
    formation_ref = formation_targets[boat_side]
    if role == "front":
        init_key = "front_visual_initialized"
        offset_key = "desired_front_offset"
        area_key = "desired_front_area"
        target_offset = VISION_FRONT_TARGET_OFFSET
    else:
        init_key = "side_visual_initialized"
        offset_key = "desired_side_offset"
        area_key = "desired_side_area"
        target_offset = VISION_SIDE_TARGET_OFFSET

    if formation_ref.get(init_key, False):
        return

    formation_ref[offset_key] = target_offset
    formation_ref[area_key] = area
    formation_ref[init_key] = True
    print(
        f"[Formation-{boat_side}] Locked {role} camera ref: "
        f"offset={target_offset:.3f} area={area:.0f} "
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
    except Exception:
        pass

    try:
        torch.backends.cuda.matmul.allow_tf32 = True
    except Exception:
        pass

    try:
        torch.backends.cudnn.allow_tf32 = True
    except Exception:
        pass

    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass

    try:
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


def get_model_class_name(model, cls_id):
    names = getattr(model, "names", {})
    if isinstance(names, dict):
        return str(names.get(cls_id, cls_id))
    if isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
        return str(names[cls_id])
    return str(cls_id)


def get_yolo_box_color(cls_id):
    if cls_id == YOLO_CLASS_LEADER:
        return (255, 0, 255)
    if cls_id == YOLO_CLASS_FOLLOWER:
        return (0, 255, 0)
    return (255, 255, 255)


def draw_labeled_box(frame, bbox, label, color, center=None, thickness=2):
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    if center is not None:
        cv2.circle(frame, center, 5, (0, 0, 255), -1)
    cv2.putText(
        frame,
        label,
        (x1, max(y1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )


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
        if h_box < WAKE_MIN_BBOX_HEIGHT:
            continue
        if w_box < WAKE_MIN_BBOX_WIDTH:
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

            score *= clamp(1.0 - abs(center_offset - ref_offset) / max(WAKE_MAX_OFFSET_FROM_YOLO, 1e-5), 0.35, 1.10)

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

    # 避免把接近畫面底部的自船船頭誤當成尾流。
    if (y + h_box) > height * (1.0 - WAKE_IGNORE_BOTTOM_RATIO):
        return None

    return {
        "bbox": (x, y, x + w_box, y + h_box),
        "area": best_area,
        "center_offset": center_offset,
        "center": (cx, cy),
        "mask": mask,
    }


# =========================================================
# 執行緒：通用 TCP 接收器
# =========================================================
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


# =========================================================
# 執行緒：中央 YOLO + WAKE CV 處理
# =========================================================
def cv_processing_thread():
    print("[Vision] Central processing thread started.")

    try:
        model = YOLO(YOLO_MODEL_PATH)
        print(f"[Vision] Model {YOLO_MODEL_PATH} loaded successfully.")
    except Exception as exc:
        print(f"[Vision] Failed to load YOLO model: {exc}")
        return

    yolo_uses_cuda, yolo_half_enabled = configure_yolo_runtime(model)
    if yolo_uses_cuda:
        print(f"[Vision] YOLO runtime on {YOLO_DEVICE} (half={yolo_half_enabled}).")
    else:
        print("[Vision] YOLO runtime on CPU/default device.")

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
        depth_estimator = DepthAnythingEstimator(
            model_id=DEPTH_ANYTHING_MODEL_ID,
            device=DEPTH_ANYTHING_DEVICE,
        )
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
            pending_streams = []

            for stream_name, config in CAMERA_STREAMS.items():
                boat_side = config["boat"]
                role = config["role"]
                with frame_lock:
                    frame = latest_frames[stream_name]
                    latest_frames[stream_name] = None

                if frame is None:
                    continue

                current_time = time.time()
                height, width = frame.shape[:2]
                display_due = (
                    SHOW_WINDOW
                    and (current_time - display_times[stream_name]) >= DISPLAY_UPDATE_INTERVAL_SEC
                )
                display_frame = frame.copy() if display_due else None

                with vision_lock:
                    prev_state = vision_states[stream_name].copy()

                preferred_offset = prev_state.get("last_known_offset", 0.0)
                last_detection_time = prev_state.get("last_detection_time", 0.0)
                has_recent_track = (current_time - last_detection_time) <= (TRACK_HOLD_SEC + 0.8)

                pending_streams.append(
                    {
                        "stream_name": stream_name,
                        "config": config,
                        "boat_side": boat_side,
                        "role": role,
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

            if not pending_streams:
                time.sleep(0.005)
                continue

            if YOLO_USE_BATCHING and len(pending_streams) < len(CAMERA_STREAMS):
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
                    display_due = (
                        SHOW_WINDOW
                        and (current_time - display_times[stream_name]) >= DISPLAY_UPDATE_INTERVAL_SEC
                    )
                    display_frame = frame.copy() if display_due else None

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

            # ⏱️ 1. 開始計時：YOLO 推論
            t_ai_start = time.perf_counter()

            if YOLO_USE_BATCHING:
                batch_results = model.predict(inference_inputs, **yolo_predict_kwargs)
            else:
                batch_results = [
                    model.predict(frame, **yolo_predict_kwargs)[0]
                    for frame in inference_inputs
                ]
            
            # ⏱️ 2. 結束計時 (將總耗時平分給每個鏡頭)
            avg_ai_ms = ((time.perf_counter() - t_ai_start) * 1000.0) / max(1, len(pending_streams))
            for item in pending_streams:
                perf_metrics[item["boat_side"]]["ai_ms"] = avg_ai_ms

            for item, result in zip(pending_streams, batch_results):
                stream_name = item["stream_name"]
                config = item["config"]
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
                center_point = None
                center_offset = 0.0
                yolo_target = None
                follower_target = None
                wake_target = None
                fused_target = None
                fusion_wake_weight = 0.0
                yolo_display_detections = []
                wake_mask = None
                depth_result = None
                depth_preview = None
                best_follower_score = -1.0

                if result is not None and result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        area = (x2 - x1) * (y2 - y1)
                        if area < YOLO_MIN_BOX_AREA:
                            continue
                        if y1 < height * IGNORE_TOP_RATIO:
                            continue
                        if y2 > height * (1.0 - IGNORE_BOTTOM_RATIO):
                            continue

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
                                )
                        else:
                            if cls_id != YOLO_CLASS_FOLLOWER:
                                continue

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
                                )

                if role == "front":
                    wake_reference_bbox = yolo_target["bbox"] if yolo_target is not None else None

                    # ⏱️ 1. 開始計時：傳統視覺處理
                    t_cv_start = time.perf_counter()

                    wake_result = detect_stern_wake(
                        frame,
                        preferred_offset if has_recent_track else None,
                        wake_reference_bbox,
                    )

                    # ⏱️ 2. 結束計時
                    perf_metrics[boat_side]["cv_ms"] = (time.perf_counter() - t_cv_start) * 1000.0

                    if wake_result is not None:
                        wake_mask = wake_result["mask"]
                        wake_target = build_track_candidate(
                            wake_result["bbox"],
                            wake_result["area"],
                            wake_result["center_offset"],
                            wake_result["center"],
                            "WAKE",
                        )

                    fused_target = fuse_track_sources(yolo_target, wake_target)
                    if fused_target is not None:
                        best_box = fused_target["bbox"]
                        best_area = fused_target["area"]
                        center_offset = fused_target["center_offset"]
                        center_point = fused_target["center"]
                        detection_method = fused_target["method"]
                        fusion_wake_weight = fused_target.get("wake_weight", 0.0)
                    elif yolo_target is not None:
                        best_box = yolo_target["bbox"]
                        best_area = yolo_target["area"]
                        center_offset = yolo_target["center_offset"]
                        center_point = yolo_target["center"]
                        detection_method = yolo_target["method"]
                    else:
                        best_box = None
                        best_area = 0.0
                        center_offset = 0.0
                        center_point = None
                        detection_method = None
                elif follower_target is not None:
                    best_box = follower_target["bbox"]
                    best_area = follower_target["area"]
                    center_offset = follower_target["center_offset"]
                    center_point = follower_target["center"]
                    detection_method = follower_target["method"]
                else:
                    best_box = None
                    best_area = 0.0
                    center_offset = 0.0
                    center_point = None
                    detection_method = None

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
                    depth_result = depth_estimator.estimate(
                        frame,
                        depth_roi_box,
                        input_max_size=DEPTH_INPUT_MAX_SIZE,
                    )
                    cache_entry["updated_at"] = current_time
                    cache_entry["result"] = depth_result
                    if depth_result.get("ok"):
                        cache_entry["preview"] = depth_estimator.build_colormap(depth_result.get("depth_map_norm"))
                    else:
                        cache_entry["preview"] = None

                if (
                    role == "front"
                    and depth_roi_box is not None
                    and (not DEPTH_ONLY_ON_YOLO or yolo_target is not None)
                ):
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

                    if best_box is not None:
                        if role == "front" and detection_method in ("YOLO", "FUSED"):
                            lock_visual_reference(boat_side, "front", center_offset, best_area)
                        elif role == "side" and detection_method == "FOLLOWER":
                            lock_visual_reference(boat_side, "side", center_offset, best_area)

                        previous_offset = state.get("last_known_offset", center_offset)
                        previous_area = state.get("last_known_area", best_area)
                        if state.get("last_detection_time", 0.0) > 0.0:
                            center_offset = blend_value(previous_offset, center_offset, TRACK_OFFSET_ALPHA)
                            best_area = blend_value(previous_area, best_area, TRACK_AREA_ALPHA)

                        center_y_norm = (center_point[1] / float(height)) if center_point is not None else 0.5
                        update_track_prediction(state, center_offset, center_y_norm, best_area, current_time)

                        state["target_detected"] = True
                        state["target_stale"] = False
                        state["method"] = detection_method
                        state["target_bbox"] = best_box
                        state["target_area"] = best_area
                        state["target_center_offset"] = center_offset
                        if role == "front" and depth_result and depth_result.get("ok"):
                            depth_value = depth_result.get("relative_depth")
                            state["target_depth"] = depth_value
                            state["target_depth_confidence"] = depth_result.get("depth_confidence", 0.0)
                            state["depth_inference_ms"] = depth_result.get("inference_sec", 0.0) * 1000.0
                            if depth_value is None:
                                state["depth_status"] = "Depth ROI invalid"
                            else:
                                state["depth_status"] = f"Depth rel={depth_value:.3f}"
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
                                state["depth_status"] = "Side follower track"
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

                        if (
                            yolo_target is not None
                            and det_box == yolo_target["bbox"]
                            and det_cls_id == YOLO_CLASS_LEADER
                        ):
                            det_label += " [target]"
                            det_thickness = 3
                        elif (
                            follower_target is not None
                            and det_box == follower_target["bbox"]
                            and det_cls_id == YOLO_CLASS_FOLLOWER
                            and role == "side"
                        ):
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
                            fusion_label = f"FUSED wake={fusion_wake_weight:.2f}"
                            cv2.putText(
                                display_frame,
                                fusion_label,
                                (16, 76),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.55,
                                (255, 255, 0),
                                2,
                            )
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
                            cv2.putText(
                                display_frame,
                                hold_text,
                                (16, 56),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 200, 255),
                                2,
                            )

                    if wake_mask is not None:
                        mask_small = cv2.resize(
                            wake_mask,
                            (0, 0),
                            fx=WAKE_MASK_PREVIEW_SCALE,
                            fy=WAKE_MASK_PREVIEW_SCALE,
                        )
                        mask_color = cv2.cvtColor(mask_small, cv2.COLOR_GRAY2BGR)
                        mask_h, mask_w = mask_color.shape[:2]
                        display_frame[0:mask_h, 0:mask_w] = mask_color

                    if depth_preview is not None:
                        depth_small = cv2.resize(
                            depth_preview,
                            (0, 0),
                            fx=DEPTH_OVERLAY_SCALE,
                            fy=DEPTH_OVERLAY_SCALE,
                        )
                        depth_h, depth_w = depth_small.shape[:2]
                        depth_y = 0
                        depth_x = max(0, display_frame.shape[1] - depth_w)
                        display_frame[depth_y : depth_y + depth_h, depth_x : depth_x + depth_w] = depth_small

                    if SHOW_OVERLAY_TEXT:
                        text_x = 10
                        if wake_mask is not None:
                            text_x = int(display_frame.shape[1] * WAKE_MASK_PREVIEW_SCALE) + 10
                        cv2.putText(
                            display_frame,
                            f"FPS: {fps:.1f}",
                            (text_x, 28),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (0, 255, 255),
                            1,
                        )
                        cv2.putText(
                            display_frame,
                            overlay_depth_status[:80],
                            (text_x, 48),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (80, 220, 255),
                            1,
                        )
                        if detection_method is not None:
                            cv2.putText(
                                display_frame,
                                f"Track: {role.upper()} {detection_method}",
                                (text_x, 68),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.45,
                                (255, 255, 0),
                                1,
                            )

                        # ==========================================
                        # 🌟 加入這段：把剛剛存的船速拿出來，用綠字畫在 Y=88 的高度
                        current_speed = boat_speeds.get(boat_side, 0.0)
                        cv2.putText(
                            display_frame,
                            f"Speed: {current_speed:.1f} kts",
                            (text_x, 100),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 0),
                            3,
                        )
                        # ==========================================

                    with frame_lock:
                        display_frames[stream_name] = display_frame
                    display_times[stream_name] = current_time

    except Exception as exc:
        print(f"[Vision] Error: {exc}")


# =========================================================
# 單艘船純視覺跟隨 PID 控制
# =========================================================
def process_boat_vision_based(sock, tx_port, side):

    # ⏱️ 1. 開始計時：控制迴圈
    t_ctrl_start = time.perf_counter()

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
        steer_error = effective_offset - desired_front_offset if front_visual_ref_ready else effective_offset
        predicted_area_ratio = normalize_area_error(target_opt, front_predicted_area)
        area_velocity_ratio = float(front_track_area_velocity) / max(float(target_opt), 1.0)

        if abs(steer_error) > STEER_DEADZONE_H:
            steer = clamp(steer_error * KV_STEER * steer_gain, -1.0, 1.0)
        else:
            steer = 0.0

        steer = clamp(steer + side_steer_bias, -1.0, 1.0)

        turn_intensity = clamp(
            (abs(steer) - STEER_DEADZONE_H) / max(1e-5, (1.0 - STEER_DEADZONE_H)),
            0.0,
            1.0,
        )
        if turn_intensity > 0.0:
            if front_method in ("YOLO", "FUSED") and front_visual_ref_ready:
                turn_area_scale = 1.0 + (VISION_TURN_FORMATION_AREA_BOOST * turn_intensity)
                target_opt *= turn_area_scale
                target_min *= turn_area_scale
                target_max *= turn_area_scale
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
            throttle = clamp(
                shaped_front_area_error * VISION_FRONT_AREA_GAIN * throttle_gain,
                0.0,
                FOLLOW_MAX_THROTTLE,
            )
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
            throttle += far_boost
            throttle_ceiling = FOLLOW_FAR_MAX_THROTTLE

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
            # Wake 只拿來做跟蹤方向的補強，不要比 bbox 距離控制更激進。
            throttle = min(throttle, VISION_FRONT_CRUISE_THROTTLE)

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
        if DISABLE_SEARCH_MODE:
            throttle = max(0.0, side_throttle_bias)
            steer = side_steer_bias
        else:
            # 沒看到 leader 時，靠最後觀測方向做小幅搜尋，並保留 side camera 修正。
            throttle = SEARCH_FORWARD_THROTTLE + max(0.0, side_throttle_bias)
            if abs(last_known_offset) > STEER_DEADZONE_H:
                steer = clamp(
                    last_known_offset * KV_STEER * SEARCH_STEER_GAIN,
                    -SEARCH_MODE_STEER,
                    SEARCH_MODE_STEER,
                )
            else:
                steer = (lost_search_dir * SEARCH_MODE_STEER) + side_steer_bias

    throttle = clamp(throttle, 0.0, throttle_ceiling)
    steer = clamp(steer, -1.0, 1.0)

    msg = json.dumps({"throttle": throttle, "steer": steer})
    sock.sendto(msg.encode("utf-8"), (UDP_IP, tx_port))

    speed_mps = state.get("speed", 0.0)

    # ⏱️ 2. 結束計時並存檔
    global perf_metrics
    perf_metrics[side]["ctrl_ms"] = (time.perf_counter() - t_ctrl_start) * 1000.0

    # ==========================================
    # 🌟 加入這兩行：把算好的節(knots)存進全域變數
    global boat_speeds
    boat_speeds[side] = speed_mps * 1.94384
    # ==========================================   

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
        "pred_offset": front_predicted_offset if front_detected else 0.0,
        "pred_conf": front_prediction_confidence if front_detected else 0.0,
        "side_steer_bias": side_steer_bias,
        "side_throttle_bias": side_throttle_bias,
        "speed_knots": speed_mps * 1.94384,
    }


# =========================================================
# 啟動點
# =========================================================
def main():
    print("=======================================")
    print("雙船 Fully Vision-Based 啟動")
    print("=======================================")

    if SHOW_WINDOW:
        for stream_name, config in CAMERA_STREAMS.items():
            cv2.namedWindow(config["window"], cv2.WINDOW_NORMAL)
            cv2.resizeWindow(config["window"], *WINDOW_SIZE)
        with frame_lock:
            for stream_name, config in CAMERA_STREAMS.items():
                display_frames[stream_name] = make_status_frame(config["window"], "Waiting for TCP stream...")

    receiver_threads = []
    for stream_name, config in CAMERA_STREAMS.items():
        receiver_threads.append(
            threading.Thread(
                target=tcp_camera_receiver_thread,
                args=(config["port"], stream_name),
                daemon=True,
            )
        )
    t_cv = threading.Thread(target=cv_processing_thread, daemon=True)

    for receiver_thread in receiver_threads:
        receiver_thread.start()
    t_cv.start()

    last_print_time = time.time()
    last_loop_time = time.time()
    t_udp = 0.0
    t_ui_copy = 0.0
    t_imshow = 0.0
    t_waitkey = 0.0

    try:
        while True:
            loop_start = time.time()
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
                for stream_name, frame in disp_frames.items():
                    cv2.imshow(CAMERA_STREAMS[stream_name]["window"], frame)
                t_imshow = time.time() - t0

                t0 = time.time()
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                t_waitkey = time.time() - t0
            else:
                t_imshow = 0.0
                t_waitkey = 0.0

            current_time = time.time()
            if current_time - last_print_time > 0.2:
                print_parts = []

                if res_left:
                    method_left = res_left["method"] or "   "
                    symbol_left = "~" if res_left["stale"] else ("*" if res_left["detected"] else ".")
                    side_symbol_left = "~" if res_left["side_stale"] else ("*" if res_left["side_detected"] else ".")
                    side_method_left = res_left["side_method"] or "   "
                    pm_l = perf_metrics["Left"]
                    print_parts.append(
                        f"[L-{method_left}] {symbol_left} 舵:{res_left['steer']:5.2f} "
                        f"油:{res_left['throttle']:4.2f} S:{res_left['area']:>5.0f} "
                        f"P:{res_left['pred_offset']:>5.2f} "
                        f"| ⏱️ AI:{pm_l['ai_ms']:4.1f}ms CV:{pm_l['cv_ms']:4.1f}ms 控:{pm_l['ctrl_ms']:4.2f}ms"
                    )

                if res_right:
                    method_right = res_right["method"] or "   "
                    symbol_right = "~" if res_right["stale"] else ("*" if res_right["detected"] else ".")
                    side_symbol_right = "~" if res_right["side_stale"] else ("*" if res_right["side_detected"] else ".")
                    side_method_right = res_right["side_method"] or "   "
                    pm_r = perf_metrics["Right"]
                    print_parts.append(
                        f"[R-{method_right}] {symbol_right} 舵:{res_right['steer']:5.2f} "
                        f"油:{res_right['throttle']:4.2f} S:{res_right['area']:>5.0f} "
                        f"P:{res_right['pred_offset']:>5.2f} "
                        f"| ⏱️ AI:{pm_r['ai_ms']:4.1f}ms CV:{pm_r['cv_ms']:4.1f}ms 控:{pm_r['ctrl_ms']:4.2f}ms"
                    )

                if print_parts:
                    print(" || ".join(print_parts))
                last_print_time = current_time

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        if SHOW_WINDOW:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
