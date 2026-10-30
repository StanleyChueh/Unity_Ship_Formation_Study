#!/usr/bin/env python3
"""Multi-arm runner for d03+ (development) and frozen held-out evaluation.

Wraps the unchanged d01 runner (run_robust.py) and d02 shared coast policy.
Arms (all share raw measurements, controller, 3 s coast policy, plant, binary):
  on_ego    candidate: d02 offset KF + ego-motion range KF (ego_tracker.py)
  on        d02 image-space robust KF
  off       matched non-Kalman EMA + finite-difference velocity, 3 s lifetime
  off_short same EMA predictor with the production non-Kalman 0.6 s hold
Evaluation requires --protocol: a frozen JSON whose hash is stored in the
manifest, listing the exact cases/seeds/arms; anything else is refused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil

import run_robust as base
from observable_cases import OBSERVABLE_CASES
from extreme_cases import EXTREME_CASES
from shared_coast_policy import patch_control

ARMS = ['on_ego', 'on', 'off', 'off_short']
DEV_SEEDS = {1701, 1702, 1703}
ALL_CASES = base.legacy.CASES+OBSERVABLE_CASES+EXTREME_CASES
EXTRA_SOURCES = ['Tools/kalman_study/run_candidate.py', 'Tools/kalman_study/run_robust_next.py',
                 'Tools/kalman_study/observable_cases.py', 'Tools/kalman_study/extreme_cases.py',
                 'Tools/kalman_study/shared_coast_policy.py', 'Tools/kalman_study/ego_tracker.py',
                 'Tools/kalman_study/ego_hooks.py', 'Assets/depth_Anything.py']
ADAPTER = 'import robust_hooks\nupdate_track_prediction = robust_hooks.update\ncoast_track_prediction = robust_hooks.coast\n'


def patch_python(project, job):
    base.patch_python(project, job)   # d01: robust adapter, shared controller, 3 s lifetime
    control = project/'Assets/usv/control.py'
    control.write_text(patch_control(control.read_text()))   # d02 shared coast policy
    vision = project/'Assets/usv/vision.py'
    text = vision.read_text()
    if job['arm'] == 'on_ego':
        for name in ['ego_tracker.py', 'ego_hooks.py']:
            shutil.copy2(base.HERE/name, project/'Assets'/name)
        assert text.count(ADAPTER) == 1
        text = text.replace(ADAPTER, ADAPTER+'import ego_hooks\nupdate_track_prediction = ego_hooks.update\ncoast_track_prediction = ego_hooks.coast\n')
    elif job['arm'] == 'off_short':
        assert text.count('hold_window = 3.0') == 1
        text = text.replace('hold_window = 3.0', 'hold_window = 0.6  # production TRACK_HOLD_SEC for the non-Kalman tracker')
    compile(text, str(vision), 'exec')
    vision.write_text(text)


def prepare():
    base.prepare()
    shutil.copy2(base.ROOT/'Assets/depth_Anything.py', base.WORK/'project/Assets/depth_Anything.py')


def source_hashes():
    result = base.source_hashes()
    for name in EXTRA_SOURCES:
        result[name] = hashlib.sha256((base.ROOT/name).read_bytes()).hexdigest()
    return result


def plan(cases, seeds, arms, data):
    jobs = []
    for index, case in enumerate(cases):
        for seed in seeds:
            order = list(arms)
            random.Random(seed*7919+index*91).shuffle(order)
            for arm in order:
                name = f'{case["case"]}_{seed}_{arm}'
                jobs.append(dict(case, seed=seed, arm=arm, duration=60, port=47520, output=str(data/'runs'/name)))
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['development', 'evaluation'], default='development')
    parser.add_argument('--cases', help='comma-separated case prefixes, e.g. C8,C10')
    parser.add_argument('--seeds')
    parser.add_argument('--arms', default=','.join(ARMS))
    parser.add_argument('--tag', required=True)
    parser.add_argument('--protocol', type=Path, help='frozen evaluation protocol JSON')
    args = parser.parse_args()
    protocol_sha = None
    if args.stage == 'evaluation':
        if args.protocol is None:
            raise RuntimeError('Evaluation requires a frozen --protocol')
        payload = args.protocol.read_bytes()
        protocol_sha = hashlib.sha256(payload).hexdigest()
        spec = json.loads(payload)
        groups = spec['groups']
    else:
        groups = [dict(cases=args.cases.split(','), seeds=[int(s) for s in args.seeds.split(',')], arms=args.arms.split(','))]
    data = base.ROOT/'Experiments/KalmanStudy'/('robust_'+args.stage)/args.tag
    jobs = []
    for group in groups:
        seeds = [int(s) for s in group['seeds']]
        if args.stage == 'evaluation' and set(seeds) & DEV_SEEDS:
            raise ValueError('Development seeds cannot be held-out evaluation seeds')
        if args.stage == 'development' and not set(seeds) <= DEV_SEEDS:
            raise ValueError('Development uses seeds 1701-1703 only')
        assert set(group['arms']) <= set(ARMS), group['arms']
        cases = [c for prefix in group['cases'] for c in ALL_CASES if c['case'].split('_')[0] == prefix]
        assert len(cases) == len(group['cases']), group['cases']
        jobs += plan(cases, seeds, group['arms'], data)
    names = [j['output'] for j in jobs]
    assert len(names) == len(set(names)), 'duplicate jobs'
    prepare()
    data.mkdir(parents=True, exist_ok=True)
    manifest = dict(jobs=jobs, source_sha256=source_hashes(), stage=args.stage, protocol_sha256=protocol_sha,
                    legacy_manifest_sha256=hashlib.sha256((base.ROOT/'Experiments/KalmanStudy/v2/manifest.json').read_bytes()).hexdigest(),
                    binary_sha256=hashlib.sha256((base.WORK/'build/study.x86_64').read_bytes()).hexdigest(),
                    arms_description=__doc__)
    path = data/'manifest.json'
    if path.exists():
        assert json.loads(path.read_text()) == manifest, 'Source/plan changed after run started: choose new tag'
    else:
        path.write_text(json.dumps(manifest, indent=2)+'\n')
    base.legacy.WORK = base.WORK
    base.legacy.patch_python = patch_python
    for index, job in enumerate(jobs):
        print(f'RUN {index+1}/{len(jobs)}', job['case'], job['seed'], job['arm'], flush=True)
        base.legacy.run(job)


if __name__ == '__main__':
    main()
