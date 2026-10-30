## WL1_lap_rain0.15_nonfixed (video `WL1_lap_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **19.28** | 93.55 | 122.23 |
| Formation broken, error > 10 m (% of time) | **44.1** | 57.2 | 53.9 |
| Triangle IoU (0-1) | **0.592** | 0.457 | 0.465 |
| Follower error, 95th percentile (m) | **43.5** | 265.1 | 354.0 |
| Follower error, peak (m) | **96.2** | 441.0 | 536.4 |
| Minimum boat separation (m) | 23.8 | **24.3** | 23.9 |
| Fresh YOLO leader detection (% frames) | **87.1** | 79.3 | 77.2 |
| Correct leader detection (% frames) | **87.1** | 79.2 | 77.2 |
| Steer variation (|d steer| per s) | **0.011** | 0.013 | 0.011 |
| Throttle variation (|d throttle| per s) | **0.025** | 0.146 | 0.124 |
| Mean formation RMSE over both seeds (m) [n=2] | **24.8** | 125.0 | 138.6 |
| Mean broken time over both seeds (%) [n=2] | **48.1** | 61.1 | 58.4 |
