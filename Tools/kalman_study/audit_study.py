#!/usr/bin/env python3
"""Verify completeness, paired interventions, source hashes and frame integrity."""
import difflib
import hashlib
import json
from pathlib import Path

from analyze import DATA,REPORT,intended_gap,load

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((DATA/'manifest.json').read_text());jobs=manifest['jobs']
    changed=[name for name,value in manifest['source_sha256'].items() if sha(ROOT/name)!=value]
    assert not changed,('Source changed after freeze',changed)
    assert len(jobs)==60
    total_steps=0;total_frames=0;groups={};per_run=[]
    for job in jobs:
        rows=load(job);total_steps+=len(rows)
        count=0
        for row in rows:
            assert row['width']==1280 and row['height']==720
            for side in ['Left','Right']:
                name=side+'Front';path=Path(job['output'])/'frames'/f'{row["step"]:05d}_{name}.jpg'
                assert sha(path)==row['image_sha256'][name],path
                total_frames+=1
                if job['arm'].startswith('off'):assert 'kf_state' not in row['status'][side]
                if intended_gap(row['t'],job):
                    assert row['selected'][name]['bbox'] is None
                    count+=1
                if job['gap']==0:assert not row['selected'][name]['forced_loss']
            for key in ['left_boxes','right_boxes']:
                for box in row[key]:
                    assert box['id'] in [1,2,3] and box['pixels']>=16
                    assert 0<=box['x']<1280 and 0<=box['y']<720 and box['x']+box['w']<=1280 and box['y']+box['h']<=720
        assert rows[-1]['t']>=59.99
        per_run.append(dict(case=job['case'],seed=job['seed'],arm=job['arm'],steps=len(rows),scheduled_censored_camera_frames=count))
        groups.setdefault((job['case'],job['seed']),{})[job['arm']]=(job,rows)
    pairs=[]
    for (case,seed),arms in groups.items():
        on_job,on=arms['on'];off_job,off=arms['off']
        allowed={'output','arm'}
        assert all(on_job[k]==off_job[k] for k in on_job if k not in allowed)
        assert len(on)==len(off)
        assert [r['t'] for r in on]==[r['t'] for r in off]
        prefix_on=[r for r in on if r['t']<0];prefix_off=[r for r in off if r['t']<0]
        calibration_delta=max(abs(a['boats'][i][key]-b['boats'][i][key]) for a,b in zip(prefix_on,prefix_off) for i in range(3) for key in ['x','z'])
        assert calibration_delta<1e-5,(case,seed,calibration_delta)
        leader_delta=max(abs(a['boats'][0][key]-b['boats'][0][key]) for a,b in zip(on,off) for key in ['x','z'])
        wave_delta=max(abs(a['wave']-b['wave']) for a,b in zip(on,off))
        pairs.append(dict(case=case,seed=seed,initial_planar_pose_difference_m=calibration_delta,
                          leader_max_planar_difference_m=leader_delta,fixed_probe_max_height_difference_m=wave_delta,
                          initial_frame_hash_matches=sum(a['image_sha256']==b['image_sha256'] for a,b in zip(prefix_on,prefix_off)),
                          initial_frames=len(prefix_on)))
    assert len(pairs)==24
    clone=Path('/tmp/usv-kalman-study/project')
    supplementary={}
    for folder in ['Assets/Resources','Assets/DatasetCapture','Assets/SUIMONO - WATER SYSTEM 2/SHADERS']:
        for path in (clone/folder).rglob('*'):
            if path.is_file() and path.suffix in ['.cs','.shader','.cginc']:
                supplementary[str(path.relative_to(clone))]=sha(path)
    for name in ['vision.py','control.py','helpers.py']:
        original=(ROOT/'Assets/usv'/name).read_text().splitlines(keepends=True)
        executed=(clone/'Assets/usv'/name).read_text().splitlines(keepends=True)
        (REPORT/('isolated-'+name+'.patch')).write_text(''.join(difflib.unified_diff(original,executed,fromfile='production/'+name,tofile='isolated/'+name)))
    original=(ROOT/'Assets/SimpleMove.cs').read_text();executed=(clone/'Assets/SimpleMove.cs').read_text()
    assert executed==original.replace('Input.GetAxis("Vertical")','0.0f').replace('Input.GetAxis("Horizontal")','0.0f')
    (REPORT/'isolated-keyboard.patch').write_text(''.join(difflib.unified_diff(original.splitlines(keepends=True),executed.splitlines(keepends=True),fromfile='production/SimpleMove.cs',tofile='isolated/SimpleMove.cs')))
    result=dict(study_version='v2',jobs=len(jobs),paired_primary_episodes=len(pairs),source_hash_check='passed',
                checked_steps=total_steps,checked_saved_frame_sha256=total_frames,
                id_box_coordinate_correction=dict(encoded_origin_y=359,expected_origin_y=719,derived_y_shift_px=360,raw_logs_unchanged=True,explanation='Frozen 720p harness retained a 360p ID-box y-origin constant. All logged ID boxes are translated down by360px in the analysis reader; x/size/pixels and world-pose metrics are unchanged.'),
                scheduled_censorship_check='passed',off_arms_kalman_absence_check='passed',
                paired_initial_pose_check='passed',camera_resolution_check='passed',
                per_run=per_run,pairs=pairs,compiled_shader_source_sha256=supplementary,
                note='Private-copy diffs are from the final run. Arm-specific hold-window changes are defined in the frozen patch generator and job files. Ground truth is evaluation-only except the pre-existing leader/ego telemetry supplied to the production controller.')
    (REPORT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (REPORT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Audit passed:',len(jobs),'jobs,',total_steps,'steps,',total_frames,'frame checksums')


if __name__=='__main__':main()
