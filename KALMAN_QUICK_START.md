# Kalman Filter Integration for USV Follower Turn Tracking

## Executive Summary

A **linear Kalman filter** has been integrated into the USV formation control system to **improve turn tracking** for follower boats. The filter processes vision-based offset (horizontal centering) and area (distance proxy) measurements to predict smoother target positions during leader maneuvers.

## What's New

### Files Added
- **`Assets/usv/kalman.py`** — Lightweight linear Kalman filter (4-state: position, velocity for offset and area)

### Files Modified
- **`Assets/usv/state.py`** — Added `"kf": None` slot to track state for per-stream filter instance
- **`Assets/usv/vision.py`** — Integrated Kalman predict/update into `update_track_prediction()`, imported `KalmanFilter`

### Documentation Added
- **`KALMAN_FILTER_GUIDE.md`** — Overview, architecture, tuning principles, advanced options
- **`KALMAN_TUNING_GUIDE.md`** — Practical tuning scenarios and diagnostics
- **`KALMAN_QUICK_START.md`** (this file) — Quick reference

---

## Why Kalman Filter?

### The Problem
Current **velocity-based prediction** extrapolates linearly:
$$\text{position}_{\text{future}} = \text{position}_{\text{current}} + \text{velocity} \times \Delta t$$

On sharp leader turns:
- Velocity estimate lags new direction
- Follower steering stays tuned to old offset
- Visual tracking misses the turn apex
- Followers end up *inside* or *outside* the turn

### The Solution
**Kalman filter** maintains a belief about state (position + velocity) and continuously updates it with measurements:

1. **Predict**: Extrapolate state forward using velocity estimate
2. **Update**: Fuse new measurement with prior prediction
3. **Smooth**: Reduce noise and outlier impact
4. **Adapt**: Automatically adjust velocity when direction changes

**Result:** Smoother, faster tracking during turns without excessive jitter.

---

## State Vector

The Kalman filter tracks 4 variables per camera stream:

$$\mathbf{x} = \begin{bmatrix} \text{offset} \\ \text{offset\_vel} \\ \text{area} \\ \text{area\_vel} \end{bmatrix}$$

Where:
- **offset**: Horizontal position of target in frame (-1 = left, 0 = center, +1 = right)
- **offset_vel**: How fast the target is moving left/right
- **area**: Target size in pixels (proxy for distance)
- **area_vel**: How fast the target is growing/shrinking

---

## How It Integrates

### Zero Configuration Required
The filter is **enabled by default** and runs inside the vision processing loop:

```
Vision Frame → YOLO Detection → Kalman Update → Predicted Offset/Area
                                      ↓
                                Control Loop
                                      ↓
                            Steering + Throttle Commands
```

### Backward Compatible
- If Kalman fails, system falls back to velocity-based prediction
- Old fields (`track_offset_velocity`, `track_area_velocity`) still populated
- Control gains in `control.py` unchanged

### Transparent to Control Logic
Control law reads the same keys as before:
- `front_predicted_offset` → steering bias
- `front_predicted_area` → throttle decision
- `front_prediction_confidence` → weighting

---

## Testing the Integration

### Verify Kalman is Working
Check logs during a turn:
```bash
# Look for "Kalman" in console output (or run unit test)
python3 << 'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("kalman", "Assets/usv/kalman.py")
kalman_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kalman_module)
KalmanFilter = kalman_module.KalmanFilter

kf = KalmanFilter()
kf.update(0.1, 100.0)
kf.predict(0.1)
kf.update(0.15, 95.0)
print(kf.state())  # Should show non-zero velocity
EOF
```

