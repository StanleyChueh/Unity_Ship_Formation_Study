## L02_lap_rough_sea1.5 (video `L02_lap_rough_sea1.5_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.39** | 5.35 | 4.43 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.844** | 0.689 | 0.748 |
| Follower error, 95th percentile (m) | **4.1** | 9.2 | 8.6 |
| Follower error, peak (m) | **4.8** | 10.3 | 10.4 |
| Minimum boat separation (m) | 20.9 | 22.5 | **23.8** |
| Fresh YOLO leader detection (% frames) | **88.1** | 88.1 | 88.0 |
| Correct leader detection (% frames) | **88.1** | 88.1 | 87.9 |
| Formation RMSE during bbox dropouts (m) | **2.23** | 4.93 | 3.96 |
| Steer variation (|d steer| per s) | **0.009** | 0.016 | 0.019 |
| Throttle variation (|d throttle| per s) | **0.030** | 0.104 | 0.107 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.5** | 5.7 | 4.7 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 1.2 | 0.0 |
