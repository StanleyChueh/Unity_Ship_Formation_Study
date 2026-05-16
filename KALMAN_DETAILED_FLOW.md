# Kalman Filter Flow: Camera → Predict → Update → Control → Boat

## COMPLETE DATA FLOW WITH EXAMPLES

```
┌────────────────────────────────────────────────────────────────────────┐
│                         CAMERA FRAME ARRIVES                           │
│                        (e.g., at 10 FPS)                              │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ↓
        ┌─────────────────────────────────────────┐
        │  YOLO DETECTION + WAKE DETECTION        │
        │  (Assets/usv/vision.py line ~600)       │
        └─────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            (Boat found in frame)        (No boat found)
                    │                               │
                    ↓                               ↓
        ┌──────────────────────┐        ┌──────────────────────┐
        │ center_offset = 0.15 │        │ Hold last detection  │
        │ area = 110           │        │ or return empty      │
        │ (normalized coords)  │        └──────────────────────┘
        └──────────────────────┘


    ┌────────────────────────────────────────────────────────────────────┐
    │              update_track_prediction() function                    │
    │            (Assets/usv/vision.py, line ~320-425)                 │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ↓                               ↓
        ┌────────────────────────┐      ┌────────────────────────┐
        │ Is Kalman initialized? │      │ First frame?           │
        │ (kf in state["kf"])    │      │ (kf is None)           │
        └────────────────────────┘      └────────────────────────┘
           YES ↓         NO ↓                      ↓
              │          │              Create new KalmanFilter()
              │          │                        │
              ↓          ↓                        ↓
        ┌────────────────────────────────────────────┐
        │          TIME DELTA CALCULATION            │
        │  dt = current_time - prev_time             │
        │  dt = ~0.1 seconds (typical 10 FPS)       │
        └────────────────────────────────────────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     KALMAN PREDICT STEP                    │
        │     kf.predict(dt)                         │
        │  (Assets/usv/kalman.py line ~34-50)       │
        └────────────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
        │  State transition matrix F:       │
        │  ┌─────────────────────────────┐  │
        │  │ [1,  dt,  0,  0]   ← offset │  │
        │  │ [0,  1,   0,  0]   ← velocity│  │
        │  │ [0,  0,  1,  dt]   ← area   │  │
        │  │ [0,  0,  0,  1]    ← velocity│  │
        │  └─────────────────────────────┘  │
        │                                   │
        │  x_prior = F × x_posterior        │
        │  P_prior = F × P × F' + Q         │
        │                                   │
        │  Q = process noise                │
        │    = diag([1e-3, 1e-2, ...]) × dt│
        └─────────────────────────────────────────────┐
                          │                           │
        ┌─────────────────┴─────────────────┐        │
        │  Example: predict 100ms forward   │        │
        │  Old state:                       │        │
        │    offset = 0.0                   │        │
        │    offset_vel = 0.0               │        │
        │    area = 100                     │        │
        │    area_vel = 0.0                 │        │
        │                                   │        │
        │  After predict():                 │        │
        │    x_prior = F × [0, 0, 100, 0]  │        │
        │            = [0, 0, 100, 0]      │        │
        │            (no change expected)   │        │
        └───────────────────────────────────┴────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     KALMAN UPDATE STEP                     │
        │     kf.update(center_offset, area)         │
        │  (Assets/usv/kalman.py line ~52-67)       │
        └────────────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────────────┐
        │                                           │
        │  Measurement matrix H:                    │
        │  ┌─────────────────────────────────────┐  │
        │  │ [1, 0, 0, 0]  ← measure offset     │  │
        │  │ [0, 0, 1, 0]  ← measure area       │  │
        │  │            (not velocities!)       │  │
        │  └─────────────────────────────────────┘  │
        │                                           │
        │  z = [center_offset, area]                │
        │    = [0.15, 110]  (current measurement)   │
        │                                           │
        │  innovation = z - H × x_prior             │
        │            = [0.15, 110] - [0, 100]       │
        │            = [0.15, 10]                   │
        │            (difference from prediction)   │
        │                                           │
        │  Kalman Gain K = P_prior × H' / (H × P × H' + R)
        │                = how much to trust meas   │
        │  R = measurement noise                    │
        │    = diag([0.01, 10.0])                   │
        │                                           │
        │  x_posterior = x_prior + K × innovation   │
        │  P_posterior = (I - K×H) × P_prior        │
        └───────────────────────────────────────────┘
                          │
        ┌─────────────────┴──────────────────┐
        │  Example: after update()           │
        │  Measurement: (0.15, 110)          │
        │  Prediction was: (0, 100)          │
        │  Innovation: (0.15, 10)            │
        │                                    │
        │  Kalman gain K makes state jump:   │
        │    offset ≈ 0.08 (avg of 0 and 0.15)
        │    offset_vel ≈ 0.8 (detected motion!)
        │    area ≈ 105 (avg of 100 and 110)
        │    area_vel ≈ 10 (detected growth)
        │                                    │
        │  NEW STATE:                        │
        │    x = [0.08, 0.8, 105, 10]       │
        └────────────────────────────────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     EXTRACT PREDICTIONS FOR CONTROL        │
        │     sx = kf.state()                        │
        │  (Assets/usv/vision.py line ~378-380)     │
        └────────────────────────────────────────────┘
                          │
        ┌─────────────────┴──────────────────────┐
        │  Extract from Kalman state vector:     │
        │  sx[0] = predicted_offset = 0.08       │
        │  sx[1] = offset_vel = 0.8              │
        │  sx[2] = predicted_area = 105          │
        │  sx[3] = area_vel = 10                 │
        │                                        │
        │  Calculate confidence:                 │
        │  confidence = motion_score × cadence   │
        │            = 0.95 × 0.9                │
        │            = 0.855  (high trust)       │
        └────────────────────────────────────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     STORE IN SHARED STATE DICT             │
        │  (Assets/usv/state.py)                     │
        │                                            │
        │  vision_states[stream_name] = {            │
        │    "predicted_offset": 0.08,               │
        │    "predicted_area": 105,                  │
        │    "prediction_confidence": 0.855,         │
        │    "kf": <KalmanFilter instance>,          │
        │    ...                                     │
        │  }                                         │
        └────────────────────────────────────────────┘
                          │
                          ↓
    ┌────────────────────────────────────────────────────────────────────┐
    │                  CONTROL LOOP READS                                │
    │            process_boat_vision_based()                             │
    │         (Assets/usv/control.py line ~180-200)                     │
    └────────────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┴──────────────────┐
        │  Fetch predictions:                │
        │  front_predicted_offset = 0.08     │
        │  front_predicted_area = 105        │
        │  front_prediction_confidence = 0.86 │
        │                                    │
        │  (Same keys as before - NO CHANGE) │
        │                                    │
        │  Blend with measured values:       │
        │  effective_offset =                │
        │    blend(offset, predicted_offset, │
        │           confidence)              │
        │  = 0.0 × (1-0.86) + 0.08 × 0.86   │
        │  = 0.069  (mostly prediction)      │
        └────────────────────────────────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     COMPUTE STEERING COMMAND               │
        │  (Assets/usv/control.py line ~290)        │
        │                                            │
        │  steer_error = effective_offset - desired │
        │             = 0.069 - 0.0                 │
        │             = 0.069                       │
        │                                            │
        │  steer = KV_STEER * steer_error * gain    │
        │        = 0.5 * 0.069 * 1.0                │
        │        = 0.0345                           │
        │  (slight right steer command)             │
        └────────────────────────────────────────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     COMPUTE THROTTLE COMMAND               │
        │  (Assets/usv/control.py line ~350)        │
        │                                            │
        │  area_error = desired_area - predicted_ar │
        │            = 120 - 105                    │
        │            = 15                           │
        │  (boat too far away)                      │
        │                                            │
        │  throttle = compute_area_gain * error     │
        │           = 0.8 * 0.125  (normalized)     │
        │           = 0.1 (speed up)                │
        └────────────────────────────────────────────┘
                          │
                          ↓
        ┌────────────────────────────────────────────┐
        │     SEND COMMANDS TO BOAT                  │
        │  (Assets/usv/control.py line ~460)        │
        │                                            │
        │  UDP Message:                              │
        │  {                                         │
        │    "throttle": 0.1,                        │
        │    "steer": 0.0345                         │
        │  }                                         │
        └────────────────────────────────────────────┘
                          │
                          ↓
                  ┌───────────────────┐
                  │   BOAT RESPONDS   │
                  │                   │
                  │ ✓ Steers 0.0345   │
                  │ ✓ Throttles 0.1   │
                  │                   │
                  └───────────────────┘


    ┌────────────────────────────────────────────────────────────────────┐
    │                    NEXT FRAME ARRIVES (~100ms)                     │
    │                   (Loop repeats from top)                          │
    └────────────────────────────────────────────────────────────────────┘
```

