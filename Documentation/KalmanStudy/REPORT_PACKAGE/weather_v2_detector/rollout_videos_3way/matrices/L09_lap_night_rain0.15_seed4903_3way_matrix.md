## L09_lap_night_rain0.15 (video `L09_lap_night_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.47** | 6.60 | 6.18 |
| Formation broken, error > 10 m (% of time) | **0.0** | 2.5 | 1.2 |
| Triangle IoU (0-1) | **0.766** | 0.619 | 0.654 |
| Follower error, 95th percentile (m) | **5.7** | 10.1 | 10.8 |
| Follower error, peak (m) | **6.7** | 12.6 | 13.2 |
| Minimum boat separation (m) | 25.4 | 24.9 | **25.9** |
| Fresh YOLO leader detection (% frames) | **88.2** | 87.8 | 87.2 |
| Correct leader detection (% frames) | **88.2** | 87.8 | 87.1 |
| Formation RMSE during bbox dropouts (m) | **3.21** | 6.02 | 5.50 |
| Steer variation (|d steer| per s) | **0.012** | 0.018 | 0.022 |
| Throttle variation (|d throttle| per s) | **0.038** | 0.130 | 0.163 |
| Mean formation RMSE over both seeds (m) [n=2] | **3.7** | 7.0 | 6.3 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 6.1 | 1.0 |
