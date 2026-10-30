## L05_lap_rain0.25 (video `L05_lap_rain0.25_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.30** | 5.20 | 4.81 |
| Formation broken, error > 10 m (% of time) | **0.0** | 1.9 | 0.0 |
| Triangle IoU (0-1) | **0.840** | 0.688 | 0.733 |
| Follower error, 95th percentile (m) | **4.2** | 9.4 | 9.9 |
| Follower error, peak (m) | **5.1** | 11.8 | 12.0 |
| Minimum boat separation (m) | 22.3 | 23.6 | **24.2** |
| Fresh YOLO leader detection (% frames) | **88.2** | 88.0 | 86.9 |
| Correct leader detection (% frames) | **88.2** | 88.0 | 86.9 |
| Formation RMSE during bbox dropouts (m) | **2.17** | 4.79 | 4.20 |
| Steer variation (|d steer| per s) | **0.011** | 0.017 | 0.018 |
| Throttle variation (|d throttle| per s) | **0.038** | 0.134 | 0.157 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.5** | 5.5 | 4.9 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 3.1 | 0.0 |
