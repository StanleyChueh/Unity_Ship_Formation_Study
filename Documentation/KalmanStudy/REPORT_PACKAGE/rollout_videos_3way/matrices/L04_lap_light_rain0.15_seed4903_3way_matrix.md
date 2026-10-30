## L04_lap_light_rain0.15 (video `L04_lap_light_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **407.78** | 531.39 | 857.56 |
| Formation broken, error > 10 m (% of time) | **44.3** | 93.9 | 98.2 |
| Triangle IoU (0-1) | **0.409** | 0.144 | 0.044 |
| Follower error, 95th percentile (m) | **1174.8** | 1414.2 | 1867.7 |
| Follower error, peak (m) | **1451.1** | 1643.2 | 1883.1 |
| Minimum boat separation (m) | 20.8 | **24.1** | 23.1 |
| Fresh YOLO leader detection (% frames) | **24.6** | 16.3 | 4.4 |
| Correct leader detection (% frames) | **24.5** | 16.3 | 4.1 |
| Formation RMSE during bbox dropouts (m) | **425.33** | 546.41 | 863.90 |
| Steer variation (|d steer| per s) | 0.029 | 0.022 | **0.013** |
| Throttle variation (|d throttle| per s) | **0.030** | 0.125 | 0.065 |
| Mean formation RMSE over both seeds (m) [n=2] | **208.0** | 481.3 | 883.2 |
| Mean broken time over both seeds (%) [n=2] | **23.4** | 93.9 | 97.1 |
