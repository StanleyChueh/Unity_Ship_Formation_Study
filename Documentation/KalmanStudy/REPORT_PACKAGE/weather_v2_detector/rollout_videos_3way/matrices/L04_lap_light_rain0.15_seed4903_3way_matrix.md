## L04_lap_light_rain0.15 (video `L04_lap_light_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.35** | 5.15 | 4.54 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.837** | 0.689 | 0.739 |
| Follower error, 95th percentile (m) | **4.2** | 8.6 | 8.6 |
| Follower error, peak (m) | **5.3** | 10.7 | 11.3 |
| Minimum boat separation (m) | 21.9 | 23.8 | **24.0** |
| Fresh YOLO leader detection (% frames) | **88.2** | 88.0 | 87.3 |
| Correct leader detection (% frames) | **88.2** | 88.0 | 87.3 |
| Formation RMSE during bbox dropouts (m) | **2.24** | 4.51 | 4.06 |
| Steer variation (|d steer| per s) | **0.012** | 0.016 | 0.019 |
| Throttle variation (|d throttle| per s) | **0.037** | 0.127 | 0.151 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.5** | 5.3 | 4.8 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 0.0 | 0.0 |
