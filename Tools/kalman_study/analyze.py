#!/usr/bin/env python3
"""Compute paired study outcomes and audit-ready tables from raw simulator logs."""
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'Experiments/KalmanStudy/v2'
REPORT=ROOT/'Documentation/KalmanStudy'


def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))*0.5 if len(poly)>2 else 0.0


def ccw(poly):
    signed=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1]))
    return poly if signed>=0 else poly[::-1]


def triangle_iou(a,b):
    polygon=ccw(a);clip=ccw(b)
    for edge,next_edge in zip(clip,clip[1:]+clip[:1]):
        before=polygon;polygon=[]
        if not before:break
        def side(p):return (next_edge[0]-edge[0])*(p[1]-edge[1])-(next_edge[1]-edge[1])*(p[0]-edge[0])
        previous=before[-1];old_side=side(previous)
        for current in before:
            new_side=side(current)
            if (new_side>=0)!=(old_side>=0):
                frac=old_side/(old_side-new_side)
                polygon.append((previous[0]+frac*(current[0]-previous[0]),previous[1]+frac*(current[1]-previous[1])))
            if new_side>=0:polygon.append(current)
            previous=current;old_side=new_side
    intersection=area(polygon);union=area(a)+area(b)-intersection
    return intersection/union if union>1e-10 else 0.0


def overlap(a,b):
    x0=max(a[0],b['x']);y0=max(a[1],b['y']);x1=min(a[2],b['x']+b['w']);y1=min(a[3],b['y']+b['h'])
    intersection=max(0,x1-x0)*max(0,y1-y0)
    union=max(0,a[2]-a[0])*max(0,a[3]-a[1])+b['w']*b['h']-intersection
    return intersection/union if union else 0


def intended_gap(t,job):
    if not job['gap'] or t<20:return False
    interval=100 if job['case'].startswith('C7') else 18
    return (t-20)%interval<job['gap']-1e-7


def load(job):
    path=Path(job['output'])
    assert (path/'unity.complete').exists() and (path/'bridge.complete').exists(),path
    rows=[json.loads(s) for s in (path/'steps.jsonl').read_text().splitlines()]
    # The frozen 720p StudyRig serializes ID box y as 359-y1 instead of
    # height-1-y1. Correct only this derived coordinate; never rewrite raw logs.
    # All current fixed-step jobs reuse that binary. A future corrected binary
    # must set id_box_encoded_y_origin=719 in its job/manifest.
    encoded_origin=job.get('id_box_encoded_y_origin',359)
    for row in rows:
        shift=row['height']-1-encoded_origin
        row['_id_box_y_shift_px']=shift
        for key in ['left_boxes','right_boxes']:
            for box in row[key]:
                box['_raw_y']=box['y']
                box['y']+=shift
    assert len(rows)>600 and all(r['step']==i for i,r in enumerate(rows)),path
    assert all(abs((b['t']-a['t'])-0.1)<1e-6 for a,b in zip(rows,rows[1:])),path
    return rows


def traces(rows,job):
    result=[]
    for r in rows:
        leader,left,right=r['boats'];fx,fz=leader['fx'],leader['fz'];norm=math.hypot(fx,fz);fx/=norm;fz/=norm
        ideals=[(leader['x'],leader['z'])];squared=[]
        for boat,side in [(left,'left'),(right,'right')]:
            back,lat=r[side+'_back'],r[side+'_side']
            target=(leader['x']+fx*back+fz*lat,leader['z']+fz*back-fx*lat)
            ideals.append(target);squared.append((boat['x']-target[0])**2+(boat['z']-target[1])**2)
        actual=[(p['x'],p['z']) for p in [leader,left,right]]
        separation=min(math.dist(actual[i],actual[j]) for i,j in [(0,1),(0,2),(1,2)])
        item=dict(t=r['t'],step=r['step'],rms=math.sqrt(np.mean(squared)),left_error=math.sqrt(squared[0]),right_error=math.sqrt(squared[1]),
                  iou=triangle_iou(actual,ideals),separation=separation,wave=r['wave'],forced=intended_gap(r['t'],job))
        for side,key in [('Left','left_boxes'),('Right','right_boxes')]:
            state=r['status'][side];selection=r['selected'].get(side+'Front',{});bbox=selection.get('bbox')
            item[side+'_fresh']=bool(state['target_detected'] and not state['target_stale'])
            item[side+'_stale']=bool(state['target_stale']);item[side+'_lost']=not bool(state['target_detected'])
            best=max(r[key],key=lambda b:overlap(bbox,b),default=None) if bbox else None
            matched=best if best and overlap(bbox,best)>0.1 else None
            item[side+'_correct']=bool(matched and matched['id']==1)
            item[side+'_wrong_identity']=bool(matched and matched['id']!=1)
            if item['forced']:assert bbox is None,(job['case'],r['t'],side,'censorship failed')
        result.append(item)
    return result


