# Experiment matrices for the 3-way rollout videos

One table per video: the three runs shown in that video (seed 4903), metrics over t = 15 s → end. Last rows: mean over both seeds (4903, 5021) for context. Bold = best of the three.

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

## L05_lap_rain0.25 (video `L05_lap_rain0.25_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.30** | 5.20 | 4.81 |
| Formation broken, error > 10 m (% of time) | **0.0** | 1.9 | 0.0 |
| Triangle IoU (0-1) | **0.840** | 0.688 | 0.733 |
| Follower error, 95th percentile (m) | **4.2** | 9.4 | 9.9 |
| Follower error, peak (m) | **5.1** | 11.8 | 12.0 |
| Minimum boat separation (m) | 22.3 | 23.6 | **24.2** |
| Fresh YOLO leader detection (% frames) | **88.2** | 88.0 | 86.9 |
| Correct leader detection (% frames) | **88.2** | 88.0 | 86.9 |
| Formation RMSE during bbox dropouts (m) | **2.17** | 4.79 | 4.20 |
| Steer variation (|d steer| per s) | **0.011** | 0.017 | 0.018 |
| Throttle variation (|d throttle| per s) | **0.038** | 0.134 | 0.157 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.5** | 5.5 | 4.9 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 3.1 | 0.0 |

## L06_lap_rain0.4 (video `L06_lap_rain0.4_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.45** | 5.21 | 4.60 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.831** | 0.688 | 0.734 |
| Follower error, 95th percentile (m) | **4.1** | 8.6 | 9.0 |
| Follower error, peak (m) | **4.5** | 10.0 | 10.6 |
| Minimum boat separation (m) | 24.7 | 25.2 | **25.4** |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Correct leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Formation RMSE during bbox dropouts (m) | **2.36** | 4.73 | 4.27 |
| Steer variation (|d steer| per s) | **0.007** | 0.015 | 0.017 |
| Throttle variation (|d throttle| per s) | **0.023** | 0.106 | 0.106 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.7** | 5.5 | 4.9 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 0.0 | 0.0 |

## L07_lap_heavy_rain1.0 (video `L07_lap_heavy_rain1.0_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.51** | 5.39 | 4.81 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.826** | 0.679 | 0.723 |
| Follower error, 95th percentile (m) | **4.2** | 9.1 | 9.5 |
| Follower error, peak (m) | **4.6** | 10.4 | 10.9 |
| Minimum boat separation (m) | 25.3 | 25.5 | **25.7** |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Correct leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Formation RMSE during bbox dropouts (m) | **2.43** | 4.76 | 4.51 |
| Steer variation (|d steer| per s) | **0.007** | 0.015 | 0.018 |
| Throttle variation (|d throttle| per s) | **0.023** | 0.116 | 0.116 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.7** | 5.6 | 5.0 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 0.4 | 0.0 |

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

## L09_lap_night_rain0.15 (video `L09_lap_night_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **3.47** | 6.60 | 6.18 |
| Formation broken, error > 10 m (% of time) | **0.0** | 2.5 | 1.2 |
| Triangle IoU (0-1) | **0.766** | 0.619 | 0.654 |
| Follower error, 95th percentile (m) | **5.7** | 10.1 | 10.8 |
| Follower error, peak (m) | **6.7** | 12.6 | 13.2 |
| Minimum boat separation (m) | 25.4 | 24.9 | **25.9** |
| Fresh YOLO leader detection (% frames) | **88.2** | 87.8 | 87.2 |
| Correct leader detection (% frames) | **88.2** | 87.8 | 87.1 |
| Formation RMSE during bbox dropouts (m) | **3.21** | 6.02 | 5.50 |
| Steer variation (|d steer| per s) | **0.012** | 0.018 | 0.022 |
| Throttle variation (|d throttle| per s) | **0.038** | 0.130 | 0.163 |
| Mean formation RMSE over both seeds (m) [n=2] | **3.7** | 7.0 | 6.3 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 6.1 | 1.0 |

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

