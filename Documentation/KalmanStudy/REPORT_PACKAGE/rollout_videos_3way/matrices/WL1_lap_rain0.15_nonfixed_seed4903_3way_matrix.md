## WL1_lap_rain0.15_nonfixed (video `WL1_lap_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **186.17** | 379.46 | 365.17 |
| Formation broken, error > 10 m (% of time) | **83.5** | 91.4 | 96.1 |
| Triangle IoU (0-1) | **0.288** | 0.122 | 0.082 |
| Follower error, 95th percentile (m) | **532.1** | 844.7 | 819.8 |
| Follower error, peak (m) | **688.0** | 851.9 | 826.8 |
| Minimum boat separation (m) | 22.3 | 23.4 | **25.1** |
| Fresh YOLO leader detection (% frames) | 17.8 | **18.2** | 15.0 |
| Correct leader detection (% frames) | 17.8 | **18.2** | 15.0 |
| Steer variation (|d steer| per s) | 0.044 | 0.028 | **0.022** |
| Throttle variation (|d throttle| per s) | **0.029** | 0.156 | 0.184 |
| Mean formation RMSE over both seeds (m) [n=2] | **170.2** | 358.1 | 380.6 |
| Mean broken time over both seeds (%) [n=2] | **81.5** | 91.5 | 96.9 |
