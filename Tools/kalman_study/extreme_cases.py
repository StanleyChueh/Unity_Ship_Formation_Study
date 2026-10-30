"""Cases added after d02 (disclosed in ROBUST_D03.md). Same binary; no renderer change.

C10 combines the original huge-wave sea state with the variable-speed/S-turn
leader and scheduled two-second measurement losses. W* cases are weather
observability probes with natural (unscheduled) detector losses; they are
selected for evaluation by a predeclared visibility rule, never by ON/OFF result.
"""
EXTREME_CASES = [
    dict(case='C10_huge_waves_s_dropout', sea=3.0, rain=0, dark=False, fog=0, motion='variable', radius=360, gap=2.0),
    dict(case='W1_rain015_rough_s', sea=1.5, rain=0.15, dark=False, fog=0.008, motion='variable', radius=360, gap=0),
    dict(case='W2_rain025_rough_s', sea=1.5, rain=0.25, dark=False, fog=0.008, motion='variable', radius=360, gap=0),
    dict(case='W3_night_rough_s', sea=1.5, rain=0, dark=True, fog=0.008, motion='variable', radius=360, gap=0),
    dict(case='W4_night_rain015_rough_s', sea=1.5, rain=0.15, dark=True, fog=0.008, motion='variable', radius=360, gap=0),
]
