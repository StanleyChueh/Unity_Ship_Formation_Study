'''
    Main application logic for the USV vision-based control system.
'''

import socket
import json
import threading
import time

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
)
from .control import process_boat_vision_based
from .helpers import apply_camera_shake, make_status_frame
from .state import display_frames, frame_lock, runtime_settings, vision_lock, vision_states
from .vision import cv_processing_thread, tcp_camera_receiver_thread


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
        if SHOW_WINDOW:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
