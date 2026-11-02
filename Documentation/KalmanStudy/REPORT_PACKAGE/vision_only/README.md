# Can the fleet hold formation without knowing the leader's speed?

Batch `Experiments/KalmanStudy/robust_evaluation/e06_vision_only`: 36 runs, all complete, source freeze
check passed (33 files). Protocol frozen before any run: `Documentation/KalmanStudy/eval_e06_vision_only_protocol.json`.
Runner: `Tools/kalman_study/run_vision_only.py`. Detector `best_realistic_v2.pt` in every arm. Descriptive test:
3 seeds per cell, 60 s runs, 10 Hz, simulation only.

## Where leader speed was used before this test

Every method in the earlier batches (e02, e03, e04, e05), including KALMAN OFF and NO bbox filtering, received the
leader's true speed from the simulator:

| Consumer | Used by |
|---|---|
| Kalman motion model, `r' = kappa(v_leader - v_own) + b` (`fusion_tracker.py`) | KALMAN ON |
| Speed command, `v_cmd = v_leader + clamp(...)` (`range_speed_policy.py`) | KALMAN ON, NO bbox filtering |
| Production feed-forward and blind-cruise throttle (`Assets/usv/control.py`) | All, including KALMAN OFF |

So those results are **not** fully vision-based. Leader position and heading were only logged, never used for control.
Simply deleting the speed makes the formation collapse (one development run, C8: 364 m KALMAN ON, 234 m KALMAN OFF).

## The three methods compared

- **With leader speed** (`on_rs`): as above; true speed, no noise or delay (a perfect radio link).
- **No leader speed** (`on_vo`): leader speed becomes a Kalman state estimated from box size over time:
  `r' = w - kappa*v_own`, `w = kappa*v_leader`. Uses the camera and the boat's own speed.
- **Strict vision only** (`on_pv`): as `on_vo`, but own speed comes from a model of the boat's own throttle commands. No
  speed sensor and no heading. The inputs are the camera and the commands the boat itself sent.

`vo_hooks.sanitize` overwrites every leader field in each state packet before any code reads it, so no leader data can leak.
The filter's one tuning value (`q = 6`) was chosen on development seeds 1701 and 1702 only.

## Results (median RMSE over 3 seeds; broken = mean % of time with error > 10 m; t = 15 s to end)

| Case | With leader speed | No leader speed | Strict vision only |
|---|---:|---:|---:|
| Calm, constant speed | 2.90 m, 0% | **1.45 m**, 0% | 2.22 m, 0% |
| Clear, speed changes + S-turns | **5.15 m**, 1.4% | 7.85 m, 25.8% | 8.48 m, 26.3% |
| Night, speed changes + S-turns | **5.69 m**, 2.0% | 6.65 m, 14.5% | 6.47 m, 12.2% |
| Huge waves, speed changes + S-turns | **5.42 m**, 4.5% | 12.26 m, 49.8% | 13.94 m, 39.3% |

Per-seed values: `VISION_ONLY_MATRIX.md/.csv`. Charts: `fig_a_cost_of_removing_leader_speed.png`, `fig_c_leader_speed_estimate.png`.
Videos (seed 4903): `rollout_videos_views/`.

- **Constant speed: leader speed is not needed.** Vision-only is better here, probably because it learns the speed the
  follower actually needs on its own arc rather than copying the leader's (not separately tested).
- **When the leader changes speed: tracking holds but is worse.** The estimate is about 1-2 s behind the true speed
  (RMS error 1.5 m/s in C8), so error grows during each change and broken time rises from about 1-5% to 12-50%.
- **Huge waves are the weak point.** Median error doubles. Wave-driven jitter in box size is the likely cause, since it is hard
  to separate from real range change. Seed 4903 of `on_vo` was lost at 311 m and logged 19 wrong-identity frames, which suggests
  it locked onto another boat. The strict arm did not fail catastrophically in these three seeds, but 3 seeds cannot show it is safer.
- **Control effort rises:** throttle variation is 2-6 times higher without leader speed.
- **The own-speed sensor made little difference:** strict and `on_vo` are within noise of each other at 3 seeds.

Non-Kalman baselines without leader speed were run on development seeds only (`robust_development/d05_vo_tune`: C8, C10, W3,
seeds 1701-1702): geometric mean RMSE 11.7 m for the Kalman filter vs 18.5 m for KALMAN OFF with a finite-difference speed
estimate, broken 32% vs 43%. This is indicative, not a held-out result.

## What can honestly be claimed

- "Camera-only leader perception, no leader telemetry" is true for `on_vo` and `on_pv`, **with these numbers**.
- The earlier headline results (e02, e05) must not be described as vision-only.
- Even the strict arm is not vision-only in every sense. It relies on a known plant model, and on a stationary calibration of
  box size at a known 25.6 m starting range.
- `Assets/usv` (what `python usv_controller.py` runs) has not been changed and **still uses leader speed**. The vision-only
  arms exist only in the `Tools/kalman_study` test harness.

## Kalman ON vs OFF when both are strictly vision-only (e07)

