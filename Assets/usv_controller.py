import json
import socket
import struct
import threading
import time

import cv2
import numpy as np
from ultralytics import YOLO

from depth_Anything import DepthAnythingEstimator

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
PORT_LEFT_CAM = 9998
PORT_RIGHT_CAM = 9999

SHOW_WINDOW = True
SHOW_OVERLAY_TEXT = True
YOLO_MODEL_PATH = "../best.pt"
USE_DEPTH_ANYTHING_TEST = True
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
IGNORE_TOP_RATIO = 0.25
IGNORE_BOTTOM_RATIO = 0.18

WAKE_LOWER_WHITE = np.array([0, 0, 240], dtype=np.uint8)
WAKE_UPPER_WHITE = np.array([180, 50, 255], dtype=np.uint8)
WAKE_SKY_CROP_RATIO = 0.50
WAKE_BOAT_CROP_RATIO = 0.75
WAKE_MASK_PREVIEW_SCALE = 0.30

TRACK_HOLD_SEC = 0.60
TRACK_REACQUIRE_BIAS = 0.35
TRACK_OFFSET_ALPHA = 0.35
TRACK_AREA_ALPHA = 0.25
STALE_TARGET_THROTTLE_SCALE = 0.65
STALE_TARGET_STEER_SCALE = 0.85
SEARCH_FORWARD_THROTTLE = 0.18
SEARCH_STEER_GAIN = 0.75
LEADER_START_SPEED_MPS = 0.35
LEADER_START_CONFIRM_SEC = 0.75
DISABLE_SEARCH_MODE = True

# =========================================================
# 3) 純視覺 PID 控制參數設定
# =========================================================
KV_STEER = 1.2
STEER_DEADZONE_H = 0.05
SEARCH_MODE_STEER = 0.5
KV_THROTTLE_P = 0.00015
FOLLOW_BASE_THROTTLE = 0.35
FOLLOW_MAX_THROTTLE = 0.45

# YOLO 距離設定
YOLO_AREA_OPT = 250000
YOLO_AREA_MIN = 200
YOLO_AREA_MAX = 350000

# WAKE(尾流) 傳統視覺距離設定
WAKE_AREA_OPT = 2000
WAKE_AREA_MIN = 500
WAKE_AREA_MAX = 5000
MIN_WAKE_CONTOUR = 150

# =========================================================
# 4) 共享狀態區
# =========================================================
vision_lock = threading.Lock()
vision_states = {
    "Left": {
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
        "lost_search_dir": 1.0,
        "last_detection_time": 0.0,
        "last_known_offset": 0.0,
        "last_known_area": 0.0,
        "last_known_method": None,
        "leader_motion_since": 0.0,
        "movement_started": False,
    },
    "Right": {
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
        "lost_search_dir": -1.0,
        "last_detection_time": 0.0,
        "last_known_offset": 0.0,
        "last_known_area": 0.0,
        "last_known_method": None,
        "leader_motion_since": 0.0,
        "movement_started": False,
    },
}

frame_lock = threading.Lock()
latest_frames = {"Left": None, "Right": None}
display_frames = {"Left": None, "Right": None}


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