## WL1_lap_rain0.15_nonfixed (video `WL1_lap_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **19.28** | 93.55 | 122.23 |
| Formation broken, error > 10 m (% of time) | **44.1** | 57.2 | 53.9 |
| Triangle IoU (0-1) | **0.592** | 0.457 | 0.465 |
| Follower error, 95th percentile (m) | **43.5** | 265.1 | 354.0 |
| Follower error, peak (m) | **96.2** | 441.0 | 536.4 |
| Minimum boat separation (m) | 23.8 | **24.3** | 23.9 |
| Fresh YOLO leader detection (% frames) | **87.1** | 79.3 | 77.2 |
| Correct leader detection (% frames) | **87.1** | 79.2 | 77.2 |
| Steer variation (|d steer| per s) | **0.011** | 0.013 | 0.011 |
| Throttle variation (|d throttle| per s) | **0.025** | 0.146 | 0.124 |
| Mean formation RMSE over both seeds (m) [n=2] | **24.8** | 125.0 | 138.6 |
| Mean broken time over both seeds (%) [n=2] | **48.1** | 61.1 | 58.4 |

## WL2_lap_rain0.25_nonfixed (video `WL2_lap_rain0.25_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **20.79** | 109.61 | 116.18 |
| Formation broken, error > 10 m (% of time) | **45.4** | 65.6 | 51.2 |
| Triangle IoU (0-1) | **0.587** | 0.409 | 0.475 |
| Follower error, 95th percentile (m) | **46.8** | 313.6 | 335.6 |
| Follower error, peak (m) | **106.7** | 491.9 | 518.4 |
| Minimum boat separation (m) | 23.5 | **24.0** | 23.7 |
| Fresh YOLO leader detection (% frames) | **85.9** | 77.1 | 78.2 |
| Correct leader detection (% frames) | **85.9** | 77.1 | 78.2 |
| Steer variation (|d steer| per s) | 0.012 | 0.014 | **0.012** |
| Throttle variation (|d throttle| per s) | **0.027** | 0.159 | 0.127 |
| Mean formation RMSE over both seeds (m) [n=2] | **35.9** | 125.3 | 122.7 |
| Mean broken time over both seeds (%) [n=2] | **49.4** | 65.3 | 53.4 |

## WL3_lap_night_nonfixed (video `WL3_lap_night_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **56.47** | 104.02 | 246.36 |
| Formation broken, error > 10 m (% of time) | **68.3** | 76.7 | 74.2 |
| Triangle IoU (0-1) | **0.421** | 0.356 | 0.287 |
| Follower error, 95th percentile (m) | **184.5** | 294.6 | 684.0 |
| Follower error, peak (m) | **189.6** | 468.2 | 792.8 |
| Minimum boat separation (m) | 24.8 | **26.4** | 24.9 |
| Fresh YOLO leader detection (% frames) | **78.7** | 75.4 | 66.9 |
| Correct leader detection (% frames) | **78.5** | 75.4 | 66.9 |
| Steer variation (|d steer| per s) | 0.027 | 0.018 | **0.011** |
| Throttle variation (|d throttle| per s) | **0.028** | 0.173 | 0.140 |
| Mean formation RMSE over both seeds (m) [n=2] | **54.8** | 118.5 | 242.5 |
| Mean broken time over both seeds (%) [n=2] | **69.5** | 76.2 | 72.1 |

## WL4_lap_night_rain0.15_nonfixed (video `WL4_lap_night_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **86.23** | 159.12 | 214.36 |
| Formation broken, error > 10 m (% of time) | **70.2** | 77.6 | 70.2 |
| Triangle IoU (0-1) | **0.410** | 0.329 | 0.329 |
| Follower error, 95th percentile (m) | **240.1** | 460.6 | 611.2 |
| Follower error, peak (m) | **405.4** | 633.3 | 751.7 |
| Minimum boat separation (m) | 24.8 | **25.0** | 23.9 |
| Fresh YOLO leader detection (% frames) | **75.5** | 71.7 | 70.8 |
| Correct leader detection (% frames) | **75.5** | 71.7 | 70.8 |
| Steer variation (|d steer| per s) | **0.013** | 0.016 | 0.013 |
| Throttle variation (|d throttle| per s) | **0.023** | 0.177 | 0.120 |
| Mean formation RMSE over both seeds (m) [n=2] | **109.8** | 149.9 | 212.2 |
| Mean broken time over both seeds (%) [n=2] | 70.4 | 80.2 | **69.5** |

