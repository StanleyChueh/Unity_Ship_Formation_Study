'''
    Configuration parameters for the USV vision-based control system.
'''

import os
import numpy as np

# =========================================================
# UDP / TCP settings
# =========================================================
UDP_IP = "127.0.0.1"

# (Follower_Left)
PORT_LEFT_RX = 5066
PORT_LEFT_TX = 5065

# (Follower_Right)
PORT_RIGHT_RX = 5068
PORT_RIGHT_TX = 5067

# (Leader)
LEADER_RX = 5075
LEADER_TX = 5074

# (Formation Mode)
FORMATION_MODE_RX = 5072

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

# =========================================================
# Vision / display / model
# =========================================================
SHOW_WINDOW = True
SHOW_SIDE_WINDOWS = False
SHOW_OVERLAY_TEXT = True
DISPLAY_UPDATE_INTERVAL_SEC = 0.0
YOLO_MODEL_PATH = "../best_v2.pt"
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
YOLO_CONFIDENCE = 0.25       # raised from 0.12 to reduce wave-glitter false positives; lower if real detections are missed
YOLO_MIN_BOX_AREA = 300
YOLO_DEVICE = "cuda:0"
YOLO_USE_BATCHING = True
YOLO_IMGSZ = 640
YOLO_BATCH_WAIT_SEC = 0.008
YOLO_ENABLE_WARMUP = True
YOLO_ENABLE_TORCH_COMPILE = False
ENABLE_WAKE_DETECTION = False
ENABLE_KALMAN_FILTER = True
# If False, side-camera detections/predictions are ignored by the controller.
# Set this in `config.py` to disable side-camera usage at startup.
ENABLE_SIDE_DETECTION = False

# Startup synchronization for repeatable experiments.
# When enabled, both followers keep outputting zero command until startup
# readiness conditions are met, reducing run-to-run timing drift.
SYNC_FOLLOWER_STARTUP_ENABLE = True
SYNC_FOLLOWER_STARTUP_REQUIRE_ALL_CAMERA_STREAMS = True
SYNC_FOLLOWER_STARTUP_REQUIRE_FOLLOWER_STATE = True
SYNC_FOLLOWER_STARTUP_REQUIRE_FRONT_VISUAL_LOCK = True
SYNC_FOLLOWER_STARTUP_REQUIRE_SIDE_VISUAL_LOCK = False
SYNC_FOLLOWER_STARTUP_SETTLE_SEC = 0.50
SYNC_FOLLOWER_STARTUP_TIMEOUT_SEC = 25.0
SYNC_FOLLOWER_STARTUP_PACKET_STALE_SEC = 0.50

# Kalman tracker tuning. Higher process noise makes the predictor respond
# faster to turns; lower measurement noise trusts detections more.
KF_PROC_POS_VAR = 1.0e-3
KF_PROC_VEL_VAR = 5.0e-2      # balanced: enough velocity dynamics for circular path, less than original 8e-2
KF_MEAS_OFFSET_VAR = 4.5e-2   # KF gain ≈0.18 vs EMA α=0.35 → KF passes ~half the YOLO noise for smoother steer
KF_MEAS_AREA_VAR = 13.0        # close to original 12: area must track responsively for throttle to close the gap
KF_ADAPTIVE_MOTION_GAIN = 0.8  # restored partial adaptive boost for turns
KF_ADAPTIVE_RESIDUAL_GAIN = 1.2
KF_MAX_PROCESS_SCALE = 9.0     # wider range so filter can still adapt on sharp circular turns
KF_INITIAL_VEL_BLEND = 0.08    # keep low: prevents noisy finite-diff velocity from polluting KF state
KF_MIN_DET_CONF = 0.10         # confidence floor: prevents R from blowing up on near-threshold detections
KF_CONF_R_MAX = 4.0            # max R inflation factor from low YOLO detection confidence (conf=0.25 → 4× R)

# Logging and Metrics Configuration
# ---------------------------------------------------------
# Near-miss distance threshold (pixels). If min_distance falls below this,
# it's counted as a "near-miss" event for safety analysis.
NEAR_MISS_DISTANCE_THRESHOLD_PX = 30.0

