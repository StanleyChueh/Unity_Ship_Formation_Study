# Views videos — formation RMSE, IoU, steer and throttle variation

Each table = the three runs shown in that video (seed 4903), metrics over t = 15 s → end of run. Bold = best of the three (lower is better except IoU).

**How to read steer/throttle variation:** lower = smoother control, but only where the formation is actually held (L01–L03). Where a method has lost the leader (heavy rain, night, dark storm) the follower cruises blind with near-constant commands, so its variation is near zero although it is failing; and in rain KALMAN ON can show higher steer variation because it is still actively tracking. Read variation together with RMSE and IoU.

## L04_lap_light_rain0.15 (video `L04_lap_light_rain0.15_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.35** | 5.15 | 4.54 |
| Formation IoU (0-1) | **0.837** | 0.689 | 0.739 |
| Steer variation (|Δsteer| per s) | **0.012** | 0.016 | 0.019 |
| Throttle variation (|Δthrottle| per s) | **0.037** | 0.127 | 0.151 |

## L05_lap_rain0.25 (video `L05_lap_rain0.25_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.30** | 5.20 | 4.81 |
| Formation IoU (0-1) | **0.840** | 0.688 | 0.733 |
| Steer variation (|Δsteer| per s) | **0.011** | 0.017 | 0.018 |
| Throttle variation (|Δthrottle| per s) | **0.038** | 0.134 | 0.157 |

## L06_lap_rain0.4 (video `L06_lap_rain0.4_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.45** | 5.21 | 4.60 |
| Formation IoU (0-1) | **0.831** | 0.688 | 0.734 |
| Steer variation (|Δsteer| per s) | **0.007** | 0.015 | 0.017 |
| Throttle variation (|Δthrottle| per s) | **0.023** | 0.106 | 0.106 |

## L07_lap_heavy_rain1.0 (video `L07_lap_heavy_rain1.0_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.51** | 5.39 | 4.81 |
| Formation IoU (0-1) | **0.826** | 0.679 | 0.723 |
| Steer variation (|Δsteer| per s) | **0.007** | 0.015 | 0.018 |
| Throttle variation (|Δthrottle| per s) | **0.023** | 0.116 | 0.116 |

## L08_lap_night (video `L08_lap_night_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.56** | 6.83 | 6.46 |
| Formation IoU (0-1) | **0.761** | 0.609 | 0.641 |
| Steer variation (|Δsteer| per s) | **0.012** | 0.017 | 0.020 |
| Throttle variation (|Δthrottle| per s) | **0.038** | 0.143 | 0.193 |

## L09_lap_night_rain0.15 (video `L09_lap_night_rain0.15_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.47** | 6.60 | 6.18 |
| Formation IoU (0-1) | **0.766** | 0.619 | 0.654 |
| Steer variation (|Δsteer| per s) | **0.012** | 0.018 | 0.022 |
| Throttle variation (|Δthrottle| per s) | **0.038** | 0.130 | 0.163 |

## L10_lap_dark_storm (video `L10_lap_dark_storm_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.04** | 5.71 | 5.26 |
| Formation IoU (0-1) | **0.789** | 0.657 | 0.685 |
| Steer variation (|Δsteer| per s) | **0.014** | 0.018 | 0.027 |
| Throttle variation (|Δthrottle| per s) | **0.040** | 0.139 | 0.180 |

## WL1_lap_rain0.15_nonfixed (video `WL1_lap_rain0.15_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **19.28** | 93.55 | 122.23 |
| Formation IoU (0-1) | **0.592** | 0.457 | 0.465 |
| Steer variation (|Δsteer| per s) | **0.011** | 0.013 | 0.011 |
| Throttle variation (|Δthrottle| per s) | **0.025** | 0.146 | 0.124 |

## WL2_lap_rain0.25_nonfixed (video `WL2_lap_rain0.25_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **20.79** | 109.61 | 116.18 |
| Formation IoU (0-1) | **0.587** | 0.409 | 0.475 |
| Steer variation (|Δsteer| per s) | 0.012 | 0.014 | **0.012** |
| Throttle variation (|Δthrottle| per s) | **0.027** | 0.159 | 0.127 |

## WL3_lap_night_nonfixed (video `WL3_lap_night_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **56.47** | 104.02 | 246.36 |
| Formation IoU (0-1) | **0.421** | 0.356 | 0.287 |
| Steer variation (|Δsteer| per s) | 0.027 | 0.018 | **0.011** |
| Throttle variation (|Δthrottle| per s) | **0.028** | 0.173 | 0.140 |

## WL4_lap_night_rain0.15_nonfixed (video `WL4_lap_night_rain0.15_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **86.23** | 159.12 | 214.36 |
| Formation IoU (0-1) | **0.410** | 0.329 | 0.329 |
| Steer variation (|Δsteer| per s) | **0.013** | 0.016 | 0.013 |
| Throttle variation (|Δthrottle| per s) | **0.023** | 0.177 | 0.120 |

