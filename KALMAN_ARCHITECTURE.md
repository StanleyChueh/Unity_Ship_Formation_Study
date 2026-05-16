# Kalman Filter System Architecture

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     VISION PROCESSING LOOP                       │
│                    (cv_processing_thread)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌──────────────────┐
                    │ YOLO Detection   │
                    │ Wake Detection   │
                    │ Sensor Fusion    │
                    └──────────────────┘
                              ↓
                   (x_meas, y_meas, area_meas)
                              ↓
        ┌─────────────────────────────────────────┐
        │   update_track_prediction() function    │
        │        (in vision.py)                   │
        └─────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────┐
        │        KALMAN FILTER STEP                │
        │  (NEW - Assets/usv/kalman.py)           │
        ├─────────────────────────────────────────┤
        │  1. Predict (time update):              │
        │     x_prior = F * x_posterior           │
        │     P_prior = F*P_posterior*F' + Q      │
        │                                          │
        │  2. Update (measurement update):        │
        │     K = P_prior*H'/(H*P_prior*H'+R)    │
        │     x_posterior = x_prior + K(z-H*x)   │
        │     P_posterior = (I-K*H)*P_prior       │
        │                                          │
        │  Output: Smoothed & predicted state     │
        │  [offset, offset_vel, area, area_vel]  │
        └─────────────────────────────────────────┘
                              ↓
        (predicted_offset, predicted_area, 
         prediction_confidence)
                              ↓
        ┌─────────────────────────────────────────┐
        │    State Storage                         │
        │    (vision_states dictionary)            │
        │    - For each stream                     │
        │    - Shared with control loop            │
        └─────────────────────────────────────────┘
                              ↓
                    ┌──────────────────┐
                    │  CONTROL LOOP    │
                    │ (control.py)     │
                    │ process_boat_    │
                    │ vision_based()   │
                    └──────────────────┘
                              ↓
        Read: predicted_offset, predicted_area,
              prediction_confidence
                              ↓
        Compute: steering_command, throttle_command
                              ↓
                    ┌──────────────────┐
                    │  Send Commands   │
                    │  to Boat         │
                    │  (UDP packets)   │
                    └──────────────────┘