# ---------------------------------------------------------
# Leader auto-trajectory (for deterministic experiments)
# If enabled, the Python app will command the chosen leader
# boat to follow a preset trajectory at startup. This helps
# run repeatable experiments (e.g. compare with/without KF).
LEADER_AUTO_TRAJECTORY_ENABLE = True
# Which UDP TX port to send the leader command to. Default targets the left-boat TX port.
# Set this to the port Unity's `ShipUDPInterface.receivePort` (on the leader) is listening on.
LEADER_AUTO_TRAJECTORY_TX_PORT = 5075
# Initial control mode to request on the leader: "Keyboard" or "Trajectory".
# If set to "Keyboard", the leader will accept manual keyboard control.
# If set to "Trajectory", the leader will be set to follow the configured trajectory.
LEADER_INITIAL_CONTROL_MODE = "Trajectory"
# Trajectory selection: "Straight", "Circle", "Triangle", "Rectangle"
LEADER_TRAJECTORY_MODE = "Circle"
LEADER_TRAJECTORY_SPEED = 18.0 #18.0
LEADER_TRAJECTORY_SPEED_RAMP_ENABLE = True
LEADER_TRAJECTORY_ACCELERATION = 6.0
LEADER_TRAJECTORY_INITIAL_SPEED = 8.0
LEADER_TRAJECTORY_CIRCLE_RADIUS = 360.0
LEADER_TRAJECTORY_TRIANGLE_SIDE = 30.0
LEADER_TRAJECTORY_RECT_SIZE = (36.0, 22.0)
LEADER_TRAJECTORY_LOOP = True
# If true, the leader will be reset/anchored when the command is applied
LEADER_TRAJECTORY_RESET_ON_APPLY = True
# Follower throttle ramping keeps both followers from jumping instantly to
# abrupt command changes during startup or catch-up maneuvers.
FOLLOWER_THROTTLE_SPEED_RAMP_ENABLE = False
FOLLOWER_THROTTLE_RAMP_UP_RATE = 0.65
FOLLOWER_THROTTLE_RAMP_DOWN_RATE = 1.2
# Formation scale multiplier for visual reference locking.
# 1.0 keeps the originally observed spacing.
# Values > 1.0 make the commanded formation larger by targeting a smaller
# apparent boat size in the cameras.
# Empirically the followers lock onto the leader at ~60 m at startup while
# the geometric target triangle has 30 m sides.  Setting 0.5 commands each
# follower to converge to half the locked distance (desired_area = locked_area
# / scale² = 4 × locked_area → follower moves to locked_d × scale = 30 m).
FORMATION_SCALE_MULTIPLIER = 1.0  # targets 30 m from 60 m startup (comment above explains: scale=0.5 → 30 m)
# Retry leader startup command to avoid missing one-shot UDP when Unity enters
# Play mode slightly later than Python start.
# Total sends includes the first send (e.g. 5 means send immediately + 4 retries).
LEADER_STARTUP_CMD_RETRY_COUNT = 5
LEADER_STARTUP_CMD_RETRY_INTERVAL_SEC = 1.0
# Wait for the follower camera links to connect before sending the leader command.
LEADER_WAIT_FOR_FOLLOWER_CONNECTIONS = True
LEADER_CONNECTION_WAIT_TIMEOUT_SEC = 30.0
LEADER_CONNECTION_POLL_INTERVAL_SEC = 0.10
# ---------------------------------------------------------

VISION_CPU_THREADS = max(1, min(8, (os.cpu_count() or 4)))
IGNORE_TOP_RATIO = 0.25
IGNORE_BOTTOM_RATIO = 0.18

# Wake detection
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

