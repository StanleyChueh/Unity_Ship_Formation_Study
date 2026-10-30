## WL2_lap_rain0.25_nonfixed (video `WL2_lap_rain0.25_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **20.79** | 109.61 | 116.18 |
| Formation broken, error > 10 m (% of time) | **45.4** | 65.6 | 51.2 |
| Triangle IoU (0-1) | **0.587** | 0.409 | 0.475 |
| Follower error, 95th percentile (m) | **46.8** | 313.6 | 335.6 |
| Follower error, peak (m) | **106.7** | 491.9 | 518.4 |
| Minimum boat separation (m) | 23.5 | **24.0** | 23.7 |
| Fresh YOLO leader detection (% frames) | **85.9** | 77.1 | 78.2 |
| Correct leader detection (% frames) | **85.9** | 77.1 | 78.2 |
| Steer variation (|d steer| per s) | 0.012 | 0.014 | **0.012** |
| Throttle variation (|d throttle| per s) | **0.027** | 0.159 | 0.127 |
| Mean formation RMSE over both seeds (m) [n=2] | **35.9** | 125.3 | 122.7 |
| Mean broken time over both seeds (%) [n=2] | **49.4** | 65.3 | 53.4 |
