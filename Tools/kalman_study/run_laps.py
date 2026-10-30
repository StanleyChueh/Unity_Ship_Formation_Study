#!/usr/bin/env python3
"""Run the full-lap circle cases (lap_cases.py) with the unchanged run_d04.py arms.

Only adds the L* cases and sets each job's duration to the case's lap_duration;
patching, arms, sharding, manifest/freeze logic are run_d04.py's.
"""
import hashlib
import sys

import run_d04
import run_candidate as rc
from lap_cases import LAP_CASES

rc.ALL_CASES = rc.ALL_CASES+LAP_CASES
_plan = rc.plan


def plan(*args, **kwargs):
    jobs = _plan(*args, **kwargs)
    for job in jobs:
        if 'lap_duration' in job:
            job['duration'] = job['lap_duration']
    return jobs


rc.plan = plan
_hashes = rc.source_hashes


def source_hashes():
    result = _hashes()
    for name in ['Tools/kalman_study/run_laps.py', 'Tools/kalman_study/lap_cases.py']:
        result[name] = hashlib.sha256((run_d04.base.ROOT/name).read_bytes()).hexdigest()
    return result


rc.source_hashes = source_hashes

if __name__ == '__main__':
    run_d04.main()
