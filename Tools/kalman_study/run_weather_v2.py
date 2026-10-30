#!/usr/bin/env python3
"""Re-run the weather laps (L04-L10, WL1-WL4) with the weather-trained detector best_realistic_v2.pt (e05).

Identical to run_laps.py / run_wlaps.py (unchanged run_d04.py arms, patching, sharding,
manifest/freeze logic). The ONLY change is the detector weights: after all arm patches,
YOLO_MODEL_PATH in the run's private config.py is set to best_realistic_v2.pt (asserted).
"""
import hashlib
import re

import run_d04
import run_candidate as rc
from lap_cases import LAP_CASES
from wlap_cases import WLAP_CASES

MODEL = run_d04.base.ROOT/'best_realistic_v2.pt'
rc.ALL_CASES = rc.ALL_CASES+LAP_CASES+WLAP_CASES
_plan = rc.plan


def plan(*args, **kwargs):
    jobs = _plan(*args, **kwargs)
    for job in jobs:
        if 'lap_duration' in job:
            job['duration'] = job['lap_duration']
        job['detector'] = MODEL.name
    return jobs


rc.plan = plan
_hashes = rc.source_hashes


def source_hashes():
    result = _hashes()
    for name in ['Tools/kalman_study/run_weather_v2.py', 'Tools/kalman_study/lap_cases.py', 'Tools/kalman_study/wlap_cases.py', 'best_realistic_v2.pt']:
        result[name] = hashlib.sha256((run_d04.base.ROOT/name).read_bytes()).hexdigest()
    return result


rc.source_hashes = source_hashes
_patch = run_d04.patch_python


def patch_python(project, job):
    _patch(project, job)
    config = project/'Assets/usv/config.py'
    text, n = re.subn(r'^YOLO_MODEL_PATH\s*=.*$', 'YOLO_MODEL_PATH = '+repr(str(MODEL)), config.read_text(), flags=re.M)
    assert n == 1
    config.write_text(text)


run_d04.patch_python = patch_python

if __name__ == '__main__':
    run_d04.main()
