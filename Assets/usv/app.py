'''
    Main application logic for the USV vision-based control system.
'''

import socket
import threading
import time

import cv2

from .config import (
    CAMERA_STREAMS,
    PORT_LEFT_RX,
    PORT_LEFT_TX,
    PORT_RIGHT_RX,
    PORT_RIGHT_TX,
    SHOW_WINDOW,
    UDP_IP,
    WINDOW_SIZE,
)
from .control import process_boat_vision_based
from .helpers import apply_camera_shake, make_status_frame
from .state import display_frames, frame_lock
from .vision import cv_processing_thread, tcp_camera_receiver_thread


def _build_udp_socket(port_rx):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, port_rx))
    sock.setblocking(False)
    return sock


def main():
    sock_left = _build_udp_socket(PORT_LEFT_RX)
    sock_right = _build_udp_socket(PORT_RIGHT_RX)

    print("=======================================")
    print("雙船 Fully Vision-Based 啟動")
    print("=======================================")

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
                    cv2.imshow(CAMERA_STREAMS[stream_name]["window"], shaken_frame)
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
