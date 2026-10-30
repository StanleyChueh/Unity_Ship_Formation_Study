# Experiment matrices for the 3-way rollout videos

One table per video: the three runs shown in that video (seed 4903), metrics over t = 15 s → end. Last rows: mean over both seeds (4903, 5021) for context. Bold = best of the three.

## L01_lap_calm (video `L01_lap_calm_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.68** | 5.85 | 4.88 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.5 | 0.0 |
| Triangle IoU (0-1) | **0.820** | 0.658 | 0.727 |
| Follower error, 95th percentile (m) | **4.1** | 9.7 | 9.4 |
| Follower error, peak (m) | **4.3** | 10.6 | 10.9 |
| Minimum boat separation (m) | **25.7** | 24.9 | 25.6 |
| Fresh YOLO leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Correct leader detection (% frames) | **88.3** | 88.3 | 88.3 |
| Formation RMSE during bbox dropouts (m) | **2.56** | 4.88 | 4.53 |
| Steer variation (|d steer| per s) | **0.004** | 0.017 | 0.013 |
| Throttle variation (|d throttle| per s) | **0.010** | 0.076 | 0.062 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.9** | 6.2 | 5.1 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 2.2 | 0.0 |

## L02_lap_rough_sea1.5 (video `L02_lap_rough_sea1.5_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **2.39** | 5.35 | 4.43 |
| Formation broken, error > 10 m (% of time) | **0.0** | 0.0 | 0.0 |
| Triangle IoU (0-1) | **0.844** | 0.689 | 0.748 |
| Follower error, 95th percentile (m) | **4.1** | 9.2 | 8.6 |
| Follower error, peak (m) | **4.8** | 10.3 | 10.4 |
| Minimum boat separation (m) | 20.9 | 22.5 | **23.8** |
| Fresh YOLO leader detection (% frames) | **88.1** | 88.1 | 88.0 |
| Correct leader detection (% frames) | **88.1** | 88.1 | 87.9 |
| Formation RMSE during bbox dropouts (m) | **2.23** | 4.93 | 3.96 |
| Steer variation (|d steer| per s) | **0.009** | 0.016 | 0.019 |
| Throttle variation (|d throttle| per s) | **0.030** | 0.104 | 0.107 |
| Mean formation RMSE over both seeds (m) [n=2] | **2.5** | 5.7 | 4.7 |
| Mean broken time over both seeds (%) [n=2] | **0.0** | 1.2 | 0.0 |

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

## L04_lap_light_rain0.15 (video `L04_lap_light_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **407.78** | 531.39 | 857.56 |
| Formation broken, error > 10 m (% of time) | **44.3** | 93.9 | 98.2 |
| Triangle IoU (0-1) | **0.409** | 0.144 | 0.044 |
| Follower error, 95th percentile (m) | **1174.8** | 1414.2 | 1867.7 |
| Follower error, peak (m) | **1451.1** | 1643.2 | 1883.1 |
| Minimum boat separation (m) | 20.8 | **24.1** | 23.1 |
| Fresh YOLO leader detection (% frames) | **24.6** | 16.3 | 4.4 |
| Correct leader detection (% frames) | **24.5** | 16.3 | 4.1 |
| Formation RMSE during bbox dropouts (m) | **425.33** | 546.41 | 863.90 |
| Steer variation (|d steer| per s) | 0.029 | 0.022 | **0.013** |
| Throttle variation (|d throttle| per s) | **0.030** | 0.125 | 0.065 |
| Mean formation RMSE over both seeds (m) [n=2] | **208.0** | 481.3 | 883.2 |
| Mean broken time over both seeds (%) [n=2] | **23.4** | 93.9 | 97.1 |

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

## L06_lap_rain0.4 (video `L06_lap_rain0.4_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **769.29** | 970.26 | 1126.07 |
| Formation broken, error > 10 m (% of time) | **70.4** | 96.8 | 99.8 |
| Triangle IoU (0-1) | **0.213** | 0.063 | 0.027 |
| Follower error, 95th percentile (m) | **1734.4** | 1758.4 | 1863.1 |
| Follower error, peak (m) | 1851.7 | **1849.3** | 1874.2 |
| Minimum boat separation (m) | 17.6 | 18.9 | **21.3** |
| Fresh YOLO leader detection (% frames) | **8.9** | 1.6 | 0.7 |
| Correct leader detection (% frames) | **8.9** | 1.5 | 0.6 |
| Formation RMSE during bbox dropouts (m) | **786.43** | 985.54 | 1134.88 |
| Steer variation (|d steer| per s) | 0.013 | 0.007 | **0.004** |
| Throttle variation (|d throttle| per s) | 0.022 | 0.027 | **0.011** |
| Mean formation RMSE over both seeds (m) [n=2] | **608.9** | 875.4 | 1023.8 |
| Mean broken time over both seeds (%) [n=2] | **77.1** | 97.4 | 99.9 |

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

