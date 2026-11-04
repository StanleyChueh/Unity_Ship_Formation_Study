#!/usr/bin/env python3
"""PR-course e08 runner: the e07 vision-only stack (detector best_realistic_v2.pt) plus the extreme-wave cases.
Usage: python3 run_extreme_waves.py --stage evaluation --tag e08_extreme_waves \
         --protocol ../../Documentation/PR_Course/eval_e08_extreme_waves_protocol.json --shard 0 --nshards 2"""
import run_vision_only  # noqa: F401  (registers vision-only arms, detector v2, lap cases)
import run_candidate as rc
import run_d04
from extreme_wave_cases import EXTREME_WAVE_CASES

rc.ALL_CASES = rc.ALL_CASES + EXTREME_WAVE_CASES

if __name__ == '__main__':
    run_d04.main()
