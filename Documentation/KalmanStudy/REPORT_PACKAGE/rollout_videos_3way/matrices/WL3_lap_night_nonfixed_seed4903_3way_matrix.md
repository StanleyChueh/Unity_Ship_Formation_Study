## WL3_lap_night_nonfixed (video `WL3_lap_night_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | 560.11 | **525.47** | 550.14 |
| Formation broken, error > 10 m (% of time) | **96.1** | 99.3 | 99.4 |
| Triangle IoU (0-1) | **0.052** | 0.034 | 0.035 |
| Follower error, 95th percentile (m) | 838.9 | **827.0** | 827.4 |
| Follower error, peak (m) | 846.1 | **834.3** | 834.6 |
| Minimum boat separation (m) | **24.7** | 4.2 | 1.4 |
| Fresh YOLO leader detection (% frames) | 0.0 | **0.1** | 0.0 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Steer variation (|d steer| per s) | 0.000 | 0.005 | **0.000** |
| Throttle variation (|d throttle| per s) | 0.001 | 0.007 | **0.000** |
| Mean formation RMSE over both seeds (m) [n=2] | 532.9 | **495.9** | 501.9 |
| Mean broken time over both seeds (%) [n=2] | **96.2** | 99.4 | 99.5 |
