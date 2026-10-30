#!/usr/bin/env python3
"""Supplementary ON/OFF check with the original asynchronous app.main loop."""
import json
import argparse
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/boat_dataset'))
import test_model_formation as normal

DATA=ROOT/'Experiments/KalmanStudy/v2/realtime'
normal.OUT=DATA
original_clone=normal.clone_project
original_patch=normal.instrument_python


def isolated_clone(work):
    project=original_clone(work)
    p=project/'Assets/SimpleMove.cs';text=p.read_text()
    p.write_text(text.replace('Input.GetAxis("Vertical")','0.0f').replace('Input.GetAxis("Horizontal")','0.0f'))
    return project


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only',action='store_true');parser.add_argument('--no-build',action='store_true')
    parser.add_argument('--wait-for',type=Path,help='Wait for another isolated batch to finish before using Unity/GPU')
    args=parser.parse_args()
    if args.wait_for:
        import time
        print('Waiting for preceding batch and its source-freeze check.',flush=True)
        while not (args.wait_for/'source-freeze-check.json').exists():time.sleep(10)
        check=json.loads((args.wait_for/'source-freeze-check.json').read_text())
        assert check['status']=='passed'

    normal.WORK.mkdir(exist_ok=True);DATA.mkdir(parents=True,exist_ok=True)
    normal.clone_project=isolated_clone
    if not args.no_build:normal.build()
    if args.build_only:return
    records=[]
    for arm in ['off','on']:
        def patch(project,output,model,radius):
            original_patch(project,output,model,radius)
            p=project/'Assets/usv/config.py';text=p.read_text()
            for key,value in dict(ENABLE_KALMAN_FILTER=arm=='on',SIMULATED_BBOX_LOSS_ENABLE=True,
                                  SIMULATED_BBOX_LOSS_DURATION_SEC=2.0,SIMULATED_BBOX_LOSS_INTERVAL_SEC=18.0,
                                  SIMULATED_BBOX_LOSS_START_DELAY_SEC=20.0,SIMULATED_BBOX_LOSS_SIDES='Both').items():
                text,n=re.subn(r'^'+key+r'\s*=.*$',key+' = '+repr(value),text,flags=re.M);assert n==1,key
            p.write_text(text)
        normal.instrument_python=patch
        records.append(normal.run(arm,ROOT/'best_realistic.pt','turn_dropout',180,70))
    (DATA/'runs.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Normal application check completed.')


if __name__=='__main__':main()