---

## SPECIFIC TURN EXAMPLE

### Scenario: Leader makes sharp LEFT turn

```
FRAME-BY-FRAME KALMAN BEHAVIOR:

Frame 0: STRAIGHT MOVING
  Measurement: offset = 0.0, area = 100
  Kalman State:
    offset = 0.0, offset_vel = 0.0
    area = 100, area_vel = 0.0
  Prediction: offset_pred = 0.0, area_pred = 100
  Control Output: steer = 0.0, throttle = 0.5

─────────────────────────────────────────

Frame 1: LEADER TURNS LEFT (SHARP!)
  Measurement: offset = -0.25, area = 98
  
  Kalman Predict step (before seeing measurement):
    x_prior = F × x_old
    = [0, 0, 100, 0]  (expects no motion based on velocity=0)
    P_prior grows (uncertainty increases)
  
  Kalman Update step (sees measurement):
    innovation = [-0.25, 98] - [0, 100]
               = [-0.25, -2]  (SURPRISE!)
    
    Kalman gain K becomes HIGH (this innovation is unexpected!)
    x_posterior = x_prior + K × innovation
    
    NEW STATE:
      offset ≈ -0.125 (halfway between prediction 0 and meas -0.25)
      offset_vel ≈ -1.25 (big jump detected!)
      area ≈ 99
      area_vel ≈ -2
  
  Prediction: offset_pred = -0.125, area_pred = 99
  Control Output: steer = -0.063, throttle = 0.45
  
  → ✓ Follower IMMEDIATELY detects turn and steers left

─────────────────────────────────────────

Frame 2: LEADER CONTINUES LEFT
  Measurement: offset = -0.4, area = 95
  
  Kalman Predict step:
    x_prior = F × x_old
    offset_prior = -0.125 + (-1.25 × 0.1)
                 = -0.125 - 0.125
                 = -0.25  (smooth prediction using velocity!)
    area_prior = 99 + (-2 × 0.1) = 98
    P_prior grows slightly
  
  Kalman Update step:
    innovation = [-0.4, 95] - [-0.25, 98]
               = [-0.15, -3]  (smaller innovation now)
    
    Kalman gain K is now LOWER (innovation is expected)
    x_posterior = x_prior + K × innovation
    
    NEW STATE:
      offset ≈ -0.33 (close to measurement -0.4)
      offset_vel ≈ -1.0 (velocity stabilizes)
      area ≈ 96
      area_vel ≈ -2
  
  Prediction: offset_pred = -0.33, area_pred = 96
  Control Output: steer = -0.165, throttle = 0.4
  
  → ✓ Follower smoothly follows the turn, velocity predicted correctly

─────────────────────────────────────────

Frame 3: LEADER COMPLETING TURN
  Measurement: offset = -0.5, area = 92
  
  Kalman Predict step:
    offset_prior = -0.33 + (-1.0 × 0.1)
                 = -0.33 - 0.1
                 = -0.43  (smooth!)
    area_prior = 96 + (-2 × 0.1) = 94
  
  Kalman Update step:
    innovation = [-0.5, 92] - [-0.43, 94]
               = [-0.07, -2]  (small offset surprise)
    
    x_posterior = x_prior + K × innovation
    offset ≈ -0.45 (fine adjustment)
    offset_vel ≈ -0.9 (velocity settling)
    area ≈ 93
    area_vel ≈ -2
  
  Prediction: offset_pred = -0.45, area_pred = 93
  Control Output: steer = -0.225, throttle = 0.35
  
  → ✓ Follower now tightly following the leader

```

