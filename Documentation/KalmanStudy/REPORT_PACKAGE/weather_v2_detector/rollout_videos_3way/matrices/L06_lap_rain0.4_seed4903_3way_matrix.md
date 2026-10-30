## L06_lap_rain0.4 (video `L06_lap_rain0.4_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.45** | 5.21 | 4.60 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.831** | 0.688 | 0.734 |
| Follower error, 95th percentile (m) | **4.1** | 8.6 | 9.0 |
| Follower error, peak (m) | **4.5** | 10.0 | 10.6 |
| Minimum boat separation (m) | 24.7 | 25.2 | **25.4** |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Correct leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Formation RMSE during bbox dropouts (m) | **2.36** | 4.73 | 4.27 |
| Steer variation (|d steer| per s) | **0.007** | 0.015 | 0.017 |
| Throttle variation (|d throttle| per s) | **0.023** | 0.106 | 0.106 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.7** | 5.5 | 4.9 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 0.0 | 0.0 |
