# Measured Kalman ON/OFF matrix

Positive improvement means lower RMSE with Kalman ON. Three paired seeds per case; bootstrap intervals are descriptive and have limited resolution.

| Case | OFF RMSE (m) | ON RMSE (m) | Paired improvement | Bootstrap 95% | ON wins | OFF / ON IoU |
|---|---:|---:|---:|---:|---:|---:|
| C0_calm_circle | 4.85 | 4.97 | -2.8% | [-6.9, +2.4]% | 1/3 | 0.704 / 0.730 |
| C1_huge_waves | 8.43 | 52.22 | -441.8% | [-1179.4, -48.4]% | 0/3 | 0.606 / 0.378 |
| C2_heavy_rain | 378.36 | 362.64 | +3.3% | [-12.4, +21.3]% | 2/3 | 0.040 / 0.038 |
| C3_dark_storm | 368.65 | 380.82 | -2.9% | [-7.6, +3.7]% | 1/3 | 0.031 / 0.013 |
| C4_turn_dropout_2s | 206.32 | 253.05 | -23.0% | [-27.3, -16.6]% | 0/3 | 0.190 / 0.169 |
| C5_speed_s_dropout | 127.61 | 157.99 | -29.6% | [-64.7, +23.6]% | 1/3 | 0.097 / 0.084 |
| C6_brief_dropout | 425.35 | 392.22 | +7.7% | [-4.2, +23.4]% | 2/3 | 0.033 / 0.036 |
| C7_unseen_turn_8s | 287.35 | 235.69 | +15.3% | [+1.9, +41.3]% | 3/3 | 0.156 / 0.146 |

## Hold-window ablations

| Case | Baseline | Baseline RMSE | ON RMSE | Paired improvement |
|---|---|---:|---:|---:|
| C4_turn_dropout_2s | off_matched | 253.22 | 253.05 | +0.0% |
| C5_speed_s_dropout | off_matched | 194.15 | 157.99 | +2.8% |
| C6_brief_dropout | off_matched | 472.88 | 392.22 | +16.9% |
| C4_turn_dropout_2s | on_short | 210.60 | 253.05 | -20.3% |
