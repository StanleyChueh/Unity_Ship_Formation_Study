## WL2_lap_rain0.25_nonfixed (video `WL2_lap_rain0.25_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **359.52** | 363.66 | 399.78 |
| Formation broken, error > 10 m (% of time) | **87.6** | 100.0 | 99.0 |
| Triangle IoU (0-1) | **0.121** | 0.104 | 0.056 |
| Follower error, 95th percentile (m) | **703.3** | 827.4 | 834.3 |
| Follower error, peak (m) | 932.4 | 844.1 | **841.5** |
| Minimum boat separation (m) | 20.6 | **24.0** | 22.2 |
| Fresh YOLO leader detection (% frames) | 12.0 | **14.1** | 10.1 |
| Correct leader detection (% frames) | 11.9 | **14.1** | 10.0 |
| Steer variation (|d steer| per s) | 0.028 | 0.039 | **0.025** |
| Throttle variation (|d throttle| per s) | **0.031** | 0.144 | 0.153 |
| Mean formation RMSE over both seeds (m) [n=2] | **245.3** | 361.0 | 444.9 |
| Mean broken time over both seeds (%) [n=2] | **82.6** | 96.0 | 98.6 |
