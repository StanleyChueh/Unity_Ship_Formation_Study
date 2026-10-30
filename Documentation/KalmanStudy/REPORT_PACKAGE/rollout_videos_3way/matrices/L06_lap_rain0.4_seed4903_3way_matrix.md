## L06_lap_rain0.4 (video `L06_lap_rain0.4_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **769.29** | 970.26 | 1126.07 |
| Formation broken, error > 10 m (% of time) | **70.4** | 96.8 | 99.8 |
| Triangle IoU (0-1) | **0.213** | 0.063 | 0.027 |
| Follower error, 95th percentile (m) | **1734.4** | 1758.4 | 1863.1 |
| Follower error, peak (m) | 1851.7 | **1849.3** | 1874.2 |
| Minimum boat separation (m) | 17.6 | 18.9 | **21.3** |
| Fresh YOLO leader detection (% frames) | **8.9** | 1.6 | 0.7 |
| Correct leader detection (% frames) | **8.9** | 1.5 | 0.6 |
| Formation RMSE during bbox dropouts (m) | **786.43** | 985.54 | 1134.88 |
| Steer variation (|d steer| per s) | 0.013 | 0.007 | **0.004** |
| Throttle variation (|d throttle| per s) | 0.022 | 0.027 | **0.011** |
| Mean formation RMSE over both seeds (m) [n=2] | **608.9** | 875.4 | 1023.8 |
| Mean broken time over both seeds (%) [n=2] | **77.1** | 97.4 | 99.9 |
