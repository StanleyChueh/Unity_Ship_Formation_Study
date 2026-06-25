'''
    Helpers for USV control and visualization.
'''

import math
import socket

import cv2
import numpy as np

from .config import (
    FINAL_STEER_DEADZONE_H,
    PREDICTION_ARROW_MIN_CONF,
    PREDICTION_ARROW_MIN_PIXELS,
    PREDICTION_ARROW_PIXELS,
    STEER_SLEW_RATE_PER_SEC,
    RIGHT_STEER_SLEW_RATE_PER_SEC,
    WINDOW_SIZE,
    YOLO_CLASS_FOLLOWER,
    YOLO_CLASS_LEADER,
)
from .state import controller_states

# recv_exact: 
#   Reliable socket receive function that ensures the exact number of bytes is read.
#   Returns None on timeout or connection closure.
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

# make_track_state:
#   Initializes the tracking state for a camera stream, 
#   including connection status, target detection info, and tracking history.
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


def get_peer_boat_side(boat_side):
    return "Right" if boat_side == "Left" else "Left"


def filter_steer_command(boat_side, raw_steer, current_time):
    control_state = controller_states[boat_side]

    if abs(raw_steer) < FINAL_STEER_DEADZONE_H:
        raw_steer = 0.0

    last_steer = control_state.get("last_steer", 0.0)
    last_command_time = control_state.get("last_command_time", 0.0)
    if last_command_time > 0.0:
        dt = clamp(current_time - last_command_time, 0.01, 0.25)
    else:
        dt = 0.05

    # Use a lower slew rate for the Right follower to reduce abrupt steering
    # changes that were observed as higher steer-jerkiness on the Right side.
    try:
        per_side_rate = RIGHT_STEER_SLEW_RATE_PER_SEC if str(boat_side).strip().lower() == "right" else STEER_SLEW_RATE_PER_SEC
    except Exception:
        per_side_rate = STEER_SLEW_RATE_PER_SEC

    max_delta = float(per_side_rate) * dt
    filtered_steer = clamp(raw_steer, last_steer - max_delta, last_steer + max_delta)

    if abs(filtered_steer) < FINAL_STEER_DEADZONE_H and raw_steer == 0.0:
        filtered_steer = 0.0

    control_state["last_steer"] = filtered_steer
    control_state["last_command_time"] = current_time
    return filtered_steer


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

# draw_prediction_arrow:
#   Draws an arrow on the frame indicating the predicted movement direction and confidence.
def draw_prediction_arrow(frame, center_point, offset_velocity, vertical_velocity, confidence):
    if frame is None or center_point is None or confidence < PREDICTION_ARROW_MIN_CONF:
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

    cv2.arrowedLine(frame, center_point, (end_x, end_y), (0, 165, 255), 2, tipLength=0.25)
    cv2.putText(
        frame,
        f"traj {confidence:.2f}",
        (center_point[0] + 8, max(center_point[1] - 10, 18)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 165, 255),
        1,
    )
