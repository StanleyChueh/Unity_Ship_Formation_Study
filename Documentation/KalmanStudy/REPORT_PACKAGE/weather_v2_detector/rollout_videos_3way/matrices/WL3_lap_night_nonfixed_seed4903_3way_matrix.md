## WL3_lap_night_nonfixed (video `WL3_lap_night_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **56.47** | 104.02 | 246.36 |
| Formation broken, error > 10 m (% of time) | **68.3** | 76.7 | 74.2 |
| Triangle IoU (0-1) | **0.421** | 0.356 | 0.287 |
| Follower error, 95th percentile (m) | **184.5** | 294.6 | 684.0 |
| Follower error, peak (m) | **189.6** | 468.2 | 792.8 |
| Minimum boat separation (m) | 24.8 | **26.4** | 24.9 |
| Fresh YOLO leader detection (% frames) | **78.7** | 75.4 | 66.9 |
| Correct leader detection (% frames) | **78.5** | 75.4 | 66.9 |
| Steer variation (|d steer| per s) | 0.027 | 0.018 | **0.011** |
| Throttle variation (|d throttle| per s) | **0.028** | 0.173 | 0.140 |
| Mean formation RMSE over both seeds (m) [n=2] | **54.8** | 118.5 | 242.5 |
| Mean broken time over both seeds (%) [n=2] | **69.5** | 76.2 | 72.1 |
