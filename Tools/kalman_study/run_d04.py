#!/usr/bin/env python3
"""d04+ runner: adds range/speed arms to the unchanged run_candidate.py, with sharding.

New arms (both use the shared range/speed law, range_speed_policy.py):
  on_rs   KF: FusionRangeTracker (vision + own speed + leader-speed telemetry, gating)
  off_rs  non-KF: matched EMA tracker; range/rate from EMA area (vision only)
  raw     NO tracker filter: raw boxes, zero rates, no coasting (hold 0 s), same controller as on_rs
  raw_nogate  as raw, and ALSO no production bbox track gate / reacquire bias (no bbox filtering at all)
Existing arms (on_ego, on, off, off_short) are patched exactly as in e01.

Sharding: `--shard i --nshards n` runs jobs with index % n == i in its own private
project /tmp/usv-d04-<i> on bridge port 47540+i. All shards build the identical
plan/manifest (asserted). Evaluation requires --protocol (hash stored).
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import run_robust as base
import run_candidate as rc
from range_speed_policy import patch_control as patch_range_speed

ARMS = rc.ARMS+['on_rs', 'off_rs', 'raw', 'raw_nogate']
EXTRA = ['Tools/kalman_study/run_d04.py', 'Tools/kalman_study/fusion_tracker.py', 'Tools/kalman_study/rs_hooks.py',
         'Tools/kalman_study/range_speed_policy.py', 'Tools/kalman_study/raw_tracker.py']
ADAPTER = rc.ADAPTER


def patch_python(project, job):
    rc.patch_python(project, job)   # e01 patches; *_rs/raw arms behave as plain on/off here
    if job['arm'] in ('on_rs', 'off_rs', 'raw', 'raw_nogate'):
        for name in ['ego_tracker.py', 'fusion_tracker.py', 'rs_hooks.py', 'raw_tracker.py']:
            shutil.copy2(base.HERE/name, project/'Assets'/name)
        vision = project/'Assets/usv/vision.py'
        text = vision.read_text()
        assert text.count(ADAPTER) == 1
        text = text.replace(ADAPTER, ADAPTER+'import rs_hooks\nupdate_track_prediction = rs_hooks.update\ncoast_track_prediction = rs_hooks.coast\n')
        if job['arm'] in ('raw', 'raw_nogate'):
            assert text.count('hold_window = 3.0') == 1
            text = text.replace('hold_window = 3.0', 'hold_window = 0.0  # raw arm: no coasting')
            text += 'import raw_tracker\nrs_hooks.RobustTracker = raw_tracker.RawTracker\n'
        compile(text, str(vision), 'exec')
        vision.write_text(text)
        control = project/'Assets/usv/control.py'
        control.write_text(patch_range_speed(control.read_text()))
        if job['arm'] == 'raw_nogate':
            config = project/'Assets/usv/config.py'
            text = config.read_text()
            import re
            for key, value in [('TRACK_GATE_ENABLE', 'False'), ('TRACK_GATE_CLASS_AGNOSTIC_ENABLE', 'False'), ('TRACK_REACQUIRE_BIAS', '0.0')]:
                text, n = re.subn(r'^'+key+r'\s*=.*$', key+' = '+value, text, flags=re.M)
                assert n == 1, key
            config.write_text(text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['development', 'evaluation'], default='development')
    p.add_argument('--cases')
    p.add_argument('--seeds')
    p.add_argument('--arms', default='on_rs,off_rs,off_short')
    p.add_argument('--tag', required=True)
    p.add_argument('--protocol', type=Path)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--nshards', type=int, default=1)
    a = p.parse_args()
    protocol_sha = None
    if a.stage == 'evaluation':
        payload = a.protocol.read_bytes()
        protocol_sha = hashlib.sha256(payload).hexdigest()
        groups = json.loads(payload)['groups']
    else:
        groups = [dict(cases=a.cases.split(','), seeds=[int(s) for s in a.seeds.split(',')], arms=a.arms.split(','))]
    data = base.ROOT/'Experiments/KalmanStudy'/('robust_'+a.stage)/a.tag
    jobs = []
    for g in groups:
        seeds = [int(s) for s in g['seeds']]
        if a.stage == 'evaluation':
            assert not set(seeds) & rc.DEV_SEEDS, 'development seeds in evaluation'
        assert set(g['arms']) <= set(ARMS), g['arms']
        cases = [c for prefix in g['cases'] for c in rc.ALL_CASES if c['case'].split('_')[0] == prefix]
        assert len(cases) == len(g['cases'])
        jobs += rc.plan(cases, seeds, g['arms'], data)
    for i, job in enumerate(jobs):
        job['port'] = 47540+i % a.nshards
    base.WORK = Path(f'/tmp/usv-d04-{a.shard}')
    rc.prepare()
    data.mkdir(parents=True, exist_ok=True)
    hashes = rc.source_hashes()
    for name in EXTRA:
        hashes[name] = hashlib.sha256((base.ROOT/name).read_bytes()).hexdigest()
    manifest = dict(jobs=jobs, source_sha256=hashes, stage=a.stage, protocol_sha256=protocol_sha, nshards=a.nshards,
                    binary_sha256=hashlib.sha256((base.WORK/'build/study.x86_64').read_bytes()).hexdigest(),
                    arms_description=__doc__)
    path = data/'manifest.json'
    if path.exists():
        assert json.loads(path.read_text()) == manifest, 'Source/plan changed: choose a new tag'
    else:
        path.write_text(json.dumps(manifest, indent=2)+'\n')
    base.legacy.WORK = base.WORK
    base.legacy.patch_python = patch_python
    for i, job in enumerate(jobs):
        if i % a.nshards != a.shard:
            continue
        print(f'RUN {i+1}/{len(jobs)}', job['case'], job['seed'], job['arm'], flush=True)
        base.legacy.run(job)


if __name__ == '__main__':
    main()
