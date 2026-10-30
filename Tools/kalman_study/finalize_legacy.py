#!/usr/bin/env python3
"""Archive and verify the frozen original study before production integration."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from analyze import DATA,REPORT,ROOT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wait',action='store_true');args=parser.parse_args()
    manifest=json.loads((DATA/'manifest.json').read_text())
    if args.wait:
        print('Waiting for all frozen baseline jobs.',flush=True)
        while not all((Path(j['output'])/'bridge.complete').exists() and (Path(j['output'])/'unity.complete').exists() for j in manifest['jobs']):time.sleep(10)
    archive=DATA/'source_snapshot';archive.mkdir(exist_ok=True)
    for name,expected in manifest['source_sha256'].items():
        source=ROOT/name;assert hashlib.sha256(source.read_bytes()).hexdigest()==expected,name
        dest=archive/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    for script in ['analyze.py','audit_study.py']:
        subprocess.run([sys.executable,str(Path(__file__).parent/script)],check=True)
    py='/home/stanley/miniconda3/envs/unity_boat/bin/python'
    subprocess.run([py,str(Path(__file__).parent/'replay_estimators.py')],check=True)
    subprocess.run([sys.executable,str(Path(__file__).parent/'make_figures.py')],check=True)
    (REPORT/'legacy-finalization.complete').write_text('Original sources archived, full matrix analyzed, audit passed, camera keyframes and figures generated.\n')
    print('Frozen legacy study finalized.',flush=True)

if __name__=='__main__':main()
