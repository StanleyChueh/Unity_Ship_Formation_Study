# Vision-only matrix

Batch `e06_vision_only`. Mean over seeds unless stated, t = 15 s → end. Bold = best in that row.

## Formation RMSE (m)

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | 2.95 | **1.50** | 2.24 | — | — |
| C8_clear_speed_s_dropout | **5.27** | 7.95 | 8.37 | — | — |
| W3_night_rough_s | **5.68** | 6.51 | 6.57 | — | — |
| C10_huge_waves_s_dropout | **5.43** | 111.74 | 13.20 | — | — |

## Median seed RMSE (m)

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | 2.90 | **1.45** | 2.22 | — | — |
| C8_clear_speed_s_dropout | **5.15** | 7.85 | 8.48 | — | — |
| W3_night_rough_s | **5.69** | 6.65 | 6.47 | — | — |
| C10_huge_waves_s_dropout | **5.42** | 12.26 | 13.94 | — | — |

## Broken, error > 10 m (% time)

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | **0.0** | **0.0** | **0.0** | — | — |
| C8_clear_speed_s_dropout | **1.4** | 25.8 | 26.3 | — | — |
| W3_night_rough_s | **2.0** | 14.5 | 12.2 | — | — |
| C10_huge_waves_s_dropout | **4.5** | 49.8 | 39.2 | — | — |

## Triangle IoU

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | 0.805 | **0.875** | 0.829 | — | — |
| C8_clear_speed_s_dropout | **0.723** | 0.647 | 0.620 | — | — |
| W3_night_rough_s | **0.688** | 0.643 | 0.637 | — | — |
| C10_huge_waves_s_dropout | **0.697** | 0.408 | 0.525 | — | — |

## Min boat separation (m)

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | **26.3** | 26.0 | 25.7 | — | — |
| C8_clear_speed_s_dropout | **25.4** | 23.6 | 22.5 | — | — |
| W3_night_rough_s | **24.8** | 22.2 | 21.9 | — | — |
| C10_huge_waves_s_dropout | **19.5** | 15.8 | 17.8 | — | — |

## Fresh detection (% frames)

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | **100.0** | **100.0** | **100.0** | — | — |
| C8_clear_speed_s_dropout | **86.7** | **86.7** | **86.7** | — | — |
| W3_night_rough_s | 100.0 | **100.0** | 99.9 | — | — |
| C10_huge_waves_s_dropout | **84.1** | 60.3 | 78.6 | — | — |

## Recovery after 2 s dropout (s)

| Case | Kalman + leader speed (radio) | Kalman, vision + own speed | Kalman, vision only (strict) | Kalman OFF, vision estimate | No bbox filtering, vision estimate |
|---|---:|---:|---:|---:|---:|
| C0_calm_circle | — | — | — | — | — |
| C8_clear_speed_s_dropout | **0.9** | **0.9** | **0.9** | — | — |
| W3_night_rough_s | — | — | — | — | — |
| C10_huge_waves_s_dropout | **0.9** | **0.9** | **0.9** | — | — |