def events(trace,job):
    if not job['gap']:return []
    out=[]
    starts=[20] if job['case'].startswith('C7') else [20,38,56]
    times=np.array([r['t'] for r in trace]);errors=np.array([r['rms'] for r in trace])
    for start in starts:
        end=start+job['gap']
        if end>job['duration']:continue
        before=errors[(times>=start-2)&(times<start)];baseline=float(np.median(before));threshold=baseline+2
        followup=min(10,job['duration']-end);recovery=None
        for i,t in enumerate(times):
            if t<end or t+0.9>end+followup:continue
            if len(errors[i:i+10])==10 and np.all(errors[i:i+10]<=threshold):recovery=float(t+0.9-end);break
        gap=errors[(times>=start)&(times<end)]
        out.append(dict(start=start,end=end,pregap_median_m=baseline,recovery_threshold_m=threshold,
                        gap_rmse_m=float(np.sqrt(np.mean(gap**2))),gap_peak_m=float(np.max(gap)),
                        peak_error_growth_m=float(np.max(gap)-baseline),
                        excess_gap_rmse_m=float(np.sqrt(np.mean(np.maximum(gap-baseline,0)**2))),
                        recovery_confirmed_s=recovery,recovery_censored=recovery is None,followup_s=followup))
    return out


def summary(job,rows,trace):
    selected=[r for r in trace if 15<=r['t']<=job['duration']]
    poses=[r for r in rows if 15<=r['t']<=job['duration']]
    result={k:job[k] for k in ['case','seed','arm','sea','rain','dark','fog','motion','radius','gap']}
    result['id_box_y_correction_px']=rows[0].get('_id_box_y_shift_px',0)
    result.update(rmse_m=float(np.sqrt(np.mean([r['rms']**2 for r in selected]))),mean_iou=float(np.mean([r['iou'] for r in selected])),
                  p95_error_m=float(np.percentile([r[k] for r in selected for k in ['left_error','right_error']],95)),
                  peak_follower_error_m=max(r[k] for r in selected for k in ['left_error','right_error']),
                  broken_pct=100*float(np.mean([r['rms']>10 for r in selected])),min_separation_m=min(r['separation'] for r in selected),
                  wave_hs_4std_m=4*float(np.std([r['wave'] for r in selected])),
                  max_abs_roll_deg=max(abs(b['roll']) for r in poses for b in r['boats'][1:]),
                  max_abs_pitch_deg=max(abs(b['pitch']) for r in poses for b in r['boats'][1:]),
                  fresh_pct=100*float(np.mean([r[s+'_fresh'] for r in selected for s in ['Left','Right']])),
                  stale_pct=100*float(np.mean([r[s+'_stale'] for r in selected for s in ['Left','Right']])),
                  lost_pct=100*float(np.mean([r[s+'_lost'] for r in selected for s in ['Left','Right']])),
                  correct_measurement_pct=100*float(np.mean([r[s+'_correct'] for r in selected for s in ['Left','Right']])),
                  wrong_identity_frames=sum(r[s+'_wrong_identity'] for r in selected for s in ['Left','Right']),
                  analysis_samples=len(selected),raw_output=job['output'])
    for key in ['steer','throttle']:
        commands=np.array([[r['controls'][s][key] for s in ['Left','Right']] for r in poses])
        result[key+'_variation_per_s']=float(np.abs(np.diff(commands,axis=0)).sum()/2/(poses[-1]['t']-poses[0]['t']))
    lengths=[]
    for side in ['Left','Right']:
        length=0
        for r in selected:
            if not r[side+'_fresh']:length+=0.1
            else:lengths.append(length);length=0
        lengths.append(length)
    result['longest_accepted_measurement_gap_s']=float(max(lengths))
    ev=events(trace,job);result['events']=ev
    gap_errors=[r['rms'] for r in selected if r['forced']]
    result['scheduled_gap_rmse_m']=float(np.sqrt(np.mean(np.square(gap_errors)))) if gap_errors else None
    result['recoveries_observed']=sum(not e['recovery_censored'] for e in ev)
    result['recoveries_censored']=sum(e['recovery_censored'] for e in ev)
    return result


