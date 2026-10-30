"""W1-W4 weather on a NON-FIXED trajectory that still completes a full circle (e04_wlaps).

Uses the simulator's built-in 'unexpected' leader motion: straight at 18 m/s until
t = 22 s, then a constant 0.11 rad/s turn (radius ~164 m) through a full 360 deg,
completed at t = 22 + 2*pi/0.11 = 79.1 s; 85 s of motion covers the lap. Weather is
identical to W1-W4 (natural detector losses only, no scheduled dropouts).
"""
WLAP_DURATION_S = 85

WLAP_CASES = [dict(case=name, sea=1.5, rain=rain, dark=dark, fog=0.008, motion='unexpected', radius=360, gap=0,
                   lap_duration=WLAP_DURATION_S)
              for name, rain, dark in [
                  ('WL1_lap_rain0.15_nonfixed', 0.15, False),
                  ('WL2_lap_rain0.25_nonfixed', 0.25, False),
                  ('WL3_lap_night_nonfixed', 0.0, True),
                  ('WL4_lap_night_rain0.15_nonfixed', 0.15, True),
              ]]
