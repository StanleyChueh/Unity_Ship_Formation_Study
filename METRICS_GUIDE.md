# Extended Metrics Guide for USV Formation Control

## Overview

The logging system now captures a comprehensive set of evaluation metrics across six key dimensions recommended by research standards:

1. **Task-level performance** (formation control quality)
2. **Vision performance** (detection and tracking)
3. **Control behavior** (smoothness and stability)
4. **Safety** (collision avoidance)
5. **Robustness** (performance consistency)
6. **Efficiency** (computational performance)

## Logged Metrics (Detailed Reference)

### Primary Metrics (Captured in CSV)

#### Task-level Performance
- **`mean_distance`** (primary): Average distance between leader and follower (computed from area proxy and offset)
- **`min_distance`**: Minimum distance observed during the run (safety margin)
- **`mean_formation_error`**: Average deviation from desired formation geometry

#### Vision Performance
- **`det_rate_pct`**: Detection rate (% of frames where target was detected)
- **`stale_rate_pct`**: Stale rate (% of frames where target was marked stale/lost)
- **`pred_mae`**: Prediction mean absolute error for position offset
- **`pred_flips`**: Count of prediction sign changes (velocity reversals, lower is better)

#### Control Behavior
- **`dsteer_mean_abs`**: Mean absolute steering command change per frame (control smoothness)
- **`dthr_mean_abs`**: Mean absolute throttle command change per frame
- **`steer_saturated_pct`**: % of frames where steering reached saturation (>0.95 normalized)
- **`throttle_saturated_pct`**: % of frames where throttle reached saturation
- **`steer_max`**: Maximum steering command magnitude in run
- **`throttle_max`**: Maximum throttle command magnitude in run

#### Efficiency
- **`fps`**: Average frames per second (main loop frequency)

#### Kalman Filter Integration
- **`kalman_on_ratio`**: Fraction of run time Kalman filter was enabled (0.0 = OFF, 1.0 = ON)
- **`kalman_enabled`** (per snapshot): Instantaneous boolean state

## CSV Output Files

### Snapshot CSV: `run_<RUN_ID>_snapshots.csv`
- **Purpose**: Time-series data for a single run
- **Generated when**: Periodically during run (default every 5 seconds) and when app exits or checkpoint saved
- **Rows**: One per side (Left, Right) per snapshot time
- **Use case**: Temporal analysis, identifying when issues occur within a run

**Column headers:**
```
run_id, elapsed_s, kalman_enabled, side, samples, det_rate_pct, stale_rate_pct, 
dsteer_mean_abs, dthr_mean_abs, pred_mae, pred_flips, steer_saturated_pct, 
throttle_saturated_pct, steer_max, throttle_max, mean_distance, min_distance, 
mean_formation_error, fps
```

### Summary CSV: `experiment_metrics/run_summaries.csv`
- **Purpose**: Aggregate metrics for cross-run comparison
- **Generated when**: App exits (Ctrl-C/ESC) or checkpoint saved (press C)
- **Rows**: One per side (Left, Right) per run_id
- **Use case**: Comparing Kalman ON vs OFF, multiple parameter variations

**Column headers:**
```
run_id, timestamp, elapsed_s, kalman_on_ratio, side, samples, det_rate_pct, 
stale_rate_pct, dsteer_mean_abs, dthr_mean_abs, pred_mae, pred_flips, 
steer_saturated_pct, throttle_saturated_pct, steer_max, throttle_max, mean_distance, 
min_distance, mean_formation_error, fps
```

## How Metrics are Computed

### Distance Metrics
- **`mean_distance`**: Average of recorded distance values during detected frames
- **`min_distance`**: Minimum distance observed (safety indicator)
- **Note**: Distance is currently estimated from area proxy (visual size); can be extended to pixel-based or 3D geometry

### Formation Error
- **`mean_formation_error`**: Average deviation from target formation geometry
- **Note**: Computed from relative position and offset measurements

### Control Saturation
- **Criterion**: Steering or throttle magnitude > 0.95 (on 0-1 scale)
- **`steer_saturated_pct`** = (saturated frames / total frames) × 100
- **`throttle_saturated_pct`** = (saturated frames / total frames) × 100
- **Interpretation**: High saturation indicates controller is maxed out (may indicate tuning issue or challenging scenario)

### Prediction Quality
- **`pred_mae`**: Mean absolute error between predicted and measured offset
- **`pred_flips`**: Count of times prediction velocity sign reversed
  - Computed by checking if `(pred_offset - prev_pred_offset) / dt` changes sign
  - **Interpretation**: High flips → unstable prediction (may benefit from Kalman or tuning)

## Workflow: Recording Clean Kalman ON/OFF Runs

### For side-by-side comparison in papers:

**Run 1: Kalman OFF**
1. Set `ENABLE_KALMAN_FILTER = False` in `Assets/usv/config.py`
2. Start the app (python3 Assets/usv/app.py or similar)
3. Let experiment run for target duration
4. Exit app (ESC or Ctrl-C) to save final summary
5. **Result**: Summary row appended to `run_summaries.csv` with `kalman_on_ratio ≈ 0.0`

**Run 2: Kalman ON**
1. Set `ENABLE_KALMAN_FILTER = True` in `Assets/usv/config.py`
2. Restart app and run experiment
3. Exit app
4. **Result**: Summary row appended to `run_summaries.csv` with `kalman_on_ratio ≈ 1.0`

### In-run checkpointing (alternative):
- During a run, press **C** to save an on-demand checkpoint (new `run_id`, independent summary)
- Useful if you need to toggle Kalman mid-run or save multiple snapshots per configuration

## Plotting and Analysis

### View all metrics across runs:
```bash
python3 Assets/usv/plot_metrics_comparison.py \
  --input experiment_metrics/run_summaries.csv \
  --output-dir experiment_metrics/plots \
  --formats pdf,svg,png
```

### Compare two specific runs side-by-side:
```bash
python3 Assets/usv/compare_two_runs.py --run1 <RUN_ID1> --run2 <RUN_ID2> --formats pdf,svg,png
```

## Future Extensions

Planned metrics for enhanced evaluation:

- **Formation RMSE**: Root mean square error across formation points
- **Bearing error**: Heading/orientation error relative to formation geometry
- **Acquisition time**: Time to first detection after loss
- **Time within tolerance**: % of time within acceptable formation bounds
- **Collision avoidance**: Explicit collision/near-miss detection
- **Scenario-wise failure analysis**: Robustness to lighting/occlusion/noise
- **GPU/CPU usage**: Computational resource consumption

## CSV Format Notes

- Floating-point numbers are formatted to 6 decimal places (`:.6f`) for precision
- Integer counts (e.g., `pred_flips`) are stored as integers
- Timestamps use ISO 8601 format with seconds precision
- All paths are absolute (experiment_metrics folder is at project root)

## Backward Compatibility

Plotting scripts (`plot_metrics_comparison.py`, `compare_two_runs.py`) are **backward-compatible**:
- Older CSVs without new metrics will still load (new columns simply absent)
- New columns are safely ignored if not used in plots
- Safe to mix old and new summary rows in the same CSV
