# Kalman Filter Tuning Guide for USV Follower Tracking

## Quick Start: Enabling & Testing

The Kalman filter is **automatically initialized and used** when you run the vision module. No configuration changes are required to enable it.

### To verify it's working:
1. Run your normal formation test with a sharp leader turn
2. Observe follower tracking smoothness during the turn
3. Check logs for any exceptions (if Kalman fails, it falls back to velocity method)

## Performance Scenarios & Tuning

### Scenario 1: Followers Lag Behind on Turns (Slow Response)

**Symptoms:**
- Follower seems to cut inside on leader turns
- Delay in steering response (~200ms+)
- Prediction confidence is too low

**Tuning:**

```python
# File: Assets/usv/kalman.py, in KalmanFilter.__init__()

# Increase velocity process noise (let velocity change more aggressively)
self.proc_vel_var = 0.05  # ← increase from 1e-2

# Decrease measurement noise (trust measurements more)
self.meas_offset_var = 0.005  # ← decrease from 1e-2
self.meas_area_var = 5.0      # ← decrease from 10.0

# In initialize(), reduce initial uncertainty on velocity
self.P = np.diag([0.05, 0.2, max(10.0, area * 0.3), 1.0])
#                      ↑ (reduced from 0.5)
```

**What this does:**
- Velocity estimates converge faster to new turning motions
- Measurements pull predictions more strongly
- Filter is more "trusting" and responsive

---

### Scenario 2: Followers Oscillate or Jitter on Target (Too Responsive)

**Symptoms:**
- Follower steering bounces side-to-side
- Area throttle fluctuates wildly
- Noisy video causing unstable predictions

**Tuning:**

```python
# File: Assets/usv/kalman.py, in KalmanFilter.__init__()

# Decrease velocity process noise (slow velocity changes)
self.proc_vel_var = 0.003  # ← decrease from 1e-2

# Increase measurement noise (trust measurements less, smooth more)
self.meas_offset_var = 0.05   # ← increase from 1e-2
self.meas_area_var = 30.0     # ← increase from 10.0

# In initialize(), increase initial uncertainty for stability
self.P = np.diag([0.1, 0.8, max(10.0, area * 0.3), 2.0])
#                 ↑    ↑                           ↑ (uncertainty cushion)
```

**What this does:**
- Velocity estimates change slowly (smoother)
- Measurements are discounted more (filter relies on history)
- Better noise rejection but may lag on rapid changes

---

### Scenario 3: Sweet Spot (Already Tuned)

If forward tracking works well but **turns are the issue**:

```python
# Leave proc_pos_var alone (handles straight-line chase)
self.proc_pos_var = 1e-3  # ← keep this

# Moderate velocity process noise for turns
self.proc_vel_var = 0.015  # ← slight increase from 1e-2

# Balanced measurement noise
self.meas_offset_var = 0.01  # ← keep or slight decrease
self.meas_area_var = 8.0     # ← keep or slight decrease
```

---

## Understanding the Parameters

| Parameter | Effect | Range | Default |
|-----------|--------|-------|---------|
| `proc_pos_var` | Position can drift | Larger = more drift | 1e-3 |
| `proc_vel_var` | Velocity can change | Larger = faster velocity changes | 1e-2 |
| `meas_offset_var` | Offset noise | Larger = trust measurements less | 1e-2 |
| `meas_area_var` | Area noise | Larger = trust measurements less | 10.0 |
| `P[0,0]` (init pos uncertainty) | Confidence on initial offset | Smaller = more confident | 0.05 |
| `P[1,1]` (init vel uncertainty) | Confidence on initial velocity | Smaller = more confident | 0.5 |

---

## Interactive Tuning Method

### Step 1: Baseline Test
Record a controlled scenario:
- Leader moves straight → follower catches up
- Leader makes a **90° turn** at constant speed
- Record:
  - Follower steering angle over time
  - Follower throttle over time
  - Target offset from center camera

### Step 2: Adjust One Parameter
Change **one** parameter by ~2-3x at a time:

```python
# Example: test higher velocity responsiveness
self.proc_vel_var = 0.03  # 3x increase
```

### Step 3: Re-test & Observe
- Does turn response improve?
- Does jitter increase?
- Does lag decrease?

### Step 4: Fine-tune
If Step 2 went in the right direction, nudge further (or less):
```python
self.proc_vel_var = 0.02  # 2x instead of 3x
```

---

## Configuration for Different Scenarios

### High-Speed Boat Turns (>5 knots, sharp maneuvers)
```python
self.proc_vel_var = 0.04       # aggressive velocity changes
self.meas_offset_var = 0.008   # trust measurements more
self.meas_area_var = 6.0
```

### Precision Formation (Low speed, tight spacing)
```python
self.proc_vel_var = 0.008      # conservative velocity changes
self.meas_offset_var = 0.02    # smooth out measurement noise
self.meas_area_var = 15.0
```

### Rough Sea (Noisy camera, waves)
```python
self.proc_vel_var = 0.01       # moderate
self.meas_offset_var = 0.05    # heavily smooth measurement
self.meas_area_var = 25.0
```

### Calm Conditions (Clean camera, good visibility)
```python
self.proc_vel_var = 0.02       # responsive
self.meas_offset_var = 0.008   # trust measurements
self.meas_area_var = 5.0
```

---

## Monitoring Kalman Performance

Add diagnostic logging to `vision.py` after the Kalman update:

```python
# In update_track_prediction(), after kf.update()
if kf is not None and kf.x is not None:
    state["kf_debug"] = {
        "offset": float(kf.x[0]),
        "offset_vel": float(kf.x[1]),
        "area": float(kf.x[2]),
        "area_vel": float(kf.x[3]),
        "P_trace": float(np.trace(kf.P)),  # covariance magnitude
    }
```

Then in `control.py`, add to return dict:
```python
"kf_debug": state.get("kf_debug", {}),
```

Log this to a file to analyze:
- **offset_vel**: Should be small (~0.0) when target is centered, large when turning
- **P_trace**: Should decrease as filter converges, increase when detection is stale
- **area_vel**: Should go negative (area shrinking = closing distance) on approach

---

## Advanced: Adaptive Noise

For future enhancement, consider auto-tuning based on innovation (residual):

```python
def update_adaptive(self, meas_offset, meas_area):
    # standard Kalman update
    H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]])
    z = np.array([meas_offset, meas_area], dtype=float)
    
    # check innovation before adding
    innovation = z - H.dot(self.x)
    inno_norm = np.linalg.norm(innovation)
    
    # if innovation is large, measurements might be unreliable
    if inno_norm > 0.3:  # threshold
        self.meas_offset_var *= 1.5  # distrust measurements temporarily
        self.meas_area_var *= 1.5
    else:
        self.meas_offset_var *= 0.95  # slowly regain trust
        self.meas_area_var *= 0.95
    
    # then run normal update with adjusted R
    # ...
```

---

## Summary

**Key Tuning Rule of Thumb:**

- **Follower too slow/laggy on turns?** → ↑ `proc_vel_var`, ↓ `meas_*_var`
- **Follower too jittery/oscillatory?** → ↓ `proc_vel_var`, ↑ `meas_*_var`
- **Sweet spot shifts with boat dynamics?** → Vary from baseline by small increments

Start with defaults, test in your specific environment, then adjust by ~1.5–2× steps. Most configurations converge within 3–5 test iterations.