# Tracking / prediction
TRACK_HOLD_SEC = 0.60
TRACK_REACQUIRE_BIAS = 0.35
TRACK_OFFSET_ALPHA = 0.35
TRACK_AREA_ALPHA = 0.25
# Wave false-positive gates (active only when a track is established).
# Hard-reject YOLO candidates that are too far in position or too different in
# area from the current track — wave glitter typically appears at unrelated
# positions and sizes.  Class-agnostic fallback recovers the track when YOLO
# mis-classifies the leader as a follower (class flip under waves).
TRACK_GATE_ENABLE = True
TRACK_GATE_MAX_OFFSET_DELTA = 0.45    # reject if candidate offset > this far from track  (normalized, 0–1 range)
TRACK_GATE_MAX_AREA_RATIO   = 5.0     # reject if area changes by more than this × vs last known area
TRACK_GATE_CLASS_AGNOSTIC_ENABLE = True   # when no correct-class det survives, fall back to any class in tight gate
TRACK_GATE_CLASS_AGNOSTIC_OFFSET = 0.20  # tight offset gate for the class-agnostic fallback pass
STALE_TARGET_THROTTLE_SCALE = 0.65
STALE_TARGET_STEER_SCALE = 0.85
SEARCH_FORWARD_THROTTLE = 0.24
SEARCH_STEER_GAIN = 0.85
DISABLE_SEARCH_MODE = True
VISUAL_FAR_BOOST_MAX = 0.14  # reduced from 0.22: prevents overshoot oscillation past 30 m target
VISUAL_SHRINK_BOOST_MAX = 0.08
VISUAL_FAR_BOOST_EXPONENT = 1.35
FOLLOW_FAR_MAX_THROTTLE = 0.9
# --- Leader-far tuning ---
# When the (visual) area of the leader is below this value, consider the leader "far".
# Units are image-area units (same units as YOLO / predicted areas).
# NOTE: when the formation reference is calibrated, is_far is computed using
# LEADER_FAR_AREA_SCALE * desired_front_area instead of this fixed threshold.
LEADER_FAR_AREA_THRESHOLD = 60000
# Scale factor applied to desired_front_area to derive a dynamic far-threshold.
# At formation distance (area ≈ desired_front_area), is_far = True (1.0 < 2.0).
# Only when the follower is significantly closer than target does is_far flip to False,
# capping throttle_ceiling at FOLLOW_MAX_THROTTLE and disabling the FAR boost multiplier.
LEADER_FAR_AREA_SCALE = 2.0

# ---- Kalman-filter approach-rate damper (anti-overshoot) ----
# When ENABLE_KALMAN_FILTER is True and the KF reports a positive area velocity
# (area growing = follower closing on leader), a D-term is subtracted from
# throttle proportional to the normalised approach rate, and the EMA alpha is
# boosted to make the throttle fall more quickly.  Both effects are ZERO when
# KF is OFF, so they show up cleanly in KF ON vs OFF comparisons.
#
# D-term: throttle -= clamp(approach_ratio * D_GAIN, 0, D_MAX)
#   where approach_ratio = track_area_velocity / target_opt
KF_APPROACH_THROTTLE_D_GAIN = 1.50   # throttle reduction per unit approach ratio
KF_APPROACH_THROTTLE_D_MAX  = 0.35   # maximum D-term reduction
# Alpha boost: throttle_alpha = min(ALPHA_MAX, base_alpha + approach_ratio * ALPHA_GAIN)
KF_APPROACH_ALPHA_GAIN            = 4.0   # alpha increase per unit approach ratio
KF_APPROACH_THROTTLE_ALPHA_MAX    = 0.70  # cap on EMA alpha when approaching

# Asymmetric EMA for throttle: allow throttle to fall faster than it rises.
# When the computed throttle setpoint decreases (follower entering deadzone,
# emergency stop, or D-term active), scale the EMA alpha up so the smoothed
# command tracks the setpoint promptly instead of lagging for 5–10 frames.
# This prevents EMA inertia from extending the overshoot window.
THROTTLE_DECREASE_ALPHA_SCALE   = 2.0   # multiply alpha when setpoint is falling
THROTTLE_FAST_DECREASE_ALPHA_MAX = 0.60  # hard cap on the boosted fall alpha
# When leader is far, reduce side/formation priority by this scale (0..1).
SIDE_PRIORITY_SCALE_WHEN_FAR = 0.35
# When leader is far, multiply the visual far boost by this factor.
FAR_VISUAL_FAR_BOOST_MULTIPLIER = 2.0
# When leader is far, increase pair-catchup boost by this multiplier (clamped to max).
PAIR_CATCHUP_MULTIPLIER_WHEN_FAR = 1.5
PREDICTION_HORIZON_SEC = 0.03   # short lookahead: provides turn prediction without amplifying velocity noise
# How much of the Kalman/predicted offset is blended into the steer error.
# Raised to 0.70 so the smoothed Kalman estimate dominates raw YOLO noise.
PREDICTION_OFFSET_BLEND = 0.50  # reduced from 0.70: less reliance on KF velocity prediction to prevent steer drift on long circular runs
# How much of the Kalman/predicted area is blended into throttle control.
PREDICTION_AREA_BLEND = 0.50
PREDICTION_VELOCITY_ALPHA = 0.20
PREDICTION_STALE_DECAY = 0.88
PREDICTION_MAX_OFFSET_DELTA = 0.35
PREDICTION_MAX_AREA_DELTA_RATIO = 0.45
PREDICTION_IDLE_DECAY = 0.60
PREDICTION_MIN_OFFSET_STEP = 0.012
PREDICTION_MIN_VERTICAL_STEP = 0.010
PREDICTION_MIN_AREA_RATIO_STEP = 0.045
PREDICTION_CONTROL_MIN_CONF = 0.20

