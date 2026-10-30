# Completed retrospective ablation tables

Positive reduction = lower RMSE; positive broken reduction = less formation-break time. No simulations launched.

## Primary cases: e02 plus posthoc e02x raw_nogate

|Case|Method|n|Mean RMSE m|Median RMSE m|Broken %|Catastrophic >50m|
|---|---|---:|---:|---:|---:|---:|
|C10_huge_waves_s_dropout|raw_nogate|8|13.92|9.00|42.4|0/8|
|C10_huge_waves_s_dropout|raw|8|12.77|8.64|37.3|0/8|
|C10_huge_waves_s_dropout|off_rs|8|24.57|7.93|29.5|1/8|
|C10_huge_waves_s_dropout|on_rs|8|17.43|4.70|8.1|1/8|
|C10_huge_waves_s_dropout|off_short|8|23.76|8.41|28.3|1/8|
|C8_clear_speed_s_dropout|raw_nogate|8|7.84|7.85|24.8|0/8|
|C8_clear_speed_s_dropout|raw|8|7.83|7.84|24.7|0/8|
|C8_clear_speed_s_dropout|off_rs|8|5.06|4.64|4.6|0/8|
|C8_clear_speed_s_dropout|on_rs|8|4.32|4.28|0.0|0/8|
|C8_clear_speed_s_dropout|off_short|8|7.63|7.38|23.1|0/8|
|W1_rain015_rough_s|raw_nogate|8|76.70|74.98|83.3|8/8|
|W1_rain015_rough_s|raw|8|65.28|65.24|82.0|8/8|
|W1_rain015_rough_s|off_rs|8|13.97|6.95|17.0|0/8|
|W1_rain015_rough_s|on_rs|8|6.50|5.45|2.2|0/8|
|W1_rain015_rough_s|off_short|8|20.27|11.77|52.4|1/8|

## Scenario-balanced primary aggregation (8 seed blocks)

|Treatment|Baseline|Geometric reduction %|Blocks favoring|Broken reduction pp|
|---|---|---:|---:|---:|
|raw|raw_nogate|+7.20|8/8|+2.16|
|off_rs|raw|+53.25|7/8|+30.94|
|on_rs|off_rs|+33.25|6/8|+13.58|
|on_rs|raw|+68.80|8/8|+44.52|
|on_rs|off_short|+48.90|8/8|+31.13|

## laps_135s_descriptive: mean RMSE, all cases (2 seeds; descriptive)

|Case|raw_nogate|raw|off_rs|on_rs|off_short|
|---|---:|---:|---:|---:|---:|
|L01_lap_calm|5.07|5.07|2.96|2.89|6.16|
|L02_lap_rough_sea1.5|4.70|4.68|2.96|2.52|5.72|
|L03_lap_huge_waves_sea3|26.71|286.19|189.82|3.27|117.33|
|L04_lap_light_rain0.15|883.24|748.51|461.68|208.04|481.26|
|L05_lap_rain0.25|912.37|938.10|513.42|168.29|625.34|
|L06_lap_rain0.4|1023.75|905.93|798.46|608.87|875.42|
|L07_lap_heavy_rain1.0|1277.82|1184.21|1018.30|1134.27|1130.18|
|L08_lap_night|1243.55|1243.55|1242.60|1241.18|1238.59|
|L09_lap_night_rain0.15|996.83|1042.20|1046.94|744.98|855.58|
|L10_lap_dark_storm|796.50|957.10|575.52|573.27|678.65|

## nonfixed_weather_85s_descriptive: mean RMSE, all cases (2 seeds; descriptive)

|Case|raw_nogate|raw|off_rs|on_rs|off_short|
|---|---:|---:|---:|---:|---:|
|WL1_lap_rain0.15_nonfixed|380.64|not run|not run|170.18|358.10|
|WL2_lap_rain0.25_nonfixed|444.88|not run|not run|245.25|361.04|
|WL3_lap_night_nonfixed|501.90|not run|not run|532.88|495.90|
|WL4_lap_night_rain0.15_nonfixed|515.73|not run|not run|460.59|490.44|
