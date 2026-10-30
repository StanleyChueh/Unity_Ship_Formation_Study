#!/usr/bin/env python3
"""Summarize every completed replacement run, without dropping failed outcomes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from analyze import ROOT, load, traces, summary, paired_table


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--allow-partial',action='store_true')
    args=parser.parse_args();data=args.directory.resolve();manifest=json.loads((data/'manifest.json').read_text())
    records=[];incomplete=[]
    for job in manifest['jobs']:
        p=Path(job['output'])
        if not ((p/'bridge.complete').exists() and (p/'unity.complete').exists()):
            incomplete.append(str(p));continue
        rows=load(job);trace=traces(rows,job);records.append(summary(job,rows,trace))
    if incomplete and not args.allow_partial:raise RuntimeError(f'{len(incomplete)} incomplete runs: no final analysis')
    table=paired_table(records)
    for row in table:
        base={r['seed']:r for r in records if r['case']==row['case'] and r['arm']=='off'}
        active={r['seed']:r for r in records if r['case']==row['case'] and r['arm']=='on'}
        seeds=row['seeds']
        row['off_gap_rmse_m']=float(np.mean([base[s]['scheduled_gap_rmse_m'] for s in seeds])) if all(base[s]['scheduled_gap_rmse_m'] is not None for s in seeds) else None
        row['on_gap_rmse_m']=float(np.mean([active[s]['scheduled_gap_rmse_m'] for s in seeds])) if all(active[s]['scheduled_gap_rmse_m'] is not None for s in seeds) else None
    result=dict(stage=manifest['stage'],complete=not incomplete,completed=len(records),planned=len(manifest['jobs']),
                source_manifest_sha256=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),
                matrix=table,run_results=records,incomplete=incomplete,
                interpretation='Replacement ON vs matched replacement EMA OFF: shared raw measurements pipeline, log area, 3s coast and controller. Closed-loop trajectories and hence subsequent detector images may differ. Development runs do not constitute held-out evidence.')
    (data/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    if records:
        with (data/'run-results.csv').open('w') as f:
            keys=[k for k in records[0] if k!='events'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in records)
    lines=[f'# Replacement tracker: {manifest["stage"]}', '',
           f'{len(records)}/{len(manifest["jobs"])} planned runs complete. OFF is the matched EMA comparator, not the original production OFF.','',
           '| Case | Pairs | EMA OFF RMSE m | Robust KF ON RMSE m | Paired reduction | ON wins | OFF / ON IoU |','|---|---:|---:|---:|---:|---:|---:|']
    for r in table:
        lines.append(f'| {r["case"]} | {r["n_pairs"]} | {r["baseline_rmse_m"]:.2f} | {r["treatment_rmse_m"]:.2f} | {r["paired_improvement_pct"]:+.1f}% | {r["wins"]}/{r["n_pairs"]} | {r["baseline_mean_iou"]:.3f} / {r["treatment_mean_iou"]:.3f} |')
    (data/'MATRIX.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))


if __name__=='__main__':main()
