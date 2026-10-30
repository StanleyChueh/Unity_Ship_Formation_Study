## L09_lap_night_rain0.15 (video `L09_lap_night_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | 959.10 | 961.02 | **904.58** |
| Formation broken, error > 10 m (% of time) | **98.1** | 100.0 | 99.8 |
| Triangle IoU (0-1) | **0.028** | 0.018 | 0.020 |
| Follower error, 95th percentile (m) | **1667.0** | 1825.1 | 1710.6 |
| Follower error, peak (m) | **1683.5** | 1860.0 | 1757.5 |
| Minimum boat separation (m) | 24.3 | **28.5** | 15.2 |
| Fresh YOLO leader detection (% frames) | **0.6** | 0.6 | 0.4 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Formation RMSE during bbox dropouts (m) | 961.30 | 959.64 | **909.36** |
| Steer variation (|d steer| per s) | 0.021 | 0.013 | **0.010** |
| Throttle variation (|d throttle| per s) | 0.023 | **0.009** | 0.011 |
| Mean formation RMSE over both seeds (m) [n=2] | **745.0** | 855.6 | 996.8 |
| Mean broken time over both seeds (%) [n=2] | **98.1** | 100.0 | 99.9 |
