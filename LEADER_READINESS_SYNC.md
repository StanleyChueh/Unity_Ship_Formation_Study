# Leader Trajectory Readiness Synchronization

## Overview
A new synchronization feature ensures that both follower boats achieve stable detection of the leader and each other before the leader begins its trajectory. This solves initialization timing issues where followers might start tracking at different times, leading to inconsistent experimental conditions.

## Problem Solved
When running experiments, the two followers (Left and Right) may not establish stable tracking at the same time. The Right follower can be slower to detect the leader due to side-camera edge geometry issues. By forcing the leader to wait, all boats start under uniform conditions.

## Configuration Flags

All settings are in `Assets/usv/config.py` under the "Leader auto-trajectory" section:

### Enable/Disable
- **`LEADER_WAIT_FOR_FOLLOWER_READINESS`** (default: `True`)
  - Set to `False` to disable synchronization and start trajectory immediately (old behavior)
  - Set to `True` to wait for both followers to be ready

### Timing
- **`LEADER_FOLLOWER_READINESS_TIMEOUT_SEC`** (default: `60.0`)
  - Maximum seconds to wait for followers to become ready
  - If timeout expires, leader starts anyway
  
- **`LEADER_FOLLOWER_READINESS_POLL_INTERVAL_SEC`** (default: `0.20`)
  - Check frequency (seconds) while waiting for readiness

### Detection Thresholds
- **`LEADER_READINESS_MIN_DETECTION_RATE_PCT`** (default: `85.0`)
  - Minimum detection rate (%) for each of: leader boat, follower boat
  - Both must exceed this threshold for a boat to be "ready"

- **`LEADER_READINESS_MIN_SAMPLES`** (default: `30`)
  - Minimum samples collected before evaluating readiness
  - Prevents premature "ready" state from noise

## Typical Workflow

1. **Python app starts**, creates metrics logger
2. **Follower cameras connect** (TCP streams start)
3. **Vision pipeline runs**, begins detecting leader and peer boats
4. **Metrics logger accumulates** samples over ~2–5 seconds
5. **Readiness check polls**:
   - For each side (Left, Right):
     - Compute `leader_detection_rate` and `follower_detection_rate`
     - Check if both rates ≥ 85% (configurable)
   - If both sides ready → proceed
   - If timeout → proceed anyway with warning
6. **Leader trajectory command sent** to Unity
7. **Experiment runs** with all boats synchronized

## Console Output

Example readiness wait output:
```
[LeaderCmd] Left: L_det=78.4% F_det=82.1% (target 85.0%, samples 22/30)
[LeaderCmd] Right: L_det=81.2% F_det=79.5% (target 85.0%, samples 22/30)
[LeaderCmd] Right: L_det=86.3% F_det=87.8% (target 85.0%, samples 35/30)
[LeaderCmd] Both followers ready (detections stable). Starting leader trajectory.
```

If timeout:
```
[LeaderCmd] WARNING: Follower readiness timeout. Left=False, Right=True. Proceeding anyway.
```

## Tuning Recommendations

### For faster startup (accept more uncertainty):
```python
LEADER_READINESS_MIN_DETECTION_RATE_PCT = 75.0  # Lower threshold
LEADER_READINESS_MIN_SAMPLES = 15              # Fewer samples
LEADER_FOLLOWER_READINESS_TIMEOUT_SEC = 30.0  # Shorter timeout
```

### For stricter consistency (wait longer):
```python
LEADER_READINESS_MIN_DETECTION_RATE_PCT = 95.0  # Higher threshold
LEADER_READINESS_MIN_SAMPLES = 50              # More samples
LEADER_FOLLOWER_READINESS_TIMEOUT_SEC = 120.0 # Longer timeout
```

### For experiments (recommended defaults):
```python
LEADER_WAIT_FOR_FOLLOWER_READINESS = True      # Enable sync
LEADER_READINESS_MIN_DETECTION_RATE_PCT = 85.0 # Balanced threshold
LEADER_READINESS_MIN_SAMPLES = 30              # ~1.5-2 sec at 15-20 Hz
LEADER_FOLLOWER_READINESS_TIMEOUT_SEC = 60.0  # Reasonable timeout
```

## Implementation Details

The synchronization uses metrics collected during the first phase of operation:
- **`leader_detected`**: Count of frames where leader boat was detected
- **`follower_detected`**: Count of frames where peer follower boat was detected
- **`samples`**: Total frame count

For each side, the detection rate is: `(detected_count / samples) * 100%`

Both leader and follower detection rates must exceed the threshold for readiness.

## Disabling Readiness Sync

To revert to the old behavior (start immediately):
```python
LEADER_WAIT_FOR_FOLLOWER_READINESS = False
```

The feature is independent of `LEADER_WAIT_FOR_FOLLOWER_CONNECTIONS`, which handles TCP camera link setup.

## Related Features

- **`LEADER_WAIT_FOR_FOLLOWER_CONNECTIONS`**: Waits for camera TCP connections (independent)
- **Right-side edge recovery**: See `RIGHT_SIDE_EDGE_RECOVERY_GAIN`, etc. (improves tracking when leader near frame edge)
