## WL4_lap_night_rain0.15_nonfixed (video `WL4_lap_night_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **404.92** | 447.64 | 515.81 |
| Formation broken, error > 10 m (% of time) | **96.3** | 99.4 | 99.4 |
| Triangle IoU (0-1) | **0.043** | 0.022 | 0.031 |
| Follower error, 95th percentile (m) | 822.8 | 899.9 | **817.4** |
| Follower error, peak (m) | 1040.3 | 963.6 | **825.0** |
| Minimum boat separation (m) | **24.7** | 14.4 | 5.0 |
| Fresh YOLO leader detection (% frames) | **1.4** | 0.4 | 0.5 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Steer variation (|d steer| per s) | 0.043 | 0.015 | **0.009** |
| Throttle variation (|d throttle| per s) | 0.044 | 0.020 | **0.013** |
| Mean formation RMSE over both seeds (m) [n=2] | **460.6** | 490.4 | 515.7 |
| Mean broken time over both seeds (%) [n=2] | **96.3** | 99.5 | 99.5 |
