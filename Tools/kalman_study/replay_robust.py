#!/usr/bin/env python3
"""Development replay only: matched measurements from saved OFF trajectories."""
import json
from pathlib import Path
import numpy as np
from robust_tracker import RobustTracker
from analyze import DATA, REPORT


def evaluate(path):
    job=json.loads((path/'job.json').read_text())
    rows=[json.loads(line) for line in (path/'steps.jsonl').read_text().splitlines()]
    results=[]
    for kalman in [False,True]:
        for side,key in [('Left','left_boxes'),('Right','right_boxes')]:
            tracker=None;errors={False:[],True:[]};areas={False:[],True:[]}
            for row in rows:
                now=row['sim_time'];measurement=row['selected'][side+'Front']
                if measurement['bbox']:
                    if tracker is None or now-tracker.last_seen>3.00001:tracker=RobustTracker(kalman)
                    tracker.observe(measurement['offset'],measurement['area'],now,measurement.get('confidence',1))
                elif tracker and now-tracker.last_seen<=3.00001:tracker.predict_to(now,missing=True)
                else:tracker=None
                gt=next((b for b in row[key] if b['id']==1),None)
                if tracker and gt and row['t']>=15:
                    missing=measurement['bbox'] is None
                    offset,_,area,_=tracker.state()
                    truth=2*(gt['x']+gt['w']/2)/row['width']-1
                    errors[missing].append((offset-truth)**2)
                    areas[missing].append(abs(np.log(area/(gt['w']*gt['h']))))
            for missing in [False,True]:
                results.append(dict(case=job['case'],seed=job['seed'],kalman=kalman,side=side,missing=missing,
                    samples=len(errors[missing]),offset_rmse=float(np.sqrt(np.mean(errors[missing]))) if errors[missing] else None,
                    log_area_mae=float(np.mean(areas[missing])) if areas[missing] else None))
    return results


def main():
    results=[]
    for path in sorted((DATA/'runs').glob('*_off')):
        if (path/'bridge.complete').exists():results+=evaluate(path)
    (REPORT/'robust-development-replay.json').write_text(json.dumps(results,indent=2)+'\n')
    for case in sorted({r['case'] for r in results}):
        print(case)
        for missing in [False,True]:
            line=[]
            for kalman in [False,True]:
                selected=[r for r in results if r['case']==case and r['missing']==missing and r['kalman']==kalman and r['samples']]
                n=sum(r['samples'] for r in selected)
                if n:line.append(('KF' if kalman else 'EMA',n,round(float(np.sqrt(sum(r['samples']*r['offset_rmse']**2 for r in selected)/n)),4)))
            print('missing' if missing else 'fresh',line)

if __name__=='__main__':main()
