"""Full-lap FIXED circle trajectory under every weather/wave level (report package, e03).

Leader: constant 18 m/s on the R360 circle used by C0-C3; one lap = 2*pi*360/18
= 126 s plus ~3 s lost while accelerating from rest, so 135 s of motion covers a
complete lap. Scheduled 2 s bbox dropouts every 18 s from t = 20 s (7 per lap) in
every condition, because bbox loss is the subject of the study. Weather values
match the earlier cases at the same level (C0/C1/C2/C3/C5, W1-W4).
"""
LAP_DURATION_S = 135

LAP_CASES = [dict(case=name, sea=sea, rain=rain, dark=dark, fog=fog, motion='circle', radius=360, gap=2.0, lap_duration=LAP_DURATION_S)
             for name, sea, rain, dark, fog in [
                 ('L01_lap_calm', 0.55, 0.0, False, 0.0),
                 ('L02_lap_rough_sea1.5', 1.5, 0.0, False, 0.0),
                 ('L03_lap_huge_waves_sea3', 3.0, 0.0, False, 0.0),
                 ('L04_lap_light_rain0.15', 1.5, 0.15, False, 0.008),
                 ('L05_lap_rain0.25', 1.5, 0.25, False, 0.008),
                 ('L06_lap_rain0.4', 1.0, 0.4, False, 0.01),
                 ('L07_lap_heavy_rain1.0', 0.9, 1.0, False, 0.032),
                 ('L08_lap_night', 1.5, 0.0, True, 0.008),
                 ('L09_lap_night_rain0.15', 1.5, 0.15, True, 0.008),
                 ('L10_lap_dark_storm', 1.5, 1.0, True, 0.02),
             ]]
