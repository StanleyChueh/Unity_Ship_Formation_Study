"""Vision adapter for the d04 range/speed arms (`on_rs` KF, `off_rs` EMA).

Delegates to the frozen d02 adapter (robust_hooks) and additionally publishes
state['range_estimate'] = (range_m, range_rate_mps) for FRONT streams, which the
shared d04 range/speed control law consumes. KF arm: FusionRangeTracker (vision
+ own speed + leader-speed telemetry, innovation gating). EMA arm: the unchanged
matched EMA tracker; range = c/sqrt(EMA area), rate from its smoothed log-area
derivative (vision only). Same pinhole calibration c in both arms.
"""
import math
import robust_hooks
from robust_tracker import RobustTracker
from fusion_tracker import FusionRangeTracker
from usv.state import boat_comm_states, formation_targets, vision_states

FORMATION_RANGE_M = 25.6
_stream = [None]


def _name(state):
    for name, candidate in vision_states.items():
        if candidate is state:
            return name
    return None


def _side(name):
    return 'Left' if name.startswith('Left') else 'Right'


def _reference_area(side):
    target = formation_targets.get(side, {})
    return target.get('desired_front_area') if target.get('front_visual_initialized') else None


def factory(kalman=True, tuning=None):
    name = _stream[0]
    if not kalman or name is None or not name.endswith('Front'):
        return RobustTracker(kalman=kalman, tuning=tuning)
    side = _side(name)
    return FusionRangeTracker(kalman=True, tuning=tuning,
                              ego=lambda: boat_comm_states.get(side, {}).get('speed_mps'),
                              leader=lambda: boat_comm_states.get(side, {}).get('leader_speed_mps'),
                              reference_area=lambda: _reference_area(side))


robust_hooks.RobustTracker = factory


def _publish_range(state, name):
    if name is None or not name.endswith('Front'):
        return
    tracker = state.get('_robust_tracker')
    if tracker is None or tracker.x is None:
        state['range_estimate'] = None
        return
    if isinstance(tracker, FusionRangeTracker) and tracker.y is not None:
        state['range_estimate'] = (float(tracker.y[0]), tracker.range_rate())
        return
    ref = _reference_area(_side(name))
    if ref is None or ref <= 1.0:
        state['range_estimate'] = None
        return
    c = FORMATION_RANGE_M*math.sqrt(ref)
    r = c/math.exp(tracker.x[1, 0]/2.0)
    state['range_estimate'] = (float(r), float(-0.5*r*tracker.x[1, 1]))


def update(state, *args, **kwargs):
    name = _name(state)
    _stream[0] = name
    result = robust_hooks.update(state, *args, **kwargs)
    _publish_range(state, name)
    return result


def coast(state, current_time):
    name = _name(state)
    _stream[0] = name
    result = robust_hooks.coast(state, current_time)
    _publish_range(state, name)
    return result


posterior = robust_hooks.posterior
