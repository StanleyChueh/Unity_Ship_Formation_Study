#!/usr/bin/env python3
"""NEW development candidate: d01 estimator plus shared credible-coast policy.

This wrapper leaves the frozen d01 files unchanged. Extra clear-weather cases
are disclosed in OBSERVABILITY_AMENDMENT.md. Evaluation is intentionally blocked
until a candidate and a separate prospective evaluation protocol are selected.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import run_robust as base
from observable_cases import OBSERVABLE_CASES
from shared_coast_policy import patch_control


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--wait-native',action='store_true')
    options,remaining=parser.parse_known_args()
    if '--stage' in remaining and remaining[remaining.index('--stage')+1]=='evaluation':
        raise RuntimeError('Freeze a separate evaluation protocol before held-out trials')
    if options.wait_native:
        p=base.ROOT/'Experiments/KalmanStudy/v2/realtime/runs.json'
        print('Waiting for queued native-app original pair before another Unity/GPU batch.',flush=True)
        while not p.exists():time.sleep(10)
        assert len(json.loads(p.read_text()))==2
    tag=remaining[remaining.index('--tag')+1] if '--tag' in remaining else 'd02'
    data=base.ROOT/'Experiments/KalmanStudy/robust_development'/tag
    data.mkdir(parents=True,exist_ok=True)
    amendment=dict(candidate='d02',description='d01 estimators with shared confidence-aware stale throttle/steering attenuation, applied equally to KF and EMA; disclosed clear-weather C8/C9 cases.',
                   document='Documentation/KalmanStudy/ROBUST_D02.md')
    path=data/'candidate-amendment.json'
    if path.exists():assert json.loads(path.read_text())==amendment
    else:path.write_text(json.dumps(amendment,indent=2)+'\n')
    base.legacy.CASES=base.legacy.CASES+OBSERVABLE_CASES
    old_prepare=base.prepare
    def prepare():
        old_prepare()
        shutil.copy2(base.ROOT/'Assets/depth_Anything.py',base.WORK/'project/Assets/depth_Anything.py')
    base.prepare=prepare
    old_patch=base.patch_python
    def patch(project,job):
        old_patch(project,job)
        p=project/'Assets/usv/control.py';p.write_text(patch_control(p.read_text()))
    base.patch_python=patch
    old_hashes=base.source_hashes
    def hashes():
        result=old_hashes()
        for name in ['Tools/kalman_study/run_robust_next.py','Tools/kalman_study/observable_cases.py',
                     'Tools/kalman_study/shared_coast_policy.py','Assets/depth_Anything.py',
                     'Documentation/KalmanStudy/OBSERVABILITY_AMENDMENT.md','Documentation/KalmanStudy/ROBUST_D02.md']:
            result[name]=hashlib.sha256((base.ROOT/name).read_bytes()).hexdigest()
        return result
    base.source_hashes=hashes
    sys.argv=[sys.argv[0]]+remaining
    base.main()


if __name__=='__main__':main()
