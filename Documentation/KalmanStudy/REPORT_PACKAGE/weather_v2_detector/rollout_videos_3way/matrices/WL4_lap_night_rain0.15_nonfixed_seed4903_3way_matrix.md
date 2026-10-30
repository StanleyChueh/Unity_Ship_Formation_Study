## WL4_lap_night_rain0.15_nonfixed (video `WL4_lap_night_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **86.23** | 159.12 | 214.36 |
| Formation broken, error > 10 m (% of time) | **70.2** | 77.6 | 70.2 |
| Triangle IoU (0-1) | **0.410** | 0.329 | 0.329 |
| Follower error, 95th percentile (m) | **240.1** | 460.6 | 611.2 |
| Follower error, peak (m) | **405.4** | 633.3 | 751.7 |
| Minimum boat separation (m) | 24.8 | **25.0** | 23.9 |
| Fresh YOLO leader detection (% frames) | **75.5** | 71.7 | 70.8 |
| Correct leader detection (% frames) | **75.5** | 71.7 | 70.8 |
| Steer variation (|d steer| per s) | **0.013** | 0.016 | 0.013 |
| Throttle variation (|d throttle| per s) | **0.023** | 0.177 | 0.120 |
| Mean formation RMSE over both seeds (m) [n=2] | **109.8** | 149.9 | 212.2 |
| Mean broken time over both seeds (%) [n=2] | 70.4 | 80.2 | **69.5** |
