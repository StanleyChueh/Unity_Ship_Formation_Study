## L05_lap_rain0.25 (video `L05_lap_rain0.25_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **167.53** | 533.61 | 879.64 |
| Formation broken, error > 10 m (% of time) | **33.1** | 92.8 | 99.5 |
| Triangle IoU (0-1) | **0.511** | 0.154 | 0.021 |
| Follower error, 95th percentile (m) | **481.7** | 1423.8 | 1838.0 |
| Follower error, peak (m) | **844.4** | 1653.9 | 1860.4 |
| Minimum boat separation (m) | 23.3 | **25.6** | 17.6 |
| Fresh YOLO leader detection (% frames) | **21.9** | 10.3 | 1.7 |
| Correct leader detection (% frames) | **21.9** | 10.3 | 1.5 |
| Formation RMSE during bbox dropouts (m) | **180.65** | 548.85 | 890.21 |
| Steer variation (|d steer| per s) | 0.026 | 0.020 | **0.011** |
| Throttle variation (|d throttle| per s) | 0.051 | 0.120 | **0.030** |
| Mean formation RMSE over both seeds (m) [n=2] | **168.3** | 625.3 | 912.4 |
| Mean broken time over both seeds (%) [n=2] | **30.1** | 93.6 | 99.5 |
