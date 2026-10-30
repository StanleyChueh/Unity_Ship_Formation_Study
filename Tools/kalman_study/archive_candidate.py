#!/usr/bin/env python3
"""Archive candidate sources before execution completes and check the freeze."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from analyze import ROOT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--wait',action='store_true');args=parser.parse_args()
    data=args.directory.resolve();path=data/'manifest.json'
    while args.wait and not path.exists():time.sleep(10)
    manifest=json.loads(path.read_text());snapshot=data/'source_snapshot';snapshot.mkdir(exist_ok=True)
    for name,expected in manifest['source_sha256'].items():
        source=ROOT/name;payload=source.read_bytes()
        assert hashlib.sha256(payload).hexdigest()==expected,('Source changed before archival',name)
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==payload,('Archive cannot be overwritten',name)
        else:dest.write_bytes(payload)
    print('Archived exact candidate sources:',snapshot,flush=True)
    if args.wait:
        while not all((Path(j['output'])/'bridge.complete').exists() and (Path(j['output'])/'unity.complete').exists() for j in manifest['jobs']):time.sleep(10)
    changed=[name for name,h in manifest['source_sha256'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    assert not changed,('Candidate changed during execution',changed)
    subprocess.run([sys.executable,str(Path(__file__).parent/'analyze_robust.py'),str(data)],check=True)
    (data/'source-freeze-check.json').write_text(json.dumps(dict(status='passed',checked_files=len(manifest['source_sha256']),manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),indent=2)+'\n')
    print('Candidate sources unchanged through completion; analysis saved.',flush=True)


if __name__=='__main__':main()
