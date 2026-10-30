#!/usr/bin/env python3
"""Read this session's local quota event; preserve an automatic handoff checkpoint.

Reads only token_count/rate_limits metadata, never exports conversation contents
or authentication files. Does not terminate experiments or edit frozen sources.
"""
import argparse
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'Documentation/KalmanStudy'


def quota():
    thread=os.environ.get('CODEX_THREAD_ID')
    if not thread:return None
    files=list(Path('/home/stanley/.codex/sessions').rglob('*'+thread+'*.jsonl'))
    if not files:return None
    p=max(files,key=lambda p:p.stat().st_mtime)
    with p.open('rb') as f:
        f.seek(max(0,p.stat().st_size-1000000));data=f.read().decode('utf8',errors='replace')
    found=None
    for line in data.splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        x=r.get('payload',{})
        if x.get('type')=='token_count' and x.get('rate_limits'):
            primary=x['rate_limits'].get('primary') or {}
            if primary.get('window_minutes')==300:
                found=dict(timestamp=r.get('timestamp'),used_percent=primary['used_percent'],
                           remaining_percent=100-primary['used_percent'],resets_at=primary.get('resets_at'))
    return found


def snapshot(q):
    batches=[]
    root=ROOT/'Experiments/KalmanStudy'
    for name in ['v2','robust_development/d01','robust_development/d02']:
        data=root/name;p=data/'manifest.json'
        if not p.exists():batches.append(dict(batch=name,status='not started'));continue
        m=json.loads(p.read_text());complete=[];partial=[]
        for j in m['jobs']:
            d=Path(j['output'])
            if (d/'bridge.complete').exists() and (d/'unity.complete').exists():complete.append(d.name)
            elif d.exists():
                lines=(d/'python.log').read_text(errors='replace').splitlines() if (d/'python.log').exists() else []
                partial.append(dict(run=d.name,last_log=lines[-1] if lines else None))
        batches.append(dict(batch=name,completed=len(complete),planned=len(m['jobs']),active_or_partial=partial,
                            source_freeze_check=(data/'source-freeze-check.json').exists()))
    native=root/'v2/realtime/runs.json'
    state=dict(updated_local=time.strftime('%Y-%m-%d %H:%M:%S %Z'),quota=q,batches=batches,
               original_report_finalized=(REPORT/'legacy-finalization.complete').exists(),native_original_pair_complete=native.exists(),
               instructions='Read RESUME.md and RESUME_KALMAN_STUDY.md. Inspect existing processes before launching. Preserve all failed results and frozen sources. No stronger held-out evaluation or production deployment has been completed.')
    (REPORT/'LIVE_STATE.json').write_text(json.dumps(state,indent=2)+'\n')
    if q and q['remaining_percent']<=3:
        (REPORT/'QUOTA_HANDOFF_REQUIRED.json').write_text(json.dumps(state,indent=2)+'\n')
    return state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    while True:
        q=quota();s=snapshot(q)
        if not args.watch or q and q['remaining_percent']<=3:
            print(json.dumps(s,indent=2),flush=True);return
        time.sleep(10)

if __name__=='__main__':main()
