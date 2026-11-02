"""Removes leader speed from the control stack for the vision-only arms.

sanitize() runs on every state packet before ANY consumer sees it and overwrites
the leader fields, so production feed-forward, blind cruise and the range/speed
law all receive the arm's vision estimate instead of telemetry.

  on_vo          KF: VisionRangeTracker (camera + own speed)
  on_pv          as on_vo; own speed from OwnSpeedModel, heading removed (camera + own commands only)
  off_short_vo   production Kalman-OFF: v_leader = v_own + (range rate)/kappa from the EMA tracker, low-passed
  raw_nogate_vo  no filtering: v_leader = v_own, so v_cmd = v_own + KP*(r - R_ref)
  off_short_pv   as off_short_vo; own speed from OwnSpeedModel, heading removed (Kalman OFF counterpart of on_pv)
  on_zero, off_short_zero  telemetry simply missing (0), no replacement (literal removal)
"""
import robust_hooks
import rs_hooks
from ego_tracker import EgoTuning
from vo_mode import MODE, FD_TAU_S, LEADER_ACCEL_DENSITY
from vision_only_tracker import VisionRangeTracker, OwnSpeedModel
from usv.state import boat_comm_states

KAPPA = 22.0/25.6
_estimate = {'Left': None, 'Right': None}
_filtered_at = {'Left': None, 'Right': None}
_own_model = {'Left': OwnSpeedModel(), 'Right': OwnSpeedModel()}


class TunedVisionTracker(VisionRangeTracker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, ego_tuning=EgoTuning(leader_accel_density=LEADER_ACCEL_DENSITY), **kwargs)


if MODE in ('on_vo', 'on_pv'):
    rs_hooks.FusionRangeTracker = TunedVisionTracker


def _own(side):
    return float(boat_comm_states.get(side, {}).get('speed_mps', 0.0))


def _refresh(state, name, now, measured):
    if name is None or not name.endswith('Front'):
        return
    side = rs_hooks._side(name)
    tracker = state.get('_robust_tracker')
    if MODE in ('on_vo', 'on_pv'):
        if isinstance(tracker, VisionRangeTracker) and tracker.y is not None:
            _estimate[side] = tracker.leader_speed()
    elif MODE == 'raw_nogate_vo':
        _estimate[side] = _own(side)
    elif MODE in ('off_short_vo', 'off_short_pv') and measured:
        rng = state.get('range_estimate')
        if rng is not None:
            raw = max(0.0, _own(side)+float(rng[1])/KAPPA)
            last, at = _estimate[side], _filtered_at[side]
            alpha = 1.0 if last is None or at is None else min(1.0, max(0.0, now-at)/FD_TAU_S)
            _estimate[side] = raw if last is None else last+alpha*(raw-last)
            _filtered_at[side] = float(now)


def update(state, center_offset, center_y_norm, area, current_time, *args, **kwargs):
    result = rs_hooks.update(state, center_offset, center_y_norm, area, current_time, *args, **kwargs)
    _refresh(state, rs_hooks._name(state), current_time, True)
    return result


def coast(state, current_time):
    result = rs_hooks.coast(state, current_time)
    _refresh(state, rs_hooks._name(state), current_time, False)
    return result


def sanitize(side, state, now):
    state = dict(state)
    for key in ['leader_x', 'leader_z', 'leader_yaw', 'leader_forward_x', 'leader_forward_z']:
        state[key] = 0.0
    if MODE in ('on_pv', 'off_short_pv'):
        state['speed'] = _own_model[side].v
        state['yaw'] = 0.0
        state['x'] = state['z'] = 0.0
    if MODE in ('on_zero', 'off_short_zero'):
        state['leader_speed'] = 0.0
    else:
        est = _estimate[side]
        state['leader_speed'] = float(state.get('speed', 0.0)) if est is None else float(est)
    return state


def record_command(side, throttle, now):
    _own_model[side].step(throttle, now)