### Field Test
1. **Straight-line chase**: Should work as before (Kalman doesn't hurt straight tracking)
2. **90° turn at constant speed**: Follower should smoothly track new heading
3. **S-curve maneuver**: Follower should adapt velocity without oscillating
4. **Rapid direction change**: Follower should catch up faster than before

---

## Quick Tuning Checklist

### ❌ Followers Lag on Turns
→ Increase `proc_vel_var` in `kalman.py`
→ Decrease `meas_offset_var` and `meas_area_var`

### ❌ Followers Oscillate
→ Decrease `proc_vel_var`
→ Increase `meas_offset_var` and `meas_area_var`

### ✅ Happy Medium
→ See `KALMAN_TUNING_GUIDE.md` for scenario-specific values

---

## Implementation Details

### Kalman Filter Equations

**State prediction** (prior):
$$\mathbf{x}_{k|k-1} = \mathbf{F} \mathbf{x}_{k-1|k-1}$$

**Measurement update** (posterior):
$$\mathbf{x}_{k|k} = \mathbf{x}_{k|k-1} + \mathbf{K}_k (\mathbf{z}_k - \mathbf{H} \mathbf{x}_{k|k-1})$$

Where:
- $\mathbf{F}$ = state transition (constant-velocity model)
- $\mathbf{H}$ = measurement matrix (offset and area only, no velocity measurements)
- $\mathbf{K}_k$ = Kalman gain (computed from noise covariances)
- $\mathbf{z}_k$ = measurement (offset, area from YOLO/Wake detection)

### Noise Tuning Parameters

| Parameter | Meaning | Tuning |
|-----------|---------|--------|
| `proc_pos_var` | Position can wander | Increase if filter "drifts" |
| `proc_vel_var` | Velocity can change | Increase for responsive turns |
| `meas_offset_var` | Offset measurement noise | Decrease for cleaner signals |
| `meas_area_var` | Area measurement noise | Decrease for stable throttle |

---

## Next Steps (Optional Enhancements)

### 1. **Extended Kalman Filter (EKF)**
If boat turning radius matters, add nonlinear motion model:
```python
class EKalmanFilter(KalmanFilter):
    def predict(self, dt, steering_angle):
        # Use boat kinematics instead of constant velocity
```

### 2. **Unscented Kalman Filter (UKF)**
If nonlinear effects are strong and you have computational budget:
```python
class UnscentedKalmanFilter:
    # Deterministic sampling of distribution
    # More robust to nonlinearities than EKF
```

### 3. **Interacting Multiple Model (IMM)**
If leader has distinct modes (accelerating, cruising, hard turn):
```python
class IMMFilter:
    # Run 3 Kalman filters with different models
    # Blend outputs based on likelihood
```

### 4. **Adaptive Noise**
Auto-tune noise based on innovation (residual):
```python
if large_innovation:
    R *= 1.5  # don't trust measurements when surprising
```

---

## Files & Locations

```
Assets/usv/
├── kalman.py                    ← NEW: Kalman filter class
├── vision.py                    ← MODIFIED: integrate KF
├── state.py                     ← MODIFIED: add "kf" slot
└── control.py                   ← (unchanged, uses predicted_offset/area)

Root/
├── KALMAN_FILTER_GUIDE.md       ← Architecture & theory
├── KALMAN_TUNING_GUIDE.md       ← Practical tuning
└── KALMAN_QUICK_START.md        ← This file
```

---

## Troubleshooting

### Issue: Kalman not improving turn tracking
**Check:**
1. Ensure vision detections are *consistent* (not dropping frames)
2. Kalman only helps if measurements are noisy or non-uniform
3. Try aggressive tuning: `proc_vel_var = 0.05`

### Issue: Followers now oscillate
**Check:**
1. Measurement noise too low; increase `meas_*_var`
2. Or lower `proc_vel_var` to limit velocity changes

### Issue: No noticeable change
**Check:**
1. Run unit test to confirm Kalman initializes
2. Add debug logging to `update_track_prediction()` to see Kalman state
3. Confirm control gains haven't been reduced (unrelated issue)

---

## References

- **Kalman, R. E.** (1960). "A new approach to linear filtering and prediction problems"
- **Bar-Shalom, Y., Li, X.-R., & Kirubarajan, T.** (2001). *Estimation with Applications to Tracking and Navigation*
- **Simon, D.** (2006). *Optimal State Estimation: Kalman, H-infinity, and Nonlinear Approaches*

---

## Support

For detailed tuning, see:
- `KALMAN_TUNING_GUIDE.md` — Step-by-step parameter adjustment
- `KALMAN_FILTER_GUIDE.md` — Architecture and advanced options

Questions? Check the logs for Kalman state and innovation magnitude.

---

**Integration Date:** May 2026  
**Status:** ✅ Tested and backward-compatible
