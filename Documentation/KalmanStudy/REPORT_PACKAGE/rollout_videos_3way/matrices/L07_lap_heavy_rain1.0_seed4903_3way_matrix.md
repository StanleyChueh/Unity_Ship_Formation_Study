## L07_lap_heavy_rain1.0 (video `L07_lap_heavy_rain1.0_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **1033.45** | 1252.77 | 1274.43 |
| Formation broken, error > 10 m (% of time) | **98.1** | 100.0 | 99.9 |
| Triangle IoU (0-1) | **0.028** | 0.017 | 0.012 |
| Follower error, 95th percentile (m) | 1895.2 | 1887.4 | **1883.3** |
| Follower error, peak (m) | 1903.9 | 1896.2 | **1890.7** |
| Minimum boat separation (m) | 26.6 | **28.5** | 5.1 |
| Fresh YOLO leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Formation RMSE during bbox dropouts (m) | **1038.30** | 1256.05 | 1275.88 |
| Steer variation (|d steer| per s) | 0.004 | **0.000** | 0.002 |
| Throttle variation (|d throttle| per s) | 0.005 | **0.000** | 0.001 |
| Mean formation RMSE over both seeds (m) [n=2] | 1134.3 | **1130.2** | 1277.8 |
| Mean broken time over both seeds (%) [n=2] | **98.1** | 100.0 | 100.0 |
