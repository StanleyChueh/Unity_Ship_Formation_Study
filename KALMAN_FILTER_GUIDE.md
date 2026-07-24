# Kalman Filter Integration for Follower Turn Tracking

## Overview

A **linear Kalman filter** has been integrated into the USV follower tracking system to improve tracking during leader turns. The filter operates on a **4-state model** to predict and smooth both **offset** (horizontal centering) and **area** (distance proxy) measurements.

## What Was Changed

### 1. New File: `Assets/usv/kalman.py`
A lightweight **KalmanFilter** class that:
- **State vector**: `[offset, offset_velocity, area, area_velocity]`
- **Measurements**: `[offset, area]`
- **Tunable noise parameters**:
  - `proc_pos_var = 1e-3` (process noise for position)
  - `proc_vel_var = 1e-2` (process noise for velocity)
  - `meas_offset_var = 1e-2` (measurement noise for offset)
  - `meas_area_var = 10.0` (measurement noise for area)

### 2. Updated: `Assets/usv/state.py`
- Added `"kf": None` to track state dict to hold a per-stream Kalman filter instance.

### 3. Updated: `Assets/usv/vision.py`
- Imported `KalmanFilter` from new `kalman` module.
- Modified `update_track_prediction()` to:
  - **Predict** forward one timestep using the Kalman filter.
  - **Update** with measured offset and area to fuse measurement with prior belief.
  - **Smooth** predictions to reduce jitter during turns.
  - Fall back gracefully if Kalman initialization fails.
  - Maintain backward compatibility with old velocity-based predictions.

## How It Improves Turn Tracking

### Before (Pure Velocity-Based)
```
Measurement → estimate velocity → extrapolate forward by PREDICTION_HORIZON_SEC
Problem: On sharp turns, velocity estimates lag and can't predict the new direction quickly.
```

### After (Kalman Filter)
```
Measurement → Kalman update (fuse with prior) → Kalman predict (using estimated velocity)
Benefit: 
  • Velocity is estimated from history within the filter state.
  • Measurement noise is handled; outliers dampen velocity estimates less abruptly.
  • Natural exponential forgetting: older measurements fade due to process noise.
  • Covariance tracks uncertainty; confidence automatically decreases in stale conditions.
```

## Tuning Guide

### For Better Turn Responsiveness (Faster Tracking)
Increase process noise (allow faster velocity changes):
```python
# In kalman.py __init__
self.proc_vel_var = 0.05   # was 1e-2 → allow bigger velocity jumps
```

### For Smoother, Less Jittery Tracking
Decrease measurement noise (trust measurements more):
```python
# In kalman.py __init__
self.meas_offset_var = 0.005  # was 1e-2 → trust offset more
self.meas_area_var = 5.0      # was 10.0  → trust area more
```

### For Slower, More Conservative Predictions
Increase measurement noise (trust measurements less):
```python
self.meas_offset_var = 0.05
self.meas_area_var = 50.0
```

### Initial Covariance (How Much Initial Uncertainty)
Modify the `initialize()` method:
```python
self.P = np.diag([0.05, 0.5, max(10.0, area * 0.3), 1.0])
#                 ↑     ↑    ↑                         ↑
#              offset vel  area_vel_uncertainty    area_uncertainty
# Higher = less confident → filter converges slower but is more robust.
```

## Integration with Control Loop

The Kalman filter runs **passively** inside `update_track_prediction()`:
1. When a detection occurs, `kalman.py` is updated with the measurement.
2. The predicted state is extracted and used for:
   - `predicted_offset` → steering bias in `control.py`
   - `predicted_area` → throttle decision in `control.py`
   - `prediction_confidence` → weighting of blending

The existing control logic in `control.py` remains **unchanged**; it still uses the same keys:
- `front_predicted_offset`
- `front_predicted_area`
- `front_prediction_confidence`

## When Kalman Filter Helps Most

✅ **Sharp leader turns**: Velocity remains smoothly estimated; filter predicts the new direction better than extrapolating old velocity.

✅ **Noisy camera frames**: Measurement fusion naturally reduces impact of occasional outliers.

✅ **Follower needs to catch up**: Covariance tracking means predictions are confident when measurements are consistent, allowing aggressive throttle when confidence is high.

❌ **Not critical for**: Straight-line chasing (simple velocity extrapolation works fine).

## Advanced Options (Future Enhancements)

### Extended Kalman Filter (EKF)
If nonlinear dynamics matter (e.g., boat turning radius):
- Use a nonlinear motion model: `x[t+1] = f(x[t], u[t])`
- Linearize at operating point → EKF

### Unscented Kalman Filter (UKF)
If higher-order nonlinearities exist:
- Deterministic sampling of state distribution
- Often smoother than EKF; more robust

### Multiple Model Filter (IMM)
If leader has distinct modes (accelerating, turning, cruising):
- Run 3 Kalman filters with different dynamics models
- Blend outputs based on likelihood
- Detect mode changes earlier

### Adaptive Noise
Auto-tune measurement noise based on innovation (residual):
```python
innovation = meas - H @ x_prior
if large_innovation:
    R *= 1.5  # less trust in measurements when unexpected
```

## Testing & Validation

1. **Manual observation**: Run the formation with leader making a sharp turn. Check if follower smoothly predicts the new heading.

2. **Logging**: Add to `control.py` return dict:
   ```python
   "kalman_pred_offset": front_predicted_offset,
   "kalman_pred_confidence": front_prediction_confidence,
   ```
   Plot over time to visualize smoothing.

3. **Parameter sweep**: Test different `proc_vel_var` and `meas_offset_var` values on a recorded turn scenario.

## Backward Compatibility

✅ If Kalman fails to initialize, the code falls back to velocity-based prediction.
✅ Old velocity fields (`track_offset_velocity`, `track_area_velocity`) are still populated.
✅ Existing control gains and thresholds remain unchanged.

## Summary

**In short**: The Kalman filter acts as a **smart smoother and predictor** that learns velocity on-the-fly, making followers track leader turns more gracefully. It's particularly valuable during **rapid direction changes** where simple velocity extrapolation fails.

Tune the noise parameters (`proc_*_var`, `meas_*_var`) to find the sweet spot between responsiveness and smoothness for your specific boat dynamics and camera frame rate.