def paired_table(records,baseline='off',treatment='on'):
    table=[];rng=np.random.default_rng(1970)
    for case in sorted({r['case'] for r in records}):
        base={r['seed']:r for r in records if r['case']==case and r['arm']==baseline}
        active={r['seed']:r for r in records if r['case']==case and r['arm']==treatment}
        seeds=sorted(base.keys()&active.keys())
        if not seeds:continue
        b=np.array([base[s]['rmse_m'] for s in seeds]);a=np.array([active[s]['rmse_m'] for s in seeds])
        pct=100*(b-a)/b
        boot=pct[rng.integers(0,len(pct),(10000,len(pct)))].mean(axis=1)
        row=dict(case=case,baseline=baseline,treatment=treatment,seeds=seeds,n_pairs=len(seeds),
                 baseline_rmse_m=float(b.mean()),treatment_rmse_m=float(a.mean()),
                 improvement_m=float((b-a).mean()),paired_improvement_pct=float(pct.mean()),
                 bootstrap95_low_pct=float(np.percentile(boot,2.5)),bootstrap95_high_pct=float(np.percentile(boot,97.5)),
                 seed_improvement_pct=pct.tolist(),wins=int(np.sum(a<b)),
                 baseline_mean_iou=float(np.mean([base[s]['mean_iou'] for s in seeds])),
                 treatment_mean_iou=float(np.mean([active[s]['mean_iou'] for s in seeds])),
                 baseline_fresh_pct=float(np.mean([base[s]['fresh_pct'] for s in seeds])),
                 treatment_fresh_pct=float(np.mean([active[s]['fresh_pct'] for s in seeds])),
                 baseline_broken_pct=float(np.mean([base[s]['broken_pct'] for s in seeds])),
                 treatment_broken_pct=float(np.mean([active[s]['broken_pct'] for s in seeds])))
        table.append(row)
    return table


def main():
    REPORT.mkdir(exist_ok=True)
    manifest=json.loads((DATA/'manifest.json').read_text());records=[]
    for job in manifest['jobs']:
        rows=load(job);trace=traces(rows,job);record=summary(job,rows,trace);records.append(record)
        with (Path(job['output'])/'trace.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(trace[0]));writer.writeheader();writer.writerows(trace)
    (REPORT/'run-results.json').write_text(json.dumps(records,indent=2)+'\n')
    scalar_keys=[k for k in records[0] if k!='events']
    with (REPORT/'run-results.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=scalar_keys);writer.writeheader();writer.writerows({k:r[k] for k in scalar_keys} for r in records)
    table=paired_table(records);ablations=paired_table(records,'off_matched')+paired_table(records,'on_short')
    (REPORT/'matrix.json').write_text(json.dumps(dict(primary=table,ablations=ablations,analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
    with (REPORT/'matrix.csv').open('w') as f:
        keys=[k for k in table[0] if k not in ('seeds','seed_improvement_pct')]
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows({k:r[k] for k in keys} for r in table)
    lines=['# Measured Kalman ON/OFF matrix','',
           'Positive improvement means lower RMSE with Kalman ON. Three paired seeds per case; bootstrap intervals are descriptive and have limited resolution.','',
           '| Case | OFF RMSE (m) | ON RMSE (m) | Paired improvement | Bootstrap 95% | ON wins | OFF / ON IoU |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for row in table:
        lines.append(f'| {row["case"]} | {row["baseline_rmse_m"]:.2f} | {row["treatment_rmse_m"]:.2f} | {row["paired_improvement_pct"]:+.1f}% | [{row["bootstrap95_low_pct"]:+.1f}, {row["bootstrap95_high_pct"]:+.1f}]% | {row["wins"]}/3 | {row["baseline_mean_iou"]:.3f} / {row["treatment_mean_iou"]:.3f} |')
    lines+=['','## Hold-window ablations','','| Case | Baseline | Baseline RMSE | ON RMSE | Paired improvement |','|---|---|---:|---:|---:|']
    for row in ablations:lines.append(f'| {row["case"]} | {row["baseline"]} | {row["baseline_rmse_m"]:.2f} | {row["treatment_rmse_m"]:.2f} | {row["paired_improvement_pct"]:+.1f}% |')
    (REPORT/'MATRIX.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__=='__main__':main()
