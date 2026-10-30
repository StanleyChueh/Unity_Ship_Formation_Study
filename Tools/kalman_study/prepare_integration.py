#!/usr/bin/env python3
"""Prepare a reviewable production patch; never activates the candidate itself.

Run only after candidate validation. This writes a unified patch and staged files
under a requested output directory. Applying it remains an explicit subsequent
engineering step, with native-application validation still required.
"""
import argparse
import difflib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent


def replace_once(text,old,new):
    assert text.count(old)==1,repr(old[:120])
    return text.replace(old,new)


def prepare(out):
    files={}
    config=(ROOT/'Assets/usv/config.py').read_text()
    config=replace_once(config,'ENABLE_KALMAN_FILTER = True',
        'ENABLE_KALMAN_FILTER = True\n# "legacy" preserves the original tracker; "robust" uses the validated\n# common log-area pipeline, with KF ON or matched EMA OFF.\nKALMAN_TRACKER_VARIANT = "robust"')
    files['config.py']=config
    vision=(ROOT/'Assets/usv/vision.py').read_text()
    vision=replace_once(vision,'from .kalman import KalmanFilter','from .kalman import KalmanFilter\nfrom . import robust_hooks')
    anchor='def update_track_prediction(state, center_offset, center_y_norm, area, current_time, ego_speed_mps=0.0, ego_yaw_rate_dps=0.0, det_conf=1.0):\n'
    vision=replace_once(vision,anchor,anchor+
        '    if KALMAN_TRACKER_VARIANT == "robust":\n        return robust_hooks.update(state, center_offset, center_y_norm, area, current_time, ego_speed_mps, ego_yaw_rate_dps, det_conf)\n')
    anchor='    prev_time = state.get("kf_coast_time", state.get("track_prev_measurement_time", current_time))'
    vision=replace_once(vision,anchor,'    if KALMAN_TRACKER_VARIANT == "robust":\n        return robust_hooks.coast(state, current_time)\n'+anchor)
    anchor='                        if state.get("last_detection_time", 0.0) > 0.0:\n                            center_offset = blend_value(previous_offset, center_offset, TRACK_OFFSET_ALPHA)'
    vision=replace_once(vision,anchor,anchor.replace(' > 0.0:', ' > 0.0 and KALMAN_TRACKER_VARIANT != "robust":'))
    anchor='                        state["target_detected"] = True\n                        state["target_stale"] = False'
    vision=replace_once(vision,anchor,'                        if role == "front" and KALMAN_TRACKER_VARIANT == "robust":\n                            center_offset, best_area = robust_hooks.posterior(state, center_offset, best_area)\n'+anchor)
    vision=replace_once(vision,'hold_window = KF_COAST_MAX_SEC if kf_active else TRACK_HOLD_SEC',
        'hold_window = 3.0 if KALMAN_TRACKER_VARIANT == "robust" else (KF_COAST_MAX_SEC if kf_active else TRACK_HOLD_SEC)')
    vision=replace_once(vision,'if within_hold and kf_active and time_since_seen > TRACK_HOLD_SEC:',
        'if within_hold and kf_active and time_since_seen > TRACK_HOLD_SEC and KALMAN_TRACKER_VARIANT != "robust":')
    vision=replace_once(vision,'        state["kf_coast_time"] = 0.0\n\n\ndef detect_stern_wake',
        '        state["kf_coast_time"] = 0.0\n        state.pop("_robust_tracker", None)\n\n\ndef detect_stern_wake')
    files['vision.py']=vision
    control=(ROOT/'Assets/usv/control.py').read_text()
    control=replace_once(control,'if ENABLE_KALMAN_FILTER and front_visual_ref_ready and float(front_track_area_velocity) > 0.0:',
        'if (KALMAN_TRACKER_VARIANT != "robust"\n                and bool(runtime_settings.get("enable_kalman_filter", ENABLE_KALMAN_FILTER))\n                and front_visual_ref_ready and float(front_track_area_velocity) > 0.0):')
    files['control.py']=control
    files['robust_tracker.py']=(HERE/'robust_tracker.py').read_text()
    files['robust_hooks.py']=(HERE/'robust_hooks.py').read_text().replace('from robust_tracker import RobustTracker','from .robust_tracker import RobustTracker').replace('from usv.state import runtime_settings','from .state import runtime_settings')
    diffs=[]
    for name,text in files.items():
        compile(text,name,'exec')
        original=ROOT/'Assets/usv'/name
        old=original.read_text() if original.exists() else ''
        diffs.extend(difflib.unified_diff(old.splitlines(keepends=True),text.splitlines(keepends=True),fromfile='a/Assets/usv/'+name if original.exists() else '/dev/null',tofile='b/Assets/usv/'+name))
        path=out/'Assets/usv'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    (out/'candidate.patch').write_text(''.join(diffs))
    print('Prepared patch only; production unchanged:',out/'candidate.patch')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('/tmp/kalman-integration-review'))
    args=parser.parse_args();prepare(args.output.resolve())

if __name__=='__main__':main()
