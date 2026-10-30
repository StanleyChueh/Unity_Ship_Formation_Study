# Experiment matrix — all conditions × all filtering arms

Cell = median formation RMSE (m) / formation-broken time (% of the analysis window with RMS error > 10 m); n = seeds. Analysis window: t = 15 s to end of run (60 s runs, or 135 s full-lap runs). Every completed run is included. Sources: e02 (frozen confirmatory test), e02x and e03_laps (descriptive extensions with identical code).


### A. FIXED trajectory — one complete R360 circle lap (135 s, leader turns >= 360°) under every weather/wave level, 2 s bbox dropouts every 18 s

| Condition | Leader motion | Kalman ON | Kalman OFF | EMA filter | No tracker filter | No bbox filter |
|---|---|---:|---:|---:|---:|---:|
| L01_lap_calm (sea 0.55, rain 0.0, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 2.9 / 0 % (n=2) | 6.2 / 2 % (n=2) | 3.0 / 0 % (n=2) | 5.1 / 0 % (n=2) | 5.1 / 0 % (n=2) |
| L02_lap_rough_sea1.5 (sea 1.5, rain 0.0, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 2.5 / 0 % (n=2) | 5.7 / 1 % (n=2) | 3.0 / 0 % (n=2) | 4.7 / 0 % (n=2) | 4.7 / 0 % (n=2) |
| L03_lap_huge_waves_sea3 (sea 3.0, rain 0.0, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 3.3 / 0 % (n=2) | 117.3 / 28 % (n=2) | 189.8 / 36 % (n=2) | 286.2 / 49 % (n=2) | 26.7 / 21 % (n=2) |
| L04_lap_light_rain0.15 (sea 1.5, rain 0.15, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 208.0 / 23 % (n=2) | 481.3 / 94 % (n=2) | 461.7 / 54 % (n=2) | 748.5 / 95 % (n=2) | 883.2 / 97 % (n=2) |
| L05_lap_rain0.25 (sea 1.5, rain 0.25, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 168.3 / 30 % (n=2) | 625.3 / 94 % (n=2) | 513.4 / 80 % (n=2) | 938.1 / 99 % (n=2) | 912.4 / 99 % (n=2) |
| L06_lap_rain0.4 (sea 1.0, rain 0.4, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 608.9 / 77 % (n=2) | 875.4 / 97 % (n=2) | 798.5 / 92 % (n=2) | 905.9 / 100 % (n=2) | 1023.8 / 100 % (n=2) |
| L07_lap_heavy_rain1.0 (sea 0.9, rain 1.0, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 1134.3 / 98 % (n=2) | 1130.2 / 100 % (n=2) | 1018.3 / 98 % (n=2) | 1184.2 / 100 % (n=2) | 1277.8 / 100 % (n=2) |
| L08_lap_night (sea 1.5, rain 0.0, NIGHT, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 1241.2 / 98 % (n=2) | 1238.6 / 100 % (n=2) | 1242.6 / 98 % (n=2) | 1243.5 / 100 % (n=2) | 1243.5 / 100 % (n=2) |
| L09_lap_night_rain0.15 (sea 1.5, rain 0.15, NIGHT, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 745.0 / 98 % (n=2) | 855.6 / 100 % (n=2) | 1046.9 / 98 % (n=2) | 1042.2 / 100 % (n=2) | 996.8 / 100 % (n=2) |
| L10_lap_dark_storm (sea 1.5, rain 1.0, NIGHT, dropouts 2.0 s) | fixed circle, constant 18 m/s, turned 378° | 573.3 / 98 % (n=2) | 678.7 / 100 % (n=2) | 575.5 / 99 % (n=2) | 957.1 / 100 % (n=2) | 796.5 / 100 % (n=2) |

### B. NON-FIXED trajectories — leader changes speed (14/20/10/18 m/s) and S-turns, or turns unexpectedly (60 s)

| Condition | Leader motion | Kalman ON | Kalman OFF | EMA filter | No tracker filter | No bbox filter |
|---|---|---:|---:|---:|---:|---:|
| C8_clear_speed_s_dropout (sea 1.0, rain 0, dropouts 2.0 s) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 4.3 / 0 % (n=8) | 7.4 / 23 % (n=8) | 4.6 / 5 % (n=8) | 7.8 / 25 % (n=8) | 7.9 / 25 % (n=8) |
| C10_huge_waves_s_dropout (sea 3.0, rain 0, dropouts 2.0 s) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 4.7 / 8 % (n=8) | 8.4 / 28 % (n=8) | 7.9 / 30 % (n=8) | 8.6 / 37 % (n=8) | 9.0 / 42 % (n=8) |
| W1_rain015_rough_s (sea 1.5, rain 0.15) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 5.4 / 2 % (n=8) | 11.8 / 52 % (n=8) | 6.9 / 17 % (n=8) | 65.2 / 82 % (n=8) | 75.0 / 83 % (n=8) |
| W2_rain025_rough_s (sea 1.5, rain 0.25) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 6.6 / 13 % (n=2) | 155.8 / 80 % (n=2) | 138.7 / 69 % (n=2) | 97.1 / 83 % (n=2) | 137.0 / 86 % (n=2) |
| C5_speed_s_dropout (sea 1.0, rain 0.4, dropouts 2.0 s) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 51.8 / 65 % (n=2) | 362.1 / 85 % (n=2) | 274.7 / 84 % (n=2) | 82.7 / 85 % (n=2) | 107.8 / 85 % (n=2) |
| W3_night_rough_s (sea 1.5, rain 0, NIGHT) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 196.1 / 91 % (n=2) | 200.8 / 91 % (n=2) | 200.8 / 91 % (n=2) | 226.1 / 91 % (n=2) | 212.7 / 91 % (n=2) |
| W4_night_rain015_rough_s (sea 1.5, rain 0.15, NIGHT) | NON-FIXED: speed 14/20/10/18 m/s + S-turns | 393.0 / 93 % (n=2) | 421.7 / 93 % (n=2) | 239.4 / 93 % (n=2) | 397.6 / 92 % (n=2) | 341.7 / 92 % (n=2) |
| C7_unseen_turn_8s (sea 0.55, rain 0, dropouts 8.0 s) | NON-FIXED: straight then sudden turn | 338.4 / 78 % (n=4) | 251.9 / 82 % (n=4) | 309.1 / 77 % (n=4) | 234.2 / 82 % (n=4) | 285.1 / 82 % (n=4) |

### C. Other conditions (60 s; fixed circles)

| Condition | Leader motion | Kalman ON | Kalman OFF | EMA filter | No tracker filter | No bbox filter |
|---|---|---:|---:|---:|---:|---:|
| C0_calm_circle (sea 0.55, rain 0) | fixed circle, constant 18 m/s | 2.5 / 0 % (n=4) | 4.4 / 0 % (n=4) | 2.6 / 0 % (n=4) | 2.5 / 0 % (n=4) | 2.5 / 0 % (n=4) |
| C1_huge_waves (sea 3.0, rain 0) | fixed circle, constant 18 m/s | 3.7 / 0 % (n=4) | 5.0 / 0 % (n=4) | 3.5 / 0 % (n=4) | 3.5 / 0 % (n=4) | 4.0 / 0 % (n=4) |
| C9_clear_rough_brief_dropout (sea 1.2, rain 0, dropouts 0.5 s) | fixed circle, constant 18 m/s | 3.8 / 0 % (n=2) | 5.9 / 0 % (n=2) | 3.9 / 0 % (n=2) | 4.2 / 0 % (n=2) | 4.2 / 0 % (n=2) |
| C4_turn_dropout_2s (sea 0.55, rain 0, dropouts 2.0 s) | fixed circle, constant 18 m/s | 11.2 / 37 % (n=4) | 88.1 / 85 % (n=4) | 6.1 / 0 % (n=4) | 144.5 / 86 % (n=4) | 144.5 / 86 % (n=4) |
| C2_heavy_rain (sea 0.9, rain 1.0) | fixed circle, constant 18 m/s | 368.1 / 95 % (n=2) | 379.6 / 100 % (n=2) | 369.1 / 95 % (n=2) | 288.4 / 100 % (n=2) | 412.1 / 100 % (n=2) |
| C3_dark_storm (sea 1.5, rain 1.0, NIGHT) | fixed circle, constant 18 m/s | 348.8 / 95 % (n=2) | 388.1 / 100 % (n=2) | 401.5 / 97 % (n=2) | 426.7 / 100 % (n=2) | 287.2 / 100 % (n=2) |

Full metrics (mean RMSE, catastrophic runs, IoU, detection rates, min separation, dropout error, measured leader turn): `experiment_matrix.csv`; per run: `all_runs.csv`.

## Confirmatory statistics (e02 primary family C8 + C10 + W1, 8 unseen seeds, exact sign-flip, fixed sequence α = 0.05)

| Hypothesis | RMSE change | 95 % bootstrap | Seeds favouring | Exact p | Result |
|---|---:|---:|---:|---:|---|
| Kalman ON vs No tracker filter | -68.8 % | [-72.4, -62.6] % | 8/8 | 0.0078 | CONFIRMED |
| Kalman ON vs Kalman OFF | -48.9 % | [-59.7, -39.0] % | 8/8 | 0.0078 | CONFIRMED |
| Kalman ON vs EMA filter | -33.2 % | [-53.3, -5.5] % | 6/8 | 0.0781 | not confirmed |
| EMA filter vs No tracker filter (descriptive) | -53.3 % | [-63.2, -37.9] % | 7/8 | 0.0156 | descriptive |
| EMA filter vs Kalman OFF (descriptive) | -23.5 % | [-44.7, +7.7] % | 6/8 | 0.1797 | descriptive |
| Kalman OFF vs No tracker filter (descriptive) | -38.9 % | [-49.6, -23.0] % | 7/8 | 0.0234 | descriptive |

## Kalman ON vs NO bbox filtering at all (e02x arm paired with e02 runs on the same seeds; descriptive, post-hoc arm)

| Condition | n | No bbox filter RMSE (mean) | Kalman ON RMSE (mean) | Geometric change | Seeds Kalman better | Broken % |
|---|---:|---:|---:|---:|---:|---:|
| C0_calm_circle | 4 | 2.6 | 2.5 | -3.1 % | 4/4 | 0.0 → 0.0 |
| C10_huge_waves_s_dropout | 8 | 13.9 | 17.4 | -43.9 % | 7/8 | 42.4 → 8.1 |
| C1_huge_waves | 4 | 3.9 | 3.5 | -9.2 % | 4/4 | 0.0 → 0.0 |
| C4_turn_dropout_2s | 4 | 141.7 | 10.4 | -92.8 % | 4/4 | 85.8 → 36.9 |
| C7_unseen_turn_8s | 4 | 277.6 | 330.4 | +20.4 % | 1/4 | 82.0 → 77.9 |
| C8_clear_speed_s_dropout | 8 | 7.8 | 4.3 | -45.0 % | 8/8 | 24.8 → 0.0 |
| W1_rain015_rough_s | 8 | 76.7 | 6.5 | -92.1 % | 8/8 | 83.3 → 2.2 |
