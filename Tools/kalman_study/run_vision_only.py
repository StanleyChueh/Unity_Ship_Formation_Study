#!/usr/bin/env python3
"""Vision-only arms (vo_hooks.py): can the fleet hold formation without leader speed?

Runs on the unchanged run_d04.py + run_weather_v2.py stack (detector v2, lap and
weather cases). Each arm is patched as its telemetry-based base arm, then the state
packet is sanitized at the top of process_boat_vision_based, so no leader field
reaches any consumer. `on_rs` stays as the telemetry reference.
"""
import hashlib
import shutil

import run_weather_v2  # noqa: F401  (detector v2 + L/WL cases)
import run_d04
import run_candidate as rc

BASE = dict(on_vo='on_rs', on_pv='on_rs', off_short_vo='off_short', off_short_pv='off_short', raw_nogate_vo='raw_nogate', on_zero='on_rs', off_short_zero='off_short')
FD_TAU_S = 1.0   # low-pass on the finite-difference leader-speed estimate (chosen on development seeds)
LEADER_ACCEL_DENSITY = 6.0   # (m/s^2)^2/Hz on w in the vision-only KF: lowest geomean RMSE of 0.3, 1.5, 6 on development seeds (d05_vo_tune)
# Development-only tuning variants: arm -> (mode, leader_accel_density, fd_tau_s)
VARIANTS = dict(on_vo_q03=('on_vo', 0.3, FD_TAU_S), on_vo_q6=('on_vo', 6.0, FD_TAU_S),
                off_short_vo_t03=('off_short_vo', LEADER_ACCEL_DENSITY, 0.3), off_short_vo_t3=('off_short_vo', LEADER_ACCEL_DENSITY, 3.0))
BASE.update({k: BASE[v[0]] for k, v in VARIANTS.items()})
FILES = ['vision_only_tracker.py', 'vo_hooks.py', 'rs_hooks.py', 'fusion_tracker.py', 'ego_tracker.py', 'raw_tracker.py']
run_d04.ARMS = run_d04.ARMS+list(BASE)
_patch = run_d04.patch_python
_hashes = rc.source_hashes
PARSE = 'state = json.loads(latest_data.decode("utf-8"))\n'
WRAP = '''

import vo_hooks as _vo_hooks
_vo_process = process_boat_vision_based


def process_boat_vision_based(sock, tx_port, side):
    result = _vo_process(sock, tx_port, side)
    if result:
        _vo_hooks.record_command(side, result.get("throttle", 0.0), time.time())
    return result
'''


def patch_python(project, job):
    arm = job['arm']
    _patch(project, dict(job, arm=BASE.get(arm, arm)))
    if arm not in BASE:
        return
    assets = project/'Assets'
    for name in FILES:
        shutil.copy2(run_d04.base.HERE/name, assets/name)
    mode, density, tau = VARIANTS.get(arm, (arm, LEADER_ACCEL_DENSITY, FD_TAU_S))
    (assets/'vo_mode.py').write_text(f'MODE = {mode!r}\nFD_TAU_S = {tau!r}\nLEADER_ACCEL_DENSITY = {density!r}\n')
    control = assets/'usv/control.py'
    text = control.read_text()
    assert text.count(PARSE) == 1
    text = text.replace(PARSE, PARSE+'    import vo_hooks as _vo\n    state = _vo.sanitize(side, state, time.time())\n')+WRAP
    compile(text, str(control), 'exec')
    control.write_text(text)
    if arm not in ('on_zero', 'off_short_zero'):
        vision = assets/'usv/vision.py'
        text = vision.read_text()+'import vo_hooks\nupdate_track_prediction = vo_hooks.update\ncoast_track_prediction = vo_hooks.coast\n'
        compile(text, str(vision), 'exec')
        vision.write_text(text)


def source_hashes():
    result = _hashes()
    for name in ['run_vision_only.py', 'vision_only_tracker.py', 'vo_hooks.py']:
        path = run_d04.base.HERE/name
        result['Tools/kalman_study/'+name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


rc.source_hashes = source_hashes
run_d04.patch_python = patch_python

if __name__ == '__main__':
    run_d04.main()
