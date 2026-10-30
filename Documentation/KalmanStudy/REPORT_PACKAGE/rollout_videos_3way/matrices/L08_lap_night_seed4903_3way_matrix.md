## L08_lap_night (video `L08_lap_night_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **1250.97** | 1255.43 | 1254.42 |
| Formation broken, error > 10 m (% of time) | **98.1** | 100.0 | 99.8 |
| Triangle IoU (0-1) | **0.030** | 0.017 | 0.019 |
| Follower error, 95th percentile (m) | 1897.3 | 1887.0 | **1886.1** |
| Follower error, peak (m) | 1906.2 | 1895.9 | **1895.0** |
| Minimum boat separation (m) | 26.6 | **28.5** | 27.1 |
| Fresh YOLO leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Formation RMSE during bbox dropouts (m) | **1254.57** | 1258.51 | 1257.58 |
| Steer variation (|d steer| per s) | 0.000 | **0.000** | 0.000 |
| Throttle variation (|d throttle| per s) | 0.001 | 0.000 | **0.000** |
| Mean formation RMSE over both seeds (m) [n=2] | 1241.2 | **1238.6** | 1243.5 |
| Mean broken time over both seeds (%) [n=2] | **98.1** | 100.0 | 99.9 |
