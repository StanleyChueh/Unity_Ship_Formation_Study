"""PR-course e08: sea states beyond anything run before (sea 3.0 = Hs ~2.45 m was the maximum).
Same frozen binary; the sea value only sets water.lgWaveHeight at runtime (StudyRig.SetWeather), so no rebuild.
Leader on the steady R360 circle (as the L laps) so differences come from waves and weather, with the usual
2 s scheduled bbox dropouts. Defined before any run; see Documentation/PR_Course/eval_e08_extreme_waves_protocol.json."""
EXTREME_WAVE_CASES = [dict(case=name, sea=sea, rain=rain, dark=dark, fog=fog, motion='circle', radius=360, gap=2.0)
                      for name, sea, rain, dark, fog in [
                          ('X1_sea4_clear', 4.0, 0.0, False, 0.0),
                          ('X2_sea5_clear', 5.0, 0.0, False, 0.0),
                          ('X3_sea4_dark_storm', 4.0, 1.0, True, 0.02),
                          ('X4_sea4_heavy_rain', 4.0, 1.0, False, 0.032),
                          ('X5_sea3_dark_storm', 3.0, 1.0, True, 0.02),
                      ]]