---

## COMPARISON: WITHOUT KALMAN

```
Same scenario, using OLD velocity method:

Frame 1: LEADER TURNS LEFT
  Measurement: offset = -0.25
  velocity = (-0.25 - 0) / 0.1 = -2.5
  prediction = -0.25 + (-2.5 × 0.1) = -0.5
  Control: steer = -0.25
  → OVERSTEER! (predicted too far)

Frame 2:
  Measurement: offset = -0.4
  velocity = (-0.4 - (-0.25)) / 0.1 = -1.5
  prediction = -0.4 + (-1.5 × 0.1) = -0.55
  Control: steer = -0.275
  → STILL OVERSHOOTING

Frame 3:
  Measurement: offset = -0.5
  velocity = (-0.5 - (-0.4)) / 0.1 = -1.0
  prediction = -0.5 + (-1.0 × 0.1) = -0.6
  Control: steer = -0.3
  → STILL LAGGING

Result: Raw velocity creates jerky, overreactive steering!
```

---

## KEY INSIGHT

**Without Kalman:**
```
velocity = (current - previous) / dt    ← Noisy, jumpy
```

**With Kalman:**
```
velocity = internal state maintained & filtered
           updates based on measurement surprise
           smoothly adapts to new direction
```

The Kalman filter's **gain K** is the magic:
- High K when innovation is unexpected → trust measurement
- Low K when innovation is expected → trust prediction
- This automatic balance creates smooth, responsive tracking!
