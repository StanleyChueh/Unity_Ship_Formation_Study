## L01_lap_calm (video `L01_lap_calm_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.68** | 5.85 | 4.88 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.5 | 0.0 |
| Triangle IoU (0-1) | **0.820** | 0.658 | 0.727 |
| Follower error, 95th percentile (m) | **4.1** | 9.7 | 9.4 |
| Follower error, peak (m) | **4.3** | 10.6 | 10.9 |
| Minimum boat separation (m) | **25.7** | 24.9 | 25.6 |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Correct leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Formation RMSE during bbox dropouts (m) | **2.56** | 4.88 | 4.53 |
| Steer variation (|d steer| per s) | **0.004** | 0.017 | 0.013 |
| Throttle variation (|d throttle| per s) | **0.010** | 0.076 | 0.062 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.9** | 6.2 | 5.1 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 2.2 | 0.0 |
