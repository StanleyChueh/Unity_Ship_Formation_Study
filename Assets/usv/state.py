import threading

from .config import BOAT_SIDES, CAMERA_STREAMS, ENABLE_KALMAN_FILTER, SYNC_FOLLOWER_STARTUP_ENABLE, ENABLE_SIDE_DETECTION


vision_lock = threading.Lock()
frame_lock = threading.Lock()


runtime_settings = {
    "enable_kalman_filter": ENABLE_KALMAN_FILTER,
    # Toggle to enable/disable using side-camera detections for control (default from config)
    "enable_side_detection": bool(ENABLE_SIDE_DETECTION),
    "startup_sync_enabled": SYNC_FOLLOWER_STARTUP_ENABLE,
    "startup_sync_released": not SYNC_FOLLOWER_STARTUP_ENABLE,
    "startup_sync_ready_since": None,
    "startup_sync_started_at": None,
    "startup_sync_status": "disabled" if not SYNC_FOLLOWER_STARTUP_ENABLE else "waiting",
    "startup_sync_wait_reason": "",
    "formation_mode": "v",
    # V --> Line Right Side Acceleration parameters
    "right_line_transition_until": 0.0,
    "right_line_throttle_scale": 0.60,
    "right_line_transition_sec": 2.0,
    # V --> Line Right Side Deceleration parameters
    "right_v_recovery_until": 0.0,
    "right_v_recovery_boost": 0.25,
    "right_v_recovery_sec": 4.0,
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
        "target_kind": None,
        "side_leader_detected": False,
        "side_leader_area": 0.0,
        "side_leader_center_offset": 0.0,
        "side_follower_detected": False,
        "side_follower_area": 0.0,
        "side_follower_center_offset": 0.0,
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
        "last_known_target_kind": None,
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
        "desired_front_target_kind": None,
        "side_visual_initialized": False,
        "desired_side_offset": 0.0,
        "desired_side_area": 0.0,
        "desired_side_target_kind": None,
    },
    "Right": {
        "front_visual_initialized": False,
        "desired_front_offset": 0.0,
        "desired_front_area": 0.0,
        "desired_front_target_kind": None,
        "side_visual_initialized": False,
        "desired_side_offset": 0.0,
        "desired_side_area": 0.0,
        "desired_side_target_kind": None,
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
        "speed_mps": 0.0,
        "yaw_deg": 0.0,
        "yaw_rate_dps": 0.0,
        "leader_speed_mps": 0.0,
    }
    for boat_side in BOAT_SIDES
}
