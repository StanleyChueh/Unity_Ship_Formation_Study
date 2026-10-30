## L08_lap_night (video `L08_lap_night_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.56** | 6.83 | 6.46 |
| Formation broken, error > 10 m (% of time) | **0.0** | 2.3 | 1.2 |
| Triangle IoU (0-1) | **0.761** | 0.609 | 0.641 |
| Follower error, 95th percentile (m) | **5.7** | 10.2 | 11.3 |
| Follower error, peak (m) | **6.5** | 11.8 | 13.3 |
| Minimum boat separation (m) | 25.6 | 25.4 | **26.4** |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.0 | 86.2 |
| Correct leader detection (% frames) | **88.3** | 88.0 | 86.1 |
| Formation RMSE during bbox dropouts (m) | **3.43** | 6.36 | 5.59 |
| Steer variation (|d steer| per s) | **0.012** | 0.017 | 0.020 |
| Throttle variation (|d throttle| per s) | **0.038** | 0.143 | 0.193 |
| Mean formation RMSE over both seeds (m) [n=2] | **3.8** | 7.1 | 301.7 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 6.4 | 40.7 |
