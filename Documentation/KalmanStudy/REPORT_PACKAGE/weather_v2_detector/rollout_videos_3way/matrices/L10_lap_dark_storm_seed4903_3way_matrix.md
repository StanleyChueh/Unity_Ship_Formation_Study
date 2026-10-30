## L10_lap_dark_storm (video `L10_lap_dark_storm_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.04** | 5.71 | 5.26 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.789** | 0.657 | 0.685 |
| Follower error, 95th percentile (m) | **5.1** | 9.1 | 9.1 |
| Follower error, peak (m) | **5.9** | 10.3 | 10.7 |
| Minimum boat separation (m) | 24.8 | 25.2 | **25.7** |
| Fresh YOLO leader detection (% frames) | **88.0** | 87.9 | 87.4 |
| Correct leader detection (% frames) | **88.0** | 87.9 | 87.3 |
| Formation RMSE during bbox dropouts (m) | **2.73** | 5.04 | 4.67 |
| Steer variation (|d steer| per s) | **0.014** | 0.018 | 0.027 |
| Throttle variation (|d throttle| per s) | **0.040** | 0.139 | 0.180 |
| Mean formation RMSE over both seeds (m) [n=2] | **3.3** | 6.1 | 5.6 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 2.4 | 0.0 |
