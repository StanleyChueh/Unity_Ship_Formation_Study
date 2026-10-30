# Detector v1 vs weather-trained detector v2 — weather laps

Same cases, seeds (4903, 5021), durations, dropouts and methods; only the YOLO weights differ: **v1** = `best_realistic.pt` (batches e03_laps / e04_wlaps), **v2** = `best_realistic_v2.pt` (batch e05_weather_v2). Values = mean over both seeds, t = 15 s → end. Bold = better detector for that method.

## Formation RMSE (m)

| Case | KALMAN ON v1 | KALMAN ON v2 | KALMAN OFF v1 | KALMAN OFF v2 | NO bbox filtering v1 | NO bbox filtering v2 |
|---|---:|---:|---:|---:|---:|---:|
| L04_lap_light_rain0.15 | 208.04 | **2.53** | 481.26 | **5.29** | 883.24 | **4.81** |
| L05_lap_rain0.25 | 168.29 | **2.48** | 625.34 | **5.50** | 912.37 | **4.91** |
| L06_lap_rain0.4 | 608.87 | **2.65** | 875.42 | **5.46** | 1023.75 | **4.91** |
| L07_lap_heavy_rain1.0 | 1134.27 | **2.73** | 1130.18 | **5.62** | 1277.82 | **4.97** |
| L08_lap_night | 1241.18 | **3.79** | 1238.59 | **7.06** | 1243.55 | **301.74** |
| L09_lap_night_rain0.15 | 744.98 | **3.71** | 855.58 | **7.00** | 996.83 | **6.26** |
| L10_lap_dark_storm | 573.27 | **3.31** | 678.65 | **6.14** | 796.50 | **5.59** |
| WL1_lap_rain0.15_nonfixed | 170.18 | **24.83** | 358.10 | **125.01** | 380.64 | **138.59** |
| WL2_lap_rain0.25_nonfixed | 245.25 | **35.94** | 361.04 | **125.31** | 444.88 | **122.73** |
| WL3_lap_night_nonfixed | 532.88 | **54.81** | 495.90 | **118.50** | 501.90 | **242.52** |
| WL4_lap_night_rain0.15_nonfixed | 460.59 | **109.85** | 490.44 | **149.93** | 515.73 | **212.19** |

## Formation broken, error > 10 m (% time)

| Case | KALMAN ON v1 | KALMAN ON v2 | KALMAN OFF v1 | KALMAN OFF v2 | NO bbox filtering v1 | NO bbox filtering v2 |
|---|---:|---:|---:|---:|---:|---:|
| L04_lap_light_rain0.15 | 23.4 | **0.0** | 93.9 | **0.0** | 97.1 | **0.0** |
| L05_lap_rain0.25 | 30.1 | **0.0** | 93.6 | **3.1** | 99.5 | **0.0** |
| L06_lap_rain0.4 | 77.1 | **0.0** | 97.4 | **0.0** | 99.9 | **0.0** |
| L07_lap_heavy_rain1.0 | 98.1 | **0.0** | 100.0 | **0.4** | 100.0 | **0.0** |
| L08_lap_night | 98.1 | **0.0** | 100.0 | **6.4** | 99.9 | **40.7** |
| L09_lap_night_rain0.15 | 98.1 | **0.0** | 100.0 | **6.1** | 99.9 | **1.0** |
| L10_lap_dark_storm | 98.3 | **0.0** | 100.0 | **2.4** | 99.9 | **0.0** |
| WL1_lap_rain0.15_nonfixed | 81.5 | **48.1** | 91.5 | **61.1** | 96.9 | **58.4** |
| WL2_lap_rain0.25_nonfixed | 82.6 | **49.4** | 96.0 | **65.3** | 98.6 | **53.4** |
| WL3_lap_night_nonfixed | 96.2 | **69.5** | 99.4 | **76.2** | 99.5 | **72.1** |
| WL4_lap_night_rain0.15_nonfixed | 96.3 | **70.4** | 99.5 | **80.2** | 99.5 | **69.5** |

## Triangle IoU (0-1)

| Case | KALMAN ON v1 | KALMAN ON v2 | KALMAN OFF v1 | KALMAN OFF v2 | NO bbox filtering v1 | NO bbox filtering v2 |
|---|---:|---:|---:|---:|---:|---:|
| L04_lap_light_rain0.15 | 0.543 | **0.827** | 0.102 | **0.682** | 0.050 | **0.727** |
| L05_lap_rain0.25 | 0.516 | **0.830** | 0.116 | **0.679** | 0.028 | **0.724** |
| L06_lap_rain0.4 | 0.185 | **0.816** | 0.071 | **0.677** | 0.029 | **0.720** |
| L07_lap_heavy_rain1.0 | 0.030 | **0.812** | 0.014 | **0.669** | 0.011 | **0.714** |
| L08_lap_night | 0.030 | **0.749** | 0.019 | **0.602** | 0.019 | **0.417** |
| L09_lap_night_rain0.15 | 0.030 | **0.754** | 0.019 | **0.605** | 0.021 | **0.650** |
| L10_lap_dark_storm | 0.025 | **0.775** | 0.015 | **0.640** | 0.020 | **0.673** |
| WL1_lap_rain0.15_nonfixed | 0.324 | **0.562** | 0.135 | **0.416** | 0.071 | **0.435** |
| WL2_lap_rain0.25_nonfixed | 0.243 | **0.551** | 0.093 | **0.400** | 0.054 | **0.459** |
| WL3_lap_night_nonfixed | 0.051 | **0.415** | 0.035 | **0.343** | 0.034 | **0.289** |
| WL4_lap_night_rain0.15_nonfixed | 0.047 | **0.389** | 0.029 | **0.327** | 0.032 | **0.322** |

