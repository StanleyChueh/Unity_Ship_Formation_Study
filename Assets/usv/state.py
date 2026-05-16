import threading

from .config import BOAT_SIDES, CAMERA_STREAMS, ENABLE_KALMAN_FILTER


vision_lock = threading.Lock()
frame_lock = threading.Lock()


runtime_settings = {
    "enable_kalman_filter": ENABLE_KALMAN_FILTER,
}


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
        # optional Kalman filter instance (initialized lazily in vision)
        "kf": None,
    }


vision_states = {
    stream_name: make_track_state(config["search_dir"])
    for stream_name, config in CAMERA_STREAMS.items()
}

latest_frames = {stream_name: None for stream_name in CAMERA_STREAMS}
display_frames = {stream_name: None for stream_name in CAMERA_STREAMS}

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

controller_states = {
    boat_side: {
        "last_steer": 0.0,
        "last_command_time": 0.0,
    }
    for boat_side in BOAT_SIDES
}

boat_comm_states = {
    boat_side: {
        "connected": False,
        "last_packet_time": 0.0,
    }
    for boat_side in BOAT_SIDES
}