```

---

## State Management

### Per-Stream State Dictionary

```python
vision_states[stream_name] = {
    # Traditional fields (unchanged)
    "target_detected": bool,
    "target_center_offset": float,       # -1 to +1
    "target_area": float,                # pixels²
    "last_known_offset": float,
    "last_known_area": float,
    
    # Velocity-based prediction (still populated for compatibility)
    "track_offset_velocity": float,
    "track_area_velocity": float,
    
    # Outputs used by control loop
    "predicted_offset": float,           # Now from Kalman filter
    "predicted_area": float,             # Now from Kalman filter
    "prediction_confidence": float,      # Adaptive confidence
    
    # NEW: Kalman filter instance
    "kf": KalmanFilter,                  # Lazily initialized
}
```

---

## Kalman Filter State & Matrices

### State Vector
```
x = [
  offset,           # Target horizontal position (-1 to +1)
  offset_velocity,  # How fast target moves horizontally (per second)
  area,             # Target size (pixels)
  area_velocity,    # How fast target grows/shrinks (pixels/sec)
]
```

### Measurement Vector
```
z = [
  offset_measured,    # From YOLO/Wake detection
  area_measured,      # From YOLO/Wake detection
]
(Note: We don't measure velocity directly)
```

### Transition Matrix (Constant Velocity Model)
```
F = [
  [1,  dt,  0,   0],    # offset(t+1) = offset(t) + dt*vel(t)
  [0,  1,   0,   0],    # velocity unchanged
  [0,  0,   1,  dt],    # area(t+1) = area(t) + dt*vel(t)
  [0,  0,   0,   1],    # area_velocity unchanged
]
```

### Measurement Matrix (We observe offset & area)
```
H = [
  [1,  0,  0,  0],      # We measure offset
  [0,  0,  1,  0],      # We measure area (not velocities)
]
```

### Process Noise Covariance
```
Q = diag([proc_pos_var, proc_vel_var, proc_pos_var, proc_vel_var]) * dt

Default:
  proc_pos_var = 1e-3   (position can drift slowly)
  proc_vel_var = 1e-2   (velocity can change)
```

### Measurement Noise Covariance
```
R = diag([meas_offset_var, meas_area_var])

Default:
  meas_offset_var = 1e-2   (offset measurement noise)
  meas_area_var = 10.0     (area measurement noise)
```

---

## Execution Timeline (Single Frame)

```
Time T (seconds):
│
├─ T₀: Frame arrives at vision processor
│   └─ Latest detected offset = 0.05, area = 120
│
├─ T₀ + 5ms: Kalman predict()
│   ├─ dt = 0.005 seconds
│   ├─ x_prior = F * x_posterior (extrapolate forward)
│   └─ P_prior = F*P*F' + Q (grow uncertainty)
│
├─ T₀ + 7ms: Kalman update()
│   ├─ z = [0.05, 120] (new measurement)
│   ├─ K = compute Kalman gain (balance measurement vs prior)
│   ├─ x_posterior = x_prior + K*(z - H*x_prior)
│   │   (fuse measurement with prediction)
│   └─ P_posterior = (I - K*H)*P_prior (reduce uncertainty)
│
├─ T₀ + 8ms: Extract state for control
│   └─ predicted_offset = x_posterior[0]
│      predicted_area = x_posterior[2]
│      prediction_confidence = f(motion_score, cadence)
│
├─ T₀ + 10ms: Control loop reads prediction
│   ├─ steer = KV_STEER * (predicted_offset - desired_offset)
│   └─ throttle = f(area_error, predicted_area)
│
└─ T₀ + 15ms: Commands sent to boat
    └─ UDP: {"throttle": 0.6, "steer": -0.2}
```

---

## Kalman Filter Gain Dynamics

### High Measurement Noise → Low Gain
```
If R (measurement noise) is high:
  K ≈ 0
  x_new ≈ x_prior    (trust prediction, not measurement)
  → Filter relies on history, smoother but slower to adapt
```

### Low Measurement Noise → High Gain
```
If R (measurement noise) is low:
  K ≈ I (identity)
  x_new ≈ z           (trust measurement over prediction)
  → Filter adapts quickly to measurements, noisier
```

### Low Process Noise → Velocity Doesn't Change Much
```
If Q (process noise) is low:
  P grows slowly
  Velocity stays constant
  → Smooth but may lag on turns
```

### High Process Noise → Velocity Can Change Quickly
```
If Q (process noise) is high:
  P grows fast
  Velocity can jump to new values
  → Responsive but may oscillate
```

---

## Turn Detection & Response

### Before (Velocity-Based)
```
Frame 1: offset = 0.0 (centered)
  → velocity = 0.0 (no motion)
  
Frame 2 (sharp left turn): offset = -0.3 (far left)
  → velocity = -0.3 (sudden large change)
  → But extrapolation uses OLD velocity still...
  
Frame 3: offset = -0.5
  → velocity now estimates at -0.2 (still catching up)
  → Steering lags the turn
```

### After (Kalman-Based)
```
Frame 1: offset = 0.0
  Kalman:
    x = [0.0, 0.0, area, 0.0]
    P = [0.05, 0.5, ...]
  
Frame 2 (sharp left turn): offset = -0.3
  Predict: x_prior = [0.0, 0.0, area, 0.0]  (no change expected)
  
  Update: 
    innovation = -0.3 - 0.0 = -0.3 (big surprise!)
    K = high (we trust measurement)
    x = x_prior + K*innovation
    x ≈ [-0.15, -0.8, area, ...]  (velocity jumps negative!)
  
Frame 3:
  Predict: uses velocity = -0.8
    x_prior ≈ [-0.25, -0.8, ...]  (smoothly extrapolates)
  
  Steering responds much faster to the new direction!
```

---

## Configuration Tuning Space

```
                    HIGH RESPONSIVENESS
                            ↑
                            │
                     Oscillates ┌───────────────────┐
                       ├────────┤ proc_vel_var=0.03 │
                       │        │ meas_*_var=small  │
  LOW MEASUREMENT ────┤        └───────────────────┘
  NOISE              │
  (trust measure)    │
                     │
                     ├────────┌───────────────────┐
                     │        │ proc_vel_var=0.01 │ ← Sweet spot
                     │        │ meas_*_var=medium │
                     │        └───────────────────┘
                     │
                     │        ┌───────────────────┐
                     ├────────┤ proc_vel_var=0.01 │
                     │        │ meas_*_var=large  │
  HIGH MEASUREMENT   │        └───────────────────┘
  NOISE              │
  (distrust measure) │
                            │
                            ↓
                    LOW RESPONSIVENESS (SMOOTH)
```

---

## Integration Checklist

- [x] Created `kalman.py` with KalmanFilter class
- [x] Added "kf" slot to state.py
- [x] Imported KalmanFilter in vision.py
- [x] Integrated predict() and update() calls into `update_track_prediction()`
- [x] Added graceful fallback if Kalman fails
- [x] Tested Kalman with simple motion scenario
- [x] Documented architecture and tuning
- [x] Verified backward compatibility
- [x] All old fields still populated

---

## Next: What Happens on Your Next Run

1. **Vision processor starts** → Creates KalmanFilter instances (lazy, per-stream)
2. **First detection arrives** → Kalman initializes with measurement
3. **Subsequent frames** → Kalman predict + update cycle runs
4. **Control loop reads** → Gets smoothed predictions automatically
5. **Followers track** → Better turn following with less jitter

No code changes needed. Just run and test!
