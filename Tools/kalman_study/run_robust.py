#!/usr/bin/env python3
"""Separate development/evaluation of robust KF; frozen baseline stays intact."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

import run_study as legacy

ROOT=legacy.ROOT
HERE=legacy.HERE
WORK=Path('/tmp/usv-robust-study')
BASELINE_WORK=legacy.WORK
DATA=ROOT/'Experiments/KalmanStudy/robust_development'
legacy_patch_python=legacy.patch_python


def patch_python(project,job):
    legacy_patch_python(project,job)
    for name in ['robust_tracker.py','robust_hooks.py']:
        shutil.copy2(HERE/name,project/'Assets'/name)
    config=project/'Assets/usv/config.py'
    text=config.read_text()
    # One shared controller: remove legacy KF-only derivative braking/alpha
    # adjustments equally in both arms. All other production gains unchanged.
    import re
    for key in ['KF_APPROACH_THROTTLE_D_GAIN','KF_APPROACH_ALPHA_GAIN']:
        text,n=re.subn(r'^'+key+r'\s*=.*$',key+' = 0.0',text,flags=re.M);assert n==1
    config.write_text(text)
    path=project/'Assets/usv/vision.py';text=path.read_text()
    anchor='                        if state.get("last_detection_time", 0.0) > 0.0:\n                            center_offset = blend_value(previous_offset, center_offset, TRACK_OFFSET_ALPHA)\n                            best_area = blend_value(previous_area, best_area, TRACK_AREA_ALPHA)'
    assert text.count(anchor)==1
    text=text.replace(anchor,'                        # Smoothing is performed once, in the shared robust/EMA adapter.')
    anchor='                        state["target_detected"] = True\n                        state["target_stale"] = False'
    assert text.count(anchor)==1
    text=text.replace(anchor,'                        if role == "front":\n                            center_offset, best_area = robust_hooks.posterior(state, center_offset, best_area)\n'+anchor)
    text=text.replace('hold_window = KF_COAST_MAX_SEC if kf_active else TRACK_HOLD_SEC','hold_window = 3.0')
    text=text.replace('within_hold = state.get("prediction_confidence", 0.0) >= KF_COAST_MIN_CONF','within_hold = True # identical predeclared lifetime in both arms')
    text+='\n# Explicit experiment adapter, applied after original function definitions.\nimport robust_hooks\nupdate_track_prediction = robust_hooks.update\ncoast_track_prediction = robust_hooks.coast\n'
    compile(text,str(path),'exec');path.write_text(text)


def source_hashes():
    files=[HERE/n for n in ['robust_tracker.py','robust_hooks.py','run_robust.py','run_study.py','bridge.py','study_runtime.py']]
    files += [ROOT/'Assets/usv'/n for n in ['vision.py','control.py','config.py','state.py','kalman.py','helpers.py']]
    files += [ROOT/'best_realistic.pt']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def prepare():
    (WORK/'project/Assets').mkdir(parents=True,exist_ok=True)
    src=BASELINE_WORK/'project/Assets/usv'
    shutil.copytree(src,WORK/'project/Assets/usv',dirs_exist_ok=True)
    # No plant/rendering changes: reuse byte-identical legacy Unity binary.
    if not (WORK/'build').exists(): (WORK/'build').symlink_to(BASELINE_WORK/'build',target_is_directory=True)


def main():
    global DATA
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['development','evaluation'],default='development')
    parser.add_argument('--cases',default='C0,C1,C4,C5')
    parser.add_argument('--seeds',default='1701')
    parser.add_argument('--duration',type=int,default=60)
    parser.add_argument('--tag',default='d01')
    parser.add_argument('--wait-baseline',action='store_true')
    args=parser.parse_args()
    seeds=[int(x) for x in args.seeds.split(',')]
    if args.stage=='evaluation' and any(s in [1701,1702,1703] for s in seeds):raise ValueError('Development seeds cannot be held-out evaluation seeds')
    DATA=ROOT/'Experiments/KalmanStudy'/('robust_'+args.stage)/args.tag
    if args.wait_baseline:
        import time
        manifest=json.loads((ROOT/'Experiments/KalmanStudy/v2/manifest.json').read_text())
        print('Waiting for frozen legacy matrix to finish before GPU use.',flush=True)
        while not all((Path(j['output'])/'bridge.complete').exists() and (Path(j['output'])/'unity.complete').exists() for j in manifest['jobs']):time.sleep(10)
    prepare();DATA.mkdir(parents=True,exist_ok=True)
    cases=[c for c in legacy.CASES if c['case'][:2] in args.cases.split(',')]
    jobs=[]
    for case in cases:
        for seed in seeds:
            arms=['on','off'];random.Random(seed+int(case['case'][1])*91).shuffle(arms)
            for arm in arms:
                name=f'{case["case"]}_{seed}_{arm}'
                jobs.append(dict(case,seed=seed,arm=arm,duration=args.duration,port=47510,output=str(DATA/'runs'/name)))
    manifest=dict(jobs=jobs,source_sha256=source_hashes(),legacy_manifest_sha256=hashlib.sha256((ROOT/'Experiments/KalmanStudy/v2/manifest.json').read_bytes()).hexdigest(),
                  binary_sha256=hashlib.sha256((WORK/'build/study.x86_64').read_bytes()).hexdigest(),stage=args.stage,
                  changes='Raw selected offset and log area; timestamp-correct robust Kalman vs EMA; shared controller without KF-only derivative damper; identical 3 s coasting/lifetime/confidence; no additional sensors or GT.')
    path=DATA/'manifest.json'
    if path.exists():assert json.loads(path.read_text())==manifest,'Source/plan changed after run started: choose new tag'
    else:path.write_text(json.dumps(manifest,indent=2)+'\n')
    original_patch=legacy.patch_python
    # patch_python above calls the original, not the redirected callable.
    globals()['legacy_patch_python']=original_patch
    legacy.WORK=WORK
    legacy.patch_python=patch_python
    for job in jobs:
        print('RUN',job['case'],job['seed'],job['arm'],flush=True)
        legacy.run(job)


if __name__=='__main__':main()
