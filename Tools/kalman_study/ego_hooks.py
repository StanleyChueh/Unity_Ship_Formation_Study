"""Vision adapter for candidate d03 (KF ON arm only).

Delegates to the frozen d02 adapter (robust_hooks) and only changes which
tracker it constructs for FRONT streams: an EgoRangeTracker bound to this
follower's own-speed telemetry and the controller's visual calibration area.
Side streams keep the unchanged d02 tracker. No leader telemetry, pose or ID.
"""
import robust_hooks
from robust_tracker import RobustTracker
from ego_tracker import EgoRangeTracker
from usv.state import boat_comm_states, formation_targets, vision_states

_stream = [None]


def _name(state):
    for name, candidate in vision_states.items():
        if candidate is state:
            return name
    return None


def factory(kalman=True, tuning=None):
    name = _stream[0]
    if not kalman or name is None or not name.endswith('Front'):
        return RobustTracker(kalman=kalman, tuning=tuning)
    side = 'Left' if name.startswith('Left') else 'Right'

    def own_speed():
        return boat_comm_states.get(side, {}).get('speed_mps')

    def reference_area():
        target = formation_targets.get(side, {})
        return target.get('desired_front_area') if target.get('front_visual_initialized') else None

    return EgoRangeTracker(kalman=True, tuning=tuning, ego=own_speed, reference_area=reference_area)


robust_hooks.RobustTracker = factory


def update(state, *args, **kwargs):
    _stream[0] = _name(state)
    return robust_hooks.update(state, *args, **kwargs)


def coast(state, current_time):
    _stream[0] = _name(state)
    return robust_hooks.coast(state, current_time)


posterior = robust_hooks.posterior