## L09_lap_night_rain0.15 (video `L09_lap_night_rain0.15_seed4903_3way.mp4`)

Leader turned 378° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | 959.10 | 961.02 | **904.58** |
| Formation broken, error > 10 m (% of time) | **98.1** | 100.0 | 99.8 |
| Triangle IoU (0-1) | **0.028** | 0.018 | 0.020 |
| Follower error, 95th percentile (m) | **1667.0** | 1825.1 | 1710.6 |
| Follower error, peak (m) | **1683.5** | 1860.0 | 1757.5 |
| Minimum boat separation (m) | 24.3 | **28.5** | 15.2 |
| Fresh YOLO leader detection (% frames) | **0.6** | 0.6 | 0.4 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Formation RMSE during bbox dropouts (m) | 961.30 | 959.64 | **909.36** |
| Steer variation (|d steer| per s) | 0.021 | 0.013 | **0.010** |
| Throttle variation (|d throttle| per s) | 0.023 | **0.009** | 0.011 |
| Mean formation RMSE over both seeds (m) [n=2] | **745.0** | 855.6 | 996.8 |
| Mean broken time over both seeds (%) [n=2] | **98.1** | 100.0 | 99.9 |

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

## WL2_lap_rain0.25_nonfixed (video `WL2_lap_rain0.25_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **359.52** | 363.66 | 399.78 |
| Formation broken, error > 10 m (% of time) | **87.6** | 100.0 | 99.0 |
| Triangle IoU (0-1) | **0.121** | 0.104 | 0.056 |
| Follower error, 95th percentile (m) | **703.3** | 827.4 | 834.3 |
| Follower error, peak (m) | 932.4 | 844.1 | **841.5** |
| Minimum boat separation (m) | 20.6 | **24.0** | 22.2 |
| Fresh YOLO leader detection (% frames) | 12.0 | **14.1** | 10.1 |
| Correct leader detection (% frames) | 11.9 | **14.1** | 10.0 |
| Steer variation (|d steer| per s) | 0.028 | 0.039 | **0.025** |
| Throttle variation (|d throttle| per s) | **0.031** | 0.144 | 0.153 |
| Mean formation RMSE over both seeds (m) [n=2] | **245.3** | 361.0 | 444.9 |
| Mean broken time over both seeds (%) [n=2] | **82.6** | 96.0 | 98.6 |

## WL3_lap_night_nonfixed (video `WL3_lap_night_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | 560.11 | **525.47** | 550.14 |
| Formation broken, error > 10 m (% of time) | **96.1** | 99.3 | 99.4 |
| Triangle IoU (0-1) | **0.052** | 0.034 | 0.035 |
| Follower error, 95th percentile (m) | 838.9 | **827.0** | 827.4 |
| Follower error, peak (m) | 846.1 | **834.3** | 834.6 |
| Minimum boat separation (m) | **24.7** | 4.2 | 1.4 |
| Fresh YOLO leader detection (% frames) | 0.0 | **0.1** | 0.0 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Steer variation (|d steer| per s) | 0.000 | 0.005 | **0.000** |
| Throttle variation (|d throttle| per s) | 0.001 | 0.007 | **0.000** |
| Mean formation RMSE over both seeds (m) [n=2] | 532.9 | **495.9** | 501.9 |
| Mean broken time over both seeds (%) [n=2] | **96.2** | 99.4 | 99.5 |

## WL4_lap_night_rain0.15_nonfixed (video `WL4_lap_night_rain0.15_nonfixed_seed4903_3way.mp4`)

Leader turned 397° in this run (complete circle).

| Metric | KALMAN ON | KALMAN OFF | NO bbox filtering |
|---|---:|---:|---:|
| Formation RMSE (m) | **404.92** | 447.64 | 515.81 |
| Formation broken, error > 10 m (% of time) | **96.3** | 99.4 | 99.4 |
| Triangle IoU (0-1) | **0.043** | 0.022 | 0.031 |
| Follower error, 95th percentile (m) | 822.8 | 899.9 | **817.4** |
| Follower error, peak (m) | 1040.3 | 963.6 | **825.0** |
| Minimum boat separation (m) | **24.7** | 14.4 | 5.0 |
| Fresh YOLO leader detection (% frames) | **1.4** | 0.4 | 0.5 |
| Correct leader detection (% frames) | **0.0** | 0.0 | 0.0 |
| Steer variation (|d steer| per s) | 0.043 | 0.015 | **0.009** |
| Throttle variation (|d throttle| per s) | 0.044 | 0.020 | **0.013** |
| Mean formation RMSE over both seeds (m) [n=2] | **460.6** | 490.4 | 515.7 |
| Mean broken time over both seeds (%) [n=2] | **96.3** | 99.5 | 99.5 |

