# Views videos — formation RMSE, IoU, steer and throttle variation

Each table = the three runs shown in that video (seed 4903), metrics over t = 15 s → end of run. Bold = best of the three (lower is better except IoU).

**How to read steer/throttle variation:** lower = smoother control, but only where the formation is actually held (L01–L03). Where a method has lost the leader (heavy rain, night, dark storm) the follower cruises blind with near-constant commands, so its variation is near zero although it is failing; and in rain KALMAN ON can show higher steer variation because it is still actively tracking. Read variation together with RMSE and IoU.

## L01_lap_calm (video `L01_lap_calm_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.68** | 5.85 | 4.88 |
| Formation IoU (0-1) | **0.820** | 0.658 | 0.727 |
| Steer variation (|Δsteer| per s) | **0.004** | 0.017 | 0.013 |
| Throttle variation (|Δthrottle| per s) | **0.010** | 0.076 | 0.062 |

## L02_lap_rough_sea1.5 (video `L02_lap_rough_sea1.5_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.39** | 5.35 | 4.43 |
| Formation IoU (0-1) | **0.844** | 0.689 | 0.748 |
| Steer variation (|Δsteer| per s) | **0.009** | 0.016 | 0.019 |
| Throttle variation (|Δthrottle| per s) | **0.030** | 0.104 | 0.107 |

## L03_lap_huge_waves_sea3 (video `L03_lap_huge_waves_sea3_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.12** | 22.27 | 20.11 |
| Formation IoU (0-1) | **0.790** | 0.579 | 0.597 |
| Steer variation (|Δsteer| per s) | **0.018** | 0.031 | 0.033 |
| Throttle variation (|Δthrottle| per s) | **0.042** | 0.138 | 0.164 |

## L04_lap_light_rain0.15 (video `L04_lap_light_rain0.15_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **407.78** | 531.39 | 857.56 |
| Formation IoU (0-1) | **0.409** | 0.144 | 0.044 |
| Steer variation (|Δsteer| per s) | 0.029 | 0.022 | **0.013** |
| Throttle variation (|Δthrottle| per s) | **0.030** | 0.125 | 0.065 |

## L05_lap_rain0.25 (video `L05_lap_rain0.25_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **167.53** | 533.61 | 879.64 |
| Formation IoU (0-1) | **0.511** | 0.154 | 0.021 |
| Steer variation (|Δsteer| per s) | 0.026 | 0.020 | **0.011** |
| Throttle variation (|Δthrottle| per s) | 0.051 | 0.120 | **0.030** |

## L06_lap_rain0.4 (video `L06_lap_rain0.4_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **769.29** | 970.26 | 1126.07 |
| Formation IoU (0-1) | **0.213** | 0.063 | 0.027 |
| Steer variation (|Δsteer| per s) | 0.013 | 0.007 | **0.004** |
| Throttle variation (|Δthrottle| per s) | 0.022 | 0.027 | **0.011** |

## L07_lap_heavy_rain1.0 (video `L07_lap_heavy_rain1.0_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **1033.45** | 1252.77 | 1274.43 |
| Formation IoU (0-1) | **0.028** | 0.017 | 0.012 |
| Steer variation (|Δsteer| per s) | 0.004 | **0.000** | 0.002 |
| Throttle variation (|Δthrottle| per s) | 0.005 | **0.000** | 0.001 |

## L08_lap_night (video `L08_lap_night_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **1250.97** | 1255.43 | 1254.42 |
| Formation IoU (0-1) | **0.030** | 0.017 | 0.019 |
| Steer variation (|Δsteer| per s) | 0.000 | **0.000** | 0.000 |
| Throttle variation (|Δthrottle| per s) | 0.001 | 0.000 | **0.000** |

## L09_lap_night_rain0.15 (video `L09_lap_night_rain0.15_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | 959.10 | 961.02 | **904.58** |
| Formation IoU (0-1) | **0.028** | 0.018 | 0.020 |
| Steer variation (|Δsteer| per s) | 0.021 | 0.013 | **0.010** |
| Throttle variation (|Δthrottle| per s) | 0.023 | **0.009** | 0.011 |

## L10_lap_dark_storm (video `L10_lap_dark_storm_seed4903_views.mp4`, leader turned 378°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **583.35** | 685.53 | 910.86 |
| Formation IoU (0-1) | **0.021** | 0.010 | 0.020 |
| Steer variation (|Δsteer| per s) | 0.063 | 0.099 | **0.047** |
| Throttle variation (|Δthrottle| per s) | 0.087 | 0.076 | **0.057** |

## WL1_lap_rain0.15_nonfixed (video `WL1_lap_rain0.15_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **186.17** | 379.46 | 365.17 |
| Formation IoU (0-1) | **0.288** | 0.122 | 0.082 |
| Steer variation (|Δsteer| per s) | 0.044 | 0.028 | **0.022** |
| Throttle variation (|Δthrottle| per s) | **0.029** | 0.156 | 0.184 |

## WL2_lap_rain0.25_nonfixed (video `WL2_lap_rain0.25_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **359.52** | 363.66 | 399.78 |
| Formation IoU (0-1) | **0.121** | 0.104 | 0.056 |
| Steer variation (|Δsteer| per s) | 0.028 | 0.039 | **0.025** |
| Throttle variation (|Δthrottle| per s) | **0.031** | 0.144 | 0.153 |

## WL3_lap_night_nonfixed (video `WL3_lap_night_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | 560.11 | **525.47** | 550.14 |
| Formation IoU (0-1) | **0.052** | 0.034 | 0.035 |
| Steer variation (|Δsteer| per s) | 0.000 | 0.005 | **0.000** |
| Throttle variation (|Δthrottle| per s) | 0.001 | 0.007 | **0.000** |

## WL4_lap_night_rain0.15_nonfixed (video `WL4_lap_night_rain0.15_nonfixed_seed4903_views.mp4`, leader turned 397°)

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **404.92** | 447.64 | 515.81 |
| Formation IoU (0-1) | **0.043** | 0.022 | 0.031 |
| Steer variation (|Δsteer| per s) | 0.043 | 0.015 | **0.009** |
| Throttle variation (|Δthrottle| per s) | 0.044 | 0.020 | **0.013** |