def make_status_frame(side, message):
    width, height = WINDOW_SIZE
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(frame, f"{side} Camera", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
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


def get_model_class_name(model, cls_id):
    names = getattr(model, "names", {})
    if isinstance(names, dict):
        return str(names.get(cls_id, cls_id))
    if isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
        return str(names[cls_id])
    return str(cls_id)


def format_depth_value(depth_value):
    if depth_value is None:
        return "---"
    return f"{depth_value:.3f}"


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


def reset_vision_state(side):
    with vision_lock:
        state = vision_states[side]
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
        state["leader_motion_since"] = 0.0
        state["movement_started"] = False


def detect_stern_wake(frame, preferred_offset=None):
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, WAKE_LOWER_WHITE, WAKE_UPPER_WHITE)

    sky_crop = int(height * WAKE_SKY_CROP_RATIO)
    boat_crop = int(height * WAKE_BOAT_CROP_RATIO)
    mask[:sky_crop, :] = 0
    mask[boat_crop:, :] = 0

    kernel_open = np.ones((3, 3), np.uint8)
    kernel_close = np.ones((1, 30), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_cnt = None
    best_area = 0.0
    best_score = -1.0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_WAKE_CONTOUR:
            continue

        score = area
        if preferred_offset is not None:
            moments = cv2.moments(cnt)
            if moments["m00"] != 0:
                cx = moments["m10"] / moments["m00"]
                center_offset = (cx - (width / 2.0)) / (width / 2.0)
                score *= 1.0 - min(abs(center_offset - preferred_offset), 1.0) * TRACK_REACQUIRE_BIAS

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
    if (y + h_box) > height * (1.0 - IGNORE_BOTTOM_RATIO):
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
def tcp_camera_receiver_thread(port, side):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port))
    server.listen(1)

    print(f"[TCP] Waiting for {side} Camera on {HOST}:{port} ...")

    while True:
        conn = None
        try:
            conn, addr = server.accept()
            conn.settimeout(TCP_FRAME_TIMEOUT)
            print(f"[TCP] {side} Camera Connected by {addr}")

            with vision_lock:
                vision_states[side]["connected"] = True

            while True:
                header = recv_exact(conn, 12)
                if header is None:
                    break

                width, height, data_len = struct.unpack("iii", header)
                if width <= 0 or height <= 0:
                    print(f"[TCP] {side} Camera invalid frame size header: {(width, height, data_len)}")
                    break
                if data_len <= 0 or data_len > MAX_JPEG_BYTES:
                    print(f"[TCP] {side} Camera invalid jpeg bytes: {data_len}")
                    break

                jpg_bytes = recv_exact(conn, data_len)
                if jpg_bytes is None:
                    break

                img_array = np.frombuffer(jpg_bytes, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is None:
                    print(f"[TCP] {side} Camera decode failed for a frame.")
                    continue

                with frame_lock:
                    latest_frames[side] = frame

        except Exception as exc:
            print(f"[TCP] {side} Camera receiver error: {exc}")
        finally:
            reset_vision_state(side)

            with frame_lock:
                latest_frames[side] = None
                if SHOW_WINDOW:
                    display_frames[side] = make_status_frame(side, "Waiting for TCP stream...")
                else:
                    display_frames[side] = None

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

    times_dict = {"Left": time.time(), "Right": time.time()}
    depth_cache = {
        "Left": {"result": None, "preview": None, "updated_at": 0.0},
        "Right": {"result": None, "preview": None, "updated_at": 0.0},
    }

    try:
        while True:
            processed_any = False

            for side in ["Left", "Right"]:
                with frame_lock:
                    frame = latest_frames[side]
                    latest_frames[side] = None

                if frame is None:
                    continue

                processed_any = True
                frame = frame.copy()
                height, width = frame.shape[:2]
                display_frame = frame.copy() if SHOW_WINDOW else None

                with vision_lock:
                    prev_state = vision_states[side].copy()

                preferred_offset = prev_state.get("last_known_offset", 0.0)
                last_detection_time = prev_state.get("last_detection_time", 0.0)
                has_recent_track = (time.time() - last_detection_time) <= (TRACK_HOLD_SEC + 0.8)

                results = model.predict(
                    frame,
                    verbose=False,
                    conf=YOLO_CONFIDENCE,
                    classes=YOLO_CLASSES,
                )

                best_box = None
                best_area = 0.0
                best_score = -1.0
                best_cls_name = ""
                detection_method = None
                center_point = None
                center_offset = 0.0
                yolo_display_detections = []
                wake_mask = None
                depth_result = None
                depth_preview = None

                if results:
                    for box in results[0].boxes:
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

                        if cls_id != YOLO_CLASS_LEADER:
                            continue

                        candidate_offset = (((x1 + x2) / 2.0) - (width / 2.0)) / (width / 2.0)
                        score = area
                        if has_recent_track:
                            score *= 1.0 - min(abs(candidate_offset - preferred_offset), 1.0) * TRACK_REACQUIRE_BIAS

                        if score > best_score:
                            best_score = score
                            best_area = area
                            best_box = (x1, y1, x2, y2)
                            best_cls_name = get_model_class_name(model, cls_id)
                            center_point = ((x1 + x2) // 2, (y1 + y2) // 2)
                            center_offset = candidate_offset
                            detection_method = "YOLO"

                if best_box is None:
                    wake_result = detect_stern_wake(frame, preferred_offset if has_recent_track else None)
                    if wake_result is not None:
                        best_box = wake_result["bbox"]
                        best_area = wake_result["area"]
                        center_offset = wake_result["center_offset"]
                        center_point = wake_result["center"]
                        wake_mask = wake_result["mask"]
                        detection_method = "WAKE"

                current_time = time.time()
                cache_entry = depth_cache[side]
                should_run_depth = (
                    depth_estimator is not None
                    and best_box is not None
                    and (
                        not DEPTH_ONLY_ON_YOLO
                        or detection_method == "YOLO"
                    )
                    and (current_time - cache_entry["updated_at"]) >= DEPTH_UPDATE_INTERVAL_SEC
                )

                if should_run_depth:
                    depth_result = depth_estimator.estimate(
                        frame,
                        best_box,
                        input_max_size=DEPTH_INPUT_MAX_SIZE,
                    )
                    cache_entry["updated_at"] = current_time
                    cache_entry["result"] = depth_result
                    if depth_result.get("ok"):
                        cache_entry["preview"] = depth_estimator.build_colormap(depth_result.get("depth_map_norm"))
                    else:
                        cache_entry["preview"] = None

                if best_box is not None and (not DEPTH_ONLY_ON_YOLO or detection_method == "YOLO"):
                    depth_result = cache_entry["result"]
                    depth_preview = cache_entry["preview"]
                else:
                    depth_result = None
                    depth_preview = None

                dt = current_time - times_dict[side]
                times_dict[side] = current_time
                fps = 1.0 / dt if dt > 0 else 0.0

                with vision_lock:
                    state = vision_states[side]
                    state["fps"] = fps
                    overlay_depth_status = state.get("depth_status", "Depth disabled")

                    if best_box is not None:
                        previous_offset = state.get("last_known_offset", center_offset)
                        previous_area = state.get("last_known_area", best_area)
                        if state.get("last_detection_time", 0.0) > 0.0:
                            center_offset = blend_value(previous_offset, center_offset, TRACK_OFFSET_ALPHA)
                            best_area = blend_value(previous_area, best_area, TRACK_AREA_ALPHA)

                        state["target_detected"] = True
                        state["target_stale"] = False
                        state["method"] = detection_method
                        state["target_bbox"] = best_box
                        state["target_area"] = best_area
                        state["target_center_offset"] = center_offset
                        if depth_result and depth_result.get("ok"):
                            depth_value = depth_result.get("relative_depth")
                            state["target_depth"] = depth_value
                            state["target_depth_confidence"] = depth_result.get("depth_confidence", 0.0)
                            state["depth_inference_ms"] = depth_result.get("inference_sec", 0.0) * 1000.0
                            if depth_value is None:
                                state["depth_status"] = "Depth ROI invalid"
                            else:
                                state["depth_status"] = f"Depth rel={depth_value:.3f}"
                        elif depth_result:
                            state["target_depth"] = None
                            state["target_depth_confidence"] = 0.0
                            state["depth_inference_ms"] = 0.0
                            state["depth_status"] = f"Depth unavailable: {depth_result.get('error', 'unknown error')}"
                        else:
                            state["target_depth"] = None
                            state["target_depth_confidence"] = 0.0
                            state["depth_inference_ms"] = 0.0
                            if depth_estimator is not None and detection_method != "YOLO" and DEPTH_ONLY_ON_YOLO:
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
                    else:
                        time_since_seen = current_time - state.get("last_detection_time", 0.0)
                        if state.get("last_known_method") is not None and time_since_seen <= TRACK_HOLD_SEC:
                            state["target_detected"] = True
                            state["target_stale"] = True
                            state["method"] = state["last_known_method"]
                            state["target_bbox"] = None
                            state["target_area"] = state.get("last_known_area", 0.0)
                            state["target_center_offset"] = state.get("last_known_offset", 0.0)
                            overlay_depth_status = state.get("depth_status", "Depth idle")
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
                            if depth_estimator is not None and not depth_estimator.available:
                                state["depth_status"] = f"Depth unavailable: {depth_estimator.error}"
                            elif depth_estimator is not None:
                                state["depth_status"] = "Depth idle"
                            else:
                                state["depth_status"] = "Depth disabled"
                            overlay_depth_status = state["depth_status"]

                if SHOW_WINDOW and display_frame is not None:
                    for detection in yolo_display_detections:
                        det_box = detection["bbox"]
                        det_cls_id = detection["cls_id"]
                        det_color = get_yolo_box_color(det_cls_id)
                        det_label = f"YOLO({detection['cls_name']}): {detection['area']:.0f}"
                        det_thickness = 2

                        if (
                            detection_method == "YOLO"
                            and best_box is not None
                            and det_box == best_box
                            and det_cls_id == YOLO_CLASS_LEADER
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

                    if best_box is not None:
                        if detection_method == "WAKE":
                            draw_labeled_box(
                                display_frame,
                                best_box,
                                f"WAKE Area: {best_area:.0f}",
                                (0, 255, 255),
                                center=center_point,
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

                    with frame_lock:
                        display_frames[side] = display_frame

            if not processed_any:
                time.sleep(0.005)

    except Exception as exc:
        print(f"[Vision] Error: {exc}")


# =========================================================
# 單艘船純視覺跟隨 PID 控制
# =========================================================
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

    with vision_lock:
        vision_state = vision_states[side].copy()

    is_detected = vision_state["target_detected"]
    is_stale = vision_state.get("target_stale", False)
    method = vision_state["method"]
    offset_x = vision_state["target_center_offset"]
    area = vision_state["target_area"]
    depth = vision_state.get("target_depth")
    depth_status = vision_state.get("depth_status", "Depth disabled")
    last_known_offset = vision_state.get("last_known_offset", 0.0)
    lost_search_dir = vision_state.get("lost_search_dir", 1.0)
    leader_motion_since = vision_state.get("leader_motion_since", 0.0)
    movement_started = vision_state.get("movement_started", False)
    leader_speed = state.get("leader_speed", 0.0)

    throttle = 1.0
    steer = 0.0

    # Hold the followers at their spawn positions until the leader has
    # clearly started moving once. This prevents the startup "search drift"
    # that makes them wander away before the mission begins.
    if not movement_started:
        now = time.time()
        if leader_speed >= LEADER_START_SPEED_MPS:
            if leader_motion_since <= 0.0:
                with vision_lock:
                    vision_states[side]["leader_motion_since"] = now
            elif (now - leader_motion_since) >= LEADER_START_CONFIRM_SEC:
                with vision_lock:
                    vision_states[side]["movement_started"] = True
                    vision_states[side]["leader_motion_since"] = 0.0
                movement_started = True
        else:
            with vision_lock:
                vision_states[side]["leader_motion_since"] = 0.0

        if not movement_started:
            throttle = 0.0
            steer = 0.0

            msg = json.dumps({"throttle": throttle, "steer": steer})
            sock.sendto(msg.encode("utf-8"), (UDP_IP, tx_port))

            speed_mps = state.get("speed", 0.0)
            return {
                "detected": is_detected,
                "stale": is_stale,
                "method": method,
                "throttle": throttle,
                "steer": steer,
                "area": area if is_detected else 0.0,
                "depth": depth,
                "depth_status": depth_status,
                "offset": offset_x if is_detected else 0.0,
                "speed_knots": speed_mps * 1.94384,
            }

    if is_detected:
        if method == "YOLO":
            target_opt, target_min, target_max = YOLO_AREA_OPT, YOLO_AREA_MIN, YOLO_AREA_MAX
        else:
            target_opt, target_min, target_max = WAKE_AREA_OPT, WAKE_AREA_MIN, WAKE_AREA_MAX

        if abs(offset_x) > STEER_DEADZONE_H:
            steer = clamp(offset_x * KV_STEER, -1.0, 1.0)
        else:
            steer = 0.0

        if steer != 0.0:
            with vision_lock:
                vision_states[side]["lost_search_dir"] = 1.0 if steer > 0 else -1.0

        error_area = target_opt - area
        if area > target_max:
            throttle = 0.0
        elif area < target_min:
            throttle = FOLLOW_MAX_THROTTLE
        else:
            throttle = FOLLOW_BASE_THROTTLE + (error_area * KV_THROTTLE_P)

        if abs(steer) > 0.4:
            throttle *= 0.5

        if is_stale:
            steer *= STALE_TARGET_STEER_SCALE
            if throttle > 0.0:
                throttle = max(throttle * STALE_TARGET_THROTTLE_SCALE, SEARCH_FORWARD_THROTTLE)
    else:
        if DISABLE_SEARCH_MODE:
            throttle = 0.0
            steer = 0.0
        else:
            # 沒看到目標時低速前進，並往最後觀測到的方向搜尋。
            throttle = SEARCH_FORWARD_THROTTLE
            if abs(last_known_offset) > STEER_DEADZONE_H:
                steer = clamp(
                    last_known_offset * KV_STEER * SEARCH_STEER_GAIN,
                    -SEARCH_MODE_STEER,
                    SEARCH_MODE_STEER,
                )
            else:
                steer = lost_search_dir * SEARCH_MODE_STEER

    throttle = clamp(throttle, 0.0, FOLLOW_MAX_THROTTLE)
    steer = clamp(steer, -1.0, 1.0)

    msg = json.dumps({"throttle": throttle, "steer": steer})
    sock.sendto(msg.encode("utf-8"), (UDP_IP, tx_port))

    speed_mps = state.get("speed", 0.0)
    return {
        "detected": is_detected,
        "stale": is_stale,
        "method": method,
        "throttle": throttle,
        "steer": steer,
        "area": area if is_detected else 0.0,
        "depth": depth,
        "depth_status": depth_status,
        "offset": offset_x if is_detected else 0.0,
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
        cv2.namedWindow("Left Camera", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Right Camera", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Left Camera", *WINDOW_SIZE)
        cv2.resizeWindow("Right Camera", *WINDOW_SIZE)
        with frame_lock:
            display_frames["Left"] = make_status_frame("Left", "Waiting for TCP stream...")
            display_frames["Right"] = make_status_frame("Right", "Waiting for TCP stream...")

    t_left = threading.Thread(target=tcp_camera_receiver_thread, args=(PORT_LEFT_CAM, "Left"), daemon=True)
    t_right = threading.Thread(target=tcp_camera_receiver_thread, args=(PORT_RIGHT_CAM, "Right"), daemon=True)
    t_cv = threading.Thread(target=cv_processing_thread, daemon=True)

    t_left.start()
    t_right.start()
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
            disp_left = None
            disp_right = None
            if SHOW_WINDOW:
                with frame_lock:
                    if display_frames["Left"] is not None:
                        disp_left = display_frames["Left"].copy()
                        display_frames["Left"] = None
                    if display_frames["Right"] is not None:
                        disp_right = display_frames["Right"].copy()
                        display_frames["Right"] = None
            t_ui_copy = time.time() - t0

            if SHOW_WINDOW:
                t0 = time.time()
                if disp_left is not None:
                    cv2.imshow("Left Camera", disp_left)
                if disp_right is not None:
                    cv2.imshow("Right Camera", disp_right)
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
                    print_parts.append(
                        f"[L-{method_left}] {symbol_left} 舵:{res_left['steer']:5.2f} "
                        f"油:{res_left['throttle']:4.2f} S:{res_left['area']:>5.0f} "
                        f"D:{format_depth_value(res_left['depth'])}"
                    )

                if res_right:
                    method_right = res_right["method"] or "   "
                    symbol_right = "~" if res_right["stale"] else ("*" if res_right["detected"] else ".")
                    print_parts.append(
                        f"[R-{method_right}] {symbol_right} 舵:{res_right['steer']:5.2f} "
                        f"油:{res_right['throttle']:4.2f} S:{res_right['area']:>5.0f} "
                        f"D:{format_depth_value(res_right['depth'])}"
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