# How many consecutive frames area must exceed target_max before zeroing throttle
AREA_PERSISTENCE_FRAMES = 3

# Prediction sign-consistency checks
# Minimum velocity magnitude to consider for sign check (offset units/sec)
# Minimum velocity magnitude to consider for sign check (offset units/sec)
PREDICTION_SIGN_CONSISTENCY_VEL_THRESH = 0.02
# If KF velocity sign disagrees with measured velocity and
# prediction confidence < this threshold, reject KF prediction for arrow/control.
PREDICTION_SIGN_CONSISTENCY_CONF = 0.60

# Reduce side-prediction blending when the detection method is only FOLLOWER
# (side-only detection is less reliable for forward/back motion).
SIDE_PREDICTION_METHOD_BLEND = 0.5

# Ego-motion compensation for prediction arrow stability
# Compensates camera-induced offset motion using own-boat yaw-rate/speed.
PREDICTION_EGO_COMPENSATION_ENABLE = True
# Convert own yaw-rate (deg/s) to expected image offset velocity (offset/s)
PREDICTION_EGO_YAW_RATE_GAIN = 0.0025
# Convert own speed contribution to expected image offset velocity (offset/s)
# The speed term is multiplied by current offset magnitude/sign.
PREDICTION_EGO_SPEED_GAIN = 0.015
# Clamp ego compensation to avoid over-correction.
PREDICTION_EGO_MAX_OFFSET_VEL = 0.25
# If False, side-camera follower tracks will not use predictive velocity dynamics.
# This keeps side-following more conservative when the follower motion is noisy.
PREDICTION_ENABLE_SIDE_FOLLOWER = True
# If False, the front-camera leader trajectory arrow is hidden.
# Kalman state updates still run so the controller can use prediction when enabled.
PREDICTION_ENABLE_LEADER_TRAJECTORY = False

# When side camera loses the leader bbox, allow using the predicted
# trajectory (from Kalman or velocity extrapolation) for a short window
# to continue side-following. Tune these if prediction causes false chase.
SIDE_PREDICTION_FOLLOW_ENABLE = True
SIDE_PREDICTION_MAX_LOST_SEC = 1.0 #1.5
SIDE_PREDICTION_MIN_CONF = 0.3 #0.2
# Side-camera target policy:
# - "dual": use follower for spacing when visible, while also biasing steering
#   with leader position to keep the leader inside the side-camera view
# - "leader_preferred": use leader when visible, otherwise follower fallback
# - "follower_preferred": use follower when visible, otherwise leader fallback
# - "leader_only": ignore follower boxes
# - "follower_only": ignore leader boxes
# - "best_area": choose the larger visible target
SIDE_CAMERA_TARGET_MODE = "leader_only"
# In dual mode, blend side steering toward the leader offset so the leader
# stays visible while follower spacing still drives the area target.
SIDE_DUAL_LEADER_OFFSET_BLEND = 0.35
SIDE_DUAL_LEADER_EDGE_START = 0.55
SIDE_DUAL_LEADER_EDGE_BLEND = 0.80
# Reduce side-camera steering/throttle bias when the fallback target class
# differs from the class used to lock the original side visual reference.
SIDE_REFERENCE_MISMATCH_BIAS_SCALE = 0.35

FRONT_PRIORITY_CONFIDENCE = 0.35
FRONT_PRIORITY_STALE_SCALE = 0.25
FRONT_PRIORITY_NO_FRONT_STEER_SCALE = 0.20