Batch `e07_vision_only_on_off`: 32 runs, all complete, freeze check passed (33 files). Protocol frozen before any run:
`Documentation/KalmanStudy/eval_e07_vision_only_on_off_protocol.json`. Both arms use the camera and own commands only, and neither was
tuned on these seeds. `on_pv` is the Kalman filter; `off_short_pv` is the production Kalman-OFF controller with leader speed from low-passed
finite differences. Values are per seed, in seed order. Videos (seed 4903): `rollout_videos_on_off/`.

| Case | Kalman RMSE (m) | Kalman OFF RMSE (m) | Broken %, Kalman | Broken %, OFF | Recovery, Kalman | Recovery, OFF |
|---|---:|---:|---:|---:|---:|---:|
| Heavy rain lap | 2.08 / 2.59 | 4.19 / 4.29 | 0 / 0 | 0 / 0 | 0.9 s | 1.8 s |
| Night lap | 3.52 / 4.25 | 7.67 / 8.26 | 0 / 0 | 14.0 / 17.2 | 0.9 s | 4.1 s |
| Night + rain lap | 3.27 / 4.04 | 6.38 / 7.68 | 0 / 0 | 3.5 / 13.2 | 0.9 s | 5.2 s |
| Dark storm lap | 3.18 / 3.88 | 6.55 / 7.60 | 0 / 0 | 5.4 / 15.3 | 1.2 s | 5.0 s |
| Huge waves lap | **891.13** / 3.55 | 6.92 / 7.60 | 92.3 / 0 | 9.7 / 15.3 | 0.9 s (3/6 dropouts not recovered) | 5.8 s |
| Clear, speed changes + S-turns | 8.46 / 9.12 / 7.44 | 18.43 / 10.39 / 7.82 | 26.2 / 27.5 / 25.1 | 49.2 / 31.5 / 25.3 | 0.9 s (3/9 not recovered) | 0.9 s (6/9 not recovered) |
| Huge waves, speed changes + S-turns | 14.73 / 100.66 / 14.13 | 105.56 / 15.53 / 80.91 | 46.3 / 88.0 / 37.0 | 79.4 / 39.5 / 91.1 | 0.9 s (4/9 not recovered) | 3.6 s (7/9 not recovered) |

Vision-only Kalman has about half the error of Kalman OFF in rain, night and storm laps, and recovers much faster. **It is worse than Kalman OFF on
the huge-wave lap**: in seed 4903 the left follower lost the leader at about t = 25 s, its speed estimate froze at 13.7 m/s, and it cruised
away to about 1,400 m while the right follower stayed at 1-6 m. Finding the leader again after a loss is the clearest thing to fix next.

## Ideas tested offline for improving vision-only tracking (saved frames, no closed-loop runs)

These score measurements against true boat separation on saved runs. They do not show how formation error would change once
the method is in the control loop. Scripts: `Tools/kalman_study/flow_feasibility.py`, `size_measurement_test.py`.
Data: `flow_feasibility.json`, `size_measurement.json`.

**Optical flow (LK features with a forward-backward check, as in the drone tracker).** Five runs, both followers.

| Use | Result |
|---|---|
| Range rate from feature scale change | Slightly better over short windows in clear water (0.5 s: 1.75-2.39 vs 2.34-3.30 m/s RMS); at a 2 s window the box is better in every case (clear 0.77-0.91 vs 1.11-1.45; huge waves 1.98-2.50 vs 4.62-5.26) |
| Steering offset through a scheduled dropout | Better while flow survives (0.001-0.005 vs 0.008-0.038), but survived only 6/12 gaps in huge waves; worse in dark storm (0.049 vs 0.012, 7/18 survived) |
| Range through a dropout | Worse: 11-48% error vs about 7-20% for the tracker (C8, C10) |

The boat is about 40 px wide, so 1 m/s of relative speed changes its size by about 0.16 px per frame, close to the resolution of
flow. Scheduled dropouts also flatter flow, because only the detector output is withheld and the image stays clean. Conclusion: flow
does not address the main weakness (speed changes), and steering is not what fails.

**Box measurement (range-rate RMS error, m/s, 1 s / 2 s windows; left follower, one run per case).**

| Case | Full 640, area (current) | ROI 640 crop, area | ROI 640 crop, width | Full 1280, width |
|---|---:|---:|---:|---:|
| Clear, speed changes | 1.75 / 0.97 | 1.58 / 0.92 | 1.29 / 1.05 | 1.31 / 1.08 |
| Night, speed changes | 4.68 / 2.27 | 3.59 / 2.02 | **2.05 / 1.34** | 2.10 / 1.40 |
| Dark storm lap | 4.74 / 2.43 | 3.81 / 1.94 | **3.12 / 1.65** | 5.86 / 2.92 |
| Huge waves, speed changes | **7.27 / 3.50** | 9.01 / 4.10 | 9.42 / 4.29 | 9.82 / 4.61 |

Zooming in costs about the same inference time as the current full-frame pass, and it is promising at night and in storms. No
measurement option helped in huge waves. The cause was not investigated; one possibility is that waves really do hide part of the hull.
Closed-loop testing is still needed before claiming any improvement in formation error.