## Fresh YOLO leader detection (% frames)

| Case | KALMAN ON v1 | KALMAN ON v2 | KALMAN OFF v1 | KALMAN OFF v2 | NO bbox filtering v1 | NO bbox filtering v2 |
|---|---:|---:|---:|---:|---:|---:|
| L04_lap_light_rain0.15 | 28.1 | **88.3** | 15.7 | **88.2** | 5.1 | **87.3** |
| L05_lap_rain0.25 | 21.8 | **88.3** | 9.7 | **88.1** | 1.9 | **87.1** |
| L06_lap_rain0.4 | 8.7 | **88.3** | 2.6 | **88.3** | 1.0 | **88.3** |
| L07_lap_heavy_rain1.0 | 0.0 | **88.3** | 0.0 | **88.3** | 0.0 | **88.3** |
| L08_lap_night | 0.0 | **88.3** | 0.0 | **88.1** | 0.0 | **69.3** |
| L09_lap_night_rain0.15 | 0.8 | **88.3** | 1.0 | **88.1** | 0.4 | **87.4** |
| L10_lap_dark_storm | 3.1 | **88.1** | 3.2 | **88.1** | 2.2 | **87.6** |
| WL1_lap_rain0.15_nonfixed | 22.2 | **85.1** | 18.5 | **77.6** | 14.9 | **76.2** |
| WL2_lap_rain0.25_nonfixed | 14.3 | **83.6** | 12.7 | **76.6** | 6.5 | **77.7** |
| WL3_lap_night_nonfixed | 0.1 | **78.6** | 0.1 | **75.0** | 0.1 | **67.4** |
| WL4_lap_night_rain0.15_nonfixed | 0.8 | **76.3** | 0.2 | **72.3** | 0.4 | **70.8** |

## Recovery after a 2 s bbox dropout (s, recovered dropouts only)

| Case | KALMAN ON v1 | KALMAN ON v2 | KALMAN OFF v1 | KALMAN OFF v2 | NO bbox filtering v1 | NO bbox filtering v2 |
|---|---:|---:|---:|---:|---:|---:|
| L04_lap_light_rain0.15 | 2.0 | **0.9** | — | 6.1 | — | 8.0 |
| L05_lap_rain0.25 | 0.9 | 0.9 | — | 6.1 | — | 8.4 |
| L06_lap_rain0.4 | 2.4 | **0.9** | — | 6.2 | — | 7.9 |
| L07_lap_heavy_rain1.0 | — | 0.9 | — | 5.9 | — | 7.7 |
| L08_lap_night | — | 0.9 | — | 6.2 | — | 9.0 |
| L09_lap_night_rain0.15 | — | 0.9 | — | 6.5 | — | 7.7 |
| L10_lap_dark_storm | — | 0.9 | — | 6.6 | — | 7.5 |
| WL1_lap_rain0.15_nonfixed | — | — | — | — | — | — |
| WL2_lap_rain0.25_nonfixed | — | — | — | — | — | — |
| WL3_lap_night_nonfixed | — | — | — | — | — | — |
| WL4_lap_night_rain0.15_nonfixed | — | — | — | — | — | — |

## Dropouts not recovered within 10 s (%)

| Case | KALMAN ON v1 | KALMAN ON v2 | KALMAN OFF v1 | KALMAN OFF v2 | NO bbox filtering v1 | NO bbox filtering v2 |
|---|---:|---:|---:|---:|---:|---:|
| L04_lap_light_rain0.15 | 17 | **0** | 100 | **17** | 100 | **0** |
| L05_lap_rain0.25 | 0 | 0 | 100 | **17** | 100 | **0** |
| L06_lap_rain0.4 | 33 | **0** | 100 | **0** | 100 | **0** |
| L07_lap_heavy_rain1.0 | 100 | **0** | 100 | **0** | 100 | **0** |
| L08_lap_night | 100 | **0** | 100 | **0** | 100 | **50** |
| L09_lap_night_rain0.15 | 100 | **0** | 100 | **0** | 100 | **17** |
| L10_lap_dark_storm | 100 | **0** | 100 | **0** | 100 | **0** |
| WL1_lap_rain0.15_nonfixed | — | — | — | — | — | — |
| WL2_lap_rain0.25_nonfixed | — | — | — | — | — | — |
| WL3_lap_night_nonfixed | — | — | — | — | — | — |
| WL4_lap_night_rain0.15_nonfixed | — | — | — | — | — | — |