# Disable side-camera steer contribution entirely.  The side camera steer bias
# opposes the front-camera correction (positive feedback) for whichever follower
# is on the outside of a curve, causing hunting oscillations in both straight
# and circular trajectories.  Side camera is still used for throttle (distance
# control).  Set True to re-enable if the geometry changes.
SIDE_STEER_ENABLED = False
SIDE_TRACK_STEER_KP = 0.50
SIDE_TRACK_MAX_STEER_BIAS = 0.10
SIDE_TRACK_MAX_THROTTLE_BIAS = 0.0   # disabled: side-cam area fluctuates widely in circle, causing throttle oscillation
SIDE_TRACK_AREA_GAIN = 0.18
SIDE_STEER_DEADZONE_H = 0.05
SIDE_STALE_BIAS_SCALE = 0.72
YOLO_TRACK_STEER_GAIN = 0.92
YOLO_TRACK_THROTTLE_GAIN = 1.08
WAKE_TRACK_STEER_GAIN = 0.90
WAKE_TRACK_THROTTLE_GAIN = 0.82
WAKE_TRACK_AREA_BIAS = 0.88
FOLLOWER_TRACK_STEER_GAIN = 0.70
FOLLOWER_TRACK_THROTTLE_GAIN = 0.75
FOLLOWER_TRACK_AREA_BIAS = 0.84
FOLLOWER_MOTION_MIN_CONF = 0.10
FOLLOWER_MOTION_STEER_GAIN = 0.42
FOLLOWER_MOTION_MAX_STEER = 0.24
FOLLOWER_AREA_CATCHUP_MAX = 0.04
STALE_TRACK_STEER_GAIN = 0.80
STALE_TRACK_THROTTLE_GAIN = 0.80
VISION_FRONT_TARGET_OFFSET = 0.0
VISION_SIDE_TARGET_OFFSET = 0.0
VISION_AREA_ERROR_DEADZONE_RATIO = 0.12 #0.14
VISION_FRONT_AREA_TOLERANCE_RATIO = 0.14
VISION_SIDE_AREA_TOLERANCE_RATIO = 0.16
VISION_FRONT_AREA_GAIN = 0.72
VISION_FRONT_AREA_MIN_THROTTLE = 0.08

# When the tracked leader sits very close to the side-camera image border,
# small offset errors can cause the follower to reduce throttle to zero.
# These two values help ignore extreme side offsets for throttle decisions
# and scale the minimum forward throttle when that happens.
SIDE_EDGE_IGNORE_OFFSET = 0.90
SIDE_EDGE_THROTTLE_SCALE = 0.90
# Right follower-specific edge recovery (boosts recentering when the leader
# stays near the border in the right side camera).
RIGHT_SIDE_EDGE_RECOVERY_GAIN = 1.20
RIGHT_SIDE_EDGE_THROTTLE_FLOOR_SCALE = 0.95
RIGHT_SIDE_EDGE_RECOVERY_START = 0.62
RIGHT_SIDE_EDGE_RECOVERY_END = 0.82
RIGHT_SIDE_THROTTLE_SMOOTH_ALPHA = 0.80
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
VISION_TURN_FORMATION_STEER_BOOST = 0.0   # disabled: was amplifying steer oscillations in circular trajectories
VISION_TURN_FORMATION_THROTTLE_SCALE = 0.88
VISION_TURN_PREDICTIVE_STEER_GAIN = 0.12   # reduced from 0.95: was amplifying velocity noise as dominant steer term
VISION_TURN_PREDICTIVE_STEER_MAX = 0.05   # reduced from 0.24: P-term now handles steady-state; predictive is supplement only
VISION_TURN_PREDICTIVE_THROTTLE_GAIN = 0.14
VISION_TURN_PREDICTIVE_THROTTLE_MAX = 0.12
VISION_TURN_PREDICTIVE_SPEED_CEILING = 0.95
FOLLOWER_PAIR_AREA_BALANCE_TOLERANCE_RATIO = 0.12
FOLLOWER_PAIR_CATCHUP_GAIN = 0.0 #0.18
FOLLOWER_PAIR_CATCHUP_MAX = 0.0 #0.14

# =========================================================
# Controller params
# =========================================================
# Startup steering lock (helps Right follower launch straight before side/front
# stabilization fully settles). When enabled, Right follower steering command
# is forced to zero for the initial lock window after control starts.
STARTUP_STEER_LOCK_ENABLE = True
STARTUP_STEER_LOCK_SEC = 2.0

