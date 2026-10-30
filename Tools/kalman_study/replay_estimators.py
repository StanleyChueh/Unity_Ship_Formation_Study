#!/usr/bin/env python3
"""Matched-input replay of production track predictors on predeclared OFF traces.

This is not a closed-loop experiment and does not retune the filter. Both modes
receive the same selected measurements, common EMA preprocessing, and three-second
maximum coast duration. Only visible-mesh GT samples can be scored.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'Experiments/KalmanStudy/v2'
REPORT=ROOT/'Documentation/KalmanStudy'
sys.path.insert(0,str(ROOT/'Assets'))


def main():
    from usv import vision,state
    manifest=json.loads((DATA/'manifest.json').read_text());records=[]
    for job in manifest['jobs']:
        if job['arm']!='off':continue
        rows=[json.loads(x) for x in (Path(job['output'])/'steps.jsonl').read_text().splitlines()]
        for enabled in [False,True]:
            state.runtime_settings['enable_kalman_filter']=enabled
            errors=[];area_errors=[];ages=[];unscorable=0
            for side,key,index in [('Left','left_boxes',1),('Right','right_boxes',2)]:
                track=state.make_track_state(1.0);previous_yaw=None;previous_time=None;ego_rate=0;ego_speed=0
                for r in rows:
                    now=1000+r['sim_time'];measurement=r['selected'][side+'Front'];box=measurement['bbox']
                    pose=r['boats'][index]
                    if box:
                        offset=measurement['offset'];area=measurement['area']
                        if track['last_detection_time']>0:
                            offset=vision.blend_value(track['last_known_offset'],offset,vision.TRACK_OFFSET_ALPHA)
                            area=vision.blend_value(track['last_known_area'],area,vision.TRACK_AREA_ALPHA)
                        vision.update_track_prediction(track,offset,(box[1]+box[3])/2/r['height'],area,now,
                                                       ego_speed_mps=ego_speed,ego_yaw_rate_dps=ego_rate,
                                                       det_conf=measurement.get('confidence',1.0))
                        track.update(last_known_offset=offset,last_known_area=area,last_detection_time=now)
                    elif track['last_detection_time']>0:
                        age=now-track['last_detection_time']
                        if age<=3+1e-6:
                            vision.coast_track_prediction(track,now)
                            if r['t']>=15:
                                gt=next((b for b in r[key] if b['id']==1),None)
                                if gt:
                                    gt_offset=2*(gt['x']+gt['w']/2)/r['width']-1
                                    errors.append(abs(track['predicted_offset']-gt_offset));ages.append(age)
                                    area_errors.append(abs(track['predicted_area']-gt['w']*gt['h'])/(gt['w']*gt['h']))
                                else:unscorable+=1
                        else:
                            track['kf']=None;track['track_prev_measurement_time']=0;track['prediction_confidence']=0
                    if previous_yaw is not None:
                        delta=(pose['yaw']-previous_yaw+180)%360-180;ego_rate=delta/(now-previous_time)
                    previous_yaw=pose['yaw'];previous_time=now;ego_speed=pose['speed']
            records.append(dict(case=job['case'],seed=job['seed'],kalman=enabled,scored_samples=len(errors),
                                missing_gt_samples=unscorable,offset_mae=float(np.mean(errors)) if errors else None,
                                area_relative_mae=float(np.mean(area_errors)) if area_errors else None,
                                mean_gap_age_s=float(np.mean(ages)) if ages else None,
                                source_trajectory=job['output'],coast_limit_s=3.0))
    (REPORT/'matched-replay.json').write_text(json.dumps(dict(
        description='Production predictor replay, not a pure Kalman-equations benchmark. Identical selected measurements and EMA inputs from OFF trajectories; matched 3 s lifetime; scoring only during missing-measurement frames with visible-mesh ground truth.',
        records=records),indent=2)+'\n')
    print('Saved',len(records),'matched predictor replays')


if __name__=='__main__':main()
