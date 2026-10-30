#!/usr/bin/env python3
"""Audit native-app sampled RGB and pre-suppression detector selections."""
import hashlib
import json
from pathlib import Path
from analyze import ROOT,REPORT,overlap


def main():
    data=ROOT/'Experiments/KalmanStudy/v2/realtime'
    manifest=json.loads((data/'protocol-manifest.json').read_text())
    changed=[p for p,h in manifest['source_sha256'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    records=[]
    for run in json.loads((data/'runs.json').read_text()):
        path=Path(run['output']);gt=[json.loads(x) for x in (path/'ground-truth.jsonl').read_text().splitlines()]
        detections=[json.loads(x) for x in (path/'selected-targets.jsonl').read_text().splitlines()]
        selected={(r['camera'],r['hash']):r for r in detections if r.get('hash')}
        matched=correct=wrong=with_box=0
        for r in gt:
            assert hashlib.sha256((path/r['image']).read_bytes()).hexdigest()==r['hash']
            for b in r['boxes']:
                assert b['x']>=0 and b['y']>=0 and b['x']+b['w']<=r['width'] and b['y']+b['h']<=r['height']
            sample=selected.get((r['camera'],r['hash']))
            if sample:
                matched+=1;box=sample.get('bbox')
                if box:
                    with_box+=1;best=max(r['boxes'],key=lambda b:overlap(box,b),default=None)
                    if best and overlap(box,best)>.1:
                        correct+=best['id']==1;wrong+=best['id']!=1
        metrics=run['metrics'][0]
        records.append(dict(arm=run['model'],sampled_rgb_sha256_verified=len(gt),
            sampled_frames_matched_to_processing=matched,matched_pre_suppression_selected_boxes=with_box,
            pre_suppression_correct_leader=correct,pre_suppression_wrong_identity=wrong,
            mean_three_boat_rms_m=float(metrics['mean_per_boat_rms_m']),mean_formation_iou=float(metrics['mean_formation_iou']),
            metrics_definition='Original app summary:3-boat/equilateral target, descriptive1pair. Global value repeated in side rows is not another replicate.'))
    result=dict(source_check='passed',records=records,
        selection_stage='selected-targets.jsonl records the candidate BEFORE scheduled suppression and BEFORE control updates. It must not be presented as the bbox actually used during a suppressed interval.',
        sampling='RGB/identity sampled every2s; asynchronous processing can skip sampled frames. Hash-matched subset is diagnostic, not an unbiased detection-rate estimate.',
        coordinate_convention='Native observer already uses height-1-y1. No360px correction is applied here.')
    (REPORT/'native-app-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Native application: original Kalman descriptive check','',
        'One asynchronous ON/OFF pair; use the original application metric, not the fixed-step follower-only RMSE.','',
        '| Arm | Original3-boat mean RMS m | Formation IoU | Sampled RGB hashes checked |','|---|---:|---:|---:|']
    for r in records:lines.append(f'| {r["arm"]} | {r["mean_three_boat_rms_m"]:.2f} | {r["mean_formation_iou"]:.3f} | {r["sampled_rgb_sha256_verified"]} |')
    lines+=['','The original ON system was worse in this pair. It does not establish a population effect.', '',result['selection_stage'], '',result['sampling']]
    (REPORT/'NATIVE_RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