KV_STEER = 1.02
RIGHT_KV_STEER = 0.78  # reduced from 1.02: less aggressive steer gain for Right to damp S-twist
STEER_DEADZONE_H = 0.020    # reduced from 0.06: P-term must be active for gentle-circle steer (~0.025 error)
FINAL_STEER_DEADZONE_H = 0.012  # reduced from 0.045: must be < P-term steer so output passes the filter
STEER_SLEW_RATE_PER_SEC = 2.0   # reduced from 4.0 to cap command rate and reduce jerkiness
RIGHT_STEER_SLEW_RATE_PER_SEC = 1.2  # reduced from 2.0: slower Right steer changes damp S-twist coupling
SEARCH_MODE_STEER = 0.5
KV_THROTTLE_P = 0.00014
FOLLOW_BASE_THROTTLE = 0.40
FOLLOW_MAX_THROTTLE = 0.68  # reduced from 0.75: prevents overshoot oscillation at target
THROTTLE_SMOOTH_ALPHA = 0.40  # reduced from 0.40: slightly more EMA smoothing on throttle
RIGHT_THROTTLE_SMOOTH_ALPHA = 0.40  # more smoothing for Right: damps throttle oscillation from S-twist
# Leader-speed feedforward: at target distance, provides ~0.65 throttle to match leader's 18 m/s cruise,
# preventing the deadzone → coast → fall behind → max-throttle chase bang-bang oscillation.
LEADER_SPEED_THROTTLE_FF = 0.036

# Area thresholds (How close/far the target is based on its image area, used for various heuristics and tuning)
YOLO_AREA_OPT = 250000
YOLO_AREA_MIN = 200
YOLO_AREA_MAX = 350000
FOLLOWER_AREA_OPT = 150000
FOLLOWER_AREA_MIN = 200
FOLLOWER_AREA_MAX = 260000

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
SIDE_TRACK_STEER_SIGN_BY_BOAT = {"Left": 1.0, "Right": -1.0}

# =========================================================
# SUIMONO wave environment control (sent to Unity at startup)
# Requires WaveController.cs attached to a GameObject in the scene.
# Set WAVE_CONTROL_ENABLE = True to override the Unity inspector
# wave parameters via UDP whenever Python starts.
# When using real SUIMONO waves, MEAS_NOISE_ENABLE and
# DETECTION_DROPOUT_ENABLE can be set to False — the actual
# camera shake from the Unity physics replaces the simulation.
#
# Beaufort-anchored preset reference:
#   Preset      | waveH | turb  | lgH  | lgSc  | wSc  | flow  | tilt
#   ------------+-------+-------+------+-------+------+-------+-----
#   Calm  B0–2  | 0.10  | 0.02  | 0.05 | 0.100 | 0.20 | 0.003 | 0.05
#   Mod   B4–5  | 0.50  | 0.12  | 0.55 | 0.040 | 0.45 | 0.010 | 0.50
#   Rough B6–7  | 0.95  | 0.20  | 1.00 | 0.020 | 0.60 | 0.020 | 1.00
#   Storm B9–10 | 1.40  | 0.50  | 2.00 | 0.012 | 0.70 | 0.150 | 1.50
#   Typhoon B12 | 1.80  | 0.80  | 3.50 | 0.008 | 0.80 | 0.350 | 1.80
# =========================================================
WAVE_CONTROL_ENABLE          = False
# If True, wave/rain settings are held back until after startup sync releases
# (i.e. after all cameras connect and visual lock is established).
# Set False only if you need waves applied before the formation locks (e.g. pre-wave
# stress tests), but this WILL destabilize boats during startup at Storm/Typhoon level.
WAVE_APPLY_AFTER_STARTUP     = False
WAVE_CONTROL_PORT            = 5070       # must match WaveController.listenPort
SUIMONO_WAVE_HEIGHT          = 1.80       # visual normal-map ripple (no physics); >0.65 causes YOLO glitter
SUIMONO_TURBULENCE           = 0.80       # surface turbulence / glint intensity
# lgWaveHeight is the PHYSICAL wave geometry — it moves boats via buoyancy.
# SUIMONO's own Beaufort-12 ceiling is 3.0; values above that are beyond the
# design range and will capsize the boats.  ShipStabilizer uprightTorque must be
# raised to ≥15000 to survive these conditions:
#   1.0 = Rough (B6–7)   boats handle it fine
#   2.0 = Storm (B9–10)  boats rock heavily but survive
#   2.5 = near-Typhoon   requires uprightTorque ≥ 15000; push to 3.0 only with ≥ 18000
SUIMONO_LARGE_WAVE_HEIGHT    = 2.50       # physical wave height — near-Typhoon; capsizes above ~3.0
SUIMONO_LARGE_WAVE_SCALE     = 0.008      # spatial frequency of large waves (longer swells at typhoon scale)
SUIMONO_WAVE_SCALE           = 0.80       # small-wave detail density
SUIMONO_FLOW_SPEED           = 0.350      # surface current speed
SUIMONO_CAMERA_TILT_STRENGTH = 1.80       # camera pitch/roll from wave surface normal
