## L10_lap_dark_storm (video `L10_lap_dark_storm_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **583.35** | 685.53 | 910.86 |
| Formation broken, error > 10 m (% of time) | **98.2** | 100.0 | 99.8 |
| Triangle IoU (0-1) | **0.021** | 0.010 | 0.020 |
| Follower error, 95th percentile (m) | **938.7** | 1196.8 | 1766.4 |
| Follower error, peak (m) | **959.9** | 1236.9 | 1776.0 |
| Minimum boat separation (m) | **26.6** | 5.2 | 17.7 |
| Fresh YOLO leader detection (% frames) | 2.3 | **3.0** | 2.6 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Formation RMSE during bbox dropouts (m) | **568.78** | 672.07 | 912.82 |
| Steer variation (|d steer| per s) | 0.063 | 0.099 | **0.047** |
| Throttle variation (|d throttle| per s) | 0.087 | 0.076 | **0.057** |
| Mean formation RMSE over both seeds (m) [n=2] | **573.3** | 678.7 | 796.5 |
| Mean broken time over both seeds (%) [n=2] | **98.3** | 100.0 | 99.9 |
