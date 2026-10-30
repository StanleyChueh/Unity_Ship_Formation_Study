## L03_lap_huge_waves_sea3 (video `L03_lap_huge_waves_sea3_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.12** | 22.27 | 20.11 |
| Formation broken, error > 10 m (% of time) | **0.0** | 17.7 | 20.0 |
| Triangle IoU (0-1) | **0.790** | 0.579 | 0.597 |
| Follower error, 95th percentile (m) | **5.2** | 62.2 | 40.7 |
| Follower error, peak (m) | **7.5** | 119.0 | 129.9 |
| Minimum boat separation (m) | 18.0 | 18.7 | **23.4** |
| Fresh YOLO leader detection (% frames) | **82.4** | 76.4 | 76.7 |
| Correct leader detection (% frames) | **82.0** | 75.6 | 75.9 |
| Formation RMSE during bbox dropouts (m) | **2.83** | 23.49 | 20.83 |
| Steer variation (|d steer| per s) | **0.018** | 0.031 | 0.033 |
| Throttle variation (|d throttle| per s) | **0.042** | 0.138 | 0.164 |
| Mean formation RMSE over both seeds (m) [n=2] | **3.3** | 117.3 | 26.7 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 27.7 | 20.9 |
