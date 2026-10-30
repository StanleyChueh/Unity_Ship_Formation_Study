## L07_lap_heavy_rain1.0 (video `L07_lap_heavy_rain1.0_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.51** | 5.39 | 4.81 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.826** | 0.679 | 0.723 |
| Follower error, 95th percentile (m) | **4.2** | 9.1 | 9.5 |
| Follower error, peak (m) | **4.6** | 10.4 | 10.9 |
| Minimum boat separation (m) | 25.3 | 25.5 | **25.7** |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Correct leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Formation RMSE during bbox dropouts (m) | **2.43** | 4.76 | 4.51 |
| Steer variation (|d steer| per s) | **0.007** | 0.015 | 0.018 |
| Throttle variation (|d throttle| per s) | **0.023** | 0.116 | 0.116 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.7** | 5.6 | 5.0 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 0.4 | 0.0 |
