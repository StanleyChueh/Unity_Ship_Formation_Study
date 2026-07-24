---
name: project-usv-formation
description: Unity ship formation control experiment — key bugs, architecture, calibration findings
metadata:
  type: project
---

## System architecture

Vision-based formation control: two follower boats track a leader using front camera (YOLO bounding box offset+area) and optional side camera. Control sends `{throttle, steer}` via UDP. No direct world-coordinate position control — spacing is maintained entirely through visual area as a distance proxy.

## Key bug fixed 2026-06-12: Kalman filter had zero effect on throttle

`PREDICTION_AREA_BLEND` was 0.0 and `PREDICTION_OFFSET_BLEND` was 0.15. The Kalman filter's predicted area was never blended into throttle control, making Kalman-ON vs Kalman-OFF experiments indistinguishable.

Fixed: `PREDICTION_AREA_BLEND = 0.35`, `PREDICTION_OFFSET_BLEND = 0.40`.

**Why:** With area blend at 0, every throttle command was driven by raw noisy area measurements. Kalman's smoother area estimate was computed but discarded.

## Key bug fixed 2026-06-12: Formation 2× too large (60 m vs 30 m target)

`FORMATION_SCALE_MULTIPLIER = 1.0` caused the visual lock to capture whatever distance the followers were at when startup sync released (~60 m). The geometric target triangle uses `LEADER_TRAJECTORY_TRIANGLE_SIDE = 30 m`. The followers maintained 60 m formation indefinitely.

Fixed: `FORMATION_SCALE_MULTIPLIER = 0.5`. With this setting `desired_area = locked_area / 0.25 = 4 × locked_area`, which drives each follower to half the locked distance = 30 m.

**How to apply:** If in a future run the mean_side annotation in the top-down window differs significantly from 30 m, recalibrate as: `scale = (actual_lock_distance / target_distance)^{-1}` = `30 / actual_lock_m`. E.g. 60 m lock → scale = 0.5.

## plot_snapshots.py improvement 2026-06-12

Previously the formation plots (Formation IoU, Pos Error, RMS, Centroid Offset, etc.) used pixel-proxy inverse-area metrics from the CSV rather than world-space meters. `recompute_scaled_iou()` computed accurate world-space metrics but they were only used when `--formation-scale != 1.0`.

Fixed: `_prefer_scaled()` helper now always uses `_scaled` variants when available. "Distance Error vs Target" label changed to "Mean Follower Error (m)". Legends added to all subplots.

## Formation control architecture note

`VISION_FRONT_TARGET_OFFSET = 0.0` drives each follower to keep the leader **centred** in their front camera. Lateral offset positioning (side vertices of the equilateral triangle) relies on the **side camera** (`ENABLE_SIDE_DETECTION`, `SIDE_CAMERA_TARGET_MODE = "leader_only"`). Without side detection, both followers converge directly behind the leader, producing a degenerate formation.

## Control loop parameters
- `FOLLOW_MAX_THROTTLE = 0.62`, `LEADER_TRAJECTORY_SPEED = 18 m/s`
- `STEER_SLEW_RATE_PER_SEC = 4.0` (permissive; lower if jerkiness remains high after Kalman fix)
- `YOLO_AREA_OPT = 250000 px` (nominal optimal detection area ~30 m range)
